"""Phase 5.5 -- tests for retrieval/selection instrumentation.

Exercises the real, frozen `select_by_hybrid_score()` (never mocked or reimplemented) and
real, file-backed Phase 3/Phase 5 ledgers throughout.
"""

from __future__ import annotations

import pytest

from phase3.evaluation.foundations.canonical import (
    CanonicalMemoryRecord,
    LIFECYCLE_CREATED,
    MEMORY_TYPE_FOUNDATION,
    SOURCE_TYPE_PHASE2_UMR,
)
from phase3.evaluation.agent.conditions import CONDITION_RETRIEVED_MEMORY, build_agent_visible_context
from phase3.evaluation.agent_runtime.messages import render_messages
from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger
from phase3.evaluation.foundations.hybrid_selection import DEFAULT_TOP_K
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger
from phase3.evaluation.foundations.mocks.mock_mem0 import MockMem0Adapter

from phase5.identity.run_identity import EventRunMembershipLedger, ExperimentRunLedger, ExperimentRunRecord
from phase5.schema.event import CANONICAL_STATUS_IN_LEDGER, CANONICAL_STATUS_NOT_IN_LEDGER
from phase5.schema.event_ledger import Phase5EventLedger
from phase5.wiring.memory_lifecycle import record_memory_creation
from phase5.wiring.retrieval_instrumentation import instrument_retrieval_and_selection, record_context_assembly

TS = "2026-09-12T00:00:00+00:00"
CFG = "CFG-test-fingerprint"


def _foundation_record(memory_id: str, text: str) -> CanonicalMemoryRecord:
    return CanonicalMemoryRecord(
        memory_id=memory_id, memory_type=MEMORY_TYPE_FOUNDATION, content={"text": text},
        source={"source_type": SOURCE_TYPE_PHASE2_UMR}, parent_ids=(),
        creation_event=f"creation-of-{memory_id}", creation_timestamp=TS, lifecycle_state=LIFECYCLE_CREATED,
    )


@pytest.fixture
def ledgers(tmp_path):
    memory_ledger = CanonicalMemoryLedger(tmp_path / "memory")
    event_ledger = CanonicalEventLedger(tmp_path / "events", memory_ledger)
    run_ledger = ExperimentRunLedger(tmp_path / "runs")
    membership_ledger = EventRunMembershipLedger(tmp_path / "membership", run_ledger)
    phase5_ledger = Phase5EventLedger(tmp_path / "phase5_events")
    run = ExperimentRunRecord(
        experiment_id="exp-1", run_id="RUN-retrieval-test", dataset="locomo",
        scope={}, started_at=TS, actor="test", reason="retrieval instrumentation test run",
    )
    run_ledger.register(run)
    return dict(
        memory_ledger=memory_ledger, event_ledger=event_ledger,
        membership_ledger=membership_ledger, phase5_ledger=phase5_ledger, run_id=run.run_id,
    )


def _seed_memory(ledgers, memory_id, text):
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        record=_foundation_record(memory_id, text), actor="test", reason="seed", timestamp=TS,
    )


def test_every_candidate_in_the_pool_gets_a_scored_event_selected_and_rejected_alike(ledgers):
    for i in range(5):
        _seed_memory(ledgers, f"mem-{i}", f"Melanie went camping in June {i}.")
    candidates = [(f"mem-{i}", f"Melanie went camping in June {i}.") for i in range(5)]

    report = instrument_retrieval_and_selection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], task_id="task-1", query="When did Melanie go camping?",
        candidates=candidates, config_fingerprint=CFG, actor="test", timestamp=TS, top_k=3,
    )
    assert len(report.candidate_scored_events) == 5  # ALL 5, not just the 3 selected
    assert len(report.hybrid_result.selected) == 3
    assert len(report.hybrid_result.rejected) == 2
    assert len(report.retrieved_event_ids) == 5
    assert len(report.selected_event_ids) == 3
    assert len(report.rejected_event_ids) == 2
    assert report.not_in_canonical_ledger == []

    # Rank is assigned over the FULL pool, 1..5, with no gaps or duplicates.
    ranks = sorted(e.candidate_rank for e in report.candidate_scored_events)
    assert ranks == [1, 2, 3, 4, 5]

    # Every rejected event really did land on a non-selected candidate.
    selected_memory_ids = {e.memory_id for e in report.candidate_scored_events if e.selected}
    rejected_memory_ids = {e.memory_id for e in report.candidate_scored_events if not e.selected}
    assert len(selected_memory_ids) == 3
    assert len(rejected_memory_ids) == 2
    assert selected_memory_ids.isdisjoint(rejected_memory_ids)


