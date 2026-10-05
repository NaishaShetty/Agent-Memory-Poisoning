"""Are B13/B17/B18's shipped operating points DOMINATED? (closing item 1)

`holdout3_matched_fpr.py` could not include B13, B17 or B18 because they are rule compositions
rather than scores, so the first statement of that gap was simply "they have no knob, and their
weakness on this corpus is therefore not an operating-point artifact". That is true of B13 and
it is NOT true of B17 and B18, which is worth correcting rather than leaving as a caveat:

    B17(t) = B13 OR (B14 score >= t)
    B18(t) = B17(t) OR (deberta >= its frozen oracle threshold)

B14 exposes a continuous score, so sweeping t traces a genuine one-parameter family for both
unions. Their SHIPPED points are the t that B14's own frozen threshold implies, and the question
that matters is whether those shipped points lie on the achievable frontier or below it. A point
below its own family's frontier is dominated: the same configuration, with one threshold moved,
is strictly better on both axes, which is a defect of calibration rather than of design and is
fixable without inventing anything.

B13 alone genuinely has no knob and appears as a single point, so for B13 the original statement
stands unchanged.

The sweep is calibrated the same way as the matched-FPR comparison -- thresholds come from the
DISJOINT dev snapshot, never from the frozen corpus -- and every point is read once off the
frozen corpus. No new model calls: all three scorers' values are already cached.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, List

import numpy as np

DATA = Path(__file__).parent / "data"
OUT = DATA / "holdout3_frontier.json"
SCORES = DATA / "external_baseline_scores.json"
DEV_TARGETS = tuple(round(x, 4) for x in np.arange(0.002, 0.302, 0.01))


def _deberta_flags(texts) -> List[bool]:
    thr = json.loads((DATA / "eval_round5.json").read_text(encoding="utf-8"))[
        "baseline_thresholds"]["deberta_pi_v2"]["oracle"]
    cache = json.loads(SCORES.read_text(encoding="utf-8"))
    out = []
    for t in texts:
        k = "deberta_pi_v2:" + hashlib.sha256(t.encode("utf-8")).hexdigest()[:24]
        out.append(float(cache.get(k, 0.0)) >= thr)
    return out


def run() -> dict:
    from phase17.b14_live import scores as b14_scores
    from phase17.holdout3_corpus import attack_records, benign_texts, verify_frozen
    from phase17.holdout3_dev_benign import dev_benign_texts, verify_disjoint
    from phase17.stats import rate_with_ci

    assert verify_frozen() and verify_disjoint()
    ev = json.loads((DATA / "eval_holdout3.json").read_text(encoding="utf-8"))
    atk = [r.text for r in attack_records()]
    ben = benign_texts()
    dev = dev_benign_texts()

    # B13's fixed per-item decisions on the frozen corpus, from the saved evaluation.
    b13_a = [bool(x) for x in ev["raw"]["B13"]["attack"]]
    b13_b = [bool(x) for x in ev["raw"]["B13"]["benign"]]
    deb_a, deb_b = _deberta_flags(atk), _deberta_flags(ben)

    sa = np.asarray([float(x) for x in b14_scores(atk)])
    sb = np.asarray([float(x) for x in b14_scores(ben)])
    sd = np.sort(np.asarray([float(x) for x in b14_scores(dev)]))[::-1]

    def thr_at(target: float) -> float:
        k = int(np.floor(target * len(sd)))
        return float(sd[0]) + 1e-9 if k <= 0 else float(sd[k - 1])

    curves: Dict[str, List[dict]] = {"B17": [], "B18": []}
    for tg in DEV_TARGETS:
        t = thr_at(tg)
        a17 = [b or s >= t for b, s in zip(b13_a, sa)]
        b17 = [b or s >= t for b, s in zip(b13_b, sb)]
        a18 = [x or d for x, d in zip(a17, deb_a)]
        b18 = [x or d for x, d in zip(b17, deb_b)]
        for name, aa, bb in (("B17", a17, b17), ("B18", a18, b18)):
            curves[name].append({"dev_target": tg, "threshold": t,
                                 "recall": round(float(np.mean(aa)), 4),
                                 "fpr": round(float(np.mean(bb)), 4),
                                 "youden": round(float(np.mean(aa) - np.mean(bb)), 4)})

    shipped = {c: {"recall": ev["configs"][c]["attack_recall"]["rate"],
                   "fpr": ev["configs"][c]["matched_benign_fpr"]["rate"]}
               for c in ("B13", "B17", "B18")}
    for c in ("B17", "B18"):
        s = shipped[c]
        # Dominated iff some swept point is at least as good on BOTH axes and better on one.
        dom = [p for p in curves[c]
               if p["recall"] >= s["recall"] - 1e-9 and p["fpr"] <= s["fpr"] + 1e-9
               and (p["recall"] > s["recall"] + 1e-9 or p["fpr"] < s["fpr"] - 1e-9)]
        best = max(curves[c], key=lambda p: p["youden"])
        s["is_dominated"] = bool(dom)
        s["dominating_points"] = dom[:3]
        s["best_youden_on_family"] = best
        s["shipped_youden"] = round(s["recall"] - s["fpr"], 4)
        s["youden_headroom"] = round(best["youden"] - (s["recall"] - s["fpr"]), 4)

    out = {"n_attacks": len(atk), "n_benign": len(ben), "n_dev": len(dev),
           "calibration": "B14's threshold swept over dev-snapshot FPR targets; B13's decisions "
                          "and deberta's frozen oracle threshold held fixed",
           "note": "B13 alone is rule-based with no knob and appears only as a shipped point; the "
                   "unions DO have a knob through their B14 component, so the earlier blanket "
                   "statement that none of the three could be compared at matched operating "
                   "points was wrong for B17 and B18.",
           "shipped": shipped, "curves": curves, "no_model_calls": True}
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    r = run()
    for c in ("B13", "B17", "B18"):
        s = r["shipped"][c]
        print(f"\n{c} shipped: recall {s['recall']:.1%}  FPR {s['fpr']:.1%}  "
              f"recall-FPR {s.get('shipped_youden', s['recall']-s['fpr']):+.1%}")
        if "is_dominated" in s:
            print(f"  dominated by a point on its own family: {s['is_dominated']}")
            b = s["best_youden_on_family"]
            print(f"  best on family: recall {b['recall']:.1%} FPR {b['fpr']:.1%} "
                  f"(recall-FPR {b['youden']:+.1%}) at dev target {b['dev_target']:.1%}")
            print(f"  headroom left on the table: {s['youden_headroom']:+.1%}")
        else:
            print("  rule-based, no threshold to sweep: the original statement stands")
    print("DONE")
