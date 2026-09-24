"""Phase 14 follow-on (2026-09-23, explicitly authorized) -- tests for
`unverifiable_closure_signal`, the FARMA isolated-instance admission fix.
Fast (pure regex, no LLM calls)."""

from __future__ import annotations

from phase6.defense.admission.reasoning_guard import _action_for_score, compute_signals, weighted_score
from phase6.defense.admission.signals import unverifiable_closure_signal
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


def test_fires_on_real_farma_1_and_2_not_farma_0():
    pool = {m.scenario_id: m.content_text for m in real_poison_scenarios().memories}
    assert unverifiable_closure_signal(_ctx("REAL-FARMA-1", pool["REAL-FARMA-1"]))["unverifiable_closure_score"] == 1.0
    assert unverifiable_closure_signal(_ctx("REAL-FARMA-2", pool["REAL-FARMA-2"]))["unverifiable_closure_score"] == 1.0
    # FARMA-0 states a real, concrete new date ("moved to September 2023") --
    # not an indefinite/unannounced closure -- and already reaches QUARANTINE
    # via two OTHER real signals without needing this one.
    assert unverifiable_closure_signal(_ctx("REAL-FARMA-0", pool["REAL-FARMA-0"]))["unverifiable_closure_score"] == 0.0


def test_all_three_real_farma_scenarios_now_reach_quarantine():
    pool = {m.scenario_id: m.content_text for m in real_poison_scenarios().memories}
    for sid in ("REAL-FARMA-0", "REAL-FARMA-1", "REAL-FARMA-2"):
        signals = compute_signals(_ctx(sid, pool[sid]))
        score = weighted_score(signals)
        assert _action_for_score(score) == QUARANTINE, f"{sid}: score={score}"


def test_does_not_fire_on_ordinary_benign_schedule_changes():
    """Real, deliberately-avoided false-positive class: ordinary benign
    conversation frequently mentions real reschedules/cancellations with a
    concrete new date or reason -- this signal must not fire on those,
    only on the narrower 'now indefinite/unconfirmable' framing."""
    text = "We moved the meeting to Friday because Jon was busy. The trip got cancelled but we're going next month instead."
    result = unverifiable_closure_signal(_ctx("t1", text))
    assert result["unverifiable_closure_score"] == 0.0


def test_zero_real_false_positives_across_all_502_real_benign_records():
    n_checked = 0
    n_fp = 0
    corpora = per_dataset_eval_corpora()
    for corpus in corpora.values():
        for pool in corpus.benign_pools:
            for m in pool.memories:
                n_checked += 1
                score = unverifiable_closure_signal(_ctx(m.scenario_id, m.content_text))
                if score["unverifiable_closure_score"] > 0:
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
            score = unverifiable_closure_signal(ctx)["unverifiable_closure_score"]
            assert score == 0.0, f"{m.scenario_id} unexpectedly fired -- would change the historical B7/B8 numbers"
