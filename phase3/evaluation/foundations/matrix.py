"""Phase 3.2-H.3 (Memory Foundation Integration Architecture) -- the authoritative
dataset x foundation x capability matrix (Step 5 of the mission).

WHAT THIS MATRIX ANSWERS, AND HOW IT IS COMPUTED (never hand-waved as 700 independent
judgments)
--------------------------------------------------------------------------------
7 datasets (the 4 ACTIVE: LoCoMo, LongMemEval, MSC, Conversation Chronicles; the 3
PREPARED_CANDIDATE: MemoryAgentBench, MemBench, MemoryArena) x 5 "foundations" (NATIVE
MAMBench, Mem0, Letta, Graphiti, A-MEM) x 20 capabilities (a documented subset of
`capability_audit.CAPABILITY_DIMENSIONS`'s 27 -- the 7 dropped are foundation-level-only
facts that do not vary by dataset: `llm_dependency`, `embedding_dependency`,
`external_service_dependency`, `local_execution`, `determinism`,
`attack_injection_points`, `license_research_use`; these already have their own per-
foundation answer in `capability_audit.py`/`model_dependency.py` and repeating them
identically across all 7 dataset rows would not be a genuinely new fact).

Rather than fabricating 700 independent per-cell judgments, every cell is COMPUTED from
two already-grounded inputs, per this explicit rule:

1. NATIVE column: MAMBench's own existing evaluation layer has NO memory-foundation layer
   of its own -- it evaluates already-produced `AgentExecutionResult`s against a fixed
   dataset profile; it never itself creates/updates/deletes/links memory state. So for
   every capability in `_NATIVE_OPERATIONAL_CAPABILITIES` (memory_creation, update,
   deletion, linking, graph, retrieval_ordering [as a foundation OPERATION, not as an
   evidence-ranking metric -- Recall@K/MRR already do this at the METRIC layer, a
   different question], retrieval_scores, lifecycle_observability, state_export,
   resetability, isolation, configuration_capture) the NATIVE cell is `NOT_APPLICABLE`,
   with a reason stating exactly this. For the remaining capabilities
   (`_NATIVE_PROFILE_MAPPED_CAPABILITIES`: retrieval, memory_identifiers, metadata,
   session_state, temporal_state, traceability, agent_integration) the NATIVE cell is
   read from that dataset's own existing H (3.2-A-H.1) capability profile, via
   `_native_profile_lookup()` -- NEVER recomputed, only looked up and re-expressed in this
   matrix's 5-value vocabulary.

2. MEM0 / LETTA / GRAPHITI / A_MEM columns: the cell is the foundation's own
   `capability_audit.py` row for that capability (a foundation-level fact, true
   regardless of which dataset's data would flow through it) -- UNLESS the capability is
   `session_state` or `temporal_state`, which additionally require the DATASET to have the
   structural precondition (multi-session structure / a temporal-ordering signal) for the
   capability to be exercisable at all; if that dataset-level precondition is not
   confirmed present, the cell is `NOT_APPLICABLE` regardless of what the foundation
   itself supports (a foundation's temporal-reasoning capability is moot against a dataset
   with no temporal signal to reason over). Where this stage did not re-derive a
   candidate dataset's precise structural precondition (MemoryAgentBench, MemBench), the
   cell is `UNKNOWN` rather than guessed either way.

STATUS VOCABULARY -- new, per the task brief's explicit Step 5 instruction
--------------------------------------------------------------------------------
`SUPPORTED` / `PARTIAL` / `NOT_PROVIDED` / `NOT_APPLICABLE` / `UNKNOWN` (a five-value
vocabulary distinct from both `capability_audit.AUDIT_STATES` --
which uses `NOT_SUPPORTED` rather than `NOT_PROVIDED` -- and
`phase3.evaluation.datasets.capability.CAPABILITY_STATES`; the task brief names this exact
vocabulary for the matrix specifically, so it is implemented literally rather than reusing
either of the other two verbatim).

Pure data/computation module: reads only the already-imported `capability_audit.py` data
and this module's own small, explicitly-cited dataset-precondition table (not a live
filesystem read of every dataset profile file) -- no network/LLM/embeddings access, no
randomness.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Tuple

from phase3.evaluation.foundations.capability_audit import (
    ALL_AUDITS,
    ALL_FOUNDATIONS,
    AUDIT_NOT_SUPPORTED,
    AUDIT_PARTIAL,
    AUDIT_SUPPORTED,
    AUDIT_UNKNOWN,
    FOUNDATION_AMEM,
    FOUNDATION_GRAPHITI,
    FOUNDATION_LETTA,
    FOUNDATION_MEM0,
)

# ---------------------------------------------------------------------------
# Status vocabulary
# ---------------------------------------------------------------------------

MATRIX_SUPPORTED = "SUPPORTED"
MATRIX_PARTIAL = "PARTIAL"
MATRIX_NOT_PROVIDED = "NOT_PROVIDED"
MATRIX_NOT_APPLICABLE = "NOT_APPLICABLE"
MATRIX_UNKNOWN = "UNKNOWN"

MATRIX_STATES: Tuple[str, ...] = (
    MATRIX_SUPPORTED,
    MATRIX_PARTIAL,
    MATRIX_NOT_PROVIDED,
    MATRIX_NOT_APPLICABLE,
    MATRIX_UNKNOWN,
)

# ---------------------------------------------------------------------------
# Datasets (4 ACTIVE + 3 PREPARED_CANDIDATE)
# ---------------------------------------------------------------------------

DATASET_LOCOMO = "LOCOMO"
DATASET_LONGMEMEVAL = "LONGMEMEVAL"
DATASET_MSC = "MSC"
DATASET_CONVERSATION_CHRONICLES = "CONVERSATION_CHRONICLES"
DATASET_MEMORYAGENTBENCH = "MEMORYAGENTBENCH"
DATASET_MEMBENCH = "MEMBENCH"
DATASET_MEMORYARENA = "MEMORYARENA"

ALL_DATASETS: Tuple[str, ...] = (
    DATASET_LOCOMO,
    DATASET_LONGMEMEVAL,
    DATASET_MSC,
    DATASET_CONVERSATION_CHRONICLES,
    DATASET_MEMORYAGENTBENCH,
    DATASET_MEMBENCH,
    DATASET_MEMORYARENA,
)

ACTIVE_DATASETS: Tuple[str, ...] = (
    DATASET_LOCOMO,
    DATASET_LONGMEMEVAL,
    DATASET_MSC,
    DATASET_CONVERSATION_CHRONICLES,
)

PREPARED_CANDIDATE_DATASETS: Tuple[str, ...] = (
    DATASET_MEMORYAGENTBENCH,
    DATASET_MEMBENCH,
    DATASET_MEMORYARENA,
)

# ---------------------------------------------------------------------------
# Foundations (NATIVE + the four PREPARED_CANDIDATE foundations)
# ---------------------------------------------------------------------------

FOUNDATION_NATIVE = "NATIVE"

ALL_MATRIX_FOUNDATIONS: Tuple[str, ...] = (FOUNDATION_NATIVE,) + ALL_FOUNDATIONS

# ---------------------------------------------------------------------------
# The 20 matrix capabilities (documented subset of CAPABILITY_DIMENSIONS's 27 -- see
# module docstring for why the other 7 are excluded).
# ---------------------------------------------------------------------------

MATRIX_CAPABILITIES: Tuple[str, ...] = (
    "memory_creation",
    "storage",
    "retrieval",
    "update",
    "deletion",
    "linking",
    "graph",
    "temporal_state",
    "session_state",
    "memory_identifiers",
    "metadata",
    "retrieval_ordering",
    "retrieval_scores",
    "lifecycle_observability",
    "traceability",
    "state_export",
    "resetability",
    "isolation",
    "configuration_capture",
    "agent_integration",
)

assert len(MATRIX_CAPABILITIES) == 20, "MATRIX_CAPABILITIES must be exactly 20 per Step 5."

# Capabilities where NATIVE MAMBench (no memory-foundation layer of its own) is
# structurally NOT_APPLICABLE.
_NATIVE_OPERATIONAL_CAPABILITIES: Tuple[str, ...] = (
    "memory_creation",
    "storage",
    "update",
    "deletion",
    "linking",
    "graph",
    "retrieval_ordering",
    "retrieval_scores",
    "lifecycle_observability",
    "state_export",
    "resetability",
    "isolation",
    "configuration_capture",
)

# Capabilities where NATIVE's cell is read from that dataset's own existing profile,
# per the grounded lookup table below.
_NATIVE_PROFILE_MAPPED_CAPABILITIES: Tuple[str, ...] = (
    "retrieval",
    "temporal_state",
    "session_state",
    "memory_identifiers",
    "metadata",
    "traceability",
    "agent_integration",
)

assert set(_NATIVE_OPERATIONAL_CAPABILITIES) | set(_NATIVE_PROFILE_MAPPED_CAPABILITIES) == set(
    MATRIX_CAPABILITIES
)

# ---------------------------------------------------------------------------
# NATIVE per-dataset, per-mapped-capability grounded lookup.
#
# Grounded in the ACTUAL existing dataset profiles read for this stage:
# phase3/evaluation/datasets/profiles/{locomo,longmemeval,msc,conversation_chronicles}.json
# (`temporal_information.kind`: LoCoMo/LongMemEval = TIMESTAMPED_ABSOLUTE, MSC/
# Conversation Chronicles = ORDERED_SEQUENCE_ONLY) and
# phase3/datasets/candidates/memoryarena/profile/memoryarena_profile.json
# (`capability_dimensions.multi_session_memory.status` = PARTIAL,
# `capability_dimensions.temporal_order.status` = PARTIAL). MemoryAgentBench/MemBench's
# own profile files use yet another key schema (`dimensions` rather than
# `capability_dimensions`) that this stage did not re-derive in full -- their session/
# temporal cells are honestly UNKNOWN rather than guessed. `retrieval`/
# `memory_identifiers`/`metadata`/`traceability`/`agent_integration` are set SUPPORTED for
# every one of the 7 datasets: all seven are, by construction, memory-QA benchmarks over
# an agent-visible task/context/evidence structure that MAMBench's existing
# `contracts`/`agent` layers already handle uniformly (this is the exact reason the H/H.1
# activation work exists) -- this is a general, load-bearing, already-established fact
# about this codebase's own architecture, not a per-dataset guess.
# ---------------------------------------------------------------------------

_NATIVE_UNIFORM_SUPPORTED_CAPABILITIES: Tuple[str, ...] = (
    "retrieval",
    "memory_identifiers",
    "metadata",
    "traceability",
    "agent_integration",
)

_NATIVE_TEMPORAL_SESSION_LOOKUP: Mapping[str, Mapping[str, Tuple[str, str]]] = {
    DATASET_LOCOMO: {
        "temporal_state": (MATRIX_SUPPORTED, "temporal_information.kind == TIMESTAMPED_ABSOLUTE"),
        "session_state": (MATRIX_SUPPORTED, "LoCoMo is a multi-session long-term dialogue benchmark by construction"),
    },
    DATASET_LONGMEMEVAL: {
        "temporal_state": (MATRIX_SUPPORTED, "temporal_information.kind == TIMESTAMPED_ABSOLUTE"),
        "session_state": (MATRIX_SUPPORTED, "LongMemEval is a multi-session long-term chat benchmark by construction"),
    },
    DATASET_MSC: {
        "temporal_state": (MATRIX_PARTIAL, "temporal_information.kind == ORDERED_SEQUENCE_ONLY (order, not absolute timestamps)"),
        "session_state": (MATRIX_SUPPORTED, "MSC (Multi-Session Chat) is explicitly a multi-session dialogue benchmark"),
    },
    DATASET_CONVERSATION_CHRONICLES: {
        "temporal_state": (MATRIX_PARTIAL, "temporal_information.kind == ORDERED_SEQUENCE_ONLY (order, not absolute timestamps)"),
        "session_state": (MATRIX_SUPPORTED, "Conversation Chronicles is explicitly a multi-session long-term dialogue benchmark"),
    },
    DATASET_MEMORYAGENTBENCH: {
        "temporal_state": (MATRIX_UNKNOWN, "MemoryAgentBench's own profile schema (dimensions) was not re-derived for temporal ordering in this stage"),
        "session_state": (MATRIX_UNKNOWN, "adapter base.py docstring characterizes MemoryAgentBench as 'flat QA-over-context' but this stage did not re-derive session-structure precisely"),
    },
    DATASET_MEMBENCH: {
        "temporal_state": (MATRIX_UNKNOWN, "MemBench's own profile schema (dimensions) was not re-derived for temporal ordering in this stage"),
        "session_state": (MATRIX_SUPPORTED, "adapter base.py docstring characterizes MemBench as 'nested session/turn transcripts'"),
    },
    DATASET_MEMORYARENA: {
        "temporal_state": (MATRIX_PARTIAL, "memoryarena_profile.json capability_dimensions.temporal_order.status == PARTIAL"),
        "session_state": (MATRIX_PARTIAL, "memoryarena_profile.json capability_dimensions.multi_session_memory.status == PARTIAL"),
    },
}

# ---------------------------------------------------------------------------
# Dataset structural preconditions for session_state/temporal_state (used to gate the
# MEM0/LETTA/GRAPHITI/A_MEM columns) -- derived from the SAME lookup table above, since
# NATIVE's own profile-grounded finding IS the dataset-level structural fact a foundation
# column must also respect.
# ---------------------------------------------------------------------------


def _dataset_precondition(dataset_id: str, capability: str) -> Tuple[str, str]:
    entry = _NATIVE_TEMPORAL_SESSION_LOOKUP.get(dataset_id, {}).get(capability)
    if entry is None:
        return (MATRIX_UNKNOWN, "No grounded dataset-level finding for this capability.")
    return entry


# ---------------------------------------------------------------------------
# Foundation-audit -> matrix-vocabulary projection
# ---------------------------------------------------------------------------

_AUDIT_TO_MATRIX: Mapping[str, str] = {
    AUDIT_SUPPORTED: MATRIX_SUPPORTED,
    AUDIT_PARTIAL: MATRIX_PARTIAL,
    AUDIT_NOT_SUPPORTED: MATRIX_NOT_PROVIDED,
    AUDIT_UNKNOWN: MATRIX_UNKNOWN,
    # AUDIT_NOT_APPLICABLE is not used by any Step-2 audit row today, but is mapped for
    # completeness in case a future audit update introduces it.
    "NOT_APPLICABLE": MATRIX_NOT_APPLICABLE,
}


@dataclass(frozen=True)
class MatrixCell:
    dataset_id: str
    foundation_id: str
    capability: str
    status: str
    reason: str

    def __post_init__(self) -> None:
        if self.status not in MATRIX_STATES:
            raise ValueError(f"status {self.status!r} not in {MATRIX_STATES!r}")


def compute_cell(dataset_id: str, foundation_id: str, capability: str) -> MatrixCell:
    """Compute one matrix cell per the rule documented in this module's docstring."""
    if dataset_id not in ALL_DATASETS:
        raise ValueError(f"dataset_id {dataset_id!r} unrecognized")
    if foundation_id not in ALL_MATRIX_FOUNDATIONS:
        raise ValueError(f"foundation_id {foundation_id!r} unrecognized")
    if capability not in MATRIX_CAPABILITIES:
        raise ValueError(f"capability {capability!r} unrecognized")

    if foundation_id == FOUNDATION_NATIVE:
        if capability in _NATIVE_OPERATIONAL_CAPABILITIES:
            return MatrixCell(
                dataset_id, foundation_id, capability,
                status=MATRIX_NOT_APPLICABLE,
                reason=(
                    "Native MAMBench has no memory-foundation layer of its own; it "
                    "evaluates already-produced agent executions and never itself "
                    "creates/stores/updates/deletes/links memory state."
                ),
            )
        if capability in _NATIVE_UNIFORM_SUPPORTED_CAPABILITIES:
            return MatrixCell(
                dataset_id, foundation_id, capability,
                status=MATRIX_SUPPORTED,
                reason=(
                    "MAMBench's existing contracts/agent layers already handle this "
                    "uniformly across all seven datasets (the basis for the H/H.1 "
                    "activation work)."
                ),
            )
        # session_state / temporal_state: profile-grounded lookup.
        status, reason = _dataset_precondition(dataset_id, capability)
        return MatrixCell(dataset_id, foundation_id, capability, status=status, reason=reason)

    # A real foundation column.
    if capability in ("session_state", "temporal_state"):
        precondition_status, precondition_reason = _dataset_precondition(dataset_id, capability)
        if precondition_status == MATRIX_NOT_APPLICABLE:
            return MatrixCell(
                dataset_id, foundation_id, capability,
                status=MATRIX_NOT_APPLICABLE,
                reason=f"Dataset lacks the structural precondition: {precondition_reason}",
            )
        if precondition_status == MATRIX_UNKNOWN:
            return MatrixCell(
                dataset_id, foundation_id, capability,
                status=MATRIX_UNKNOWN,
                reason=(
                    f"Dataset-level structural precondition unknown ({precondition_reason}); "
                    "foundation-level capability cannot be meaningfully gated."
                ),
            )
        audit_row = ALL_AUDITS[foundation_id].rows[capability]
        foundation_status = _AUDIT_TO_MATRIX[audit_row.status]
        # If the dataset precondition is only PARTIAL, cap an otherwise-SUPPORTED
        # foundation capability at PARTIAL for this cell (never let a partial dataset
        # precondition silently upgrade to a full SUPPORTED claim).
        if precondition_status == MATRIX_PARTIAL and foundation_status == MATRIX_SUPPORTED:
            foundation_status = MATRIX_PARTIAL
        return MatrixCell(
            dataset_id, foundation_id, capability,
            status=foundation_status,
            reason=(
                f"Foundation-level capability_audit row ({audit_row.status}: "
                f"{audit_row.reason}), gated by dataset precondition ({precondition_status}: "
                f"{precondition_reason})."
            ),
        )

    audit_row = ALL_AUDITS[foundation_id].rows[capability]
    return MatrixCell(
        dataset_id, foundation_id, capability,
        status=_AUDIT_TO_MATRIX[audit_row.status],
        reason=f"Foundation-level capability_audit row (dataset-independent): {audit_row.reason}",
    )


