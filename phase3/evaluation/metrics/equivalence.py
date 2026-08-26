"""Evidence equivalence representation, validation, and connected-component grouping.

Phase 3.2-D scope note: this module implements ONLY the explicit, evaluator-declared
`equivalent_to` relation defined in `memory_schema.md` section 3.3 / section 4 and
`memory_schema.json`'s `equivalent_to` field, and `relationship_schema.md` section 2's
`equivalent_to` relationship row (symmetric, many-to-many). Equivalence is NEVER inferred
from content, string similarity, embeddings, or an LLM -- there is no semantic model
anywhere in this package. If two memory ids are not explicitly declared equivalent (or
transitively connected through explicit declarations), they are simply not equivalent as
far as this module is concerned, no matter how similar their `content` payloads look.

Pure functions: no filesystem/network/LLM/embeddings access, no randomness, no global
state. Inputs are plain mappings/sequences (`{memory_id: {"equivalent_to": [...]}, ...}`
or an explicit edge list `[(a, b), ...]`), never an `AgentVisibleContext`-shaped object.

Four distinct concepts this module is careful never to collapse (per memory_schema.md
section 4 and the 3.2-D task brief):
- Identity: equivalence never merges or rewrites a `memory_id`. Two equivalent memories
  remain two distinct identities forever -- `equivalence_classes()` returns *groups* of
  ids, never a merged id.
- Lineage/provenance: equivalence never implies a parent-derivation relationship. Two
  equivalent memories are not required to share, or even to have, any parent. See
  `provenance.py` for lineage, which is computed independently and is the only module
  in this package that reads parent identifiers.
- Task relevance: equivalence says nothing about whether either memory is gold evidence
  for any particular task.
- Evidence independence: equivalence is one INPUT to the independence diagnostic in
  `provenance.py`'s `independence_report`, not the diagnostic itself.

Decisions (explicit, per the 3.2-D task brief):

DECISION E1 -- symmetry is REQUIRED to be explicitly declared on both sides, not
auto-inferred as equivalence, for VALIDATION purposes. Rationale: `memory_schema.json`'s
`equivalent_to` field is a per-memory list (each memory declares its own outgoing
equivalence links), and both existing 3.2-B fixtures (`equivalent_memory/memory_a.json`,
`memory_b.json`) declare the relationship on BOTH sides (`A.equivalent_to = [B]` AND
`B.equivalent_to = [A]`) rather than relying on one-sided declaration + auto-symmetrization.
Treating a one-sided declaration as automatically symmetric would let a single memory
unilaterally assert "I am equivalent to X" without X's creator/curator ever having agreed
to that -- a form of untrusted-declaration risk this package should not paper over
silently. `validate_equivalence_edges()` therefore reports a one-sided declaration as
`ASYMMETRIC_DECLARATION` (a validation finding, not a silent auto-fix).

`equivalence_classes()` (connected-components) defaults to `require_symmetric=True`,
matching DECISION E1 -- only edges declared on both sides connect two memories into one
component. Passing `require_symmetric=False` computes components over the symmetric
CLOSURE of the edge set as given (i.e. a one-sided declaration is still treated as
connecting the pair for grouping purposes) -- this is documented explicitly as the looser
mode, for a caller who has already validated symmetry through other means and wants
transitive grouping regardless.

DECISION E2 -- self-equivalence (`A.equivalent_to` containing `A` itself) is explicitly
INVALID, not a silent no-op. A memory cannot be evidentially equivalent to itself -- that is
simply identity, a distinct concept (see the callout above). `validate_equivalence_edges()`
reports this as `SELF_EQUIVALENCE_DECLARED`, and self-edges never contribute connectivity
in `equivalence_classes()`.
"""

from __future__ import annotations

from typing import Dict, List, Mapping, Sequence, Set, Tuple

from .types import MetricResult, STATUS_OK, STATUS_UNDEFINED_EMPTY_SEQUENCE

# ---------------------------------------------------------------------------
# Validation finding vocabulary (equivalence-specific; not in types.py's shared
# STATUS_* vocabulary because these are structural findings, not MetricResult statuses)
# ---------------------------------------------------------------------------

