"""Phase 1 validation suite (Step 14).

Runs a fixed set of named checks over the processed output of all datasets
and produces a PASS/FAIL verdict per category plus supporting detail.
Nothing here mutates data — validation is read-only and runs after
normalization has already been written to data/processed/.
"""
from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

from preprocessing.config import PipelineConfig
from preprocessing.io_utils import iter_jsonl


@dataclasses.dataclass
class CheckResult:
    name: str
    status: str  # "PASS" | "FAIL"
    detail: dict

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


def _load_all(cfg: PipelineConfig) -> tuple[list[dict], list[dict]]:
    memory_records: list[dict] = []
    task_records: list[dict] = []
    for name, ds in cfg.datasets.items():
        mem_path = ds.processed_dir / "memory_records.jsonl"
        task_path = ds.processed_dir / "task_records.jsonl"
        if mem_path.exists():
            memory_records.extend(iter_jsonl(mem_path))
        if task_path.exists():
            task_records.extend(iter_jsonl(task_path))
    return memory_records, task_records


def _check_unique_memory_ids(memory_records: list[dict]) -> CheckResult:
    ids = [r["memory_id"] for r in memory_records]
    dupes = {i for i in ids if ids.count(i) > 1} if len(ids) != len(set(ids)) else set()
    status = "PASS" if not dupes else "FAIL"
    return CheckResult("unique_memory_ids", status, {"total": len(ids), "unique": len(set(ids)), "duplicate_ids_sample": list(dupes)[:10]})


def _check_no_cross_dataset_id_collision(memory_records: list[dict]) -> CheckResult:
    by_id: dict[str, set[str]] = {}
    for r in memory_records:
        by_id.setdefault(r["memory_id"], set()).add(r["source_dataset"])
    collisions = {k: sorted(v) for k, v in by_id.items() if len(v) > 1}
    status = "PASS" if not collisions else "FAIL"
    return CheckResult("no_cross_dataset_id_collision", status, {"collisions_sample": dict(list(collisions.items())[:10])})


def _check_valid_source_references(cfg: PipelineConfig, memory_records: list[dict]) -> CheckResult:
    repo_root = cfg.raw_dir.parent.parent
    missing = []
    checked_files = set()
    for r in memory_records:
        sf = r["source_file"]
        if sf in checked_files:
            continue
        checked_files.add(sf)
        if not (repo_root / sf).exists():
            missing.append(sf)
    status = "PASS" if not missing else "FAIL"
    return CheckResult("valid_source_references", status, {"files_checked": len(checked_files), "missing": missing})


def _check_provenance_completeness(memory_records: list[dict]) -> CheckResult:
    required = {
        "source_dataset",
        "source_file",
        "source_record_id",
        "conversation_id",
        "extraction_pipeline_version",
    }
    bad = []
    for r in memory_records:
        prov = r.get("provenance", {})
        if not required.issubset(prov.keys()) or any(prov.get(k) in (None, "") for k in required):
            bad.append(r["memory_id"])
    status = "PASS" if not bad else "FAIL"
    return CheckResult("valid_provenance", status, {"invalid_count": len(bad), "sample": bad[:10]})


def _check_task_evidence_links(memory_records: list[dict], task_records: list[dict]) -> CheckResult:
    memory_ids = {r["memory_id"] for r in memory_records}
    broken = []
    for t in task_records:
        for mid in t.get("evidence_memory_ids", []):
            if mid not in memory_ids:
                broken.append((t["task_id"], mid))
    status = "PASS" if not broken else "FAIL"
    return CheckResult("no_broken_task_evidence_links", status, {"broken_count": len(broken), "sample": broken[:10]})


_EXPECTED_MULTI_FILE_SESSION_DATASETS = {
    # LongMemEval officially publishes multiple variant files (oracle,
    # s_cleaned, m_cleaned) drawn from an overlapping pool of sessions by
    # design -- the same session_id legitimately appearing in more than one
    # file is expected here, not a data-integrity problem. See
    # data/reports/longmemeval_inspection.json and the Phase 1 report.
    "longmemeval",
}


def _check_session_conversation_consistency(memory_records: list[dict]) -> CheckResult:
    """Every (conversation_id, session_id) pair must be internally consistent:
    same source_dataset and source_file for all its turns -- EXCEPT for
    datasets in _EXPECTED_MULTI_FILE_SESSION_DATASETS, where cross-file
    session sharing is a documented, expected property of the source data
    (see docstring), tracked separately and not counted as a failure."""
    groups: dict[tuple, set] = {}
    for r in memory_records:
        key = (r["source_dataset"], r["conversation_id"], r["session_id"])
        groups.setdefault(key, set()).add(r["source_file"])

    inconsistent = {}
    expected_overlap = {}
    for k, v in groups.items():
        if len(v) <= 1:
            continue
        if k[0] in _EXPECTED_MULTI_FILE_SESSION_DATASETS:
            expected_overlap[str(k)] = sorted(v)
        else:
            inconsistent[str(k)] = sorted(v)

    status = "PASS" if not inconsistent else "FAIL"
    return CheckResult(
        "session_conversation_consistency",
        status,
        {
            "inconsistent_count": len(inconsistent),
            "sample": dict(list(inconsistent.items())[:10]),
            "expected_cross_file_overlap_count": len(expected_overlap),
            "expected_cross_file_overlap_note": "sessions shared across "
            "LongMemEval's oracle/s_cleaned/m_cleaned variant files; not a "
            "failure, see _EXPECTED_MULTI_FILE_SESSION_DATASETS",
        },
    )


