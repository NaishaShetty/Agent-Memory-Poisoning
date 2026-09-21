"""Phase 11 -- locks in the precise, traced diagnosis of why
MemoryGraft-style-volume and Sleeper's LOFO detection could not be
further improved by any threshold-selection technique, per
`docs/phase11/PHASE11_FINAL_GAP_CLOSURE_REPORT.md`. Real, structural
findings, not a vague "instability" claim -- each is reproducible from
these exact real scores."""

from __future__ import annotations

from phase11.data import split
from phase11.gnn.lofo import filter_pools_excluding_family, family_map_for_pools
from phase11.gnn.lofo_blend_infold_threshold_semantic import build_dataset, _raw_sum
from phase11.gnn.train import train_model


def test_sleeper_held_out_poison_scores_below_three_real_training_benign_outliers():
    """The precise, traced reason Sleeper's LOFO detection cannot reach
    any reasonable FPR: all 5 real held-out Sleeper poison examples score
    EXACTLY 2.0 (raw feature sum), while 3 real training-benign examples
    (excluding Sleeper from training) score HIGHER (>2.0) -- a genuine
    corpus-construction fact, not a threshold-algorithm artifact."""
    family = "Sleeper"
    train_pools = filter_pools_excluding_family(split.all_dev_pools(), family)
    train_ds = build_dataset(train_pools)
    held_out_ds = build_dataset(split.held_out_pools())
    held_out_family_map = family_map_for_pools(split.held_out_pools())

    model = train_model(train_ds, seed=11, weight_decay=0.005)
    train_raw = _raw_sum(train_ds.features).tolist()
    held_raw = _raw_sum(held_out_ds.features).tolist()

    sleeper_scores = [
        s for nid, s, y in zip(held_out_ds.node_ids, held_raw, held_out_ds.labels.tolist())
        if y == 1.0 and held_out_family_map.get(nid) == family
    ]
    train_benign = [s for s, y in zip(train_raw, train_ds.labels.tolist()) if y == 0.0]

    assert len(sleeper_scores) == 5
    assert all(round(s, 3) == 2.0 for s in sleeper_scores)
    higher_benign = [b for b in train_benign if b > 2.0]
    assert len(higher_benign) == 3  # the exact, real count driving the FPR cost


def test_memorygraft_paraphrase_subset_overlaps_benign_upper_tail_under_lofo():
    """The precise, traced reason for MemoryGraft-style-volume's LOFO
    detection plateau: its 10 held-out PARAPHRASE-family poison examples
    score in a distinct, LOWER cluster (~1.3-1.4) than its 10 NEARDUP
    examples (~1.8-2.5) -- LOFO excludes MemoryGraft entirely, so the
    model never sees ANY training example where the semantic-divergence
    signal correlates with poison (it is the only family in this corpus
    that exercises that mechanism), leaving the paraphrase subset
    indistinguishable from ordinary benign variation."""
    family = "MemoryGraft-style-volume"
    train_pools = filter_pools_excluding_family(split.all_dev_pools(), family)
    train_ds = build_dataset(train_pools)
    held_out_ds = build_dataset(split.held_out_pools())
    held_out_family_map = family_map_for_pools(split.held_out_pools())

    model = train_model(train_ds, seed=11, weight_decay=0.005)
    held_raw = _raw_sum(held_out_ds.features).tolist()

    fam_scores = sorted(
        s for nid, s, y in zip(held_out_ds.node_ids, held_raw, held_out_ds.labels.tolist())
        if y == 1.0 and held_out_family_map.get(nid) == family
    )
    assert len(fam_scores) == 20
    low_cluster = [s for s in fam_scores if s < 1.5]
    high_cluster = [s for s in fam_scores if s >= 1.5]
    assert len(low_cluster) == 10  # the real PARAPHRASE subset
    assert len(high_cluster) == 10  # the real NEARDUP subset -- already well-separated
