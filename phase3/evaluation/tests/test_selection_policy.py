"""Tests for `foundations.selection_policy` -- the threshold-based selection mechanism
(design review sections 2.2/2.3). Uses a fake scorer (monkeypatched
`similarity.score_candidates`) so these tests never load the real embedding model --
that real-model behavior is covered separately by
`test_selection_policy_real_model.py`, gated behind the real environment."""

from __future__ import annotations

import phase3.evaluation.foundations.selection_policy as sp
from phase3.evaluation.foundations.similarity import ScoredCandidate


def _fake_score_candidates(scores_by_id):
    def _fake(query, candidates):
        return [
            ScoredCandidate(memory_id=mid, content=content, score=scores_by_id[mid])
            for mid, content in candidates
        ]
    return _fake


def test_select_by_threshold_keeps_only_scores_at_or_above_threshold(monkeypatch):
    monkeypatch.setattr(sp, "score_candidates", _fake_score_candidates({
        "a": 0.9, "b": 0.5, "c": 0.2,
    }))
    result = sp.select_by_threshold(
        "query", [("a", "content a"), ("b", "content b"), ("c", "content c")], threshold=0.5,
    )
    assert {c.memory_id for c in result.selected} == {"a", "b"}
    assert {c.memory_id for c in result.rejected} == {"c"}
    assert result.threshold == 0.5


def test_select_by_threshold_can_select_zero(monkeypatch):
    monkeypatch.setattr(sp, "score_candidates", _fake_score_candidates({"a": 0.1, "b": 0.2}))
    result = sp.select_by_threshold("query", [("a", "x"), ("b", "y")], threshold=0.9)
    assert result.selected == ()
    assert len(result.rejected) == 2


def test_select_by_threshold_respects_max_k_cap(monkeypatch):
    monkeypatch.setattr(sp, "score_candidates", _fake_score_candidates({
        "a": 0.9, "b": 0.8, "c": 0.7, "d": 0.6,
    }))
    result = sp.select_by_threshold(
        "query", [("a", "x"), ("b", "y"), ("c", "z"), ("d", "w")], threshold=0.5, max_k=2,
    )
    assert len(result.selected) == 2
    assert {c.memory_id for c in result.selected} == {"a", "b"}
    assert {c.memory_id for c in result.rejected} == {"c", "d"}


def test_select_by_threshold_empty_candidates():
    result = sp.select_by_threshold("query", [], threshold=0.5)
    assert result.selected == ()
    assert result.rejected == ()


def test_calibrate_threshold_from_gold_evidence_uses_real_percentile(monkeypatch):
    def _fake(query, candidates):
        # one candidate per call in calibration -- score derived from a per-call counter
        idx = _fake.calls
        _fake.calls += 1
        return [ScoredCandidate(memory_id=candidates[0][0], content=candidates[0][1], score=idx / 10.0)]
    _fake.calls = 0
    monkeypatch.setattr(sp, "score_candidates", _fake)

    pairs = [(f"q{i}", f"e{i}") for i in range(10)]  # scores will be 0.0..0.9
    result = sp.calibrate_threshold_from_gold_evidence(pairs, coverage_target=0.9)

    assert result["n_pairs"] == 10
    assert result["coverage_target"] == 0.9
    assert len(result["scores"]) == 10
    assert 0.0 <= result["threshold"] <= 0.9
