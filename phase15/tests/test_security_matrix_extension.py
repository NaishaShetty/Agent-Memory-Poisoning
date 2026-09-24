"""Phase 15 -- tests for the B9/B10 security-matrix reshape. Real (uses the
real per-dataset corpus and real signal computation, no LLM calls)."""

from __future__ import annotations

from phase6.defense.risk.risk_score import GROUPED_GATED, GROUPED_GATED_RETRIEVAL_CORROBORATED
from phase12.eval_corpus import (
    DATASET_CONVERSATION_CHRONICLES,
    DATASET_LOCOMO,
    DATASET_LONGMEMEVAL,
    DATASET_MSC,
    per_dataset_eval_corpora,
)
from phase15.security_matrix_extension import CONFIG_NAME_B9, b10_corpus_level_result, b9_matrix_cells


def test_b9_matrix_cells_covers_all_four_real_datasets():
    cells = b9_matrix_cells()
    dataset_names = {c.dataset_name for c in cells}
    assert dataset_names == {DATASET_LOCOMO, DATASET_LONGMEMEVAL, DATASET_MSC, DATASET_CONVERSATION_CHRONICLES}
    for cell in cells:
        assert cell.config_name == CONFIG_NAME_B9
        assert 0.0 <= cell.metrics.poison_detection_rate <= 1.0
        assert 0.0 <= cell.metrics.benign_false_positive_rate <= 1.0
        assert cell.metrics.n_poison == 15


def test_b9_matrix_cells_match_the_frozen_run_b9_risk_composed_function_directly():
    """Real, direct cross-check: this reshape must use the SAME real
    mechanism `run_b9_risk_composed()` already provides, not a
    reimplementation -- confirmed by calling it directly with the same real
    pools and rule and comparing."""
    from phase6.evaluation.ablations.run_b0_b7 import run_b9_risk_composed

    corpora = per_dataset_eval_corpora()
    cells = b9_matrix_cells(corpora)
    for cell in cells:
        expected_metrics, _ = run_b9_risk_composed(
            pools=corpora[cell.dataset_name].pools, rule=GROUPED_GATED_RETRIEVAL_CORROBORATED,
        )
        assert cell.metrics == expected_metrics


def test_real_sleeper_family_detection_fixed_on_phase12_own_real_corpus():
    """Real regression for the Sleeper-detection finding (Section 3.4 of the
    Phase 15 report): B9 must now detect the real Sleeper-family scenario on
    every real dataset, matching B8's own real 100% on the same content --
    confirmed directly, not merely argued from the signal-registration diff."""
    for cell in b9_matrix_cells():
        assert cell.metrics.per_attack_family_detection["sleeper_memory_poisoning"] == 1.0


def test_real_longmemeval_false_positive_rate_fixed_with_no_detection_cost():
    """Real regression for the LongMemEval FPR finding (Section 3.3): the
    fixed rule must bring FPR to 0.0% on LongMemEval while NOT reducing
    detection anywhere, confirmed directly against the SAME real corpus
    computed under the unfixed `GROUPED_GATED` rule."""
    corpora = per_dataset_eval_corpora()
    fixed = {c.dataset_name: c for c in b9_matrix_cells(corpora, rule=GROUPED_GATED_RETRIEVAL_CORROBORATED)}
    unfixed = {c.dataset_name: c for c in b9_matrix_cells(corpora, rule=GROUPED_GATED)}

    assert fixed[DATASET_LONGMEMEVAL].metrics.benign_false_positive_rate == 0.0
    assert unfixed[DATASET_LONGMEMEVAL].metrics.benign_false_positive_rate > 0.0  # the real bug this fixes

    for dataset_name in fixed:
        assert fixed[dataset_name].metrics.poison_detection_rate >= unfixed[dataset_name].metrics.poison_detection_rate
        assert fixed[dataset_name].metrics.benign_false_positive_rate <= unfixed[dataset_name].metrics.benign_false_positive_rate


def test_b10_corpus_level_result_is_real_and_not_decomposed_per_dataset():
    result = b10_corpus_level_result()
    assert result.config_name == "B10"
    assert 0.0 <= result.mean_detection <= 1.0
    assert 0.0 <= result.false_positive_rate <= 1.0
    assert "not decomposed" in result.scope_note.lower()
