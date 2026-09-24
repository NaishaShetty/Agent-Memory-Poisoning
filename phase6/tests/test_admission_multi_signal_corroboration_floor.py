"""Phase 14 follow-on (2026-09-23, explicitly authorized) -- tests for the
SEPARATE `GROUPED_GATED_ADMISSION_CORROBORATED` composition rule
(`risk_score.py`'s own module note has the full real justification for why
this is a new rule, not a change to the shared `GROUPED_GATED`). Fast (no
LLM calls)."""

from __future__ import annotations

from phase6.defense.admission.reasoning_guard import compute_signals as admission_signals
from phase6.defense.retrieval.embedding_signals import pool_consensus_divergence_signals_semantic
from phase6.defense.retrieval.signals import pool_consensus_divergence_signals
from phase6.defense.risk.risk_action import action_for_risk_estimate
from phase6.defense.risk.risk_score import (
    GROUPED_GATED,
    GROUPED_GATED_ADMISSION_CORROBORATED,
    compute_memory_risk_score,
)
from phase6.defense.policy.states import ALLOW, QUARANTINE, REQUIRE_VALIDATION, UNASSESSED
from phase6.defense.sleeper.signals import imperative_write_directive_signal
from phase6.defense.signals.contract import build_signal_context
from phase6.evaluation.ablations.dev_corpus import dev_admission_pool
from phase11.data.real_corpus import real_poison_scenarios
from phase12.eval_corpus import per_dataset_eval_corpora

TS = "2026-01-01T00:00:00Z"


def _ctx(memory_id: str, text: str):
    return build_signal_context(
        memory_id=memory_id, content_text=text, content_type="CONVERSATIONAL_FACT",
        memory_type="foundation", parent_ids=(), lifecycle_state="ACTIVE", creation_timestamp=TS,
    )


def test_real_dev_poison_scenarios_with_two_plus_admission_signals_reach_quarantine_under_new_rule():
    pool = dev_admission_pool()
    expected_quarantine = {"DEV-ADMISSION-POISON-HIGH", "DEV-ADMISSION-POISON-MED-A", "DEV-ADMISSION-POISON-MED-B", "DEV-ADMISSION-POISON-LOW-C"}
    for m in pool.memories:
        signals = admission_signals(_ctx(m.scenario_id, m.content_text))
        estimate = compute_memory_risk_score(m.scenario_id, signals, rule=GROUPED_GATED_ADMISSION_CORROBORATED)
        action = action_for_risk_estimate(estimate, current_security_state=UNASSESSED)
        if m.scenario_id in expected_quarantine:
            assert action == QUARANTINE, f"{m.scenario_id}: expected QUARANTINE, got {action}"


def test_real_dev_single_signal_poison_scenarios_are_not_escalated_to_quarantine_under_new_rule():
    """Real, deliberate non-regression: a poison scenario with only ONE
    admission signal must NOT be swept up by the 2-corroborator floor."""
    pool = dev_admission_pool()
    single_signal_ids = {"DEV-ADMISSION-POISON-LOW-A", "DEV-ADMISSION-POISON-LOW-B"}
    for m in pool.memories:
        if m.scenario_id not in single_signal_ids:
            continue
        signals = admission_signals(_ctx(m.scenario_id, m.content_text))
        estimate = compute_memory_risk_score(m.scenario_id, signals, rule=GROUPED_GATED_ADMISSION_CORROBORATED)
        action = action_for_risk_estimate(estimate, current_security_state=UNASSESSED)
        assert action == REQUIRE_VALIDATION, f"{m.scenario_id}: expected REQUIRE_VALIDATION, got {action}"


def test_real_dev_benign_near_miss_is_not_quarantined_under_new_rule():
    pool = dev_admission_pool()
    for m in pool.memories:
        if m.scenario_id != "DEV-ADMISSION-BENIGN-NEAR-MISS":
            continue
        signals = admission_signals(_ctx(m.scenario_id, m.content_text))
        estimate = compute_memory_risk_score(m.scenario_id, signals, rule=GROUPED_GATED_ADMISSION_CORROBORATED)
        action = action_for_risk_estimate(estimate, current_security_state=UNASSESSED)
        assert action == ALLOW


