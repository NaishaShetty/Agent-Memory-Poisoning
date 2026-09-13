"""Phase 5.8A -- tests for Memory Behavior Dataset derivation, including generation of a
real sample dataset file from the real full pipeline chain (Stage 5.4 live attack
injection through Stage 5.7 lineage), per the explicit "generated dataset" deliverable.
"""

from __future__ import annotations

import pytest

from phase3.evaluation.agent.conditions import CONDITION_RETRIEVED_MEMORY, build_agent_visible_context
from phase3.evaluation.agent_runtime.messages import DEFAULT_SYSTEM_PROMPT, render_messages
from phase3.evaluation.agent_runtime.runner import RunConfiguration
from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger
from phase3.evaluation.foundations.memory_versioning import SupersessionLedger
from phase3.evaluation.llm.provider import GenerationConfig, LlamaServerEndpoint, LlamaServerProvider, _RawHttpResponse

from phase5.identity.run_identity import EventRunMembershipLedger, ExperimentRunLedger, ExperimentRunRecord
from phase5.schema.event_ledger import Phase5EventLedger
from phase5.wiring.agent_decision_instrumentation import instrument_agent_decision
from phase5.wiring.live_attack_runs import run_live_farma_injection
from phase5.wiring.memory_behavior_dataset import (
    RECORD_TYPE_AGENT_INTERACTION,
    RECORD_TYPE_ATTACK_INJECTION,
    RECORD_TYPE_MEMORY_LIFECYCLE,
    RECORD_TYPE_MEMORY_RELATIONSHIP,
    RECORD_TYPE_RETRIEVAL_SELECTION,
    MemoryBehaviorDatasetError,
    MemoryBehaviorRecord,
    derive_memory_behavior_dataset,
    read_memory_behavior_dataset_jsonl,
    write_memory_behavior_dataset_jsonl,
)
from phase5.wiring.memory_lifecycle import record_memory_creation, record_memory_derivation
from phase5.wiring.retrieval_instrumentation import instrument_retrieval_and_selection, record_context_assembly

TS = "2026-09-12T00:00:00+00:00"
CFG = "CFG-dataset-test"


@pytest.fixture
def ledgers(tmp_path):
    memory_ledger = CanonicalMemoryLedger(tmp_path / "memory")
    event_ledger = CanonicalEventLedger(tmp_path / "events", memory_ledger)
    supersession_ledger = SupersessionLedger(tmp_path / "supersessions")
    run_ledger = ExperimentRunLedger(tmp_path / "runs")
    membership_ledger = EventRunMembershipLedger(tmp_path / "membership", run_ledger)
    phase5_ledger = Phase5EventLedger(tmp_path / "phase5_events")
    run = ExperimentRunRecord(
        experiment_id="exp-dataset", run_id="RUN-dataset", dataset="locomo",
        scope={"attack_id": "farma"}, started_at=TS, actor="test", reason="dataset derivation test run",
    )
    run_ledger.register(run)
    return dict(
        memory_ledger=memory_ledger, event_ledger=event_ledger, supersession_ledger=supersession_ledger,
        membership_ledger=membership_ledger, phase5_ledger=phase5_ledger, run_id=run.run_id,
    )


def _scripted_provider(reply_text: str) -> LlamaServerProvider:
    import json

    def post_json(url, body, timeout):
        payload = {
            "choices": [{"message": {"content": reply_text}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            "system_fingerprint": "b10717-a32af33de",
        }
        return _RawHttpResponse(status=200, body=json.dumps(payload).encode("utf-8"))
    return LlamaServerProvider(endpoint=LlamaServerEndpoint(), post_json=post_json)


def _run_full_pipeline(ledgers, task_id="task-dataset"):
    injection_result = run_live_farma_injection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], timestamp=TS,
    )
    poisoned_memory_id = injection_result.memory_creation.created_event.memory_ids[0]
    poisoned_content = ledgers["memory_ledger"].get(poisoned_memory_id).content["text"]

    query = "When is Melanie planning on going camping?"
    instrument_retrieval_and_selection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], task_id=task_id, query=query,
        candidates=[(poisoned_memory_id, poisoned_content)], config_fingerprint=CFG, actor="test", timestamp=TS, top_k=1,
    )
    memory_items = [{"memory_id": poisoned_memory_id, "content": poisoned_content}]
    context = build_agent_visible_context(condition=CONDITION_RETRIEVED_MEMORY, task_id=task_id, prompt=query, memory_items=memory_items)
    rendered = render_messages(context, system_prompt=DEFAULT_SYSTEM_PROMPT)
    record_context_assembly(
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], task_id=task_id, context_memory_ids=(poisoned_memory_id,),
        rendered_messages=rendered, actor="test", reason="prompt rendered", timestamp=TS,
    )
    run_config = RunConfiguration(
        llm_provider=_scripted_provider("Melanie's camping trip was moved to September 2023."),
        generation_config=GenerationConfig(temperature=0.0, seed=42, max_tokens=64, enable_thinking=False, n_ctx=1024),
        system_prompt=DEFAULT_SYSTEM_PROMPT, max_retries=0,
    )
    instrument_agent_decision(
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], task_id=task_id, decision_id="dec-dataset", action_id="act-dataset",
        exposed_memory_ids=(poisoned_memory_id,), messages=rendered, run_config=run_config,
        actor="test", timestamp=TS,
    )
    return poisoned_memory_id


