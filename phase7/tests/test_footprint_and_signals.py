"""Phase 7.2/7.4 -- tests for propagation footprint construction and the four
propagation-shape signals, exercised against the real Stage 5.4-5.8 pipeline
(live attack injection through PropagationGraph composition), mirroring
`phase5/tests/test_lineage.py` and `phase5/tests/test_trace_assembly.py`'s own
"reconstruct from real persisted state, not hand-crafted fixtures alone" style.
"""

from __future__ import annotations

import pytest

from phase3.evaluation.foundations.canonical import (
    CanonicalMemoryRecord,
    LIFECYCLE_CREATED,
    MEMORY_TYPE_DERIVED,
    SOURCE_TYPE_DERIVATION_EVENT,
)
from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger
from phase3.evaluation.foundations.memory_versioning import SupersessionLedger

from phase5.identity.run_identity import EventRunMembershipLedger, ExperimentRunLedger, ExperimentRunRecord
from phase5.schema.event_ledger import Phase5EventLedger
from phase5.wiring.lineage import DERIVED_FROM, EVIDENCE_LINEAGE_REACHABILITY, EVIDENCE_OBSERVED_EVENT, PROPAGATED_TO, SELECTED_WITH
from phase5.wiring.live_attack_runs import run_live_farma_injection
from phase5.wiring.memory_lifecycle import record_memory_derivation
from phase5.wiring.retrieval_instrumentation import instrument_retrieval_and_selection
from phase5.wiring.trace_assembly import build_propagation_graph

from phase7.propagation.footprint import build_benign_footprint, build_propagation_footprint, footprint_growth
from phase7.propagation.signals import cross_task_bleed, cycle_reinforcement_depth, fan_out_rate, re_entry_rate

TS = "2026-09-16T00:00:00+00:00"
TS2 = "2026-09-16T00:01:00+00:00"
TS3 = "2026-09-16T00:02:00+00:00"
CFG = "CFG-phase7-test"


@pytest.fixture
def ledgers(tmp_path):
    memory_ledger = CanonicalMemoryLedger(tmp_path / "memory")
    event_ledger = CanonicalEventLedger(tmp_path / "events", memory_ledger)
    supersession_ledger = SupersessionLedger(tmp_path / "supersessions")
    run_ledger = ExperimentRunLedger(tmp_path / "runs")
    membership_ledger = EventRunMembershipLedger(tmp_path / "membership", run_ledger)
    phase5_ledger = Phase5EventLedger(tmp_path / "phase5_events")
    run = ExperimentRunRecord(
        experiment_id="exp-phase7", run_id="RUN-phase7", dataset="locomo",
        scope={"attack_id": "farma"}, started_at=TS, actor="test", reason="phase7 footprint test run",
    )
    run_ledger.register(run)
    return dict(
        memory_ledger=memory_ledger, event_ledger=event_ledger, supersession_ledger=supersession_ledger,
        membership_ledger=membership_ledger, phase5_ledger=phase5_ledger, run_id=run.run_id,
    )


def _build_footprint(ledgers, root_memory_id):
    graph = build_propagation_graph(
        ledgers["run_id"], memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        supersession_ledger=ledgers["supersession_ledger"],
    )
    return build_propagation_footprint(
        root_memory_id, graph=graph, event_ledger=ledgers["event_ledger"], phase5_event_ledger=ledgers["phase5_ledger"],
    )


def _seed_chain_and_crowding(ledgers):
    """Root poisoned memory M0 (real FARMA injection) -> M1 derived from M0 ->
    M2 derived from M1 (a 2-hop DERIVED_FROM chain), then two retrieval tasks:
    task-crowded selects M0 and M1 together (crowding), task-clean selects only
    an unrelated candidate M0 alone is never paired with M2 anywhere."""
    injection_result = run_live_farma_injection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], timestamp=TS,
    )
    m0 = injection_result.memory_creation.created_event.memory_ids[0]
    m0_content = ledgers["memory_ledger"].get(m0).content["text"]

    m1_record = CanonicalMemoryRecord(
        memory_id="mem-m1", memory_type=MEMORY_TYPE_DERIVED, content={"text": "derived from poison M0"},
        source={"source_type": SOURCE_TYPE_DERIVATION_EVENT}, parent_ids=(m0,),
        creation_event="derivation-of-m1", creation_timestamp=TS2, lifecycle_state=LIFECYCLE_CREATED,
    )
    record_memory_derivation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        derived_record=m1_record, source_memory_ids=(m0,), actor="test", reason="m1 derived from m0", timestamp=TS2,
    )

    m2_record = CanonicalMemoryRecord(
        memory_id="mem-m2", memory_type=MEMORY_TYPE_DERIVED, content={"text": "derived from mem-m1"},
        source={"source_type": SOURCE_TYPE_DERIVATION_EVENT}, parent_ids=("mem-m1",),
        creation_event="derivation-of-m2", creation_timestamp=TS3, lifecycle_state=LIFECYCLE_CREATED,
    )
    record_memory_derivation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        derived_record=m2_record, source_memory_ids=("mem-m1",), actor="test", reason="m2 derived from m1", timestamp=TS3,
    )

    instrument_retrieval_and_selection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], task_id="task-crowded", query="crowded query",
        candidates=[(m0, m0_content), ("mem-m1", "derived from poison M0")],
        config_fingerprint=CFG, actor="test", timestamp=TS3, top_k=2,
    )
    instrument_retrieval_and_selection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], task_id="task-clean", query="unrelated query",
        candidates=[(m0, m0_content)], config_fingerprint=CFG, actor="test", timestamp=TS3, top_k=1,
    )
    return m0


