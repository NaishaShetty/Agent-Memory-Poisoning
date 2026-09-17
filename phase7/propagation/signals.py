"""Phase 7.4 -- Propagation-Shape Signals.

Four pure functions over a `PropagationFootprint` (Stage 7.2), each answering one
of the Phase 7 plan's Sec 4 point 2 questions. Every signal returns a
`SignalResult` naming which `evidence_kind`(s) its underlying edges actually carry
-- per the plan's evidence-kind discipline (Sec 5, point 2), a signal is never
reported without disclosing whether it rests on OBSERVED_EVENT, EXPOSURE_ONLY, or
LINEAGE_REACHABILITY edges. None of these functions reads a ledger directly; they
are read-only consumers of a `PropagationFootprint`, mirroring
`phase6.defense.propagation.signals`'s own plain-data-carrier discipline.

These signals are STRUCTURAL (edge-count/graph-shape based), not content-
similarity based -- unlike `lineage_taint_signal()`'s Jaccard-based
`content_retention()` term, which is already disclosed as defeatable by
paraphrase (`docs/phase6/ADAPTIVE_ATTACKER_KNOWLEDGE.md`). Whether that makes
them robust to a "shallow-and-wide" adaptive attacker (many independent short
chains instead of one deep chain) is an open, disclosed question this module
does NOT claim to have answered -- that is Stage 7.7's job, not this one's.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Sequence, Tuple

from phase5.wiring.lineage import (
    DERIVED_FROM,
    EVIDENCE_EXPOSURE_ONLY,
    EVIDENCE_OBSERVED_EVENT,
    SELECTED_WITH,
    USED_BY,
)
from phase7.propagation.footprint import FootprintEdge, PropagationFootprint

SIGNALS_VERSION = "propagation-shape-signals-1.0.0"


@dataclass(frozen=True)
class SignalResult:
    """One signal's value, the `evidence_kind`(s) actually backing it (empty tuple
    if the signal found nothing to measure), and a `detail` dict of the raw counts
    a caller can audit without recomputing the signal."""

    value: float
    evidence_kinds: Tuple[str, ...]
    detail: Dict[str, object]


def _evidence_kinds(edges: Sequence[FootprintEdge]) -> Tuple[str, ...]:
    return tuple(sorted({fe.edge.evidence_kind for fe in edges}))


def fan_out_rate(footprint: PropagationFootprint, *, denominator: float) -> SignalResult:
    """New `DERIVED_FROM` edges whose parent (`DERIVED_FROM`'s `target_id`) is
    already a footprint member -- i.e. a real derivation event that used a
    footprint member as one of its sources -- per `denominator` (caller-
    supplied: elapsed wall-clock seconds, or tasks processed; unit is the
    caller's choice, this function only counts events).

    `PRODUCED` is deliberately NOT counted here, despite the Phase 7 plan's own
    Sec 4 point 2 naming "DERIVED_FROM/PRODUCED edges" together: a `PRODUCED`
    edge's `source_id` is always an injection_id (`derive_produced_edges()`),
    never a memory_id, and `footprint.member_ids` only ever contains memory_ids
    -- so a `PRODUCED` edge can structurally never originate FROM a footprint
    member, and a clause checking for it would always be dead code. Fan-out, as
    actually measurable from the real edge vocabulary, is a `DERIVED_FROM`-only
    signal.
    """
    if denominator <= 0:
        raise ValueError(f"denominator must be > 0; got {denominator}")
    originating = [
        fe for fe in footprint.edges
        if fe.edge.relationship_type == DERIVED_FROM and fe.edge.target_id in footprint.member_ids
    ]
    return SignalResult(
        value=len(originating) / denominator,
        evidence_kinds=_evidence_kinds(originating),
        detail={"originating_edge_count": len(originating), "denominator": denominator},
    )


def re_entry_rate(footprint: PropagationFootprint, *, all_task_ids: Sequence[str]) -> SignalResult:
    """Fraction of tasks (out of `all_task_ids`, the real task universe the caller
    observed -- never guessed) whose top-K selected set contained 2+ footprint
    members simultaneously: a real `SELECTED_WITH` edge whose BOTH endpoints are
    footprint members. This is the direct, measurable formalization of the FARMA
    "8 of 8 top-K slots" crowding phenomenon named in
    `PHASE5_HANDOFF_REPORT.md` Sec 5 (Phase 7 plan Sec 3, Sec 7.6).
    """
    if not all_task_ids:
        raise ValueError("all_task_ids must be non-empty -- a rate needs a real denominator.")
    crowded = [
        fe for fe in footprint.edges
        if fe.edge.relationship_type == SELECTED_WITH
        and fe.edge.source_id in footprint.member_ids
        and fe.edge.target_id in footprint.member_ids
    ]
    crowded_task_ids = tuple(sorted({fe.task_id for fe in crowded if fe.task_id is not None}))
    total_tasks = len(set(all_task_ids))
    return SignalResult(
        value=len(crowded_task_ids) / total_tasks,
        evidence_kinds=_evidence_kinds(crowded),
        detail={"crowded_task_ids": crowded_task_ids, "total_tasks": total_tasks},
    )


def _longest_derived_from_chain(footprint: PropagationFootprint) -> Tuple[str, ...]:
    child_to_parents: Dict[str, Tuple[str, ...]] = {}
    for fe in footprint.edges:
        e = fe.edge
        if e.relationship_type == DERIVED_FROM and e.source_id in footprint.member_ids and e.target_id in footprint.member_ids:
            child_to_parents[e.source_id] = child_to_parents.get(e.source_id, ()) + (e.target_id,)

    def _longest_from(memory_id: str, visited: frozenset) -> Tuple[str, ...]:
        parents = child_to_parents.get(memory_id, ())
        best: Tuple[str, ...] = (memory_id,)
        for parent_id in parents:
            if parent_id in visited:
                continue
            candidate = (memory_id,) + _longest_from(parent_id, visited | {parent_id})
            if len(candidate) > len(best):
                best = candidate
        return best

    return max(
        (_longest_from(mid, frozenset({mid})) for mid in footprint.member_ids),
        key=len,
        default=(footprint.root_memory_id,),
    )


def cycle_reinforcement_depth(footprint: PropagationFootprint) -> SignalResult:
    """Longest `DERIVED_FROM` chain within the footprint (member-to-member),
    measured in hops -- the closest graph-native definition of "self-reinforcing"
    available from the real, already-collected edge vocabulary (Phase 7 plan
    Sec 4, point 2). A `DERIVED_FROM` chain alone already captures "a footprint
    memory used to derive another footprint memory," since a child's own
    `DERIVED_FROM` edge names its real parent directly: an intervening `USED_BY`
    hop through a decision_id is not a separate STRUCTURAL requirement, because
    `USED_BY` targets a decision_id and no `DERIVED_FROM` edge can ever originate
    from a decision_id (decision_ids and memory_ids share no id-namespace).

    `corroborated_by_decision` reports, per hop, whether that hop's PARENT memory
    also has a real `USED_BY` edge to some decision (necessarily `EXPOSURE_ONLY`
    evidence) -- auxiliary corroboration that a decision was at least exposed to
    the ancestor, never used to inflate `value` itself.
    """
    chain = _longest_derived_from_chain(footprint)
    depth = len(chain) - 1

    used_by_sources = {
        fe.edge.source_id for fe in footprint.edges if fe.edge.relationship_type == USED_BY
    }
    corroborated = tuple(mid in used_by_sources for mid in chain[:-1])

    depth_edges = [
        fe for fe in footprint.edges
        if fe.edge.relationship_type == DERIVED_FROM
        and fe.edge.source_id in chain and fe.edge.target_id in chain
    ]
    kinds = _evidence_kinds(depth_edges)
    if any(corroborated):
        kinds = tuple(sorted(set(kinds) | {EVIDENCE_EXPOSURE_ONLY}))

    return SignalResult(
        value=float(depth), evidence_kinds=kinds,
        detail={"longest_chain": chain, "corroborated_by_decision": corroborated},
    )


def cross_task_bleed(footprint: PropagationFootprint) -> SignalResult:
    """Whether the footprint spans more than one real task_id -- distinguishing
    contained, single-task influence from cross-session spread (Phase 7 plan Sec
    4, point 2). Unions two real sources, never inferring a task_id from
    anything else: (a) every edge-carried task_id (`FootprintEdge.task_id`,
    resolved from the edge's own citing event), and (b)
    `footprint.retrieval_task_ids` (`query_co_retrieved_memory_ids()`'s group
    query, per `build_propagation_footprint()`'s module docstring) -- which
    covers a footprint member retrieved ALONE in a task, where no pairwise
    `RETRIEVED_WITH`/`SELECTED_WITH` edge exists to carry that task_id. Without
    (b), a solo-retrieval task would be silently undercounted here."""
    edge_task_ids = {fe.task_id for fe in footprint.edges if fe.task_id is not None}
    retrieval_only_task_ids = tuple(sorted(set(footprint.retrieval_task_ids) - edge_task_ids))
    task_ids = tuple(sorted(edge_task_ids | set(footprint.retrieval_task_ids)))

    dated_edges = [fe for fe in footprint.edges if fe.task_id is not None]
    evidence_kinds = _evidence_kinds(dated_edges)
    if footprint.retrieval_task_ids:
        evidence_kinds = tuple(sorted(set(evidence_kinds) | {EVIDENCE_OBSERVED_EVENT}))

    return SignalResult(
        value=float(len(task_ids)),
        evidence_kinds=evidence_kinds,
        detail={
            "distinct_task_ids": task_ids,
            "bleeds_across_tasks": len(task_ids) > 1,
            "retrieval_only_task_ids": retrieval_only_task_ids,
        },
    )


__all__ = [
    "SIGNALS_VERSION", "SignalResult",
    "fan_out_rate", "re_entry_rate", "cycle_reinforcement_depth", "cross_task_bleed",
]
