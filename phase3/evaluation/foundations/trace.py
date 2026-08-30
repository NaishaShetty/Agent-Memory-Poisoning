"""Phase 3.2-H.3 (Memory Foundation Integration Architecture) -- `FoundationTraceArtifact`:
a plain-dict trace shape capturing one foundation-adapter operation, for downstream
evaluation consumption.

WHY A NEW, SEPARATE, ADDITIVE STRUCTURE -- NOT AN EXTENSION OF
`phase3/evaluation/contracts/trace_artifact.schema.json`
--------------------------------------------------------------------------------
`trace_artifact.schema.json` is an existing, protected contract surface (per this stage's
protection rules: "any existing `phase3/evaluation/{contracts,...}` file... additive only
from here"). Extending it to add foundation-specific fields would be a PROTECTED-SURFACE
change requiring the STOP-and-report discipline. This module instead defines a genuinely
NEW, separate, additive structure -- `FoundationTraceArtifact` -- that a future H.4 stage
could, if it chooses, reconcile with `trace_artifact.schema.json` (or leave permanently
separate, since a foundation operation trace and an evaluation-run trace answer different
questions). No existing schema file is read, imported, modified, or referenced by this
module.

WHY A PLAIN DATACLASS, NOT A JSON SCHEMA
--------------------------------------------------------------------------------
Mirrors `security/reproducibility.py`'s own "why a dict, not a dataclass" reasoning in
spirit but makes the opposite choice for the opposite reason: every field below must be
representable as EXPLICITLY ABSENT (a foundation genuinely does not expose retrieval
scores, say) as distinct from "present but empty" or "present as None for another reason."
A frozen dataclass with `Optional[...] = None` defaults, paired with a companion
`present: FrozenSet[str]` field recording which fields the adapter actually populated
(vs. left at their absent-default), makes "explicitly absent" a directly-inspectable,
type-checked case -- exactly the same guarantee `AdapterField`/`FoundationField`'s
`availability` gives per-field, applied here to a whole trace record. A JSON Schema was
considered and rejected for this stage: schema authorship/validation wiring is out of
scope for what Step 2's audit actually justifies building right now (no foundation is
really running), and a dataclass is sufecient to satisfy every test in Step 7.

Pure dataclass module: no filesystem/network/LLM/embeddings access, no randomness.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, FrozenSet, Mapping, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Operation-type vocabulary (mirrors MemoryFoundationAdapter's method names)
# ---------------------------------------------------------------------------

OPERATION_INITIALIZE = "INITIALIZE"
OPERATION_RESET = "RESET"
OPERATION_ADD_MEMORY = "ADD_MEMORY"
OPERATION_RETRIEVE = "RETRIEVE"
OPERATION_UPDATE_MEMORY = "UPDATE_MEMORY"
OPERATION_DELETE_MEMORY = "DELETE_MEMORY"
OPERATION_INSPECT_MEMORY = "INSPECT_MEMORY"
OPERATION_EXPORT_STATE = "EXPORT_STATE"
OPERATION_SHUTDOWN = "SHUTDOWN"

ALL_OPERATIONS: Tuple[str, ...] = (
    OPERATION_INITIALIZE,
    OPERATION_RESET,
    OPERATION_ADD_MEMORY,
    OPERATION_RETRIEVE,
    OPERATION_UPDATE_MEMORY,
    OPERATION_DELETE_MEMORY,
    OPERATION_INSPECT_MEMORY,
    OPERATION_EXPORT_STATE,
    OPERATION_SHUTDOWN,
)

# ---------------------------------------------------------------------------
# Phase 4 attack-surface stage vocabulary (identification only -- see module docstring
# in `phase4_attack_surface.py`... actually declared here since the trace IS where each
# interception point becomes an identifiable field/stage, per the task brief's Step 7
# requirement: "assert the trace/lifecycle model has an identifiable field/stage for each
# of the listed interception points").
# ---------------------------------------------------------------------------

ATTACK_SURFACE_INPUT_INGESTION = "INPUT_INGESTION"
ATTACK_SURFACE_MEMORY_CREATION = "MEMORY_CREATION"
ATTACK_SURFACE_MEMORY_UPDATE = "MEMORY_UPDATE"
ATTACK_SURFACE_MEMORY_LINKING = "MEMORY_LINKING"
ATTACK_SURFACE_STORAGE = "STORAGE"
ATTACK_SURFACE_RETRIEVAL = "RETRIEVAL"
ATTACK_SURFACE_SELECTION = "SELECTION"
ATTACK_SURFACE_AGENT_CONTEXT = "AGENT_CONTEXT"

ALL_ATTACK_SURFACE_STAGES: Tuple[str, ...] = (
    ATTACK_SURFACE_INPUT_INGESTION,
    ATTACK_SURFACE_MEMORY_CREATION,
    ATTACK_SURFACE_MEMORY_UPDATE,
    ATTACK_SURFACE_MEMORY_LINKING,
    ATTACK_SURFACE_STORAGE,
    ATTACK_SURFACE_RETRIEVAL,
    ATTACK_SURFACE_SELECTION,
    ATTACK_SURFACE_AGENT_CONTEXT,
)

# Which operation(s) each attack-surface stage maps onto -- identification only, per the
# task brief's explicit instruction not to implement any attack here (Phase 4 scope).
ATTACK_SURFACE_OPERATION_MAP: Mapping[str, Tuple[str, ...]] = {
    ATTACK_SURFACE_INPUT_INGESTION: (OPERATION_ADD_MEMORY,),
    ATTACK_SURFACE_MEMORY_CREATION: (OPERATION_ADD_MEMORY,),
    ATTACK_SURFACE_MEMORY_UPDATE: (OPERATION_UPDATE_MEMORY,),
    ATTACK_SURFACE_MEMORY_LINKING: (OPERATION_ADD_MEMORY, OPERATION_UPDATE_MEMORY),
    ATTACK_SURFACE_STORAGE: (OPERATION_ADD_MEMORY, OPERATION_EXPORT_STATE),
    ATTACK_SURFACE_RETRIEVAL: (OPERATION_RETRIEVE,),
    ATTACK_SURFACE_SELECTION: (OPERATION_RETRIEVE,),
    ATTACK_SURFACE_AGENT_CONTEXT: (OPERATION_RETRIEVE,),
}


@dataclass(frozen=True)
class FoundationTraceArtifact:
    """One foundation-adapter operation, traced.

    Every field beyond `foundation_id`/`adapter_version`/`operation`/`timestamp` is
    OPTIONAL and may be legitimately absent -- `present` records which optional fields
    this specific trace actually populated, so "absent because the foundation doesn't
    expose this" is directly checkable (`"native_scores" not in trace.present`) without
    relying on `None` (which could otherwise mean either "absent" or "present, and the
    value genuinely is None").
    """

    foundation_id: str
    adapter_version: str
    operation: str
    timestamp: str

    input_ids: Tuple[str, ...] = field(default_factory=tuple)
    output_ids: Tuple[str, ...] = field(default_factory=tuple)
    memory_ids: Tuple[str, ...] = field(default_factory=tuple)
    retrieval_ordering: Tuple[str, ...] = field(default_factory=tuple)
    native_scores: Optional[Mapping[str, float]] = None
    metadata: Optional[Mapping[str, Any]] = None
    state_fingerprint: Optional[str] = None
    configuration_fingerprint: Optional[str] = None
    agent_visible_boundary_marker: Optional[str] = None
    errors: Tuple[str, ...] = field(default_factory=tuple)
    unsupported_operation_markers: Tuple[str, ...] = field(default_factory=tuple)
    lifecycle_state: Optional[str] = None
    attack_surface_stage: Optional[str] = None
    conformance_tag: str = "MOCK_CONFORMANCE"

    present: FrozenSet[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if self.operation not in ALL_OPERATIONS:
            raise ValueError(f"operation {self.operation!r} is not one of {ALL_OPERATIONS!r}")
        if self.attack_surface_stage is not None and self.attack_surface_stage not in ALL_ATTACK_SURFACE_STAGES:
            raise ValueError(
                f"attack_surface_stage {self.attack_surface_stage!r} is not one of "
                f"{ALL_ATTACK_SURFACE_STAGES!r}"
            )
        if self.conformance_tag not in ("MOCK_CONFORMANCE",):
            # Deliberately the ONLY permitted value at this stage -- see module docstring
            # of `foundations/mocks/__init__.py` for the full MOCK_CONFORMANCE-vs-
            # REAL_FOUNDATION_CONFORMANCE discipline this enforces structurally.
            raise ValueError(
                f"conformance_tag must be 'MOCK_CONFORMANCE' at this stage; got "
                f"{self.conformance_tag!r}. REAL_FOUNDATION_CONFORMANCE is not achievable "
                "anywhere in this framework-architecture stage (no real foundation runs)."
            )


def build_trace(
    foundation_id: str,
    adapter_version: str,
    operation: str,
    timestamp: str,
    **optional_fields: Any,
) -> FoundationTraceArtifact:
    """Construct a `FoundationTraceArtifact`, recording in `present` exactly which optional
    fields were supplied (so `trace.present` never silently claims a field is populated
    when the caller never set it, and never silently claims a field is absent when the
    caller passed an explicit falsy-but-meaningful value like an empty tuple).
    """
    recognized_optional = {
        "input_ids",
        "output_ids",
        "memory_ids",
        "retrieval_ordering",
        "native_scores",
        "metadata",
        "state_fingerprint",
        "configuration_fingerprint",
        "agent_visible_boundary_marker",
        "errors",
        "unsupported_operation_markers",
        "lifecycle_state",
        "attack_surface_stage",
        "conformance_tag",
    }
    unknown = set(optional_fields.keys()) - recognized_optional
    if unknown:
        raise ValueError(f"build_trace() got unrecognized optional field(s): {sorted(unknown)!r}")

    present = frozenset(optional_fields.keys())
    return FoundationTraceArtifact(
        foundation_id=foundation_id,
        adapter_version=adapter_version,
        operation=operation,
        timestamp=timestamp,
        present=present,
        **optional_fields,
    )


__all__ = [
    "OPERATION_INITIALIZE",
    "OPERATION_RESET",
    "OPERATION_ADD_MEMORY",
    "OPERATION_RETRIEVE",
    "OPERATION_UPDATE_MEMORY",
    "OPERATION_DELETE_MEMORY",
    "OPERATION_INSPECT_MEMORY",
    "OPERATION_EXPORT_STATE",
    "OPERATION_SHUTDOWN",
    "ALL_OPERATIONS",
    "ATTACK_SURFACE_INPUT_INGESTION",
    "ATTACK_SURFACE_MEMORY_CREATION",
    "ATTACK_SURFACE_MEMORY_UPDATE",
    "ATTACK_SURFACE_MEMORY_LINKING",
    "ATTACK_SURFACE_STORAGE",
    "ATTACK_SURFACE_RETRIEVAL",
    "ATTACK_SURFACE_SELECTION",
    "ATTACK_SURFACE_AGENT_CONTEXT",
    "ALL_ATTACK_SURFACE_STAGES",
    "ATTACK_SURFACE_OPERATION_MAP",
    "FoundationTraceArtifact",
    "build_trace",
]
