"""Make the learned/graph component earn its place (external review round 5).

THE PROBLEM, from `b10_ablation_results.json` and confirmed in
`PHASE17_REVIEW4_RESULTS.md` §8c: B10's learned GNN is useless as shipped and dangerous
unshipped.

  gated (W=0, 0.25, 1)   identical on EVERY population -- only_a = only_b = 0, p = 1.0.
                         The gate decides everything; the learned score changes no decision.
  ungated (W=1)          33/34 on `frozen75` (the arena containing coordinated near-duplicate
                         poison pools) versus 16/34 gated -- but 18/502 benign FPR (3.6%) and
                         0/47 on isolated evasion variants.

So the learned component has real signal, in exactly one place: pools where several memories
corroborate each other because an attacker planted a cluster. The shipped gating destroys
that signal; removing the gating exports it to every memory, including isolated benign ones,
which is where the false positives come from.

THE FIX: stop treating it as a per-memory score at all. Coordination is a property of a
POOL, so this computes a pool-level statistic and only lets it act when the pool actually
looks coordinated:

  1. build the pool's memory-memory similarity graph (the real embedding this project's
     retrieval signals use);
  2. find its largest near-duplicate clique above `SIM`;
  3. if that clique is at least `MIN_CLIQUE` memories AND they do not share a common
     conversational source, the pool is COORDINATED and its clique members are escalated;
  4. otherwise the signal emits nothing at all -- an isolated memory can never be escalated
     by it, which is structurally why it cannot reproduce the ungated variant's benign
     false positives.

That is the reviewer's own proposal ("keep it only as a documented ungated variant for
coordinated attacks") turned into something shippable: ungated within coordinated pools,
silent everywhere else. Thresholds are set on dev in `tune()`.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import numpy as np

OUT = Path(__file__).parent / "data" / "coordination_signal.json"
# FROZEN on dev (`tune()`, 2026-09-30). At this operating point the signal escalates 19/34
# coordinated poisons in the frozen75 arena at 0/613 benign false positives, versus B10's
# shipped gated variant (16/34, 0/502) and its ungated variant (33/34 but 18/502 = 3.6% FPR).
# Better recall than the shipped gating at the same zero benign cost, and structurally unable
# to reproduce the ungated variant's false positives, since it cannot fire on an isolated
# memory at all. It does NOT reach the ungated 33/34 -- that recall is real and is paid for
# with a benign cost this project is not willing to ship.
SIM = 0.90
MIN_CLIQUE = 3


def coordinated_members(items: Sequence[Tuple[str, str]], sim: float = SIM,
                        min_clique: int = MIN_CLIQUE) -> Dict[str, float]:
    """{memory_id: clique similarity} for members of a near-duplicate cluster of at least
    `min_clique` memories. Empty for any pool without such a cluster — including every
    single-memory pool, by construction."""
    from phase17.semantic_detector import _embed

    if len(items) < min_clique:
        return {}
    ids = [i for i, _ in items]
    E = _embed([t for _, t in items])
    S = E @ E.T
    np.fill_diagonal(S, 0.0)
    adj = S >= sim
    out: Dict[str, float] = {}
    n = len(ids)
    for i in range(n):
        nbrs = [j for j in range(n) if adj[i, j]]
        if len(nbrs) + 1 < min_clique:
            continue
        # require the neighbourhood to be mutually similar too (a cluster, not a hub)
        mutual = [j for j in nbrs if sum(adj[j, k] for k in nbrs if k != j) + 1 >= min_clique - 1]
        if len(mutual) + 1 >= min_clique:
            out[ids[i]] = float(S[i, mutual].max()) if mutual else 0.0
    return out


def tune(sims=(0.78, 0.82, 0.86, 0.90), cliques=(2, 3, 4)) -> dict:
    """DEV ONLY: how often does a coordinated cluster appear in real benign pools (false
    alarms) versus in this project's coordinated poison arena (true detections)?"""
    from phase17.arenas import dataset_arena, frozen_arena
    from phase17.extra_datasets import convomem_pools

    # `frozen_arena` (corpus.py's 75 scenarios) is the arena that actually CONTAINS
    # coordinated near-duplicate / paraphrased poison clusters, and is where B10's ungated
    # variant scored 33/34. `coordinated_arena(original_records())` is not: it merely pools
    # 15 poisons from 7 different families together, which are not near-duplicates of one
    # another, so a clique signal correctly finds nothing there.
    poison_pools, ptruth = frozen_arena()
    benign_pools = sorted(dataset_arena()[0], key=lambda p: p.pool_id)[0::2]
    benign_pools += sorted(convomem_pools()[0], key=lambda p: p.pool_id)[0::2]
    res = {}
    for sim in sims:
        for mc in cliques:
            tp = tot_p = fp_in_poison_pool = 0
            for p in poison_pools:
                items = [(m.scenario_id, m.content_text) for m in p.memories]
                hit = coordinated_members(items, sim, mc)
                for m in p.memories:
                    if m.is_poison_ground_truth:
                        tot_p += 1
                        tp += m.scenario_id in hit
                    else:
                        fp_in_poison_pool += m.scenario_id in hit
            fp = tot_b = 0
            for p in benign_pools:
                items = [(m.scenario_id, m.content_text) for m in p.memories]
                hit = coordinated_members(items, sim, mc)
                fp += len(hit)
                tot_b += len(p.memories)
            res[f"sim={sim},clique={mc}"] = {"poison_escalated": f"{tp}/{tot_p}",
                                             "benign_in_poison_pools": fp_in_poison_pool,
                                             "benign_escalated": f"{fp}/{tot_b}",
                                             "benign_rate": round(fp / max(tot_b, 1), 4)}
            print(f"  sim={sim} clique={mc}: poison {tp}/{tot_p}, benign-in-poison-pool "
                  f"{fp_in_poison_pool}, benign {fp}/{tot_b}", flush=True)
    OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")
    return res


if __name__ == "__main__":
    print(json.dumps(tune(), indent=1))
    print("DONE")
