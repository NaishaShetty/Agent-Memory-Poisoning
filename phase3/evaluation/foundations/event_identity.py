"""Phase 3.3-H.2-R (Canonical Event Ledger Remediation) -- the MAMBench Event ID Factory:
a single, benchmark-owned authority for generating `CanonicalEvent.event_id` values.

WHY THIS MODULE EXISTS
--------------------------------------------------------------------------------
H.2 established that `CanonicalEventLedger` CHECKS `event_id` uniqueness/collision, but
left generation of `event_id` values entirely up to whatever caller constructs a
`CanonicalEvent` -- there was no single, named, benchmark-owned authority responsible for
actually MINTING one. The post-implementation review flagged this as a gap: "the ledger can
verify uniqueness but does not establish who is responsible for generating benchmark event
identities."

THIS MODULE DOES NOT REPLACE CanonicalEvent's EXISTING CONTRACT
--------------------------------------------------------------------------------
`CanonicalEvent.event_id` remains a plain, caller-supplied `str` field -- H.2's contract is
unchanged, and every existing H.2 test/caller that constructs a `CanonicalEvent` with its
own explicit `event_id` continues to work unmodified. `generate_event_id()` below is an
ADDITIVE convenience: a caller MAY call it to obtain a value to pass as `event_id=...`, or
may continue supplying its own. The factory never bypasses `CanonicalEventLedger.append()`'s
own collision/idempotency check -- it only produces a candidate string; the ledger remains
the sole authority over whether that string is actually new, an idempotent repeat, or a
collision (mission: "The factory must not bypass ledger validation").

WHY CONTENT-DERIVED (fingerprint-based), NOT uuid4()
--------------------------------------------------------------------------------
Two existing, established conventions in this repository were weighed:

1. `foundations/mocks/common.py::DeterministicClock` -- "never `uuid4()`/`random`" for
   anything that needs to be reproducible across runs.
2. `security/reproducibility.py::fingerprint()` -- the repository's ALREADY-EXISTING,
   already-used-everywhere (e.g. `agent_runtime/trace.py`'s `trace_fingerprint`) SHA-256
   canonical-serialization fingerprint function. Reusing it here means this module invents
   no second hashing/ID scheme.

`generate_event_id()` therefore derives an id deterministically from the event's own
defining fields via `fingerprint()`: given the SAME `(event_type, memory_ids, timestamp,
actor, reason, task_id, previous_state, new_state, foundation_name, foundation_memory_id,
source_memory_ids, target_memory_id)`, it always returns the SAME id. This has a
useful, deliberate property: two calls describing the truly-identical historical fact
naturally coalesce onto the SAME `event_id`, which is EXACTLY `CanonicalEventLedger`'s own
idempotent-duplicate policy (identical `event_id` + identical payload -> no-op) --
determinism and the ledger's collision policy reinforce each other by construction, rather
than needing a separately-invented "nonce" concept to avoid accidental collisions between
genuinely different events (any real difference in the inputs changes the fingerprint, and
therefore the id).

This module does NOT use `uuid4()` merely because it would be convenient: a random id
would (a) make two calls describing the identical fact mint two DIFFERENT ids, defeating
the ledger's idempotency guarantee for a caller that legitimately retries the same logical
append, and (b) be irreproducible, unlike every other identity-bearing construct already in
this framework's reproducibility story.

NAMESPACE
--------------------------------------------------------------------------------
Every id this module produces is prefixed `EVT-` specifically so it is visually and
structurally distinct from every other identifier namespace in this framework (see
`PHASE3_3_H2_CANONICAL_EVENT_LEDGER.md`'s "Identity separation" section for the full table):
canonical memory ids (dataset-native, unprefixed), foundation/vendor ids (vendor-native,
unprefixed), task ids (dataset-native), and the new `BND-`-prefixed experiment-boundary ids
(`experiment_boundary.py`). None of these namespaces overlaps in practice (they are never
compared for equality across namespaces anywhere in this framework), but the prefix makes a
misuse (e.g. accidentally passing an `event_id` where a `memory_id` was expected) far more
likely to be caught by a human reviewing a trace/log, even though nothing in this module
enforces the prefix as a hard runtime enforcement -- see `looks_like_generated_event_id()`.
"""

from __future__ import annotations

from typing import Optional, Sequence

from phase3.evaluation.security.reproducibility import fingerprint

EVENT_ID_PREFIX = "EVT"


def generate_event_id(
    event_type: str,
    memory_ids: Sequence[str],
    timestamp: str,
    actor: str,
    reason: str,
    *,
    task_id: Optional[str] = None,
    previous_state: Optional[str] = None,
    new_state: Optional[str] = None,
    foundation_name: Optional[str] = None,
    foundation_memory_id: Optional[str] = None,
    source_memory_ids: Optional[Sequence[str]] = None,
    target_memory_id: Optional[str] = None,
) -> str:
    """The MAMBench Event ID Factory: deterministically mint an `event_id` from the exact
    same fields `CanonicalEvent` itself validates (see `canonical_event.py`).

    Benchmark-owned: this function is pure Python, has no vendor/foundation dependency, and
    never reads or is influenced by any `MemoryFoundationAdapter` state.

    Deterministic/reproducible: identical arguments always produce the identical id, via
    `security.reproducibility.fingerprint()` (SHA-256 over a canonical serialization) --
    the same content-addressing convention every other reproducibility-sensitive construct
    in this framework already uses, not a second, newly-invented scheme.

    Collision-checkable: the returned string is a plain `str`; passing it as
    `CanonicalEvent(event_id=..., ...)` and then `CanonicalEventLedger.append()`-ing that
    event still runs the ledger's full collision/idempotency check -- this function never
    writes to a ledger and never bypasses one.
    """
    payload = {
        "event_type": event_type,
        "memory_ids": list(memory_ids),
        "timestamp": timestamp,
        "actor": actor,
        "reason": reason,
        "task_id": task_id,
        "previous_state": previous_state,
        "new_state": new_state,
        "foundation_name": foundation_name,
        "foundation_memory_id": foundation_memory_id,
        "source_memory_ids": list(source_memory_ids) if source_memory_ids is not None else None,
        "target_memory_id": target_memory_id,
    }
    return f"{EVENT_ID_PREFIX}-{fingerprint(payload)}"


