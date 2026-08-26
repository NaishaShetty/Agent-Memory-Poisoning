"""Provenance validation, lineage (ancestor/descendant) traversal, cycle/orphan detection,
lineage depth, root-origin analysis, and the lineage-based evidence independence diagnostic.

Phase 3.2-D scope note: everything here operates on EXPLICIT `parent_ids` edges (per
`memory_schema.json`'s `parent_ids` field and `relationship_schema.md` section 2.1,
"Explicit edges only -- no giant families"). Ancestor/descendant sets are always computed
by transitive traversal at query time -- this module never precomputes or caches a merged
"lineage family" object, per the explicit rejection of that historical abstraction in
`relationship_schema.md` section 2.1 and `memory_schema.md` section 5. A derived memory with
multiple parents (`A -> C`, `B -> C`) always keeps both parent identities visible in every
function's output; nothing here collapses them into a single origin id.

Pure functions: no filesystem/network/LLM/embeddings access, no randomness, no global
state. Inputs are plain mappings (`memory_id -> memory_record`, each record shaped like
`memory_schema.json`, i.e. with at least `memory_id`, `memory_type`, `parent_ids`), never an
`AgentVisibleContext`-shaped object.

DECISIONS (explicit, per the 3.2-D task brief -- each is also called out in
`phase3/evaluation/metrics/README.md`'s CANONICAL/PROVISIONAL/DIAGNOSTIC-ONLY table):

DECISION P1 (PROVISIONAL) -- lineage depth uses MIN-depth-of-parents + 1 for multi-parent
nodes, i.e. `depth(node) = 1 + min(depth(p) for p in parents)` (roots have depth 0). Neither
`memory_schema.md`, `relationship_schema.md`, nor `TRACEABILITY_CONTRACT.md` specifies
min-vs-max for multi-parent derivation, and `phase3/evaluation/AUDIT.md` section 8/13 flags
derivation depth as one of the not-yet-frozen algorithmic choices (`_lineage_depth()` in the
historical `clean_agent_v1/src/clean_baseline.py` is tied to the old, rejected
lineage-family model and is not reused here). MIN-depth is chosen because it answers "what
is the SHORTEST legitimate derivation chain that could have produced this memory" -- which
is the more conservative (harder-to-inflate) reading for a diagnostic whose purpose is
detecting anomalously deep derivation chains (a suspiciously short apparent depth is exactly
what an attacker minimizing traceability distance would want, so under-counting depth is the
safer failure direction for a diagnostic, not the safer failure direction for, say, a
lifecycle guarantee). This is flagged PROVISIONAL, not CANONICAL -- a future contract
revision may specify MAX-depth instead, in which case this function must be revisited.

DECISION P2 -- cycle detection is depth-first with explicit `visited`/`in_progress` sets
(iterative, not recursive, to avoid Python recursion-depth blowups on pathological inputs).
On detecting a cycle, traversal STOPS for that node and reports the cycle; it does not
attempt to "route around" the cycle to keep computing a partial ancestor/descendant set for
that node, because any such partial set would be arbitrary (which edge do you drop to break
the cycle?) and could silently understate an integrity problem.

DECISION P3 -- `LINEAGE_INDEPENDENT` (the independence diagnostic's default/no-relationship
classification) is explicitly scoped as "no explicit lineage or equivalence relationship
found between the two memories" -- it is NEVER reported or documented as "these two pieces
of evidence are epistemically/causally independent." Two memories with no explicit lineage
or equivalence edge could still, in reality, restate the same underlying fact via a
completely undeclared channel (e.g. both hand-authored by the same curator from the same
external source, with no `parent_ids`/`equivalent_to` edge ever recorded) -- this module has
no way to see that, by design (no semantic model), so it must not claim to.
"""

from __future__ import annotations

from typing import Dict, List, Mapping, Optional, Sequence, Set, Tuple

from .types import MetricResult, STATUS_OK, STATUS_UNDEFINED_EMPTY_SEQUENCE
from .equivalence import equivalence_classes

# ---------------------------------------------------------------------------
# Provenance completeness vocabulary
# ---------------------------------------------------------------------------

PROVENANCE_COMPLETE = "COMPLETE"
PROVENANCE_INCOMPLETE = "INCOMPLETE"
PROVENANCE_INVALID = "INVALID"

VALID_MEMORY_TYPES = ("foundation", "derived")
VALID_SOURCE_TYPES = ("phase2_umr", "derivation_event", "future_observation")

