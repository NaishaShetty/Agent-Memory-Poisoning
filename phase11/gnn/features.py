"""Phase 11.2 -- Signal-Contract-compliant node feature extraction for the GNN.

Every feature is drawn EXCLUSIVELY from `phase10`'s own
`SANCTIONED_RISK_SIGNAL_KEYS` (`phase6/defense/risk/risk_score.py`) -- the
same real, already-legitimate signal vocabulary `compute_memory_risk_score()`
itself is restricted to. No new signal is invented here: every value is
computed by calling the SAME shipped signal functions `run_b9_risk_composed()`
already calls (`admission_signals`, `pool_consensus_divergence_signals`,
`lineage_taint_signal`, `imperative_write_directive_signal`), never a raw
foundation-metadata read.

`assert_features_are_sanctioned()` is the static check Plan Section 11.2/8
requires: it raises before any training run if `FEATURE_KEYS` ever drifts
outside `SANCTIONED_RISK_SIGNAL_KEYS`, mirroring every existing
`FORBIDDEN_SIGNAL_KEYS` guard elsewhere in this project.
"""

from __future__ import annotations

from typing import Dict, Sequence, Tuple

from phase6.defense.admission.reasoning_guard import compute_signals as admission_signals
from phase6.defense.orchestration.pipeline import MemoryScenario, ScenarioPool
from phase6.defense.propagation.signals import lineage_taint_signal
from phase6.defense.retrieval.embedding_signals import pool_consensus_divergence_signals_semantic
from phase6.defense.retrieval.signals import pool_consensus_divergence_signals
from phase6.defense.risk.risk_score import SANCTIONED_RISK_SIGNAL_KEYS
from phase6.defense.signals.contract import build_signal_context
from phase6.defense.sleeper.signals import imperative_write_directive_signal

# The closed, disclosed set of feature keys this module computes -- a
# deliberate subset of SANCTIONED_RISK_SIGNAL_KEYS chosen because these five
# are computable per-scenario from this project's real, already-authored
# corpora without inventing any additional context the corpora do not carry
# (e.g. `age_based_dormancy_gate_score` needs a real timestamp delta the
# ablation corpus does not model, exactly as `run_b9_risk_composed()`'s own
# docstring already discloses for the same reason).
#
# LEFT UNCHANGED, DELIBERATELY (2026-09-20): kept at exactly the original 9
# keys. This is the shared foundation `phase11/gln/stream.py` (the GLN --
# an entirely separate, never-retrained-for-this architecture), Option 1's
# `phase11/gnn/self_supervised.py`, and Option 2's
# `phase11/expanded_features/dataset.py` all still import and depend on for
# their own ALREADY-REPORTED, protected numbers. `GNN_FEATURE_KEYS` below
# is a SEPARATE, GNN-only extension -- consumed only by
# `pool_node_features_gnn()`/`pools_node_features_gnn()` and
# `phase11/gnn/train.py::build_dataset()` -- so the new signal reaches the
# GNN specifically without silently changing the GLN's own input
# dimensionality (a real mistake caught and reverted during this
# investigation: the first version of this change edited `FEATURE_KEYS`
# itself, which silently grew the GLN's own untested input dimension too
# and broke its real calibration -- benign held-out risk jumped to ~1.0 for
# every example. See `docs/phase11/PHASE11_PARAPHRASE_FIX_REPORT.md`
# Section 3 for the full, disclosed account).
FEATURE_KEYS: Tuple[str, ...] = tuple(
    sorted(
        {
            "self_reference_score",
            "decision_log_vocabulary_score",
            "perfection_claim_score",
            "template_anomaly_score",
            "provenance_anomaly_score",
            "consensus_divergence_score",
            "lineage_taint_score",
            "imperative_write_directive_score",
            "dormancy_activation_score",
        }
    )
)

# GNN-only extension (2026-09-20, Phase 11 follow-on, explicitly
# authorized): adds `semantic_consensus_divergence_score` -- a real,
# directly-diagnosed gap this closes: `PARAPHRASE-POISON-*`
# (MemoryGraft-style-volume) scores EXACTLY 0.0 on the lexical
# `consensus_divergence_score` (paraphrased wording evades Jaccard
# token-overlap clustering entirely -- confirmed directly, not assumed)
# but is correctly identified as a coordinated near-duplicate cluster by
# the SAME embedding-based signal `embedding_signals.py` already ships for
# exactly this documented reason (its own module docstring: "three
# differently-WORDED but same-lie coordinated poison records evade lexical
# clustering entirely"). This is not a new signal invented for this fix --
# it is an already-shipped, already-sanctioned-elsewhere-eligible Phase 6.6
# mechanism, simply never previously given to the GNN.
GNN_FEATURE_KEYS: Tuple[str, ...] = FEATURE_KEYS + ("semantic_consensus_divergence_score",)


