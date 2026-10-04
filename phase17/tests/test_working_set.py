"""Guards for the working-set discipline (`phase17/working_set.py`). No live LLM calls.

These tests exist because the defect they guard against already happened three separate
times -- the worm population stopped propagating, the exfiltration population stopped
exfiltrating, and the published AgentPoison records read 0/6 because their trigger was never
carried -- and each time it was found by hand, late, after numbers had been published on top
of it. A population that silently stops functioning is the most expensive kind of error in
this benchmark, because nothing about it looks wrong.

So the floor check below is the load-bearing one: it fails CI when a population's working
rate drops more than the recorded margin below what it was when frozen.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

DATA = Path(__file__).resolve().parents[1] / "data"


def _report():
    p = DATA / "working_set.json"
    if not p.exists():
        pytest.skip("working set not computed in this checkout (run phase17.working_set)")
    return json.loads(p.read_text(encoding="utf-8"))


def test_working_rate_has_not_fallen_below_each_population_floor():
    """THE REGRESSION GUARD. A regenerated corpus that stops functioning, or a new corpus
    bolted on without an audit, fails here instead of quietly diluting every rate."""
    f = DATA / "working_set_floors.json"
    if not f.exists():
        pytest.skip("floors not recorded yet (run: python -m phase17.working_set --record-floors)")
    floors = json.loads(f.read_text(encoding="utf-8"))["floors"]
    rows = _report()["populations"]
    bad = {p: (rows[p]["rate"], fl) for p, fl in floors.items()
           if p in rows and rows[p]["rate"] < fl}
    assert not bad, (
        "Population working rates fell below their recorded floors "
        f"{ {p: f'{r:.1%} < {fl:.1%}' for p, (r, fl) in bad.items()} }. "
        "An attack population has stopped doing what it claims. Diagnose the population -- "
        "do NOT lower the floor to make this pass.")


def test_every_audited_population_appears_in_the_working_set_report():
    """The register defect, as a test: a population that exists but is in no audit is
    invisible, and invisible is how `corpus_extended` and `frozen75` went unmeasured for two
    rounds, and how Mosscap stayed out of the audit while being used as a hold-out."""
    from phase17.attack_validity_audit import populations

    rows = _report()["populations"]
    missing = sorted(set(populations()) - set(rows))
    assert not missing, (
        f"Populations declared in attack_validity_audit.populations() but absent from the "
        f"working-set report: {missing}. Re-run the audit; a population with no audit has no "
        "working rate, so any detection number on it is uninterpretable.")


def test_working_set_never_consults_a_defense_decision():
    """The filter must be a property of the ATTACK alone. If a defense's output ever became an
    input, the filter would select the instances that defense happens to catch, and every
    'recall on working attacks' number built on it would be circular."""
    src = (Path(__file__).resolve().parents[1] / "working_set.py").read_text(encoding="utf-8")
    code = "\n".join(l for l in src.splitlines() if not l.strip().startswith("#"))
    code = code.split('"""', 2)[-1]  # drop the module docstring, which discusses these names
    for banned in ("apply_defense", "b12_excluded", "excluded_on_full", "defended_retrieval"):
        assert banned not in code, (
            f"working_set.py references {banned!r}. Working-set membership must not depend on "
            "any defense's decision.")


def test_working_set_is_a_subset_of_what_subverted_the_agent():
    for pop, v in _report()["populations"].items():
        assert v["n_working_set"] <= v["n_subverts"] <= v["n_total"], pop
        assert v["lost_to_mechanism_check"] >= 0, pop


def test_recall_on_working_is_recomputable_from_the_evaluation():
    """`eval_round6` must persist raw per-item decisions and their ids. Round 6 did not, so
    answering 'what is recall on the working subset?' required re-running a 2-hour evaluation."""
    p = DATA / "eval_round6.json"
    if not p.exists():
        pytest.skip("eval_round6 not run in this checkout")
    d = json.loads(p.read_text(encoding="utf-8"))
    if "raw" not in d:
        pytest.skip("eval_round6.json predates raw-output persistence; re-run to enable")
    assert "raw_ids" in d, "raw decisions saved without ids; they cannot be joined to the audit"
    for key, ids in d["raw_ids"].items():
        for cfg, pops in d["raw"].items():
            if key in pops:
                assert len(pops[key]) == len(ids), f"{cfg} {key}: decisions/ids length mismatch"


def test_both_denominators_are_reported_not_just_the_favourable_one():
    """The discipline is only honest if the full population stays published. A report that
    carried the working-set rate alone would be the exact selective-reporting failure this
    project retracted once already."""
    rows = _report()["populations"]
    assert rows, "no populations in the working-set report"
    for pop, v in rows.items():
        assert v["n_total"] > 0 and "n_working_set" in v, pop
