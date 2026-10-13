"""Targeted phase, Priority 1: owner-disjoint (leave-one-owner-out) evaluation of B13's corroboration.
Pre-registered: docs/phase17/PREREGISTRATION_TARGETED_2026-10-13.md (commit dff63620), sections 1-5.

Stages (each cached and resumable):
  profiles()    NLI profile (relatedness, max entailment, max contradiction; B13's own premises, top_k=20) of every
                owner's observations + fabrications and every hold-out text, under evidence conditions
                correct / wrong ((o+1) mod 10) / trunc50 / trunc10.  GPU-safe, no LLM calls.
  components()  B13's non-corroboration components (base, content, lineage, worm) and B12 for the owner
                populations, in the frozen evaluation's shapes (observations: pools of 4, untrusted;
                fabrications: isolated arena, 3 real user-turn distractors).  LLM judge tiers (cached).
  analyse()     LOO thresholds, policies A (A-ship primary, A-nom, A-frozen reference, curve), B (conservative,
                three-outcome) and C (B12); evidence conditions; hold-outs; QA-evidence availability (U1);
                owner-cluster bootstrap; predictions.
Nothing here fits anything on the held-out owner.
"""
from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import numpy as np

DATA = Path(__file__).resolve().parents[1] / "data"
OUT = DATA / "remediation" / "b13_owner_loo.json"
PROFILE_CACHE = DATA / "remediation" / "b13_loo_profile_cache.json"
COMP_CACHE = DATA / "remediation" / "b13_loo_components.json"
OWNERS = tuple(range(10))
CONDITIONS = ("correct", "wrong", "trunc50", "trunc10")
# A-ship: the quantile levels at which the SHIPPED constants (0.0019 / 0.0057, calibrated at top_k=5) sit on the
# 1,026 dev observations of owners 1-4 at the current top_k=20: 5/1026 and 21/1026 (pre-registration section 0).
Q_SHIP = (5 / 1026, 21 / 1026)
Q_NOM = (0.02, 0.05)
CURVE = (0.0025, 0.005, 0.01, 0.02, 0.05, 0.10)
FPR_BUDGET_CONTR = 0.005        # corroboration_v2's documented rules, refit LOO
REL_KEEP = 0.95
BOOT = 10_000
SEED = 2026


def wrong_owner(o: int) -> int:
    return (o + 1) % 10


