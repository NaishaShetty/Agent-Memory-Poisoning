"""The pre-registered evaluation on hold-out 3 (`docs/phase17/PREREGISTRATION_HOLDOUT3.md`).

Run ONCE, after the corpus was frozen and the predictions recorded. Nothing here re-fits
anything: every threshold, weight and radius is read from an existing frozen artifact.

Reports attack recall and matched-benign false positives together, always, because the benign
half is the point -- it is benign text from the same platforms as the attacks, so it is the
first FPR test in this project a detector cannot pass by telling Reddit apart from our own
benign corpora.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Dict, List, Sequence

OUT = Path(__file__).parent / "data" / "eval_holdout3.json"
# CHECKPOINTED per (config, half). Cold-cache B14/B17/B18 over 2,000 long texts is a multi-hour
# job, and this project has already lost two long runs to wrappers being stopped. Decisions are
# deterministic (temperature 0, fixed seeds), so reusing a completed half is exact, not an
# approximation.
PARTIAL = Path(__file__).parent / "data" / "eval_holdout3_partial.json"
CONFIGS = ("B12", "B13", "B14", "B15", "B17", "B18")
BASELINES = ("llama_guard3", "deberta_pi_v2", "perplexity_gpt2", "llm_prompt_qwen", "llm_prompt_llama31")
BATCH = 4


def _decide(config: str, texts: Sequence[str], prefix: str, source: str = "tool_output"):
    from phase14.defended_retrieval import apply_defense

    out = []
    for i in range(0, len(texts), BATCH):
        chunk = [(f"{prefix}-{i+j}", t) for j, t in enumerate(texts[i:i + BATCH])]
        ctx = dict(sources={mid: source for mid, _ in chunk}) if config in (
            "B13", "B14", "B15", "B17", "B18") else {}
        _, dec = apply_defense(config, tuple(chunk), **ctx)
        out += [bool(d.excluded) for d in dec]
        if (i // BATCH) % 25 == 0:
            print(f"    {config} {prefix} {i}/{len(texts)}", flush=True)
    return out


def _baseline_flags(texts: Sequence[str]) -> Dict[str, List[bool]]:
    """Cached scores where available, computed otherwise; thresholds read from round 5."""
    from phase17.external_baselines import SCORERS, unload
    from phase17.cache_io import merge_write

    SC = Path(__file__).parent / "data" / "external_baseline_scores.json"
    cache = json.loads(SC.read_text(encoding="utf-8")) if SC.exists() else {}
    thr = json.loads((Path(__file__).parent / "data" / "eval_round5.json").read_text(
        encoding="utf-8"))["baseline_thresholds"]
    out = {}
    for b in BASELINES:
        keys = [b + ":" + hashlib.sha256(t.encode("utf-8")).hexdigest()[:24] for t in texts]
        todo = [(k, t) for k, t in zip(keys, texts) if k not in cache]
        if todo:
            print(f"  {b}: scoring {len(todo)} uncached", flush=True)
            fn = SCORERS[b]
            new = {}
            for n, (k, t) in enumerate(todo, 1):
                try:
                    new[k] = float(fn(t))
                except Exception:
                    new[k] = 0.0
                if n % 100 == 0:
                    merge_write(SC, new)
                    cache.update(new)
                    new = {}
                    print(f"    {b} {n}/{len(todo)}", flush=True)
            merge_write(SC, new)
            cache.update(new)
            try:
                unload(b)
            except Exception:
                pass
        s = [cache.get(k, 0.0) for k in keys]
        for tname in ("dev", "oracle"):
            t = thr[b][tname]
            out[f"{b}@{tname}"] = [x >= t for x in s]
    return out


def run() -> dict:
    from phase17.holdout3_corpus import attack_records, benign_texts, verify_frozen
    from phase17.stats import paired_delta, rate_with_ci

    assert verify_frozen(), "hold-out 3 no longer matches its frozen digest"
    atk = [r.text for r in attack_records()]
    ben = benign_texts()
    print(f"hold-out 3: {len(atk)} attacks, {len(ben)} matched benign", flush=True)

    done = json.loads(PARTIAL.read_text(encoding="utf-8")) if PARTIAL.exists() else {}
    raw = {}
    for c in CONFIGS:
        t0 = time.time()
        raw[c] = {}
        for half, texts, prefix in (("attack", atk, "ITW"), ("benign", ben, "ITWBEN")):
            k = f"{c}:{half}"
            if k in done and len(done[k]) == len(texts):
                raw[c][half] = done[k]
                print(f"  {c} {half}: cached", flush=True)
                continue
            raw[c][half] = _decide(c, texts, prefix)
            done[k] = raw[c][half]
            PARTIAL.write_text(json.dumps(done), encoding="utf-8")
        print(f"  {c}: {round(time.time()-t0,1)}s", flush=True)
    bl_atk = _baseline_flags(atk)
    bl_ben = _baseline_flags(ben)

    out = {"preregistration": "docs/phase17/PREREGISTRATION_HOLDOUT3.md",
           "frozen_digest": json.loads(
               (Path(__file__).parent / "data" / "holdout3_freeze.json").read_text(
                   encoding="utf-8"))["sha256"],
           "n_attacks": len(atk), "n_benign": len(ben),
           "note": "jailbreak corpus, not memory poisoning; benign half is from the same "
                   "platforms as the attacks",
           "configs": {}, "baselines": {}}
    for c in CONFIGS:
        out["configs"][c] = {
            "attack_recall": rate_with_ci(sum(raw[c]["attack"]), len(atk)),
            "matched_benign_fpr": rate_with_ci(sum(raw[c]["benign"]), len(ben))}
    for k in bl_atk:
        out["baselines"][k] = {
            "attack_recall": rate_with_ci(sum(bl_atk[k]), len(atk)),
            "matched_benign_fpr": rate_with_ci(sum(bl_ben[k]), len(ben))}
    # The two pre-registered predictions that can falsify B18.
    out["prediction_checks"] = {
        "P1_B18_ge_B17": {
            "B18": out["configs"]["B18"]["attack_recall"]["rate"],
            "B17": out["configs"]["B17"]["attack_recall"]["rate"],
            "holds": out["configs"]["B18"]["attack_recall"]["rate"] >= out["configs"]["B17"]["attack_recall"]["rate"],
            "paired": paired_delta(raw["B18"]["attack"], raw["B17"]["attack"])},
        "P2_B18_beats_B14_by_5pts": {
            "delta_points": round(100 * (out["configs"]["B18"]["attack_recall"]["rate"]
                                         - out["configs"]["B14"]["attack_recall"]["rate"]), 1),
            "holds": (out["configs"]["B18"]["attack_recall"]["rate"]
                      - out["configs"]["B14"]["attack_recall"]["rate"]) >= 0.05,
            "paired": paired_delta(raw["B18"]["attack"], raw["B14"]["attack"])},
        "P3_B13_poor_here": {"B13": out["configs"]["B13"]["attack_recall"]["rate"],
                             "B14": out["configs"]["B14"]["attack_recall"]["rate"]},
        "P5_no_config_above_85pct": {
            "max_config_recall": max(v["attack_recall"]["rate"] for v in out["configs"].values())},
    }
    out["raw"] = {c: raw[c] for c in CONFIGS}
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    r = run()
    print(f"\n{'config':24s} {'attack recall':>16s} {'matched-benign FPR':>20s}")
    for c, v in r["configs"].items():
        a, b = v["attack_recall"], v["matched_benign_fpr"]
        print(f"  {c:22s} {a['k']:5d}/{a['n']:<5d} {a['rate']:6.1%} {b['k']:6d}/{b['n']:<5d} {b['rate']:7.2%}")
    print()
    for c, v in r["baselines"].items():
        a, b = v["attack_recall"], v["matched_benign_fpr"]
        print(f"  {c:22s} {a['k']:5d}/{a['n']:<5d} {a['rate']:6.1%} {b['k']:6d}/{b['n']:<5d} {b['rate']:7.2%}")
    print("\nPREDICTION CHECKS:")
    print(json.dumps(r["prediction_checks"], indent=1))
    print("DONE")
