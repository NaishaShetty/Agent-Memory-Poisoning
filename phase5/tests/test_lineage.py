"""Phase 5.7 -- tests for provenance/lineage/memory-interaction derivation.

Exercises each derive_* function against real ledgers built through Stage 5.4/5.5/5.6's
own wiring wherever possible, so these tests prove the derivation actually reconstructs
from persisted state, not from hand-crafted fixtures alone.
"""

from __future__ import annotations

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
    EVENT_COUNTERFACTUALLY_INFLUENTIAL,
    EVENT_RETIRED,
    EVENT_SUPERSEDED,
    MASKING_METHOD_SELECTED_SET_REMOVAL,
)
from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger
from phase3.evaluation.foundations.memory_versioning import SupersessionLedger

from phase5.identity.run_identity import EventRunMembershipLedger, ExperimentRunLedger, ExperimentRunRecord
from phase5.schema.event_ledger import Phase5EventLedger
from phase5.wiring.agent_decision_instrumentation import record_agent_decision, FINISH_REASON_GENERATED, USED_MEMORIES_NOT_OBSERVABLE
from phase5.wiring.completeness import check_attack_injection_completeness
from phase5.wiring.lineage import (
    DERIVED_FROM,
    EVIDENCE_COUNTERFACTUAL,
    EVIDENCE_EXPOSURE_ONLY,
    EVIDENCE_LINEAGE_REACHABILITY,
    EVIDENCE_OBSERVED_EVENT,
    INFLUENCED,
    MemoryInteractionEdge,
    PRODUCED,
    PROPAGATED_TO,
    REFERENCES,
    RETRIEVED_WITH,
    SELECTED_WITH,
    SUPERSEDES,
    USED_BY,
    derive_co_retrieved_edges,
    derive_co_selected_edges,
    derive_derived_from_edges,
    derive_exposed_to_decision_edges,
    derive_influenced_edges,
    derive_produced_edges,
    derive_propagated_to_edges,
    derive_references_edges,
    derive_supersedes_edges,
    query_co_retrieved_memory_ids,
    query_co_selected_memory_ids,
    tainted_memory_evidence,
)
from phase5.wiring.live_attack_runs import run_live_farma_injection
from phase5.wiring.memory_lifecycle import record_memory_creation, record_memory_derivation, record_memory_lifecycle_transition
from phase5.wiring.retrieval_instrumentation import instrument_retrieval_and_selection

TS = "2026-09-12T00:00:00+00:00"
TS2 = "2026-09-12T00:01:00+00:00"
CFG = "CFG-lineage-test"


def _foundation_record(memory_id, text, source_type=SOURCE_TYPE_PHASE2_UMR):
    return CanonicalMemoryRecord(
        memory_id=memory_id, memory_type=MEMORY_TYPE_FOUNDATION, content={"text": text},
        source={"source_type": source_type}, parent_ids=(),
        creation_event=f"creation-of-{memory_id}", creation_timestamp=TS, lifecycle_state=LIFECYCLE_CREATED,
    )


@pytest.fixture
def ledgers(tmp_path):
    memory_ledger = CanonicalMemoryLedger(tmp_path / "memory")
    event_ledger = CanonicalEventLedger(tmp_path / "events", memory_ledger)
    supersession_ledger = SupersessionLedger(tmp_path / "supersessions")
    run_ledger = ExperimentRunLedger(tmp_path / "runs")
    membership_ledger = EventRunMembershipLedger(tmp_path / "membership", run_ledger)
    phase5_ledger = Phase5EventLedger(tmp_path / "phase5_events")
    run = ExperimentRunRecord(
        experiment_id="exp-lineage", run_id="RUN-lineage", dataset="locomo",
        scope={}, started_at=TS, actor="test", reason="lineage test run",
    )
    run_ledger.register(run)
    return dict(
        memory_ledger=memory_ledger, event_ledger=event_ledger, supersession_ledger=supersession_ledger,
        membership_ledger=membership_ledger, phase5_ledger=phase5_ledger, run_id=run.run_id,
    )


def test_derive_produced_edges_from_live_attack_injection(ledgers):
    injection_result = run_live_farma_injection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], timestamp=TS,
    )
    poisoned_memory_id = injection_result.memory_creation.created_event.memory_ids[0]

    edges = derive_produced_edges(ledgers["phase5_ledger"])
    assert len(edges) == 1
    edge = edges[0]
    assert edge.relationship_type == PRODUCED
    assert edge.source_id == injection_result.injection_event.injection_id
    assert edge.target_id == poisoned_memory_id
    assert edge.evidence_kind == EVIDENCE_OBSERVED_EVENT
    assert edge.established_by_event_ids == (injection_result.injection_event.event_id,)


