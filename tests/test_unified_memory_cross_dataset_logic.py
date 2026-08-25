"""Phase 2.2: fast, synthetic-fixture tests of the cross-dataset
validation logic itself (collision detection, quarantine-vs-trusted
consistency) -- independent of the slow real-data full scan.
"""
from __future__ import annotations

import json

from preprocessing.config import DatasetPaths, PipelineConfig
from preprocessing.unified_validation import validate_cross_dataset


def _write_umr(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def _write_phase1_stub(path, n):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for _ in range(n):
            f.write("{}\n")


_BASE_FIELDS = dict(
    schema_version="1.1.0", content_type="plain_text", source_file="f",
    source_record_id="r", conversation_id="c", session_id="s", turn_id="t",
    event_order=0, source_role=None, source_timestamp=None,
    timestamp_type="unavailable", benchmark_timestamp=None,
    normalized_timestamp=None, temporal_provenance="source_relative",
    quality_status="valid", data_quality=[], trusted_clean_memory=True,
    provenance={}, derivation_parents=[], retrieval_history=[],
    propagation_history=[], trust_score=None, security_state=None,
    poison_status=None, embedding=None, embedding_metadata=None,
    dataset_scope="FULL_SOURCE_ACQUIRED", dataset_version_or_revision=None,
    field_status={}, metadata={},
)


def _rec(memory_id, source_dataset, admission_status="ADMISSIBLE"):
    return {
        **_BASE_FIELDS,
        "memory_id": memory_id,
        "content": "hi",
        "source_dataset": source_dataset,
        "admission_status": admission_status,
    }


def _cfg(tmp_path):
    raw_dir = tmp_path / "data" / "raw"
    interim_dir = tmp_path / "data" / "interim"
    processed_dir = tmp_path / "data" / "processed"
    datasets = {}
    for name in ("locomo", "longmemeval", "msc", "conversation_chronicles"):
        datasets[name] = DatasetPaths(
            name=name, raw_dir=raw_dir / name, interim_dir=interim_dir / name,
            processed_dir=processed_dir / name, raw_files=[], optional_raw_files=[], enabled=True,
        )
    return PipelineConfig(
        seed=1, raw_dir=raw_dir, interim_dir=interim_dir, processed_dir=processed_dir,
        metadata_dir=tmp_path / "data" / "metadata", reports_dir=tmp_path / "data" / "reports",
        logs_dir=tmp_path / "data" / "logs", datasets=datasets, config_path=tmp_path / "fake.yaml",
    )


def test_detects_cross_dataset_id_collision(tmp_path):
    cfg = _cfg(tmp_path)
    shared_id = "a" * 24
    for ds, other_id in (("locomo", "b" * 24), ("msc", "c" * 24)):
        recs = [_rec(shared_id, ds), _rec(other_id, ds)]
        _write_umr(cfg.processed_dir / "unified_memory" / ds / "memory_records.jsonl", recs)
        _write_phase1_stub(cfg.processed_dir / ds / "memory_records.jsonl", len(recs))
    for ds in ("longmemeval", "conversation_chronicles"):
        _write_umr(cfg.processed_dir / "unified_memory" / ds / "memory_records.jsonl", [])
        _write_phase1_stub(cfg.processed_dir / ds / "memory_records.jsonl", 0)

    report = validate_cross_dataset(cfg)
    collision_check = next(c for c in report["checks"] if c["name"] == "no_cross_dataset_id_collision")
    assert collision_check["status"] == "FAIL"
    assert report["overall_status"] == "FAIL"


def test_passes_with_no_collisions_and_consistent_quarantine(tmp_path):
    cfg = _cfg(tmp_path)
    counter = 0
    for ds in ("locomo", "longmemeval", "msc", "conversation_chronicles"):
        recs = []
        for _ in range(3):
            mid = f"{counter:024d}"
            recs.append(_rec(mid, ds))
            counter += 1
        _write_umr(cfg.processed_dir / "unified_memory" / ds / "memory_records.jsonl", recs)
        _write_phase1_stub(cfg.processed_dir / ds / "memory_records.jsonl", len(recs))

    report = validate_cross_dataset(cfg)
    assert report["overall_status"] == "PASS"
    assert report["total_records"] == 12


def test_flags_a_quarantined_record_incorrectly_marked_trusted(tmp_path):
    cfg = _cfg(tmp_path)
    bad = _rec("d" * 24, "locomo", admission_status="QUARANTINED")
    bad["trusted_clean_memory"] = True  # inconsistent on purpose
    _write_umr(cfg.processed_dir / "unified_memory" / "locomo" / "memory_records.jsonl", [bad])
    _write_phase1_stub(cfg.processed_dir / "locomo" / "memory_records.jsonl", 1)
    for ds in ("longmemeval", "msc", "conversation_chronicles"):
        _write_umr(cfg.processed_dir / "unified_memory" / ds / "memory_records.jsonl", [])
        _write_phase1_stub(cfg.processed_dir / ds / "memory_records.jsonl", 0)

    report = validate_cross_dataset(cfg)
    check = next(c for c in report["checks"] if c["name"] == "quarantined_records_never_trusted_clean")
    assert check["status"] == "FAIL"
    assert len(check["detail"]["violations"]) == 1
