"""Phase 14 -- tests for the real, live defended-retrieval wiring. Fast (no
LLM calls -- these are all real, deterministic signal-function/decision-logic
calls)."""

from __future__ import annotations

from phase14.defended_retrieval import (
    CONFIG_B0_NO_DEFENSE,
    CONFIG_B1_ADMISSION_ONLY,
    CONFIG_B9_RISK_COMPOSED,
    apply_defense,
)


def test_b0_never_excludes_anything():
    items = [("m1", "Melanie signed up for her pottery class on 14 August 2023."), ("m2", "irrelevant benign text")]
    kept, decisions = apply_defense(CONFIG_B0_NO_DEFENSE, items)
    assert kept == tuple(items)
    assert all(not d.excluded for d in decisions)
    assert all(d.action == "ALLOW" for d in decisions)


def test_unknown_config_raises():
    import pytest

    with pytest.raises(ValueError):
        apply_defense("NOT_A_REAL_CONFIG", [("m1", "text")])


def test_b1_and_b9_return_a_decision_for_every_real_candidate():
    items = [("m1", "a"), ("m2", "b"), ("m3", "c")]
    for config in (CONFIG_B1_ADMISSION_ONLY, CONFIG_B9_RISK_COMPOSED):
        kept, decisions = apply_defense(config, items)
        assert {d.memory_id for d in decisions} == {"m1", "m2", "m3"}
        assert set(kept) <= set(items)


def test_excluded_items_are_never_in_kept():
    """Regression: an excluded candidate (QUARANTINE/BLOCK) must never appear
    in the real kept set, and every non-excluded one must."""
    items = [("m1", "a"), ("m2", "b")]
    kept, decisions = apply_defense(CONFIG_B1_ADMISSION_ONLY, items)
    excluded_ids = {d.memory_id for d in decisions if d.excluded}
    kept_ids = {mid for mid, _ in kept}
    assert excluded_ids.isdisjoint(kept_ids)
    assert kept_ids == {mid for mid, _ in items} - excluded_ids


def test_real_benign_content_is_never_quarantined_by_b1_or_b9():
    """Real, already-established finding (Phase 6-12's own work): ordinary
    real LoCoMo-style benign content should not trip either real config."""
    items = [
        ("b1", "Jon lost his job as a banker on January 19, 2023."),
        ("b2", "Caroline is now leaning toward social work as a career."),
        ("b3", "Melanie enjoys long solo drives on weekends."),
    ]
    for config in (CONFIG_B1_ADMISSION_ONLY, CONFIG_B9_RISK_COMPOSED):
        _, decisions = apply_defense(config, items)
        assert all(not d.excluded for d in decisions), f"{config} incorrectly excluded real benign content"
