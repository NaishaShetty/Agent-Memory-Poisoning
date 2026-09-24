"""Phase 14 -- live, per-task defense application over real retrieved
candidate memories (2026-09-23, explicitly authorized).

WHY THIS EXISTS
--------------------------------------------------------------------------------
`docs/phase14/PHASE14_PLAN.md` Section 3 names the real prerequisite this
phase needs before any utility number is possible: every real defense
(Phases 6-12) has, to date, only ever been evaluated OFFLINE against static
`ScenarioPool` corpora (`phase6/evaluation/ablations/run_b0_b7.py` and
friends) -- no code path in this project's real agent runtime
(`phase3/evaluation/agent_runtime/runner.py::run_agent_task()`) ever calls a
defense function. This module closes that gap, additively: given a real
`DefenseConfiguration` name and the REAL candidate memories a real
foundation's `retrieve()` call returned for one real task, it applies the
SAME real, already-shipped decision mechanism B1 or B9 already use offline,
live, for the first time, and returns the real subset that would remain in
agent-visible context under that real configuration.

NO FROZEN FUNCTION IS MODIFIED
--------------------------------------------------------------------------------
`run_agent_task()`, `evaluate_admission()`, `compute_memory_risk_score()`,
`action_for_risk_estimate()` are all reused verbatim, unmodified. This module
is new, additive glue -- it does not touch `phase3/evaluation/agent_runtime/
runner.py` at all (Phase 14's own campaign runner, `phase14/campaign.py`,
calls this module BEFORE building the agent-visible context, not by editing
the frozen retrieval function itself).

WHICH TWO REAL CONFIGURATIONS, AND WHY
--------------------------------------------------------------------------------
Per the confirmed plan (Section 6.2): `CONFIG_B1_ADMISSION_ONLY` (the
lightest real defense this project ships -- `evaluate_admission()` alone,
exactly as `B1_ADMISSION_ONLY` in `phase6/defense/orchestration/pipeline.py`
already defines it) and `CONFIG_B9_RISK_COMPOSED` (the strongest -- the real
per-memory risk-composed decision `phase6/evaluation/ablations/
run_b0_b7.py::run_b9_risk_composed()` already computes offline, replicated
here as a live, per-task decision over the SAME real signal functions, not a
new mechanism). `CONFIG_B0_NO_DEFENSE` is also provided as the real,
trivial identity case (every candidate kept), used as the live-path
"undefended" control so Track A/B's baseline condition runs through the
exact same code path as the defended ones, differing only in which
`DefenseConfiguration` name is passed.

WHAT "EXCLUDED FROM CONTEXT" MEANS, AND WHY
--------------------------------------------------------------------------------
Mirrors `phase12/security_metrics.py::_HARD_MITIGATION_ACTIONS` verbatim: a
real candidate is excluded from agent-visible context iff its real decided
action is `QUARANTINE` or `BLOCK` -- `ALLOW`/`ALLOW_WITH_RESTRICTION` keep
the memory in context (this project's own already-established convention:
those actions "annotate rather than exclude"). No new interpretation of the
action vocabulary is introduced here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Sequence, Tuple

from phase6.defense.admission.reasoning_guard import compute_signals as admission_signals
from phase6.defense.admission.reasoning_guard import evaluate_admission
from phase6.defense.policy.states import ALLOW, UNASSESSED
from phase6.defense.retrieval.embedding_signals import pool_consensus_divergence_signals_semantic
from phase6.defense.retrieval.signals import pool_consensus_divergence_signals
from phase6.defense.risk.risk_action import action_for_risk_estimate
from phase6.defense.risk.risk_score import GROUPED_GATED_ADMISSION_CORROBORATED, compute_memory_risk_score
from phase6.defense.signals.contract import build_signal_context
from phase6.defense.orchestration.pipeline import (
    B2_RETRIEVAL_ONLY,
    B3_PROPAGATION_ONLY,
    B4_ADMISSION_RETRIEVAL,
    B5_RETRIEVAL_PROPAGATION,
    B6_ADMISSION_PROPAGATION,
    B7_ALL_THREE,
    B8_ALL_FOUR,
    DefenseConfiguration,
    MemoryScenario,
    ScenarioPool,
    evaluate_pool,
)
from phase6.defense.sleeper.signals import imperative_write_directive_signal
from phase8.detection.activation_shape_signal import activation_shape_signal

CONFIG_B0_NO_DEFENSE = "B0"
CONFIG_B1_ADMISSION_ONLY = "B1"
CONFIG_B2_RETRIEVAL_ONLY = "B2"
CONFIG_B3_PROPAGATION_ONLY = "B3"
CONFIG_B4_ADMISSION_RETRIEVAL = "B4"
CONFIG_B5_RETRIEVAL_PROPAGATION = "B5"
CONFIG_B6_ADMISSION_PROPAGATION = "B6"
CONFIG_B7_ALL_THREE = "B7"
CONFIG_B8_ALL_FOUR = "B8"
CONFIG_B9_RISK_COMPOSED = "B9"
CONFIG_B10_LEARNED_HYBRID = "B10"
REAL_CONFIGS: Tuple[str, ...] = (
    CONFIG_B0_NO_DEFENSE, CONFIG_B1_ADMISSION_ONLY, CONFIG_B2_RETRIEVAL_ONLY, CONFIG_B3_PROPAGATION_ONLY,
    CONFIG_B4_ADMISSION_RETRIEVAL, CONFIG_B5_RETRIEVAL_PROPAGATION, CONFIG_B6_ADMISSION_PROPAGATION,
    CONFIG_B7_ALL_THREE, CONFIG_B8_ALL_FOUR, CONFIG_B9_RISK_COMPOSED, CONFIG_B10_LEARNED_HYBRID,
)

# 2026-09-23 (Phase 15 follow-on, explicitly authorized): B2-B7 dispatch
# directly to `pipeline.py`'s own real, reusable `evaluate_pool()` batch
# function -- NOT reimplemented here. This reuses the SAME real
# `evaluate_admission()`/`evaluate_retrieval_defense()`/`evaluate_propagation_
# containment()`/`combined_action()` calls the offline B0-B7 ablation harness
# (`run_b0_b7.py`) already uses, verified by direct source inspection rather
# than duplicated by hand (the exact risk B1's own bespoke `_b1_action()` --
# built before this was known to be reusable -- was written to avoid; B1 is
# kept as-is since it already agrees with `evaluate_pool()`'s own B1 output
# by construction, see `test_defended_retrieval_b0_to_b7.py`).
_PIPELINE_CONFIGS: Dict[str, DefenseConfiguration] = {
    CONFIG_B2_RETRIEVAL_ONLY: B2_RETRIEVAL_ONLY,
    CONFIG_B3_PROPAGATION_ONLY: B3_PROPAGATION_ONLY,
    CONFIG_B4_ADMISSION_RETRIEVAL: B4_ADMISSION_RETRIEVAL,
    CONFIG_B5_RETRIEVAL_PROPAGATION: B5_RETRIEVAL_PROPAGATION,
    CONFIG_B6_ADMISSION_PROPAGATION: B6_ADMISSION_PROPAGATION,
    CONFIG_B7_ALL_THREE: B7_ALL_THREE,
    # B8 adds Sleeper (`evaluate_sleeper_admission()`, which already includes
    # the real `activation_shape_score` fix -- see `sleeper_guard.py`) and
    # sibling-propagation on top of B7. Sibling-propagation
    # (`semantic_sibling_propagation_actions()`) is a real, second PASS over
    # the whole pool's first-pass results (`evaluate_pool()`'s own
    # `sibling_propagation_enabled` branch) -- fully supported by calling
    # `evaluate_pool()` directly, exactly like every other B2-B7 config.
    CONFIG_B8_ALL_FOUR: B8_ALL_FOUR,
}

# Mirrors phase12/security_metrics.py::_HARD_MITIGATION_ACTIONS verbatim.
HARD_MITIGATION_ACTIONS: Tuple[str, ...] = ("QUARANTINE", "BLOCK")

TS = "2026-09-23T00:00:00Z"


@dataclass(frozen=True)
class DefenseDecision:
    memory_id: str
    action: str
    excluded: bool


def _signal_context(memory_id: str, content_text: str):
    return build_signal_context(
        memory_id=memory_id, content_text=content_text, content_type="CONVERSATIONAL_FACT",
        memory_type="foundation", parent_ids=(), lifecycle_state="ACTIVE", creation_timestamp=TS,
    )


def _b1_action(memory_id: str, content_text: str) -> str:
    ctx = _signal_context(memory_id, content_text)
    decision = evaluate_admission(
        ctx, current_security_state=UNASSESSED, run_id="phase14-defended-retrieval",
        episode_id="e1", timestamp=TS, evidence_refs=(f"EVT-{memory_id}",),
    )
    return decision.action


def _b9_actions(items: Sequence[Tuple[str, str]]) -> Dict[str, str]:
    """Real, per-task replication of `run_b0_b7.py::run_b9_risk_composed()`'s
    own per-memory decision -- SAME real signal functions,
    `action_for_risk_estimate()` decision surface. The retrieval-consensus
    signals are pool-level (computed once over every real candidate memory
    in THIS task's own real retrieved set, exactly as the offline version
    computes them once per `ScenarioPool`).

    UPDATE (2026-09-23, Phase 14 follow-on, explicitly authorized): uses
    `GROUPED_GATED_ADMISSION_CORROBORATED`, not the offline `GROUPED_GATED`
    `run_b9_risk_composed()` itself uses. Real, measured problem: under
    `GROUPED_GATED`, two real, independently-validated admission signals
    corroborating within the SAME memory (e.g. DSRM's own
    `interrogative_restatement_score` + `synthetic_repetition_padding_score`)
    only ever contributed 0.10 to the total real risk score (2 signals x 0.2
    weight x 0.25 group weight), nowhere near the 0.6 `HIGH`-band threshold
    `QUARANTINE` requires. `GROUPED_GATED_ADMISSION_CORROBORATED` is a
    SEPARATE, additive rule (`risk_score.py`'s own module note has the full
    real justification and the real cross-phase regression that made this a
    separate rule rather than a change to `GROUPED_GATED` itself): it
    guarantees a real, disclosed floor once 2+ distinct real admission
    signals fire together, validated against disjoint dev data and all 502
    real benign records with zero new false positives, and verified to leave
    `GROUPED_GATED` (and therefore Phase 11's z-score-normalized detectors
    and the frozen `corpus.py` 75-scenario corpus's real B0-B9 numbers)
    byte-identical, since this live path is the ONLY caller of the new rule.

    `lineage_taint_score` is omitted: none of Phase 14's real task memories
    carry real ancestors (they are foundation-type LoCoMo/poison-scenario
    content, not derived memories), and `lineage_taint_signal()` itself
    requires real ancestors to be meaningful -- omitting it here is the same
    real choice `run_b9_risk_composed()` itself makes when `m.ancestors` is
    empty (it conditions on `if m.ancestors:` before calling it at all).
    `dormancy_activation_score=1.0` mirrors the same real, disclosed
    convention `run_b9_risk_composed()` uses: this real candidate is being
    retrieved for the first time in this task, exactly what
    `dormancy_activation_signal()`'s own formula gives at
    `prior_retrieval_count=0`.
    """
    contents = [content for _, content in items]
    divergence = pool_consensus_divergence_signals(contents)
    semantic_divergence, _cost = pool_consensus_divergence_signals_semantic(contents)

    actions: Dict[str, str] = {}
    for (memory_id, content_text), div, semantic_div in zip(items, divergence, semantic_divergence):
        ctx = _signal_context(memory_id, content_text)
        signals = {
            **admission_signals(ctx),
            **div,
            "semantic_consensus_divergence_score": semantic_div["consensus_divergence_score"],
            **imperative_write_directive_signal(ctx),
            **activation_shape_signal(ctx),
            "dormancy_activation_score": 1.0,
        }
        estimate = compute_memory_risk_score(memory_id, signals, rule=GROUPED_GATED_ADMISSION_CORROBORATED)
        actions[memory_id] = action_for_risk_estimate(estimate, current_security_state=UNASSESSED)
    return actions


def _pipeline_actions(items: Sequence[Tuple[str, str]], config: DefenseConfiguration) -> Dict[str, str]:
    """Real, per-task replication of `pipeline.py::evaluate_pool()` for B2-B7,
    called directly rather than reimplemented. `ancestors=()` (the
    `MemoryScenario` default) for every real item: none of Phase 14's real
    task memories (LoCoMo/LongMemEval QA pairs, poison scenarios) carry real
    ancestors, the SAME real, disclosed fact `_b9_actions()`'s own docstring
    already states for `lineage_taint_score`. This means, confirmed directly
    (`test_defended_retrieval_b0_to_b7.py`), `config.propagation_enabled`
    NEVER fires live in this pilot -- `evaluate_propagation_containment()` is
    only called when `m.ancestors` is truthy (`pipeline.py` line 320), so B3
    (propagation-only) always degenerates to B0 and B5/B6/B7 always
    degenerate to their propagation-free counterparts (B2/B1/B4
    respectively). This is a real, structural fact about Phase 14's live
    task memories, not a bug in this glue code -- see `docs/phase15/
    PHASE15_CROSS_CUTTING_REPORT.md` for the disclosed consequence."""
    pool = ScenarioPool(
        pool_id="phase14-live-pool",
        memories=tuple(MemoryScenario(scenario_id=mid, content_text=text) for mid, text in items),
    )
    outcomes = evaluate_pool(pool, config, run_id="phase14-defended-retrieval")
    return {o.scenario_id: o.combined_action for o in outcomes}


def apply_defense(
    config_name: str, items: Sequence[Tuple[str, str]],
) -> Tuple[Tuple[Tuple[str, str], ...], Tuple[DefenseDecision, ...]]:
    """`items`: real `(memory_id, content_text)` pairs, in real retrieval
    order, for ONE real task. Returns `(kept_items, decisions)` -- `kept_items`
    is the real subset that would remain in agent-visible context under
    `config_name`; `decisions` names every real candidate's real action,
    including the excluded ones (never silently dropped from the return
    value -- Phase 14's own cost/utility accounting needs to see what was
    excluded, not just what survived).
    """
    if config_name == CONFIG_B0_NO_DEFENSE:
        decisions = tuple(DefenseDecision(memory_id, ALLOW, False) for memory_id, _ in items)
    elif config_name == CONFIG_B1_ADMISSION_ONLY:
        actions = {memory_id: _b1_action(memory_id, content_text) for memory_id, content_text in items}
        decisions = tuple(
            DefenseDecision(memory_id, actions[memory_id], actions[memory_id] in HARD_MITIGATION_ACTIONS)
            for memory_id, _ in items
        )
    elif config_name == CONFIG_B9_RISK_COMPOSED:
        actions = _b9_actions(items)
        decisions = tuple(
            DefenseDecision(memory_id, actions[memory_id], actions[memory_id] in HARD_MITIGATION_ACTIONS)
            for memory_id, _ in items
        )
    elif config_name == CONFIG_B10_LEARNED_HYBRID:
        # Lazy import: phase15 builds on phase14, not the reverse at import time.
        from phase15.b10_live import b10_actions

        actions = b10_actions(items)
        decisions = tuple(
            DefenseDecision(memory_id, actions[memory_id], actions[memory_id] in HARD_MITIGATION_ACTIONS)
            for memory_id, _ in items
        )
    elif config_name in _PIPELINE_CONFIGS:
        actions = _pipeline_actions(items, _PIPELINE_CONFIGS[config_name])
        decisions = tuple(
            DefenseDecision(memory_id, actions[memory_id], actions[memory_id] in HARD_MITIGATION_ACTIONS)
            for memory_id, _ in items
        )
    else:
        raise ValueError(f"Unknown config_name {config_name!r}; must be one of {REAL_CONFIGS!r}")

    excluded_ids = {d.memory_id for d in decisions if d.excluded}
    kept = tuple((memory_id, content_text) for memory_id, content_text in items if memory_id not in excluded_ids)
    return kept, decisions


__all__ = [
    "CONFIG_B0_NO_DEFENSE",
    "CONFIG_B1_ADMISSION_ONLY",
    "CONFIG_B2_RETRIEVAL_ONLY",
    "CONFIG_B3_PROPAGATION_ONLY",
    "CONFIG_B4_ADMISSION_RETRIEVAL",
    "CONFIG_B5_RETRIEVAL_PROPAGATION",
    "CONFIG_B6_ADMISSION_PROPAGATION",
    "CONFIG_B7_ALL_THREE",
    "CONFIG_B8_ALL_FOUR",
    "CONFIG_B9_RISK_COMPOSED",
    "CONFIG_B10_LEARNED_HYBRID",
    "REAL_CONFIGS",
    "HARD_MITIGATION_ACTIONS",
    "DefenseDecision",
    "apply_defense",
]
