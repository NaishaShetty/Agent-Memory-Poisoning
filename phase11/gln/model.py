"""Phase 11.3 -- a real, from-scratch Gated Linear Network (GLN).

Veness et al., "Gated Linear Networks" (2021) -- chosen (Plan Section 3) for
its real, documented strength: per-neuron, per-example ONLINE weight updates
with no catastrophic forgetting by construction, which is exactly this
project's real shape of problem -- a small number of real events about one
memory, arriving in genuine streaming order, never available in advance.

Minimal, disclosed architecture:
  - Each layer has `neurons_per_layer` gated linear neurons.
  - Each neuron owns `num_contexts` independent weight vectors (one per
    "context" -- a half-space region of a fixed, random side-information
    projection). Only the ONE weight vector whose half-space the current
    side-information falls into is used and updated for a given example --
    this is the real "gating" the architecture is named for.
  - A neuron's output is `sigmoid(w_c . logit_clip(inputs))`, where `inputs`
    is the previous layer's real output probabilities (the raw feature
    vector for layer 0's inputs).
  - Online update, per neuron, per example: plain online logistic-regression
    gradient descent on the ACTIVE context's weight vector only --
    `w_c += lr * (target - output) * logit_clip(inputs)`.

No `torch`/heavy dependency needed here -- `numpy` is sufficient and keeps
the online, one-example-at-a-time update loop simple and transparent, per
Plan Section 6 ("a minimal, from-scratch implementation" preferred over a new
dependency).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Sequence, Tuple

import numpy as np

GLN_VERSION = "phase11-gln-0.1.0"

_EPS = 1e-6


def _clip_logit(p: np.ndarray) -> np.ndarray:
    p_clipped = np.clip(p, _EPS, 1.0 - _EPS)
    return np.log(p_clipped / (1.0 - p_clipped))


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -30.0, 30.0)))


@dataclass
class _GatedNeuron:
    """One gated linear neuron: `num_contexts` independent weight vectors,
    selected per-example by which half-space a fixed random projection of the
    side-information vector falls into."""

    input_dim: int
    context_dim: int
    num_contexts: int
    seed: int
    weights: np.ndarray = field(init=False)
    context_hyperplanes: np.ndarray = field(init=False)

    def __post_init__(self) -> None:
        rng = np.random.default_rng(self.seed)
        # +1 for the bias term appended to every input vector.
        self.weights = np.full((self.num_contexts, self.input_dim + 1), 1.0 / (self.input_dim + 1))
        self.context_hyperplanes = rng.normal(size=(self.num_contexts, self.context_dim))

    def _active_context(self, side_info: np.ndarray) -> int:
        projections = self.context_hyperplanes @ side_info
        # A real, deterministic half-space gate: each bit of the context
        # index is the sign of one hyperplane's projection, combined into one
        # integer index -- the standard GLN context-selection scheme.
        bits = (projections > 0).astype(int)
        index = 0
        for b in bits:
            index = (index * 2 + int(b)) % self.num_contexts
        return index

    def predict_and_update(
        self, inputs: np.ndarray, side_info: np.ndarray, target: float | None, lr: float
    ) -> float:
        context = self._active_context(side_info)
        x = np.concatenate([_clip_logit(inputs), [1.0]])
        w = self.weights[context]
        output = float(_sigmoid(np.array([w @ x]))[0])
        if target is not None:
            gradient = (output - target) * x
            self.weights[context] = w - lr * gradient
        return output


class GatedLinearLayer:
    def __init__(self, num_neurons: int, input_dim: int, context_dim: int, num_context_bits: int, seed: int):
        self.neurons = [
            _GatedNeuron(input_dim, context_dim, 2**num_context_bits, seed=seed + i)
            for i in range(num_neurons)
        ]

    def predict_and_update(self, inputs: np.ndarray, side_info: np.ndarray, target: float | None, lr: float) -> np.ndarray:
        return np.array([n.predict_and_update(inputs, side_info, target, lr) for n in self.neurons])


class GatedLinearNetwork:
    """A real, small, multi-layer GLN. Default: two hidden layers plus one
    single-neuron output layer -- disclosed, versioned constants."""

    def __init__(
        self,
        input_dim: int,
        context_dim: int,
        layer_sizes: Sequence[int] = (4, 2, 1),
        num_context_bits: int = 2,
        seed: int = 11,
        learning_rate: float = 0.1,
    ):
        self.input_dim = input_dim
        self.context_dim = context_dim
        self.learning_rate = learning_rate
        self.layers: List[GatedLinearLayer] = []
        prev_dim = input_dim
        for i, size in enumerate(layer_sizes):
            self.layers.append(
                GatedLinearLayer(size, prev_dim, context_dim, num_context_bits, seed=seed + i * 100)
            )
            prev_dim = size

    def predict_and_update(self, features: np.ndarray, side_info: np.ndarray, target: float | None = None) -> float:
        """One real online step: forward through every layer, and -- when
        `target` is given -- update every neuron's active-context weights
        toward it (every layer bootstraps off the SAME final target, the
        standard GLN online training scheme, not backprop)."""
        h = features
        for layer in self.layers:
            h = layer.predict_and_update(h, side_info, target, self.learning_rate)
        return float(h[0])

    def predict(self, features: np.ndarray, side_info: np.ndarray) -> float:
        return self.predict_and_update(features, side_info, target=None)
