"""Phase 10 plan Section 10.5 -- the real B9 "risk-composed" ablation vs B8's
already-reported 70.6%/7.3% baseline, on the SAME 75-scenario corpus
(`phase6/evaluation/ablations/corpus.py::all_pools()`).

HISTORICAL FINDING (as first shipped, `docs/phase10/PHASE10_REPORT.md`
Section 2): B9 (GROUPED_GATED risk composition + Stage 10.2's
action_for_risk_estimate) measured 47.1% poison detection at the SAME 7.3%
benign false-positive rate B8 achieves at 70.6% -- a genuine, disclosed
regression. Root cause, verified by direct computation: GROUPED_GATED's
per-guard-group equal weighting (`GROUP_WEIGHT = 0.25`) meant the strongest
possible single-guard-only evidence contributed at most 0.25 to the composed
score, so several real FARMA-family scenarios with an admission-guard
internal score of 0.4-0.5 (already enough to flag under
`reasoning_guard.py`'s own 0.15 threshold) fell below the OLD
`BAND_THRESHOLD_MODERATE` (0.15) once diluted to 0.10-0.125.

UPDATE (2026-09-17) -- THE NAMED FOLLOW-ON WAS ATTEMPTED AND WORKED
--------------------------------------------------------------------------------
`docs/phase10/PHASE10_REPORT.md` Section 5 named the real fix explicitly:
recalibrate `BAND_THRESHOLD_MODERATE` against `dev_corpus.py` (extended with
admission/propagation/sleeper-shaped fixtures, never the corpus this file
measures), never this reported corpus. That recalibration
(`phase6/evaluation/ablations/risk_sweep.py`, `BAND_THRESHOLD_MODERATE` now
0.05, was 0.15) was performed, found a real, non-circular improvement on the
disjoint dev corpus (detection 20.0%->93.3% with the SAME 25% false-positive
rate throughout that range -- every dev false positive already existed at
the old threshold), and was shipped BEFORE this file was ever re-run against
the reported corpus below -- the real result below was measured after the
fact, not tuned to produce it.

REAL, MEASURED RESULT: B9 NOW MATCHES B8 EXACTLY, NOT JUST "LESS OF A
REGRESSION"
--------------------------------------------------------------------------------
70.6% poison detection at 7.3% FPR -- identical to B8 on every real number,
including the per-family breakdown (FARMA and Sleeper both recovered to
100%; MemoryGraft-style-volume remains 50%, matching B8 exactly, unaffected
by this recalibration since its own real limitation -- FC-01's
majority-manipulation weakness -- is structural, not a threshold gap, per
`docs/phase6/PHASE6_RESULTS.md`'s own account). This is reported as an
honest match, not oversold as an improvement: B9 does not exceed B8's real
detection anywhere in this corpus; it recovers to parity. Whether a
risk-composed decision surface offers anything B8's simpler per-guard
max-severity rule does not (e.g. `RiskEstimate`'s continuous score and
richer `REQUIRE_VALIDATION` band structure vs B8's binary combined_action)
is a real, separate, still-open question this comparison does not answer
either way.
"""

from __future__ import annotations

from phase6.evaluation.ablations.run_b0_b7 import run_all, run_b9_risk_composed


def test_b9_real_measured_numbers_locked_in():
    metrics, exclusions = run_b9_risk_composed()
    assert exclusions == []  # every risk-driven action was a legal MGP transition
    assert metrics.n_poison == 34
    assert metrics.n_benign == 41
    assert round(metrics.poison_detection_rate, 3) == 0.706
    assert round(metrics.benign_false_positive_rate, 3) == 0.073


def test_b9_now_matches_b8_after_the_dev_corpus_recalibration():
    """UPDATE (2026-09-17): replaces the original `test_b9_underperforms_b8_
    on_detection_at_equal_fpr` -- after the real, non-circular
    `BAND_THRESHOLD_MODERATE` recalibration, B9 no longer underperforms B8;
    it matches it exactly on every real number. Locked in as a regression
    guard so a future accidental change to GROUPED_GATED's weighting or the
    band thresholds cannot silently regress this back without a human
    noticing and updating this test's own rationale."""
    b9_metrics, _ = run_b9_risk_composed()
    b8_metrics = next(m for m in run_all()[0] if m.config_name == "B8")

    assert round(b8_metrics.poison_detection_rate, 3) == 0.706
    assert round(b8_metrics.benign_false_positive_rate, 3) == 0.073
    assert b9_metrics.benign_false_positive_rate == b8_metrics.benign_false_positive_rate
    assert b9_metrics.poison_detection_rate == b8_metrics.poison_detection_rate
    assert b9_metrics.per_attack_family_detection == b8_metrics.per_attack_family_detection


def test_farma_detection_recovered_after_recalibration():
    """UPDATE (2026-09-17): replaces the original `test_farma_detection_
    collapse_is_the_verified_root_cause` -- FARMA-family detection, which
    collapsed to 1/7 (14.3%) under the pre-recalibration threshold, is now
    fully recovered to 7/7 (100%), matching B8 exactly. The real root cause
    named in this file's own module docstring (GROUP_WEIGHT=0.25 diluting a
    single guard's own already-sufficient evidence) is confirmed by this
    recovery: the dev-corpus recalibration changed only the threshold each
    guard-group's diluted contribution is compared against, not the
    dilution itself, and that was enough."""
    metrics, _ = run_b9_risk_composed()
    assert metrics.per_attack_family_detection["FARMA"] == 1.0
