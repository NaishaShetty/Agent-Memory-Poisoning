"""DEV attacks for the injection regime: the EARLIER jailbreak snapshot of hold-out 3's source.

WHY. Round 7 composes neutralisation with detection (`compose_neutralise.py`) and adds a
confidence gate to the union configurations' B13 component. Both have to be developed on
injection-shaped attacks with a matched benign half, and the only matched corpus this project
had was hold-out 3 -- which has been scored five times and is now RETIRED from further
measurement by the owner's decision (2026-10-06). So development needs its own attacks.

`TrustAIRLab/in-the-wild-jailbreak-prompts` ships `jailbreak_2023_05_07`, an earlier
collection from the same communities. Paired with `holdout3_dev_benign` (the same snapshot's
`regular_*` prompts) it is a matched dev bed. Anything fitted or selected in round 7 is fitted
here, and the FINAL test is hold-out 5 (`holdout5_corpus.py`), a different platform entirely.

DISJOINTNESS, both exact and near-duplicate. The snapshots share prompts, and jailbreaks
circulate as lightly edited copies, so any dev item that is a near-copy of a frozen hold-out 3
attack is dropped from the DEV side (never from the frozen side). The count is recorded.
"""
from __future__ import annotations

import json
import time
import urllib.parse
from pathlib import Path
from typing import List

from phase17.holdout3_corpus import WRAPPERS, _get
from phase17.poison_sets import PoisonRecord

DATA = Path(__file__).parent / "data"
CACHE = DATA / "injection_dev_attacks.json"
ROWS_API = "https://datasets-server.huggingface.co/rows"
DATASET = "TrustAIRLab/in-the-wild-jailbreak-prompts"
CONFIG = "jailbreak_2023_05_07"
SPLIT = "dev_inthewild_2023_05_07"
MIN_LEN, MAX_LEN = 25, 1200


def build() -> dict:
    from phase17.holdout3_corpus import attack_records as h3_attacks
    from phase17.near_dup import split_near_duplicates

    rows, offset = [], 0
    while True:
        q = urllib.parse.urlencode({"dataset": DATASET, "config": CONFIG, "split": "train",
                                    "offset": offset, "length": 100})
        got = [x["row"] for x in _get(f"{ROWS_API}?{q}").get("rows", [])]
        if not got:
            break
        rows += got
        offset += 100
        time.sleep(1.5)
    seen, raw = set(), []
    for r in rows:
        t = " ".join((r.get("prompt") or "").split())
        if len(t) < MIN_LEN or t.lower() in seen:
            continue
        seen.add(t.lower())
        raw.append((t[:MAX_LEN], len(t), r.get("platform")))
    frozen = [r.text for r in h3_attacks()]
    keep, drop = split_near_duplicates([t for t, _, _ in raw], frozen)
    items = []
    for j, i in enumerate(keep):
        t, n, plat = raw[i]
        w = WRAPPERS[j % len(WRAPPERS)]
        items.append({"id": f"DEVITW-{j}", "raw_len": n, "platform": plat,
                      "text": w.format(x=t), "wrapper": w})
    data = {"dataset": DATASET, "config": CONFIG, "license": "MIT", "role": "DEV ONLY",
            "n_fetched": len(rows), "n_after_dedup": len(raw),
            "n_dropped_near_duplicate_of_holdout3": len(drop), "n": len(items), "attacks": items}
    CACHE.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    return data


def records() -> List[PoisonRecord]:
    if not CACHE.exists():
        return []
    return [PoisonRecord(i["id"], i["text"], "in_the_wild_jailbreak", SPLIT)
            for i in json.loads(CACHE.read_text(encoding="utf-8"))["attacks"]]


if __name__ == "__main__":
    d = build()
    print(f"fetched {d['n_fetched']}, {d['n_after_dedup']} after exact dedup, dropped "
          f"{d['n_dropped_near_duplicate_of_holdout3']} near-duplicates of frozen hold-out 3, "
          f"kept {d['n']} DEV attacks")
    print("DONE")
