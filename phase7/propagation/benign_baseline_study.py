"""Phase 7.8 (gap fix) -- Committed Benign Baseline Study.

WHY THIS MODULE EXISTS
--------------------------------------------------------------------------------
`PHASE7_REPORT.md` Sec 2 reports a specific benign-baseline table ("n=8 real
seeds: 5 roots, 3 with one derived child each") and calls the comparison built
on it "the most important honest finding in this report." That table was
originally produced by a one-off scratch script, not by anything committed
under `phase7/` -- unlike the attack study
(`attack_study.py::run_seven_attack_footprint_study()`) and the crowding study
(`crowding_study.py::run_farma_crowding_study()`), which anyone can call
directly and reproduce their own reported numbers exactly. This module closes
that gap: `run_benign_baseline_study()` builds the SAME "5 roots, 3 with a
derived child" corpus, deterministically, from real, live-instrumented ledger
calls, and runs the real `compute_benign_baseline()` (Stage 7.3, unmodified)
over it -- so the report's headline benign-baseline numbers are now backed by
code anyone can re-run and check, exactly like every other stage's numbers.

WHY THIS EXACT SHAPE (5 ROOTS, 3 WITH ONE CHILD, A CROWDED/SOLO RETRIEVAL PAIR)
--------------------------------------------------------------------------------
Structurally identical to what `attack_study.py`'s per-attack synthetic
downstream chain builds (one root, one `DERIVED_FROM` child, a crowded task
co-selecting both, a solo task retrieving the root alone) -- same
`fan_out_denominator=1.0`, same edge types, same task shape -- so the benign
baseline and the attack-study numbers are genuinely comparable, not just
superficially similar. Only 3 of the 5 roots get a derived child (a real,
disclosed mix, not uniform by fiat) so the baseline reflects that most benign
memories have no descendants at all (`build_benign_footprint()`'s own
docstring: "a footprint of size 1 is the expected common case, not an
error") alongside some real, ordinary consolidation activity.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from phase3.evaluation.foundations.canonical import (
    CanonicalMemoryRecord,
    LIFECYCLE_CREATED,
    MEMORY_TYPE_DERIVED,
    MEMORY_TYPE_FOUNDATION,
    SOURCE_TYPE_DERIVATION_EVENT,
    SOURCE_TYPE_PHASE2_UMR,
)
from phase5.wiring.memory_lifecycle import record_memory_creation, record_memory_derivation
from phase5.wiring.retrieval_instrumentation import instrument_retrieval_and_selection
from phase5.wiring.trace_assembly import build_propagation_graph

from phase7.propagation.attack_study import new_study_ledgers
from phase7.propagation.benign_baseline import BenignBaselineReport, benign_seed_memory_ids, compute_benign_baseline

TS = "2026-09-16T00:00:00+00:00"
CFG = "CFG-phase7-benign-baseline-study"

NUM_ROOTS = 5
# Every other root (indices 0, 2, 4) gets a derived child -- 3 of 5, matching
# the report's own stated "5 roots, 3 with one derived child each."
_ROOTS_WITH_CHILDREN = frozenset(i for i in range(NUM_ROOTS) if i % 2 == 0)


def _build_baseline_corpus(storage_dir) -> dict:
    ledgers = new_study_ledgers(storage_dir, "benign-baseline-study", reason="Phase 7.8 committed benign baseline study")
    for i in range(NUM_ROOTS):
        root_id = f"benign-root-{i}"
        record_memory_creation(
            memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
            membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
            record=CanonicalMemoryRecord(
                memory_id=root_id, memory_type=MEMORY_TYPE_FOUNDATION, content={"text": f"benign fact {i}"},
                source={"source_type": SOURCE_TYPE_PHASE2_UMR}, parent_ids=(),
                creation_event=f"creation-of-{root_id}", creation_timestamp=TS, lifecycle_state=LIFECYCLE_CREATED,
            ),
            actor="phase7_benign_baseline_study", reason="benign baseline root", timestamp=TS,
        )

        if i in _ROOTS_WITH_CHILDREN:
            child_id = f"benign-child-{i}"
            record_memory_derivation(
                memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
                membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
                derived_record=CanonicalMemoryRecord(
                    memory_id=child_id, memory_type=MEMORY_TYPE_DERIVED, content={"text": f"benign follow-up {i}"},
                    source={"source_type": SOURCE_TYPE_DERIVATION_EVENT}, parent_ids=(root_id,),
                    creation_event=f"derivation-of-{child_id}", creation_timestamp=TS, lifecycle_state=LIFECYCLE_CREATED,
                ),
                source_memory_ids=(root_id,), actor="phase7_benign_baseline_study",
                reason="ordinary benign consolidation", timestamp=TS,
            )
            instrument_retrieval_and_selection(
                memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
                phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
                run_id=ledgers["run_id"], task_id=f"task-benign-{i}-crowded", query="q",
                candidates=[(root_id, f"benign fact {i}"), (child_id, f"benign follow-up {i}")],
                config_fingerprint=CFG, actor="phase7_benign_baseline_study", timestamp=TS, top_k=2,
            )

        instrument_retrieval_and_selection(
            memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
            phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
            run_id=ledgers["run_id"], task_id=f"task-benign-{i}-solo", query="q",
            candidates=[(root_id, f"benign fact {i}")], config_fingerprint=CFG,
            actor="phase7_benign_baseline_study", timestamp=TS, top_k=1,
        )
    return ledgers


@dataclass(frozen=True)
class BenignBaselineStudyResult:
    """The committed, reproducible counterpart to `PHASE7_REPORT.md` Sec 2's
    benign-baseline table. `seed_memory_ids` and `baseline` come straight from
    real `benign_seed_memory_ids()`/`compute_benign_baseline()` calls -- no
    number here is hand-typed."""

    num_roots: int
    roots_with_children: Tuple[str, ...]
    seed_memory_ids: Tuple[str, ...]
    baseline: BenignBaselineReport


def run_benign_baseline_study(*, storage_dir, fan_out_denominator: float = 1.0) -> BenignBaselineStudyResult:
    """Build the committed "5 roots, 3 with one derived child each" benign
    corpus and run the real `compute_benign_baseline()` over it.
    `storage_dir` must be a fresh, empty directory. Deterministic: the corpus
    shape, content, and ids are all fixed by this function, never randomized,
    so re-running it reproduces the exact same numbers every time."""
    ledgers = _build_baseline_corpus(storage_dir)
    graph = build_propagation_graph(
        ledgers["run_id"], memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        supersession_ledger=ledgers["supersession_ledger"],
    )
    seeds = benign_seed_memory_ids(ledgers["memory_ledger"], graph)
    baseline = compute_benign_baseline(
        seeds, graph=graph, event_ledger=ledgers["event_ledger"], phase5_event_ledger=ledgers["phase5_ledger"],
        fan_out_denominator=fan_out_denominator,
    )
    return BenignBaselineStudyResult(
        num_roots=NUM_ROOTS,
        roots_with_children=tuple(sorted(f"benign-root-{i}" for i in _ROOTS_WITH_CHILDREN)),
        seed_memory_ids=seeds,
        baseline=baseline,
    )


__all__ = ["NUM_ROOTS", "BenignBaselineStudyResult", "run_benign_baseline_study"]
