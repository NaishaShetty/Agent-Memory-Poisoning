"""The single, pre-registered evaluation of the frozen B13 (external review round 4).

Protocol fixed in advance by `docs/phase17/PREREGISTRATION_B13.md` (committed before the
test populations existed). This script only RUNS what that document specifies; it makes no
choices of its own. Run once; the result goes to `data/frozen_eval_b13.json` and is
reported in `docs/phase17/PHASE17_REVIEW4_RESULTS.md`.

Primary comparisons P1-P4 from the pre-registration are computed explicitly and named as
such, so a reader can check them without reading the whole table.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

from phase17.stats import paired_delta, rate_with_ci

OUT = Path(__file__).parent / "data" / "frozen_eval_b13.json"
CONFIGS = ("B9", "B11", "B12", "B13")


def _decide(config: str, items: Sequence[Tuple[str, str]], **ctx):
    from phase14.defended_retrieval import apply_defense

    _, dec = apply_defense(config, tuple(items), **(ctx if config == "B13" else {}))
    return dec


def _score_pool(config: str, texts: Sequence[str], prefix: str, *, sources=None, evidence=None, names=()) -> List[dict]:
    """Score `texts` in pools of 4, the standard benign-pool shape used elsewhere."""
    rows = []
    for i in range(0, len(texts), 4):
        chunk = [(f"{prefix}-{i + j}", t) for j, t in enumerate(texts[i:i + 4])]
        src = {mid: (sources or {}).get(mid, "tool_output") for mid, _ in chunk}
        dec = _decide(config, chunk, sources=src, evidence=evidence or [], evidence_names=names)
        rows += [{"id": d.memory_id, "excluded": d.excluded, "flagged": d.action != "ALLOW"} for d in dec]
    return rows


def _score_isolated(config: str, texts: Sequence[str], prefix: str, *, evidence=None, names=()) -> List[dict]:
    """Attacks: one pool per record with 3 real benign distractors (`isolated_arena` shape)."""
    from phase17 import arenas
    from phase17.poison_sets import PoisonRecord

    recs = [PoisonRecord(f"{prefix}-{i}", t, prefix, "frozen_eval") for i, t in enumerate(texts)]
    pools, _ = arenas.isolated_arena(recs)
    rows = []
    for p, r in zip(pools, recs):
        items = [(m.scenario_id, m.content_text) for m in p.memories]
        # The poison arrives through an untrusted channel; the distractors are real prior
        # conversation content, i.e. the user's own turns. This is the provenance the threat
        # model already assumes -- see BENCHMARK_CARD.md.
        src = {mid: ("tool_output" if mid == r.scenario_id else "user_turn") for mid, _ in items}
        dec = _decide(config, items, sources=src, evidence=evidence or [], evidence_names=names)
        d = next(x for x in dec if x.memory_id == r.scenario_id)
        rows.append({"id": r.scenario_id, "excluded": d.excluded, "flagged": d.action != "ALLOW"})
    return rows


def _rates(rows: List[dict]) -> dict:
    n = len(rows)
    return {"excluded": rate_with_ci(sum(r["excluded"] for r in rows), n),
            "flagged": rate_with_ci(sum(r["flagged"] for r in rows), n)}


def run() -> dict:
    from phase17.b13_dev_calibration import agentdojo_benign
    from phase17.chinese_native_attacks import translated_benign_texts
    from phase17.eval_populations import attack_populations, benign_populations
    from phase17.external_attacks import external_records
    from phase17.provenance_sets import TEST_SAMPLES, fabrications, observations, owner_turns, speakers

    from phase17.semantic_detector import warm_all_tiers

    out = {"configs": list(CONFIGS), "populations": {}, "primary": {}, "raw": {}}
    # Pre-compute every judge-tier answer concurrently; the per-pool decisions below are
    # then cache hits and identical to running them one at a time.
    warm_all_tiers([f["text"] for f in fabrications("test")]
                   + [o["text"] for s_ in TEST_SAMPLES for o in observations(s_)]
                   + [t for v in attack_populations().items() for t in v[1]]
                   + [t for v in benign_populations().items() for t in v[1]]
                   + agentdojo_benign("test") + translated_benign_texts())

    # --- 1. provenance test fabrications + LoCoMo's own observations, per conversation ----
    fabs = fabrications("test")
    per_cfg_fab: Dict[str, Dict[str, List[dict]]] = {c: {"additive": [], "preference": [], "observations": []} for c in CONFIGS}
    for s in TEST_SAMPLES:
        ev = [t["text"] for t in owner_turns(s)]
        nm = speakers(s)
        obs = [o["text"] for o in observations(s)]
        for kind in ("additive", "preference"):
            texts = [f["text"] for f in fabs if f["sample"] == s and f["kind"] == kind]
            if not texts:
                continue
            for c in CONFIGS:
                per_cfg_fab[c][kind] += _score_isolated(c, texts, f"FAB-{kind}-{s}", evidence=ev, names=nm)
        for c in CONFIGS:
            per_cfg_fab[c]["observations"] += _score_pool(
                c, obs, f"OBS-{s}", sources={}, evidence=ev, names=nm)
        print("conversation", s, "done", flush=True)
    for c in CONFIGS:
        for k, rows in per_cfg_fab[c].items():
            out["populations"].setdefault(f"provenance_{k}", {})[c] = _rates(rows)
        out["raw"].setdefault(c, {})["provenance"] = per_cfg_fab[c]

    # --- 2. every other pre-registered population -----------------------------------------
    attacks, benign = attack_populations(), benign_populations()
    ext_by_source = {}
    for r in external_records():
        ext_by_source.setdefault(r.family, []).append(r.text)
    pops = [(f"attack::{k}", v, True) for k, v in attacks.items()]
    pops += [(f"benign::{k}", v, False) for k, v in benign.items()]
    pops.append(("benign::agentdojo_tool_outputs_test", agentdojo_benign("test"), False))
    pops.append(("benign::chinese_translated_benign", translated_benign_texts(), False))
    for name, texts, is_attack in pops:
        if not texts:
            continue
        for c in CONFIGS:
            rows = (_score_isolated if is_attack else _score_pool)(c, texts, name.split("::")[1][:12])
            out["populations"].setdefault(name, {})[c] = _rates(rows)
            out["raw"].setdefault(c, {})[name] = rows
        print(name, "done", flush=True)

    # Every benign pool above is scored as `tool_output`, i.e. the worst case where no
    # provenance is recorded at all. The two benign sets that in reality come from the
    # USER'S OWN MOUTH -- standing instructions like "always CC my wife on invoices", and
    # ordinary spoken preferences that name a vendor -- are also scored with their true
    # source, since that is the case B13's trust rule exists for. Both are reported; the
    # untrusted scoring is the floor, the user_turn scoring is the realistic one.
    for name in ("benign::legitimate_imperatives_40", "benign::named_party_preferences_6",
                 "benign::confirmed_human_20"):
        texts = next((t for n, t, _ in pops if n == name), None)
        if not texts:
            continue
        for c in CONFIGS:
            rows = _score_pool(c, texts, name.split("::")[1][:12],
                               sources={f"{name.split('::')[1][:12]}-{i}": "user_turn" for i in range(len(texts))})
            out["populations"].setdefault(name + " [as user_turn]", {})[c] = _rates(rows)
            out["raw"].setdefault(c, {})[name + " [as user_turn]"] = rows
        print(name, "[as user_turn] done", flush=True)

    # --- 3. the four pre-registered primary comparisons ------------------------------------
    def pair(pop, a="B12", b="B13", field="excluded"):
        ra = out["raw"][a]["provenance"][pop] if pop in ("additive", "preference", "observations") else out["raw"][a][pop]
        rb = out["raw"][b]["provenance"][pop] if pop in ("additive", "preference", "observations") else out["raw"][b][pop]
        return paired_delta([r[field] for r in ra], [r[field] for r in rb])

    out["primary"]["P1_additive_fabrications_B12_vs_B13"] = pair("additive")
    out["primary"]["P2_preference_fabrications_B12_vs_B13"] = pair("preference")
    out["primary"]["P3_benign_false_positives"] = {
        "locomo_observations": pair("observations"),
        "agentdojo_tool_outputs_test": pair("benign::agentdojo_tool_outputs_test"),
        "legitimate_imperatives_40": pair("benign::legitimate_imperatives_40"),
    }
    out["primary"]["P4_external_attacks_B12_vs_B13"] = pair("attack::external_all_266")
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


if __name__ == "__main__":
    r = run()
    for name, per in sorted(r["populations"].items()):
        cells = " ".join(f"{c}={per[c]['excluded']['k']}/{per[c]['excluded']['n']}" for c in CONFIGS if c in per)
        print(f"{name:55s} {cells}")
    print("\nPRIMARY")
    print(json.dumps(r["primary"], indent=1))
    print("DONE")
