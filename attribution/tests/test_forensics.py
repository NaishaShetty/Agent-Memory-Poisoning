"""Phase 9, Stage 9.1 -- `attribution.wiring.forensics` tests.

Fixture pattern mirrors `attribution/tests/test_attribution.py::ledgers` exactly (same
real ledgers, same real Stage 5.4-5.7 wiring calls). Per Stage 9.1's own acceptance
criteria: at least one constructed scenario each for a clean single-hop reconstruction,
a multi-hop reconstruction through a real derived memory, a diamond-ancestry case
correctly reported as MULTIPLE_PLAUSIBLE_ORIGINS, and a benign/no-attack case correctly
reported as NO_ATTACK_ORIGIN_FOUND -- plus determinism and a static import check.
"""

from __future__ import annotations

import inspect

import pytest

from phase3.evaluation.foundations.canonical import (
    CanonicalMemoryRecord,
    LIFECYCLE_CREATED,
    MEMORY_TYPE_DERIVED,
    SOURCE_TYPE_DERIVATION_EVENT,
    SOURCE_TYPE_PHASE2_UMR,
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
from phase5.wiring.live_attack_runs import run_live_dsrm_injection, run_live_farma_injection
from phase5.wiring.memory_lifecycle import record_memory_creation, record_memory_derivation

from attribution.wiring.forensics import (
    CHAIN_INSUFFICIENT_EVIDENCE,
    CHAIN_MULTIPLE_PLAUSIBLE_ORIGINS,
    CHAIN_NO_ATTACK_ORIGIN_FOUND,
    CHAIN_SINGLE_ORIGIN_HIGH_CONFIDENCE,
    reconstruct_attack_origin,
)

TS = "2026-09-17T00:00:00+00:00"
TS2 = "2026-09-17T00:01:00+00:00"
TS3 = "2026-09-17T00:02:00+00:00"
CFG = "CFG-forensics-test"


def _foundation_record(memory_id, text, source_type=SOURCE_TYPE_PHASE2_UMR):
    return CanonicalMemoryRecord(
        memory_id=memory_id, memory_type="foundation", content={"text": text},
        source={"source_type": source_type}, parent_ids=(),
        creation_event=f"creation-of-{memory_id}", creation_timestamp=TS, lifecycle_state=LIFECYCLE_CREATED,
    )


def _make_ledgers(tmp_path, run_id="RUN-forensics"):
    memory_ledger = CanonicalMemoryLedger(tmp_path / "memory")
    event_ledger = CanonicalEventLedger(tmp_path / "events", memory_ledger)
    supersession_ledger = SupersessionLedger(tmp_path / "supersessions")
    run_ledger = ExperimentRunLedger(tmp_path / "runs")
    membership_ledger = EventRunMembershipLedger(tmp_path / "membership", run_ledger)
    phase5_ledger = Phase5EventLedger(tmp_path / "phase5_events")
    run = ExperimentRunRecord(
        experiment_id="exp-forensics", run_id=run_id, dataset="locomo",
        scope={}, started_at=TS, actor="test", reason="forensics test run",
    )
    run_ledger.register(run)
    return dict(
        memory_ledger=memory_ledger, event_ledger=event_ledger, supersession_ledger=supersession_ledger,
        membership_ledger=membership_ledger, phase5_ledger=phase5_ledger, run_id=run.run_id,
    )


@pytest.fixture
def ledgers(tmp_path):
    return _make_ledgers(tmp_path)


def _record_decision(ledgers, decision_id, task_id, exposed_memory_ids, timestamp=TS2):
    return record_agent_decision(
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], task_id=task_id, decision_id=decision_id,
        exposed_memory_ids=exposed_memory_ids, output="the answer",
        finish_reason=FINISH_REASON_GENERATED, model_identity="qwen3-8b", config_fingerprint=CFG,
        used_memories_observability=USED_MEMORIES_NOT_OBSERVABLE,
        actor="test", reason="generation completed", timestamp=timestamp,
    )


# ---------------------------------------------------------------------------
# Scenario 1 -- clean single-hop reconstruction (attack-produced memory exposed directly)
# ---------------------------------------------------------------------------

def test_clean_single_hop_reconstruction(ledgers):
    injection_result = run_live_farma_injection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], timestamp=TS,
    )
    memory_id = injection_result.memory_creation.created_event.memory_ids[0]
    decision_event = _record_decision(ledgers, "dec-1", "task-1", (memory_id,))

    reconstruction = reconstruct_attack_origin(
        "DECISION", decision_event.decision_id, run_id=ledgers["run_id"],
        event_ledger=ledgers["event_ledger"], phase5_event_ledger=ledgers["phase5_ledger"],
    )

    assert reconstruction.chain_confidence == CHAIN_SINGLE_ORIGIN_HIGH_CONFIDENCE
    assert len(reconstruction.exposure) == 1
    assert memory_id in reconstruction.exposure
    assert reconstruction.per_memory_origin[memory_id].attack_id == "farma"


