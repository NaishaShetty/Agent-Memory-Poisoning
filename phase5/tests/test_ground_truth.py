"""Post-Phase-5 hardening -- OR-12 coverage gap closure tests."""

from __future__ import annotations

import pytest

from phase3.evaluation.foundations.canonical import (
    CanonicalMemoryRecord, LIFECYCLE_CREATED, MEMORY_TYPE_FOUNDATION, SOURCE_TYPE_PHASE2_UMR,
)
from phase3.evaluation.foundations.canonical_event import CanonicalEvent, EVENT_COUNTERFACTUALLY_INFLUENTIAL, MASKING_METHOD_SELECTED_SET_REMOVAL
from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger

from phase5.identity.run_identity import EventRunMembershipLedger, ExperimentRunLedger, ExperimentRunRecord
from phase5.schema.event import ADMISSION_STATUS_REJECTED, POISON_ADMITTED, POISON_IN_CANDIDATE_POOL, POISON_INFLUENCED_RESPONSE, POISON_NOT_ADMITTED, POISON_SELECTED_TOP_K
from phase5.schema.event_ledger import Phase5EventLedger
from phase5.wiring.ground_truth import derive_ground_truth_transitions
from phase5.wiring.lineage import derive_produced_edges
from phase5.wiring.live_attack_runs import run_live_farma_injection
from phase5.wiring.memory_lifecycle import record_attack_injection
from phase5.wiring.retrieval_instrumentation import instrument_retrieval_and_selection

TS = "2026-09-12T00:00:00+00:00"
CFG = "CFG-gt-test"


@pytest.fixture
def ledgers(tmp_path):
    memory_ledger = CanonicalMemoryLedger(tmp_path / "memory")
    event_ledger = CanonicalEventLedger(tmp_path / "events", memory_ledger)
    run_ledger = ExperimentRunLedger(tmp_path / "runs")
    membership_ledger = EventRunMembershipLedger(tmp_path / "membership", run_ledger)
    phase5_ledger = Phase5EventLedger(tmp_path / "phase5_events")
    run = ExperimentRunRecord(
        experiment_id="exp-gt", run_id="RUN-gt", dataset="locomo",
        scope={"attack_id": "farma"}, started_at=TS, actor="test", reason="ground truth test",
    )
    run_ledger.register(run)
    return dict(
        memory_ledger=memory_ledger, event_ledger=event_ledger,
        membership_ledger=membership_ledger, phase5_ledger=phase5_ledger, run_id=run.run_id,
    )


def test_derives_poison_admitted_and_in_pool_and_selected_from_real_pipeline(ledgers):
    injection_result = run_live_farma_injection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], timestamp=TS,
    )
    memory_id = injection_result.memory_creation.created_event.memory_ids[0]
    content = ledgers["memory_ledger"].get(memory_id).content["text"]
    instrument_retrieval_and_selection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], task_id="task-gt", query="q",
        candidates=[(memory_id, content)], config_fingerprint=CFG, actor="test", timestamp=TS, top_k=1,
    )

    memory_id_to_attack_id = {e.target_id: "farma" for e in derive_produced_edges(ledgers["phase5_ledger"])}
    transitions = derive_ground_truth_transitions(
        phase5_event_ledger=ledgers["phase5_ledger"], event_ledger=ledgers["event_ledger"],
        memory_id_to_attack_id=memory_id_to_attack_id, timestamp=TS,
    )
    states_for_memory = {t.state for t in transitions if t.memory_id == memory_id}
    assert POISON_ADMITTED in states_for_memory
    assert POISON_IN_CANDIDATE_POOL in states_for_memory
    assert POISON_SELECTED_TOP_K in states_for_memory
    for t in transitions:
        if t.memory_id == memory_id:
            assert t.attack_id == "farma"  # resolved via the PRODUCED lineage edge
            assert t.derived_from_event_id  # every transition cites a real event


def test_derives_poison_not_admitted_from_rejected_injection(ledgers):
    record_attack_injection(
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], attack_id="farma", injection_id="INJ-gt-rejected",
        artifact_id="artifact-gt-rejected", admission_status=ADMISSION_STATUS_REJECTED,
        actor="test", reason="rejected", timestamp=TS,
    )
    transitions = derive_ground_truth_transitions(phase5_event_ledger=ledgers["phase5_ledger"], timestamp=TS)
    assert any(t.state == POISON_NOT_ADMITTED and t.memory_id == "artifact-gt-rejected" for t in transitions)


def test_derives_poison_influenced_response_only_from_real_counterfactual_event(ledgers):
    assert derive_ground_truth_transitions(
        phase5_event_ledger=ledgers["phase5_ledger"], event_ledger=ledgers["event_ledger"], timestamp=TS,
    ) == ()

    record = CanonicalMemoryRecord(
        memory_id="mem-gt-influenced", memory_type=MEMORY_TYPE_FOUNDATION, content={"text": "fact"},
        source={"source_type": SOURCE_TYPE_PHASE2_UMR}, parent_ids=(), creation_event="c", creation_timestamp=TS,
        lifecycle_state=LIFECYCLE_CREATED,
    )
    ledgers["memory_ledger"].put(record)
    counterfactual_event = CanonicalEvent(
        event_id="evt-gt-cf", event_type=EVENT_COUNTERFACTUALLY_INFLUENTIAL, memory_ids=("mem-gt-influenced",),
        timestamp=TS, actor="test", reason="masking changed the answer", task_id="task-gt-cf",
        config_fingerprint=CFG, counterfactual_answer_hash="h1", baseline_answer_hash="h2",
        diff_criterion="exact_match_changed", masking_method=MASKING_METHOD_SELECTED_SET_REMOVAL,
    )
    ledgers["event_ledger"].append(counterfactual_event)
    transitions = derive_ground_truth_transitions(
        phase5_event_ledger=ledgers["phase5_ledger"], event_ledger=ledgers["event_ledger"], timestamp=TS,
    )
    assert any(t.state == POISON_INFLUENCED_RESPONSE and t.memory_id == "mem-gt-influenced" for t in transitions)


def test_deterministic_across_repeated_calls(ledgers):
    run_live_farma_injection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], timestamp=TS,
    )
    first = derive_ground_truth_transitions(phase5_event_ledger=ledgers["phase5_ledger"], event_ledger=ledgers["event_ledger"], timestamp=TS)
    second = derive_ground_truth_transitions(phase5_event_ledger=ledgers["phase5_ledger"], event_ledger=ledgers["event_ledger"], timestamp=TS)
    assert first == second


def test_never_persists_anything_itself(ledgers):
    """Read-only: derive_ground_truth_transitions() must never mutate either ledger."""
    run_live_farma_injection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], timestamp=TS,
    )
    before = ledgers["phase5_ledger"].all_events()
    derive_ground_truth_transitions(phase5_event_ledger=ledgers["phase5_ledger"], event_ledger=ledgers["event_ledger"], timestamp=TS)
    assert ledgers["phase5_ledger"].all_events() == before
