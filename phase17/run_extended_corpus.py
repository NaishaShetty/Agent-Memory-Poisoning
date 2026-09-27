"""Evaluate the 140-instance extended corpus (held_out_extended) with the live B9 rule, G1 and B12,
by attack class, with Wilson intervals. Benign FPR is unchanged (same benign pools as run_b12)."""
import json
from pathlib import Path

from phase17 import arenas
from phase17.corpus_extended import extended_records
from phase17.engine import EXCLUDING_ACTIONS, build_signal_table, rule_actions
from phase17.run_b12 import KEYS, rows_for
from phase17.stats import rate_with_ci
from phase6.defense.policy.states import ALLOW
from phase6.defense.risk.risk_score import GROUPED_GATED_ADMISSION_CORROBORATED as LIVE

OUT = Path(__file__).parent / "data" / "extended_corpus_results.json"


def main():
    rs = extended_records()
    pools, _ = arenas.isolated_arena(rs)
    ids = {r.scenario_id for r in rs}
    rows = rows_for(pools, ids)
    base = rule_actions(build_signal_table(pools), rule=LIVE)
    out = {"n": len(rs), "total": {k: rate_with_ci(sum(rows[r.scenario_id][k] for r in rs), len(rs)) for k in KEYS},
           "base_live_flagged": rate_with_ci(sum(base[r.scenario_id] != ALLOW for r in rs), len(rs)),
           "base_live_excluded": rate_with_ci(sum(base[r.scenario_id] in EXCLUDING_ACTIONS for r in rs), len(rs)), "by_class": {}}
    for c in sorted({r.family for r in rs}):
        cr = [r for r in rs if r.family == c]
        out["by_class"][c] = {"n": len(cr), **{k: sum(rows[r.scenario_id][k] for r in cr) for k in ("B12_flag", "B12_excl")},
                              "base_flag": sum(base[r.scenario_id] != ALLOW for r in cr), "base_excl": sum(base[r.scenario_id] in EXCLUDING_ACTIONS for r in cr)}
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    f = lambda x: f"{x['k']}/{x['n']}"
    print("DONE", out["n"], "B12 excl", f(out["total"]["B12_excl"]), "flag", f(out["total"]["B12_flag"]), "base flag", f(out["base_live_flagged"]),
          "base excl", f(out["base_live_excluded"]), out["by_class"])


if __name__ == "__main__":
    main()
