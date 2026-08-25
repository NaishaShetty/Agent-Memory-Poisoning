"""Phase 2.1-R, Part 1: LongMemEval provenance/integrity case study tests.

Runs against the real repository data (read-only) since the case study is
about two specific, real records, not synthetic fixtures.
"""
from __future__ import annotations

import json

from preprocessing.config import load_config
from preprocessing.trusted_baseline import (
    excluded_memory_ids,
    is_trusted_clean_memory,
    load_provenance_exceptions,
)

_TARGET_IDS = {"d6198c013c7fe0fbad262a75", "d2435a9b16c870ba3022e52f"}


def _cfg():
    return load_config()


def _processed_records_by_id(cfg, ids):
    path = cfg.processed_dir / "longmemeval" / "memory_records.jsonl"
    found = {}
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            if rec.get("memory_id") in ids:
                found[rec["memory_id"]] = rec
    return found


def test_case_study_file_exists_and_covers_exactly_the_two_known_records():
    cfg = _cfg()
    exceptions = load_provenance_exceptions(cfg)
    ids = {r["memory_id"] for r in exceptions["records"]}
    assert ids == _TARGET_IDS


def test_original_processed_content_is_unchanged_and_still_carries_the_defect():
    """The remediation must not have repaired, stripped, or altered the
    original processed records -- rule 3/6: preserve original values."""
    cfg = _cfg()
    records = _processed_records_by_id(cfg, _TARGET_IDS)
    assert set(records) == _TARGET_IDS
    for memory_id, rec in records.items():
        assert "�" in rec["content"], (
            f"{memory_id}: expected the original U+FFFD defect to still be "
            "present untouched; content must not be silently repaired"
        )
        assert rec["quality_status"] == "valid_flagged"
        assert "source_encoding_replacement_char" in rec.get("data_quality", [])


def test_case_study_records_are_traceable_to_source():
    cfg = _cfg()
    exceptions = load_provenance_exceptions(cfg)
    for r in exceptions["records"]:
        assert r["source_dataset"] == "longmemeval"
        assert r["source_file"]
        assert r["source_record_id"]
        assert r["conversation_id"]
        assert r["turn_id"]


def test_case_study_status_fields_are_explicit_and_from_known_vocabulary():
    cfg = _cfg()
    exceptions = load_provenance_exceptions(cfg)
    for r in exceptions["records"]:
        assert r["provenance_status"] in {"VERIFIED", "VERIFIED_WITH_ISSUE", "UNVERIFIED"}
        assert r["admission_status"] in {"ADMISSIBLE", "FLAGGED", "QUARANTINED"}
        assert r["issue_type"] == "ENCODING_INTEGRITY_UNCERTAIN"
        # never claim clean while unresolved
        assert r["provenance_status"] != "VERIFIED"
        assert r["admission_status"] != "ADMISSIBLE"


def test_repair_was_not_attempted_and_reasoning_is_recorded():
    cfg = _cfg()
    exceptions = load_provenance_exceptions(cfg)
    for r in exceptions["records"]:
        assert r["repair_attempted"] is False
        assert r["repair_rationale"]


def test_raw_file_evidence_confirms_pre_existing_source_corruption():
    """Re-verifies, against the real raw file on disk, that the defect is
    present verbatim at the recorded byte offset -- i.e. the claim that
    this predates Phase 1 processing is independently checkable, not just
    asserted."""
    cfg = _cfg()
    exceptions = load_provenance_exceptions(cfg)
    raw_path = cfg.raw_dir / "longmemeval" / "longmemeval_s_cleaned.json"
    replacement_bytes = "�".encode("utf-8")
    for r in exceptions["records"]:
        offset = r["evidence"]["raw_file_byte_offset"]
        with raw_path.open("rb") as f:
            f.seek(offset)
            chunk = f.read(80)
        assert replacement_bytes * 2 in chunk, (
            f"{r['memory_id']}: raw file near byte offset {offset} does not "
            "contain two consecutive encoded U+FFFD codepoints as claimed"
        )
        assert r["evidence"]["raw_file_contains_replacement_bytes_verbatim"] is True


def test_records_are_excluded_from_trusted_clean_memory_baseline():
    cfg = _cfg()
    excluded = excluded_memory_ids(cfg)
    assert excluded == _TARGET_IDS
    records = _processed_records_by_id(cfg, _TARGET_IDS)
    for memory_id, rec in records.items():
        assert is_trusted_clean_memory(rec, excluded) is False


def test_exclusion_does_not_block_ordinary_valid_records():
    """Control case: the exclusion mechanism must be narrowly scoped to
    the two flagged records, not accidentally block everything."""
    cfg = _cfg()
    excluded = excluded_memory_ids(cfg)
    ordinary_valid = {"memory_id": "not-a-real-id", "quality_status": "valid"}
    ordinary_repaired = {"memory_id": "also-not-real", "quality_status": "repaired"}
    assert is_trusted_clean_memory(ordinary_valid, excluded) is True
    assert is_trusted_clean_memory(ordinary_repaired, excluded) is True


def test_trusted_baseline_predicate_is_deterministic():
    cfg = _cfg()
    excluded = excluded_memory_ids(cfg)
    records = _processed_records_by_id(cfg, _TARGET_IDS)
    for rec in records.values():
        first = is_trusted_clean_memory(rec, excluded)
        second = is_trusted_clean_memory(rec, excluded)
        assert first == second is False