def test_derive_produced_edges_excludes_rejected_injections(ledgers):
    from phase5.wiring.memory_lifecycle import record_attack_injection
    from phase5.schema.event import ADMISSION_STATUS_REJECTED

    record_attack_injection(
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], attack_id="farma", injection_id="INJ-rejected", artifact_id="a1",
        admission_status=ADMISSION_STATUS_REJECTED, actor="test", reason="rejected", timestamp=TS,
    )
    assert derive_produced_edges(ledgers["phase5_ledger"]) == ()


def test_derive_derived_from_edges(ledgers):
    parent = _foundation_record("mem-parent", "parent fact")
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        record=parent, actor="test", reason="seed", timestamp=TS,
    )
    child = CanonicalMemoryRecord(
        memory_id="mem-child", memory_type=MEMORY_TYPE_DERIVED, content={"text": "derived fact"},
        source={"source_type": SOURCE_TYPE_DERIVATION_EVENT}, parent_ids=("mem-parent",),
        creation_event="derivation-of-mem-child", creation_timestamp=TS2, lifecycle_state=LIFECYCLE_CREATED,
    )
    result = record_memory_derivation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        derived_record=child, source_memory_ids=("mem-parent",),
        actor="test", reason="child derived from parent", timestamp=TS2,
    )
    edges = derive_derived_from_edges(ledgers["event_ledger"])
    assert len(edges) == 1
    assert edges[0] == MemoryInteractionEdge(
        relationship_type=DERIVED_FROM, source_id="mem-child", target_id="mem-parent",
        evidence_kind=EVIDENCE_OBSERVED_EVENT, established_by_event_ids=(result.created_event.event_id,),
    )


def test_derive_supersedes_edges(ledgers):
    old, new = _foundation_record("mem-old", "outdated"), _foundation_record("mem-new", "corrected")
    for rec in (old, new):
        record_memory_creation(
            memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
            membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
            record=rec, actor="test", reason="seed", timestamp=TS,
        )
    superseded_event = CanonicalEvent(
        event_id="evt-superseded-1", event_type=EVENT_SUPERSEDED, memory_ids=("mem-old",),
        timestamp=TS2, actor="test", reason="corrected", previous_state=LIFECYCLE_ACTIVE, new_state=LIFECYCLE_RETIRED,
    )
    retired_event = CanonicalEvent(
        event_id="evt-retired-1", event_type=EVENT_RETIRED, memory_ids=("mem-old",),
        timestamp=TS2, actor="test", reason="corrected", previous_state=LIFECYCLE_ACTIVE, new_state=LIFECYCLE_RETIRED,
    )
    record_memory_lifecycle_transition(
        event_ledger=ledgers["event_ledger"], memory_ledger=ledgers["memory_ledger"],
        supersession_ledger=ledgers["supersession_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], superseded_memory_id="mem-old", superseding_memory_id="mem-new",
        superseded_event=superseded_event, retired_event=retired_event,
    )
    edges = derive_supersedes_edges(ledgers["event_ledger"], ledgers["supersession_ledger"])
    assert len(edges) == 1
    assert edges[0].relationship_type == SUPERSEDES
    assert edges[0].source_id == "mem-new"
    assert edges[0].target_id == "mem-old"
    assert edges[0].established_by_event_ids == ("evt-superseded-1",)


def test_derive_exposed_to_decision_edges_never_claims_confirmed_usage(ledgers):
    decision_event = record_agent_decision(
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], task_id="task-1", decision_id="dec-1",
        exposed_memory_ids=("mem-a", "mem-b"), output="the answer",
        finish_reason=FINISH_REASON_GENERATED, model_identity="qwen3-8b", config_fingerprint=CFG,
        used_memories_observability=USED_MEMORIES_NOT_OBSERVABLE,
        actor="test", reason="generation completed", timestamp=TS,
    )
    edges = derive_exposed_to_decision_edges(ledgers["phase5_ledger"])
    assert len(edges) == 2
    assert {e.source_id for e in edges} == {"mem-a", "mem-b"}
    for edge in edges:
        assert edge.relationship_type == USED_BY
        assert edge.target_id == "dec-1"
        assert edge.evidence_kind == EVIDENCE_EXPOSURE_ONLY  # never upgraded to confirmed usage
        assert edge.established_by_event_ids == (decision_event.event_id,)


