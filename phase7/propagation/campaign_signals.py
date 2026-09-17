"""Phase 7.9 (post-report extension) -- Campaign-Level Aggregation Signals.

CLOSES REPORT LIMITATION 5.3: THE PER-FOOTPRINT ROOT-SPLITTING BLIND SPOT
--------------------------------------------------------------------------------
Stage 7.7's adaptive-evasion check found: every Stage 7.4 signal is computed
PER-FOOTPRINT (one attack root at a time, via `build_propagation_footprint()`).
An attacker who splits ONE campaign's total attacker-produced volume across N
independent, low-volume roots keeps every INDIVIDUAL footprint's `fan_out_rate`
low, even though the population-wide total is identical to one deep chain of
the same size. The Phase 7 report (`docs/phase7/PHASE7_REPORT.md` Sec 5.3)
named this a real, disclosed gap, explicitly out of scope for v1: "closing this
would require a cross-footprint, campaign-level aggregation layer." This
module is that layer -- still a MONITOR, not a defense: it aggregates and
reports real per-footprint `SignalResult`s, it never blocks, quarantines, or
otherwise intervenes, so it does not cross the line the plan's Sec 6 point 1
draws.

WHAT "CAMPAIGN" MEANS HERE -- NO NEW CONCEPT, JUST "EVERY REAL ATTACK ROOT
DISCOVERABLE IN ONE ALREADY-ASSEMBLED GRAPH"
--------------------------------------------------------------------------------
No new grouping key is introduced. `discover_campaign_root_ids()` reuses the
exact same `PRODUCED`-edge-target discovery `benign_baseline.py`'s
`benign_seed_memory_ids()` already uses, for the opposite purpose (that
function EXCLUDES these ids to build a benign corpus; this module COLLECTS
them to build a campaign). A caller who already knows their own subset of
attack roots (e.g. a specific attack's own live-trial roots, as opposed to
every attack root the whole run happens to contain) may pass `root_ids`
directly to any of the three functions below instead of calling
`discover_campaign_root_ids()` first.

THREE SIGNALS -- WHY EACH AGGREGATES THE WAY IT DOES, NOT UNIFORMLY
--------------------------------------------------------------------------------
- `campaign_fan_out_rate()` -- SUMS every root's own real `fan_out_rate`
  numerator, then divides once by a campaign-level denominator. Edge counts
  legitimately sum: N attacker-adjacent memories split across N independent
  roots (1 each) now report the SAME total as one deep chain of N, closing
  the report's own named blind spot.
- `campaign_max_cycle_reinforcement_depth()` -- takes the MAX, never the sum,
  of every root's own `cycle_reinforcement_depth`, mirroring the identical
  max-over-ancestors convention `phase6.defense.propagation.signals
  .lineage_taint_signal()` already uses for an analogous reason: one real deep
  chain elsewhere in the same campaign should not be diluted by averaging
  against unrelated shallow roots. This does NOT retroactively invent a fake
  deep chain for a genuinely shallow-and-wide campaign (there is no length-N
  path to find in one); it only prevents a real one from being hidden by
  co-occurring shallow roots.
- `campaign_re_entry_rate()` -- generalizes `re_entry_rate()`'s own "both
  endpoints in THIS footprint's member_ids" test to "both endpoints in the
  UNION of every campaign root's member_ids." This is the one signal the
  report explicitly flagged as "not shown to have the [splitting] blind
  spot... but not exhaustively verified either" -- and verification here
  finds a REAL, previously-undisclosed instance of the same blind spot at the
  campaign level: N independent single-node roots, each contributing exactly
  one candidate to the SAME real retrieval task, can fully crowd that task's
  top-K (structurally identical to FARMA's real crowding mechanism) while
  every INDIVIDUAL root's own one-node footprint reports `re_entry_rate = 0`
  (a one-node footprint has no other member to be co-selected WITH). See
  `phase7/tests/test_campaign_signals.py` for the actual measured
  reproduction of this, not just the claim.

NOT A NEW EVIDENCE KIND OR EDGE TYPE
--------------------------------------------------------------------------------
Every value here is a real aggregation (sum/max/union) of Stage 7.4's own,
unmodified `SignalResult`s and `PropagationFootprint`s -- no new
edge-derivation function is added, and no new evidence-kind vocabulary entry
is introduced (plan Sec 6 point 1, still honored).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Sequence, Tuple

from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger
from phase5.schema.event_ledger import Phase5EventLedger
from phase5.wiring.lineage import PRODUCED, SELECTED_WITH
from phase5.wiring.trace_assembly import PropagationGraph

from phase7.propagation.footprint import FootprintEdge, all_retrieval_task_ids, build_propagation_footprint
from phase7.propagation.signals import SignalResult, cycle_reinforcement_depth, fan_out_rate, re_entry_rate

CAMPAIGN_SIGNALS_VERSION = "campaign-aggregation-signals-1.1.0"


def discover_campaign_root_ids(graph: PropagationGraph) -> Tuple[str, ...]:
    """Every real attack-produced root in `graph` -- the same PRODUCED-edge-target
    discovery `benign_baseline.py::benign_seed_memory_ids()` already uses, for the
    opposite purpose. Deterministic (sorted) ordering, never ledger insertion
    order."""
    return tuple(sorted({e.target_id for e in graph.edges_of_type(PRODUCED)}))


@dataclass(frozen=True)
class CampaignSignalResult:
    """One campaign-level aggregate: its `value`, the union of `evidence_kinds`
    the underlying real edges carried, and `per_root` -- every individual root's
    own (unmodified, Stage 7.4) `SignalResult`, kept for audit so a caller can
    always see the per-footprint numbers this aggregate was built from, never
    just the aggregate alone."""

    value: float
    evidence_kinds: Tuple[str, ...]
    per_root: Dict[str, SignalResult]


def _footprints(
    root_ids: Sequence[str], *, graph: PropagationGraph, event_ledger: CanonicalEventLedger,
    phase5_event_ledger: Phase5EventLedger,
) -> Dict[str, object]:
    if not root_ids:
        raise ValueError("root_ids must be non-empty -- a campaign aggregate needs at least one real attack root.")
    return {
        root_id: build_propagation_footprint(
            root_id, graph=graph, event_ledger=event_ledger, phase5_event_ledger=phase5_event_ledger,
        )
        for root_id in root_ids
    }


def campaign_fan_out_rate(
    root_ids: Sequence[str], *, graph: PropagationGraph, event_ledger: CanonicalEventLedger,
    phase5_event_ledger: Phase5EventLedger, denominator: float = 1.0,
) -> CampaignSignalResult:
    """Real sum of every root's own `fan_out_rate` numerator (each computed with
    `denominator=1.0`, i.e. the raw `DERIVED_FROM` count), divided once by
    `denominator` -- see module docstring."""
    if denominator <= 0:
        raise ValueError(f"denominator must be > 0; got {denominator}")
    footprints = _footprints(root_ids, graph=graph, event_ledger=event_ledger, phase5_event_ledger=phase5_event_ledger)
    per_root, kinds, total = {}, set(), 0.0
    for root_id, footprint in footprints.items():
        result = fan_out_rate(footprint, denominator=1.0)
        per_root[root_id] = result
        kinds |= set(result.evidence_kinds)
        total += result.value
    return CampaignSignalResult(value=total / denominator, evidence_kinds=tuple(sorted(kinds)), per_root=per_root)


def campaign_max_cycle_reinforcement_depth(
    root_ids: Sequence[str], *, graph: PropagationGraph, event_ledger: CanonicalEventLedger,
    phase5_event_ledger: Phase5EventLedger,
) -> CampaignSignalResult:
    """Real max of every root's own `cycle_reinforcement_depth` -- see module
    docstring for why max, not sum."""
    footprints = _footprints(root_ids, graph=graph, event_ledger=event_ledger, phase5_event_ledger=phase5_event_ledger)
    per_root, kinds, best = {}, set(), 0.0
    for root_id, footprint in footprints.items():
        result = cycle_reinforcement_depth(footprint)
        per_root[root_id] = result
        kinds |= set(result.evidence_kinds)
        best = max(best, result.value)
    return CampaignSignalResult(value=best, evidence_kinds=tuple(sorted(kinds)), per_root=per_root)


def campaign_re_entry_rate(
    root_ids: Sequence[str], *, graph: PropagationGraph, event_ledger: CanonicalEventLedger,
    phase5_event_ledger: Phase5EventLedger,
) -> CampaignSignalResult:
    """Real `re_entry_rate` generalization: a task counts as crowded if it
    co-selected 2+ memories belonging to the UNION of every campaign root's own
    footprint, regardless of which specific root each belongs to -- closing the
    campaign-level crowding blind spot named in the module docstring. `per_root`
    still reports each root's own (unchanged, individually-blind) `re_entry_rate`
    for comparison."""
    footprints = _footprints(root_ids, graph=graph, event_ledger=event_ledger, phase5_event_ledger=phase5_event_ledger)
    all_task_ids = all_retrieval_task_ids(phase5_event_ledger)

    campaign_member_ids = frozenset().union(*(fp.member_ids for fp in footprints.values()))
    seen_edges: Dict[Tuple[str, str, str], FootprintEdge] = {}
    for footprint in footprints.values():
        for fe in footprint.edges:
            if fe.edge.relationship_type == SELECTED_WITH:
                seen_edges[(fe.edge.source_id, fe.edge.target_id, fe.task_id or "")] = fe

    crowded = [
        fe for fe in seen_edges.values()
        if fe.edge.source_id in campaign_member_ids and fe.edge.target_id in campaign_member_ids
    ]
    if not all_task_ids:
        raise ValueError("all_task_ids must be non-empty -- a rate needs a real denominator.")
    crowded_task_ids = tuple(sorted({fe.task_id for fe in crowded if fe.task_id is not None}))
    total_tasks = len(set(all_task_ids))
    value = len(crowded_task_ids) / total_tasks
    kinds = tuple(sorted({fe.edge.evidence_kind for fe in crowded}))

    per_root = {
        root_id: re_entry_rate(footprint, all_task_ids=all_task_ids)
        for root_id, footprint in footprints.items()
    }
    return CampaignSignalResult(value=value, evidence_kinds=kinds, per_root=per_root)


@dataclass(frozen=True)
class ContentSimilarityCluster:
    """One real content-similarity cluster among campaign roots: `root_ids`
    (2+, since a singleton is not a cluster), and `min_pairwise_similarity`
    -- the weakest pairwise Jaccard similarity within the cluster, kept for
    audit so a caller can see how tight the grouping actually is, not just
    that it exists."""

    root_ids: Tuple[str, ...]
    min_pairwise_similarity: float


def campaign_content_similarity_clusters(
    root_ids: Sequence[str], *, memory_ledger: CanonicalMemoryLedger,
    near_duplicate_threshold: float = 0.7,
) -> Tuple[ContentSimilarityCluster, ...]:
    """CLOSES PART OF REPORT LIMITATION 5.3'S OWN DISCLOSED RESIDUAL GAP: "a
    genuinely adaptive attacker who avoids ever sharing a real retrieval task
    or derivation event with their own other memories would still be
    invisible to any signal in this file, since every one of them still
    requires a real, observed edge to aggregate over."

    This is the one campaign signal that does NOT require a shared edge
    between roots at all -- it groups roots purely by real CONTENT similarity
    (their own `CanonicalMemoryRecord.content['text']`), reusing the EXACT
    SAME clustering core Phase 6's retrieval-consensus defense already
    validated (`phase6.defense.retrieval.dedup_consensus.
    cluster_by_similarity_matrix`, `phase6.defense.retrieval.signals.
    _jaccard_similarity`/`_tokenize`) -- not reimplemented, per this
    project's own reuse discipline. It catches an attacker who splits one
    campaign's volume across N structurally-independent roots (no shared
    retrieval task, no derivation edge between them) but whose payloads are
    still textually similar to each other -- the common case for a
    volume/repetition-style split (MemoryGraft's own documented mechanism),
    since the content doing the actual poisoning work is usually what gets
    repeated.

    HONEST, DISCLOSED SCOPE LIMIT, NOT CLAIMED SOLVED: an attacker whose
    split payloads are ALSO textually diverse (no two roots share `near_
    duplicate_threshold` similarity) remains invisible to this signal too --
    that residual case is a genuine, irreducible limit of structural/lexical
    monitoring (the same disclosed boundary `phase6/defense/retrieval/
    signals.py` already carries for its own near-duplicate clustering), not
    something this function claims to close. Singleton clusters (a root that
    matches no other root) are never reported -- only real, 2+-member
    groupings are a "cluster" in this signal's sense.
    """
    from phase6.defense.retrieval.dedup_consensus import cluster_by_similarity_matrix
    from phase6.defense.retrieval.signals import _jaccard_similarity, _tokenize

    if not root_ids:
        raise ValueError("root_ids must be non-empty -- a campaign aggregate needs at least one real attack root.")

    records = {root_id: memory_ledger.get(root_id) for root_id in root_ids}
    missing = [root_id for root_id, record in records.items() if record is None]
    if missing:
        raise ValueError(f"No real CanonicalMemoryRecord found for root_ids {missing!r}.")

    ordered_ids = tuple(root_ids)
    tokenized = [_tokenize(str(records[rid].content.get("text", ""))) for rid in ordered_ids]
    n = len(tokenized)
    similarity_matrix = [[_jaccard_similarity(tokenized[i], tokenized[j]) for j in range(n)] for i in range(n)]
    cluster_of = cluster_by_similarity_matrix(similarity_matrix, near_duplicate_threshold)

    members_by_cluster: Dict[int, list] = {}
    for index, cluster_id in enumerate(cluster_of):
        members_by_cluster.setdefault(cluster_id, []).append(index)

    clusters = []
    for indices in members_by_cluster.values():
        if len(indices) < 2:
            continue
        pairwise = [
            similarity_matrix[i][j] for a, i in enumerate(indices) for j in indices[a + 1:]
        ]
        clusters.append(
            ContentSimilarityCluster(
                root_ids=tuple(ordered_ids[i] for i in indices),
                min_pairwise_similarity=min(pairwise),
            )
        )
    return tuple(clusters)


__all__ = [
    "CAMPAIGN_SIGNALS_VERSION", "CampaignSignalResult",
    "discover_campaign_root_ids", "campaign_fan_out_rate",
    "campaign_max_cycle_reinforcement_depth", "campaign_re_entry_rate",
    "ContentSimilarityCluster", "campaign_content_similarity_clusters",
]
