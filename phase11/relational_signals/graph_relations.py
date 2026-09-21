"""Phase 11.y Family C -- relational/graph-structure candidate signal:
NEIGHBORHOOD SEMANTIC COHERENCE.

Distinct from every graph feature Option 2 already tried (`graph_degree`,
`pool_size`, `retrieved_with_degree`, etc., all confounded by real-vs-hand-
authored pool-size differences -- see
`docs/phase11/PHASE11_X_OPTION2_EXPANDED_FEATURES_REPORT.md` Section 15).
Those measured STRUCTURAL COUNT; this measures SEMANTIC COHERENCE among the
same real `RETRIEVED_WITH` neighbors -- a genuinely different quantity that
happens to use the same real, already-sanctioned edge type
(`phase11/gnn/graph_build.py`, unmodified, reused read-only here).

DEFINITION
--------------------------------------------------------------------------------
For a memory `i` in pool `P`, `coherence(i) = mean_{j in P, j != i} cos(embed(i), embed(j))`.
No new edge is created -- `P`'s real, already-sanctioned `RETRIEVED_WITH`
membership (same-pool co-retrieval) is the only relationship used.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from phase6.defense.orchestration.pipeline import ScenarioPool
from phase11.relational_signals.semantic_relations import embed


@dataclass(frozen=True)
class CoherenceResult:
    scenario_id: str
    pool_id: str
    pool_size: int
    is_poison_ground_truth: bool
    attack_family_ground_truth: Optional[str]
    coherence: float  # mean cosine similarity to real co-pool members; NaN if pool_size == 1


def pool_coherence(pool: ScenarioPool) -> List[CoherenceResult]:
    if len(pool.memories) < 2:
        return [
            CoherenceResult(
                m.scenario_id, pool.pool_id, len(pool.memories), m.is_poison_ground_truth,
                m.attack_family_ground_truth, float("nan"),
            )
            for m in pool.memories
        ]
    texts = [m.content_text for m in pool.memories]
    vecs = embed(texts)
    results = []
    for i, m in enumerate(pool.memories):
        others = [vecs[j] for j in range(len(vecs)) if j != i]
        sims = [float(vecs[i] @ o) for o in others]
        results.append(
            CoherenceResult(
                m.scenario_id, pool.pool_id, len(pool.memories), m.is_poison_ground_truth,
                m.attack_family_ground_truth, sum(sims) / len(sims),
            )
        )
    return results
