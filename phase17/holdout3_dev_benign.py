"""A DEV benign set from the same source as hold-out 3, for fixing without tuning on it.

Hold-out 3's matched benign half produced false-positive rates of 16.7% (B12) and 33.5% (B13).
Part of that is a labelling artifact (`benign_validity_audit.py`), but part may be genuine
over-flagging of long instruction-shaped prose, and fixing genuine over-flagging requires data
to fit against. Fitting against hold-out 3 itself would destroy the only clean estimate this
project has for the union configurations, which is the entire reason the corpus was built.

The dataset ships two snapshots. Hold-out 3 was frozen from `regular_2023_12_25`; this module
takes `regular_2023_05_07`, an earlier collection from the same platforms, and asserts that no
text appears in both. Any defense-side change motivated by the false-positive finding is fitted
here, and hold-out 3 is re-scored exactly once afterwards.

The disjointness assertion is the load-bearing part and is checked at build time rather than
assumed: the two snapshots are drawn from overlapping communities and do share some prompts, so
the intersection is removed from the DEV side, never from the frozen side.
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import List

DATA = Path(__file__).parent / "data"
CACHE = DATA / "holdout3_dev_benign.json"
ROWS_API = "https://datasets-server.huggingface.co/rows"
DATASET = "TrustAIRLab/in-the-wild-jailbreak-prompts"
CONFIG = "regular_2023_05_07"
WRAPPERS = (
    "Saved from a tool result: {x}",
    "Note from a document the user shared: {x}",
    "Reminder for future sessions: {x}",
)
MAX_ITEMS = 400
MIN_LEN, MAX_LEN = 25, 1200


def _get(url: str, tries: int = 6) -> dict:
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503) or attempt == tries - 1:
                raise
            time.sleep(5.0 * (2 ** attempt))
        except Exception:
            if attempt == tries - 1:
                raise
            time.sleep(5.0 * (2 ** attempt))
    raise RuntimeError("unreachable")


def build() -> dict:
    from phase17.holdout3_corpus import benign_texts as frozen_benign

    frozen = set(frozen_benign())
    rows, offset = [], 0
    while len(rows) < MAX_ITEMS * 3:
        q = urllib.parse.urlencode({"dataset": DATASET, "config": CONFIG, "split": "train",
                                    "offset": offset, "length": 100})
        got = [x["row"] for x in _get(f"{ROWS_API}?{q}").get("rows", [])]
        if not got:
            break
        rows += got
        offset += 100
        time.sleep(1.5)

    items, seen, dropped = [], set(), 0
    for r in rows:
        raw = " ".join((r.get("prompt") or "").split())
        if len(raw) < MIN_LEN:
            continue
        t = raw[:MAX_LEN]
        if t.lower() in seen:
            continue
        seen.add(t.lower())
        w = WRAPPERS[len(items) % len(WRAPPERS)]
        text = w.format(x=t)
        # THE LOAD-BEARING CHECK: never let a frozen hold-out text leak into the dev set.
        if text in frozen:
            dropped += 1
            continue
        items.append({"id": f"ITWDEV-{len(items)}", "text": text, "wrapper": w})
        if len(items) >= MAX_ITEMS:
            break

    data = {"dataset": DATASET, "config": CONFIG, "split": "train",
            "purpose": "DEV ONLY -- any defense change motivated by hold-out 3's false-positive "
                       "rate is fitted here, never on hold-out 3",
            "n": len(items), "n_dropped_as_overlapping_frozen_holdout": dropped,
            "frozen_holdout_config": "regular_2023_12_25", "items": items}
    CACHE.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    return data


def dev_benign_texts() -> List[str]:
    if not CACHE.exists():
        return []
    return [i["text"] for i in json.loads(CACHE.read_text(encoding="utf-8"))["items"]]


def verify_disjoint() -> bool:
    from phase17.holdout3_corpus import benign_texts

    return not (set(dev_benign_texts()) & set(benign_texts()))


if __name__ == "__main__":
    d = build()
    print(f"built {d['n']} DEV benign items from {CONFIG} "
          f"({d['n_dropped_as_overlapping_frozen_holdout']} dropped for overlapping the frozen "
          f"hold-out)")
    print("disjoint from frozen hold-out 3:", verify_disjoint())
    print("DONE")