def test_clean_single_hop_reconstruction_via_action_target(ledgers):
    injection_result = run_live_farma_injection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], timestamp=TS,
    )
    memory_id = injection_result.memory_creation.created_event.memory_ids[0]
    decision_event = _record_decision(ledgers, "dec-1a", "task-1a", (memory_id,))
    action_event = record_agent_action(
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], task_id="task-1a", decision_id=decision_event.decision_id,
        action_id="act-1a", action="submit_answer", result="the answer",
        actor="test", reason="submitted", timestamp=TS3,
    )

    reconstruction = reconstruct_attack_origin(
        "ACTION", action_event.action_id, run_id=ledgers["run_id"],
        event_ledger=ledgers["event_ledger"], phase5_event_ledger=ledgers["phase5_ledger"],
    )

    assert reconstruction.chain_confidence == CHAIN_SINGLE_ORIGIN_HIGH_CONFIDENCE
    assert reconstruction.decision_id == decision_event.decision_id


# ---------------------------------------------------------------------------
# Scenario 2 -- multi-hop reconstruction through a real derived memory
# ---------------------------------------------------------------------------

def test_multi_hop_reconstruction_through_derived_memory(ledgers):
    injection_result = run_live_farma_injection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], timestamp=TS,
    )
    root_memory_id = injection_result.memory_creation.created_event.memory_ids[0]

    child = CanonicalMemoryRecord(
        memory_id="mem-mh-child", memory_type=MEMORY_TYPE_DERIVED, content={"text": "derived from attack root"},
        source={"source_type": SOURCE_TYPE_DERIVATION_EVENT}, parent_ids=(root_memory_id,),
        creation_event="derivation-of-mem-mh-child", creation_timestamp=TS2, lifecycle_state=LIFECYCLE_CREATED,
    )
    record_memory_derivation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        derived_record=child, source_memory_ids=(root_memory_id,),
        actor="test", reason="child derived from attack root", timestamp=TS2,
    )
    decision_event = _record_decision(ledgers, "dec-2", "task-2", ("mem-mh-child",), timestamp=TS3)

    reconstruction = reconstruct_attack_origin(
        "DECISION", decision_event.decision_id, run_id=ledgers["run_id"],
        event_ledger=ledgers["event_ledger"], phase5_event_ledger=ledgers["phase5_ledger"],
    )

    assert reconstruction.chain_confidence == CHAIN_SINGLE_ORIGIN_HIGH_CONFIDENCE
    assert reconstruction.per_memory_lineage["mem-mh-child"].source_id == root_memory_id
    assert reconstruction.per_memory_origin[root_memory_id].attack_id == "farma"


# ---------------------------------------------------------------------------
# Scenario 3 -- diamond ancestry -> MULTIPLE_PLAUSIBLE_ORIGINS, naming every candidate
# ---------------------------------------------------------------------------

def test_diamond_ancestry_multiple_plausible_origins(ledgers):
    farma_result = run_live_farma_injection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], timestamp=TS,
    )
    dsrm_result = run_live_dsrm_injection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], timestamp=TS,
    )
    farma_memory_id = farma_result.memory_creation.created_event.memory_ids[0]
    dsrm_memory_id = dsrm_result.memory_creation.created_event.memory_ids[0]

    merged_child = CanonicalMemoryRecord(
        memory_id="mem-diamond-child", memory_type=MEMORY_TYPE_DERIVED, content={"text": "merged from two attacks"},
        source={"source_type": SOURCE_TYPE_DERIVATION_EVENT}, parent_ids=(farma_memory_id, dsrm_memory_id),
        creation_event="derivation-of-mem-diamond-child", creation_timestamp=TS2, lifecycle_state=LIFECYCLE_CREATED,
    )
    record_memory_derivation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        derived_record=merged_child, source_memory_ids=(farma_memory_id, dsrm_memory_id),
        actor="test", reason="merge derivation from two attacks", timestamp=TS2,
    )
    decision_event = _record_decision(ledgers, "dec-3", "task-3", ("mem-diamond-child",), timestamp=TS3)

    reconstruction = reconstruct_attack_origin(
        "DECISION", decision_event.decision_id, run_id=ledgers["run_id"],
        event_ledger=ledgers["event_ledger"], phase5_event_ledger=ledgers["phase5_ledger"],
    )

    assert reconstruction.chain_confidence == CHAIN_MULTIPLE_PLAUSIBLE_ORIGINS
    lineage = reconstruction.per_memory_lineage["mem-diamond-child"]
    assert set(lineage.candidate_source_ids) == {farma_memory_id, dsrm_memory_id}
    assert reconstruction.per_memory_origin[farma_memory_id].attack_id == "farma"
    assert reconstruction.per_memory_origin[dsrm_memory_id].attack_id == "dsrm"
    assert any("MULTIPLE_POSSIBLE_SOURCES" in line for line in reconstruction.narrative)


# ---------------------------------------------------------------------------
# Scenario 4 -- genuinely benign decision -> NO_ATTACK_ORIGIN_FOUND
# ---------------------------------------------------------------------------

