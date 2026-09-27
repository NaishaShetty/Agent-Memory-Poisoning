"""Tests for GeminiProvider that do not require a live network call or API key."""
import os

import pytest

from phase17.gemini_provider import GeminiProvider


def test_health_check_false_without_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert GeminiProvider().health_check() is False


def test_generate_raises_without_key(monkeypatch):
    from phase3.evaluation.llm.provider import GenerationConfig
    from phase3.evaluation.llm.provider import LLMProviderConnectionError

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    p = GeminiProvider()
    cfg = GenerationConfig(temperature=0.0, seed=1, max_tokens=8, enable_thinking=False, n_ctx=1024, request_timeout_sec=5.0)
    with pytest.raises(LLMProviderConnectionError):
        p.generate([{"role": "user", "content": "hi"}], cfg)


def test_never_reads_key_from_anywhere_but_env(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    p = GeminiProvider()
    assert p._api_key() == "test-key-not-real"
    assert "test-key-not-real" not in repr(p)  # the key is never captured into an instance field
