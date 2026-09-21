"""SUPERSEDED (2026-09-20) -- kept for the real, disclosed negative/
diagnostic result it produced, not as a recommended approach. The
chunk-size sweep here (Fix Attempt A) was measured to have NO effect --
the real cause of the reference-threshold's residual FPR was not pool
topology at all, but a genuinely different, more fundamental fact: every
one of the 135 real LoCoMo benign turns in `real_benign_scenarios()`
shares the IDENTICAL 9-feature vector (`(0,0,1,0,0,0,0,0,0)` -- only the
constant `dormancy_activation_score` is ever nonzero on ordinary
conversational text), confirmed directly in
`docs/phase11/PHASE11_LOFO_FPR_AND_FARMA_FIX_REPORT.md` Section 2. That
same degeneracy is also why this module's own blend-weight sweep (Fix
Attempt B) produced a broken, degenerate result (AUROC pinned at exactly
0.5) once corrected to use reference-based z-score statistics -- dividing
by zero variance. The REAL, adopted fix is
`phase11/gnn/lofo_blend_infold_threshold.py` (same blend, but calibrated
against the fold's own real, non-degenerate training-benign set instead of
this degenerate real-LoCoMo reference) -- see
`docs/phase11/PHASE11_LOFO_FPR_AND_FARMA_FIX_REPORT.md` Attempt 3 for the
real, measured, adopted result, now wired into `run_b10.py`
(`docs/phase11/PHASE11_BLEND_WIRING_REPORT.md`).

--- Original module docstring below, unmodified ---

Phase 11 -- two further real fix attempts, requested directly: (1) the
reference-threshold's own residual FPR (disclosed as likely caused by a
cross-corpus pool-size mismatch between the 135-example reference's
15-member cliques and the training/held-out corpus's 3-9-member pools),
and (2) FARMA's ranking never breaking chance-level AUROC under any fit
tried so far.

FIX ATTEMPT A -- RE-CHUNK THE REFERENCE TO A COMPARABLE POOL SIZE
--------------------------------------------------------------------------------
`_rechunked_reference_pools(chunk_size)` regroups the SAME 135 real LoCoMo
benign turns `real_benign_scenarios()` already provides into smaller pools
(real content unchanged, only pool membership changes) -- the exact same
technique `PHASE11_X_OPTION2_EXPANDED_FEATURES_REPORT.md` Section 15
already used and disclosed for a different purpose, applied here locally
(this module never modifies `real_corpus.py` itself, so Option 1/2's own
protected numbers are untouched). Chunk sizes {3, 5, 8, 15} are
pre-registered before any result is seen -- 15 is the ORIGINAL, unchunked
reference (`lofo_reference_threshold.py`'s own result, reproduced here as
the comparison point), 3/5/8 span the training/held-out corpus's own real
3-9-member pool-size range.

FIX ATTEMPT B -- BLEND THE FITTED SCORE WITH THE UNTRAINED RAW-SUM SCORE
--------------------------------------------------------------------------------
`PHASE11_LOFO_BASELINE_C_REPORT.md`'s own real finding: the untrained
raw-feature-sum score achieves AUROC 1.0 on FARMA's real held-out poison,
while every FITTED model (GNN, linear) collapses toward or below chance
for that same family. Rather than discard the fitted model (it is the
best option for MemoryGraft-style-volume), this blends the two, per-node,
after z-score-normalizing each on the SAME fold-local training
distribution (no held-out, no excluded-family data used for the
normalization statistics): `blended = w * z(fitted) + (1-w) * z(raw_sum)`.
`w` is pre-registered over {0.0, 0.25, 0.5, 0.75, 1.0} -- 0.0 is pure
raw-sum, 1.0 is pure fitted (reproducing the prior report's own numbers as
a same-run comparison point), before any blended result is seen.

EFFICIENCY, NOT A METHODOLOGY CHANGE
--------------------------------------------------------------------------------
Each (family, seed) GNN is trained EXACTLY ONCE (identical to every prior
LOFO module's protocol) and its scores are reused across every chunk-size
and blend-weight combination tested here -- avoiding redundant retraining,
never re-fitting a different model to chase a better number.
"""

from __future__ import annotations

import statistics
from typing import Dict, List, Sequence, Tuple

import torch

