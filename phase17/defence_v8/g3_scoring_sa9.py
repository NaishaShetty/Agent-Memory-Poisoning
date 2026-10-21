"""v8 addendum W1b confirmatory scoring: "C AND K + G" on SA-9
(docs/phase17/v8/V8_PREREG_ADDENDUM_W1b.md Sec 3). Mirrors g3_scoring_v8.py's structure
exactly, pointed at SA-9/mem0_sa9, plus the writer-authentication gate from g3_v8.py and
the stress-test strata (Sec 3.2).

  python -m phase17.defence_v8.g3_scoring_sa9 signals <dev|eval>
  python -m phase17.defence_v8.g3_scoring_sa9 eval
  python -m phase17.defence_v8.g3_scoring_sa9 stress
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from phase17.defence_v8 import common_v8

common_v8.isolate()

from phase17.defence_v7.g3_v7 import K, limits  # noqa: E402  (frozen; imported unchanged)
from phase17.defence_v8.g3_v8 import ck_plus_g, dev_writer_verifier  # noqa: E402

DATA = common_v8.DATA
SIG_CACHE = DATA / "v8_signals_sa9.json"
OUT = DATA / "g3_eval_sa9.json"
STRESS_OUT = DATA / "g3_stress_sa9.json"


def _stage() -> dict:
    from phase17.defence_v8 import sa9_corpus as C
    from phase17.defence_v8.mem0_sa9 import STAGE

    assert C.verify_frozen()
    return json.loads(STAGE.read_text(encoding="utf-8"))["items"]


def items(split: str) -> List[Dict]:
    from phase17.defence_v8 import sa9_corpus as C

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
    from phase17.defence_v2.sleeper_v2 import _intent
    from phase17.defence_v3.sleeper_v3 import _conv_text, n1
    from phase17.provenance_sets import speakers  # dispatches to longmemeval_owners for owners >= 200

    cache = json.loads(SIG_CACHE.read_text(encoding="utf-8")) if SIG_CACHE.exists() else {}
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
        SIG_CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
        print(f"  signals owner {o}: {len(todo)}", flush=True)
    return cache


def conditions(sig: Dict) -> Dict[str, callable]:
    def k_stored(x):
        return any(sig[t][K] for t in x["stored_list"])

    return {"C&K(plain, same frozen rule as W1)": lambda x: x["untrusted"] and k_stored(x),
            "C&K+G(W1b primary)": lambda x: ck_plus_g(x, k_stored, dev_writer_verifier)}


def evaluate(split: str = "eval") -> Dict:
    xs = items(split)
    sig = signals(xs)
    conds = conditions(sig)
    out = {"split": split, "n": len(xs), "conditions": {name: limits(xs, pred) for name, pred in conds.items()}}
    if split == "eval":
        OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    return out


# ------------------------------------------------------------------------------------------------ stress-test strata (3.2)
def stress_strata() -> Dict:
    """No new generation: reuses SA-9 eval's document/missing-channel attack items, each
    scored under three forced writer/signature scenarios. Reported separately; earns no
    closure credit (see addendum Sec 3.2 for why)."""
    from phase17.defence_v8.ledger_chain_v8 import AuthenticatedLedger, writer_signature
    from phase17.defence_v8.writer_policy import REGISTRY, TRUSTED_WRITERS

    xs = items("eval")
    sig = signals(xs)

    def k_stored(x):
        return any(sig[t][K] for t in x["stored_list"])

    atk = [x for x in xs if x["kind"].startswith("atk") and x["channel"] in ("document", "missing")]

    def _verifier_for(writer_id: str, sign_with: str):
        """Returns a per-item verifier simulating: this item's memory was written by
        `writer_id`, signed with `sign_with`'s key (sign_with == writer_id -> genuine;
        otherwise forged)."""
        def verifier(x):
            from phase17.defence_v6.ledger import sha

            L = AuthenticatedLedger()  # in-memory only (path=None); one fresh chain per item
            payload = {"channel": x["channel"], "sha256": sha(x["note"]), "claims": [x["note"]]}
            key = REGISTRY.get(sign_with)
            sig_val = writer_signature(sign_with, key, payload) if key is not None else "none"
            eid = L.record_event_signed(x["note"], x["channel"], writer_id, sig_val, REGISTRY, claims=[x["note"]])
            L.link("m", "ADD", eid, x["note"])
            return L.verified_trusted_writer("m", TRUSTED_WRITERS)
        return verifier

    scenarios = {
        "authenticated_non_owner_trusted_writer": _verifier_for("shared_drive_import", "shared_drive_import"),
        "compromised_trusted_writer": _verifier_for("calendar_integration", "calendar_integration"),
        "unsigned_writer": lambda x: False,   # no signature at all: G never triggers (sanity check)
    }

    out = {}
    for name, verifier in scenarios.items():
        plain = [bool(x["untrusted"] and k_stored(x)) for x in atk]
        gated = [bool(ck_plus_g(x, k_stored, verifier)) for x in atk]
        n = len(atk)
        out[name] = {"n": n, "plain_detected": sum(plain), "gated_detected": sum(gated),
                     "plain_rate": sum(plain) / n if n else None, "gated_rate": sum(gated) / n if n else None,
                     "mcnemar_b_c": {"only_plain": sum(p and not g for p, g in zip(plain, gated)),
                                    "only_gated": sum(g and not p for p, g in zip(plain, gated))}}
    STRESS_OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    return out


if __name__ == "__main__":
    import sys

    if sys.argv[1] == "signals":
        signals(items(sys.argv[2]))
        print("signals: done")
    elif sys.argv[1] == "stress":
        print(json.dumps(stress_strata(), indent=1))
    else:
        print(json.dumps(evaluate(), indent=1))