def test_derive_influenced_edges_only_from_real_counterfactual_events(ledgers):
    # No counterfactually_influential event exists yet -- must be empty, never inferred
    # from retrieval/selection/exposure alone.
    assert derive_influenced_edges(ledgers["event_ledger"]) == ()

    memory = _foundation_record("mem-influential", "a forged claim")
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        record=memory, actor="test", reason="seed", timestamp=TS,
    )
    counterfactual_event = CanonicalEvent(
        event_id="evt-counterfactual-1", event_type=EVENT_COUNTERFACTUALLY_INFLUENTIAL,
        memory_ids=("mem-influential",), timestamp=TS2, actor="test", reason="masking changed the answer",
        task_id="task-cf", config_fingerprint=CFG, counterfactual_answer_hash="hash-masked",
        baseline_answer_hash="hash-baseline", diff_criterion="exact_match_changed",
        masking_method=MASKING_METHOD_SELECTED_SET_REMOVAL,
    )
    ledgers["event_ledger"].append(counterfactual_event)

    edges = derive_influenced_edges(ledgers["event_ledger"])
    assert len(edges) == 1
    assert edges[0].relationship_type == INFLUENCED
    assert edges[0].source_id == "mem-influential"
    assert edges[0].evidence_kind == EVIDENCE_COUNTERFACTUAL
    assert edges[0].established_by_event_ids == ("evt-counterfactual-1",)


def test_derive_propagated_to_edges_wraps_taint_propagation(ledgers):
    injection_result = run_live_farma_injection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], timestamp=TS,
    )
    attack_memory_id = injection_result.memory_creation.created_event.memory_ids[0]
    derived = CanonicalMemoryRecord(
        memory_id="mem-propagated-child", memory_type=MEMORY_TYPE_DERIVED, content={"text": "propagated forged claim"},
        source={"source_type": SOURCE_TYPE_DERIVATION_EVENT}, parent_ids=(attack_memory_id,),
        creation_event="derivation-of-mem-propagated-child", creation_timestamp=TS2, lifecycle_state=LIFECYCLE_CREATED,
    )
    record_memory_derivation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        derived_record=derived, source_memory_ids=(attack_memory_id,),
        actor="test", reason="attack content propagated into a new memory", timestamp=TS2,
    )
    edges = derive_propagated_to_edges(ledgers["memory_ledger"], [attack_memory_id], event_ledger=ledgers["event_ledger"])
    assert len(edges) == 1
    assert edges[0].relationship_type == PROPAGATED_TO
    assert edges[0].source_id == attack_memory_id
    assert edges[0].target_id == "mem-propagated-child"
    assert edges[0].evidence_kind == EVIDENCE_LINEAGE_REACHABILITY  # never claimed as influence
    # Review fix: the citation must be the REAL `derived` event, never the descendant's
    # own creation_event (the prior proxy this fix replaced).
    cited_event = ledgers["event_ledger"].get_event(edges[0].established_by_event_ids[0])
    assert cited_event.event_type == "derived"
    assert cited_event.event_id != ledgers["memory_ledger"].get("mem-propagated-child").creation_event


def test_query_co_selected_and_co_retrieved_memory_ids(ledgers):
    for i in range(4):
        record_memory_creation(
            memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
            membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
            record=_foundation_record(f"mem-{i}", f"fact {i} about camping"), actor="test", reason="seed", timestamp=TS,
        )
    candidates = [(f"mem-{i}", f"fact {i} about camping") for i in range(4)]
    instrument_retrieval_and_selection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], task_id="task-group", query="camping",
        candidates=candidates, config_fingerprint=CFG, actor="test", timestamp=TS, top_k=2,
    )
    co_retrieved = query_co_retrieved_memory_ids(ledgers["phase5_ledger"], "task-group")
    co_selected = query_co_selected_memory_ids(ledgers["phase5_ledger"], "task-group")
    assert set(co_retrieved) == {f"mem-{i}" for i in range(4)}
    assert len(co_selected) == 2
    assert set(co_selected).issubset(set(co_retrieved))


