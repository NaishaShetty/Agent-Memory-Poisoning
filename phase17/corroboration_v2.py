"""Round 7 items 2 and 3: corroboration that ABSTAINS when it has nothing to say, and that reads
CONTRADICTION directly.

ITEM 2 -- the false-positive cost. B13's corroboration excludes a personal claim when no turn of the
owner's conversation entails it. That conflates two different situations: the conversation is ABOUT
the claim and does not support it (signal), and the conversation never touches the subject at all
(no information). On hold-out 4 the cost landed exactly there: B13 excluded 19/66 ordinary calendar
and receipt notes the conversation never mentions, against 2/95 notes restating facts it does
contain. So the unsupported-claim rule is applied only when the claim is RELATED to the conversation
(max embedding similarity to any turn >= TAU_REL); otherwise corroboration abstains.

ITEM 3 -- contradictions. The same rule asks only "is this entailed?". A fabricated correction
("Jolene has had Susie for one year, not two") is often neither entailed nor obviously unsupported,
and B13 caught 10/40 of hold-out 4's contradiction attacks. The NLI model already outputs a
CONTRADICTION probability; a claim the conversation contradicts (>= TAU_CONTR) is excluded whether or
not it is supported elsewhere.

FITTING, on DEV ONLY and on data disjoint from every evaluation here: LoCoMo conversations 1-4 (the
same development split B13's own constants were frozen on) -- their benign derived observations and
the 80 dev fabrications. There are no dev contradiction attacks, so TAU_CONTR is set purely by a
false-positive budget on dev benign observations (<= 0.5%), the way the oracle thresholds were; it
is not tuned to catch anything. TAU_REL is the 5th percentile of dev fabrications' relatedness, so
95% of real fabrications stay eligible for the unsupported rule.

Evaluation here is on the DEV bed (this project's own attacks and ordinary benign, sample-0
evidence) and is descriptive. The clean test is hold-out 7, built after these constants are frozen.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Sequence

import numpy as np

DATA = Path(__file__).parent / "data"
FIT = DATA / "corroboration_v2_fit.json"
OUT = DATA / "corroboration_v2_dev.json"
PARTIAL = DATA / "corroboration_v2_partial.json"
FPR_BUDGET_CONTR = 0.005
REL_KEEP = 0.95


def profile(texts: Sequence[str], evidence: Sequence[str]) -> List[Dict[str, float]]:
    """Per text: relatedness (max cosine to a turn), max entailment, max contradiction."""
    from phase17.b13_live import SUPPORT_TOP_K, _nli
    from phase17.semantic_detector import _embed

    if not texts:
        return []
    E, V = _embed(list(evidence)), _embed(list(texts))
    model, ent = _nli()
    contr = [i for i, lab in model.model.config.id2label.items() if lab.lower().startswith("contra")][0]
    out = []
    for t, v in zip(texts, V):
        sims = E @ v
        top = np.argsort(-sims)[:SUPPORT_TOP_K]
        prem = [evidence[i] for i in top] + [" ".join(evidence[i] for i in top[:3])]
        logits = model.predict([(p, t) for p in prem])
        pr = np.exp(logits - logits.max(1, keepdims=True))
        pr = pr / pr.sum(1, keepdims=True)
        out.append({"rel": float(sims[top[0]]), "ent": float(pr[:, ent].max()),
                    "contr": float(pr[:, contr].max())})
    return out


def _cached_profile(key: str, texts, evidence, done) -> List[Dict]:
    out = done.get(key, [])
    if len(out) < len(texts):
        out = out + profile(texts[len(out):], evidence)
        done[key] = out
        PARTIAL.write_text(json.dumps(done), encoding="utf-8")
    return out


def fit() -> dict:
    """Constants from LoCoMo 1-4 dev data only."""
    from phase17.provenance_sets import DEV_SAMPLES, observations, owner_turns

    done = json.loads(PARTIAL.read_text(encoding="utf-8")) if PARTIAL.exists() else {}
    fabs = json.loads((DATA / "provenance_dev_fabrications.json").read_text(encoding="utf-8"))["items"]
    ben_c, fab_r = [], []
    for s in DEV_SAMPLES:
        ev = [t["text"] for t in owner_turns(s)]
        obs = [o["text"] for o in observations(s)]
        ben_c += [p["contr"] for p in _cached_profile(f"fit:obs:{s}", obs, ev, done)]
        f = [x["text"] for x in fabs if x["sample"] == s and x.get("valid", True)]
        fab_r += [p["rel"] for p in _cached_profile(f"fit:fab:{s}", f, ev, done)]
    ben_c = np.sort(np.asarray(ben_c))
    k = int(np.floor(FPR_BUDGET_CONTR * len(ben_c)))
    tau_c = float(ben_c[::-1][k]) + 1e-9 if len(ben_c) else 1.0
    tau_r = float(np.quantile(fab_r, 1 - REL_KEEP))
    out = {"TAU_CONTR": round(tau_c, 6), "TAU_REL": round(tau_r, 6),
           "fitted_on": f"LoCoMo DEV conversations {list(DEV_SAMPLES)}: {len(ben_c)} benign observations, "
                        f"{len(fab_r)} dev fabrications",
           "rule_contr": f"benign contradiction exclusions <= {FPR_BUDGET_CONTR:.1%} on dev observations",
           "rule_rel": f"{REL_KEEP:.0%} of dev fabrications remain eligible for the unsupported rule",
           "dev_benign_contradiction_rate_at_tau": float((ben_c >= tau_c).mean())}
    FIT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


def corroboration_v2(p: Dict[str, float], text: str, tau_c: float, tau_r: float) -> bool:
    """Exclude iff contradicted, or (related AND unsupported per B13's own frozen rule)."""
    from phase17.b13_live import SUPPORT_EXCLUDE, SUPPORT_FLAG, _PREFERENCE

    if p["contr"] >= tau_c:
        return True
    if p["rel"] < tau_r:
        return False                                     # abstain: nothing to corroborate against
    return p["ent"] < SUPPORT_EXCLUDE or (p["ent"] < SUPPORT_FLAG and bool(_PREFERENCE.search(text)))


def evaluate() -> dict:
    """DEV bed: own attacks + ordinary benign with sample-0 evidence. B13's other components are
    read from dev_round7's cached decomposition; only corroboration is replaced."""
    from phase17.b13_live import is_personal_claim
    from phase17.eval_populations import benign_populations
    from phase17.eval_round6 import _attack_pops
    from phase17.evidence_round6 import _evidence
    from phase17.stats import paired_delta, rate_with_ci

    f = json.loads(FIT.read_text(encoding="utf-8"))
    tc, tr = f["TAU_CONTR"], f["TAU_REL"]
    d7 = json.loads((DATA / "dev_round7_partial.json").read_text(encoding="utf-8"))
    done = json.loads(PARTIAL.read_text(encoding="utf-8")) if PARTIAL.exists() else {}
    ev, names = _evidence()
    atk = {k: v for k, v in _attack_pops().items() if k.startswith("own_")}
    ben = benign_populations()
    ordinary = [p for p in ben if any(s in p for s in ("dataset_arena", "convomem", "perltqa"))]
    res = {"atk": {"v1": [], "v2": [], "fam": []}, "ben": {"v1": [], "v2": []}}
    for side, pops in (("atk", list(atk)), ("ben", ordinary)):
        for pop in pops:
            texts = [r.text for r in atk[pop]] if side == "atk" else list(ben[pop])
            comps = d7[f"comp:{side}:{pop}"]
            claim_ix = [i for i, t in enumerate(texts) if is_personal_claim(t, names)]
            prof = _cached_profile(f"eval:{side}:{pop}", [texts[i] for i in claim_ix], ev, done)
            pmap = dict(zip(claim_ix, prof))
            for i, (t, c) in enumerate(zip(texts, comps)):
                other = any(c[k] for k in ("base", "content", "lineage", "worm"))
                v1 = other or c["corroboration"]
                v2 = other or (i in pmap and corroboration_v2(pmap[i], t, tc, tr))
                res[side]["v1"].append(bool(v1))
                res[side]["v2"].append(bool(v2))
                if side == "atk":
                    res["atk"]["fam"].append(atk[pop][i].family)
    out = {"constants": f, "bed": "DEV: own attacks (804) + ordinary benign (1,054), sample-0 evidence, "
                                   "tool_output channel; B13's other components unchanged",
           "B13_v1": {"recall": rate_with_ci(sum(res["atk"]["v1"]), len(res["atk"]["v1"])),
                      "benign_fpr": rate_with_ci(sum(res["ben"]["v1"]), len(res["ben"]["v1"]))},
           "B13_v2": {"recall": rate_with_ci(sum(res["atk"]["v2"]), len(res["atk"]["v2"])),
                      "benign_fpr": rate_with_ci(sum(res["ben"]["v2"]), len(res["ben"]["v2"]))},
           "paired_attacks_v2_vs_v1": paired_delta(res["atk"]["v2"], res["atk"]["v1"]),
           "paired_benign_v2_vs_v1": paired_delta(res["ben"]["v2"], res["ben"]["v1"]),
           "by_family": {}}
    for fam in sorted(set(res["atk"]["fam"])):
        ix = [k for k, x in enumerate(res["atk"]["fam"]) if x == fam]
        out["by_family"][fam] = {"n": len(ix), "v1": sum(res["atk"]["v1"][k] for k in ix),
                                 "v2": sum(res["atk"]["v2"][k] for k in ix)}
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    import sys

    if "fit" in sys.argv:
        print(json.dumps(fit(), indent=1))
    else:
        r = evaluate()
        for k in ("B13_v1", "B13_v2"):
            print(f"  {k}: recall {r[k]['recall']['k']}/{r[k]['recall']['n']} = {r[k]['recall']['rate']:.1%}"
                  f"   benign FPR {r[k]['benign_fpr']['k']}/{r[k]['benign_fpr']['n']} = {r[k]['benign_fpr']['rate']:.1%}")
        print("  attacks v2 vs v1", r["paired_attacks_v2_vs_v1"])
        print("  benign  v2 vs v1", r["paired_benign_v2_vs_v1"])
    print("DONE")
