from __future__ import annotations

from preprocessing.removal_log import RemovalLog
from preprocessing.schema import MemoryRecord, Provenance


def test_provenance_to_dict_roundtrip():
    p = Provenance(
        source_dataset="ds",
        source_file="f.json",
        source_record_id="r1",
        conversation_id="c1",
        session_id="s1",
        turn_id="t1",
        extraction_pipeline_version="1.0.0",
    )
    d = p.to_dict()
    assert d["source_dataset"] == "ds"
    assert d["turn_id"] == "t1"


def test_memory_record_benchmark_timestamp_defaults_reserved():
    r = MemoryRecord(
        memory_id="m1",
        content="hi",
        source_dataset="ds",
        source_file="f.json",
        source_record_id="r1",
        conversation_id="c1",
        session_id="s1",
        turn_id="t1",
        source_role="user",
        event_order=0,
        source_timestamp=None,
        timestamp_type="unavailable",
        benchmark_timestamp=None,
        provenance={},
        data_quality=[],
        metadata={},
    )
    assert r.to_dict()["benchmark_timestamp"] is None


def test_removal_log_records_and_flushes(tmp_path):
    log = RemovalLog(dataset="ds", run_timestamp="t0")
    log.record(source_record_id="r1", source_file="f.json", operation="removed", reason="empty_text")
    log.record(source_record_id="r2", source_file="f.json", operation="flagged", reason="sampled")
    assert len(log) == 2
    assert log.count_by_operation("removed") == 1
    assert log.count_by_operation("flagged") == 1

    n = log.flush(tmp_path)
    assert n == 2
    out = (tmp_path / "removal_log.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(out) == 2

    # flushing again appends (append-only log, per Step 7)
    log.flush(tmp_path)
    out2 = (tmp_path / "removal_log.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(out2) == 4