def test_benign_decision_reports_no_attack_origin_found(ledgers):
    benign = _foundation_record("mem-benign", "a real, ordinary fact")
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        record=benign, actor="test", reason="seed", timestamp=TS,
    )
    decision_event = _record_decision(ledgers, "dec-4", "task-4", ("mem-benign",))

    reconstruction = reconstruct_attack_origin(
        "DECISION", decision_event.decision_id, run_id=ledgers["run_id"],
        event_ledger=ledgers["event_ledger"], phase5_event_ledger=ledgers["phase5_ledger"],
    )

    assert reconstruction.chain_confidence == CHAIN_NO_ATTACK_ORIGIN_FOUND
    assert reconstruction.per_memory_origin["mem-benign"].status == "NO_ATTACK_ORIGIN"
    assert "NO_ATTACK_ORIGIN" in reconstruction.narrative[-1]


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_no_exposed_memories_is_insufficient_evidence(ledgers):
    decision_event = _record_decision(ledgers, "dec-5", "task-5", ())

    reconstruction = reconstruct_attack_origin(
        "DECISION", decision_event.decision_id, run_id=ledgers["run_id"],
        event_ledger=ledgers["event_ledger"], phase5_event_ledger=ledgers["phase5_ledger"],
    )

    assert reconstruction.chain_confidence == CHAIN_INSUFFICIENT_EVIDENCE
    assert reconstruction.exposure == {}


def test_unknown_decision_id_raises(ledgers):
    with pytest.raises(ValueError):
        reconstruct_attack_origin(
            "DECISION", "no-such-decision", run_id=ledgers["run_id"],
            event_ledger=ledgers["event_ledger"], phase5_event_ledger=ledgers["phase5_ledger"],
        )


def test_unsupported_target_type_raises(ledgers):
    with pytest.raises(ValueError):
        reconstruct_attack_origin(
            "NOT_A_REAL_TARGET_TYPE", "mem-benign", run_id=ledgers["run_id"],
            event_ledger=ledgers["event_ledger"], phase5_event_ledger=ledgers["phase5_ledger"],
        )


# ---------------------------------------------------------------------------
# MEMORY-typed target -- the real Stage 9.3 entry-point shape (a Phase 6
# MGPDecisionRecord.candidate_memory_id, or a Phase 7 campaign member id): no decision
# context, EXPOSURE hop skipped rather than fabricated.
# ---------------------------------------------------------------------------

def test_memory_target_skips_exposure_and_still_finds_origin(ledgers):
    injection_result = run_live_farma_injection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], timestamp=TS,
    )
    memory_id = injection_result.memory_creation.created_event.memory_ids[0]

    reconstruction = reconstruct_attack_origin(
        "MEMORY", memory_id, run_id=ledgers["run_id"],
        event_ledger=ledgers["event_ledger"], phase5_event_ledger=ledgers["phase5_ledger"],
    )

    assert reconstruction.decision_id is None
    assert reconstruction.exposure == {}
    assert reconstruction.walked_memory_ids == (memory_id,)
    assert reconstruction.chain_confidence == CHAIN_SINGLE_ORIGIN_HIGH_CONFIDENCE
    assert reconstruction.per_memory_origin[memory_id].attack_id == "farma"
    assert any("NOT CHECKED" in line for line in reconstruction.narrative)


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

def test_reconstruction_is_deterministic(ledgers):
    injection_result = run_live_farma_injection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], timestamp=TS,
    )
    memory_id = injection_result.memory_creation.created_event.memory_ids[0]
    decision_event = _record_decision(ledgers, "dec-6", "task-6", (memory_id,))

    first = reconstruct_attack_origin(
        "DECISION", decision_event.decision_id, run_id=ledgers["run_id"],
        event_ledger=ledgers["event_ledger"], phase5_event_ledger=ledgers["phase5_ledger"],
    )
    second = reconstruct_attack_origin(
        "DECISION", decision_event.decision_id, run_id=ledgers["run_id"],
        event_ledger=ledgers["event_ledger"], phase5_event_ledger=ledgers["phase5_ledger"],
    )

    assert first.to_dict() == second.to_dict()
    assert first.reconstruction_id == second.reconstruction_id


# ---------------------------------------------------------------------------
# Static discipline check -- forensics.py is purely additive, never touches Phase 3/4/5
# internals beyond the same real event-reading `attribution/wiring/action.py` already
# does, and never imports Phase 4 or defense/propagation modules directly.
# ---------------------------------------------------------------------------

def test_forensics_module_imports_only_attribution_and_frozen_substrate():
    import attribution.wiring.forensics as forensics_module

    source = inspect.getsource(forensics_module)
    forbidden_substrings = [
        "phase4.", "phase6.", "phase7.", "taint_propagation", "campaign_signals",
    ]
    for token in forbidden_substrings:
        assert token not in source, f"forensics.py must not import/reference {token!r} -- it is purely additive over attribution/ and phase5/wiring/lineage.py."