# Orphan / integrity finding vocabulary
FINDING_ORPHAN_PARENT_REFERENCE = "ORPHAN_PARENT_REFERENCE"
FINDING_MISSING_MEMORY_TYPE = "MISSING_MEMORY_TYPE"
FINDING_INVALID_MEMORY_TYPE = "INVALID_MEMORY_TYPE"
FINDING_MISSING_SOURCE = "MISSING_SOURCE"
FINDING_INVALID_SOURCE_TYPE = "INVALID_SOURCE_TYPE"
FINDING_FOUNDATION_WITH_PARENTS = "FOUNDATION_WITH_PARENTS"
FINDING_DERIVED_WITHOUT_PARENTS = "DERIVED_WITHOUT_PARENTS"
FINDING_MISSING_MEMORY_ID = "MISSING_MEMORY_ID"

# Independence classification vocabulary (DECISION P3)
CLASS_LINEAGE_INDEPENDENT = "LINEAGE_INDEPENDENT"
CLASS_SHARED_LINEAGE_ORIGIN = "SHARED_LINEAGE_ORIGIN"
CLASS_DIRECT_ANCESTOR_DESCENDANT = "DIRECT_ANCESTOR_DESCENDANT"
CLASS_EQUIVALENT_INFORMATION = "EQUIVALENT_INFORMATION"
CLASS_MULTI_ORIGIN_DERIVED = "MULTI_ORIGIN_DERIVED"
CLASS_UNKNOWN = "UNKNOWN"


# ---------------------------------------------------------------------------
# Parent/lineage edge validation
# ---------------------------------------------------------------------------


def validate_parent_edges(memories: Mapping[str, Mapping[str, object]]) -> MetricResult:
    """Per-edge validation of every `(parent_id, child_id)` pair implied by each memory's
    `parent_ids` list. Each edge is validated independently -- multiple parents of the same
    child are NEVER collapsed into a family/group abstraction; `A->C` and `B->C` are
    reported as two separate edges (per `relationship_schema.md` section 2.1).

    An edge is valid iff both endpoints exist in `memories` (direction is always
    parent -> child by construction of `parent_ids`, so there is no direction ambiguity to
    check). An edge referencing a parent_id absent from `memories` is a
    `FINDING_ORPHAN_PARENT_REFERENCE` -- reported, not repaired (no parent is invented, no
    edge is silently dropped from the report).

    Never undefined -- an empty memory set yields `value=0.0` (zero edges), `STATUS_OK`.
    """
    known_ids = set(memories.keys())
    edges: List[Tuple[str, str]] = []
    orphan_edges: List[Tuple[str, str]] = []

    for child_id, record in memories.items():
        for parent_id in record.get("parent_ids") or []:
            edges.append((parent_id, child_id))
            if parent_id not in known_ids:
                orphan_edges.append((parent_id, child_id))

    valid_edges = [e for e in edges if e not in orphan_edges]

    return MetricResult(
        metric_name="PARENT_EDGE_VALIDATION",
        value=float(len(valid_edges)),
        status=STATUS_OK,
        detail={
            "total_edges": len(edges),
            "valid_edge_count": len(valid_edges),
            "orphan_edges": [f"{p}->{c}" for p, c in orphan_edges],
            "orphan_parent_reference_count": len(orphan_edges),
        },
        note="Each parent->child edge validated independently; multi-parent children retain all edges separately.",
    )


def orphan_parent_count(memories: Mapping[str, Mapping[str, object]]) -> MetricResult:
    """Count of distinct memories that reference at least one parent_id absent from
    `memories` (an ORPHAN_PARENT_REFERENCE). Convenience wrapper over
    `validate_parent_edges()` grouped by child rather than by edge.
    """
    known_ids = set(memories.keys())
    orphaned_children: Set[str] = set()
    for child_id, record in memories.items():
        for parent_id in record.get("parent_ids") or []:
            if parent_id not in known_ids:
                orphaned_children.add(child_id)

    return MetricResult(
        metric_name="ORPHAN_PARENT_COUNT",
        value=float(len(orphaned_children)),
        status=STATUS_OK,
        detail={"orphaned_children": sorted(orphaned_children)},
    )


# ---------------------------------------------------------------------------
# Cycle detection (DECISION P2)
# ---------------------------------------------------------------------------


