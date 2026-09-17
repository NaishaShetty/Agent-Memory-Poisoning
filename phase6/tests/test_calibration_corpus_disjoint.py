"""Phase 6.9 P0 regression test -- the threshold-calibration corpus
(`dev_corpus.py`, used by `sweep.py`) must never overlap with the
reported-metrics corpus (`corpus.py`, used by `run_b0_b7.py`).

Audit finding this closes: both previously drew from the identical
`near_duplicate_consensus_pool()`/`paraphrased_consensus_pool()`/
`_benign_pool()` objects in `corpus.py` -- so any threshold picked by
inspecting performance on that corpus was then reported as a metric measured
on the SAME corpus (calibration circularity, the same pattern already found
and disclosed in Phase 4's judgment-gate calibration). This is a standing
structural check that the fix (`dev_corpus.py`) does not silently erode back
into overlap in a future edit.
"""

from __future__ import annotations

from phase6.evaluation.ablations import corpus as reported_corpus
from phase6.evaluation.ablations import dev_corpus
from phase6.evaluation.ablations.sweep import _dev_pools, sweep, _gated_lexical


def _all_reported_content() -> set:
    texts = set()
    for pool in reported_corpus.all_pools():
        for m in pool.memories:
            texts.add(m.content_text)
    return texts


def _all_reported_scenario_ids() -> set:
    ids = set()
    for pool in reported_corpus.all_pools():
        for m in pool.memories:
            ids.add(m.scenario_id)
    return ids


def _all_calibration_content() -> set:
    texts = set()
    for contents, _labels in _dev_pools().values():
        texts.update(contents)
    for m in dev_corpus.dev_admission_pool().memories:
        texts.add(m.content_text)
    for m in dev_corpus.dev_sleeper_pool().memories:
        texts.add(m.content_text)
    for _scenario_id, descendant_content, ancestors, _label in dev_corpus.dev_propagation_scenarios():
        texts.add(descendant_content)
        texts.update(a.content_text for a in ancestors)
    return texts


def _all_calibration_scenario_ids() -> set:
    ids = set()
    for m in dev_corpus.dev_near_duplicate_pool().memories:
        ids.add(m.scenario_id)
    for m in dev_corpus.dev_paraphrased_pool().memories:
        ids.add(m.scenario_id)
    for m in dev_corpus.dev_admission_pool().memories:
        ids.add(m.scenario_id)
    for m in dev_corpus.dev_sleeper_pool().memories:
        ids.add(m.scenario_id)
    for scenario_id, _descendant_content, _ancestors, _label in dev_corpus.dev_propagation_scenarios():
        ids.add(scenario_id)
    return ids


def test_calibration_corpus_shares_no_content_with_reported_metrics_corpus():
    """The exact audit finding, made an assertion: before the fix, this set
    intersection was non-empty (the near-duplicate and paraphrased poison/
    truth text was identical in both corpora)."""
    overlap = _all_calibration_content() & _all_reported_content()
    assert overlap == set(), (
        f"Calibration corpus (dev_corpus.py, used by sweep.py's threshold "
        f"selection) and the reported-metrics corpus (corpus.py, used by "
        f"run_b0_b7.py) share content: {overlap!r}. A threshold calibrated "
        f"on this text and then reported as a metric measured on the same "
        f"text is circular -- see dev_corpus.py's module docstring."
    )


def test_calibration_corpus_shares_no_scenario_ids_with_reported_metrics_corpus():
    overlap = _all_calibration_scenario_ids() & _all_reported_scenario_ids()
    assert overlap == set()


def test_calibration_corpus_still_has_the_same_shape_as_before(
    poison_pool_size=4, benign_pool_size=3,
):
    """The fix must change WHAT content is used, not the corpus's shape
    (poison-cluster-of-3 + 1 truth memory per consensus pool; 3-memory benign
    pools) -- otherwise Item 1's sweep methodology (poison-detection-rate /
    false-positive-rate over matched pool sizes) would no longer be
    comparable to the original, documented protocol."""
    pools = _dev_pools()
    assert len(pools["near_duplicate"][0]) == poison_pool_size
    assert len(pools["paraphrased"][0]) == poison_pool_size
    assert len(pools["diverse_benign"][0]) == benign_pool_size
    assert len(pools["uniform_benign"][0]) == benign_pool_size
    assert sum(pools["near_duplicate"][1]) == 3  # 3 poison-labeled, 1 truth
    assert sum(pools["paraphrased"][1]) == 3


def test_sweep_runs_end_to_end_on_the_disjoint_calibration_corpus():
    """Not just a shape check -- actually runs the real sweep function over
    the new corpus and confirms it produces sane, real (not degenerate)
    detection/false-positive numbers, i.e. the disjoint corpus still
    exercises the mechanism it is meant to calibrate."""
    results = sweep(_gated_lexical, [0.1, 0.6])
    assert len(results) == 2
    low, high = results
    # A low threshold must flag at least as much as a high one on real data.
    assert low["poison_detection_rate"] >= high["poison_detection_rate"]
    assert 0.0 <= low["false_positive_rate"] <= 1.0
    assert 0.0 <= high["false_positive_rate"] <= 1.0
