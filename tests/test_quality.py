from __future__ import annotations

from preprocessing.quality import (
    QUALITY_IRRECOVERABLY_INVALID,
    QUALITY_REPAIRED,
    QUALITY_VALID,
    QUALITY_VALID_FLAGGED,
    QuarantineLog,
    resolve_quality_status,
)


def test_resolve_quality_status_plain():
    assert resolve_quality_status(whitespace_normalized=False, has_encoding_issue=False) == QUALITY_VALID


def test_resolve_quality_status_repaired():
    assert resolve_quality_status(whitespace_normalized=True, has_encoding_issue=False) == QUALITY_REPAIRED


def test_resolve_quality_status_flagged():
    assert resolve_quality_status(whitespace_normalized=False, has_encoding_issue=True) == QUALITY_VALID_FLAGGED


def test_resolve_quality_status_flagged_outranks_repaired():
    # An unresolved defect must not be masked by a successful repair.
    assert resolve_quality_status(whitespace_normalized=True, has_encoding_issue=True) == QUALITY_VALID_FLAGGED


def test_quarantine_log_add_and_flush(tmp_path):
    log = QuarantineLog(dataset="fake", run_timestamp="t0")
    log.add(
        source_file="f.json",
        source_record_id="r1",
        exclusion_reason="empty_content",
        raw_content={"text": ""},
        conversation_id="c1",
        session_id="s1",
        turn_id="s1:0",
    )
    assert len(log) == 1
    assert log.count_by_reason("empty_content") == 1

    interim_dir = tmp_path / "interim" / "fake"
    logs_dir = tmp_path / "logs"
    n = log.flush(interim_dir, logs_dir)
    assert n == 1

    import json

    lines = (interim_dir / "quarantine.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["quality_status"] == QUALITY_IRRECOVERABLY_INVALID
    assert record["raw_content"] == {"text": ""}
    assert record["exclusion_reason"] == "empty_content"

    # cross-dataset shared log also received it
    shared_lines = (logs_dir / "quarantine_log.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(shared_lines) == 1


def test_quarantine_log_rejects_unknown_status(tmp_path):
    log = QuarantineLog(dataset="fake", run_timestamp="t0")
    try:
        log.add(
            source_file="f.json",
            source_record_id="r1",
            exclusion_reason="x",
            raw_content={},
            quality_status="not_a_real_status",
        )
        assert False, "expected AssertionError"
    except AssertionError:
        pass
