"""Attempt to improve evasion detection using B12 (with the new lineage tier) + order-free
conflict check against the SAME arena's 3 real LoCoMo distractors, on all 47 evasion
variants (not just the 13 gold-bearing ones)."""
import json
from pathlib import Path

from phase17 import arenas, conflict_check as cc
from phase17.b11_live import APPEAL_THRESHOLD, CONFLICT_THRESHOLD, SUPERSEDE_THRESHOLD
from phase17.b12_live import _detector, b12_actions
from phase17.poison_sets import evasion_records
from phase17.stats import cluster_bootstrap, rate_with_ci

OUT = Path(__file__).parent / "data" / "evasion_improved_results.json"


def main():
    ev = evasion_records()
    pools, truth = arenas.isolated_arena(ev)
    rows = {}
    for p in pools:
        items = [(m.scenario_id, m.content_text) for m in p.memories]
        actions = b12_actions(items, conflict="order_free")
        for m in p.memories:
            if truth[m.scenario_id].is_poison:
                rows[m.scenario_id] = actions[m.scenario_id] in ("QUARANTINE", "BLOCK")
    excl = rate_with_ci(sum(rows[r.scenario_id] for r in ev), len(ev))
    cluster = cluster_bootstrap([rows[r.scenario_id] for r in ev], [r.parent_id for r in ev])
    by_variant = {v: rate_with_ci(sum(rows[r.scenario_id] for r in ev if r.variant == v), sum(1 for r in ev if r.variant == v))
                  for v in sorted({r.variant for r in ev})}
    out = {"n": len(ev), "excluded": excl, "cluster_aware": cluster, "by_variant": by_variant}
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
