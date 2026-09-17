"""Phase 7.3 -- Benign Baseline.

WHY THIS STAGE MUST EXIST BEFORE ANY "ABNORMAL" CLAIM
--------------------------------------------------------------------------------
Phase 7 plan Sec 4, point 3 is explicit: every propagation-shape signal must be
computed identically over benign memory growth (no attack present) before it is
ever called "abnormal" against an attack footprint -- mirroring this project's
own established discipline (Phase 6's B0 no-defense control, Phase 3's
Condition A no-memory baseline) of never reporting a detection number without
its corresponding false-positive-on-benign-behavior number alongside it. This
module is that measurement, and nothing more: it runs the SAME four Stage 7.4
signal functions, UNMODIFIED, over benign-rooted footprints
(`build_benign_footprint()`, Stage 7.2) and reports a plain descriptive
distribution -- no threshold is proposed here, and none should be read into
this module's output. Threshold-setting (if it ever happens) is explicitly out
of scope for Phase 7 v1 (plan Sec 6, point 1): this is a monitor, not a
defense.

WHAT "BENIGN" MEANS HERE
--------------------------------------------------------------------------------
`benign_seed_memory_ids()` excludes only real `PRODUCED` targets -- memories a
real `attack_injection` event actually created. It does NOT additionally
exclude a `PROPAGATED_TO` descendant of an attack that happens to also be
reachable from a different, clean ancestor by construction (Phase 3/5's own
provenance model does not allow a memory to have two independent creation
origins, so this distinction is moot in practice, but is named here rather than
silently assumed). A caller building the narrower "attacks present but their
footprint excluded" corpus the plan's Sec 3 also allows should additionally
subtract every id `tainted_memories()` names as reachable from any known attack
root before calling `compute_benign_baseline()`.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Dict, Sequence, Tuple

from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger
from phase5.schema.event_ledger import Phase5EventLedger
from phase5.wiring.lineage import PRODUCED
from phase5.wiring.trace_assembly import PropagationGraph

from phase7.propagation.footprint import all_retrieval_task_ids, build_benign_footprint
from phase7.propagation.signals import cross_task_bleed, cycle_reinforcement_depth, fan_out_rate, re_entry_rate

BASELINE_VERSION = "benign-baseline-1.0.0"


def benign_seed_memory_ids(memory_ledger: CanonicalMemoryLedger, graph: PropagationGraph) -> Tuple[str, ...]:
    """Every real memory id in `memory_ledger` that is NOT a `PRODUCED` target
    (see module docstring, "WHAT 'BENIGN' MEANS HERE"). Deterministic ordering
    (sorted by memory_id) -- never ledger insertion order."""
    attack_produced_ids = {e.target_id for e in graph.edges_of_type(PRODUCED)}
    return tuple(sorted(
        r.memory_id for r in memory_ledger.list_records() if r.memory_id not in attack_produced_ids
    ))


@dataclass(frozen=True)
class SignalDistribution:
    """Descriptive statistics only, per this module's own charter above -- never
    an invented threshold. `n=0` (an all-`nan` distribution) means the signal
    could not be computed for any seed at all (e.g. `re_entry_rate` when the run
    has no real retrieval task at all to form a denominator from), reported
    honestly rather than silently coerced to 0.0, which would be indistinguishable
    from a real, measured zero rate."""

    n: int
    values: Tuple[float, ...]
    mean: float
    median: float
    minimum: float
    maximum: float
    stdev: float  # 0.0 when n == 1 (no variance to measure); nan when n == 0


def _distribution(values: Sequence[float]) -> SignalDistribution:
    vs = tuple(values)
    if not vs:
        nan = float("nan")
        return SignalDistribution(n=0, values=(), mean=nan, median=nan, minimum=nan, maximum=nan, stdev=nan)
    return SignalDistribution(
        n=len(vs), values=vs, mean=statistics.mean(vs), median=statistics.median(vs),
        minimum=min(vs), maximum=max(vs), stdev=statistics.stdev(vs) if len(vs) >= 2 else 0.0,
    )


@dataclass(frozen=True)
class BenignBaselineReport:
    """One distribution per Stage 7.4 signal, over `seed_memory_ids`, plus the
    union of `evidence_kind`s each signal actually rested on across every seed
    -- so a reader can see at a glance, e.g., that `fan_out_rate` here is
    entirely `OBSERVED_EVENT`-backed, never silently upgraded or conflated with
    a stronger/weaker kind than what was really measured."""

    seed_memory_ids: Tuple[str, ...]
    fan_out_rate: SignalDistribution
    re_entry_rate: SignalDistribution
    cycle_reinforcement_depth: SignalDistribution
    cross_task_bleed: SignalDistribution
    evidence_kinds_by_signal: Dict[str, Tuple[str, ...]]


def compute_benign_baseline(
    seed_memory_ids: Sequence[str],
    *,
    graph: PropagationGraph,
    event_ledger: CanonicalEventLedger,
    phase5_event_ledger: Phase5EventLedger,
    fan_out_denominator: float = 1.0,
) -> BenignBaselineReport:
    """Run `build_benign_footprint()` + all four Stage 7.4 signal functions,
    UNMODIFIED, over every seed in `seed_memory_ids` -- the same functions a
    later stage runs over real attack footprints, so any future "is this
    abnormal" comparison is apples-to-apples by construction.

    `fan_out_denominator` is passed straight through to `fan_out_rate()` for
    every seed (the same unit -- e.g. "per task processed" -- must be used for
    both the baseline and whatever it is later compared against, or the
    comparison is meaningless; this function does not pick a unit on the
    caller's behalf). `re_entry_rate` is computed only if this run has at least
    one real retrieval task at all (a real denominator to divide by); if not,
    its distribution is reported as `n=0` rather than a fabricated 0.0 (see
    `SignalDistribution`).
    """
    if not seed_memory_ids:
        raise ValueError("seed_memory_ids must be non-empty -- a baseline needs at least one real benign seed.")

    all_task_ids = all_retrieval_task_ids(phase5_event_ledger)

    fan_out_values, re_entry_values, depth_values, bleed_values = [], [], [], []
    fan_out_kinds, re_entry_kinds, depth_kinds, bleed_kinds = set(), set(), set(), set()

    for seed_id in seed_memory_ids:
        footprint = build_benign_footprint(
            seed_id, graph=graph, event_ledger=event_ledger, phase5_event_ledger=phase5_event_ledger,
        )

        fo = fan_out_rate(footprint, denominator=fan_out_denominator)
        fan_out_values.append(fo.value)
        fan_out_kinds |= set(fo.evidence_kinds)

        if all_task_ids:
            re = re_entry_rate(footprint, all_task_ids=all_task_ids)
            re_entry_values.append(re.value)
            re_entry_kinds |= set(re.evidence_kinds)

        depth = cycle_reinforcement_depth(footprint)
        depth_values.append(depth.value)
        depth_kinds |= set(depth.evidence_kinds)

        bleed = cross_task_bleed(footprint)
        bleed_values.append(bleed.value)
        bleed_kinds |= set(bleed.evidence_kinds)

    return BenignBaselineReport(
        seed_memory_ids=tuple(seed_memory_ids),
        fan_out_rate=_distribution(fan_out_values),
        re_entry_rate=_distribution(re_entry_values),
        cycle_reinforcement_depth=_distribution(depth_values),
        cross_task_bleed=_distribution(bleed_values),
        evidence_kinds_by_signal={
            "fan_out_rate": tuple(sorted(fan_out_kinds)),
            "re_entry_rate": tuple(sorted(re_entry_kinds)),
            "cycle_reinforcement_depth": tuple(sorted(depth_kinds)),
            "cross_task_bleed": tuple(sorted(bleed_kinds)),
        },
    )


__all__ = [
    "BASELINE_VERSION", "SignalDistribution", "BenignBaselineReport",
    "benign_seed_memory_ids", "compute_benign_baseline",
]
