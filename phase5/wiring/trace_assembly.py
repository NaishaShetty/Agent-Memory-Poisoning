"""Phase 5.8 -- Trace Assembly & Propagation Graph.

WHAT THIS STAGE IS
--------------------------------------------------------------------------------
Every prior Phase 5 stage (5.2-5.7) added either a new persisted event family or a
derivation function over already-persisted events -- but nothing yet ASSEMBLES all of
it, for one experiment run, into the single structured trace the master prompt's own
architecture diagram describes (Experiment / Injection / Memory Lifecycle / Agent Events
/ Memory Evolution / Outcome), or composes Stage 5.7's lineage functions into one
propagation graph. This module is that assembly layer -- pure composition and query, no
new event type, no new ledger, nothing computed here that a later stage could not
recompute identically from the same persisted state.

WHY THIS IS POSSIBLE AT ALL: STAGE 5.3's MEMBERSHIP LEDGER
--------------------------------------------------------------------------------
`EventRunMembershipLedger.events_for_run(run_id)` (Stage 5.3) is the one mechanism that
makes "assemble everything that happened in run X" a well-defined query instead of a
guess: every event this framework's Phase 5 wiring ever appends -- whichever of the two
schemas (`CanonicalEvent` or `Phase5Event`) minted it -- is registered there. This module
does nothing more than: ask that ledger for the run's event ids, resolve each to its real
event object via `EventRunMembership.event_schema`, and bucket the results.

WHY THE PROPAGATION GRAPH IS SCOPED PER RUN, NOT GLOBAL
--------------------------------------------------------------------------------
Stage 5.7's `derive_*` functions each scan their WHOLE ledger (`all_events()`), not one
run's slice of it -- correct for their own purpose (a caller decides what ledger to hand
them), but wrong for "the propagation graph for THIS experiment" if a ledger directory
ever holds more than one run's events. `build_propagation_graph()` therefore calls every
Stage 5.7 function exactly as before (never reimplementing any of them) and then filters
their output to edges whose `established_by_event_ids` are ALL registered to `run_id` via
the membership ledger -- the one correct way to scope a derived-elsewhere fact to one run
without asking Stage 5.7's functions to know about runs themselves.

"DERIVED FROM PERSISTED EVIDENCE, NOT MANUALLY CONSTRUCTED" (master prompt, Stage 5.8)
--------------------------------------------------------------------------------
Every function in this module is read-only and recomputes its output fresh, every call,
from ledger state -- exactly `ProvenanceGraph`'s own "a projection, never a second store"
discipline, extended to the cross-schema, whole-trace case.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from phase3.evaluation.foundations.canonical_event import (
    CanonicalEvent,
    EVENT_CREATED,
    EVENT_DERIVED,
    EVENT_COUNTERFACTUALLY_INFLUENTIAL,
    EVENT_REJECTED,
    EVENT_RELATIONSHIP_DETECTED,
    EVENT_RETIRED,
    EVENT_RETRIEVED,
    EVENT_SELECTED,
    EVENT_SUPERSEDED,
    EVENT_USED,
)
from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger
from phase3.evaluation.foundations.memory_versioning import SupersessionLedger

from phase5.identity.run_identity import EVENT_SCHEMA_CANONICAL_EVENT, EventRunMembershipLedger
from phase5.schema.event import (
    AGENT_ACTION,
    AGENT_DECISION,
    ATTACK_GROUND_TRUTH_TRANSITION,
    ATTACK_INJECTION,
    CONTEXT_ASSEMBLED,
    RETRIEVAL_CANDIDATE_SCORED,
    Phase5Event,
)
from phase5.schema.event_ledger import Phase5EventLedger
from phase5.wiring.lineage import (
    MemoryInteractionEdge,
    derive_co_retrieved_edges,
    derive_co_selected_edges,
    derive_derived_from_edges,
    derive_exposed_to_decision_edges,
    derive_influenced_edges,
    derive_produced_edges,
    derive_propagated_to_edges,
    derive_references_edges,
    derive_supersedes_edges,
)


@dataclass(frozen=True)
class ExperimentTrace:
    """The full, structured trace for one run_id -- one section per branch of the master
    prompt's own trace-assembly diagram. Every field is a tuple of REAL event objects
    (`CanonicalEvent` or `Phase5Event`), resolved from the ledgers, never summarized or
    lossily reinterpreted. An empty tuple means "no such event exists for this run,"
    never "not checked.\""""

    run_id: str
    # Injection
    injections: Tuple[Phase5Event, ...]
    # Memory Lifecycle
    memory_created: Tuple[CanonicalEvent, ...]
    memory_derived: Tuple[CanonicalEvent, ...]
    memory_superseded: Tuple[CanonicalEvent, ...]
    memory_retired: Tuple[CanonicalEvent, ...]
    memory_retrieved: Tuple[CanonicalEvent, ...]
    memory_selected: Tuple[CanonicalEvent, ...]
    memory_rejected: Tuple[CanonicalEvent, ...]
    memory_used: Tuple[CanonicalEvent, ...]
    retrieval_candidates_scored: Tuple[Phase5Event, ...]
    # Agent Events
    context_assembled: Tuple[Phase5Event, ...]
    agent_decisions: Tuple[Phase5Event, ...]
    agent_actions: Tuple[Phase5Event, ...]
    # Memory Evolution
    relationships_detected: Tuple[CanonicalEvent, ...]
    # Outcome
    ground_truth_transitions: Tuple[Phase5Event, ...]
    counterfactual_findings: Tuple[CanonicalEvent, ...]
    # Anything registered to this run whose event_id could not be resolved in either
    # ledger (should not happen under normal wiring -- surfaced explicitly, never
    # silently dropped, mirroring this project's own "honest accounting" convention).
    unresolved_event_ids: Tuple[str, ...] = field(default_factory=tuple)