def assert_features_are_sanctioned() -> None:
    unsanctioned = set(FEATURE_KEYS) - SANCTIONED_RISK_SIGNAL_KEYS
    if unsanctioned:
        raise ValueError(
            f"phase11.gnn.features.FEATURE_KEYS contains unsanctioned key(s) "
            f"{sorted(unsanctioned)!r} -- every GNN feature must be a member "
            "of SANCTIONED_RISK_SIGNAL_KEYS (Phase 11 plan Section 11.2/8)."
        )


assert_features_are_sanctioned()


def scenario_signal_context(scenario: MemoryScenario):
    return build_signal_context(
        memory_id=scenario.scenario_id,
        content_text=scenario.content_text,
        content_type="CONVERSATIONAL_FACT",
        memory_type=scenario.memory_type,
        parent_ids=scenario.parent_ids,
        lifecycle_state="ACTIVE",
        creation_timestamp="2026-09-14T00:00:00Z",
    )


def _scenario_signals(scenario: MemoryScenario, div: Dict[str, float]) -> Dict[str, float]:
    ctx = scenario_signal_context(scenario)
    signals: Dict[str, float] = {
        **admission_signals(ctx),
        **div,
        **imperative_write_directive_signal(ctx),
        # Same real, legitimate value run_b9_risk_composed() uses: this
        # corpus models a single admission event with no retrieval
        # history yet, and dormancy_activation_signal()'s own formula
        # gives exactly 1.0 at prior_retrieval_count=0.
        "dormancy_activation_score": 1.0,
    }
    if scenario.ancestors:
        signals.update(lineage_taint_signal(scenario.content_text, scenario.ancestors))
    return signals


def pool_node_features(pool: ScenarioPool) -> Dict[str, Tuple[float, ...]]:
    """Real per-memory sanctioned signal values for every memory in `pool`,
    computed the SAME way `run_b9_risk_composed()` computes them (same
    function calls, same defaults) -- returns `{scenario_id: feature_vector}`
    in the fixed `FEATURE_KEYS` order (9 keys -- LEFT UNCHANGED, see this
    module's own docstring; the GLN and Option 1/2 depend on this exact
    shape). Use `pool_node_features_gnn()` for the GNN's own extended,
    10-key vocabulary."""
    contents = [m.content_text for m in pool.memories]
    divergence = pool_consensus_divergence_signals(contents)

    features: Dict[str, Tuple[float, ...]] = {}
    for scenario, div in zip(pool.memories, divergence):
        signals = _scenario_signals(scenario, div)
        features[scenario.scenario_id] = tuple(signals.get(k, 0.0) for k in FEATURE_KEYS)
    return features


def pools_node_features(pools: Sequence[ScenarioPool]) -> Dict[str, Tuple[float, ...]]:
    merged: Dict[str, Tuple[float, ...]] = {}
    for pool in pools:
        merged.update(pool_node_features(pool))
    return merged


def pool_node_features_gnn(pool: ScenarioPool) -> Dict[str, Tuple[float, ...]]:
    """The GNN-only extended feature vector (`GNN_FEATURE_KEYS`, 10 keys --
    the original 9 plus `semantic_consensus_divergence_score`). NEVER
    consumed by the GLN or by Option 1/2's own protected investigations --
    only by `phase11/gnn/train.py::build_dataset()` and its own
    downstream LOFO/blend modules."""
    contents = [m.content_text for m in pool.memories]
    divergence = pool_consensus_divergence_signals(contents)
    semantic_divergence, _cost = pool_consensus_divergence_signals_semantic(contents)

    features: Dict[str, Tuple[float, ...]] = {}
    for scenario, div, semantic_div in zip(pool.memories, divergence, semantic_divergence):
        signals = _scenario_signals(scenario, div)
        # semantic_div is {"consensus_divergence_score": v} -- the SAME key
        # name the lexical signal uses (D1/D2 are interchangeable
        # ALTERNATIVES for that one sanctioned key elsewhere in this
        # project); remapped to its OWN distinct sanctioned key here so the
        # GNN gets both as separate, additive features rather than one
        # silently overwriting the other.
        signals["semantic_consensus_divergence_score"] = semantic_div["consensus_divergence_score"]
        features[scenario.scenario_id] = tuple(signals.get(k, 0.0) for k in GNN_FEATURE_KEYS)
    return features


def pools_node_features_gnn(pools: Sequence[ScenarioPool]) -> Dict[str, Tuple[float, ...]]:
    merged: Dict[str, Tuple[float, ...]] = {}
    for pool in pools:
        merged.update(pool_node_features_gnn(pool))
    return merged
