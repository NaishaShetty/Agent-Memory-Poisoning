"""Re-measure unseen-mechanism detection on the ENLARGED, 180-instance population
(30/mechanism), closing the "n=10 too narrow" critique with a real, larger sample and
tighter Wilson intervals."""
import json
from pathlib import Path

from phase17 import arenas
from phase17.novel_attacks_extended import novel_records_extended, novel_records_extra_only
from phase17.run_b12 import KEYS, rows_for
from phase17.stats import rate_with_ci

OUT = Path(__file__).parent / "data" / "extended_novel_results.json"


def main():
    recs = novel_records_extended()
    pools, _ = arenas.isolated_arena(recs)
    rows = rows_for(pools, {r.scenario_id for r in recs})
    out = {"n": len(recs), "total": {k: rate_with_ci(sum(rows[r.scenario_id][k] for r in recs), len(recs)) for k in KEYS}, "by_mechanism": {}}
    for m in sorted({r.family for r in recs}):
        rs = [r for r in recs if r.family == m]
        out["by_mechanism"][m] = {"n": len(rs), **{k: rate_with_ci(sum(rows[r.scenario_id][k] for r in rs), len(rs)) for k in KEYS}}
    # ADDED (external review round 2, 2026-09-28): the new-only 120, isolated from the
    # original 60 -- the correct figure to cite for generalization to genuinely unseen
    # scenarios (the total-180 figure just reports a larger sample of a mixed population).
    new_only = novel_records_extra_only()
    out["new_only_120"] = {"n": len(new_only), **{k: rate_with_ci(sum(rows[r.scenario_id][k] for r in new_only), len(new_only)) for k in KEYS}}
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    f = lambda x: f"{x['k']}/{x['n']}"
    print("n=", out["n"], "B12_excl", f(out["total"]["B12_excl"]), "B12_flag", f(out["total"]["B12_flag"]))
    print("new_only_120 B12_excl", f(out["new_only_120"]["B12_excl"]), "B12_flag", f(out["new_only_120"]["B12_flag"]))
    for m, v in out["by_mechanism"].items():
        print(" ", m, f(v["B12_excl"]), f(v["B12_flag"]))
    print("DONE")


if __name__ == "__main__":
    main()