def detect_cycles(memories: Mapping[str, Mapping[str, object]]) -> MetricResult:
    """Deterministic cycle detection over the explicit parent_ids graph (edges traversed
    child -> parent, i.e. following ancestry upward, which is equivalent to detecting a
    cycle in the parent->child graph).

    Iterative DFS with `visited` (fully explored, no cycle found through this node) and
    `in_progress` (currently on the active traversal stack) sets -- never recurses, so it is
    safe against stack overflow on pathological/adversarial inputs, and never infinite-loops
    on a cyclic graph: revisiting an `in_progress` node immediately reports a cycle and stops
    descending further from it.

    Only parent_ids referencing a known memory are traversed (an orphan reference is not a
    cycle and is reported separately by `validate_parent_edges`/`orphan_parent_count`).

    `MetricResult.value` = number of distinct cycles found (a node participating in more
    than one detected cycle path is still only counted once per distinct cycle discovered);
    `detail["cycles"]` lists each cycle as an ordered list of memory_ids.  Never undefined --
    an empty or acyclic memory set yields `value=0.0`, `STATUS_OK`.
    """
    known_ids = set(memories.keys())
    visited: Set[str] = set()
    cycles: List[List[str]] = []

    for start in sorted(known_ids):
        if start in visited:
            continue
        stack: List[Tuple[str, int]] = [(start, 0)]
        path: List[str] = []
        in_progress: Set[str] = set()

        while stack:
            node, child_index = stack[-1]
            parents = [
                p
                for p in (memories.get(node, {}).get("parent_ids") or [])
                if p in known_ids
            ]

            if child_index == 0:
                path.append(node)
                in_progress.add(node)

            if child_index < len(parents):
                stack[-1] = (node, child_index + 1)
                next_parent = parents[child_index]
                if next_parent in in_progress:
                    cycle_start = path.index(next_parent)
                    cycle = path[cycle_start:] + [next_parent]
                    if cycle not in cycles:
                        cycles.append(cycle)
                    # Do not descend further into the cycle from here.
                    continue
                if next_parent not in visited:
                    stack.append((next_parent, 0))
            else:
                stack.pop()
                path.pop()
                in_progress.discard(node)
                visited.add(node)

    return MetricResult(
        metric_name="CYCLE_DETECTION",
        value=float(len(cycles)),
        status=STATUS_OK,
        detail={"cycles": cycles, "cycle_count": len(cycles)},
        note="Iterative DFS; stops descending into a detected cycle rather than repairing/routing around it.",
    )


def _has_cycle_through(memories: Mapping[str, Mapping[str, object]], node: str) -> bool:
    """Helper: is `node` a member of any detected cycle?"""
    result = detect_cycles(memories)
    for cycle in result.detail["cycles"]:
        if node in cycle:
            return True
    return False


# ---------------------------------------------------------------------------
# Ancestry / descendant traversal
# ---------------------------------------------------------------------------


def ancestors(
    memories: Mapping[str, Mapping[str, object]],
    memory_id: str,
    include_self: bool = False,
) -> MetricResult:
    """All memories reachable by transitively following `parent_ids` edges upward from
    `memory_id`, per `memory_schema.md` section 5 ("Ancestor/descendant... computed by
    walking explicit parent_ids edges -- not a precomputed lineage-family set").

    Excludes `memory_id` itself unless `include_self=True`.

    Safe on cyclic input: if a cycle is reachable from `memory_id`, traversal detects it
    (via a `visited`/`in_progress` set, mirroring `detect_cycles`) and STOPS extending
    through the repeated node rather than looping forever; `detail["cycle_detected"]`
    reports this explicitly rather than silently returning a possibly-incomplete set with no
    indication anything was wrong.

    Never undefined -- an unknown `memory_id` yields an empty ancestor set with
    `status=STATUS_UNDEFINED_EMPTY_SEQUENCE` (there is nothing to compute ancestors of).
    """
    if memory_id not in memories:
        return MetricResult(
            metric_name="ANCESTORS",
            value=None,
            status=STATUS_UNDEFINED_EMPTY_SEQUENCE,
            detail={"memory_id": memory_id},
            note=f"{memory_id!r} not found in the supplied memory set.",
        )

    known_ids = set(memories.keys())
    result_set: Set[str] = set()
    in_progress: Set[str] = set()
    visited: Set[str] = set()
    cycle_detected = False

    def visit(node: str) -> None:
        nonlocal cycle_detected
        if node in in_progress:
            cycle_detected = True
            return
        if node in visited:
            return
        in_progress.add(node)
        for parent_id in memories.get(node, {}).get("parent_ids") or []:
            if parent_id in known_ids:
                result_set.add(parent_id)
                visit(parent_id)
        in_progress.discard(node)
        visited.add(node)

    visit(memory_id)

    if include_self:
        result_set.add(memory_id)

    return MetricResult(
        metric_name="ANCESTORS",
        value=float(len(result_set)),
        status=STATUS_OK,
        detail={
            "memory_id": memory_id,
            "ancestors": sorted(result_set),
            "include_self": include_self,
            "cycle_detected": cycle_detected,
        },
        note=(
            "value = ancestor count. If cycle_detected is True, traversal stopped extending "
            "through the repeated node; the returned set may be incomplete relative to what "
            "an acyclic graph would have produced -- run detect_cycles() for the full cycle report."
        ),
    )


