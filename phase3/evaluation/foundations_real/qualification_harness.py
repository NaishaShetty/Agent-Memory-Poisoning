"""Phase 3.3-H.4-D (Foundation Qualification Gate) -- the round-trip qualification harness.

THE QUESTION THIS MODULE ANSWERS
--------------------------------------------------------------------------------
Not "does this foundation's CRUD run for real" (Phase 3.2-H.4's `RealConformanceRecord` --
a different, prerequisite question, see `qualification_record.py`'s module docstring for
the dependency). This module answers: given a foundation whose CRUD already conforms, does
replaying one of the frozen relationship/lineage fixtures
(`qualification_fixtures.py`) through `canonical_write.write_canonical_memory()` against
THAT foundation, then reconstructing the resulting relationship graph PURELY from the
benchmark-owned canonical ledgers (`CanonicalMemoryLedger`, `CanonicalEventLedger`,
`SupersessionLedger`), agree with the graph `metrics/provenance.py`/`metrics/equivalence.py`
independently compute from the fixture's own raw JSON?

WHY RELATIONSHIP FACTS ARE NEVER COPIED ONTO THE WRITTEN RECORD
--------------------------------------------------------------------------------
`CanonicalMemoryRecord` (H.1) has `equivalent_to`/`conflicts_with`/`superseded_by`/
`lifecycle_state` fields, and the fixture JSON already populates them with each scenario's
FINAL, intended answer (e.g. `conflicting_memory/memory_a.json` already says
`"lifecycle_state": "RETIRED", "superseded_by": "mem-pref-coffee"`). If this harness copied
those fields onto the record it writes, "reconstruction" would just be reading back exactly
what was written -- a tautology, not a qualification check. Every memory this harness writes
therefore ALWAYS has `lifecycle_state=CREATED`, `equivalent_to=None`, `conflicts_with=None`,
`superseded_by=None` -- identity/content/provenance (`memory_id`, `memory_type`, `content`,
`source`, `parent_ids`) are the only fields carried over verbatim, because those are fixed
facts, not the outcomes this harness exists to independently reconstruct. Every relationship
fact is instead established by REPLAYING an event (`created`/`derived`/`relationship_detected`
/`superseded`+`retired` via `memory_versioning.supersede_memory()`) and later reconstructed
by reading the EVENT ledger and `SupersessionLedger` back -- never by re-reading the fixture
JSON at reconstruction time (mission section 5, step 4).

CREATED/DERIVED EVENTS ARE SYNTHESIZED, NOT REPLAYED FROM `events.json` VERBATIM
--------------------------------------------------------------------------------
`conflicting_memory/events.json`'s and `equivalent_memory/events.json`'s own module
docstrings already flag themselves as "not exercised for full schema validation" -- a
Phase 3.2-B hand-authored illustration, not a machine-replayable log. `lineage/*.json`
fixtures have no `events.json` at all. Rather than special-casing "fixture has an events
file" vs "fixture does not," this harness ALWAYS synthesizes the `created`/`derived` event
for each memory deterministically from that memory's OWN record fields
(`creation_event` as the event_id, `creation_timestamp` as the timestamp, `parent_ids`
deciding `created` vs `derived`) -- one code path for every fixture shape, and no content is
invented: every field placed on the synthesized event is copied from the fixture's own
per-memory record, never fabricated.

SUPERSESSION IS DRIVEN BY THE RECORD'S OWN `superseded_by` FIELD, NOT A RAW `superseded`
EVENT -- because a raw fixture `superseded` event has no field naming WHO the superseder is
(`relationship_schema.md` section 3's `superseded` event concerns exactly one memory_id);
the pairing lives only on the memory record. This harness reads `superseded_by` off each
raw fixture record and calls `memory_versioning.supersede_memory()` -- H.3's own,
unmodified, authoritative mechanism -- rather than hand-rolling a second way to establish
the same fact.

WHY `memory_versioning` IS NEVER CALLED FOR `derived`-TYPE MEMORIES
--------------------------------------------------------------------------------
`reconstruct_version_history()` sets `lifecycle_state=event.new_state` for the FIRST
lifecycle-relevant event; a `derived` `CanonicalEvent` is NOT one of H.2's
`_STATE_CHANGING_EVENT_TYPES`, so `new_state` is always `None` for it -- feeding a
`derived`-only history into `reconstruct_version_history()` would construct a
`CanonicalMemoryVersion` with `lifecycle_state=None`, which its own `__post_init__` rejects.
H.3's own test suite never exercises this path either (it only ever seeds via `created`).
This is a latent gap in a FROZEN H.3 module (`memory_versioning.py`, call-only per this
stage's mission section 3) -- this harness works around it by simply never invoking
`memory_versioning` for a `derived`-type memory (none of the frozen fixtures need
supersession/retirement checked on a derived memory anyway), rather than patching a frozen
file.

CONFLICTS_WITH HAS NO EXISTING metrics/*.py FUNCTION -- ONE SMALL, DOCUMENTED EXTRACTION
HELPER, MIRRORING equivalence.extract_equivalence_edges() EXACTLY
--------------------------------------------------------------------------------
`metrics/equivalence.py` computes `equivalent_to` components; NOTHING in `metrics/` computes
anything for `conflicts_with` (grepped and confirmed absent). Per mission section 3
("`metrics/provenance.py`, `metrics/equivalence.py` -- call only"), this harness does not
modify either file to add one. `_symmetric_edges()` below is a small, local, purely
mechanical extraction (read declared `field_name` lists off each record, keep only pairs
declared on BOTH sides) -- it does not compute or infer conflict from content in any way,
exactly the same non-semantic, declared-edges-only posture `equivalence.py`'s own module
docstring insists on for `equivalent_to`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from phase3.evaluation.foundations.adapter import MemoryFoundationAdapter
from phase3.evaluation.foundations.canonical import (
    CanonicalMemoryRecord,
    LIFECYCLE_CREATED,
    LIFECYCLE_RETIRED,
)
from phase3.evaluation.foundations.canonical_event import (
    CanonicalEvent,
    EVENT_CREATED,
    EVENT_DERIVED,
    EVENT_RELATIONSHIP_DETECTED,
    EVENT_RETIRED,
    EVENT_SUPERSEDED,
    RELATIONSHIP_CONFLICTS_WITH,
    RELATIONSHIP_EQUIVALENT_TO,
)
from phase3.evaluation.foundations.canonical_write import (
    STATUS_CANONICAL_AND_FOUNDATION,
    CanonicalWriteResult,
    write_canonical_memory,
)
from phase3.evaluation.foundations.event_ledger import (
    CanonicalEventLedger,
    SingleOccurrenceViolationError,
    UnknownCanonicalMemoryError,
)
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger
from phase3.evaluation.foundations.memory_versioning import (
    MemoryVersioningError,
    NoLifecycleHistoryError,
    SupersessionLedger,
    get_current_version,
    supersede_memory,
)
from phase3.evaluation.foundations_real.qualification_fixtures import FixtureBundle
from phase3.evaluation.metrics.equivalence import equivalence_classes
from phase3.evaluation.metrics.provenance import (
    ancestors,
    descendants,
    detect_cycles,
    independence_report,
    orphan_parent_count,
)
from phase3.evaluation.foundations.run_config import RunConfigLedger

REPLAY_ACTOR = "qualification_harness_replay"
RELATIONSHIP_MECHANISM_FIXTURE_DECLARED = "fixture_declared_relationship"


# ---------------------------------------------------------------------------
# Replay
# ---------------------------------------------------------------------------


@dataclass
class ReplayError:
    step: str
    memory_id: str
    detail: str


@dataclass
class ReplayResult:
    write_results: Dict[str, CanonicalWriteResult] = field(default_factory=dict)
    appended_event_ids: List[str] = field(default_factory=list)
    superseded_memory_ids: List[str] = field(default_factory=list)
    errors: List[ReplayError] = field(default_factory=list)

    @property
    def all_writes_succeeded(self) -> bool:
        return all(r.status == STATUS_CANONICAL_AND_FOUNDATION for r in self.write_results.values())


def _synthesize_lifecycle_event(memory_id: str, record: Mapping[str, Any]) -> CanonicalEvent:
    """One `created` or `derived` `CanonicalEvent` per fixture memory record, per module
    docstring "CREATED/DERIVED EVENTS ARE SYNTHESIZED" -- every field copied from the
    record itself, nothing invented."""
    parent_ids = tuple(record.get("parent_ids") or ())
    if not parent_ids:
        return CanonicalEvent(
            event_id=record["creation_event"],
            event_type=EVENT_CREATED,
            memory_ids=(memory_id,),
            timestamp=record["creation_timestamp"],
            actor=REPLAY_ACTOR,
            reason=f"synthesized creation event for fixture memory {memory_id!r} (memory_schema.md source={record.get('source')!r}).",
            new_state=LIFECYCLE_CREATED,
        )
    return CanonicalEvent(
        event_id=record["creation_event"],
        event_type=EVENT_DERIVED,
        memory_ids=parent_ids + (memory_id,),
        timestamp=record["creation_timestamp"],
        actor=REPLAY_ACTOR,
        reason=f"synthesized derivation event for fixture memory {memory_id!r} from parent_ids={parent_ids!r}.",
        source_memory_ids=parent_ids,
        target_memory_id=memory_id,
    )


def _event_replay_order(memories: Mapping[str, Mapping[str, Any]]) -> List[str]:
    """Topological order (parents' own creation/derivation event before any event that
    references them as a source) over `parent_ids`, Kahn's-algorithm style.

    NECESSARY ADAPTATION, DOCUMENTED: H.2-R2's frozen single-occurrence check
    (`event_ledger.py::_check_single_occurrence`, extended but not altered in shape by
    H.4-BC/H.4-F) treats ANY appearance of `memory_id` in a `derived` event's `memory_ids`
    tuple (which legitimately includes every SOURCE, not only the target) as "this memory
    already has a creation slot." Appending a child's `derived` event before a source
    memory's OWN `created`/`derived` event has been appended therefore raises
    `SingleOccurrenceViolationError` when that source's own event is appended afterward --
    not because anything is actually wrong, but because the check cannot distinguish
    "appears as this event's target" from "appears as this event's source." Synthesizing
    events in topological order avoids this for every ACYCLIC fixture. `bundle.memories`'s
    OWN declared order is preserved as the tie-break for nodes with no unresolved
    dependency, so ordering is only ever adjusted where genuinely required, never
    arbitrarily shuffled.

    A genuine graph CYCLE (fixture `10_cycle.json`) has no valid topological order --
    nodes that can never become "ready" are appended, best-effort, in declared order at the
    end; `replay_fixture()` catches and records the resulting
    `SingleOccurrenceViolationError` for those specific events rather than letting it abort
    the whole fixture. This is an honest, structural limitation of the frozen event ledger's
    single-occurrence model for a genuine multi-node cycle among `derived` memories, not a
    bug this harness silently papers over -- see also `qualification_fixtures.py`'s
    fixture-by-fixture design note. Crucially, ancestor/descendant/cycle RECONSTRUCTION
    (`reconstruct_graph()`) never depends on these events at all -- it reads `parent_ids`
    directly off `CanonicalMemoryLedger`, which Step 1 always writes successfully regardless
    of Step 2's event-replay outcome.
    """
    ids = list(memories.keys())
    known = set(ids)
    remaining_parents: Dict[str, List[str]] = {
        mid: [p for p in (memories[mid].get("parent_ids") or []) if p in known] for mid in ids
    }
    ready = [mid for mid in ids if not remaining_parents[mid]]
    ordered: List[str] = []
    resolved = set()
    while ready:
        node = ready.pop(0)
        ordered.append(node)
        resolved.add(node)
        for mid in ids:
            if mid in resolved or mid in ready:
                continue
            if node in remaining_parents[mid]:
                remaining_parents[mid] = [p for p in remaining_parents[mid] if p != node]
            if not remaining_parents[mid] and mid not in ready:
                ready.append(mid)
    # Any node never resolved participates in a cycle -- appended in declared order last.
    for mid in ids:
        if mid not in resolved:
            ordered.append(mid)
    return ordered


def _symmetric_edges(memories: Mapping[str, Mapping[str, Any]], field_name: str) -> Tuple[Tuple[str, str], ...]:
    """Declared-on-both-sides pairs for `field_name` (`"equivalent_to"` or
    `"conflicts_with"`) -- mirrors `equivalence.py` DECISION E1's symmetric-declaration
    requirement exactly, but generalized to any such field since no `metrics/*.py` module
    defines this for `conflicts_with`. Returns each pair exactly once, in lexicographic
    order (matching `relationship_schema.md` section 3.2's ordering rule for symmetric
    `relationship_detected` events)."""
    pairs = set()
    for mid, record in memories.items():
        for target in record.get(field_name) or []:
            if target == mid:
                continue
            if target in memories and mid in (memories[target].get(field_name) or []):
                pairs.add(tuple(sorted((mid, target))))
    return tuple(sorted(pairs))


def replay_fixture(
    bundle: FixtureBundle,
    *,
    foundation: Optional[MemoryFoundationAdapter],
    foundation_name: Optional[str],
    memory_ledger: CanonicalMemoryLedger,
    event_ledger: CanonicalEventLedger,
    supersession_ledger: SupersessionLedger,
    config_ledger: Optional[RunConfigLedger] = None,
    config_fingerprint: Optional[str] = None,
) -> ReplayResult:
    """Replay `bundle` through `foundation` and the canonical ledgers, per mission section 5
    steps 1-3. Never re-sorts `bundle.memories` -- written in its own declared iteration
    order. Best-effort: a caught, EXPECTED failure shape (`UnknownCanonicalMemoryError` for
    an orphan `parent_ids` reference -- fixture `09_orphan_reference.json`'s whole point) is
    recorded in `result.errors` and replay continues for every other memory/event, rather
    than aborting the whole fixture on the first such failure.
    """
    result = ReplayResult()

    # Step 1: write every memory. lifecycle_state/equivalent_to/conflicts_with/
    # superseded_by are deliberately NEVER copied from the fixture record -- see module
    # docstring.
    for memory_id, raw in bundle.memories.items():
        record = CanonicalMemoryRecord(
            memory_id=raw["memory_id"],
            memory_type=raw["memory_type"],
            content=raw["content"],
            source=raw["source"],
            parent_ids=tuple(raw.get("parent_ids") or ()),
            creation_event=raw["creation_event"],
            creation_timestamp=raw["creation_timestamp"],
            lifecycle_state=LIFECYCLE_CREATED,
        )
        write_result = write_canonical_memory(
            memory_ledger, record, foundation=foundation, foundation_name=foundation_name
        )
        result.write_results[memory_id] = write_result

    # Step 2: created/derived events, one per memory, synthesized from the record itself,
    # appended in topological order (see `_event_replay_order()`).
    for memory_id in _event_replay_order(bundle.memories):
        raw = bundle.memories[memory_id]
        event = _synthesize_lifecycle_event(memory_id, raw)
        try:
            event_ledger.append(event)
            result.appended_event_ids.append(event.event_id)
        except (UnknownCanonicalMemoryError, SingleOccurrenceViolationError) as exc:
            result.errors.append(ReplayError(step="lifecycle_event", memory_id=memory_id, detail=str(exc)))

    # Step 3a: relationship_detected events for declared equivalent_to/conflicts_with pairs.
    for a, b in _symmetric_edges(bundle.memories, "equivalent_to"):
        event = CanonicalEvent(
            event_id=f"rel-equivalent_to-{a}-{b}",
            event_type=EVENT_RELATIONSHIP_DETECTED,
            memory_ids=(a, b),
            timestamp=bundle.memories[b]["creation_timestamp"],
            actor=REPLAY_ACTOR,
            reason=f"fixture declares {a!r}.equivalent_to includes {b!r} and vice versa.",
            relationship_type=RELATIONSHIP_EQUIVALENT_TO,
            mechanism=RELATIONSHIP_MECHANISM_FIXTURE_DECLARED,
        )
        event_ledger.append(event)
        result.appended_event_ids.append(event.event_id)

    for a, b in _symmetric_edges(bundle.memories, "conflicts_with"):
        event = CanonicalEvent(
            event_id=f"rel-conflicts_with-{a}-{b}",
            event_type=EVENT_RELATIONSHIP_DETECTED,
            memory_ids=(a, b),
            timestamp=bundle.memories[b]["creation_timestamp"],
            actor=REPLAY_ACTOR,
            reason=f"fixture declares {a!r}.conflicts_with includes {b!r} and vice versa.",
            relationship_type=RELATIONSHIP_CONFLICTS_WITH,
            mechanism=RELATIONSHIP_MECHANISM_FIXTURE_DECLARED,
        )
        event_ledger.append(event)
        result.appended_event_ids.append(event.event_id)

    # Step 3b: supersession, driven by each record's own superseded_by field (never a raw
    # events.json 'superseded' entry -- see module docstring).
    for memory_id, raw in bundle.memories.items():
        superseder = raw.get("superseded_by")
        if not superseder:
            continue
        if superseder not in bundle.memories:
            result.errors.append(
                ReplayError(step="supersession", memory_id=memory_id, detail=f"declared superseder {superseder!r} not present in this fixture.")
            )
            continue
        superseded_event = CanonicalEvent(
            event_id=f"{memory_id}-superseded-by-harness",
            event_type=EVENT_SUPERSEDED,
            memory_ids=(memory_id,),
            timestamp=raw["creation_timestamp"],
            actor=REPLAY_ACTOR,
            reason=f"fixture declares {memory_id!r}.superseded_by={superseder!r}.",
            previous_state=LIFECYCLE_CREATED,
            new_state=LIFECYCLE_RETIRED,
        )
        retired_event = CanonicalEvent(
            event_id=f"{memory_id}-retired-by-harness",
            event_type=EVENT_RETIRED,
            memory_ids=(memory_id,),
            timestamp=raw["creation_timestamp"],
            actor=REPLAY_ACTOR,
            reason=f"{memory_id!r} retired via supersession by {superseder!r}.",
            previous_state=LIFECYCLE_CREATED,
            new_state=LIFECYCLE_RETIRED,
        )
        try:
            supersede_memory(
                event_ledger, memory_ledger, supersession_ledger,
                superseded_memory_id=memory_id, superseding_memory_id=superseder,
                superseded_event=superseded_event, retired_event=retired_event,
            )
        except (MemoryVersioningError, UnknownCanonicalMemoryError, SingleOccurrenceViolationError) as exc:
            result.errors.append(ReplayError(step="supersession", memory_id=memory_id, detail=str(exc)))
            continue
        result.appended_event_ids.extend([superseded_event.event_id, retired_event.event_id])
        result.superseded_memory_ids.append(memory_id)

    return result


# ---------------------------------------------------------------------------
# Expected graph (from raw fixture JSON, via metrics/provenance.py + metrics/equivalence.py)
# ---------------------------------------------------------------------------


def _derivation_touched_ids(memories: Mapping[str, Mapping[str, Any]]) -> set:
    """Every memory_id that is EITHER a derived-type memory itself OR appears as a parent
    (source) of one -- i.e. every id that would appear in some `derived` `CanonicalEvent`'s
    `memory_ids` tuple. `memory_versioning.reconstruct_version_history()` (frozen, H.3)
    filters lifecycle events via `CanonicalEventLedger.events_for_memory()`, which matches
    on ANY appearance in `memory_ids` -- it cannot distinguish a `derived` event's TARGET
    from its SOURCES. A source memory's otherwise-normal `created`-only history would
    therefore incorrectly also pick up a `derived` event it merely contributed to (as a
    parent), which carries `new_state=None` (derived events are not state-changing) and
    breaks `CanonicalMemoryVersion.__post_init__`'s validation. This is a second, related
    latent gap in the same frozen H.3 module (never exercised by H.3's own test suite,
    which never derives from a memory that is ALSO checked for its own version history) --
    this harness avoids it by never invoking `memory_versioning` for any id in this set,
    exactly mirroring the module docstring's "WHY `memory_versioning` IS NEVER CALLED FOR
    `derived`-TYPE MEMORIES" reasoning, extended to a derived memory's parents too."""
    touched = set()
    for mid, raw in memories.items():
        parent_ids = raw.get("parent_ids") or []
        if parent_ids:
            touched.add(mid)
            touched.update(parent_ids)
    return touched


def compute_expected_graph(bundle: FixtureBundle) -> Dict[str, Any]:
    memories = bundle.memories
    ids = sorted(memories.keys())
    touched = _derivation_touched_ids(memories)

    graph: Dict[str, Any] = {
        "ancestors": {mid: sorted(ancestors(memories, mid).detail.get("ancestors", [])) for mid in ids},
        "descendants": {mid: sorted(descendants(memories, mid).detail.get("descendants", [])) for mid in ids},
        "cycles": sorted(frozenset(c) for c in detect_cycles(memories).detail["cycles"]),
        "equivalence_components": sorted(tuple(c) for c in equivalence_classes(memories=memories).detail["components"]),
        "conflict_pairs": list(_symmetric_edges(memories, "conflicts_with")),
        "orphan_children": sorted(orphan_parent_count(memories).detail["orphaned_children"]),
        "supersession": {
            mid: {"retired": True, "superseded_by": raw.get("superseded_by")}
            for mid, raw in memories.items()
            if raw.get("superseded_by") and mid not in touched
        },
    }
    if bundle.selected_memory_ids:
        graph["independence_pairwise"] = dict(
            independence_report(memories, list(bundle.selected_memory_ids)).detail["pairwise"]
        )
    return graph


# ---------------------------------------------------------------------------
# Reconstructed graph (purely from the canonical ledgers -- never the fixture JSON again)
# ---------------------------------------------------------------------------


def reconstruct_graph(
    memory_ledger: CanonicalMemoryLedger,
    event_ledger: CanonicalEventLedger,
    supersession_ledger: SupersessionLedger,
    memory_ids: Sequence[str],
    selected_memory_ids: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    ids = sorted(memory_ids)

    # Rebuild a metrics/provenance.py-shaped mapping purely from CanonicalMemoryLedger +
    # relationship_detected events -- never from any fixture JSON.
    memories_map: Dict[str, Dict[str, Any]] = {}
    for mid in ids:
        record = memory_ledger.get(mid)
        memories_map[mid] = {
            "memory_id": mid,
            "memory_type": record.memory_type if record else None,
            "parent_ids": list(record.parent_ids) if record else [],
            "equivalent_to": [],
        }
    touched = _derivation_touched_ids(memories_map)

    conflict_pairs = set()
    for event in event_ledger.all_events():
        if event.event_type != EVENT_RELATIONSHIP_DETECTED:
            continue
        a, b = event.memory_ids
        if event.relationship_type == RELATIONSHIP_EQUIVALENT_TO:
            if a in memories_map:
                memories_map[a]["equivalent_to"].append(b)
            if b in memories_map:
                memories_map[b]["equivalent_to"].append(a)
        elif event.relationship_type == RELATIONSHIP_CONFLICTS_WITH:
            conflict_pairs.add(tuple(sorted((a, b))))

    graph: Dict[str, Any] = {
        "ancestors": {mid: sorted(ancestors(memories_map, mid).detail.get("ancestors", [])) for mid in ids},
        "descendants": {mid: sorted(descendants(memories_map, mid).detail.get("descendants", [])) for mid in ids},
        "cycles": sorted(frozenset(c) for c in detect_cycles(memories_map).detail["cycles"]),
        "equivalence_components": sorted(tuple(c) for c in equivalence_classes(memories=memories_map).detail["components"]),
        "conflict_pairs": sorted(conflict_pairs),
        "orphan_children": sorted(orphan_parent_count(memories_map).detail["orphaned_children"]),
        "supersession": {},
    }

    for mid in ids:
        if mid in touched:
            continue  # memory_versioning gap for derivation-touched ids -- see _derivation_touched_ids().
        try:
            current = get_current_version(event_ledger, memory_ledger, supersession_ledger, mid)
        except NoLifecycleHistoryError:
            continue
        if current.lifecycle_state == LIFECYCLE_RETIRED:
            graph["supersession"][mid] = {"retired": True, "superseded_by": current.superseded_by}

    if selected_memory_ids:
        graph["independence_pairwise"] = dict(
            independence_report(memories_map, list(selected_memory_ids)).detail["pairwise"]
        )
    return graph


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------


def compare_graphs(expected: Mapping[str, Any], reconstructed: Mapping[str, Any]) -> Tuple[bool, List[str]]:
    """Explicit, per-key comparison -- never a bare boolean. Returns `(passed, mismatches)`
    where every mismatch names the specific disagreeing key/edge (mission section 9,
    adversarial case 2)."""
    mismatches: List[str] = []
    keys = sorted(set(expected.keys()) | set(reconstructed.keys()))
    for key in keys:
        exp_val = expected.get(key)
        rec_val = reconstructed.get(key)
        if exp_val != rec_val:
            mismatches.append(f"{key}: expected={exp_val!r} reconstructed={rec_val!r}")
    return (len(mismatches) == 0, mismatches)


# ---------------------------------------------------------------------------
# End-to-end per-fixture result
# ---------------------------------------------------------------------------


@dataclass
class FixtureQualificationResult:
    fixture_name: str
    passed: bool
    mismatches: List[str] = field(default_factory=list)
    replay_errors: List[ReplayError] = field(default_factory=list)
    all_writes_succeeded: bool = True

    def to_dict(self) -> dict:
        return {
            "fixture_name": self.fixture_name,
            "passed": self.passed,
            "mismatches": list(self.mismatches),
            "replay_errors": [vars(e) for e in self.replay_errors],
            "all_writes_succeeded": self.all_writes_succeeded,
        }


def run_qualification_fixture(
    bundle: FixtureBundle,
    *,
    foundation: Optional[MemoryFoundationAdapter],
    foundation_name: Optional[str],
    memory_ledger: CanonicalMemoryLedger,
    event_ledger: CanonicalEventLedger,
    supersession_ledger: SupersessionLedger,
    config_ledger: Optional[RunConfigLedger] = None,
    config_fingerprint: Optional[str] = None,
) -> FixtureQualificationResult:
    """The harness's entire job for one `(foundation, fixture)` pair (mission section 5):
    replay, compute expected, reconstruct, compare. Produces one pass/fail-with-detail
    result; deciding what an entire FOUNDATION's overall verdict should be from many of
    these is `qualification_record.py`'s job, not this function's."""
    replay = replay_fixture(
        bundle,
        foundation=foundation,
        foundation_name=foundation_name,
        memory_ledger=memory_ledger,
        event_ledger=event_ledger,
        supersession_ledger=supersession_ledger,
        config_ledger=config_ledger,
        config_fingerprint=config_fingerprint,
    )

    expected = compute_expected_graph(bundle)
    reconstructed = reconstruct_graph(
        memory_ledger, event_ledger, supersession_ledger,
        memory_ids=list(bundle.memories.keys()),
        selected_memory_ids=bundle.selected_memory_ids,
    )
    passed, mismatches = compare_graphs(expected, reconstructed)

    # A replay error that ISN'T the expected orphan-reference shape is a genuine failure,
    # not a benign, already-accounted-for gap -- surface it as a mismatch too.
    cycle_members = {mid for cycle in expected.get("cycles", []) for mid in cycle}
    unexplained_errors = [
        e for e in replay.errors
        if not (
            e.step == "lifecycle_event"
            and (e.memory_id in expected.get("orphan_children", []) or e.memory_id in cycle_members)
        )
    ]
    for err in unexplained_errors:
        mismatches.append(f"unexplained replay error: step={err.step!r} memory_id={err.memory_id!r} detail={err.detail!r}")
        passed = False

    return FixtureQualificationResult(
        fixture_name=bundle.name,
        passed=passed,
        mismatches=mismatches,
        replay_errors=replay.errors,
        all_writes_succeeded=replay.all_writes_succeeded,
    )


__all__ = [
    "REPLAY_ACTOR",
    "RELATIONSHIP_MECHANISM_FIXTURE_DECLARED",
    "ReplayError",
    "ReplayResult",
    "replay_fixture",
    "compute_expected_graph",
    "reconstruct_graph",
    "compare_graphs",
    "FixtureQualificationResult",
    "run_qualification_fixture",
]
