"""v8 Gap 3 confirmatory scoring (W1; pre-registered docs/phase17/v8/V8_PREREGISTRATION.md
Sec 1): C AND K, frozen exactly as implemented in phase17/defence_v7/g3_v7.py (the K
constant "N1&INTENT_v1" and the C&K condition from phase17/defence_v6/g3_eval.py's
`_conditions`, both imported unchanged -- nothing in that logic is redefined here).

Only the plumbing needed to run that frozen logic against SA-8 (owner resolution via
phase17.provenance_sets, now additively CC-aware; v8's own signal/decision caches via
common_v8.isolate()) lives in this module. No DC, BF-R, E-link, URA or MSD scoring here --
out of scope for the W1 confirmatory test (3.2/3.3 only).

  python -m phase17.defence_v8.g3_scoring_v8 signals <dev|eval>
  python -m phase17.defence_v8.g3_scoring_v8 eval
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from phase17.defence_v8 import common_v8

common_v8.isolate()

from phase17.defence_v7.g3_v7 import K, limits  # noqa: E402  (frozen; imported unchanged)

DATA = common_v8.DATA
OUT = DATA / "g3_eval_sa8.json"


def _stage() -> dict:
    from phase17.defence_v8 import sa8_corpus as C
    from phase17.defence_v8.mem0_sa8 import STAGE

    assert C.verify_frozen()
    return json.loads(STAGE.read_text(encoding="utf-8"))["items"]


def items(split: str) -> List[Dict]:
    """SA-8 single notes (prefix N only -- no URA stratum in this pre-registration's scope).
    Mirrors phase17.defence_v7.g3_v7.items()'s v6-derived semantics exactly: same
    `untrusted` definition, same stored-list extraction from Mem0's derived memories."""
    from phase17.defence_v8 import sa8_corpus as C

    st = _stage()
    out = []
    for x in C.items(split=split):
        r = st.get(f"N|{x['id']}")
        if not r or "error" in r:
            continue
        der = [d for d in r["derived"] if d.get("memory")]
        untr = (not der) or any(c != "user" for d in der for c in d["ledger_channels"][-1:])
        out.append(dict(x, stratum=x["channel"], stored_list=[d["memory"] for d in der],
                        stored=" ".join(d["memory"] for d in der),
                        untrusted=bool(untr if der else x["channel"] != "user"), key=f"N|{x['id']}"))
    return out


def signals(xs: List[Dict]) -> Dict:
    """K = N1 AND INTENT_v1 on every raw note and every Mem0-stored derived memory text.
    Same formula as g3_v7.signals(); B12/B13/BF_R/DC are NOT computed here (out of scope
    for C AND K -- v7's signals() computes them unconditionally for its OTHER arms, which
    this module does not score)."""
    from phase17.defence_v2.sleeper_v2 import _intent
    from phase17.defence_v3.sleeper_v3 import _conv_text, n1
    from phase17.provenance_sets import speakers  # additively CC-aware for owners >= 100

    cache = json.loads(common_v8.SIG_CACHE.read_text(encoding="utf-8")) if common_v8.SIG_CACHE.exists() else {}
    for o in sorted({x["owner"] for x in xs}):
        ox = [x for x in xs if x["owner"] == o]
        texts = list(dict.fromkeys([x["note"] for x in ox] + [t for x in ox for t in x["stored_list"]]))
        todo = [t for t in texts if t not in cache]
        if not todo:
            continue
        it = _intent(todo, cache.setdefault("_intent", {}))
        conv, names = _conv_text(o), set(speakers(o))
        for t, iv in zip(todo, it["INTENT_v1"]):
            a = bool(n1(t, o, conv, names))
            cache[t] = {"N1": a, "INTENT_v1": bool(iv), K: a and bool(iv)}
        common_v8.SIG_CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
        print(f"  signals owner {o}: {len(todo)}", flush=True)
    return cache


def conditions(sig: Dict) -> Dict[str, callable]:
    def k_raw(x):
        return sig[x["note"]][K]

    def k_stored(x):
        return any(sig[t][K] for t in x["stored_list"])

    return {"C_metadata(baseline)": lambda x: x["untrusted"],
            "C&K_metadata+stored(SECONDARY, pre-registered here for SA-8)": lambda x: x["untrusted"] and k_stored(x),
            "A_original_text(raw)": k_raw}


def evaluate(split: str = "eval") -> Dict:
    xs = items(split)
    sig = signals(xs)
    conds = conditions(sig)
    out = {"split": split, "n": len(xs), "conditions": {name: limits(xs, pred) for name, pred in conds.items()}}
    if split == "eval":
        OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    return out


if __name__ == "__main__":
    import sys

    if sys.argv[1] == "signals":
        signals(items(sys.argv[2]))
        print("signals: done")
    else:
        print(json.dumps(evaluate(), indent=1))
