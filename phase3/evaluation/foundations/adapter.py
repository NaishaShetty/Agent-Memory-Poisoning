"""Phase 3.2-H.3 (Memory Foundation Integration Architecture) -- `MemoryFoundationAdapter`,
the common interface a memory-foundation integration (Mem0, Letta, Graphiti, A-MEM, or a
future fifth) would implement.

WHY THIS MODULE EXISTS
--------------------------------------------------------------------------------
`phase3/evaluation/extensions/adapters/base.py`'s `DatasetAdapter` is a READ-ONLY accessor
interface over an already-normalized dataset record -- it never performs any memory
operation (no add/retrieve/update/delete), because a *dataset* has no lifecycle of its own.
A *memory foundation* is different in kind: Mem0/Letta/Graphiti/A-MEM are STATEFUL systems
with genuine operations (create, retrieve, update, delete, inspect, export, reset). This
module's `MemoryFoundationAdapter` is the interface for THAT different kind of thing, built
to mirror `DatasetAdapter`'s never-fabricating discipline exactly:

- Every method returns a `FoundationField` (this module's analogue of
  `extensions.adapters.base.AdapterField`), never a bare value.
- An operation a foundation genuinely does not support (per the Step 2 audit in
  `capability_audit.py`) reports `FOUNDATION_NOT_SUPPORTED`, never a silent
  `0`/`False`/`[]`/`None` standing in for "not supported."
- A foundation's documented "successfully did X, nothing more to report" semantic (e.g. a
  delete of an already-absent id returning an empty confirmation) is represented as
  `FOUNDATION_AVAILABLE` with an explicit, documented `note` -- this is deliberately
  DIFFERENT from `FOUNDATION_NOT_SUPPORTED`, per the task brief's explicit instruction not
  to conflate "operation not supported at all" with "operation supported, this is its
  genuine empty/no-op result."

STATUS VOCABULARY -- reuses `phase3.evaluation.datasets.capability.CAPABILITY_STATES`
verbatim, extended by exactly one new value
--------------------------------------------------------------------------------
`CAPABILITY_STATES` (AVAILABLE/PARTIAL/UNAVAILABLE/UNKNOWN/NOT_PROVIDED_BY_SOURCE/
PROVISIONAL) already answers almost everything a `FoundationField` needs to say. The one
genuine gap: `NOT_PROVIDED_BY_SOURCE` reads, by name, as "this DATASET RECORD source lacks
this field" -- reusing it verbatim for "this FOUNDATION's architecture lacks this
operation entirely" would be a confusing overload of a name that already means something
dataset-specific elsewhere in this codebase. This module therefore adds exactly ONE new
value, `FOUNDATION_NOT_SUPPORTED_BY_ARCHITECTURE`, documented here as the foundation-level
analogue of `NOT_PROVIDED_BY_SOURCE` -- every other value (AVAILABLE, PARTIAL, UNAVAILABLE,
UNKNOWN, PROVISIONAL) is reused with its EXACT existing meaning, unchanged.

Pure interface/dataclass module: the abstract methods below prescribe a contract; no
concrete implementation, no network/LLM/embeddings access, no randomness. Concrete
implementations (the four Mock* adapters under `foundations/mocks/`) are deterministic
test doubles only -- see that package's module docstring for the MOCK_CONFORMANCE
discipline.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence, Tuple

from phase3.evaluation.datasets.capability import (
    CAPABILITY_AVAILABLE,
    CAPABILITY_PARTIAL,
    CAPABILITY_PROVISIONAL,
    CAPABILITY_STATES,
    CAPABILITY_UNAVAILABLE,
    CAPABILITY_UNKNOWN,
)

# ---------------------------------------------------------------------------
# Status vocabulary: CAPABILITY_STATES reused verbatim + exactly one new value.
# ---------------------------------------------------------------------------

FOUNDATION_NOT_SUPPORTED_BY_ARCHITECTURE = "NOT_SUPPORTED_BY_ARCHITECTURE"

FOUNDATION_FIELD_STATES: Tuple[str, ...] = tuple(CAPABILITY_STATES) + (
    FOUNDATION_NOT_SUPPORTED_BY_ARCHITECTURE,
)

# Re-exported so callers of this module do not need a separate import of
# datasets.capability just to spell the reused constants.
FOUNDATION_AVAILABLE = CAPABILITY_AVAILABLE
FOUNDATION_PARTIAL = CAPABILITY_PARTIAL
FOUNDATION_UNAVAILABLE = CAPABILITY_UNAVAILABLE
FOUNDATION_UNKNOWN = CAPABILITY_UNKNOWN
FOUNDATION_PROVISIONAL = CAPABILITY_PROVISIONAL


@dataclass(frozen=True)
class FoundationField:
    """One never-fabricating accessor/operation result from a `MemoryFoundationAdapter`
    method. Mirrors `extensions.adapters.base.AdapterField`'s discipline exactly, adapted
    to a stateful-operation interface rather than a read-only dataset-record interface.

    Attributes
    ----------
    value:
        The operation's result, or `None` if `availability` is not AVAILABLE/PARTIAL.
    availability:
        One of `FOUNDATION_FIELD_STATES`.
    operation:
        The literal adapter method name this result came from (e.g. `"add_memory"`) --
        always traceable, never a bare "unknown."
    note:
        Human-readable explanation, always populated when `availability` is not AVAILABLE.
    """

    value: Any
    availability: str
    operation: str = "NONE"
    note: str = ""

    def __post_init__(self) -> None:
        if self.availability not in FOUNDATION_FIELD_STATES:
            raise ValueError(
                f"availability {self.availability!r} is not one of {FOUNDATION_FIELD_STATES!r}"
            )


@dataclass(frozen=True)
class FoundationIdentity:
    """Static identity record for one foundation adapter instance.

    `status` is always `PREPARED_CANDIDATE` for all four foundations at this stage (see
    `phase3.evaluation.foundations.registry`) -- never `ACTIVE`, which is reserved for a
    future H.4 real-conformance stage.
    """

    foundation_id: str
    foundation_name: str
    adapter_version: str
    status: str


class MemoryFoundationAdapter(abc.ABC):
    """Common interface a memory-foundation integration implements.

    Every method returns `FoundationField` (or, for `capabilities()`/`foundation_identity()`,
    a typed record) -- never a bare value -- so "the foundation's architecture does not "
    "support this at all" (`FOUNDATION_NOT_SUPPORTED_BY_ARCHITECTURE`), "supported for some "
    "but not all inputs" (`FOUNDATION_PARTIAL`), and "supported" (`FOUNDATION_AVAILABLE`) "
    are always distinguishable, never collapsed into a bare `0`/`False`/`[]`/`None`.
    """

    @abc.abstractmethod
    def foundation_identity(self) -> FoundationIdentity:
        """Static identity: which foundation, which adapter version, and its
        `PREPARED_CANDIDATE`/`ACTIVE` status."""

    @abc.abstractmethod
    def capabilities(self) -> Mapping[str, Any]:
        """The capability audit for this foundation (a read-only passthrough of the
        relevant `capability_audit.FoundationAudit`) -- this method never recomputes or
        overrides what the Step 2 audit already determined."""

    @abc.abstractmethod
    def initialize(self, configuration: Mapping[str, Any]) -> FoundationField:
        """Bring the adapter into a ready-to-use state given a configuration mapping.
        `configuration` must never contain a secret/key/token-shaped field -- see
        `fingerprinting.reject_secrets`."""

    @abc.abstractmethod
    def reset(self) -> FoundationField:
        """Clear all foundation-held state for this adapter instance back to empty. See
        `phase3.evaluation.foundations.reset_isolation` for the A->B->A verification
        pattern this supports."""

    @abc.abstractmethod
    def add_memory(
        self,
        memory_id: Optional[str],
        content: Mapping[str, Any],
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> FoundationField:
        """Create one memory item. `memory_id` is a caller-suggested id; a foundation
        whose architecture assigns its own ids (documented, not assumed) may return a
        DIFFERENT id in the result -- callers must read the returned id from `value`,
        never assume it echoes the id passed in."""

    @abc.abstractmethod
    def retrieve(
        self,
        query: Mapping[str, Any],
        top_k: Optional[int] = None,
    ) -> FoundationField:
        """Retrieve memory items relevant to `query`. The returned `value`, when
        AVAILABLE/PARTIAL, is expected to be an ORDER-PRESERVING sequence (ranked-order
        semantics, if the foundation documents any) -- see
        `foundations.mocks`'s dedicated order-preservation tests."""

    @abc.abstractmethod
    def update_memory(
        self,
        memory_id: str,
        content: Mapping[str, Any],
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> FoundationField:
        """Update an existing memory item's content/metadata."""

    @abc.abstractmethod
    def delete_memory(self, memory_id: str) -> FoundationField:
        """Delete one memory item. See the module docstring for the AVAILABLE-vs-
        NOT_SUPPORTED_BY_ARCHITECTURE distinction this must preserve."""

    @abc.abstractmethod
    def inspect_memory(self, memory_id: str) -> FoundationField:
        """Return whatever lifecycle/introspection detail the foundation exposes for one
        memory item (e.g. its current linked/related memories, its temporal validity, its
        last-updated timestamp) -- shape is foundation-native, not flattened."""

    @abc.abstractmethod
    def export_state(self) -> FoundationField:
        """Return a full, foundation-native snapshot of all memory state currently held by
        this adapter instance. Used by `reset_isolation`'s A->B->A comparison and by
        `fingerprinting.fingerprint_state`."""

    @abc.abstractmethod
    def normalize_trace(self, operation_result: FoundationField) -> Mapping[str, Any]:
        """Project one `FoundationField` operation result into a
        `trace.FoundationTraceArtifact`-shaped mapping (see `trace.py`) -- the one place a
        foundation-native result is translated into this framework's common trace shape,
        without discarding foundation-native structure (e.g. Graphiti's relationship
        richness is preserved as a nested field, never flattened into a bare list)."""

    @abc.abstractmethod
    def shutdown(self) -> FoundationField:
        """Release any adapter-held resources. For a mock/in-memory adapter this is
        typically a no-op reported as AVAILABLE; a real foundation integration (H.4) might
        close a network/database connection here."""


__all__ = [
    "FOUNDATION_NOT_SUPPORTED_BY_ARCHITECTURE",
    "FOUNDATION_FIELD_STATES",
    "FOUNDATION_AVAILABLE",
    "FOUNDATION_PARTIAL",
    "FOUNDATION_UNAVAILABLE",
    "FOUNDATION_UNKNOWN",
    "FOUNDATION_PROVISIONAL",
    "FoundationField",
    "FoundationIdentity",
    "MemoryFoundationAdapter",
]
