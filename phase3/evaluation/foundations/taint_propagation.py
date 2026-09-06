"""Phase 3.3-H.4-G (`tainted_by` Attack-Propagation Query) -- `tainted_memories()`, a
read-only lineage-reachability query over the canonical memory ledger.

WHY THIS LIVES IN `foundations/`, NOT `metrics/`
--------------------------------------------------------------------------------
`metrics/provenance.py` is a package of PURE functions over plain, caller-supplied
mappings (`{memory_id: {"parent_ids": [...], ...}}`) -- it has no concept of a
`CanonicalMemoryLedger`, a `CanonicalMemoryRecord`, or `memory_versioning`'s lifecycle
machinery, and this mission's own instructions are explicit that it must not gain one
(§3: "do not modify this function, add parameters to it, or fork a copy"). This module is
the opposite: it is entirely ABOUT canonical-ledger/lifecycle infrastructure -- it builds a
live snapshot from `CanonicalMemoryLedger.list_records()` and cross-references
`memory_versioning.get_current_version()` -- and only DELEGATES the actual graph traversal
to `metrics.provenance.descendants()`, reused verbatim. Every other H.1/H.2/H.3-adjacent
query module in this codebase that consumes `CanonicalMemoryLedger`/`memory_versioning`
directly (`memory_versioning.py` itself, `qualification_harness.py`) lives under
`foundations/`/`foundations_real/`, not `metrics/` -- this module follows that same
placement convention.

WHY NO EVENT-LEDGER REPLAY
--------------------------------------------------------------------------------
`parent_ids` already lives directly on `CanonicalMemoryRecord` (H.1) -- reading the ledger's
own records is simpler and sufficient to answer "what is reachable via `derived_from`."
This module has no dependency on `canonical_event.py`/`event_ledger.py` at all (confirmed:
no import of either anywhere in this file) -- it needs a memory's IDENTITY/lineage shape,
not its EVENT history, for the traversal itself. `memory_versioning.py` (H.3) IS used, but
only for its `get_current_version()` lifecycle query, which itself never touches the event
ledger's `derived`/`created` events for this purpose in a way this module needs to
replicate.

WHY THIS IS NOT `counterfactually_influential` (Initiative A) -- READ THIS, IT MATTERS
================================================================================
`tainted_by` is a LINEAGE-REACHABILITY fact, computed purely from `derived_from`
(`parent_ids`) edges: a memory is "tainted" iff it is reachable by transitively following
`derived_from` FROM a confirmed-attack memory. It says NOTHING about whether that memory
was ever retrieved, selected, exposed to an agent, or actually influenced any task's
answer -- those are exactly what a (separate, not-yet-built) `counterfactually_influential`
finding (Initiative A) would establish, by comparing a clean run against a manipulated run.
A tainted memory may never have been selected for any task and may have had zero actual
effect on any real answer; conversely (in principle, though outside what THIS traversal
computes) a memory could be counterfactually influential without being lineage-tainted, if
influence flowed through a channel this framework does not model as `derived_from` at all.
`TaintReport` below, and any future report or metric built on `tainted_memories()`, MUST
report `tainted_memory_ids` alongside, never as a substitute for, a
`counterfactually_influential` finding, once Initiative A exists.
================================================================================

ONLY `derived_from` PROPAGATES TAINT -- `equivalent_to`/`conflicts_with` NEVER DO
--------------------------------------------------------------------------------
True by construction: the live snapshot this module builds
(`{memory_id: {"parent_ids": [...]}}`) carries ONLY `parent_ids` -- `equivalent_to`/
`conflicts_with` are never read into it at all, so `metrics.provenance.descendants()`
structurally cannot traverse them (it only ever reads `parent_ids`, per its own module
docstring). `test_taint_propagation.py` tests this directly (a memory `equivalent_to` an
attack memory, with no `derived_from` edge to it, must NOT appear in `tainted_memory_ids`)
to prove this isn't merely true because no such fixture was tried.

THE H.3/H.4-D VERSIONING GAP -- WORKED AROUND HERE TOO, NOT REPAIRED
--------------------------------------------------------------------------------
`PHASE3_3_H4_D_IMPLEMENTATION_REPORT.md` documents a latent bug in frozen
`memory_versioning.reconstruct_version_history()`: a memory that is merely a PARENT of some
`derived` memory incorrectly picks up that `derived` event into its own version history
(via `CanonicalEventLedger.events_for_memory()`'s "matches on any appearance in
`memory_ids`" property, which cannot distinguish a `derived` event's TARGET from its
SOURCES), and `CanonicalMemoryVersion.__post_init__` then rejects the resulting `new_state
=None`. `qualification_harness.py::_derivation_touched_ids()` is H.4-D's own, private
(underscore-prefixed, not exported) workaround for this. Per this mission's own
instruction not to reach into another module's private internals, `_is_derivation_touched()`
below REPLICATES that exact narrow check locally (it is a two-line set-membership test, not
a divergent reimplementation) with this comment as the explicit citation of prior art. A
tainted id found to be derivation-touched is reported as
`LIFECYCLE_STATUS_UNKNOWN_VERSIONING_GAP` and `get_current_version()` is never called on
it -- this module does not repair the underlying frozen-file bug, exactly as H.4-D did not.

DISCOVERED DURING TESTING, STATED HONESTLY: every genuine taint descendant is, BY
CONSTRUCTION, a `derived`-type memory -- non-empty `parent_ids` is exactly what connects it
to its ancestor via `derived_from` in the first place -- so it ALWAYS satisfies
`_is_derivation_touched()`'s own "has non-empty parent_ids" clause on its own account,
regardless of whether it is also someone else's parent. Given the current H.3 gap, this
means `lifecycle_status` realistically reports `LIFECYCLE_STATUS_UNKNOWN_VERSIONING_GAP`
for EVERY genuinely-tainted id today -- `get_current_version()` is never actually reachable
for a real taint result under the present frozen H.3 behavior. This is not a defect in
THIS module; it is an honest consequence of a documented gap in a module this stage must
not modify, surfaced here rather than hidden, exactly matching this framework's own
established convention for naming such limitations plainly (see also H.4-F's temporal-
ordering limitation, H.4-D's own first documented instance of this exact gap).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Sequence, Set, Tuple

from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger
from phase3.evaluation.foundations.memory_versioning import NoLifecycleHistoryError, get_current_version
from phase3.evaluation.metrics.provenance import descendants

LIFECYCLE_STATUS_UNKNOWN_VERSIONING_GAP = "UNKNOWN_VERSIONING_GAP"
LIFECYCLE_STATUS_NO_LIFECYCLE_HISTORY = "NO_LIFECYCLE_HISTORY"


class UnknownAttackMemoryError(KeyError):
    """Raised when an id in `attack_memory_ids` does not exist in the linked
    `CanonicalMemoryLedger`. NOT a reuse of `event_ledger.UnknownCanonicalMemoryError` --
    this module has no dependency on `event_ledger.py` at all (see module docstring "WHY NO
    EVENT-LEDGER REPLAY"), and that error type lives there; this is a new, small,
    analogous type for the same KIND of fact ("referenced memory_id does not exist"),
    scoped to this module rather than importing a sibling stage's error class purely for
    its name."""


@dataclass(frozen=True)
class TaintReport:
    """Result of one `tainted_memories()` call.

    LINEAGE-REACHABILITY, NOT COUNTERFACTUAL INFLUENCE -- see module docstring's
    prominent section. `tainted_memory_ids` means "reachable from a confirmed attack via
    `derived_from`," nothing more; it is never equivalent to, and must never be reported as
    a substitute for, a `counterfactually_influential` (Initiative A) finding.

    Attributes
    ----------
    attack_memory_ids:
        The confirmed-attack ids this report was computed for, exactly as supplied
        (order preserved as given, for traceability back to the caller's own input).
    tainted_memory_ids:
        The UNION of every attack id's descendant set, sorted, deduplicated. Never
        includes an `attack_memory_ids` member UNLESS that member is also a genuine
        descendant of a DIFFERENT attack id in this same call (a legitimate, documented
        case -- see mission section 6, invariant 2 -- never suppressed).
    tainted_by_attack:
        Per-attack-id breakdown: `attack_memory_id -> sorted tuple of its own descendant
        ids`. Deliberately NOT flattened away -- Phase 4's own attribution work will likely
        need to know which specific attack a given tainted memory traces back to.
    lifecycle_status:
        `tainted_memory_id -> current lifecycle_state string` (e.g. `"ACTIVE"`,
        `"RETIRED"`), or `LIFECYCLE_STATUS_UNKNOWN_VERSIONING_GAP` for a derivation-touched
        id (see module docstring), or `LIFECYCLE_STATUS_NO_LIFECYCLE_HISTORY` if the
        canonical ledger has the memory but the event ledger/version history was never
        established for it (a genuine, different, honestly-reported gap, not the same as
        the versioning bug).
    any_cycle_detected:
        `True` iff ANY underlying `descendants()` traversal (one per attack id) reported a
        cycle -- OR'd across all of them, never silently dropped.
    """

    attack_memory_ids: Tuple[str, ...]
    tainted_memory_ids: Tuple[str, ...]
    tainted_by_attack: Mapping[str, Tuple[str, ...]]
    lifecycle_status: Mapping[str, str]
    any_cycle_detected: bool = False


def _is_derivation_touched(memory_id: str, snapshot: Mapping[str, Mapping[str, Any]]) -> bool:
    """Is `memory_id` either a `derived`-shaped memory itself (non-empty `parent_ids`) OR
    a PARENT referenced by some other memory's `parent_ids`? Either shape hits the H.3/
    H.4-D `events_for_memory()` versioning gap (module docstring) if fed to
    `get_current_version()`. Mirrors `qualification_harness.py::_derivation_touched_ids()`
    exactly (H.4-D prior art, cited per this mission's own instruction not to import that
    module's private name directly) -- deliberately NOT imported from there, since it is
    underscore-prefixed and not part of that module's public API.
    """
    own_parents = snapshot.get(memory_id, {}).get("parent_ids") or []
    if own_parents:
        return True
    return any(memory_id in (record.get("parent_ids") or []) for record in snapshot.values())


def tainted_memories(
    memory_ledger: CanonicalMemoryLedger,
    attack_memory_ids: Sequence[str],
    *,
    event_ledger=None,
    supersession_ledger: Any = None,
) -> TaintReport:
    """Compute the set of currently-known memories reachable from `attack_memory_ids` via
    `derived_from` (`parent_ids`), plus their current lifecycle status where safely
    determinable.

    Read-only: this function calls only `memory_ledger.list_records()`/`.exists()` and
    (optionally) `memory_versioning.get_current_version()` -- it never calls `put()`,
    `append()`, or any other mutating method on any ledger, on this or any other object it
    is given (provable by construction: no such call appears anywhere in this module).

    Parameters
    ----------
    memory_ledger:
        The canonical memory ledger to build the live lineage snapshot from.
    attack_memory_ids:
        The confirmed-attack memory ids to trace forward from. Order does not affect the
        result (`TaintReport.tainted_memory_ids`/`tainted_by_attack` are computed
        independently per id and are order-independent by construction).
    event_ledger, supersession_ledger:
        Optional. If BOTH are supplied, `lifecycle_status` is populated via
        `memory_versioning.get_current_version()` for every non-derivation-touched tainted
        id. If either is omitted, `lifecycle_status` is simply left empty -- no attempt to
        determine status is made at all in that case (this is different from, and never
        confused with, `LIFECYCLE_STATUS_NO_LIFECYCLE_HISTORY`, which means status WAS
        attempted and found undeterminable for a specific id). A caller that only cares
        about the lineage-reachability fact itself may omit both.

    Raises
    ------
    UnknownAttackMemoryError
        If any id in `attack_memory_ids` does not exist in `memory_ledger` -- checked
        BEFORE any traversal, so a bad input never silently produces an empty/partial
        result (mission section 7, adversarial case 3).
    """
    unknown = [mid for mid in attack_memory_ids if not memory_ledger.exists(mid)]
    if unknown:
        raise UnknownAttackMemoryError(
            f"attack_memory_ids contains id(s) not present in the linked CanonicalMemoryLedger: "
            f"{sorted(unknown)!r}. Refusing to compute a partial/empty taint report for an "
            "unresolvable attack id."
        )

    # Pure, read-only snapshot -- no mutation of memory_ledger or anything derived from it.
    snapshot: Dict[str, Dict[str, Any]] = {
        record.memory_id: {"parent_ids": list(record.parent_ids)} for record in memory_ledger.list_records()
    }

    tainted_by_attack: Dict[str, Tuple[str, ...]] = {}
    union: Set[str] = set()
    any_cycle_detected = False

    for attack_id in attack_memory_ids:
        result = descendants(snapshot, attack_id, include_self=False)
        own_descendants = tuple(sorted(result.detail.get("descendants", [])))
        tainted_by_attack[attack_id] = own_descendants
        union.update(own_descendants)
        any_cycle_detected = any_cycle_detected or bool(result.detail.get("cycle_detected", False))

    tainted_memory_ids = tuple(sorted(union))

    lifecycle_status: Dict[str, str] = {}
    if event_ledger is not None and supersession_ledger is not None:
        for tainted_id in tainted_memory_ids:
            if _is_derivation_touched(tainted_id, snapshot):
                lifecycle_status[tainted_id] = LIFECYCLE_STATUS_UNKNOWN_VERSIONING_GAP
                continue
            try:
                current = get_current_version(event_ledger, memory_ledger, supersession_ledger, tainted_id)
                lifecycle_status[tainted_id] = current.lifecycle_state
            except NoLifecycleHistoryError:
                lifecycle_status[tainted_id] = LIFECYCLE_STATUS_NO_LIFECYCLE_HISTORY

    return TaintReport(
        attack_memory_ids=tuple(attack_memory_ids),
        tainted_memory_ids=tainted_memory_ids,
        tainted_by_attack=tainted_by_attack,
        lifecycle_status=lifecycle_status,
        any_cycle_detected=any_cycle_detected,
    )


__all__ = [
    "LIFECYCLE_STATUS_UNKNOWN_VERSIONING_GAP",
    "LIFECYCLE_STATUS_NO_LIFECYCLE_HISTORY",
    "UnknownAttackMemoryError",
    "TaintReport",
    "tainted_memories",
]