def test_memory_interaction_edge_rejects_unknown_relationship_type():
    with pytest.raises(ValueError, match="relationship_type"):
        MemoryInteractionEdge(
            relationship_type="NOT_A_REAL_TYPE", source_id="a", target_id="b",
            evidence_kind=EVIDENCE_OBSERVED_EVENT, established_by_event_ids=("evt-1",),
        )


def test_memory_interaction_edge_rejects_unknown_evidence_kind():
    with pytest.raises(ValueError, match="evidence_kind"):
        MemoryInteractionEdge(
            relationship_type=DERIVED_FROM, source_id="a", target_id="b",
            evidence_kind="MADE_UP_EVIDENCE", established_by_event_ids=("evt-1",),
        )


def test_memory_interaction_edge_rejects_empty_established_by():
    with pytest.raises(ValueError, match="established_by_event_ids"):
        MemoryInteractionEdge(
            relationship_type=DERIVED_FROM, source_id="a", target_id="b",
            evidence_kind=EVIDENCE_OBSERVED_EVENT, established_by_event_ids=(),
        )


def test_non_interference_frozen_taint_propagation_unchanged(ledgers):
    """Confirms this module calls, rather than reimplements, tainted_memories()."""
    from phase3.evaluation.foundations.taint_propagation import tainted_memories

    injection_result = run_live_farma_injection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], timestamp=TS,
    )
    attack_memory_id = injection_result.memory_creation.created_event.memory_ids[0]
    baseline_report = tainted_memories(ledgers["memory_ledger"], [attack_memory_id], event_ledger=ledgers["event_ledger"])
    edges = derive_propagated_to_edges(ledgers["memory_ledger"], [attack_memory_id], event_ledger=ledgers["event_ledger"])
    assert len(edges) == len(baseline_report.tainted_memory_ids)


# ---------------------------------------------------------------------------
# Review fix, item 1: PROPAGATED_TO evidence grounding -- required tests 1-6.
# ---------------------------------------------------------------------------

def _seed_attack_and_derived_chain(ledgers):
    """FARMA attack memory -> real derived child -> real derived grandchild, all through
    real Stage 5.4 wiring, for the evidence-grounding tests below."""
    injection_result = run_live_farma_injection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], timestamp=TS,
    )
    attack_id = injection_result.memory_creation.created_event.memory_ids[0]
    child = CanonicalMemoryRecord(
        memory_id="mem-chain-child", memory_type=MEMORY_TYPE_DERIVED, content={"text": "propagated once"},
        source={"source_type": SOURCE_TYPE_DERIVATION_EVENT}, parent_ids=(attack_id,),
        creation_event="derivation-of-mem-chain-child", creation_timestamp=TS2, lifecycle_state=LIFECYCLE_CREATED,
    )
    record_memory_derivation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        derived_record=child, source_memory_ids=(attack_id,),
        actor="test", reason="first hop", timestamp=TS2,
    )
    grandchild = CanonicalMemoryRecord(
        memory_id="mem-chain-grandchild", memory_type=MEMORY_TYPE_DERIVED, content={"text": "propagated twice"},
        source={"source_type": SOURCE_TYPE_DERIVATION_EVENT}, parent_ids=("mem-chain-child",),
        creation_event="derivation-of-mem-chain-grandchild", creation_timestamp="2026-09-12T00:02:00+00:00",
        lifecycle_state=LIFECYCLE_CREATED,
    )
    record_memory_derivation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        derived_record=grandchild, source_memory_ids=("mem-chain-child",),
        actor="test", reason="second hop", timestamp="2026-09-12T00:02:00+00:00",
    )
    return attack_id


def test_required_1_tainted_memories_output_unchanged_by_evidence_helper(ledgers):
    """Required test 1: tainted_memories()'s own output must be byte-for-byte identical
    whether or not tainted_memory_evidence()/derive_propagated_to_edges() are ever
    called -- the new helper is additive, never a modification of the frozen function's
    behavior."""
    from phase3.evaluation.foundations.taint_propagation import tainted_memories

    attack_id = _seed_attack_and_derived_chain(ledgers)
    before = tainted_memories(ledgers["memory_ledger"], [attack_id], event_ledger=ledgers["event_ledger"])

    tainted_memory_evidence(ledgers["memory_ledger"], [attack_id], event_ledger=ledgers["event_ledger"])
    derive_propagated_to_edges(ledgers["memory_ledger"], [attack_id], event_ledger=ledgers["event_ledger"])

    after = tainted_memories(ledgers["memory_ledger"], [attack_id], event_ledger=ledgers["event_ledger"])
    assert before == after


