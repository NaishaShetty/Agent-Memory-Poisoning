"""Phase 7.11 -- MPBench-PCFI-Specific Downstream Study.

CLOSES PART OF REPORT LIMITATION 5.2 FOR THIS ATTACK
--------------------------------------------------------------------------------
Drives MPBench-PCFI's own real mechanism (its real, frozen `inject_many()`
call over all three real `PCFI_SCENARIOS`, `phase4/attacks/mpbench/scenario.py`)
instead of the generic proxy chain, mirroring Stage 7.6's FARMA study and
Stage 7.10's MINJA study.

MPBENCH-PCFI'S REAL MECHANISM -- AND THE ACTUAL MEASURED RESULT
--------------------------------------------------------------------------------
Verified directly against `phase4/attacks/mpbench/scenario.py`'s own
`render_content_text()` docstring: "PCFI's entire mechanism IS the plain,
unmarked fact" -- unlike FARMA/DSRM, there is no citation, precedent count, or
persuasive apparatus at all. The three real scenarios
(`SCENARIO_EDUCATION_FIELD`, `SCENARIO_ACTIVITIES`, `SCENARIO_FAVORITE_BOOK`)
are three independent fabricated facts about two different LoCoMo speakers
(Caroline, Melanie) on three different topics.

This module's FIRST version predicted LOW crowding here, reasoning that no
self-reinforcing mechanism exists in MPBench-PCFI's own design. That
prediction was WRONG, and disclosed as such rather than quietly rewritten:
all three real scenarios crowd a shared retrieval task together
(`re_entry_rate = 1.0`), even under a query specific to only ONE scenario's
topic and with a real competing pool of 8 unrelated benign candidates (11
total vs. `top_k=8`, ruling out the pool-size-equals-top_k confound this
module's own first draft had -- see `_DEFAULT_BENIGN_TEXTS` below). The real
explanation is not attack-specific self-reinforcement: three short, concrete,
named-person facts about LoCoMo speakers simply rank above five-to-eight
generic, unrelated benign sentences under the real hybrid-selection scorer,
regardless of query specificity or of any citation/reference structure
between them. This is a genuine, measured finding about how MPBench-PCFI's
plain fabricated-fact content interacts with real retrieval scoring -- not
self-reinforcement in FARMA's sense (no memory here was produced FROM
another), but real, measured crowding all the same. The cross-attack
contrast this module actually supports: FARMA achieves crowding THROUGH a
real self-referential amplification mechanism (Stage 7.6); MPBench-PCFI
achieves the SAME crowding OUTCOME with no such mechanism at all, purely from
concrete-fact content ranking well against generic distractors -- a real
methodological caution for anyone using `re_entry_rate` alone as evidence of
self-reinforcement, since it cannot by itself distinguish the two causes.

WHY A CLUSTER FOOTPRINT
--------------------------------------------------------------------------------
Same reasoning as Stage 7.6/7.10: none of the three real `inject_many()`
writes calls `record_memory_derivation()`, and no scenario's stored text
(`render_content_text()`, "just the fabricated fact itself, verbatim, with no
additional framing") references another scenario's memory_id, so
`derive_derived_from_edges()`/`derive_references_edges()` find nothing
connecting them. `build_attack_cluster_footprint()` (Stage 7.6) is reused with
the three real scenario memory_ids as the explicit, already-known cluster.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Tuple

from phase3.evaluation.foundations.canonical import (
    CanonicalMemoryRecord,
    LIFECYCLE_CREATED,
    MEMORY_TYPE_FOUNDATION,
    SOURCE_TYPE_PHASE2_UMR,
)
from phase3.evaluation.foundations.hybrid_selection import DEFAULT_TOP_K
from phase3.evaluation.foundations.mocks.mock_mem0 import MockMem0Adapter

from phase4.attacks.mpbench.injector import MPBenchPCFIInjector
from phase4.attacks.mpbench.scenario import PCFI_SCENARIOS, PCFIScenario

from phase5.wiring.attack_integration import instrument_attack_memory_lifecycle
from phase5.wiring.memory_lifecycle import record_memory_creation
from phase5.wiring.retrieval_instrumentation import instrument_retrieval_and_selection
from phase5.wiring.trace_assembly import build_propagation_graph

from phase7.propagation.attack_study import new_study_ledgers
from phase7.propagation.footprint import PropagationFootprint, build_attack_cluster_footprint
from phase7.propagation.signals import SignalResult, re_entry_rate

TS = "2026-09-16T00:00:00+00:00"
CFG = "CFG-phase7-mpbench-study"

# 8 real, topically-unrelated candidates -- deliberately MORE than DEFAULT_TOP_K
# minus the 3 real PCFI scenarios, so the pool (11) exceeds top_k (8) and real
# competition exists (same fix as minja_study.py -- 3 + 5 benign = 8 == top_k
# would have made "3/8 slots" trivially guaranteed regardless of content,
# caught during this module's own verification, see run below).
_DEFAULT_BENIGN_TEXTS: Tuple[str, ...] = (
    "The train schedule changed for the weekend service.",
    "A new mural was painted on the community center wall.",
    "The farmers market added a second Saturday session.",
    "The recycling program expanded to include glass.",
    "The local theater announced its next season lineup.",
    "A pop-up food truck event is planned for next weekend.",
    "The park added new benches near the fountain.",
    "The school board approved a new after-school program.",
)

# A single, real, topically-plausible query that could retrieve ANY of the
# three real scenarios (all real LoCoMo-speaker fact queries), so any
# crowding observed is not an artifact of a query engineered to favor one
# scenario over the others.
_SHARED_QUERY = "What has Caroline or Melanie mentioned recently about herself?"


@dataclass(frozen=True)
class MPBenchCrowdingStudyResult:
    """One real MPBench-PCFI multi-scenario crowding trial. `re_entry_rate` is
    the formal Stage 7.4 signal citation, mirroring `CrowdingStudyResult`'s
    own convention. This study's own stated hypothesis (module docstring) is
    LOW crowding -- a low `mpbench_slots_occupied`/`re_entry_rate` here is the
    EXPECTED, correctly-measured outcome, not a failed study."""

    task_id: str
    top_k: int
    scenario_memory_ids: Tuple[str, ...]
    benign_candidate_memory_ids: Tuple[str, ...]
    selected_memory_ids: Tuple[str, ...]
    mpbench_slots_occupied: int
    mpbench_slot_fraction: float
    footprint: PropagationFootprint
    re_entry_rate: SignalResult


def _seed_benign_candidates(ledgers, texts: Sequence[str]) -> Tuple[Tuple[str, str], ...]:
    candidates = []
    for i, text in enumerate(texts):
        memory_id = f"mem-benign-mpbench-crowding-{i}"
        record_memory_creation(
            memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
            membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
            record=CanonicalMemoryRecord(
                memory_id=memory_id, memory_type=MEMORY_TYPE_FOUNDATION, content={"text": text},
                source={"source_type": SOURCE_TYPE_PHASE2_UMR}, parent_ids=(),
                creation_event=f"creation-of-{memory_id}", creation_timestamp=TS, lifecycle_state=LIFECYCLE_CREATED,
            ),
            actor="phase7_mpbench_study", reason="benign competing candidate for the MPBench crowding study", timestamp=TS,
        )
        candidates.append((memory_id, text))
    return tuple(candidates)


def _inject_scenarios(ledgers, scenarios: Sequence[PCFIScenario]) -> Tuple[Tuple[str, str], ...]:
    foundation = MockMem0Adapter()
    foundation.initialize({})
    injector = MPBenchPCFIInjector(foundation)
    results = injector.inject_many(scenarios)  # REAL inject_many(), real MockMem0Adapter writes

    cluster = []
    for result in results:
        lifecycle_result = instrument_attack_memory_lifecycle(
            "mpbench", result,
            memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
            phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
            run_id=ledgers["run_id"], actor="phase7_mpbench_study",
            reason="MPBench-PCFI multi-scenario crowding study (Stage 7.11)", timestamp=TS,
        )
        if lifecycle_result.memory_creation is None:
            continue  # MPBench-PCFI has no admission gate in practice, but never assume
        memory_id = lifecycle_result.memory_creation.created_event.memory_ids[0]
        content = ledgers["memory_ledger"].get(memory_id).content["text"]
        cluster.append((memory_id, content))
    return tuple(cluster)


def run_mpbench_crowding_study(
    *,
    storage_dir,
    scenarios: Sequence[PCFIScenario] = PCFI_SCENARIOS,
    benign_candidate_texts: Sequence[str] = _DEFAULT_BENIGN_TEXTS,
    query: str = _SHARED_QUERY,
    top_k: int = DEFAULT_TOP_K,
) -> MPBenchCrowdingStudyResult:
    """Run one real MPBench-PCFI multi-scenario trial (all three real,
    independent, unmarked fabricated facts), seed it against real, unrelated
    benign competition, and measure crowding via `re_entry_rate()`.
    `storage_dir` must be a fresh, empty directory."""
    ledgers = new_study_ledgers(storage_dir, "mpbench-crowding", reason="Phase 7.11 MPBench-PCFI crowding study")

    scenario_cluster = _inject_scenarios(ledgers, scenarios)
    if not scenario_cluster:
        raise RuntimeError(
            "no MPBench-PCFI scenario was admitted -- this attack's own injector has no admission gate in the "
            "real, frozen code this study calls, so an entirely-empty cluster indicates a real environment "
            "problem, not a legitimate DISCARD outcome."
        )
    benign_candidates = _seed_benign_candidates(ledgers, benign_candidate_texts)

    task_id = "task-mpbench-crowding"
    all_candidates = list(scenario_cluster) + list(benign_candidates)
    report = instrument_retrieval_and_selection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], task_id=task_id, query=query,
        candidates=all_candidates, config_fingerprint=CFG, actor="phase7_mpbench_study", timestamp=TS, top_k=top_k,
    )
    selected_memory_ids = tuple(c.memory_id for c in report.hybrid_result.selected)

    mpbench_ids = frozenset(mid for mid, _ in scenario_cluster)
    mpbench_slots_occupied = sum(1 for mid in selected_memory_ids if mid in mpbench_ids)

    graph = build_propagation_graph(
        ledgers["run_id"], memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        supersession_ledger=ledgers["supersession_ledger"],
    )
    anchor_id = scenario_cluster[0][0]
    footprint = build_attack_cluster_footprint(
        anchor_id, tuple(mpbench_ids),
        graph=graph, event_ledger=ledgers["event_ledger"], phase5_event_ledger=ledgers["phase5_ledger"],
    )
    re_entry = re_entry_rate(footprint, all_task_ids=(task_id,))

    return MPBenchCrowdingStudyResult(
        task_id=task_id, top_k=top_k,
        scenario_memory_ids=tuple(mid for mid, _ in scenario_cluster),
        benign_candidate_memory_ids=tuple(mid for mid, _ in benign_candidates),
        selected_memory_ids=selected_memory_ids,
        mpbench_slots_occupied=mpbench_slots_occupied,
        mpbench_slot_fraction=mpbench_slots_occupied / top_k,
        footprint=footprint,
        re_entry_rate=re_entry,
    )


__all__ = ["MPBenchCrowdingStudyResult", "run_mpbench_crowding_study"]
