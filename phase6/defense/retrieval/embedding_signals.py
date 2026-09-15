"""Phase 6.6 (2026-09-14 semantic-escalation follow-up) -- D2: embedding-based
semantic consensus divergence.

WHY THIS EXISTS
--------------------------------------------------------------------------------
`signals.py`'s lexical (Jaccard) divergence, by its own module docstring, is
"almost certainly less accurate AND less semantically aware than the real
A-MemGuard mechanism," and a real, disclosed test
(`test_paraphrased_coordinated_poison_still_fully_evades_dedup`) proves a
concrete failure: three differently-WORDED but same-lie coordinated poison
records evade lexical clustering entirely.

Per explicit instruction, this limitation is not left permanently unresolved
just because the lexical baseline is simpler. This module is D2 in the
D0 (no defense) / D1 (lexical) / D2 (semantic embeddings) / D3 (LLM judge) /
D4 (combined) framework: a genuinely separate, independently evaluable
mechanism, built on REAL sentence embeddings, sharing the exact same
clustering/dampening core as D1 (`dedup_consensus.py`) so the two are a fair,
controlled comparison -- same algorithm, one varied factor (the similarity
metric).

MODEL CHOICE -- NOT ARBITRARY
--------------------------------------------------------------------------------
`sentence-transformers/all-MiniLM-L6-v2` is used because it is the SAME model
Phase 3's own real hybrid rerank cosine term and AgentPoison's real gradient
attack already share (Methodology Draft Section 12.5, Section 17.3) -- reusing
it keeps Phase 6's semantic signal in the same embedding space the rest of this
project already uses, rather than introducing a second, unrelated model with
its own separate footprint. This is a deliberate consistency choice, not a
default picked without reason.

FROZEN CONFIGURATION (per explicit instruction: freeze model, preprocessing,
metric, and threshold before any evaluation; never tune on held-out attacks)
--------------------------------------------------------------------------------
- Model: `sentence-transformers/all-MiniLM-L6-v2` (`EMBEDDING_MODEL_NAME`).
- Preprocessing: none beyond the model's own default tokenization -- raw
  `content_text`, no stemming/lowercasing/stopword removal (unlike the lexical
  signal, which does lowercase-token-set comparison; the embedding model's own
  training already handles casing/morphology).
- Similarity metric: cosine similarity via normalized-embedding dot product
  (`normalize_embeddings=True`).
- Near-duplicate threshold: `NEAR_DUPLICATE_THRESHOLD_SEMANTIC = 0.85`.
  DISCLOSED, NOT INDEPENDENTLY CALIBRATED: this value is chosen from ONE
  illustrative real measurement (the paraphrase-vs-truth example this stage's
  own tests use: paraphrases scored 0.919-0.941 cosine similarity with each
  other and 0.134-0.156 with an unrelated true fact -- a wide, easily-separable
  gap at this specific example). Using the SAME example to both motivate a
  threshold AND test the mechanism would be circular if presented as
  validation; it is presented here ONLY as a threshold justification, and the
  actual validation claim is limited to "this threshold correctly separates
  THIS constructed example," not a general claim about MAMBench's real attack
  content. Real calibration against real, held-out-appropriate development
  data is explicitly Stage 6.9's job (Rule 14: never tune on the held-out
  evaluation set itself).
- Dampening exponent: reuses `DEDUP_DAMPENING_EXPONENT = 0.5` from `signals.py`
  unchanged -- no separate semantic-specific dampening tuning was performed
  (no evidence yet justifies a different value here).

ENVIRONMENT / REPRODUCIBILITY
--------------------------------------------------------------------------------
`HF_HUB_OFFLINE=1` is set before loading the model, so this module NEVER
attempts a network fetch -- it requires the model already present in the local
Hugging Face cache (confirmed present in this environment at
`~/.cache/huggingface/hub/models--sentence-transformers--all-MiniLM-L6-v2`,
verified by direct inspection before this module was written, not assumed).
If the model is not cached in a different environment, this module raises
loudly (`OSError` from the underlying library) rather than silently falling
back to a network fetch or a different model.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Optional, Sequence, Tuple

from phase6.defense.policy.records import FORBIDDEN_SIGNAL_KEYS, EvaluatorOnlyLeakageError
from phase6.defense.retrieval.dedup_consensus import cluster_by_similarity_matrix, dampened_divergence
from phase6.defense.retrieval.signals import DEDUP_DAMPENING_EXPONENT

EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
NEAR_DUPLICATE_THRESHOLD_SEMANTIC = 0.85
SEMANTIC_SIGNALS_VERSION = "retrieval-semantic-signals-1.0.0"

os.environ.setdefault("HF_HUB_OFFLINE", "1")

_model_cache: dict = {}


def _get_model():
    """Lazily loaded, process-wide cached model instance -- loaded once, not
    per call (a real, measured cost; see `EmbeddingComputationCost` below).
    Import of `sentence_transformers` is deferred to this function so that
    every OTHER module in this package remains importable in an environment
    that does not have it installed (this project's own "additive, never a
    hard new dependency on everything" discipline)."""
    if "model" not in _model_cache:
        from sentence_transformers import SentenceTransformer

        _model_cache["model"] = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _model_cache["model"]


@dataclass(frozen=True)
class EmbeddingComputationCost:
    """Real, measured cost of one `pool_consensus_divergence_signals_semantic`
    call -- never estimated or assumed. Populated by the function itself via
    `time.perf_counter()` around the actual `model.encode()` call."""

    pool_size: int
    encode_latency_seconds: float
    model_name: str


def pool_consensus_divergence_signals_semantic(
    contents: Sequence[str],
    *,
    near_duplicate_threshold: float = NEAR_DUPLICATE_THRESHOLD_SEMANTIC,
    dampening_exponent: float = DEDUP_DAMPENING_EXPONENT,
) -> Tuple[Tuple[Dict[str, float], ...], EmbeddingComputationCost]:
    """The semantic (D2) counterpart of `signals.pool_consensus_divergence_
    signals`, built on the SAME `dedup_consensus` clustering/dampening core,
    differing only in how pairwise similarity is computed (real cosine
    similarity of `all-MiniLM-L6-v2` sentence embeddings, instead of Jaccard
    token overlap).

    Returns `(signals, cost)`: the same `{"consensus_divergence_score": v}`
    tuple shape `signals.py` returns, plus a real, measured
    `EmbeddingComputationCost` record -- callers that need the cost for
    reporting (Stage 6.9/6.12) get it without a second, separately-timed call.
    """
    import time

    model = _get_model()
    n = len(contents)
    if n == 0:
        return (), EmbeddingComputationCost(pool_size=0, encode_latency_seconds=0.0, model_name=EMBEDDING_MODEL_NAME)

    start = time.perf_counter()
    embeddings = model.encode(list(contents), normalize_embeddings=True)
    encode_latency = time.perf_counter() - start

    similarity_matrix = [
        [float(embeddings[i] @ embeddings[j]) for j in range(n)] for i in range(n)
    ]
    cluster_of = cluster_by_similarity_matrix(similarity_matrix, near_duplicate_threshold)
    divergences = dampened_divergence(similarity_matrix, cluster_of, dampening_exponent)

    results = []
    for divergence in divergences:
        signal = {"consensus_divergence_score": divergence}
        offending = set(signal.keys()) & FORBIDDEN_SIGNAL_KEYS
        if offending:  # unreachable given the fixed key name, kept for parity/defense-in-depth
            raise EvaluatorOnlyLeakageError(f"pool_consensus_divergence_signals_semantic leaked {offending!r}")
        results.append(signal)

    cost = EmbeddingComputationCost(
        pool_size=n, encode_latency_seconds=encode_latency, model_name=EMBEDDING_MODEL_NAME
    )
    return tuple(results), cost
