"""DEV benign for the injection regime, from the same platform as hold-out 5 but disjoint from it.

WHY. Round 7's injection-regime work (neutralisation composed with detection; B20/B21, the
union configurations without B13's content detector) needs a matched benign set to develop
against. Hold-out 3's "dev snapshot" turned out to be the hold-out under a different wrapper
(ROUND7_LOG R7-1), and hold-out 3 is retired. Hold-out 5 sampled 1,000 of toxic-chat's 8,199
non-toxic, non-jailbreak prompts; the remaining ~7,000 are the same distribution and are not in
the hold-out, which is an ordinary train/test split of one source.

DISJOINTNESS is checked the way R7-1 showed it must be: wrappers stripped, near-duplicates
(word 5-gram containment >= 0.6) against BOTH halves of frozen hold-out 5 dropped from the DEV
side. The count is recorded, and `verify_disjoint()` re-checks it.

There is no matched DEV attack set from this platform: every toxic-chat jailbreak is in hold-out
5. Dev attacks for the injection regime are therefore the 266 externally-authored dev attacks
(`external_attacks`), which are injection-shaped but from other sources. That asymmetry is stated
wherever a dev number is reported.
"""
from __future__ import annotations

import json
import random
from pathlib import Path
from typing import List

DATA = Path(__file__).parent / "data"
CACHE = DATA / "toxicchat_dev_benign.json"
N = 400
SEED = 11


def build() -> dict:
    from phase17.holdout5_corpus import (MAX_LEN, MIN_LEN, WRAPPERS, _clean, _rows, attack_records,
                                         benign_texts, verify_frozen)
    from phase17.near_dup import split_near_duplicates

    assert verify_frozen(), "hold-out 5 must be frozen before a dev split is drawn beside it"
    df = _rows()
    df["t"] = df["user_input"].map(_clean)
    df = df[df["t"].str.len() >= MIN_LEN].drop_duplicates("t")
    ben = [t[:MAX_LEN] for t in df[(df["jailbreaking"] == 0) & (df["toxicity"] == 0)]["t"]]
    frozen = benign_texts() + [r.text for r in attack_records()]
    keep, drop = split_near_duplicates(ben, frozen)
    rng = random.Random(SEED)
    pick = sorted(rng.sample(keep, min(N, len(keep))))
    items = [{"id": f"TXCDEV-{j}", "text": WRAPPERS[j % len(WRAPPERS)].format(x=ben[i])}
             for j, i in enumerate(pick)]
    data = {"source": "lmsys/toxic-chat toxicchat0124, non-toxic non-jailbreak prompts NOT in "
                      "hold-out 5", "role": "DEV ONLY", "license": "CC-BY-NC-4.0",
            "n_candidates": len(ben), "n_dropped_near_duplicate_of_holdout5": len(drop),
            "n": len(items), "items": items}
    CACHE.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    return data


def dev_benign_texts() -> List[str]:
    if not CACHE.exists():
        return []
    return [i["text"] for i in json.loads(CACHE.read_text(encoding="utf-8"))["items"]]


def verify_disjoint() -> bool:
    from phase17.holdout5_corpus import attack_records, benign_texts
    from phase17.near_dup import split_near_duplicates

    _, drop = split_near_duplicates(dev_benign_texts(),
                                    benign_texts() + [r.text for r in attack_records()])
    return not drop


if __name__ == "__main__":
    d = build()
    print(f"{d['n_candidates']} candidates; {d['n_dropped_near_duplicate_of_holdout5']} near-copies "
          f"of hold-out 5 dropped (this includes the 1,000 hold-out items themselves); kept {d['n']}")
    print("disjoint from hold-out 5:", verify_disjoint())
    print("DONE")
