"""Phase 3.3-V2 -- the benchmark-owned hybrid selection mechanism (V2's validated
Condition-C selection policy): cosine similarity + token/lexical overlap + entity/date
overlap, fixed weights, top-K by blended score (no hard threshold).

PROVENANCE -- this is not a new idea introduced here. It is the exact mechanism
validated across `phase3/experiments/research_variant/` Rounds 5/6/7/11 (retrieval pool
widening + hybrid rerank), fixed weights `0.5/0.3/0.2` disclosed and fixed BEFORE any of
those rounds were run (never tuned on their results). This module is the promotion of
that validated research mechanism into production `phase3/evaluation` code, mirroring
`foundations/selection_policy.py`'s own threshold-based sibling exactly in spirit:
- `selection_policy.py` -- retrieve N=20, keep everything >= a calibrated threshold,
  capped at top-K.
- `hybrid_selection.py` (this module) -- retrieve N=20, score every candidate with a
  fixed-weight blend of THREE signals, take the top-K by that blended score -- no hard
  score floor (Round 2b's finding: a hard threshold discarded genuinely useful
  borderline candidates a ranked top-K captured instead).

Reuses `foundations/similarity.py::score_candidates()` (the same pinned
`sentence-transformers/all-MiniLM-L6-v2` model already loaded by both real foundation
adapters) for the cosine term -- no new embedding model, no new dependency.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Sequence, Tuple

from phase3.evaluation.foundations.similarity import score_candidates

RETRIEVAL_POOL_SIZE_N = 20  # identical constant to selection_policy.py -- same pool size
DEFAULT_TOP_K = 8  # validated in Rounds 5/6/7/11 -- not tuned per-run

HYBRID_WEIGHT_COSINE = 0.5
HYBRID_WEIGHT_TOKEN_OVERLAP = 0.3
HYBRID_WEIGHT_ENTITY_OVERLAP = 0.2

_WORD_RE = re.compile(r"[A-Za-z0-9']+")
_PROPER_RE = re.compile(r"\b[A-Z][a-zA-Z]+\b")
_DIGIT_RE = re.compile(r"\b\d+\b")


def _token_overlap_recall(query: str, content: str) -> float:
    q = set(_WORD_RE.findall(query.lower()))
    if not q:
        return 0.0
    c = set(_WORD_RE.findall(content.lower()))
    return len(q & c) / len(q)


def _entity_overlap_recall(query: str, content: str) -> float:
    q_entities = set(_PROPER_RE.findall(query)) | set(_DIGIT_RE.findall(query))
    if not q_entities:
        return 0.0
    c_entities = set(_PROPER_RE.findall(content)) | set(_DIGIT_RE.findall(content))
    return len(q_entities & c_entities) / len(q_entities)


@dataclass(frozen=True)
class HybridScoredCandidate:
    memory_id: str
    content: str
    cosine_score: float
    token_overlap_score: float
    entity_overlap_score: float
    blended_score: float


@dataclass(frozen=True)
class HybridSelectionResult:
    selected: Tuple[HybridScoredCandidate, ...]
    rejected: Tuple[HybridScoredCandidate, ...]
    top_k: int
    weights: Tuple[float, float, float]


def select_by_hybrid_score(
    query: str,
    candidates: Sequence[Tuple[str, str]],
    top_k: int = DEFAULT_TOP_K,
) -> HybridSelectionResult:
    """Score every `(memory_id, content)` candidate with the fixed-weight blend, keep
    the top `top_k` by blended score. Never a hard score floor -- a pool with fewer
    than `top_k` candidates simply selects all of them; a pool with `top_k` or more
    always selects exactly `top_k` (unlike `select_by_threshold`, which can select
    fewer than `max_k` or zero). Every non-selected candidate is returned in
    `rejected`, in the same scored form, so a caller can emit a real `rejected`
    CanonicalEvent for each with its own real score attached -- identical discipline to
    `selection_policy.py::select_by_threshold()`.
    """
    if not candidates:
        return HybridSelectionResult(selected=(), rejected=(), top_k=top_k,
                                      weights=(HYBRID_WEIGHT_COSINE, HYBRID_WEIGHT_TOKEN_OVERLAP, HYBRID_WEIGHT_ENTITY_OVERLAP))

    cosine_scored = {c.memory_id: c.score for c in score_candidates(query, candidates)}

    scored: List[HybridScoredCandidate] = []
    for memory_id, content in candidates:
        cosine = cosine_scored.get(memory_id, 0.0)
        tok = _token_overlap_recall(query, content)
        ent = _entity_overlap_recall(query, content)
        blended = HYBRID_WEIGHT_COSINE * cosine + HYBRID_WEIGHT_TOKEN_OVERLAP * tok + HYBRID_WEIGHT_ENTITY_OVERLAP * ent
        scored.append(HybridScoredCandidate(
            memory_id=memory_id, content=content, cosine_score=cosine,
            token_overlap_score=tok, entity_overlap_score=ent, blended_score=blended,
        ))

    scored_sorted = sorted(scored, key=lambda c: c.blended_score, reverse=True)
    selected = tuple(scored_sorted[:top_k])
    rejected = tuple(scored_sorted[top_k:])

    return HybridSelectionResult(
        selected=selected, rejected=rejected, top_k=top_k,
        weights=(HYBRID_WEIGHT_COSINE, HYBRID_WEIGHT_TOKEN_OVERLAP, HYBRID_WEIGHT_ENTITY_OVERLAP),
    )


__all__ = [
    "RETRIEVAL_POOL_SIZE_N",
    "DEFAULT_TOP_K",
    "HYBRID_WEIGHT_COSINE",
    "HYBRID_WEIGHT_TOKEN_OVERLAP",
    "HYBRID_WEIGHT_ENTITY_OVERLAP",
    "HybridScoredCandidate",
    "HybridSelectionResult",
    "select_by_hybrid_score",
]
