"""Gap 1: how much does owner-conversation corroboration depend on the evidence and on who calibrated it?
NEW ANALYSIS (not pre-registered), on frozen hold-out texts; no parameter is fitted on any hold-out.

Arms, per hold-out (HO4 owner 7, HO7 owner 8, HO8 owner 1) and SA-1 (owner 3):
  full         the owner's whole conversation (must reproduce the cached corroboration firings: check)
  trunc10      only the first 10% of the owner's turns (sparse evidence)
  wrong_owner  another owner's conversation (evidence present but irrelevant)
and two threshold sets:
  frozen       b13_live.SUPPORT_EXCLUDE / SUPPORT_FLAG (calibrated on LoCoMo 1-4, incl. HO8's and SA-1's owners)
  disjoint     the SAME calibration procedure (b13_dev_calibration: 2% / 5% quantiles of the owners' own
               observation memories' support) re-run on owners 2 and 4 only -- excludes owners 1 and 3.
B13 = (base | content | lineage | worm, cached) OR corroboration(arm, thresholds) on untrusted channels.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

import numpy as np

DATA = Path(__file__).resolve().parents[1] / "data"
OUT = DATA / "remediation" / "corroboration_robustness.json"
CACHE = DATA / "remediation" / "corroboration_support_cache.json"


def _support(texts: List[str], evidence: List[str], names, cache: Dict, tag: str) -> List[float]:
    from phase17.b13_live import is_personal_claim, support_scores

    todo = [t for t in dict.fromkeys(texts) if f"{tag}|{t}" not in cache and is_personal_claim(t, names)]
    if todo:
        for t, s in zip(todo, support_scores(todo, evidence)):
            cache[f"{tag}|{t}"] = float(s)
        CACHE.write_text(json.dumps(cache), encoding="utf-8")
    return [cache.get(f"{tag}|{t}") for t in texts]          # None = not a personal claim -> not checked


def _corr(s, text, thr) -> bool:
    from phase17.b13_live import _PREFERENCE

    return s is not None and (s < thr[0] or (s < thr[1] and bool(_PREFERENCE.search(text))))


def disjoint_thresholds(cache: Dict) -> Dict:
    from phase17.provenance_sets import observations, owner_turns

    obs_s = []
    for s in (2, 4):
        ev = [t["text"] for t in owner_turns(s)]
        obs = [o["text"] for o in observations(s)]
        from phase17.b13_live import support_scores
        key = f"calib_obs_{s}"
        if key not in cache:
            cache[key] = [float(x) for x in support_scores(obs, ev)]
            CACHE.write_text(json.dumps(cache), encoding="utf-8")
        obs_s += cache[key]
    o = sorted(obs_s)
    return {"exclude": float(o[int(0.02 * len(o))]), "flag": float(o[int(0.05 * len(o))]), "n_observations": len(o),
            "owners": [2, 4]}


def run() -> Dict:
    from phase17 import holdout4_corpus as h4, holdout7_corpus as h7, holdout8_corpus as h8
    from phase17.b13_live import SUPPORT_EXCLUDE, SUPPORT_FLAG
    from phase17.provenance_sets import owner_turns
    from phase17.remediation.sleeper_corpus import items as sa_items
    from phase17.stats import rate_with_ci

    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    dis = disjoint_thresholds(cache)
    thr = {"frozen": (SUPPORT_EXCLUDE, SUPPORT_FLAG), "disjoint": (dis["exclude"], dis["flag"])}
    p4 = json.loads((DATA / "eval_round7_holdouts_partial.json").read_text(encoding="utf-8"))
    p8 = json.loads((DATA / "eval_holdout8_partial.json").read_text(encoding="utf-8"))
    p7 = json.loads((DATA / "remediation" / "b13_decomposition_partial.json").read_text(encoding="utf-8"))
    sets = {
        "holdout4": (7, 8, [r.text for r in h4.attack_records()], h4.benign_texts(), p4["comp:h4:atk"], p4["comp:h4:ben"]),
        "holdout7": (8, 7, [r.text for r in h7.attack_records()], h7.benign_texts(), p7["h7:comp:atk"], p7["h7:comp:ben"]),
        "holdout8": (1, 7, [r.text for r in h8.attack_records()], h8.benign_texts(), p8["h8:comp:atk"], p8["h8:comp:ben"]),
        "sa1": (3, 7, [x["note"] for x in sa_items("atk")], [x["note"] for x in sa_items("ben")], None, None),
    }
    out: Dict = {"kind": "NEW ANALYSIS (not pre-registered); frozen texts; no fitting on hold-outs",
                 "thresholds": {"frozen": {"exclude": SUPPORT_EXCLUDE, "flag": SUPPORT_FLAG, "owners": [1, 2, 3, 4]},
                                "disjoint": dis}, "sets": {}}
    for name, (owner, wrong, atk, ben, ca, cb) in sets.items():
        turns = owner_turns(owner)
        names = sorted({t["speaker"] for t in turns})
        ev_full = [t["text"] for t in turns]
        evs = {"full": ev_full, "trunc10": ev_full[: max(1, len(ev_full) // 10)],
               "wrong_owner": [t["text"] for t in owner_turns(wrong)]}
        res = {"owner": owner, "wrong_owner": wrong, "n_attacks": len(atk), "n_benign": len(ben),
               "evidence_turns": {k: len(v) for k, v in evs.items()}, "arms": {}}
        for ek, ev in evs.items():
            sa_ = _support(atk, ev, names, cache, f"{name}|{ek}")
            sb_ = _support(ben, ev, names, cache, f"{name}|{ek}")
            for tk, th in thr.items():
                corr_a = [_corr(s, t, th) for s, t in zip(sa_, atk)]
                corr_b = [_corr(s, t, th) for s, t in zip(sb_, ben)]
                arm = {"corroboration_recall": rate_with_ci(sum(corr_a), len(atk)),
                       "corroboration_benign_fpr": rate_with_ci(sum(corr_b), len(ben))}
                if ca is not None:
                    rest_a = [any(c[k] for k in ("base", "content", "lineage", "worm")) for c in ca]
                    rest_b = [any(c[k] for k in ("base", "content", "lineage", "worm")) for c in cb]
                    arm["B13_recall"] = rate_with_ci(sum(a or b for a, b in zip(rest_a, corr_a)), len(atk))
                    arm["B13_benign_fpr"] = rate_with_ci(sum(a or b for a, b in zip(rest_b, corr_b)), len(ben))
                    if ek == "full" and tk == "frozen":
                        arm["reproduces_cached_corroboration"] = (
                            corr_a == [bool(c["corroboration"]) for c in ca] and corr_b == [bool(c["corroboration"]) for c in cb])
                res["arms"][f"{ek}|{tk}"] = arm
        out["sets"][name] = res
        OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
        print(name, "done", flush=True)
    return out


if __name__ == "__main__":
    r = run()
    print("disjoint thresholds:", r["thresholds"]["disjoint"], "frozen:", r["thresholds"]["frozen"])
    for name, s in r["sets"].items():
        for k, a in s["arms"].items():
            print(f"{name:9s} {k:20s} corr {a['corroboration_recall']['k']:3d}/{s['n_attacks']} FP {a['corroboration_benign_fpr']['k']:3d}/{s['n_benign']}"
                  + (f" | B13 {a['B13_recall']['k']}/{s['n_attacks']} FP {a['B13_benign_fpr']['k']}/{s['n_benign']}" if "B13_recall" in a else "")
                  + (f" | reproduces {a['reproduces_cached_corroboration']}" if "reproduces_cached_corroboration" in a else ""))
