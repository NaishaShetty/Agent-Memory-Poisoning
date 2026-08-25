"""Phase 2.3: temporal normalization tests. Fast, synthetic-fixture unit
tests against preprocessing/temporal.py and preprocessing/unified_memory.py
(Tests 1-9 below, numbered per the Phase 2.3 brief), plus one real-data
regression check (Test 10) that reuses the already-generated
data/processed/unified_memory output rather than rerunning the pipeline.
"""
from __future__ import annotations

import json

from preprocessing.temporal import (
    DATA_QUALITY_INVALID_SOURCE_TIMESTAMP,
    TEMPORAL_PROVENANCE_BENCHMARK_ASSIGNED,
    TEMPORAL_PROVENANCE_SOURCE_ABSOLUTE,
    TEMPORAL_PROVENANCE_SOURCE_RELATIVE,
    VALID_TEMPORAL_PROVENANCE,
    compute_temporal_fields,
    parse_locomo_timestamp,
    parse_longmemeval_timestamp,
)
from preprocessing.unified_memory import map_memory_record
from preprocessing.unified_schema import (
    ABSENCE_NOT_APPLICABLE,
    ABSENCE_NOT_AVAILABLE,
    ABSENCE_UNRESOLVED,
    ORIGIN_BENCHMARK_GENERATED,
    ORIGIN_INFERRED,
    ORIGIN_SOURCE_PROVIDED,
    validate_record,
)

_TS = "2026-08-16T00:00:00Z"


def _phase1_record(**overrides) -> dict:
    base = {
        "memory_id": "abc123def4567890abcdef12",
        "content": "hello there",
        "source_dataset": "locomo",
        "source_file": "data/raw/locomo/locomo10.json",
        "source_record_id": "conv-1",
        "conversation_id": "conv-1",
        "session_id": "session_1",
        "turn_id": "D1:1",
        "source_role": "Alice",
        "event_order": 0,
        "source_timestamp": "1:00 pm on 1 January, 2024",
        "timestamp_type": "absolute",
        "benchmark_timestamp": None,
        "provenance": {
            "source_dataset": "locomo", "source_file": "data/raw/locomo/locomo10.json",
            "source_record_id": "conv-1", "conversation_id": "conv-1",
            "session_id": "session_1", "turn_id": "D1:1",
            "extraction_pipeline_version": "1.0.0",
        },
        "data_quality": [],
        "metadata": {},
        "quality_status": "valid",
    }
    base.update(overrides)
    return base


def _map(record, **kwargs):
    kwargs.setdefault("conversation_id_origin", ORIGIN_SOURCE_PROVIDED)
    kwargs.setdefault("dataset_scope", "FULL_SOURCE_ACQUIRED")
    kwargs.setdefault("dataset_version_or_revision", "v1.0")
    kwargs.setdefault("exception_ids", frozenset())
    kwargs.setdefault("generated_at", _TS)
    return map_memory_record(record, **kwargs)


# ---------------------------------------------------------------------------
# Test 1 -- source timestamp preservation
# ---------------------------------------------------------------------------

def test_source_timestamp_preserved_verbatim_alongside_normalization():
    p1 = _phase1_record(source_timestamp="1:56 pm on 8 May, 2023")
    umr = _map(p1)
    assert umr["source_timestamp"] == "1:56 pm on 8 May, 2023"
    assert umr["normalized_timestamp"] == "2023-05-08T13:56:00"


def test_raw_relative_signal_preserved_in_metadata_not_overwritten():
    """MSC/Conversation Chronicles preserve their raw relative-gap
    description in metadata (Phase 1 behavior); Phase 2.3 must not touch
    or remove it even though it also derives temporal fields."""
    p1 = _phase1_record(
        source_dataset="msc", session_id="session_2", source_timestamp=None,
        timestamp_type="relative",
        metadata={"relative_time_since_previous_session": {"time_num": 2, "time_unit": "days", "time_back": True}},
    )
    umr = _map(p1)
    assert umr["metadata"]["relative_time_since_previous_session"] == {"time_num": 2, "time_unit": "days", "time_back": True}
    assert umr["source_timestamp"] is None


# ---------------------------------------------------------------------------
# Test 2 -- provenance
# ---------------------------------------------------------------------------

