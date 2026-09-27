"""Phase 17 Workstream A (unseen model family) -- a real, minimal `LLMProvider` backed by
Google's Gemini API free tier, added on explicit user instruction to extend the
"unseen model family" generalization axis beyond the two local Ollama models this
project otherwise uses everywhere.

The API key is read ONLY from the `GEMINI_API_KEY` environment variable -- never
hardcoded, never written to any file this module controls, never logged or echoed. If
the variable is unset, `health_check()` returns False and callers should skip this
provider rather than fail loudly (the same "assumes it MAY be running, checks
explicitly" discipline `LlamaServerProvider`/`OllamaProvider` already use for their own
optional backends).

This is a REAL, live network provider: every `generate()` call is a real HTTPS request
to Google's `generativelanguage.googleapis.com`, using whatever real free-tier quota and
rate limits Google enforces server-side -- not a scripted/mocked provider.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Mapping, Optional, Sequence

from phase3.evaluation.llm.provider import (
    GenerationConfig,
    GenerationResult,
    LLMProvider,
    LLMProviderConnectionError,
    LLMProviderTimeoutError,
    LLMProviderUnexpectedResponseError,
)

DEFAULT_MODEL = "gemini-3.5-flash-lite"  # gemini-3.8-flash's free-tier daily quota (20/day)
# was exhausted by this module's own earlier smoke-testing; -flash-lite is a distinct
# model with its own separate free-tier quota bucket, confirmed working directly.
BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
_last_call_ts = [0.0]  # process-wide throttle -- the free tier's real RPM ceiling is low


class GeminiProvider(LLMProvider):
    """Real `LLMProvider` backed by the real, hosted Gemini API (free tier).
    `api_key_env` names the environment variable holding the key -- never the key
    itself, so this class never carries a literal secret in any of its fields."""

    def __init__(self, model: str = DEFAULT_MODEL, api_key_env: str = "GEMINI_API_KEY", min_interval_sec: float = 6.0) -> None:
        self._model = model
        self._api_key_env = api_key_env
        self._min_interval_sec = min_interval_sec

    def _api_key(self) -> str:
        key = os.environ.get(self._api_key_env)
        if not key:
            raise LLMProviderConnectionError(f"{self._api_key_env} is not set; GeminiProvider cannot be used.")
        return key

    def health_check(self, timeout_sec: float = 5.0) -> bool:
        key = os.environ.get(self._api_key_env)
        if not key:
            return False
        try:
            req = urllib.request.Request(f"{BASE_URL}/models?key={key}", method="GET")
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                return resp.status == 200
        except Exception:
            return False

    def generate(self, messages: Sequence[Mapping[str, str]], config: GenerationConfig) -> GenerationResult:
        key = self._api_key()
        # Gemini has no separate "system" role in this minimal path -- fold any system
        # message into the first user turn, exactly the same flattening this project's
        # own `_build_judge_messages()`-style single-user-turn prompts already use.
        parts = []
        for m in messages:
            prefix = "" if m.get("role") == "user" else f"[{m.get('role', 'user')}] "
            parts.append(f"{prefix}{m.get('content', '')}")
        # Gemini's API charges a small fixed per-call token overhead even with
        # thinkingBudget=0 (confirmed directly: max_tokens=8/20 returned finishReason
        # MAX_TOKENS with zero visible text; max_tokens=100 returned real text with no
        # overhead at all) -- floor at 32 so a caller's local-model-tuned max_tokens
        # (e.g. 8, used everywhere for a YES/NO judge call) does not silently starve
        # every Gemini call of visible output.
        max_tokens = max(config.max_tokens, 32)
        gen_config: Dict[str, Any] = {"temperature": config.temperature, "maxOutputTokens": max_tokens}
        if self._model not in ("gemini-3.5-flash-lite",):  # this model rejects thinkingConfig (400 INVALID_ARGUMENT), confirmed directly
            gen_config["thinkingConfig"] = {"thinkingBudget": 0}
        body = json.dumps({"contents": [{"parts": [{"text": "\n\n".join(parts)}]}], "generationConfig": gen_config}).encode("utf-8")
        url = f"{BASE_URL}/models/{self._model}:generateContent?key={key}"
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
        # Proactive process-wide throttle -- the free tier's real RPM ceiling is low
        # enough that back-to-back calls hit 429 even with per-call retries; confirmed
        # directly (repeated 429s on a 40-call burst before this throttle was added).
        wait = self._min_interval_sec - (time.time() - _last_call_ts[0])
        if wait > 0:
            time.sleep(wait)
        t0 = time.time()
        raw = None
        last_exc: Optional[Exception] = None
        # Free-tier 503 ("model overloaded")/429 (rate limit) are transient and common
        # on the free tier -- retry with real backoff rather than failing the whole call
        # on the first bad response, mirroring the retry discipline other real network
        # providers in this project already apply to their own transient errors.
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=config.request_timeout_sec) as resp:
                    raw = json.loads(resp.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as exc:
                last_exc = exc
                if exc.code in (429, 503) and attempt < 3:
                    time.sleep(6.0 * (attempt + 1))
                    continue
                if exc.code == 429:
                    raise LLMProviderTimeoutError(f"Gemini rate-limited (free tier): {exc}") from exc
                raise LLMProviderConnectionError(f"Gemini request failed: {exc}") from exc
            except urllib.error.URLError as exc:
                raise LLMProviderConnectionError(f"Gemini request failed: {exc}") from exc
            finally:
                _last_call_ts[0] = time.time()
        if raw is None:
            raise LLMProviderConnectionError(f"Gemini request failed after retries: {last_exc}")
        latency = time.time() - t0
        try:
            cands = raw["candidates"]
            text = "".join(p.get("text", "") for p in cands[0].get("content", {}).get("parts", []))
            finish = cands[0].get("finishReason", "UNKNOWN")
        except (KeyError, IndexError) as exc:
            raise LLMProviderUnexpectedResponseError(f"Unexpected Gemini response shape: {raw!r}") from exc
        usage = raw.get("usageMetadata", {})
        return GenerationResult(
            text=text, finish_reason=finish, prompt_tokens=usage.get("promptTokenCount"),
            completion_tokens=usage.get("candidatesTokenCount"), latency_sec=latency,
            server_fingerprint=f"gemini-api:{self._model}", raw_response=raw,
        )

    def model_metadata(self) -> Mapping[str, Any]:
        return {"provider": "google-gemini-api", "model": self._model, "backend": "hosted (free tier)"}

    def configuration_fingerprint(self, config: GenerationConfig) -> str:
        return f"gemini-api:{self._model}:temp={config.temperature}:max_tokens={config.max_tokens}"


__all__ = ["GeminiProvider", "DEFAULT_MODEL"]
