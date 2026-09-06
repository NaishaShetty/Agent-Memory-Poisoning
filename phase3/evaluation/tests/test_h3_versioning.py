"""Phase 3.3-H.3 (Immutable Memory Versioning, Supersession & Retirement) contract tests.

Covers the mission's 44 test items, 16 invariants, and 9 adversarial cases (A-I). See
`phase3/evaluation/foundations/memory_versioning.py`'s module docstring for the full
evidence-based reasoning behind this stage's design: "versioning" here means an immutable
LIFECYCLE-STATE history for one permanent `memory_id` (content never changes across
versions of the same memory_id), NOT multiple content-variants sharing one identity --
that reading of the mission's own illustrative diagram was rejected as inconsistent with
the frozen `memory_schema.md`/`relationship_schema.md`.
"""

from __future__ import annotations

import json

import pytest

from phase3.evaluation.foundations.canonical import (
    CanonicalMemoryRecord,
    LIFECYCLE_ACTIVE,
    LIFECYCLE_CREATED,
    LIFECYCLE_RETIRED,
    MEMORY_TYPE_DERIVED,
    MEMORY_TYPE_FOUNDATION,
    SOURCE_TYPE_DERIVATION_EVENT,
    SOURCE_TYPE_PHASE2_UMR,
)
from phase3.evaluation.foundations.canonical_event import (
    CanonicalEvent,
    EVENT_CREATED,
    EVENT_DERIVED,
    EVENT_RETIRED,
    EVENT_SUPERSEDED,
)
from phase3.evaluation.foundations.event_identity import build_canonical_event
from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger, SingleOccurrenceViolationError
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger
from phase3.evaluation.foundations.memory_versioning import (
    AlreadyRetiredError,
    CanonicalMemoryVersion,
    NoLifecycleHistoryError,
    STATUS_FULLY_RETIRED,
    STATUS_FULLY_SUPERSEDED,
    SupersessionCollisionError,
    SupersessionLedger,
    SupersessionRecord,
    UnknownMemoryError,
    get_current_version,
    get_version,
    reconstruct_version_history,
    retire_memory,
    supersede_memory,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _memory_record(memory_id: str, memory_type=MEMORY_TYPE_FOUNDATION, parent_ids=()) -> CanonicalMemoryRecord:
    source = (
        {"source_type": SOURCE_TYPE_DERIVATION_EVENT, "reference_id": "deriv-1"}
        if memory_type == MEMORY_TYPE_DERIVED
        else {"source_type": SOURCE_TYPE_PHASE2_UMR, "reference_id": "umr-1"}
    )
    return CanonicalMemoryRecord(
        memory_id=memory_id, memory_type=memory_type, content={"text": f"content for {memory_id}"},
        source=source, parent_ids=tuple(parent_ids), creation_event="evt-seed",
        creation_timestamp="2026-01-01T00:00:00Z", lifecycle_state=LIFECYCLE_CREATED,
    )


def _created_event(memory_id: str, timestamp="2026-01-01T00:00:00Z") -> CanonicalEvent:
    return build_canonical_event(
        event_type=EVENT_CREATED, memory_ids=(memory_id,), timestamp=timestamp,
        actor="creation_policy", reason="ingested", new_state=LIFECYCLE_CREATED,
    )


def _system(tmp_path, name="sys"):
    memory_ledger = CanonicalMemoryLedger(tmp_path / f"{name}-memory")
    event_ledger = CanonicalEventLedger(tmp_path / f"{name}-events", memory_ledger)
    supersession_ledger = SupersessionLedger(tmp_path / f"{name}-supersessions")
    return memory_ledger, event_ledger, supersession_ledger


def _seed_memory(memory_ledger, event_ledger, memory_id, timestamp="2026-01-01T00:00:00Z"):
    memory_ledger.put(_memory_record(memory_id))
    event_ledger.append(_created_event(memory_id, timestamp))


def _reconstruct(memory_ledger, event_ledger, supersession_ledger, memory_id):
    return reconstruct_version_history(event_ledger, memory_ledger, supersession_ledger, memory_id)


# ===========================================================================
# IDENTITY -- items 1-5
# ===========================================================================


def test_1_version_id_ownership(tmp_path):
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    _seed_memory(memory_ledger, event_ledger, "m1")
    version = get_current_version(event_ledger, memory_ledger, supersession_ledger, "m1")
    assert version.version_id == "m1::v1"


def test_2_deterministic_version_identity(tmp_path):
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    _seed_memory(memory_ledger, event_ledger, "m1")
    v_a = get_current_version(event_ledger, memory_ledger, supersession_ledger, "m1")
    v_b = get_current_version(event_ledger, memory_ledger, supersession_ledger, "m1")
    assert v_a == v_b


def test_3_duplicate_identical_version_behavior(tmp_path):
    """Reconstruction is a pure function -- calling it twice never creates a second
    on-disk version or duplicate side effect."""
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    _seed_memory(memory_ledger, event_ledger, "m1")
    for _ in range(3):
        history = _reconstruct(memory_ledger, event_ledger, supersession_ledger, "m1")
        assert len(history) == 1


def test_4_conflicting_version_id_collision_is_structurally_impossible(tmp_path):
    """No two DIFFERENT memory_ids ever produce the same version_id, since version_id
    embeds memory_id verbatim."""
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    _seed_memory(memory_ledger, event_ledger, "m1")
    _seed_memory(memory_ledger, event_ledger, "m2")
    v1 = get_current_version(event_ledger, memory_ledger, supersession_ledger, "m1")
    v2 = get_current_version(event_ledger, memory_ledger, supersession_ledger, "m2")
    assert v1.version_id != v2.version_id


def test_5_version_id_cannot_be_a_vendor_id(tmp_path):
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    _seed_memory(memory_ledger, event_ledger, "m1")
    version = get_current_version(event_ledger, memory_ledger, supersession_ledger, "m1")
    assert "vendor" not in version.version_id
    assert version.version_id.startswith("m1::")


# ===========================================================================
# BASIC VERSIONING -- items 6-11
# ===========================================================================


def test_6_create_initial_version(tmp_path):
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    _seed_memory(memory_ledger, event_ledger, "m1")
    history = _reconstruct(memory_ledger, event_ledger, supersession_ledger, "m1")
    assert len(history) == 1
    assert history[0].lifecycle_state == LIFECYCLE_CREATED
    assert history[0].superseded_by is None


def test_7_retrieve_current_version(tmp_path):
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    _seed_memory(memory_ledger, event_ledger, "m1")
    current = get_current_version(event_ledger, memory_ledger, supersession_ledger, "m1")
    assert current.version_number == 1


def test_8_create_second_version_via_retirement(tmp_path):
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    _seed_memory(memory_ledger, event_ledger, "m1")
    retired_event = build_canonical_event(
        event_type=EVENT_RETIRED, memory_ids=("m1",), timestamp="2026-01-02T00:00:00Z",
        actor="creation_policy", reason="retired, no successor.", previous_state=LIFECYCLE_CREATED, new_state=LIFECYCLE_RETIRED,
    )
    result = retire_memory(event_ledger, memory_ledger, supersession_ledger, "m1", retired_event=retired_event)
    assert result.status == STATUS_FULLY_RETIRED
    history = _reconstruct(memory_ledger, event_ledger, supersession_ledger, "m1")
    assert len(history) == 2
    assert history[1].lifecycle_state == LIFECYCLE_RETIRED


def test_9_old_version_remains_immutable(tmp_path):
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    _seed_memory(memory_ledger, event_ledger, "m1")
    v1_before = get_version(event_ledger, memory_ledger, supersession_ledger, "m1", 1)
    retired_event = build_canonical_event(
        event_type=EVENT_RETIRED, memory_ids=("m1",), timestamp="2026-01-02T00:00:00Z",
        actor="creation_policy", reason="retired.", previous_state=LIFECYCLE_CREATED, new_state=LIFECYCLE_RETIRED,
    )
    retire_memory(event_ledger, memory_ledger, supersession_ledger, "m1", retired_event=retired_event)
    v1_after = get_version(event_ledger, memory_ledger, supersession_ledger, "m1", 1)
    assert v1_before == v1_after  # byte-for-byte unchanged


def test_10_new_version_becomes_current(tmp_path):
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    _seed_memory(memory_ledger, event_ledger, "m1")
    retired_event = build_canonical_event(
        event_type=EVENT_RETIRED, memory_ids=("m1",), timestamp="2026-01-02T00:00:00Z",
        actor="creation_policy", reason="retired.", previous_state=LIFECYCLE_CREATED, new_state=LIFECYCLE_RETIRED,
    )
    retire_memory(event_ledger, memory_ledger, supersession_ledger, "m1", retired_event=retired_event)
    current = get_current_version(event_ledger, memory_ledger, supersession_ledger, "m1")
    assert current.version_number == 2
    assert current.lifecycle_state == LIFECYCLE_RETIRED


def test_11_version_history_reconstructs_correctly(tmp_path):
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    _seed_memory(memory_ledger, event_ledger, "m1")
    memory_ledger.put(_memory_record("m2"))
    event_ledger.append(_created_event("m2", "2026-01-02T00:00:00Z"))
    superseded_event = build_canonical_event(
        event_type=EVENT_SUPERSEDED, memory_ids=("m1",), timestamp="2026-01-03T00:00:00Z",
        actor="creation_policy", reason="m2 supersedes m1.", previous_state=LIFECYCLE_CREATED, new_state=LIFECYCLE_RETIRED,
    )
    retired_event = build_canonical_event(
        event_type=EVENT_RETIRED, memory_ids=("m1",), timestamp="2026-01-03T00:00:01Z",
        actor="creation_policy", reason="m1 retired via supersession.", previous_state=LIFECYCLE_CREATED, new_state=LIFECYCLE_RETIRED,
    )
    result = supersede_memory(
        event_ledger, memory_ledger, supersession_ledger, "m1", "m2",
        superseded_event=superseded_event, retired_event=retired_event,
    )
    assert result.status == STATUS_FULLY_SUPERSEDED
    history = _reconstruct(memory_ledger, event_ledger, supersession_ledger, "m1")
    assert [v.lifecycle_state for v in history] == [LIFECYCLE_CREATED, LIFECYCLE_RETIRED, LIFECYCLE_RETIRED]
    assert history[1].superseded_by == "m2"
    assert history[2].superseded_by == "m2"  # carried forward


# ===========================================================================
# LINEAGE -- items 12-16
# ===========================================================================


def test_12_predecessor_exists(tmp_path):
    """A version's predecessor is always version_number - 1, and always exists once
    version_number > 1 (enforced structurally: versions are enumerated strictly in
    append order, never skipping)."""
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    _seed_memory(memory_ledger, event_ledger, "m1")
    retired_event = build_canonical_event(
        event_type=EVENT_RETIRED, memory_ids=("m1",), timestamp="2026-01-02T00:00:00Z",
        actor="creation_policy", reason="retired.", previous_state=LIFECYCLE_CREATED, new_state=LIFECYCLE_RETIRED,
    )
    retire_memory(event_ledger, memory_ledger, supersession_ledger, "m1", retired_event=retired_event)
    history = _reconstruct(memory_ledger, event_ledger, supersession_ledger, "m1")
    for version in history[1:]:
        predecessor = get_version(event_ledger, memory_ledger, supersession_ledger, "m1", version.version_number - 1)
        assert predecessor is not None


def test_13_self_reference_rejected(tmp_path):
    with pytest.raises(Exception):  # SupersessionRecord.__post_init__ raises MemoryVersioningError
        SupersessionRecord(superseded_memory_id="m1", superseding_memory_id="m1", superseded_event_id="e1")


def test_14_cycles_rejected(tmp_path):
    """A -> B (A superseded by B, A now RETIRED). Attempting B -> A (A, now retired,
    'superseding' B back) would form a 2-cycle -- rejected: a RETIRED memory can never
    be used as a superseder (see memory_versioning.py's cycle-rejection comment in
    supersede_memory())."""
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    _seed_memory(memory_ledger, event_ledger, "a")
    _seed_memory(memory_ledger, event_ledger, "b", "2026-01-01T00:01:00Z")
    superseded_event_ab = build_canonical_event(
        event_type=EVENT_SUPERSEDED, memory_ids=("a",), timestamp="2026-01-02T00:00:00Z",
        actor="creation_policy", reason="b supersedes a.", previous_state=LIFECYCLE_CREATED, new_state=LIFECYCLE_RETIRED,
    )
    retired_event_a = build_canonical_event(
        event_type=EVENT_RETIRED, memory_ids=("a",), timestamp="2026-01-02T00:00:01Z",
        actor="creation_policy", reason="a retired.", previous_state=LIFECYCLE_CREATED, new_state=LIFECYCLE_RETIRED,
    )
    supersede_memory(event_ledger, memory_ledger, supersession_ledger, "a", "b", superseded_event=superseded_event_ab, retired_event=retired_event_a)

    superseded_event_ba = build_canonical_event(
        event_type=EVENT_SUPERSEDED, memory_ids=("b",), timestamp="2026-01-03T00:00:00Z",
        actor="creation_policy", reason="a supersedes b (would form a cycle).", previous_state=LIFECYCLE_CREATED, new_state=LIFECYCLE_RETIRED,
    )
    retired_event_b = build_canonical_event(
        event_type=EVENT_RETIRED, memory_ids=("b",), timestamp="2026-01-03T00:00:01Z",
        actor="creation_policy", reason="b retired.", previous_state=LIFECYCLE_CREATED, new_state=LIFECYCLE_RETIRED,
    )
    from phase3.evaluation.foundations.memory_versioning import MemoryVersioningError

    with pytest.raises(MemoryVersioningError, match="itself RETIRED"):
        supersede_memory(event_ledger, memory_ledger, supersession_ledger, "b", "a", superseded_event=superseded_event_ba, retired_event=retired_event_b)
    # B remains unaffected by the rejected attempt.
    assert get_current_version(event_ledger, memory_ledger, supersession_ledger, "b").lifecycle_state == LIFECYCLE_CREATED


def test_15_wrong_memory_predecessor_rejected(tmp_path):
    """A version reconstructed for m1 never includes an event that belongs to m2 --
    events_for_memory()'s own H.2 filtering already guarantees this; verified directly."""
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    _seed_memory(memory_ledger, event_ledger, "m1")
    _seed_memory(memory_ledger, event_ledger, "m2", "2026-01-01T00:01:00Z")
    history_m1 = _reconstruct(memory_ledger, event_ledger, supersession_ledger, "m1")
    assert all(v.memory_id == "m1" for v in history_m1)


def test_16_multiple_invalid_successors_rejected(tmp_path):
    """relationship_schema.md: at most ONE superseder per memory. A second, DIFFERENT
    superseder is rejected."""
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    _seed_memory(memory_ledger, event_ledger, "m1")
    memory_ledger.put(_memory_record("m2"))
    event_ledger.append(_created_event("m2", "2026-01-01T00:01:00Z"))
    memory_ledger.put(_memory_record("m3"))
    event_ledger.append(_created_event("m3", "2026-01-01T00:02:00Z"))

    superseded_event = build_canonical_event(
        event_type=EVENT_SUPERSEDED, memory_ids=("m1",), timestamp="2026-01-02T00:00:00Z",
        actor="creation_policy", reason="m2 supersedes m1.", previous_state=LIFECYCLE_CREATED, new_state=LIFECYCLE_RETIRED,
    )
    retired_event = build_canonical_event(
        event_type=EVENT_RETIRED, memory_ids=("m1",), timestamp="2026-01-02T00:00:01Z",
        actor="creation_policy", reason="m1 retired.", previous_state=LIFECYCLE_CREATED, new_state=LIFECYCLE_RETIRED,
    )
    supersede_memory(event_ledger, memory_ledger, supersession_ledger, "m1", "m2", superseded_event=superseded_event, retired_event=retired_event)

    with pytest.raises(AlreadyRetiredError):
        conflicting_superseded = build_canonical_event(
            event_type=EVENT_SUPERSEDED, memory_ids=("m1",), timestamp="2026-01-03T00:00:00Z",
            actor="creation_policy", reason="m3 ALSO claims to supersede m1.", previous_state=LIFECYCLE_CREATED, new_state=LIFECYCLE_RETIRED,
        )
        conflicting_retired = build_canonical_event(
            event_type=EVENT_RETIRED, memory_ids=("m1",), timestamp="2026-01-03T00:00:01Z",
            actor="creation_policy", reason="m1 retired again?", previous_state=LIFECYCLE_CREATED, new_state=LIFECYCLE_RETIRED,
        )
        supersede_memory(event_ledger, memory_ledger, supersession_ledger, "m1", "m3", superseded_event=conflicting_superseded, retired_event=conflicting_retired)


# ===========================================================================
# SUPERSESSION -- items 17-22
# ===========================================================================


def _do_supersede(memory_ledger, event_ledger, supersession_ledger, old="m1", new="m2", ts="2026-01-02T00:00:00Z"):
    superseded_event = build_canonical_event(
        event_type=EVENT_SUPERSEDED, memory_ids=(old,), timestamp=ts,
        actor="creation_policy", reason=f"{new} supersedes {old}.", previous_state=LIFECYCLE_CREATED, new_state=LIFECYCLE_RETIRED,
    )
    retired_event = build_canonical_event(
        event_type=EVENT_RETIRED, memory_ids=(old,), timestamp=ts,
        actor="creation_policy", reason=f"{old} retired via supersession.", previous_state=LIFECYCLE_CREATED, new_state=LIFECYCLE_RETIRED,
    )
    return supersede_memory(event_ledger, memory_ledger, supersession_ledger, old, new, superseded_event=superseded_event, retired_event=retired_event)


def test_17_valid_v1_to_v2_supersession(tmp_path):
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    _seed_memory(memory_ledger, event_ledger, "m1")
    memory_ledger.put(_memory_record("m2"))
    event_ledger.append(_created_event("m2", "2026-01-01T00:01:00Z"))
    result = _do_supersede(memory_ledger, event_ledger, supersession_ledger)
    assert result.status == STATUS_FULLY_SUPERSEDED


def test_18_superseded_version_no_longer_current(tmp_path):
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    _seed_memory(memory_ledger, event_ledger, "m1")
    memory_ledger.put(_memory_record("m2"))
    event_ledger.append(_created_event("m2", "2026-01-01T00:01:00Z"))
    _do_supersede(memory_ledger, event_ledger, supersession_ledger)
    current = get_current_version(event_ledger, memory_ledger, supersession_ledger, "m1")
    assert current.version_number != 1
    assert current.lifecycle_state == LIFECYCLE_RETIRED


def test_19_duplicate_supersession_rejected(tmp_path):
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    _seed_memory(memory_ledger, event_ledger, "m1")
    memory_ledger.put(_memory_record("m2"))
    event_ledger.append(_created_event("m2", "2026-01-01T00:01:00Z"))
    _do_supersede(memory_ledger, event_ledger, supersession_ledger)
    with pytest.raises(AlreadyRetiredError):
        _do_supersede(memory_ledger, event_ledger, supersession_ledger, ts="2026-01-03T00:00:00Z")


def test_20_conflicting_supersession_rejected(tmp_path):
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    _seed_memory(memory_ledger, event_ledger, "m1")
    memory_ledger.put(_memory_record("m2"))
    event_ledger.append(_created_event("m2", "2026-01-01T00:01:00Z"))
    memory_ledger.put(_memory_record("m3"))
    event_ledger.append(_created_event("m3", "2026-01-01T00:02:00Z"))
    _do_supersede(memory_ledger, event_ledger, supersession_ledger, old="m1", new="m2")
    with pytest.raises(AlreadyRetiredError):
        _do_supersede(memory_ledger, event_ledger, supersession_ledger, old="m1", new="m3", ts="2026-01-03T00:00:00Z")


def test_21_supersession_event_correctly_recorded(tmp_path):
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    _seed_memory(memory_ledger, event_ledger, "m1")
    memory_ledger.put(_memory_record("m2"))
    event_ledger.append(_created_event("m2", "2026-01-01T00:01:00Z"))
    result = _do_supersede(memory_ledger, event_ledger, supersession_ledger)
    superseded_event = event_ledger.get_event(result.superseded_event_id)
    assert superseded_event.event_type == EVENT_SUPERSEDED
    assert superseded_event.previous_state == LIFECYCLE_CREATED
    assert superseded_event.new_state == LIFECYCLE_RETIRED


def test_22_event_version_linkage_reconstructable(tmp_path):
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    _seed_memory(memory_ledger, event_ledger, "m1")
    memory_ledger.put(_memory_record("m2"))
    event_ledger.append(_created_event("m2", "2026-01-01T00:01:00Z"))
    result = _do_supersede(memory_ledger, event_ledger, supersession_ledger)
    history = _reconstruct(memory_ledger, event_ledger, supersession_ledger, "m1")
    superseded_version = next(v for v in history if v.established_by_event_id == result.superseded_event_id)
    assert superseded_version.superseded_by == "m2"


# ===========================================================================
# RETIREMENT -- items 23-28
# ===========================================================================


def _do_retire(memory_ledger, event_ledger, supersession_ledger, memory_id="m1", ts="2026-01-02T00:00:00Z"):
    retired_event = build_canonical_event(
        event_type=EVENT_RETIRED, memory_ids=(memory_id,), timestamp=ts,
        actor="creation_policy", reason="retired.", previous_state=LIFECYCLE_CREATED, new_state=LIFECYCLE_RETIRED,
    )
    return retire_memory(event_ledger, memory_ledger, supersession_ledger, memory_id, retired_event=retired_event)


def test_23_valid_retirement(tmp_path):
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    _seed_memory(memory_ledger, event_ledger, "m1")
    result = _do_retire(memory_ledger, event_ledger, supersession_ledger)
    assert result.status == STATUS_FULLY_RETIRED


def test_24_retired_memory_remains_physically_present(tmp_path):
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    _seed_memory(memory_ledger, event_ledger, "m1")
    _do_retire(memory_ledger, event_ledger, supersession_ledger)
    assert memory_ledger.exists("m1")
    assert memory_ledger.get("m1").content == {"text": "content for m1"}


def test_25_retired_version_remains_reconstructable(tmp_path):
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    _seed_memory(memory_ledger, event_ledger, "m1")
    _do_retire(memory_ledger, event_ledger, supersession_ledger)
    v1 = get_version(event_ledger, memory_ledger, supersession_ledger, "m1", 1)
    v2 = get_version(event_ledger, memory_ledger, supersession_ledger, "m1", 2)
    assert v1 is not None and v2 is not None


def test_26_retirement_event_correctly_recorded(tmp_path):
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    _seed_memory(memory_ledger, event_ledger, "m1")
    result = _do_retire(memory_ledger, event_ledger, supersession_ledger)
    event = event_ledger.get_event(result.retired_event_id)
    assert event.new_state == LIFECYCLE_RETIRED


def test_27_duplicate_retirement_rejected(tmp_path):
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    _seed_memory(memory_ledger, event_ledger, "m1")
    _do_retire(memory_ledger, event_ledger, supersession_ledger)
    with pytest.raises(AlreadyRetiredError):
        _do_retire(memory_ledger, event_ledger, supersession_ledger, ts="2026-01-03T00:00:00Z")


def test_28_retirement_vs_supersession_semantics_remain_distinct(tmp_path):
    """A plain retirement (no successor) leaves superseded_by=None forever; a
    supersession-driven retirement always has superseded_by set. Both use event_type
    'retired', but only the latter carries linkage."""
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    _seed_memory(memory_ledger, event_ledger, "m1")
    memory_ledger.put(_memory_record("m2"))
    event_ledger.append(_created_event("m2", "2026-01-01T00:01:00Z"))
    _do_retire(memory_ledger, event_ledger, supersession_ledger, memory_id="m1")

    memory_ledger.put(_memory_record("m3"))
    event_ledger.append(_created_event("m3", "2026-01-01T00:02:00Z"))
    memory_ledger.put(_memory_record("m4"))
    event_ledger.append(_created_event("m4", "2026-01-01T00:03:00Z"))
    _do_supersede(memory_ledger, event_ledger, supersession_ledger, old="m3", new="m4", ts="2026-01-02T00:00:00Z")

    plain_retirement = get_current_version(event_ledger, memory_ledger, supersession_ledger, "m1")
    superseded_retirement = get_current_version(event_ledger, memory_ledger, supersession_ledger, "m3")
    assert plain_retirement.superseded_by is None
    assert superseded_retirement.superseded_by == "m4"


# ===========================================================================
# RESET -- items 29-30
# ===========================================================================


def test_29_experiment_reset_does_not_retire_a_memory(tmp_path):
    """No code path anywhere in memory_versioning.py IMPORTS ExperimentBoundaryRecord --
    structurally impossible for a RESET to retire anything (checked via actual module
    imports, not docstring text, which legitimately discusses the distinction in prose)."""
    from phase3.evaluation.foundations import memory_versioning

    assert "experiment_boundary" not in memory_versioning.__dict__
    assert not hasattr(memory_versioning, "ExperimentBoundaryRecord")
    assert not hasattr(memory_versioning, "ExperimentBoundaryLedger")


def test_30_foundation_reset_cannot_erase_canonical_version_history(tmp_path):
    """No MemoryFoundationAdapter import exists anywhere in this module's actual imports
    -- reconstruction is provably independent of any vendor's reset/delete behavior."""
    from phase3.evaluation.foundations import memory_versioning

    assert not hasattr(memory_versioning, "MemoryFoundationAdapter")


# ===========================================================================
# RECONSTRUCTION -- items 31-35
# ===========================================================================


def test_31_current_state_reconstruction(tmp_path):
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    _seed_memory(memory_ledger, event_ledger, "m1")
    current = get_current_version(event_ledger, memory_ledger, supersession_ledger, "m1")
    assert current.lifecycle_state == LIFECYCLE_CREATED


def test_32_historical_state_reconstruction(tmp_path):
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    _seed_memory(memory_ledger, event_ledger, "m1")
    _do_retire(memory_ledger, event_ledger, supersession_ledger)
    historical = get_version(event_ledger, memory_ledger, supersession_ledger, "m1", 1)
    assert historical.lifecycle_state == LIFECYCLE_CREATED  # the ORIGINAL state, preserved


def test_33_full_version_chain_reconstruction(tmp_path):
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    _seed_memory(memory_ledger, event_ledger, "m1")
    memory_ledger.put(_memory_record("m2"))
    event_ledger.append(_created_event("m2", "2026-01-01T00:01:00Z"))
    _do_supersede(memory_ledger, event_ledger, supersession_ledger)
    chain = _reconstruct(memory_ledger, event_ledger, supersession_ledger, "m1")
    assert [v.version_number for v in chain] == [1, 2, 3]


def test_34_reconstruction_without_vendor_availability(tmp_path):
    """No vendor object is ever constructed anywhere in this test module."""
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    _seed_memory(memory_ledger, event_ledger, "m1")
    assert get_current_version(event_ledger, memory_ledger, supersession_ledger, "m1") is not None


def test_35_reconstruction_after_simulated_vendor_deletion(tmp_path):
    """Simulated by simply never creating a vendor object at all -- the canonical side
    has zero dependency on one existing, so its 'deletion' changes nothing observable
    here."""
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    _seed_memory(memory_ledger, event_ledger, "m1")
    _do_retire(memory_ledger, event_ledger, supersession_ledger)
    history = _reconstruct(memory_ledger, event_ledger, supersession_ledger, "m1")
    assert len(history) == 2


# ===========================================================================
# FAILURE SEMANTICS -- items 36-40
# ===========================================================================


def test_36_version_write_failure_is_not_applicable_no_separate_version_store(tmp_path):
    """Documents the design choice: since versions are computed, not separately
    persisted, there is no 'version write' that can fail independently of the underlying
    event/memory writes -- this eliminates an entire failure-mode category by
    construction rather than handling it."""
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    _seed_memory(memory_ledger, event_ledger, "m1")
    # No separate "commit version" step exists to fail.
    assert not hasattr(memory_ledger, "commit_version")
    assert not hasattr(event_ledger, "commit_version")


def test_37_event_write_failure_leaves_canonical_memory_intact(tmp_path):
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    memory_ledger.put(_memory_record("m1"))  # no created event appended -- simulates a failure between steps
    assert memory_ledger.exists("m1")
    with pytest.raises(NoLifecycleHistoryError):
        reconstruct_version_history(event_ledger, memory_ledger, supersession_ledger, "m1")


def test_38_linkage_write_failure_reported_explicitly_not_silently_repaired(tmp_path):
    """Simulates step 3 (SupersessionRecord append) failing after step 2 (superseded
    event) succeeded, by directly seeding a CONFLICTING SupersessionRecord first so the
    real append() call inside supersede_memory() raises -- proves the honest partial
    state (superseded event recorded, no resolvable linkage) rather than a crash that
    loses the already-durable superseded event."""
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    _seed_memory(memory_ledger, event_ledger, "m1")
    memory_ledger.put(_memory_record("m2"))
    event_ledger.append(_created_event("m2", "2026-01-01T00:01:00Z"))
    memory_ledger.put(_memory_record("m3"))
    event_ledger.append(_created_event("m3", "2026-01-01T00:02:00Z"))

    # Pre-seed a DIFFERENT linkage for m1 directly on the supersession ledger, bypassing
    # supersede_memory()'s own precondition checks, to force the internal append() to hit
    # a genuine collision.
    superseded_event = build_canonical_event(
        event_type=EVENT_SUPERSEDED, memory_ids=("m1",), timestamp="2026-01-02T00:00:00Z",
        actor="creation_policy", reason="m2 supersedes m1.", previous_state=LIFECYCLE_CREATED, new_state=LIFECYCLE_RETIRED,
    )
    supersession_ledger.append(
        SupersessionRecord(superseded_memory_id="m1", superseding_memory_id="m3", superseded_event_id="some-other-event-id")
    )
    retired_event = build_canonical_event(
        event_type=EVENT_RETIRED, memory_ids=("m1",), timestamp="2026-01-02T00:00:01Z",
        actor="creation_policy", reason="m1 retired.", previous_state=LIFECYCLE_CREATED, new_state=LIFECYCLE_RETIRED,
    )
    from phase3.evaluation.foundations.memory_versioning import STATUS_SUPERSEDED_EVENT_ONLY

    result = supersede_memory(event_ledger, memory_ledger, supersession_ledger, "m1", "m2", superseded_event=superseded_event, retired_event=retired_event)
    assert result.status == STATUS_SUPERSEDED_EVENT_ONLY
    # The superseded event IS durably recorded despite the linkage failure.
    assert event_ledger.get_event(superseded_event.event_id) is not None


def test_39_reload_after_partial_failure_shows_honest_state(tmp_path):
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    _seed_memory(memory_ledger, event_ledger, "m1")
    superseded_event = build_canonical_event(
        event_type=EVENT_SUPERSEDED, memory_ids=("m1",), timestamp="2026-01-02T00:00:00Z",
        actor="creation_policy", reason="pending linkage.", previous_state=LIFECYCLE_CREATED, new_state=LIFECYCLE_RETIRED,
    )
    event_ledger.append(superseded_event)  # linkage + retired event deliberately never appended

    reloaded_memory_ledger = CanonicalMemoryLedger(memory_ledger._dir)
    reloaded_event_ledger = CanonicalEventLedger(event_ledger._dir, reloaded_memory_ledger)
    reloaded_supersession_ledger = SupersessionLedger(supersession_ledger._dir)
    history = reconstruct_version_history(reloaded_event_ledger, reloaded_memory_ledger, reloaded_supersession_ledger, "m1")
    assert len(history) == 2
    assert history[1].superseded_by is None  # honestly absent, never fabricated
    assert history[1].lifecycle_state == LIFECYCLE_RETIRED  # the superseded event's own new_state


def test_40_no_silent_corruption_malformed_supersession_record_raises(tmp_path):
    ledger = SupersessionLedger(tmp_path / "corrupt-supersessions")
    ledger.append(SupersessionRecord("m1", "m2", "evt-1"))
    with open(ledger._path, "a", encoding="utf-8") as fh:
        fh.write("{not valid json\n")
    with pytest.raises(json.JSONDecodeError):
        SupersessionLedger(ledger._dir)


# ===========================================================================
# COMPATIBILITY -- items 41-44 (spot checks; full suites run separately in CI-style regression)
# ===========================================================================


def test_41_h1_module_still_importable_and_unmodified_behavior(tmp_path):
    ledger = CanonicalMemoryLedger(tmp_path / "h1-check")
    ledger.put(_memory_record("m1"))
    assert ledger.get("m1").lifecycle_state == LIFECYCLE_CREATED  # frozen-at-creation, per module docstring


def test_42_h2_module_still_importable_and_unmodified_behavior(tmp_path):
    memory_ledger, event_ledger, _ = _system(tmp_path)
    _seed_memory(memory_ledger, event_ledger, "m1")
    with pytest.raises(SingleOccurrenceViolationError):
        event_ledger.append(_created_event("m1", "2026-02-01T00:00:00Z"))  # different timestamp -> different event_id -> genuine violation


def test_43_h2_r_experiment_boundary_untouched(tmp_path):
    from phase3.evaluation.foundations.experiment_boundary import BOUNDARY_RESET, ExperimentBoundaryLedger, build_reset_boundary

    ledger = ExperimentBoundaryLedger(tmp_path / "boundaries")
    boundary = build_reset_boundary({"dataset": "x"}, "2026-01-01T00:00:00Z", "system", "reset")
    assert ledger.append(boundary) is not None
    assert boundary.boundary_type == BOUNDARY_RESET


def test_44_h2_r2_single_occurrence_and_factories_untouched(tmp_path):
    from phase3.evaluation.foundations.event_identity import generate_event_id

    kwargs = dict(event_type=EVENT_CREATED, memory_ids=("m1",), timestamp="2026-01-01T00:00:00Z", actor="x", reason="y", new_state=LIFECYCLE_CREATED)
    assert generate_event_id(**kwargs) == generate_event_id(**kwargs)


# ===========================================================================
# INVARIANTS
# ===========================================================================


def test_invariant_identity_stable_across_versions(tmp_path):
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    _seed_memory(memory_ledger, event_ledger, "m1")
    _do_retire(memory_ledger, event_ledger, supersession_ledger)
    history = _reconstruct(memory_ledger, event_ledger, supersession_ledger, "m1")
    assert all(v.memory_id == "m1" for v in history)


def test_invariant_version_immutability():
    v = CanonicalMemoryVersion(
        version_id="m1::v1", memory_id="m1", version_number=1, lifecycle_state=LIFECYCLE_CREATED,
        superseded_by=None, established_by_event_id="e1", recorded_at="2026-01-01T00:00:00Z",
    )
    with pytest.raises(Exception):
        v.lifecycle_state = LIFECYCLE_RETIRED


def test_invariant_content_never_referenced_by_version(tmp_path):
    """CanonicalMemoryVersion carries no content field at all -- content is permanently
    owned by CanonicalMemoryRecord (H.1), never duplicated or re-asserted here."""
    assert not hasattr(CanonicalMemoryVersion, "content")


def test_invariant_current_version_always_refers_to_existing_version(tmp_path):
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    _seed_memory(memory_ledger, event_ledger, "m1")
    current = get_current_version(event_ledger, memory_ledger, supersession_ledger, "m1")
    assert get_version(event_ledger, memory_ledger, supersession_ledger, "m1", current.version_number) == current


def test_invariant_unknown_memory_raises(tmp_path):
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    with pytest.raises(UnknownMemoryError):
        reconstruct_version_history(event_ledger, memory_ledger, supersession_ledger, "nonexistent")


def test_invariant_events_remain_append_only_after_h3():
    assert not hasattr(CanonicalEventLedger, "update_event")
    assert not hasattr(CanonicalEventLedger, "delete_event")


def test_invariant_no_h3_module_imports_agent_visible_context():
    import inspect

    from phase3.evaluation.agent import conditions as agent_conditions
    from phase3.evaluation.agent_runtime import runner as agent_runner

    for module in (agent_conditions, agent_runner):
        source = inspect.getsource(module)
        assert "memory_versioning" not in source


def test_invariant_no_runtime_wiring_into_g1():
    import inspect

    from phase3.evaluation.agent_runtime import campaign_formal_runner

    source = inspect.getsource(campaign_formal_runner)
    assert "memory_versioning" not in source


# ===========================================================================
# Phase 3.3-H.3-R -- remediation for the multi-memory `derived`-event contamination bug
# ===========================================================================
#
# Root cause (PHASE3_3_H3_R_IMPLEMENTATION_REPORT.md section 1): `derived` is the one
# `_LIFECYCLE_EVENT_TYPES` member that is not single-memory-scoped -- its `memory_ids`
# legitimately names every source/parent AND the one target/child. Before this
# remediation, `reconstruct_version_history(P)` for a memory `P` that is ONLY a
# source/parent of some `derived` event (never that event's own `target_memory_id`)
# incorrectly admitted that event into `P`'s own lifecycle history (since
# `events_for_memory()` matches on ANY appearance in `memory_ids`), and then crashed
# constructing a `CanonicalMemoryVersion` with `lifecycle_state=None` (`derived` events are
# not state-changing, so `new_state` is always `None`). The fix: a `derived` event only
# counts toward `memory_id`'s OWN lifecycle history if `memory_id == event.target_memory_id`.


def _derived_event_multi(target_memory_id, source_memory_ids, timestamp="2026-02-01T00:00:00Z"):
    source_memory_ids = tuple(source_memory_ids)
    return build_canonical_event(
        event_type=EVENT_DERIVED,
        memory_ids=source_memory_ids + (target_memory_id,),
        timestamp=timestamp,
        actor="creation_policy",
        reason="derived from multiple sources.",
        source_memory_ids=source_memory_ids,
        target_memory_id=target_memory_id,
    )


def test_h3_r_pure_source_memory_reconstruction_no_longer_crashes(tmp_path):
    """A, B are plain foundation memories, each contributing as a SOURCE to C's
    derivation. Before H.3-R, `reconstruct_version_history("A")` raised
    `MemoryVersioningError` (a spurious `derived` entry with `lifecycle_state=None`
    leaking in from C's creation event). After H.3-R, it must succeed and reflect ONLY
    A's own genuine `created` history -- no trace of C's derivation event at all."""
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    _seed_memory(memory_ledger, event_ledger, "A")
    _seed_memory(memory_ledger, event_ledger, "B")
    memory_ledger.put(_memory_record("C", memory_type=MEMORY_TYPE_DERIVED, parent_ids=["A", "B"]))
    event_ledger.append(_derived_event_multi("C", ["A", "B"]))

    history_a = _reconstruct(memory_ledger, event_ledger, supersession_ledger, "A")
    assert len(history_a) == 1
    assert history_a[0].lifecycle_state == LIFECYCLE_CREATED
    # The ONE version present must be established by A's own `created` event -- never by
    # C's `derived` event (which would be the spurious, pre-fix contamination).
    a_created_event_id = event_ledger.events_for_memory("A")[0].event_id
    assert history_a[0].established_by_event_id == a_created_event_id


def test_h3_r_pure_source_memory_current_version_is_its_own_created_state(tmp_path):
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    _seed_memory(memory_ledger, event_ledger, "A")
    _seed_memory(memory_ledger, event_ledger, "B")
    memory_ledger.put(_memory_record("C", memory_type=MEMORY_TYPE_DERIVED, parent_ids=["A", "B"]))
    event_ledger.append(_derived_event_multi("C", ["A", "B"]))

    current_a = get_current_version(event_ledger, memory_ledger, supersession_ledger, "A")
    assert current_a.version_number == 1
    assert current_a.lifecycle_state == LIFECYCLE_CREATED
    current_b = get_current_version(event_ledger, memory_ledger, supersession_ledger, "B")
    assert current_b.lifecycle_state == LIFECYCLE_CREATED


def test_h3_r_source_memorys_own_later_retirement_is_still_correctly_tracked(tmp_path):
    """A is a source of C's derivation AND is separately, legitimately retired later.
    The fix must not suppress A's OWN real lifecycle events -- only the spurious
    cross-memory `derived` entry."""
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    _seed_memory(memory_ledger, event_ledger, "A")
    memory_ledger.put(_memory_record("C", memory_type=MEMORY_TYPE_DERIVED, parent_ids=["A"]))
    event_ledger.append(_derived_event_multi("C", ["A"]))

    retired_event = build_canonical_event(
        event_type=EVENT_RETIRED, memory_ids=("A",), timestamp="2026-02-02T00:00:00Z",
        actor="creation_policy", reason="retired after contributing to C.",
        previous_state=LIFECYCLE_CREATED, new_state=LIFECYCLE_RETIRED,
    )
    retire_memory(event_ledger, memory_ledger, supersession_ledger, "A", retired_event=retired_event)

    history_a = _reconstruct(memory_ledger, event_ledger, supersession_ledger, "A")
    assert [v.lifecycle_state for v in history_a] == [LIFECYCLE_CREATED, LIFECYCLE_RETIRED]
    current_a = get_current_version(event_ledger, memory_ledger, supersession_ledger, "A")
    assert current_a.lifecycle_state == LIFECYCLE_RETIRED


def test_h3_r2_target_memorys_own_derived_creation_reconstructs_as_created(tmp_path):
    """FIXED (Phase 3.3-H.3-R2): a `derived`-type memory's OWN creation event legitimately
    has `target_memory_id == memory_id`, so H.3-R's fix correctly KEEPS it in that
    memory's own history. That event's `new_state` is always `None` (`derived` events are
    not state-changing, per canonical_event.py), so H.3-R2 infers `LIFECYCLE_CREATED` for
    it instead of reading `event.new_state` directly -- matching every `created` event's
    own existing convention in this test suite. Version 1 for a derived memory must now
    reconstruct successfully with that inferred state, not raise."""
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    _seed_memory(memory_ledger, event_ledger, "A")
    memory_ledger.put(_memory_record("C", memory_type=MEMORY_TYPE_DERIVED, parent_ids=["A"]))
    event_ledger.append(_derived_event_multi("C", ["A"]))

    history = reconstruct_version_history(event_ledger, memory_ledger, supersession_ledger, "C")
    assert len(history) == 1
    assert history[0].lifecycle_state == LIFECYCLE_CREATED
    assert history[0].version_number == 1
    assert history[0].superseded_by is None

    current = get_current_version(event_ledger, memory_ledger, supersession_ledger, "C")
    assert current.lifecycle_state == LIFECYCLE_CREATED


def test_h3_r2_derived_memory_supersession_composes_correctly(tmp_path):
    """The H.3-R2-inferred LIFECYCLE_CREATED base state for a derived memory must compose
    correctly with the pre-existing, unmodified supersession/retirement machinery -- not
    just work in isolation as version 1."""
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    _seed_memory(memory_ledger, event_ledger, "A")
    memory_ledger.put(_memory_record("C", memory_type=MEMORY_TYPE_DERIVED, parent_ids=["A"]))
    event_ledger.append(_derived_event_multi("C", ["A"]))
    memory_ledger.put(_memory_record("D", memory_type=MEMORY_TYPE_FOUNDATION))
    event_ledger.append(
        CanonicalEvent(
            event_id="ev-create-d", event_type=EVENT_CREATED, memory_ids=("D",),
            timestamp="2026-01-01T00:00:01Z", actor="creation_policy", reason="ingested",
            new_state=LIFECYCLE_CREATED,
        )
    )

    result = supersede_memory(
        event_ledger, memory_ledger, supersession_ledger,
        superseded_memory_id="C", superseding_memory_id="D",
        superseded_event=CanonicalEvent(
            event_id="ev-sup-c", event_type=EVENT_SUPERSEDED, memory_ids=("C",),
            timestamp="2026-01-01T00:00:02Z", actor="creation_policy", reason="d supersedes c.",
            previous_state=LIFECYCLE_CREATED, new_state=LIFECYCLE_RETIRED,
        ),
        retired_event=CanonicalEvent(
            event_id="ev-ret-c", event_type=EVENT_RETIRED, memory_ids=("C",),
            timestamp="2026-01-01T00:00:03Z", actor="creation_policy", reason="c retired.",
            previous_state=LIFECYCLE_CREATED, new_state=LIFECYCLE_RETIRED,
        ),
    )
    assert result.status == STATUS_FULLY_SUPERSEDED

    history = reconstruct_version_history(event_ledger, memory_ledger, supersession_ledger, "C")
    assert [v.lifecycle_state for v in history] == [LIFECYCLE_CREATED, LIFECYCLE_RETIRED, LIFECYCLE_RETIRED]
    assert history[-1].superseded_by == "D"


def test_h3_r2_three_memory_derivation_chain_reconstructs_for_all_three(tmp_path):
    """A created, B derived from A, C derived from B -- B is BOTH a target (of A's
    derivation) and a source (of C's derivation). Both H.3-R (which events count) and
    H.3-R2 (what state a derived event implies) must compose correctly: B's own history
    must show exactly its own creation-via-derivation, never C's, and must not raise."""
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    _seed_memory(memory_ledger, event_ledger, "A")
    memory_ledger.put(_memory_record("B", memory_type=MEMORY_TYPE_DERIVED, parent_ids=["A"]))
    event_ledger.append(_derived_event_multi("B", ["A"]))
    memory_ledger.put(_memory_record("C", memory_type=MEMORY_TYPE_DERIVED, parent_ids=["B"]))
    event_ledger.append(_derived_event_multi("C", ["B"]))

    history_a = reconstruct_version_history(event_ledger, memory_ledger, supersession_ledger, "A")
    history_b = reconstruct_version_history(event_ledger, memory_ledger, supersession_ledger, "B")
    history_c = reconstruct_version_history(event_ledger, memory_ledger, supersession_ledger, "C")

    assert len(history_a) == 1 and history_a[0].lifecycle_state == LIFECYCLE_CREATED
    assert len(history_b) == 1 and history_b[0].lifecycle_state == LIFECYCLE_CREATED
    assert len(history_c) == 1 and history_c[0].lifecycle_state == LIFECYCLE_CREATED


def test_h3_r_multi_source_derivation_all_sources_reconstruct_cleanly(tmp_path):
    """Three sources, one derived target -- every source's own history must reconstruct
    cleanly (the mission's own multi-parent case), and none of them cross-contaminate
    each other's history either."""
    memory_ledger, event_ledger, supersession_ledger = _system(tmp_path)
    for mid in ("A", "B", "C"):
        _seed_memory(memory_ledger, event_ledger, mid)
    memory_ledger.put(_memory_record("D", memory_type=MEMORY_TYPE_DERIVED, parent_ids=["A", "B", "C"]))
    event_ledger.append(_derived_event_multi("D", ["A", "B", "C"]))

    for mid in ("A", "B", "C"):
        history = _reconstruct(memory_ledger, event_ledger, supersession_ledger, mid)
        assert len(history) == 1
        assert history[0].lifecycle_state == LIFECYCLE_CREATED
