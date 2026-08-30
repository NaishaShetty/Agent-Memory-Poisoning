"""Phase 3.2-H.3 (Memory Foundation Integration Architecture) -- the seven-stage memory
lifecycle vocabulary: MEMORY_AVAILABLE -> MEMORY_RETRIEVED -> MEMORY_SELECTED ->
MEMORY_EXPOSED -> MEMORY_USED -> MEMORY_CONTRIBUTED -> (MEMORY_CAUSED, never implemented).

WHY THIS MODULE EXISTS
--------------------------------------------------------------------------------
`extensions/agentic_memory.py` (Phase 3.2-H.3's first stage) already established a
four-way discipline for MemoryArena-shaped chain data: MEMORY_AVAILABLE != MEMORY_USED !=
MEMORY_CONTRIBUTED != MEMORY_CAUSED, reusing `agent.diagnostics.classify_retrieval_
utilization` (MEMORY_USED) and `agent.paired.classify_memory_contribution`
(MEMORY_CONTRIBUTED) verbatim, and deliberately never implementing MEMORY_CAUSED. This
module MIRRORS that exact discipline for the foundation-integration layer, extending the
vocabulary with three EARLIER lifecycle stages that a stateful memory foundation's pipeline
genuinely has and MemoryArena's flat chain-subtask data did not need:

- MEMORY_AVAILABLE: a memory item exists in the foundation's store at all (structural).
- MEMORY_RETRIEVED: the foundation's retrieval operation returned this item as a candidate
  for a given query (NEW here -- MemoryArena's structural availability check had no
  analogue of "a retrieval call ran and returned candidates," since MemoryArena has no
  memory-unit layer at all, per `agentic_memory.py`'s own gap analysis).
- MEMORY_SELECTED: this item was chosen from among the retrieved candidates to be shown to
  the agent (NEW here -- distinguishes "returned by the retrieval call" from "selected for
  the agent's context," which for a real foundation with a rerank/top-k step are genuinely
  different moments).
- MEMORY_EXPOSED: this item's content was actually placed into the agent-visible payload
  (NEW here -- distinguishes "selected" from "successfully passed the
  `contracts.boundary.validate_agent_visible()` check and appeared in the agent-visible
  context," since a selection could in principle fail that check and never be exposed).
- MEMORY_USED: re-exports `agent.diagnostics.classify_retrieval_utilization` VERBATIM
  (unchanged from `agentic_memory.py`'s own re-export) -- did the agent's answer draw on
  the exposed item.
- MEMORY_CONTRIBUTED: re-exports `agent.paired.classify_memory_contribution` VERBATIM
  (unchanged) -- did providing the item change the observed correctness outcome.
- MEMORY_CAUSED: deliberately, explicitly NOT implemented anywhere in this module. See
  `agentic_memory.py`'s own module docstring for the full non-causal-discipline rationale,
  which applies here completely unmodified: a genuine causal claim requires an intervention
  design beyond a single paired observation, out of scope for a framework-architecture
  stage. `test_foundation_architecture_h3.py` asserts this status string never appears as
  an achievable/returned value anywhere in this package.

REJECTED ALTERNATIVE: reimplement MEMORY_USED/MEMORY_CONTRIBUTED with foundation-specific
logic (e.g. treating Graphiti's edge-traversal differently from Mem0's flat retrieval).
Rejected for the same reason `agentic_memory.py` rejected reimplementing them for
MemoryArena: `classify_retrieval_utilization` and `classify_memory_contribution` operate
entirely on `AgentExecutionResult` + `expected_answer`, neither of which has, or needs, any
opinion about what "memory" substantively means or which foundation produced it. This
module's job is only to supply the three EARLIER, foundation-specific stages that don't
yet have a diagnostic home, and to assemble the full seven-name ordered vocabulary in one
place.

Pure functions/dataclasses: no filesystem/network/LLM/embeddings access, no randomness, no
global/mutable state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import AbstractSet, Any, Mapping, Optional, Sequence, Tuple

from phase3.evaluation.agent.diagnostics import classify_retrieval_utilization
from phase3.evaluation.agent.paired import (
    PairedComparisonIdentityError,
    classify_memory_contribution,
)
from phase3.evaluation.metrics.types import MetricResult

# ---------------------------------------------------------------------------
# The seven-stage ordered lifecycle vocabulary
# ---------------------------------------------------------------------------

MEMORY_AVAILABLE = "MEMORY_AVAILABLE"
MEMORY_RETRIEVED = "MEMORY_RETRIEVED"
MEMORY_SELECTED = "MEMORY_SELECTED"
MEMORY_EXPOSED = "MEMORY_EXPOSED"
MEMORY_USED = "MEMORY_USED"
MEMORY_CONTRIBUTED = "MEMORY_CONTRIBUTED"

# Deliberately NOT a stage any function in this module can return -- see module docstring.
# Kept as a named constant (rather than only appearing in prose) so
# `test_foundation_architecture_h3.py` can grep the codebase for any function returning it.
MEMORY_CAUSED = "MEMORY_CAUSED"

LIFECYCLE_STAGES: Tuple[str, ...] = (
    MEMORY_AVAILABLE,
    MEMORY_RETRIEVED,
    MEMORY_SELECTED,
    MEMORY_EXPOSED,
    MEMORY_USED,
    MEMORY_CONTRIBUTED,
    # MEMORY_CAUSED intentionally excluded from this tuple -- it is not an achievable
    # lifecycle stage in this framework, only a named placeholder for what is NOT built.
)

NOT_AVAILABLE = "NOT_AVAILABLE"
NOT_RETRIEVED = "NOT_RETRIEVED"
NOT_SELECTED = "NOT_SELECTED"
NOT_EXPOSED = "NOT_EXPOSED"


# ---------------------------------------------------------------------------
# MEMORY_AVAILABLE (structural)
# ---------------------------------------------------------------------------


def classify_memory_availability(
    memory_id: str,
    store_memory_ids: AbstractSet[str],
) -> MetricResult:
    """Purely STRUCTURAL: is `memory_id` present in the foundation's store at all,
    independent of whether any retrieval call has ever touched it?
    """
    classification = MEMORY_AVAILABLE if memory_id in store_memory_ids else NOT_AVAILABLE
    return MetricResult(
        metric_name="FOUNDATION_MEMORY_AVAILABILITY",
        value=None,
        status=classification,
        detail={"memory_id": memory_id, "store_size": len(store_memory_ids)},
        note=(
            "Purely structural -- reports store membership only, never whether this item "
            "was retrieved/selected/exposed/used."
        ),
    )


# ---------------------------------------------------------------------------
# MEMORY_RETRIEVED
# ---------------------------------------------------------------------------


def classify_memory_retrieval(
    memory_id: str,
    retrieved_memory_ids: Sequence[str],
) -> MetricResult:
    """Did the foundation's retrieval operation return `memory_id` as a candidate for a
    given query? `retrieved_memory_ids` is taken in EXACT caller order (never reordered
    here) -- order is preserved in `detail` so a downstream check can assert ranking was
    not silently discarded.
    """
    classification = MEMORY_RETRIEVED if memory_id in retrieved_memory_ids else NOT_RETRIEVED
    return MetricResult(
        metric_name="FOUNDATION_MEMORY_RETRIEVAL",
        value=None,
        status=classification,
        detail={
            "memory_id": memory_id,
            "retrieved_memory_ids": list(retrieved_memory_ids),
            "rank": (
                list(retrieved_memory_ids).index(memory_id)
                if memory_id in retrieved_memory_ids
                else None
            ),
        },
        note="Reports candidate-set membership and rank position only, never selection/exposure/usage.",
    )


# ---------------------------------------------------------------------------
# MEMORY_SELECTED
# ---------------------------------------------------------------------------


def classify_memory_selection(
    memory_id: str,
    selected_memory_ids: Sequence[str],
) -> MetricResult:
    """Was `memory_id` chosen from among retrieved candidates to be shown to the agent?
    Order-preserving, mirrors `classify_memory_retrieval`'s discipline.
    """
    classification = MEMORY_SELECTED if memory_id in selected_memory_ids else NOT_SELECTED
    return MetricResult(
        metric_name="FOUNDATION_MEMORY_SELECTION",
        value=None,
        status=classification,
        detail={
            "memory_id": memory_id,
            "selected_memory_ids": list(selected_memory_ids),
        },
        note="Reports selection-set membership only, never whether the item was actually exposed/used.",
    )


# ---------------------------------------------------------------------------
# MEMORY_EXPOSED
# ---------------------------------------------------------------------------


def classify_memory_exposure(
    memory_id: str,
    agent_visible_payload: Mapping[str, Any],
) -> MetricResult:
    """Did `memory_id`'s content actually appear in the agent-visible payload (the payload
    that has already passed `contracts.boundary.validate_agent_visible()`)? This function
    does NOT itself run the boundary check -- callers are expected to have validated the
    payload already (e.g. via `agent.conditions.build_agent_visible_context`, which runs
    that check internally) -- it only inspects `memory_content` items' `memory_id` field
    for a match.
    """
    memory_content = agent_visible_payload.get("memory_content", [])
    exposed_ids = [
        item.get("memory_id") for item in memory_content if isinstance(item, Mapping)
    ]
    classification = MEMORY_EXPOSED if memory_id in exposed_ids else NOT_EXPOSED
    return MetricResult(
        metric_name="FOUNDATION_MEMORY_EXPOSURE",
        value=None,
        status=classification,
        detail={"memory_id": memory_id, "exposed_memory_ids": exposed_ids},
        note="Reports agent-visible-payload membership only, never whether the agent actually used the content.",
    )


# ---------------------------------------------------------------------------
# MEMORY_USED and MEMORY_CONTRIBUTED -- pure re-exports (see module docstring)
# ---------------------------------------------------------------------------

classify_memory_usage = classify_retrieval_utilization
classify_memory_foundation_contribution = classify_memory_contribution


@dataclass(frozen=True)
class LifecycleTrace:
    """The full, ordered sequence of lifecycle classifications observed for one memory
    item across one scripted scenario. `stages_reached` is a tuple built in the EXACT
    order the six achievable stages were classified as reached (never MEMORY_CAUSED,
    which cannot appear here by construction -- no function in this module produces it).
    """

    memory_id: str
    stages_reached: Tuple[str, ...]


def build_lifecycle_trace(
    memory_id: str,
    store_memory_ids: AbstractSet[str],
    retrieved_memory_ids: Sequence[str] = (),
    selected_memory_ids: Sequence[str] = (),
    agent_visible_payload: Optional[Mapping[str, Any]] = None,
    usage_result: Optional[MetricResult] = None,
    contribution_result: Optional[MetricResult] = None,
) -> LifecycleTrace:
    """Assemble the ordered stages `memory_id` actually reached, stopping at the first
    stage NOT reached (a memory item cannot be MEMORY_SELECTED without first being
    MEMORY_RETRIEVED, etc. -- this function enforces that ordering structurally rather than
    trusting the caller's inputs to already be consistent).
    """
    stages: list = []

    availability = classify_memory_availability(memory_id, store_memory_ids)
    if availability.status != MEMORY_AVAILABLE:
        return LifecycleTrace(memory_id=memory_id, stages_reached=tuple(stages))
    stages.append(MEMORY_AVAILABLE)

    retrieval = classify_memory_retrieval(memory_id, retrieved_memory_ids)
    if retrieval.status != MEMORY_RETRIEVED:
        return LifecycleTrace(memory_id=memory_id, stages_reached=tuple(stages))
    stages.append(MEMORY_RETRIEVED)

    selection = classify_memory_selection(memory_id, selected_memory_ids)
    if selection.status != MEMORY_SELECTED:
        return LifecycleTrace(memory_id=memory_id, stages_reached=tuple(stages))
    stages.append(MEMORY_SELECTED)

    if agent_visible_payload is None:
        return LifecycleTrace(memory_id=memory_id, stages_reached=tuple(stages))
    exposure = classify_memory_exposure(memory_id, agent_visible_payload)
    if exposure.status != MEMORY_EXPOSED:
        return LifecycleTrace(memory_id=memory_id, stages_reached=tuple(stages))
    stages.append(MEMORY_EXPOSED)

    if usage_result is None:
        return LifecycleTrace(memory_id=memory_id, stages_reached=tuple(stages))
    if usage_result.status != "SELECTED_AND_USED":
        return LifecycleTrace(memory_id=memory_id, stages_reached=tuple(stages))
    stages.append(MEMORY_USED)

    if contribution_result is None:
        return LifecycleTrace(memory_id=memory_id, stages_reached=tuple(stages))
    if contribution_result.status != "POSITIVE_MEMORY_CONTRIBUTION":
        return LifecycleTrace(memory_id=memory_id, stages_reached=tuple(stages))
    stages.append(MEMORY_CONTRIBUTED)

    return LifecycleTrace(memory_id=memory_id, stages_reached=tuple(stages))


__all__ = [
    "MEMORY_AVAILABLE",
    "MEMORY_RETRIEVED",
    "MEMORY_SELECTED",
    "MEMORY_EXPOSED",
    "MEMORY_USED",
    "MEMORY_CONTRIBUTED",
    "MEMORY_CAUSED",
    "LIFECYCLE_STAGES",
    "NOT_AVAILABLE",
    "NOT_RETRIEVED",
    "NOT_SELECTED",
    "NOT_EXPOSED",
    "classify_memory_availability",
    "classify_memory_retrieval",
    "classify_memory_selection",
    "classify_memory_exposure",
    "classify_memory_usage",
    "classify_memory_foundation_contribution",
    "LifecycleTrace",
    "build_lifecycle_trace",
    "PairedComparisonIdentityError",
]