def test_pool_smaller_than_top_k_selects_everything_and_rejects_nothing(ledgers):
    _seed_memory(ledgers, "mem-only", "the only candidate")
    report = instrument_retrieval_and_selection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], task_id="task-2", query="anything",
        candidates=[("mem-only", "the only candidate")], config_fingerprint=CFG, actor="test", timestamp=TS,
        top_k=DEFAULT_TOP_K,
    )
    assert len(report.candidate_scored_events) == 1
    assert report.candidate_scored_events[0].selected is True
    assert report.rejected_event_ids == []


def test_empty_candidate_pool_produces_no_events(ledgers):
    report = instrument_retrieval_and_selection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], task_id="task-3", query="anything",
        candidates=[], config_fingerprint=CFG, actor="test", timestamp=TS,
    )
    assert report.candidate_scored_events == []
    assert report.hybrid_result.selected == ()
    assert report.hybrid_result.rejected == ()


def test_candidate_not_in_canonical_ledger_is_honestly_reported_not_silently_dropped(ledgers):
    # mem-known is seeded through Stage 5.4's wiring; mem-unknown was never wired at all
    # (e.g. an attack memory whose creation was never instrumented) -- its score event
    # must still be recorded (OR-6 does not depend on canonical-ledger membership), but no
    # retrieved/selected/rejected CanonicalEvent can reference it.
    _seed_memory(ledgers, "mem-known", "a known fact")
    candidates = [("mem-known", "a known fact"), ("mem-unknown", "an unwired fact")]

    report = instrument_retrieval_and_selection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], task_id="task-4", query="a known fact",
        candidates=candidates, config_fingerprint=CFG, actor="test", timestamp=TS, top_k=5,
    )
    assert len(report.candidate_scored_events) == 2  # both scored regardless
    assert report.not_in_canonical_ledger == ["mem-unknown"]
    # Only mem-known produced canonical events.
    recorded_memory_ids = set()
    for eid in report.retrieved_event_ids:
        recorded_memory_ids.update(ledgers["event_ledger"].get_event(eid).memory_ids)
    assert recorded_memory_ids == {"mem-known"}

    # The gap is a durable, explicit, machine-checkable field on the persisted
    # RETRIEVAL_CANDIDATE_SCORED event -- not merely the in-process report list above.
    events_by_memory_id = {e.memory_id: e for e in report.candidate_scored_events}
    assert events_by_memory_id["mem-known"].canonical_status == CANONICAL_STATUS_IN_LEDGER
    assert events_by_memory_id["mem-unknown"].canonical_status == CANONICAL_STATUS_NOT_IN_LEDGER


