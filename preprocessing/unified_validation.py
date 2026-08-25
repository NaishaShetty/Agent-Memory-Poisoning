"""Phase 2.2: cross-dataset validation over the Unified Memory Record
(UMR) output. Streams each dataset's file (never loads all four fully
into memory at once beyond the ID-collision index, which is small
relative to full records: ~1.27M short strings).
"""
from __future__ import annotations

from pathlib import Path

from preprocessing.config import PipelineConfig
from preprocessing.io_utils import iter_jsonl, write_json
from preprocessing.unified_schema import (
    CORE_DATASETS,
    VALID_ADMISSION_STATUSES,
    VALID_FIELD_STATUSES,
    VALID_QUALITY_STATUSES,
    validate_record,
)


def _unified_path(cfg: PipelineConfig, dataset: str) -> Path:
    return cfg.processed_dir / "unified_memory" / dataset / "memory_records.jsonl"


def validate_cross_dataset(cfg: PipelineConfig) -> dict:
    """Runs schema validation on every record and the cross-dataset
    consistency checks Phase 2.2 requires. Returns a report dict in the
    same PASS/FAIL check-list style as phase1_validation_report.json, for
    consistency with the project's existing validation reporting
    convention (preprocessing/validation.py)."""
    checks = []
    seen_ids: dict[str, str] = {}  # memory_id -> dataset that first used it
    collisions: list[dict] = []
    cross_dataset_collisions: list[dict] = []
    schema_violations: list[dict] = []
    per_dataset_counts: dict[str, int] = {}
    session_ids_by_dataset: dict[str, set] = {ds: set() for ds in CORE_DATASETS}
    admission_counts: dict[str, dict] = {ds: {} for ds in CORE_DATASETS}
    origin_misuse: list[dict] = []
    quarantined_but_trusted: list[dict] = []
    field_status_violations: list[dict] = []

    for dataset in CORE_DATASETS:
        path = _unified_path(cfg, dataset)
        count = 0
        for rec in iter_jsonl(path):
            count += 1
            try:
                validate_record(rec)
            except Exception as e:
                schema_violations.append({"dataset": dataset, "memory_id": rec.get("memory_id"), "error": str(e)})
                continue

            mid = rec["memory_id"]
            if mid in seen_ids:
                entry = {"memory_id": mid, "datasets": sorted({seen_ids[mid], dataset})}
                collisions.append(entry)
                if seen_ids[mid] != dataset:
                    cross_dataset_collisions.append(entry)
            else:
                seen_ids[mid] = dataset

            if rec["source_dataset"] != dataset:
                origin_misuse.append({
                    "memory_id": mid, "file_dataset": dataset,
                    "record_source_dataset": rec["source_dataset"],
                })

            if rec["session_id"] is not None:
                session_ids_by_dataset[dataset].add(rec["session_id"])

            admission_counts[dataset][rec["admission_status"]] = (
                admission_counts[dataset].get(rec["admission_status"], 0) + 1
            )

            if rec["admission_status"] == "QUARANTINED" and rec["trusted_clean_memory"] is True:
                quarantined_but_trusted.append({"dataset": dataset, "memory_id": mid})

            bad_statuses = {
                f: s for f, s in rec.get("field_status", {}).items() if s not in VALID_FIELD_STATUSES
            }
            if bad_statuses:
                field_status_violations.append({"dataset": dataset, "memory_id": mid, "bad_statuses": bad_statuses})

        per_dataset_counts[dataset] = count

    total = sum(per_dataset_counts.values())

    checks.append({
        "name": "schema_conformance",
        "status": "PASS" if not schema_violations else "FAIL",
        "detail": {"total_checked": total, "violations": schema_violations[:20], "violation_count": len(schema_violations)},
    })
    checks.append({
        "name": "unique_memory_ids_within_dataset_and_across_datasets",
        "status": "PASS" if not collisions else "FAIL",
        "detail": {"total": total, "unique": len(seen_ids), "collisions_sample": collisions[:20]},
    })
    checks.append({
        "name": "no_cross_dataset_id_collision",
        "status": "PASS" if not cross_dataset_collisions else "FAIL",
        "detail": {"collisions_sample": cross_dataset_collisions[:20]},
    })
    checks.append({
        "name": "source_dataset_field_matches_containing_file",
        "status": "PASS" if not origin_misuse else "FAIL",
        "detail": {"violations": origin_misuse[:20], "violation_count": len(origin_misuse)},
    })
    checks.append({
        "name": "admission_status_values_are_from_known_vocabulary",
        "status": "PASS" if all(
            set(counts.keys()).issubset(VALID_ADMISSION_STATUSES) for counts in admission_counts.values()
        ) else "FAIL",
        "detail": {"admission_counts_by_dataset": admission_counts},
    })
    checks.append({
        "name": "quarantined_records_never_trusted_clean",
        "status": "PASS" if not quarantined_but_trusted else "FAIL",
        "detail": {"violations": quarantined_but_trusted},
    })
    checks.append({
        "name": "field_status_values_are_from_known_vocabulary",
        "status": "PASS" if not field_status_violations else "FAIL",
        "detail": {"violations": field_status_violations[:20], "violation_count": len(field_status_violations)},
    })
    checks.append({
        "name": "record_counts_match_phase1_processed_output",
        "status": "PASS" if _counts_match_phase1(cfg, per_dataset_counts) else "FAIL",
        "detail": {"unified_counts": per_dataset_counts},
    })

    overall_status = "PASS" if all(c["status"] == "PASS" for c in checks) else "FAIL"
    return {
        "schema_version": "1.0.0",
        "overall_status": overall_status,
        "total_records": total,
        "per_dataset_counts": per_dataset_counts,
        "checks": checks,
    }


def _counts_match_phase1(cfg: PipelineConfig, unified_counts: dict) -> bool:
    for dataset, count in unified_counts.items():
        phase1_path = cfg.processed_dir / dataset / "memory_records.jsonl"
        with phase1_path.open("r", encoding="utf-8") as f:
            phase1_count = sum(1 for line in f if line.strip())
        if phase1_count != count:
            return False
    return True


def write_validation_report(cfg: PipelineConfig) -> Path:
    report = validate_cross_dataset(cfg)
    out_path = cfg.reports_dir / "phase2_2_unified_memory_validation_report.json"
    write_json(out_path, report)
    return out_path


if __name__ == "__main__":
    from preprocessing.config import load_config

    _cfg = load_config()
    _path = write_validation_report(_cfg)
    print(f"Wrote {_path}")
