"""Phase 6.15 -- tests for the cross-attack generalization evaluation. Every
assertion reflects the REAL, measured DGS computation, checked before being
written up (see docs/phase6/CROSS_ATTACK_GENERALIZATION.md for the full
account, including why DGS=0.0 for the admission layer is reported honestly
rather than softened).
"""

from __future__ import annotations

import pytest

from phase6.defense.policy.states import ALLOW
from phase6.evaluation.generalization.dgs import (
    ATTACK_FAMILIES,
    defense_generalization_score,
    evaluate_all_seven,
)


def test_all_seven_attack_families_are_represented():
    results = evaluate_all_seven()
    assert {r.attack for r in results} == set(ATTACK_FAMILIES.keys())
    assert len(results) == 7


def test_each_result_carries_its_mechanism_family_and_content_provenance():
    """Every result must be traceable: which mechanism family, and whether
    its content is real (cite the source) or synthetic (labeled as such) --
    never an unmarked result."""
    results = evaluate_all_seven()
    for r in results:
        assert r.mechanism_family
        assert r.content_source  # non-empty
        assert "real" in r.content_source.lower() or "synthetic" in r.content_source.lower()


def test_dgs_reflects_the_real_measured_admission_layer_result():
    """REAL RESULT (not assumed in advance): the shipped, never-per-attack-
    tuned admission guard catches NONE of the seven attack families'
    representative content -- DGS=0.0. This is reported honestly, not
    softened, consistent with Stage 6.10/6.14's own already-disclosed
    findings that this project's content signals are largely
    signature-specific rather than behavior-general."""
    results = evaluate_all_seven()
    dgs = defense_generalization_score(results)
    assert dgs == 0.0
    assert all(not r.caught_by_current_defense for r in results)


def test_agentpoison_is_flagged_as_an_architectural_gap_not_just_a_miss():
    """AgentPoison's real attack surface (a query-side embedding trigger) is
    structurally different from what any Phase 6 content signal inspects --
    this must be stated explicitly in that result's notes, not silently
    treated as the same kind of miss as the other six."""
    results = evaluate_all_seven()
    agentpoison = next(r for r in results if r.attack == "AgentPoison")
    assert "structural" in agentpoison.notes.lower() or "architectural" in agentpoison.notes.lower() or "never inspected" in agentpoison.notes.lower()


def test_farma_result_carries_the_seed_vs_amplified_caveat():
    """The FARMA result must repeat Stage 6.10's own disclosed caveat (the
    real log content is likely the unamplified seed, not the amplified
    records Stage 6.5's own synthetic test targets) -- this caveat must not
    be dropped when the result is reused here."""
    results = evaluate_all_seven()
    farma = next(r for r in results if r.attack == "FARMA")
    assert "seed" in farma.notes.lower()


def test_defense_generalization_score_rejects_empty_input():
    with pytest.raises(ValueError):
        defense_generalization_score(())


def test_defense_generalization_score_arithmetic_is_correct():
    """Direct arithmetic check, independent of the real evaluate_all_seven()
    result, using a hand-constructed input."""
    from phase6.evaluation.generalization.dgs import PerAttackResult

    fake_results = (
        PerAttackResult("A", "family1", "synthetic", True, "PREVENTED_AT_ADMISSION", "caught"),
        PerAttackResult("B", "family2", "synthetic", False, "INFLUENCE_STATUS_UNKNOWN", "not caught"),
        PerAttackResult("C", "family3", "synthetic", True, "PREVENTED_AT_ADMISSION", "caught"),
        PerAttackResult("D", "family4", "synthetic", False, "INFLUENCE_STATUS_UNKNOWN", "not caught"),
    )
    assert defense_generalization_score(fake_results) == pytest.approx(0.5)
