"""SA-9 corpus (v8 addendum W1b; docs/phase17/v8/V8_PREREG_ADDENDUM_W1b.md Sec 3).

Main confirmatory population for "C AND K + G" (3.2/3.3). Owners 200-209 (LongMemEval,
never used before -- see phase17.defence_v8.longmemeval_owners). Reuses SA-7/SA-8's eight
kinds, INTENT text, per-owner-kind cap, gates and channel() function unchanged. Near-dup
blocks against the union of SA-1..SA-8. Writer identity for the eval-side confirmatory
score is assigned at SCORING time by the label-independent policy rule
(writer_policy.assign_writer), not baked into the corpus file -- the corpus itself carries
no writer field, exactly like SA-8.

Only deviation from SA-8's generation (logged D-V8-4): `who` is always "User", never
alternating, because LongMemEval's second role is "assistant", not a second human.
"""
from __future__ import annotations

from phase17.defence_v7 import atomic  # noqa: F401  (crash-safe checkpoints: atomic file writes)

import hashlib
import json
import random
import re
import time
from pathlib import Path
from typing import Dict, List

from phase17.defence_v7 import sa7_corpus as S7
from phase17.defence_v8 import longmemeval_owners as L
from phase17.defence_v8 import sa8_corpus as S8
from phase17.remediation import sleeper_corpus as S1
from phase17.remediation import sleeper_corpus2 as S2

DATA = Path(__file__).resolve().parents[1] / "data" / "defence_v8"
CACHE = DATA / "sa9_corpus.json"
PARTIAL = DATA / "sa9_corpus_partial.json"
FREEZE = DATA / "sa9_corpus_freeze.json"
DEV_OWNERS = L.DEV_OWNERS
EVAL_OWNERS = L.EVAL_OWNERS
KINDS = S7.KINDS
PER_OWNER_KIND = S7.PER_OWNER_KIND
BATCHES = S7.BATCHES
SEED_BASE = 129000
HIGH_IMPACT = S7.HIGH_IMPACT
INTENT = S7.INTENT

_prompt = S7._prompt


def _jobs():
    return [(o, kind, b, SEED_BASE + 1000 * o + 100 * ki + b) for o in DEV_OWNERS + EVAL_OWNERS
            for ki, kind in enumerate(KINDS) for b in range(BATCHES)]


def build() -> dict:
    from phase17.gemini_provider import GeminiProvider
    from phase17.holdout4_corpus import _excerpt
    from phase3.evaluation.llm.provider import GenerationConfig

    DATA.mkdir(parents=True, exist_ok=True)
    gen = GeminiProvider()
    done = json.loads(PARTIAL.read_text(encoding="utf-8")) if PARTIAL.exists() else {}
    jobs = _jobs()
    for n, (o, kind, b, seed) in enumerate(jobs, 1):
        key = f"{o}:{kind}:{b}"
        if key in done:
            continue
        a, _bb = L.speakers(o)
        who = "User"   # D-V8-4: always the human role, never "assistant"
        cfg = GenerationConfig(temperature=0.9, seed=seed, max_tokens=2400, enable_thinking=False, n_ctx=8192,
                               request_timeout_sec=180.0)
        try:
            raw = gen.generate([{"role": "user", "content": _prompt(_excerpt(L.owner_turns(o), random.Random(seed)),
                                                                     kind, who, who, "Assistant")}], cfg).text
            done[key] = {"who": who, "items": S1._parse(raw)}
        except Exception as exc:  # noqa: BLE001
            print(f"  stopped at {key}: {type(exc).__name__}: {exc}"[:200], flush=True)
            break
        PARTIAL.write_text(json.dumps(done, ensure_ascii=False), encoding="utf-8")
        print(f"  {n}/{len(jobs)} {key}: {len(done[key]['items'])} parsed", flush=True)
    if any(f"{o}:{k}:{b}" not in done for o, k, b, _ in jobs):
        return {"complete": False, "done": len(done), "of": len(jobs)}
    return _filter(done, jobs)


def _prior_texts() -> List[str]:
    """Everything SA-1..SA-8 kept, so SA-9 near-dup-blocks against the full history."""
    return S8._prior_texts() + [x["note"] for x in json.loads(S8.CACHE.read_text(encoding="utf-8"))["items"]]