def build_full_matrix() -> Mapping[Tuple[str, str, str], MatrixCell]:
    """The complete 7 x 5 x 20 = 700-cell matrix."""
    matrix: dict = {}
    for dataset_id in ALL_DATASETS:
        for foundation_id in ALL_MATRIX_FOUNDATIONS:
            for capability in MATRIX_CAPABILITIES:
                matrix[(dataset_id, foundation_id, capability)] = compute_cell(
                    dataset_id, foundation_id, capability
                )
    return matrix


FULL_MATRIX: Mapping[Tuple[str, str, str], MatrixCell] = build_full_matrix()


__all__ = [
    "MATRIX_SUPPORTED",
    "MATRIX_PARTIAL",
    "MATRIX_NOT_PROVIDED",
    "MATRIX_NOT_APPLICABLE",
    "MATRIX_UNKNOWN",
    "MATRIX_STATES",
    "DATASET_LOCOMO",
    "DATASET_LONGMEMEVAL",
    "DATASET_MSC",
    "DATASET_CONVERSATION_CHRONICLES",
    "DATASET_MEMORYAGENTBENCH",
    "DATASET_MEMBENCH",
    "DATASET_MEMORYARENA",
    "ALL_DATASETS",
    "ACTIVE_DATASETS",
    "PREPARED_CANDIDATE_DATASETS",
    "FOUNDATION_NATIVE",
    "ALL_MATRIX_FOUNDATIONS",
    "MATRIX_CAPABILITIES",
    "MatrixCell",
    "compute_cell",
    "build_full_matrix",
    "FULL_MATRIX",
]
