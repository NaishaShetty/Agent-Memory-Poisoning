"""Phase 14 follow-on (2026-09-23, explicitly authorized) -- tests for
`preference_decision_update_signal`, the MPBench isolated-instance
admission fix. Fast (pure regex, no LLM calls)."""

from __future__ import annotations

from phase6.defense.admission.reasoning_guard import _action_for_score, compute_signals, weighted_score
from phase6.defense.admission.signals import preference_decision_update_signal
from phase6.defense.policy.states import QUARANTINE
from phase6.defense.signals.contract import build_signal_context
from phase11.data.real_corpus import real_poison_scenarios
from phase12.eval_corpus import per_dataset_eval_corpora

TS = "2026-01-01T00:00:00Z"


def _ctx(memory_id: str, text: str):
    return build_signal_context(
        memory_id=memory_id, content_text=text, content_type="CONVERSATIONAL_FACT",
        memory_type="foundation", parent_ids=(), lifecycle_state="ACTIVE", creation_timestamp=TS,
    )


def test_fires_on_all_three_real_mpbench_scenarios():
    pool = {m.scenario_id: m.content_text for m in real_poison_scenarios().memories}
    for sid in ("REAL-MPBENCH-0", "REAL-MPBENCH-1", "REAL-MPBENCH-2"):
        result = preference_decision_update_signal(_ctx(sid, pool[sid]))
        assert result["preference_decision_update_score"] == 1.0, f"{sid} should fire"


def test_all_three_real_mpbench_scenarios_now_reach_quarantine():
    pool = {m.scenario_id: m.content_text for m in real_poison_scenarios().memories}
    for sid in ("REAL-MPBENCH-0", "REAL-MPBENCH-1", "REAL-MPBENCH-2"):
        signals = compute_signals(_ctx(sid, pool[sid]))
        score = weighted_score(signals)
        assert _action_for_score(score) == QUARANTINE, f"{sid}: score={score}"


def test_fires_only_on_mpbench_across_the_real_15_scenario_corpus():
    pool = real_poison_scenarios().memories
    for m in pool:
        result = preference_decision_update_signal(_ctx(m.scenario_id, m.content_text))
        if result["preference_decision_update_score"] > 0:
            assert m.attack_family_ground_truth == "mpbench", f"unexpected fire on {m.scenario_id}"


def test_does_not_fire_on_a_plain_third_person_report_without_recency_wording():
    """Real, deliberately-avoided false-positive class: an ordinary
    third-person EVENT report (no preference/decision-update framing) must
    not fire -- only the base third_person_report_score should."""
    text = "Jon mentioned he lost his job as a banker yesterday."
    result = preference_decision_update_signal(_ctx("t1", text))
    assert result["preference_decision_update_score"] == 0.0


def test_fires_without_any_third_person_framing_confirming_genuine_independence():
    """Regression for the real revision this signal went through (see its own
    module comment): it must NOT require third_person_report_score's own
    opening pattern at all -- a first-person preference-change statement with
    recency wording must fire on its own."""
    text = "I've decided against psychology and I'm now leaning toward social work instead."
    result = preference_decision_update_signal(_ctx("t2", text))
    assert result["preference_decision_update_score"] == 1.0


def test_zero_real_false_positives_across_all_502_real_benign_records():
    n_checked = 0
    n_fp = 0
    corpora = per_dataset_eval_corpora()
    for corpus in corpora.values():
        for pool in corpus.benign_pools:
            for m in pool.memories:
                n_checked += 1
                score = preference_decision_update_signal(_ctx(m.scenario_id, m.content_text))
                if score["preference_decision_update_score"] > 0:
                    n_fp += 1
    assert n_checked == 502
    assert n_fp == 0


def test_zero_real_effect_on_the_frozen_75_scenario_corpus():
    from phase6.evaluation.ablations.corpus import all_pools

    for pool in all_pools():
        for m in pool.memories:
            ctx = build_signal_context(
                memory_id=m.scenario_id, content_text=m.content_text, content_type="CONVERSATIONAL_FACT",
                memory_type=m.memory_type, parent_ids=m.parent_ids, lifecycle_state="ACTIVE", creation_timestamp=TS,
            )
            score = preference_decision_update_signal(ctx)["preference_decision_update_score"]
            assert score == 0.0, f"{m.scenario_id} unexpectedly fired -- would change the historical B7/B8 numbers"
