"""Phase 11 -- leave-one-attack-family-out generalization test for the GLN,
completing the GLN half of the "GLN and the B10 hybrid were never touched
by any of this" gap. Mirrors `phase11/gnn/lofo.py`'s own protocol as
closely as the GLN's different (online, streaming) architecture allows.

WHY THE PROTOCOL DIFFERS FROM THE GNN'S OWN LOFO
--------------------------------------------------------------------------------
The GNN is batch-trained once, then evaluated with frozen weights. The GLN
is architecturally an ONLINE learner (Plan Section 3's own stated reason
for choosing it) -- `_warm_up_gln_and_score_held_out()` (`run_b10.py`)
already only ever calls `model.predict(...)` (never `..._and_update(...,
target=...)`) at held-out time, so held-out ground truth never reaches its
weights either way. The honest LOFO question for THIS architecture is:
after warming up on every family EXCEPT the excluded one, what score does
the frozen model give the excluded family's held-out examples on their
FIRST (zero-shot, no online adaptation yet) retrieval -- i.e. real,
measured zero-shot generalization, the direct GLN analogue of the GNN's
own "trained without this family, scored on it once" question.
"""

from __future__ import annotations

import statistics
from typing import Dict, List, Sequence

import numpy as np
import torch

from phase11.data import split
from phase11.gnn.features import FEATURE_KEYS
from phase11.gnn.lofo import _discover_families, family_map_for_pools, filter_pools_excluding_family
from phase11.gnn.self_supervised import auroc as _auroc
from phase11.gln.model import GatedLinearNetwork
from phase11.gln.stream import STREAM_SEED, build_memory_streams


def run_lofo_fold(family: str) -> dict:
    warmup_pools = filter_pools_excluding_family(split.all_dev_pools(), family)
    warmup_streams = build_memory_streams(warmup_pools)

    held_out_pools = split.held_out_pools()
    held_out_streams = build_memory_streams(held_out_pools)
    held_out_family_map = family_map_for_pools(held_out_pools)

    model = GatedLinearNetwork(input_dim=len(FEATURE_KEYS), context_dim=len(FEATURE_KEYS), seed=STREAM_SEED)
    for stream in warmup_streams:
        features = np.clip(np.array(stream.events[0], dtype=float), 1e-3, 1 - 1e-3)
        model.predict_and_update(features, features, target=1.0 if stream.is_poison_ground_truth else 0.0)

    family_scores, benign_scores = [], []
    for stream in held_out_streams:
        features = np.clip(np.array(stream.events[0], dtype=float), 1e-3, 1 - 1e-3)
        score = model.predict(features, features)  # zero-shot -- no online update from this call
        if stream.is_poison_ground_truth and held_out_family_map.get(stream.scenario_id) == family:
            family_scores.append(score)
        elif not stream.is_poison_ground_truth:
            benign_scores.append(score)

    combined = torch.tensor(family_scores + benign_scores)
    labels = torch.tensor([1.0] * len(family_scores) + [0.0] * len(benign_scores))
    return {
        "family": family, "n_poison": len(family_scores), "n_benign": len(benign_scores),
        "auroc": _auroc(combined, labels),
        "mean_poison_score": statistics.mean(family_scores) if family_scores else float("nan"),
        "mean_benign_score": statistics.mean(benign_scores) if benign_scores else float("nan"),
    }


def run_all_families() -> Dict[str, dict]:
    families = _discover_families(split.all_dev_pools())
    return {family: run_lofo_fold(family) for family in families}


def baseline_pooled_family() -> dict:
    """The SAME real GLN protocol `run_b10.py` already uses (warm up on
    ALL families), for a same-run comparison point -- not a new
    measurement, reusing `stream.py`'s own real per-family breakdown
    machinery would require its own module; this reproduces just the
    per-family zero-shot AUROC using the already-warmed-up, full model."""
    warmup_streams = build_memory_streams(split.all_dev_pools())
    held_out_pools = split.held_out_pools()
    held_out_streams = build_memory_streams(held_out_pools)
    held_out_family_map = family_map_for_pools(held_out_pools)

    model = GatedLinearNetwork(input_dim=len(FEATURE_KEYS), context_dim=len(FEATURE_KEYS), seed=STREAM_SEED)
    for stream in warmup_streams:
        features = np.clip(np.array(stream.events[0], dtype=float), 1e-3, 1 - 1e-3)
        model.predict_and_update(features, features, target=1.0 if stream.is_poison_ground_truth else 0.0)

    by_family: Dict[str, List[float]] = {}
    benign_scores = []
    for stream in held_out_streams:
        features = np.clip(np.array(stream.events[0], dtype=float), 1e-3, 1 - 1e-3)
        score = model.predict(features, features)
        if stream.is_poison_ground_truth:
            by_family.setdefault(held_out_family_map.get(stream.scenario_id), []).append(score)
        else:
            benign_scores.append(score)

    out = {}
    for family, scores in by_family.items():
        combined = torch.tensor(scores + benign_scores)
        labels = torch.tensor([1.0] * len(scores) + [0.0] * len(benign_scores))
        out[family] = {"n_poison": len(scores), "auroc": _auroc(combined, labels)}
    return out


if __name__ == "__main__":
    import json

    print("=== GLN LOFO (zero-shot, family excluded from warmup) ===")
    lofo = run_all_families()
    for family, r in lofo.items():
        print(f"  {family}: n={r['n_poison']} auroc={r['auroc']:.4f} "
              f"mean_poison={r['mean_poison_score']:.4f} mean_benign={r['mean_benign_score']:.4f}")

    print("\n=== GLN pooled-family (all families in warmup), for comparison ===")
    pooled = baseline_pooled_family()
    print(json.dumps(pooled, indent=2))
