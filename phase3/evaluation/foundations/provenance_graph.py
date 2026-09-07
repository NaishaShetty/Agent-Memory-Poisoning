"""Phase 3.3-H4-PROVENANCE-GRAPH (+ EXTENSION PASS) — a real, persisted-by-projection
lifecycle/provenance graph. Original version built this session; extended per
`PHASE3_PROVENANCE_GRAPH_DESIGN_REVIEW.md` after that design was reviewed, closing the
gaps that review identified: memory-version nodes, experiment-boundary nodes (so a clean
run and a manipulated run can be represented side by side without inventing cross-boundary
edges), a formal persistence schema (`phase3/schemas/provenance_graph_schema.json`), and
named, Phase-4-facing query functions -- most importantly wiring `taint_propagation.py`'s
`tainted_memories()` into the graph for the first time (`attack_origin_lineage()`).

DESIGN DECISION -- A PROJECTION, NOT A NEW STORE (UNCHANGED BY THE EXTENSION)
--------------------------------------------------------------------------------
`ProvenanceGraph` is built fresh, every call, from already-persisted
`CanonicalMemoryLedger`/`CanonicalEventLedger`/`SupersessionLedger` state -- exactly the
discipline H.3's `CanonicalMemoryVersion` established ("a version is a pure, deterministic
projection over the event log... no separate versions.jsonl store"). This still holds for
every extension below, including multi-boundary graphs (§ build_multi_boundary_
provenance_graph): a multi-boundary graph is still nothing but a composition of several
single-boundary projections, never a new mutable store.

GROUNDING -- NO EDGE IS EVER INVENTED (UNCHANGED)
--------------------------------------------------------------------------------
Every edge carries `established_by_event_id` (or, for `derived_from`, the child memory's
own `creation_event` string; for `has_version`, the version's own `established_by_event_id`;
for `within_boundary`, the boundary's own `boundary_id`) pointing at the real record that
produced it. `used` edges only appear if a real `used` `CanonicalEvent` exists -- confirmed,
still, that no real runtime code appends one, so they remain legitimately absent from every
graph built against real data today.

MULTI-BOUNDARY GRAPHS -- NEVER A SYNTHESIZED CROSS-BOUNDARY EDGE
--------------------------------------------------------------------------------
`build_multi_boundary_provenance_graph()` composes N single-boundary graphs into one
`ProvenanceGraph` object, purely for a caller's convenience in iterating/comparing them
side by side (e.g. a clean run vs. a manipulated run). Node ids are namespaced
`f"{boundary_label}::{canonical_id}"` to prevent collision (the RAW canonical id is always
preserved in `attributes["canonical_id"]`, per the identity requirement -- see §7 of the
design review). **This function never adds an edge between two nodes from different
boundaries.** Phase 3 has no basis to know that memory X in one boundary "corresponds to"
memory X' in another -- that correspondence is a Phase 4 analysis decision this module
must never make on Phase 4's behalf. Tested directly (`test_multi_boundary_never_synthesizes_cross_boundary_edges`).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from phase3.evaluation.foundations.canonical_event import (
    CanonicalEvent,
    EVENT_COUNTERFACTUALLY_INFLUENTIAL,
    EVENT_CREATED,
    EVENT_DERIVED,
    EVENT_REJECTED,
    EVENT_RELATIONSHIP_DETECTED,
    EVENT_RETIRED,
    EVENT_RETRIEVED,
    EVENT_SELECTED,
    EVENT_SUPERSEDED,
    EVENT_USED,
    RELATIONSHIP_CONFLICTS_WITH,
    RELATIONSHIP_EQUIVALENT_TO,
)
from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger
from phase3.evaluation.foundations.memory_versioning import (
    SupersessionLedger,
    get_current_version,
    reconstruct_version_history,
)

# ---------------------------------------------------------------------------
# Node/edge type vocabulary -- closed, no free-form types invented at call time.
# ---------------------------------------------------------------------------

NODE_TYPE_MEMORY = "memory"
NODE_TYPE_TASK = "task"
NODE_TYPE_MEMORY_VERSION = "memory_version"
NODE_TYPE_EXPERIMENT_BOUNDARY = "experiment_boundary"
NODE_TYPES: Tuple[str, ...] = (NODE_TYPE_MEMORY, NODE_TYPE_TASK, NODE_TYPE_MEMORY_VERSION, NODE_TYPE_EXPERIMENT_BOUNDARY)

EDGE_DERIVED_FROM = "derived_from"
EDGE_RETRIEVED = "retrieved"
EDGE_SELECTED = "selected"
EDGE_REJECTED = "rejected"
EDGE_USED = "used"
EDGE_COUNTERFACTUALLY_INFLUENTIAL = "counterfactually_influential"
EDGE_SUPERSEDED_BY = "superseded_by"
EDGE_EQUIVALENT_TO = "equivalent_to"
EDGE_CONFLICTS_WITH = "conflicts_with"
EDGE_HAS_VERSION = "has_version"
EDGE_WITHIN_BOUNDARY = "within_boundary"

EDGE_TYPES: Tuple[str, ...] = (
    EDGE_DERIVED_FROM, EDGE_RETRIEVED, EDGE_SELECTED, EDGE_REJECTED, EDGE_USED,
    EDGE_COUNTERFACTUALLY_INFLUENTIAL, EDGE_SUPERSEDED_BY, EDGE_EQUIVALENT_TO, EDGE_CONFLICTS_WITH,
    EDGE_HAS_VERSION, EDGE_WITHIN_BOUNDARY,
)

# task-scoped edge types -- carry a task_id; memory-to-memory edge types never do.
_TASK_SCOPED_EDGE_TYPES: Tuple[str, ...] = (
    EDGE_RETRIEVED, EDGE_SELECTED, EDGE_REJECTED, EDGE_USED, EDGE_COUNTERFACTUALLY_INFLUENTIAL,
)

LIFECYCLE_STATUS_CURRENT = "CURRENT"
LIFECYCLE_STATUS_AT_CREATION_ONLY = "AT_CREATION_ONLY"

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "provenance_graph_schema.json"


class ProvenanceGraphError(ValueError):
    """Raised for a caller error (e.g. requesting a node that doesn't exist) -- never for
    a data-integrity problem the underlying ledgers would themselves already reject."""


@dataclass(frozen=True)
class GraphNode:
    node_id: str
    node_type: str
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.node_type not in NODE_TYPES:
            raise ProvenanceGraphError(f"node_type {self.node_type!r} is not one of {NODE_TYPES!r}.")


@dataclass(frozen=True)
class GraphEdge:
    source_id: str
    target_id: str
    edge_type: str
    established_by_event_id: Optional[str] = None
    task_id: Optional[str] = None

    def __post_init__(self) -> None:
        if self.edge_type not in EDGE_TYPES:
            raise ProvenanceGraphError(f"edge_type {self.edge_type!r} is not one of {EDGE_TYPES!r}.")
        if self.edge_type in _TASK_SCOPED_EDGE_TYPES and not self.task_id:
            raise ProvenanceGraphError(f"edge_type {self.edge_type!r} requires task_id.")
        if self.edge_type not in _TASK_SCOPED_EDGE_TYPES and self.task_id is not None:
            raise ProvenanceGraphError(f"edge_type {self.edge_type!r} must not carry task_id.")


@dataclass(frozen=True)
class ProvenanceGraph:
    """Read-only view. Never constructed directly by a caller -- always via
    `build_provenance_graph()`/`build_multi_boundary_provenance_graph()`, so every edge is
    guaranteed grounded (§ module docstring)."""

    nodes: Tuple[GraphNode, ...]
    edges: Tuple[GraphEdge, ...]

    def __post_init__(self) -> None:
        node_ids = {n.node_id for n in self.nodes}
        if len(node_ids) != len(self.nodes):
            raise ProvenanceGraphError("duplicate node_id in nodes -- one node per id, never merged.")
        for e in self.edges:
            if e.source_id not in node_ids:
                raise ProvenanceGraphError(f"edge source_id {e.source_id!r} has no corresponding node -- never a dangling edge.")
            if e.target_id not in node_ids:
                raise ProvenanceGraphError(f"edge target_id {e.target_id!r} has no corresponding node -- never a dangling edge.")

    def node(self, node_id: str) -> Optional[GraphNode]:
        return next((n for n in self.nodes if n.node_id == node_id), None)

    def nodes_of_type(self, node_type: str) -> Tuple[GraphNode, ...]:
        return tuple(n for n in self.nodes if n.node_type == node_type)

    def memory_ids(self) -> Tuple[str, ...]:
        return tuple(n.node_id for n in self.nodes if n.node_type == NODE_TYPE_MEMORY)

    def task_ids(self) -> Tuple[str, ...]:
        return tuple(n.node_id for n in self.nodes if n.node_type == NODE_TYPE_TASK)

    def edges_from(self, node_id: str, edge_type: Optional[str] = None) -> Tuple[GraphEdge, ...]:
        return tuple(e for e in self.edges if e.source_id == node_id and (edge_type is None or e.edge_type == edge_type))

    def edges_to(self, node_id: str, edge_type: Optional[str] = None) -> Tuple[GraphEdge, ...]:
        return tuple(e for e in self.edges if e.target_id == node_id and (edge_type is None or e.edge_type == edge_type))

    def edges_for_task(self, task_id: str) -> Tuple[GraphEdge, ...]:
        return tuple(e for e in self.edges if e.task_id == task_id)

    def ancestors_of(self, memory_id: str) -> Set[str]:
        """Transitively walk `derived_from` edges UPWARD (parents). Cycle-safe: a node
        already visited is never re-descended into."""
        visited: Set[str] = set()
        frontier = [memory_id]
        while frontier:
            current = frontier.pop()
            for e in self.edges_from(current, EDGE_DERIVED_FROM):
                if e.target_id not in visited:
                    visited.add(e.target_id)
                    frontier.append(e.target_id)
        return visited

    def descendants_of(self, memory_id: str) -> Set[str]:
        """Transitively walk `derived_from` edges DOWNWARD (children)."""
        visited: Set[str] = set()
        frontier = [memory_id]
        while frontier:
            current = frontier.pop()
            for e in self.edges_to(current, EDGE_DERIVED_FROM):
                if e.source_id not in visited:
                    visited.add(e.source_id)
                    frontier.append(e.source_id)
        return visited

    def to_dict(self) -> Dict[str, Any]:
        """Export-only serialization matching `schemas/provenance_graph_schema.json`
        exactly. NOT the authoritative representation -- rebuilding from the ledgers via
        `build_provenance_graph()` always is; this is a snapshot, not a second store. No
        `load_provenance_graph_from_json()` counterpart exists, deliberately -- the only
        path back to a `ProvenanceGraph` object is rebuilding from the live ledgers."""
        return {
            "nodes": [{"node_id": n.node_id, "node_type": n.node_type, "attributes": dict(n.attributes)} for n in self.nodes],
            "edges": [
                {
                    "source_id": e.source_id, "target_id": e.target_id, "edge_type": e.edge_type,
                    "established_by_event_id": e.established_by_event_id, "task_id": e.task_id,
                }
                for e in self.edges
            ],
        }


def _memory_node_attributes(
    record,
    memory_ledger: CanonicalMemoryLedger,
    event_ledger: Optional[CanonicalEventLedger],
    supersession_ledger: Optional[SupersessionLedger],
) -> Tuple[Dict[str, Any], Optional[Tuple[str, str]]]:
    """Returns `(attributes, superseded_by_grounding)`, where `superseded_by_grounding`
    is `None` or `(superseding_memory_id, established_by_event_id)`. See H.3-R2 note: safe
    to call `get_current_version()` unconditionally now that that bug is fixed."""
    attrs: Dict[str, Any] = {
        "canonical_id": record.memory_id,
        "memory_type": record.memory_type,
        "creation_timestamp": record.creation_timestamp,
        "creation_event": record.creation_event,
    }
    if event_ledger is not None and supersession_ledger is not None:
        try:
            current = get_current_version(event_ledger, memory_ledger, supersession_ledger, record.memory_id)
        except Exception:
            current = None
        if current is not None:
            attrs["lifecycle_state"] = current.lifecycle_state
            attrs["lifecycle_status"] = LIFECYCLE_STATUS_CURRENT
            attrs["superseded_by"] = current.superseded_by
            grounding = (current.superseded_by, current.established_by_event_id) if current.superseded_by else None
            return attrs, grounding
    attrs["lifecycle_state"] = record.lifecycle_state
    attrs["lifecycle_status"] = LIFECYCLE_STATUS_AT_CREATION_ONLY
    attrs["superseded_by"] = None
    return attrs, None


def _prefixed(boundary_label: Optional[str], raw_id: str) -> str:
    return f"{boundary_label}::{raw_id}" if boundary_label else raw_id


def build_provenance_graph(
    memory_ledger: CanonicalMemoryLedger,
    event_ledger: CanonicalEventLedger,
    supersession_ledger: Optional[SupersessionLedger] = None,
    *,
    include_versions: bool = False,
    boundary_label: Optional[str] = None,
) -> ProvenanceGraph:
    """Build a `ProvenanceGraph` from exactly one `(memory_ledger, event_ledger[,
    supersession_ledger])` triple -- the natural per-experiment/per-pool scope. Pure,
    deterministic, no foundation/adapter import anywhere.

    `supersession_ledger` optional: if omitted, memory nodes carry only their at-creation
    `lifecycle_state`, labeled `AT_CREATION_ONLY`, never mistaken for current state.

    `include_versions` (new): if `True` (requires `supersession_ledger`), attach one
    `memory_version` node per `CanonicalMemoryVersion` (H.3) to its memory node via a
    `has_version` edge, in exact append order -- exposes full lifecycle-state history as
    graph structure, not just a current-state attribute. Retrieval/selection/etc. edges
    still attach at the MEMORY level, never to a specific version (per the design review's
    recommendation: attaching to "the version current at event time" would require new,
    not-yet-existing capability in `memory_versioning.py`, a frozen-adjacent file).

    `boundary_label` (new): if given, every node id in this graph is namespaced
    `f"{boundary_label}::{canonical_id}"` and one `experiment_boundary` node is added, with
    a `within_boundary` edge from every other node to it. Used internally by
    `build_multi_boundary_provenance_graph()`; a caller building a single-boundary graph
    (the common case, and every existing real usage this session) should leave this `None`
    -- unprefixed node ids, identical behavior to before this extension.
    """
    memory_records = {r.memory_id: r for r in memory_ledger.list_records()}

    nodes: List[GraphNode] = []
    superseded_by_groundings: Dict[str, Tuple[str, str]] = {}
    for mid, record in memory_records.items():
        attrs, grounding = _memory_node_attributes(record, memory_ledger, event_ledger, supersession_ledger)
        nodes.append(GraphNode(node_id=_prefixed(boundary_label, mid), node_type=NODE_TYPE_MEMORY, attributes=attrs))
        if grounding is not None:
            superseded_by_groundings[mid] = grounding

    edges: List[GraphEdge] = []

    for superseded_id, (superseding_id, established_event_id) in superseded_by_groundings.items():
        if superseding_id in memory_records:
            edges.append(GraphEdge(
                source_id=_prefixed(boundary_label, superseded_id),
                target_id=_prefixed(boundary_label, superseding_id),
                edge_type=EDGE_SUPERSEDED_BY, established_by_event_id=established_event_id,
            ))

    for mid, record in memory_records.items():
        for parent_id in record.parent_ids:
            if parent_id in memory_records:
                edges.append(GraphEdge(
                    source_id=_prefixed(boundary_label, mid), target_id=_prefixed(boundary_label, parent_id),
                    edge_type=EDGE_DERIVED_FROM, established_by_event_id=record.creation_event,
                ))

    if include_versions and supersession_ledger is not None:
        for mid in memory_records:
            try:
                history = reconstruct_version_history(event_ledger, memory_ledger, supersession_ledger, mid)
            except Exception:
                continue  # honestly skip a memory whose version history cannot reconstruct, never fabricate one
            memory_node_id = _prefixed(boundary_label, mid)
            for version in history:
                version_node_id = _prefixed(boundary_label, version.version_id)
                nodes.append(GraphNode(
                    node_id=version_node_id, node_type=NODE_TYPE_MEMORY_VERSION,
                    attributes={
                        "canonical_id": version.version_id, "memory_id": mid,
                        "version_number": version.version_number, "lifecycle_state": version.lifecycle_state,
                        "superseded_by": version.superseded_by, "recorded_at": version.recorded_at,
                    },
                ))
                edges.append(GraphEdge(
                    source_id=memory_node_id, target_id=version_node_id, edge_type=EDGE_HAS_VERSION,
                    established_by_event_id=version.established_by_event_id,
                ))

    task_ids_seen: Set[str] = set()
    event_type_to_edge_type = {
        EVENT_RETRIEVED: EDGE_RETRIEVED,
        EVENT_SELECTED: EDGE_SELECTED,
        EVENT_REJECTED: EDGE_REJECTED,
        EVENT_USED: EDGE_USED,
        EVENT_COUNTERFACTUALLY_INFLUENTIAL: EDGE_COUNTERFACTUALLY_INFLUENTIAL,
    }
    relationship_type_to_edge_type = {
        RELATIONSHIP_EQUIVALENT_TO: EDGE_EQUIVALENT_TO,
        RELATIONSHIP_CONFLICTS_WITH: EDGE_CONFLICTS_WITH,
    }

    for event in event_ledger.all_events():
        if event.event_type in event_type_to_edge_type:
            if not event.task_id:
                continue
            for mid in event.memory_ids:
                if mid not in memory_records:
                    continue
                # No "task::" infix -- matches the original, already-tested single-boundary
                # behavior exactly when boundary_label is None (plain task_id as node_id).
                # A task_id colliding with a memory_id's raw id would violate
                # ProvenanceGraph's node-id-uniqueness invariant regardless of any prefix
                # scheme; this was already true before this extension and is accepted as a
                # non-issue given this codebase's real id shapes (dataset-hash task ids vs.
                # UMR-derived memory ids never coincide in practice) -- not solved by
                # inventing a new namespace here.
                task_node_id = _prefixed(boundary_label, event.task_id)
                if task_node_id not in task_ids_seen:
                    nodes.append(GraphNode(node_id=task_node_id, node_type=NODE_TYPE_TASK, attributes={"canonical_id": event.task_id}))
                    task_ids_seen.add(task_node_id)
                edges.append(GraphEdge(
                    source_id=task_node_id, target_id=_prefixed(boundary_label, mid),
                    edge_type=event_type_to_edge_type[event.event_type],
                    established_by_event_id=event.event_id, task_id=event.task_id,
                ))
        elif event.event_type == EVENT_RELATIONSHIP_DETECTED:
            edge_type = relationship_type_to_edge_type.get(event.relationship_type)
            if edge_type is None:
                continue
            mid_a, mid_b = event.memory_ids
            if mid_a in memory_records and mid_b in memory_records:
                edges.append(GraphEdge(
                    source_id=_prefixed(boundary_label, mid_a), target_id=_prefixed(boundary_label, mid_b),
                    edge_type=edge_type, established_by_event_id=event.event_id,
                ))

    if boundary_label is not None:
        boundary_node_id = f"boundary::{boundary_label}"
        nodes.append(GraphNode(
            node_id=boundary_node_id, node_type=NODE_TYPE_EXPERIMENT_BOUNDARY,
            attributes={"boundary_label": boundary_label},
        ))
        for n in list(nodes):
            if n.node_id != boundary_node_id:
                edges.append(GraphEdge(source_id=n.node_id, target_id=boundary_node_id, edge_type=EDGE_WITHIN_BOUNDARY))

    return ProvenanceGraph(nodes=tuple(nodes), edges=tuple(edges))


def build_multi_boundary_provenance_graph(
    boundaries: Sequence[Tuple[str, CanonicalMemoryLedger, CanonicalEventLedger, Optional[SupersessionLedger]]],
    *,
    include_versions: bool = False,
) -> ProvenanceGraph:
    """Compose N single-boundary graphs (e.g. `("clean", ...)`, `("manipulated", ...)`)
    into ONE `ProvenanceGraph`, for side-by-side Phase 4 comparison. Each boundary_label
    must be unique. Guarantees, by construction (never asserted after the fact): no edge
    connects two nodes from different boundaries -- each sub-build only ever produces
    edges among its own (already-namespaced) node ids, and this function does nothing but
    concatenate the resulting node/edge tuples.
    """
    labels = [b[0] for b in boundaries]
    if len(set(labels)) != len(labels):
        raise ProvenanceGraphError(f"boundary labels must be unique, got {labels!r}.")

    all_nodes: List[GraphNode] = []
    all_edges: List[GraphEdge] = []
    for boundary_label, memory_ledger, event_ledger, supersession_ledger in boundaries:
        sub = build_provenance_graph(
            memory_ledger, event_ledger, supersession_ledger,
            include_versions=include_versions, boundary_label=boundary_label,
        )
        all_nodes.extend(sub.nodes)
        all_edges.extend(sub.edges)

    return ProvenanceGraph(nodes=tuple(all_nodes), edges=tuple(all_edges))


# ---------------------------------------------------------------------------
# Named, Phase-4-facing queries (design review §6). Thin wrappers over the primitives
# above, plus the one genuine integration this extension closes: attack_origin_lineage(),
# which reuses taint_propagation.tainted_memories() rather than reimplementing reachability
# a second time.
# ---------------------------------------------------------------------------


def forward_provenance(graph: ProvenanceGraph, memory_id: str) -> Set[str]:
    """Every memory reachable FROM `memory_id` via `derived_from` (its descendants)."""
    return graph.descendants_of(memory_id)


def backward_provenance(graph: ProvenanceGraph, memory_id: str) -> Set[str]:
    """Every memory `memory_id` was derived from, transitively (its ancestors)."""
    return graph.ancestors_of(memory_id)


def derivation_propagation(graph: ProvenanceGraph, memory_id: str) -> Set[str]:
    """Alias for `forward_provenance()` -- named separately per the design review's own
    query catalog, since "derived-memory propagation" and "forward provenance" are the
    same graph-level operation under two names Phase 4's own vocabulary uses."""
    return forward_provenance(graph, memory_id)


def task_exposure_and_use(graph: ProvenanceGraph, task_id: str) -> Dict[str, Tuple[str, ...]]:
    """Groups every edge for `task_id` by edge type, returning the target memory ids for
    each -- `{"retrieved": (...), "selected": (...), "rejected": (...), "used": (...),
    "counterfactually_influential": (...)}` (a key only appears if at least one such edge
    exists for this task -- never a fabricated empty entry for an edge type that has zero
    real occurrences)."""
    result: Dict[str, List[str]] = {}
    for e in graph.edges_for_task(task_id):
        result.setdefault(e.edge_type, []).append(e.target_id)
    return {k: tuple(v) for k, v in result.items()}


def attack_origin_lineage(
    graph: ProvenanceGraph,
    memory_ledger: CanonicalMemoryLedger,
    attack_memory_ids: Sequence[str],
    *,
    event_ledger: Optional[CanonicalEventLedger] = None,
    supersession_ledger: Optional[SupersessionLedger] = None,
):
    """Attack-origin lineage / taint propagation -- reuses
    `taint_propagation.tainted_memories()` (H.4-G) verbatim, never reimplemented. Returns
    its `TaintReport` directly; `graph` is accepted as a parameter for interface symmetry
    with the other named queries here and so a future caller can cross-reference the
    report's `tainted_memory_ids` against `graph.node()`/`graph.edges_to()` for the
    specific `derived_from` edges that compose each propagation path, but this function
    itself does not re-derive anything the report doesn't already state -- it is a thin,
    honest pass-through, not a second computation that could disagree with H.4-G's own.
    """
    from phase3.evaluation.foundations.taint_propagation import tainted_memories

    return tainted_memories(
        memory_ledger, attack_memory_ids, event_ledger=event_ledger, supersession_ledger=supersession_ledger,
    )


__all__ = [
    "NODE_TYPE_MEMORY", "NODE_TYPE_TASK", "NODE_TYPE_MEMORY_VERSION", "NODE_TYPE_EXPERIMENT_BOUNDARY", "NODE_TYPES",
    "EDGE_DERIVED_FROM", "EDGE_RETRIEVED", "EDGE_SELECTED", "EDGE_REJECTED", "EDGE_USED",
    "EDGE_COUNTERFACTUALLY_INFLUENTIAL", "EDGE_SUPERSEDED_BY", "EDGE_EQUIVALENT_TO", "EDGE_CONFLICTS_WITH",
    "EDGE_HAS_VERSION", "EDGE_WITHIN_BOUNDARY", "EDGE_TYPES",
    "LIFECYCLE_STATUS_CURRENT", "LIFECYCLE_STATUS_AT_CREATION_ONLY", "SCHEMA_PATH",
    "ProvenanceGraphError", "GraphNode", "GraphEdge", "ProvenanceGraph",
    "build_provenance_graph", "build_multi_boundary_provenance_graph",
    "forward_provenance", "backward_provenance", "derivation_propagation",
    "task_exposure_and_use", "attack_origin_lineage",
]
