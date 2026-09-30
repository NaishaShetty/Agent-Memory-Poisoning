"""Tests for external review round 5 (structural; no live LLM calls).

The load-bearing one is `test_external_test_corpus_is_still_frozen`: the round-5 defense
work is only meaningful if its test set provably did not change after being frozen.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

DATA = Path(__file__).resolve().parents[1] / "data"


def test_external_test_corpus_is_still_frozen():
    from phase17 import external_test_corpus as e

    if not e.FREEZE.exists():
        pytest.skip("external test corpus not built in this checkout")
    assert e.verify_frozen(), (
        "The frozen external TEST corpus no longer matches the SHA-256 recorded when it was "
        "frozen. Either it was edited after freezing -- which invalidates every held-out "
        "number measured on it -- or it was rebuilt. Re-freeze only with a disclosed reason.")


def test_external_dev_and_test_corpora_do_not_overlap():
    from phase17.external_attacks import external_records
    from phase17.external_test_corpus import test_attack_records

    dev = {r.text for r in external_records()}
    test = {r.text for r in test_attack_records()}
    if not dev or not test:
        pytest.skip("external corpora not built in this checkout")
    assert not (dev & test), f"{len(dev & test)} attack texts appear in BOTH external dev and test"


def test_external_test_corpus_records_license_and_authorship():
    path = DATA / "external_test_attacks.json"
    if not path.exists():
        pytest.skip("external test corpus not built in this checkout")
    src = json.loads(path.read_text(encoding="utf-8"))["sources"]
    for name, meta in src.items():
        assert meta.get("license"), f"{name} has no recorded license"
        assert meta.get("authorship"), f"{name} has no recorded authorship"


def test_external_test_corpus_contains_genuinely_human_authored_attacks():
    """The first human-authored attacks in this project; the claim must stay checkable."""
    path = DATA / "external_test_attacks.json"
    if not path.exists():
        pytest.skip("external test corpus not built in this checkout")
    d = json.loads(path.read_text(encoding="utf-8"))
    human = [i for i in d["items"] if i["source"] == "gandalf"]
    assert len(human) > 500
    assert "human" in d["sources"]["gandalf"]["authorship"].lower()


def _norm(t: str) -> str:
    return " ".join(t.lower().split())


def test_b14_training_data_is_disjoint_from_the_frozen_external_test_set():
    """The load-bearing leakage check for round 5: nothing B14 is fitted on may appear in
    the frozen external TEST corpus, in either direction, including after the deterministic
    memory-note wrappers are stripped."""
    from phase17.external_test_corpus import test_attack_records, test_benign_texts
    from phase17.train_b14 import training_data

    try:
        texts, _, _ = training_data()
    except FileNotFoundError:
        pytest.skip("dev pool not available in this checkout")
    test_texts = {_norm(r.text) for r in test_attack_records()} | {_norm(t) for t in test_benign_texts()}
    if not test_texts:
        pytest.skip("external test corpus not built in this checkout")
    overlap = {t for t in (_norm(x) for x in texts) if t in test_texts}
    assert not overlap, f"{len(overlap)} B14 training items also appear in the frozen external TEST corpus"


def test_agentdojo_dev_and_test_halves_are_disjoint():
    from phase17.b13_dev_calibration import agentdojo_benign

    dev, test = agentdojo_benign("dev"), agentdojo_benign("test")
    if not dev or not test:
        pytest.skip("AgentDojo benign extract not present")
    assert not ({_norm(t) for t in dev} & {_norm(t) for t in test})


def test_b14_does_not_train_on_this_projects_held_out_attack_populations():
    """novel_60 / novel_new120 / gemini_30 / evasion / zh_native / trackb keep their
    published meaning only if B14 never sees them during fitting."""
    from phase17.eval_populations import attack_populations
    from phase17.train_b14 import training_data

    try:
        texts, _, _ = training_data()
    except FileNotFoundError:
        pytest.skip("dev pool not available in this checkout")
    train = {_norm(t) for t in texts}
    pops = attack_populations()
    for name in ("novel_60 (qwen)", "novel_new120 (qwen, disjoint scenarios)", "gemini_authored_30",
                 "evasion_47", "zh_native_30 (gemini)"):
        held = {_norm(t) for t in pops.get(name, [])}
        assert not (train & held), f"B14 training overlaps the held-out population {name!r}"
