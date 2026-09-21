"""Phase 11.1/11.2 -- real graph assembly for the GNN.

Builds one `networkx.Graph` per `ScenarioPool`, using only the real,
sanctioned structural edge vocabulary `phase6/defense/signals/contract.py`
already restricts every signal function to (`ALLOWED_STRUCTURAL_EDGE_TYPES`):
`RETRIEVED_WITH` between every pair of memories co-retrieved in the same
pool, and `DERIVED_FROM` between a derived memory and each of its real
`parent_ids`/`ancestors`. No new edge type is invented, and `USED_BY`/
`INFLUENCED` (the contract's own excluded types) are never added.
"""

from __future__ import annotations

from typing import Dict, Sequence, Tuple

import networkx as nx

from phase5.wiring.lineage import DERIVED_FROM, RETRIEVED_WITH
from phase6.defense.orchestration.pipeline import ScenarioPool


def build_pool_graph(pool: ScenarioPool) -> nx.Graph:
    graph = nx.Graph()
    for m in pool.memories:
        graph.add_node(m.scenario_id, is_poison_ground_truth=m.is_poison_ground_truth)

    ids = [m.scenario_id for m in pool.memories]
    for i, a in enumerate(ids):
        for b in ids[i + 1 :]:
            graph.add_edge(a, b, edge_type=RETRIEVED_WITH)

    for m in pool.memories:
        for parent_id in m.parent_ids:
            if not graph.has_node(parent_id):
                graph.add_node(parent_id, is_poison_ground_truth=False)
            graph.add_edge(m.scenario_id, parent_id, edge_type=DERIVED_FROM)
        for ancestor in m.ancestors:
            if not graph.has_node(ancestor.memory_id):
                graph.add_node(ancestor.memory_id, is_poison_ground_truth=False)
            graph.add_edge(m.scenario_id, ancestor.memory_id, edge_type=DERIVED_FROM)
    return graph


def build_pools_graph(pools: Sequence[ScenarioPool]) -> nx.Graph:
    """One combined graph across every pool in `pools` -- pools stay
    disjoint components (no cross-pool edges are invented) since a real
    RETRIEVED_WITH/DERIVED_FROM edge only ever exists within one real query's
    candidate set or one real lineage chain."""
    combined = nx.Graph()
    for pool in pools:
        combined = nx.union(combined, build_pool_graph(pool), rename=("", ""))
    return combined


def node_order_and_adjacency(graph: nx.Graph) -> Tuple[Tuple[str, ...], "list[list[int]]"]:
    """A stable node ordering plus a plain adjacency list (indices into that
    ordering) -- the shape `phase11/gnn/model.py`'s from-scratch
    message-passing layer consumes, so the model never needs to import
    networkx directly."""
    nodes = tuple(graph.nodes())
    index: Dict[str, int] = {n: i for i, n in enumerate(nodes)}
    adjacency = [[index[nbr] for nbr in graph.neighbors(n)] for n in nodes]
    return nodes, adjacency


def node_order_and_relation_adjacency(
    graph: nx.Graph,
) -> Tuple[Tuple[str, ...], "Dict[str, list[list[int]]]"]:
    """Phase 11.x -- the SAME stable node ordering as `node_order_and_adjacency()`,
    but split into one adjacency list PER real edge type (`RETRIEVED_WITH`,
    `DERIVED_FROM`) instead of collapsing both into one undifferentiated
    adjacency. Additive: `node_order_and_adjacency()` is unchanged and still
    used by the original `MinimalGNN`. Only the two edge types this project's
    own signal contract (`ALLOWED_STRUCTURAL_EDGE_TYPES`) already sanctions
    are ever produced -- no new relation is invented here."""
    nodes = tuple(graph.nodes())
    index: Dict[str, int] = {n: i for i, n in enumerate(nodes)}
    adjacency: Dict[str, "list[list[int]]"] = {
        RETRIEVED_WITH: [[] for _ in nodes],
        DERIVED_FROM: [[] for _ in nodes],
    }
    for u, v, data in graph.edges(data=True):
        edge_type = data["edge_type"]
        i, j = index[u], index[v]
        adjacency[edge_type][i].append(j)
        adjacency[edge_type][j].append(i)
    return nodes, adjacency
