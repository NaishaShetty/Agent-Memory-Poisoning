"""Phase 11.3 -- validates `GatedLinearNetwork` against a small, constructed,
non-project toy sequence with a KNOWN right answer, before it is ever trusted
on real project data (Plan Section 11.3, mirroring Stage 6.8's own "validate
the regex against constructed true/false positives before real use"
discipline for `imperative_write_directive_signal()`).

The toy sequence is a real, disclosed CONCEPT-DRIFT stream: for the first
half of the stream the true label is a deterministic function of feature 0;
for the second half it is a deterministic function of feature 1 instead --
purely synthetic, and never confused with a real Phase 11 evaluation number.
A continual online learner is architecturally supposed to recover after the
drift; a model with no online update at all cannot. This is the known right
answer the toy sequence checks.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import numpy as np

from phase11.gln.model import GatedLinearNetwork

TOY_SEED = 7
TOY_LENGTH = 240
TOY_FEATURE_DIM = 3
TOY_DRIFT_POINT = 120
TOY_WINDOW = 20


@dataclass(frozen=True)
class ToyValidationResult:
    pre_drift_accuracy: float
    immediately_post_drift_accuracy: float
    recovered_post_drift_accuracy: float
    passed: bool


def _generate_toy_stream() -> Tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(TOY_SEED)
    features = rng.uniform(-1.0, 1.0, size=(TOY_LENGTH, TOY_FEATURE_DIM))
    labels = np.empty(TOY_LENGTH, dtype=float)
    labels[:TOY_DRIFT_POINT] = (features[:TOY_DRIFT_POINT, 0] > 0.0).astype(float)
    labels[TOY_DRIFT_POINT:] = (features[TOY_DRIFT_POINT:, 1] > 0.0).astype(float)
    return features, labels


def _accuracy(preds: np.ndarray, labels: np.ndarray) -> float:
    return float(np.mean((preds >= 0.5) == (labels >= 0.5)))


def run_toy_validation() -> ToyValidationResult:
    """Real, deterministic (fixed `TOY_SEED`) online run. Windows of exactly
    `TOY_WINDOW` real predictions are used for each of the three real,
    reported accuracy numbers below -- always stated with this same small,
    disclosed `n=20` per window, never as a bare percentage."""
    features, labels = _generate_toy_stream()
    # side_info = the same feature vector -- a real, minimal choice: the
    # context gate needs SOME real signal to condition on, and this toy
    # sequence's only real signal is its own feature vector.
    model = GatedLinearNetwork(input_dim=TOY_FEATURE_DIM, context_dim=TOY_FEATURE_DIM, seed=TOY_SEED)

    predictions = np.empty(TOY_LENGTH, dtype=float)
    for t in range(TOY_LENGTH):
        x = np.clip((features[t] + 1.0) / 2.0, 1e-3, 1 - 1e-3)  # map to (0, 1) "probabilities"
        pred = model.predict_and_update(x, features[t], target=labels[t])
        predictions[t] = pred

    pre_drift = _accuracy(
        predictions[TOY_DRIFT_POINT - TOY_WINDOW : TOY_DRIFT_POINT],
        labels[TOY_DRIFT_POINT - TOY_WINDOW : TOY_DRIFT_POINT],
    )
    immediately_post_drift = _accuracy(
        predictions[TOY_DRIFT_POINT : TOY_DRIFT_POINT + TOY_WINDOW],
        labels[TOY_DRIFT_POINT : TOY_DRIFT_POINT + TOY_WINDOW],
    )
    recovered_post_drift = _accuracy(predictions[-TOY_WINDOW:], labels[-TOY_WINDOW:])

    # The known right answer: pre-drift accuracy should be well above chance
    # (the model learned SOMETHING real), and the model should genuinely
    # recover after the drift (continual learning's whole point) even if it
    # dips right at the changepoint.
    passed = pre_drift >= 0.7 and recovered_post_drift >= 0.7

    return ToyValidationResult(
        pre_drift_accuracy=pre_drift,
        immediately_post_drift_accuracy=immediately_post_drift,
        recovered_post_drift_accuracy=recovered_post_drift,
        passed=passed,
    )


if __name__ == "__main__":
    result = run_toy_validation()
    print(result)
