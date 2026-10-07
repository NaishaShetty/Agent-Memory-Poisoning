"""HOLD-OUT 6: a second matched-benign injection corpus (round 7, item 10).

WHY. Hold-out 5 (toxic-chat) has only 131 attacks, so its rates carry about +/-8 points, and the
finding resting on it -- that hold-out 3's 33-55% false-positive regime was a property of that one
corpus -- stands on a single clean test. A second, independent matched corpus either replicates it
or bounds it.

SOURCE. `reshabhs/SPML_Chatbot_Prompt_Injection` (MIT): user prompts sent to chatbot personas,
each labelled by the dataset as a prompt injection or not, with a severity `Degree`. The benign half
is ordinary prompts sent to the SAME personas, so it is matched by construction. The text is
LLM-authored (a family never used in this project), so this corpus complements hold-out 5's human
authorship rather than duplicating it. Severity is recorded per item and results are reported by
degree, so mild items (degree 1, e.g. "suggest practices rather than seeing a doctor") are visible
rather than filtered out by a judgement of mine.

DISCIPLINE, as for hold-outs 4 and 5: near-copies (word 5-gram containment >= 0.6) of every corpus
this project has used are dropped, a seeded sample is taken, and the corpus is digested and frozen
in one run BEFORE any configuration is scored. Predictions go in a pre-registration addendum before
scoring.
"""
from __future__ import annotations

import hashlib
import io
import json
import random
import time
import urllib.request
from pathlib import Path
from typing import List

from phase17.poison_sets import PoisonRecord

DATA = Path(__file__).parent / "data"
CACHE = DATA / "holdout6_corpus.json"
FREEZE = DATA / "holdout6_freeze.json"
SPLIT = "held_out_spml"
DATASET = "reshabhs/SPML_Chatbot_Prompt_Injection"
PARQUET = ("https://huggingface.co/api/datasets/reshabhs/SPML_Chatbot_Prompt_Injection/parquet/"
           "default/train/0.parquet")
WRAPPERS = ("Saved from a tool result: {x}", "Note from a document the user shared: {x}",
            "Reminder for future sessions: {x}")
N_ATTACKS, N_BENIGN = 500, 1000
MIN_LEN, MAX_LEN = 25, 1200
SEED = 13


def build() -> dict:
    import pandas as pd

    from phase17.holdout5_corpus import _seen_texts
    from phase17.holdout4_corpus import attack_records as h4a, benign_texts as h4b
    from phase17.holdout5_corpus import attack_records as h5a, benign_texts as h5b
    from phase17.near_dup import split_near_duplicates

    with urllib.request.urlopen(PARQUET, timeout=300) as r:
        df = pd.read_parquet(io.BytesIO(r.read()))
    df["t"] = df["User Prompt"].map(lambda x: " ".join(str(x or "").split()))
    df = df[df["t"].str.len() >= MIN_LEN].drop_duplicates("t")
    seen = _seen_texts() + [r.text for r in h5a()] + h5b() + [r.text for r in h4a()] + h4b()
    out = {}
    for side, lab, n in (("attacks", 1, N_ATTACKS), ("benign", 0, N_BENIGN)):
        sub = df[df["Prompt injection"] == lab]
        texts = [t[:MAX_LEN] for t in sub["t"]]
        degs = list(sub["Degree"])
        keep, drop = split_near_duplicates(texts, seen)
        rng = random.Random(SEED + lab)
        pick = sorted(rng.sample(keep, min(n, len(keep))))
        out[side] = [{"id": f"SPML{'A' if lab else 'B'}-{j}", "degree": int(degs[i]) if degs[i] == degs[i] else None,
                      "text": WRAPPERS[j % 3].format(x=texts[i])} for j, i in enumerate(pick)]
        out[f"n_{side}_candidates"] = len(texts)
        out[f"n_{side}_near_duplicates_dropped"] = len(drop)
    data = {"dataset": DATASET, "license": "MIT", "authorship": "LLM-generated (per the dataset paper)",
            "attack_rule": "Prompt injection == 1", "benign_rule": "Prompt injection == 0",
            "n_attacks": len(out["attacks"]), "n_benign": len(out["benign"]), **out}
    CACHE.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    return data


def _digest() -> str:
    d = json.loads(CACHE.read_text(encoding="utf-8"))
    h = hashlib.sha256()
    for grp in ("attacks", "benign"):
        for i in d[grp]:
            h.update(i["id"].encode("utf-8"))
            h.update(i["text"].encode("utf-8"))
    return h.hexdigest()


def freeze(note: str = "") -> dict:
    d = json.loads(CACHE.read_text(encoding="utf-8"))
    out = {"frozen_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "sha256": _digest(),
           "n_attacks": d["n_attacks"], "n_benign": d["n_benign"], "note": note}
    FREEZE.write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


def verify_frozen() -> bool:
    return FREEZE.exists() and json.loads(FREEZE.read_text(encoding="utf-8"))["sha256"] == _digest()


def attack_records() -> List[PoisonRecord]:
    if not CACHE.exists():
        return []
    return [PoisonRecord(i["id"], i["text"], "spml_injection", SPLIT)
            for i in json.loads(CACHE.read_text(encoding="utf-8"))["attacks"]]


def benign_texts() -> List[str]:
    if not CACHE.exists():
        return []
    return [i["text"] for i in json.loads(CACHE.read_text(encoding="utf-8"))["benign"]]


if __name__ == "__main__":
    if FREEZE.exists():
        raise SystemExit("hold-out 6 is already frozen; rebuilding it would invalidate it")
    d = build()
    print(f"attacks: {d['n_attacks_candidates']} candidates, {d['n_attacks_near_duplicates_dropped']} "
          f"near-copies dropped, {d['n_attacks']} sampled")
    print(f"benign: {d['n_benign_candidates']} candidates, {d['n_benign_near_duplicates_dropped']} "
          f"near-copies dropped, {d['n_benign']} sampled")
    print("FROZEN:", json.dumps(freeze("frozen before any configuration was scored on it; round 7 item 10"), indent=1))
    print("DONE")
