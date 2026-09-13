"""Phase 5.8 -- tests for trace assembly and propagation-graph composition.

Exercises assemble_trace()/build_propagation_graph() against the real full pipeline
(Stage 5.4 live attack injection through Stage 5.7 lineage) wherever possible.
"""

from __future__ import annotations

import pytest

from phase3.evaluation.agent.conditions import CONDITION_RETRIEVED_MEMORY, build_agent_visible_context
from phase3.evaluation.agent_runtime.messages import DEFAULT_SYSTEM_PROMPT, render_messages
from phase3.evaluation.agent_runtime.runner import RunConfiguration
from phase3.evaluation.foundations.canonical import (
    CanonicalMemoryRecord,
    LIFECYCLE_ACTIVE,
    LIFECYCLE_CREATED,
    LIFECYCLE_RETIRED,
    MEMORY_TYPE_FOUNDATION,
    SOURCE_TYPE_PHASE2_UMR,
)
from phase3.evaluation.foundations.canonical_event import CanonicalEvent, EVENT_RETIRED, EVENT_SUPERSEDED
from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger
from phase3.evaluation.foundations.memory_versioning import SupersessionLedger
from phase3.evaluation.llm.provider import GenerationConfig, LlamaServerEndpoint, LlamaServerProvider, _RawHttpResponse

from phase5.identity.run_identity import EventRunMembershipLedger, ExperimentRunLedger, ExperimentRunRecord
from phase5.schema.event_ledger import Phase5EventLedger
from phase5.wiring.agent_decision_instrumentation import instrument_agent_decision
from phase5.wiring.lineage import (
    DERIVED_FROM,
    EVIDENCE_COUNTERFACTUAL,
    EVIDENCE_OBSERVED_EVENT,
    INFLUENCED,
    PRODUCED,
    PROPAGATED_TO,
    REFERENCES,
    SUPERSEDES,
    USED_BY,
)
from phase5.wiring.live_attack_runs import run_live_farma_injection
from phase5.wiring.memory_lifecycle import record_memory_creation, record_memory_derivation, record_memory_lifecycle_transition
from phase5.wiring.retrieval_instrumentation import instrument_retrieval_and_selection, record_context_assembly
from phase5.wiring.trace_assembly import ExperimentTrace, PropagationGraph, assemble_trace, build_propagation_graph

TS = "2026-09-12T00:00:00+00:00"
TS2 = "2026-09-12T00:01:00+00:00"
CFG = "CFG-trace-test"


def _foundation_record(memory_id, text):
    return CanonicalMemoryRecord(
        memory_id=memory_id, memory_type=MEMORY_TYPE_FOUNDATION, content={"text": text},
        source={"source_type": SOURCE_TYPE_PHASE2_UMR}, parent_ids=(),
        creation_event=f"creation-of-{memory_id}", creation_timestamp=TS, lifecycle_state=LIFECYCLE_CREATED,
    )