def descendants(
    memories: Mapping[str, Mapping[str, object]],
    memory_id: str,
    include_self: bool = False,
) -> MetricResult:
    """All memories reachable by transitively following `parent_ids` edges DOWNWARD (i.e.
    memories that list `memory_id`, or any descendant of it, as a parent) from `memory_id`.

    Mirrors `ancestors()` exactly but in the opposite direction. Does not collapse into a
    lineage-family id -- returns the explicit descendant set. Safe on cyclic input for the
    same reasons as `ancestors()`.
    """
    if memory_id not in memories:
        return MetricResult(
            metric_name="DESCENDANTS",
            value=None,
            status=STATUS_UNDEFINED_EMPTY_SEQUENCE,
            detail={"memory_id": memory_id},
            note=f"{memory_id!r} not found in the supplied memory set.",
        )

    # Build a child index: parent_id -> [child_ids] (only known children).
    children_of: Dict[str, List[str]] = {mid: [] for mid in memories}
    for child_id, record in memories.items():
        for parent_id in record.get("parent_ids") or []:
            if parent_id in children_of:
                children_of[parent_id].append(child_id)

    result_set: Set[str] = set()
    in_progress: Set[str] = set()
    visited: Set[str] = set()
    cycle_detected = False

    def visit(node: str) -> None:
        nonlocal cycle_detected
        if node in in_progress:
            cycle_detected = True
            return
        if node in visited:
            return
        in_progress.add(node)
        for child_id in children_of.get(node, []):
            result_set.add(child_id)
            visit(child_id)
        in_progress.discard(node)
        visited.add(node)

    visit(memory_id)

    if include_self:
        result_set.add(memory_id)

    return MetricResult(
        metric_name="DESCENDANTS",
        value=float(len(result_set)),
        status=STATUS_OK,
        detail={
            "memory_id": memory_id,
            "descendants": sorted(result_set),
            "include_self": include_self,
            "cycle_detected": cycle_detected,
        },
        note=(
            "value = descendant count. If cycle_detected is True, traversal stopped extending "
            "through the repeated node -- see detect_cycles() for the full cycle report."
        ),
    )


# ---------------------------------------------------------------------------
# Root / origin analysis
# ---------------------------------------------------------------------------


def root_origins(memories: Mapping[str, Mapping[str, object]], memory_id: str) -> MetricResult:
    """All lineage roots (memories with no parents, i.e. `parent_ids == []`, typically
    `memory_type == "foundation"`) reachable via ancestor traversal from `memory_id`.

    Supports multiple roots for multi-parent derivation without arbitrarily picking one:
    `A -> C`, `B -> C` (A, B both foundation) -> `root_origins(C) = {A, B}`.

    If `memory_id` itself has no parents, it is its own (sole) root origin.
    """
    if memory_id not in memories:
        return MetricResult(
            metric_name="ROOT_ORIGINS",
            value=None,
            status=STATUS_UNDEFINED_EMPTY_SEQUENCE,
            detail={"memory_id": memory_id},
            note=f"{memory_id!r} not found in the supplied memory set.",
        )

    own_parents = memories[memory_id].get("parent_ids") or []
    if not own_parents:
        return MetricResult(
            metric_name="ROOT_ORIGINS",
            value=1.0,
            status=STATUS_OK,
            detail={"memory_id": memory_id, "roots": [memory_id]},
            note=f"{memory_id!r} has no parents; it is its own root origin.",
        )

    anc_result = ancestors(memories, memory_id, include_self=False)
    ancestor_ids = anc_result.detail.get("ancestors", [])

    roots = [
        aid
        for aid in ancestor_ids
        if not (memories.get(aid, {}).get("parent_ids") or [])
    ]

    return MetricResult(
        metric_name="ROOT_ORIGINS",
        value=float(len(roots)),
        status=STATUS_OK,
        detail={
            "memory_id": memory_id,
            "roots": sorted(roots),
            "cycle_detected": anc_result.detail.get("cycle_detected", False),
        },
        note="Multiple roots are retained explicitly (multi-parent derivation) -- never collapsed to one.",
    )


