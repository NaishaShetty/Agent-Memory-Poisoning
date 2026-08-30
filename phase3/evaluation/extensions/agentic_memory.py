"""Phase 3.2-H.3 -- agentic task-chain memory diagnostics for MemoryArena-shaped data.

WHY THIS MODULE EXISTS (gap analysis summary; full detail in
`PHASE3_2_H3_FRAMEWORK_EXTENSION_SPEC.md`, Extension 3)
--------------------------------------------------------------------------------
MemoryArena's `agentic_task_memory` capability is confirmed AVAILABLE and is explicitly
called out, in its own H.1 profile, as "the single most load-bearing, genuinely-new
capability this candidate would add if activated" -- and, per
`mambench_compatibility.json`'s `overall_assessment`, "[has] NO dedicated metric anywhere in
the current phase3/evaluation/metrics/ suite." Every retrieval/evidence/lineage metric is
NOT_ATTEMPTABLE because MemoryArena has no memory-unit layer and no gold_evidence_ids at all
(confirmed by full scan, 701 records) -- this is a genuine FRAMEWORK LIMITATION for the one
capability MemoryArena actually adds (interdependent multi-session task CHAINS), not a
dataset-quality problem.

REJECTED ALTERNATIVE 1: invent a new schema-canonical `AGENTIC_TASK_CHAIN` evidence type and
new gold-evidence-ID scheme for MemoryArena. Rejected because MemoryArena genuinely has no
per-memory-unit identity in the source (confirmed absent) -- inventing one would fabricate
ground truth the mission's absolute rules forbid.

REJECTED ALTERNATIVE 2: define a brand-new PROVISIONAL condition (e.g.
`PRIOR_SUBTASK_CONTEXT_AVAILABLE`) alongside `agent/conditions.py`'s three canonical + three
3.2-E provisional conditions. Rejected: `agent/conditions.py`'s existing provisional
condition `CONDITION_SELECTED_MEMORY_AVAILABLE` ("Agent-visible context contains task plus
some selected memory content, without asserting the full retrieval+selection pipeline
semantics RETRIEVED_MEMORY implies") is already a semantically exact fit for "the agent is
given a prior subtask's question/answer as its 'selected memory' for a later subtask in the
same chain" -- treating a chain's earlier subtask as this condition's "selected memory
content" requires zero new condition vocabulary. Per the 3.2-E task brief's own rule ("only
add a new condition if the existing ones genuinely can't represent it"), this alternative is
rejected in favor of REUSING `CONDITION_SELECTED_MEMORY_AVAILABLE` verbatim.

REJECTED ALTERNATIVE 3: reimplement `agent/paired.py`'s paired-comparison /
memory-contribution classification with MemoryArena-specific logic. Rejected:
`paired.classify_memory_contribution` and `paired.paired_condition_comparison` operate
entirely on `AgentExecutionResult` + `expected_answer` -- neither function has, or needs, any
opinion about what "memory" substantively means. Both are REUSED verbatim below; this module
only supplies the MemoryArena-specific "what counts as a chain's memory item" adapter logic
that produces the `AgentExecutionResult`s paired.py already knows how to compare.

DESIGN: MEMORY_AVAILABLE != MEMORY_USED != MEMORY_CONTRIBUTED != MEMORY_CAUSED
--------------------------------------------------------------------------------
Four genuinely distinct, never-conflated concepts, per the 3.2-H.3 task brief's explicit
requirement:

- MEMORY_AVAILABLE: a purely STRUCTURAL fact -- was prior-subtask content structurally
  available to be shown to the agent for this subtask (i.e. `subtask_index > 0` within its
  chain)? `classify_chain_memory_availability` below. NEW, tiny, non-fabricating (grounded
  directly in `chain_length`/`subtask_index`, both AVAILABLE per the H.1 profile).
- MEMORY_USED: did the agent's answer draw on the offered prior-subtask memory item(s), per
  whatever trace the execution provides? REUSES
  `agent.diagnostics.classify_retrieval_utilization` VERBATIM (imported, not reimplemented)
  -- that function already asks exactly this question (`selected_memory_ids` vs.
  `used_memory_ids`) with no MemoryArena-specific change needed.
- MEMORY_CONTRIBUTED: did providing the memory item change (NO_MEMORY -> WITH_MEMORY) the
  observed answer-correctness outcome for the SAME subtask? REUSES
  `agent.paired.classify_memory_contribution` VERBATIM (imported, not reimplemented, its
  `PairedComparisonIdentityError` identity checks apply unchanged).
- MEMORY_CAUSED: a genuine CAUSAL claim ("providing the memory caused the corrected
  answer"). Deliberately, explicitly, NOT built anywhere in this module or elsewhere in this
  framework -- `paired.py`'s own module docstring already establishes the non-causal
  discipline this module inherits rather than weakens ("PAIRED CONDITION COMPARISON... never
  counterfactual"). A genuine causal claim would require an intervention design well beyond a
  single paired observation (e.g. repeated sampling under controlled reasoning-layer noise),
  which is out of scope for a framework-extension stage building deterministic diagnostics.
  Any future Phase 3.3+ work that wants to approach causal language must design that
  separately; this module's job is only to keep the three weaker, honestly-scoped concepts
  cleanly distinct from each other and from the causal claim that is NOT being made.

Pure functions/dataclasses: no filesystem/network/LLM/embeddings access, no randomness, no
global/mutable state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Mapping, Optional, Sequence, Tuple

from phase3.evaluation.agent.conditions import (
    CONDITION_NO_MEMORY,
    CONDITION_SELECTED_MEMORY_AVAILABLE,
    build_agent_visible_context,
)
from phase3.evaluation.agent.diagnostics import classify_retrieval_utilization
from phase3.evaluation.agent.outcomes import AgentExecutionResult
from phase3.evaluation.agent.paired import (
    PairedComparisonIdentityError,
    classify_memory_contribution,
)
from phase3.evaluation.metrics.types import MetricResult

# ---------------------------------------------------------------------------
# Chain/subtask structural representation (grounded in H.1: chain_length/subtask_index/
# source_task_id are all confirmed AVAILABLE; positional-only dependency, per
# memoryarena_profile.json's multi_session_memory/test_time_learning entries).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ChainSubtask:
    """One subtask within a MemoryArena-shaped interdependent task chain.

    Mirrors `phase3/datasets/candidates/memoryarena/normalized/subtasks.jsonl`'s actual
    fields (`derived_subtask_key`, `chain_length`, `question`, `answer`) plus the
    `subtask_index` this module derives (deterministically) from the `derived_subtask_key`'s
    trailing integer -- NOT a source-native field, but a lossless parse of one, not an
    invention.
    """

    chain_id: str
    subtask_index: int
    chain_length: int
    question: str
    answer: Any  # str | list | dict, per MemoryArena's per-config answer type variance


def subtask_index_from_derived_key(derived_subtask_key: str) -> int:
    """Parse the trailing integer off a `derived_subtask_key` like
    `"bundled_shopping:0:2"` -> `2`. Deterministic, lossless. Raises `ValueError` if the key
    does not end in an integer segment after a `:` -- never guesses.
    """
    parts = derived_subtask_key.split(":")
    if len(parts) < 2:
        raise ValueError(
            f"derived_subtask_key {derived_subtask_key!r} does not have a ':'-delimited "
            "trailing subtask index."
        )
    try:
        return int(parts[-1])
    except ValueError as exc:
        raise ValueError(
            f"derived_subtask_key {derived_subtask_key!r}'s trailing segment "
            f"{parts[-1]!r} is not an integer subtask index."
        ) from exc


# ---------------------------------------------------------------------------
# MEMORY_AVAILABLE (structural, NEW, non-fabricating)
# ---------------------------------------------------------------------------

MEMORY_AVAILABILITY_AVAILABLE = "MEMORY_AVAILABLE"
MEMORY_AVAILABILITY_NOT_AVAILABLE_FIRST_SUBTASK = "NOT_AVAILABLE_FIRST_SUBTASK"


def classify_chain_memory_availability(subtask: ChainSubtask) -> MetricResult:
    """Purely STRUCTURAL classification: is there any PRIOR subtask in this chain whose
    content could, in principle, be offered to the agent as "memory" for `subtask`?

    Definition: `MEMORY_AVAILABLE` iff `subtask.subtask_index > 0` (there is at least one
    earlier subtask in the same chain); `NOT_AVAILABLE_FIRST_SUBTASK` iff
    `subtask.subtask_index == 0` (the first subtask in a chain has no prior-subtask content
    to draw on, by construction -- this is not a data gap, it is a structural fact about
    chain position, mirroring `agent.diagnostics`'s `NO_SELECTED_EVIDENCE` framing: a
    genuinely-empty precondition is reported as its own distinct case, never conflated with
    "available but not used").

    This function does NOT determine whether that prior content was actually SHOWN to the
    agent (that is a harness/adapter decision downstream) or USED (see
    `classify_retrieval_utilization`, reused verbatim below) -- it answers only the narrowest
    structural question, which is exactly why it must be kept a separate concept.
    """
    if subtask.subtask_index > 0:
        classification = MEMORY_AVAILABILITY_AVAILABLE
        prior_count = subtask.subtask_index
    else:
        classification = MEMORY_AVAILABILITY_NOT_AVAILABLE_FIRST_SUBTASK
        prior_count = 0

    return MetricResult(
        metric_name="CHAIN_MEMORY_AVAILABILITY",
        value=None,
        status=classification,
        detail={
            "chain_id": subtask.chain_id,
            "subtask_index": subtask.subtask_index,
            "chain_length": subtask.chain_length,
            "prior_subtask_count": prior_count,
        },
        note=(
            "Purely structural -- reports whether ANY prior subtask exists in this chain, "
            "never whether it was shown to or used by the agent. See classify_retrieval_"
            "utilization (MEMORY_USED) and classify_memory_contribution (MEMORY_CONTRIBUTED) "
            "for those separate, stronger claims."
        ),
    )


# ---------------------------------------------------------------------------
# Agent-visible context assembly for the WITH_MEMORY side (REUSES
# CONDITION_SELECTED_MEMORY_AVAILABLE and build_agent_visible_context verbatim -- see
# REJECTED ALTERNATIVE 2 above for why no new condition constant is introduced).
# ---------------------------------------------------------------------------


def prior_subtask_memory_id(chain_id: str, prior_subtask_index: int) -> str:
    """Deterministic, chain-adapter-defined memory-id convention for "subtask N's
    question+answer, treated as one memory item for a later subtask in the same chain."
    NOT a source-native memory_id (MemoryArena has none) -- an explicit, documented adapter
    convention, never claimed as anything else.
    """
    return f"{chain_id}:subtask:{prior_subtask_index}"


def build_prior_subtask_memory_items(
    prior_subtasks: Sequence[ChainSubtask],
) -> List[Mapping[str, Any]]:
    """Build `{"memory_id": ..., "content": ...}` items (the shape
    `agent.conditions.build_agent_visible_context` expects) from a chain's PRIOR subtasks,
    one item per prior subtask, each carrying that subtask's own question+answer as its
    content. Order-preserving (no reordering, no deduplication) -- mirrors the same "never
    silently reorder a caller's sequence" discipline used throughout
    `phase3/evaluation/metrics/`.
    """
    items = []
    for st in prior_subtasks:
        items.append(
            {
                "memory_id": prior_subtask_memory_id(st.chain_id, st.subtask_index),
                "content": {"question": st.question, "answer": st.answer},
            }
        )
    return items


def build_chain_agent_visible_context(
    task_id: str,
    prompt: str,
    condition: str,
    prior_subtasks: Sequence[ChainSubtask] = (),
) -> Mapping[str, Any]:
    """Thin wrapper over `agent.conditions.build_agent_visible_context` (REUSED verbatim,
    including its own `boundary.validate_agent_visible()` call) -- `condition` must be
    `CONDITION_NO_MEMORY` or `CONDITION_SELECTED_MEMORY_AVAILABLE` (the two conditions this
    module's paired comparison uses); any other condition raises the SAME `ValueError`
    `build_agent_visible_context` already raises for an unrecognized condition (no parallel
    validation logic is added here).
    """
    if condition not in (CONDITION_NO_MEMORY, CONDITION_SELECTED_MEMORY_AVAILABLE):
        raise ValueError(
            "build_chain_agent_visible_context only supports CONDITION_NO_MEMORY or "
            f"CONDITION_SELECTED_MEMORY_AVAILABLE for chain-structured data; got {condition!r}."
        )
    memory_items = (
        build_prior_subtask_memory_items(prior_subtasks)
        if condition == CONDITION_SELECTED_MEMORY_AVAILABLE
        else None
    )
    return build_agent_visible_context(
        condition=condition,
        task_id=task_id,
        prompt=prompt,
        memory_items=memory_items,
    )


# ---------------------------------------------------------------------------
# MEMORY_USED and MEMORY_CONTRIBUTED -- pure re-exports, so callers of this module never
# need to import agent.diagnostics/agent.paired separately AND so a reader can see, right
# here, that no MemoryArena-specific reimplementation exists for either concept.
# ---------------------------------------------------------------------------

# MEMORY_USED: re-export of the existing, unchanged diagnostic.
classify_chain_memory_usage = classify_retrieval_utilization

# MEMORY_CONTRIBUTED: re-export of the existing, unchanged diagnostic. Reusing this function
# means its identity-preservation discipline (raising PairedComparisonIdentityError on a
# task_id/expected_answer/condition mismatch) applies to chain data completely unmodified.
classify_chain_memory_contribution = classify_memory_contribution

__all__ = [
    "ChainSubtask",
    "subtask_index_from_derived_key",
    "MEMORY_AVAILABILITY_AVAILABLE",
    "MEMORY_AVAILABILITY_NOT_AVAILABLE_FIRST_SUBTASK",
    "classify_chain_memory_availability",
    "prior_subtask_memory_id",
    "build_prior_subtask_memory_items",
    "build_chain_agent_visible_context",
    "classify_chain_memory_usage",
    "classify_chain_memory_contribution",
    "PairedComparisonIdentityError",
]
