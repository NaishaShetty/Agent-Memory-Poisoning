"""Phase 9, Stage 9.4 -- real, multi-attack validation of the FULL backward walk.

Runs `reconstruct_attack_origin()` against real Phase 4 attack data produced by each
attack's own real, frozen `Injector` class (via the same real Stage 5.4
`run_live_*_injection()` helpers -- or, where a second real product from the SAME
attack is needed, the same real injector classes called directly against a second real,
frozen artifact already checked into that attack's own module) -- never hand-built
`AttributionResult`s or synthetic evidence.

Acceptance bar (Phase 9 plan Section 4.4):
  - Attacks with one clean origin (Sleeper, AgentPoison, MPBench-PCFI, DSRM, MINJA):
    reconstruction reaches SINGLE_ORIGIN_HIGH_CONFIDENCE and names the real planted
    artifact's own memory id.
  - Attacks whose real mechanism can produce multiple plausible originating memories
    BY DESIGN (FARMA's amplification cluster, MemoryGraft's volume-style repetition):
    reconstruction reports MULTIPLE_PLAUSIBLE_ORIGINS, naming every real candidate --
    never collapsed to one arbitrary pick.
  - A genuinely benign flagged decision: reconstruction reaches NO_ATTACK_ORIGIN_FOUND.
"""

from __future__ import annotations

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
from phase3.evaluation.foundations.mocks.mock_mem0 import MockMem0Adapter

from phase4.attacks.farma.injector import FARMAInjector
from phase4.attacks.farma.reasoning_trace import SEED_CAMPING, SEED_CHARITY_RACE
from phase4.attacks.memorygraft.adapter import MemoryGraftInjector
from phase4.attacks.memorygraft.locomo_seed import SEED_RESEARCH_TOPIC
from phase4.attacks.memorygraft.persistence_gate import PoisonedExperienceArtifact

from phase5.identity.run_identity import EventRunMembershipLedger, ExperimentRunLedger, ExperimentRunRecord
from phase5.schema.event_ledger import Phase5EventLedger
from phase5.wiring.agent_decision_instrumentation import FINISH_REASON_GENERATED, USED_MEMORIES_NOT_OBSERVABLE, record_agent_decision
from phase5.wiring.attack_integration import instrument_attack_memory_lifecycle
from phase5.wiring.live_attack_runs import (
    _generation_config,
    _scripted_llm_provider,
    run_live_agentpoison_injection,
    run_live_dsrm_injection,
    run_live_farma_injection,
    run_live_memorygraft_injection,
    run_live_minja_injection,
    run_live_mpbench_injection,
    run_live_sleeper_injection,
)
from phase5.wiring.memory_lifecycle import record_memory_creation, record_memory_derivation

from attribution.wiring.forensics import (
    CHAIN_MULTIPLE_PLAUSIBLE_ORIGINS,
    CHAIN_NO_ATTACK_ORIGIN_FOUND,
    CHAIN_SINGLE_ORIGIN_HIGH_CONFIDENCE,
    reconstruct_attack_origin,
)

TS = "2026-09-17T00:00:00+00:00"
TS2 = "2026-09-17T00:01:00+00:00"
TS3 = "2026-09-17T00:02:00+00:00"
CFG = "CFG-phase9-validation"


