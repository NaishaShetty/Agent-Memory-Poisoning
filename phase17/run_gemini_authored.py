"""Evaluate B12/B11 on Gemini-authored (not Qwen-authored) attacks -- closes finding 2's
'test other-model-written attacks' half."""
import json
from pathlib import Path

from phase17 import arenas
from phase17.gemini_authored_attacks import gemini_records
from phase17.run_b12 import KEYS, rows_for
from phase17.stats import rate_with_ci

OUT = Path(__file__).parent / "data" / "gemini_authored_results.json"


def main():
    recs = gemini_records()
    pools, _ = arenas.isolated_arena(recs)
    rows = rows_for(pools, {r.scenario_id for r in recs})
    out = {"n": len(recs), "total": {k: rate_with_ci(sum(rows[r.scenario_id][k] for r in recs), len(recs)) for k in KEYS}, "by_mechanism": {}}
    for m in sorted({r.family for r in recs}):
        rs = [r for r in recs if r.family == m]
        out["by_mechanism"][m] = {"n": len(rs), **{k: rate_with_ci(sum(rows[r.scenario_id][k] for r in rs), len(rs)) for k in KEYS}}
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    f = lambda x: f"{x['k']}/{x['n']}"
    print("n=", out["n"], "B12_excl", f(out["total"]["B12_excl"]), "B12_flag", f(out["total"]["B12_flag"]))
    for m, v in out["by_mechanism"].items():
        print(" ", m, f(v["B12_excl"]), f(v["B12_flag"]))
    print("DONE")


if __name__ == "__main__":
    main()