FINDING_OK = "OK"
FINDING_UNKNOWN_MEMORY_REFERENCE = "UNKNOWN_MEMORY_REFERENCE"
FINDING_SELF_EQUIVALENCE_DECLARED = "SELF_EQUIVALENCE_DECLARED"
FINDING_ASYMMETRIC_DECLARATION = "ASYMMETRIC_DECLARATION"


def extract_equivalence_edges(
    memories: Mapping[str, Mapping[str, object]]
) -> List[Tuple[str, str]]:
    """Extract explicit `(a, b)` equivalence edges from a mapping of
    `memory_id -> memory_record` (each record shaped like `memory_schema.json`, i.e. it may
    carry an `equivalent_to: [memory_id, ...]` field).

    Returns one tuple per declared link, in `(declaring_id, target_id)` order, exactly as
    declared -- no deduplication, no symmetrization, no self-edge filtering. This is a
    literal extraction step; validation/classification happens in
    `validate_equivalence_edges()` and `equivalence_classes()`.
    """
    edges: List[Tuple[str, str]] = []
    for memory_id, record in memories.items():
        targets = record.get("equivalent_to") or []
        for target in targets:
            edges.append((memory_id, target))
    return edges


def validate_equivalence_edges(
    memories: Mapping[str, Mapping[str, object]],
    edges: Sequence[Tuple[str, str]] = None,
) -> MetricResult:
    """Validate a set of explicit equivalence edges against a known memory set.

    If `edges` is not supplied, edges are extracted from `memories` via
    `extract_equivalence_edges()`.

    Checks performed (each is reported, never silently repaired):
    - `UNKNOWN_MEMORY_REFERENCE`: an edge references a memory_id not present in `memories`.
    - `SELF_EQUIVALENCE_DECLARED`: an edge declares a memory equivalent to itself
      (DECISION E2).
    - `ASYMMETRIC_DECLARATION`: edge (a, b) is declared but (b, a) is not
      (DECISION E1) -- reported for both known and unknown targets, since asymmetry is a
      property of the declared edge set itself.

    `MetricResult.value` is the count of edges with zero findings (i.e. valid,
    symmetric, non-self, known-reference edges); never undefined -- an empty edge set
    yields `value=0.0`, `STATUS_OK` (there being no equivalence edges is a well-defined,
    valid state, not an error).
    """
    if edges is None:
        edges = extract_equivalence_edges(memories)

    known_ids = set(memories.keys())
    edge_set = set(edges)

    findings: Dict[Tuple[str, str], List[str]] = {}
    for a, b in edges:
        edge_findings: List[str] = []
        if a not in known_ids or b not in known_ids:
            edge_findings.append(FINDING_UNKNOWN_MEMORY_REFERENCE)
        if a == b:
            edge_findings.append(FINDING_SELF_EQUIVALENCE_DECLARED)
        if a != b and (b, a) not in edge_set:
            edge_findings.append(FINDING_ASYMMETRIC_DECLARATION)
        findings[(a, b)] = edge_findings or [FINDING_OK]

    valid_edges = [e for e, f in findings.items() if f == [FINDING_OK]]

    return MetricResult(
        metric_name="EQUIVALENCE_EDGE_VALIDATION",
        value=float(len(valid_edges)),
        status=STATUS_OK,
        detail={
            "total_edges": len(edges),
            "valid_edge_count": len(valid_edges),
            "findings": {f"{a}->{b}": f for (a, b), f in findings.items()},
        },
        note=(
            "value = count of edges with no findings (known refs, non-self, symmetric). "
            "See detail['findings'] for the per-edge breakdown."
        ),
    )


