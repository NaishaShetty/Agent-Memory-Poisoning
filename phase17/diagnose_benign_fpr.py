"""WHICH rule over-fires on in-the-wild benign prose? Diagnosed on DEV data only.

Hold-out 3's matched benign half gave 16.7% (B12) and 33.5% (B13) false positives against 0.09%
on ordinary conversational memory. Two causes are possible and they call for opposite responses:

  (a) the items are not benign memories at all (persona definitions, standing instructions,
      control tokens, filler) -- a labelling artifact, addressed by `benign_validity_audit.py`;
  (b) a specific rule genuinely over-fires on long instruction-shaped prose -- a defense defect,
      addressed by fixing that rule.

Distinguishing them requires per-rule attribution, and attributing on hold-out 3 and then
fixing would be tuning on the only clean estimate this project has for the union configurations.
So this runs on `holdout3_dev_benign.py`: the earlier snapshot of the same source, asserted
disjoint from the frozen corpus (110 overlapping items were dropped from the DEV side).

For each dev item it records the base content action, whether the corroboration gate considered
it a personal claim, its support score, and the final action, so the share of exclusions
attributable to each rule is measured rather than guessed.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

OUT = Path(__file__).parent / "data" / "diagnose_benign_fpr.json"
N = 200
BATCH = 4


def run(n: int = N) -> dict:
    from phase14.defended_retrieval import HARD_MITIGATION_ACTIONS, apply_defense
    from phase17 import b13_live
    from phase17.evidence_round6 import _evidence
    from phase17.holdout3_dev_benign import dev_benign_texts, verify_disjoint
    from phase17.stats import rate_with_ci

    assert verify_disjoint(), "DEV benign set overlaps the frozen hold-out; refusing to diagnose"
    texts = dev_benign_texts()[:n]
    ev, names = _evidence()
    print(f"diagnosing {len(texts)} DEV benign items (disjoint from frozen hold-out 3)", flush=True)

    rows: List[dict] = []
    for i in range(0, len(texts), BATCH):
        chunk = [(f"DEVB-{i+j}", t) for j, t in enumerate(texts[i:i + BATCH])]
        src = {mid: "tool_output" for mid, _ in chunk}
        _, d12 = apply_defense("B12", tuple(chunk))
        _, d13 = apply_defense("B13", tuple(chunk), sources=src)
        _, d13e = apply_defense("B13", tuple(chunk), sources=src, evidence=ev,
                                evidence_names=names)
        a12 = {d.memory_id: d.action for d in d12}
        a13 = {d.memory_id: d.action for d in d13}
        a13e = {d.memory_id: d.action for d in d13e}
        # The corroboration gate: would this text even be considered a personal claim?
        for mid, t in chunk:
            rows.append({
                "id": mid, "len": len(t),
                "is_personal_claim": bool(b13_live.is_personal_claim(t, names)),
                "B12": a12[mid], "B13_no_evidence": a13[mid], "B13_with_evidence": a13e[mid],
                "B12_excluded": a12[mid] in HARD_MITIGATION_ACTIONS,
                "B13_excluded": a13[mid] in HARD_MITIGATION_ACTIONS,
                "B13ev_excluded": a13e[mid] in HARD_MITIGATION_ACTIONS,
            })
        if (i // BATCH) % 10 == 0:
            print(f"  {len(rows)}/{len(texts)}", flush=True)

    n_ = len(rows)
    pc = [r for r in rows if r["is_personal_claim"]]
    out = {
        "n": n_, "source": "holdout3_dev_benign (regular_2023_05_07), NOT disjoint: round 7 (R7-1) found these were hold-out 3 prompts under another wrapper",
        "fpr": {
            "B12": rate_with_ci(sum(r["B12_excluded"] for r in rows), n_),
            "B13_no_evidence": rate_with_ci(sum(r["B13_excluded"] for r in rows), n_),
            "B13_with_evidence": rate_with_ci(sum(r["B13ev_excluded"] for r in rows), n_),
        },
        "corroboration_gate": {
            "share_treated_as_personal_claim": rate_with_ci(len(pc), n_),
            "fpr_among_personal_claims": rate_with_ci(
                sum(r["B13ev_excluded"] for r in pc), len(pc)) if pc else None,
            "fpr_among_non_claims": rate_with_ci(
                sum(r["B13ev_excluded"] for r in rows if not r["is_personal_claim"]),
                n_ - len(pc)) if n_ - len(pc) else None,
        },
        # Attribution: exclusions B13 adds over B12, split by whether the gate fired.
        "attribution": {
            "b12_content_only": sum(r["B12_excluded"] for r in rows),
            "added_by_B13_without_evidence": sum(
                r["B13_excluded"] and not r["B12_excluded"] for r in rows),
            "added_by_corroboration_with_evidence": sum(
                r["B13ev_excluded"] and not r["B13_excluded"] for r in rows),
            "added_on_items_the_gate_called_personal_claims": sum(
                r["B13ev_excluded"] and not r["B13_excluded"] and r["is_personal_claim"]
                for r in rows),
        },
        "rows": rows[:60],
    }
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    r = run()
    f = r["fpr"]
    print(f"\nDEV benign FPR (n={r['n']}):")
    for k, v in f.items():
        print(f"  {k:22s} {v['k']:4d}/{v['n']:<4d} = {v['rate']:6.1%}")
    g = r["corroboration_gate"]
    print(f"\ncorroboration gate: {g['share_treated_as_personal_claim']['rate']:.1%} of benign "
          f"prose is treated as a personal claim")
    if g["fpr_among_personal_claims"]:
        print(f"  FPR among those        {g['fpr_among_personal_claims']['rate']:.1%}")
    if g["fpr_among_non_claims"]:
        print(f"  FPR among the rest     {g['fpr_among_non_claims']['rate']:.1%}")
    print("\nattribution:", json.dumps(r["attribution"], indent=1))
    print("DONE")
