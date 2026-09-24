"""Phase 6.12 -- tests for the Defense Metrics & Evaluation Protocol module:
intervention-stage classification, security/defense/utility/cost metrics, and
the Pareto frontier helper.
"""

from __future__ import annotations

import pytest

from phase6.defense.policy.states import ALLOW, BLOCK, DOWNRANK, QUARANTINE
from phase6.evaluation.metrics.cost_metrics import ALL_COMPONENT_PROFILES, total_query_latency_seconds
from phase6.evaluation.metrics.defense_metrics import (
    benign_downrank_rate,
    benign_quarantine_rate,
    benign_retrieval_suppression_rate,
    defense_success_rate,
    false_positive_rate,
)
from phase6.evaluation.metrics.intervention_stage import (
    InterventionEvidence,
    InterventionStage,
    classify_intervention_stage,
)
from phase6.evaluation.metrics.pareto import ConfigurationPoint, pareto_frontier
from phase6.evaluation.metrics.security_metrics import (
    attack_mitigation_rate,
    poison_acceptance_rate,
    poison_influence_rate,
    poison_selection_rate,
    propagation_rate,
    sleeper_detection_rate,
)
from phase6.evaluation.metrics.utility_metrics import utility_retention_score


# ---------------------------------------------------------------------------
# Intervention stage classification -- mutual exclusivity, priority order
# ---------------------------------------------------------------------------


def test_prevented_at_admission_via_block():
    ev = InterventionEvidence(admission_action=BLOCK)
    assert classify_intervention_stage(ev) == InterventionStage.PREVENTED_AT_ADMISSION


def test_prevented_at_admission_via_quarantine():
    ev = InterventionEvidence(admission_action=QUARANTINE)
    assert classify_intervention_stage(ev) == InterventionStage.PREVENTED_AT_ADMISSION


def test_admission_takes_priority_over_retrieval():
    """Even if retrieval evidence ALSO looks concerning, admission's earlier
    lifecycle position wins the classification -- the item never reached
    retrieval in the first place."""
    ev = InterventionEvidence(admission_action=BLOCK, retrieval_eligible=False, retrieval_action=QUARANTINE)
    assert classify_intervention_stage(ev) == InterventionStage.PREVENTED_AT_ADMISSION


def test_prevented_at_retrieval_via_ineligible():
    ev = InterventionEvidence(admission_action=ALLOW, retrieval_eligible=False)
    assert classify_intervention_stage(ev) == InterventionStage.PREVENTED_AT_RETRIEVAL


def test_prevented_at_retrieval_via_downrank():
    ev = InterventionEvidence(admission_action=ALLOW, retrieval_eligible=True, retrieval_action=DOWNRANK)
    assert classify_intervention_stage(ev) == InterventionStage.PREVENTED_AT_RETRIEVAL


def test_contained_at_propagation():
    ev = InterventionEvidence(admission_action=ALLOW, retrieval_eligible=True, propagation_action=QUARANTINE)
    assert classify_intervention_stage(ev) == InterventionStage.CONTAINED_AT_PROPAGATION


def test_detected_sleeper_pre_activation():
    ev = InterventionEvidence(admission_action=ALLOW, retrieval_eligible=True, sleeper_action=QUARANTINE)
    assert classify_intervention_stage(ev) == InterventionStage.DETECTED_SLEEPER_PRE_ACTIVATION


def test_influence_status_unknown_when_nothing_intervened_and_no_counterfactual():
    ev = InterventionEvidence(admission_action=ALLOW, retrieval_eligible=True)
    assert classify_intervention_stage(ev) == InterventionStage.INFLUENCE_STATUS_UNKNOWN


def test_confirmed_no_influence():
    ev = InterventionEvidence(admission_action=ALLOW, retrieval_eligible=True, counterfactual_influence=False)
    assert classify_intervention_stage(ev) == InterventionStage.CONFIRMED_NO_INFLUENCE


def test_confirmed_influenced_unmitigated():
    ev = InterventionEvidence(
        admission_action=ALLOW, retrieval_eligible=True, counterfactual_influence=True, later_quarantined=False
    )
    assert classify_intervention_stage(ev) == InterventionStage.CONFIRMED_INFLUENCED_UNMITIGATED


