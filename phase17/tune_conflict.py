"""DEV-only: does the specific-change supersession test (v2) separate legit updates
from plain conflicts AND forged supersessions better than v1?"""
import json
from pathlib import Path
import numpy as np
from phase17 import conflict_check as cc, conflict_sets
from phase17.judge_scores import roc_auc

def main():
    pairs = [p for p in conflict_sets.load() if p["split"] == "dev"]
    res = {}
    for v in (1, 2):
        sc = {p["id"]: cc.pair_scores(p["a"], p["b"], v) for p in pairs}
        pos = [sc[p["id"]][1] for p in pairs if p["kind"] == "legit_update"]
        neg = [sc[p["id"]][1] for p in pairs if p["kind"] in ("plain_conflict", "forged_supersession")]
        fs = [sc[p["id"]][1] for p in pairs if p["kind"] == "forged_supersession"]
        res[f"v{v}"] = {"auc_legit_vs_forged": roc_auc(pos, neg), "mean_legit": float(np.mean(pos)), "mean_forged_sup": float(np.mean(fs)),
                        "n": [len(pos), len(neg)]}
        print(v, res[f"v{v}"], flush=True)
    Path(__file__).parent.joinpath("data", "conflict_tuning.json").write_text(json.dumps(res, indent=2))

if __name__ == "__main__":
    main()