def looks_like_generated_event_id(candidate: str) -> bool:
    """Best-effort, non-authoritative check: does `candidate` carry this factory's naming
    convention? Never used by `CanonicalEvent`/`CanonicalEventLedger` for any validation
    decision (a caller-supplied, non-factory-minted `event_id` remains fully valid) -- this
    exists only as a debugging/introspection convenience."""
    return isinstance(candidate, str) and candidate.startswith(f"{EVENT_ID_PREFIX}-")


# ---------------------------------------------------------------------------
# Phase 3.3-H.2-R2 -- one documented integration surface (section D1)
# ---------------------------------------------------------------------------
#
# WHY THE `EVT-` PREFIX IS NOT RUNTIME-ENFORCED (H.2-R2 section B1 decision)
# --------------------------------------------------------------------------------
# `CanonicalEvent.event_id` remains validated only as "non-empty string" -- the same rule
# every other identity field in this framework (`memory_id`, `task_id`, `boundary_id`) is
# held to; none of them carries a runtime-enforced prefix either. Making `EVT-` mandatory
# NOW would retroactively invalidate every existing H.2/H.2-R test fixture that predates
# this factory (`"evt-001"`, `"e1"`..`"e9"`, etc. throughout `test_canonical_event_ledger_
# h2.py`/`test_h2_remediation.py`) for a purely cosmetic reason -- exactly the "arbitrary
# formatting more important than semantic identity" outcome the H.2-R2 mission brief warns
# against, and the mission explicitly asks NOT to rewrite legitimate existing test
# fixtures without a real migration need. Namespace separation between an event id and a
# boundary id is instead achieved STRUCTURALLY: `CanonicalEventLedger` and
# `ExperimentBoundaryLedger` are different classes with entirely separate internal
# dictionaries and on-disk files, so even if the exact same literal string were used as
# both an `event_id` and a `boundary_id`, looking it up in the WRONG ledger simply finds
# nothing -- there is no shared table where a collision between the two namespaces could
# even occur. `looks_like_generated_event_id()` above (and its boundary-id counterpart,
# `experiment_boundary.looks_like_generated_boundary_id()`) remain advisory-only, exactly
# as before this stage.


def build_canonical_event(
    event_type: str,
    memory_ids,
    timestamp: str,
    actor: str,
    reason: str,
    **kwargs,
):
    """The recommended single integration surface for constructing a `CanonicalEvent`:
    mints its `event_id` via `generate_event_id()` and constructs the event in one call, so
    future runtime call sites (subsystem A, B, C, ...) do not each independently reinvent
    "call the factory, then build the event" -- one documented path, used consistently.

    Does NOT bypass any validation: the returned object is a plain `CanonicalEvent`,
    constructed via its normal `__post_init__` (so a malformed `event_type`/state
    combination still raises `CanonicalEventValidationError` exactly as if constructed
    directly), and appending it to a `CanonicalEventLedger` still runs that ledger's full
    collision/idempotency/linkage/single-occurrence checks unchanged -- this function
    performs no ledger operation of its own.

    The lower-level `CanonicalEvent(...)` constructor is NOT removed or deprecated by this
    function's existence -- it remains the right choice for tests, fixtures, and any
    caller that already has (or wants to control) its own `event_id`.

    `**kwargs` accepts any of `CanonicalEvent`'s remaining optional fields (`task_id`,
    `previous_state`, `new_state`, `foundation_name`, `foundation_memory_id`,
    `source_memory_ids`, `target_memory_id`) verbatim -- both `generate_event_id()` and
    `CanonicalEvent(...)` are called with the identical field set, so the returned event's
    `event_id` is always internally consistent with its own content.
    """
    from phase3.evaluation.foundations.canonical_event import CanonicalEvent

    memory_ids = tuple(memory_ids)
    identity_kwargs = {
        "task_id": kwargs.get("task_id"),
        "previous_state": kwargs.get("previous_state"),
        "new_state": kwargs.get("new_state"),
        "foundation_name": kwargs.get("foundation_name"),
        "foundation_memory_id": kwargs.get("foundation_memory_id"),
        "source_memory_ids": kwargs.get("source_memory_ids"),
        "target_memory_id": kwargs.get("target_memory_id"),
    }
    event_id = generate_event_id(
        event_type=event_type,
        memory_ids=memory_ids,
        timestamp=timestamp,
        actor=actor,
        reason=reason,
        **identity_kwargs,
    )
    return CanonicalEvent(
        event_id=event_id,
        event_type=event_type,
        memory_ids=memory_ids,
        timestamp=timestamp,
        actor=actor,
        reason=reason,
        **kwargs,
    )


__all__ = [
    "EVENT_ID_PREFIX",
    "generate_event_id",
    "looks_like_generated_event_id",
    "build_canonical_event",
]