def assemble_trace(
    run_id: str,
    *,
    event_ledger: CanonicalEventLedger,
    phase5_event_ledger: Phase5EventLedger,
    membership_ledger: EventRunMembershipLedger,
) -> ExperimentTrace:
    """Assemble the complete trace for `run_id` purely from persisted ledger state --
    never from in-process objects a caller happens to still be holding. Two calls with
    the same ledgers and `run_id` always produce the identical trace (determinism, per
    Stage 5.9's own upcoming requirement)."""
    event_ids = membership_ledger.events_for_run(run_id)

    buckets: Dict[str, List] = {
        "injections": [], "memory_created": [], "memory_derived": [], "memory_superseded": [],
        "memory_retired": [], "memory_retrieved": [], "memory_selected": [], "memory_rejected": [],
        "memory_used": [], "retrieval_candidates_scored": [], "context_assembled": [],
        "agent_decisions": [], "agent_actions": [], "relationships_detected": [],
        "ground_truth_transitions": [], "counterfactual_findings": [],
    }
    unresolved: List[str] = []

    _CANONICAL_BUCKET_BY_TYPE = {
        EVENT_CREATED: "memory_created",
        EVENT_DERIVED: "memory_derived",
        EVENT_SUPERSEDED: "memory_superseded",
        EVENT_RETIRED: "memory_retired",
        EVENT_RETRIEVED: "memory_retrieved",
        EVENT_SELECTED: "memory_selected",
        EVENT_REJECTED: "memory_rejected",
        EVENT_USED: "memory_used",
        EVENT_RELATIONSHIP_DETECTED: "relationships_detected",
        EVENT_COUNTERFACTUALLY_INFLUENTIAL: "counterfactual_findings",
    }
    _PHASE5_BUCKET_BY_TYPE = {
        ATTACK_INJECTION: "injections",
        RETRIEVAL_CANDIDATE_SCORED: "retrieval_candidates_scored",
        CONTEXT_ASSEMBLED: "context_assembled",
        AGENT_DECISION: "agent_decisions",
        AGENT_ACTION: "agent_actions",
        ATTACK_GROUND_TRUTH_TRANSITION: "ground_truth_transitions",
    }

    for event_id in event_ids:
        membership = membership_ledger.run_for_event(event_id)
        if membership is None:
            unresolved.append(event_id)
            continue
        if membership.event_schema == EVENT_SCHEMA_CANONICAL_EVENT:
            event = event_ledger.get_event(event_id)
            bucket_name = _CANONICAL_BUCKET_BY_TYPE.get(event.event_type) if event is not None else None
        else:
            event = phase5_event_ledger.get(event_id) if phase5_event_ledger.exists(event_id) else None
            bucket_name = _PHASE5_BUCKET_BY_TYPE.get(event.event_type) if event is not None else None

        if event is None or bucket_name is None:
            unresolved.append(event_id)
            continue
        buckets[bucket_name].append(event)

    return ExperimentTrace(
        run_id=run_id,
        injections=tuple(buckets["injections"]),
        memory_created=tuple(buckets["memory_created"]),
        memory_derived=tuple(buckets["memory_derived"]),
        memory_superseded=tuple(buckets["memory_superseded"]),
        memory_retired=tuple(buckets["memory_retired"]),
        memory_retrieved=tuple(buckets["memory_retrieved"]),
        memory_selected=tuple(buckets["memory_selected"]),
        memory_rejected=tuple(buckets["memory_rejected"]),
        memory_used=tuple(buckets["memory_used"]),
        retrieval_candidates_scored=tuple(buckets["retrieval_candidates_scored"]),
        context_assembled=tuple(buckets["context_assembled"]),
        agent_decisions=tuple(buckets["agent_decisions"]),
        agent_actions=tuple(buckets["agent_actions"]),
        relationships_detected=tuple(buckets["relationships_detected"]),
        ground_truth_transitions=tuple(buckets["ground_truth_transitions"]),
        counterfactual_findings=tuple(buckets["counterfactual_findings"]),
        unresolved_event_ids=tuple(unresolved),
    )