def test_required_2_propagated_to_edges_contain_genuine_lineage_evidence(ledgers):
    """Required test 2: every PROPAGATED_TO edge's established_by_event_ids must be REAL
    `derived` CanonicalEvents that actually exist in the event ledger -- never the
    descendant's creation_event, never a fabricated id."""
    attack_id = _seed_attack_and_derived_chain(ledgers)
    edges = derive_propagated_to_edges(ledgers["memory_ledger"], [attack_id], event_ledger=ledgers["event_ledger"])
    assert len(edges) == 2  # child and grandchild both reachable

    for edge in edges:
        for event_id in edge.established_by_event_ids:
            cited = ledgers["event_ledger"].get_event(event_id)
            assert cited is not None
            assert cited.event_type == "derived"


def test_required_3_evidence_corresponds_to_actual_taint_propagation_lineage(ledgers):
    """Required test 3: the LineageEvidence path/event chain must correspond exactly to
    the real derivation hops -- attack -> child -> grandchild -- not an arbitrary or
    shortest unrelated path."""
    attack_id = _seed_attack_and_derived_chain(ledgers)
    report = tainted_memory_evidence(ledgers["memory_ledger"], [attack_id], event_ledger=ledgers["event_ledger"])
    assert report.ungrounded_descendant_ids == ()

    by_descendant = {ev.descendant_memory_id: ev for ev in report.evidence}
    child_evidence = by_descendant["mem-chain-child"]
    assert child_evidence.path_memory_ids == (attack_id, "mem-chain-child")
    assert len(child_evidence.supporting_event_ids) == 1

    grandchild_evidence = by_descendant["mem-chain-grandchild"]
    assert grandchild_evidence.path_memory_ids == (attack_id, "mem-chain-child", "mem-chain-grandchild")
    assert len(grandchild_evidence.supporting_event_ids) == 2
    # Each hop's event really is the `derived` event for that exact (child, parent) pair.
    first_hop_event = ledgers["event_ledger"].get_event(grandchild_evidence.supporting_event_ids[0])
    assert first_hop_event.target_memory_id == "mem-chain-child"
    assert first_hop_event.source_memory_ids == (attack_id,)
    second_hop_event = ledgers["event_ledger"].get_event(grandchild_evidence.supporting_event_ids[1])
    assert second_hop_event.target_memory_id == "mem-chain-grandchild"
    assert second_hop_event.source_memory_ids == ("mem-chain-child",)


def test_required_4_temporal_ordering_alone_never_creates_propagated_to_edge(ledgers):
    """Required test 4: two memories created in sequence, with NO real parent_ids
    relationship between them, must produce zero PROPAGATED_TO edges -- temporal
    adjacency is not lineage."""
    attack_id = _seed_attack_and_derived_chain(ledgers)
    # A later, entirely independent memory -- created AFTER the attack chain, same run,
    # same actor, but never derived from anything.
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        record=_foundation_record("mem-temporally-later-unrelated", "an unrelated later fact"),
        actor="test", reason="unrelated, later in time", timestamp="2026-09-12T00:05:00+00:00",
    )
    edges = derive_propagated_to_edges(ledgers["memory_ledger"], [attack_id], event_ledger=ledgers["event_ledger"])
    target_ids = {e.target_id for e in edges}
    assert "mem-temporally-later-unrelated" not in target_ids


def test_required_5_unrelated_memories_receive_no_propagation_edges(ledgers):
    """Required test 5: an independently-created, never-derived-from memory must never
    appear as a PROPAGATED_TO target for an unrelated attack id."""
    attack_id = _seed_attack_and_derived_chain(ledgers)
    unrelated = _foundation_record("mem-unrelated-independent", "totally unrelated content")
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        record=unrelated, actor="test", reason="independent memory", timestamp=TS,
    )
    edges = derive_propagated_to_edges(ledgers["memory_ledger"], [attack_id], event_ledger=ledgers["event_ledger"])
    assert all(e.target_id != "mem-unrelated-independent" for e in edges)
    assert all(e.source_id != "mem-unrelated-independent" for e in edges)


