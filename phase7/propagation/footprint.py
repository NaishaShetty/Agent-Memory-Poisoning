"""Phase 7.2 -- Propagation Footprint Construction.

WHAT THIS MODULE DOES
--------------------------------------------------------------------------------
`build_propagation_footprint()` composes two already-frozen outputs -- a
`phase5.wiring.trace_assembly.PropagationGraph` (itself a composition of every
`phase5.wiring.lineage.derive_*_edges()` function) and the two event ledgers that
graph's edges cite -- into one longitudinal, timestamped structure per poisoned-
memory root. It derives no new edges and reimplements no reachability logic:
the descendant set comes straight from the graph's own `PROPAGATED_TO` edges,
which are themselves `tainted_memories()`'s output, unmodified (Phase 7 plan
Sec 2, 7.2). This module's only additive work is: (a) resolving every edge's
`established_by_event_ids` to a real timestamp/task_id so the footprint can be
read as a function of time, not just a final static set, and (b) collecting
every OTHER real edge that touches a footprint member, so the footprint carries
its full annotated structure (USED_BY, INFLUENCED, REFERENCES, RETRIEVED_WITH,
SELECTED_WITH, PRODUCED), each edge keeping its own `evidence_kind` label.

WHY "TOUCHING", NOT A SECOND REACHABILITY COMPUTATION
--------------------------------------------------------------------------------
The footprint's member-id set (`PropagationFootprint.member_ids`) is fixed once,
from `PROPAGATED_TO` alone -- the one relationship type whose whole job is
lineage reachability from a confirmed root. Every other edge type is then
included only if it already touches that fixed member set (source_id or
target_id in `member_ids`); this module never asks "is X reachable" a second
way for any other edge type. This is a deliberate difference from a full graph
BFS: `USED_BY`/`INFLUENCED` edges point at decision_ids/task_ids, which are
never memory ids and so can never grow `member_ids` themselves -- including
them as "touching" annotations (not reachability) keeps the growth rule
single-sourced in `PROPAGATED_TO`, exactly as `tainted_memories()` intends.

WHY RETRIEVAL-TASK COVERAGE NEEDS A SECOND SOURCE, NOT JUST EDGES
--------------------------------------------------------------------------------
`RETRIEVED_WITH`/`SELECTED_WITH` (`derive_co_retrieved_edges()`/
`derive_co_selected_edges()`) are PAIRWISE by construction: a task that
retrieves/selects exactly one footprint member alongside zero other candidates
produces no edge at all, even though a real `retrieval_candidate_scored` event
for that member in that task genuinely exists. Relying on `touching` edges
alone for "which tasks did this footprint ever appear in" therefore silently
undercounts solo-candidate tasks. `PropagationFootprint.retrieval_task_ids`
closes this without inventing anything: it reuses
`lineage.py::query_co_retrieved_memory_ids()` -- the real, already-frozen GROUP
query over one task's retrieval pool, not a pairwise derivation -- per real
task_id the run's own `retrieval_candidate_scored` events name, exactly the
same task-discovery `build_propagation_graph()` itself already does.

`build_benign_footprint()` -- STAGE 7.3's ENTRY POINT
--------------------------------------------------------------------------------
`build_propagation_footprint()`'s member-id growth rule (`PROPAGATED_TO`) is
attack-only by construction: `derive_propagated_to_edges()` is always scoped to
`tainted_memories()`'s own confirmed-attack-ancestor input, so a benign seed
(no attack anywhere in its ancestry) will always show zero `PROPAGATED_TO`
edges, zero descendants, and a trivially single-node footprint -- not because
nothing downstream of it exists, but because `PROPAGATED_TO` was never meant to
answer that question for a non-attack root. Stage 7.3 (the benign baseline;
Phase 7 plan Sec 4 point 3, Sec 7.3) needs the SAME kind of downstream-footprint
measurement for ordinary memory growth, so it needs a benign-valid growth rule.

`build_benign_footprint()` supplies one: plain `DERIVED_FROM` reachability from
an arbitrary seed memory, with no attack framing at all -- the same forward-BFS
`tainted_memories()` itself performs over `parent_ids`/`derived` events, just
not restricted to a confirmed-attack starting set (nothing about `DERIVED_FROM`
edges themselves is attack-specific; `derive_derived_from_edges()` wraps every
real `derived` `CanonicalEvent` in the ledger, benign or not). This reuses only
the real, already-collected `DERIVED_FROM` edges already in `graph`; it does
not call `tainted_memories()` itself (which requires a confirmed-attack id and
would raise/mismatch for a benign seed) and it does not modify any frozen
Phase 3/5 code. The resulting footprint's `member_ids` therefore carries
`OBSERVED_EVENT` evidence, not `LINEAGE_REACHABILITY` -- an honest difference
from the attack path, disclosed on `build_benign_footprint()` itself, never
silently conflated with attack-rooted reachability.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, FrozenSet, List, Optional, Sequence, Tuple

from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger
from phase5.schema.event import RETRIEVAL_CANDIDATE_SCORED
from phase5.schema.event_ledger import Phase5EventLedger
from phase5.wiring.lineage import DERIVED_FROM, MemoryInteractionEdge, PRODUCED, PROPAGATED_TO, query_co_retrieved_memory_ids
from phase5.wiring.trace_assembly import PropagationGraph


@dataclass(frozen=True)
class FootprintEdge:
    """One `MemoryInteractionEdge` touching the footprint, annotated with the real
    timestamp/task_id resolved from its own `established_by_event_ids` -- never a
    second, independently-guessed time. When an edge cites more than one event
    (e.g. a multi-hop `PROPAGATED_TO` edge, or a pairwise co-membership edge citing
    both members' own events), `established_at` is the LATEST of those real
    timestamps: the moment the edge's own fact became fully true."""

    edge: MemoryInteractionEdge
    established_at: str
    task_id: Optional[str]


@dataclass(frozen=True)
class PropagationFootprint:
    """The longitudinal footprint of one poisoned-memory root: every memory id
    `PROPAGATED_TO` confirms reachable from it (plus the root itself), and every
    real edge touching any of those ids, timestamp-sorted. `member_ids` is the
    LINEAGE_REACHABILITY-only backbone (Phase 7 plan Sec 4, point 1); `edges`
    additionally carries every other evidence kind for context, each edge still
    labeled with its own `evidence_kind` (Phase 7 plan Sec 5, point 2).

    `retrieval_task_ids`: every real task_id in which ANY footprint member was
    retrieved, sourced from `query_co_retrieved_memory_ids()` (a real group
    query over `retrieval_candidate_scored` events) rather than from
    `RETRIEVED_WITH`/`SELECTED_WITH` edges -- so a task that retrieved a
    footprint member alone (no pairing candidate, hence no pairwise edge) is
    still counted here, unlike in `edges`. `evidence_kind` for this source is
    always `OBSERVED_EVENT` (the real `retrieval_candidate_scored` event
    itself), same as any other Stage 5.7-derived OBSERVED_EVENT edge."""

    root_memory_id: str
    member_ids: Tuple[str, ...]
    edges: Tuple[FootprintEdge, ...]
    retrieval_task_ids: Tuple[str, ...] = ()

    def edges_of_type(self, relationship_type: str) -> Tuple[FootprintEdge, ...]:
        return tuple(fe for fe in self.edges if fe.edge.relationship_type == relationship_type)

    def edges_of_evidence_kind(self, evidence_kind: str) -> Tuple[FootprintEdge, ...]:
        return tuple(fe for fe in self.edges if fe.edge.evidence_kind == evidence_kind)


def _resolve_event(
    event_id: str, *, event_ledger: CanonicalEventLedger, phase5_event_ledger: Phase5EventLedger,
) -> Tuple[str, Optional[str]]:
    """(timestamp, task_id) for a real event id, checked against both ledger
    families -- an edge's citing event may be a `CanonicalEvent` or a `Phase5Event`,
    and `MemoryInteractionEdge` itself carries no marker for which. Raises, never
    fabricates, if the id resolves in neither (should not happen for a real edge --
    every `MemoryInteractionEdge` is constructed only from real, citable events)."""
    event = event_ledger.get_event(event_id)
    if event is not None:
        return event.timestamp, event.task_id
    if phase5_event_ledger.exists(event_id):
        p5_event = phase5_event_ledger.get(event_id)
        return p5_event.timestamp, p5_event.task_id
    raise KeyError(
        f"event_id {event_id!r} (cited by a MemoryInteractionEdge) was not found in "
        "either the CanonicalEventLedger or the Phase5EventLedger -- no edge is ever "
        "invented, so this indicates a real ledger/graph mismatch, not a missing case "
        "to silently skip."
    )


def _parsed_timestamp(value: str) -> datetime:
    """Real chronological order, not lexicographic string order -- the frozen
    `_validate_timestamp()` (Phase 3/5) only requires a parseable ISO-8601
    string, never a canonical UTC offset or fixed fractional-second precision,
    so two real timestamps at different offsets (e.g. `+00:00` vs `-04:00`) can
    sort BACKWARDS under plain string comparison even though they are both
    valid. Every timestamp comparison/sort in this module must go through this
    function, never compare `established_at` strings directly. Mirrors the
    frozen validator's own `Z` -> `+00:00` normalization."""
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    return datetime.fromisoformat(normalized)


def _latest(
    event_ids: Tuple[str, ...], *, event_ledger: CanonicalEventLedger, phase5_event_ledger: Phase5EventLedger,
) -> Tuple[str, Optional[str]]:
    resolved = [
        _resolve_event(eid, event_ledger=event_ledger, phase5_event_ledger=phase5_event_ledger)
        for eid in event_ids
    ]
    return max(resolved, key=lambda pair: _parsed_timestamp(pair[0]))


def all_retrieval_task_ids(phase5_event_ledger: Phase5EventLedger) -> Tuple[str, ...]:
    """Every real task_id this run's own `retrieval_candidate_scored` events
    name -- the same task universe `build_propagation_graph()` itself discovers
    for its per-task `RETRIEVED_WITH`/`SELECTED_WITH` composition. Exposed for
    callers (e.g. `benign_baseline.py`) needing the true task denominator for a
    rate signal, not just the tasks one footprint happens to touch."""
    return tuple(sorted({
        e.task_id for e in phase5_event_ledger.all_events()
        if e.event_type == RETRIEVAL_CANDIDATE_SCORED and e.task_id is not None
    }))


def _assemble_footprint(
    root_memory_id: str,
    member_ids: FrozenSet[str],
    *,
    graph: PropagationGraph,
    event_ledger: CanonicalEventLedger,
    phase5_event_ledger: Phase5EventLedger,
) -> PropagationFootprint:
    """Shared assembly step for both `build_propagation_footprint()` (attack-
    rooted, `PROPAGATED_TO`-grown `member_ids`) and `build_benign_footprint()`
    (benign-rooted, `DERIVED_FROM`-grown `member_ids`): given an already-decided
    member-id set, collect every real edge touching it, resolve timestamps, and
    discover retrieval-task coverage. Never decides `member_ids` itself."""
    touching = tuple(
        e for e in graph.edges if e.source_id in member_ids or e.target_id in member_ids
    )

    footprint_edges = []
    for e in touching:
        established_at, task_id = _latest(
            e.established_by_event_ids, event_ledger=event_ledger, phase5_event_ledger=phase5_event_ledger,
        )
        footprint_edges.append(FootprintEdge(edge=e, established_at=established_at, task_id=task_id))
    footprint_edges.sort(
        key=lambda fe: (_parsed_timestamp(fe.established_at), fe.edge.relationship_type, fe.edge.source_id, fe.edge.target_id)
    )

    all_task_ids = all_retrieval_task_ids(phase5_event_ledger)
    retrieval_task_ids = tuple(
        task_id for task_id in all_task_ids
        if set(query_co_retrieved_memory_ids(phase5_event_ledger, task_id)) & member_ids
    )

    return PropagationFootprint(
        root_memory_id=root_memory_id,
        member_ids=tuple(sorted(member_ids)),
        edges=tuple(footprint_edges),
        retrieval_task_ids=retrieval_task_ids,
    )


def _attack_produced_ids(graph: PropagationGraph) -> FrozenSet[str]:
    return frozenset(e.target_id for e in graph.edges_of_type(PRODUCED))


def _attack_tainted_ids(graph: PropagationGraph) -> FrozenSet[str]:
    """Every real memory id this graph's own `PROPAGATED_TO` edges name as a
    descendant of SOME attack root, unioned with the attack roots themselves --
    i.e. every id `build_benign_footprint()` must refuse, so a benign baseline
    can never be silently polluted with real attack data (Phase 7 plan Sec 4
    point 3's whole premise depends on the baseline corpus actually being
    attack-free)."""
    return _attack_produced_ids(graph) | frozenset(
        e.target_id for e in graph.edges_of_type(PROPAGATED_TO)
    )


def build_propagation_footprint(
    root_memory_id: str,
    *,
    graph: PropagationGraph,
    event_ledger: CanonicalEventLedger,
    phase5_event_ledger: Phase5EventLedger,
) -> PropagationFootprint:
    """Build the footprint for `root_memory_id` from an already-assembled
    `PropagationGraph` (`phase5.wiring.trace_assembly.build_propagation_graph()`).
    Pure composition: no ledger is scanned here beyond resolving edge timestamps
    and discovering `retrieval_task_ids` (see module docstring), and no
    reachability is recomputed -- `graph` is trusted as already correct.
    `member_ids` grows only via `PROPAGATED_TO` (`LINEAGE_REACHABILITY`
    evidence) -- for a non-attack root, use `build_benign_footprint()` instead,
    since `PROPAGATED_TO` will always be empty for one (see module docstring).

    `root_memory_id` MUST itself be a real `PRODUCED` target (a genuine attack
    root), never an intermediate descendant of one -- `PROPAGATED_TO` edges
    only ever originate from a confirmed attack root (`derive_propagated_to_edges()`
    is always scoped to this run's own `PRODUCED` targets), never from a
    descendant of one. Calling this on a descendant would silently return a
    misleadingly small (often single-node) footprint rather than raise, so this
    function validates the precondition explicitly instead of trusting the
    caller to already know it."""
    attack_produced_ids = _attack_produced_ids(graph)
    if root_memory_id not in attack_produced_ids:
        raise ValueError(
            f"root_memory_id {root_memory_id!r} is not a PRODUCED target in this graph (real attack roots: "
            f"{sorted(attack_produced_ids)!r}) -- build_propagation_footprint() only accepts a genuine attack "
            "root, since PROPAGATED_TO edges never originate from a descendant of one. To measure downstream "
            "growth from a non-attack memory, use build_benign_footprint() instead."
        )
    descendant_ids: FrozenSet[str] = frozenset(
        e.target_id for e in graph.edges_of_type(PROPAGATED_TO) if e.source_id == root_memory_id
    )
    member_ids: FrozenSet[str] = frozenset({root_memory_id}) | descendant_ids
    return _assemble_footprint(
        root_memory_id, member_ids, graph=graph, event_ledger=event_ledger, phase5_event_ledger=phase5_event_ledger,
    )


def _derived_from_descendants(seed_memory_id: str, graph: PropagationGraph) -> FrozenSet[str]:
    """Every real memory reachable FORWARD from `seed_memory_id` through
    `DERIVED_FROM` edges -- i.e. every memory whose own lineage, followed one
    `DERIVED_FROM` hop at a time (child -> parent), eventually names
    `seed_memory_id`. Cycle-safe via a visited set, mirroring
    `taint_propagation.py::descendants()`'s own cycle-safety discipline. This is
    the benign-valid generalization of what `PROPAGATED_TO`/`tainted_memories()`
    compute for an attack root (module docstring, "build_benign_footprint()")."""
    parent_to_children: Dict[str, List[str]] = {}
    for e in graph.edges_of_type(DERIVED_FROM):
        parent_to_children.setdefault(e.target_id, []).append(e.source_id)

    visited = {seed_memory_id}
    frontier = [seed_memory_id]
    descendants: set = set()
    while frontier:
        current = frontier.pop()
        for child_id in parent_to_children.get(current, ()):
            if child_id in visited:
                continue
            visited.add(child_id)
            descendants.add(child_id)
            frontier.append(child_id)
    return frozenset(descendants)


def build_benign_footprint(
    seed_memory_id: str,
    *,
    graph: PropagationGraph,
    event_ledger: CanonicalEventLedger,
    phase5_event_ledger: Phase5EventLedger,
) -> PropagationFootprint:
    """Build the Stage 7.3 benign-baseline footprint for `seed_memory_id`: the
    same `PropagationFootprint` shape `build_propagation_footprint()` produces,
    but with `member_ids` grown via plain `DERIVED_FROM` reachability
    (`_derived_from_descendants()`) instead of `PROPAGATED_TO` -- valid for ANY
    real memory, attack-produced or not, so it is the right tool for measuring
    ordinary memory growth (no attack present) rather than attack lineage.
    `seed_memory_id` need not be an attack root; a seed with no derived children
    at all simply yields a single-node footprint, which is itself a real,
    countable data point for the baseline (most benign memories have no
    descendants -- a footprint of size 1 is the expected common case, not an
    error).

    `seed_memory_id` MUST NOT be a real attack root or a `PROPAGATED_TO`
    descendant of one (`_attack_tainted_ids()`) -- accepting one would silently
    mix real attack data into what Stage 7.3's whole discipline requires to be
    an attack-free measurement (Phase 7 plan Sec 4 point 3). `benign_seed_memory_ids()`
    already filters attack-produced ids out of its own candidate list, but this
    function validates its own precondition directly rather than trusting every
    caller to have gone through that helper first."""
    tainted_ids = _attack_tainted_ids(graph)
    if seed_memory_id in tainted_ids:
        raise ValueError(
            f"seed_memory_id {seed_memory_id!r} is an attack-produced or attack-tainted memory in this graph "
            "-- build_benign_footprint() refuses it, since admitting real attack data into a benign-baseline "
            "footprint would silently invalidate Stage 7.3's own 'no attack present' premise. Use "
            "build_propagation_footprint() for an attack root instead."
        )
    member_ids = frozenset({seed_memory_id}) | _derived_from_descendants(seed_memory_id, graph)
    return _assemble_footprint(
        seed_memory_id, member_ids, graph=graph, event_ledger=event_ledger, phase5_event_ledger=phase5_event_ledger,
    )


def build_attack_cluster_footprint(
    root_memory_id: str,
    cluster_memory_ids: Sequence[str],
    *,
    graph: PropagationGraph,
    event_ledger: CanonicalEventLedger,
    phase5_event_ledger: Phase5EventLedger,
) -> PropagationFootprint:
    """Build a footprint for an explicitly-given SIBLING cluster of attack-
    produced memories -- e.g. FARMA's own seed + amplification-cycle entries
    (Stage 7.6), which are independent `DIRECT_MEMORY_WRITE`s citing each other
    only through attacker-supplied `cites` metadata, never through a real
    `record_memory_derivation()` call. Neither `build_propagation_footprint()`
    (grows via `PROPAGATED_TO`, i.e. lineage DESCENDANTS of one root) nor
    `build_benign_footprint()` (grows via `DERIVED_FROM`, also a lineage
    relationship) fits this shape: a FARMA amplification cycle is not derived
    FROM the seed in Phase 5's lineage model, so both would report a
    single-node footprint for the seed even though 10+ real sibling memories
    from the same attack sequence exist. This constructor makes NO
    reachability decision of its own -- `cluster_memory_ids` is taken exactly
    as given, and the only check performed is that every id in it is a real
    `PRODUCED` target (never a benign or non-existent id silently accepted).

    `root_memory_id` is carried only as a display/identity anchor on the
    returned `PropagationFootprint` (e.g. the cluster's own seed artifact) and
    MUST itself be one of `cluster_memory_ids`."""
    if root_memory_id not in cluster_memory_ids:
        raise ValueError(f"root_memory_id {root_memory_id!r} must be one of cluster_memory_ids {sorted(cluster_memory_ids)!r}.")
    attack_produced_ids = _attack_produced_ids(graph)
    non_attack_ids = set(cluster_memory_ids) - attack_produced_ids
    if non_attack_ids:
        raise ValueError(
            f"cluster_memory_ids contains id(s) that are not real PRODUCED targets in this graph: "
            f"{sorted(non_attack_ids)!r} -- build_attack_cluster_footprint() never silently accepts a "
            "non-attack or nonexistent id into an attack-cluster measurement."
        )
    return _assemble_footprint(
        root_memory_id, frozenset(cluster_memory_ids), graph=graph, event_ledger=event_ledger, phase5_event_ledger=phase5_event_ledger,
    )


def footprint_growth(footprint: PropagationFootprint) -> Tuple[Tuple[str, int], ...]:
    """The longitudinal view Sec 4 point 1 asks for: cumulative distinct member-id
    count as a function of time, one point per real edge (already timestamp-sorted
    on `footprint.edges`). Not a new computation over ledger state -- purely a
    re-presentation of `footprint.edges` as a growth curve."""
    seen = {footprint.root_memory_id}
    points = []
    for fe in footprint.edges:
        seen.add(fe.edge.source_id)
        seen.add(fe.edge.target_id)
        points.append((fe.established_at, len(seen)))
    return tuple(points)


__all__ = [
    "FootprintEdge", "PropagationFootprint",
    "build_propagation_footprint", "build_benign_footprint", "build_attack_cluster_footprint", "footprint_growth",
    "all_retrieval_task_ids",
]