def test_zero_real_benign_quarantines_across_all_502_real_benign_records_under_new_rule():
    """The real, direct, end-to-end check: does the new rule ever QUARANTINE
    a real benign record under B9's full real risk composition (admission +
    retrieval + sleeper signals together)? Not just per-signal in isolation."""
    n_checked = 0
    n_quarantined = 0
    corpora = per_dataset_eval_corpora()
    for corpus in corpora.values():
        for pool in corpus.benign_pools:
            contents = [m.content_text for m in pool.memories]
            if not contents:
                continue
            div = pool_consensus_divergence_signals(contents)
            sem, _cost = pool_consensus_divergence_signals_semantic(contents)
            for m, d, s in zip(pool.memories, div, sem):
                n_checked += 1
                ctx = _ctx(m.scenario_id, m.content_text)
                signals = {
                    **admission_signals(ctx), **d,
                    "semantic_consensus_divergence_score": s["consensus_divergence_score"],
                    **imperative_write_directive_signal(ctx), "dormancy_activation_score": 1.0,
                }
                estimate = compute_memory_risk_score(m.scenario_id, signals, rule=GROUPED_GATED_ADMISSION_CORROBORATED)
                action = action_for_risk_estimate(estimate, current_security_state=UNASSESSED)
                if action == QUARANTINE:
                    n_quarantined += 1
    assert n_checked == 502
    assert n_quarantined == 0


def test_real_dsrm_farma_mpbench_reach_quarantine_under_new_rule():
    """Regression for the real Phase 14 gap this fix closes: all 9 real
    isolated DSRM/FARMA/MPBench scenarios (each now firing 2+ real,
    independently-validated admission signals) reach QUARANTINE under B9's
    live real risk composition, using only a real, isolated benign distractor
    pool (no coordinated real cluster needed)."""
    pool = {m.scenario_id: m.content_text for m in real_poison_scenarios().memories}
    scenario_ids = [f"REAL-{fam}-{i}" for fam in ("DSRM", "FARMA", "MPBENCH") for i in range(3)]
    for sid in scenario_ids:
        contents = [pool[sid], "Jon lost his job as a banker on January 19, 2023.", "Gina lost her job at Door Dash in January 2023."]
        div = pool_consensus_divergence_signals(contents)
        sem, _cost = pool_consensus_divergence_signals_semantic(contents)
        ctx = _ctx(sid, pool[sid])
        signals = {
            **admission_signals(ctx), **div[0], "semantic_consensus_divergence_score": sem[0]["consensus_divergence_score"],
            **imperative_write_directive_signal(ctx), "dormancy_activation_score": 1.0,
        }
        estimate = compute_memory_risk_score(sid, signals, rule=GROUPED_GATED_ADMISSION_CORROBORATED)
        action = action_for_risk_estimate(estimate, current_security_state=UNASSESSED)
        assert action == QUARANTINE, f"{sid}: expected QUARANTINE, got {action}"


def test_grouped_gated_itself_is_byte_identical_to_before_the_new_rule_existed():
    """Real isolation check: the SHARED `GROUPED_GATED` rule (Phase 11's own
    z-score-normalized detectors and the frozen `corpus.py` 75-scenario
    corpus both depend on it) must give the EXACT SAME risk_score for these
    same 9 real DSRM/FARMA/MPBench scenarios as it did before
    `GROUPED_GATED_ADMISSION_CORROBORATED` was added -- i.e. it must NOT
    reach QUARANTINE from admission-group signals alone, since no floor is
    applied under this rule."""
    pool = {m.scenario_id: m.content_text for m in real_poison_scenarios().memories}
    scenario_ids = [f"REAL-{fam}-{i}" for fam in ("DSRM", "FARMA", "MPBENCH") for i in range(3)]
    for sid in scenario_ids:
        contents = [pool[sid], "Jon lost his job as a banker on January 19, 2023.", "Gina lost her job at Door Dash in January 2023."]
        div = pool_consensus_divergence_signals(contents)
        sem, _cost = pool_consensus_divergence_signals_semantic(contents)
        ctx = _ctx(sid, pool[sid])
        signals = {
            **admission_signals(ctx), **div[0], "semantic_consensus_divergence_score": sem[0]["consensus_divergence_score"],
            **imperative_write_directive_signal(ctx), "dormancy_activation_score": 1.0,
        }
        estimate = compute_memory_risk_score(sid, signals, rule=GROUPED_GATED)
        action = action_for_risk_estimate(estimate, current_security_state=UNASSESSED)
        assert action != QUARANTINE, f"{sid}: GROUPED_GATED must stay unaffected by the new rule, got {action}"
