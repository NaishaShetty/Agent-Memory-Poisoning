"""Phase 5.4 (fix, issue 3) -- tests proving all 7 frozen Phase 4 attacks are wired to
the shared Phase 5 injection instrumentation, using each attack's REAL, unmodified result
dataclass (imported directly from its own frozen module) -- never a stand-in fake shape.
"""

from __future__ import annotations

import pytest

from phase4.attacks.agentpoison.injector import AgentPoisonInjectionResult
from phase4.attacks.agentpoison.injector import ADMISSION_ADMITTED as AP_ADMITTED, ADMISSION_REJECTED as AP_REJECTED
from phase4.attacks.dsrm.injector import DSRMInjectionResult
from phase4.attacks.dsrm.injector import ADMISSION_ADMITTED as DSRM_ADMITTED
from phase4.attacks.farma.injector import FARMAInjectionResult
from phase4.attacks.farma.injector import ADMISSION_ADMITTED as FARMA_ADMITTED, ADMISSION_REJECTED as FARMA_REJECTED
from phase4.attacks.memorygraft.adapter import (
    ADMISSION_ADMITTED as MG_ADMITTED,
    ADMISSION_NOT_ADMITTED as MG_NOT_ADMITTED,
    MemoryGraftInjectionResult,
)
from phase4.attacks.memorygraft.persistence_gate import DECISION_DISCARD, DECISION_KEEP, PersistenceJudgment
from phase4.attacks.minja.injector import StepInjectionResult
from phase4.attacks.minja.injector import ADMISSION_ADMITTED as MINJA_ADMITTED
from phase4.attacks.mpbench.injector import MPBenchInjectionResult
from phase4.attacks.mpbench.injector import ADMISSION_ADMITTED as MPBENCH_ADMITTED
from phase4.attacks.sleeper_memory_poisoning.injection_gate import DECISION_KEEP as SLEEPER_DECISION_KEEP, InjectionJudgment
from phase4.attacks.sleeper_memory_poisoning.injector import SleeperInjectionResult
from phase4.attacks.sleeper_memory_poisoning.injector import ADMISSION_ADMITTED as SLEEPER_ADMITTED

from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger

from phase5.identity.run_identity import EventRunMembershipLedger, ExperimentRunLedger, ExperimentRunRecord
from phase5.schema.event_ledger import Phase5EventLedger
from phase5.wiring.attack_integration import (
    NORMALIZERS,
    build_attack_canonical_memory_record,
    instrument_attack_injection,
    instrument_attack_memory_lifecycle,
    normalize_agentpoison_injection,
    normalize_dsrm_injection,
    normalize_farma_injection,
    normalize_memorygraft_injection,
    normalize_minja_injection,
    normalize_mpbench_injection,
    normalize_sleeper_injection,
)

TS = "2026-09-12T00:00:00+00:00"


@pytest.fixture
def ledgers(tmp_path):
    memory_ledger = CanonicalMemoryLedger(tmp_path / "memory")
    event_ledger = CanonicalEventLedger(tmp_path / "events", memory_ledger)
    run_ledger = ExperimentRunLedger(tmp_path / "runs")
    membership_ledger = EventRunMembershipLedger(tmp_path / "membership", run_ledger)
    phase5_ledger = Phase5EventLedger(tmp_path / "phase5_events")
    run = ExperimentRunRecord(
        experiment_id="phase4-integration-test", run_id="RUN-integration", dataset="locomo",
        scope={}, started_at=TS, actor="test", reason="integration test run",
    )
    run_ledger.register(run)
    return dict(
        memory_ledger=memory_ledger, event_ledger=event_ledger,
        membership_ledger=membership_ledger, phase5_ledger=phase5_ledger, run_id=run.run_id,
    )


# ---------------------------------------------------------------------------
# Normalizer-level tests: one admitted case per attack, using each attack's real result
# dataclass and real admission-status constant.
# ---------------------------------------------------------------------------

def test_normalize_agentpoison():
    result = AgentPoisonInjectionResult(poison_id="p1", admission_status=AP_ADMITTED, attacker_originated=True, canonical_memory_id="mem-1", stored_text="x")
    n = normalize_agentpoison_injection(result)
    assert (n.attack_id, n.artifact_id, n.admission_status, n.memory_id) == ("agentpoison", "p1", AP_ADMITTED, "mem-1")


def test_normalize_dsrm():
    result = DSRMInjectionResult(artifact_id="a1", admission_status=DSRM_ADMITTED, attacker_originated=True, canonical_memory_id="mem-2", stored_text="x", variant="v1")
    n = normalize_dsrm_injection(result)
    assert (n.attack_id, n.artifact_id, n.admission_status, n.memory_id) == ("dsrm", "a1", DSRM_ADMITTED, "mem-2")


