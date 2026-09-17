"""Phase 7.3 -- tests for the benign baseline: build_benign_footprint() and
compute_benign_baseline(), exercised against a corpus with NO attack present at
all (only real record_memory_creation()/record_memory_derivation() calls),
mirroring phase5/tests' own "reconstruct from real persisted state" style.
"""

from __future__ import annotations

import math

import pytest

from phase3.evaluation.foundations.canonical import (
    CanonicalMemoryRecord,
    LIFECYCLE_CREATED,
    MEMORY_TYPE_DERIVED,
    MEMORY_TYPE_FOUNDATION,
    SOURCE_TYPE_DERIVATION_EVENT,
    SOURCE_TYPE_PHASE2_UMR,
)
from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger
from phase3.evaluation.foundations.memory_versioning import SupersessionLedger

from phase5.identity.run_identity import EventRunMembershipLedger, ExperimentRunLedger, ExperimentRunRecord
from phase5.schema.event_ledger import Phase5EventLedger
from phase5.wiring.lineage import EVIDENCE_OBSERVED_EVENT
from phase5.wiring.memory_lifecycle import record_memory_creation, record_memory_derivation
from phase5.wiring.retrieval_instrumentation import instrument_retrieval_and_selection
from phase5.wiring.trace_assembly import build_propagation_graph

from phase7.propagation.benign_baseline import benign_seed_memory_ids, compute_benign_baseline
from phase7.propagation.footprint import build_benign_footprint

TS = "2026-09-16T00:00:00+00:00"
TS2 = "2026-09-16T00:01:00+00:00"
TS3 = "2026-09-16T00:02:00+00:00"
CFG = "CFG-phase7-benign-test"


@pytest.fixture
def ledgers(tmp_path):
    memory_ledger = CanonicalMemoryLedger(tmp_path / "memory")
    event_ledger = CanonicalEventLedger(tmp_path / "events", memory_ledger)
    supersession_ledger = SupersessionLedger(tmp_path / "supersessions")
    run_ledger = ExperimentRunLedger(tmp_path / "runs")
    membership_ledger = EventRunMembershipLedger(tmp_path / "membership", run_ledger)
    phase5_ledger = Phase5EventLedger(tmp_path / "phase5_events")
    run = ExperimentRunRecord(
        experiment_id="exp-phase7-benign", run_id="RUN-phase7-benign", dataset="locomo",
        scope={}, started_at=TS, actor="test", reason="phase7 benign baseline test run",
    )
    run_ledger.register(run)
    return dict(
        memory_ledger=memory_ledger, event_ledger=event_ledger, supersession_ledger=supersession_ledger,
        membership_ledger=membership_ledger, phase5_ledger=phase5_ledger, run_id=run.run_id,
    )


def _foundation_record(memory_id, text):
    return CanonicalMemoryRecord(
        memory_id=memory_id, memory_type=MEMORY_TYPE_FOUNDATION, content={"text": text},
        source={"source_type": SOURCE_TYPE_PHASE2_UMR}, parent_ids=(),
        creation_event=f"creation-of-{memory_id}", creation_timestamp=TS, lifecycle_state=LIFECYCLE_CREATED,
    )


def _seed_benign_corpus(ledgers):
    """M0 (foundation) -> M1 derived from M0 -> M2 derived from M1 (ordinary
    consolidation chain, no attack). M-solo, M-other are independent foundation
    memories with no descendants. task-pair co-selects M0/M-other (benign
    co-retrieval); task-solo retrieves M-solo alone."""
    for memory_id, text in [("mem-m0", "m0 fact"), ("mem-solo", "solo fact"), ("mem-other", "other fact")]:
        record_memory_creation(
            memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
            membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
            record=_foundation_record(memory_id, text), actor="test", reason="seed", timestamp=TS,
        )

    m1 = CanonicalMemoryRecord(
        memory_id="mem-m1", memory_type=MEMORY_TYPE_DERIVED, content={"text": "consolidated from m0"},
        source={"source_type": SOURCE_TYPE_DERIVATION_EVENT}, parent_ids=("mem-m0",),
        creation_event="derivation-of-m1", creation_timestamp=TS2, lifecycle_state=LIFECYCLE_CREATED,
    )
    record_memory_derivation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        derived_record=m1, source_memory_ids=("mem-m0",), actor="test", reason="m1 consolidated from m0", timestamp=TS2,
    )

    m2 = CanonicalMemoryRecord(
        memory_id="mem-m2", memory_type=MEMORY_TYPE_DERIVED, content={"text": "consolidated from m1"},
        source={"source_type": SOURCE_TYPE_DERIVATION_EVENT}, parent_ids=("mem-m1",),
        creation_event="derivation-of-m2", creation_timestamp=TS3, lifecycle_state=LIFECYCLE_CREATED,
    )
    record_memory_derivation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        derived_record=m2, source_memory_ids=("mem-m1",), actor="test", reason="m2 consolidated from m1", timestamp=TS3,
    )

    instrument_retrieval_and_selection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], task_id="task-pair", query="pair query",
        candidates=[("mem-m0", "m0 fact"), ("mem-other", "other fact")],
        config_fingerprint=CFG, actor="test", timestamp=TS3, top_k=2,
    )
    instrument_retrieval_and_selection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], task_id="task-solo", query="solo query",
        candidates=[("mem-solo", "solo fact")], config_fingerprint=CFG, actor="test", timestamp=TS3, top_k=1,
    )


