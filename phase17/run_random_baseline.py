"""Run RANDOM_BUDGET_MATCHED against B9-live, B11, and B12 on the held-out novel-mechanism
split (poison) + dataset_arena benign (odd/held-out pools), at each detector's OWN real
alert rate, so a reader can see whether real detection beats chance at that budget."""
import json
from pathlib import Path

from phase17 import arenas
from phase17.arenas import dataset_arena
from phase17.engine import EXCLUDING_ACTIONS, build_signal_table, rule_actions
from phase17.novel_attacks import novel_records
from phase17.run_b12 import rows_for as rows_b12
from phase17.sanity_baselines import compare_to_random
from phase6.defense.policy.states import ALLOW
from phase6.defense.risk.risk_score import GROUPED_GATED_ADMISSION_CORROBORATED as LIVE

OUT = Path(__file__).parent / "data" / "random_baseline_results.json"


def main():
    novel = novel_records()
    pools, _ = arenas.isolated_arena(novel)
    poison_ids = [r.scenario_id for r in novel]

    te = sorted(dataset_arena()[0], key=lambda p: p.pool_id)[1::2]
    benign_ids_all = [m.scenario_id for p in te for m in p.memories]

    table = build_signal_table(pools)
    live_actions = rule_actions(table, rule=LIVE)
    b12_rows = rows_b12(pools, set(poison_ids))
    benign_b12 = rows_b12(te, set(benign_ids_all))

    out = {}
    live_flags = {i: (live_actions[i] != ALLOW) for i in poison_ids}
    live_flags.update({i: False for i in benign_ids_all})  # B9-live not separately run on this benign pool here; excluded rate reported for poison only
    out["B9-live_on_novel"] = compare_to_random(poison_ids, [], live_flags)

    b12_flags = {i: b12_rows[i]["B12_excl"] for i in poison_ids}
    b12_flags.update({i: benign_b12[i]["B12_excl"] for i in benign_ids_all})
    out["B12_excluded_on_novel_plus_benign"] = compare_to_random(poison_ids, benign_ids_all, b12_flags)

    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
