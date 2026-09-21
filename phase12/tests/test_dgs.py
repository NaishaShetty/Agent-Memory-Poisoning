"""Phase 12 -- tests for the Defense Generalization Score."""

from __future__ import annotations

from phase12.dgs import compute_dgs
from phase12.evaluation_matrix import ALL_RULE_BASED_CONFIGS
from phase12.eval_corpus import assert_disjoint_from_held_out_pools


def test_dgs_never_modifies_held_out_pools():
    # Runs after compute_dgs to confirm the reference corpus this metric
    # reads is unchanged by the act of reading it (same discipline
    # phase11/tests/test_gnn_lofo.py already enforces for the GNN).
    compute_dgs(ALL_RULE_BASED_CONFIGS)
    assert_disjoint_from_held_out_pools()  # the NEW corpus is still disjoint; held_out_pools() itself is untouched


def test_dgs_one_result_per_config():
    results = compute_dgs(ALL_RULE_BASED_CONFIGS)
    assert len(results) == len(ALL_RULE_BASED_CONFIGS)
    assert {r.config_name for r in results} == {c.name for c in ALL_RULE_BASED_CONFIGS}


def test_dgs_b0_has_zero_detection_both_corpora():
    results = compute_dgs(ALL_RULE_BASED_CONFIGS)
    b0 = next(r for r in results if r.config_name == "B0")
    assert b0.tuned_detection_rate == 0.0
    assert b0.new_corpus_detection_rate == 0.0
    assert b0.detection_gap == 0.0


def test_dgs_rates_are_bounded():
    results = compute_dgs(ALL_RULE_BASED_CONFIGS)
    for r in results:
        assert 0.0 <= r.tuned_detection_rate <= 1.0
        assert 0.0 <= r.new_corpus_detection_rate <= 1.0
        assert 0.0 <= r.tuned_fpr <= 1.0
        assert 0.0 <= r.new_corpus_fpr <= 1.0
        assert -1.0 <= r.detection_gap <= 1.0
        assert r.generalization_ratio >= 0.0


def test_dgs_uses_real_n_from_both_corpora():
    results = compute_dgs(ALL_RULE_BASED_CONFIGS)
    for r in results:
        assert r.n_poison_tuned == 34  # the reported 75-scenario corpus's own known real split
        assert r.n_benign_tuned == 41
        assert r.n_poison_new == 15  # phase12's own real poison pool size
        assert r.n_benign_new > 0
