"""Phase 6's own ablation, re-run with the semantic retrieval variants beside the originals (2026-10-09).

Owner-authorised post-freeze fix, done additively: `pipeline.SEMANTIC_RETRIEVAL_CONFIGS` (B2s, B4s,
B5s, B7s, B8s) are the recommended retrieval configurations; the original B2-B8 are unchanged so
every number recorded with them stays reproducible. This runs Phase 6's own driver
(`run_b0_b7.run_all`) on its own corpus for both sets -- no new mechanism, no fitting.
"""
from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).parent / "data" / "phase6_semantic_variants.json"


def run() -> dict:
    from phase6.defense.orchestration.pipeline import (B2_RETRIEVAL_ONLY, B4_ADMISSION_RETRIEVAL,
                                                       B5_RETRIEVAL_PROPAGATION, B7_ALL_THREE, B8_ALL_FOUR,
                                                       SEMANTIC_RETRIEVAL_CONFIGS)
    from phase6.evaluation.ablations.run_b0_b7 import run_all

    originals = (B2_RETRIEVAL_ONLY, B4_ADMISSION_RETRIEVAL, B5_RETRIEVAL_PROPAGATION, B7_ALL_THREE, B8_ALL_FOUR)
    res, excl = run_all(originals + SEMANTIC_RETRIEVAL_CONFIGS)
    out = {"corpus": "Phase 6's own 75-scenario ablation corpus (run_b0_b7.all_pools)", "configs": {},
           "exclusions": [e.__dict__ for e in excl] if excl and hasattr(excl[0], "__dict__") else [str(e) for e in excl]}
    for m in res:
        out["configs"][m.config_name] = {"poison_detection_rate": m.poison_detection_rate,
                                         "benign_false_positive_rate": m.benign_false_positive_rate,
                                         "n_poison": m.n_poison, "n_benign": m.n_benign,
                                         "per_family": dict(m.per_attack_family_detection)}
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    r = run()
    for c, v in r["configs"].items():
        print(f"{c:4s} detect {v['poison_detection_rate']:.1%}  FPR {v['benign_false_positive_rate']:.1%}  "
              f"(n_poison {v['n_poison']}, n_benign {v['n_benign']})")
    print("DONE")
