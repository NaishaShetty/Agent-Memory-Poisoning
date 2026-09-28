"""Stage 2 (main interpreter): run the defenses on what LIVE Mem0 actually retrieved
(stage 1), closing the 'Mem0 was never tested live' half of the memory-foundation
generalization axis, alongside the already-closed A-MEM half."""
import json
from pathlib import Path

from phase14.defended_retrieval import (
    CONFIG_B0_NO_DEFENSE, CONFIG_B9_RISK_COMPOSED, CONFIG_B11_GENERALIZED, CONFIG_B12_STACKED, apply_defense,
)
from phase14.track_b_poison import TrackBCase, build_track_b_cases, run_track_b_case

HERE = Path(__file__).parent
CONFIGS = (CONFIG_B0_NO_DEFENSE, CONFIG_B9_RISK_COMPOSED, CONFIG_B11_GENERALIZED, CONFIG_B12_STACKED)


def resolve_case_items(case: dict) -> tuple:
    """THIS case's own (memory_id, text) pairs for its own retrieved_ids -- pulled out of
    `main()`'s loop (external review round 2, 2026-09-28) so the regression test in
    `phase17/tests/test_live_foundation_stages.py` calls the REAL function instead of
    re-implementing the same logic inline, which would not have caught a regression."""
    text_by_id = dict(case["items"])  # THIS case's own pairs only
    return tuple((mid, text_by_id[mid]) for mid in case["retrieved_ids"] if mid in text_by_id)


def main():
    data = json.loads((HERE / "stage1_out.json").read_text(encoding="utf-8"))
    base = {c.task_id: c for c in build_track_b_cases()}
    # BUG FIX (found by external review, 2026-09-28): this MUST be built per-case, not as
    # one global dict across all 27 cases. The original/plain/embedded variants of the SAME
    # parent all reuse the same `poison_id` string as their memory_id (by design, so
    # cross-variant comparisons line up) -- a single global `{mid: text for c in data for
    # mid, text in c["items"]}` therefore let each later case's variant text silently
    # overwrite the earlier one under the same key, so every "original"/"plain" case was
    # actually scored against whichever variant happened to be last in `data` (usually
    # "embedded"). Every prior number from this script (this file's own git history) is
    # WRONG and is superseded by the corrected run this fix produces.
    res = {"poison_retrieved_by_mem0": {}, "by_kind": {}}
    for kind in ("poison_original", "poison_plain", "poison_embedded"):
        cs = [c for c in data if c["kind"] == kind]
        from phase17.stats import rate_with_ci
        res["poison_retrieved_by_mem0"][kind] = rate_with_ci(sum(c["poison_id"] in c["retrieved_ids"] for c in cs), len(cs))
    for cfg in CONFIGS:
        agg = {}
        for c in data:
            items = resolve_case_items(c)
            if not items:
                continue
            _, dec = apply_defense(cfg, items)
            ex = {d.memory_id for d in dec if d.excluded}
            a = agg.setdefault(c["kind"], {"n": 0, "poison_excluded": 0, "benign_excluded": 0, "forged": 0, "gold": 0})
            a["n"] += 1
            a["benign_excluded"] += len(ex - {c["poison_id"]})
            if c["poison_id"]:
                a["poison_excluded"] += c["poison_id"] in ex
                orig = base[c["id"].split("-plain")[0].split("-embedded")[0]]
                tb = TrackBCase(c["id"], orig.attack_family, orig.target_scenario_id, orig.question, orig.gold_answer,
                                orig.forged_claim, items)
                r = run_track_b_case(tb, cfg)
                a["forged"] += bool(r["matches_forged"]); a["gold"] += bool(r["matches_gold"])
        res["by_kind"][cfg] = agg
        print(cfg, agg, flush=True)
    (HERE / "stage2_results.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print("DONE")


if __name__ == "__main__":
    main()
