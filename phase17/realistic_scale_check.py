"""Phase 17 fix (external review round 4, 2026-09-28) -- every Phase 17 test before this
used `N_DISTRACTORS = 3` (`phase17/arenas.py::isolated_arena`): a real assistant's memory
store holds hundreds to thousands of memories, and neither (a) whether a poison memory is
even retrieved when it must compete against many more real memories, nor (b) B12's own
real per-item cost at that scale, had ever been measured.

Uses `phase17.arenas.realistic_arena` (100 real benign distractors per pool by default,
drawn from LoCoMo + ConvoMem, vs. the standard 3) on a sample of held-out novel-mechanism
records, and reports both B12's detection outcome (does it still catch what it caught at
n=3?) and real wall-clock cost per pool.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

OUT = Path(__file__).parent / "data" / "realistic_scale_results.json"


def run(n_samples: int = 24, n_distractors: int = 100, seed: int = 17) -> dict:
    import random

    from phase14.defended_retrieval import CONFIG_B12_STACKED, apply_defense
    from phase17.arenas import isolated_arena, realistic_arena
    from phase17.novel_attacks_extended import novel_records_extended

    recs = novel_records_extended()
    rng = random.Random(seed)
    families = sorted({r.family for r in recs})
    sample = []
    for fam in families:
        cands = [r for r in recs if r.family == fam]
        rng.shuffle(cands)
        sample += cands[: max(1, n_samples // len(families))]
    sample = sample[:n_samples] if n_samples < len(sample) else sample

    # baseline: the SAME records at the standard n=3 distractor scale, for direct comparison.
    small_pools, _ = isolated_arena(sample)
    big_pools, big_truth = realistic_arena(sample, n_distractors=n_distractors)

    rows = []
    for small_pool, big_pool, r in zip(small_pools, big_pools, sample):
        small_items = tuple((m.scenario_id, m.content_text) for m in small_pool.memories)
        t0 = time.monotonic()
        _, small_dec = apply_defense(CONFIG_B12_STACKED, small_items)
        small_elapsed = time.monotonic() - t0
        small_d = next(d for d in small_dec if d.memory_id == r.scenario_id)

        big_items = tuple((m.scenario_id, m.content_text) for m in big_pool.memories)
        t0 = time.monotonic()
        _, big_dec = apply_defense(CONFIG_B12_STACKED, big_items)
        big_elapsed = time.monotonic() - t0
        big_d = next(d for d in big_dec if d.memory_id == r.scenario_id)

        distractor_fp = sum(1 for d in big_dec if d.memory_id != r.scenario_id and d.excluded)
        distractor_flagged = sum(1 for d in big_dec if d.memory_id != r.scenario_id and d.action != "ALLOW")

        rows.append({
            "scenario_id": r.scenario_id, "family": r.family,
            "n_distractors_small": len(small_items) - 1, "n_distractors_big": len(big_items) - 1,
            "small_scale_action": small_d.action, "small_scale_excluded": small_d.excluded,
            "big_scale_action": big_d.action, "big_scale_excluded": big_d.excluded,
            "detection_changed": small_d.excluded != big_d.excluded,
            "small_scale_seconds": round(small_elapsed, 2), "big_scale_seconds": round(big_elapsed, 2),
            "big_scale_benign_distractors_excluded": distractor_fp,
            "big_scale_benign_distractors_flagged": distractor_flagged,
            "big_scale_benign_n": len(big_items) - 1,
        })
        print(rows[-1], flush=True)

    n = len(rows)
    out = {
        "n_samples": n, "n_distractors_big": n_distractors,
        "small_scale_excluded": sum(r["small_scale_excluded"] for r in rows),
        "big_scale_excluded": sum(r["big_scale_excluded"] for r in rows),
        "n_detection_changed": sum(r["detection_changed"] for r in rows),
        "total_small_scale_seconds": sum(r["small_scale_seconds"] for r in rows),
        "total_big_scale_seconds": sum(r["big_scale_seconds"] for r in rows),
        "total_benign_distractors_tested": sum(r["big_scale_benign_n"] for r in rows),
        "total_benign_distractors_excluded": sum(r["big_scale_benign_distractors_excluded"] for r in rows),
        "total_benign_distractors_flagged": sum(r["big_scale_benign_distractors_flagged"] for r in rows),
        "rows": rows,
    }
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


if __name__ == "__main__":
    r = run()
    print("DONE")
    print("small_scale_excluded:", r["small_scale_excluded"], "/", r["n_samples"])
    print("big_scale_excluded:", r["big_scale_excluded"], "/", r["n_samples"])
    print("n_detection_changed:", r["n_detection_changed"])
    print("total_small_scale_seconds:", round(r["total_small_scale_seconds"], 1))
    print("total_big_scale_seconds:", round(r["total_big_scale_seconds"], 1))
    print("benign distractors excluded:", r["total_benign_distractors_excluded"], "/", r["total_benign_distractors_tested"])
    print("benign distractors flagged:", r["total_benign_distractors_flagged"], "/", r["total_benign_distractors_tested"])
