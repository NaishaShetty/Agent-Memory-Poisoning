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
