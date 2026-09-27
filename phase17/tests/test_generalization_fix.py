"""Tests for the Phase 17 generalization fix (G1 rule, dev-set disjointness, judge cache)."""

import json
from pathlib import Path

from phase6.defense.risk.risk_score import (
    COMPOSITION_RULES, GROUPED_GATED_ADMISSION_AND_RETRIEVAL_CORROBORATED, GROUPED_GATED_ADMISSION_CORROBORATED,
    compute_memory_risk_score,
)
from phase17 import dev_sets

DATA = Path(__file__).resolve().parents[1] / "data"


def test_g1_rule_registered_and_frozen_rules_unchanged():
    assert GROUPED_GATED_ADMISSION_AND_RETRIEVAL_CORROBORATED in COMPOSITION_RULES
    sig = {"consensus_divergence_score": 0.9, "semantic_consensus_divergence_score": 0.9, "dormancy_activation_score": 1.0}
    live = compute_memory_risk_score("m", sig, rule=GROUPED_GATED_ADMISSION_CORROBORATED)
    g1 = compute_memory_risk_score("m", sig, rule=GROUPED_GATED_ADMISSION_AND_RETRIEVAL_CORROBORATED)
    assert live.risk_score > 0.0          # retrieval-only evidence moves the live rule ...
    assert g1.risk_score == 0.0           # ... but cannot move the language-safe rule


def test_g1_keeps_admission_evidence():
    sig = {"self_reference_score": 0.9, "stale_precedent_dismissal_score": 0.9}
    a = compute_memory_risk_score("m", sig, rule=GROUPED_GATED_ADMISSION_CORROBORATED)
    b = compute_memory_risk_score("m", sig, rule=GROUPED_GATED_ADMISSION_AND_RETRIEVAL_CORROBORATED)
    assert a.risk_score == b.risk_score > 0.0


def test_dev_and_eval_sets_are_disjoint():
    dev = dev_sets.load()
    eval_texts = {i["text"] for i in json.loads((DATA / "novel_attacks.json").read_text(encoding="utf-8"))["items"]}
    assert not eval_texts & {a["text"] for a in dev["attacks"]}
    assert not set(dev["mechanisms"]) & set(json.loads((DATA / "novel_attacks.json").read_text(encoding="utf-8"))["mechanisms"])
    assert len(dev["attacks"]) >= 50 and len(dev["benign"]) >= 100
