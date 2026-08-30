"""`MockGraphitiAdapter` -- deterministic MOCK_CONFORMANCE test double for Graphiti's
architecture, per `capability_audit.GRAPHITI_AUDIT`.

Native shape preserved: `add_memory` creates an EPISODE, from which entity NODES and
temporally-annotated EDGES are derived (a simplified, deterministic stand-in for the
audit's documented "entities and relationships... incremental extraction" -- this mock
does not run any real LLM extraction; entities/edges are derived directly and
deterministically from the caller-supplied `content` shape, never invented). Critically,
per the mission's "never flatten foundation-native semantics" rule:
`inspect_memory()`/`export_state()` expose entities and edges as a genuinely NESTED graph
structure (`{"nodes": [...], "edges": [...]}`), never collapsed into a flat list the way
Mem0's or A-MEM's simpler record shapes are -- this is the one mock where preserving
graph/relationship richness is the entire point.

Edges carry `valid_at`/`invalid_at` fields (the audit's confirmed bi-temporal model);
`update_memory` on an existing episode's edge invalidates the OLD edge (`invalid_at` set)
rather than deleting it, mirroring the audit's "temporal edge invalidation" finding for
handling contradictions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Tuple

from phase3.evaluation.foundations.adapter import (
    FoundationField,
    FoundationIdentity,
    MemoryFoundationAdapter,
)
from phase3.evaluation.foundations.capability_audit import ALL_AUDITS, FOUNDATION_GRAPHITI
from phase3.evaluation.foundations.mocks.common import (
    DeterministicClock,
    available,
    check_call_payload,
    make_identity,
    not_supported,
)
from phase3.evaluation.foundations.trace import (
    OPERATION_ADD_MEMORY,
    OPERATION_DELETE_MEMORY,
    OPERATION_EXPORT_STATE,
    OPERATION_INITIALIZE,
    OPERATION_INSPECT_MEMORY,
    OPERATION_RESET,
    OPERATION_RETRIEVE,
    OPERATION_SHUTDOWN,
    OPERATION_UPDATE_MEMORY,
    ATTACK_SURFACE_MEMORY_CREATION,
    ATTACK_SURFACE_MEMORY_LINKING,
    ATTACK_SURFACE_RETRIEVAL,
    build_trace,
)

ADAPTER_VERSION = "mock-graphiti-0.1.0"


@dataclass
class _Edge:
    edge_id: str
    source: str
    target: str
    relationship: str
    valid_at: str
    invalid_at: Optional[str] = None


@dataclass
class _Episode:
    episode_id: str
    content: Mapping[str, Any]
    metadata: Mapping[str, Any]
    node_ids: Tuple[str, ...]


class MockGraphitiAdapter(MemoryFoundationAdapter):
    """Deterministic, in-memory, MOCK_CONFORMANCE-only test double. No Neo4j/FalkorDB/
    Neptune, no real LLM/embedding provider, no real Graphiti library dependency anywhere
    in this class."""

    def __init__(self) -> None:
        self._episodes: Dict[str, _Episode] = {}
        self._nodes: Dict[str, Mapping[str, Any]] = {}
        self._edges: Dict[str, _Edge] = {}
        self._clock = DeterministicClock()
        self._next_auto_id = 0
        self._next_edge_id = 0

    def foundation_identity(self) -> FoundationIdentity:
        return make_identity(FOUNDATION_GRAPHITI, "Graphiti", ADAPTER_VERSION)

    def capabilities(self) -> Mapping[str, Any]:
        return ALL_AUDITS[FOUNDATION_GRAPHITI]

    def initialize(self, configuration: Mapping[str, Any]) -> FoundationField:
        self._clock.tick()
        return available(OPERATION_INITIALIZE, True, "Mock initialized; no real graph-database connection created.")

    def reset(self) -> FoundationField:
        self._episodes.clear()
        self._nodes.clear()
        self._edges.clear()
        self._clock.tick()
        return available(OPERATION_RESET, True)

    def shutdown(self) -> FoundationField:
        self._clock.tick()
        return available(OPERATION_SHUTDOWN, True, "No real resources held; no-op.")

    def add_memory(
        self,
        memory_id: Optional[str],
        content: Mapping[str, Any],
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> FoundationField:
        check_call_payload(content, metadata)
        if memory_id is None:
            self._next_auto_id += 1
            memory_id = f"graphiti-episode-{self._next_auto_id}"

        entities = content.get("entities", [])
        relationships = content.get("relationships", [])
        node_ids: List[str] = []
        for entity in entities:
            node_id = str(entity["name"]) if isinstance(entity, Mapping) else str(entity)
            self._nodes[node_id] = {"name": node_id, "episode_id": memory_id}
            node_ids.append(node_id)

        timestamp = self._clock.tick()
        for rel in relationships:
            self._next_edge_id += 1
            edge_id = f"edge-{self._next_edge_id}"
            self._edges[edge_id] = _Edge(
                edge_id=edge_id,
                source=str(rel["source"]),
                target=str(rel["target"]),
                relationship=str(rel.get("type", "RELATED_TO")),
                valid_at=timestamp,
            )

        self._episodes[memory_id] = _Episode(
            episode_id=memory_id, content=dict(content), metadata=dict(metadata or {}), node_ids=tuple(node_ids)
        )
        return available(OPERATION_ADD_MEMORY, {"memory_id": memory_id, "node_ids": node_ids})

    def retrieve(self, query: Mapping[str, Any], top_k: Optional[int] = None) -> FoundationField:
        check_call_payload(query, None)
        entity_name = query.get("entity")
        results = []
        if entity_name is not None:
            for episode in self._episodes.values():
                if entity_name in episode.node_ids:
                    results.append({"memory_id": episode.episode_id, "content": episode.content})
        else:
            query_text = str(query.get("text", ""))
            for episode in self._episodes.values():
                text_blob = " ".join(str(v) for v in episode.content.values())
                if not query_text or query_text in text_blob:
                    results.append({"memory_id": episode.episode_id, "content": episode.content})
        if top_k is not None:
            results = results[:top_k]
        self._clock.tick()
        return available(OPERATION_RETRIEVE, results)

    def update_memory(
        self,
        memory_id: str,
        content: Mapping[str, Any],
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> FoundationField:
        check_call_payload(content, metadata)
        if memory_id not in self._episodes:
            self._clock.tick()
            return available(
                OPERATION_UPDATE_MEMORY,
                {"memory_id": memory_id, "updated": False},
                "No episode with this id existed; genuine no-op result.",
            )
        # Bi-temporal invalidation: invalidate all edges sourced from this episode's
        # nodes rather than deleting them, then add new edges from the updated content --
        # per the audit's confirmed "temporal edge invalidation" contradiction-handling.
        invalidated_at = self._clock.tick()
        episode = self._episodes[memory_id]
        for edge in self._edges.values():
            if edge.source in episode.node_ids and edge.invalid_at is None:
                edge.invalid_at = invalidated_at

        new_relationships = content.get("relationships", [])
        for rel in new_relationships:
            self._next_edge_id += 1
            edge_id = f"edge-{self._next_edge_id}"
            self._edges[edge_id] = _Edge(
                edge_id=edge_id,
                source=str(rel["source"]),
                target=str(rel["target"]),
                relationship=str(rel.get("type", "RELATED_TO")),
                valid_at=invalidated_at,
            )
        self._episodes[memory_id] = _Episode(
            episode_id=memory_id, content=dict(content), metadata=dict(metadata or {}), node_ids=episode.node_ids
        )
        return available(OPERATION_UPDATE_MEMORY, {"memory_id": memory_id, "updated": True})

    def delete_memory(self, memory_id: str) -> FoundationField:
        # Not documented (audit: 'deletion' row UNKNOWN) -- never fabricated.
        return not_supported(
            OPERATION_DELETE_MEMORY,
            "capability_audit.GRAPHITI_AUDIT's 'deletion' row is UNKNOWN; this mock does "
            "not fabricate a delete behavior the audit did not confirm (temporal "
            "invalidation via update_memory is the confirmed contradiction-handling path "
            "instead).",
        )

    def inspect_memory(self, memory_id: str) -> FoundationField:
        episode = self._episodes.get(memory_id)
        if episode is None:
            return not_supported(OPERATION_INSPECT_MEMORY, f"No episode with id {memory_id!r} exists.")
        nodes = [self._nodes[nid] for nid in episode.node_ids if nid in self._nodes]
        edges = [
            {
                "edge_id": e.edge_id,
                "source": e.source,
                "target": e.target,
                "relationship": e.relationship,
                "valid_at": e.valid_at,
                "invalid_at": e.invalid_at,
            }
            for e in self._edges.values()
            if e.source in episode.node_ids
        ]
        # Nested, NOT flattened -- see module docstring.
        return available(
            OPERATION_INSPECT_MEMORY,
            {
                "memory_id": memory_id,
                "content": episode.content,
                "graph": {"nodes": nodes, "edges": edges},
            },
        )

    def export_state(self) -> FoundationField:
        snapshot = {
            "episodes": [
                {"episode_id": e.episode_id, "content": e.content, "node_ids": list(e.node_ids)}
                for e in self._episodes.values()
            ],
            "nodes": dict(self._nodes),
            "edges": [
                {
                    "edge_id": e.edge_id,
                    "source": e.source,
                    "target": e.target,
                    "relationship": e.relationship,
                    "valid_at": e.valid_at,
                    "invalid_at": e.invalid_at,
                }
                for e in self._edges.values()
            ],
        }
        return available(OPERATION_EXPORT_STATE, snapshot)

    def normalize_trace(self, operation_result: FoundationField) -> Mapping[str, Any]:
        attack_stage = None
        if operation_result.operation == OPERATION_ADD_MEMORY:
            attack_stage = ATTACK_SURFACE_MEMORY_CREATION
        elif operation_result.operation == OPERATION_UPDATE_MEMORY:
            attack_stage = ATTACK_SURFACE_MEMORY_LINKING
        elif operation_result.operation == OPERATION_RETRIEVE:
            attack_stage = ATTACK_SURFACE_RETRIEVAL
        trace = build_trace(
            foundation_id=FOUNDATION_GRAPHITI,
            adapter_version=ADAPTER_VERSION,
            operation=operation_result.operation,
            timestamp=self._clock.tick(),
            **({"attack_surface_stage": attack_stage} if attack_stage else {}),
        )
        return trace.__dict__


__all__ = ["MockGraphitiAdapter", "ADAPTER_VERSION"]