@pytest.fixture
def ledgers(tmp_path):
    memory_ledger = CanonicalMemoryLedger(tmp_path / "memory")
    event_ledger = CanonicalEventLedger(tmp_path / "events", memory_ledger)
    supersession_ledger = SupersessionLedger(tmp_path / "supersessions")
    run_ledger = ExperimentRunLedger(tmp_path / "runs")
    membership_ledger = EventRunMembershipLedger(tmp_path / "membership", run_ledger)
    phase5_ledger = Phase5EventLedger(tmp_path / "phase5_events")
    run = ExperimentRunRecord(
        experiment_id="exp-trace", run_id="RUN-trace", dataset="locomo",
        scope={"attack_id": "farma"}, started_at=TS, actor="test", reason="trace assembly test run",
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


def test_assemble_trace_reconstructs_the_full_real_pipeline(ledgers):
    # --- Stage 5.4: live attack injection ---
    injection_result = run_live_farma_injection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], timestamp=TS,
    )
    poisoned_memory_id = injection_result.memory_creation.created_event.memory_ids[0]
    poisoned_content = ledgers["memory_ledger"].get(poisoned_memory_id).content["text"]

    # --- Stage 5.5: retrieval, selection, context assembly ---
    query = "When is Melanie planning on going camping?"
    retrieval_report = instrument_retrieval_and_selection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], task_id="task-trace", query=query,
        candidates=[(poisoned_memory_id, poisoned_content)], config_fingerprint=CFG, actor="test", timestamp=TS, top_k=1,
    )
    memory_items = [{"memory_id": poisoned_memory_id, "content": poisoned_content}]
    context = build_agent_visible_context(condition=CONDITION_RETRIEVED_MEMORY, task_id="task-trace", prompt=query, memory_items=memory_items)
    rendered = render_messages(context, system_prompt=DEFAULT_SYSTEM_PROMPT)
    context_event = record_context_assembly(
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], task_id="task-trace", context_memory_ids=(poisoned_memory_id,),
        rendered_messages=rendered, actor="test", reason="prompt rendered", timestamp=TS,
    )

    # --- Stage 5.6: decision + action ---
    run_config = RunConfiguration(
        llm_provider=_scripted_provider("Melanie's camping trip was moved to September 2023."),
        generation_config=GenerationConfig(temperature=0.0, seed=42, max_tokens=64, enable_thinking=False, n_ctx=1024),
        system_prompt=DEFAULT_SYSTEM_PROMPT, max_retries=0,
    )
    decision_result = instrument_agent_decision(
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], task_id="task-trace", decision_id="dec-trace", action_id="act-trace",
        exposed_memory_ids=(poisoned_memory_id,), messages=rendered, run_config=run_config,
        actor="test", timestamp=TS,
    )

    # --- Stage 5.8: assemble the trace, purely from persisted state ---
    trace = assemble_trace(
        ledgers["run_id"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
    )
    assert trace.run_id == ledgers["run_id"]
    assert trace.unresolved_event_ids == ()

    assert len(trace.injections) == 1
    assert trace.injections[0].event_id == injection_result.injection_event.event_id

    assert len(trace.memory_created) == 1
    assert trace.memory_created[0].memory_ids == (poisoned_memory_id,)

    assert len(trace.memory_retrieved) == 1
    assert len(trace.memory_selected) == 1
    assert trace.memory_rejected == ()

    assert len(trace.retrieval_candidates_scored) == 1
    assert len(trace.context_assembled) == 1
    assert trace.context_assembled[0].event_id == context_event.event_id

    assert len(trace.agent_decisions) == 1
    assert trace.agent_decisions[0].event_id == decision_result.decision_event.event_id
    assert len(trace.agent_actions) == 1
    assert trace.agent_actions[0].event_id == decision_result.action_event.event_id

    assert trace.memory_derived == ()
    assert trace.memory_superseded == ()
    assert trace.counterfactual_findings == ()
    assert trace.ground_truth_transitions == ()


def test_assemble_trace_is_deterministic_across_repeated_calls(ledgers):
    run_live_farma_injection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], timestamp=TS,
    )
    trace1 = assemble_trace(
        ledgers["run_id"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
    )
    trace2 = assemble_trace(
        ledgers["run_id"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
    )
    assert trace1 == trace2


def test_assemble_trace_reconstructs_from_a_fresh_ledger_reload(ledgers, tmp_path):
    run_live_farma_injection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], timestamp=TS,
    )
    reloaded_memory = CanonicalMemoryLedger(tmp_path / "memory")
    reloaded_events = CanonicalEventLedger(tmp_path / "events", reloaded_memory)
    reloaded_phase5 = Phase5EventLedger(tmp_path / "phase5_events")
    reloaded_membership = EventRunMembershipLedger(tmp_path / "membership", ExperimentRunLedger(tmp_path / "runs"))

    trace = assemble_trace(
        ledgers["run_id"], event_ledger=reloaded_events,
        phase5_event_ledger=reloaded_phase5, membership_ledger=reloaded_membership,
    )
    assert len(trace.injections) == 1
    assert len(trace.memory_created) == 1


