"""Post-Phase-5 hardening -- Section 7: Attribution Readiness Audit.

Attribution itself is NOT implemented here (confirmed out of scope for all of Phase 5,
per the explicit design decision recorded in Stage 5.8's documentation). This file only
verifies that the evidence a future attribution algorithm would need is actually
present, persisted, and reconstructable from real pipeline data -- for each of the five
chains the hardening prompt names (A-E). Each test either confirms the chain is
AVAILABLE from real evidence, or (for chain E) confirms the discipline that prevents a
false influence claim.
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
from phase5.wiring.agent_decision_instrumentation import (
    FINISH_REASON_GENERATED,
    USED_MEMORIES_NOT_OBSERVABLE,
    record_agent_action,
    record_agent_decision,
)
from phase5.wiring.lineage import DERIVED_FROM, INFLUENCED, SUPERSEDES, derive_derived_from_edges, derive_influenced_edges, derive_supersedes_edges
from phase5.wiring.live_attack_runs import run_live_farma_injection
from phase5.wiring.memory_lifecycle import record_memory_creation, record_memory_derivation, record_memory_lifecycle_transition
from phase5.wiring.retrieval_instrumentation import instrument_retrieval_and_selection, record_context_assembly
from phase5.wiring.trace_assembly import assemble_trace

TS = "2026-09-12T00:00:00+00:00"
TS2 = "2026-09-12T00:01:00+00:00"
CFG = "CFG-attribution-test"


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
        experiment_id="exp-attribution", run_id="RUN-attribution", dataset="locomo",
        scope={"attack_id": "farma"}, started_at=TS, actor="test", reason="attribution readiness test",
    )
    run_ledger.register(run)
    return dict(
        memory_ledger=memory_ledger, event_ledger=event_ledger, supersession_ledger=supersession_ledger,
        membership_ledger=membership_ledger, phase5_ledger=phase5_ledger, run_id=run.run_id,
    )


def test_chain_a_attack_origin_available(ledgers):
    """A. attack_id -> injection_id -> artifact_id -> origin memory_id -- all four fields
    are on the ONE real, persisted attack_injection event; no cross-referencing or
    inference required."""
    injection_result = run_live_farma_injection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], timestamp=TS,
    )
    event = injection_result.injection_event
    assert event.attack_id == "farma"
    assert event.injection_id is not None and event.injection_id.startswith("P5INJ-")
    assert event.artifact_id is not None
    assert event.memory_id == injection_result.memory_creation.created_event.memory_ids[0]
    # AVAILABLE: reconstructable from the persisted event alone.


def test_chain_b_memory_lineage_available(ledgers):
    """B. origin memory -> derived memory -> supersession/version relationships -- both
    DERIVED_FROM and SUPERSEDES edges are real, event-grounded facts (Stage 5.7)."""
    origin = _foundation_record("mem-origin", "origin fact")
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        record=origin, actor="test", reason="seed", timestamp=TS,
    )
    derived = CanonicalMemoryRecord(
        memory_id="mem-derived", memory_type=MEMORY_TYPE_DERIVED, content={"text": "derived fact"},
        source={"source_type": SOURCE_TYPE_DERIVATION_EVENT}, parent_ids=("mem-origin",),
        creation_event="derivation-of-mem-derived", creation_timestamp=TS2, lifecycle_state=LIFECYCLE_CREATED,
    )
    record_memory_derivation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        derived_record=derived, source_memory_ids=("mem-origin",),
        actor="test", reason="derived from origin", timestamp=TS2,
    )
    derived_edges = derive_derived_from_edges(ledgers["event_ledger"])
    assert any(e.source_id == "mem-derived" and e.target_id == "mem-origin" and e.relationship_type == DERIVED_FROM for e in derived_edges)

    replacement = _foundation_record("mem-replacement", "corrected fact")
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        record=replacement, actor="test", reason="seed replacement", timestamp=TS2,
    )
    superseded_event = CanonicalEvent(
        event_id="evt-superseded-attrib", event_type=EVENT_SUPERSEDED, memory_ids=("mem-origin",),
        timestamp=TS2, actor="test", reason="corrected", previous_state=LIFECYCLE_ACTIVE, new_state=LIFECYCLE_RETIRED,
    )
    retired_event = CanonicalEvent(
        event_id="evt-retired-attrib", event_type=EVENT_RETIRED, memory_ids=("mem-origin",),
        timestamp=TS2, actor="test", reason="corrected", previous_state=LIFECYCLE_ACTIVE, new_state=LIFECYCLE_RETIRED,
    )
    record_memory_lifecycle_transition(
        event_ledger=ledgers["event_ledger"], memory_ledger=ledgers["memory_ledger"],
        supersession_ledger=ledgers["supersession_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], superseded_memory_id="mem-origin", superseding_memory_id="mem-replacement",
        superseded_event=superseded_event, retired_event=retired_event,
    )
    supersedes_edges = derive_supersedes_edges(ledgers["event_ledger"], ledgers["supersession_ledger"])
    assert any(e.source_id == "mem-replacement" and e.target_id == "mem-origin" and e.relationship_type == SUPERSEDES for e in supersedes_edges)
    # AVAILABLE: both relationship kinds are real, persisted, event-grounded edges.


def test_chain_c_propagation_through_exposure_available(ledgers):
    """C. source memory -> retrieval -> selection -> context exposure -> downstream
    memory/behavior -- every hop is a real, persisted event; the LAST hop
    ("downstream memory/behavior") is available only when something real actually
    happened downstream (a derived memory, or a decision) -- never asserted absent
    real evidence."""
    injection_result = run_live_farma_injection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], timestamp=TS,
    )
    memory_id = injection_result.memory_creation.created_event.memory_ids[0]
    content = ledgers["memory_ledger"].get(memory_id).content["text"]

    report = instrument_retrieval_and_selection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], task_id="task-chain-c", query="q",
        candidates=[(memory_id, content)], config_fingerprint=CFG, actor="test", timestamp=TS, top_k=1,
    )
    assert report.retrieved_event_ids and report.selected_event_ids  # retrieval -> selection: AVAILABLE

    context_event = record_context_assembly(
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], task_id="task-chain-c", context_memory_ids=(memory_id,),
        rendered_messages=({"role": "user", "content": content},), actor="test", reason="exposed", timestamp=TS,
    )
    assert memory_id in context_event.context_memory_ids  # exposure: AVAILABLE

    # Downstream "behavior": a decision made with this memory exposed.
    decision_event = record_agent_decision(
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], task_id="task-chain-c", decision_id="dec-chain-c",
        exposed_memory_ids=(memory_id,), output="an answer", finish_reason=FINISH_REASON_GENERATED,
        model_identity="qwen3-8b", config_fingerprint=CFG, used_memories_observability=USED_MEMORIES_NOT_OBSERVABLE,
        actor="test", reason="decision made", timestamp=TS,
    )
    assert memory_id in decision_event.exposed_memory_ids  # downstream behavior link: AVAILABLE (as EXPOSURE, not confirmed use)


def test_chain_d_agent_interaction_available(ledgers):
    """D. memory -> context -> decision -> action -- all linked by task_id/decision_id,
    all real persisted events."""
    memory_id = "mem-chain-d"
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        record=_foundation_record(memory_id, "fact"), actor="test", reason="seed", timestamp=TS,
    )
    context_event = record_context_assembly(
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], task_id="task-chain-d", context_memory_ids=(memory_id,),
        rendered_messages=({"role": "user", "content": "fact"},), actor="test", reason="exposed", timestamp=TS,
    )
    decision_event = record_agent_decision(
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], task_id="task-chain-d", decision_id="dec-chain-d",
        exposed_memory_ids=(memory_id,), output="an answer", finish_reason=FINISH_REASON_GENERATED,
        model_identity="qwen3-8b", config_fingerprint=CFG, used_memories_observability=USED_MEMORIES_NOT_OBSERVABLE,
        actor="test", reason="decision made", timestamp=TS,
    )
    action_event = record_agent_action(
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], task_id="task-chain-d", decision_id="dec-chain-d",
        action_id="act-chain-d", action="submit_answer", result="SUCCESS", actor="test", reason="answer submitted", timestamp=TS,
    )
    assert context_event.task_id == decision_event.task_id == action_event.task_id == "task-chain-d"
    assert memory_id in context_event.context_memory_ids and memory_id in decision_event.exposed_memory_ids
    assert action_event.decision_id == decision_event.decision_id
    # AVAILABLE: the full memory -> context -> decision -> action chain reconstructs from
    # persisted identifiers alone.


def test_chain_e_influence_available_only_from_real_counterfactual_evidence(ledgers):
    """E. a genuine counterfactually_influential event can be linked back to run, memory,
    and evidence -- AND, critically, no such link exists absent a real counterfactual
    event (never inferred from temporal order, retrieval, selection, or exposure)."""
    injection_result = run_live_farma_injection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], timestamp=TS,
    )
    memory_id = injection_result.memory_creation.created_event.memory_ids[0]

    # Before any counterfactual run: MISSING, correctly -- not inferred from anything else.
    assert derive_influenced_edges(ledgers["event_ledger"]) == ()

    counterfactual_event = CanonicalEvent(
        event_id="evt-counterfactual-attrib", event_type=EVENT_COUNTERFACTUALLY_INFLUENTIAL,
        memory_ids=(memory_id,), timestamp=TS2, actor="test", reason="masking changed the answer",
        task_id="task-chain-e", config_fingerprint=CFG, counterfactual_answer_hash="hash-masked",
        baseline_answer_hash="hash-baseline", diff_criterion="exact_match_changed",
        masking_method=MASKING_METHOD_SELECTED_SET_REMOVAL,
    )
    ledgers["event_ledger"].append(counterfactual_event)
    edges = derive_influenced_edges(ledgers["event_ledger"])
    assert len(edges) == 1
    assert edges[0].relationship_type == INFLUENCED
    assert edges[0].source_id == memory_id
    assert edges[0].established_by_event_ids == (counterfactual_event.event_id,)
    # AVAILABLE: linked back to run (via membership, not asserted here since this event
    # wasn't registered to a run in this minimal test -- see test_lineage.py's
    # test_derive_influenced_edges_only_from_real_counterfactual_events for the run-linked
    # version), memory (source_id), and evidence (established_by_event_ids -> the event
    # itself carries baseline/counterfactual hashes and masking_method).