def test_footprint_member_ids_are_the_lineage_reachable_descendants(ledgers):
    m0 = _seed_chain_and_crowding(ledgers)
    footprint = _build_footprint(ledgers, m0)
    assert set(footprint.member_ids) == {m0, "mem-m1", "mem-m2"}


def test_footprint_edges_carry_real_evidence_kinds_and_are_time_sorted(ledgers):
    m0 = _seed_chain_and_crowding(ledgers)
    footprint = _build_footprint(ledgers, m0)

    propagated = footprint.edges_of_type(PROPAGATED_TO)
    assert propagated
    assert all(fe.edge.evidence_kind == EVIDENCE_LINEAGE_REACHABILITY for fe in propagated)

    derived_from = footprint.edges_of_type(DERIVED_FROM)
    assert {(fe.edge.source_id, fe.edge.target_id) for fe in derived_from} == {("mem-m1", m0), ("mem-m2", "mem-m1")}
    assert all(fe.edge.evidence_kind == EVIDENCE_OBSERVED_EVENT for fe in derived_from)

    timestamps = [fe.established_at for fe in footprint.edges]
    assert timestamps == sorted(timestamps)


def test_footprint_growth_is_non_decreasing_and_reaches_full_membership(ledgers):
    m0 = _seed_chain_and_crowding(ledgers)
    footprint = _build_footprint(ledgers, m0)
    growth = footprint_growth(footprint)
    counts = [c for _, c in growth]
    assert counts == sorted(counts)
    assert counts[-1] >= 3


def test_fan_out_rate_counts_derivations_off_footprint_members(ledgers):
    m0 = _seed_chain_and_crowding(ledgers)
    footprint = _build_footprint(ledgers, m0)
    result = fan_out_rate(footprint, denominator=2.0)
    assert result.detail["originating_edge_count"] == 2  # mem-m1 off m0, mem-m2 off mem-m1
    assert result.value == pytest.approx(1.0)
    assert result.evidence_kinds == (EVIDENCE_OBSERVED_EVENT,)


def test_fan_out_rate_rejects_nonpositive_denominator(ledgers):
    m0 = _seed_chain_and_crowding(ledgers)
    footprint = _build_footprint(ledgers, m0)
    with pytest.raises(ValueError):
        fan_out_rate(footprint, denominator=0.0)


def test_re_entry_rate_flags_only_the_crowded_task(ledgers):
    m0 = _seed_chain_and_crowding(ledgers)
    footprint = _build_footprint(ledgers, m0)
    result = re_entry_rate(footprint, all_task_ids=("task-crowded", "task-clean"))
    assert result.detail["crowded_task_ids"] == ("task-crowded",)
    assert result.value == pytest.approx(0.5)
    assert result.evidence_kinds == (EVIDENCE_OBSERVED_EVENT,)

    selected_with = footprint.edges_of_type(SELECTED_WITH)
    assert any(fe.task_id == "task-crowded" for fe in selected_with)


def test_re_entry_rate_requires_a_real_task_universe(ledgers):
    m0 = _seed_chain_and_crowding(ledgers)
    footprint = _build_footprint(ledgers, m0)
    with pytest.raises(ValueError):
        re_entry_rate(footprint, all_task_ids=())


def test_cycle_reinforcement_depth_measures_the_two_hop_chain(ledgers):
    m0 = _seed_chain_and_crowding(ledgers)
    footprint = _build_footprint(ledgers, m0)
    result = cycle_reinforcement_depth(footprint)
    assert result.value == 2.0
    assert result.detail["longest_chain"] == ("mem-m2", "mem-m1", m0)
    assert result.evidence_kinds == (EVIDENCE_OBSERVED_EVENT,)


def test_cycle_reinforcement_depth_is_zero_for_a_root_with_no_derived_children(ledgers):
    injection_result = run_live_farma_injection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], timestamp=TS,
    )
    m0 = injection_result.memory_creation.created_event.memory_ids[0]
    footprint = _build_footprint(ledgers, m0)
    result = cycle_reinforcement_depth(footprint)
    assert result.value == 0.0
    assert result.detail["longest_chain"] == (m0,)
    assert result.evidence_kinds == ()