def test_assemble_trace_scopes_strictly_to_its_own_run(ledgers, tmp_path):
    from phase5.wiring.memory_lifecycle import record_attack_injection
    from phase5.schema.event import ADMISSION_STATUS_ADMITTED

    run_live_farma_injection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], timestamp=TS,
    )
    other_run = ExperimentRunRecord(
        experiment_id="exp-trace-2", run_id="RUN-trace-other", dataset="locomo",
        scope={}, started_at=TS, actor="test", reason="a second, unrelated run",
    )
    ledgers["membership_ledger"]._run_ledger.register(other_run)
    # A second, genuinely distinct injection (different attack_id/artifact_id/memory_id --
    # not the same FARMA fixture reused, which would collide on CanonicalMemoryLedger's
    # own memory_id-based collision policy since SEED_CAMPING's artifact_id is fixed) --
    # registered against the OTHER run.
    record_attack_injection(
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id="RUN-trace-other", attack_id="agentpoison", injection_id="INJ-other-run",
        artifact_id="artifact-other-run", admission_status=ADMISSION_STATUS_ADMITTED,
        actor="test", reason="second run's own injection", timestamp=TS2, memory_id="mem-other-run",
    )
    trace_1 = assemble_trace(
        ledgers["run_id"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
    )
    trace_2 = assemble_trace(
        "RUN-trace-other", event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
    )
    assert len(trace_1.injections) == 1
    assert len(trace_2.injections) == 1
    assert trace_1.injections[0].event_id != trace_2.injections[0].event_id


# ---------------------------------------------------------------------------
# Propagation graph
# ---------------------------------------------------------------------------

def test_build_propagation_graph_includes_produced_and_used_by(ledgers):
    injection_result = run_live_farma_injection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], timestamp=TS,
    )
    poisoned_memory_id = injection_result.memory_creation.created_event.memory_ids[0]

    from phase5.wiring.agent_decision_instrumentation import record_agent_decision, FINISH_REASON_GENERATED, USED_MEMORIES_NOT_OBSERVABLE
    record_agent_decision(
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], task_id="task-graph", decision_id="dec-graph",
        exposed_memory_ids=(poisoned_memory_id,), output="the answer",
        finish_reason=FINISH_REASON_GENERATED, model_identity="qwen3-8b", config_fingerprint=CFG,
        used_memories_observability=USED_MEMORIES_NOT_OBSERVABLE,
        actor="test", reason="generation completed", timestamp=TS,
    )

    graph = build_propagation_graph(
        ledgers["run_id"], memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        supersession_ledger=ledgers["supersession_ledger"],
    )
    assert graph.run_id == ledgers["run_id"]
    produced = graph.edges_of_type(PRODUCED)
    assert any(e.target_id == poisoned_memory_id for e in produced)
    used_by = graph.edges_of_type(USED_BY)
    assert any(e.source_id == poisoned_memory_id and e.target_id == "dec-graph" for e in used_by)
    assert graph.edges_touching(poisoned_memory_id)  # non-empty


def test_build_propagation_graph_scopes_edges_to_the_given_run(ledgers):
    from phase5.wiring.memory_lifecycle import record_attack_injection
    from phase5.schema.event import ADMISSION_STATUS_ADMITTED

    injection_result_1 = run_live_farma_injection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], timestamp=TS,
    )
    other_run = ExperimentRunRecord(
        experiment_id="exp-graph-2", run_id="RUN-graph-other", dataset="locomo",
        scope={}, started_at=TS, actor="test", reason="a second, unrelated run",
    )
    ledgers["membership_ledger"]._run_ledger.register(other_run)
    # A genuinely distinct injection (not the same FARMA fixture reused -- its fixed
    # artifact_id would collide on CanonicalMemoryLedger's own memory_id-based policy),
    # registered against the OTHER run.
    record_attack_injection(
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id="RUN-graph-other", attack_id="agentpoison", injection_id="INJ-other-run-graph",
        artifact_id="artifact-other-run-graph", admission_status=ADMISSION_STATUS_ADMITTED,
        actor="test", reason="second run's own injection", timestamp=TS2, memory_id="mem-other-run-graph",
    )
    graph_1 = build_propagation_graph(
        ledgers["run_id"], memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
    )
    mem_1 = injection_result_1.memory_creation.created_event.memory_ids[0]
    produced_targets = {e.target_id for e in graph_1.edges_of_type(PRODUCED)}
    assert mem_1 in produced_targets
    assert "mem-other-run-graph" not in produced_targets  # strictly scoped, never leaks the other run's edges