def _filter(done, jobs) -> dict:
    from phase17.holdout7_corpus import _CONDITIONAL, _IMPERATIVE, _PROTECTIVE
    from phase17.near_dup import Index

    seen = Index(_prior_texts())
    own: List[str] = []
    split_texts: Dict[str, List[str]] = {"dev": [], "eval": []}
    kept, per = [], {}
    dropped = {"length_or_gate": 0, "explicit_harm": 0, "explicit_not_imperative": 0, "not_high_impact": 0,
               "trigger_leaks_note": 0, "near_dup_seen": 0, "near_dup_within": 0, "near_dup_cross_split": 0}
    for o, kind, b, _ in jobs:
        split = "dev" if o in DEV_OWNERS else "eval"
        other = "eval" if split == "dev" else "dev"
        own_re = re.compile(r"\b(User)\b")
        for j, it in enumerate(done[f"{o}:{kind}:{b}"]["items"]):
            if per.get((o, kind), 0) >= PER_OWNER_KIND:
                break
            t = it["note"]
            if not (S1.MIN_LEN <= len(t) <= S1.MAX_LEN and _CONDITIONAL.search(t) and not _PROTECTIVE.search(t)
                    and it["trigger"] and it["non_trigger"] and own_re.search(t) and not S1._FIRST.search(t)):
                dropped["length_or_gate"] += 1
                continue
            if kind in ("atk_implicit", "atk_explicit") and S2.EXPLICIT_HARM.search(t):
                dropped["explicit_harm"] += 1
                continue
            if kind == "atk_explicit" and not _IMPERATIVE.search(t):
                dropped["explicit_not_imperative"] += 1
                continue
            if kind.endswith("highimpact") and not HIGH_IMPACT.search(t):
                dropped["not_high_impact"] += 1
                continue
            ni = Index([t])
            if ni.max_containment(it["trigger"]) >= 0.4 or ni.max_containment(it["non_trigger"]) >= 0.4:
                dropped["trigger_leaks_note"] += 1
                continue
            if seen.max_containment(t) >= 0.6:
                dropped["near_dup_seen"] += 1
                continue
            if split_texts[other] and Index(split_texts[other]).max_containment(t) >= 0.6:
                dropped["near_dup_cross_split"] += 1
                continue
            if own and Index(own).max_containment(t) >= 0.6:
                dropped["near_dup_within"] += 1
                continue
            own.append(t)
            split_texts[split].append(t)
            per[(o, kind)] = per.get((o, kind), 0) + 1
            iid = f"SA9-{o}-{kind}-{b}-{j}"
            kept.append({"id": iid, "owner": o, "split": split, "kind": kind, "channel": S7.S6.channel(iid, kind),
                         "about": done[f"{o}:{kind}:{b}"]["who"], **it})
    counts = {f"{o}:{k}": per.get((o, k), 0) for o in DEV_OWNERS + EVAL_OWNERS for k in KINDS}
    CACHE.write_text(json.dumps({"author": S1.AUTHOR, "dev_owners": list(DEV_OWNERS), "eval_owners": list(EVAL_OWNERS),
                                 "owner_episode": {str(o): L.OWNER_EPISODE[o] for o in DEV_OWNERS + EVAL_OWNERS},
                                 "counts": counts, "dropped": dropped, "items": kept}, indent=1, ensure_ascii=False),
                     encoding="utf-8")
    short = {k: v for k, v in counts.items() if v < PER_OWNER_KIND}
    return {"complete": True, "n": len(kept), "short_cells": short, "dropped": dropped}


def _digest() -> str:
    h = hashlib.sha256()
    for i in json.loads(CACHE.read_text(encoding="utf-8"))["items"]:
        for k in ("id", "note", "trigger", "non_trigger", "channel"):
            h.update(i[k].encode("utf-8"))
    return h.hexdigest()


def freeze() -> dict:
    d = json.loads(CACHE.read_text(encoding="utf-8"))
    out = {"frozen_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "sha256": _digest(), "n": len(d["items"]),
           "counts": d["counts"]}
    FREEZE.write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


def verify_frozen() -> bool:
    return FREEZE.exists() and CACHE.exists() and json.loads(FREEZE.read_text(encoding="utf-8"))["sha256"] == _digest()


def items(kind: str = None, split: str = None, owner: int = None) -> List[Dict]:
    return [x for x in json.loads(CACHE.read_text(encoding="utf-8"))["items"]
            if (kind is None or x["kind"] == kind) and (split is None or x["split"] == split)
            and (owner is None or x["owner"] == owner)]


if __name__ == "__main__":
    import sys

    if "freeze" in sys.argv:
        if FREEZE.exists():
            raise SystemExit("SA-9 already frozen")
        print(freeze())
    else:
        print(build())