def _make_ledgers(tmp_path, run_id="RUN-phase9-validation"):
    memory_ledger = CanonicalMemoryLedger(tmp_path / "memory")
    event_ledger = CanonicalEventLedger(tmp_path / "events", memory_ledger)
    supersession_ledger = SupersessionLedger(tmp_path / "supersessions")
    run_ledger = ExperimentRunLedger(tmp_path / "runs")
    membership_ledger = EventRunMembershipLedger(tmp_path / "membership", run_ledger)
    phase5_ledger = Phase5EventLedger(tmp_path / "phase5_events")
    run = ExperimentRunRecord(
        experiment_id="exp-phase9-validation", run_id=run_id, dataset="locomo",
        scope={}, started_at=TS, actor="test", reason="phase 9 stage 9.4 validation run",
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


def _reconstruct(ledgers, decision_id):
    return reconstruct_attack_origin(
        "DECISION", decision_id, run_id=ledgers["run_id"],
        event_ledger=ledgers["event_ledger"], phase5_event_ledger=ledgers["phase5_ledger"],
    )


# ---------------------------------------------------------------------------
# Clean single-origin attacks -- AgentPoison, DSRM, MPBench-PCFI, Sleeper
# ---------------------------------------------------------------------------

CLEAN_ORIGIN_RUNNERS = [
    (run_live_agentpoison_injection, "agentpoison"),
    (run_live_dsrm_injection, "dsrm"),
    (run_live_mpbench_injection, "mpbench"),
    (run_live_sleeper_injection, "sleeper_memory_poisoning"),
]


@pytest.mark.parametrize("runner,expected_attack_id", CLEAN_ORIGIN_RUNNERS, ids=[a for _, a in CLEAN_ORIGIN_RUNNERS])
def test_clean_single_origin_attack_reconstructs_with_high_confidence(ledgers, runner, expected_attack_id):
    result = runner(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], timestamp=TS,
    )
    memory_id = result.memory_creation.created_event.memory_ids[0]
    decision = _record_decision(ledgers, f"dec-{expected_attack_id}", f"task-{expected_attack_id}", (memory_id,))

    reconstruction = _reconstruct(ledgers, decision.decision_id)

    assert reconstruction.chain_confidence == CHAIN_SINGLE_ORIGIN_HIGH_CONFIDENCE
    assert reconstruction.per_memory_origin[memory_id].attack_id == expected_attack_id
    assert reconstruction.per_memory_origin[memory_id].source_id == result.injection_event.injection_id


# ---------------------------------------------------------------------------
# MINJA -- one clean origin per step; each step's real memory reconstructs cleanly
# when investigated as its own incident.
# ---------------------------------------------------------------------------

def test_minja_each_real_step_memory_reconstructs_with_high_confidence(ledgers):
    step_results = run_live_minja_injection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], timestamp=TS,
    )
    assert len(step_results) == 3  # MINJA's own real 3-step query sequence

    for i, step_result in enumerate(step_results):
        memory_id = step_result.memory_creation.created_event.memory_ids[0]
        decision = _record_decision(ledgers, f"dec-minja-{i}", f"task-minja-{i}", (memory_id,), timestamp=TS2)

        reconstruction = _reconstruct(ledgers, decision.decision_id)

        assert reconstruction.chain_confidence == CHAIN_SINGLE_ORIGIN_HIGH_CONFIDENCE
        assert reconstruction.per_memory_origin[memory_id].attack_id == "minja"


# ---------------------------------------------------------------------------
# FARMA -- real amplification-style convergence: two of FARMA's own real, frozen
# seed artifacts, merge-derived into one downstream memory -> MULTIPLE_PLAUSIBLE_ORIGINS,
# naming both real candidates.
# ---------------------------------------------------------------------------

def test_farma_amplification_style_merge_reports_multiple_plausible_origins(ledgers):
    camping_result = run_live_farma_injection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], timestamp=TS,
    )
    camping_memory_id = camping_result.memory_creation.created_event.memory_ids[0]

    foundation = MockMem0Adapter()
    foundation.initialize({})
    charity_race_result_raw = FARMAInjector(foundation).inject(SEED_CHARITY_RACE)  # FARMA's own second real seed
    charity_race_result = instrument_attack_memory_lifecycle(
        "farma", charity_race_result_raw,
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], actor="phase9_validation:farma", reason="second real FARMA seed for amplification-style convergence test",
        timestamp=TS,
    )
    charity_race_memory_id = charity_race_result.memory_creation.created_event.memory_ids[0]
    assert camping_memory_id != charity_race_memory_id

    merged_child = CanonicalMemoryRecord(
        memory_id="mem-farma-amplified-convergence", memory_type=MEMORY_TYPE_DERIVED,
        content={"text": "an amplification-style entry drawing on both prior FARMA seeds"},
        source={"source_type": SOURCE_TYPE_DERIVATION_EVENT}, parent_ids=(camping_memory_id, charity_race_memory_id),
        creation_event="derivation-of-mem-farma-amplified-convergence", creation_timestamp=TS2, lifecycle_state=LIFECYCLE_CREATED,
    )
    record_memory_derivation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        derived_record=merged_child, source_memory_ids=(camping_memory_id, charity_race_memory_id),
        actor="test", reason="amplification-style convergence of two real FARMA seeds", timestamp=TS2,
    )
    decision = _record_decision(ledgers, "dec-farma-amplified", "task-farma-amplified", (merged_child.memory_id,), timestamp=TS3)

    reconstruction = _reconstruct(ledgers, decision.decision_id)

    assert reconstruction.chain_confidence == CHAIN_MULTIPLE_PLAUSIBLE_ORIGINS
    lineage = reconstruction.per_memory_lineage[merged_child.memory_id]
    assert set(lineage.candidate_source_ids) == {camping_memory_id, charity_race_memory_id}
    assert reconstruction.per_memory_origin[camping_memory_id].attack_id == "farma"
    assert reconstruction.per_memory_origin[charity_race_memory_id].attack_id == "farma"


