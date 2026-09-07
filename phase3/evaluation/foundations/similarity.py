"""Phase 3.3-DATASET -- the benchmark-owned cosine-similarity reranking utility, per
`PHASE3_SELECTION_AND_CREATION_POLICY_DESIGN_REVIEW.md` section 2.1's decided Option B:
a single, foundation-independent mechanism `phase3/evaluation` owns directly, rather
than reusing whatever ranking a specific foundation's `retrieve()` happens to return
internally (which would make "selection" mean a different thing for Mem0 vs. A-MEM).

MODEL: pinned `sentence-transformers/all-MiniLM-L6-v2` -- the SAME model both
`RealMem0Adapter` and `RealAMemAdapter` already load internally (see
`canonical_wiring.py`'s `EMBEDDING_MODEL_REVISION_UNPINNED` constant) -- so this
introduces no NEW model dependency, only a new, benchmark-owned USE of a model this
codebase already depends on twice over. Deterministic (no sampling, no LLM call) --
preserves `REPRODUCIBILITY_CONTRACT.md §3`'s guarantee exactly as `EnvironmentRecord`
already extends it to everything else this session built.

SCOPE BOUNDARY (per the design review's explicit split): this module answers "how
similar are two pieces of text," nothing more. It is reused by BOTH the selection
policy (`selection_policy.py`, this task's other new module) and, if `equivalent_to`
detection is ever built (still deferred, per the design review's §3.2/§4), that future
work -- but `conflicts_with` (contradiction) detection is explicitly OUT OF SCOPE here:
cosine similarity cannot distinguish "near-duplicate" from "same-topic-but-contradicts"
(the design review's own worked example: "meeting is Tuesday" vs. "meeting is
Wednesday" score as SIMILAR, not dissimilar, despite being contradictory) -- this
module must never be used to claim a `conflicts_with` detection; nothing here does so.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence

EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


class SimilarityModelUnavailableError(RuntimeError):
    """Raised if `sentence-transformers` (or the pinned model) cannot be loaded --
    never silently degrades to a fake/random score."""


_model_cache = {}


def _load_model():
    """Lazy, process-local cache -- loaded at most once per process, mirroring how
    each foundation adapter already loads its own embedding model once at
    `initialize()` time. Deliberately NOT loaded at module-import time, so importing
    this module (e.g. for its constants) never requires the real dependency to be
    installed."""
    if "model" not in _model_cache:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise SimilarityModelUnavailableError(
                f"sentence-transformers is not importable in this environment: {exc!r}. "
                f"Run under the same environment RealMem0Adapter/RealAMemAdapter use "
                f"(this codebase's convention: C:\\h4venv), which already carries it."
            ) from exc
        _model_cache["model"] = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _model_cache["model"]


@dataclass(frozen=True)
class ScoredCandidate:
    memory_id: str
    content: str
    score: float


def score_candidates(query: str, candidates: Sequence[Sequence[str]]) -> List[ScoredCandidate]:
    """Cosine similarity between `query` and each `(memory_id, content)` pair in
    `candidates`, in a single batched embedding call (real cost measured, not
    estimated: batching all candidates plus the query in one `model.encode()` call is
    materially cheaper than one call per candidate at LoCoMo's N=20 pool sizes).
    Returns scores in the SAME order as `candidates` -- callers sort/threshold, this
    function never reorders.
    """
    import numpy as np

    if not candidates:
        return []

    model = _load_model()
    texts = [query] + [content for _, content in candidates]
    embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    query_vec = embeddings[0]
    candidate_vecs = embeddings[1:]

    scores = candidate_vecs @ query_vec  # normalized vectors -> dot product == cosine similarity
    return [
        ScoredCandidate(memory_id=mid, content=content, score=float(score))
        for (mid, content), score in zip(candidates, scores)
    ]


__all__ = [
    "EMBEDDING_MODEL_NAME",
    "SimilarityModelUnavailableError",
    "ScoredCandidate",
    "score_candidates",
]