def test_normalize_farma():
    result = FARMAInjectionResult(artifact_id="a2", admission_status=FARMA_ADMITTED, attacker_originated=True, canonical_memory_id="mem-3", stored_text="x", precedent_count=2)
    n = normalize_farma_injection(result)
    assert (n.attack_id, n.artifact_id, n.admission_status, n.memory_id) == ("farma", "a2", FARMA_ADMITTED, "mem-3")


def test_normalize_minja():
    result = StepInjectionResult(step_id="s1", admission_status=MINJA_ADMITTED, attacker_originated=True, canonical_memory_id="mem-4", stored_text="x")
    n = normalize_minja_injection(result)
    assert (n.attack_id, n.artifact_id, n.admission_status, n.memory_id) == ("minja", "s1", MINJA_ADMITTED, "mem-4")


def test_normalize_mpbench():
    result = MPBenchInjectionResult(scenario_id="sc1", admission_status=MPBENCH_ADMITTED, attacker_originated=True, canonical_memory_id="mem-5", stored_text="x")
    n = normalize_mpbench_injection(result)
    assert (n.attack_id, n.artifact_id, n.admission_status, n.memory_id) == ("mpbench", "sc1", MPBENCH_ADMITTED, "mem-5")


def test_normalize_sleeper():
    judgment = InjectionJudgment(artifact_id="ar1", decision=SLEEPER_DECISION_KEEP, rationale="r", raw_response_text="raw")
    result = SleeperInjectionResult(artifact_id="ar1", admission_status=SLEEPER_ADMITTED, attacker_originated=True, canonical_memory_id="mem-6", judgment=judgment, stored_text="x")
    n = normalize_sleeper_injection(result)
    assert (n.attack_id, n.artifact_id, n.admission_status, n.memory_id) == ("sleeper_memory_poisoning", "ar1", SLEEPER_ADMITTED, "mem-6")


def test_normalize_memorygraft_admitted():
    judgment = PersistenceJudgment(artifact_id="mg1", decision=DECISION_KEEP, rationale="r", foundation="mem0", raw_response_text="raw", gate_config_fingerprint="CFG-x", latency_sec=0.1)
    result = MemoryGraftInjectionResult(artifact_id="mg1", judgment=judgment, admission_status=MG_ADMITTED, attacker_originated=True, canonical_memory_id="mem-7", foundation_field_note=None)
    n = normalize_memorygraft_injection(result)
    assert (n.attack_id, n.artifact_id, n.admission_status, n.memory_id) == ("memorygraft", "mg1", MG_ADMITTED, "mem-7")


def test_normalize_memorygraft_not_admitted_third_admission_value_passes_through():
    """MemoryGraft's genuine third admission outcome -- confirms it is passed through
    verbatim, never coerced into ADMITTED/REJECTED."""
    judgment = PersistenceJudgment(artifact_id="mg2", decision=DECISION_DISCARD, rationale="discarded", foundation="mem0", raw_response_text="raw", gate_config_fingerprint="CFG-x", latency_sec=0.1)
    result = MemoryGraftInjectionResult(artifact_id="mg2", judgment=judgment, admission_status=MG_NOT_ADMITTED, attacker_originated=True, canonical_memory_id=None, foundation_field_note=None)
    n = normalize_memorygraft_injection(result)
    assert n.admission_status == MG_NOT_ADMITTED
    assert n.memory_id is None


# ---------------------------------------------------------------------------
# End-to-end: instrument_attack_injection() for all 7, via the shared dispatcher, proving
# each attack reaches the SAME recording path (record_attack_injection()).
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("attack_id", sorted(NORMALIZERS))
def test_all_seven_attacks_are_registered(attack_id):
    assert attack_id in NORMALIZERS
    assert callable(NORMALIZERS[attack_id])


def test_instrument_attack_injection_end_to_end_farma_admitted(ledgers):
    result = FARMAInjectionResult(artifact_id="farma-e2e", admission_status=FARMA_ADMITTED, attacker_originated=True, canonical_memory_id="mem-e2e", stored_text="x", precedent_count=1)
    event = instrument_attack_injection(
        "farma", result,
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], actor="farma_campaign", reason="artifact admitted", timestamp=TS,
    )
    assert event.attack_id == "farma"
    assert event.artifact_id == "farma-e2e"
    assert event.memory_id == "mem-e2e"
    assert ledgers["phase5_ledger"].exists(event.event_id)
    assert ledgers["membership_ledger"].run_for_event(event.event_id).run_id == ledgers["run_id"]
    # injection_id was minted automatically and deterministically
    assert event.injection_id is not None
    assert event.injection_id.startswith("P5INJ-")


