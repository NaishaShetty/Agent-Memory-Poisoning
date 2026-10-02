"""A SECOND frozen hold-out set, built before B15 exists (external review round 6).

WHY A SECOND ONE. `external_test_corpus.py` is frozen and was used exactly once, for B14.
But round 5's results have now been read, and the single most important thing they showed is
that an off-the-shelf classifier (ProtectAI deberta-v3) reaches 84.6% at 0.13% FPR for one
local forward pass while B14 spends 179x more to add six points. B15 is designed around that
observation. **That means the architecture choice was informed by test data**, and reporting
B15 on the same frozen set would overstate how held-out its number is — no threshold would
be tuned there, but the choice of what to build would have been.

So B15 gets a test set that did not exist when it was designed:

  mosscap  `Lakera/mosscap_prompt_injection` (MIT) — prompt-injection attempts typed by real
           human players of Lakera's *second* game, Mosscap. Never fetched, scored or looked
           at by this project before this module. Human-authored, like Gandalf, but a
           different game with different levels and defenses, so the attack styles differ.

Frozen the same way as the first: a SHA-256 over the exact texts, recorded in
`data/holdout2_freeze.json`, with a CI test that recomputes it.

THE SAME LIMITS APPLY, and they are not reduced by the set being new: this is a
prompt-injection corpus, not a memory-poisoning one. Players are trying to extract a
password from a chatbot. A good score is evidence about detecting overt injected
instructions that arrive in memory, and says nothing about additive fabrication or
preference hijack. `provenance_test_fabrications` and this project's own mechanism
populations remain the only tests of those.

ONE FURTHER HONEST NOTE. Mosscap prompts are conversational attack *turns*, not stored
memory notes, so the same three fixed wrappers used everywhere else place them in memory.
Many are also benign-looking chat ("let's play a word association game") whose malice lives
in the surrounding game context rather than the text — so a *low* score here may reflect
items that are not injections once removed from that context, not detector failure. The
validity audit (`attack_validity_audit.py`) is the check on that, and its criterion was
committed long before this set existed.
"""
from __future__ import annotations

import hashlib
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import List

from phase17.poison_sets import PoisonRecord

DATA = Path(__file__).parent / "data"
CACHE = DATA / "holdout2_attacks.json"
FREEZE = DATA / "holdout2_freeze.json"
SPLIT = "held_out_mosscap"
ROWS_API = "https://datasets-server.huggingface.co/rows"
DATASET = "Lakera/mosscap_prompt_injection"
WRAPPERS = (
    "Saved from a tool result: {x}",
    "Note from a document the user shared: {x}",
    "Reminder for future sessions: {x}",
)
MAX_ITEMS = 1200


def _fetch(split: str, limit: int = 100, cap: int = MAX_ITEMS) -> List[dict]:
    out, offset = [], 0
    while len(out) < cap:
        q = urllib.parse.urlencode({"dataset": DATASET, "config": "default", "split": split,
                                    "offset": offset, "length": limit})
        with urllib.request.urlopen(f"{ROWS_API}?{q}", timeout=120) as r:
            d = json.loads(r.read().decode("utf-8"))
        rows = [x["row"] for x in d.get("rows", [])]
        if not rows:
            break
        out += rows
        offset += limit
        time.sleep(0.2)
    return out[:cap]


def build() -> dict:
    rows = _fetch("test") + _fetch("train", cap=MAX_ITEMS)
    items, seen = [], set()
    for r in rows:
        t = " ".join((r.get("prompt") or "").split())
        if not (25 <= len(t) <= 1200) or t.lower() in seen:
            continue
        seen.add(t.lower())
        w = WRAPPERS[len(items) % len(WRAPPERS)]
        items.append({"id": f"MOSSCAP-{len(items)}", "level": r.get("level"), "raw": t,
                      "text": w.format(x=t), "wrapper": w})
        if len(items) >= MAX_ITEMS:
            break
    data = {"dataset": DATASET, "license": "MIT", "authorship": "human (Mosscap game players)",
            "n": len(items), "items": items}
    CACHE.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    return data


def _digest() -> str:
    h = hashlib.sha256()
    for i in json.loads(CACHE.read_text(encoding="utf-8"))["items"]:
        h.update(i["id"].encode("utf-8"))
        h.update(i["text"].encode("utf-8"))
    return h.hexdigest()


def freeze(note: str = "") -> dict:
    d = {"frozen_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "sha256": _digest(),
         "n": len(records()), "note": note}
    FREEZE.write_text(json.dumps(d, indent=1), encoding="utf-8")
    return d


def verify_frozen() -> bool:
    return FREEZE.exists() and json.loads(FREEZE.read_text(encoding="utf-8"))["sha256"] == _digest()


def records() -> List[PoisonRecord]:
    if not CACHE.exists():
        return []
    return [PoisonRecord(i["id"], i["text"], "mosscap", SPLIT)
            for i in json.loads(CACHE.read_text(encoding="utf-8"))["items"]]


if __name__ == "__main__":
    d = build()
    print(f"built {d['n']} Mosscap attacks (MIT, human-authored)")
    print("FROZEN:", json.dumps(freeze("frozen before B15 was written"), indent=1))
    print("DONE")