@dataclass(frozen=True)
class PropagationGraph:
    """The run-scoped propagation/lineage graph: every `MemoryInteractionEdge` Stage 5.7
    can derive, filtered to edges whose citing event(s) are ALL registered to `run_id`.
    A projection, like `ProvenanceGraph` -- never a second store, recomputed fresh."""

    run_id: str
    edges: Tuple[MemoryInteractionEdge, ...]

    def edges_of_type(self, relationship_type: str) -> Tuple[MemoryInteractionEdge, ...]:
        return tuple(e for e in self.edges if e.relationship_type == relationship_type)

    def edges_touching(self, memory_or_id: str) -> Tuple[MemoryInteractionEdge, ...]:
        return tuple(e for e in self.edges if e.source_id == memory_or_id or e.target_id == memory_or_id)


def _edge_belongs_to_run(edge: MemoryInteractionEdge, run_id: str, membership_ledger: EventRunMembershipLedger) -> bool:
    for event_id in edge.established_by_event_ids:
        membership = membership_ledger.run_for_event(event_id)
        if membership is None or membership.run_id != run_id:
            return False
    return True


def assemble_task_trace(run_id: str, task_id: str, *, event_ledger: CanonicalEventLedger, phase5_event_ledger: Phase5EventLedger, membership_ledger: EventRunMembershipLedger) -> ExperimentTrace:
    """Post-Phase-5 hardening, Section 15: a read-only convenience projection that
    FILTERS `assemble_trace()`'s own output down to one task -- it does not re-query the
    ledgers independently, and it is not a second source of truth. Run-scoped fields with
    no `task_id` of their own (`memory_created`/`memory_derived`/`memory_superseded`/
    `memory_retired`/`injections`) are passed through UNFILTERED -- a memory's creation or
    an attack's injection is a run-level fact, not owned by any one task, so narrowing it
    to "this task's events" would silently drop a fact this task's own retrieval/decision
    events still depend on for reconstruction. Every task-scoped field is filtered to
    events whose own `task_id` matches.
    """
    full_trace = assemble_trace(run_id, event_ledger=event_ledger, phase5_event_ledger=phase5_event_ledger, membership_ledger=membership_ledger)

    def _keep(events):
        return tuple(e for e in events if getattr(e, "task_id", None) == task_id)

    return ExperimentTrace(
        run_id=run_id,
        injections=full_trace.injections,  # run-level fact, not task-owned
        memory_created=full_trace.memory_created,  # run-level fact, not task-owned
        memory_derived=full_trace.memory_derived,  # run-level fact, not task-owned
        memory_superseded=full_trace.memory_superseded,  # run-level fact, not task-owned
        memory_retired=full_trace.memory_retired,  # run-level fact, not task-owned
        memory_retrieved=_keep(full_trace.memory_retrieved),
        memory_selected=_keep(full_trace.memory_selected),
        memory_rejected=_keep(full_trace.memory_rejected),
        memory_used=_keep(full_trace.memory_used),
        retrieval_candidates_scored=_keep(full_trace.retrieval_candidates_scored),
        context_assembled=_keep(full_trace.context_assembled),
        agent_decisions=_keep(full_trace.agent_decisions),
        agent_actions=_keep(full_trace.agent_actions),
        relationships_detected=full_trace.relationships_detected,  # no task_id field on this event type
        ground_truth_transitions=full_trace.ground_truth_transitions,  # not currently task-scoped by any producer
        counterfactual_findings=_keep(full_trace.counterfactual_findings),
        unresolved_event_ids=full_trace.unresolved_event_ids,
    )


