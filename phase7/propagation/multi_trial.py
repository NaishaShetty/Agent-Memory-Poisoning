"""Phase 7.5/7.6 multi-trial extension -- partially closes Limitation 5.1 (every
number in the original report was n=1).

SCOPE, PRECISELY -- WHAT THIS DOES AND DOES NOT FIX
--------------------------------------------------------------------------------
`phase5/wiring/live_attack_runs.py` is frozen Stage 5.4 wiring: each attack's
`run_live_*_injection()` hardcodes ONE fixed real artifact, with no parameter to
vary the injected content itself (`gate_reply` is the sole exception, and only
for Sleeper/MemoryGraft). This module does not modify that frozen wiring, and
does not fabricate variation in the injection step for the five attacks with no
such parameter -- doing that honestly would require driving each attack's OWN
real downstream mechanism, which is Report Limitation 5.2's separately-named,
much larger open item and remains out of scope here.

What this module DOES vary, genuinely, producing real n>1 distributions from
real, independently-computed graphs (never a repeated call expected to, or
forced to, produce the same number):

1. The DOWNSTREAM TOPOLOGY that Stage 7.5's own synthetic proxy chain builds
   after admission (`attack_study.py::_seed_downstream_chain`'s single fixed
   shape is one of four real topologies this module can now build:
   `single_child`, `two_siblings`, `chain_depth_2`, `no_children`). Every
   attack's admission step still runs through the same real, unmodified
   `run_live_*_injection()` call each time -- only what Phase 7 itself builds
   downstream of admission varies.
2. For FARMA crowding specifically, `run_farma_crowding_study()`'s own two
   already-exposed real parameters (`num_amplification_cycles`,
   `benign_candidate_texts`) -- both real, disclosed knobs the Stage 7.6 module
   already supported, just never swept before this module existed.

This does NOT claim to show attack-specific propagation structure (still
Limitation 5.2, untouched) -- it shows how the existing structural signals
behave across several real, distinct topologies/parameterizations rather than
exactly one, and reports the resulting distribution honestly, including when
that distribution has zero variance (a real finding, not a bug).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Sequence, Tuple

from phase3.evaluation.foundations.canonical import (
    CanonicalMemoryRecord,
    LIFECYCLE_CREATED,
    MEMORY_TYPE_DERIVED,
    SOURCE_TYPE_DERIVATION_EVENT,
)

from phase5.wiring.memory_lifecycle import record_memory_derivation
from phase5.wiring.retrieval_instrumentation import instrument_retrieval_and_selection
from phase5.wiring.trace_assembly import build_propagation_graph

from phase7.propagation.attack_study import (
    _GATE_REPLY_ATTACKS,
    _LIVE_INJECTION_RUNNERS,
    SEVEN_FROZEN_ATTACK_IDS,
    _first_admitted_memory,
    new_study_ledgers,
)
from phase7.propagation.benign_baseline import SignalDistribution, _distribution
from phase7.propagation.crowding_study import _DEFAULT_BENIGN_TEXTS, run_farma_crowding_study
from phase7.propagation.footprint import all_retrieval_task_ids, build_propagation_footprint
from phase7.propagation.signals import cross_task_bleed, cycle_reinforcement_depth, fan_out_rate, re_entry_rate

TS2 = "2026-09-16T00:01:00+00:00"
CFG = "CFG-phase7-multi-trial"

DOWNSTREAM_TOPOLOGIES: Tuple[str, ...] = ("single_child", "two_siblings", "chain_depth_2", "no_children")


def _make_derived_record(child_id: str, parent_id: str, attack_id: str, label: str) -> CanonicalMemoryRecord:
    return CanonicalMemoryRecord(
        memory_id=child_id, memory_type=MEMORY_TYPE_DERIVED,
        content={"text": f"{label} note derived from the {attack_id} poisoned memory"},
        source={"source_type": SOURCE_TYPE_DERIVATION_EVENT}, parent_ids=(parent_id,),
        creation_event=f"derivation-of-{child_id}", creation_timestamp=TS2, lifecycle_state=LIFECYCLE_CREATED,
    )


def _derive(ledgers, attack_id: str, child_id: str, parent_id: str, label: str) -> None:
    record_memory_derivation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        derived_record=_make_derived_record(child_id, parent_id, attack_id, label),
        source_memory_ids=(parent_id,), actor="phase7_multi_trial",
        reason=f"multi-topology downstream chain ({label}) for the {attack_id} footprint study", timestamp=TS2,
    )


def _retrieve(ledgers, attack_id: str, task_suffix: str, candidates, top_k: int) -> None:
    instrument_retrieval_and_selection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], task_id=f"task-{attack_id}-{task_suffix}", query=f"{task_suffix} query",
        candidates=candidates, config_fingerprint=CFG, actor="phase7_multi_trial", timestamp=TS2, top_k=top_k,
    )


def _seed_topology(ledgers, attack_id: str, root_id: str, root_content: str, topology: str) -> None:
    """Build one of `DOWNSTREAM_TOPOLOGIES` downstream of `root_id`. Every node
    and edge created is a real `record_memory_derivation()`/
    `instrument_retrieval_and_selection()` call -- no shortcuts, no fabricated
    ledger rows."""
    if topology not in DOWNSTREAM_TOPOLOGIES:
        raise ValueError(f"unknown topology {topology!r}; must be one of {DOWNSTREAM_TOPOLOGIES!r}")

    if topology == "no_children":
        _retrieve(ledgers, attack_id, "solo", [(root_id, root_content)], top_k=1)
        return

    if topology == "single_child":
        child_id = f"mem-{attack_id}-mt-child-1"
        _derive(ledgers, attack_id, child_id, root_id, "follow-up")
        child_content = f"follow-up note derived from the {attack_id} poisoned memory"
        _retrieve(ledgers, attack_id, "crowded", [(root_id, root_content), (child_id, child_content)], top_k=2)
        _retrieve(ledgers, attack_id, "solo", [(root_id, root_content)], top_k=1)
        return

    if topology == "two_siblings":
        child_a, child_b = f"mem-{attack_id}-mt-sib-a", f"mem-{attack_id}-mt-sib-b"
        _derive(ledgers, attack_id, child_a, root_id, "sibling-a")
        _derive(ledgers, attack_id, child_b, root_id, "sibling-b")
        content_a = f"sibling-a note derived from the {attack_id} poisoned memory"
        content_b = f"sibling-b note derived from the {attack_id} poisoned memory"
        _retrieve(
            ledgers, attack_id, "crowded",
            [(root_id, root_content), (child_a, content_a), (child_b, content_b)], top_k=3,
        )
        _retrieve(ledgers, attack_id, "solo", [(root_id, root_content)], top_k=1)
        return

    if topology == "chain_depth_2":
        child_1, child_2 = f"mem-{attack_id}-mt-chain-1", f"mem-{attack_id}-mt-chain-2"
        _derive(ledgers, attack_id, child_1, root_id, "chain-1")
        content_1 = f"chain-1 note derived from the {attack_id} poisoned memory"
        _derive(ledgers, attack_id, child_2, child_1, "chain-2")
        content_2 = f"chain-2 note derived from the {attack_id} poisoned memory"
        _retrieve(
            ledgers, attack_id, "crowded",
            [(root_id, root_content), (child_1, content_1), (child_2, content_2)], top_k=3,
        )
        _retrieve(ledgers, attack_id, "solo", [(root_id, root_content)], top_k=1)
        return


@dataclass(frozen=True)
class AttackMultiTopologyStudyResult:
    """Real distributions (n = number of topologies actually admitted) for one
    attack, over `DOWNSTREAM_TOPOLOGIES`. `admitted_count` may be less than
    `len(topologies)` only if the attack's own live injector legitimately
    DISCARDs across repeated calls -- reported honestly, never padded."""

    attack_id: str
    topologies: Tuple[str, ...]
    admitted_count: int
    fan_out_rate: SignalDistribution
    re_entry_rate: SignalDistribution
    cycle_reinforcement_depth: SignalDistribution
    cross_task_bleed: SignalDistribution


def run_attack_multi_topology_trial(
    attack_id: str, *, storage_dir, topologies: Sequence[str] = DOWNSTREAM_TOPOLOGIES, gate_reply: Optional[str] = None,
) -> AttackMultiTopologyStudyResult:
    """Run one real live injection of `attack_id` per topology in `topologies`
    (a fresh ledger set each time, since injection is deterministic and cheap),
    build the real downstream shape, and collect the four Stage 7.4 signals into
    real per-topology distributions. `storage_dir` must be a fresh, empty
    directory."""
    if attack_id not in SEVEN_FROZEN_ATTACK_IDS:
        raise ValueError(f"unknown attack_id {attack_id!r}; must be one of {SEVEN_FROZEN_ATTACK_IDS!r}")

    fan_out_values, re_entry_values, depth_values, bleed_values = [], [], [], []
    admitted_count = 0

    for topology in topologies:
        ledgers = new_study_ledgers(
            storage_dir / topology, f"{attack_id}-{topology}",
            reason="Phase 7.5 multi-topology footprint study",
        )
        runner = _LIVE_INJECTION_RUNNERS[attack_id]
        kwargs: Dict[str, object] = dict(
            memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
            phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
            run_id=ledgers["run_id"], timestamp="2026-09-16T00:00:00+00:00",
        )
        if gate_reply is not None:
            if attack_id not in _GATE_REPLY_ATTACKS:
                raise ValueError(f"gate_reply is only accepted for {_GATE_REPLY_ATTACKS!r}, not {attack_id!r}")
            kwargs["gate_reply"] = gate_reply
        result = runner(**kwargs)

        picked = _first_admitted_memory(result, ledgers["memory_ledger"])
        if picked is None:
            continue  # legitimate DISCARD -- skip honestly, never padded into the distribution
        admitted_count += 1
        root_id, root_content = picked
        _seed_topology(ledgers, attack_id, root_id, root_content, topology)

        graph = build_propagation_graph(
            ledgers["run_id"], memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
            phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
            supersession_ledger=ledgers["supersession_ledger"],
        )
        footprint = build_propagation_footprint(
            root_id, graph=graph, event_ledger=ledgers["event_ledger"], phase5_event_ledger=ledgers["phase5_ledger"],
        )
        all_task_ids = all_retrieval_task_ids(ledgers["phase5_ledger"])

        fan_out_values.append(fan_out_rate(footprint, denominator=1.0).value)
        re_entry_values.append(re_entry_rate(footprint, all_task_ids=all_task_ids).value)
        depth_values.append(cycle_reinforcement_depth(footprint).value)
        bleed_values.append(cross_task_bleed(footprint).value)

    return AttackMultiTopologyStudyResult(
        attack_id=attack_id, topologies=tuple(topologies), admitted_count=admitted_count,
        fan_out_rate=_distribution(fan_out_values), re_entry_rate=_distribution(re_entry_values),
        cycle_reinforcement_depth=_distribution(depth_values), cross_task_bleed=_distribution(bleed_values),
    )


def run_seven_attack_multi_topology_study(
    *, storage_dir, topologies: Sequence[str] = DOWNSTREAM_TOPOLOGIES,
) -> Dict[str, AttackMultiTopologyStudyResult]:
    """One real multi-topology trial per frozen attack. `storage_dir` must be a
    fresh, empty directory."""
    return {
        attack_id: run_attack_multi_topology_trial(attack_id, storage_dir=storage_dir / attack_id, topologies=topologies)
        for attack_id in SEVEN_FROZEN_ATTACK_IDS
    }


# -- FARMA crowding parameter sweep -------------------------------------------------

_ALT_BENIGN_TEXTS_1: Tuple[str, ...] = (
    "The city council approved the new bike lane proposal.",
    "Wren repainted the garage door a dark shade of green.",
    "The community garden added three new raised beds.",
    "Omar's chess club meets every other Tuesday evening.",
    "The library extended its weekend hours starting next month.",
)
_ALT_BENIGN_TEXTS_2: Tuple[str, ...] = (
    "The bakery on Fifth Street started selling sourdough on Fridays.",
    "Talia's marathon training plan shifted to early mornings.",
    "The apartment building replaced its lobby lighting fixtures.",
    "A new coffee roaster opened near the train station.",
    "The neighborhood watch scheduled its spring cleanup day.",
)

CROWDING_PARAMETER_SWEEP: Tuple[Dict[str, object], ...] = (
    {"num_amplification_cycles": 5},
    {"num_amplification_cycles": 10},
    {"num_amplification_cycles": 15},
    {"num_amplification_cycles": 10, "benign_candidate_texts": _ALT_BENIGN_TEXTS_1},
    {"num_amplification_cycles": 10, "benign_candidate_texts": _ALT_BENIGN_TEXTS_2},
)


@dataclass(frozen=True)
class CrowdingMultiParameterStudyResult:
    """Real distributions over `CROWDING_PARAMETER_SWEEP` -- every entry is an
    independent, real FARMA injection + real retrieval, never a repeated call
    with unchanged inputs."""

    parameter_sets: Tuple[Dict[str, object], ...]
    re_entry_rate: SignalDistribution
    farma_slot_fraction: SignalDistribution


def run_farma_crowding_multi_parameter_study(
    *, storage_dir, parameter_sets: Sequence[Dict[str, object]] = CROWDING_PARAMETER_SWEEP,
) -> CrowdingMultiParameterStudyResult:
    """Run `run_farma_crowding_study()` once per real parameter combination in
    `parameter_sets`, collecting `re_entry_rate`/`farma_slot_fraction` into real
    distributions. `storage_dir` must be a fresh, empty directory."""
    re_entry_values, slot_fraction_values = [], []
    for i, params in enumerate(parameter_sets):
        result = run_farma_crowding_study(storage_dir=storage_dir / f"trial-{i}", **params)
        re_entry_values.append(result.re_entry_rate.value)
        slot_fraction_values.append(result.farma_slot_fraction)

    return CrowdingMultiParameterStudyResult(
        parameter_sets=tuple(parameter_sets),
        re_entry_rate=_distribution(re_entry_values),
        farma_slot_fraction=_distribution(slot_fraction_values),
    )


__all__ = [
    "DOWNSTREAM_TOPOLOGIES", "AttackMultiTopologyStudyResult",
    "run_attack_multi_topology_trial", "run_seven_attack_multi_topology_study",
    "CROWDING_PARAMETER_SWEEP", "CrowdingMultiParameterStudyResult",
    "run_farma_crowding_multi_parameter_study",
]