def equivalence_classes(
    memories: Mapping[str, Mapping[str, object]] = None,
    edges: Sequence[Tuple[str, str]] = None,
    require_symmetric: bool = True,
) -> MetricResult:
    """Deterministic connected-components computation over explicit equivalence edges.

    E.g. A≡B, B≡C (both declared symmetrically) -> one component `{A, B, C}`.

    Either `memories` (edges extracted via `extract_equivalence_edges`) or an explicit
    `edges` sequence must be supplied.

    `require_symmetric` (DECISION E1, default True): only edges declared on both sides
    (a,b) AND (b,a) are used to connect nodes. Self-edges are always ignored (an edge
    (a,a) contributes no new connectivity). Unknown-memory-reference edges (when `memories`
    is supplied) are excluded from traversal -- use `validate_equivalence_edges()` first to
    surface those as findings rather than have them silently affect grouping.

    Isolated memories (no valid equivalence edges) form their own singleton component --
    every memory_id known to this function (via `memories`, if supplied) appears in exactly
    one component.

    Output is deterministic: components are returned as a list of sorted-tuples, sorted by
    their first (smallest) member, so repeated calls on the same input always produce
    identical output (union-find with no reliance on dict/set iteration order for the
    final shape).

    Never undefined -- an empty input (no memories, no edges) yields `value=0.0`
    (zero components), `STATUS_OK`.
    """
    if edges is None:
        if memories is None:
            edges = []
        else:
            edges = extract_equivalence_edges(memories)

    edge_set = set(edges)
    all_ids: Set[str] = set()
    if memories is not None:
        # Known-memory-set mode: the node universe is exactly `memories.keys()`.
        # An edge referencing an id outside that set is an UNKNOWN_MEMORY_REFERENCE
        # finding (see `validate_equivalence_edges`), not a license to add a phantom
        # node to the component graph.
        all_ids |= set(memories.keys())
    else:
        # Edge-list-only mode (no known memory set supplied): the node universe is
        # whatever ids appear in the edges themselves.
        for a, b in edges:
            all_ids.add(a)
            all_ids.add(b)

    usable_edges: List[Tuple[str, str]] = []
    for a, b in edges:
        if a == b:
            continue
        if memories is not None and (a not in memories or b not in memories):
            continue
        if require_symmetric and (b, a) not in edge_set:
            continue
        usable_edges.append((a, b))

    # Union-find.
    parent: Dict[str, str] = {node: node for node in all_ids}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: str, y: str) -> None:
        rx, ry = find(x), find(y)
        if rx != ry:
            # Deterministic merge direction: keep the lexicographically smaller root.
            if rx < ry:
                parent[ry] = rx
            else:
                parent[rx] = ry

    for a, b in usable_edges:
        union(a, b)

    groups: Dict[str, List[str]] = {}
    for node in all_ids:
        root = find(node)
        groups.setdefault(root, []).append(node)

    components = sorted(tuple(sorted(members)) for members in groups.values())

    return MetricResult(
        metric_name="EQUIVALENCE_CLASSES",
        value=float(len(components)),
        status=STATUS_OK,
        detail={
            "components": [list(c) for c in components],
            "component_count": len(components),
            "largest_component_size": max((len(c) for c in components), default=0),
            "require_symmetric": require_symmetric,
        },
        note=(
            "value = distinct equivalence component count (includes singleton components "
            "for memories with no valid equivalence edges)."
        ),
    )


def equivalence_group_size(
    memory_id: str,
    memories: Mapping[str, Mapping[str, object]] = None,
    edges: Sequence[Tuple[str, str]] = None,
    require_symmetric: bool = True,
) -> MetricResult:
    """Size of the equivalence component containing `memory_id` (including itself).

    A memory with no equivalence relationships has a group size of 1 (itself alone) -- this
    is well-defined, not undefined, since "the set of things this memory is equivalent to,
    including itself" is always at least `{memory_id}`.

    If `memory_id` is not present in `memories`/`edges` at all, this is reported as
    undefined (`STATUS_UNDEFINED_EMPTY_SEQUENCE` is reused here to mean "no such node in the
    graph", i.e. there is nothing to report a group size for).
    """
    components_result = equivalence_classes(
        memories=memories, edges=edges, require_symmetric=require_symmetric
    )
    for component in components_result.detail["components"]:
        if memory_id in component:
            return MetricResult(
                metric_name="EQUIVALENCE_GROUP_SIZE",
                value=float(len(component)),
                status=STATUS_OK,
                detail={"memory_id": memory_id, "component": component},
            )
    return MetricResult(
        metric_name="EQUIVALENCE_GROUP_SIZE",
        value=None,
        status=STATUS_UNDEFINED_EMPTY_SEQUENCE,
        detail={"memory_id": memory_id},
        note=f"{memory_id!r} not found in the supplied memories/edges; no group to report.",
    )
