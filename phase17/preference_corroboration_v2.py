"""Phase 17 fix round 4 -- preference-hijack corroboration, DECONFOUNDED.

ROOT CAUSE of round 3's inconclusive result (`preference_corroboration.py`): comparing
LLM-authored `preference_hijack` texts against a DIFFERENT set of real human-written
LoCoMo text confounds "is this corroborated" with "is this LLM-generated" -- the two
classes differ in authorship style, not just in the property being tested.

FIX: test the corroboration hypothesis using ONLY real, human-written LoCoMo dialogue
turns on BOTH sides, from the SAME real conversation this project's own DSRM/FARMA/
MPBENCH poison scenarios were injected into (LoCoMo sample 0): for every real
preference-shaped turn (a keyword filter over real dialogue, not fabricated), count how
many OTHER real turns in the SAME conversation independently corroborate it (embedding
similarity >= a fixed bar). A genuinely repeated preference should have count >= 1 more
often than an isolated, one-off statement -- and this project's own REAL poison text
(injected once, referencing nothing else in the conversation) is exactly the "isolated,
one-off statement" case, so it can be tested DIRECTLY, with no LLM-authored proxy needed
at all.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Tuple

import numpy as np

OUT = Path(__file__).parent / "data" / "preference_corroboration_v2_results.json"
LOCOMO = Path("data/raw/locomo/locomo10.json")
PREF_KEYWORDS = ("like", "likes", "liked", "enjoy", "enjoys", "loves", "love", "prefer", "prefers",
                 "favorite", "favourite", "hobby", "hobbies", "into ", "fan of", "passion")


def _real_conversation_turns(sample_idx: int) -> List[str]:
    raw = json.loads(LOCOMO.read_text(encoding="utf-8"))
    conv = raw[sample_idx]["conversation"]
    out = []
    for k in sorted((kk for kk in conv if kk.startswith("session_") and not kk.endswith("date_time")),
                    key=lambda s: int(s.split("_")[1])):
        for t in conv[k]:
            out.append(t["text"])
    return out


def run(sample_idx: int = 0, sim_bar: float = 0.6) -> dict:
    from phase17.poison_sets import original_records
    from phase17.semantic_detector import _embed

    turns = _real_conversation_turns(sample_idx)
    pref_turns = [t for t in turns if any(k in t.lower() for k in PREF_KEYWORDS)]
    vecs = _embed(pref_turns)
    n = len(pref_turns)
    corrob_counts = []
    for i in range(n):
        sims = vecs @ vecs[i]
        sims[i] = -1.0
        corrob_counts.append(int((sims >= sim_bar).sum()))

    isolated = sum(1 for c in corrob_counts if c == 0)
    corroborated = sum(1 for c in corrob_counts if c >= 1)

    # Direct test: this benchmark's OWN real DSRM/FARMA/MPBENCH poison scenarios, injected
    # into this SAME real conversation (sample 0), against the SAME real preference-turn set.
    poison_texts = [r.text for r in original_records() if r.family in ("dsrm", "farma", "mpbench")]
    pvecs = _embed(poison_texts)
    poison_corrob = []
    for pv in pvecs:
        sims = vecs @ pv
        poison_corrob.append(int((sims >= sim_bar).sum()))

    out = {
        "sample_idx": sample_idx, "sim_bar": sim_bar, "n_real_preference_turns": n,
        "corrob_counts": corrob_counts, "n_isolated(count=0)": isolated, "n_corroborated(count>=1)": corroborated,
        "isolated_rate": isolated / n if n else None,
        "poison_texts_n": len(poison_texts), "poison_corrob_counts": poison_corrob,
        "poison_isolated(count=0)": sum(1 for c in poison_corrob if c == 0),
        "conclusion": None,
    }
    # Is the real poison (which we KNOW is a one-off, isolated, injected claim) actually
    # more often "isolated" (count=0) than a real, genuine preference statement is?
    if n:
        out["conclusion"] = (
            f"real poison isolated-rate={out['poison_isolated(count=0)']}/{len(poison_texts)} vs "
            f"real genuine-preference isolated-rate={isolated}/{n}"
        )
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    r = run()
    print(json.dumps({k: v for k, v in r.items() if not k.endswith("counts")}, indent=1))
    print("genuine preference corrob counts:", r["corrob_counts"])
    print("poison corrob counts:", r["poison_corrob_counts"])
    print("DONE")