def test_instrument_attack_injection_end_to_end_farma_rejected(ledgers):
    result = FARMAInjectionResult(artifact_id="farma-rejected", admission_status=FARMA_REJECTED, attacker_originated=True, canonical_memory_id=None, stored_text="x", precedent_count=0)
    event = instrument_attack_injection(
        "farma", result,
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], actor="farma_campaign", reason="artifact rejected", timestamp=TS,
    )
    assert event.admission_status == FARMA_REJECTED
    assert event.memory_id is None
    assert ledgers["phase5_ledger"].exists(event.event_id)


def test_instrument_attack_injection_unregistered_attack_id_raises(ledgers):
    with pytest.raises(KeyError, match="not registered in NORMALIZERS"):
        instrument_attack_injection(
            "some_future_eighth_attack", object(),
            phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
            run_id=ledgers["run_id"], actor="test", reason="test", timestamp=TS,
        )


def test_generate_injection_id_deterministic_across_repeated_calls(ledgers):
    result = AgentPoisonInjectionResult(poison_id="p-repeat", admission_status=AP_ADMITTED, attacker_originated=True, canonical_memory_id="mem-repeat", stored_text="x")
    event1 = instrument_attack_injection(
        "agentpoison", result,
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], actor="test", reason="admitted", timestamp=TS,
    )
    event2 = instrument_attack_injection(
        "agentpoison", result,
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], actor="test", reason="admitted", timestamp=TS,
    )
    assert event1.injection_id == event2.injection_id
    assert event1.event_id == event2.event_id  # idempotent re-instrumentation of the identical fact


# ---------------------------------------------------------------------------
# Full chain (issue 2): injection -> admission -> memory creation -> created event, for
# every attack whose content is resolvable, using instrument_attack_memory_lifecycle().
# ---------------------------------------------------------------------------

def _assert_full_chain(ledgers, lifecycle_result, expected_attack_id, expected_memory_id):
    assert lifecycle_result.injection_event.attack_id == expected_attack_id
    assert lifecycle_result.injection_event.memory_id == expected_memory_id
    assert ledgers["phase5_ledger"].exists(lifecycle_result.injection_event.event_id)
    assert lifecycle_result.memory_creation is not None
    created_event = lifecycle_result.memory_creation.created_event
    assert created_event.event_type == "created"
    assert created_event.memory_ids == (expected_memory_id,)
    assert ledgers["memory_ledger"].exists(expected_memory_id)
    # The full chain is reconstructable purely from returned/persisted identifiers:
    # injection_event.memory_id == created_event's own memory_id == the ledger record.
    assert ledgers["membership_ledger"].run_for_event(created_event.event_id).run_id == ledgers["run_id"]
    assert ledgers["membership_ledger"].run_for_event(lifecycle_result.injection_event.event_id).run_id == ledgers["run_id"]


def test_full_chain_agentpoison(ledgers):
    result = AgentPoisonInjectionResult(poison_id="p-chain", admission_status=AP_ADMITTED, attacker_originated=True, canonical_memory_id="mem-chain-ap", stored_text="malicious demonstration text")
    r = instrument_attack_memory_lifecycle(
        "agentpoison", result,
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], actor="test", reason="admitted", timestamp=TS,
    )
    _assert_full_chain(ledgers, r, "agentpoison", "mem-chain-ap")
    stored = ledgers["memory_ledger"].get("mem-chain-ap")
    assert stored.content["text"] == "malicious demonstration text"
    assert stored.source["attacker_originated"] is True
    assert stored.source["attack_id"] == "agentpoison"


def test_full_chain_dsrm(ledgers):
    result = DSRMInjectionResult(artifact_id="a-chain", admission_status=DSRM_ADMITTED, attacker_originated=True, canonical_memory_id="mem-chain-dsrm", stored_text="x", variant="v1")
    r = instrument_attack_memory_lifecycle(
        "dsrm", result,
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], actor="test", reason="admitted", timestamp=TS,
    )
    _assert_full_chain(ledgers, r, "dsrm", "mem-chain-dsrm")


def test_full_chain_farma(ledgers):
    result = FARMAInjectionResult(artifact_id="a-chain-2", admission_status=FARMA_ADMITTED, attacker_originated=True, canonical_memory_id="mem-chain-farma", stored_text="x", precedent_count=1)
    r = instrument_attack_memory_lifecycle(
        "farma", result,
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], actor="test", reason="admitted", timestamp=TS,
    )
    _assert_full_chain(ledgers, r, "farma", "mem-chain-farma")


