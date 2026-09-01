"""Phase 3.3-C -- the SOURCE_MEMORY_ID / ADAPTER_MEMORY_ID / FOUNDATION_MEMORY_ID identity
bridge for real memory foundations, and its collision/uniqueness verification.

WHY THIS MODULE EXISTS -- THE 3.3-B FINDING
--------------------------------------------------------------------------------
The 3.3-B real Mem0 pilot found that Mem0 discards any caller-suggested id at `add()`
time and assigns its own UUID (`RealMem0Adapter`'s own docstring already documents this:
"Mem0's real `add()` does NOT accept or preserve a caller-supplied id at all"). This
means `retrieve()` returns FOUNDATION_MEMORY_IDs that have no textual relationship to a
dataset's SOURCE_MEMORY_ID (e.g. LoCoMo's `memory_id`), so a literal-ID-based check like
Strict TSR (`set(selected) & set(gold_evidence) != empty`) will report a retrieval
failure even when the actually-retrieved CONTENT is correct -- an identity gap, not a
retrieval-quality gap.

THE INVESTIGATION (Part 1 of this stage's mission, performed by direct empirical probing
against the real, installed `mem0ai` library in `C:\\h4venv`, not assumed):

    source memory (LoCoMo memory_records.jsonl row)
        |  RealMem0Adapter.add_memory(memory_id=<ignored>, content, metadata={"source_memory_id": ...})
        v
    Mem0 storage -- assigns its OWN uuid; the metadata dict (INCLUDING any custom key
        like "source_memory_id" that is not one of Mem0's own "promoted" identity keys
        -- user_id/agent_id/run_id/actor_id/role/attributed_to/expiration_date -- which
        ARE special-cased and would NOT survive under this same path) is stored verbatim
        and IS returned, nested under a "metadata" key, by `Memory.get()`.
        v
    RealMem0Adapter.retrieve() -- returns ONLY a bare list of FOUNDATION_MEMORY_ID
        strings (`value=[r["id"] for r in results]`); metadata is NOT included here.
        v
    RealMem0Adapter.inspect_memory(foundation_memory_id) -- DOES return the full
        metadata bucket, VERIFIED DIRECTLY (see this stage's identity/collision probe
        scripts, run against the real library): a memory added with
        metadata={"source_memory_id": "0a2bbeb23bfc6abe6a886f09", ...} is later returned
        by inspect_memory() as
        {"id": "<uuid>", "memory": "...", "metadata": {"source_memory_id":
        "0a2bbeb23bfc6abe6a886f09", ...}, ...} -- exact, lossless, verbatim round-trip.

CONCLUSION: the identity bridge requires ZERO modification to `RealMem0Adapter` or to
`MemoryFoundationAdapter`. `inspect_memory()` -- an existing, already-abstract-interface
method every foundation adapter must implement -- is sufficient. This module is a pure,
additive, foundation-agnostic consumer of that existing method; it adds no new adapter
method, no new abstraction, and does not touch `phase3/evaluation/foundations/adapter.py`
or `phase3/evaluation/foundations_real/mem0_real_adapter.py` at all.

`agent_runtime/runner.py` already calls `inspect_memory()` for every selected id (to get
displayable content) -- this module's `resolve_source_identity()` reuses that SAME call
shape so a pilot never has to make an extra foundation round-trip solely for identity
resolution; see `pilot_mem0_locomo_resolved.py` for where the two are combined in one
pass.

WHAT THIS MODULE DOES NOT DO (the mission's explicit prohibitions)
--------------------------------------------------------------------------------
No text similarity, no embedding similarity, no LLM judgment, no positional/nearest-
neighbor guessing is used anywhere in this module to establish an identity mapping. The
ONLY signal ever consulted is the literal, explicit `metadata["source_memory_id"]` value
a caller supplied at ingestion time. If that key is absent (verified directly: Mem0
represents "no extra metadata beyond promoted keys" as a literal `metadata: None` on the
returned record, not an empty dict, not an inferred guess), the resolution is reported
`NOT_RESOLVABLE` -- never fabricated, never silently defaulted to the FOUNDATION_MEMORY_ID
itself standing in for the source id.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from phase3.evaluation.foundations.adapter import (
    FOUNDATION_AVAILABLE,
    FOUNDATION_PARTIAL,
    MemoryFoundationAdapter,
)

# ---------------------------------------------------------------------------
# Identity namespace vocabulary (Part 2 of the 3.3-C mission; extends, without
# modifying, the informal convention PHASE3_3_EXPERIMENTAL_SPEC.md Part 19 introduced).
# These are field-name / label constants, never conflated with each other and never
# collapsed into a single generic "memory_id".
# ---------------------------------------------------------------------------

SOURCE_MEMORY_ID = "SOURCE_MEMORY_ID"
ADAPTER_MEMORY_ID = "ADAPTER_MEMORY_ID"
FOUNDATION_MEMORY_ID = "FOUNDATION_MEMORY_ID"
GOLD_EVIDENCE_ID = "GOLD_EVIDENCE_ID"
EXPERIMENT_ID = "EXPERIMENT_ID"

# Resolution status vocabulary -- deliberately small and honest. No "GUESSED" status
# exists because guessing is prohibited outright, not merely discouraged.
STATUS_RESOLVED = "RESOLVED"
STATUS_NOT_RESOLVABLE = "NOT_RESOLVABLE"  # metadata key genuinely absent
STATUS_INSPECT_UNAVAILABLE = "INSPECT_UNAVAILABLE"  # foundation could not even be asked

# Resolution STRATEGY vocabulary -- Phase 3.3-D. Two genuinely different, foundation-
# native identity mechanisms were found by direct empirical investigation (never
# assumed): Mem0 always assigns its own opaque id and requires a post-hoc metadata
# lookup to recover source identity; Graphiti's EntityNode and A-mem-sys's MemoryNote
# both accept and HONOR a caller-supplied id directly (verified: `add_memory()`'s
# returned `requested_id_honored` is `True` for both, against the real libraries), so
# their source identity is established AT INGESTION, with no lookup needed at all. Both
# strategies produce the SAME `IdentityResolution` shape -- this is the "one common
# contract, foundation-specific implementation" the 3.3-D mission asks for: no separate
# Mem0IdentityAdapter/GraphitiIdentityAdapter/AMEMIdentityAdapter classes exist.
STRATEGY_METADATA_LOOKUP = "METADATA_LOOKUP"  # Mem0
STRATEGY_DIRECT_ASSIGNMENT = "DIRECT_ASSIGNMENT"  # Graphiti, A-MEM


@dataclass(frozen=True)
class IdentityResolution:
    """One FOUNDATION_MEMORY_ID's resolved (or honestly unresolved) identity chain.

    `adapter_memory_id` is the id the CALLER suggested to `add_memory()` -- recorded here
    even though, for Mem0 specifically, it is always ignored by the real library (see
    module docstring) -- so a trace can show "what we asked for" distinctly from "what we
    got," per the mission's namespace-preservation requirement.

    `strategy` records WHICH mechanism produced this resolution (Phase 3.3-D addition,
    backward-compatible default of METADATA_LOOKUP so every 3.3-C call site that never
    passed this field keeps working unchanged).
    """

    foundation_memory_id: str
    adapter_memory_id: Optional[str]
    source_memory_id: Optional[str]
    status: str
    metadata_snapshot: Mapping[str, Any] = field(default_factory=dict)
    strategy: str = STRATEGY_METADATA_LOOKUP

    def __post_init__(self) -> None:
        valid = (STATUS_RESOLVED, STATUS_NOT_RESOLVABLE, STATUS_INSPECT_UNAVAILABLE)
        if self.status not in valid:
            raise ValueError(f"status {self.status!r} is not one of {valid!r}")
        if self.status == STATUS_RESOLVED and self.source_memory_id is None:
            raise ValueError("status=RESOLVED requires a non-None source_memory_id")
        if self.status != STATUS_RESOLVED and self.source_memory_id is not None:
            raise ValueError(
                f"status={self.status!r} must not carry a non-None source_memory_id "
                "-- an unresolved identity must never smuggle a value through."
            )
        valid_strategies = (STRATEGY_METADATA_LOOKUP, STRATEGY_DIRECT_ASSIGNMENT)
        if self.strategy not in valid_strategies:
            raise ValueError(f"strategy {self.strategy!r} is not one of {valid_strategies!r}")


def resolve_source_identity(
    foundation: MemoryFoundationAdapter,
    foundation_memory_id: str,
    *,
    adapter_memory_id: Optional[str] = None,
    metadata_key: str = "source_memory_id",
) -> IdentityResolution:
    """Resolve ONE foundation memory id's source identity via `inspect_memory()` only.

    Deterministic, lossless-when-present, and honest-when-absent by construction: this
    function performs exactly one foundation call and one dict lookup. There is no retry,
    no fallback heuristic, and no code path that returns a non-None `source_memory_id`
    without that exact literal value having come from the foundation's own stored
    metadata.
    """
    inspect_field = foundation.inspect_memory(foundation_memory_id)
    if inspect_field.availability not in (FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL):
        return IdentityResolution(
            foundation_memory_id=foundation_memory_id,
            adapter_memory_id=adapter_memory_id,
            source_memory_id=None,
            status=STATUS_INSPECT_UNAVAILABLE,
        )

    native = inspect_field.value or {}
    metadata = native.get("metadata") if isinstance(native, Mapping) else None
    # Verified directly (see module docstring): Mem0 represents "no extra metadata"
    # as a literal `None`, not `{}` -- both are handled identically here (honest
    # absence), but neither is ever treated as "try something else."
    source_id = metadata.get(metadata_key) if isinstance(metadata, Mapping) else None

    if source_id is None:
        return IdentityResolution(
            foundation_memory_id=foundation_memory_id,
            adapter_memory_id=adapter_memory_id,
            source_memory_id=None,
            status=STATUS_NOT_RESOLVABLE,
            metadata_snapshot=dict(metadata) if isinstance(metadata, Mapping) else {},
        )

    return IdentityResolution(
        foundation_memory_id=foundation_memory_id,
        adapter_memory_id=adapter_memory_id,
        source_memory_id=str(source_id),
        status=STATUS_RESOLVED,
        metadata_snapshot=dict(metadata) if isinstance(metadata, Mapping) else {},
    )


def resolve_source_identities(
    foundation: MemoryFoundationAdapter,
    foundation_memory_ids: Sequence[str],
    *,
    adapter_memory_ids: Optional[Mapping[str, str]] = None,
    metadata_key: str = "source_memory_id",
) -> Dict[str, IdentityResolution]:
    """Batch form of `resolve_source_identity`, one real foundation call per id (no
    foundation exposes a batch-inspect operation in this framework's interface, so this
    is a plain loop, not a hidden optimization that would need separate verification)."""
    adapter_memory_ids = adapter_memory_ids or {}
    return {
        fid: resolve_source_identity(
            foundation, fid, adapter_memory_id=adapter_memory_ids.get(fid), metadata_key=metadata_key
        )
        for fid in foundation_memory_ids
    }


def resolve_via_direct_assignment(
    requested_source_id: Optional[str],
    add_memory_result_value: Mapping[str, Any],
) -> IdentityResolution:
    """Phase 3.3-D -- the second identity strategy, for foundations that accept and can
    HONOR a caller-supplied id at `add_memory()` time (Graphiti's `EntityNode.uuid`,
    A-mem-sys's `MemoryNote.id` -- both empirically verified against the real,
    installed libraries: `add_memory()`'s returned
    `{"memory_id": ..., "requested_id_honored": ...}` shape, already produced by
    `RealGraphitiAdapter`/`RealAMemAdapter` unmodified, is exactly what this function
    consumes).

    Unlike `resolve_source_identity()` (METADATA_LOOKUP), this performs NO foundation
    call of its own -- the identity was established (or not) at the moment `add_memory()`
    returned, so resolution here is a pure, local, deterministic check of that already-
    real result. This is honest specifically because it only ever reports RESOLVED when
    `requested_id_honored` is literally `True` -- if a foundation silently assigned its
    own id despite a request (which neither Graphiti nor A-mem-sys did in this stage's
    direct testing, but a caller must never assume this is universal for every
    configuration), this reports NOT_RESOLVABLE, never assuming success.
    """
    foundation_memory_id = add_memory_result_value.get("memory_id")
    honored = add_memory_result_value.get("requested_id_honored")

    if requested_source_id and honored is True:
        return IdentityResolution(
            foundation_memory_id=foundation_memory_id,
            adapter_memory_id=requested_source_id,
            source_memory_id=requested_source_id,
            status=STATUS_RESOLVED,
            strategy=STRATEGY_DIRECT_ASSIGNMENT,
        )
    return IdentityResolution(
        foundation_memory_id=foundation_memory_id,
        adapter_memory_id=requested_source_id,
        source_memory_id=None,
        status=STATUS_NOT_RESOLVABLE,
        strategy=STRATEGY_DIRECT_ASSIGNMENT,
    )


# ---------------------------------------------------------------------------
# Collision / uniqueness verification (Part 4)
# ---------------------------------------------------------------------------

DUPLICATE_SOURCE_MAPPING = "DUPLICATE_SOURCE_MAPPING"  # >1 foundation id resolved to the
# SAME source_memory_id within the checked set -- reported, never silently collapsed.


@dataclass(frozen=True)
class CollisionReport:
    """Result of checking a set of `IdentityResolution`s for the specific collision
    shape Part 4 of the 3.3-C mission asks about: one source id silently mapping to
    multiple UNRELATED foundation records within the set actually used by one run.

    NOTE on scope: this checks collisions only within the resolutions it is given (e.g.
    the retrieved-and-selected set for one query, or one full ingestion batch) -- it does
    NOT claim global uniqueness across a foundation's entire, unbounded store, which no
    adapter in this framework exposes a cheap way to enumerate. This scope limitation is
    stated explicitly in `note`, never silently assumed away.
    """

    collision_free: bool
    duplicate_source_ids: Mapping[str, Tuple[str, ...]]  # source_id -> (foundation_ids,)
    resolved_count: int
    not_resolvable_count: int
    inspect_unavailable_count: int
    note: str


def verify_collision_safety(resolutions: Mapping[str, IdentityResolution]) -> CollisionReport:
    """Check the specific collision condition Part 4 asks about, over exactly the
    resolutions supplied -- see `CollisionReport`'s docstring for the scope limitation.
    """
    by_source: Dict[str, list] = {}
    not_resolvable = 0
    inspect_unavailable = 0
    for foundation_id, resolution in resolutions.items():
        if resolution.status == STATUS_RESOLVED:
            by_source.setdefault(resolution.source_memory_id, []).append(foundation_id)
        elif resolution.status == STATUS_NOT_RESOLVABLE:
            not_resolvable += 1
        else:
            inspect_unavailable += 1

    duplicates = {
        source_id: tuple(sorted(fids)) for source_id, fids in by_source.items() if len(fids) > 1
    }

    return CollisionReport(
        collision_free=not duplicates,
        duplicate_source_ids=duplicates,
        resolved_count=sum(1 for r in resolutions.values() if r.status == STATUS_RESOLVED),
        not_resolvable_count=not_resolvable,
        inspect_unavailable_count=inspect_unavailable,
        note=(
            "Collision check scoped to the supplied resolution set only, not the "
            "foundation's entire store (no adapter in this framework exposes a cheap "
            "full-store enumeration). A duplicate here means the SAME source_memory_id "
            "metadata value was found on more than one distinct FOUNDATION_MEMORY_ID "
            "within this set -- e.g. from re-ingesting the same source record without an "
            "intervening RESET, a real, observed behavior of Mem0's real add() path "
            "(verified directly: Mem0 does not deduplicate on repeated add() calls with "
            "infer=False, even for byte-identical content -- each call creates a new, "
            "distinct FOUNDATION_MEMORY_ID)."
        ),
    )


__all__ = [
    "SOURCE_MEMORY_ID",
    "ADAPTER_MEMORY_ID",
    "FOUNDATION_MEMORY_ID",
    "GOLD_EVIDENCE_ID",
    "EXPERIMENT_ID",
    "STATUS_RESOLVED",
    "STATUS_NOT_RESOLVABLE",
    "STATUS_INSPECT_UNAVAILABLE",
    "STRATEGY_METADATA_LOOKUP",
    "STRATEGY_DIRECT_ASSIGNMENT",
    "IdentityResolution",
    "resolve_source_identity",
    "resolve_source_identities",
    "resolve_via_direct_assignment",
    "DUPLICATE_SOURCE_MAPPING",
    "CollisionReport",
    "verify_collision_safety",
]
