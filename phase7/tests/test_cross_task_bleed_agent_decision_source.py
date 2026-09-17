"""Phase 7 -- verifies Report Limitation 5.4's own disclosed boundary is
accurate, rather than leaving it unchecked: `cross_task_bleed()` claims two
real sources of task-membership ((a) any edge carrying a task_id, (b)
`retrieval_task_ids`'s solo-retrieval group query) and explicitly does NOT
claim a third. This test proves source (a) already covers a real, existing
case that could easily be mistaken for the "missing third source" -- a task
whose ONLY real event is a real `agent_decision` (`exposed_memory_ids`),
with NO `retrieval_candidate_scored` event at all for that task. Per
`derive_exposed_to_decision_edges()` (`phase5/wiring/lineage.py`), this
produces a real USED_BY/EXPOSURE_ONLY edge that DOES carry a resolved
task_id -- so `cross_task_bleed` sees this task via source (a), and the
limitation's own claim ("no such path exists today... would be invisible to
it") remains correctly scoped: it is about a task with NEITHER a scored
retrieval NOR any other real edge at all, which genuinely cannot exist in
the frozen Stage 5.5 wiring (every real agent_decision carries a task_id and
produces a real edge once exposed_memory_ids is non-empty).
"""

from __future__ import annotations

import pytest

from phase3.evaluation.foundations.canonical import (
    CanonicalMemoryRecord,
    LIFECYCLE_CREATED,
    MEMORY_TYPE_FOUNDATION,
    SOURCE_TYPE_PHASE2_UMR,
)
from phase5.wiring.agent_decision_instrumentation import record_agent_decision
from phase5.wiring.memory_lifecycle import record_memory_creation
from phase5.wiring.trace_assembly import build_propagation_graph

from phase7.propagation.attack_study import new_study_ledgers
from phase7.propagation.footprint import build_benign_footprint
from phase7.propagation.signals import cross_task_bleed

TS = "2026-09-16T00:00:00+00:00"


def _create_memory(ledgers, memory_id: str, text: str) -> None:
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        record=CanonicalMemoryRecord(
            memory_id=memory_id, memory_type=MEMORY_TYPE_FOUNDATION, content={"text": text},
            source={"source_type": SOURCE_TYPE_PHASE2_UMR}, parent_ids=(),
            creation_event=f"creation-of-{memory_id}", creation_timestamp=TS, lifecycle_state=LIFECYCLE_CREATED,
        ),
        actor="phase7_test", reason="verifying cross_task_bleed's real AGENT_DECISION source", timestamp=TS,
    )


def test_a_task_with_only_an_agent_decision_event_is_still_seen_by_cross_task_bleed(tmp_path):
    ledgers = new_study_ledgers(tmp_path, "decision-only-task")
    _create_memory(ledgers, "mem-solo", "a real benign memory, never retrieval-scored")

    # A real agent_decision event, with NO retrieval_candidate_scored event at all
    # for this task -- the exact scenario Limitation 5.4 worries a "third source"
    # might be needed for.
    record_agent_decision(
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], task_id="task-decision-only", decision_id="decision-1",
        exposed_memory_ids=("mem-solo",), output="a real generated answer", finish_reason="generated",
        model_identity="{}", config_fingerprint="CFG-test", used_memories_observability="NOT_OBSERVABLE",
        actor="phase7_test", reason="real decision exposing mem-solo, no retrieval event", timestamp=TS,
    )

    graph = build_propagation_graph(
        ledgers["run_id"], memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        supersession_ledger=ledgers["supersession_ledger"],
    )
    footprint = build_benign_footprint(
        "mem-solo", graph=graph, event_ledger=ledgers["event_ledger"], phase5_event_ledger=ledgers["phase5_ledger"],
    )
    bleed = cross_task_bleed(footprint)

    # Proves source (a) -- "every edge-carried task_id" -- already sees this task via
    # the real USED_BY/EXPOSURE_ONLY edge derive_exposed_to_decision_edges() produces,
    # confirming Limitation 5.4's own disclosed boundary is accurate as written.
    assert bleed.detail["distinct_task_ids"] == ("task-decision-only",)
    assert bleed.value == pytest.approx(1.0)
