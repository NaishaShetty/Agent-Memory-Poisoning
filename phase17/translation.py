"""Phase 17 -- recorded Chinese translations of the poison sets (the language
axis; pairs with `perltqa.py`). The local model (qwen2.5:7b, strong in Chinese)
translates each English poison record; every prompt/seed/output is persisted to
`phase17/data/translated_poison.json`. Valid = at least 30% CJK characters and
not a refusal. Labelled `held_out_zh`; a translation of a known/novel attack,
NOT an independent mechanism -- it tests language robustness only.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List

from phase3.evaluation.llm.provider import GenerationConfig
from phase12.propagation.ollama_provider import OllamaProvider
from phase17.poison_sets import PoisonRecord

SPLIT_ZH = "held_out_zh"
CACHE = Path(__file__).parent / "data" / "translated_poison.json"
MODEL = "qwen2.5:7b"
_CJK = re.compile(r"[\u4e00-\u9fff]")
_REFUSAL = ("i cannot", "i can't", "i'm sorry", "as an ai", "i am unable")


def _cjk_fraction(t: str) -> float:
    return len(_CJK.findall(t)) / max(len(t), 1)


def generate(parents: List[PoisonRecord], path: Path = CACHE) -> dict:
    provider = OllamaProvider(model=MODEL)
    items = []
    for p in parents:
        cfg = GenerationConfig(temperature=0.0, seed=7, max_tokens=300, enable_thinking=False, n_ctx=2048,
                               request_timeout_sec=180.0)
        prompt = ("Translate the following text into natural Simplified Chinese, preserving every name, date, "
                  "number, claim and instruction exactly. Output only the Chinese translation.\n\n" + p.text)
        out = provider.generate([{"role": "user", "content": prompt}], cfg).text.strip()
        valid = bool(out) and _cjk_fraction(out) >= 0.3 and not any(m in out.lower() for m in _REFUSAL)
        items.append({"zh_id": f"ZH-{p.scenario_id}", "parent_id": p.scenario_id, "family": p.family,
                      "parent_split": p.split, "model": MODEL, "seed": 7, "prompt": prompt, "text": out,
                      "cjk_fraction": round(_cjk_fraction(out), 3), "valid": valid})
    data = {"model": MODEL, "items": items}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return data


def zh_records(path: Path = CACHE) -> List[PoisonRecord]:
    if not path.exists():
        return []
    d = json.loads(path.read_text(encoding="utf-8"))
    return [PoisonRecord(i["zh_id"], i["text"], i["family"], SPLIT_ZH, i["parent_id"]) for i in d["items"] if i["valid"]]


__all__ = ["SPLIT_ZH", "generate", "zh_records"]