def test_required_6_unknown_versioning_gap_remains_visible(ledgers):
    """Required test 6: the frozen H.3/H.4-D UNKNOWN_VERSIONING_GAP limitation must
    remain visible on LineageEvidence.lifecycle_status, never silently bypassed or hidden
    by this additive helper."""
    from phase3.evaluation.foundations.taint_propagation import LIFECYCLE_STATUS_UNKNOWN_VERSIONING_GAP

    attack_id = _seed_attack_and_derived_chain(ledgers)
    report = tainted_memory_evidence(
        ledgers["memory_ledger"], [attack_id],
        event_ledger=ledgers["event_ledger"], supersession_ledger=ledgers["supersession_ledger"],
    )
    # Every derivation-touched id (both the child and grandchild are derivation-touched --
    # see _is_derivation_touched()) must show the gap, exactly as tainted_memories() itself
    # would report it -- never silently resolved or omitted here.
    statuses = {ev.descendant_memory_id: ev.lifecycle_status for ev in report.evidence}
    assert statuses["mem-chain-child"] == LIFECYCLE_STATUS_UNKNOWN_VERSIONING_GAP
    assert statuses["mem-chain-grandchild"] == LIFECYCLE_STATUS_UNKNOWN_VERSIONING_GAP


def test_ungrounded_descendant_reported_not_fabricated(ledgers, tmp_path):
    """A descendant that IS reachable per tainted_memories() (real parent_ids set) but has
    NO corresponding `derived` CanonicalEvent (bypassing record_memory_derivation()) must
    be reported in ungrounded_descendant_ids, never given an invented event id."""
    attack = _foundation_record("mem-bypass-attack", "attack content")
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        record=attack, actor="test", reason="seed", timestamp=TS,
    )
    # Written directly to the memory ledger with parent_ids set, bypassing
    # record_memory_derivation() -- so no `derived` CanonicalEvent will ever exist for it.
    bypassed_child = CanonicalMemoryRecord(
        memory_id="mem-bypassed-child", memory_type=MEMORY_TYPE_DERIVED, content={"text": "no derived event"},
        source={"source_type": SOURCE_TYPE_DERIVATION_EVENT}, parent_ids=("mem-bypass-attack",),
        creation_event="hand-written-no-event", creation_timestamp=TS2, lifecycle_state=LIFECYCLE_CREATED,
    )
    ledgers["memory_ledger"].put(bypassed_child)

    report = tainted_memory_evidence(ledgers["memory_ledger"], ["mem-bypass-attack"], event_ledger=ledgers["event_ledger"])
    assert "mem-bypassed-child" in report.ungrounded_descendant_ids
    assert all(ev.descendant_memory_id != "mem-bypassed-child" for ev in report.evidence)

    edges = derive_propagated_to_edges(ledgers["memory_ledger"], ["mem-bypass-attack"], event_ledger=ledgers["event_ledger"])
    assert all(e.target_id != "mem-bypassed-child" for e in edges)  # no fabricated edge either


# ---------------------------------------------------------------------------
# Review fix, items 2/3: pairwise RETRIEVED_WITH / SELECTED_WITH edges.
# ---------------------------------------------------------------------------

def _seed_and_retrieve(ledgers, task_id, n=4, top_k=2, prefix="mem-pw"):
    for i in range(n):
        record_memory_creation(
            memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
            membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
            record=_foundation_record(f"{prefix}-{i}", f"fact {i} about camping"), actor="test", reason="seed", timestamp=TS,
        )
    candidates = [(f"{prefix}-{i}", f"fact {i} about camping") for i in range(n)]
    return instrument_retrieval_and_selection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], task_id=task_id, query="camping",
        candidates=candidates, config_fingerprint=CFG, actor="test", timestamp=TS, top_k=top_k,
    )


def test_derive_co_retrieved_edges_covers_all_pairs_in_the_pool(ledgers):
    _seed_and_retrieve(ledgers, "task-pw-1", n=4, top_k=2)
    edges = derive_co_retrieved_edges(ledgers["phase5_ledger"], "task-pw-1")
    assert len(edges) == 6  # C(4,2)
    for edge in edges:
        assert edge.relationship_type == RETRIEVED_WITH
        assert edge.evidence_kind == EVIDENCE_OBSERVED_EVENT
        assert edge.source_id < edge.target_id  # deterministic canonical ordering


def test_derive_co_selected_edges_covers_only_selected_pairs(ledgers):
    _seed_and_retrieve(ledgers, "task-pw-2", n=4, top_k=2)
    edges = derive_co_selected_edges(ledgers["phase5_ledger"], "task-pw-2")
    assert len(edges) == 1  # C(2,2) = 1
    assert edges[0].relationship_type == SELECTED_WITH
    selected_group = set(query_co_selected_memory_ids(ledgers["phase5_ledger"], "task-pw-2"))
    assert {edges[0].source_id, edges[0].target_id} == selected_group


