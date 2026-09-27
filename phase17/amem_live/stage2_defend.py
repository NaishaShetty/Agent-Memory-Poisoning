"""Stage 2 (main interpreter): run the defenses on what LIVE A-mem-sys actually retrieved (stage 1) and
measure (a) poison exclusion, (b) forged-answer rate through the same Track B answer runner,
(c) benign exclusion on real LoCoMo cases -- closing 'the defense has never been tested against a live
A-MEM instance' (Phase 6 limitations #12/#13)."""
import json
from pathlib import Path

from phase14.defended_retrieval import (
    CONFIG_B0_NO_DEFENSE, CONFIG_B9_RISK_COMPOSED, CONFIG_B11_GENERALIZED, CONFIG_B12_STACKED, apply_defense,
)
from phase14.track_b_poison import TrackBCase, build_track_b_cases, run_track_b_case
from phase17.stats import rate_with_ci

HERE = Path(__file__).parent
CONFIGS = (CONFIG_B0_NO_DEFENSE, CONFIG_B9_RISK_COMPOSED, CONFIG_B11_GENERALIZED, CONFIG_B12_STACKED)


def main():
    data = json.loads((HERE / "stage1_out.json").read_text(encoding="utf-8"))
    base = {c.task_id: c for c in build_track_b_cases()}
    res = {"n_stores": len(data), "stores_with_evolved_links": sum(1 for c in data if any(n["links"] for n in c["notes"].values())),
           "poison_retrieved_by_amem": {}, "by_kind": {}}
    for kind in ("poison_original", "poison_plain", "poison_embedded"):
        cs = [c for c in data if c["kind"] == kind]
        res["poison_retrieved_by_amem"][kind] = rate_with_ci(sum(c["poison_id"] in c["retrieved_ids"] for c in cs), len(cs))
    for cfg in CONFIGS:
        agg = {}
        for c in data:
            items = tuple((r["id"], r["content"] or "") for r in c["retrieved"])
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
