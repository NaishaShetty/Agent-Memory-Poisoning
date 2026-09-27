"""Phase 17 fix round 6 -- preference-hijack: attempt a CORROBORATION-based signal.

HYPOTHESIS: a genuine long-standing preference tends to be reinforced or referenced by
MULTIPLE real memories in a real conversation (the person mentions liking something more
than once, in different contexts); a hijack is typically introduced as ONE isolated,
freshly-planted assertion with no other memory in the store that independently supports
it. Tested directly: for each novel `preference_hijack` instance, is there any OTHER
real memory (drawn from the SAME held-out novel-mechanism pool's benign neighbourhood --
there is none by construction, so this is tested against the real Track-A LoCoMo store
instead, the closest real analogue of "a real store with many real memories about one
person") that corroborates it. If corroboration is rare for genuine preferences too, this
hypothesis is falsified honestly, not forced.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

import numpy as np

OUT = Path(__file__).parent / "data" / "preference_corroboration_results.json"


def _real_preference_statements(n: int = 30) -> List[str]:
    """Real, genuine LoCoMo QA pairs whose answer states a preference/habit (a
    conservative keyword filter over real gold answers, not fabricated)."""
    import json as _json

    raw = _json.loads(Path("data/raw/locomo/locomo10.json").read_text(encoding="utf-8"))
    kws = ("like", "enjoy", "love", "prefer", "favorite", "favourite", "hobby", "hobbies")
    out = []
    for sample in raw:
        for qa in sample.get("qa", []):
            a = str(qa.get("answer", "")).lower()
            if any(k in a for k in kws) and qa.get("question"):
                out.append(f"{qa['question']} {qa['answer']}")
            if len(out) >= n:
                return out
    return out


def run() -> dict:
    from phase17.novel_attacks import novel_records
    from phase17.semantic_detector import _embed

    hijacks = [r.text for r in novel_records() if r.family == "preference_hijack"]
    genuine = _real_preference_statements(30)

    # For each text, is there ANY other real preference statement in `genuine` (excluding
    # itself if present) with cosine similarity >= 0.55 -- a crude "another memory talks
    # about a similar preference" corroboration proxy.
    gvecs = _embed(genuine)

    def corroborated(text: str) -> float:
        v = _embed([text])[0]
        sims = gvecs @ v
        return float(sims.max())

    hijack_max_sim = [corroborated(t) for t in hijacks]
    genuine_max_sim = []
    for i, t in enumerate(genuine):
        others = np.delete(gvecs, i, axis=0)
        genuine_max_sim.append(float((others @ gvecs[i]).max()) if len(others) else 0.0)

    out = {
        "hijack_max_similarity_to_any_other_real_preference": hijack_max_sim,
        "genuine_max_similarity_to_any_OTHER_real_preference": genuine_max_sim,
        "hijack_mean": float(np.mean(hijack_max_sim)), "genuine_mean": float(np.mean(genuine_max_sim)),
        "separable": abs(float(np.mean(hijack_max_sim)) - float(np.mean(genuine_max_sim))) > 0.1,
    }
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    r = run()
    print(json.dumps({k: v for k, v in r.items() if not k.endswith("_sim")}, indent=1))
    print("hijack:", [round(x, 2) for x in r["hijack_max_similarity_to_any_other_real_preference"]])
    print("genuine:", [round(x, 2) for x in r["genuine_max_similarity_to_any_OTHER_real_preference"]])
    print("DONE")
