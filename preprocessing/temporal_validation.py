"""Phase 2.3: temporal consistency validation over the Unified Memory
Record (UMR) output, in the same streaming, check-list-report style as
preprocessing/unified_validation.py (Phase 2.2). Runs after
unified_validation's own checks and does not repeat them (schema
conformance already covers `normalized_timestamp`/`temporal_provenance`
type/enum correctness -- this module checks *temporal-specific*
consistency properties unified_validation.py has no reason to know about).
"""
from __future__ import annotations

import re
from pathlib import Path

from preprocessing.config import PipelineConfig
from preprocessing.io_utils import iter_jsonl, write_json
from preprocessing.temporal import (
    NORMALIZATION_POLICY_VERSION,
    VALID_TEMPORAL_PROVENANCE,
    compute_temporal_fields,
)
from preprocessing.unified_schema import CORE_DATASETS

_SESSION_ID_RE = re.compile(r"^session_(\d+)$")


def _unified_path(cfg: PipelineConfig, dataset: str) -> Path:
    return cfg.processed_dir / "unified_memory" / dataset / "memory_records.jsonl"


def validate_temporal(cfg: PipelineConfig) -> dict:
    checks = []

    provenance_violations: list[dict] = []
    fabrication_violations: list[dict] = []
    ordering_violations: list[dict] = []
    determinism_violations: list[dict] = []
    duplicate_timestamp_examples: dict[str, int] = {ds: 0 for ds in CORE_DATASETS}
    missing_handling_violations: list[dict] = []
    invalid_handling_violations: list[dict] = []
    per_dataset_counts: dict[str, int] = {}
    per_dataset_provenance_counts: dict[str, dict] = {ds: {} for ds in CORE_DATASETS}

    for dataset in CORE_DATASETS:
        path = _unified_path(cfg, dataset)
        count = 0
        # (source_file, conversation_id, session ordinal) -> last-seen
        # event_order, to check within-session ordering never regresses as
        # the file is streamed (Phase 1/2.2 write records in source order;
        # Phase 2.3 must not have reordered anything). source_file is part
        # of the key because LongMemEval's session_id can legitimately
        # repeat across its two raw files (oracle vs s_cleaned) -- Phase 1
        # dedups per-file, not globally, so a repeat is two distinct
        # session occurrences, not a regression (see
        # preprocessing/datasets/longmemeval.py).
        last_event_order: dict[tuple, int] = {}
        # last-seen (session_ordinal) per (source_file, conversation_id),
        # to check cross-session ordering is monotonic non-decreasing.
        last_session_ordinal: dict[tuple, int] = {}
        seen_source_timestamps: dict[str, str] = {}  # source_timestamp -> normalized_timestamp, for internal-consistency

        for rec in iter_jsonl(path):
            count += 1
            mid = rec.get("memory_id")

            tp = rec.get("temporal_provenance")
            per_dataset_provenance_counts[dataset][tp] = per_dataset_provenance_counts[dataset].get(tp, 0) + 1
            if tp not in VALID_TEMPORAL_PROVENANCE:
                provenance_violations.append({"dataset": dataset, "memory_id": mid, "temporal_provenance": tp})

            # No-fabrication rule (spec Test 9): a record whose source
            # gives no absolute time (timestamp_type != "absolute", or an
            # absolute claim that failed to parse) must NEVER end up with
            # temporal_provenance == source_absolute, and
            # benchmark_timestamp (when present) must never be mistaken
            # for a source-observed value (field_status is checked by
            # unified_validation.py; here we check the value-level rule).
            if tp == "source_absolute" and rec.get("normalized_timestamp") is None:
                fabrication_violations.append({"dataset": dataset, "memory_id": mid, "reason": "source_absolute provenance with no normalized_timestamp"})
            if tp != "source_absolute" and rec.get("normalized_timestamp") is not None:
                fabrication_violations.append({"dataset": dataset, "memory_id": mid, "reason": "normalized_timestamp set without source_absolute provenance"})
            if tp == "source_absolute" and rec.get("benchmark_timestamp") is not None:
                fabrication_violations.append({"dataset": dataset, "memory_id": mid, "reason": "benchmark_timestamp assigned alongside a real source_absolute value"})

            # Missing/invalid handling (spec Tests 5/7): every record with
            # timestamp_type == "unavailable" and no relative signal must
            # have normalized_timestamp == None (never invented).
            if rec.get("timestamp_type") == "unavailable" and rec.get("normalized_timestamp") is not None:
                missing_handling_violations.append({"dataset": dataset, "memory_id": mid})

            session_id = rec.get("session_id")
            event_order = rec.get("event_order")
            conv_id = rec.get("conversation_id")
            source_file = rec.get("source_file")
            m = _SESSION_ID_RE.match(session_id) if session_id else None
            ordinal = int(m.group(1)) if m else 0

            key = (source_file, conv_id, ordinal)
            if key in last_event_order and event_order is not None and event_order < last_event_order[key]:
                ordering_violations.append({
                    "dataset": dataset, "memory_id": mid, "conversation_id": conv_id,
                    "session_id": session_id, "reason": "event_order regressed within session as file was streamed",
                })
            if event_order is not None:
                last_event_order[key] = event_order

            conv_key = (source_file, conv_id)
            if conv_key in last_session_ordinal and ordinal < last_session_ordinal[conv_key]:
                ordering_violations.append({
                    "dataset": dataset, "memory_id": mid, "conversation_id": conv_id,
                    "reason": "session ordinal regressed within conversation as file was streamed",
                })
            last_session_ordinal[conv_key] = max(last_session_ordinal.get(conv_key, ordinal), ordinal)

            # Duplicate timestamps (spec Test 6): legitimate when several
            # turns in the same session share one session-level source
            # timestamp. Counted, not treated as a violation, and only for
            # absolute-type records (the only ones with a real shared
            # source value).
            st = rec.get("source_timestamp")
            if st is not None:
                if st in seen_source_timestamps and seen_source_timestamps[st] != rec.get("normalized_timestamp"):
                    invalid_handling_violations.append({
                        "dataset": dataset, "memory_id": mid,
                        "reason": "identical source_timestamp parsed to two different normalized_timestamp values",
                    })
                elif st in seen_source_timestamps:
                    duplicate_timestamp_examples[dataset] += 1
                seen_source_timestamps[st] = rec.get("normalized_timestamp")

        per_dataset_counts[dataset] = count

    # Determinism (spec Test 4): recompute temporal fields for a bounded
    # sample per dataset and confirm bit-identical output on a second run.
    determinism_sample_size = 200
    for dataset in CORE_DATASETS:
        path = _unified_path(cfg, dataset)
        for i, rec in enumerate(iter_jsonl(path)):
            if i >= determinism_sample_size:
                break
            umr_input = {
                "source_dataset": rec["source_dataset"],
                "timestamp_type": rec["timestamp_type"],
                "source_timestamp": rec["source_timestamp"],
                "session_id": rec["session_id"],
                "event_order": rec["event_order"],
            }
            first = compute_temporal_fields(umr_input)
            second = compute_temporal_fields(umr_input)
            if first != second:
                determinism_violations.append({"dataset": dataset, "memory_id": rec.get("memory_id")})
            recomputed_matches_stored = (
                first["normalized_timestamp"] == rec.get("normalized_timestamp")
                and first["benchmark_timestamp"] == rec.get("benchmark_timestamp")
                and first["temporal_provenance"] == rec.get("temporal_provenance")
            )
            if not recomputed_matches_stored:
                determinism_violations.append({
                    "dataset": dataset, "memory_id": rec.get("memory_id"),
                    "reason": "recomputing from stored inputs does not reproduce the stored temporal fields",
                })

    total = sum(per_dataset_counts.values())

    checks.append({
        "name": "temporal_provenance_values_are_from_known_vocabulary",
        "status": "PASS" if not provenance_violations else "FAIL",
        "detail": {"violations": provenance_violations[:20], "violation_count": len(provenance_violations)},
    })
    checks.append({
        "name": "no_accidental_fabrication_source_absolute_vs_normalized_timestamp",
        "status": "PASS" if not fabrication_violations else "FAIL",
        "detail": {"violations": fabrication_violations[:20], "violation_count": len(fabrication_violations)},
    })
    checks.append({
        "name": "ordering_consistency_within_session_and_across_sessions",
        "status": "PASS" if not ordering_violations else "FAIL",
        "detail": {"violations": ordering_violations[:20], "violation_count": len(ordering_violations)},
    })
    checks.append({
        "name": "determinism_recompute_matches_stored_and_is_stable",
        "status": "PASS" if not determinism_violations else "FAIL",
        "detail": {"sample_size_per_dataset": determinism_sample_size, "violations": determinism_violations[:20], "violation_count": len(determinism_violations)},
    })
    checks.append({
        "name": "missing_temporal_information_never_silently_invented",
        "status": "PASS" if not missing_handling_violations else "FAIL",
        "detail": {"violations": missing_handling_violations[:20], "violation_count": len(missing_handling_violations)},
    })
    checks.append({
        "name": "identical_source_timestamps_never_parse_inconsistently",
        "status": "PASS" if not invalid_handling_violations else "FAIL",
        "detail": {"violations": invalid_handling_violations[:20], "violation_count": len(invalid_handling_violations)},
    })
    checks.append({
        "name": "all_four_core_datasets_produce_temporal_fields",
        "status": "PASS" if all(per_dataset_provenance_counts[ds] for ds in CORE_DATASETS) else "FAIL",
        "detail": {"per_dataset_provenance_counts": per_dataset_provenance_counts},
    })

    overall_status = "PASS" if all(c["status"] == "PASS" for c in checks) else "FAIL"
    return {
        "schema_version": "1.0.0",
        "normalization_policy_version": NORMALIZATION_POLICY_VERSION,
        "overall_status": overall_status,
        "total_records": total,
        "per_dataset_counts": per_dataset_counts,
        "duplicate_source_timestamp_occurrences_by_dataset": duplicate_timestamp_examples,
        "checks": checks,
    }


def write_temporal_validation_report(cfg: PipelineConfig) -> Path:
    report = validate_temporal(cfg)
    out_path = cfg.reports_dir / "phase2_3_temporal_validation_report.json"
    write_json(out_path, report)
    return out_path


if __name__ == "__main__":
    from preprocessing.config import load_config

    _cfg = load_config()
    _path = write_temporal_validation_report(_cfg)
    print(f"Wrote {_path}")