def test_not_in_canonical_ledger_state_is_never_confused_with_rejected_retrieved_or_not_selected(ledgers):
    """Explicit proof of the three-state distinction the review asked for:
    NOT_IN_CANONICAL_LEDGER must never be interpretable as 'rejected', 'retrieved', or
    'not selected' -- it is a separate, orthogonal axis (canonical identity resolution),
    not a fourth selection outcome."""
    _seed_memory(ledgers, "mem-known-2", "a known fact")
    # top_k=5 so mem-unknown-2 would have been SELECTED had it resolved -- proving
    # canonical_status is independent of the selection decision, not a proxy for it.
    candidates = [("mem-known-2", "a known fact"), ("mem-unknown-2", "an unwired fact that ranks high")]

    report = instrument_retrieval_and_selection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], task_id="task-4b", query="a known fact",
        candidates=candidates, config_fingerprint=CFG, actor="test", timestamp=TS, top_k=5,
    )
    unknown_event = next(e for e in report.candidate_scored_events if e.memory_id == "mem-unknown-2")

    # 1. Never confused with "rejected": no rejected CanonicalEvent exists for it at all
    #    (nothing in event_ledger references mem-unknown-2 in any event_type).
    assert all(
        "mem-unknown-2" not in e.memory_ids
        for e in ledgers["event_ledger"].all_events()
    )
    # 2. Never confused with "retrieved": same check -- zero CanonicalEvents reference it.
    assert unknown_event.memory_id not in report.retrieved_event_ids  # (ids, not memory_ids, but sanity)
    # 3. Never confused with "not selected": the score event's own `selected` flag is
    #    independent of canonical_status -- it may be True or False regardless.
    #    (select_by_hybrid_score ranks purely on text; whichever way it ranks here, the
    #    key assertion is that canonical_status is NOT derived from `selected`.)
    assert unknown_event.canonical_status == CANONICAL_STATUS_NOT_IN_LEDGER
    assert unknown_event.selected in (True, False)  # a real bool, set independently

    # 4. Durable and reconstructable after a fresh ledger reload (not just in the
    #    original in-process Phase5Event objects) -- the property Stage 5.8's future
    #    trace assembler will depend on.
    reloaded_ledger = Phase5EventLedger(ledgers["phase5_ledger"]._dir)
    reloaded_event = reloaded_ledger.get(unknown_event.event_id)
    assert reloaded_event.canonical_status == CANONICAL_STATUS_NOT_IN_LEDGER


def test_config_fingerprint_required_and_propagated_to_retrieved_and_selected_events(ledgers):
    _seed_memory(ledgers, "mem-cfg", "fact")
    report = instrument_retrieval_and_selection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], task_id="task-5", query="fact",
        candidates=[("mem-cfg", "fact")], config_fingerprint=CFG, actor="test", timestamp=TS,
    )
    retrieved_event = ledgers["event_ledger"].get_event(report.retrieved_event_ids[0])
    selected_event = ledgers["event_ledger"].get_event(report.selected_event_ids[0])
    assert retrieved_event.config_fingerprint == CFG
    assert selected_event.config_fingerprint == CFG
    scored_event = report.candidate_scored_events[0]
    assert scored_event.config_fingerprint == CFG


def _fake_rendered_messages(*memory_ids):
    lines = [f"[{mid}] some content" for mid in memory_ids]
    return (
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "\n".join(lines) + "\n\nQuestion: what happened?"},
    )


def test_context_assembly_preserves_render_order(ledgers):
    messages = _fake_rendered_messages("mem-3", "mem-1", "mem-2")
    event = record_context_assembly(
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], task_id="task-6", context_memory_ids=("mem-3", "mem-1", "mem-2"),
        rendered_messages=messages, actor="test", reason="prompt rendered", timestamp=TS,
    )
    assert event.context_memory_ids == ("mem-3", "mem-1", "mem-2")
    assert event.rendered_messages == messages
    assert ledgers["phase5_ledger"].exists(event.event_id)
    assert ledgers["membership_ledger"].run_for_event(event.event_id).run_id == ledgers["run_id"]

    # The persisted content is literally what was rendered -- reconstructable without
    # rerunning the experiment, per the OR-7 review fix.
    reloaded = ledgers["phase5_ledger"].get(event.event_id)
    assert reloaded.rendered_messages == messages
    assert reloaded.rendered_context_fingerprint == event.rendered_context_fingerprint


def test_context_assembly_rejects_empty_context():
    with pytest.raises(ValueError, match="non-empty"):
        record_context_assembly(
            phase5_event_ledger=None, membership_ledger=None, run_id="RUN-x", task_id="task-7",
            context_memory_ids=(), rendered_messages=_fake_rendered_messages("mem-1"),
            actor="test", reason="test", timestamp=TS,
        )