def test_confirmed_influenced_then_recovered():
    ev = InterventionEvidence(
        admission_action=ALLOW, retrieval_eligible=True, counterfactual_influence=True, later_quarantined=True
    )
    assert classify_intervention_stage(ev) == InterventionStage.CONFIRMED_INFLUENCED_THEN_RECOVERED


def test_later_quarantined_ignored_when_no_influence_confirmed():
    """later_quarantined is only meaningful conditional on real confirmed
    influence -- setting it True with counterfactual_influence=False must not
    accidentally produce a 'recovered' classification."""
    ev = InterventionEvidence(
        admission_action=ALLOW, retrieval_eligible=True, counterfactual_influence=False, later_quarantined=True
    )
    assert classify_intervention_stage(ev) == InterventionStage.CONFIRMED_NO_INFLUENCE


# ---------------------------------------------------------------------------
# Security metrics
# ---------------------------------------------------------------------------


def test_par_basic():
    assert poison_acceptance_rate(3, 10) == pytest.approx(0.3)


def test_psr_basic():
    assert poison_selection_rate(2, 3) == pytest.approx(2 / 3)


def test_pir_basic():
    assert poison_influence_rate(1, 4) == pytest.approx(0.25)


def test_propagation_rate_basic():
    assert propagation_rate(2, 5) == pytest.approx(0.4)


def test_sdr_basic():
    assert sleeper_detection_rate(4, 5) == pytest.approx(0.8)


def test_security_metrics_reject_numerator_exceeding_denominator():
    with pytest.raises(ValueError):
        poison_acceptance_rate(11, 10)


def test_security_metrics_reject_zero_denominator():
    with pytest.raises(ValueError):
        poison_acceptance_rate(0, 0)


def test_attack_mitigation_rate_full_breakdown():
    evidences = [
        InterventionEvidence(admission_action=BLOCK),
        InterventionEvidence(admission_action=ALLOW, retrieval_eligible=True, counterfactual_influence=False),
        InterventionEvidence(admission_action=ALLOW, retrieval_eligible=True, counterfactual_influence=True, later_quarantined=False),
    ]
    result = attack_mitigation_rate(evidences)
    assert result.attack_attempts == 3
    assert result.mitigated == 2  # BLOCK + confirmed-no-influence
    assert result.rate == pytest.approx(2 / 3)
    assert result.stage_breakdown[InterventionStage.PREVENTED_AT_ADMISSION.value] == 1
    assert result.stage_breakdown[InterventionStage.CONFIRMED_NO_INFLUENCE.value] == 1
    assert result.stage_breakdown[InterventionStage.CONFIRMED_INFLUENCED_UNMITIGATED.value] == 1


def test_attack_mitigation_rate_rejects_empty():
    with pytest.raises(ValueError):
        attack_mitigation_rate([])


# ---------------------------------------------------------------------------
# Defense metrics -- DSR always carries its breakdown
# ---------------------------------------------------------------------------


def test_dsr_matches_amr_by_construction():
    """Disclosed in both modules' docstrings: DSR and AMR use the identical
    classification and grouping -- verify this is actually true in code, not
    just claimed in prose."""
    from phase6.evaluation.metrics.security_metrics import attack_mitigation_rate

    evidences = [
        InterventionEvidence(admission_action=BLOCK),
        InterventionEvidence(admission_action=ALLOW, retrieval_eligible=True),
    ]
    dsr = defense_success_rate(evidences)
    amr = attack_mitigation_rate(evidences)
    assert dsr.rate == amr.rate
    assert dsr.stage_breakdown == amr.stage_breakdown


def test_dsr_result_type_always_has_stage_breakdown_field():
    """Structural guarantee: there is no code path returning a bare DSR
    number without the breakdown -- checked by asserting the dataclass field
    exists and is populated for every InterventionStage, not just the ones
    that occurred."""
    import dataclasses

    result = defense_success_rate([InterventionEvidence(admission_action=BLOCK)])
    field_names = {f.name for f in dataclasses.fields(result)}
    assert "stage_breakdown" in field_names
    assert set(result.stage_breakdown.keys()) == {s.value for s in InterventionStage}


