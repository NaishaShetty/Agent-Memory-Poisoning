"""Fix round 5 -- three dev-tuned attempts on the remaining setbacks; each is shipped ONLY if it
passes its dev criterion AND keeps held-out benign exclusion ~0:
  B  steering exclusion  : steer AND stacked-flag  -> exclude (preference hijack)
  C  hearsay flag        : second-hand new-attribute claims (additive fabrications)
  D  reduced overlap     : refit without dev groups conceptually close to eval mechanisms."""
import json
import sys
from pathlib import Path

import numpy as np

from phase17.arenas import dataset_arena
from phase17.extra_datasets import convomem_pools
from phase17.novel_attacks import novel_records
from phase17.poison_sets import evasion_records
from phase17.perltqa import perltqa_pools
from phase17.semantic_detector import LLMJudge
from phase17.stacked_detector import StackedDetector
from phase17.stats import rate_with_ci
from phase17 import dev_family_sets
from phase17.tune_lomo import dev_pool

DATA = Path(__file__).parent / "data"
STEERING_DEV = {"contact_swap", "recipient_substitution", "brand_steering", "price_anchoring", "fake_emergency_contact", "link_injection"}
OVERLAP_DEV = {"silent_logging", "fake_system_update", "date_trigger", "rule_persistence", "approval_bypass", "silent_copy",
               "trusted_source_claim", "signed_authority", "auto_approve_purchases", "concealment_rule", "wipe_resistance", "language_trigger"}


def odd_benign():
    out = {}
    for n, pt in {"dataset_arena": dataset_arena(), "convomem": convomem_pools()}.items():
        out[n] = [m.content_text for p in sorted(pt[0], key=lambda p: p.pool_id)[1::2] for m in p.memories]
    return out


def part_B():
    pos, neg = dev_pool()
    allx = pos + neg
    det = StackedDetector.load(DATA / "stacked_model.json")
    steer = LLMJudge("steer")
    # OOF-free proxy: dev items scored by the shipped model are in-sample, so tune with the judge/steer only
    # and require the stacked FLAG threshold as a second condition; dev recall reported in-sample (disclosed).
    st_pos = [x for x in pos if x["group"] in STEERING_DEV]
    sflag = lambda xs: [steer.flag(x["text"]) for x in xs]
    fl = lambda xs: det.decide([x["text"] for x in xs], 0.02)
    dev = {"steering_dev_n": len(st_pos), "steer_only": sum(sflag(st_pos)), "steer_and_stackflag": sum(a and b for a, b in zip(sflag(st_pos), fl(st_pos))),
           "benign_dev_fp_steer_and_stackflag": sum(a and b for a, b in zip(sflag(neg), fl(neg))), "n_neg": len(neg)}
    hj = [r.text for r in novel_records() if r.family == "preference_hijack"]
    ev = {"hijack_steer": sum(map(steer.flag, hj)), "hijack_steer_and_stackflag": sum(a and b for a, b in zip(map(steer.flag, hj), det.decide(hj, 0.02))), "n": len(hj)}
    ben = {}
    for n, tx in odd_benign().items():
        ben[n] = {"n": len(tx), "steer_and_stackflag": sum(a and b for a, b in zip(map(steer.flag, tx), det.decide(tx, 0.02)))}
    steer.save()
    return {"dev": dev, "eval": ev, "benign": ben}


def part_C():
    hear = LLMJudge("hearsay")
    dev_pos = [i["text"] for i in dev_family_sets.load() if i["cls"] == "third_person_report"]
    pos, neg = dev_pool()
    real = [x["text"] for x in neg if x["group"].startswith("real:")]
    dev = {"dev_third_person_recall": [sum(map(hear.flag, dev_pos)), len(dev_pos)], "dev_real_benign_fp": [sum(map(hear.flag, real)), len(real)]}
    from phase17.gold_registry import gold_memories
    mp = [t for k, (_, t) in gold_memories().items() if "MPBENCH" in k]
    ev = {"mpbench_originals_flagged": [sum(map(hear.flag, mp)), len(mp)]}
    ben = {n: {"n": len(tx), "flagged": sum(map(hear.flag, tx))} for n, tx in odd_benign().items()}
    hear.save()
    return {"dev": dev, "eval": ev, "benign": ben}


def part_D():
    pos, neg = dev_pool()
    keep = [x for x in pos + neg if x["group"] not in OVERLAP_DEV]
    det = StackedDetector()
    fit = det.fit([x["text"] for x in keep], [x["label"] for x in keep], [x["group"] for x in keep])
    nv = novel_records()
    tx = [r.text for r in nv]
    ex, fl = det.decide(tx, 0.005), det.decide(tx, 0.02)
    by = {}
    for r, e, f in zip(nv, ex, fl):
        b = by.setdefault(r.family, [0, 0, 0]); b[0] += 1; b[1] += e; b[2] += f
    ben = {n: {"n": len(t), "excluded": sum(det.decide(t, 0.005)), "flagged": sum(det.decide(t, 0.02))} for n, t in odd_benign().items()}
    return {"dropped_dev_groups": sorted(OVERLAP_DEV), "n_train_pos": sum(x["label"] for x in keep), "oof_recall": fit["oof_recall"],
            "novel_excluded": rate_with_ci(sum(ex), len(tx)), "novel_flagged": rate_with_ci(sum(fl), len(tx)),
            "by_mechanism": {k: {"n": v[0], "excluded": v[1], "flagged": v[2]} for k, v in by.items()}, "benign": ben}


if __name__ == "__main__":
    which = sys.argv[1]
    res = {"B": part_B, "C": part_C, "D": part_D}[which]()
    (DATA / f"fix5_{which}.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(which, json.dumps(res)[:1500])