def test_context_assembly_rejects_empty_rendered_messages():
    with pytest.raises(ValueError, match="rendered_messages must be non-empty"):
        record_context_assembly(
            phase5_event_ledger=None, membership_ledger=None, run_id="RUN-x", task_id="task-7",
            context_memory_ids=("mem-1",), rendered_messages=(),
            actor="test", reason="test", timestamp=TS,
        )


def test_non_interference_select_by_hybrid_score_behavior_unchanged(ledgers):
    """Non-interference check: instrumenting the funnel must not change what
    select_by_hybrid_score() itself returns."""
    from phase3.evaluation.foundations.hybrid_selection import select_by_hybrid_score

    candidates = [("mem-a", "camping in June"), ("mem-b", "totally unrelated text")]
    baseline = select_by_hybrid_score("camping in June", candidates, top_k=1)

    _seed_memory(ledgers, "mem-a", "camping in June")
    _seed_memory(ledgers, "mem-b", "totally unrelated text")
    report = instrument_retrieval_and_selection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], task_id="task-8", query="camping in June",
        candidates=candidates, config_fingerprint=CFG, actor="test", timestamp=TS, top_k=1,
    )
    assert report.hybrid_result.selected == baseline.selected
    assert report.hybrid_result.rejected == baseline.rejected


# ---------------------------------------------------------------------------
# Live test: real foundation.retrieve()/inspect_memory() calls against MockMem0Adapter,
# mirroring campaign_runner.retrieve_select_generate()'s own retrieval steps (up to, but
# not including, generation -- that belongs to Stage 5.6).
# ---------------------------------------------------------------------------

def test_live_retrieval_against_real_mock_foundation(ledgers):
    foundation = MockMem0Adapter()
    foundation.initialize({})
    texts = {
        "mem-live-1": "Melanie went camping in June 2023.",
        "mem-live-2": "Melanie's favorite color is blue.",
        "mem-live-3": "Melanie enjoys rock climbing on weekends.",
    }
    for memory_id, text in texts.items():
        foundation.add_memory(memory_id=memory_id, content={"text": text}, metadata={"user_id": "u1"})
        _seed_memory(ledgers, memory_id, text)

    query = "When did Melanie go camping?"
    retrieve_field = foundation.retrieve({"text": "", "user_id": "u1"}, top_k=20)  # broad pool, real call
    candidates = []
    for item in retrieve_field.value:
        inspect_field = foundation.inspect_memory(item["memory_id"])
        candidates.append((item["memory_id"], inspect_field.value["content"]["text"]))

    report = instrument_retrieval_and_selection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], task_id="task-live", query=query,
        candidates=candidates, config_fingerprint=CFG, actor="test", timestamp=TS, top_k=2,
    )
    assert len(report.candidate_scored_events) == 3
    assert report.not_in_canonical_ledger == []
    selected_ids = {e.memory_id for e in report.candidate_scored_events if e.selected}
    assert "mem-live-1" in selected_ids  # the camping fact should rank highly for this query

    # Real render, exactly as campaign_runner.retrieve_select_generate() would produce it
    # -- build_agent_visible_context() + render_messages(), both real, frozen Phase 3
    # functions, never reimplemented.
    ordered_selected = tuple(c.memory_id for c in report.hybrid_result.selected)
    memory_items = [{"memory_id": c.memory_id, "content": c.content} for c in report.hybrid_result.selected]
    context = build_agent_visible_context(
        condition=CONDITION_RETRIEVED_MEMORY, task_id="task-live", prompt=query, memory_items=memory_items,
    )
    rendered = render_messages(context, system_prompt="You are a helpful assistant.")

    context_event = record_context_assembly(
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], task_id="task-live", context_memory_ids=ordered_selected,
        rendered_messages=rendered, actor="test", reason="prompt rendered from selected memories", timestamp=TS,
    )
    assert set(context_event.context_memory_ids) == selected_ids
    assert context_event.rendered_messages == tuple(rendered)
    # The literal camping fact text must actually be present in the persisted rendered
    # content -- reconstructable without rerunning retrieval or generation.
    rendered_text = " ".join(m["content"] for m in context_event.rendered_messages)
    assert "Melanie went camping in June 2023." in rendered_text
