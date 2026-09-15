"""P2 fix (2026-09-14) -- unit tests for `campaign_formal_analysis.py`, the
module that computes this project's actual published McNemar
significance/p-values and per-condition aggregate metrics. The audit found
this module (and 10 siblings) had zero existing test coverage despite
computing headline statistics directly cited in
`PHASE3_3_G_FORMAL_CAMPAIGN_REPORT.md` and similar frozen reports -- exactly
where a silent off-by-one or aggregation bug would do the most damage.

`mcnemar_test()` is pure and file-I/O-free, so it is tested directly and
thoroughly below. `analyze()` reads real campaign result files from disk and
calls `build_formal_sample(120)` (an expensive, real dataset-sampling call) --
`test_analyze_aggregation_math` exercises it end-to-end against a small,
fully-controlled synthetic campaign fixture (monkeypatched file paths and a
monkeypatched `build_formal_sample`), verifying the aggregation arithmetic by
hand-computed expected values, not by re-reading the function's own output.
"""

from __future__ import annotations

import json

import pytest
import scipy.stats

from phase3.evaluation.agent_runtime import campaign_formal_analysis as cfa

# ---------------------------------------------------------------------------
# mcnemar_test() -- the pure statistical core
# ---------------------------------------------------------------------------


def test_mcnemar_no_discordant_pairs_is_maximally_non_significant():
    """b=c=0 (every pair concordant) -- zero evidence of a difference either
    way; must be the least significant possible result (p=1.0), not an
    error or an arbitrary default."""
    pairs = [(True, True), (True, True), (False, False)]
    result = cfa.mcnemar_test(pairs)
    assert result["discordant_b"] == 0
    assert result["discordant_c"] == 0
    assert result["p_value"] == 1.0
    assert result["effect_paired_difference"] == 0.0


def test_mcnemar_small_sample_uses_exact_binomial_test():
    """discordant < 25 must route through the exact binomial test, matching
    a hand-computed scipy.stats.binomtest call exactly -- not the
    chi-square approximation, which is unreliable at this scale (module
    docstring)."""
    # 8 pairs: condition 1 succeeds where 2 fails (b=6); condition 1 fails
    # where 2 succeeds (c=2). Discordant total = 8 < 25.
    pairs = [(True, False)] * 6 + [(False, True)] * 2 + [(True, True)] * 3
    result = cfa.mcnemar_test(pairs)
    assert result["discordant_b"] == 6
    assert result["discordant_c"] == 2
    assert result["exact_test_used"] is True
    expected_p = scipy.stats.binomtest(6, 8, 0.5, alternative="two-sided").pvalue
    assert result["p_value"] == pytest.approx(expected_p)
    assert result["statistic"] == 6.0


def test_mcnemar_large_sample_uses_continuity_corrected_chi_square():
    """discordant >= 25 must switch to the chi-square approximation, matching
    a hand-computed formula exactly: chi2 = (|b-c|-1)^2 / (b+c)."""
    b, c = 20, 10  # discordant = 30 >= 25
    pairs = [(True, False)] * b + [(False, True)] * c
    result = cfa.mcnemar_test(pairs)
    assert result["exact_test_used"] is False
    expected_chi2 = (abs(b - c) - 1) ** 2 / (b + c)
    expected_p = float(scipy.stats.chi2.sf(expected_chi2, df=1))
    assert result["statistic"] == pytest.approx(expected_chi2)
    assert result["p_value"] == pytest.approx(expected_p)


def test_mcnemar_boundary_at_exactly_25_discordant_uses_chi_square():
    """The module docstring's own stated boundary ('b + c >= 25') -- exactly
    25 discordant pairs must use the chi-square branch, not the exact one
    (an off-by-one here would silently switch which test is reported for
    borderline-sized real campaigns)."""
    b, c = 15, 10  # discordant = 25
    pairs = [(True, False)] * b + [(False, True)] * c
    result = cfa.mcnemar_test(pairs)
    assert result["discordant_b"] + result["discordant_c"] == 25
    assert result["exact_test_used"] is False


def test_mcnemar_boundary_at_24_discordant_uses_exact_test():
    b, c = 14, 10  # discordant = 24
    pairs = [(True, False)] * b + [(False, True)] * c
    result = cfa.mcnemar_test(pairs)
    assert result["discordant_b"] + result["discordant_c"] == 24
    assert result["exact_test_used"] is True


def test_mcnemar_proportions_and_effect_size_are_correct():
    # 10 pairs: cond1 success in 7, cond2 success in 4.
    pairs = [(True, True)] * 3 + [(True, False)] * 4 + [(False, True)] * 1 + [(False, False)] * 2
    result = cfa.mcnemar_test(pairs)
    assert result["n_pairs"] == 10
    assert result["proportion_1"] == pytest.approx(7 / 10)
    assert result["proportion_2"] == pytest.approx(4 / 10)
    assert result["effect_paired_difference"] == pytest.approx(0.3)


def test_mcnemar_empty_pairs_returns_none_proportions_not_a_crash():
    result = cfa.mcnemar_test([])
    assert result["n_pairs"] == 0
    assert result["proportion_1"] is None
    assert result["proportion_2"] is None
    assert result["effect_paired_difference"] is None
    assert result["p_value"] == 1.0  # zero discordant pairs by construction