def test_cross_task_bleed_also_counts_a_solo_retrieval_task(ledgers):
    # task-clean retrieves m0 alone -- a single-candidate retrieval produces no
    # pairwise RETRIEVED_WITH/SELECTED_WITH edge, so it carries no edge-derived
    # task_id, but it DOES show up via query_co_retrieved_memory_ids() and so
    # must still be counted (the fix for the previously-disclosed undercount).
    m0 = _seed_chain_and_crowding(ledgers)
    footprint = _build_footprint(ledgers, m0)
    assert footprint.retrieval_task_ids == ("task-clean", "task-crowded")

    result = cross_task_bleed(footprint)
    assert result.detail["distinct_task_ids"] == ("task-clean", "task-crowded")
    assert result.detail["retrieval_only_task_ids"] == ("task-clean",)
    assert result.detail["bleeds_across_tasks"] is True
    assert result.value == 2.0


def test_fan_out_rate_never_counts_produced_edges(ledgers):
    # Regression: a PRODUCED edge's source_id is always an injection_id, never
    # a memory_id, so it can never originate FROM a footprint member -- that
    # clause used to be silently dead code. m0's footprint has exactly one
    # PRODUCED edge touching it (the injection that created m0 itself), which
    # must contribute nothing to fan_out_rate's count.
    m0 = _seed_chain_and_crowding(ledgers)
    footprint = _build_footprint(ledgers, m0)
    from phase5.wiring.lineage import PRODUCED
    produced_edges = footprint.edges_of_type(PRODUCED)
    assert len(produced_edges) == 1  # the injection that created m0

    result = fan_out_rate(footprint, denominator=1.0)
    assert result.detail["originating_edge_count"] == 2  # only the two DERIVED_FROM hops


def test_build_propagation_footprint_rejects_a_non_attack_root(ledgers):
    # Regression: calling this on mem-m1 (a real descendant of the attack, but
    # not itself a PRODUCED target) used to silently return a misleading
    # single-node footprint instead of raising.
    _seed_chain_and_crowding(ledgers)
    graph = build_propagation_graph(
        ledgers["run_id"], memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        supersession_ledger=ledgers["supersession_ledger"],
    )
    with pytest.raises(ValueError, match="not a PRODUCED target"):
        build_propagation_footprint(
            "mem-m1", graph=graph, event_ledger=ledgers["event_ledger"], phase5_event_ledger=ledgers["phase5_ledger"],
        )


def test_footprint_edge_ordering_uses_real_chronological_time_not_lexicographic_strings(ledgers):
    # Regression: two real, validly-formatted timestamps at different UTC
    # offsets can sort BACKWARDS under plain string comparison even though one
    # is genuinely later. m1's derivation timestamp below is chronologically
    # AFTER m0's creation timestamp (04:00 UTC vs 00:00 UTC) but its raw string
    # ("2026-09-15T20:00:00-08:00") sorts BEFORE m0's string
    # ("2026-09-16T00:00:00+00:00") lexicographically (because "09-15" <
    # "09-16"). A footprint built with a naive string sort would place m1's
    # DERIVED_FROM edge before m0's PRODUCED edge -- backwards.
    injection_result = run_live_farma_injection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], timestamp=TS,
    )
    m0 = injection_result.memory_creation.created_event.memory_ids[0]
    later_but_lexicographically_smaller_ts = "2026-09-15T20:00:00-08:00"  # = 2026-09-16T04:00:00 UTC

    m1_record = CanonicalMemoryRecord(
        memory_id="mem-m1", memory_type=MEMORY_TYPE_DERIVED, content={"text": "derived from poison M0"},
        source={"source_type": SOURCE_TYPE_DERIVATION_EVENT}, parent_ids=(m0,),
        creation_event="derivation-of-m1", creation_timestamp=later_but_lexicographically_smaller_ts,
        lifecycle_state=LIFECYCLE_CREATED,
    )
    record_memory_derivation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        derived_record=m1_record, source_memory_ids=(m0,), actor="test", reason="m1 derived from m0",
        timestamp=later_but_lexicographically_smaller_ts,
    )

    footprint = _build_footprint(ledgers, m0)
    relationship_order = [fe.edge.relationship_type for fe in footprint.edges]
    assert relationship_order.index("PRODUCED") < relationship_order.index(DERIVED_FROM)

    raw_strings = [fe.established_at for fe in footprint.edges]
    assert raw_strings != sorted(raw_strings), (
        "this fixture is only a meaningful regression test if plain string-sorting "
        "the same timestamps would have produced a DIFFERENT (wrong) order"
    )


def test_build_benign_footprint_refuses_an_attack_produced_seed(ledgers):
    # Regression: calling build_benign_footprint() on a real attack-produced or
    # attack-tainted memory used to silently pollute the benign baseline.
    m0 = _seed_chain_and_crowding(ledgers)
    graph = build_propagation_graph(
        ledgers["run_id"], memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        supersession_ledger=ledgers["supersession_ledger"],
    )
    with pytest.raises(ValueError, match="attack-produced or attack-tainted"):
        build_benign_footprint(
            m0, graph=graph, event_ledger=ledgers["event_ledger"], phase5_event_ledger=ledgers["phase5_ledger"],
        )
    with pytest.raises(ValueError, match="attack-produced or attack-tainted"):
        build_benign_footprint(
            "mem-m2", graph=graph, event_ledger=ledgers["event_ledger"], phase5_event_ledger=ledgers["phase5_ledger"],
        )
