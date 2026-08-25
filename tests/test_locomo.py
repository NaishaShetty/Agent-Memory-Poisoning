from __future__ import annotations

from preprocessing.datasets import locomo
from preprocessing.quality import QUALITY_REPAIRED, QUALITY_VALID, QuarantineLog
from preprocessing.removal_log import RemovalLog
from tests.conftest import write_json


def _sample(sample_id="conv-1"):
    return {
        "sample_id": sample_id,
        "conversation": {
            "speaker_a": "Alice",
            "speaker_b": "Bob",
            "session_1_date_time": "1:00 pm on 1 May, 2024",
            "session_1": [
                {"speaker": "Alice", "dia_id": "D1:1", "text": "Hi Bob!"},
                {"speaker": "Bob", "dia_id": "D1:2", "text": "  Hello   Alice   "},
                {"speaker": "Alice", "dia_id": "D1:3", "text": "   "},  # empty after strip
            ],
            "session_2_date_time": "2:00 pm on 2 May, 2024",
            "session_2": [
                {"speaker": "Bob", "dia_id": "D2:1", "text": "Second session"},
            ],
        },
        "qa": [
            {"question": "Who greeted Bob?", "answer": "Alice", "evidence": ["D1:1"], "category": 1},
            {"question": "Missing evidence?", "answer": "?", "evidence": ["D9:9"], "category": 2},
        ],
        "event_summary": {},
        "observation": {},
        "session_summary": {},
    }


def _write_fixture(cfg):
    path = cfg.raw_dir / "locomo10.json"
    write_json(path, [_sample()])
    return path


def test_inspect_reports_counts(make_cfg):
    cfg = make_cfg("locomo", ["locomo10.json"])
    _write_fixture(cfg)
    report = locomo.inspect(cfg)
    assert report["num_samples_conversations"] == 1
    assert report["num_turns"] == 4  # includes the empty-text turn, inspection doesn't drop it
    assert report["num_qa_instances"] == 2
    assert report["quality_issues"]["qa_instances_missing_evidence"] == 0


def test_clean_and_normalize_drops_empty_text_and_logs_it(make_cfg):
    cfg = make_cfg("locomo", ["locomo10.json"])
    _write_fixture(cfg)
    log = RemovalLog(dataset="locomo", run_timestamp="t0")
    memory_records, task_records = locomo.clean_and_normalize(cfg, log)

    # 4 raw turns, 1 empty -> 3 memory records
    assert len(memory_records) == 3
    assert len(log) == 1
    assert log._events[0].reason == "empty_text"

    texts = {r.content for r in memory_records}
    assert "Hi Bob!" in texts
    assert "Hello Alice" in texts  # whitespace normalized


def test_provenance_preserved(make_cfg):
    cfg = make_cfg("locomo", ["locomo10.json"])
    _write_fixture(cfg)
    log = RemovalLog(dataset="locomo", run_timestamp="t0")
    memory_records, _ = locomo.clean_and_normalize(cfg, log)

    r = next(r for r in memory_records if r.turn_id == "D1:1")
    assert r.conversation_id == "conv-1"
    assert r.session_id == "session_1"
    assert r.source_role == "Alice"
    assert r.source_timestamp == "1:00 pm on 1 May, 2024"
    assert r.timestamp_type == "absolute"
    assert r.provenance["source_record_id"] == "conv-1"
    assert r.provenance["turn_id"] == "D1:1"
    assert r.benchmark_timestamp is None


def test_deterministic_memory_ids(make_cfg):
    cfg = make_cfg("locomo", ["locomo10.json"])
    _write_fixture(cfg)
    log1 = RemovalLog(dataset="locomo", run_timestamp="t0")
    log2 = RemovalLog(dataset="locomo", run_timestamp="t1")
    mem1, _ = locomo.clean_and_normalize(cfg, log1)
    mem2, _ = locomo.clean_and_normalize(cfg, log2)

    ids1 = {r.turn_id: r.memory_id for r in mem1}
    ids2 = {r.turn_id: r.memory_id for r in mem2}
    assert ids1 == ids2  # same source -> same IDs regardless of run


def test_qa_evidence_resolved_to_memory_ids(make_cfg):
    cfg = make_cfg("locomo", ["locomo10.json"])
    _write_fixture(cfg)
    log = RemovalLog(dataset="locomo", run_timestamp="t0")
    memory_records, task_records = locomo.clean_and_normalize(cfg, log)

    mem_by_turn = {r.turn_id: r.memory_id for r in memory_records}
    task_with_evidence = next(t for t in task_records if t.evidence_refs_raw == ["D1:1"])
    assert task_with_evidence.evidence_memory_ids == [mem_by_turn["D1:1"]]

    task_missing_evidence = next(t for t in task_records if t.evidence_refs_raw == ["D9:9"])
    assert task_missing_evidence.evidence_memory_ids == []  # unresolved evidence, not fabricated


def test_missing_raw_file_fails_clearly(make_cfg):
    cfg = make_cfg("locomo", ["locomo10.json"])
    import pytest

    with pytest.raises(FileNotFoundError, match="Missing required raw file"):
        locomo.inspect(cfg)


def test_quality_status_assigned(make_cfg):
    cfg = make_cfg("locomo", ["locomo10.json"])
    _write_fixture(cfg)
    log = RemovalLog(dataset="locomo", run_timestamp="t0")
    memory_records, _ = locomo.clean_and_normalize(cfg, log)

    by_turn = {r.turn_id: r for r in memory_records}
    assert by_turn["D1:1"].quality_status == QUALITY_VALID
    assert by_turn["D1:2"].quality_status == QUALITY_REPAIRED  # whitespace was normalized


def test_empty_turn_is_quarantined_not_silently_dropped(make_cfg):
    cfg = make_cfg("locomo", ["locomo10.json"])
    _write_fixture(cfg)
    log = RemovalLog(dataset="locomo", run_timestamp="t0")
    quarantine = QuarantineLog(dataset="locomo", run_timestamp="t0")
    memory_records, _ = locomo.clean_and_normalize(cfg, log, quarantine)

    assert len(quarantine) == 1
    q = quarantine._records[0]
    assert q.exclusion_reason == "empty_content"
    assert q.conversation_id == "conv-1"
    assert q.raw_content["dia_id"] == "D1:3"  # original record preserved verbatim
    assert q.quality_status == "irrecoverably_invalid"


def test_quarantine_log_is_optional_backward_compatible(make_cfg):
    # Older call sites that don't pass a quarantine_log must keep working.
    cfg = make_cfg("locomo", ["locomo10.json"])
    _write_fixture(cfg)
    log = RemovalLog(dataset="locomo", run_timestamp="t0")
    memory_records, task_records = locomo.clean_and_normalize(cfg, log)  # no quarantine_log
    assert len(memory_records) == 3