def test_every_normalized_temporal_value_identifies_its_origin():
    for tt, ts in [("absolute", "1:00 pm on 1 January, 2024"), ("relative", None), ("unavailable", None)]:
        umr = _map(_phase1_record(timestamp_type=tt, source_timestamp=ts))
        assert umr["temporal_provenance"] in VALID_TEMPORAL_PROVENANCE
        assert umr["field_status"]["temporal_provenance"] == ORIGIN_INFERRED
        assert umr["field_status"]["normalized_timestamp"] in {
            ORIGIN_INFERRED, ABSENCE_NOT_AVAILABLE, ABSENCE_UNRESOLVED,
        }
        assert umr["field_status"]["benchmark_timestamp"] in {
            ORIGIN_BENCHMARK_GENERATED, ABSENCE_NOT_APPLICABLE,
        }


def test_absolute_provenance_never_marked_benchmark_generated():
    umr = _map(_phase1_record())
    assert umr["temporal_provenance"] == TEMPORAL_PROVENANCE_SOURCE_ABSOLUTE
    assert umr["field_status"]["normalized_timestamp"] == ORIGIN_INFERRED
    assert umr["field_status"]["benchmark_timestamp"] == ABSENCE_NOT_APPLICABLE


def test_relative_provenance_benchmark_timestamp_marked_benchmark_generated_not_source_provided():
    umr = _map(_phase1_record(timestamp_type="relative", source_timestamp=None))
    assert umr["temporal_provenance"] == TEMPORAL_PROVENANCE_SOURCE_RELATIVE
    assert umr["field_status"]["benchmark_timestamp"] == ORIGIN_BENCHMARK_GENERATED
    assert umr["field_status"]["benchmark_timestamp"] != ORIGIN_SOURCE_PROVIDED


# ---------------------------------------------------------------------------
# Test 3 -- relative ordering is unchanged by normalization
# ---------------------------------------------------------------------------

def test_event_order_and_turn_id_untouched_by_temporal_normalization():
    p1 = _phase1_record(event_order=17, turn_id="D1:18")
    umr = _map(p1)
    assert umr["event_order"] == 17
    assert umr["turn_id"] == "D1:18"


def test_benchmark_timestamp_preserves_within_session_ordering():
    earlier = _map(_phase1_record(timestamp_type="relative", source_timestamp=None, event_order=0, session_id="session_2"))
    later = _map(_phase1_record(timestamp_type="relative", source_timestamp=None, event_order=5, session_id="session_2"))
    assert earlier["benchmark_timestamp"] < later["benchmark_timestamp"]


def test_benchmark_timestamp_preserves_cross_session_ordering():
    session2 = _map(_phase1_record(timestamp_type="relative", source_timestamp=None, event_order=999, session_id="session_2"))
    session3 = _map(_phase1_record(timestamp_type="relative", source_timestamp=None, event_order=0, session_id="session_3"))
    assert session2["benchmark_timestamp"] < session3["benchmark_timestamp"]


# ---------------------------------------------------------------------------
# Test 4 -- determinism
# ---------------------------------------------------------------------------

def test_compute_temporal_fields_is_deterministic():
    umr_input = {
        "source_dataset": "locomo", "timestamp_type": "absolute",
        "source_timestamp": "1:56 pm on 8 May, 2023", "session_id": "session_3", "event_order": 12,
    }
    a = compute_temporal_fields(umr_input)
    b = compute_temporal_fields(umr_input)
    assert a == b


def test_full_mapping_is_deterministic():
    p1 = _phase1_record()
    assert _map(p1) == _map(p1)


# ---------------------------------------------------------------------------
# Test 5 -- missing values
# ---------------------------------------------------------------------------

def test_missing_timestamp_stays_explicitly_missing_not_invented():
    umr = _map(_phase1_record(timestamp_type="unavailable", source_timestamp=None))
    assert umr["normalized_timestamp"] is None
    assert umr["field_status"]["normalized_timestamp"] == ABSENCE_NOT_AVAILABLE
    # A benchmark coordinate IS assigned (documented policy), but it must
    # never claim to be source-observed.
    assert umr["benchmark_timestamp"] is not None
    assert umr["temporal_provenance"] != TEMPORAL_PROVENANCE_SOURCE_ABSOLUTE


# ---------------------------------------------------------------------------
# Test 6 -- duplicate timestamps preserved, not artificially uniqued
# ---------------------------------------------------------------------------

def test_duplicate_source_timestamps_are_not_artificially_altered():
    """Multiple turns in one LoCoMo/LongMemEval session legitimately share
    one session-level source_timestamp; normalized_timestamp must be
    identical for both, and event_order remains the only disambiguator."""
    same_ts = "1:56 pm on 8 May, 2023"
    a = _map(_phase1_record(source_timestamp=same_ts, event_order=0, turn_id="D1:1"))
    b = _map(_phase1_record(source_timestamp=same_ts, event_order=1, turn_id="D1:2"))
    assert a["source_timestamp"] == b["source_timestamp"]
    assert a["normalized_timestamp"] == b["normalized_timestamp"]
    assert a["event_order"] != b["event_order"]


