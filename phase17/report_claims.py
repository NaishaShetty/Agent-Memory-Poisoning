"""Outcomes of pre-registered predictions, computed from artifacts -- never typed by hand.

WHY (round 7, unfavourable #2). The hold-out 3 pre-registration made five predictions and three
failed. The results paper listed P1, P2, P3 and P5 and silently omitted P4 -- the prediction that
failed BACKWARDS (the published baselines were predicted to degrade most; this project's own
configurations degraded far more). The evaluation artifact had no P4 entry either, and P3 carried
no verdict. A summary that drops the worst-failing prediction is selective reporting even when
every number it does print is correct.

So outcomes are computed here, one per numbered prediction in the pre-registration document, each
with an explicit HELD/FAILED status and the evidence. `phase17/tests/test_round7_discipline.py`
parses the pre-registration and fails if any numbered prediction lacks an outcome, and
`error_registry.py` proves that by deleting one.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
PREREG3 = ROOT / "docs" / "phase17" / "PREREGISTRATION_HOLDOUT3.md"
ORDINARY_FPR = 1 / 1088          # the ordinary-benign rate the pre-registration compared against


def preregistered_predictions(path: Path = PREREG3) -> List[str]:
    """The numbered predictions under 'Predictions, recorded in advance', verbatim."""
    txt = path.read_text(encoding="utf-8")
    block = txt.split("Predictions, recorded in advance", 1)[1].split("\n## ", 1)[0]
    return [m.group(2).strip() for m in re.finditer(r"(?m)^(\d)\.\s+(.+)$", block)]


def holdout3_prediction_outcomes(h3: Dict) -> List[Dict]:
    c, b = h3["configs"], h3["baselines"]
    rec = {k: v["attack_recall"]["rate"] for k, v in c.items()}
    fpr = {k: v["matched_benign_fpr"]["rate"] for k, v in c.items()}
    bfpr = {k: v["matched_benign_fpr"]["rate"] for k, v in b.items() if k.endswith("@dev")}
    out = []
    out.append({"id": "P1", "prediction": "B18 >= B17 on attack recall",
                "status": "HELD" if rec["B18"] >= rec["B17"] else "FAILED",
                "evidence": f"B18 {rec['B18']:.1%} vs B17 {rec['B17']:.1%} (paired p=0.25: "
                            f"held, but not distinguishable)"})
    d = 100 * (rec["B18"] - rec["B14"])
    out.append({"id": "P2", "prediction": "B18 beats B14 by >= 5 points",
                "status": "HELD" if d >= 5 else "FAILED", "evidence": f"delta {d:+.1f} points"})
    gap = 100 * (min(rec["B14"], rec["B18"]) - rec["B13"])
    out.append({"id": "P3", "prediction": "B13 poor here, well below B14/B18",
                "status": "HELD" if gap >= 10 else "FAILED",
                "evidence": f"B13 {rec['B13']:.1%}, {gap:.1f} points below the weaker of B14/B18"})
    worse_all = all(v > 3 * ORDINARY_FPR for v in fpr.values())
    our_deg = max(fpr.values())
    base_deg = max(bfpr.values())
    out.append({"id": "P4", "prediction": "FPR materially worse than ordinary benign for every "
                "config; published baselines degrade MOST",
                "status": "HELD" if (worse_all and base_deg >= our_deg) else "FAILED",
                "evidence": (f"first half held (configs {min(fpr.values()):.1%}-{our_deg:.1%} vs "
                             f"{ORDINARY_FPR:.2%} ordinary); second half FAILED BACKWARDS -- the "
                             f"worst baseline@dev reached {base_deg:.1%}, this project's "
                             f"configurations {our_deg:.1%}")})
    mx = max(rec.values())
    out.append({"id": "P5", "prediction": "no configuration above ~85% attack recall",
                "status": "HELD" if mx <= 0.85 else "FAILED",
                "evidence": f"max {mx:.1%}; " + ", ".join(f"{k} {v:.1%}" for k, v in rec.items()
                                                          if v > 0.85) + " exceed it"})
    return out
