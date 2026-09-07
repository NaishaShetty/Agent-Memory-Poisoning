"""Tests for `foundations.relationship_candidates.suggest_equivalent_to_candidates()`
-- the low-confidence candidate-flagging layer. Fake provider, no real model/LLM."""

from __future__ import annotations

from phase3.evaluation.foundations import relationship_candidates as rc
from phase3.evaluation.llm.provider import GenerationConfig
from phase3.evaluation.tests.test_agent_runtime import FakeLLMProvider


def _config():
    return GenerationConfig(temperature=0.0, seed=42, max_tokens=16, enable_thinking=False, n_ctx=2048)


def test_suggest_candidates_never_writes_anything_only_returns_suggestions(monkeypatch):
    def _fake_score(query, others):
        from phase3.evaluation.foundations.similarity import ScoredCandidate
        return [ScoredCandidate(memory_id=mid, content=content, score=0.9) for mid, content in others]

    monkeypatch.setattr(rc, "score_candidates", _fake_score)
    provider = FakeLLMProvider(response_text="EQUIVALENT")

    candidates = [("a", "Hello there, how are you?"), ("b", "Hi, how's it going?")]
    suggestions = rc.suggest_equivalent_to_candidates(candidates, provider, _config())

    assert len(suggestions) == 1
    assert suggestions[0].status == rc.STATUS_SUGGESTED_LOW_CONFIDENCE
    assert suggestions[0].memory_id_a == "a"
    assert suggestions[0].memory_id_b == "b"
    assert suggestions[0].llm_judge_label == "EQUIVALENT"


def test_suggest_candidates_below_gate_never_reach_the_llm(monkeypatch):
    def _fake_score(query, others):
        from phase3.evaluation.foundations.similarity import ScoredCandidate
        return [ScoredCandidate(memory_id=mid, content=content, score=0.1) for mid, content in others]

    monkeypatch.setattr(rc, "score_candidates", _fake_score)
    provider = FakeLLMProvider(response_text="EQUIVALENT")

    candidates = [("a", "unrelated text one"), ("b", "unrelated text two")]
    suggestions = rc.suggest_equivalent_to_candidates(candidates, provider, _config())

    assert suggestions == []
    assert provider.calls == []  # never called -- gated out before the LLM


def test_suggest_candidates_llm_says_not_equivalent_produces_no_suggestion(monkeypatch):
    def _fake_score(query, others):
        from phase3.evaluation.foundations.similarity import ScoredCandidate
        return [ScoredCandidate(memory_id=mid, content=content, score=0.9) for mid, content in others]

    monkeypatch.setattr(rc, "score_candidates", _fake_score)
    provider = FakeLLMProvider(response_text="NEUTRAL")

    candidates = [("a", "text one"), ("b", "text two")]
    suggestions = rc.suggest_equivalent_to_candidates(candidates, provider, _config())

    assert suggestions == []
    assert len(provider.calls) == 1  # LLM was called, just didn't confirm


def test_suggest_conflicts_with_candidates_never_writes_anything_only_returns_suggestions(monkeypatch):
    def _fake_score(query, others):
        from phase3.evaluation.foundations.similarity import ScoredCandidate
        return [ScoredCandidate(memory_id=mid, content=content, score=0.8) for mid, content in others]

    monkeypatch.setattr(rc, "score_candidates", _fake_score)
    provider = FakeLLMProvider(response_text="CONFLICTING")

    candidates = [("a", "My favorite color is blue."), ("b", "My favorite color is red.")]
    suggestions = rc.suggest_conflicts_with_candidates(candidates, provider, _config())

    assert len(suggestions) == 1
    assert suggestions[0].status == rc.STATUS_SUGGESTED_LOW_CONFIDENCE
    assert suggestions[0].llm_judge_label == "CONFLICTING"


def test_suggest_conflicts_with_candidates_below_gate_never_reach_the_llm(monkeypatch):
    def _fake_score(query, others):
        from phase3.evaluation.foundations.similarity import ScoredCandidate
        return [ScoredCandidate(memory_id=mid, content=content, score=0.1) for mid, content in others]

    monkeypatch.setattr(rc, "score_candidates", _fake_score)
    provider = FakeLLMProvider(response_text="CONFLICTING")

    candidates = [("a", "unrelated text one"), ("b", "unrelated text two")]
    suggestions = rc.suggest_conflicts_with_candidates(candidates, provider, _config())

    assert suggestions == []
    assert provider.calls == []


def test_suggest_conflicts_with_candidates_llm_says_not_conflicting_produces_no_suggestion(monkeypatch):
    def _fake_score(query, others):
        from phase3.evaluation.foundations.similarity import ScoredCandidate
        return [ScoredCandidate(memory_id=mid, content=content, score=0.8) for mid, content in others]

    monkeypatch.setattr(rc, "score_candidates", _fake_score)
    provider = FakeLLMProvider(response_text="NEUTRAL")

    candidates = [("a", "text one"), ("b", "text two")]
    suggestions = rc.suggest_conflicts_with_candidates(candidates, provider, _config())

    assert suggestions == []
    assert len(provider.calls) == 1
