"""The round-5 comparison table: every config and every baseline, on own / external-dev /
external-TEST, with confidence intervals, paired significance tests, false-positive rates,
per-source breakdowns, and the working-attack subset alongside the full population.

Rules this script enforces rather than assumes:
  * Baselines get their best fair configuration: thresholds calibrated on the SAME dev
    negatives B12 and B14 were calibrated on, plus an oracle threshold chosen on test data
    in the baseline's favour (matched to B14's ordinary-benign exclusion count). Beating a
    crippled baseline proves nothing, so both are reported.
  * Every attack number appears twice: on the full source-labelled population, and on the
    subset that actually subverted the undefended agent (`attack_validity_audit.py`, whose
    criterion was committed before it ran). Neither replaces the other.
  * external-TEST is scored exactly once per config, at the end, and its freeze digest is
    verified first — if the corpus changed since freezing, the run aborts.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import numpy as np

from phase17.stats import paired_delta, rate_with_ci

OUT = Path(__file__).parent / "data" / "eval_round5.json"
CONFIGS = ("B9", "B12", "B13", "B14")
BASELINES = ("llama_guard3", "deberta_pi_v2", "perplexity_gpt2", "llm_prompt_qwen", "llm_prompt_llama31")


def _attack_pops() -> Dict[str, List]:
    from phase17.attack_validity_audit import populations

    return populations()


def _benign_pops() -> Dict[str, List[str]]:
    from phase17.b13_dev_calibration import agentdojo_benign
    from phase17.eval_populations import benign_populations
    from phase17.external_test_corpus import test_benign_texts

    b = dict(benign_populations())
    b["agentdojo_tool_outputs_test"] = agentdojo_benign("test")
    b["external_test_benign (deepset)"] = test_benign_texts()
    return b


def _decide_attacks(config: str, recs, batch: int = 0) -> List[bool]:
    """Excluded-or-not for each record, one pool per record with 3 real benign distractors."""
    from phase14.defended_retrieval import apply_defense
    from phase17 import arenas

    pools, _ = arenas.isolated_arena(recs)
    out = []
    for p, r in zip(pools, recs):
        items = [(m.scenario_id, m.content_text) for m in p.memories]
        src = {mid: ("tool_output" if mid == r.scenario_id else "user_turn") for mid, _ in items}
        ctx = dict(sources=src) if config in ("B13", "B14") else {}
        _, dec = apply_defense(config, tuple(items), **ctx)
        out.append(next(d for d in dec if d.memory_id == r.scenario_id).excluded)
    return out


def _decide_benign(config: str, texts: Sequence[str]) -> List[bool]:
    from phase14.defended_retrieval import apply_defense

    out = []
    for i in range(0, len(texts), 4):
        chunk = [(f"BEN-{i+j}", t) for j, t in enumerate(texts[i:i + 4])]
        ctx = dict(sources={mid: "tool_output" for mid, _ in chunk}) if config in ("B13", "B14") else {}
        _, dec = apply_defense(config, tuple(chunk), **ctx)
        out += [d.excluded for d in dec]
    return out


def _baseline_flags(name: str, texts: Sequence[str], thr: float) -> List[bool]:
    from phase17.external_baselines import SCORERS, ScoreCache

    cache = ScoreCache()
    w = 8 if name in ("llama_guard3", "llm_prompt_qwen", "llm_prompt_llama31") else 0
    s = cache.get_many(name, list(texts), SCORERS[name], w)
    cache.save()
    return [x >= thr for x in s]


def _baseline_thresholds(ref_benign_excl: int, ref_benign_texts: Sequence[str]) -> Dict[str, Dict[str, float]]:
    """Dev-calibrated thresholds, plus an oracle threshold matched to the reference config's
    own ordinary-benign exclusion count (chosen on test data, in the baseline's favour)."""
    from phase17.external_baselines import SCORERS, ScoreCache, threshold_at_fpr
    from phase17.tune_lomo import dev_pool

    _, dev_neg = dev_pool()
    dev_texts = [x["text"] for x in dev_neg]
    cache = ScoreCache()
    out = {}
    for b in BASELINES:
        w = 8 if b in ("llama_guard3", "llm_prompt_qwen", "llm_prompt_llama31") else 0
        dev_s = cache.get_many(b, dev_texts, SCORERS[b], w)
        ben_s = sorted(cache.get_many(b, list(ref_benign_texts), SCORERS[b], w), reverse=True)
        cache.save()
        oracle = (ben_s[ref_benign_excl] + 1e-9) if ref_benign_excl < len(ben_s) else ben_s[-1]
        out[b] = {"dev": threshold_at_fpr(dev_s, 0.005), "oracle": float(oracle)}
    return out


def run(reference: str = "B14") -> dict:
    from phase17.attack_validity_audit import working_ids
    from phase17.external_test_corpus import verify_frozen
    from phase17.semantic_detector import warm_all_tiers

    assert verify_frozen(), ("The frozen external TEST corpus does not match its recorded digest; "
                            "refusing to report a held-out number on a changed test set.")
    attacks, benign = _attack_pops(), _benign_pops()
    working = working_ids()
    all_texts = [r.text for rs in attacks.values() for r in rs] + [t for v in benign.values() for t in v]
    print(f"warming judge tiers over {len(all_texts)} texts", flush=True)
    warm_all_tiers(all_texts)

    out = {"configs": list(CONFIGS), "baselines": list(BASELINES), "reference": reference,
           "attack_populations": {}, "benign_populations": {}, "timing": {}, "working_subset": {}}
    raw: Dict[str, Dict[str, List[bool]]] = {c: {} for c in CONFIGS}

    for c in CONFIGS:
        t0 = time.time()
        for name, recs in attacks.items():
            raw[c][f"attack::{name}"] = _decide_attacks(c, recs)
            print(f"  {c} {name} done", flush=True)
        for name, texts in benign.items():
            raw[c][f"benign::{name}"] = _decide_benign(c, texts)
        out["timing"][c] = {"seconds": round(time.time() - t0, 1),
                            "n_items": sum(len(v) for v in raw[c].values())}

    # ordinary-benign reference for the oracle thresholds
    from phase17.eval_populations import ORDINARY_BENIGN

    ref_benign_texts = [t for k in ORDINARY_BENIGN for t in benign[k]]
    ref_excl = sum(sum(raw[reference][f"benign::{k}"]) for k in ORDINARY_BENIGN)
    thr = _baseline_thresholds(ref_excl, ref_benign_texts)
    out["baseline_thresholds"] = thr
    out["oracle_reference"] = {"config": reference, "ordinary_benign_excluded": ref_excl,
                               "ordinary_benign_n": len(ref_benign_texts)}

    for b in BASELINES:
        for mode in ("dev", "oracle"):
            for name, recs in attacks.items():
                raw[f"{b}@{mode}"] = raw.get(f"{b}@{mode}", {})
                raw[f"{b}@{mode}"][f"attack::{name}"] = _baseline_flags(b, [r.text for r in recs], thr[b][mode])
            for name, texts in benign.items():
                raw[f"{b}@{mode}"][f"benign::{name}"] = _baseline_flags(b, texts, thr[b][mode])
        print(f"  baseline {b} done", flush=True)

    systems = list(CONFIGS) + [f"{b}@{m}" for b in BASELINES for m in ("dev", "oracle")]
    for name, recs in attacks.items():
        key = f"attack::{name}"
        ids = [r.scenario_id for r in recs]
        w = working.get(name, set())
        out["attack_populations"][name] = {
            s: rate_with_ci(sum(raw[s][key]), len(raw[s][key])) for s in systems}
        if w:
            idx = [i for i, x in enumerate(ids) if x in w]
            out["working_subset"][name] = {"n_working": len(idx), "n_total": len(ids), **{
                s: rate_with_ci(sum(raw[s][key][i] for i in idx), len(idx)) for s in systems}}
    for name in benign:
        key = f"benign::{name}"
        out["benign_populations"][name] = {s: rate_with_ci(sum(raw[s][key]), len(raw[s][key])) for s in systems}

    # paired significance vs the reference config, on the aggregate groupings that matter
    groups = {"own": [k for k in attacks if k.startswith("own_")],
              "external_dev": [k for k in attacks if k.startswith("extdev_")],
              "external_test": [k for k in attacks if k.startswith("exttest_")]}
    out["aggregates"] = {}
    for gname, keys in groups.items():
        out["aggregates"][gname] = {}
        for s in systems:
            v = [x for k in keys for x in raw[s][f"attack::{k}"]]
            out["aggregates"][gname][s] = rate_with_ci(sum(v), len(v))
        ref = [x for k in keys for x in raw[reference][f"attack::{k}"]]
        out["aggregates"][gname]["paired_vs_reference"] = {
            s: paired_delta([x for k in keys for x in raw[s][f"attack::{k}"]], ref)
            for s in systems if s != reference}
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def table(r: dict, group: str = "external_test") -> str:
    rows = [f"| system | {group} |", "|---|---|"]
    for s, v in sorted(r["aggregates"][group].items(), key=lambda kv: -(kv[1]["rate"] if isinstance(kv[1], dict) and "rate" in kv[1] else -1)):
        if not (isinstance(v, dict) and "rate" in v):
            continue
        ci = v["ci95"]
        rows.append(f"| {s} | {v['k']}/{v['n']} = {v['rate']:.1%} [{ci[0]:.1%}, {ci[1]:.1%}] |")
    return "\n".join(rows)


if __name__ == "__main__":
    r = run()
    for g in ("own", "external_dev", "external_test"):
        print(f"\n### {g}")
        print(table(r, g))
    print("\nDONE")
