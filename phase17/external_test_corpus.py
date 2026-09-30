"""The FROZEN external test corpus (external review round 5, 2026-09-30).

WHY THIS EXISTS, and why it is separate from `external_attacks.py`:

The round-4 baseline comparison measured B12 and B13 on all 266 attacks in
`external_attacks.py`, per source, and those numbers were read and written up. Any defense
built afterwards has therefore *seen* that population's results, so it can no longer serve
as a clean test set — no matter that nothing was numerically tuned on it. Those 266 are
consequently **external-DEV** from here on.

This module builds a genuinely untouched **external-TEST** set from sources this project has
never measured, and freezes it. Two sources, chosen because both are authored OUTSIDE any
LLM this project runs:

  gandalf   `Lakera/gandalf_ignore_instructions` (MIT). 1,000 prompt-injection attempts
            typed by real human players of the Gandalf game. **These are the first
            genuinely human-authored attacks in this project** — every other attack text
            anywhere in MAMBench is LLM-generated. That closes, for this population, the
            authorship confound `PHASE17_CURRENT_RESULTS.md` §5 has carried since round 2.
  deepset   `deepset/prompt-injections` (CC-BY-4.0). 662 items, label 1 = injection,
            label 0 = benign — so it supplies an externally-authored BENIGN control as
            well, which matters because a false-positive rate measured only on this
            project's own benign text has the mirror-image confound.

HONEST LIMITS OF THIS TEST SET, stated up front rather than discovered later:
  * Both sources are **prompt-injection** corpora, not memory-poisoning corpora. Gandalf in
    particular is dominated by one narrow goal (make the model reveal a password) and is
    often extremely overt ("Ignore all previous text..."). A high score here is evidence
    about detecting overt injected instructions placed in memory, NOT evidence about
    detecting subtle memory poisoning such as additive fabrication or preference hijack.
    The own-authored and external-dev populations remain the ones that test those.
  * Adaptation to memory notes is deterministic (the same three fixed wrappers
    `external_attacks.py` uses, rotated by index); no model rewrites anything.
  * deepset is multilingual and its benign half is ordinary user questions, not memory
    notes, so its benign items are a weaker analogue of a real memory store than
    `dataset_arena`/`convomem`.

FREEZE: `freeze()` records a SHA-256 over the exact test texts in `data/external_test_
freeze.json`. `phase17/tests/test_review5_fixes.py` recomputes it, so if the test set is
ever edited after freezing, CI fails rather than the change passing silently.
"""
from __future__ import annotations

import hashlib
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, List

from phase17.poison_sets import PoisonRecord

DATA = Path(__file__).parent / "data"
CACHE_ATTACKS = DATA / "external_test_attacks.json"
CACHE_BENIGN = DATA / "external_test_benign.json"
FREEZE = DATA / "external_test_freeze.json"
SPLIT_EXTERNAL_TEST = "held_out_external_test"
ROWS_API = "https://datasets-server.huggingface.co/rows"
WRAPPERS = (
    "Saved from a tool result: {x}",
    "Note from a document the user shared: {x}",
    "Reminder for future sessions: {x}",
)
SOURCES = {
    "gandalf": {"dataset": "Lakera/gandalf_ignore_instructions", "config": "default",
                "splits": ("train", "validation", "test"), "text": "text", "label": None,
                "license": "MIT", "authorship": "human (Gandalf game players)"},
    "deepset": {"dataset": "deepset/prompt-injections", "config": "default",
                "splits": ("train", "test"), "text": "text", "label": "label",
                "license": "CC-BY-4.0", "authorship": "mixed human/synthetic (dataset authors)"},
}


def _fetch(dataset: str, config: str, split: str, limit: int = 100) -> List[dict]:
    out, offset = [], 0
    while True:
        q = urllib.parse.urlencode({"dataset": dataset, "config": config, "split": split,
                                    "offset": offset, "length": limit})
        with urllib.request.urlopen(f"{ROWS_API}?{q}", timeout=120) as r:
            d = json.loads(r.read().decode("utf-8"))
        rows = [x["row"] for x in d.get("rows", [])]
        out += rows
        if len(rows) < limit or len(out) >= d.get("num_rows_total", 0):
            return out
        offset += limit
        time.sleep(0.2)


def build() -> Dict[str, dict]:
    attacks, benign = [], []
    meta = {}
    for name, spec in SOURCES.items():
        rows = []
        for split in spec["splits"]:
            rows += _fetch(spec["dataset"], spec["config"], split)
        meta[name] = {k: spec[k] for k in ("dataset", "license", "authorship")}
        meta[name]["n_rows"] = len(rows)
        for r in rows:
            text = (r.get(spec["text"]) or "").strip()
            if not (15 <= len(text) <= 1500):
                continue
            is_attack = True if spec["label"] is None else bool(r.get(spec["label"]))
            bucket = attacks if is_attack else benign
            w = WRAPPERS[len(bucket) % len(WRAPPERS)]
            bucket.append({"id": f"EXT-TEST-{name.upper()}-{len(bucket)}", "source": name,
                           "text": w.format(x=text), "raw": text, "wrapper": w})
    CACHE_ATTACKS.write_text(json.dumps({"sources": meta, "n": len(attacks), "items": attacks},
                                        indent=1, ensure_ascii=False), encoding="utf-8")
    CACHE_BENIGN.write_text(json.dumps({"sources": meta, "n": len(benign), "items": benign},
                                       indent=1, ensure_ascii=False), encoding="utf-8")
    return {"attacks": len(attacks), "benign": len(benign), "sources": meta}


def _digest() -> str:
    h = hashlib.sha256()
    for p in (CACHE_ATTACKS, CACHE_BENIGN):
        for i in json.loads(p.read_text(encoding="utf-8"))["items"]:
            h.update(i["id"].encode("utf-8"))
            h.update(i["text"].encode("utf-8"))
    return h.hexdigest()


def freeze(note: str = "") -> dict:
    d = {"frozen_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "sha256": _digest(),
         "n_attacks": len(test_attack_records()), "n_benign": len(test_benign_texts()), "note": note}
    FREEZE.write_text(json.dumps(d, indent=1), encoding="utf-8")
    return d


def verify_frozen() -> bool:
    if not FREEZE.exists():
        return False
    return json.loads(FREEZE.read_text(encoding="utf-8"))["sha256"] == _digest()


def test_attack_records() -> List[PoisonRecord]:
    if not CACHE_ATTACKS.exists():
        return []
    return [PoisonRecord(i["id"], i["text"], f"exttest_{i['source']}", SPLIT_EXTERNAL_TEST)
            for i in json.loads(CACHE_ATTACKS.read_text(encoding="utf-8"))["items"]]


def test_benign_texts() -> List[str]:
    if not CACHE_BENIGN.exists():
        return []
    return [i["text"] for i in json.loads(CACHE_BENIGN.read_text(encoding="utf-8"))["items"]]


if __name__ == "__main__":
    from collections import Counter

    r = build()
    print(json.dumps(r, indent=1))
    print("attacks by source:", Counter(x.family for x in test_attack_records()))
    print("FROZEN:", json.dumps(freeze("frozen before any round-5 defense development"), indent=1))
    print("DONE")
