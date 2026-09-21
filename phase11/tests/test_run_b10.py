"""Phase 11.5 -- B10 runs end to end against the real held-out corpus and
reports real n, deterministically."""

from __future__ import annotations

from phase6.defense.risk.risk_score import WEIGHTED_SUM
from phase11.evaluation.run_b10 import run_b10


def test_b10_runs_end_to_end_with_real_n():
    metrics, exclusions = run_b10()
    assert metrics.n_poison > 0
    assert metrics.n_benign > 0
    assert 0.0 <= metrics.poison_detection_rate <= 1.0
    assert 0.0 <= metrics.benign_false_positive_rate <= 1.0


def test_b10_is_deterministic():
    first, _ = run_b10()
    second, _ = run_b10()
    assert first.poison_detection_rate == second.poison_detection_rate
    assert first.benign_false_positive_rate == second.benign_false_positive_rate


def test_b10_grouped_gated_default_now_matches_b9_real_numbers():
    """UPDATE (2026-09-17): locks in the real recovery from B10's original
    degenerate 100.0%/100.0% (WEIGHTED_SUM) to a real match with B8/B9 under
    the new default (GROUPED_GATED + a MIN-based learned_group + the GNN's
    own data-scale improvement) -- see hybrid.py's and risk_score.py's own
    Update notes for the full, real, measured account. Not an improvement
    over B9, a recovery to parity -- reported as such.

    UPDATE (2026-09-20, first pass): `run_b10.py`'s own
    `_train_gnn_and_score_held_out()` was changed to feed B10 a
    substantially better-calibrated GNN score (the LOFO-discovered raw-sum
    blend) -- independently verified to raise pooled-family GNN detection
    from 55.9% to 70.6% ON ITS OWN, but B10's own final number stayed at
    70.6%/7.3% because `PARAPHRASE-POISON-*` scored GLN exactly 0.0, and
    `_learned_group_score()`'s MIN gate erased any GNN contribution there
    regardless of how good the GNN's own score was.

    UPDATE (2026-09-20, second pass -- the real, complete fix): the root
    cause was closed at its source, not worked around at the composition
    level -- `run_b9_risk_composed()`/`run_b10.py` now also supply
    `semantic_consensus_divergence_score` (`_retrieval_group_score()`'s own
    Update note, `phase6/defense/risk/risk_score.py`), which correctly
    identifies `PARAPHRASE-POISON-*` as a coordinated cluster where the
    lexical signal could not. B9 itself now hits 100.0% detection at 14.6%
    FPR (up from 70.6%/7.3%), and B10 matches it exactly -- see
    `docs/phase11/PHASE11_PARAPHRASE_FIX_REPORT.md` for the full, real,
    traced account, including why the 14.6% FPR is a well-understood,
    already-accepted cost (every new false positive is a genuine "truth"
    memory sitting inside a coordinated poison pool, the SAME mechanism
    that already flagged the analogous NEARDUP-TRUTH-* memories under the
    lexical signal alone), not a new, unexplained regression."""
    metrics, exclusions = run_b10()  # default rule=GROUPED_GATED
    assert exclusions == []
    assert round(metrics.poison_detection_rate, 3) == 1.0
    assert round(metrics.benign_false_positive_rate, 3) == 0.146


def test_b10_weighted_sum_still_reproduces_the_original_disclosed_regression():
    """The original, disclosed WEIGHTED_SUM finding is preserved and remains
    reproducible on demand -- a real, historical negative result, not
    silently erased by the GROUPED_GATED fix becoming the new default."""
    metrics, exclusions = run_b10(rule=WEIGHTED_SUM)
    assert exclusions == []
    assert metrics.poison_detection_rate == 1.0
    assert metrics.benign_false_positive_rate == 1.0
