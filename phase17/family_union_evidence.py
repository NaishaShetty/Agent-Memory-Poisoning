"""Unfavourable #12: the founding families re-measured under B17/B18 WITH the owner's conversation.

Table 5C of the results paper carried B17/B18 columns of dashes. `evidence_round6` scored both
configurations with evidence, but its per-family loop needs the no-evidence arm from
`eval_round6.json`, which predates B17/B18, so the comparison silently dropped them. That left
the configuration round 6 recommended for memory poisoning (B18 + evidence; superseded in round 7 by B13 + evidence) with no
per-family figure for the seven families the benchmark reconstructs from the literature.

NO MODEL IS RE-RUN. Every decision needed already exists:

  with evidence   per-item B17/B18 decisions persisted by `evidence_round6` (its partial file)
  no evidence     B17 = B13 OR B14 from `eval_round6`'s per-item decisions (B17 is a
                  parameter-free union, so this is its definition, not an approximation); B18 =
                  B17 OR deberta >= the round-5 frozen oracle threshold, from the cached scores

The union derivation is CHECKED rather than assumed: the with-evidence B17 decisions that were
actually computed must equal B13-with-evidence OR B14-with-evidence item for item, and the module
refuses to report if they do not.

Every rate is given on the full family AND on its working-attack subset, with the ordinary-benign
false-positive cost measured on the same footing beside it.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, List

DATA = Path(__file__).parent / "data"
OUT = DATA / "family_union_evidence.json"
FOUNDING = ("agentpoison", "minja", "farma", "memorygraft", "dsrm", "mpbench",
            "sleeper_memory_poisoning")


def _deb(texts: List[str]) -> List[bool]:
    from phase17.b18_live import deberta_threshold

    cache = json.loads((DATA / "external_baseline_scores.json").read_text(encoding="utf-8"))
    thr = deberta_threshold()
    out = []
    for t in texts:
        k = "deberta_pi_v2:" + hashlib.sha256(t.encode("utf-8")).hexdigest()[:24]
        if k not in cache:
            raise KeyError(f"no cached deberta score for an item; refusing to guess ({k})")
        out.append(cache[k] >= thr)
    return out


def run() -> dict:
    from phase17.eval_round6 import _attack_pops
    from phase17.stats import paired_delta, rate_with_ci
    from phase17.working_set import working_set

    part = json.loads((DATA / "evidence_round6_partial.json").read_text(encoding="utf-8"))
    r6 = json.loads((DATA / "eval_round6.json").read_text(encoding="utf-8"))
    pops = {k: v for k, v in _attack_pops().items() if k.startswith("own_")}
    ws = working_set()

    def r6dec(c, pop):
        return [bool(e) for e, _ in r6["raw"][c][f"attack::{pop}"]]

    # The union check, on every population, before anything is reported.
    mismatches = 0
    for pop in pops:
        a, b, u = (part[f"{c}:atk:{pop}"] for c in ("B13", "B14", "B17"))
        mismatches += sum((x or y) != z for x, y, z in zip(a, b, u))
    if mismatches:
        raise SystemExit(f"B17-with-evidence != B13 OR B14 on {mismatches} items; the derivation "
                         f"of the no-evidence arm would not be B17's definition")

    rows: Dict[str, Dict[str, List]] = {}
    for pop, recs in pops.items():
        texts = [r.text for r in recs]
        b17_no = [x or y for x, y in zip(r6dec("B13", pop), r6dec("B14", pop))]
        b18_no = [x or y for x, y in zip(b17_no, _deb(texts))]
        dec = {"B13": (r6dec("B13", pop), part[f"B13:atk:{pop}"]),
               "B17": (b17_no, part[f"B17:atk:{pop}"]),
               "B18": (b18_no, part[f"B18:atk:{pop}"])}
        wset = ws.get(pop, set())
        for i, r in enumerate(recs):
            row = rows.setdefault(r.family, {"working": [], **{c: ([], []) for c in dec}})
            row["working"].append(r.scenario_id in wset)
            for c, (n_, w) in dec.items():
                row[c][0].append(n_[i])
                row[c][1].append(w[i])

    def block(n_, w, mask=None):
        if mask is not None:
            n_ = [x for x, m in zip(n_, mask) if m]
            w = [x for x, m in zip(w, mask) if m]
        if not n_:
            return None
        return {"no_evidence": rate_with_ci(sum(n_), len(n_)),
                "with_evidence": rate_with_ci(sum(w), len(w)),
                "paired": paired_delta(w, n_)}

    out = {"source": "evidence_round6_partial.json (with evidence) + eval_round6.json and cached "
                     "deberta scores (no evidence); no model re-run",
           "union_check": "B17-with-evidence == B13-with-evidence OR B14-with-evidence on every "
                          "item: verified",
           "families": {}}
    for fam, row in sorted(rows.items()):
        e = {"n": len(row["working"]), "n_working": sum(row["working"]),
             "founding": fam in FOUNDING}
        for c in ("B13", "B17", "B18"):
            e[c] = {"full": block(*row[c]), "working": block(*row[c], mask=row["working"])}
        out["families"][fam] = e
    ev = json.loads((DATA / "evidence_round6.json").read_text(encoding="utf-8"))
    out["ordinary_benign_fpr_with_evidence"] = {
        c: ev["aggregate"][c]["ordinary_benign_with_evidence"] for c in ("B13", "B17", "B18")}

    # The NO-evidence aggregates for B17/B18, which evidence_round6 left as None (it predates them),
    # derived from the same per-item decisions. The derivation must first reproduce the B13 and B14
    # no-evidence aggregates evidence_round6 published, or it refuses.
    ordinary = [k for k, e in ev["benign"].items() if e.get("ordinary") and e.get("channel") == "tool_output"]

    def agg(c_or_fn, kind):
        keys = [f"attack::{p}" for p in pops] if kind == "attack" else [f"benign::{p}" for p in ordinary]
        xs = []
        for k in keys:
            xs += c_or_fn(k)
        return rate_with_ci(sum(xs), len(xs))

    def dec(c):
        return lambda k: [bool(e) for e, _ in r6["raw"][c][k]]

    def union17(k):
        return [a or b for a, b in zip(dec("B13")(k), dec("B14")(k))]

    def texts_of(k):
        kind, pop = k.split("::", 1)
        if kind == "attack":
            return [r.text for r in pops[pop]]
        from phase17.eval_round6 import _benign_pops
        return list(_benign_pops()[pop])

    def union18(k):
        return [a or b for a, b in zip(union17(k), _deb(texts_of(k)))]

    for c, kind, field in (("B13", "attack", "attacks_no_evidence"), ("B14", "attack", "attacks_no_evidence"),
                           ("B13", "benign", "ordinary_benign_no_evidence"),
                           ("B14", "benign", "ordinary_benign_no_evidence")):
        got, pub = agg(dec(c), kind), ev["aggregate"][c][field]
        if (got["k"], got["n"]) != (pub["k"], pub["n"]):
            raise SystemExit(f"{c} {field}: derived {got['k']}/{got['n']} != published {pub['k']}/{pub['n']}")
    out["aggregate_no_evidence"] = {
        "B17": {"attacks": agg(union17, "attack"), "ordinary_benign": agg(union17, "benign")},
        "B18": {"attacks": agg(union18, "attack"), "ordinary_benign": agg(union18, "benign")},
        "check": "derivation reproduces evidence_round6's B13/B14 no-evidence aggregates exactly"}
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    r = run()
    print(r["union_check"])
    print(f"\n{'family':26s} {'n':>4s} {'wk':>4s}   B13 no->ev       B17 no->ev       B18 no->ev"
          f"      B18 working no->ev")
    for fam, e in r["families"].items():
        cells = []
        for c in ("B13", "B17", "B18"):
            f = e[c]["full"]
            cells.append(f"{f['no_evidence']['rate']:5.1%}->{f['with_evidence']['rate']:5.1%}")
        w = e["B18"]["working"]
        wc = f"{w['no_evidence']['rate']:5.1%}->{w['with_evidence']['rate']:5.1%}" if w else "-"
        star = "*" if e["founding"] else " "
        print(f"{star}{fam:25s} {e['n']:4d} {e['n_working']:4d}   " + "   ".join(cells) + f"   {wc}")
    for c, v in r["ordinary_benign_fpr_with_evidence"].items():
        print(f"  ordinary-benign FPR with evidence, {c}: {v['k']}/{v['n']} = {v['rate']:.1%}")
    print("DONE")