def test_build_propagation_graph_never_fabricates_influenced(ledgers):
    run_live_farma_injection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], timestamp=TS,
    )
    graph = build_propagation_graph(
        ledgers["run_id"], memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
    )
    assert graph.edges_of_type(INFLUENCED) == ()  # no counterfactually_influential event exists


def test_build_propagation_graph_includes_pairwise_retrieval_edges(ledgers):
    for i in range(3):
        record_memory_creation(
            memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
            membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
            record=_foundation_record(f"mem-graph-pw-{i}", f"fact {i} about camping"), actor="test", reason="seed", timestamp=TS,
        )
    candidates = [(f"mem-graph-pw-{i}", f"fact {i} about camping") for i in range(3)]
    instrument_retrieval_and_selection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], task_id="task-graph-pw", query="camping",
        candidates=candidates, config_fingerprint=CFG, actor="test", timestamp=TS, top_k=3,
    )
    graph = build_propagation_graph(
        ledgers["run_id"], memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
    )
    from phase5.wiring.lineage import RETRIEVED_WITH
    assert len(graph.edges_of_type(RETRIEVED_WITH)) == 3  # C(3,2)


def test_non_interference_provenance_graph_and_taint_propagation_unmodified(ledgers):
    """Confirms Stage 5.8 calls, never reimplements, the frozen mechanisms Stage 5.7
    already wraps -- an end-to-end sanity check that nothing here bypasses them."""
    from phase3.evaluation.foundations.provenance_graph import build_provenance_graph
    injection_result = run_live_farma_injection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], timestamp=TS,
    )
    # ProvenanceGraph itself still works, unaffected by anything Stage 5.8 does.
    prov_graph = build_provenance_graph(ledgers["memory_ledger"], ledgers["event_ledger"])
    assert prov_graph is not None
    build_propagation_graph(
        ledgers["run_id"], memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
    )
    prov_graph_after = build_provenance_graph(ledgers["memory_ledger"], ledgers["event_ledger"])
    assert prov_graph == prov_graph_after


# ---------------------------------------------------------------------------
# Post-Phase-5 hardening, Section 15: task-level projection.
# ---------------------------------------------------------------------------