# ---------------------------------------------------------------------------
# Test 7 -- invalid values are detected, not silently accepted
# ---------------------------------------------------------------------------

def test_malformed_absolute_timestamp_is_detected_and_flagged():
    umr = _map(_phase1_record(source_timestamp="not a real timestamp", timestamp_type="absolute"))
    assert umr["normalized_timestamp"] is None
    assert umr["field_status"]["normalized_timestamp"] == ABSENCE_UNRESOLVED
    assert DATA_QUALITY_INVALID_SOURCE_TIMESTAMP in umr["data_quality"]
    # Never silently repaired into a source_absolute claim.
    assert umr["temporal_provenance"] != TEMPORAL_PROVENANCE_SOURCE_ABSOLUTE


def test_impossible_calendar_date_is_detected_not_guessed():
    # 31 June does not exist.
    assert parse_locomo_timestamp("1:00 pm on 31 June, 2023") is None
    assert parse_longmemeval_timestamp("2023/06/31 (Sat) 13:00") is None


def test_valid_locomo_and_longmemeval_formats_parse_correctly():
    assert parse_locomo_timestamp("1:56 pm on 8 May, 2023").isoformat() == "2023-05-08T13:56:00"
    assert parse_locomo_timestamp("12:00 am on 1 January, 2024").isoformat() == "2024-01-01T00:00:00"
    assert parse_locomo_timestamp("12:00 pm on 1 January, 2024").isoformat() == "2024-01-01T12:00:00"
    assert parse_longmemeval_timestamp("2023/07/07 (Fri) 14:05").isoformat() == "2023-07-07T14:05:00"


def test_parsers_never_raise_on_none_or_empty():
    assert parse_locomo_timestamp(None) is None
    assert parse_locomo_timestamp("") is None
    assert parse_longmemeval_timestamp(None) is None
    assert parse_longmemeval_timestamp("") is None


# ---------------------------------------------------------------------------
# Test 8 -- cross-dataset normalization
# ---------------------------------------------------------------------------

def test_all_four_datasets_produce_valid_temporal_fields():
    cases = [
        ("locomo", "absolute", "1:56 pm on 8 May, 2023"),
        ("longmemeval", "absolute", "2023/07/07 (Fri) 14:05"),
        ("msc", "relative", None),
        ("conversation_chronicles", "relative", None),
    ]
    for dataset, tt, ts in cases:
        p1 = _phase1_record(source_dataset=dataset, timestamp_type=tt, source_timestamp=ts)
        umr = _map(p1)
        validate_record(umr)
        assert umr["temporal_provenance"] in VALID_TEMPORAL_PROVENANCE


# ---------------------------------------------------------------------------
# Test 9 -- no accidental fabrication
# ---------------------------------------------------------------------------

def test_relative_only_source_never_acquires_a_fake_source_absolute_label():
    for dataset in ("msc", "conversation_chronicles"):
        umr = _map(_phase1_record(source_dataset=dataset, timestamp_type="relative", source_timestamp=None))
        assert umr["temporal_provenance"] != TEMPORAL_PROVENANCE_SOURCE_ABSOLUTE
        assert umr["normalized_timestamp"] is None


def test_benchmark_assigned_coordinate_is_outside_any_real_dataset_date_range():
    """All four datasets' real timestamps are 2022 or later (see
    data/reports/*_inspection.json). The synthetic epoch anchor
    (1970-01-01) can never be confused with a real one at a glance, on
    top of the mandatory temporal_provenance field."""
    umr = _map(_phase1_record(timestamp_type="unavailable", source_timestamp=None))
    assert umr["benchmark_timestamp"].startswith("1970-")


# ---------------------------------------------------------------------------
# Test 10 -- regression: real Phase 2.2 output still validates and every
# record now carries well-formed Phase 2.3 fields. Reads the already
# generated corpus rather than rerunning the full pipeline.
# ---------------------------------------------------------------------------

def test_real_unified_memory_output_carries_valid_temporal_fields():
    import pathlib

    repo_root = pathlib.Path(__file__).resolve().parent.parent
    for dataset in ("locomo", "longmemeval", "msc", "conversation_chronicles"):
        path = repo_root / "data" / "processed" / "unified_memory" / dataset / "memory_records.jsonl"
        if not path.exists():
            continue  # real corpus not present in this environment; fixture-based tests above still cover behavior
        with path.open("r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                rec = json.loads(line)
                validate_record(rec)
                assert rec["temporal_provenance"] in VALID_TEMPORAL_PROVENANCE
                if i >= 500:
                    break
