"""Regression tests for the targeted phase (B13 owner LOO; attack validity; statistics audit)."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

DATA = Path(__file__).resolve().parents[1] / "data"
REM = DATA / "remediation"


def test_shipped_constants_sit_at_half_percent_budget_at_top20():
    """The frozen B13 constants were calibrated at top_k=5 (2%/5%); at top_k=20 they sit at ~0.5%/~2% of the same
    dev observations. Re-running the 2%/5% rule at top_k=20 is a different budget, not a different owner set --
    the artefact behind the withdrawn '3x owner instability' claim."""
    from phase17.b13_live import SUPPORT_EXCLUDE, SUPPORT_FLAG, SUPPORT_TOP_K

    p = DATA / "corroboration_v2_partial.json"
    if not p.exists():
        pytest.skip("dev profile cache absent")
    assert SUPPORT_TOP_K == 20
    d = json.loads(p.read_text(encoding="utf-8"))
    e = np.concatenate([[x["ent"] for x in d[f"fit:obs:{s}"]] for s in (1, 2, 3, 4)])
    assert len(e) == 1026
    assert (e < SUPPORT_EXCLUDE).sum() == 5 and (e < SUPPORT_FLAG).sum() == 21
    es = np.sort(e)
    nominal = es[int(0.02 * len(es))]
    assert nominal > 2.5 * SUPPORT_EXCLUDE        # the nominal rule at top-20 is a much looser point


def test_policy_b_semantics_three_outcomes():
    from phase17.remediation.b13_owner_loo import _policy_b

    names = ["Jolene"]
    t = "Jolene prefers the blue brand."
    assert _policy_b({"rel": .9, "ent": .5, "contr": .999}, t, names, .01, .02, .99, .6) == "CONTRADICTED"
    assert _policy_b({"rel": .3, "ent": .0001, "contr": .1}, t, names, .01, .02, .99, .6) == "DEFER"
    assert _policy_b({"rel": .9, "ent": .0001, "contr": .1}, t, names, .01, .02, .99, .6) == "UNSUPPORTED"
    assert _policy_b({"rel": .9, "ent": .9, "contr": .1}, t, names, .01, .02, .99, .6) == "PASS"
    assert _policy_b(None, t, names, .01, .02, .99, .6) == "PASS"               # no evidence -> no decision
    assert _policy_b({"rel": .9, "ent": .0, "contr": .0}, "The meeting is at 3pm.", [], .01, .02, .99, .6) == "PASS"


def test_loo_calibration_never_contains_the_held_out_owner():
    p = REM / "b13_owner_loo.json"
    if not p.exists():
        pytest.skip("LOO output absent")
    r = json.loads(p.read_text(encoding="utf-8"))
    for o, row in r["owners"].items():
        cal = row["calibration"]["calibration_owners"]
        assert int(o) not in cal and len(cal) == 9
    a = r["reproduction"]["A-ship levels on owners 1-4 (should reproduce the shipped constants)"]
    assert a[0] == pytest.approx(0.0019, abs=5e-4) and a[1] == pytest.approx(0.0057, abs=1.5e-3)


def test_loo_decomposition_reproduces_cached_corroboration():
    p = REM / "b13_owner_loo.json"
    if not p.exists():
        pytest.skip("LOO output absent")
    r = json.loads(p.read_text(encoding="utf-8"))
    for name in ("holdout4", "holdout7", "holdout8"):
        c = r["holdouts"][name]["conditions"]["correct"]
        assert c["atk"]["reproduces_cached_corroboration"] and c["ben"]["reproduces_cached_corroboration"]


def test_none_condition_is_noev():
    p = REM / "b13_owner_loo.json"
    if not p.exists():
        pytest.skip("LOO output absent")
    pooled = json.loads(p.read_text(encoding="utf-8"))["evidence_conditions"]["none"]["pooled"]
    for pol in ("A-ship", "A-nom", "A-frozen", "B"):
        assert pooled[pol]["detection"]["k"] == pooled["noev"]["detection"]["k"]
        assert pooled[pol]["benign_exclusion"]["k"] == pooled["noev"]["benign_exclusion"]["k"]


def test_owner_bootstrap_is_cluster_level():
    from phase17.remediation.b13_owner_loo import _boot_pooled

    per = {o: {"k": 1, "n": 10} for o in range(10)}
    b = _boot_pooled(per, "k", "n", np.random.default_rng(0))
    assert b["point"] == 0.1 and b["ci95"] == [0.1, 0.1] and b["clusters"] == 10


def test_paired_effect_counts_and_mcnemar():
    from phase17.remediation.validity_final import _paired

    x = [True] * 6 + [False] * 4
    y = [False] * 4 + [True] * 2 + [False] * 2 + [True] * 2
    r = _paired(x, y, {"population": ["a"] * 5 + ["b"] * 5}, np.random.default_rng(0))
    assert r["discordant"] == [4, 2] and r["diff_points"] == 20.0
    assert r["p_exact_mcnemar"] == pytest.approx(0.6875)


def test_validity_sample_matches_pr1():
    from phase17.remediation.validity_final import _sample

    p = REM / "probe_robustness_partial.json"
    if not p.exists():
        pytest.skip("PR-1 cache absent")
    d = json.loads(p.read_text(encoding="utf-8"))
    ids = {k.split(":", 2)[2] for k in d if k.startswith("ans:with:")}
    assert {r["id"] for r in _sample()} == ids


def test_one_sided_fisher_is_what_was_reported():
    from phase17.remediation.stats_audit import _fisher, _holm

    assert _fisher(40, 60, 0, 60, "greater") == pytest.approx(3.659e-17, rel=1e-3)
    assert _fisher(40, 60, 0, 60) == pytest.approx(2 * 3.659e-17, rel=1e-3)
    assert _holm([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.06, 0.06])
