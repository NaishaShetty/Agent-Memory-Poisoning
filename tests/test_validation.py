from __future__ import annotations

from preprocessing.config import DatasetPaths, PipelineConfig
from preprocessing.io_utils import write_jsonl
from preprocessing.validation import run_validation


def _base_record(**overrides):
    r = {
        "memory_id": "m1",
        "content": "hello",
        "source_dataset": "fake",
        "source_file": "raw.txt",
        "source_record_id": "rec1",
        "conversation_id": "conv1",
        "session_id": "session_1",
        "turn_id": "session_1:0",
        "source_role": "user",
        "event_order": 0,
        "source_timestamp": None,
        "timestamp_type": "unavailable",
        "benchmark_timestamp": None,
        "provenance": {
            "source_dataset": "fake",
            "source_file": "raw.txt",
            "source_record_id": "rec1",
            "conversation_id": "conv1",
            "session_id": "session_1",
            "turn_id": "session_1:0",
            "extraction_pipeline_version": "1.0.0",
        },
        "data_quality": [],
        "metadata": {},
    }
    r.update(overrides)
    return r


def _cfg(tmp_path, name="fake"):
    raw_dir = tmp_path / "data" / "raw"
    processed_dir = tmp_path / "data" / "processed"
    ds = DatasetPaths(
        name=name,
        raw_dir=raw_dir / name,
        interim_dir=tmp_path / "data" / "interim" / name,
        processed_dir=processed_dir / name,
        raw_files=[],
        optional_raw_files=[],
        enabled=True,
    )
    return PipelineConfig(
        seed=1,
        raw_dir=raw_dir,
        interim_dir=tmp_path / "data" / "interim",
        processed_dir=processed_dir,
        metadata_dir=tmp_path / "data" / "metadata",
        reports_dir=tmp_path / "data" / "reports",
        logs_dir=tmp_path / "data" / "logs",
        datasets={name: ds},
        config_path=tmp_path / "cfg.yaml",
    )


def test_validation_passes_on_clean_data(tmp_path):
    cfg = _cfg(tmp_path)
    (tmp_path / "raw.txt").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "raw.txt").write_text("x", encoding="utf-8")
    write_jsonl(cfg.dataset("fake").processed_dir / "memory_records.jsonl", [_base_record()])
    write_jsonl(cfg.dataset("fake").processed_dir / "task_records.jsonl", [])

    report = run_validation(cfg)
    assert report["overall_status"] == "PASS"
    assert all(c["status"] == "PASS" for c in report["checks"])


def test_validation_catches_duplicate_memory_ids(tmp_path):
    cfg = _cfg(tmp_path)
    (tmp_path / "raw.txt").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "raw.txt").write_text("x", encoding="utf-8")
    write_jsonl(
        cfg.dataset("fake").processed_dir / "memory_records.jsonl",
        [_base_record(memory_id="dup"), _base_record(memory_id="dup", turn_id="session_1:1", event_order=1)],
    )
    write_jsonl(cfg.dataset("fake").processed_dir / "task_records.jsonl", [])

    report = run_validation(cfg)
    assert report["overall_status"] == "FAIL"
    check = next(c for c in report["checks"] if c["name"] == "unique_memory_ids")
    assert check["status"] == "FAIL"


def test_validation_catches_broken_task_evidence_link(tmp_path):
    cfg = _cfg(tmp_path)
    (tmp_path / "raw.txt").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "raw.txt").write_text("x", encoding="utf-8")
    write_jsonl(cfg.dataset("fake").processed_dir / "memory_records.jsonl", [_base_record()])
    write_jsonl(
        cfg.dataset("fake").processed_dir / "task_records.jsonl",
        [{"task_id": "t1", "evidence_memory_ids": ["does-not-exist"]}],
    )

    report = run_validation(cfg)
    check = next(c for c in report["checks"] if c["name"] == "no_broken_task_evidence_links")
    assert check["status"] == "FAIL"
    assert report["overall_status"] == "FAIL"


def test_validation_catches_missing_source_file(tmp_path):
    cfg = _cfg(tmp_path)
    # raw.txt intentionally not created
    write_jsonl(cfg.dataset("fake").processed_dir / "memory_records.jsonl", [_base_record()])

    report = run_validation(cfg)
    check = next(c for c in report["checks"] if c["name"] == "valid_source_references")
    assert check["status"] == "FAIL"