def build_propagation_graph(
    run_id: str,
    *,
    memory_ledger: CanonicalMemoryLedger,
    event_ledger: CanonicalEventLedger,
    phase5_event_ledger: Phase5EventLedger,
    membership_ledger: EventRunMembershipLedger,
    supersession_ledger: Optional[SupersessionLedger] = None,
) -> PropagationGraph:
    """Compose every applicable Stage 5.7 `derive_*` function -- calling each exactly as
    Stage 5.7 defines it, never reimplementing any of them -- then filter to this run's
    own edges via `_edge_belongs_to_run()`. `PRODUCED`/`DERIVED_FROM`/`SUPERSEDES`/
    `USED_BY`/`INFLUENCED`/`REFERENCES` need no extra parameters beyond the ledgers
    themselves; `RETRIEVED_WITH`/`SELECTED_WITH` are derived per task_id (discovered from
    this run's own `retrieval_candidate_scored` events); `PROPAGATED_TO` is derived from
    this run's own `PRODUCED` targets (the memories this run's attacks actually
    produced), never a caller-supplied, potentially-stale attack id list.

    `REFERENCES` (Stage 5.7 reopened 2026-09-13, then reconciled into this composition
    2026-09-13) is composed exactly like every other unconditional Stage 5.7 edge type
    above -- this stage's own documented contract has always been "every applicable
    Stage 5.7 `derive_*` function" (see `PHASE5_5_8_TRACE_ASSEMBLY_PROPAGATION_GRAPH.md`),
    and `RETRIEVED_WITH`/`USED_BY`/etc. already establish that this graph represents the
    complete Stage 5.7 relationship vocabulary, not a narrower propagation/lineage-only
    subset -- so once a real `derive_*` function existed for `REFERENCES`, composing it
    here was the contract already in force, not a new design decision.
    """
    all_edges: List[MemoryInteractionEdge] = []

    produced_edges = derive_produced_edges(phase5_event_ledger)
    all_edges.extend(produced_edges)
    all_edges.extend(derive_derived_from_edges(event_ledger))
    if supersession_ledger is not None:
        all_edges.extend(derive_supersedes_edges(event_ledger, supersession_ledger))
    all_edges.extend(derive_exposed_to_decision_edges(phase5_event_ledger))
    all_edges.extend(derive_influenced_edges(event_ledger))
    all_edges.extend(derive_references_edges(memory_ledger, event_ledger))

    # Scope PROPAGATED_TO to attack memory ids this RUN's own PRODUCED edges name --
    # never an externally-supplied, potentially cross-run list.
    run_produced_edges = [e for e in produced_edges if _edge_belongs_to_run(e, run_id, membership_ledger)]
    attack_memory_ids = tuple(sorted({e.target_id for e in run_produced_edges}))
    if attack_memory_ids:
        all_edges.extend(derive_propagated_to_edges(
            memory_ledger, attack_memory_ids, event_ledger=event_ledger, supersession_ledger=supersession_ledger,
        ))

    # Pairwise co-retrieval/co-selection, per distinct task_id this run's own
    # retrieval_candidate_scored events name.
    task_ids = sorted({
        e.task_id for e in phase5_event_ledger.all_events()
        if e.event_type == RETRIEVAL_CANDIDATE_SCORED
    })
    for task_id in task_ids:
        task_edges = derive_co_retrieved_edges(phase5_event_ledger, task_id) + derive_co_selected_edges(phase5_event_ledger, task_id)
        all_edges.extend(e for e in task_edges if _edge_belongs_to_run(e, run_id, membership_ledger))

    scoped_edges = tuple(e for e in all_edges if _edge_belongs_to_run(e, run_id, membership_ledger))
    return PropagationGraph(run_id=run_id, edges=scoped_edges)


__all__ = [
    "ExperimentTrace",
    "assemble_trace",
    "assemble_task_trace",
    "PropagationGraph",
    "build_propagation_graph",
]