def test_pairwise_edges_never_cross_task_boundaries(ledgers):
    _seed_and_retrieve(ledgers, "task-pw-a", n=3, top_k=2, prefix="mem-pw-a")
    _seed_and_retrieve(ledgers, "task-pw-b", n=3, top_k=2, prefix="mem-pw-b")
    edges_a = derive_co_retrieved_edges(ledgers["phase5_ledger"], "task-pw-a")
    edges_b = derive_co_retrieved_edges(ledgers["phase5_ledger"], "task-pw-b")
    ids_a = {e.source_id for e in edges_a} | {e.target_id for e in edges_a}
    ids_b = {e.source_id for e in edges_b} | {e.target_id for e in edges_b}
    assert ids_a.isdisjoint(ids_b)  # distinct memory pools, never mixed across tasks

    # Even when the SAME memory_id is retrieved for two different tasks, each task's
    # edges must cite only that task's own events -- never conflate the two.
    for i in range(3):
        record_memory_creation(
            memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
            membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
            record=_foundation_record(f"mem-shared-{i}", f"shared fact {i}"), actor="test", reason="seed", timestamp=TS,
        )
    shared_candidates = [(f"mem-shared-{i}", f"shared fact {i}") for i in range(3)]
    instrument_retrieval_and_selection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], task_id="task-pw-shared-1", query="shared",
        candidates=shared_candidates, config_fingerprint=CFG, actor="test", timestamp=TS, top_k=2,
    )
    instrument_retrieval_and_selection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], task_id="task-pw-shared-2", query="shared",
        candidates=shared_candidates, config_fingerprint=CFG, actor="test", timestamp=TS, top_k=2,
    )
    edges_shared_1 = derive_co_retrieved_edges(ledgers["phase5_ledger"], "task-pw-shared-1")
    edges_shared_2 = derive_co_retrieved_edges(ledgers["phase5_ledger"], "task-pw-shared-2")
    cited_1 = {eid for e in edges_shared_1 for eid in e.established_by_event_ids}
    cited_2 = {eid for e in edges_shared_2 for eid in e.established_by_event_ids}
    assert cited_1.isdisjoint(cited_2)  # same memory ids, but strictly separate real events cited
    for eid in cited_1:
        assert ledgers["phase5_ledger"].get(eid).task_id == "task-pw-shared-1"
    for eid in cited_2:
        assert ledgers["phase5_ledger"].get(eid).task_id == "task-pw-shared-2"


def test_pairwise_edges_deterministic_across_repeated_calls(ledgers):
    _seed_and_retrieve(ledgers, "task-pw-det", n=4, top_k=3)
    first = derive_co_retrieved_edges(ledgers["phase5_ledger"], "task-pw-det")
    second = derive_co_retrieved_edges(ledgers["phase5_ledger"], "task-pw-det")
    assert first == second  # identical edges, identical order, every call


def test_pairwise_edges_cite_real_scored_events(ledgers):
    _seed_and_retrieve(ledgers, "task-pw-cite", n=3, top_k=3)
    edges = derive_co_retrieved_edges(ledgers["phase5_ledger"], "task-pw-cite")
    for edge in edges:
        for event_id in edge.established_by_event_ids:
            assert ledgers["phase5_ledger"].exists(event_id)


# ---------------------------------------------------------------------------
# REFERENCES -- reopened Stage 5.7, 2026-09-13 (see module docstring "REFERENCES --
# REOPENED"). Structural content-citation detection, never an agent-behavior claim.
# ---------------------------------------------------------------------------

