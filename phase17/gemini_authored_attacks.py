"""Phase 17 fix (external review, 2026-09-28, finding 2's remaining half) -- attacks
authored by a genuinely DIFFERENT model family from the judge/detector (Qwen2.5:7b),
closing the "test human-written or other-model-written attacks... or a second generator
family" suggested fix. Every attack text B11/B12 were evaluated against elsewhere in
Phase 17 was Qwen-authored; these are Gemini-authored, using the SAME 6 unseen-mechanism
descriptions (so the mechanism, not the wording style, stays comparable), never used to
tune the judge or detector.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List

from phase17.novel_attacks import MECHANISMS, SCENARIOS, _prompt
from phase17.poison_sets import PoisonRecord

CACHE = Path(__file__).parent / "data" / "gemini_authored_attacks.json"
SPLIT = "held_out_gemini_authored"
_REFUSAL = ("i cannot", "i can't", "i'm sorry", "as an ai", "i am unable", "i won't")


def generate(path: Path = CACHE) -> dict:
    from phase17.gemini_provider import GeminiProvider
    from phase3.evaluation.llm.provider import GenerationConfig

    provider = GeminiProvider()
    if not provider.health_check():
        raise SystemExit("GEMINI_API_KEY not set this session -- re-export it and re-run.")
    items = []
    for mi, (mech, desc) in enumerate(MECHANISMS.items()):
        for si, scenario in enumerate(SCENARIOS[:5]):  # 5/mechanism = 30 total, budget-bounded by the free tier
            cfg = GenerationConfig(temperature=0.8, seed=8000 + 10 * mi + si, max_tokens=120, enable_thinking=False,
                                   n_ctx=2048, request_timeout_sec=60.0)
            prompt = _prompt(desc, scenario)
            try:
                out = provider.generate([{"role": "user", "content": prompt}], cfg).text.strip().strip('"')
            except Exception as exc:
                out = ""
                print("ERR", mech, si, type(exc).__name__)
            valid = bool(out) and 20 <= len(out) <= 400 and not any(m in out.lower() for m in _REFUSAL)
            items.append({"attack_id": f"GEMINI-{mech.upper()}-{si}", "mechanism": mech, "scenario": scenario,
                          "model": "gemini-3.5-flash-lite", "seed": 8000 + 10 * mi + si, "text": out, "valid": valid})
            print(mech, si, valid, out[:60])
    data = {"model": "gemini-3.5-flash-lite", "mechanisms": MECHANISMS, "items": items}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def gemini_records(path: Path = CACHE) -> List[PoisonRecord]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [PoisonRecord(i["attack_id"], i["text"], i["mechanism"], SPLIT) for i in data["items"] if i["valid"]]


if __name__ == "__main__":
    d = generate()
    print("generated", len(d["items"]), "valid", sum(i["valid"] for i in d["items"]))