def shared_origin_report(
    memories: Mapping[str, Mapping[str, object]], selected_ids: Sequence[str]
) -> MetricResult:
    """For a set of selected memory ids, report which root origins are shared across more
    than one selected memory -- the structural basis for detecting non-independent
    corroboration due to common lineage ancestry (as opposed to equivalence).

    `detail["roots_by_memory"]` maps each selected id to its root-origin set;
    `detail["shared_roots"]` maps each root id that is an ancestor of 2+ distinct selected
    memories to the list of selected memories sharing it. `value` = count of distinct shared
    roots (0 if none, or if fewer than 2 selected ids are supplied).
    """
    if len(selected_ids) == 0:
        return MetricResult(
            metric_name="SHARED_ORIGIN_REPORT",
            value=None,
            status=STATUS_UNDEFINED_EMPTY_SEQUENCE,
            detail={},
            note="selected_ids is empty; shared-origin report is undefined.",
        )

    roots_by_memory: Dict[str, List[str]] = {}
    for mid in selected_ids:
        if mid in memories:
            roots_by_memory[mid] = root_origins(memories, mid).detail.get("roots", [])
        else:
            roots_by_memory[mid] = []

    root_to_members: Dict[str, List[str]] = {}
    for mid, roots in roots_by_memory.items():
        for root in roots:
            root_to_members.setdefault(root, []).append(mid)

    shared_roots = {
        root: sorted(set(members))
        for root, members in root_to_members.items()
        if len(set(members)) >= 2
    }

    return MetricResult(
        metric_name="SHARED_ORIGIN_REPORT",
        value=float(len(shared_roots)),
        status=STATUS_OK,
        detail={
            "roots_by_memory": roots_by_memory,
            "shared_roots": shared_roots,
            "distinct_shared_root_count": len(shared_roots),
        },
    )


# ---------------------------------------------------------------------------
# Lineage depth (DECISION P1 -- PROVISIONAL: min-depth for multi-parent nodes)
# ---------------------------------------------------------------------------


def lineage_depth(memories: Mapping[str, Mapping[str, object]], memory_id: str) -> MetricResult:
    """depth(root) = 0; depth(child) = 1 + MIN(depth(parent) for parent in parents).

    PROVISIONAL choice (DECISION P1, see module docstring): min-depth, not max-depth, is
    used for multi-parent nodes with parents at different depths.

    Safe against cycles: if `memory_id` participates in a cycle (per `detect_cycles`),
    depth is undefined for it -- returns `value=None`,
    `status=STATUS_UNDEFINED_EMPTY_SEQUENCE`, rather than looping or returning a misleading
    number.
    """
    if memory_id not in memories:
        return MetricResult(
            metric_name="LINEAGE_DEPTH",
            value=None,
            status=STATUS_UNDEFINED_EMPTY_SEQUENCE,
            detail={"memory_id": memory_id},
            note=f"{memory_id!r} not found in the supplied memory set.",
        )

    if _has_cycle_through(memories, memory_id):
        return MetricResult(
            metric_name="LINEAGE_DEPTH",
            value=None,
            status=STATUS_UNDEFINED_EMPTY_SEQUENCE,
            detail={"memory_id": memory_id, "cycle_detected": True},
            note=f"{memory_id!r} participates in a cycle; lineage depth is undefined.",
        )

    known_ids = set(memories.keys())
    memo: Dict[str, int] = {}

    def depth_of(node: str) -> int:
        if node in memo:
            return memo[node]
        parents = [p for p in (memories.get(node, {}).get("parent_ids") or []) if p in known_ids]
        if not parents:
            memo[node] = 0
        else:
            memo[node] = 1 + min(depth_of(p) for p in parents)
        return memo[node]

    d = depth_of(memory_id)
    return MetricResult(
        metric_name="LINEAGE_DEPTH",
        value=float(d),
        status=STATUS_OK,
        detail={"memory_id": memory_id, "depth": d, "convention": "MIN_DEPTH_MULTI_PARENT (PROVISIONAL)"},
        note="PROVISIONAL: min-depth-of-parents+1 convention for multi-parent nodes. See module docstring DECISION P1.",
    )