def test_false_positive_rate_basic():
    assert false_positive_rate(1, 20) == pytest.approx(0.05)


def test_benign_rate_family_are_independent_numbers():
    """The three companion rates must be computable independently -- a
    benign memory downranked is not automatically counted as quarantined or
    suppressed."""
    assert benign_quarantine_rate(1, 20) == pytest.approx(0.05)
    assert benign_downrank_rate(2, 20) == pytest.approx(0.10)
    assert benign_retrieval_suppression_rate(3, 20) == pytest.approx(0.15)


# ---------------------------------------------------------------------------
# Utility metrics
# ---------------------------------------------------------------------------


def test_urs_no_loss():
    result = utility_retention_score(0.817, 0.817)
    assert result.urs == pytest.approx(1.0)


def test_urs_real_loss():
    result = utility_retention_score(0.70, 0.817)
    assert result.urs < 1.0
    assert result.urs == pytest.approx(0.70 / 0.817)


def test_urs_rejects_zero_baseline():
    with pytest.raises(ValueError):
        utility_retention_score(0.5, 0.0)


def test_urs_rejects_out_of_range_rates():
    with pytest.raises(ValueError):
        utility_retention_score(1.5, 0.8)
    with pytest.raises(ValueError):
        utility_retention_score(0.5, -0.1)


# ---------------------------------------------------------------------------
# Cost metrics
# ---------------------------------------------------------------------------


def test_non_llm_components_have_zero_token_and_model_overhead():
    from phase6.evaluation.metrics.cost_metrics import (
        ADMISSION_REASONING_GUARD,
        PROPAGATION_CONTAINMENT,
        RETRIEVAL_LEXICAL_D1,
        SLEEPER_GUARD,
    )

    for profile in (ADMISSION_REASONING_GUARD, RETRIEVAL_LEXICAL_D1, PROPAGATION_CONTAINMENT, SLEEPER_GUARD):
        assert profile.model_call_overhead == 0
        assert profile.token_overhead == 0


def test_semantic_d2_has_real_measured_latency():
    from phase6.evaluation.metrics.cost_metrics import RETRIEVAL_SEMANTIC_D2

    assert RETRIEVAL_SEMANTIC_D2.measured_latency_seconds is not None
    assert RETRIEVAL_SEMANTIC_D2.measured_latency_seconds > 0
    assert RETRIEVAL_SEMANTIC_D2.model_call_overhead == 1


def test_all_component_profiles_present():
    # UPDATE (2026-09-23, Phase 14, explicitly authorized): the Consolidation
    # Guard (Phase 12's fifth defense component) now has a real profile too --
    # it had none at all when this test was written, since it did not yet
    # exist. 6 -> 7, additive only; every prior profile is unchanged.
    assert len(ALL_COMPONENT_PROFILES) == 7


def test_total_query_latency_is_none_if_any_component_unmeasured():
    assert total_query_latency_seconds(0.017, None) is None


def test_total_query_latency_sums_when_all_measured():
    assert total_query_latency_seconds(0.017, 0.003) == pytest.approx(0.020)


# ---------------------------------------------------------------------------
# Pareto frontier
# ---------------------------------------------------------------------------


def test_pareto_frontier_excludes_dominated_point():
    points = [
        ConfigurationPoint("A", security=0.5, utility=0.9),
        ConfigurationPoint("B", security=0.3, utility=0.8),  # dominated by A on both axes
        ConfigurationPoint("C", security=0.8, utility=0.6),
    ]
    frontier = pareto_frontier(points)
    names = {p.name for p in frontier}
    assert names == {"A", "C"}


def test_pareto_frontier_keeps_equal_points_both():
    points = [
        ConfigurationPoint("A", security=0.5, utility=0.9),
        ConfigurationPoint("B", security=0.5, utility=0.9),
    ]
    frontier = pareto_frontier(points)
    assert len(frontier) == 2


def test_pareto_frontier_rejects_empty():
    with pytest.raises(ValueError):
        pareto_frontier([])


def test_pareto_frontier_single_point_is_always_on_frontier():
    points = [ConfigurationPoint("Solo", security=0.1, utility=0.1)]
    assert pareto_frontier(points) == tuple(points)
