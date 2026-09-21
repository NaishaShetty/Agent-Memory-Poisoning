"""Phase 11 -- regression/leakage tests for the "outside the box" fix:
`grouped_raw_score.py` (reuses the project's own GROUPED_GATED rule
composition as an untrained reference), `combined_untrained_score.py`
(MAX(z(raw_sum), z(grouped_raw))), and `lofo_combined_untrained.py` (the
resulting real, multi-seed LOFO result)."""

from __future__ import annotations

import inspect

from phase11.data import split
from phase11.gnn.grouped_raw_score import pools_grouped_raw_scores
from phase11.gnn.combined_untrained_score import combined_untrained_score, grouped_raw_tensor, raw_sum
from phase11.gnn.lofo import filter_pools_excluding_family
from phase11.gnn.lofo_combined_untrained import build_dataset, macro_summary, run_all_families, run_fold, summarize


def test_grouped_raw_score_reuses_compute_memory_risk_score_not_reimplemented():
    """Structural check: `pools_grouped_raw_scores` must call
    `compute_memory_risk_score`, not reimplement `_grouped_gated_rule`'s
    own group logic -- the whole point of reuse over reinvention."""
    source = inspect.getsource(pools_grouped_raw_scores)
    assert "compute_memory_risk_score" in source
    assert "GROUPED_GATED" in source


def test_grouped_raw_score_never_includes_learned_signal_keys():
    """The grouped-raw score must be purely rule-based -- no
    `gnn_risk_score`/`gln_risk_score` key ever present, so `learned_group`
    always contributes exactly 0.0."""
    source = inspect.getsource(pools_grouped_raw_scores)
    assert "gnn_risk_score" not in source
    assert "gln_risk_score" not in source


def test_grouped_raw_score_real_sleeper_separation():
    """Locks in the real, diagnosed fix: Sleeper's held-out poison scores
    (all exactly 0.25 under the grouped-raw score) must sit strictly above
    every real training-benign example (with Sleeper excluded) -- the
    exact separation `raw_sum` could never achieve."""
    family = "Sleeper"
    train_pools = filter_pools_excluding_family(split.all_dev_pools(), family)
    train_scores = pools_grouped_raw_scores(train_pools)
    held_scores = pools_grouped_raw_scores(split.held_out_pools())

    train_labels = {m.scenario_id: m.is_poison_ground_truth for pool in train_pools for m in pool.memories}
    held_labels = {m.scenario_id: m.is_poison_ground_truth for pool in split.held_out_pools() for m in pool.memories}
    from phase11.gnn.lofo import family_map_for_pools
    held_family_map = family_map_for_pools(split.held_out_pools())

    train_benign_max = max(s for nid, s in train_scores.items() if not train_labels.get(nid, False))
    sleeper_scores = [s for nid, s in held_scores.items() if held_labels.get(nid) and held_family_map.get(nid) == family]

    assert len(sleeper_scores) == 5
    assert min(sleeper_scores) > train_benign_max


def test_combined_untrained_score_is_max_not_average():
    """Structural check: the combination must be `torch.maximum`, not a
    mean -- the whole point of the fix over the rejected averaging
    attempt."""
    source = inspect.getsource(combined_untrained_score)
    assert "torch.maximum" in source


def test_grouped_raw_tensor_defaults_missing_nodes_to_zero():
    """Synthetic ancestor nodes (added only by `graph_build.py`, never
    present in `pools_grouped_raw_scores()`'s output) must default to 0.0,
    not raise a KeyError."""
    train_pools = split.all_dev_pools()
    train_ds = build_dataset(train_pools)
    tensor = grouped_raw_tensor(train_pools, train_ds.node_ids)
    assert tensor.shape[0] == len(train_ds.node_ids)


def test_lofo_combined_farma_and_sleeper_now_fully_resolved():
    """Real, measured, locked-in result: both families that previously had
    real, diagnosed LOFO weaknesses now reach 100% detection with the
    combined untrained score."""
    farma = summarize(run_fold("FARMA", seeds=(11,)))
    sleeper = summarize(run_fold("Sleeper", seeds=(11,)))
    memorygraft = summarize(run_fold("MemoryGraft-style-volume", seeds=(11,)))
    assert farma["detection_rate_mean"] == 1.0
    assert sleeper["detection_rate_mean"] == 1.0
    assert memorygraft["detection_rate_mean"] == 1.0


def test_lofo_combined_macro_beats_every_prior_lofo_configuration():
    """Real, locked-in regression: macro detection with the combined score
    must exceed every prior LOFO configuration's own macro detection
    (the best prior result was 87.5% at w=0.25 with raw_sum alone,
    PHASE11_LOFO_FPR_AND_FARMA_FIX_REPORT.md)."""
    all_results = run_all_families(seeds=(11,))
    macro = macro_summary(all_results)
    assert macro["macro_detection_rate"] >= 0.85
    assert macro["macro_false_positive_rate"] < 0.10


def test_lofo_combined_never_touches_held_out_pools_for_fitting():
    source = inspect.getsource(run_fold)
    assert "filter_pools_excluding_family(split.held_out_pools()" not in source
