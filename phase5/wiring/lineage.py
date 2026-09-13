"""Phase 5.7 -- Provenance, Lineage & Memory Interaction Instrumentation.

WHAT EXISTS ALREADY
--------------------------------------------------------------------------------
- `provenance_graph.py::ProvenanceGraph`/`build_provenance_graph()` -- real, tested,
  projects a graph purely from `CanonicalMemoryLedger`/`CanonicalEventLedger`/
  `SupersessionLedger` state, grounding every edge in an `established_by_event_id` --
  "no edge is ever invented."
- `taint_propagation.py::tainted_memories()` -- real, tested, computes lineage
  reachability (via `derived_from`/`parent_ids` only) from a set of confirmed-attack
  memory ids. Its own docstring is explicit and load-bearing: this is
  LINEAGE-REACHABILITY, NOT COUNTERFACTUAL INFLUENCE.
- `canonical_event.py::EVENT_COUNTERFACTUALLY_INFLUENTIAL` -- the ONE real,
  schema-validated source of an actual influence claim in this framework, always tied to
  a specific masking intervention (`masking_method`, `baseline_answer_hash`,
  `counterfactual_answer_hash`, `diff_criterion`).

THE GAP THIS STAGE CLOSES
--------------------------------------------------------------------------------
None of the above ever sees a `Phase5Event` (Stage 5.2-5.6's `attack_injection`,
`retrieval_candidate_scored`, `context_assembled`, `agent_decision`, `agent_action`) --
`ProvenanceGraph` is frozen and reads only `CanonicalEvent`-shaped ledgers. So the
master prompt's own worked example --
    Injection I1 -> Memory M17 -> Retrieved R4 -> Selected S4 -> Used by Decision D7
    -> Action A3 -> Generated Memory M31
-- cannot be reconstructed from `ProvenanceGraph` alone: it mixes `CanonicalEvent` facts
(created/derived/retrieved/selected) with `Phase5Event` facts (attack_injection,
agent_decision, agent_action). This module is the additive layer that reads BOTH ledger
families and produces one common, closed, typed relationship vocabulary
(`MemoryInteractionEdge`) -- reusing `ProvenanceGraph`/`tainted_memories()` verbatim for
the CanonicalEvent half, never reimplementing them.

WHY THIS IS A DERIVATION LAYER, NOT A NEW EVENT TYPE
--------------------------------------------------------------------------------
`Phase5Event`'s own module docstring (Stage 5.2) already anticipated this: "Stage 5.7's
derivation logic is a separate, explicit, auditable step, not hidden inside this
schema." Every function here is read-only and recomputes its output fresh from ledger
state every call -- exactly `ProvenanceGraph`'s own "a projection, never a second store"
discipline, applied to the cross-schema case.

THE CENTRAL DISCIPLINE: TEMPORAL ORDER IS NEVER INFLUENCE (contract, master prompt Section 15)
--------------------------------------------------------------------------------
Every `MemoryInteractionEdge` carries an `evidence_kind`, which is the load-bearing field
for this discipline -- never omitted, never left to be inferred from `relationship_type`
alone:

    OBSERVED_EVENT          -- a directly recorded fact (e.g. an injection produced a
                               memory, one memory was derived from another). Strong.
    EXPOSURE_ONLY           -- a memory was exposed to a decision (`agent_decision`'s
                               `exposed_memory_ids`). Per contract OR-10 /
                               `used_memories_observability=NOT_OBSERVABLE`, this is
                               NEVER upgraded to a claim that the memory was actually
                               used/relied upon by the agent -- exposure is not usage.
    COUNTERFACTUAL_EVIDENCE -- backed by a real `counterfactually_influential`
                               `CanonicalEvent`. The ONLY evidence_kind this module ever
                               attaches to an `INFLUENCED` edge. There is no
                               `derive_influenced_edges()` code path that produces an
                               `INFLUENCED` edge from anything else -- if no
                               `counterfactually_influential` event exists for a pair,
                               no `INFLUENCED` edge is produced for it, full stop.
    LINEAGE_REACHABILITY    -- backed by `tainted_memories()`. Explicitly weaker than
                               `COUNTERFACTUAL_EVIDENCE`: reachable-by-derivation does not
                               mean influential, and `PROPAGATED_TO` edges are always
                               tagged this way, never silently upgraded.

REFERENCES -- REOPENED 2026-09-13, BY EXPLICIT USER INSTRUCTION, AFTER THIS STAGE WAS FROZEN
--------------------------------------------------------------------------------
The Post-Phase-5 hardening pass (`PHASE5_POST_FREEZE_HARDENING_REPORT.md` Sec 10)
explicitly declined to infer REFERENCES, for a SPECIFIC reason: it considered, and
rejected, inferring that "the model actually referenced [a memory] in its answer" from
`render_messages()`'s citation format, word overlap, or semantic similarity -- an
agent-BEHAVIOR claim that would require semantic judgment this framework has no
calibrated way to make. That decision is UNCHANGED and this reopening does not revisit
it: `derive_references_edges()` (below) makes no claim about what the model did.

What it derives instead is a narrower, purely STRUCTURAL fact, exactly analogous to
`DERIVED_FROM`: whether one real memory's own persisted CONTENT literally contains
another real memory's exact `[memory_id]` citation-bracket substring (the identical
literal format `agent_runtime/messages.py::render_messages()` itself uses to present a
memory to the model -- reused here only as a textual pattern to search for, never as a
claim about model behavior). This is an exact, deterministic substring match against
real, known memory_ids -- not a heuristic, not word overlap, not semantic similarity --
so it does not reintroduce the case Section 10 rejected. A memory's content either
contains another memory's literal id in that bracket form, or it does not; there is
nothing to judge.

Every produced edge is grounded in the REAL creation-type (`created`/`derived`)
`CanonicalEvent` for the CITING memory -- never a fabricated event, and never the memory
record's own bare `creation_event` string field (which this codebase already learned, in
this same stage's first review, is sometimes only a descriptive marker, not a real,
citable event_id -- see `tainted_memory_evidence()`'s docstring for that exact prior
mistake). `CanonicalEventLedger`'s own single-occurrence invariant for creation-type
events guarantees at most one such event per memory, so this citation is always
unambiguous when it exists.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from phase3.evaluation.foundations.canonical_event import EVENT_COUNTERFACTUALLY_INFLUENTIAL, EVENT_CREATED, EVENT_DERIVED
from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger
from phase3.evaluation.foundations.memory_versioning import SupersessionLedger
from phase3.evaluation.foundations.taint_propagation import tainted_memories

from phase5.schema.event import ATTACK_INJECTION, RETRIEVAL_CANDIDATE_SCORED, ADMISSION_STATUS_ADMITTED
from phase5.schema.event_ledger import Phase5EventLedger

# ---------------------------------------------------------------------------
# Closed relationship vocabulary -- the master prompt's own list (Section 15), made real.
# ---------------------------------------------------------------------------

DERIVED_FROM = "DERIVED_FROM"
PRODUCED = "PRODUCED"
SUPERSEDES = "SUPERSEDES"
RETRIEVED_WITH = "RETRIEVED_WITH"
SELECTED_WITH = "SELECTED_WITH"
USED_BY = "USED_BY"
INFLUENCED = "INFLUENCED"
PROPAGATED_TO = "PROPAGATED_TO"
REFERENCES = "REFERENCES"  # named for completeness; no derive_* function produces it yet

RELATIONSHIP_TYPES: Tuple[str, ...] = (
    DERIVED_FROM, PRODUCED, SUPERSEDES, RETRIEVED_WITH, SELECTED_WITH,
    USED_BY, INFLUENCED, PROPAGATED_TO, REFERENCES,
)

EVIDENCE_OBSERVED_EVENT = "OBSERVED_EVENT"
EVIDENCE_EXPOSURE_ONLY = "EXPOSURE_ONLY"
EVIDENCE_COUNTERFACTUAL = "COUNTERFACTUAL_EVIDENCE"
EVIDENCE_LINEAGE_REACHABILITY = "LINEAGE_REACHABILITY"

EVIDENCE_KINDS: Tuple[str, ...] = (
    EVIDENCE_OBSERVED_EVENT, EVIDENCE_EXPOSURE_ONLY, EVIDENCE_COUNTERFACTUAL, EVIDENCE_LINEAGE_REACHABILITY,
)


@dataclass(frozen=True)
class MemoryInteractionEdge:
    """One relationship fact, always grounded in a citable event id (or ids) -- never
    invented. `relationship_type` and `evidence_kind` are both required and independently
    validated; a caller must never infer evidence strength from relationship_type alone.
    """

    relationship_type: str
    source_id: str
    target_id: str
    evidence_kind: str
    established_by_event_ids: Tuple[str, ...]

    def __post_init__(self) -> None:
        if self.relationship_type not in RELATIONSHIP_TYPES:
            raise ValueError(f"relationship_type {self.relationship_type!r} is not one of {RELATIONSHIP_TYPES!r}.")
        if self.evidence_kind not in EVIDENCE_KINDS:
            raise ValueError(f"evidence_kind {self.evidence_kind!r} is not one of {EVIDENCE_KINDS!r}.")
        if not self.established_by_event_ids:
            raise ValueError("established_by_event_ids must be non-empty -- no edge is ever invented without a citable event.")


def derive_produced_edges(phase5_event_ledger: Phase5EventLedger) -> Tuple[MemoryInteractionEdge, ...]:
    """PRODUCED: attack_id/artifact_id -> memory_id, for every ADMITTED `attack_injection`
    event. `source_id` is the injection_id (the attack attempt), never the bare attack_id
    string -- an attack can produce many memories, and each PRODUCED edge must trace back
    to the ONE injection event that produced that ONE memory."""
    edges = []
    for event in phase5_event_ledger.all_events():
        if event.event_type == ATTACK_INJECTION and event.admission_status == ADMISSION_STATUS_ADMITTED:
            edges.append(MemoryInteractionEdge(
                relationship_type=PRODUCED, source_id=event.injection_id, target_id=event.memory_id,
                evidence_kind=EVIDENCE_OBSERVED_EVENT, established_by_event_ids=(event.event_id,),
            ))
    return tuple(edges)


def derive_derived_from_edges(event_ledger: CanonicalEventLedger) -> Tuple[MemoryInteractionEdge, ...]:
    """DERIVED_FROM: child memory -> each of its real parent memories, wrapping
    `CanonicalEvent`'s own frozen `derived` event type verbatim (never recomputed from
    `parent_ids` directly -- the event is the citable fact)."""
    edges = []
    for event in event_ledger.all_events():
        if event.event_type == EVENT_DERIVED:
            for source_memory_id in event.source_memory_ids:
                edges.append(MemoryInteractionEdge(
                    relationship_type=DERIVED_FROM, source_id=event.target_memory_id, target_id=source_memory_id,
                    evidence_kind=EVIDENCE_OBSERVED_EVENT, established_by_event_ids=(event.event_id,),
                ))
    return tuple(edges)


_CREATION_TYPE_EVENTS: Tuple[str, ...] = (EVENT_CREATED, EVENT_DERIVED)


def _content_text(content: Mapping[str, object]) -> str:
    """Every string value in a `CanonicalMemoryRecord.content` mapping, joined -- never
    assumes a specific key name (e.g. `"text"`) beyond what `content`'s own schema
    guarantees (a mapping), so this works uniformly across every attack's own content
    shape without attack-specific branching (the same discipline Stage 5.4's
    `NORMALIZERS` dict was built to satisfy for injection, applied here to content)."""
    return "\n".join(str(v) for v in content.values() if isinstance(v, str))


def _find_creation_type_event(memory_id: str, event_ledger: CanonicalEventLedger):
    """The one real `created`/`derived` `CanonicalEvent` that established `memory_id`'s
    content -- guaranteed at most one by `CanonicalEventLedger`'s own single-occurrence
    invariant for creation-type events. Returns `None`, never fabricates, if none is
    found (should not happen for a real record, but this function does not assume it)."""
    for event in event_ledger.events_for_memory(memory_id):
        if event.event_type in _CREATION_TYPE_EVENTS:
            return event
    return None


def derive_references_edges(
    memory_ledger: CanonicalMemoryLedger, event_ledger: CanonicalEventLedger,
) -> Tuple[MemoryInteractionEdge, ...]:
    """REFERENCES: citing memory -> cited memory, whenever the citing memory's own real,
    persisted content literally contains the cited memory's exact `[memory_id]`
    citation-bracket substring. See module docstring "REFERENCES -- REOPENED" for why
    this is a structural content fact, never an agent-behavior/usage claim -- this
    function never reads `agent_decision`/`agent_action` output at all, only
    `CanonicalMemoryRecord.content`.

    Grounded in the citing memory's real creation-type event (never its own
    `creation_event` field, which is not always a real, citable event_id -- see
    `_find_creation_type_event()`). A citing memory whose creation-type event cannot be
    found produces no edge for that citation, rather than a fabricated citation
    (mirrors `tainted_memory_evidence()`'s own "report as ungrounded, never invent" rule).

    O(n^2) in the number of real memories, scanning the whole ledger every call -- the
    same disclosed performance characteristic as `derive_produced_edges()`/
    `derive_derived_from_edges()` (see the Post-Phase-5 hardening report's own
    "whole-ledger-scan performance" decision); not optimized here for the same reason.
    """
    records = memory_ledger.list_records()
    all_memory_ids = tuple(r.memory_id for r in records)
    edges: List[MemoryInteractionEdge] = []

    for record in records:
        text = _content_text(record.content)
        if not text:
            continue
        for other_id in all_memory_ids:
            if other_id == record.memory_id:
                continue
            if f"[{other_id}]" not in text:
                continue
            citing_event = _find_creation_type_event(record.memory_id, event_ledger)
            if citing_event is None:
                continue  # honest omission -- never a fabricated citation
            edges.append(MemoryInteractionEdge(
                relationship_type=REFERENCES, source_id=record.memory_id, target_id=other_id,
                evidence_kind=EVIDENCE_OBSERVED_EVENT, established_by_event_ids=(citing_event.event_id,),
            ))
    return tuple(edges)


def derive_supersedes_edges(
    event_ledger: CanonicalEventLedger, supersession_ledger: SupersessionLedger,
) -> Tuple[MemoryInteractionEdge, ...]:
    """SUPERSEDES: superseding memory -> superseded memory, wrapping `SupersessionRecord`s
    verbatim (H.3's own authoritative mechanism, never reinterpreted).

    `SupersessionLedger` exposes no full-enumeration method (only
    `superseder_of(memory_id)`/`get_by_event_id(event_id)`, both point lookups) -- this is
    frozen Phase 3 code and this module does not add one. Instead this iterates the real
    `superseded` `CanonicalEvent`s (which the event ledger DOES let us enumerate via
    `all_events()`) and resolves each to its `SupersessionRecord` via
    `get_by_event_id()`, the exact lookup path `SupersessionLedger` already provides.
    """
    from phase3.evaluation.foundations.canonical_event import EVENT_SUPERSEDED

    edges = []
    for event in event_ledger.all_events():
        if event.event_type == EVENT_SUPERSEDED:
            record = supersession_ledger.get_by_event_id(event.event_id)
            if record is None:
                continue  # honest partial state (supersede_memory()'s own documented possibility) -- never fabricated
            edges.append(MemoryInteractionEdge(
                relationship_type=SUPERSEDES, source_id=record.superseding_memory_id, target_id=record.superseded_memory_id,
                evidence_kind=EVIDENCE_OBSERVED_EVENT, established_by_event_ids=(event.event_id,),
            ))
    return tuple(edges)


def derive_exposed_to_decision_edges(phase5_event_ledger: Phase5EventLedger) -> Tuple[MemoryInteractionEdge, ...]:
    """USED_BY, tagged EXPOSURE_ONLY: memory -> decision_id, for every memory in an
    `agent_decision`'s `exposed_memory_ids`. NEVER upgraded to a stronger usage claim --
    contract OR-10 / `used_memories_observability` governs this exactly, and this
    function does not second-guess it: it names the relationship USED_BY (matching the
    master prompt's own vocabulary) but the `evidence_kind` on every edge it produces
    makes unambiguous that this is exposure, not confirmed use.
    """
    from phase5.schema.event import AGENT_DECISION

    edges = []
    for event in phase5_event_ledger.all_events():
        if event.event_type == AGENT_DECISION:
            for memory_id in event.exposed_memory_ids:
                edges.append(MemoryInteractionEdge(
                    relationship_type=USED_BY, source_id=memory_id, target_id=event.decision_id,
                    evidence_kind=EVIDENCE_EXPOSURE_ONLY, established_by_event_ids=(event.event_id,),
                ))
    return tuple(edges)


def derive_influenced_edges(event_ledger: CanonicalEventLedger) -> Tuple[MemoryInteractionEdge, ...]:
    """INFLUENCED, tagged COUNTERFACTUAL_EVIDENCE: the ONLY relationship this module ever
    derives from `counterfactually_influential` `CanonicalEvent`s -- never from temporal
    ordering, never from mere retrieval/selection/exposure. If no such event exists for a
    memory, no `INFLUENCED` edge exists for it; this function does not synthesize one from
    any other signal."""
    edges = []
    for event in event_ledger.all_events():
        if event.event_type == EVENT_COUNTERFACTUALLY_INFLUENTIAL:
            memory_id = event.memory_ids[0]
            edges.append(MemoryInteractionEdge(
                relationship_type=INFLUENCED, source_id=memory_id, target_id=event.task_id,
                evidence_kind=EVIDENCE_COUNTERFACTUAL, established_by_event_ids=(event.event_id,),
            ))
    return tuple(edges)


@dataclass(frozen=True)
class LineageEvidence:
    """One confirmed-attack -> descendant taint fact, grounded in the REAL `derived`
    `CanonicalEvent`s that establish every hop of a real path between them -- never a
    same-record proxy. `lifecycle_status` is carried through from `TaintReport` verbatim
    (including `LIFECYCLE_STATUS_UNKNOWN_VERSIONING_GAP` when applicable) so that known,
    disclosed limitation stays visible here too, never silently dropped."""

    attack_memory_id: str
    descendant_memory_id: str
    path_memory_ids: Tuple[str, ...]  # attack_memory_id ... descendant_memory_id, inclusive, in order
    supporting_event_ids: Tuple[str, ...]  # one real `derived` event_id per hop, same order as path
    lifecycle_status: str


@dataclass(frozen=True)
class TaintLineageEvidenceReport:
    """Result of `tainted_memory_evidence()`. `ungrounded_descendant_ids` holds every
    descendant `tainted_memories()` confirms reachable but for which NO fully-evidenced
    real event path could be found (e.g. a `CanonicalMemoryRecord` written with
    `parent_ids` set directly, bypassing `record_memory_derivation()`, so no `derived`
    event exists to cite) -- reported explicitly, per the "do not invent event IDs" rule,
    never silently dropped and never given a fabricated citation."""

    attack_memory_ids: Tuple[str, ...]
    evidence: Tuple[LineageEvidence, ...]
    ungrounded_descendant_ids: Tuple[str, ...]


def _find_parent_path(start_id: str, target_id: str, parent_ids_by_memory: Mapping[str, Tuple[str, ...]]) -> Optional[List[str]]:
    """BFS from `start_id` upward through real `parent_ids` edges (the exact same data
    `tainted_memories()`/`descendants()` themselves read from `memory_ledger.list_records()`
    -- never a second, independently-computed graph) until `target_id` is reached. Returns
    the shortest real path (deterministic given `parent_ids`' own tuple order), or `None`
    if unreachable. Cycle-safe via a visited set, mirroring `descendants()`'s own
    cycle-safety discipline."""
    if start_id == target_id:
        return [start_id]
    visited = {start_id}
    queue: deque = deque([[start_id]])
    while queue:
        path = queue.popleft()
        current = path[-1]
        for parent_id in parent_ids_by_memory.get(current, ()):
            if parent_id in visited:
                continue
            new_path = path + [parent_id]
            if parent_id == target_id:
                return new_path
            visited.add(parent_id)
            queue.append(new_path)
    return None


def tainted_memory_evidence(
    memory_ledger: CanonicalMemoryLedger,
    attack_memory_ids: Sequence[str],
    *,
    event_ledger: CanonicalEventLedger,
    supersession_ledger: Optional[SupersessionLedger] = None,
) -> TaintLineageEvidenceReport:
    """Additive companion to `tainted_memories()` -- called here VERBATIM for the
    authoritative reachability computation and `lifecycle_status` (this function changes
    NEITHER `tainted_memories()`'s code NOR its own observable behavior; it is called
    with the exact same arguments a direct caller would use). What this function adds:
    for each confirmed attack -> descendant taint fact, the REAL `derived` event ids that
    establish a concrete path between them, so a caller (namely
    `derive_propagated_to_edges()`, below) never has to fall back to a same-record proxy
    citation.

    Reuses `derive_derived_from_edges()` (this module) for the event-cited parent/child
    hops, and walks the real `parent_ids` data (`memory_ledger.list_records()` -- the
    exact same source `tainted_memories()`/`descendants()` themselves read) via
    `_find_parent_path()` to find one concrete path per descendant. Does NOT reimplement
    `taint_propagation.descendants()`'s own full-reachability-set algorithm -- this is a
    narrower, additive question (one real path's event evidence for an ALREADY-confirmed
    pair), not a second way to decide reachability.
    """
    report = tainted_memories(memory_ledger, attack_memory_ids, event_ledger=event_ledger, supersession_ledger=supersession_ledger)

    # child_memory_id -> [(parent_memory_id, real derived-event_id), ...]
    derived_from_index: Dict[str, List[Tuple[str, str]]] = {}
    for edge in derive_derived_from_edges(event_ledger):
        derived_from_index.setdefault(edge.source_id, []).append((edge.target_id, edge.established_by_event_ids[0]))

    parent_ids_by_memory: Dict[str, Tuple[str, ...]] = {
        record.memory_id: record.parent_ids for record in memory_ledger.list_records()
    }

    evidence: List[LineageEvidence] = []
    ungrounded: List[str] = []

    for attack_id, descendant_ids in report.tainted_by_attack.items():
        for descendant_id in descendant_ids:
            path = _find_parent_path(descendant_id, attack_id, parent_ids_by_memory)
            if path is None:
                ungrounded.append(descendant_id)
                continue
            supporting_event_ids: List[str] = []
            fully_grounded = True
            for child_id, parent_id in zip(path, path[1:]):
                event_id = next((eid for (pid, eid) in derived_from_index.get(child_id, []) if pid == parent_id), None)
                if event_id is None:
                    fully_grounded = False
                    break
                supporting_event_ids.append(event_id)
            if not fully_grounded:
                ungrounded.append(descendant_id)
                continue
            evidence.append(LineageEvidence(
                attack_memory_id=attack_id, descendant_memory_id=descendant_id,
                path_memory_ids=tuple(reversed(path)),
                supporting_event_ids=tuple(reversed(supporting_event_ids)),
                lifecycle_status=report.lifecycle_status.get(descendant_id, ""),
            ))

    return TaintLineageEvidenceReport(
        attack_memory_ids=tuple(attack_memory_ids), evidence=tuple(evidence), ungrounded_descendant_ids=tuple(ungrounded),
    )


def derive_propagated_to_edges(
    memory_ledger: CanonicalMemoryLedger,
    attack_memory_ids: Sequence[str],
    *,
    event_ledger: CanonicalEventLedger,
    supersession_ledger: Optional[SupersessionLedger] = None,
) -> Tuple[MemoryInteractionEdge, ...]:
    """PROPAGATED_TO, tagged LINEAGE_REACHABILITY: now grounded in the GENUINE per-hop
    `derived`-event lineage evidence `tainted_memory_evidence()` exposes (Stage 5.7
    review fix), never the descendant's own `creation_event` (the prior proxy). Reuses
    `tainted_memories()`, unmodified, via `tainted_memory_evidence()` -- this function
    still does not reimplement taint reachability itself.

    `event_ledger` is now REQUIRED (previously optional, used only for
    `lifecycle_status`): genuine per-hop event citation is not possible without it, and
    this function never falls back to a fabricated or same-record citation when it is
    unavailable -- there is no such fallback path anymore.

    A descendant `tainted_memories()` confirms reachable but whose path cannot be FULLY
    grounded in real `derived` events produces NO edge here (see
    `TaintLineageEvidenceReport.ungrounded_descendant_ids`) -- a caller needing full
    visibility into ungrounded taint facts should call `tainted_memory_evidence()`
    directly rather than assume this function's edge list is exhaustive over
    `tainted_memories()`'s own reachable set.
    """
    report = tainted_memory_evidence(
        memory_ledger, attack_memory_ids, event_ledger=event_ledger, supersession_ledger=supersession_ledger,
    )
    return tuple(
        MemoryInteractionEdge(
            relationship_type=PROPAGATED_TO, source_id=ev.attack_memory_id, target_id=ev.descendant_memory_id,
            evidence_kind=EVIDENCE_LINEAGE_REACHABILITY, established_by_event_ids=ev.supporting_event_ids,
        )
        for ev in report.evidence
    )


def query_co_selected_memory_ids(phase5_event_ledger: Phase5EventLedger, task_id: str) -> Tuple[str, ...]:
    """SELECTED_WITH, as a group query. This group-query API is unchanged and remains the
    right choice when only membership (not edge objects) is needed; `derive_co_selected_edges()`
    below is the additive, opt-in pairwise-edge form for a caller (e.g. Stage 5.8) that
    specifically needs `MemoryInteractionEdge` objects."""
    return tuple(
        e.memory_id for e in phase5_event_ledger.events_for_task(task_id)
        if e.event_type == RETRIEVAL_CANDIDATE_SCORED and e.selected
    )


def query_co_retrieved_memory_ids(phase5_event_ledger: Phase5EventLedger, task_id: str) -> Tuple[str, ...]:
    """RETRIEVED_WITH, as a group query over the full candidate pool for one task. This
    group-query API is unchanged; `derive_co_retrieved_edges()` below is the additive,
    opt-in pairwise-edge form -- opt-in and scoped to one task_id at a time, so a caller
    is never forced to pay the O(n^2) cost across an entire run's worth of tasks."""
    return tuple(
        e.memory_id for e in phase5_event_ledger.events_for_task(task_id)
        if e.event_type == RETRIEVAL_CANDIDATE_SCORED
    )


def _derive_co_membership_edges(
    phase5_event_ledger: Phase5EventLedger, task_id: str, *, only_selected: bool, relationship_type: str,
) -> Tuple[MemoryInteractionEdge, ...]:
    """Shared implementation for `derive_co_retrieved_edges()`/`derive_co_selected_edges()`
    -- both are the same construction (deterministic pairwise edges within one task's real
    `retrieval_candidate_scored` events) over a different membership filter. Scoped
    STRICTLY to `task_id` -- one call never crosses into another task's retrieval pool,
    satisfying "only pairs within the same retrieval group" and "never O(n^2) across an
    entire run" by construction (the caller chooses which task(s) to call this for).
    """
    scored_events = [
        e for e in phase5_event_ledger.events_for_task(task_id)
        if e.event_type == RETRIEVAL_CANDIDATE_SCORED and (e.selected if only_selected else True)
    ]
    # Deterministic ordering: sort by memory_id (a stable, content-derived key), never by
    # ledger insertion order (which is real but incidental, not a semantic property worth
    # encoding into edge identity).
    scored_events.sort(key=lambda e: e.memory_id)
    # Deterministic deduplication: if the same memory_id somehow has more than one scored
    # event for this task (should not happen under current wiring, but never assumed),
    # keep only the first (lowest event_id) so a pair is never emitted twice.
    by_memory_id: Dict[str, object] = {}
    for e in scored_events:
        by_memory_id.setdefault(e.memory_id, e)
    memory_ids = sorted(by_memory_id)

    edges = []
    for i in range(len(memory_ids)):
        for j in range(i + 1, len(memory_ids)):
            id_a, id_b = memory_ids[i], memory_ids[j]  # id_a < id_b, lexicographic -- always the same order for a given pair
            event_a, event_b = by_memory_id[id_a], by_memory_id[id_b]
            edges.append(MemoryInteractionEdge(
                relationship_type=relationship_type, source_id=id_a, target_id=id_b,
                evidence_kind=EVIDENCE_OBSERVED_EVENT,
                established_by_event_ids=(event_a.event_id, event_b.event_id),
            ))
    return tuple(edges)


def derive_co_retrieved_edges(phase5_event_ledger: Phase5EventLedger, task_id: str) -> Tuple[MemoryInteractionEdge, ...]:
    """RETRIEVED_WITH pairwise edges for every pair of candidates in ONE task's real
    retrieval pool (`query_co_retrieved_memory_ids()`'s own group, expanded). Deterministic
    ordering/deduplication (see `_derive_co_membership_edges()`); no causal or influence
    claim -- `evidence_kind=OBSERVED_EVENT` records only "these were scored in the same
    real retrieval pool," nothing about what happened to them afterward.
    """
    return _derive_co_membership_edges(phase5_event_ledger, task_id, only_selected=False, relationship_type=RETRIEVED_WITH)


def derive_co_selected_edges(phase5_event_ledger: Phase5EventLedger, task_id: str) -> Tuple[MemoryInteractionEdge, ...]:
    """SELECTED_WITH pairwise edges for every pair of candidates in ONE task's real
    selected (top-K) set (`query_co_selected_memory_ids()`'s own group, expanded). Same
    determinism/no-causal-claim discipline as `derive_co_retrieved_edges()`."""
    return _derive_co_membership_edges(phase5_event_ledger, task_id, only_selected=True, relationship_type=SELECTED_WITH)


__all__ = [
    "DERIVED_FROM", "PRODUCED", "SUPERSEDES", "RETRIEVED_WITH", "SELECTED_WITH",
    "USED_BY", "INFLUENCED", "PROPAGATED_TO", "REFERENCES", "RELATIONSHIP_TYPES",
    "EVIDENCE_OBSERVED_EVENT", "EVIDENCE_EXPOSURE_ONLY", "EVIDENCE_COUNTERFACTUAL",
    "EVIDENCE_LINEAGE_REACHABILITY", "EVIDENCE_KINDS",
    "MemoryInteractionEdge", "LineageEvidence", "TaintLineageEvidenceReport",
    "derive_produced_edges", "derive_derived_from_edges", "derive_supersedes_edges",
    "derive_exposed_to_decision_edges", "derive_influenced_edges", "derive_references_edges",
    "tainted_memory_evidence", "derive_propagated_to_edges",
    "query_co_selected_memory_ids", "query_co_retrieved_memory_ids",
    "derive_co_retrieved_edges", "derive_co_selected_edges",
]