# ---------------------------------------------------------------------------
# Provenance validation (COMPLETE / INCOMPLETE / INVALID)
# ---------------------------------------------------------------------------


def validate_provenance(
    memories: Mapping[str, Mapping[str, object]], memory_id: str
) -> MetricResult:
    """Validate one memory's provenance against `memory_schema.json`'s structural rules.

    Checks (never silently coerced missing -> valid):
    - `memory_id` present and matches the key.
    - `memory_type` present and one of `VALID_MEMORY_TYPES`.
    - `source` present with a valid `source_type`.
    - `parent_ids` structurally consistent with `memory_type`:
        * foundation memories MUST have empty `parent_ids` (a foundation memory falsely
          claiming parents is `FOUNDATION_WITH_PARENTS`).
        * derived memories MUST have non-empty `parent_ids`
          (`DERIVED_WITHOUT_PARENTS` otherwise).
    - every parent_id must reference a memory present in `memories`
      (`ORPHAN_PARENT_REFERENCE`, reported, not repaired).

    Classification (three-way, never silently coerced):
    - `PROVENANCE_INVALID`: at least one hard-structural violation was found (invalid/
      missing memory_type, missing/invalid source, foundation-with-parents, orphan parent
      reference, missing memory_id).
    - `PROVENANCE_INCOMPLETE`: no hard violation, but a required-but-optional-in-practice
      field is absent in a way that leaves provenance impossible to fully verify (currently:
      `derived` memory missing `source.reference_id`, which is required to trace back to the
      creating derivation event per `memory_schema.md` section 7).
    - `PROVENANCE_COMPLETE`: no findings at all.
    """
    if memory_id not in memories:
        return MetricResult(
            metric_name="PROVENANCE_VALIDATION",
            value=None,
            status=STATUS_UNDEFINED_EMPTY_SEQUENCE,
            detail={"memory_id": memory_id, "classification": None},
            note=f"{memory_id!r} not found in the supplied memory set.",
        )

    record = memories[memory_id]
    findings: List[str] = []
    incomplete_findings: List[str] = []

    if not record.get("memory_id"):
        findings.append(FINDING_MISSING_MEMORY_ID)

    memory_type = record.get("memory_type")
    if not memory_type:
        findings.append(FINDING_MISSING_MEMORY_TYPE)
    elif memory_type not in VALID_MEMORY_TYPES:
        findings.append(FINDING_INVALID_MEMORY_TYPE)

    source = record.get("source")
    if not source:
        findings.append(FINDING_MISSING_SOURCE)
    else:
        source_type = source.get("source_type")
        if source_type not in VALID_SOURCE_TYPES:
            findings.append(FINDING_INVALID_SOURCE_TYPE)
        elif not source.get("reference_id"):
            incomplete_findings.append("MISSING_SOURCE_REFERENCE_ID")

    parent_ids = record.get("parent_ids") or []
    known_ids = set(memories.keys())
    orphan_parents = [p for p in parent_ids if p not in known_ids]
    if orphan_parents:
        findings.append(FINDING_ORPHAN_PARENT_REFERENCE)

    if memory_type == "foundation" and parent_ids:
        findings.append(FINDING_FOUNDATION_WITH_PARENTS)
    if memory_type == "derived" and not parent_ids:
        findings.append(FINDING_DERIVED_WITHOUT_PARENTS)

    if findings:
        classification = PROVENANCE_INVALID
    elif incomplete_findings:
        classification = PROVENANCE_INCOMPLETE
    else:
        classification = PROVENANCE_COMPLETE

    return MetricResult(
        metric_name="PROVENANCE_VALIDATION",
        value={"COMPLETE": 1.0, "INCOMPLETE": 0.5, "INVALID": 0.0}[classification],
        status=STATUS_OK,
        detail={
            "memory_id": memory_id,
            "classification": classification,
            "findings": findings,
            "incomplete_findings": incomplete_findings,
            "orphan_parent_ids": orphan_parents,
        },
        note=(
            "value is a convenience numeric encoding (COMPLETE=1.0/INCOMPLETE=0.5/INVALID=0.0) "
            "for aggregation only -- detail['classification'] is the load-bearing three-way result. "
            "Never silently coerce missing information to COMPLETE."
        ),
    )