def test_derive_memory_behavior_dataset_covers_all_categories(ledgers):
    poisoned_memory_id = _run_full_pipeline(ledgers)
    records = derive_memory_behavior_dataset(
        ledgers["run_id"], memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        supersession_ledger=ledgers["supersession_ledger"],
    )
    record_types_present = {r.record_type for r in records}
    assert RECORD_TYPE_MEMORY_LIFECYCLE in record_types_present
    assert RECORD_TYPE_RETRIEVAL_SELECTION in record_types_present
    assert RECORD_TYPE_AGENT_INTERACTION in record_types_present
    assert RECORD_TYPE_MEMORY_RELATIONSHIP in record_types_present
    assert RECORD_TYPE_ATTACK_INJECTION in record_types_present
    # No counterfactually_influential event was ever recorded in this pipeline (no
    # counterfactual masking run occurred) -- correctly absent from the dataset, not
    # fabricated to fill out the category list.
    assert "counterfactual_evidence" not in record_types_present

    for record in records:
        assert record.run_id == ledgers["run_id"]
        assert len(record.source_event_ids) > 0  # every record cites a real event


def test_every_record_source_event_id_exists_in_a_real_ledger(ledgers):
    """Validation-ready provenance: every cited source_event_id must resolve to a real,
    persisted event in one of the two ledgers -- never a dangling or fabricated id."""
    _run_full_pipeline(ledgers)
    records = derive_memory_behavior_dataset(
        ledgers["run_id"], memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        supersession_ledger=ledgers["supersession_ledger"],
    )
    for record in records:
        for event_id in record.source_event_ids:
            resolvable = (
                ledgers["event_ledger"].get_event(event_id) is not None
                or ledgers["phase5_ledger"].exists(event_id)
            )
            assert resolvable, f"record {record.record_type!r} cites unresolvable event_id {event_id!r}"


def test_derivation_is_deterministic_across_repeated_calls(ledgers):
    _run_full_pipeline(ledgers)
    records_1 = derive_memory_behavior_dataset(
        ledgers["run_id"], memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        supersession_ledger=ledgers["supersession_ledger"],
    )
    records_2 = derive_memory_behavior_dataset(
        ledgers["run_id"], memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        supersession_ledger=ledgers["supersession_ledger"],
    )
    assert records_1 == records_2


def test_derivation_is_deterministic_from_a_fresh_ledger_reload(ledgers, tmp_path):
    _run_full_pipeline(ledgers)
    baseline = derive_memory_behavior_dataset(
        ledgers["run_id"], memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        supersession_ledger=ledgers["supersession_ledger"],
    )

    reloaded_memory = CanonicalMemoryLedger(tmp_path / "memory")
    reloaded_events = CanonicalEventLedger(tmp_path / "events", reloaded_memory)
    reloaded_supersession = SupersessionLedger(tmp_path / "supersessions")
    reloaded_run_ledger = ExperimentRunLedger(tmp_path / "runs")
    reloaded_membership = EventRunMembershipLedger(tmp_path / "membership", reloaded_run_ledger)
    reloaded_phase5 = Phase5EventLedger(tmp_path / "phase5_events")

    reloaded = derive_memory_behavior_dataset(
        ledgers["run_id"], memory_ledger=reloaded_memory, event_ledger=reloaded_events,
        phase5_event_ledger=reloaded_phase5, membership_ledger=reloaded_membership,
        supersession_ledger=reloaded_supersession,
    )
    assert baseline == reloaded


def test_record_rejects_empty_source_event_ids():
    with pytest.raises(MemoryBehaviorDatasetError, match="source_event_ids"):
        MemoryBehaviorRecord(record_type=RECORD_TYPE_MEMORY_LIFECYCLE, run_id="RUN-x", source_event_ids=(), fields={})


def test_record_rejects_unknown_record_type():
    with pytest.raises(MemoryBehaviorDatasetError, match="record_type"):
        MemoryBehaviorRecord(record_type="not_a_real_type", run_id="RUN-x", source_event_ids=("evt-1",), fields={})


