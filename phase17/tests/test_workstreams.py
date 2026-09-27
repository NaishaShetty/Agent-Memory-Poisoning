"""Tests for the Phase 17 workstream modules (leakage audit, sanity baselines, provenance
integrity, canonical matrix/frontier assembly)."""
import json
from pathlib import Path

import pytest

from phase17 import leakage_audit
from phase17.provenance_integrity import structural_forgery_is_rejected
from phase17.sanity_baselines import always_allow, always_quarantine, compare_to_random, random_budget_matched

DATA = Path(__file__).resolve().parents[1] / "data"


def test_leakage_audit_passes_on_real_data():
    report = leakage_audit.audit_all()
    assert set(report.passed) == set(report.checks)
    assert report.details["dev_eval_text_disjoint"]["n_overlap"] == 0
    assert report.details["poison_target_not_in_benign_train"]["overlap"] == []


def test_leakage_audit_detects_injected_overlap():
    with pytest.raises(leakage_audit.LeakageError):
        leakage_audit.check_poison_record_metadata_complete([type("R", (), {"scenario_id": "", "text": "x", "family": "f", "split": "s"})()])


def test_structural_forgery_all_rejected():
    r = structural_forgery_is_rejected()
    assert r["all_rejected"] is True
    assert "attacker_originated" in r["confirmed_rejected"]


def test_sanity_baselines_are_trivial_bounds():
    ids = [f"m{i}" for i in range(20)]
    assert not any(always_allow(ids).values())
    assert all(always_quarantine(ids).values())
    rb = random_budget_matched(ids, 0.5, seed=1)
    assert abs(sum(rb.values()) - 10) <= 1


def test_compare_to_random_matches_alert_rate():
    poison = [f"p{i}" for i in range(10)]
    benign = [f"b{i}" for i in range(90)]
    flags = {i: True for i in poison} | {i: False for i in benign}
    res = compare_to_random(poison, benign, flags, n_boot=50)
    assert res["alert_rate_matched"] == pytest.approx(0.10)
    assert res["real_detection"]["k"] == 10


def test_canonical_matrix_and_frontier_artifacts_exist_and_are_traceable():
    m = json.loads((DATA / "canonical_matrix.json").read_text(encoding="utf-8"))
    assert len(m["rows"]) > 0
    for row in m["rows"]:
        assert row["source"] != "N/A"  # every non-baseline row must trace to a real artifact
    f = json.loads((DATA / "security_utility_frontier.json").read_text(encoding="utf-8"))
    assert "B12" in f and "B0" in f
