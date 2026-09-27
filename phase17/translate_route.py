"""Fix round 5 -- language routing by TRANSLATION. The stacked detector's embedding is English-only, so
CJK text used to fall back to the judge alone (23/84 Chinese poison excluded vs 35/60-style English
strength). Route: translate CJK text to English with the local multilingual model (temperature 0,
cached by text hash), then score the translation with the same English detector. One extra LLM call,
only for CJK text."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

CACHE = Path(__file__).parent / "data" / "translate_route_cache.json"
_c = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
_n = 0
PROMPT = ("Translate the following memory note into plain English, preserving every name, number, claim and instruction "
          "exactly. Output only the translation.\n\n{t}")


def to_english(text: str) -> str:
    global _n
    k = hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]
    if k not in _c:
        from phase12.propagation.ollama_provider import OllamaProvider
        from phase3.evaluation.llm.provider import GenerationConfig

        cfg = GenerationConfig(temperature=0.0, seed=7, max_tokens=300, enable_thinking=False, n_ctx=2048, request_timeout_sec=180.0)
        _c[k] = OllamaProvider(model="qwen2.5:7b").generate([{"role": "user", "content": PROMPT.format(t=text[:1500])}], cfg).text.strip()
        _n += 1
        if _n % 50 == 0:
            save()
    return _c[k]


def save() -> None:
    disk = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    disk.update(_c)
    CACHE.write_text(json.dumps(disk, ensure_ascii=False), encoding="utf-8")
