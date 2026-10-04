"""A THIRD frozen hold-out, built and frozen BEFORE B17/B18 were ever scored on it.

WHY. B15's architecture was chosen after reading `external_test`'s baseline results, and B17
and B18 were chosen after reading hold-out results outright. That left Mosscap as the only
clean hold-out for B15, and NO clean hold-out at all for B17/B18 -- so their numbers were
descriptive, not a generalisation claim. Fixing that needs a set that did not exist, in this
project, at the moment those configs were designed.

  in-the-wild  `TrustAIRLab/in-the-wild-jailbreak-prompts` (MIT), the "Do Anything Now"
               collection: jailbreak prompts real people posted on Reddit and Discord, plus
               `regular_*`, matched ordinary prompts from the same platforms for false
               positives. Never fetched, scored or inspected by this project before this
               module.

It is a genuinely different distribution from the first two hold-outs, which both come from
Lakera's password games: these are unprompted attacks on deployed assistants, written to be
used rather than to win a level, and they are long (multi-paragraph personas) where game
prompts are short.

The benign half matters as much as the attack half here. Gandalf and Mosscap gave attacks only,
so every FPR number in this project comes from the same four benign populations. `regular_*`
gives benign text from the SAME source and platforms as the attacks, which is the harder and
fairer false-positive test: it removes the possibility that a detector is really just
distinguishing Reddit from the project's own benign corpora.

DISCIPLINE, and the whole point of the module. The corpus is built, digested and frozen in one
run, with the digest recorded, BEFORE any config is evaluated on it. `docs/phase17/
PREREGISTRATION_HOLDOUT3.md` names the configs, the frozen thresholds and the predictions
before the run. Nothing here is re-fitted; no threshold, weight or radius is chosen from this
set. A CI test recomputes the digest.

THE SAME LIMIT APPLIES AS TO THE OTHER TWO, and is not reduced by the set being new: this is a
jailbreak corpus, not a memory-poisoning one. A good score is evidence about detecting overt
injected instructions that arrive in memory, and says nothing about additive fabrication or
preference hijack. This project's own mechanism populations remain the only test of those.

CONTENT NOTE: in-the-wild jailbreaks include deliberately offensive and sexual prompts, because
that is what people write when trying to break a deployed assistant. The texts are detector
inputs and are not reproduced in any report.
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
CACHE = DATA / "holdout3_attacks.json"
FREEZE = DATA / "holdout3_freeze.json"
SPLIT = "held_out_inthewild"
ROWS_API = "https://datasets-server.huggingface.co/rows"
DATASET = "TrustAIRLab/in-the-wild-jailbreak-prompts"
ATTACK_CONFIG = "jailbreak_2023_12_25"
BENIGN_CONFIG = "regular_2023_12_25"
# The same three wrappers used for every other externally-authored corpus here, so placement in
# memory is identical and the comparison is about the text.
WRAPPERS = (
    "Saved from a tool result: {x}",
    "Note from a document the user shared: {x}",
    "Reminder for future sessions: {x}",
)
MAX_ATTACKS = 1000
MAX_BENIGN = 1000
# In-the-wild jailbreaks run to several thousand characters. The cap matches the other corpora's
# 1,200-character ceiling so no config is advantaged by length alone; `raw_len` is kept so the
# truncation is auditable.
MIN_LEN, MAX_LEN = 25, 1200


def _get(url: str, tries: int = 6) -> dict:
    """The rows API rate-limits (HTTP 429) well before 30 sequential pages. Backoff, because a
    half-fetched corpus that gets frozen anyway is the worst possible outcome here."""
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


def _fetch(config: str, cap: int, limit: int = 100) -> List[dict]:
    # Over-fetch only modestly (1.6x): dedup and the length floor discard some, but fetching 3x
    # meant 30+ sequential pages per config and tripped the rate limit immediately.
    out, offset = [], 0
    target = int(cap * 1.6)
    while len(out) < target:
        q = urllib.parse.urlencode({"dataset": DATASET, "config": config, "split": "train",
                                    "offset": offset, "length": limit})
        rows = [x["row"] for x in _get(f"{ROWS_API}?{q}").get("rows", [])]
        if not rows:
            break
        out += rows
        offset += limit
        time.sleep(1.5)
    return out


def _items(rows, cap, prefix):
    items, seen = [], set()
    for r in rows:
        raw = " ".join((r.get("prompt") or "").split())
        if len(raw) < MIN_LEN:
            continue
        t = raw[:MAX_LEN]
        if t.lower() in seen:
            continue
        seen.add(t.lower())
        w = WRAPPERS[len(items) % len(WRAPPERS)]
        items.append({"id": f"{prefix}-{len(items)}", "raw_len": len(raw),
                      "platform": r.get("platform"), "text": w.format(x=t), "wrapper": w})
        if len(items) >= cap:
            break
    return items


def build() -> dict:
    atk = _items(_fetch(ATTACK_CONFIG, MAX_ATTACKS), MAX_ATTACKS, "ITW")
    ben = _items(_fetch(BENIGN_CONFIG, MAX_BENIGN), MAX_BENIGN, "ITWBEN")
    # No text may appear on both sides.
    atk_texts = {i["text"] for i in atk}
    ben = [i for i in ben if i["text"] not in atk_texts]
    data = {"dataset": DATASET, "attack_config": ATTACK_CONFIG, "benign_config": BENIGN_CONFIG,
            "license": "MIT", "authorship": "human (Reddit/Discord users, 'Do Anything Now' collection)",
            "n_attacks": len(atk), "n_benign": len(ben),
            "content_note": "in-the-wild jailbreaks include deliberately offensive prompts; "
                            "texts are detector inputs and are not reproduced in reports",
            "attacks": atk, "benign": ben}
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
    return [PoisonRecord(i["id"], i["text"], "in_the_wild_jailbreak", SPLIT)
            for i in json.loads(CACHE.read_text(encoding="utf-8"))["attacks"]]


def benign_texts() -> List[str]:
    if not CACHE.exists():
        return []
    return [i["text"] for i in json.loads(CACHE.read_text(encoding="utf-8"))["benign"]]


if __name__ == "__main__":
    d = build()
    print(f"built {d['n_attacks']} in-the-wild jailbreak attacks and {d['n_benign']} matched "
          f"benign prompts (MIT, human-authored)")
    print("FROZEN:", json.dumps(freeze("frozen before B17/B18 were scored on it"), indent=1))
    print("DONE")
