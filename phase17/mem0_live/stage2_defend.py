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


def main():
    data = json.loads((HERE / "stage1_out.json").read_text(encoding="utf-8"))
    base = {c.task_id: c for c in build_track_b_cases()}
    text_by_id = {mid: t for c in data for mid, t in c["items"]}
    res = {"poison_retrieved_by_mem0": {}, "by_kind": {}}
    for kind in ("poison_original", "poison_plain", "poison_embedded"):
        cs = [c for c in data if c["kind"] == kind]
        from phase17.stats import rate_with_ci
        res["poison_retrieved_by_mem0"][kind] = rate_with_ci(sum(c["poison_id"] in c["retrieved_ids"] for c in cs), len(cs))
    for cfg in CONFIGS:
        agg = {}
        for c in data:
            items = tuple((mid, text_by_id[mid]) for mid in c["retrieved_ids"] if mid in text_by_id)
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