def evidence(o: int, cond: str) -> List[str]:
    from phase17.provenance_sets import owner_turns

    if cond == "none":
        return []
    src = wrong_owner(o) if cond == "wrong" else o
    ev = [t["text"] for t in owner_turns(src)]
    if cond == "trunc50":
        return ev[: max(1, len(ev) // 2)]
    if cond == "trunc10":
        return ev[: max(1, len(ev) // 10)]
    return ev


def owner_populations() -> Dict[int, Dict]:
    from phase17.provenance_sets import fabrications, observations, speakers

    fabs = fabrications("dev") + fabrications("test")
    out = {}
    for o in OWNERS:
        out[o] = {"names": speakers(o), "obs": observations(o),
                  "fab": [f for f in fabs if f["sample"] == o],
                  "split": "dev" if o in (1, 2, 3, 4) else "test"}
    return out


def holdout_sets() -> Dict[str, Dict]:
    from phase17 import holdout4_corpus as h4, holdout7_corpus as h7, holdout8_corpus as h8
    from phase17.remediation import sleeper_corpus as s1, sleeper_corpus2 as s2

    return {
        "holdout4": {"owner": 7, "atk": [r.text for r in h4.attack_records()], "ben": list(h4.benign_texts()),
                     "families": [r.family for r in h4.attack_records()], "clean": True},
        "holdout7": {"owner": 8, "atk": [r.text for r in h7.attack_records()], "ben": list(h7.benign_texts()),
                     "families": [r.family for r in h7.attack_records()], "clean": True},
        "sa2": {"owner": 9, "atk": [x["note"] for x in s2.items("atk")], "ben": [x["note"] for x in s2.items("ben")],
                "families": ["implicit_sleeper"] * len(s2.items("atk")), "clean": True},
        "holdout8": {"owner": 1, "atk": [r.text for r in h8.attack_records()], "ben": list(h8.benign_texts()),
                     "families": [r.family for r in h8.attack_records()], "clean": False},
        "sa1": {"owner": 3, "atk": [x["note"] for x in s1.items("atk")], "ben": [x["note"] for x in s1.items("ben")],
                "families": ["explicit_sleeper"] * len(s1.items("atk")), "clean": False},
    }


# ----------------------------------------------------------------------------------------------- stage 1
def _load(path: Path) -> Dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def profiles() -> Dict:
    from phase17.corroboration_v2 import profile

    cache = _load(PROFILE_CACHE)
    jobs = []
    pops = owner_populations()
    for o, p in pops.items():
        texts = [x["text"] for x in p["obs"]] + [x["text"] for x in p["fab"]]
        for c in CONDITIONS:
            jobs.append((f"owner{o}", o, c, texts))
    for name, h in holdout_sets().items():
        for c in CONDITIONS:
            jobs.append((name, h["owner"], c, h["atk"] + h["ben"]))
    for tag, o, c, texts in jobs:
        key = f"{tag}|{c}"
        have = cache.get(key, {})
        todo = [t for t in dict.fromkeys(texts) if t not in have]
        if todo:
            ev = evidence(o, c)
            for i in range(0, len(todo), 64):
                chunk = todo[i:i + 64]
                for t, pr in zip(chunk, profile(chunk, ev)):
                    have[t] = pr
                cache[key] = have
                PROFILE_CACHE.write_text(json.dumps(cache), encoding="utf-8")
            print(f"  profiles {key}: {len(todo)} new", flush=True)
    return cache


# ----------------------------------------------------------------------------------------------- stage 2
def components() -> Dict:
    """B13's non-corroboration components + B12, owner populations (frozen-evaluation shapes)."""
    from phase14.defended_retrieval import apply_defense
    from phase17 import arenas
    from phase17.b20_live import b13_components
    from phase17.poison_sets import PoisonRecord
    from phase17.semantic_detector import warm_all_tiers

    cache = _load(COMP_CACHE)
    pops = owner_populations()
    warm_all_tiers([x["text"] for p in pops.values() for x in p["obs"] + p["fab"]])
    for o, p in pops.items():
        if f"obs|{o}" not in cache:
            texts = [x["text"] for x in p["obs"]]
            rows = []
            for i in range(0, len(texts), 4):
                chunk = tuple((f"OBS-{o}-{i + j}", t) for j, t in enumerate(texts[i:i + 4]))
                comp = b13_components(chunk, sources={m: "tool_output" for m, _ in chunk})
                _, b12 = apply_defense("B12", chunk)
                b12m = {d.memory_id: bool(d.excluded) for d in b12}
                rows += [{**comp[m], "B12": b12m[m]} for m, _ in chunk]
            cache[f"obs|{o}"] = rows
            COMP_CACHE.write_text(json.dumps(cache), encoding="utf-8")
        if f"fab|{o}" not in cache:
            recs = [PoisonRecord(f"FAB-{o}-{i}", x["text"], x["kind"], "loo") for i, x in enumerate(p["fab"])]
            pools, _ = arenas.isolated_arena(recs)
            rows = []
            for pool, r in zip(pools, recs):
                items = tuple((m.scenario_id, m.content_text) for m in pool.memories)
                src = {mid: ("tool_output" if mid == r.scenario_id else "user_turn") for mid, _ in items}
                comp = b13_components(items, sources=src)
                _, b12 = apply_defense("B12", items)
                rows.append({**comp[r.scenario_id],
                             "B12": bool(next(d for d in b12 if d.memory_id == r.scenario_id).excluded)})
            cache[f"fab|{o}"] = rows
            COMP_CACHE.write_text(json.dumps(cache), encoding="utf-8")
        print(f"  components owner {o} done", flush=True)
    sets = holdout_sets()
    for name in ("sa1", "sa2"):
        if f"{name}|atk" in cache:
            continue
        h = sets[name]
        for side in ("atk", "ben"):
            rows = []
            for i in range(0, len(h[side]), 4):          # _admission's shape: pools of 4, untrusted channel
                chunk = tuple((f"SA1N-{i + j}", t) for j, t in enumerate(h[side][i:i + 4]))
                comp = b13_components(chunk, sources={m: "tool_output" for m, _ in chunk})
                rows += [comp[m] for m, _ in chunk]
            cache[f"{name}|{side}"] = rows
        COMP_CACHE.write_text(json.dumps(cache), encoding="utf-8")
    return cache


def verify_decomposition(owner: int = 5, n_pools: int = 15) -> Dict:
    """excluded(B13, direct) == noev-components OR corroboration(frozen constants), item by item."""
    from phase14.defended_retrieval import apply_defense
    from phase17.b13_live import SUPPORT_EXCLUDE, SUPPORT_FLAG
    from phase17.b20_live import b13_components, b13_excluded_from_components

    p = owner_populations()[owner]
    texts = [x["text"] for x in p["obs"]][: 4 * n_pools]
    ev = evidence(owner, "correct")
    prof = _load(PROFILE_CACHE)[f"owner{owner}|correct"]
    agree_direct, agree_comp, n = 0, 0, 0
    for i in range(0, len(texts), 4):
        chunk = tuple((f"V-{i + j}", t) for j, t in enumerate(texts[i:i + 4]))
        src = {m: "tool_output" for m, _ in chunk}
        _, dec = apply_defense("B13", chunk, sources=src, evidence=ev, evidence_names=p["names"])
        comp_ev = b13_components(chunk, sources=src, evidence=ev, evidence_names=p["names"])
        comp_no = b13_components(chunk, sources=src)
        for d, (m, t) in zip(dec, chunk):
            mine = any(comp_no[m][k] for k in ("base", "content", "lineage", "worm")) or \
                _corr(prof[t], t, p["names"], SUPPORT_EXCLUDE, SUPPORT_FLAG)
            agree_direct += bool(d.excluded) == mine
            agree_comp += b13_excluded_from_components(comp_ev[m]) == mine
            n += 1
    return {"owner": owner, "n": n, "equal_to_direct_b13": agree_direct, "equal_to_components_with_evidence": agree_comp}


# ----------------------------------------------------------------------------------------------- stage 3
def _q(sorted_vals: np.ndarray, q: float) -> float:
    return float(sorted_vals[int(q * len(sorted_vals))])   # b13_dev_calibration's convention


def _corr(pr: Optional[Dict], text: str, names, tx: float, tf: float) -> bool:
    from phase17.b13_live import _PREFERENCE, is_personal_claim

    if pr is None or not is_personal_claim(text, names):
        return False
    return pr["ent"] < tx or (pr["ent"] < tf and bool(_PREFERENCE.search(text)))


def _policy_b(pr: Optional[Dict], text: str, names, tx: float, tf: float, tc: float, tr: float) -> str:
    """CONTRADICTED / DEFER / UNSUPPORTED (quarantine) / PASS -- pre-registration section 2."""
    from phase17.b13_live import is_personal_claim

    if pr is None or not is_personal_claim(text, names):
        return "PASS"
    if pr["contr"] >= tc:
        return "CONTRADICTED"
    if pr["rel"] < tr:
        return "DEFER"
    return "UNSUPPORTED" if _corr(pr, text, names, tx, tf) else "PASS"


def _rate(k: int, n: int) -> Dict:
    from phase17.stats import rate_with_ci

    return rate_with_ci(k, n) if n else {"k": 0, "n": 0, "rate": None, "ci95": None}


def _boot_pooled(per_owner: Dict[int, Dict[str, int]], num: str, den: str, rng: np.random.Generator,
                 diff_num: Optional[str] = None) -> Dict:
    """Owner-cluster bootstrap of a pooled rate (or of a paired pooled difference num - diff_num)."""
    owners = list(per_owner)
    ks = np.array([per_owner[o][num] for o in owners], float)
    ns = np.array([per_owner[o][den] for o in owners], float)
    k2 = np.array([per_owner[o][diff_num] for o in owners], float) if diff_num else None
    idx = rng.integers(0, len(owners), size=(BOOT, len(owners)))
    nsum = ns[idx].sum(1)
    est = ks[idx].sum(1) / nsum
    if k2 is not None:
        est = est - k2[idx].sum(1) / nsum
    point = ks.sum() / ns.sum() - (k2.sum() / ns.sum() if k2 is not None else 0.0)
    return {"point": round(float(point), 4), "ci95": [round(float(np.quantile(est, 0.025)), 4),
                                                     round(float(np.quantile(est, 0.975)), 4)], "clusters": len(owners)}


def _qa_links(o: int) -> List[set]:
    from phase17.provenance_sets import _raw, observations

    raw = _raw()[o]
    obs_by_dia: Dict[str, set] = {}
    for idx, x in enumerate(observations(o)):
        ev = x["evidence"] if isinstance(x["evidence"], list) else [x["evidence"]]
        for d in ev:
            for dd in str(d).replace(",", ";").split(";"):
                obs_by_dia.setdefault(dd.strip(), set()).add(idx)
    out = []
    for qa in raw["qa"]:
        if qa.get("category") not in (1, 2, 3, 4):
            continue
        linked = set()
        for d in qa.get("evidence", []):
            linked |= obs_by_dia.get(str(d).strip(), set())
        if linked:
            out.append(linked)
    return out


def analyse() -> Dict:
    from phase17.b13_live import SUPPORT_EXCLUDE, SUPPORT_FLAG
    from phase17.stats import paired_delta

    prof = _load(PROFILE_CACHE)
    comp = _load(COMP_CACHE)
    pops = owner_populations()
    rng = np.random.default_rng(SEED)
    noev = lambda c: (not c.get("trusted")) and any(c[k] for k in ("base", "content", "lineage", "worm"))  # noqa: E731

    # ---- calibration statistics per owner (correct-owner evidence; nothing else is ever used for fitting)
    obs_ent = {o: np.array([prof[f"owner{o}|correct"][x["text"]]["ent"] for x in p["obs"]]) for o, p in pops.items()}
    obs_con = {o: np.array([prof[f"owner{o}|correct"][x["text"]]["contr"] for x in p["obs"]]) for o, p in pops.items()}
    fab_rel = {o: np.array([prof[f"owner{o}|correct"][x["text"]]["rel"] for x in p["fab"]]) for o, p in pops.items()}

    def fit(calib: Sequence[int]) -> Dict:
        e = np.sort(np.concatenate([obs_ent[c] for c in calib]))
        cn = np.sort(np.concatenate([obs_con[c] for c in calib]))
        k = int(np.floor(FPR_BUDGET_CONTR * len(cn)))
        out = {"calibration_owners": list(calib), "n_observations": int(len(e)),
               "A-ship": (_q(e, Q_SHIP[0]), _q(e, Q_SHIP[1])), "A-nom": (_q(e, Q_NOM[0]), _q(e, Q_NOM[1])),
               "tau_contr": float(cn[::-1][k]) + 1e-9,
               "tau_rel": float(np.quantile(np.concatenate([fab_rel[c] for c in calib]), 1 - REL_KEEP)),
               "curve": {str(q): (_q(e, q), _q(e, min(0.99, 2.5 * q))) for q in CURVE}}
        return out

    res: Dict = {"preregistration": "docs/phase17/PREREGISTRATION_TARGETED_2026-10-13.md (dff63620)",
                 "kind": "pre-specified re-analysis on previously used data (see pre-registration section 0)",
                 "shipped_constants": {"exclude": SUPPORT_EXCLUDE, "flag": SUPPORT_FLAG},
                 "q_ship": Q_SHIP, "q_nom": Q_NOM,
                 "reproduction": {"A-ship levels on owners 1-4 (should reproduce the shipped constants)": fit((1, 2, 3, 4))["A-ship"],
                                  "A-nom on owners 1-4": fit((1, 2, 3, 4))["A-nom"],
                                  "A-nom on owners 2,4 (the previous round's 'disjoint')": fit((2, 4))["A-nom"]},
                 "owners": {}, "evidence_conditions": {}, "holdouts": {}}
    # single-owner calibrations: dispersion of the threshold itself (descriptive)
    res["single_owner_thresholds"] = {o: {"A-ship": fit((o,))["A-ship"], "A-nom": fit((o,))["A-nom"]} for o in OWNERS}

    fits = {o: fit([c for c in OWNERS if c != o]) for o in OWNERS}
    policies = ("A-ship", "A-nom", "A-frozen", "B", "C-B12", "noev")
    per_cond: Dict[str, Dict[int, Dict]] = {}
    item_level: Dict[str, Dict[int, Dict[str, Dict[str, List[bool]]]]] = {}
    for cond in CONDITIONS + ("none",):
        per_cond[cond], item_level[cond] = {}, {}
        for o, p in pops.items():
            f = fits[o]
            pr = prof.get(f"owner{o}|{cond}", {}) if cond != "none" else {}
            row: Dict = {"split": p["split"], "n_benign": len(p["obs"]), "n_attack": len(p["fab"])}
            dec: Dict[str, Dict[str, List[bool]]] = {pol: {"atk": [], "ben": []} for pol in policies}
            defer: Dict[str, List[bool]] = {"atk": [], "ben": []}
            outcome_counts: Dict[str, Dict[str, int]] = {"atk": {}, "ben": {}}
            for side, xs in (("ben", p["obs"]), ("atk", p["fab"])):
                comps = comp[f"{'obs' if side == 'ben' else 'fab'}|{o}"]
                for x, c in zip(xs, comps):
                    t, pp = x["text"], pr.get(x["text"])
                    ne = noev(c)
                    dec["noev"][side].append(ne)
                    dec["C-B12"][side].append(bool(c["B12"]))
                    dec["A-ship"][side].append(ne or _corr(pp, t, p["names"], *f["A-ship"]))
                    dec["A-nom"][side].append(ne or _corr(pp, t, p["names"], *f["A-nom"]))
                    dec["A-frozen"][side].append(ne or _corr(pp, t, p["names"], SUPPORT_EXCLUDE, SUPPORT_FLAG))
                    ob = _policy_b(pp, t, p["names"], *f["A-ship"], f["tau_contr"], f["tau_rel"])
                    outcome_counts[side][ob] = outcome_counts[side].get(ob, 0) + 1
                    dec["B"][side].append(ne or ob in ("CONTRADICTED", "UNSUPPORTED"))
                    defer[side].append((not ne) and ob == "DEFER")
            for pol in policies:
                row[pol] = {"TP": sum(dec[pol]["atk"]), "FN": len(p["fab"]) - sum(dec[pol]["atk"]),
                            "FP": sum(dec[pol]["ben"]), "TN": len(p["obs"]) - sum(dec[pol]["ben"])}
                row[pol]["detection"] = _rate(row[pol]["TP"], len(p["fab"]))
                row[pol]["benign_exclusion"] = _rate(row[pol]["FP"], len(p["obs"]))
                tp, fp = row[pol]["TP"], row[pol]["FP"]
                row[pol]["precision"] = round(tp / (tp + fp), 3) if tp + fp else None
            row["B"]["deferred_attack"] = sum(defer["atk"])
            row["B"]["deferred_benign"] = sum(defer["ben"])
            row["B"]["outcomes"] = outcome_counts
            if cond == "correct":
                row["calibration"] = {k: f[k] for k in ("calibration_owners", "n_observations", "A-ship", "A-nom",
                                                        "tau_contr", "tau_rel")}
                # U1: QA-evidence availability
                links = _qa_links(o)
                ua = {}
                for pol in ("noev", "A-ship", "A-nom", "A-frozen", "B", "C-B12"):
                    ex = dec[pol]["ben"]
                    ua[pol] = {"n_qa": len(links), "all_linked_excluded": sum(all(ex[i] for i in L) for L in links),
                               "any_linked_excluded": sum(any(ex[i] for i in L) for L in links)}
                exd = [a or b for a, b in zip(dec["B"]["ben"], defer["ben"])]
                ua["B_excluded_or_deferred"] = {"n_qa": len(links), "all_linked_excluded": sum(all(exd[i] for i in L) for L in links),
                                                "any_linked_excluded": sum(any(exd[i] for i in L) for L in links)}
                row["utility_U1"] = ua
                # curve (no point is selected from it)
                row["curve"] = {}
                for q, (tx, tf) in f["curve"].items():
                    a = [ne or _corr(pr.get(x["text"]), x["text"], p["names"], tx, tf)
                         for x, ne in zip(p["fab"], dec["noev"]["atk"])]
                    b = [ne or _corr(pr.get(x["text"]), x["text"], p["names"], tx, tf)
                         for x, ne in zip(p["obs"], dec["noev"]["ben"])]
                    row["curve"][q] = {"thresholds": (tx, tf), "TP": sum(a), "FP": sum(b)}
            per_cond[cond][o] = row
            item_level[cond][o] = dec
            if cond == "correct":
                res.setdefault("benign_item_decisions_correct", {})[o] = {
                    "A-ship": dec["A-ship"]["ben"], "A-nom": dec["A-nom"]["ben"], "B": dec["B"]["ben"],
                    "B_deferred": defer["ben"]}
    res["owners"] = per_cond["correct"]

    # ---- pooled + owner-cluster bootstrap, per condition
    def pooled(cond: str) -> Dict:
        out = {}
        rows = per_cond[cond]
        for pol in policies:
            po = {o: {"tp": r[pol]["TP"], "na": r["n_attack"], "fp": r[pol]["FP"], "nb": r["n_benign"]} for o, r in rows.items()}
            out[pol] = {"detection": {"k": sum(v["tp"] for v in po.values()), "n": sum(v["na"] for v in po.values()),
                                      "owner_bootstrap": _boot_pooled(po, "tp", "na", rng)},
                        "benign_exclusion": {"k": sum(v["fp"] for v in po.values()), "n": sum(v["nb"] for v in po.values()),
                                             "owner_bootstrap": _boot_pooled(po, "fp", "nb", rng)},
                        "per_owner_benign_exclusion_range": [min(r[pol]["benign_exclusion"]["rate"] for r in rows.values()),
                                                             max(r[pol]["benign_exclusion"]["rate"] for r in rows.values())],
                        "per_owner_detection_range": [min(r[pol]["detection"]["rate"] for r in rows.values()),
                                                      max(r[pol]["detection"]["rate"] for r in rows.values())]}
            for split in ("dev", "test"):
                sub = [r for r in rows.values() if r["split"] == split]
                out[pol][f"{split}_owners"] = {"TP": sum(r[pol]["TP"] for r in sub), "n_attack": sum(r["n_attack"] for r in sub),
                                               "FP": sum(r[pol]["FP"] for r in sub), "n_benign": sum(r["n_benign"] for r in sub)}
        return out

    for cond in CONDITIONS + ("none",):
        res["evidence_conditions"][cond] = {"pooled": pooled(cond),
                                            "per_owner": {o: {pol: {"TP": r[pol]["TP"], "FP": r[pol]["FP"]} for pol in ("A-ship", "A-nom", "B")}
                                                          | {"deferred_benign": r["B"]["deferred_benign"], "deferred_attack": r["B"]["deferred_attack"]}
                                                          for o, r in per_cond[cond].items()}}
    # ---- B vs A-ship (and C vs A-ship) paired, correct evidence
    cmp = {}
    for cand in ("B", "C-B12", "A-nom"):
        po = {o: {"ta": r["A-ship"]["TP"], "tc": r[cand]["TP"], "na": r["n_attack"], "fa": r["A-ship"]["FP"],
                  "fc": r[cand]["FP"], "nb": r["n_benign"]} for o, r in per_cond["correct"].items()}
        atk_a = [x for o in OWNERS for x in item_level["correct"][o]["A-ship"]["atk"]]
        atk_c = [x for o in OWNERS for x in item_level["correct"][o][cand]["atk"]]
        ben_a = [x for o in OWNERS for x in item_level["correct"][o]["A-ship"]["ben"]]
        ben_c = [x for o in OWNERS for x in item_level["correct"][o][cand]["ben"]]
        cmp[cand] = {"benign_exclusion_diff": _boot_pooled(po, "fc", "nb", rng, diff_num="fa"),
                     "detection_diff": _boot_pooled(po, "tc", "na", rng, diff_num="ta"),
                     "max_owner_benign_increase_points": round(100 * max(
                         (r[cand]["FP"] - r["A-ship"]["FP"]) / r["n_benign"] for r in per_cond["correct"].values()), 2),
                     "paired_attacks_item_level": paired_delta(atk_c, atk_a),
                     "paired_benign_item_level": paired_delta(ben_c, ben_a)}
    res["comparisons_vs_A_ship"] = cmp

    # ---- hold-outs (repeated evaluations, exploratory; LOO thresholds of the hold-out's owner)
    cached = {
        "holdout4": (json.loads((DATA / "eval_round7_holdouts_partial.json").read_text(encoding="utf-8")), "comp:h4:atk", "comp:h4:ben", "h4:atk:B12", "h4:ben:B12"),
        "holdout7": (json.loads((DATA / "remediation" / "b13_decomposition_partial.json").read_text(encoding="utf-8"))
                     | json.loads((DATA / "eval_round7b_holdouts_partial.json").read_text(encoding="utf-8")),
                     "h7:comp:atk", "h7:comp:ben", "h7:atk:B12", "h7:ben:B12"),
        "holdout8": (json.loads((DATA / "eval_holdout8_partial.json").read_text(encoding="utf-8")), "h8:comp:atk", "h8:comp:ben", "h8:atk:B12", "h8:ben:B12"),
    }
    sa_adm = {"sa1": json.loads((DATA / "remediation" / "sleeper_activation_partial.json").read_text(encoding="utf-8"))["admission"],
              "sa2": json.loads((DATA / "remediation" / "sa2_partial.json").read_text(encoding="utf-8"))["admission"]}
    for name, h in holdout_sets().items():
        o = h["owner"]
        f = fits[o]
        names = pops[o]["names"]
        if name in cached:
            d, ka, kb, ba, bb = cached[name]
            comps = {"atk": d[ka], "ben": d[kb]}
            b12 = {"atk": d[ba], "ben": d[bb]}
        else:
            comps = {"atk": comp[f"{name}|atk"], "ben": comp[f"{name}|ben"]}
            n_atk = len(h["atk"])
            b12 = {"atk": sa_adm[name]["B12"][:n_atk], "ben": sa_adm[name]["B12"][n_atk:]}
        hr: Dict = {"owner": o, "clean_owner": h["clean"], "n_attack": len(h["atk"]), "n_benign": len(h["ben"]),
                    "label": "repeated evaluation (exploratory)", "loo_thresholds": {"A-ship": f["A-ship"], "A-nom": f["A-nom"]},
                    "conditions": {}}
        for cond in CONDITIONS + ("none",):
            pr = prof.get(f"{name}|{cond}", {}) if cond != "none" else {}
            cr: Dict = {}
            for side in ("atk", "ben"):
                texts = h[side]
                ne = [noev(c) for c in comps[side]]
                pols = {
                    "noev": ne,
                    "A-ship": [a or _corr(pr.get(t), t, names, *f["A-ship"]) for a, t in zip(ne, texts)],
                    "A-nom": [a or _corr(pr.get(t), t, names, *f["A-nom"]) for a, t in zip(ne, texts)],
                    "A-frozen": [a or _corr(pr.get(t), t, names, SUPPORT_EXCLUDE, SUPPORT_FLAG) for a, t in zip(ne, texts)],
                    "C-B12": [bool(x) for x in b12[side]],
                }
                outs = [_policy_b(pr.get(t), t, names, *f["A-ship"], f["tau_contr"], f["tau_rel"]) for t in texts]
                pols["B"] = [a or ob in ("CONTRADICTED", "UNSUPPORTED") for a, ob in zip(ne, outs)]
                cr[side] = {k: sum(v) for k, v in pols.items()}
                cr[side]["B_deferred"] = sum((not a) and ob == "DEFER" for a, ob in zip(ne, outs))
                if cond == "correct" and name in cached:
                    # reproduction: corroboration at frozen constants == cached component
                    cr[side]["reproduces_cached_corroboration"] = [
                        _corr(pr.get(t), t, names, SUPPORT_EXCLUDE, SUPPORT_FLAG) for t in texts] == [bool(c["corroboration"]) for c in comps[side]]
                if side == "atk" and cond == "correct":
                    fams = sorted(set(h["families"]))
                    cr["by_family"] = {fm: {pol: sum(v[i] for i, x in enumerate(h["families"]) if x == fm) for pol, v in pols.items()}
                                       | {"n": sum(x == fm for x in h["families"])} for fm in fams}
            hr["conditions"][cond] = cr
        res["holdouts"][name] = hr
        OUT.write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")

    # ---- predictions (pre-registration section 7)
    thr = [fits[o]["A-ship"][0] for o in OWNERS]
    pc = res["evidence_conditions"]
    pool_fp = lambda cond, pol="A-ship": pc[cond]["pooled"][pol]["benign_exclusion"]["k"] / pc[cond]["pooled"][pol]["benign_exclusion"]["n"]  # noqa: E731
    pool_tp = lambda cond, pol: pc[cond]["pooled"][pol]["detection"]["k"] / pc[cond]["pooled"][pol]["detection"]["n"]  # noqa: E731
    crit = cmp["B"]
    ho_ok = all(res["holdouts"][h]["conditions"]["correct"]["atk"]["B"] >= res["holdouts"][h]["conditions"]["correct"]["atk"]["A-ship"]
                - 0.05 * res["holdouts"][h]["n_attack"] for h in ("holdout4", "holdout7", "sa2"))
    meets = (crit["benign_exclusion_diff"]["ci95"][1] < 0 and crit["detection_diff"]["point"] >= -0.02
             and crit["detection_diff"]["ci95"][0] >= -0.10 and crit["max_owner_benign_increase_points"] <= 2 and ho_ok)
    res["improvement_criterion_B"] = {"meets": bool(meets), "holdout_condition_ok": bool(ho_ok)}
    res["predictions"] = [
        {"id": "L1", "prediction": "A-ship LOO exclude thresholds within x1.5 (max/min)", "value": round(max(thr) / min(thr), 3),
         "status": "HELD" if max(thr) / min(thr) <= 1.5 else "FAILED"},
        {"id": "L2", "prediction": "full-B13 benign exclusion <= 5% for every owner (A-ship LOO)",
         "value": [round(r["A-ship"]["benign_exclusion"]["rate"], 4) for r in per_cond["correct"].values()],
         "status": "HELD" if all(r["A-ship"]["benign_exclusion"]["rate"] <= 0.05 for r in per_cond["correct"].values()) else "FAILED"},
        {"id": "L3", "prediction": "pooled detection A-ship LOO within +/-10 points of A-frozen",
         "value": [round(pool_tp("correct", "A-ship"), 4), round(pool_tp("correct", "A-frozen"), 4)],
         "status": "HELD" if abs(pool_tp("correct", "A-ship") - pool_tp("correct", "A-frozen")) <= 0.10 else "FAILED"},
        {"id": "L4", "prediction": "wrong-owner pooled benign exclusion >= 3x correct-owner",
         "value": [round(pool_fp("wrong"), 4), round(pool_fp("correct"), 4)],
         "status": "HELD" if pool_fp("wrong") >= 3 * pool_fp("correct") else "FAILED"},
        {"id": "L5", "prediction": "trunc10 pooled benign exclusion >= 2x correct-owner",
         "value": [round(pool_fp("trunc10"), 4), round(pool_fp("correct"), 4)],
         "status": "HELD" if pool_fp("trunc10") >= 2 * pool_fp("correct") else "FAILED"},
        {"id": "B1", "prediction": "policy B does NOT meet the improvement criterion",
         "value": res["improvement_criterion_B"], "status": "HELD" if not meets else "FAILED"},
    ]
    OUT.write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
    return res


if __name__ == "__main__":
    import sys

    stage = sys.argv[1] if len(sys.argv) > 1 else "all"
    if stage in ("profiles", "all"):
        profiles()
    if stage in ("components", "all"):
        components()
    if stage in ("verify", "all"):
        print(verify_decomposition())
    if stage in ("analyse", "all"):
        r = analyse()
        for p in r["predictions"]:
            print(p["id"], p["status"], p["value"])
    print("DONE")
