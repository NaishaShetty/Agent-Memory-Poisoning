"""Phase 2.2: Unified Memory Record mapper tests against small synthetic
Phase 1-style fixtures. Fast, deterministic; does not touch real data/.
"""
from __future__ import annotations

from preprocessing.unified_memory import map_memory_record
from preprocessing.unified_schema import (
    ABSENCE_NOT_APPLICABLE,
    ABSENCE_NOT_AVAILABLE,
    ABSENCE_NOT_EVALUATED,
    ADMISSION_ADMISSIBLE,
    ADMISSION_FLAGGED,
    ADMISSION_QUARANTINED,
    ORIGIN_BENCHMARK_GENERATED,
    ORIGIN_INFERRED,
    ORIGIN_SOURCE_PROVIDED,
    SCHEMA_VERSION,
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


def _map(record, exception_ids=frozenset()):
    return map_memory_record(
        record,
        conversation_id_origin=ORIGIN_SOURCE_PROVIDED,
        dataset_scope="FULL_SOURCE_ACQUIRED",
        dataset_version_or_revision="v1.0",
        exception_ids=exception_ids,
        generated_at=_TS,
    )


def test_normal_record_validates_against_schema():
    umr = _map(_phase1_record())
    validate_record(umr)
    assert umr["schema_version"] == SCHEMA_VERSION


def test_memory_id_is_reused_from_phase1_not_regenerated():
    p1 = _phase1_record()
    umr = _map(p1)
    assert umr["memory_id"] == p1["memory_id"]
    assert umr["field_status"]["memory_id"] == ORIGIN_BENCHMARK_GENERATED


def test_source_provided_content_is_not_marked_benchmark_generated():
    umr = _map(_phase1_record())
    assert umr["field_status"]["content"] == ORIGIN_SOURCE_PROVIDED
    assert umr["field_status"]["source_dataset"] == ORIGIN_SOURCE_PROVIDED


def test_benchmark_generated_fields_are_not_marked_source_provided():
    umr = _map(_phase1_record())
    assert umr["field_status"]["event_order"] == ORIGIN_BENCHMARK_GENERATED
    assert umr["field_status"]["provenance"] == ORIGIN_BENCHMARK_GENERATED


def test_turn_id_origin_follows_data_quality_flag_not_dataset_name():
    """The same field must be classified differently per-record based on
    real evidence (Phase 1's own data_quality flag), not a hardcoded
    per-dataset assumption -- this is the key mapping-correctness property."""
    native = _map(_phase1_record(turn_id="D1:1", data_quality=[]))
    derived = _map(_phase1_record(turn_id="session_1:0", data_quality=["turn_id_derived_positional"]))
    assert native["field_status"]["turn_id"] == ORIGIN_SOURCE_PROVIDED
    assert derived["field_status"]["turn_id"] == ORIGIN_BENCHMARK_GENERATED


def test_missing_optional_fields_use_not_available_not_a_guess():
    umr = _map(_phase1_record(source_role=None, source_timestamp=None, turn_id=None))
    assert umr["source_role"] is None
    assert umr["field_status"]["source_role"] == ABSENCE_NOT_AVAILABLE
    assert umr["field_status"]["source_timestamp"] == ABSENCE_NOT_AVAILABLE
    assert umr["field_status"]["turn_id"] == ABSENCE_NOT_AVAILABLE


def test_future_phase_fields_are_null_and_explicitly_not_evaluated():
    umr = _map(_phase1_record())
    for field in ("trust_score", "security_state", "embedding"):
        assert umr[field] is None
        assert umr["field_status"][field] == ABSENCE_NOT_EVALUATED
    assert umr["poison_status"] is None
    assert umr["field_status"]["poison_status"] == ABSENCE_NOT_APPLICABLE


def test_no_synthetic_absolute_timestamp_is_ever_written_to_normalized_timestamp():
    """Phase 2.2 boundary ('no synthetic timestamp') meant no fabricated
    ABSOLUTE time. Phase 2.3 (preprocessing/temporal.py) is explicitly the
    phase that may assign a deterministic, clearly-non-real
    benchmark_timestamp for common-coordinate purposes when no source
    absolute time exists -- but it must never be written into
    normalized_timestamp (which is reserved for real, source-parsed
    absolute time) and must always be marked BENCHMARK_GENERATED, never
    SOURCE_PROVIDED. See tests/test_temporal_normalization.py for the full
    Phase 2.3 test suite."""
    umr = _map(_phase1_record(source_timestamp=None, timestamp_type="unavailable"))
    assert umr["normalized_timestamp"] is None
    assert umr["field_status"]["normalized_timestamp"] == ABSENCE_NOT_AVAILABLE
    assert umr["benchmark_timestamp"] is not None
    assert umr["field_status"]["benchmark_timestamp"] == ORIGIN_BENCHMARK_GENERATED
    assert umr["temporal_provenance"] == "source_relative"


def test_derivation_and_propagation_structures_are_empty_not_fabricated():
    umr = _map(_phase1_record())
    assert umr["derivation_parents"] == []
    assert umr["retrieval_history"] == []
    assert umr["propagation_history"] == []
    assert umr["field_status"]["derivation_parents"] == ABSENCE_NOT_AVAILABLE


def test_quality_status_and_flags_survive_mapping_unchanged():
    p1 = _phase1_record(quality_status="repaired", data_quality=["whitespace_normalized"])
    umr = _map(p1)
    assert umr["quality_status"] == "repaired"
    assert umr["data_quality"] == ["whitespace_normalized"]


def test_admission_status_admissible_for_ordinary_valid_record():
    umr = _map(_phase1_record(quality_status="valid"))
    assert umr["admission_status"] == ADMISSION_ADMISSIBLE
    assert umr["trusted_clean_memory"] is True


def test_admission_status_flagged_for_valid_flagged_quality():
    umr = _map(_phase1_record(quality_status="valid_flagged"))
    assert umr["admission_status"] == ADMISSION_FLAGGED
    assert umr["trusted_clean_memory"] is False


def test_admission_status_quarantined_via_general_exception_rule_not_hardcoded_id():
    """The rule is generic (memory_id in exception_ids), demonstrated here
    with an arbitrary synthetic ID, not the real LongMemEval IDs -- proving
    the mechanism isn't an ad hoc filter keyed to two specific strings."""
    p1 = _phase1_record(memory_id="zzz999zzz999zzz999zzz99", quality_status="valid")
    umr = _map(p1, exception_ids=frozenset({"zzz999zzz999zzz999zzz99"}))
    assert umr["admission_status"] == ADMISSION_QUARANTINED
    assert umr["trusted_clean_memory"] is False


def test_conversation_id_origin_is_explicit_and_dataset_supplied():
    umr = map_memory_record(
        _phase1_record(),
        conversation_id_origin=ORIGIN_INFERRED,
        dataset_scope="FULL_SOURCE_ACQUIRED",
        dataset_version_or_revision=None,
        exception_ids=frozenset(),
        generated_at=_TS,
    )
    assert umr["field_status"]["conversation_id"] == ORIGIN_INFERRED
    assert umr["field_status"]["dataset_version_or_revision"] == ABSENCE_NOT_AVAILABLE


def test_mapping_is_deterministic():
    p1 = _phase1_record()
    a = _map(p1)
    b = _map(p1)
    assert a == b


def test_metadata_is_preserved_verbatim():
    p1 = _phase1_record(metadata={"persona": "x", "image_url": "http://example.com/1.png"})
    umr = _map(p1)
    assert umr["metadata"] == p1["metadata"]


def test_schema_validation_rejects_bad_field_status():
    umr = _map(_phase1_record())
    umr["field_status"]["content"] = "NOT_A_REAL_STATUS"
    import pytest
    with pytest.raises(Exception):
        validate_record(umr)


def test_schema_validation_rejects_missing_required_field():
    umr = _map(_phase1_record())
    del umr["memory_id"]
    import pytest
    with pytest.raises(Exception):
        validate_record(umr)
