"""Phase 3.3-H.1 (Canonical Memory Ledger) -- the authoritative write boundary.

Orchestrates the write order the mission requires:

    1. construct/validate CanonicalMemoryRecord (phase3.evaluation.foundations.canonical)
    2. write it to the CanonicalMemoryLedger (phase3.evaluation.foundations.ledger)
    3. call the foundation adapter (EXISTING, UNCHANGED `MemoryFoundationAdapter.add_memory`
       interface -- see "WHY NO ADAPTER INTERFACE CHANGE" below)
    4. record the vendor id as an alias
    5. return a `CanonicalWriteResult` that distinguishes every partial-failure shape

WHY NO ADAPTER INTERFACE CHANGE
--------------------------------------------------------------------------------
The H.1 mission's PREFERRED contract is `add_memory(record: CanonicalMemoryRecord)`, but
also explicitly requires auditing every implementation/caller first and, if changing the
public interface would break too many existing surfaces, introducing an explicit,
documented, deprecated, tested compatibility layer instead of a breaking change.

The audit (`PHASE3_3_H1_CANONICAL_MEMORY_LEDGER.md` section 2) found:

- FOUR concrete real adapters (`foundations_real/{mem0,amem,graphiti,letta}_real_adapter.py`)
  and FOUR mock adapters (`foundations/mocks/mock_*.py`), all implementing the existing
  `add_memory(memory_id, content, metadata)` signature.
- `phase3/evaluation/agent_runtime/campaign_formal_runner.py` calls `add_memory()` directly
  with this signature and, AT THE TIME OF THIS STAGE, has live worker processes running the
  3.3-G.1 A-MEM x LongMemEval N=120 campaign against `RealAMemAdapter` (verified via `ps`/
  `Get-CimInstance Win32_Process` before any code was written -- see the implementation
  report). The mission's explicit STOP condition #3 ("H.1 requires changes to the currently
  running G.1 process") and its instruction to prefer "additive implementation followed by
  controlled migration/testing" both point the same direction: changing
  `MemoryFoundationAdapter.add_memory`'s signature would require editing every
  implementation, INCLUDING `amem_real_adapter.py`, which is presently on this process's
  live execution path.

This module therefore introduces `write_canonical_memory()` as an explicit, documented
TRANSITIONAL WRAPPER: it consumes a `CanonicalMemoryRecord` as its authoritative input (the
mission's actual architectural goal -- the canonical record, not a bare triple, is what a
caller constructs and validates), and translates it into exactly the existing
`add_memory(memory_id, content, metadata)` call underneath. Every foundation adapter (real
and mock) therefore already "speaks" this contract with ZERO modification to any adapter
file -- see the implementation report's per-foundation status table. This wrapper is the
ONLY authoritative write path this stage recommends adopting; existing direct
`foundation.add_memory(...)` call sites are left untouched (deliberately -- migrating them
is deferred to a later, manually-reviewed stage per the mission's G.1-non-disruption
requirement), and are documented as such.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

from phase3.evaluation.foundations.adapter import (
    FOUNDATION_AVAILABLE,
    FOUNDATION_PARTIAL,
    MemoryFoundationAdapter,
)
from phase3.evaluation.foundations.canonical import CanonicalMemoryRecord
from phase3.evaluation.foundations.ledger import (
    CanonicalAliasError,
    CanonicalCollisionError,
    CanonicalMemoryLedger,
    PUT_CREATED,
    PUT_IDEMPOTENT,
)

# ---------------------------------------------------------------------------
# Consistency-model status vocabulary (mission: "ATOMICITY / FAILURE SEMANTICS" section).
# Deliberately small and exhaustive -- every `write_canonical_memory()` call returns
# exactly one of these, never a bare boolean/exception-only signal for the foundation leg.
# ---------------------------------------------------------------------------

STATUS_CANONICAL_ONLY = "CANONICAL_ONLY"
STATUS_CANONICAL_AND_FOUNDATION = "CANONICAL_AND_FOUNDATION"
STATUS_FOUNDATION_FAILED = "FOUNDATION_FAILED"
STATUS_ALIAS_PERSISTENCE_FAILED = "ALIAS_PERSISTENCE_FAILED"

WRITE_STATUSES = (
    STATUS_CANONICAL_ONLY,
    STATUS_CANONICAL_AND_FOUNDATION,
    STATUS_FOUNDATION_FAILED,
    STATUS_ALIAS_PERSISTENCE_FAILED,
)

# Metadata keys this module always injects into the foundation-facing metadata payload so a
# foundation that preserves arbitrary metadata verbatim (Mem0's `inspect_memory()` -- see
# `agent_runtime/identity.py`'s METADATA_LOOKUP strategy) can still be resolved back to its
# canonical identity even if `set_alias()` were somehow never called. These are a BEST-EFFORT
# breadcrumb, never a substitute for the alias table itself: `resolve_alias()` /
# `get_aliases()` on the ledger remain the authoritative lookup.
CANONICAL_ID_METADATA_KEY = "canonical_memory_id"
CANONICAL_TYPE_METADATA_KEY = "mambench_memory_type"


@dataclass(frozen=True)
class CanonicalWriteResult:
    """Outcome of one `write_canonical_memory()` call. `status` is always exactly one of
    `WRITE_STATUSES` -- partial failure is always explicit, never swallowed into a bare
    success/failure boolean (mission: "Do NOT silently claim that the operation succeeded
    in either case.")."""

    status: str
    memory_id: str
    put_result: str  # PUT_CREATED / PUT_IDEMPOTENT
    foundation_name: Optional[str] = None
    foundation_memory_id: Optional[str] = None
    note: str = ""

    def __post_init__(self) -> None:
        if self.status not in WRITE_STATUSES:
            raise ValueError(f"status {self.status!r} is not one of {WRITE_STATUSES!r}")


def _foundation_metadata(record: CanonicalMemoryRecord, metadata_extra: Optional[Mapping[str, Any]]) -> Mapping[str, Any]:
    """Build the metadata payload handed to `foundation.add_memory()`. Caller-supplied
    `metadata_extra` (e.g. `user_id`, `tags` -- foundation-specific concerns the canonical
    schema does not model) is merged in, but the canonical-identity breadcrumb keys are
    always present and are never overridable by `metadata_extra` -- content authority stays
    with the canonical record (mission: "CONTENT AUTHORITY")."""
    merged = dict(metadata_extra or {})
    merged[CANONICAL_ID_METADATA_KEY] = record.memory_id
    merged[CANONICAL_TYPE_METADATA_KEY] = record.memory_type
    # source_memory_id is the pre-existing identity-bridge convention
    # (agent_runtime/identity.py's METADATA_LOOKUP strategy); populated here so a canonical
    # write is resolvable by both the pre-existing bridge AND this stage's alias table.
    merged.setdefault("source_memory_id", record.memory_id)
    return merged


def _extract_vendor_id(add_field_value: Any) -> Optional[str]:
    """Every real and mock adapter in this framework returns `add_memory()`'s
    `value` as a mapping carrying a `"memory_id"` key (verified directly against all four
    real adapters and all four mocks during this stage's audit -- see the implementation
    report). This is the ONE place that convention is depended on; never a fabricated
    fallback if the shape is unexpected."""
    if isinstance(add_field_value, Mapping):
        vendor_id = add_field_value.get("memory_id")
        if isinstance(vendor_id, str) and vendor_id:
            return vendor_id
    return None


def write_canonical_memory(
    ledger: CanonicalMemoryLedger,
    record: CanonicalMemoryRecord,
    *,
    foundation: Optional[MemoryFoundationAdapter] = None,
    foundation_name: Optional[str] = None,
    metadata_extra: Optional[Mapping[str, Any]] = None,
) -> CanonicalWriteResult:
    """The authoritative write path: canonical record first, foundation second, alias
    third. See module docstring for why this drives the EXISTING `add_memory(memory_id,
    content, metadata)` interface rather than a new one.

    Raises `CanonicalCollisionError` (propagated, never swallowed) if `record.memory_id`
    already exists in `ledger` with different content/provenance -- a collision must fail
    loudly, per H.1's ID COLLISION POLICY. This is the one step this function does NOT wrap
    in a status value, because a collision is not a "partial success," it is a caller bug
    or a genuine data-integrity problem that must stop execution.

    If `foundation` is `None`, only the canonical write happens (`STATUS_CANONICAL_ONLY`)
    -- this is a legitimate, first-class outcome (e.g. a caller building up canonical
    ledger state ahead of any foundation ingestion), not a degraded case.
    """
    put_result = ledger.put(record)  # raises CanonicalCollisionError, never caught here

    if foundation is None:
        return CanonicalWriteResult(
            status=STATUS_CANONICAL_ONLY,
            memory_id=record.memory_id,
            put_result=put_result,
            note="No foundation adapter supplied; canonical record persisted only.",
        )

    add_field = foundation.add_memory(
        memory_id=record.memory_id,
        content=dict(record.content),
        metadata=_foundation_metadata(record, metadata_extra),
    )

    if add_field.availability not in (FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL):
        # INVARIANT 6: vendor failure never erases the canonical record -- it is already
        # durably written above.
        return CanonicalWriteResult(
            status=STATUS_FOUNDATION_FAILED,
            memory_id=record.memory_id,
            put_result=put_result,
            foundation_name=foundation_name,
            note=f"foundation.add_memory availability={add_field.availability!r}: {add_field.note}",
        )

    vendor_id = _extract_vendor_id(add_field.value)
    if vendor_id is None:
        return CanonicalWriteResult(
            status=STATUS_ALIAS_PERSISTENCE_FAILED,
            memory_id=record.memory_id,
            put_result=put_result,
            foundation_name=foundation_name,
            note=(
                "Foundation write succeeded but returned no extractable vendor memory id "
                f"(add_memory value={add_field.value!r}); alias cannot be recorded."
            ),
        )

    if foundation_name is None:
        return CanonicalWriteResult(
            status=STATUS_ALIAS_PERSISTENCE_FAILED,
            memory_id=record.memory_id,
            put_result=put_result,
            foundation_memory_id=vendor_id,
            note="Foundation write succeeded but no foundation_name was supplied; alias requires one.",
        )

    try:
        ledger.set_alias(record.memory_id, foundation_name, vendor_id)
    except CanonicalAliasError as exc:
        return CanonicalWriteResult(
            status=STATUS_ALIAS_PERSISTENCE_FAILED,
            memory_id=record.memory_id,
            put_result=put_result,
            foundation_name=foundation_name,
            foundation_memory_id=vendor_id,
            note=f"alias persistence failed: {exc}",
        )

    return CanonicalWriteResult(
        status=STATUS_CANONICAL_AND_FOUNDATION,
        memory_id=record.memory_id,
        put_result=put_result,
        foundation_name=foundation_name,
        foundation_memory_id=vendor_id,
    )


__all__ = [
    "STATUS_CANONICAL_ONLY",
    "STATUS_CANONICAL_AND_FOUNDATION",
    "STATUS_FOUNDATION_FAILED",
    "STATUS_ALIAS_PERSISTENCE_FAILED",
    "WRITE_STATUSES",
    "CANONICAL_ID_METADATA_KEY",
    "CANONICAL_TYPE_METADATA_KEY",
    "CanonicalWriteResult",
    "write_canonical_memory",
    "PUT_CREATED",
    "PUT_IDEMPOTENT",
]