# ---------------------------------------------------------------------------
# MemoryGraft -- real volume-style repetition: the default real artifact plus a
# second, real LoCoMo-reformulated MemoryGraft artifact, merge-derived ->
# MULTIPLE_PLAUSIBLE_ORIGINS, naming both real candidates.
# ---------------------------------------------------------------------------

def test_memorygraft_volume_style_merge_reports_multiple_plausible_origins(ledgers):
    first_result = run_live_memorygraft_injection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], timestamp=TS,
    )
    first_memory_id = first_result.memory_creation.created_event.memory_ids[0]

    foundation = MockMem0Adapter()
    foundation.initialize({})
    gate_reply = "DECISION: KEEP\nRATIONALE: Looks like a valid task note."
    injector = MemoryGraftInjector(
        foundation_adapter=foundation, foundation_label="mem0",
        llm_provider=_scripted_llm_provider([gate_reply]), generation_config=_generation_config(),
    )
    second_result_raw = injector.inject(SEED_RESEARCH_TOPIC)  # MemoryGraft's own second real, frozen artifact
    second_result = instrument_attack_memory_lifecycle(
        "memorygraft", second_result_raw,
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], actor="phase9_validation:memorygraft",
        reason="second real MemoryGraft artifact for volume-style repetition test",
        timestamp=TS, stored_text_override=SEED_RESEARCH_TOPIC.resp,
    )
    second_memory_id = second_result.memory_creation.created_event.memory_ids[0]
    assert first_memory_id != second_memory_id

    merged_child = CanonicalMemoryRecord(
        memory_id="mem-memorygraft-volume-convergence", memory_type=MEMORY_TYPE_DERIVED,
        content={"text": "a summary note drawing on both prior forged task experiences"},
        source={"source_type": SOURCE_TYPE_DERIVATION_EVENT}, parent_ids=(first_memory_id, second_memory_id),
        creation_event="derivation-of-mem-memorygraft-volume-convergence", creation_timestamp=TS2, lifecycle_state=LIFECYCLE_CREATED,
    )
    record_memory_derivation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        derived_record=merged_child, source_memory_ids=(first_memory_id, second_memory_id),
        actor="test", reason="volume-style convergence of two real MemoryGraft artifacts", timestamp=TS2,
    )
    decision = _record_decision(ledgers, "dec-memorygraft-volume", "task-memorygraft-volume", (merged_child.memory_id,), timestamp=TS3)

    reconstruction = _reconstruct(ledgers, decision.decision_id)

    assert reconstruction.chain_confidence == CHAIN_MULTIPLE_PLAUSIBLE_ORIGINS
    lineage = reconstruction.per_memory_lineage[merged_child.memory_id]
    assert set(lineage.candidate_source_ids) == {first_memory_id, second_memory_id}
    assert reconstruction.per_memory_origin[first_memory_id].attack_id == "memorygraft"
    assert reconstruction.per_memory_origin[second_memory_id].attack_id == "memorygraft"


# ---------------------------------------------------------------------------
# Genuinely benign decision -- no attack anywhere in the chain
# ---------------------------------------------------------------------------

def test_genuinely_benign_decision_reports_no_attack_origin_found(ledgers):
    benign = CanonicalMemoryRecord(
        memory_id="mem-phase9-benign", memory_type="foundation",
        content={"text": "a real, ordinary conversational fact with no attack involvement"},
        source={"source_type": SOURCE_TYPE_PHASE2_UMR}, parent_ids=(),
        creation_event="creation-of-mem-phase9-benign", creation_timestamp=TS, lifecycle_state=LIFECYCLE_CREATED,
    )
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        record=benign, actor="test", reason="seed", timestamp=TS,
    )
    decision = _record_decision(ledgers, "dec-phase9-benign", "task-phase9-benign", (benign.memory_id,))

    reconstruction = _reconstruct(ledgers, decision.decision_id)

    assert reconstruction.chain_confidence == CHAIN_NO_ATTACK_ORIGIN_FOUND
    assert reconstruction.per_memory_origin[benign.memory_id].status == "NO_ATTACK_ORIGIN"
