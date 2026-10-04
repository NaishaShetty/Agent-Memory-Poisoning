"""The round-6 comparison: B15 against B12/B13/B14 and the baselines, on BOTH frozen hold-outs.

Two hold-outs, used for different purposes and reported separately:

  external_test  `external_test_corpus.py` (1,258 attacks, 998 human-authored). Frozen before
                 B14. B14's number here is clean; **B15's is not**, because B15's architecture
                 was chosen after reading this set's baseline results. Reported, labelled.
  holdout2       `holdout2_corpus.py` (1,200 Mosscap attacks, human-authored, MIT). Frozen
                 before B15 existed, so it is clean for every config including B15.

Also reports this project's own held-out populations, which no config was fitted on, and the
benign populations under both provenance conditions — because the whole point of round 6 is
cost-adjusted comparison, not recall alone.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, List, Sequence

from phase17.stats import paired_delta, rate_with_ci

OUT = Path(__file__).parent / "data" / "eval_round6.json"
CONFIGS = ("B12", "B13", "B14", "B15")
BASELINES = ("llama_guard3", "deberta_pi_v2", "perplexity_gpt2", "llm_prompt_qwen", "llm_prompt_llama31")


def _attack_pops() -> Dict[str, List]:
    from phase17.chinese_native_attacks import native_zh_records
    from phase17.external_attacks import external_records
    from phase17.external_test_corpus import test_attack_records
    from phase17.gemini_authored_attacks import gemini_records
    from phase17.holdout2_corpus import records as mosscap_records
    from phase17.memory_worm_regen import worm_regen_records
    from phase17.novel_attacks import novel_records
    from phase17.novel_attacks_extended import novel_records_extra_only
    from phase17.translation import zh_records
    from phase17.arenas import frozen_arena
    from phase17.corpus_extended import extended_records
    from phase17.founding_family_regen import founding_regen_records
    from phase17.poison_sets import PoisonRecord, evasion_records, original_records, regenerated_records

    frozen75 = [PoisonRecord(m.scenario_id, m.content_text, m.attack_family_ground_truth or "frozen75",
                             "held_out_frozen75")
                for p in frozen_arena()[0] for m in p.memories if m.is_poison_ground_truth]
    return {
        "own_novel_60": novel_records(), "own_novel_new120": novel_records_extra_only(),
        # zh_translated was in round 5 and fell out of round 6. It is half of the Chinese
        # confound finding (native 22/30 vs translated 30/84): dropping it leaves the native
        # number with nothing to compare against, which is how the confound hid in the first
        # place.
        "own_zh_translated_84": zh_records(),
        "own_gemini_30": gemini_records(), "own_evasion_47": evasion_records(),
        "own_worm_regen": worm_regen_records(), "own_zh_native_30": native_zh_records(),
        "own_trackb_15": original_records(), "own_trackb_regen_9": regenerated_records(),
        # ADDED round 6: the attack register found these two in NO evaluation table at all.
        "own_corpus_extended": extended_records(), "own_frozen75": frozen75,
        "own_founding_regen": founding_regen_records(),
        "external_dev_266": external_records(),
        "external_test_1258": test_attack_records(),
        "holdout2_mosscap_1200": mosscap_records(),
    }


def _benign_pops() -> Dict[str, List[str]]:
    from phase17.agentdojo_benign import agentdojo_benign
    from phase17.eval_populations import benign_populations
    from phase17.external_test_corpus import test_benign_texts

    b = dict(benign_populations())
    b["agentdojo_tool_outputs_test"] = agentdojo_benign("test")
    b["external_test_benign"] = test_benign_texts()
    return b


def _decide_attacks(config: str, recs):
    from phase14.defended_retrieval import apply_defense
    from phase17 import arenas

    pools, _ = arenas.isolated_arena(recs)
    out = []
    for p, r in zip(pools, recs):
        items = [(m.scenario_id, m.content_text) for m in p.memories]
        src = {mid: ("tool_output" if mid == r.scenario_id else "user_turn") for mid, _ in items}
        ctx = dict(sources=src) if config in ("B13", "B14", "B15") else {}
        _, dec = apply_defense(config, tuple(items), **ctx)
        d = next(x for x in dec if x.memory_id == r.scenario_id)
        out.append((d.excluded, d.action != "ALLOW"))
    return out


def _decide_benign(config: str, texts: Sequence[str], source: str = "tool_output"):
    from phase14.defended_retrieval import apply_defense

    out = []
    for i in range(0, len(texts), 4):
        chunk = [(f"BEN-{i+j}", t) for j, t in enumerate(texts[i:i + 4])]
        ctx = dict(sources={mid: source for mid, _ in chunk}) if config in ("B13", "B14", "B15") else {}
        _, dec = apply_defense(config, tuple(chunk), **ctx)
        out += [(d.excluded, d.action != "ALLOW") for d in dec]
    return out


def run(configs=CONFIGS) -> dict:
    from phase17.external_test_corpus import verify_frozen as vf1
    from phase17.holdout2_corpus import verify_frozen as vf2
    from phase17.semantic_detector import warm_all_tiers

    assert vf1(), "external_test corpus no longer matches its frozen digest"
    assert vf2(), "holdout2 corpus no longer matches its frozen digest"
    attacks, benign = _attack_pops(), _benign_pops()
    warm_all_tiers([r.text for rs in attacks.values() for r in rs]
                   + [t for v in benign.values() for t in v])

    out = {"configs": list(configs),
           "clean_for_all_configs": "holdout2_mosscap_1200",
           "informed_for_B15": "external_test_1258 (B15's architecture was chosen after reading "
                               "this set's baseline results; B14's number on it is clean)",
           "attack_populations": {}, "benign_populations": {}, "timing": {}}
    raw = {}
    for c in configs:
        raw[c] = {}
        t0 = time.time()
        for name, recs in attacks.items():
            raw[c][f"attack::{name}"] = _decide_attacks(c, recs)
            print(f"  {c} {name} done", flush=True)
        for name, texts in benign.items():
            raw[c][f"benign::{name}"] = _decide_benign(c, texts)
            if name in ("legitimate_imperatives_40", "named_party_preferences_6", "confirmed_human_20"):
                raw[c][f"benign::{name} [as user_turn]"] = _decide_benign(c, texts, "user_turn")
        out["timing"][c] = round(time.time() - t0, 1)

    for name in attacks:
        key = f"attack::{name}"
        out["attack_populations"][name] = {
            c: {"excluded": rate_with_ci(sum(e for e, _ in raw[c][key]), len(raw[c][key])),
                "flagged": rate_with_ci(sum(f for _, f in raw[c][key]), len(raw[c][key]))} for c in configs}
    for key in sorted({k for c in configs for k in raw[c] if k.startswith("benign::")}):
        out["benign_populations"][key[8:]] = {
            c: {"excluded": rate_with_ci(sum(e for e, _ in raw[c][key]), len(raw[c][key])),
                "flagged": rate_with_ci(sum(f for _, f in raw[c][key]), len(raw[c][key]))}
            for c in configs if key in raw[c]}

    groups = {"own": [k for k in attacks if k.startswith("own_")],
              "external_dev": ["external_dev_266"],
              "external_test": ["external_test_1258"],
              "holdout2_mosscap": ["holdout2_mosscap_1200"]}
    out["aggregates"] = {}
    for g, keys in groups.items():
        out["aggregates"][g] = {}
        for c in configs:
            v = [e for k in keys for e, _ in raw[c][f"attack::{k}"]]
            out["aggregates"][g][c] = rate_with_ci(sum(v), len(v))
        ref = [e for k in keys for e, _ in raw["B13"][f"attack::{k}"]]
        out["aggregates"][g]["paired_vs_B13"] = {
            c: paired_delta([e for k in keys for e, _ in raw[c][f"attack::{k}"]], ref)
            for c in configs if c != "B13"}
    # Raw per-item decisions, so recall can be recomputed on the WORKING-attack subset without
    # re-running the whole evaluation. Round 6 could not do that and had to re-run.
    out["raw"] = {c: {k: [[bool(e), bool(f)] for e, f in v] for k, v in raw[c].items()} for c in configs}
    out["raw_ids"] = {f"attack::{n}": [r.scenario_id for r in rs] for n, rs in attacks.items()}
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


if __name__ == "__main__":
    r = run()
    for g in ("own", "external_dev", "external_test", "holdout2_mosscap"):
        print(f"\n### {g}")
        for c in r["configs"]:
            v = r["aggregates"][g][c]
            print(f"  {c}: {v['k']}/{v['n']} = {v['rate']:.1%}")
    print("DONE")
