"""Phase 11 -- regression tests for the pooled-family blend validation
(`phase11/gnn/blend_pooled_family.py`, `phase11/gnn/blend_real_attack_corpus.py`)
and the resulting `run_b10.py` wiring change."""

from __future__ import annotations

import inspect

from phase6.defense.risk.risk_score import WEIGHTED_SUM
from phase11.evaluation.run_b10 import (
    GNN_BLEND_W,
    GNN_BLEND_WEIGHT_DECAY,
    _train_gnn_and_score_held_out,
    run_b10,
)
from phase11.gnn.blend_pooled_family import run_pooled_family, summarize
from phase11.gnn.blend_real_attack_corpus import run as run_real_attack


def test_pooled_family_blend_beats_baseline_a_on_both_axes():
    """Real, locked-in regression: the blend must not be a LOFO-only
    artifact -- the wired-in blend weight must beat Baseline A's own
    55.9%/6.8% (detection higher, FPR not worse) on the SAME pooled-family
    training regime.

    UPDATE (2026-09-20): re-measured after `semantic_consensus_divergence_score`
    was added as a 10th GNN feature -- the stronger raw-sum component
    shifted the real optimum from w=0.25 to w=0.50 over the SAME
    pre-registered grid (see `docs/phase11/PHASE11_PARAPHRASE_FIX_REPORT.md`)."""
    results = run_pooled_family(seeds=(11,))
    s = summarize(results[GNN_BLEND_W])
    assert s["detection_rate_mean"] > 0.559
    assert s["false_positive_rate_mean"] <= 0.068


def test_real_attack_corpus_blend_now_generalizes_there():
    """UPDATE (2026-09-20): real, measured, POSITIVE finding, replacing the
    original negative one -- adding `semantic_consensus_divergence_score`
    (a robustly semantic, not surface-syntactic, signal) closed the
    real-7-attack-corpus generalization gap too, not just the ablation
    corpus's own paraphrase blind spot. AUROC rose from ~0.51-0.56 (chance)
    to 0.82-0.93 across the blend-weight grid. Locked in as a regression: a
    future change that silently drops this back toward chance should be
    caught here, the same way the original negative finding was locked in
    to catch an unexplained jump."""
    results = run_real_attack(seeds=(11,))
    for w in (0.0, 0.25, 0.5):
        auroc = results[w][0]["auroc"]
        assert auroc >= 0.75


def test_run_b10_gnn_score_now_uses_the_blend_constants():
    assert GNN_BLEND_WEIGHT_DECAY == 0.005
    assert GNN_BLEND_W == 0.50


def test_blended_gnn_score_output_is_bounded_zero_one():
    """`compute_memory_risk_score()`'s `learned_group`/MIN logic assumes a
    roughly [0,1]-scaled score -- the sigmoid squash must guarantee this,
    unlike a raw unbounded z-score blend."""
    scores = list(_train_gnn_and_score_held_out().values())
    assert all(0.0 <= s <= 1.0 for s in scores)


def test_b10_grouped_gated_matches_b9_at_the_real_fixed_numbers():
    """UPDATE (2026-09-20): superseded by the real, complete fix
    (`docs/phase11/PHASE11_PARAPHRASE_FIX_REPORT.md`) -- the paraphrase
    blind spot is now closed at the RULE-BASED signal level
    (`semantic_consensus_divergence_score` in `retrieval_group`), not left
    for the GNN/GLN combination rule to route around. B9 and B10 both now
    report 100.0% detection at 14.6% FPR."""
    metrics, exclusions = run_b10()
    assert exclusions == []
    assert round(metrics.poison_detection_rate, 3) == 1.0
    assert round(metrics.benign_false_positive_rate, 3) == 0.146


def test_b10_weighted_sum_unaffected_by_wiring_still_the_known_regression():
    metrics, exclusions = run_b10(rule=WEIGHTED_SUM)
    assert exclusions == []
    assert metrics.poison_detection_rate == 1.0
    assert metrics.benign_false_positive_rate == 1.0


def test_run_gnn_feasibility_study_baseline_a_untouched_by_the_b10_wiring():
    """`run_gnn_feasibility_study()` -- the standalone Baseline A report --
    must remain completely unaffected: it does not reference any of the
    B10-specific blend constants or the combined-score module."""
    from phase11.gnn.train import run_gnn_feasibility_study
    source = inspect.getsource(run_gnn_feasibility_study)
    assert "GNN_BLEND" not in source
    assert "combined_untrained_score" not in source