def test_mcnemar_is_symmetric_under_swapping_conditions():
    """Swapping which condition is "1" and which is "2" must swap b/c and
    negate the effect size, but leave the p-value (a two-sided test)
    unchanged -- a real invariant of a correctly-implemented two-sided
    McNemar test."""
    pairs = [(True, False)] * 6 + [(False, True)] * 2 + [(True, True)] * 3
    swapped = [(o2, o1) for o1, o2 in pairs]
    result = cfa.mcnemar_test(pairs)
    swapped_result = cfa.mcnemar_test(swapped)
    assert swapped_result["discordant_b"] == result["discordant_c"]
    assert swapped_result["discordant_c"] == result["discordant_b"]
    assert swapped_result["p_value"] == pytest.approx(result["p_value"])
    assert swapped_result["effect_paired_difference"] == pytest.approx(-result["effect_paired_difference"])


# ---------------------------------------------------------------------------
# analyze() -- end-to-end aggregation math, against a small synthetic fixture
# ---------------------------------------------------------------------------


class _FakeTask:
    def __init__(self, task_id, evidence_memory_ids):
        self.task_id = task_id
        self.evidence_memory_ids = evidence_memory_ids


def _trace(task_id, dataset, correct, retrieved=(), selected=()):
    return {
        "record_id": task_id, "dataset": dataset,
        "failure_stage": "NONE" if correct else "ANSWER_MISMATCH",
        "evaluation_result": {"success_status": "ANSWER_CORRECT" if correct else "ANSWER_INCORRECT"},
        "retrieved_memories": list(retrieved), "selected_memories": list(selected),
    }


def test_analyze_aggregation_math(tmp_path, monkeypatch):
    """Two tasks, Conditions A and B only (C left empty), fully synthetic and
    hand-computed. Verifies analyze()'s own aggregation arithmetic --
    answer_correct_count, n, and the paired B-vs-A McNemar test -- against
    values computed independently here, not against the function's own
    output re-read."""
    results_path = tmp_path / "campaign_3_3g_formal_ab_result.json"
    c_locomo_path = tmp_path / "campaign_3_3g_formal_c_locomo_result.json"
    c_longmemeval_path = tmp_path / "campaign_3_3g1_formal_c_longmemeval_result.json"
    output_path = tmp_path / "analysis_output.json"

    # Task t1: A correct, B correct (concordant). Task t2: A incorrect, B
    # correct (discordant, B helped). _paired("A", "B", ...) builds pairs as
    # (A_correct, B_correct), so mcnemar_test's own convention (b = cond1
    # success/cond2 failure, c = cond1 failure/cond2 success) makes this a
    # `c` pair (A failure, B success), not a `b` pair -- by hand: b=0, c=1.
    # "dataset" must be present at the TOP level of each result dict (matching
    # the real production shape every real campaign runner writes, e.g.
    # campaign_v3_hybrid_runner.py's own results.append({"dataset": task.dataset, ...}))
    # -- _paired()'s own restrict_dataset filter reads r1.get("dataset")/r2.get("dataset")
    # at this top level, NOT trace["dataset"].
    campaign = {
        "results_a": [
            {"task_id": "t1", "dataset": "locomo", "status": "SUCCESSFUL_EVALUATION", "trace": _trace("t1", "locomo", True)},
            {"task_id": "t2", "dataset": "locomo", "status": "SUCCESSFUL_EVALUATION", "trace": _trace("t2", "locomo", False)},
        ],
        "results_b": [
            {"task_id": "t1", "dataset": "locomo", "status": "SUCCESSFUL_EVALUATION", "trace": _trace("t1", "locomo", True)},
            {"task_id": "t2", "dataset": "locomo", "status": "SUCCESSFUL_EVALUATION", "trace": _trace("t2", "locomo", True)},
        ],
    }
    results_path.write_text(json.dumps(campaign), encoding="utf-8")

    monkeypatch.setattr(cfa, "RESULTS_PATH", results_path)
    monkeypatch.setattr(cfa, "RESULTS_C_LOCOMO_PATH", c_locomo_path)
    monkeypatch.setattr(cfa, "RESULTS_C_LONGMEMEVAL_PATH", c_longmemeval_path)
    monkeypatch.setattr(cfa, "ANALYSIS_OUTPUT_PATH", output_path)
    monkeypatch.setattr(
        cfa, "build_formal_sample",
        lambda n: {"locomo": [_FakeTask("t1", ()), _FakeTask("t2", ())]},
    )

    summary = cfa.analyze()

    assert summary["execution_summary"]["A"]["successful"] == 2
    assert summary["execution_summary"]["B"]["successful"] == 2
    assert summary["aggregate"]["locomo"]["A"]["answer_correct_count"] == 1
    assert summary["aggregate"]["locomo"]["A"]["n"] == 2
    assert summary["aggregate"]["locomo"]["B"]["answer_correct_count"] == 2
    assert summary["aggregate"]["locomo"]["B"]["n"] == 2

    b_vs_a = summary["mcnemar_answer_correctness"]["B_vs_A"]["locomo"]
    assert b_vs_a["discordant_b"] == 0  # cond1(A)-pass, cond2(B)-fail
    assert b_vs_a["discordant_c"] == 1  # cond1(A)-fail, cond2(B)-pass
    assert b_vs_a["n_pairs"] == 2

    # The real disk write happened (into the monkeypatched, tmp_path-scoped
    # output_path) -- confirms analyze() didn't silently skip persistence.
    assert output_path.exists()
    on_disk = json.loads(output_path.read_text(encoding="utf-8"))
    assert on_disk["per_task_condition_rows_count"] == summary["per_task_condition_rows_count"]