def test_full_chain_minja(ledgers):
    result = StepInjectionResult(step_id="s-chain", admission_status=MINJA_ADMITTED, attacker_originated=True, canonical_memory_id="mem-chain-minja", stored_text="x")
    r = instrument_attack_memory_lifecycle(
        "minja", result,
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], actor="test", reason="admitted", timestamp=TS,
    )
    _assert_full_chain(ledgers, r, "minja", "mem-chain-minja")


def test_full_chain_mpbench(ledgers):
    result = MPBenchInjectionResult(scenario_id="sc-chain", admission_status=MPBENCH_ADMITTED, attacker_originated=True, canonical_memory_id="mem-chain-mpbench", stored_text="x")
    r = instrument_attack_memory_lifecycle(
        "mpbench", result,
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], actor="test", reason="admitted", timestamp=TS,
    )
    _assert_full_chain(ledgers, r, "mpbench", "mem-chain-mpbench")


def test_full_chain_sleeper(ledgers):
    judgment = InjectionJudgment(artifact_id="ar-chain", decision=SLEEPER_DECISION_KEEP, rationale="r", raw_response_text="raw")
    result = SleeperInjectionResult(artifact_id="ar-chain", admission_status=SLEEPER_ADMITTED, attacker_originated=True, canonical_memory_id="mem-chain-sleeper", judgment=judgment, stored_text="x")
    r = instrument_attack_memory_lifecycle(
        "sleeper_memory_poisoning", result,
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], actor="test", reason="admitted", timestamp=TS,
    )
    _assert_full_chain(ledgers, r, "sleeper_memory_poisoning", "mem-chain-sleeper")


def test_full_chain_memorygraft_requires_stored_text_override(ledgers):
    """MemoryGraft's own result carries no stored_text -- proves the function refuses to
    silently skip memory-creation wiring, then succeeds once given the real content the
    frozen injector actually wrote (artifact.resp, per the module docstring's audit)."""
    judgment = PersistenceJudgment(artifact_id="mg-chain", decision=DECISION_KEEP, rationale="r", foundation="mem0", raw_response_text="raw", gate_config_fingerprint="CFG-x", latency_sec=0.1)
    result = MemoryGraftInjectionResult(artifact_id="mg-chain", judgment=judgment, admission_status=MG_ADMITTED, attacker_originated=True, canonical_memory_id="mem-chain-mg", foundation_field_note=None)

    with pytest.raises(ValueError, match="no resolvable stored_text"):
        instrument_attack_memory_lifecycle(
            "memorygraft", result,
            memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
            phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
            run_id=ledgers["run_id"], actor="test", reason="admitted", timestamp=TS,
        )

    r = instrument_attack_memory_lifecycle(
        "memorygraft", result,
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], actor="test", reason="admitted", timestamp=TS,
        stored_text_override="the real artifact.resp content",
    )
    _assert_full_chain(ledgers, r, "memorygraft", "mem-chain-mg")
    assert ledgers["memory_ledger"].get("mem-chain-mg").content["text"] == "the real artifact.resp content"


def test_rejected_and_not_admitted_never_produce_memory_creation(ledgers):
    farma_rejected = FARMAInjectionResult(artifact_id="a-rej", admission_status=FARMA_REJECTED, attacker_originated=True, canonical_memory_id=None, stored_text="x", precedent_count=0)
    r1 = instrument_attack_memory_lifecycle(
        "farma", farma_rejected,
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], actor="test", reason="rejected", timestamp=TS,
    )
    assert r1.memory_creation is None
    assert r1.injection_event.memory_id is None

    judgment = PersistenceJudgment(artifact_id="mg-discard", decision=DECISION_DISCARD, rationale="discarded", foundation="mem0", raw_response_text="raw", gate_config_fingerprint="CFG-x", latency_sec=0.1)
    mg_not_admitted = MemoryGraftInjectionResult(artifact_id="mg-discard", judgment=judgment, admission_status=MG_NOT_ADMITTED, attacker_originated=True, canonical_memory_id=None, foundation_field_note="gate returned DISCARD")
    r2 = instrument_attack_memory_lifecycle(
        "memorygraft", mg_not_admitted,
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], actor="test", reason="discarded", timestamp=TS,
    )
    assert r2.memory_creation is None
    assert r2.injection_event.admission_status == MG_NOT_ADMITTED


def test_build_attack_canonical_memory_record_requires_memory_id():
    from phase5.wiring.attack_integration import NormalizedInjection
    normalized = NormalizedInjection("farma", "artifact-x", FARMA_REJECTED, None, "x")
    with pytest.raises(ValueError, match="requires normalized.memory_id"):
        build_attack_canonical_memory_record(normalized, stored_text="x", creation_timestamp=TS)