def _check_event_ordering(memory_records: list[dict]) -> CheckResult:
    """event_order must be a non-negative, gap-free, strictly increasing
    sequence starting at 0 within each (source_dataset, conversation_id,
    session_id) grouping for per-session-scoped datasets, or within each
    (source_dataset, conversation_id) for whole-conversation-scoped ones
    (LoCoMo). Both scopes are checked; a group passes if either holds."""
    per_session: dict[tuple, list[int]] = {}
    per_conversation: dict[tuple, list[int]] = {}
    for r in memory_records:
        per_session.setdefault((r["source_dataset"], r["conversation_id"], r["session_id"]), []).append(r["event_order"])
        per_conversation.setdefault((r["source_dataset"], r["conversation_id"]), []).append(r["event_order"])

    def is_gapfree_sequence(values: list[int]) -> bool:
        s = sorted(values)
        return s == list(range(len(s)))

    bad_groups = []
    for key, session_orders in per_session.items():
        dataset = key[0]
        conv_key = (key[0], key[1])
        ok_session = is_gapfree_sequence(session_orders)
        ok_conversation = is_gapfree_sequence(sorted(set(per_conversation[conv_key]))) if conv_key in per_conversation else False
        # A conversation-scoped dataset (LoCoMo) is valid if the *conversation*
        # ordering is gap-free even though per-session ordering is not 0-based.
        if not ok_session and not ok_conversation:
            bad_groups.append(str(key))

    status = "PASS" if not bad_groups else "FAIL"
    return CheckResult("valid_event_ordering", status, {"invalid_group_count": len(bad_groups), "sample": bad_groups[:10]})


def _check_encoding(memory_records: list[dict]) -> CheckResult:
    bad = []
    for r in memory_records:
        content = r["content"]
        if "�" in content:
            bad.append(r["memory_id"])
    status = "PASS" if not bad else "FAIL"
    return CheckResult("encoding_correctness", status, {"replacement_char_count": len(bad), "sample": bad[:10]})


def _check_schema_consistency(memory_records: list[dict]) -> CheckResult:
    required_fields = {
        "memory_id", "content", "source_dataset", "source_file", "source_record_id",
        "conversation_id", "session_id", "turn_id", "source_role", "event_order",
        "source_timestamp", "timestamp_type", "benchmark_timestamp", "provenance",
        "data_quality", "metadata",
    }
    bad = []
    for r in memory_records:
        if not required_fields.issubset(r.keys()):
            bad.append(r.get("memory_id", "<unknown>"))
    status = "PASS" if not bad else "FAIL"
    return CheckResult("schema_consistency", status, {"invalid_count": len(bad), "sample": bad[:10]})


def _check_no_train_test_leakage(memory_records: list[dict]) -> CheckResult:
    """For datasets with explicit split files (conversation_chronicles), the
    same conversation_id must not appear under more than one split file."""
    conv_to_files: dict[tuple, set] = {}
    for r in memory_records:
        if r["source_dataset"] != "conversation_chronicles":
            continue
        conv_to_files.setdefault(r["conversation_id"], set()).add(r["source_file"])
    leaked = {k: sorted(v) for k, v in conv_to_files.items() if len(v) > 1}
    status = "PASS" if not leaked else "FAIL"
    return CheckResult("no_train_test_leakage", status, {"leaked_conversation_count": len(leaked), "sample": dict(list(leaked.items())[:10])})


def run_validation(cfg: PipelineConfig) -> dict:
    memory_records, task_records = _load_all(cfg)

    checks = [
        _check_unique_memory_ids(memory_records),
        _check_no_cross_dataset_id_collision(memory_records),
        _check_valid_source_references(cfg, memory_records),
        _check_provenance_completeness(memory_records),
        _check_task_evidence_links(memory_records, task_records),
        _check_session_conversation_consistency(memory_records),
        _check_event_ordering(memory_records),
        _check_encoding(memory_records),
        _check_schema_consistency(memory_records),
        _check_no_train_test_leakage(memory_records),
    ]

    overall = "PASS" if all(c.status == "PASS" for c in checks) else "FAIL"

    return {
        "overall_status": overall,
        "total_memory_records": len(memory_records),
        "total_task_records": len(task_records),
        "checks": [c.to_dict() for c in checks],
    }