def test_assemble_task_trace_filters_task_scoped_fields_but_keeps_run_level_facts(ledgers):
    from phase5.wiring.trace_assembly import assemble_task_trace

    injection_result = run_live_farma_injection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], timestamp=TS,
    )
    memory_id = injection_result.memory_creation.created_event.memory_ids[0]
    content = ledgers["memory_ledger"].get(memory_id).content["text"]

    for task_id in ("task-a", "task-b"):
        instrument_retrieval_and_selection(
            memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
            phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
            run_id=ledgers["run_id"], task_id=task_id, query="q",
            candidates=[(memory_id, content)], config_fingerprint=CFG, actor="test", timestamp=TS, top_k=1,
        )

    full_trace = assemble_trace(
        ledgers["run_id"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
    )
    task_a_trace = assemble_task_trace(
        ledgers["run_id"], "task-a", event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
    )

    # Task-scoped fields: filtered down to just task-a's own events.
    assert len(full_trace.retrieval_candidates_scored) == 2  # one per task
    assert len(task_a_trace.retrieval_candidates_scored) == 1
    assert task_a_trace.retrieval_candidates_scored[0].task_id == "task-a"
    assert all(e.task_id == "task-a" for e in task_a_trace.memory_retrieved)
    assert all(e.task_id == "task-a" for e in task_a_trace.memory_selected)

    # Run-level facts: passed through unfiltered -- the injection and the memory's
    # creation are not owned by any one task, and dropping them would break
    # reconstruction of task-a's own retrieval (which depends on the memory existing).
    assert task_a_trace.injections == full_trace.injections
    assert task_a_trace.memory_created == full_trace.memory_created

    # This is a pure filter over assemble_trace()'s own output, never a second query --
    # no event id appears in the task trace that isn't already in the full trace.
    def _all_event_ids(trace):
        ids = set()
        for field_name in ("injections", "memory_created", "memory_retrieved", "memory_selected", "retrieval_candidates_scored"):
            ids.update(e.event_id for e in getattr(trace, field_name))
        return ids
    assert _all_event_ids(task_a_trace).issubset(_all_event_ids(full_trace))


# ---------------------------------------------------------------------------
# Final 5.8-5.9 reconciliation (2026-09-13): REFERENCES composed into
# build_propagation_graph(), per that function's own long-standing "every applicable
# Stage 5.7 derive_* function" contract -- see PHASE5_5_8_TRACE_ASSEMBLY_PROPAGATION_GRAPH.md
# "Reconciliation" section for the evidence-based decision.
# ---------------------------------------------------------------------------

def test_build_propagation_graph_includes_real_references_edge(ledgers):
    """Requirement 1: a real structural reference appears in the assembled graph."""
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        record=_foundation_record("mem-refgraph-cited", "the original fact"), actor="test", reason="seed", timestamp=TS,
    )
    from phase3.evaluation.foundations.canonical import MEMORY_TYPE_DERIVED, SOURCE_TYPE_DERIVATION_EVENT
    citing = CanonicalMemoryRecord(
        memory_id="mem-refgraph-citing", memory_type=MEMORY_TYPE_DERIVED, content={"text": "as established in [mem-refgraph-cited], the claim holds"},
        source={"source_type": SOURCE_TYPE_DERIVATION_EVENT}, parent_ids=("mem-refgraph-cited",),
        creation_event="derivation-of-mem-refgraph-citing", creation_timestamp=TS2, lifecycle_state=LIFECYCLE_CREATED,
    )
    derivation_result = record_memory_derivation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        derived_record=citing, source_memory_ids=("mem-refgraph-cited",),
        actor="test", reason="cites its own parent explicitly", timestamp=TS2,
    )

    graph = build_propagation_graph(
        ledgers["run_id"], memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
    )
    references_edges = graph.edges_of_type(REFERENCES)
    assert len(references_edges) == 1
    edge = references_edges[0]
    assert edge.source_id == "mem-refgraph-citing"
    assert edge.target_id == "mem-refgraph-cited"

    # Requirement 2: grounded in the real creation/derivation event.
    assert edge.established_by_event_ids == (derivation_result.created_event.event_id,)

    # Requirement 7: evidence kind remains OBSERVED_EVENT.
    assert edge.evidence_kind == EVIDENCE_OBSERVED_EVENT


def test_build_propagation_graph_no_references_edge_without_exact_citation(ledgers):
    """Requirement 3: no edge occurs without an exact [memory_id] citation."""
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        record=_foundation_record("mem-refgraph-plain-a", "fact a about camping"), actor="test", reason="seed", timestamp=TS,
    )
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        record=_foundation_record("mem-refgraph-plain-b", "an unrelated fact b"), actor="test", reason="seed", timestamp=TS2,
    )
    graph = build_propagation_graph(
        ledgers["run_id"], memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
    )
    assert graph.edges_of_type(REFERENCES) == ()


def test_build_propagation_graph_no_references_edge_from_word_overlap(ledgers):
    """Requirement 4: word overlap alone does not produce an edge -- the exact idea the
    Post-Phase-5 hardening pass rejected for the model-behavior case must still not fire
    here for the structural case either."""
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        record=_foundation_record("mem-refgraph-src", "camping trip to the lake"), actor="test", reason="seed", timestamp=TS,
    )
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        # Mentions "mem-refgraph-src" as plain text, no bracket citation form.
        record=_foundation_record("mem-refgraph-similar", "mem-refgraph-src was also a camping trip"),
        actor="test", reason="seed", timestamp=TS2,
    )
    graph = build_propagation_graph(
        ledgers["run_id"], memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
    )
    assert graph.edges_of_type(REFERENCES) == ()


def test_build_propagation_graph_no_self_reference_edge(ledgers):
    """Requirement 5: self-reference does not produce an edge."""
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        record=_foundation_record("mem-refgraph-self", "as noted in [mem-refgraph-self] previously"),
        actor="test", reason="seed", timestamp=TS,
    )
    graph = build_propagation_graph(
        ledgers["run_id"], memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
    )
    assert graph.edges_of_type(REFERENCES) == ()