def provenance_completeness_report(memories: Mapping[str, Mapping[str, object]]) -> MetricResult:
    """Aggregate provenance-completeness diagnostic across an entire memory set:
    classifies EVERY memory via `validate_provenance()` and reports the
    COMPLETE/INCOMPLETE/INVALID tally plus the completeness rate.

    `value` = `count(COMPLETE) / total` (the completeness rate). `detail["counts"]` tallies
    all three classifications (never collapsed); `detail["per_memory"]` gives the full
    per-memory classification + findings, so no memory's classification is silently
    dropped from the aggregate view.

    Empty `memories` -> undefined (`STATUS_UNDEFINED_EMPTY_SEQUENCE`) -- there is nothing to
    be complete or incomplete about.
    """
    if len(memories) == 0:
        return MetricResult(
            metric_name="PROVENANCE_COMPLETENESS",
            value=None,
            status=STATUS_UNDEFINED_EMPTY_SEQUENCE,
            detail={"per_memory": {}, "counts": {}},
            note="memories is empty; provenance completeness is undefined.",
        )

    per_memory: Dict[str, Dict[str, object]] = {}
    counts = {PROVENANCE_COMPLETE: 0, PROVENANCE_INCOMPLETE: 0, PROVENANCE_INVALID: 0}
    for memory_id in memories:
        result = validate_provenance(memories, memory_id)
        classification = result.detail["classification"]
        per_memory[memory_id] = result.detail
        counts[classification] += 1

    total = len(memories)
    return MetricResult(
        metric_name="PROVENANCE_COMPLETENESS",
        value=counts[PROVENANCE_COMPLETE] / total,
        status=STATUS_OK,
        detail={"per_memory": per_memory, "counts": counts, "total": total},
        note=(
            "value is the COMPLETE-fraction across the whole memory set. See "
            "detail['per_memory'] for the full per-memory classification, never silently "
            "coerced to COMPLETE."
        ),
    )


# ---------------------------------------------------------------------------
# Evidence independence diagnostic (lineage/equivalence-based ONLY -- see DECISION P3)
# ---------------------------------------------------------------------------