def _graph(ledgers):
    return build_propagation_graph(
        ledgers["run_id"], memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        supersession_ledger=ledgers["supersession_ledger"],
    )


def test_benign_seed_memory_ids_excludes_no_one_when_no_attack_present(ledgers):
    _seed_benign_corpus(ledgers)
    graph = _graph(ledgers)
    seeds = benign_seed_memory_ids(ledgers["memory_ledger"], graph)
    assert set(seeds) == {"mem-m0", "mem-m1", "mem-m2", "mem-solo", "mem-other"}


def test_build_benign_footprint_grows_via_derived_from_not_propagated_to(ledgers):
    _seed_benign_corpus(ledgers)
    graph = _graph(ledgers)
    footprint = build_benign_footprint(
        "mem-m0", graph=graph, event_ledger=ledgers["event_ledger"], phase5_event_ledger=ledgers["phase5_ledger"],
    )
    assert set(footprint.member_ids) == {"mem-m0", "mem-m1", "mem-m2"}


def test_build_benign_footprint_is_a_single_node_for_a_leaf_memory(ledgers):
    _seed_benign_corpus(ledgers)
    graph = _graph(ledgers)
    footprint = build_benign_footprint(
        "mem-solo", graph=graph, event_ledger=ledgers["event_ledger"], phase5_event_ledger=ledgers["phase5_ledger"],
    )
    assert footprint.member_ids == ("mem-solo",)


def test_compute_benign_baseline_reports_a_real_distribution_per_signal(ledgers):
    _seed_benign_corpus(ledgers)
    graph = _graph(ledgers)
    seeds = benign_seed_memory_ids(ledgers["memory_ledger"], graph)

    report = compute_benign_baseline(
        seeds, graph=graph, event_ledger=ledgers["event_ledger"], phase5_event_ledger=ledgers["phase5_ledger"],
        fan_out_denominator=1.0,
    )

    assert report.seed_memory_ids == seeds
    assert report.fan_out_rate.n == len(seeds)
    # fan_out_rate is footprint-WIDE, not per-node: mem-m0's footprint spans
    # {mem-m0, mem-m1, mem-m2}, so it counts BOTH derivation edges (mem-m1 off
    # mem-m0, mem-m2 off mem-m1) == 2.0; mem-m1's footprint spans {mem-m1,
    # mem-m2}, counting only the second == 1.0; every leaf footprint == 0.0.
    assert sorted(report.fan_out_rate.values) == [0.0, 0.0, 0.0, 1.0, 2.0]
    assert report.fan_out_rate.mean == pytest.approx(0.6)
    assert report.evidence_kinds_by_signal["fan_out_rate"] == (EVIDENCE_OBSERVED_EVENT,)

    # Real retrieval tasks exist (task-pair, task-solo) -- re_entry_rate must be
    # computed, not reported as an empty n=0 distribution.
    assert report.re_entry_rate.n == len(seeds)
    # Only mem-m0/mem-other's footprint (both single-node, task-pair co-selects
    # them) can show crowding, and cross_task_bleed's own two-source union
    # means EVERY seed touched by task-pair OR task-solo counts as bleeding
    # only once it appears in 2+ tasks.
    assert all(v in (0.0, 1.0) for v in report.re_entry_rate.values)

    assert report.cycle_reinforcement_depth.n == len(seeds)
    assert sorted(report.cycle_reinforcement_depth.values) == [0.0, 0.0, 0.0, 1.0, 2.0]

    assert report.cross_task_bleed.n == len(seeds)
    assert not any(math.isnan(v) for v in report.cross_task_bleed.values)


def test_compute_benign_baseline_rejects_empty_seed_list(ledgers):
    _seed_benign_corpus(ledgers)
    graph = _graph(ledgers)
    with pytest.raises(ValueError):
        compute_benign_baseline(
            (), graph=graph, event_ledger=ledgers["event_ledger"], phase5_event_ledger=ledgers["phase5_ledger"],
        )


def test_signal_distribution_is_nan_when_a_signal_has_no_real_denominator(ledgers):
    # No retrieval task at all in this run -- re_entry_rate must report n=0 /
    # nan, never a fabricated 0.0.
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        record=_foundation_record("mem-alone", "alone fact"), actor="test", reason="seed", timestamp=TS,
    )
    graph = _graph(ledgers)
    seeds = benign_seed_memory_ids(ledgers["memory_ledger"], graph)
    report = compute_benign_baseline(
        seeds, graph=graph, event_ledger=ledgers["event_ledger"], phase5_event_ledger=ledgers["phase5_ledger"],
    )
    assert report.re_entry_rate.n == 0
    assert math.isnan(report.re_entry_rate.mean)
    assert report.evidence_kinds_by_signal["re_entry_rate"] == ()
