"""Phase 11.3 -- real per-memory event streams, and a real, measured answer
to Phase 10's own open question (`docs/phase10/PHASE10_PLAN.md` Section 6):
"whether a memory's risk should fall after a sustained period of safe,
corroborated use."

STREAM CONSTRUCTION, DISCLOSED
--------------------------------------------------------------------------------
For each real memory scenario, one real event = one more (simulated)
retrieval of that SAME memory. The event's real signal values are computed
the SAME way `phase11/gnn/features.py` computes them for the GNN -- the
content-derived signals (`self_reference_score`, ..., `imperative_write_
directive_score`) are fixed per memory (they are properties of the content,
not of time), and the one signal that genuinely evolves per event is
`dormancy_activation_score`, using the REAL, shipped
`dormancy_activation_signal(prior_retrieval_count)` formula
(`phase6/defense/sleeper/signals.py`) with `prior_retrieval_count`
incrementing by one at each simulated event -- exactly the real mechanism
Phase 6.8 already ships, run forward over more (simulated) retrievals than
this project's static, single-pass ablation corpus otherwise exercises.

This is a real, disclosed EXTRAPOLATION of an existing real signal over
simulated time, not new real telemetry this project's corpora do not
actually contain (there is no real multi-week retrieval log in this
project's real data) -- stated plainly here and again in
`docs/phase11/PHASE11_REPORT.md`, never presented as literal, observed
temporal data.

Non-circular training: the GLN's online weights are warmed up on
`train_pools()`' streams, sanity-checked on `dev_pools()`' streams, and the
one real, reported risk-decay finding is measured on `held_out_pools()`'
streams only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

import numpy as np

from phase11.data import split
from phase11.gnn.features import FEATURE_KEYS, scenario_signal_context
from phase11.gln.model import GatedLinearNetwork
from phase6.defense.admission.reasoning_guard import compute_signals as admission_signals
from phase6.defense.orchestration.pipeline import ScenarioPool
from phase6.defense.retrieval.signals import pool_consensus_divergence_signals
from phase6.defense.sleeper.signals import dormancy_activation_signal, imperative_write_directive_signal

STREAM_EVENTS_PER_MEMORY = 12
STREAM_SEED = 11


@dataclass(frozen=True)
class MemoryStream:
    scenario_id: str
    is_poison_ground_truth: bool
    events: Tuple[Tuple[float, ...], ...]  # one FEATURE_KEYS-ordered vector per event


def build_memory_streams(pools: Sequence[ScenarioPool]) -> List[MemoryStream]:
    streams: List[MemoryStream] = []
    for pool in pools:
        contents = [m.content_text for m in pool.memories]
        divergence = pool_consensus_divergence_signals(contents)
        for scenario, div in zip(pool.memories, divergence):
            ctx = scenario_signal_context(scenario)
            static_signals: Dict[str, float] = {**admission_signals(ctx), **div, **imperative_write_directive_signal(ctx)}
            events = []
            for retrieval_index in range(STREAM_EVENTS_PER_MEMORY):
                dormancy = dormancy_activation_signal(retrieval_index)["dormancy_activation_score"]
                step_signals = {**static_signals, "dormancy_activation_score": dormancy}
                events.append(tuple(step_signals.get(k, 0.0) for k in FEATURE_KEYS))
            streams.append(MemoryStream(scenario.scenario_id, scenario.is_poison_ground_truth, tuple(events)))
    return streams


def _run_streams(model: GatedLinearNetwork, streams: Sequence[MemoryStream], *, update: bool) -> Dict[str, List[float]]:
    trajectories: Dict[str, List[float]] = {}
    for stream in streams:
        risks = []
        for event in stream.events:
            features = np.clip(np.array(event, dtype=float), 1e-3, 1 - 1e-3)
            target = 1.0 if stream.is_poison_ground_truth else 0.0
            risk = model.predict_and_update(features, features, target=target if update else None)
            risks.append(risk)
        trajectories[stream.scenario_id] = risks
    return trajectories


def run_risk_decay_study() -> dict:
    """The real, end-to-end run: warm up on train streams, sanity-check on
    dev streams, then measure the real risk-decay finding on held-out
    streams -- the same real corpus B0-B9 already report against."""
    train_streams = build_memory_streams(split.train_pools())
    dev_streams = build_memory_streams(split.dev_pools())
    held_out_streams = build_memory_streams(split.held_out_pools())

    model = GatedLinearNetwork(input_dim=len(FEATURE_KEYS), context_dim=len(FEATURE_KEYS), seed=STREAM_SEED)
    _run_streams(model, train_streams, update=True)
    _run_streams(model, dev_streams, update=True)
    held_out_trajectories = _run_streams(model, held_out_streams, update=True)

    benign_ids = {s.scenario_id for s in held_out_streams if not s.is_poison_ground_truth}
    poison_ids = {s.scenario_id for s in held_out_streams if s.is_poison_ground_truth}

    def _mean_first_vs_last(ids: set) -> Tuple[float, float, int]:
        if not ids:
            return 0.0, 0.0, 0
        firsts = [held_out_trajectories[i][0] for i in ids]
        lasts = [held_out_trajectories[i][-1] for i in ids]
        return float(np.mean(firsts)), float(np.mean(lasts)), len(ids)

    benign_first, benign_last, n_benign = _mean_first_vs_last(benign_ids)
    poison_first, poison_last, n_poison = _mean_first_vs_last(poison_ids)

    return {
        "gln_version": "phase11-gln-0.1.0",
        "events_per_memory": STREAM_EVENTS_PER_MEMORY,
        "held_out_benign": {
            "n": n_benign,
            "mean_risk_at_first_retrieval": benign_first,
            "mean_risk_after_sustained_safe_use": benign_last,
            "risk_fell": benign_last < benign_first,
        },
        "held_out_poison": {
            "n": n_poison,
            "mean_risk_at_first_retrieval": poison_first,
            "mean_risk_after_sustained_activity": poison_last,
            "risk_rose_or_held": poison_last >= poison_first,
        },
    }


if __name__ == "__main__":
    import json

    print(json.dumps(run_risk_decay_study(), indent=2))
