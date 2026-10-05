"""Hold-out 3 at MATCHED operating points -- fixing a comparison I set up unfairly.

THE PROBLEM WITH THE FIRST HOLD-OUT-3 TABLE. It reported our configurations at their shipped
action thresholds and the published baselines at thresholds suffixed `@dev`, and those are not
the same kind of number. The baselines' thresholds were calibrated on dev NEGATIVES, so each
baseline was allowed to pick an operating point suited to the distribution. Our configurations
ran at thresholds frozen from ordinary CONVERSATIONAL-MEMORY benign text and were then scored
against long Reddit/Discord prose -- a distribution their thresholds had never seen. The
resulting 54.9% false-positive rate for the union configurations is therefore partly a
statement about an uncalibrated operating point, not only about discrimination.

That asymmetry favoured the baselines, and the honest fix is to remove it rather than to
caveat it: calibrate EVERYTHING the same way, on the same data, and evaluate once.

THE PROTOCOL, and the calibration set is the load-bearing choice:
  * thresholds are fitted on `holdout3_dev_benign.py` -- 400 benign items from the dataset's
    EARLIER snapshot of the same platforms, asserted disjoint from the frozen corpus (110
    overlapping items were dropped from the dev side, so the disjointness is enforced rather
    than hoped for);
  * for each scorer, the threshold is the smallest value whose false-positive rate on that dev
    set is at or below the target;
  * targets are 0.5%, 2% and 8%, the last chosen because it is where the strongest baseline
    landed, so "at equal false-positive cost" is answerable directly;
  * recall is then read once off the 1,000 frozen hold-out attacks, and the realised
    false-positive rate once off the 995 frozen benign items.

Nothing is fitted on the frozen corpus. The realised FPR on it will not equal the target,
because the two snapshots differ; that gap is itself worth reporting and is included.

WHAT THIS CANNOT DO. B13's provenance and corroboration rules are structural, not a score, so
B13 has no knob and does not appear in the matched-FPR table -- its weakness on this corpus is
not an operating-point artifact. Only B12, B14 and B15, which expose a continuous score, and
the five published baselines can be compared this way.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, List, Sequence

import numpy as np

DATA = Path(__file__).parent / "data"
OUT = DATA / "holdout3_matched_fpr.json"
SCORES = DATA / "external_baseline_scores.json"
TARGETS = (0.005, 0.02, 0.08)
BASELINES = ("llama_guard3", "deberta_pi_v2", "perplexity_gpt2", "llm_prompt_qwen",
             "llm_prompt_llama31")


def _bkey(name: str, text: str) -> str:
    return name + ":" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]


def _baseline_scores(name: str, texts: Sequence[str]) -> List[float]:
    """Cached where possible; computes and persists the rest."""
    from phase17.cache_io import merge_write
    from phase17.external_baselines import SCORERS

    cache = json.loads(SCORES.read_text(encoding="utf-8")) if SCORES.exists() else {}
    keys = [_bkey(name, t) for t in texts]
    todo = [(k, t) for k, t in zip(keys, texts) if k not in cache]
    if todo:
        print(f"  {name}: scoring {len(todo)} uncached", flush=True)
        fn, new = SCORERS[name], {}
        for n, (k, t) in enumerate(todo, 1):
            try:
                new[k] = float(fn(t))
            except Exception:
                new[k] = 0.0
            if n % 100 == 0:
                merge_write(SCORES, new)
                cache.update(new)
                new = {}
                print(f"    {name} {n}/{len(todo)}", flush=True)
        merge_write(SCORES, new)
        cache.update(new)
    return [float(cache.get(k, 0.0)) for k in keys]


def _config_scores(cfg: str, texts: Sequence[str]) -> List[float]:
    if cfg == "B14":
        from phase17.b14_live import scores

        return [float(x) for x in scores(list(texts))]
    if cfg == "B15":
        from phase17.b15_live import scores

        return [float(x) for x in scores(list(texts))]
    if cfg == "B12":
        from phase17.b12_live import _detector

        det = _detector()
        for attr in ("scores", "score_many", "predict_proba"):
            fn = getattr(det, attr, None)
            if fn:
                v = fn(list(texts))
                return [float(x) for x in (v[:, 1] if getattr(v, "ndim", 1) == 2 else v)]
        raise RuntimeError("B12 detector exposes no batch score method")
    raise ValueError(cfg)


def _threshold_at(dev: Sequence[float], target: float) -> float:
    """Smallest threshold whose dev false-positive rate is <= target."""
    s = np.sort(np.asarray(dev))[::-1]
    k = int(np.floor(target * len(s)))
    if k <= 0:
        return float(s[0]) + 1e-9
    return float(s[k - 1])


def run(configs=("B12", "B14", "B15")) -> dict:
    from phase17.holdout3_corpus import attack_records, benign_texts, verify_frozen
    from phase17.holdout3_dev_benign import dev_benign_texts, verify_disjoint
    from phase17.stats import rate_with_ci

    assert verify_frozen(), "hold-out 3 no longer matches its frozen digest"
    assert verify_disjoint(), "the dev calibration set overlaps the frozen corpus"
    dev = dev_benign_texts()
    atk = [r.text for r in attack_records()]
    ben = benign_texts()
    print(f"calibrating on {len(dev)} DEV benign; evaluating on {len(atk)} attacks / "
          f"{len(ben)} frozen benign", flush=True)

    out = {"targets": list(TARGETS), "n_dev": len(dev), "n_attacks": len(atk), "n_benign": len(ben),
           "calibration_set": "holdout3_dev_benign (regular_2023_05_07), disjoint from the frozen "
                              "corpus by construction",
           "note": "thresholds are fitted on DEV ONLY; recall and realised FPR are read once off "
                   "the frozen corpus. B13 has no continuous score and cannot appear here, so "
                   "its weakness on this corpus is not an operating-point artifact.",
           "scorers": {}}

    def add(label, dv, av, bv):
        e = {}
        for t in TARGETS:
            thr = _threshold_at(dv, t)
            e[f"fpr<={t:.3f}"] = {
                "threshold": thr,
                "recall": rate_with_ci(int(sum(x >= thr for x in av)), len(av)),
                "realised_benign_fpr": rate_with_ci(int(sum(x >= thr for x in bv)), len(bv)),
            }
        out["scorers"][label] = e
        best = e[f"fpr<={TARGETS[-1]:.3f}"]
        print(f"  {label:22s} @dev-FPR {TARGETS[-1]:.0%}: recall {best['recall']['rate']:6.1%} "
              f"realised FPR {best['realised_benign_fpr']['rate']:6.1%}", flush=True)

    for cfg in configs:
        try:
            dv, av, bv = (_config_scores(cfg, x) for x in (dev, atk, ben))
        except Exception as exc:
            print(f"  {cfg}: SKIPPED ({type(exc).__name__}: {exc})", flush=True)
            out["scorers"][cfg] = {"error": f"{type(exc).__name__}: {exc}"}
            continue
        add(cfg, dv, av, bv)
    for b in BASELINES:
        dv = _baseline_scores(b, dev)
        av = _baseline_scores(b, atk)
        bv = _baseline_scores(b, ben)
        add(b, dv, av, bv)

    # The headline: at the same dev-calibrated operating point, who discriminates best?
    tgt = f"fpr<={TARGETS[-1]:.3f}"
    rank = sorted(((k, v[tgt]["recall"]["rate"], v[tgt]["realised_benign_fpr"]["rate"])
                   for k, v in out["scorers"].items() if tgt in v),
                  key=lambda r: -(r[1] - r[2]))
    out["ranking_at_matched_dev_fpr"] = [
        {"scorer": k, "recall": r, "realised_fpr": f, "recall_minus_fpr": round(r - f, 4)}
        for k, r, f in rank]
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    r = run()
    print(f"\n### Ranking at a dev-calibrated {TARGETS[-1]:.0%} FPR operating point")
    print(f"  {'scorer':24s} {'recall':>8s} {'realised FPR':>13s} {'recall-FPR':>11s}")
    for e in r["ranking_at_matched_dev_fpr"]:
        print(f"  {e['scorer']:24s} {e['recall']:8.1%} {e['realised_fpr']:13.1%} "
              f"{e['recall_minus_fpr']:+11.1%}")
    print("DONE")
