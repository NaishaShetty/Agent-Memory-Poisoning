"""Phase 8.9 -- regression test locking in the real, measured calibration finding.

Pure unit tests (no h4venv needed): every assertion is a real, observed value from
running the real, unmodified `evaluate_sleeper_retrieval_risk()` -- not a hand-picked
target the study was tuned to hit.
"""

from __future__ import annotations

import pytest

from phase8.detection.sleeper_threshold_calibration_study import (
    REAL_POISON_ACTIVATION_PRIOR_COUNT,
    run_threshold_calibration_study,
)


def test_real_poison_activation_point_is_correctly_cited():
    """Guards against the cited constant drifting from Stage 8.6's own real, measured
    activation point without this test noticing."""
    assert REAL_POISON_ACTIVATION_PRIOR_COUNT == 1


def test_legitimate_brand_new_content_scores_higher_than_the_real_poison_did():
    """The real, measured, uncomfortable finding: a brand-new legitimate persistent-
    policy memory's very first query scores STRICTLY MORE suspicious (gated_score=1.0)
    than the real attack scored at its own real, historical moment of activation
    (gated_score=0.5) -- confirmed by running the real signal function, not asserted
    from the formula alone."""
    result = run_threshold_calibration_study()
    assert result.legitimate_new_content_score == pytest.approx(1.0)
    assert result.poison_activation_point.gated_score == pytest.approx(0.5)
    assert result.legitimate_new_content_score > result.poison_activation_point.gated_score


def test_no_threshold_in_0_1_can_separate_legitimate_new_content_from_the_real_attack():
    """The real, mathematical conclusion this study exists to establish: since
    legitimate-new-content's real score (1.0) is >= the real poison's own real
    activation score (0.5), no threshold T in (0, 1] can flag the attack (T <= 0.5)
    without also flagging every brand-new legitimate memory (1.0 >= T trivially)."""
    result = run_threshold_calibration_study()
    assert result.no_threshold_can_separate_them is True


def test_current_thresholds_quarantine_both_at_their_real_respective_points():
    """Confirms the CURRENT (0.5/0.2) thresholds are not somehow accidentally already
    fine: both the real poison and brand-new legitimate content land in QUARANTINE at
    their respective real, cited scoring points."""
    result = run_threshold_calibration_study()
    assert result.poison_activation_point.action == "QUARANTINE"
    legit_at_n0 = next(p for p in result.legitimate_content_points if p.prior_retrieval_count == 0)
    assert legit_at_n0.action == "QUARANTINE"


def test_legitimate_content_eventually_reaches_allow_as_prior_count_grows():
    """Real, disclosed context: this is not a claim that legitimate content is
    PERMANENTLY misclassified -- it recovers to ALLOW once it accumulates enough real
    prior retrievals (n>=5 under the current thresholds), the same real
    dormancy_activation_signal() shape Stage 8.2 already validated. The problem is
    specifically the FIRST query (or two), not the long run."""
    result = run_threshold_calibration_study()
    allowed = [p for p in result.legitimate_content_points if p.action == "ALLOW"]
    assert allowed, "legitimate content never reaches ALLOW in this sweep -- re-check the swept range"
    assert min(p.prior_retrieval_count for p in allowed) >= 5