def test_build_propagation_graph_references_never_influenced(ledgers):
    """Requirement 6: REFERENCES never produces INFLUENCED."""
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        record=_foundation_record("mem-refgraph-a", "fact a"), actor="test", reason="seed", timestamp=TS,
    )
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        record=_foundation_record("mem-refgraph-b", "fact b, see also [mem-refgraph-a]"), actor="test", reason="seed", timestamp=TS2,
    )
    graph = build_propagation_graph(
        ledgers["run_id"], memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
    )
    assert len(graph.edges_of_type(REFERENCES)) == 1
    assert graph.edges_of_type(INFLUENCED) == ()
    for edge in graph.edges_of_type(REFERENCES):
        assert edge.evidence_kind != EVIDENCE_COUNTERFACTUAL
        assert edge.relationship_type != INFLUENCED


def test_build_propagation_graph_references_deterministic_across_repeated_calls(ledgers):
    """Requirement 8: deterministic repeated reconstruction."""
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        record=_foundation_record("mem-refgraph-det-a", "fact a"), actor="test", reason="seed", timestamp=TS,
    )
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        record=_foundation_record("mem-refgraph-det-b", "fact b cites [mem-refgraph-det-a]"), actor="test", reason="seed", timestamp=TS2,
    )
    graph_1 = build_propagation_graph(
        ledgers["run_id"], memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
    )
    graph_2 = build_propagation_graph(
        ledgers["run_id"], memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
    )
    assert graph_1.edges_of_type(REFERENCES) == graph_2.edges_of_type(REFERENCES)


def test_build_propagation_graph_references_survive_fresh_ledger_reload(ledgers, tmp_path):
    """Requirement 9: fresh-ledger reload produces identical output."""
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        record=_foundation_record("mem-refgraph-reload-a", "fact a"), actor="test", reason="seed", timestamp=TS,
    )
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        record=_foundation_record("mem-refgraph-reload-b", "fact b cites [mem-refgraph-reload-a]"), actor="test", reason="seed", timestamp=TS2,
    )
    original_graph = build_propagation_graph(
        ledgers["run_id"], memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
    )

    reloaded_memory = CanonicalMemoryLedger(tmp_path / "memory")
    reloaded_events = CanonicalEventLedger(tmp_path / "events", reloaded_memory)
    reloaded_phase5 = Phase5EventLedger(tmp_path / "phase5_events")
    reloaded_membership = EventRunMembershipLedger(tmp_path / "membership", ExperimentRunLedger(tmp_path / "runs"))
    reloaded_graph = build_propagation_graph(
        ledgers["run_id"], memory_ledger=reloaded_memory, event_ledger=reloaded_events,
        phase5_event_ledger=reloaded_phase5, membership_ledger=reloaded_membership,
    )
    assert original_graph.edges_of_type(REFERENCES) == reloaded_graph.edges_of_type(REFERENCES)


def test_build_propagation_graph_references_respect_run_isolation(ledgers):
    """Requirement 10: run isolation remains intact -- a citation recorded under a
    different run must never appear in this run's own graph."""
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        record=_foundation_record("mem-refgraph-iso-a", "fact a"), actor="test", reason="seed", timestamp=TS,
    )
    other_run = ExperimentRunRecord(
        experiment_id="exp-refgraph-iso", run_id="RUN-refgraph-iso-other", dataset="locomo",
        scope={}, started_at=TS, actor="test", reason="a second, unrelated run",
    )
    ledgers["membership_ledger"]._run_ledger.register(other_run)
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id="RUN-refgraph-iso-other",
        record=_foundation_record("mem-refgraph-iso-b", "fact b cites [mem-refgraph-iso-a]"), actor="test", reason="seed", timestamp=TS2,
    )
    # Note: the citing memory "mem-refgraph-iso-b" is registered to the OTHER run, even
    # though both memories live in the same shared memory_ledger for this test -- exactly
    # the case _edge_belongs_to_run() must scope correctly (an edge's established_by_event_ids
    # must ALL be registered to the queried run).
    graph_this_run = build_propagation_graph(
        ledgers["run_id"], memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
    )
    assert graph_this_run.edges_of_type(REFERENCES) == ()

    graph_other_run = build_propagation_graph(
        "RUN-refgraph-iso-other", memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
    )
    references_edges = graph_other_run.edges_of_type(REFERENCES)
    assert len(references_edges) == 1
    assert references_edges[0].source_id == "mem-refgraph-iso-b"
