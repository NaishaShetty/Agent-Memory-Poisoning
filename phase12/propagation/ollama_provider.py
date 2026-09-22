"""Phase 12 -- Propagation Rate follow-on (2026-09-21, explicitly authorized):
a real, non-mocked `LLMProvider` implementation backed by a real, locally
running Ollama server (`http://127.0.0.1:11434`, `llama2:7b`, confirmed
reachable directly -- `ollama list` shows it installed and running on this
machine).

WHY OLLAMA, NOT `LlamaServerProvider`
--------------------------------------------------------------------------------
This project's existing `LlamaServerProvider` (`phase3/evaluation/llm/provider.py`)
targets a specific `llama-server.exe` process serving the exact
`QWEN3_8B_Q4_K_M_IDENTITY` artifact at port 8811 -- confirmed NOT running on
this machine (connection refused). No `llama-server.exe` binary or GGUF
model file for that identity was found on this machine either. A real,
already-running local model WAS found (Ollama's `llama2:7b`, port 11434) --
this module is a thin, real adapter from Ollama's own real HTTP API to the
SAME `LLMProvider` interface every other real provider in this project
implements, so downstream code (the propagation-rate measurement) is not
coupled to which concrete backend served the real completion.

This is a REAL provider -- every `generate()` call makes a real HTTP request
to a real, running local inference server and returns its real output. It is
not a scripted/mocked provider (`_scripted_llm_provider()`, used throughout
Phase 4/11 for admission-decision tests where the LLM's role is a fixed,
disclosed stand-in) -- there is no script here, no canned response list.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any, Mapping, Sequence

from phase3.evaluation.llm.provider import (
    GenerationConfig,
    GenerationResult,
    LLMProvider,
    LLMProviderConnectionError,
    LLMProviderTimeoutError,
    LLMProviderUnexpectedResponseError,
)

OLLAMA_BASE_URL = "http://127.0.0.1:11434"
OLLAMA_MODEL = "llama2"


class OllamaProvider(LLMProvider):
    """Real `LLMProvider` backed by a real, running Ollama server. Does not
    start/stop/manage the Ollama process -- exactly the same "assumes it MAY
    be running, checks explicitly" discipline `LlamaServerProvider` already
    uses."""

    def __init__(self, base_url: str = OLLAMA_BASE_URL, model: str = OLLAMA_MODEL) -> None:
        self._base_url = base_url
        self._model = model

    def health_check(self, timeout_sec: float = 5.0) -> bool:
        try:
            req = urllib.request.Request(self._base_url.rstrip("/") + "/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                return resp.status == 200
        except Exception:
            return False

    def generate(self, messages: Sequence[Mapping[str, str]], config: GenerationConfig) -> GenerationResult:
        body = json.dumps({
            "model": self._model,
            "messages": list(messages),
            "stream": False,
            "options": {
                "temperature": config.temperature,
                "seed": config.seed,
                "num_predict": config.max_tokens,
                "num_ctx": config.n_ctx,
            },
        }).encode("utf-8")
        req = urllib.request.Request(
            self._base_url.rstrip("/") + "/api/chat", data=body,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        start = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=config.request_timeout_sec) as resp:
                raw = json.loads(resp.read())
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, TimeoutError) or "timed out" in str(exc.reason).lower():
                raise LLMProviderTimeoutError(str(exc)) from exc
            raise LLMProviderConnectionError(str(exc)) from exc
        except TimeoutError as exc:
            raise LLMProviderTimeoutError(str(exc)) from exc
        latency = time.perf_counter() - start

        if "message" not in raw or "content" not in raw.get("message", {}):
            raise LLMProviderUnexpectedResponseError(f"Unexpected Ollama response shape: {raw!r}")

        return GenerationResult(
            text=raw["message"]["content"],
            finish_reason=raw.get("done_reason", "unknown"),
            prompt_tokens=raw.get("prompt_eval_count"),
            completion_tokens=raw.get("eval_count"),
            latency_sec=latency,
            server_fingerprint=raw.get("model"),
            raw_response=raw,
        )

    def model_metadata(self) -> Mapping[str, Any]:
        return {"provider": "ollama", "model": self._model, "base_url": self._base_url}

    def configuration_fingerprint(self, config: GenerationConfig) -> str:
        return (
            f"ollama:{self._model}:temp={config.temperature}:seed={config.seed}:"
            f"max_tokens={config.max_tokens}:n_ctx={config.n_ctx}"
        )
