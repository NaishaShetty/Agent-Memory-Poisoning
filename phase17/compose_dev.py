"""DEV run of neutralisation composed with detection, on the injection development bed.

Attacks: the 266 externally-authored dev attacks; matched benign: 400 toxic-chat dev prompts
(disjoint from hold-out 5). Detector decisions come from `dev_round7.json` (no re-scoring);
compliance raw and framed is measured by `compose_neutralise.compliance`, reusing neutralise_v2's
cache for the 120 attacks it already ran. The output selects NOTHING automatically: it is the
evidence on which the hold-out pre-registration's configurations and predictions are written.
"""
from __future__ import annotations

import json
from pathlib import Path

DATA = Path(__file__).parent / "data"
OUT = DATA / "compose_dev.json"


def run() -> dict:
    from phase17.compose_neutralise import compliance, summarise
    from phase17.external_attacks import external_records
    from phase17.neutralise import WINNER

    d7 = json.loads((DATA / "dev_round7.json").read_text(encoding="utf-8"))
    raw = d7["raw_injection"]
    atk = [r.text for r in external_records()]
    c_raw = compliance(atk, "raw")
    c_neu = compliance(atk, WINNER)
    dets = {c: (raw[c]["atk"], raw[c]["ben"]) for c in raw}
    out = {"bed": "injection dev: external dev attacks (266) vs toxic-chat dev benign (400)",
           "frame": WINNER, "caveat": "dev attacks and dev benign come from different sources",
           **summarise(c_raw, c_neu, dets)}
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    r = run()
    print(f"compliance raw {r['compliance_raw']['rate']:.1%} -> framed {r['compliance_framed']['rate']:.1%}"
          f"  {r['paired_framed_vs_raw']}")
    for d, v in r["by_detector"].items():
        print(f"\n  {d}: recall {v['detector_recall']['rate']:.1%}, benign FPR {v['detector_benign_fpr']['rate']:.1%}")
        for p, x in v["policies"].items():
            print(f"    {p:34s} harm {x['harm_k']:3d}/{x['n']} = {x['harm_rate']:5.1%}   benign excluded "
                  f"{x['benign_exclusion_rate']:5.1%}   benign framed {x['benign_share_framed']:5.1%}")
    print("DONE")
