"""B16 at the PRE-REGISTERED radius 0.90, on FRESH adaptive seeds (Analysis 2 of
`docs/phase17/PREREGISTRATION_HOLDOUT3.md`).

WHY THIS RUN EXISTS. The frozen dev radius 0.97 showed no effect (4/30 vs 5/30, p=1.0). A
radius of 0.90 eliminated adaptive evasion entirely (0/30, p=0.0625) -- but that radius was
chosen after seeing the 0.97 result, on the same 43 seeds. That is selection on the thing being
measured, twice over, and it is why the 0.90 figure was published as exploratory and not as a
result.

So the radius is fixed in advance at **0.90** (recorded in the pre-registration before this ran)
and the seeds are ones the adaptive attacker has never been pointed at. If 0.90 fails here, B16
fails; the radius will not be adjusted again.

SEED SELECTION RULE, fixed before the run and deliberately mechanical:
  * drawn from `novel_attacks_extended` (disjoint scenarios from `novel_records`),
    `founding_family_regen` and `corpus_extended` -- none of which contributed any of the
    original 43 seeds;
  * stratified by family, up to SEEDS_PER_FAMILY each, seeded shuffle;
  * every seed id is checked against the original 43 and excluded if present.

Everything else is identical to `eval_rejection_memory.py`: same attacker, same budget of 5,
same rewrite model, same NLI claim-preservation gate, same excluded/flagged distinction.
"""
from __future__ import annotations

import json
import random
from pathlib import Path
from typing import List

OUT = Path(__file__).parent / "data" / "eval_rejection_fresh.json"
PARTIAL = Path(__file__).parent / "data" / "eval_rejection_fresh_partial.json"
REJECT_SIM = 0.90          # PRE-REGISTERED; do not change after seeing results
SEEDS_PER_FAMILY = 6
SEED = 31


def fresh_seeds() -> List[tuple]:
    from phase17.adaptive_query_attacker import _seed_records
    from phase17.corpus_extended import extended_records
    from phase17.founding_family_regen import founding_regen_records
    from phase17.novel_attacks_extended import novel_records_extra_only

    used = {sid for sid, _t, _f in _seed_records(12)[0]}
    pool = list(novel_records_extra_only()) + list(founding_regen_records()) + list(extended_records())
    pool = [r for r in pool if r.scenario_id not in used]
    rng = random.Random(SEED)
    rng.shuffle(pool)
    by_fam: dict = {}
    out = []
    for r in pool:
        if by_fam.get(r.family, 0) >= SEEDS_PER_FAMILY:
            continue
        by_fam[r.family] = by_fam.get(r.family, 0) + 1
        out.append((r.scenario_id, r.text, r.family))
    return out


def run(workers: int = 3) -> dict:
    import concurrent.futures as cf

    from phase17.eval_rejection_memory import attack_one_stateful, _summarise
    from phase17.stats import paired_delta

    seeds = fresh_seeds()
    used_ids = {sid for sid, _t, _f in seeds}
    from phase17.adaptive_query_attacker import _seed_records

    overlap = used_ids & {s for s, _t, _f in _seed_records(12)[0]}
    assert not overlap, f"fresh seeds overlap the original 43: {overlap}"
    print(f"fresh seeds: {len(seeds)} across {len({f for _,_,f in seeds})} families, "
          f"radius {REJECT_SIM} (pre-registered)", flush=True)

    done = json.loads(PARTIAL.read_text(encoding="utf-8")) if PARTIAL.exists() else {}
    rows = {}
    for arm, use_ledger in (("B15", False), ("B16@0.90", True)):
        cfg = "B15" if not use_ledger else "B16"
        todo = [(s, t) for s, t, _f in seeds if f"{arm}:{s}" not in done]
        got = [done[f"{arm}:{s}"] for s, _t, _f in seeds if f"{arm}:{s}" in done]
        if got:
            print(f"  {arm}: {len(got)} cached, {len(todo)} to compute", flush=True)
        with cf.ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(attack_one_stateful, s, t, cfg, use_ledger,
                              REJECT_SIM if use_ledger else None): s for s, t in todo}
            for n, f in enumerate(cf.as_completed(futs), 1):
                r = f.result()
                got.append(r)
                done[f"{arm}:{r['seed_id']}"] = r
                if n % 5 == 0 or n == len(todo):
                    PARTIAL.write_text(json.dumps(done, ensure_ascii=False), encoding="utf-8")
                    print(f"  {arm}: {n}/{len(todo)}", flush=True)
        PARTIAL.write_text(json.dumps(done, ensure_ascii=False), encoding="utf-8")
        rows[arm] = got
        s = _summarise(got)
        g = s["genuine_adaptive_evasion_of_initially_excluded"]
        print(f"  {arm}: genuine adaptive evasion {g['k']}/{g['n']}", flush=True)

    ids = [s for s, _t, _f in seeds]
    def vec(arm):
        m = {r["seed_id"]: r for r in rows[arm]}
        return [bool(m[i].get("success") and m[i].get("genuine_adaptive_evasion")) for i in ids if i in m]
    out = {"preregistration": "docs/phase17/PREREGISTRATION_HOLDOUT3.md (Analysis 2)",
           "reject_sim": REJECT_SIM, "preregistered": True,
           "seed_rule": f"novel_extended + founding_regen + corpus_extended, <={SEEDS_PER_FAMILY} "
                        f"per family, seed {SEED}, disjoint from the original 43",
           "n_seeds": len(seeds),
           "families": sorted({f for _, _, f in seeds}),
           "per_arm": {a: _summarise(rows[a]) for a in rows},
           "paired_B16_vs_B15": paired_delta(vec("B16@0.90"), vec("B15")),
           "falsification_rule": "no reduction, or p>0.1 with >=20 initially-excluded seeds, "
                                 "falsifies B16",
           "cost_that_must_accompany_a_positive": "ledger-poisoning blast radius 29.7% at 0.90 "
                                                  "vs 0.7% at 0.97"}
    for a in rows:
        for r in rows[a]:
            r["history"] = r["history"][:6]
        out["per_arm"][a]["rows"] = rows[a]
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


if __name__ == "__main__":
    r = run()
    for a, s in r["per_arm"].items():
        g = s["genuine_adaptive_evasion_of_initially_excluded"]
        print(f"\n{a}: initially excluded {s['n_initially_excluded']}/{s['n_seeds']}; "
              f"genuine adaptive evasion {g['k']}/{g['n']} = {g['rate']:.1%}")
    print(f"\npaired B16@0.90 vs B15: {r['paired_B16_vs_B15']}")
    print("DONE")
