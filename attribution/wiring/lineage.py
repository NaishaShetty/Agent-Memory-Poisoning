"""Attribution -- LINEAGE.

Question: what is this memory's real, immediate parentage? Reuses
`phase5.wiring.lineage.derive_derived_from_edges()` verbatim -- a DERIVED_FROM edge is
`source_id=child_memory_id, target_id=parent_memory_id`, one edge per real parent named
in a `derived` `CanonicalEvent`'s `source_memory_ids`.

WHY THIS IS ONE-HOP, NOT THE FULL CHAIN TO AN ATTACK
--------------------------------------------------------------------------------
"This memory's real ancestor chain, hop by hop" (the question LINEAGE answers) is a
structural parentage fact independent of whether any ancestor happens to be
attack-produced. Resolving a full grounded path specifically TO a confirmed attack
origin is a different, narrower question -- that is `attribute_propagation()`
(`attribution/wiring/propagation.py`), which reuses `tainted_memory_evidence()` for
exactly that. Keeping them separate means a memory's ordinary (non-attack) derivation
history is still attributable even when it has no attack ancestor at all.

MULTIPLE REAL PARENTS IS A GENUINE, REACHABLE CASE HERE (unlike ORIGIN)
--------------------------------------------------------------------------------
`derived`'s own `source_memory_ids` tuple can legitimately name more than one parent (a
merge-style derivation). `attribute_lineage()` reports `MULTIPLE_POSSIBLE_SOURCES` in
that case -- never arbitrarily picking one parent as "the" lineage source.

`full_chain=True` -- FULL ANCESTOR CHAIN, NOT JUST IMMEDIATE PARENTAGE
--------------------------------------------------------------------------------
By default (`full_chain=False`) this function answers only the one-hop question. Passing
`full_chain=True` walks the ENTIRE real ancestor graph (repeated `derive_derived_from_edges()`
traversal, cycle-safe via a visited set) and answers the full "what is this memory's
complete real ancestor chain" question:
- If every node walked has at most one real parent, the ancestor graph is a single linear
  chain -- `status=UNIQUE`, `source_id` is the deepest root ancestor, `lineage_path` is
  the complete chain from that root to `memory_id`, inclusive.
- If ANY node along the way has more than one real parent, the full chain is genuinely
  branching (a DAG, not a single path) -- `status=MULTIPLE_POSSIBLE_SOURCES`, with
  `candidate_source_ids` naming EVERY distinct ancestor found (never narrowed to only the
  deepest roots, which could under-report a real branch point that reconverges deeper --
  e.g. a diamond-shaped derivation history), and no single `lineage_path` is asserted.
This is still the same LINEAGE question as the one-hop case (real parentage, independent
of any attack), just answered exhaustively rather than one hop at a time -- it remains
distinct from `attribute_propagation()`, which answers a narrower question scoped to a
caller-given set of attack origins.
"""

from __future__ import annotations

from collections import deque
from typing import Dict, List, Tuple

from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger

from phase5.wiring.lineage import EVIDENCE_OBSERVED_EVENT, derive_derived_from_edges

from attribution.schema import (
    ATTRIBUTION_LINEAGE,
    SOURCE_MEMORY,
    SOURCE_NONE,
    STATUS_MULTIPLE_POSSIBLE_SOURCES,
    STATUS_NO_LINEAGE_ANCESTOR,
    STATUS_UNIQUE,
    TARGET_MEMORY,
    AttributionResult,
    generate_attribution_id,
)


def attribute_lineage(memory_id: str, *, run_id: str, event_ledger: CanonicalEventLedger, full_chain: bool = False) -> AttributionResult:
    """One `AttributionResult` for `memory_id`'s real parentage, within `run_id`.
    `full_chain=False` (default): immediate (one-hop) parentage only. `full_chain=True`:
    the complete real ancestor graph -- see module docstring."""
    edges = [e for e in derive_derived_from_edges(event_ledger) if e.source_id == memory_id]

    if not edges:
        return AttributionResult(
            attribution_id=generate_attribution_id(attribution_type=ATTRIBUTION_LINEAGE, run_id=run_id, target_id=memory_id, full_chain=full_chain),
            run_id=run_id, target_type=TARGET_MEMORY, target_id=memory_id,
            attribution_type=ATTRIBUTION_LINEAGE, status=STATUS_NO_LINEAGE_ANCESTOR, source_type=SOURCE_NONE,
            rationale=f"No real 'derived' CanonicalEvent names memory_id={memory_id!r} as a child -- this is a root/foundation memory, not derived from anything.",
        )

    if full_chain:
        return _attribute_lineage_full_chain(memory_id, run_id=run_id, event_ledger=event_ledger)

    parent_ids = tuple(sorted({e.target_id for e in edges}))
    all_event_ids = tuple(sorted({eid for e in edges for eid in e.established_by_event_ids}))

    if len(parent_ids) == 1:
        return AttributionResult(
            attribution_id=generate_attribution_id(
                attribution_type=ATTRIBUTION_LINEAGE, run_id=run_id, target_id=memory_id, source_id=parent_ids[0],
            ),
            run_id=run_id, target_type=TARGET_MEMORY, target_id=memory_id,
            attribution_type=ATTRIBUTION_LINEAGE, status=STATUS_UNIQUE,
            source_type=SOURCE_MEMORY, source_id=parent_ids[0],
            lineage_path=(parent_ids[0], memory_id),
            evidence_event_ids=all_event_ids, evidence_kind=EVIDENCE_OBSERVED_EVENT,
            rationale=f"Real 'derived' event(s) {all_event_ids!r} name exactly one parent, {parent_ids[0]!r}, for memory_id={memory_id!r}.",
        )

    return AttributionResult(
        attribution_id=generate_attribution_id(
            attribution_type=ATTRIBUTION_LINEAGE, run_id=run_id, target_id=memory_id, candidate_source_ids=parent_ids,
        ),
        run_id=run_id, target_type=TARGET_MEMORY, target_id=memory_id,
        attribution_type=ATTRIBUTION_LINEAGE, status=STATUS_MULTIPLE_POSSIBLE_SOURCES,
        source_type=SOURCE_MEMORY, candidate_source_ids=parent_ids,
        evidence_event_ids=all_event_ids, evidence_kind=EVIDENCE_OBSERVED_EVENT,
        rationale=f"Real 'derived' event(s) {all_event_ids!r} name {len(parent_ids)} distinct real parents for memory_id={memory_id!r} -- a genuine merge-derivation, not an arbitrary pick.",
    )