def independence_report(
    memories: Mapping[str, Mapping[str, object]], selected_ids: Sequence[str]
) -> MetricResult:
    """Structured (never single-boolean) independence diagnostic for a set of selected
    memory ids, based ONLY on explicit lineage (`parent_ids`) and equivalence
    (`equivalent_to`) relationships -- NEVER semantic/content similarity.

    For each pair of distinct selected ids `(x, y)`, exactly one classification applies:
    - `EQUIVALENT_INFORMATION`: x and y are in the same equivalence component
      (`equivalence.equivalence_classes`).
    - `DIRECT_ANCESTOR_DESCENDANT`: x is an ancestor of y, or y is an ancestor of x
      (checked after equivalence, so an equivalent pair is never also reported as
      ancestor/descendant even if it happens to also have a lineage edge -- equivalence
      takes precedence as the more specific corroboration-relevant finding).
    - `SHARED_LINEAGE_ORIGIN`: not equivalent, not in a direct ancestor/descendant
      relationship, but their root-origin sets intersect (per `shared_origin_report`).
    - `MULTI_ORIGIN_DERIVED`: informational per-item tag (not a pairwise classification) --
      the item itself has more than one root origin (multi-parent derivation reaching more
      than one foundation memory). Reported per-item in `detail["per_item"]`, not as a
      pairwise classification.
    - `LINEAGE_INDEPENDENT`: none of the above relationships hold for this pair. **This is
      NEVER proof of epistemic/causal independence** -- see the prominent caveat below and
      in the README. It means only: no explicit lineage or equivalence relationship was
      found between x and y in the data available to this function.
    - `UNKNOWN`: one or both of x/y are absent from `memories` entirely, so no relationship
      can be determined either way.

    ================================================================================
    PROMINENT CAVEAT: `LINEAGE_INDEPENDENT` is NOT proof of independent evidence. It is
    a narrow, structural statement: "no explicit `parent_ids` or `equivalent_to` edge
    connects these two memories, and they do not share a detected root origin." Genuine
    epistemic independence (did these two facts really come from separate, uncorrelated
    real-world sources?) is NOT something this module can ever determine -- there is no
    semantic model here by design (per the 3.2-D task brief's absolute scope limits). Two
    `LINEAGE_INDEPENDENT` memories could still restate the same fact through an entirely
    undeclared channel. Always read this classification as "LINEAGE-independent", never
    as "independent" unqualified.
    ================================================================================

    `detail["per_item"]` reports, per selected id: its equivalence component, direct
    parents, and root origins (per the 3.2-D task brief's required structure).
    `detail["pairwise"]` reports the classification per unordered pair.
    `value` is NOT a single opaque independence score (per the 3.2-D task brief's explicit
    prohibition on inventing one) -- it is simply the count of pairs classified
    `LINEAGE_INDEPENDENT`, provided only as a convenience count alongside the full
    structural detail, never as a stand-in for "how independent is this evidence set."
    """
    if len(selected_ids) == 0:
        return MetricResult(
            metric_name="INDEPENDENCE_REPORT",
            value=None,
            status=STATUS_UNDEFINED_EMPTY_SEQUENCE,
            detail={},
            note="selected_ids is empty; independence report is undefined.",
        )

    distinct_ids = list(dict.fromkeys(selected_ids))

    equiv_result = equivalence_classes(memories=memories, require_symmetric=True)
    id_to_component: Dict[str, int] = {}
    for idx, component in enumerate(equiv_result.detail["components"]):
        for mid in component:
            id_to_component[mid] = idx

    per_item: Dict[str, Dict[str, object]] = {}
    for mid in distinct_ids:
        if mid not in memories:
            per_item[mid] = {
                "known": False,
                "equivalence_component": None,
                "direct_parents": None,
                "root_origins": None,
                "multi_origin_derived": None,
            }
            continue
        parents = memories[mid].get("parent_ids") or []
        roots = root_origins(memories, mid).detail.get("roots", [])
        per_item[mid] = {
            "known": True,
            "equivalence_component": sorted(
                equiv_result.detail["components"][id_to_component[mid]]
            )
            if mid in id_to_component
            else [mid],
            "direct_parents": sorted(parents),
            "root_origins": sorted(roots),
            "multi_origin_derived": len(roots) > 1,
        }

    pairwise: Dict[str, str] = {}
    lineage_independent_count = 0

    for i in range(len(distinct_ids)):
        for j in range(i + 1, len(distinct_ids)):
            x, y = distinct_ids[i], distinct_ids[j]
            pair_key = f"{x}|{y}"

            if not per_item[x]["known"] or not per_item[y]["known"]:
                pairwise[pair_key] = CLASS_UNKNOWN
                continue

            if (
                x in id_to_component
                and y in id_to_component
                and id_to_component[x] == id_to_component[y]
            ):
                pairwise[pair_key] = CLASS_EQUIVALENT_INFORMATION
                continue

            x_ancestors = ancestors(memories, x, include_self=False).detail.get("ancestors", [])
            y_ancestors = ancestors(memories, y, include_self=False).detail.get("ancestors", [])
            if y in x_ancestors or x in y_ancestors:
                pairwise[pair_key] = CLASS_DIRECT_ANCESTOR_DESCENDANT
                continue

            x_roots = set(per_item[x]["root_origins"] or [])
            y_roots = set(per_item[y]["root_origins"] or [])
            if x_roots & y_roots:
                pairwise[pair_key] = CLASS_SHARED_LINEAGE_ORIGIN
                continue

            pairwise[pair_key] = CLASS_LINEAGE_INDEPENDENT
            lineage_independent_count += 1

    return MetricResult(
        metric_name="INDEPENDENCE_REPORT",
        value=float(lineage_independent_count),
        status=STATUS_OK,
        detail={
            "per_item": per_item,
            "pairwise": pairwise,
            "lineage_independent_pair_count": lineage_independent_count,
            "total_pairs": len(pairwise),
        },
        note=(
            "value = count of pairs classified LINEAGE_INDEPENDENT (a convenience count, NOT "
            "an opaque independence score). LINEAGE_INDEPENDENT is scoped strictly to 'no "
            "explicit lineage/equivalence relationship found' -- it is NEVER proof of "
            "epistemic/causal independence. See module docstring DECISION P3."
        ),
    )
