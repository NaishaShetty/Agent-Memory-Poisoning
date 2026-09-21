"""Phase 11.y Section 9 (priority experiment) -- semantic consistency between
a candidate memory and its GENUINELY RELATED neighborhood.

THE REAL, AUDITABLE RELATIONSHIP USED HERE
--------------------------------------------------------------------------------
"Genuinely related" is defined as: real benign turns from the SAME real
LoCoMo task the candidate memory's own seed targets. This is not invented --
every poison seed's real target LoCoMo task_id is already a known, real fact
(recorded in `phase4/attacks/*/seeds.py` for the original 15, and in
`phase11/data/poison_regeneration.py`'s own `GenerationRecord` for the new
7). No new edge type or schema field is introduced; this module only reuses
an already-known real fact (shared task_id) to define a comparison set.

WHAT THIS DOES NOT CLAIM
--------------------------------------------------------------------------------
Per the governing instructions: low similarity to a neighborhood is NOT
automatically "contradiction," and this module never asserts a real
contradiction label. It computes one candidate measurement --
"neighborhood agreement" (mean cosine similarity to the real neighborhood)
-- and reports whether poison and benign populations differ on it. No
ground-truth contradiction relationship is created.

MODEL: the SAME pinned `sentence-transformers/all-MiniLM-L6-v2`, loaded via
`phase3/evaluation/foundations/similarity.py::_load_model()` unmodified --
no new model, no modification to the existing Phase 6.6 semantic-divergence
implementation.

TASK-0 DIAGNOSTIC USE, DISCLOSED
--------------------------------------------------------------------------------
`real_benign_scenarios()` deliberately excludes LoCoMo task_id=0 (to avoid
overlapping with the original 15 poison seeds' own source task). Several
poison seeds legitimately target task 0, so this module fetches task-0 real
benign turns via the SAME real `load_db_locomo()` loader `real_corpus.py`
already uses -- but ONLY for this read-only comparison. Those turns are
NEVER added to any training pool, and this module contains no function that
returns them as a `ScenarioPool` -- confirmed by
`phase11/tests/test_relational_signals.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np

from phase3.evaluation.foundations.similarity import _load_model
from phase4.attacks.agentpoison.locomo_pool import load_db_locomo

# task_id basis: "declared" = the seed's own real task_id field; "thematic" =
# the new seed's content is thematically anchored to that task but not a
# direct QA contradiction (MINJA/AgentPoison, per poison_regeneration.py's
# own disclosure); "none" = no real task association exists at all.
POISON_SOURCE_TASK_MAP: Dict[str, Tuple[Optional[int], str]] = {
    # original 15 (real_corpus.py) -- all DSRM/FARMA/MPBench/MemoryGraft/Sleeper
    # seeds real-declare task_id=0; MINJA/AgentPoison's original seeds have no
    # real task association (placeholder trigger text / generic bridging queries).
    "REAL-DSRM-0": (0, "declared"), "REAL-DSRM-1": (0, "declared"), "REAL-DSRM-2": (0, "declared"),
    "REAL-FARMA-0": (0, "declared"), "REAL-FARMA-1": (0, "declared"), "REAL-FARMA-2": (0, "declared"),
    "REAL-MPBENCH-0": (0, "declared"), "REAL-MPBENCH-1": (0, "declared"), "REAL-MPBENCH-2": (0, "declared"),
    "REAL-MEMORYGRAFT-0": (0, "declared"), "REAL-SLEEPER-0": (0, "declared"),
    "REAL-MINJA-0": (None, "none"), "REAL-MINJA-1": (None, "none"), "REAL-MINJA-2": (None, "none"),
    "REAL-AGENTPOISON-0": (None, "none"),
    # new 7 (poison_regeneration.py) -- declared for DSRM/FARMA/MPBench/Sleeper/
    # MemoryGraft (real QA-pair targets); thematic only for MINJA/AgentPoison
    # (their own module already discloses this).
    "REGEN-DSRM-0": (1, "declared"), "REGEN-FARMA-0": (2, "declared"), "REGEN-MPBENCH-0": (3, "declared"),
    "REGEN-SLEEPER-0": (4, "declared"), "REGEN-MEMORYGRAFT-0": (5, "declared"),
    "REGEN-MINJA-0": (6, "thematic"), "REGEN-MINJA-1": (6, "thematic"), "REGEN-MINJA-2": (6, "thematic"),
    "REGEN-AGENTPOISON-0": (7, "thematic"),
}

_TASK0_DIAGNOSTIC_CACHE: Dict[int, List[str]] = {}


def _task0_diagnostic_benign_turns(max_turns: int = 15) -> List[str]:
    """Real task-0 LoCoMo turns, READ-ONLY, for the neighborhood comparison
    only -- never returned as a ScenarioPool, never added to training."""
    if 0 not in _TASK0_DIAGNOSTIC_CACHE:
        _TASK0_DIAGNOSTIC_CACHE[0] = load_db_locomo(task_index=0, max_turns=max_turns)
    return _TASK0_DIAGNOSTIC_CACHE[0]


def embed(texts: List[str]) -> np.ndarray:
    model = _load_model()
    return np.asarray(model.encode(list(texts), normalize_embeddings=True, show_progress_bar=False))


@dataclass(frozen=True)
class NeighborhoodAgreementResult:
    scenario_id: str
    source_task_id: Optional[int]
    task_basis: str
    is_poison_ground_truth: bool
    attack_family_ground_truth: Optional[str]
    neighborhood_size: int
    mean_similarity: float
    min_similarity: float
    max_similarity: float


def compute_neighborhood_agreement(
    candidates: List, task_neighborhoods: Dict[int, List[str]],
) -> List[NeighborhoodAgreementResult]:
    """`candidates`: real MemoryScenario objects with a KNOWN source task
    (via POISON_SOURCE_TASK_MAP for poison, or the caller's own real
    per-task benign pools for benign). `task_neighborhoods`: {task_id: [real
    benign turn texts for that task]} -- the caller supplies this (from
    `real_benign_scenarios()` for tasks 1-9, plus the task-0 diagnostic
    fetch above for task 0), never computed inside this function, so no
    hidden data access happens here."""
    results: List[NeighborhoodAgreementResult] = []
    for scenario, task_id, basis in candidates:
        if task_id is None or task_id not in task_neighborhoods or not task_neighborhoods[task_id]:
            continue
        neighborhood_texts = [t for t in task_neighborhoods[task_id] if t != scenario.content_text]
        if not neighborhood_texts:
            continue
        vecs = embed([scenario.content_text] + neighborhood_texts)
        candidate_vec, neighbor_vecs = vecs[0], vecs[1:]
        sims = neighbor_vecs @ candidate_vec
        results.append(
            NeighborhoodAgreementResult(
                scenario_id=scenario.scenario_id, source_task_id=task_id, task_basis=basis,
                is_poison_ground_truth=scenario.is_poison_ground_truth,
                attack_family_ground_truth=scenario.attack_family_ground_truth,
                neighborhood_size=len(neighborhood_texts),
                mean_similarity=float(sims.mean()), min_similarity=float(sims.min()),
                max_similarity=float(sims.max()),
            )
        )
    return results
