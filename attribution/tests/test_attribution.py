"""Attribution -- the 11 named test scenarios (A-K) plus schema unit tests.

Fixture pattern mirrors `phase5/tests/test_lineage.py::ledgers` exactly (same real
ledgers, same real Stage 5.4-5.7 wiring calls) -- attribution is validated against real
persisted evidence built through the frozen pipeline, never hand-waved fixtures that
bypass it.
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
from phase5.wiring.live_attack_runs import run_live_dsrm_injection, run_live_farma_injection
from phase5.wiring.memory_lifecycle import record_memory_creation, record_memory_derivation, record_memory_lifecycle_transition

from attribution.metrics import (
    ambiguity_rate,
    build_origin_ground_truth,
    false_attribution_rate,
    influence_attribution_accuracy,
    lineage_reconstruction_accuracy,
    origin_attribution_accuracy,
    source_precision_recall,
)
from attribution.schema import (
    ATTRIBUTION_INFLUENCE,
    ATTRIBUTION_LINEAGE,
    ATTRIBUTION_ORIGIN,
    SOURCE_ATTACK,
    SOURCE_MEMORY,
    STATUS_EXPOSURE_ESTABLISHED,
    STATUS_INFLUENCE_ESTABLISHED,
    STATUS_INFLUENCE_NOT_ESTABLISHED,
    STATUS_MULTIPLE_POSSIBLE_SOURCES,
    STATUS_NO_ATTACK_ORIGIN,
    STATUS_NO_LINEAGE_ANCESTOR,
    STATUS_REFERENCES_ESTABLISHED,
    STATUS_REFERENCES_NOT_ESTABLISHED,
    STATUS_UNIQUE,
    AttributionResult,
    AttributionValidationError,
)
from attribution.wiring.action import attribute_action
from attribution.wiring.exposure import attribute_exposure
from attribution.wiring.influence import attribute_influence
from attribution.wiring.lineage import attribute_lineage
from attribution.wiring.origin import attribute_origin
from attribution.wiring.orchestrator import attribute_memory
from attribution.wiring.propagation import attribute_propagation
from attribution.wiring.references import attribute_references

TS = "2026-09-13T00:00:00+00:00"
TS2 = "2026-09-13T00:01:00+00:00"
TS3 = "2026-09-13T00:02:00+00:00"
CFG = "CFG-attribution-test"


def _foundation_record(memory_id, text, source_type=SOURCE_TYPE_PHASE2_UMR):
    return CanonicalMemoryRecord(
        memory_id=memory_id, memory_type=MEMORY_TYPE_FOUNDATION, content={"text": text},
        source={"source_type": source_type}, parent_ids=(),
        creation_event=f"creation-of-{memory_id}", creation_timestamp=TS, lifecycle_state=LIFECYCLE_CREATED,
    )


def _make_ledgers(tmp_path, run_id="RUN-attribution"):
    memory_ledger = CanonicalMemoryLedger(tmp_path / "memory")
    event_ledger = CanonicalEventLedger(tmp_path / "events", memory_ledger)
    supersession_ledger = SupersessionLedger(tmp_path / "supersessions")
    run_ledger = ExperimentRunLedger(tmp_path / "runs")
    membership_ledger = EventRunMembershipLedger(tmp_path / "membership", run_ledger)
    phase5_ledger = Phase5EventLedger(tmp_path / "phase5_events")
    run = ExperimentRunRecord(
        experiment_id="exp-attribution", run_id=run_id, dataset="locomo",
        scope={}, started_at=TS, actor="test", reason="attribution test run",
    )
    run_ledger.register(run)
    return dict(
        memory_ledger=memory_ledger, event_ledger=event_ledger, supersession_ledger=supersession_ledger,
        membership_ledger=membership_ledger, phase5_ledger=phase5_ledger, run_id=run.run_id,
    )


@pytest.fixture
def ledgers(tmp_path):
    return _make_ledgers(tmp_path)


# ---------------------------------------------------------------------------
# Schema unit tests
# ---------------------------------------------------------------------------

def test_attribution_result_rejects_positive_status_without_evidence():
    with pytest.raises(AttributionValidationError, match="evidence_event_ids"):
        AttributionResult(
            attribution_id="ATTR-1", run_id="RUN-1", target_type="MEMORY", target_id="m1",
            attribution_type=ATTRIBUTION_ORIGIN, status=STATUS_UNIQUE, source_id="attack-x",
        )


def test_attribution_result_rejects_unique_without_source_id():
    with pytest.raises(AttributionValidationError, match="source_id"):
        AttributionResult(
            attribution_id="ATTR-2", run_id="RUN-1", target_type="MEMORY", target_id="m1",
            attribution_type=ATTRIBUTION_ORIGIN, status=STATUS_UNIQUE,
            evidence_event_ids=("evt-1",), evidence_kind="OBSERVED_EVENT",
        )


def test_attribution_result_rejects_negative_status_with_source_id():
    with pytest.raises(AttributionValidationError, match="not an origin-resolution finding"):
        AttributionResult(
            attribution_id="ATTR-3", run_id="RUN-1", target_type="MEMORY", target_id="m1",
            attribution_type=ATTRIBUTION_ORIGIN, status=STATUS_NO_ATTACK_ORIGIN, source_id="should-not-be-set",
        )


def test_attribution_result_rejects_multiple_sources_with_one_candidate():
    with pytest.raises(AttributionValidationError, match="MULTIPLE_POSSIBLE_SOURCES"):
        AttributionResult(
            attribution_id="ATTR-4", run_id="RUN-1", target_type="MEMORY", target_id="m1",
            attribution_type=ATTRIBUTION_LINEAGE, status=STATUS_MULTIPLE_POSSIBLE_SOURCES,
            candidate_source_ids=("only-one",),
        )


def test_attribution_result_round_trips_through_dict():
    result = AttributionResult(
        attribution_id="ATTR-5", run_id="RUN-1", target_type="MEMORY", target_id="m1",
        attribution_type=ATTRIBUTION_ORIGIN, status=STATUS_UNIQUE, source_type=SOURCE_ATTACK,
        source_id="attack-x", evidence_event_ids=("evt-1", "evt-2"), evidence_kind="OBSERVED_EVENT",
        lineage_path=("a", "b"), candidate_source_ids=None, details={"k": "v"},
    )
    restored = AttributionResult.from_dict(result.to_dict())
    assert restored == result


# ---------------------------------------------------------------------------
# Scenario A -- direct origin
# ---------------------------------------------------------------------------

def test_scenario_a_direct_origin(ledgers):
    injection_result = run_live_farma_injection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], timestamp=TS,
    )
    memory_id = injection_result.memory_creation.created_event.memory_ids[0]

    result = attribute_origin(memory_id, run_id=ledgers["run_id"], phase5_event_ledger=ledgers["phase5_ledger"])
    assert result.status == STATUS_UNIQUE
    assert result.source_type == SOURCE_ATTACK
    assert result.source_id == injection_result.injection_event.injection_id
    assert result.attack_id == "farma"
    assert result.evidence_event_ids == (injection_result.injection_event.event_id,)


# ---------------------------------------------------------------------------
# Scenario B -- derived lineage
# ---------------------------------------------------------------------------

def test_scenario_b_derived_lineage(ledgers):
    parent = _foundation_record("mem-b-parent", "parent fact")
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        record=parent, actor="test", reason="seed", timestamp=TS,
    )
    child = CanonicalMemoryRecord(
        memory_id="mem-b-child", memory_type=MEMORY_TYPE_DERIVED, content={"text": "derived fact"},
        source={"source_type": SOURCE_TYPE_DERIVATION_EVENT}, parent_ids=("mem-b-parent",),
        creation_event="derivation-of-mem-b-child", creation_timestamp=TS2, lifecycle_state=LIFECYCLE_CREATED,
    )
    record_memory_derivation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        derived_record=child, source_memory_ids=("mem-b-parent",),
        actor="test", reason="child derived from parent", timestamp=TS2,
    )

    result = attribute_lineage("mem-b-child", run_id=ledgers["run_id"], event_ledger=ledgers["event_ledger"])
    assert result.status == STATUS_UNIQUE
    assert result.source_type == SOURCE_MEMORY
    assert result.source_id == "mem-b-parent"
    assert result.lineage_path == ("mem-b-parent", "mem-b-child")


# ---------------------------------------------------------------------------
# Scenario C -- multiple attacks, no cross-attribution
# ---------------------------------------------------------------------------

def test_scenario_c_multiple_attacks_no_cross_attribution(ledgers):
    farma_result = run_live_farma_injection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], timestamp=TS,
    )
    dsrm_result = run_live_dsrm_injection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], timestamp=TS2,
    )
    farma_memory_id = farma_result.memory_creation.created_event.memory_ids[0]
    dsrm_memory_id = dsrm_result.memory_creation.created_event.memory_ids[0]
    assert farma_memory_id != dsrm_memory_id

    farma_attribution = attribute_origin(farma_memory_id, run_id=ledgers["run_id"], phase5_event_ledger=ledgers["phase5_ledger"])
    dsrm_attribution = attribute_origin(dsrm_memory_id, run_id=ledgers["run_id"], phase5_event_ledger=ledgers["phase5_ledger"])

    assert farma_attribution.attack_id == "farma"
    assert farma_attribution.source_id == farma_result.injection_event.injection_id
    assert dsrm_attribution.attack_id == "dsrm"
    assert dsrm_attribution.source_id == dsrm_result.injection_event.injection_id
    assert farma_attribution.source_id != dsrm_attribution.source_id


# ---------------------------------------------------------------------------
# Scenario D -- ambiguous/convergent lineage preserved
# ---------------------------------------------------------------------------

def test_scenario_d_ambiguous_convergent_lineage_preserved(ledgers):
    parent_1 = _foundation_record("mem-d-parent-1", "fact one")
    parent_2 = _foundation_record("mem-d-parent-2", "fact two")
    for rec in (parent_1, parent_2):
        record_memory_creation(
            memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
            membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
            record=rec, actor="test", reason="seed", timestamp=TS,
        )
    merged_child = CanonicalMemoryRecord(
        memory_id="mem-d-merged-child", memory_type=MEMORY_TYPE_DERIVED, content={"text": "merged fact"},
        source={"source_type": SOURCE_TYPE_DERIVATION_EVENT}, parent_ids=("mem-d-parent-1", "mem-d-parent-2"),
        creation_event="derivation-of-mem-d-merged-child", creation_timestamp=TS2, lifecycle_state=LIFECYCLE_CREATED,
    )
    record_memory_derivation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        derived_record=merged_child, source_memory_ids=("mem-d-parent-1", "mem-d-parent-2"),
        actor="test", reason="merge derivation", timestamp=TS2,
    )

    result = attribute_lineage("mem-d-merged-child", run_id=ledgers["run_id"], event_ledger=ledgers["event_ledger"])
    assert result.status == STATUS_MULTIPLE_POSSIBLE_SOURCES
    assert result.source_id is None  # never an arbitrary pick
    assert set(result.candidate_source_ids) == {"mem-d-parent-1", "mem-d-parent-2"}


# ---------------------------------------------------------------------------
# Scenario E -- exposure without influence -> INFLUENCE_NOT_ESTABLISHED
# ---------------------------------------------------------------------------

def test_scenario_e_exposure_without_influence(ledgers):
    memory = _foundation_record("mem-e-exposed", "an exposed but not influential fact")
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        record=memory, actor="test", reason="seed", timestamp=TS,
    )
    decision_event = record_agent_decision(
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], task_id="task-e", decision_id="dec-e",
        exposed_memory_ids=("mem-e-exposed",), output="the answer",
        finish_reason=FINISH_REASON_GENERATED, model_identity="qwen3-8b", config_fingerprint=CFG,
        used_memories_observability=USED_MEMORIES_NOT_OBSERVABLE,
        actor="test", reason="generation completed", timestamp=TS2,
    )

    exposure = attribute_exposure("mem-e-exposed", "dec-e", run_id=ledgers["run_id"], phase5_event_ledger=ledgers["phase5_ledger"])
    assert exposure.status == STATUS_EXPOSURE_ESTABLISHED
    assert exposure.evidence_event_ids == (decision_event.event_id,)

    influence = attribute_influence("mem-e-exposed", run_id=ledgers["run_id"], event_ledger=ledgers["event_ledger"])
    assert influence.status == STATUS_INFLUENCE_NOT_ESTABLISHED
    assert influence.source_id is None


# ---------------------------------------------------------------------------
# Scenario F -- genuine influence -> ESTABLISHED with real event ids
# ---------------------------------------------------------------------------

def test_scenario_f_genuine_influence_established(ledgers):
    memory = _foundation_record("mem-f-influential", "a forged claim")
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        record=memory, actor="test", reason="seed", timestamp=TS,
    )
    counterfactual_event = CanonicalEvent(
        event_id="evt-f-counterfactual-1", event_type=EVENT_COUNTERFACTUALLY_INFLUENTIAL,
        memory_ids=("mem-f-influential",), timestamp=TS2, actor="test", reason="masking changed the answer",
        task_id="task-f", config_fingerprint=CFG, counterfactual_answer_hash="hash-masked",
        baseline_answer_hash="hash-baseline", diff_criterion="exact_match_changed",
        masking_method=MASKING_METHOD_SELECTED_SET_REMOVAL,
    )
    ledgers["event_ledger"].append(counterfactual_event)

    result = attribute_influence("mem-f-influential", run_id=ledgers["run_id"], event_ledger=ledgers["event_ledger"], task_id="task-f")
    assert result.status == STATUS_INFLUENCE_ESTABLISHED
    assert result.evidence_event_ids == ("evt-f-counterfactual-1",)
    assert result.evidence_kind == "COUNTERFACTUAL_EVIDENCE"


# ---------------------------------------------------------------------------
# Scenario G -- temporal-order trap does not produce influence
# ---------------------------------------------------------------------------

def test_scenario_g_temporal_order_trap_does_not_produce_influence(ledgers):
    memory = _foundation_record("mem-g-early", "an early, heavily-used fact")
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        record=memory, actor="test", reason="seed", timestamp=TS,
    )
    # This memory is exposed to THREE separate decisions, all strictly before any
    # counterfactual test is ever run against it -- a naive "used early and often ->
    # probably influential" heuristic would flag it. No such heuristic exists here.
    for i in range(3):
        record_agent_decision(
            phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
            run_id=ledgers["run_id"], task_id=f"task-g-{i}", decision_id=f"dec-g-{i}",
            exposed_memory_ids=("mem-g-early",), output="the answer",
            finish_reason=FINISH_REASON_GENERATED, model_identity="qwen3-8b", config_fingerprint=CFG,
            used_memories_observability=USED_MEMORIES_NOT_OBSERVABLE,
            actor="test", reason="generation completed", timestamp=TS2,
        )
    result = attribute_influence("mem-g-early", run_id=ledgers["run_id"], event_ledger=ledgers["event_ledger"])
    assert result.status == STATUS_INFLUENCE_NOT_ESTABLISHED
    assert result.evidence_event_ids == ()


# ---------------------------------------------------------------------------
# Scenario H -- cross-run isolation trap
# ---------------------------------------------------------------------------

def test_scenario_h_cross_run_isolation(tmp_path):
    ledgers_a = _make_ledgers(tmp_path / "run-a", run_id="RUN-h-a")
    ledgers_b = _make_ledgers(tmp_path / "run-b", run_id="RUN-h-b")

    injection_result = run_live_farma_injection(
        memory_ledger=ledgers_a["memory_ledger"], event_ledger=ledgers_a["event_ledger"],
        phase5_event_ledger=ledgers_a["phase5_ledger"], membership_ledger=ledgers_a["membership_ledger"],
        run_id=ledgers_a["run_id"], timestamp=TS,
    )
    memory_id = injection_result.memory_creation.created_event.memory_ids[0]

    result_a = attribute_origin(memory_id, run_id=ledgers_a["run_id"], phase5_event_ledger=ledgers_a["phase5_ledger"])
    assert result_a.status == STATUS_UNIQUE

    # Run B's own ledgers never saw this injection -- attribution against run B's
    # (empty) Phase5EventLedger must find nothing, never leak run A's evidence.
    result_b = attribute_origin(memory_id, run_id=ledgers_b["run_id"], phase5_event_ledger=ledgers_b["phase5_ledger"])
    assert result_b.status == STATUS_NO_ATTACK_ORIGIN
    assert result_b.run_id == "RUN-h-b"


# ---------------------------------------------------------------------------
# Scenario I -- version/supersession survives without collapsing
# ---------------------------------------------------------------------------

def test_scenario_i_supersession_does_not_collapse_attribution(ledgers):
    injection_result = run_live_farma_injection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], timestamp=TS,
    )
    old_memory_id = injection_result.memory_creation.created_event.memory_ids[0]

    new_memory = _foundation_record("mem-i-corrected", "corrected, non-attack fact")
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        record=new_memory, actor="test", reason="seed", timestamp=TS2,
    )
    superseded_event = CanonicalEvent(
        event_id="evt-i-superseded-1", event_type=EVENT_SUPERSEDED, memory_ids=(old_memory_id,),
        timestamp=TS3, actor="test", reason="corrected", previous_state=LIFECYCLE_ACTIVE, new_state=LIFECYCLE_RETIRED,
    )
    retired_event = CanonicalEvent(
        event_id="evt-i-retired-1", event_type=EVENT_RETIRED, memory_ids=(old_memory_id,),
        timestamp=TS3, actor="test", reason="corrected", previous_state=LIFECYCLE_ACTIVE, new_state=LIFECYCLE_RETIRED,
    )
    record_memory_lifecycle_transition(
        event_ledger=ledgers["event_ledger"], memory_ledger=ledgers["memory_ledger"],
        supersession_ledger=ledgers["supersession_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], superseded_memory_id=old_memory_id, superseding_memory_id="mem-i-corrected",
        superseded_event=superseded_event, retired_event=retired_event,
    )

    old_attribution = attribute_origin(old_memory_id, run_id=ledgers["run_id"], phase5_event_ledger=ledgers["phase5_ledger"])
    new_attribution = attribute_origin("mem-i-corrected", run_id=ledgers["run_id"], phase5_event_ledger=ledgers["phase5_ledger"])

    assert old_attribution.status == STATUS_UNIQUE
    assert old_attribution.attack_id == "farma"
    # The successor is its OWN, independently-attributed memory -- SUPERSEDES is a
    # separate relationship, never a channel that transfers the predecessor's attack
    # origin onto it.
    assert new_attribution.status == STATUS_NO_ATTACK_ORIGIN


# ---------------------------------------------------------------------------
# Scenario J -- ledger-reload determinism
# ---------------------------------------------------------------------------

def test_scenario_j_ledger_reload_determinism(tmp_path):
    ledgers_first = _make_ledgers(tmp_path, run_id="RUN-j")
    injection_result = run_live_farma_injection(
        memory_ledger=ledgers_first["memory_ledger"], event_ledger=ledgers_first["event_ledger"],
        phase5_event_ledger=ledgers_first["phase5_ledger"], membership_ledger=ledgers_first["membership_ledger"],
        run_id=ledgers_first["run_id"], timestamp=TS,
    )
    memory_id = injection_result.memory_creation.created_event.memory_ids[0]
    result_before_reload = attribute_origin(memory_id, run_id="RUN-j", phase5_event_ledger=ledgers_first["phase5_ledger"])

    # Fresh ledger objects constructed from the SAME storage_dir -- proves attribution
    # depends only on persisted state, never on in-process objects.
    reloaded_phase5_ledger = Phase5EventLedger(tmp_path / "phase5_events")
    result_after_reload = attribute_origin(memory_id, run_id="RUN-j", phase5_event_ledger=reloaded_phase5_ledger)

    assert result_before_reload == result_after_reload


# ---------------------------------------------------------------------------
# Scenario K -- repeated-call determinism
# ---------------------------------------------------------------------------

def test_scenario_k_repeated_call_determinism(ledgers):
    injection_result = run_live_farma_injection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], timestamp=TS,
    )
    memory_id = injection_result.memory_creation.created_event.memory_ids[0]

    first = attribute_origin(memory_id, run_id=ledgers["run_id"], phase5_event_ledger=ledgers["phase5_ledger"])
    second = attribute_origin(memory_id, run_id=ledgers["run_id"], phase5_event_ledger=ledgers["phase5_ledger"])
    assert first == second

    lineage_first = attribute_lineage(memory_id, run_id=ledgers["run_id"], event_ledger=ledgers["event_ledger"])
    lineage_second = attribute_lineage(memory_id, run_id=ledgers["run_id"], event_ledger=ledgers["event_ledger"])
    assert lineage_first == lineage_second


# ---------------------------------------------------------------------------
# PROPAGATION and orchestrator coverage (not one of the 11 named letters, but real
# additional coverage for a type the letters don't otherwise exercise standalone)
# ---------------------------------------------------------------------------

def test_propagation_unique_and_no_attack_origin(ledgers):
    injection_result = run_live_farma_injection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], timestamp=TS,
    )
    attack_id = injection_result.memory_creation.created_event.memory_ids[0]
    child = CanonicalMemoryRecord(
        memory_id="mem-prop-child", memory_type=MEMORY_TYPE_DERIVED, content={"text": "propagated"},
        source={"source_type": SOURCE_TYPE_DERIVATION_EVENT}, parent_ids=(attack_id,),
        creation_event="derivation-of-mem-prop-child", creation_timestamp=TS2, lifecycle_state=LIFECYCLE_CREATED,
    )
    record_memory_derivation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        derived_record=child, source_memory_ids=(attack_id,), actor="test", reason="hop", timestamp=TS2,
    )
    unrelated = _foundation_record("mem-prop-unrelated", "unrelated content")
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        record=unrelated, actor="test", reason="seed", timestamp=TS,
    )

    propagated = attribute_propagation(
        "mem-prop-child", run_id=ledgers["run_id"], memory_ledger=ledgers["memory_ledger"],
        event_ledger=ledgers["event_ledger"], attack_memory_ids=[attack_id],
    )
    assert propagated.status == STATUS_UNIQUE
    assert propagated.source_id == attack_id
    assert propagated.lineage_path == (attack_id, "mem-prop-child")

    not_propagated = attribute_propagation(
        "mem-prop-unrelated", run_id=ledgers["run_id"], memory_ledger=ledgers["memory_ledger"],
        event_ledger=ledgers["event_ledger"], attack_memory_ids=[attack_id],
    )
    assert not_propagated.status == STATUS_NO_ATTACK_ORIGIN


def test_lineage_no_ancestor_for_foundation_memory(ledgers):
    memory = _foundation_record("mem-root", "a root fact")
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        record=memory, actor="test", reason="seed", timestamp=TS,
    )
    result = attribute_lineage("mem-root", run_id=ledgers["run_id"], event_ledger=ledgers["event_ledger"])
    assert result.status == STATUS_NO_LINEAGE_ANCESTOR
    assert result.source_id is None


def test_orchestrator_attribute_memory_combines_types_without_collapsing(ledgers):
    injection_result = run_live_farma_injection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], timestamp=TS,
    )
    memory_id = injection_result.memory_creation.created_event.memory_ids[0]
    decision_event = record_agent_decision(
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], task_id="task-orch", decision_id="dec-orch",
        exposed_memory_ids=(memory_id,), output="the answer",
        finish_reason=FINISH_REASON_GENERATED, model_identity="qwen3-8b", config_fingerprint=CFG,
        used_memories_observability=USED_MEMORIES_NOT_OBSERVABLE,
        actor="test", reason="generation completed", timestamp=TS2,
    )

    results = attribute_memory(
        memory_id, run_id=ledgers["run_id"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], memory_ledger=ledgers["memory_ledger"],
        attack_memory_ids=[memory_id], decision_id="dec-orch",
    )
    by_type = {r.attribution_type: r for r in results}
    assert set(by_type) == {"ORIGIN", "LINEAGE", "INFLUENCE", "PROPAGATION", "EXPOSURE", "REFERENCES"}
    assert by_type["ORIGIN"].status == STATUS_UNIQUE
    assert by_type["LINEAGE"].status == STATUS_NO_LINEAGE_ANCESTOR
    assert by_type["INFLUENCE"].status == STATUS_INFLUENCE_NOT_ESTABLISHED
    assert by_type["EXPOSURE"].status == STATUS_EXPOSURE_ESTABLISHED
    assert by_type["REFERENCES"].status == STATUS_REFERENCES_NOT_ESTABLISHED
    assert decision_event.event_id  # sanity: the real decision event was actually recorded


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def test_metrics_computed_over_real_scenario_a_and_h(ledgers, tmp_path):
    injection_result = run_live_farma_injection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], timestamp=TS,
    )
    attack_memory_id = injection_result.memory_creation.created_event.memory_ids[0]
    unrelated = _foundation_record("mem-metrics-unrelated", "unrelated content")
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        record=unrelated, actor="test", reason="seed", timestamp=TS,
    )

    results_by_memory_id = {
        attack_memory_id: attribute_origin(attack_memory_id, run_id=ledgers["run_id"], phase5_event_ledger=ledgers["phase5_ledger"]),
        "mem-metrics-unrelated": attribute_origin("mem-metrics-unrelated", run_id=ledgers["run_id"], phase5_event_ledger=ledgers["phase5_ledger"]),
    }
    ground_truth = {
        attack_memory_id: injection_result.injection_event.injection_id,
        "mem-metrics-unrelated": None,
    }
    assert origin_attribution_accuracy(results_by_memory_id, ground_truth) == 1.0
    precision, recall = source_precision_recall(results_by_memory_id, ground_truth)
    assert precision == 1.0 and recall == 1.0
    assert ambiguity_rate(tuple(results_by_memory_id.values())) == 0.0

    with pytest.raises(ValueError):
        false_attribution_rate({}, {})


def test_metrics_lineage_and_influence(ledgers):
    parent_1 = _foundation_record("mem-ml-parent-1", "p1")
    parent_2 = _foundation_record("mem-ml-parent-2", "p2")
    for rec in (parent_1, parent_2):
        record_memory_creation(
            memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
            membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
            record=rec, actor="test", reason="seed", timestamp=TS,
        )
    merged = CanonicalMemoryRecord(
        memory_id="mem-ml-merged", memory_type=MEMORY_TYPE_DERIVED, content={"text": "merged"},
        source={"source_type": SOURCE_TYPE_DERIVATION_EVENT}, parent_ids=("mem-ml-parent-1", "mem-ml-parent-2"),
        creation_event="derivation-of-mem-ml-merged", creation_timestamp=TS2, lifecycle_state=LIFECYCLE_CREATED,
    )
    record_memory_derivation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        derived_record=merged, source_memory_ids=("mem-ml-parent-1", "mem-ml-parent-2"),
        actor="test", reason="merge", timestamp=TS2,
    )
    results_by_memory_id = {"mem-ml-merged": attribute_lineage("mem-ml-merged", run_id=ledgers["run_id"], event_ledger=ledgers["event_ledger"])}
    ground_truth_parents = {"mem-ml-merged": ("mem-ml-parent-1", "mem-ml-parent-2")}
    assert lineage_reconstruction_accuracy(results_by_memory_id, ground_truth_parents) == 1.0

    counterfactual_event = CanonicalEvent(
        event_id="evt-ml-counterfactual-1", event_type=EVENT_COUNTERFACTUALLY_INFLUENTIAL,
        memory_ids=("mem-ml-parent-1",), timestamp=TS2, actor="test", reason="masking changed the answer",
        task_id="task-ml", config_fingerprint=CFG, counterfactual_answer_hash="hash-masked",
        baseline_answer_hash="hash-baseline", diff_criterion="exact_match_changed",
        masking_method=MASKING_METHOD_SELECTED_SET_REMOVAL,
    )
    ledgers["event_ledger"].append(counterfactual_event)
    influence_results = {
        "mem-ml-parent-1": attribute_influence("mem-ml-parent-1", run_id=ledgers["run_id"], event_ledger=ledgers["event_ledger"]),
        "mem-ml-parent-2": attribute_influence("mem-ml-parent-2", run_id=ledgers["run_id"], event_ledger=ledgers["event_ledger"]),
    }
    influence_ground_truth = {"mem-ml-parent-1": True, "mem-ml-parent-2": False}
    assert influence_attribution_accuracy(influence_results, influence_ground_truth) == 1.0


# ---------------------------------------------------------------------------
# Fix 1 -- ACTION-targeted attribution
# ---------------------------------------------------------------------------

def test_action_targeted_attribution_resolves_via_decision(ledgers):
    memory = _foundation_record("mem-act-exposed", "a fact used by an action")
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        record=memory, actor="test", reason="seed", timestamp=TS,
    )
    record_agent_decision(
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], task_id="task-act", decision_id="dec-act",
        exposed_memory_ids=("mem-act-exposed",), output="the answer",
        finish_reason=FINISH_REASON_GENERATED, model_identity="qwen3-8b", config_fingerprint=CFG,
        used_memories_observability=USED_MEMORIES_NOT_OBSERVABLE,
        actor="test", reason="generation completed", timestamp=TS2,
    )
    action_event = record_agent_action(
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], task_id="task-act", decision_id="dec-act", action_id="act-1",
        action="submit_answer", result="ok", actor="test", reason="submitted", timestamp=TS3,
    )

    result = attribute_action("act-1", "mem-act-exposed", run_id=ledgers["run_id"], phase5_event_ledger=ledgers["phase5_ledger"])
    assert result.target_type == "ACTION"
    assert result.target_id == "act-1"
    assert result.status == STATUS_EXPOSURE_ESTABLISHED
    assert result.details["action_id"] == "act-1"
    assert result.details["decision_id"] == "dec-act"
    assert action_event.action_id == "act-1"


def test_action_targeted_attribution_raises_on_unknown_action(ledgers):
    with pytest.raises(ValueError, match="action_id"):
        attribute_action("act-does-not-exist", "mem-x", run_id=ledgers["run_id"], phase5_event_ledger=ledgers["phase5_ledger"])


def test_orchestrator_includes_action_result_when_action_id_given(ledgers):
    memory = _foundation_record("mem-orch-act", "fact")
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        record=memory, actor="test", reason="seed", timestamp=TS,
    )
    record_agent_decision(
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], task_id="task-orch-act", decision_id="dec-orch-act",
        exposed_memory_ids=("mem-orch-act",), output="the answer",
        finish_reason=FINISH_REASON_GENERATED, model_identity="qwen3-8b", config_fingerprint=CFG,
        used_memories_observability=USED_MEMORIES_NOT_OBSERVABLE,
        actor="test", reason="generation completed", timestamp=TS2,
    )
    record_agent_action(
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], task_id="task-orch-act", decision_id="dec-orch-act", action_id="act-orch-1",
        action="submit_answer", result="ok", actor="test", reason="submitted", timestamp=TS3,
    )
    results = attribute_memory(
        "mem-orch-act", run_id=ledgers["run_id"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], action_id="act-orch-1",
    )
    action_results = [r for r in results if r.target_type == "ACTION"]
    assert len(action_results) == 1
    assert action_results[0].status == STATUS_EXPOSURE_ESTABLISHED


# ---------------------------------------------------------------------------
# Fix 2 -- full ancestor chain for LINEAGE
# ---------------------------------------------------------------------------

def _seed_linear_chain(ledgers, ids, texts):
    """Seed a strictly linear real derivation chain ids[0] (root, foundation) -> ids[1] -> ... -> ids[-1]."""
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        record=_foundation_record(ids[0], texts[0]), actor="test", reason="seed", timestamp=TS,
    )
    for i in range(1, len(ids)):
        child = CanonicalMemoryRecord(
            memory_id=ids[i], memory_type=MEMORY_TYPE_DERIVED, content={"text": texts[i]},
            source={"source_type": SOURCE_TYPE_DERIVATION_EVENT}, parent_ids=(ids[i - 1],),
            creation_event=f"derivation-of-{ids[i]}", creation_timestamp=f"2026-09-13T00:0{i}:00+00:00",
            lifecycle_state=LIFECYCLE_CREATED,
        )
        record_memory_derivation(
            memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
            membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
            derived_record=child, source_memory_ids=(ids[i - 1],),
            actor="test", reason="hop", timestamp=f"2026-09-13T00:0{i}:00+00:00",
        )


def test_full_chain_lineage_linear(ledgers):
    ids = ["mem-chain-root", "mem-chain-mid", "mem-chain-leaf"]
    _seed_linear_chain(ledgers, ids, ["root fact", "mid fact", "leaf fact"])

    one_hop = attribute_lineage("mem-chain-leaf", run_id=ledgers["run_id"], event_ledger=ledgers["event_ledger"])
    assert one_hop.status == STATUS_UNIQUE
    assert one_hop.source_id == "mem-chain-mid"
    assert one_hop.lineage_path == ("mem-chain-mid", "mem-chain-leaf")

    full = attribute_lineage("mem-chain-leaf", run_id=ledgers["run_id"], event_ledger=ledgers["event_ledger"], full_chain=True)
    assert full.status == STATUS_UNIQUE
    assert full.source_id == "mem-chain-root"
    assert full.lineage_path == tuple(ids)
    assert len(full.evidence_event_ids) == 2  # both real hops cited


def test_full_chain_lineage_branching_reports_all_ancestors(ledgers):
    parent_1 = _foundation_record("mem-fc-parent-1", "p1")
    parent_2 = _foundation_record("mem-fc-parent-2", "p2")
    for rec in (parent_1, parent_2):
        record_memory_creation(
            memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
            membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
            record=rec, actor="test", reason="seed", timestamp=TS,
        )
    merged = CanonicalMemoryRecord(
        memory_id="mem-fc-merged", memory_type=MEMORY_TYPE_DERIVED, content={"text": "merged"},
        source={"source_type": SOURCE_TYPE_DERIVATION_EVENT}, parent_ids=("mem-fc-parent-1", "mem-fc-parent-2"),
        creation_event="derivation-of-mem-fc-merged", creation_timestamp=TS2, lifecycle_state=LIFECYCLE_CREATED,
    )
    record_memory_derivation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        derived_record=merged, source_memory_ids=("mem-fc-parent-1", "mem-fc-parent-2"),
        actor="test", reason="merge", timestamp=TS2,
    )
    grandchild = CanonicalMemoryRecord(
        memory_id="mem-fc-grandchild", memory_type=MEMORY_TYPE_DERIVED, content={"text": "one more hop"},
        source={"source_type": SOURCE_TYPE_DERIVATION_EVENT}, parent_ids=("mem-fc-merged",),
        creation_event="derivation-of-mem-fc-grandchild", creation_timestamp=TS3, lifecycle_state=LIFECYCLE_CREATED,
    )
    record_memory_derivation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        derived_record=grandchild, source_memory_ids=("mem-fc-merged",),
        actor="test", reason="hop after merge", timestamp=TS3,
    )

    full = attribute_lineage("mem-fc-grandchild", run_id=ledgers["run_id"], event_ledger=ledgers["event_ledger"], full_chain=True)
    assert full.status == STATUS_MULTIPLE_POSSIBLE_SOURCES
    assert full.source_id is None
    assert set(full.candidate_source_ids) == {"mem-fc-parent-1", "mem-fc-parent-2", "mem-fc-merged"}


def test_full_chain_lineage_no_ancestor_same_as_one_hop(ledgers):
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        record=_foundation_record("mem-fc-root-only", "root only"), actor="test", reason="seed", timestamp=TS,
    )
    result = attribute_lineage("mem-fc-root-only", run_id=ledgers["run_id"], event_ledger=ledgers["event_ledger"], full_chain=True)
    assert result.status == STATUS_NO_LINEAGE_ANCESTOR


# ---------------------------------------------------------------------------
# Fix 3 -- ground-truth assembly helper
# ---------------------------------------------------------------------------

def test_build_origin_ground_truth_from_real_injection_results(ledgers):
    farma_result = run_live_farma_injection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], timestamp=TS,
    )
    dsrm_result = run_live_dsrm_injection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], timestamp=TS2,
    )
    unrelated = _foundation_record("mem-bg-unrelated", "unrelated")
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        record=unrelated, actor="test", reason="seed", timestamp=TS,
    )

    ground_truth = build_origin_ground_truth(
        [farma_result, dsrm_result], known_non_attack_memory_ids=["mem-bg-unrelated"],
    )
    farma_memory_id = farma_result.memory_creation.created_event.memory_ids[0]
    dsrm_memory_id = dsrm_result.memory_creation.created_event.memory_ids[0]
    assert ground_truth[farma_memory_id] == farma_result.injection_event.injection_id
    assert ground_truth[dsrm_memory_id] == dsrm_result.injection_event.injection_id
    assert ground_truth["mem-bg-unrelated"] is None

    results_by_memory_id = {
        mid: attribute_origin(mid, run_id=ledgers["run_id"], phase5_event_ledger=ledgers["phase5_ledger"])
        for mid in ground_truth
    }
    assert origin_attribution_accuracy(results_by_memory_id, ground_truth) == 1.0


# ---------------------------------------------------------------------------
# Fix 4 (partial closure) -- REFERENCES, closed via a reopened Stage 5.7
# ---------------------------------------------------------------------------

def test_attribute_references_established_from_real_content_citation(ledgers):
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        record=_foundation_record("mem-ar-cited", "the original fact"), actor="test", reason="seed", timestamp=TS,
    )
    citing = CanonicalMemoryRecord(
        memory_id="mem-ar-citing", memory_type=MEMORY_TYPE_DERIVED, content={"text": "per [mem-ar-cited], the claim holds"},
        source={"source_type": SOURCE_TYPE_DERIVATION_EVENT}, parent_ids=("mem-ar-cited",),
        creation_event="derivation-of-mem-ar-citing", creation_timestamp=TS2, lifecycle_state=LIFECYCLE_CREATED,
    )
    record_memory_derivation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        derived_record=citing, source_memory_ids=("mem-ar-cited",),
        actor="test", reason="cites its own parent explicitly", timestamp=TS2,
    )

    result = attribute_references("mem-ar-citing", run_id=ledgers["run_id"], memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"])
    assert result.status == STATUS_REFERENCES_ESTABLISHED
    assert result.candidate_source_ids == ("mem-ar-cited",)
    assert result.source_id is None  # never squeezed into a single source_id
    assert len(result.evidence_event_ids) == 1


def test_attribute_references_not_established_without_citation(ledgers):
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        record=_foundation_record("mem-ar-plain", "a fact with no citations"), actor="test", reason="seed", timestamp=TS,
    )
    result = attribute_references("mem-ar-plain", run_id=ledgers["run_id"], memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"])
    assert result.status == STATUS_REFERENCES_NOT_ESTABLISHED
    assert result.candidate_source_ids is None


def test_attribute_references_never_from_word_overlap(ledgers):
    """The behavioral-inference idea (word overlap / semantic similarity) that the
    Post-Phase-5 hardening pass explicitly rejected must still never fire here -- this
    reopening did not revisit that rejection."""
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        record=_foundation_record("mem-ar-src", "camping trip to the lake"), actor="test", reason="seed", timestamp=TS,
    )
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        record=_foundation_record("mem-ar-mention", "mem-ar-src was also a camping trip"),  # plain text, no bracket citation
        actor="test", reason="seed", timestamp=TS2,
    )
    result = attribute_references("mem-ar-mention", run_id=ledgers["run_id"], memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"])
    assert result.status == STATUS_REFERENCES_NOT_ESTABLISHED
