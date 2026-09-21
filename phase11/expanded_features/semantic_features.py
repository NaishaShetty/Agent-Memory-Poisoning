"""Phase 11.x Option 2 -- reduced-dimensionality semantic features.

Reuses the ALREADY-PINNED `sentence-transformers/all-MiniLM-L6-v2` model via
`phase3/evaluation/foundations/similarity.py::_load_model()`, imported and
called exactly as that module already exposes it -- no new model, no
modification to that file or to the existing Phase 6.6 semantic-divergence
implementation (`phase6/defense/retrieval/embedding_signals.py`), and no
existing embedding usage is replaced.

DIMENSIONALITY REDUCTION -- PCA, FIT ON TRAINING DATA ONLY
--------------------------------------------------------------------------------
Per the governing instructions (Section 8): raw 384-dim embeddings are never
used directly in a covariance-based estimator at this project's real n. A
plain, from-scratch PCA (via `numpy.linalg.svd`, no new dependency) is fit
ONCE on the real TRAINING embeddings only (never dev, never held-out) and
reused, frozen, for every subsequent transform. The number of retained
components is chosen by a pre-registered rule -- smallest `k` such that
cumulative explained variance on the TRAINING set reaches 90%, capped at 20
-- decided before looking at any dev or held-out separation result, so the
dimensionality choice itself cannot be an outcome-chasing decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence, Tuple

import numpy as np

from phase3.evaluation.foundations.similarity import _load_model

MAX_PCA_DIMS = 20
TARGET_EXPLAINED_VARIANCE = 0.90


def embed_texts(texts: Sequence[str]) -> np.ndarray:
    """Real MiniLM embeddings via the existing, unmodified, pinned model
    loader -- no new model introduced."""
    model = _load_model()
    return np.asarray(model.encode(list(texts), normalize_embeddings=True, show_progress_bar=False))


@dataclass(frozen=True)
class FittedPCA:
    mean: np.ndarray
    components: np.ndarray  # shape (k, 384)
    explained_variance_ratio: Tuple[float, ...]
    n_components: int
    n_training_examples: int


def fit_pca(train_embeddings: np.ndarray) -> FittedPCA:
    """Fit PCA on TRAINING embeddings only, via SVD (no sklearn dependency
    introduced). `k` is chosen by the pre-registered 90%-cumulative-variance
    rule (capped at `MAX_PCA_DIMS`), decided before any dev/held-out
    evaluation is run."""
    mean = train_embeddings.mean(axis=0)
    centered = train_embeddings - mean
    # full_matrices=False: economy SVD, sufficient since n_training << 384
    _, singular_values, vt = np.linalg.svd(centered, full_matrices=False)
    variance = singular_values ** 2
    total_variance = variance.sum()
    explained_ratio = variance / total_variance if total_variance > 0 else variance

    cumulative = np.cumsum(explained_ratio)
    k_for_target = int(np.searchsorted(cumulative, TARGET_EXPLAINED_VARIANCE) + 1)
    k = min(k_for_target, MAX_PCA_DIMS, vt.shape[0])

    return FittedPCA(
        mean=mean,
        components=vt[:k],
        explained_variance_ratio=tuple(explained_ratio[:k].tolist()),
        n_components=k,
        n_training_examples=train_embeddings.shape[0],
    )


def apply_pca(embeddings: np.ndarray, fitted: FittedPCA) -> np.ndarray:
    """Transform ANY embeddings (train, dev, or held-out) using a PCA
    already fit on training data only -- this function never refits."""
    centered = embeddings - fitted.mean
    return centered @ fitted.components.T