def test_derive_references_edges_detects_real_content_citation(ledgers):
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        record=_foundation_record("mem-cited", "the original fact"), actor="test", reason="seed", timestamp=TS,
    )
    citing = CanonicalMemoryRecord(
        memory_id="mem-citing", memory_type=MEMORY_TYPE_DERIVED, content={"text": "as established in [mem-cited], the claim holds"},
        source={"source_type": SOURCE_TYPE_DERIVATION_EVENT}, parent_ids=("mem-cited",),
        creation_event="derivation-of-mem-citing", creation_timestamp=TS2, lifecycle_state=LIFECYCLE_CREATED,
    )
    result = record_memory_derivation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        derived_record=citing, source_memory_ids=("mem-cited",),
        actor="test", reason="derived and cites its own parent explicitly", timestamp=TS2,
    )

    edges = derive_references_edges(ledgers["memory_ledger"], ledgers["event_ledger"])
    references_edges = [e for e in edges if e.relationship_type == REFERENCES]
    assert len(references_edges) == 1
    edge = references_edges[0]
    assert edge.source_id == "mem-citing"
    assert edge.target_id == "mem-cited"
    assert edge.evidence_kind == EVIDENCE_OBSERVED_EVENT
    # Grounded in the REAL 'derived' event for the citing memory -- never a fabricated id,
    # never the record's own bare creation_event string field.
    assert edge.established_by_event_ids == (result.created_event.event_id,)


def test_derive_references_edges_no_edge_without_literal_citation(ledgers):
    for mid, text in (("mem-nc-a", "fact a about camping"), ("mem-nc-b", "an unrelated fact b")):
        record_memory_creation(
            memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
            membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
            record=_foundation_record(mid, text), actor="test", reason="seed", timestamp=TS,
        )
    edges = derive_references_edges(ledgers["memory_ledger"], ledgers["event_ledger"])
    assert edges == ()


def test_derive_references_edges_never_from_word_overlap_or_similarity(ledgers):
    """Mere textual similarity/overlap (not a literal [memory_id] bracket citation) must
    never produce a REFERENCES edge -- this is the exact heuristic the Post-Phase-5
    hardening report explicitly rejected (Sec 10), and this reopening does not revisit
    that rejection."""
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        record=_foundation_record("mem-sim-source", "camping trip to the lake"), actor="test", reason="seed", timestamp=TS,
    )
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        # Mentions "mem-sim-source" as plain text (no bracket citation form) -- must NOT count.
        record=_foundation_record("mem-sim-similar", "mem-sim-source was also a camping trip to the lake"),
        actor="test", reason="seed", timestamp=TS2,
    )
    edges = derive_references_edges(ledgers["memory_ledger"], ledgers["event_ledger"])
    assert edges == ()


def test_derive_references_edges_never_self_references(ledgers):
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        record=_foundation_record("mem-self-ref", "as noted in [mem-self-ref] previously"), actor="test", reason="seed", timestamp=TS,
    )
    edges = derive_references_edges(ledgers["memory_ledger"], ledgers["event_ledger"])
    assert edges == ()


def test_derive_references_edges_never_claims_causality_or_influence(ledgers):
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        record=_foundation_record("mem-ref-a", "fact a"), actor="test", reason="seed", timestamp=TS,
    )
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        record=_foundation_record("mem-ref-b", "fact b, see also [mem-ref-a]"), actor="test", reason="seed", timestamp=TS2,
    )
    for edge in derive_references_edges(ledgers["memory_ledger"], ledgers["event_ledger"]):
        assert edge.evidence_kind != EVIDENCE_COUNTERFACTUAL
        assert edge.relationship_type != INFLUENCED


def test_derive_references_edges_deterministic_across_repeated_calls(ledgers):
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        record=_foundation_record("mem-det-a", "fact a"), actor="test", reason="seed", timestamp=TS,
    )
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        record=_foundation_record("mem-det-b", "fact b cites [mem-det-a]"), actor="test", reason="seed", timestamp=TS2,
    )
    first = derive_references_edges(ledgers["memory_ledger"], ledgers["event_ledger"])
    second = derive_references_edges(ledgers["memory_ledger"], ledgers["event_ledger"])
    assert first == second


def test_pairwise_edges_never_claim_causality_or_influence(ledgers):
    """No pairwise co-retrieval/co-selection fact may ever be mistaken for INFLUENCED --
    evidence_kind is always OBSERVED_EVENT, never COUNTERFACTUAL_EVIDENCE, for these."""
    _seed_and_retrieve(ledgers, "task-pw-no-causal", n=3, top_k=2)
    for edge in derive_co_retrieved_edges(ledgers["phase5_ledger"], "task-pw-no-causal"):
        assert edge.evidence_kind != EVIDENCE_COUNTERFACTUAL
        assert edge.relationship_type != INFLUENCED
    for edge in derive_co_selected_edges(ledgers["phase5_ledger"], "task-pw-no-causal"):
        assert edge.evidence_kind != EVIDENCE_COUNTERFACTUAL
        assert edge.relationship_type != INFLUENCED
