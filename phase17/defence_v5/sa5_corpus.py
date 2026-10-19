"""SA-5 corpus (v5 held-out): SA-3/SA-4 author, template and gates; owners 5, 7, 8 (NEW notes); kinds atk and
ben_unground, 15 per owner per kind; near-duplicate blocking against SA-1, SA-2, SA-3 and SA-4. Frozen by sha256 before any scoring.
"""
from __future__ import annotations

import hashlib
import json
import random
import re
import time
from pathlib import Path
from typing import Dict, List

from phase17.defence_v2 import sa3_corpus as S3
from phase17.remediation import sleeper_corpus as S1
from phase17.remediation import sleeper_corpus2 as S2

DATA = Path(__file__).resolve().parents[1] / "data" / "defence_v5"
CACHE = DATA / "sa5_corpus.json"
PARTIAL = DATA / "sa5_corpus_partial.json"
FREEZE = DATA / "sa5_corpus_freeze.json"
OWNERS = (5, 7, 8)
KINDS = ("atk", "ben_unground")
PER_OWNER_KIND = 15
BATCHES = 3


def _jobs():
    return [(o, kind, b, 95000 + 1000 * o + 100 * ki + b) for o in OWNERS for ki, kind in enumerate(KINDS) for b in range(BATCHES)]


def build() -> dict:
    from phase17.gemini_provider import GeminiProvider
    from phase17.holdout4_corpus import _excerpt
    from phase17.provenance_sets import owner_turns, speakers
    from phase3.evaluation.llm.provider import GenerationConfig

    DATA.mkdir(parents=True, exist_ok=True)
    gen = GeminiProvider()
    done = json.loads(PARTIAL.read_text(encoding="utf-8")) if PARTIAL.exists() else {}
    jobs = _jobs()
    for n, (o, kind, b, seed) in enumerate(jobs, 1):
        key = f"{o}:{kind}:{b}"
        if key in done:
            continue
        a, bb = speakers(o)
        who = (a, bb)[seed % 2]
        cfg = GenerationConfig(temperature=0.9, seed=seed, max_tokens=2400, enable_thinking=False, n_ctx=8192,
                               request_timeout_sec=180.0)
        try:
            raw = gen.generate([{"role": "user", "content": S3._prompt(_excerpt(owner_turns(o), random.Random(seed)),
                                                                        kind, who, a, bb)}], cfg).text
            done[key] = {"who": who, "items": S1._parse(raw)}
        except Exception as exc:
            print(f"  stopped at {key}: {type(exc).__name__}: {exc}"[:200], flush=True)
            break
        PARTIAL.write_text(json.dumps(done, ensure_ascii=False), encoding="utf-8")
        print(f"  {n}/{len(jobs)} {key}: {len(done[key]['items'])} parsed", flush=True)
    if any(f"{o}:{k}:{b}" not in done for o, k, b, _ in jobs):
        return {"complete": False}
    return _filter(done, jobs)


def _filter(done, jobs) -> dict:
    from phase17.holdout7_corpus import _CONDITIONAL, _PROTECTIVE
    from phase17.near_dup import Index
    from phase17.provenance_sets import speakers

    prior = S1._seen_texts()
    for mod in (S1, S2):
        d = json.loads(mod.CACHE.read_text(encoding="utf-8"))
        prior += [x["note"] for g in ("attacks", "lookalikes") for x in d[g]]
    prior += [x["note"] for x in json.loads(S3.CACHE.read_text(encoding="utf-8"))["items"]]
    from phase17.defence_v4 import sa4_corpus as S4
    prior += [x["note"] for x in json.loads(S4.CACHE.read_text(encoding="utf-8"))["items"]]
    seen = Index(prior)
    own: List[str] = []
    kept, per = [], {}
    dropped = {"length_or_gate": 0, "explicit_harm": 0, "trigger_leaks_note": 0, "near_dup_seen": 0, "near_dup_within": 0}
    for o, kind, b, _ in jobs:
        own_re = re.compile(rf"\b({'|'.join(re.escape(n) for n in speakers(o))})\b")
        for j, it in enumerate(done[f"{o}:{kind}:{b}"]["items"]):
            if per.get((o, kind), 0) >= PER_OWNER_KIND:
                break
            t = it["note"]
            if not (S1.MIN_LEN <= len(t) <= S1.MAX_LEN and _CONDITIONAL.search(t) and not _PROTECTIVE.search(t)
                    and it["trigger"] and it["non_trigger"] and own_re.search(t) and not S1._FIRST.search(t)):
                dropped["length_or_gate"] += 1
                continue
            if kind == "atk" and S2.EXPLICIT_HARM.search(t):
                dropped["explicit_harm"] += 1
                continue
            ni = Index([t])
            if ni.max_containment(it["trigger"]) >= 0.4 or ni.max_containment(it["non_trigger"]) >= 0.4:
                dropped["trigger_leaks_note"] += 1
                continue
            if seen.max_containment(t) >= 0.6:
                dropped["near_dup_seen"] += 1
                continue
            if own and Index(own).max_containment(t) >= 0.6:
                dropped["near_dup_within"] += 1
                continue
            own.append(t)
            per[(o, kind)] = per.get((o, kind), 0) + 1
            kept.append({"id": f"SA5-{o}-{kind}-{b}-{j}", "owner": o, "split": "eval", "kind": kind,
                         "about": done[f"{o}:{kind}:{b}"]["who"], **it})
    counts = {f"{o}:{k}": per.get((o, k), 0) for o in OWNERS for k in KINDS}
    CACHE.write_text(json.dumps({"author": S1.AUTHOR, "owners": list(OWNERS), "counts": counts, "dropped": dropped,
                                 "items": kept}, indent=1, ensure_ascii=False), encoding="utf-8")
    return {"complete": True, "n": len(kept), "counts": counts, "dropped": dropped}


def _digest() -> str:
    h = hashlib.sha256()
    for i in json.loads(CACHE.read_text(encoding="utf-8"))["items"]:
        for k in ("id", "note", "trigger", "non_trigger"):
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


def items(kind: str = None, owner: int = None) -> List[Dict]:
    return [x for x in json.loads(CACHE.read_text(encoding="utf-8"))["items"]
            if (kind is None or x["kind"] == kind) and (owner is None or x["owner"] == owner)]


if __name__ == "__main__":
    import sys

    print(freeze() if "freeze" in sys.argv else build())