def test_jsonl_round_trip(ledgers, tmp_path):
    _run_full_pipeline(ledgers)
    records = derive_memory_behavior_dataset(
        ledgers["run_id"], memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        supersession_ledger=ledgers["supersession_ledger"],
    )
    out_path = tmp_path / "dataset.jsonl"
    write_memory_behavior_dataset_jsonl(records, out_path)
    reloaded = read_memory_behavior_dataset_jsonl(out_path)
    assert reloaded == records


def test_never_modifies_frozen_ledgers(ledgers):
    """Non-interference: dataset derivation is read-only."""
    _run_full_pipeline(ledgers)
    before_events = ledgers["event_ledger"].all_events()
    before_phase5 = ledgers["phase5_ledger"].all_events()
    derive_memory_behavior_dataset(
        ledgers["run_id"], memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        supersession_ledger=ledgers["supersession_ledger"],
    )
    assert ledgers["event_ledger"].all_events() == before_events
    assert ledgers["phase5_ledger"].all_events() == before_phase5


# ---------------------------------------------------------------------------
# Final 5.8-5.9 reconciliation (2026-09-13): REFERENCES now flows through the existing
# memory_relationship category automatically, once Stage 5.8's build_propagation_graph()
# composes derive_references_edges() -- no new dataset category was created, per the
# "prefer the existing memory_relationship category" instruction.
# ---------------------------------------------------------------------------

def test_references_edge_flows_through_existing_memory_relationship_category(ledgers):
    from phase3.evaluation.foundations.canonical import (
        LIFECYCLE_CREATED,
        MEMORY_TYPE_DERIVED,
        MEMORY_TYPE_FOUNDATION,
        SOURCE_TYPE_DERIVATION_EVENT,
        SOURCE_TYPE_PHASE2_UMR,
        CanonicalMemoryRecord,
    )

    cited = CanonicalMemoryRecord(
        memory_id="mem-dataset-ref-cited", memory_type=MEMORY_TYPE_FOUNDATION, content={"text": "the original fact"},
        source={"source_type": SOURCE_TYPE_PHASE2_UMR}, parent_ids=(),
        creation_event="creation-of-mem-dataset-ref-cited", creation_timestamp=TS, lifecycle_state=LIFECYCLE_CREATED,
    )
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        record=cited, actor="test", reason="seed", timestamp=TS,
    )
    citing = CanonicalMemoryRecord(
        memory_id="mem-dataset-ref-citing", memory_type=MEMORY_TYPE_DERIVED, content={"text": "per [mem-dataset-ref-cited], the claim holds"},
        source={"source_type": SOURCE_TYPE_DERIVATION_EVENT}, parent_ids=("mem-dataset-ref-cited",),
        creation_event="derivation-of-mem-dataset-ref-citing", creation_timestamp=TS, lifecycle_state=LIFECYCLE_CREATED,
    )
    record_memory_derivation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        derived_record=citing, source_memory_ids=("mem-dataset-ref-cited",),
        actor="test", reason="cites its own parent explicitly", timestamp=TS,
    )

    records = derive_memory_behavior_dataset(
        ledgers["run_id"], memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        supersession_ledger=ledgers["supersession_ledger"],
    )
    references_records = [
        r for r in records
        if r.record_type == RECORD_TYPE_MEMORY_RELATIONSHIP and r.fields.get("relationship_type") == "REFERENCES"
    ]
    assert len(references_records) == 1
    record = references_records[0]
    assert record.fields["source_id"] == "mem-dataset-ref-citing"
    assert record.fields["target_id"] == "mem-dataset-ref-cited"
    assert record.fields["evidence_kind"] == "OBSERVED_EVENT"
    assert len(record.source_event_ids) == 1  # grounded in the real derivation event, never fabricated


# ---------------------------------------------------------------------------
# The actual "generated dataset" deliverable: a real sample dataset file, produced from
# a real full-pipeline run, committed under phase5/datasets/.
# ---------------------------------------------------------------------------

def test_generate_committed_sample_dataset(ledgers):
    poisoned_memory_id = _run_full_pipeline(ledgers, task_id="task-sample-dataset")
    records = derive_memory_behavior_dataset(
        ledgers["run_id"], memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        supersession_ledger=ledgers["supersession_ledger"],
    )
    assert len(records) >= 6  # at least one record per non-empty category in this pipeline

    out_path = "phase5/datasets/memory_behavior_dataset_sample.jsonl"
    write_memory_behavior_dataset_jsonl(records, out_path)
    reloaded = read_memory_behavior_dataset_jsonl(out_path)
    assert reloaded == records
    assert any(
        r.record_type == "memory_lifecycle" and r.fields.get("memory_ids") == [poisoned_memory_id]
        for r in reloaded
    )