from phase11.data import split
from phase11.data.real_corpus import real_benign_scenarios
from phase11.gnn.features import pools_node_features, FEATURE_KEYS
from phase11.gnn.lofo import SEEDS, _discover_families, filter_pools_excluding_family, family_map_for_pools
from phase11.gnn.self_supervised import auroc as _auroc
from phase11.gnn.train import build_dataset, train_model, TARGET_TRAIN_FALSE_POSITIVE_RATE, _threshold_for_target_fpr
from phase6.defense.orchestration.pipeline import ScenarioPool

CHUNK_SIZES: Tuple[int, ...] = (3, 5, 8, 15)  # 15 = original, unchunked reference
BLEND_WEIGHTS: Tuple[float, ...] = (0.0, 0.25, 0.5, 0.75, 1.0)  # 1.0 = pure fitted (prior report's own number)
WEIGHT_DECAY = 0.005  # best value found in the prior sweep -- held fixed, not re-swept here


def _rechunked_reference_pools(chunk_size: int) -> Tuple[ScenarioPool, ...]:
    flat = [m for pool in real_benign_scenarios() for m in pool.memories]
    pools = []
    for i in range(0, len(flat), chunk_size):
        chunk = tuple(flat[i:i + chunk_size])
        pools.append(ScenarioPool(f"REF-CHUNK-{chunk_size}-{i // chunk_size}", chunk))
    return tuple(pools)


def _raw_sum(features: torch.Tensor) -> torch.Tensor:
    return features.sum(dim=1)


def _zscore(values: torch.Tensor, mean: float, std: float) -> torch.Tensor:
    if std == 0.0:
        return torch.zeros_like(values)
    return (values - mean) / std


def _evaluate(scores: Sequence[float], labels: Sequence[float], threshold: float) -> dict:
    poison = [s for s, y in zip(scores, labels) if y == 1.0]
    benign = [s for s, y in zip(scores, labels) if y == 0.0]
    detected = sum(1 for s in poison if s >= threshold)
    flagged = sum(1 for s in benign if s >= threshold)
    return {
        "n_poison": len(poison), "n_benign": len(benign),
        "detection_rate": detected / len(poison) if poison else float("nan"),
        "false_positive_rate": flagged / len(benign) if benign else float("nan"),
        "auroc": _auroc(torch.tensor(list(scores)), torch.tensor(list(labels))),
    }


def run_fold_all_configs(family: str, *, seeds: Sequence[int] = SEEDS) -> Dict[Tuple[int, float], List[dict]]:
    """Trains once per seed for this family's fold, then evaluates every
    (chunk_size, blend_weight) combination against that SAME trained
    model's own real scores -- no redundant retraining."""
    train_pools = filter_pools_excluding_family(split.all_dev_pools(), family)
    train_ds = build_dataset(train_pools)

    held_out_pools = split.held_out_pools()
    held_out_ds = build_dataset(held_out_pools)
    held_out_family_map = family_map_for_pools(held_out_pools)

    reference_ds_by_chunk = {cs: build_dataset(_rechunked_reference_pools(cs)) for cs in CHUNK_SIZES}

    results: Dict[Tuple[int, float], List[dict]] = {(cs, w): [] for cs in CHUNK_SIZES for w in BLEND_WEIGHTS}

    for seed in seeds:
        model = train_model(train_ds, seed=seed, weight_decay=WEIGHT_DECAY)

        # z-score statistics come from the LARGE reference population (135 real
        # examples), not the tiny 8-11-example training fold -- fixed here after
        # a real, measured finding that using the tiny fold's own mean/std
        # reintroduced the exact small-sample fragility the reference-threshold
        # fix (`lofo_reference_threshold.py`) was built to remove in the first
        # place. Still training-side only (the reference is never poison-
        # labeled, never used to fit model weights) -- computed once per
        # chunk_size below, from that SAME chunking's own reference scores.
        held_out_fitted = model.predict_proba(held_out_ds.features, held_out_ds.mean_adj)
        held_out_raw = _raw_sum(held_out_ds.features)

        for chunk_size in CHUNK_SIZES:
            ref_ds = reference_ds_by_chunk[chunk_size]
            ref_fitted = model.predict_proba(ref_ds.features, ref_ds.mean_adj)
            ref_raw = _raw_sum(ref_ds.features)

            # z-score stats fit on THIS chunking's own reference population (n=135
            # regardless of chunk_size -- chunking only changes pool/graph topology,
            # not how many real examples exist), then applied identically to both
            # the reference itself and the held-out scores.
            fit_mean, fit_std = ref_fitted.mean().item(), ref_fitted.std(unbiased=False).item()
            raw_mean, raw_std = ref_raw.mean().item(), ref_raw.std(unbiased=False).item()

            ref_z_fit = _zscore(ref_fitted, fit_mean, fit_std)
            ref_z_raw = _zscore(ref_raw, raw_mean, raw_std)
            held_out_z_fit = _zscore(held_out_fitted, fit_mean, fit_std)
            held_out_z_raw = _zscore(held_out_raw, raw_mean, raw_std)

            for w in BLEND_WEIGHTS:
                ref_blend = (w * ref_z_fit + (1 - w) * ref_z_raw).tolist()
                threshold = _threshold_for_target_fpr(ref_blend, [0.0] * len(ref_blend), TARGET_TRAIN_FALSE_POSITIVE_RATE)

                held_out_blend = (w * held_out_z_fit + (1 - w) * held_out_z_raw).tolist()
                held_out_labels = held_out_ds.labels.tolist()

                family_scores, benign_scores = [], []
                for nid, score, label in zip(held_out_ds.node_ids, held_out_blend, held_out_labels):
                    if label == 1.0 and held_out_family_map.get(nid) == family:
                        family_scores.append(score)
                    elif label == 0.0:
                        benign_scores.append(score)

                result = _evaluate(
                    family_scores + benign_scores,
                    [1.0] * len(family_scores) + [0.0] * len(benign_scores),
                    threshold,
                )
                result.update(family=family, seed=seed, chunk_size=chunk_size, w=w)
                results[(chunk_size, w)].append(result)

    return results


