"""Phase 6.9 -- Defense Composition & Ablation Framework: the orchestration
layer that composes Stages 6.5-6.8's independently-built components into
named, ablatable configurations (B0-B7 plus a standalone Sleeper condition,
per the Stage 6.9 brief).

WHAT THIS MODULE IS, AND IS NOT
--------------------------------------------------------------------------------
This is a MEASUREMENT harness, not a live-pipeline integration. It composes
the real decision functions already built (`reasoning_guard.evaluate_admission`,
`consensus_guard.evaluate_retrieval_defense`, `containment_guard.evaluate_
propagation_containment`, `sleeper_guard.evaluate_sleeper_admission`) over a
synthetic, hand-constructed scenario corpus, and reports a per-component and
combined outcome for each scenario. It does NOT write to a real
`GovernanceLedger` with real sequential state transitions (Stage 6.10's real
integration job); it computes a `combined_action` via a SEVERITY ranking across
whichever components are enabled, purely for ablation reporting. This
simplification is disclosed, not hidden -- see `combined_action()`'s docstring.

EVALUATOR-ONLY GROUND TRUTH IS USED ONLY FOR METRICS, NEVER FOR DECISIONS
--------------------------------------------------------------------------------
`MemoryScenario.is_poison_ground_truth` and `.attack_family_ground_truth` are
read ONLY by `compute_metrics()`, AFTER every defense decision has already been
made from the scenario's legitimate fields alone. No decision function in this
module or any it calls ever receives these two fields -- verified directly by
`test_ablation_framework.py`'s own leakage test, not merely asserted here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Sequence, Tuple

from phase6.defense.admission.reasoning_guard import evaluate_admission
from phase6.defense.policy.states import (
    ALLOW,
    ALLOW_WITH_RESTRICTION,
    BLOCKED,
    DOWNRANK,
    IllegalTransitionError,
    QUARANTINE,
    QUARANTINED,
    REQUIRE_VALIDATION,
    UNASSESSED,
)
from phase6.defense.propagation.containment_guard import evaluate_propagation_containment
from phase6.defense.propagation.signals import AncestorRecord
from phase6.defense.retrieval.consensus_guard import RetrievalCandidate, evaluate_retrieval_defense, semantic_divergence_fn
from phase6.defense.retrieval.signals import pool_consensus_divergence_signals
from phase6.defense.signals.contract import build_signal_context
from phase6.defense.sleeper.sleeper_guard import evaluate_sleeper_admission

# Severity ranking for combining multiple components' independent votes into
# one reported outcome (module docstring: measurement-only simplification --
# NOT the real MGP state machine, which is sequential and stateful).
_ACTION_SEVERITY = {
    ALLOW: 0,
    DOWNRANK: 1,
    ALLOW_WITH_RESTRICTION: 2,
    REQUIRE_VALIDATION: 3,
    QUARANTINE: 4,
    "BLOCK": 5,
}

# P2 fix (2026-09-14): the audit finding this closes -- evaluate_pool() (the
# real, existing batch entry point) called evaluate_propagation_containment()
# per-memory with no try/except, so the documented, intentional
# IllegalTransitionError (raised when a currently-QUARANTINED descendant's
# freshly-computed taint has genuinely dropped -- containment_guard.py's own
# docstring: "this guard is not the pathway for resolving an existing
# quarantine... should route through a review/RELEASE mechanism, not this
# function") would crash the ENTIRE pool evaluation, losing every other
# memory's outcome too, not just the one case needing review. The guard's own
# raise behavior is correct and unchanged for a direct, single caller; this
# is the batch-wiring-side catch the guard's own docstring already
# anticipated as the caller's responsibility. Not a real action (never fed
# into combined_action()'s severity ranking, which has no slot for "refer to
# a human process") -- surfaced as its own distinct, visible marker on the
# per-memory record instead.
REFER_TO_RELEASE_PROCESS = "REFER_TO_RELEASE_PROCESS"


def combined_action(actions: Sequence[Optional[str]]) -> str:
    """The most severe action among the given component votes (None entries,
    meaning "this component was not enabled," are ignored). Used ONLY for
    ablation reporting -- see module docstring."""
    present = [a for a in actions if a is not None]
    if not present:
        return ALLOW
    return max(present, key=lambda a: _ACTION_SEVERITY[a])


@dataclass(frozen=True)
class MemoryScenario:
    """One synthetic memory in the Stage 6.9 ablation corpus.

    `is_poison_ground_truth` and `attack_family_ground_truth` are EVALUATOR-
    ONLY -- read only by `compute_metrics()`, never passed to any defense
    decision function.

    Resource-reconciliation fix (2026-09-15): `current_security_state`
    defaults to `UNASSESSED`, not `TRUSTED`. A B0-B7 corpus scenario
    represents a memory being evaluated by the admission guard for the
    FIRST time -- `UNASSESSED` is the state `states.py`'s own transition
    table defines for exactly that case ("any first assessment is legal,"
    including straight to BLOCKED). The prior `TRUSTED` default was
    semantically wrong for this (it means "already admitted and currently
    trusted," not "not yet assessed") and was silently tolerated only
    because, before the D1 admission-guard fix, `evaluate_admission` never
    checked `current_security_state` at all. Once that fix correctly started
    enforcing the transition table, this wrong default surfaced as a real
    crash (`run_b0_b7.py`'s own `IllegalTransitionError` on `POOL-FARMA`,
    since `states.py` correctly forbids TRUSTED -> BLOCKED in one step) --
    see `docs/phase6/DEFENSE_COMPOSITION_AND_ABLATION.md` for the full
    reconciliation. `TRUSTED` remains available as an explicit override for
    scenarios that specifically need to represent an already-trusted
    memory under RE-assessment (see `test_ablation_framework.py`'s own
    TRUSTED-re-assessment regression tests, which pass it explicitly, not
    via this default)."""

    scenario_id: str
    content_text: str
    memory_type: str = "foundation"
    parent_ids: Tuple[str, ...] = ()
    ancestors: Tuple[AncestorRecord, ...] = ()
    # Retrieval-time context (only meaningful when this scenario appears in a
    # ScenarioPool and retrieval is enabled):
    prior_retrieval_count: int = 0
    current_security_state: str = UNASSESSED
    # Evaluator-only ground truth (metrics only -- see module docstring):
    is_poison_ground_truth: bool = False
    attack_family_ground_truth: Optional[str] = None


@dataclass(frozen=True)
class ScenarioPool:
    """A group of memories co-retrieved together for one query -- the unit
    the retrieval-consensus component (D1/D2) operates over."""

    pool_id: str
    memories: Tuple[MemoryScenario, ...]


@dataclass(frozen=True)
class DefenseConfiguration:
    """One named, ablatable configuration (B0-B7, or a standalone Sleeper
    condition).

    `retrieval_divergence_fn_override`: optional escape hatch (Stage 6.9) to
    substitute an experimental divergence function (e.g. the min-cluster-size
    gate in `phase6/evaluation/ablations/calibration.py`) in place of the
    metric-based lexical/semantic selection -- used to compare the shipped
    Stage 6.6 mechanism against a candidate fix without touching any shipped
    default. `None` (the default) preserves the original `retrieval_metric`
    based selection exactly.
    """

    name: str
    admission_enabled: bool = False
    retrieval_enabled: bool = False
    retrieval_metric: str = "lexical"  # "lexical" | "semantic"
    retrieval_divergence_fn_override: Optional[object] = None
    propagation_enabled: bool = False
    sleeper_enabled: bool = False


# The canonical B0-B7 matrix, exactly as the Stage 6.9 brief specifies.
B0_NO_DEFENSE = DefenseConfiguration("B0")
B1_ADMISSION_ONLY = DefenseConfiguration("B1", admission_enabled=True)
B2_RETRIEVAL_ONLY = DefenseConfiguration("B2", retrieval_enabled=True)
B3_PROPAGATION_ONLY = DefenseConfiguration("B3", propagation_enabled=True)
B4_ADMISSION_RETRIEVAL = DefenseConfiguration("B4", admission_enabled=True, retrieval_enabled=True)
B5_RETRIEVAL_PROPAGATION = DefenseConfiguration("B5", retrieval_enabled=True, propagation_enabled=True)
B6_ADMISSION_PROPAGATION = DefenseConfiguration("B6", admission_enabled=True, propagation_enabled=True)
B7_ALL_THREE = DefenseConfiguration(
    "B7", admission_enabled=True, retrieval_enabled=True, propagation_enabled=True
)
SLEEPER_ONLY = DefenseConfiguration("SLEEPER", sleeper_enabled=True)

# B8 (2026-09-17): the brief's own B0-B7 matrix (Stage 6.9) evaluated Sleeper
# ONLY as its own standalone condition (`SLEEPER_ONLY` above), never combined
# with B7's admission+retrieval+propagation stack -- not because combining
# them was expected to fail, simply because it was never tried. It was tried
# post-shipping: real, measured result on the same corpus B0-B7 uses,
# `phase6/evaluation/ablations/run_b0_b7.py`'s own driver, no new mechanism
# invented -- poison detection rises from B7's 47.1% to 52.9% (Sleeper-family
# content: 0% under B7 alone -> 40%, matching SLEEPER_ONLY's own real number
# exactly) at the SAME 7.3% false-positive rate as B7 (Sleeper's own
# false-positive contribution was already independently confirmed at 0% on
# real LoCoMo data, `docs/phase6/SLEEPER_DEFENSE.md`). No detection is
# sacrificed anywhere combining these four layers never previously tested
# together.
B8_ALL_FOUR = DefenseConfiguration(
    "B8", admission_enabled=True, retrieval_enabled=True, propagation_enabled=True, sleeper_enabled=True
)

B0_TO_B7: Tuple[DefenseConfiguration, ...] = (
    B0_NO_DEFENSE,
    B1_ADMISSION_ONLY,
    B2_RETRIEVAL_ONLY,
    B3_PROPAGATION_ONLY,
    B4_ADMISSION_RETRIEVAL,
    B5_RETRIEVAL_PROPAGATION,
    B6_ADMISSION_PROPAGATION,
    B7_ALL_THREE,
)


@dataclass(frozen=True)
class MemoryOutcome:
    scenario_id: str
    admission_action: Optional[str]
    retrieval_action: Optional[str]
    propagation_action: Optional[str]
    sleeper_action: Optional[str]
    combined_action: str
    # Ground truth carried through for metrics ONLY -- see module docstring.
    is_poison_ground_truth: bool
    attack_family_ground_truth: Optional[str]


def _to_signal_context(scenario: MemoryScenario):
    return build_signal_context(
        memory_id=scenario.scenario_id,
        content_text=scenario.content_text,
        content_type="CONVERSATIONAL_FACT",
        memory_type=scenario.memory_type,
        parent_ids=scenario.parent_ids,
        lifecycle_state="ACTIVE",
        creation_timestamp="2026-09-14T00:00:00Z",
    )


def evaluate_pool(
    pool: ScenarioPool, config: DefenseConfiguration, *, run_id: str
) -> Tuple[MemoryOutcome, ...]:
    """Apply `config`'s enabled components to every memory in `pool`,
    returning one `MemoryOutcome` per memory. Retrieval consensus is computed
    once over the whole pool (it is inherently a pool-level signal); every
    other component is evaluated per-memory, independent of the pool."""
    n = len(pool.memories)

    retrieval_actions: Dict[str, Optional[str]] = {m.scenario_id: None for m in pool.memories}
    if config.retrieval_enabled:
        candidates = [
            RetrievalCandidate(
                memory_id=m.scenario_id,
                content_text=m.content_text,
                cosine_score=0.7,
                token_overlap_score=0.5,
                entity_overlap_score=0.2,
                raw_blended_score=0.5 * 0.7 + 0.3 * 0.5 + 0.2 * 0.2,
                security_state=m.current_security_state,
            )
            for m in pool.memories
        ]
        if config.retrieval_divergence_fn_override is not None:
            divergence_fn = config.retrieval_divergence_fn_override
        else:
            divergence_fn = semantic_divergence_fn if config.retrieval_metric == "semantic" else pool_consensus_divergence_signals
        result = evaluate_retrieval_defense(
            candidates,
            run_id=run_id,
            episode_id="episode-1",
            timestamp="2026-09-14T00:00:00Z",
            evidence_refs_for=lambda mid: (f"EVT-{mid}",),
            divergence_fn=divergence_fn,
        )
        for decision in result.downrank_decisions:
            retrieval_actions[decision.candidate_memory_id] = decision.action
        for decision in result.escalation_decisions:
            retrieval_actions[decision.candidate_memory_id] = decision.action  # escalation overrides downrank

    outcomes = []
    for m in pool.memories:
        context = _to_signal_context(m)

        admission_action = None
        if config.admission_enabled:
            admission_action = evaluate_admission(
                context, current_security_state=m.current_security_state,
                run_id=run_id, episode_id="episode-1",
                timestamp="2026-09-14T00:00:00Z", evidence_refs=(f"EVT-{m.scenario_id}",),
            ).action

        propagation_action = None
        if config.propagation_enabled and m.ancestors:
            try:
                propagation_action = evaluate_propagation_containment(
                    m.scenario_id, m.content_text, m.current_security_state, m.ancestors,
                    run_id=run_id, episode_id="episode-1", timestamp="2026-09-14T00:00:00Z",
                    evidence_refs=(f"EVT-{m.scenario_id}",),
                ).action
            except IllegalTransitionError:
                # A currently-QUARANTINED descendant whose freshly-computed taint has
                # genuinely dropped -- a legitimate case needing a real RELEASE
                # decision, not a batch-crashing error. See REFER_TO_RELEASE_PROCESS
                # above.
                propagation_action = REFER_TO_RELEASE_PROCESS

        sleeper_action = None
        if config.sleeper_enabled:
            sleeper_action = evaluate_sleeper_admission(
                context, run_id=run_id, episode_id="episode-1",
                timestamp="2026-09-14T00:00:00Z", evidence_refs=(f"EVT-{m.scenario_id}",),
            ).action

        # REFER_TO_RELEASE_PROCESS is not a real action and has no severity --
        # excluded from the combined vote (treated like a disabled component),
        # while remaining visible on the record itself (MemoryOutcome.propagation_action).
        propagation_action_for_combining = None if propagation_action == REFER_TO_RELEASE_PROCESS else propagation_action
        final = combined_action(
            [admission_action, retrieval_actions[m.scenario_id], propagation_action_for_combining, sleeper_action]
        )

        outcomes.append(
            MemoryOutcome(
                scenario_id=m.scenario_id,
                admission_action=admission_action,
                retrieval_action=retrieval_actions[m.scenario_id],
                propagation_action=propagation_action,
                sleeper_action=sleeper_action,
                combined_action=final,
                is_poison_ground_truth=m.is_poison_ground_truth,
                attack_family_ground_truth=m.attack_family_ground_truth,
            )
        )
    return tuple(outcomes)


@dataclass(frozen=True)
class ConfigurationMetrics:
    config_name: str
    poison_detection_rate: float  # fraction of poison-ground-truth memories with combined_action != ALLOW
    benign_false_positive_rate: float  # fraction of benign-ground-truth memories with combined_action != ALLOW
    n_poison: int
    n_benign: int
    per_attack_family_detection: Dict[str, float] = field(default_factory=dict)


def compute_metrics(outcomes: Sequence[MemoryOutcome], config_name: str) -> ConfigurationMetrics:
    """Computed strictly AFTER all decisions are made -- ground truth never
    reaches a decision function, only this reporting step."""
    poison = [o for o in outcomes if o.is_poison_ground_truth]
    benign = [o for o in outcomes if not o.is_poison_ground_truth]
    poison_detected = sum(1 for o in poison if o.combined_action != ALLOW)
    benign_flagged = sum(1 for o in benign if o.combined_action != ALLOW)

    per_family: Dict[str, float] = {}
    families = {o.attack_family_ground_truth for o in poison if o.attack_family_ground_truth}
    for family in families:
        family_poison = [o for o in poison if o.attack_family_ground_truth == family]
        detected = sum(1 for o in family_poison if o.combined_action != ALLOW)
        per_family[family] = detected / len(family_poison) if family_poison else 0.0

    return ConfigurationMetrics(
        config_name=config_name,
        poison_detection_rate=poison_detected / len(poison) if poison else 0.0,
        benign_false_positive_rate=benign_flagged / len(benign) if benign else 0.0,
        n_poison=len(poison),
        n_benign=len(benign),
        per_attack_family_detection=per_family,
    )
