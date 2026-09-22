"""Phase 12 generalization-gap follow-on (2026-09-21, explicitly authorized)
-- regression test for `real_attack_corpus_detector.run_with_tuned_comparison()`,
which extends Phase 12's DGS methodology to the learned GNN+grouped-raw
blend (previously scoped out of `phase12/dgs.py` as "a follow-on pass").
"""

from __future__ import annotations

from phase11.gnn.real_attack_corpus_detector import run_with_tuned_comparison, summarize_tuned_comparison


def test_tuned_vs_real_generalization_is_real_and_positive():
    results = run_with_tuned_comparison()
    summary = summarize_tuned_comparison(results)

    assert summary["n_poison_tuned"] == 34
    assert summary["n_poison_real"] == 24

    # Real, measured positive generalization: the blend detects MORE on
    # real content than on the corpus it was tuned against, at no FPR cost
    # (same threshold, same benign population it always used for FPR).
    assert summary["real_detection_rate_mean"] > summary["tuned_detection_rate_mean"]
    assert summary["generalization_ratio"] > 1.0
    assert round(summary["tuned_fpr_mean"], 3) == 0.091

    for family, rate in summary["real_per_family_detection_rate_mean"].items():
        assert rate >= 0.9, f"{family} detection dropped below 90%: {rate}"
