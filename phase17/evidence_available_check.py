"""What the corroboration check is worth when the conversation IS available (round 5).

`eval_round5.py` scores every attack with provenance but with NO `evidence`, because most
populations invent their own people and there is no conversation to check a claim against.
That makes its B13/B14 numbers a FLOOR: the corroboration signal -- the thing that reached
additive fabrication (0/72 → 43/72 in the frozen evaluation) -- is switched off throughout.

Some populations are different. This project's Track B poisons were injected into a specific
real LoCoMo conversation, and the `evasion_47` variants are rewrites of those same poisons,
so the real conversation exists and a deployment would have it. Those are exactly the cases
where content-only detection has been stuck: `evasion_47` sits at 3-4/47 for every config,
and the reports have said since round 3 that content alone has hit its ceiling there.

This measures the same populations twice -- without evidence (the floor `eval_round5`
reports) and with the real conversation supplied -- so the gap attributable to having
provenance and corroboration available is visible rather than assumed.

The evidence is the real conversation's own turns, not anything constructed for the test, and
the poison is marked as arriving through an untrusted channel exactly as the threat model
says it does.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from phase17.stats import paired_delta, rate_with_ci

OUT = Path(__file__).parent / "data" / "evidence_available_check.json"
CONFIGS = ("B12", "B13", "B14")
LOCOMO_SAMPLE = 0  # the conversation Track B's poisons were injected into


def _populations() -> Dict[str, List]:
    from phase17.poison_sets import evasion_records, original_records, regenerated_records

    return {"trackb_original_15": original_records(),
            "trackb_regen_9": regenerated_records(),
            "evasion_47": evasion_records()}


def run() -> dict:
    from phase14.defended_retrieval import apply_defense
    from phase17 import arenas
    from phase17.provenance_sets import owner_turns, speakers
    from phase17.semantic_detector import warm_all_tiers

    evidence = [t["text"] for t in owner_turns(LOCOMO_SAMPLE)]
    names = speakers(LOCOMO_SAMPLE)
    pops = _populations()
    warm_all_tiers([r.text for rs in pops.values() for r in rs])

    out = {"locomo_sample": LOCOMO_SAMPLE, "n_evidence_turns": len(evidence), "speakers": names,
           "populations": {}}
    for name, recs in pops.items():
        pools, _ = arenas.isolated_arena(recs)
        res = {c: {"no_evidence": [], "with_evidence": []} for c in CONFIGS}
        for p, r in zip(pools, recs):
            items = [(m.scenario_id, m.content_text) for m in p.memories]
            src = {mid: ("tool_output" if mid == r.scenario_id else "user_turn") for mid, _ in items}
            for c in CONFIGS:
                for mode, ctx in (("no_evidence", dict(sources=src) if c != "B12" else {}),
                                  ("with_evidence", dict(sources=src, evidence=evidence, evidence_names=names)
                                   if c != "B12" else {})):
                    _, dec = apply_defense(c, tuple(items), **ctx)
                    d = next(x for x in dec if x.memory_id == r.scenario_id)
                    res[c][mode].append(d.excluded)
        out["populations"][name] = {
            c: {m: rate_with_ci(sum(v[m]), len(v[m])) for m in ("no_evidence", "with_evidence")}
            for c, v in res.items()}
        for c in CONFIGS:
            out["populations"][name][c]["paired"] = paired_delta(res[c]["no_evidence"], res[c]["with_evidence"])
        print(f"  {name}: " + "  ".join(
            f"{c} {sum(res[c]['no_evidence'])}->{sum(res[c]['with_evidence'])}/{len(recs)}" for c in CONFIGS),
            flush=True)
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


if __name__ == "__main__":
    r = run()
    print("\n(excluded without evidence -> with the real conversation available)")
    for name, per in r["populations"].items():
        for c in CONFIGS:
            v = per[c]
            print(f"  {name:20s} {c}: {v['no_evidence']['k']:2d}/{v['no_evidence']['n']} -> "
                  f"{v['with_evidence']['k']:2d}/{v['with_evidence']['n']}  p={v['paired']['p_exact']:.3g}")
    print("DONE")
