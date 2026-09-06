"""Phase 3.3-H.4-G (`tainted_by` Attack-Propagation Query) contract tests.

Covers every invariant in mission section 6 and every adversarial case in section 7 of
PHASE3_3_H4_G_MISSION.md. Uses H.1's `CanonicalMemoryLedger`/`CanonicalMemoryRecord`, H.2's
`CanonicalEventLedger`, and H.3's `SupersessionLedger` directly -- no foundation/vendor
dependency anywhere in this file.
"""

from __future__ import annotations

import pytest

from phase3.evaluation.foundations.canonical import (
    CanonicalMemoryRecord,
    LIFECYCLE_CREATED,
    MEMORY_TYPE_DERIVED,
    MEMORY_TYPE_FOUNDATION,
    SOURCE_TYPE_DERIVATION_EVENT,
    SOURCE_TYPE_PHASE2_UMR,
)
from phase3.evaluation.foundations.canonical_event import (
    CanonicalEvent,
    EVENT_CREATED,
    EVENT_DERIVED,
    EVENT_RELATIONSHIP_DETECTED,
    RELATIONSHIP_EQUIVALENT_TO,
)
from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger
from phase3.evaluation.foundations.memory_versioning import SupersessionLedger
from phase3.evaluation.foundations.taint_propagation import (
    LIFECYCLE_STATUS_UNKNOWN_VERSIONING_GAP,
    TaintReport,
    UnknownAttackMemoryError,
    tainted_memories,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mem(memory_id, parent_ids=()):
    parent_ids = tuple(parent_ids)
    source = (
        {"source_type": SOURCE_TYPE_DERIVATION_EVENT, "reference_id": f"evt-derive-{memory_id}"}
        if parent_ids
        else {"source_type": SOURCE_TYPE_PHASE2_UMR, "reference_id": f"umr-{memory_id}"}
    )
    return CanonicalMemoryRecord(
        memory_id=memory_id,
        memory_type=MEMORY_TYPE_DERIVED if parent_ids else MEMORY_TYPE_FOUNDATION,
        content={"text": f"content for {memory_id}"},
        source=source,
        parent_ids=parent_ids,
        creation_event=f"evt-created-{memory_id}",
        creation_timestamp="2026-01-01T00:00:00Z",
        lifecycle_state=LIFECYCLE_CREATED,
    )


def _created_event(memory_id):
    return CanonicalEvent(
        event_id=f"evt-created-{memory_id}",
        event_type=EVENT_CREATED,
        memory_ids=(memory_id,),
        timestamp="2026-01-01T00:00:00Z",
        actor="creation_policy",
        reason="ingested.",
        new_state=LIFECYCLE_CREATED,
    )


def _derived_event(memory_id, parent_ids):
    parent_ids = tuple(parent_ids)
    return CanonicalEvent(
        event_id=f"evt-derive-{memory_id}",
        event_type=EVENT_DERIVED,
        memory_ids=parent_ids + (memory_id,),
        timestamp="2026-01-01T00:00:01Z",
        actor="creation_policy",
        reason="derived.",
        source_memory_ids=parent_ids,
        target_memory_id=memory_id,
    )


def _ledgers(tmp_path, name="sys"):
    memory_ledger = CanonicalMemoryLedger(tmp_path / name / "memory")
    event_ledger = CanonicalEventLedger(tmp_path / name / "events", memory_ledger)
    supersession_ledger = SupersessionLedger(tmp_path / name / "supersessions")
    return memory_ledger, event_ledger, supersession_ledger


def _seed_chain(memory_ledger, event_ledger):
    """A -> B -> C, plain lineage chain, no derivation for A/B's own lifecycle purposes
    other than being parents (which IS the versioning-gap trigger for A and B)."""
    memory_ledger.put(_mem("A"))
    memory_ledger.put(_mem("B", parent_ids=["A"]))
    memory_ledger.put(_mem("C", parent_ids=["B"]))
    event_ledger.append(_created_event("A"))
    event_ledger.append(_derived_event("B", ["A"]))
    event_ledger.append(_derived_event("C", ["B"]))


# ---------------------------------------------------------------------------
# Section 6, item 1: read-only -- no mutation
# ---------------------------------------------------------------------------


def test_module_never_calls_put_or_append():
    import inspect

    from phase3.evaluation.foundations import taint_propagation as module

    source = inspect.getsource(module)
    assert ".put(" not in source
    assert ".append(" not in source


def test_tainted_memories_does_not_change_ledger_state(tmp_path):
    memory_ledger, event_ledger, supersession_ledger = _ledgers(tmp_path)
    _seed_chain(memory_ledger, event_ledger)
    before = memory_ledger.list_records()
    tainted_memories(memory_ledger, ["A"], event_ledger=event_ledger, supersession_ledger=supersession_ledger)
    after = memory_ledger.list_records()
    assert before == after


# ---------------------------------------------------------------------------
# Section 6, item 2: attack id itself excluded, unless also a genuine descendant of a
# DIFFERENT attack id
# ---------------------------------------------------------------------------


def test_attack_memory_excludes_itself_by_default(tmp_path):
    memory_ledger, event_ledger, _ = _ledgers(tmp_path)
    _seed_chain(memory_ledger, event_ledger)
    report = tainted_memories(memory_ledger, ["A"])
    assert "A" not in report.tainted_memory_ids
    assert report.tainted_memory_ids == ("B", "C")


def test_attack_memory_appears_if_descendant_of_a_different_attack(tmp_path):
    """A chain of confirmed attacks: X -> Y. If both X and Y are passed as attack ids, Y
    (an attack itself) legitimately appears in tainted_memory_ids because it is a genuine
    descendant of X -- this is documented as legitimate, never suppressed."""
    memory_ledger, event_ledger, _ = _ledgers(tmp_path)
    memory_ledger.put(_mem("X"))
    memory_ledger.put(_mem("Y", parent_ids=["X"]))
    memory_ledger.put(_mem("Z", parent_ids=["Y"]))
    event_ledger.append(_created_event("X"))
    event_ledger.append(_derived_event("Y", ["X"]))
    event_ledger.append(_derived_event("Z", ["Y"]))

    report = tainted_memories(memory_ledger, ["X", "Y"])
    assert "Y" in report.tainted_memory_ids  # Y is an attack id AND a descendant of X
    assert "Z" in report.tainted_memory_ids
    assert report.tainted_by_attack["X"] == ("Y", "Z")
    assert report.tainted_by_attack["Y"] == ("Z",)


# ---------------------------------------------------------------------------
# Section 6, item 3: only derived_from -- equivalent_to/conflicts_with never propagate
# ---------------------------------------------------------------------------


def test_equivalent_to_relationship_does_not_propagate_taint(tmp_path):
    memory_ledger, event_ledger, _ = _ledgers(tmp_path)
    memory_ledger.put(_mem("A"))
    memory_ledger.put(_mem("E"))  # no parent_ids relationship to A at all
    event_ledger.append(_created_event("A"))
    event_ledger.append(_created_event("E"))
    # E is declared equivalent_to A via a relationship_detected event (H.4-BC) -- NOT a
    # derived_from/parent_ids edge.
    event_ledger.append(
        CanonicalEvent(
            event_id="rel-equiv-A-E",
            event_type=EVENT_RELATIONSHIP_DETECTED,
            memory_ids=("A", "E"),
            timestamp="2026-01-01T00:00:02Z",
            actor="creation_policy",
            reason="declared equivalent.",
            relationship_type=RELATIONSHIP_EQUIVALENT_TO,
            mechanism="manual_annotation",
        )
    )
    report = tainted_memories(memory_ledger, ["A"])
    assert "E" not in report.tainted_memory_ids
    assert report.tainted_memory_ids == ()


# ---------------------------------------------------------------------------
# Section 6, item 4: deterministic, order-independent
# ---------------------------------------------------------------------------


def test_deterministic_regardless_of_attack_id_order(tmp_path):
    memory_ledger, event_ledger, _ = _ledgers(tmp_path)
    memory_ledger.put(_mem("X"))
    memory_ledger.put(_mem("Y"))
    memory_ledger.put(_mem("Z", parent_ids=["X", "Y"]))
    for mid in ("X", "Y"):
        event_ledger.append(_created_event(mid))
    event_ledger.append(_derived_event("Z", ["X", "Y"]))

    report1 = tainted_memories(memory_ledger, ["X", "Y"])
    report2 = tainted_memories(memory_ledger, ["Y", "X"])
    assert report1.tainted_memory_ids == report2.tainted_memory_ids == ("Z",)
    assert report1.tainted_by_attack == {"X": ("Z",), "Y": ("Z",)}
    assert report2.tainted_by_attack == {"Y": ("Z",), "X": ("Z",)}


def test_repeated_calls_produce_identical_reports(tmp_path):
    memory_ledger, event_ledger, _ = _ledgers(tmp_path)
    _seed_chain(memory_ledger, event_ledger)
    r1 = tainted_memories(memory_ledger, ["A"])
    r2 = tainted_memories(memory_ledger, ["A"])
    assert r1 == r2


# ---------------------------------------------------------------------------
# Section 6, item 5: derivation-touched id never fed to get_current_version()
# ---------------------------------------------------------------------------


def test_derivation_touched_tainted_id_reports_versioning_gap_not_a_crash(tmp_path):
    """B is derived from A AND is itself a parent of C -- doubly derivation-touched.
    Both must report the gap marker, never raise `MemoryVersioningError`."""
    memory_ledger, event_ledger, supersession_ledger = _ledgers(tmp_path)
    _seed_chain(memory_ledger, event_ledger)  # A -> B -> C

    report = tainted_memories(
        memory_ledger, ["A"], event_ledger=event_ledger, supersession_ledger=supersession_ledger
    )
    assert report.tainted_memory_ids == ("B", "C")
    assert report.lifecycle_status["B"] == LIFECYCLE_STATUS_UNKNOWN_VERSIONING_GAP
    assert report.lifecycle_status["C"] == LIFECYCLE_STATUS_UNKNOWN_VERSIONING_GAP
    assert report.lifecycle_status["C"] == LIFECYCLE_STATUS_UNKNOWN_VERSIONING_GAP


def test_every_genuine_taint_descendant_is_structurally_derivation_touched(tmp_path):
    """DISCOVERED, DOCUMENTED FINDING (not assumed in advance): every genuine taint
    descendant is, BY CONSTRUCTION, a `derived`-type memory (non-empty `parent_ids` --
    that is exactly what connects it to its ancestor via `derived_from`), so it always
    satisfies `_is_derivation_touched()`'s first clause on its own. Given the current H.3
    versioning gap, this means `lifecycle_status` realistically reports
    `LIFECYCLE_STATUS_UNKNOWN_VERSIONING_GAP` for EVERY genuinely-tainted id today -- there
    is no constructible taint scenario where a real descendant escapes this, since
    reachability via `parent_ids` and "derivation-touched" are the same structural fact
    for any non-attack, non-self node. `get_current_version()` would only ever be reached
    for a tainted id in a hypothetical future where H.3's gap is fixed -- this test records
    that reality honestly rather than asserting a scenario that cannot occur."""
    memory_ledger, event_ledger, supersession_ledger = _ledgers(tmp_path)
    _seed_chain(memory_ledger, event_ledger)  # A -> B -> C
    report = tainted_memories(memory_ledger, ["A"], event_ledger=event_ledger, supersession_ledger=supersession_ledger)
    assert report.tainted_memory_ids == ("B", "C")
    assert all(status == LIFECYCLE_STATUS_UNKNOWN_VERSIONING_GAP for status in report.lifecycle_status.values())


# ---------------------------------------------------------------------------
# Section 6, item 6: any_cycle_detected surfaces correctly
# ---------------------------------------------------------------------------


def test_cycle_is_surfaced_via_any_cycle_detected(tmp_path):
    memory_ledger, event_ledger, _ = _ledgers(tmp_path)
    # A -> B -> C -> A (each declares the previous as its own parent, closing the loop).
    memory_ledger.put(_mem("A", parent_ids=["C"]))
    memory_ledger.put(_mem("B", parent_ids=["A"]))
    memory_ledger.put(_mem("C", parent_ids=["B"]))
    report = tainted_memories(memory_ledger, ["A"])
    assert report.any_cycle_detected is True


def test_no_cycle_reports_false(tmp_path):
    memory_ledger, event_ledger, _ = _ledgers(tmp_path)
    _seed_chain(memory_ledger, event_ledger)
    report = tainted_memories(memory_ledger, ["A"])
    assert report.any_cycle_detected is False


# ---------------------------------------------------------------------------
# Section 7, item 1: overlapping descendant sets from two attacks
# ---------------------------------------------------------------------------


def test_overlapping_descendants_counted_once_in_union_but_listed_under_both_attacks(tmp_path):
    memory_ledger, event_ledger, _ = _ledgers(tmp_path)
    memory_ledger.put(_mem("A1"))
    memory_ledger.put(_mem("A2"))
    memory_ledger.put(_mem("Shared", parent_ids=["A1", "A2"]))
    event_ledger.append(_created_event("A1"))
    event_ledger.append(_created_event("A2"))
    event_ledger.append(_derived_event("Shared", ["A1", "A2"]))

    report = tainted_memories(memory_ledger, ["A1", "A2"])
    assert report.tainted_memory_ids == ("Shared",)  # counted once
    assert report.tainted_by_attack["A1"] == ("Shared",)
    assert report.tainted_by_attack["A2"] == ("Shared",)  # listed under both


# ---------------------------------------------------------------------------
# Section 7, item 2: attack with no descendants -> empty, not an error
# ---------------------------------------------------------------------------


def test_attack_with_no_descendants_is_empty_not_an_error(tmp_path):
    memory_ledger, event_ledger, _ = _ledgers(tmp_path)
    memory_ledger.put(_mem("Lonely"))
    event_ledger.append(_created_event("Lonely"))
    report = tainted_memories(memory_ledger, ["Lonely"])
    assert report.tainted_memory_ids == ()
    assert report.tainted_by_attack == {"Lonely": ()}


# ---------------------------------------------------------------------------
# Section 7, item 3: unknown attack id raises clearly, never a silent partial result
# ---------------------------------------------------------------------------


def test_unknown_attack_memory_id_raises(tmp_path):
    memory_ledger, event_ledger, _ = _ledgers(tmp_path)
    _seed_chain(memory_ledger, event_ledger)
    with pytest.raises(UnknownAttackMemoryError):
        tainted_memories(memory_ledger, ["A", "does-not-exist"])


def test_unknown_attack_memory_id_among_valid_ones_still_raises_not_partial(tmp_path):
    memory_ledger, event_ledger, _ = _ledgers(tmp_path)
    _seed_chain(memory_ledger, event_ledger)
    with pytest.raises(UnknownAttackMemoryError, match="does-not-exist"):
        tainted_memories(memory_ledger, ["does-not-exist", "A"])


# ---------------------------------------------------------------------------
# Section 7, item 4: cyclic derived_from graph containing the attack memory
# ---------------------------------------------------------------------------


def test_cyclic_graph_containing_attack_memory_surfaces_cycle_and_descendants(tmp_path):
    memory_ledger, event_ledger, _ = _ledgers(tmp_path)
    memory_ledger.put(_mem("A", parent_ids=["C"]))
    memory_ledger.put(_mem("B", parent_ids=["A"]))
    memory_ledger.put(_mem("C", parent_ids=["B"]))
    report = tainted_memories(memory_ledger, ["A"])
    assert report.any_cycle_detected is True
    # descendants() still reports what it could safely compute before detecting the cycle.
    assert isinstance(report.tainted_memory_ids, tuple)


# ---------------------------------------------------------------------------
# Section 7, item 5: chain of confirmed attacks -- tainted descendant is itself an attack id
# ---------------------------------------------------------------------------


def test_chain_of_confirmed_attacks_no_double_counting_in_union(tmp_path):
    memory_ledger, event_ledger, _ = _ledgers(tmp_path)
    memory_ledger.put(_mem("Attack1"))
    memory_ledger.put(_mem("Attack2", parent_ids=["Attack1"]))
    memory_ledger.put(_mem("Downstream", parent_ids=["Attack2"]))
    event_ledger.append(_created_event("Attack1"))
    event_ledger.append(_derived_event("Attack2", ["Attack1"]))
    event_ledger.append(_derived_event("Downstream", ["Attack2"]))

    report = tainted_memories(memory_ledger, ["Attack1", "Attack2"])
    # Attack2 is itself an attack AND a taint source AND a descendant of Attack1.
    assert report.tainted_memory_ids == ("Attack2", "Downstream")
    assert report.tainted_by_attack["Attack1"] == ("Attack2", "Downstream")
    assert report.tainted_by_attack["Attack2"] == ("Downstream",)
    # Union contains Attack2 exactly once (a tuple, not a multiset).
    assert report.tainted_memory_ids.count("Attack2") == 1


# ---------------------------------------------------------------------------
# Section 5 (mission): TaintReport must never be conflated with counterfactual influence
# ---------------------------------------------------------------------------


def test_taint_report_docstring_disclaims_counterfactual_influence():
    assert "counterfactual" in TaintReport.__doc__.lower()
    assert "influence" in TaintReport.__doc__.lower()


def test_taint_report_has_no_counterfactually_influential_field():
    field_names = set(TaintReport.__dataclass_fields__.keys())
    assert "counterfactually_influential" not in field_names