def _attribute_lineage_full_chain(memory_id: str, *, run_id: str, event_ledger: CanonicalEventLedger) -> AttributionResult:
    """Full-chain traversal -- see `attribute_lineage(full_chain=True)`'s module docstring
    entry. Reuses `derive_derived_from_edges()` verbatim for every edge; never re-derives
    parentage from `CanonicalMemoryRecord.parent_ids` directly (that would bypass the
    citable-event discipline every other attribution function here follows)."""
    edges = derive_derived_from_edges(event_ledger)
    parents_by_child: Dict[str, List[Tuple[str, str]]] = {}
    for e in edges:
        parents_by_child.setdefault(e.source_id, []).append((e.target_id, e.established_by_event_ids[0]))

    visited = {memory_id}
    all_event_ids: List[str] = []
    has_branch = False
    queue = deque([memory_id])
    while queue:
        current = queue.popleft()
        parent_pairs = parents_by_child.get(current, [])
        if len(parent_pairs) > 1:
            has_branch = True
        for parent_id, event_id in parent_pairs:
            all_event_ids.append(event_id)
            if parent_id in visited:
                continue  # cycle-safety -- should not occur, mirrors _find_parent_path()'s own discipline
            visited.add(parent_id)
            queue.append(parent_id)

    sorted_event_ids = tuple(sorted(set(all_event_ids)))
    ancestors = tuple(sorted(visited - {memory_id}))

    if not has_branch:
        # A single linear chain -- reconstruct it by following the one parent at each hop.
        path = [memory_id]
        current = memory_id
        while current in parents_by_child:
            parent_id, _ = parents_by_child[current][0]
            path.append(parent_id)
            current = parent_id
        path.reverse()  # root ... memory_id
        return AttributionResult(
            attribution_id=generate_attribution_id(
                attribution_type=ATTRIBUTION_LINEAGE, run_id=run_id, target_id=memory_id, full_chain=True, source_id=path[0],
            ),
            run_id=run_id, target_type=TARGET_MEMORY, target_id=memory_id,
            attribution_type=ATTRIBUTION_LINEAGE, status=STATUS_UNIQUE,
            source_type=SOURCE_MEMORY, source_id=path[0], lineage_path=tuple(path),
            evidence_event_ids=sorted_event_ids, evidence_kind=EVIDENCE_OBSERVED_EVENT,
            rationale=f"Full real ancestor chain for memory_id={memory_id!r} is a single linear path {tuple(path)!r} with no branching.",
        )

    return AttributionResult(
        attribution_id=generate_attribution_id(
            attribution_type=ATTRIBUTION_LINEAGE, run_id=run_id, target_id=memory_id, full_chain=True, candidate_source_ids=ancestors,
        ),
        run_id=run_id, target_type=TARGET_MEMORY, target_id=memory_id,
        attribution_type=ATTRIBUTION_LINEAGE, status=STATUS_MULTIPLE_POSSIBLE_SOURCES,
        source_type=SOURCE_MEMORY, candidate_source_ids=ancestors,
        evidence_event_ids=sorted_event_ids, evidence_kind=EVIDENCE_OBSERVED_EVENT,
        rationale=(
            f"Full real ancestor graph for memory_id={memory_id!r} branches (at least one real ancestor has "
            f"more than one parent) -- reporting every distinct ancestor found, {ancestors!r}, rather than "
            "narrowing to only the deepest roots (which could under-report a branch that reconverges deeper)."
        ),
    )


__all__ = ["attribute_lineage"]