def summarize(results: List[dict]) -> dict:
    detections = [r["detection_rate"] for r in results]
    fprs = [r["false_positive_rate"] for r in results]
    aurocs = [r["auroc"] for r in results]
    return {
        "family": results[0]["family"], "chunk_size": results[0]["chunk_size"], "w": results[0]["w"],
        "n_poison": results[0]["n_poison"], "n_benign": results[0]["n_benign"],
        "detection_rate_mean": statistics.mean(detections),
        "false_positive_rate_mean": statistics.mean(fprs),
        "auroc_mean": statistics.mean(aurocs), "auroc_min": min(aurocs), "auroc_max": max(aurocs),
    }


def run_all_families(*, seeds: Sequence[int] = SEEDS) -> Dict[str, Dict[Tuple[int, float], List[dict]]]:
    families = _discover_families(split.all_dev_pools())
    return {family: run_fold_all_configs(family, seeds=seeds) for family in families}


def macro_by_config(all_results: Dict[str, Dict[Tuple[int, float], List[dict]]]) -> Dict[Tuple[int, float], dict]:
    configs = next(iter(all_results.values())).keys()
    out = {}
    for cfg in configs:
        per_family_summaries = [summarize(all_results[family][cfg]) for family in all_results]
        out[cfg] = {
            "macro_auroc": statistics.mean(s["auroc_mean"] for s in per_family_summaries),
            "macro_detection_rate": statistics.mean(s["detection_rate_mean"] for s in per_family_summaries),
            "macro_false_positive_rate": statistics.mean(s["false_positive_rate_mean"] for s in per_family_summaries),
        }
    return out


if __name__ == "__main__":
    import json

    all_results = run_all_families()
    macro = macro_by_config(all_results)

    print("=== Macro summary by (chunk_size, w) ===")
    for cfg, m in sorted(macro.items()):
        print(f"chunk_size={cfg[0]:>2} w={cfg[1]:.2f}  "
              f"macro_auroc={m['macro_auroc']:.4f} "
              f"macro_detection={m['macro_detection_rate']:.4f} "
              f"macro_fpr={m['macro_false_positive_rate']:.4f}")

    print("\n=== Per-family detail at w=0.0 (pure raw-sum) and w=1.0 (pure fitted), chunk_size=5 ===")
    for family in all_results:
        for w in (0.0, 1.0):
            s = summarize(all_results[family][(5, w)])
            print(f"  {family} w={w}: auroc_mean={s['auroc_mean']:.4f} "
                  f"detection_mean={s['detection_rate_mean']:.4f} fpr_mean={s['false_positive_rate_mean']:.4f}")
