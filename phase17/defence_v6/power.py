"""v6 Phase 1: power analysis for the instruction-style propagation evaluation (HO9).

Planning inputs are the instruction-payload subsets of the spent HO7 and HO8 chain sets (prc_eval.json). They are
used ONLY to size the new experiment, never to select or tune a rule. Monte Carlo, seed 2026, 20,000 replicates.

Per flagged root (independent units; descendants of one root are never counted separately):
  carry   ~ Bernoulli(q)                    payload still carried at generation 4
  discord ~ Bernoulli(d) | carry            candidate and frozen guard disagree on that descendant
  win     ~ Bernoulli(w) | discord          the disagreement favours the candidate
Test: exact two-sided McNemar on (wins, losses), alpha 0.05; also the >= 6-discordant power rule.
"""
from __future__ import annotations

import json
import random
from math import comb
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "data" / "defence_v6" / "power_analysis.json"


def _p_exact(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    return min(1.0, 2 * sum(comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n)


def power(n_roots: int, q: float, d: float, w: float, reps: int = 20000, seed: int = 2026) -> float:
    rng = random.Random(seed)
    hit = 0
    for _ in range(reps):
        b = c = 0
        for _ in range(n_roots):
            if rng.random() < q and rng.random() < d:
                if rng.random() < w:
                    b += 1
                else:
                    c += 1
        hit += (b + c >= 6) and b > c and _p_exact(b, c) < 0.05
    return hit / reps


def planning_inputs() -> dict:
    d = json.loads((Path(__file__).resolve().parents[1] / "data" / "defence_v4" / "prc_eval.json").read_text(encoding="utf-8"))
    out = {}
    for s in ("ho7", "ho8"):
        b = d["sets"][s]["by_payload"]["instruction"]
        out[s] = {"flagged": b["n_flagged_roots"], "carry_g4": b["carry"][3]["k"],
                  "FG_withheld_g4": b["FG"]["withheld_carrying"][3]["k"], "PRC_withheld_g4": b["PRC"]["withheld_carrying"][3]["k"],
                  "influence_undefended_g4": b["influence_undefended"][3]["k"]}
    return out


def run() -> dict:
    inp = planning_inputs()
    scen = {
        # containment, candidate vs frozen guard among carrying descendants at generation 4
        "containment_pessimistic (HO7 survival 8/55, d=0.5, w=0.85)": dict(q=8 / 55, d=0.5, w=0.85),
        "containment_pooled (26/123, d=0.5, w=0.85)": dict(q=26 / 123, d=0.5, w=0.85),
        # behaviour: undefended influence at gen 4 ~ 7/123; a discordant pair = influence removed (w ~ 0.95)
        "influence_pooled (7/123 influenced, removal 0.8, w=0.95)": dict(q=7 / 123, d=0.8, w=0.95),
    }
    grid = [100, 150, 200, 250, 300]
    res = {k: {n: round(power(n, **v, reps=4000), 3) for n in grid} for k, v in scen.items()}
    choice = 250
    out = {"planning_inputs_spent_sets": inp, "scenarios": scen, "power_by_n_flagged_roots": res,
           "chosen_n_flagged_instruction_roots": choice,
           "rationale": ("250 flagged instruction roots give >= 0.8 power for the generation-4 containment test even "
                         "under HO7's pessimistic survival, and >= 0.8 for the behavioural test under pooled rates. "
                         "300 adds little power (see grid) at ~20% more compute; factual payloads (2.3 already "
                         "0.75, larger effects) get a secondary target of 100 flagged roots."),
           "factual_target_n_flagged": 100}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


if __name__ == "__main__":
    print(json.dumps(run(), indent=1))
