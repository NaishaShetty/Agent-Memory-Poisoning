"""Phase 14 follow-on (2026-09-23, explicitly authorized) -- tests for
`synthetic_repetition_padding_signal`, the DSRM isolated-instance admission
fix. Fast (pure regex, no LLM calls)."""

from __future__ import annotations

from phase6.defense.admission.reasoning_guard import _action_for_score, compute_signals, weighted_score
from phase6.defense.admission.signals import synthetic_repetition_padding_signal
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


def test_fires_on_real_dsrm_verbatim_repetition():
    pool = {m.scenario_id: m.content_text for m in real_poison_scenarios().memories}
    for sid in ("REAL-DSRM-0", "REAL-DSRM-1", "REAL-DSRM-2"):
        result = synthetic_repetition_padding_signal(_ctx(sid, pool[sid]))
        assert result["synthetic_repetition_padding_score"] == 1.0, f"{sid} should fire"


def test_all_three_real_dsrm_scenarios_now_reach_quarantine():
    """Regression for the real Phase 14 gap this signal closes: DSRM alone
    used to land at ALLOW_WITH_RESTRICTION (single-signal cap); with this
    real, independent second signal, it now reaches QUARANTINE."""
    pool = {m.scenario_id: m.content_text for m in real_poison_scenarios().memories}
    for sid in ("REAL-DSRM-0", "REAL-DSRM-1", "REAL-DSRM-2"):
        signals = compute_signals(_ctx(sid, pool[sid]))
        score = weighted_score(signals)
        assert _action_for_score(score) == QUARANTINE, f"{sid}: score={score}"


def test_fires_on_na_padding():
    result = synthetic_repetition_padding_signal(_ctx("t1", "Some real fact here. N/A N/A N/A"))
    assert result["synthetic_repetition_padding_score"] == 1.0


def test_does_not_fire_on_ordinary_benign_repetition_without_a_proper_noun():
    """Real, generic repeated instructional step (no named subject) --
    the real false positive this signal's own docstring discloses finding
    and fixing, kept as a permanent regression case."""
    text = (
        "**Rack installation:** Place the assembled rack onto the hitch adapter and secure it "
        "with the provided bolts or pins. Some other real content in between here to separate them. "
        "**Rack installation:** Place the assembled rack onto the hitch adapter and secure it "
        "with the provided bolts or pins."
    )
    result = synthetic_repetition_padding_signal(_ctx("t2", text))
    assert result["synthetic_repetition_padding_score"] == 0.0


def test_does_not_fire_on_a_single_non_repeated_sentence():
    result = synthetic_repetition_padding_signal(_ctx("t3", "Melanie signed up for her pottery class on 14 August 2023."))
    assert result["synthetic_repetition_padding_score"] == 0.0


def test_zero_real_false_positives_across_all_502_real_benign_records():
    """Slower (iterates all 502 real benign records across 4 real datasets)
    but no LLM/embedding calls -- pure regex, real, direct validation
    mirroring every other admission signal's own documented FP check."""
    n_checked = 0
    n_fp = 0
    corpora = per_dataset_eval_corpora()
    for corpus in corpora.values():
        for pool in corpus.benign_pools:
            for m in pool.memories:
                n_checked += 1
                score = synthetic_repetition_padding_signal(_ctx(m.scenario_id, m.content_text))
                if score["synthetic_repetition_padding_score"] > 0:
                    n_fp += 1
    assert n_checked == 502
    assert n_fp == 0


def test_zero_real_effect_on_the_frozen_75_scenario_corpus():
    """Regression: this signal must remain completely inert on corpus.py's
    75 real scenarios (poison or benign) -- the historically-reported
    B7/B8 70.6%/7.3% numbers must not shift."""
    from phase6.evaluation.ablations.corpus import all_pools

    for pool in all_pools():
        for m in pool.memories:
            ctx = build_signal_context(
                memory_id=m.scenario_id, content_text=m.content_text, content_type="CONVERSATIONAL_FACT",
                memory_type=m.memory_type, parent_ids=m.parent_ids, lifecycle_state="ACTIVE", creation_timestamp=TS,
            )
            score = synthetic_repetition_padding_signal(ctx)["synthetic_repetition_padding_score"]
            assert score == 0.0, f"{m.scenario_id} unexpectedly fired -- would change the historical B7/B8 numbers"
