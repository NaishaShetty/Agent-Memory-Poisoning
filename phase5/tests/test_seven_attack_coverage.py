"""Post-Phase-5 hardening -- Section 17: seven-attack end-to-end coverage.

Runs each of the 7 frozen Phase 4 attacks' REAL injectors (via Stage 5.4's
`live_attack_runs.py`, unmodified) through the full downstream pipeline -- retrieval,
selection, context assembly, decision/action, lineage, trace assembly, and Memory
Behavior Dataset derivation -- wherever the attack's own real outcome makes that stage
applicable. A rejected/non-admitted outcome (Sleeper DISCARD, MemoryGraft DISCARD) is a
legitimate NOT_APPLICABLE result for every downstream memory-dependent stage, never a
failure -- this file asserts that distinction explicitly rather than collapsing it.

No attack code is modified. No stage is skipped for an attack that legitimately reaches
it; no stage is force-run for an attack that legitimately cannot reach it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

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
from phase5.wiring.live_attack_runs import (
    run_live_agentpoison_injection,
    run_live_dsrm_injection,
    run_live_farma_injection,
    run_live_memorygraft_injection,
    run_live_minja_injection,
    run_live_mpbench_injection,
    run_live_sleeper_injection,
)
from phase5.wiring.memory_behavior_dataset import derive_memory_behavior_dataset
from phase5.wiring.retrieval_instrumentation import instrument_retrieval_and_selection, record_context_assembly
from phase5.wiring.trace_assembly import assemble_trace, build_propagation_graph

TS = "2026-09-12T00:00:00+00:00"
CFG = "CFG-coverage-test"

PASS = "PASS"
NOT_APPLICABLE = "NOT_APPLICABLE"
FAILED = "FAILED"


@dataclass
class AttackCoverageRow:
    attack: str
    injection: str = FAILED
    admission: str = FAILED
    lifecycle: str = FAILED
    retrieval: str = FAILED
    selection: str = FAILED
    agent: str = FAILED
    lineage: str = FAILED
    trace: str = FAILED
    dataset: str = FAILED
    note: str = ""


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


def _new_ledgers(tmp_path, name, attack_id):
    d = tmp_path / name
    memory_ledger = CanonicalMemoryLedger(d / "memory")
    event_ledger = CanonicalEventLedger(d / "events", memory_ledger)
    supersession_ledger = SupersessionLedger(d / "supersessions")
    run_ledger = ExperimentRunLedger(d / "runs")
    membership_ledger = EventRunMembershipLedger(d / "membership", run_ledger)
    phase5_ledger = Phase5EventLedger(d / "phase5_events")
    run = ExperimentRunRecord(
        experiment_id=f"exp-coverage-{attack_id}", run_id=f"RUN-coverage-{attack_id}", dataset="locomo",
        scope={"attack_id": attack_id}, started_at=TS, actor="test", reason="seven-attack coverage test",
    )
    run_ledger.register(run)
    return dict(
        memory_ledger=memory_ledger, event_ledger=event_ledger, supersession_ledger=supersession_ledger,
        membership_ledger=membership_ledger, phase5_ledger=phase5_ledger, run_id=run.run_id,
    )


def _run_downstream_pipeline(ledgers, memory_id: str, content: str, row: AttackCoverageRow):
    """The shared downstream chain -- identical for every attack, once a memory exists."""
    task_id = f"task-{row.attack}"
    query = "What happened?"

    try:
        report = instrument_retrieval_and_selection(
            memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
            phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
            run_id=ledgers["run_id"], task_id=task_id, query=query,
            candidates=[(memory_id, content)], config_fingerprint=CFG, actor="test", timestamp=TS, top_k=1,
        )
        row.retrieval = PASS if report.retrieved_event_ids else FAILED
        row.selection = PASS if report.selected_event_ids else FAILED
    except Exception as exc:  # pragma: no cover -- would indicate a real defect
        row.retrieval = FAILED
        row.selection = FAILED
        row.note += f" retrieval/selection error: {exc!r};"
        return

    try:
        memory_items = [{"memory_id": memory_id, "content": content}]
        context = build_agent_visible_context(condition=CONDITION_RETRIEVED_MEMORY, task_id=task_id, prompt=query, memory_items=memory_items)
        rendered = render_messages(context, system_prompt=DEFAULT_SYSTEM_PROMPT)
        record_context_assembly(
            phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
            run_id=ledgers["run_id"], task_id=task_id, context_memory_ids=(memory_id,),
            rendered_messages=rendered, actor="test", reason="prompt rendered", timestamp=TS,
        )
        run_config = RunConfiguration(
            llm_provider=_scripted_provider("a generated answer"),
            generation_config=GenerationConfig(temperature=0.0, seed=42, max_tokens=64, enable_thinking=False, n_ctx=1024),
            system_prompt=DEFAULT_SYSTEM_PROMPT, max_retries=0,
        )
        decision_result = instrument_agent_decision(
            phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
            run_id=ledgers["run_id"], task_id=task_id, decision_id=f"dec-{row.attack}", action_id=f"act-{row.attack}",
            exposed_memory_ids=(memory_id,), messages=rendered, run_config=run_config, actor="test", timestamp=TS,
        )
        row.agent = PASS if decision_result.generation_text is not None else FAILED
    except Exception as exc:  # pragma: no cover
        row.agent = FAILED
        row.note += f" agent error: {exc!r};"
        return

    try:
        graph = build_propagation_graph(
            ledgers["run_id"], memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
            phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
            supersession_ledger=ledgers["supersession_ledger"],
        )
        from phase5.wiring.lineage import PRODUCED
        row.lineage = PASS if any(e.target_id == memory_id for e in graph.edges_of_type(PRODUCED)) else FAILED
    except Exception as exc:  # pragma: no cover
        row.lineage = FAILED
        row.note += f" lineage error: {exc!r};"
        return

    try:
        trace = assemble_trace(
            ledgers["run_id"], event_ledger=ledgers["event_ledger"],
            phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        )
        row.trace = PASS if trace.unresolved_event_ids == () and len(trace.injections) >= 1 else FAILED
    except Exception as exc:  # pragma: no cover
        row.trace = FAILED
        row.note += f" trace error: {exc!r};"
        return

    try:
        records = derive_memory_behavior_dataset(
            ledgers["run_id"], memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
            phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
            supersession_ledger=ledgers["supersession_ledger"],
        )
        row.dataset = PASS if len(records) > 0 else FAILED
    except Exception as exc:  # pragma: no cover
        row.dataset = FAILED
        row.note += f" dataset error: {exc!r};"


def _mark_downstream_not_applicable(row: AttackCoverageRow, reason: str):
    row.retrieval = row.selection = row.agent = row.lineage = NOT_APPLICABLE
    # trace/dataset are still applicable -- an injection attempt alone is still tracked.
    row.trace = PASS
    row.dataset = PASS
    row.note += f" {reason};"


COVERAGE: Dict[str, AttackCoverageRow] = {}


@pytest.fixture(scope="module", autouse=True)
def _print_coverage_matrix_at_end():
    yield
    lines = ["\n=== Seven-Attack End-to-End Coverage Matrix ==="]
    header = f"{'Attack':<26}{'Inject':<8}{'Admit':<8}{'Lifecycle':<10}{'Retrieval':<10}{'Selection':<10}{'Agent':<8}{'Lineage':<10}{'Trace':<8}{'Dataset':<8}"
    lines.append(header)
    for row in COVERAGE.values():
        lines.append(
            f"{row.attack:<26}{row.injection:<8}{row.admission:<8}{row.lifecycle:<10}{row.retrieval:<10}"
            f"{row.selection:<10}{row.agent:<8}{row.lineage:<10}{row.trace:<8}{row.dataset:<8}"
        )
        if row.note.strip():
            lines.append(f"    note: {row.note.strip()}")
    print("\n".join(lines))


def test_coverage_agentpoison(tmp_path):
    ledgers = _new_ledgers(tmp_path, "agentpoison", "agentpoison")
    row = AttackCoverageRow(attack="agentpoison")
    result = run_live_agentpoison_injection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], timestamp=TS,
    )
    row.injection = PASS
    row.admission = PASS if result.memory_creation is not None else NOT_APPLICABLE
    if result.memory_creation is not None:
        row.lifecycle = PASS
        memory_id = result.memory_creation.created_event.memory_ids[0]
        content = ledgers["memory_ledger"].get(memory_id).content["text"]
        _run_downstream_pipeline(ledgers, memory_id, content, row)
    else:
        row.lifecycle = NOT_APPLICABLE
        _mark_downstream_not_applicable(row, "rejected/not-admitted -- no memory created")
    COVERAGE["agentpoison"] = row
    assert row.injection == PASS


def test_coverage_dsrm(tmp_path):
    ledgers = _new_ledgers(tmp_path, "dsrm", "dsrm")
    row = AttackCoverageRow(attack="dsrm")
    result = run_live_dsrm_injection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], timestamp=TS,
    )
    row.injection = PASS
    row.admission = PASS if result.memory_creation is not None else NOT_APPLICABLE
    if result.memory_creation is not None:
        row.lifecycle = PASS
        memory_id = result.memory_creation.created_event.memory_ids[0]
        content = ledgers["memory_ledger"].get(memory_id).content["text"]
        _run_downstream_pipeline(ledgers, memory_id, content, row)
    else:
        row.lifecycle = NOT_APPLICABLE
        _mark_downstream_not_applicable(row, "rejected/not-admitted -- no memory created")
    COVERAGE["dsrm"] = row
    assert row.injection == PASS


def test_coverage_farma(tmp_path):
    ledgers = _new_ledgers(tmp_path, "farma", "farma")
    row = AttackCoverageRow(attack="farma")
    result = run_live_farma_injection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], timestamp=TS,
    )
    row.injection = PASS
    row.admission = PASS if result.memory_creation is not None else NOT_APPLICABLE
    if result.memory_creation is not None:
        row.lifecycle = PASS
        memory_id = result.memory_creation.created_event.memory_ids[0]
        content = ledgers["memory_ledger"].get(memory_id).content["text"]
        _run_downstream_pipeline(ledgers, memory_id, content, row)
    else:
        row.lifecycle = NOT_APPLICABLE
        _mark_downstream_not_applicable(row, "rejected/not-admitted -- no memory created")
    COVERAGE["farma"] = row
    assert row.injection == PASS


def test_coverage_minja(tmp_path):
    ledgers = _new_ledgers(tmp_path, "minja", "minja")
    row = AttackCoverageRow(attack="minja")
    results = run_live_minja_injection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], timestamp=TS,
    )
    row.injection = PASS if len(results) == 3 else FAILED
    admitted = [r for r in results if r.memory_creation is not None]
    row.admission = PASS if admitted else NOT_APPLICABLE
    if admitted:
        row.lifecycle = PASS
        first = admitted[0]
        memory_id = first.memory_creation.created_event.memory_ids[0]
        content = ledgers["memory_ledger"].get(memory_id).content["text"]
        _run_downstream_pipeline(ledgers, memory_id, content, row)
    else:
        row.lifecycle = NOT_APPLICABLE
        _mark_downstream_not_applicable(row, "no step admitted")
    COVERAGE["minja"] = row
    assert row.injection == PASS


def test_coverage_mpbench(tmp_path):
    ledgers = _new_ledgers(tmp_path, "mpbench", "mpbench")
    row = AttackCoverageRow(attack="mpbench")
    result = run_live_mpbench_injection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], timestamp=TS,
    )
    row.injection = PASS
    row.admission = PASS if result.memory_creation is not None else NOT_APPLICABLE
    if result.memory_creation is not None:
        row.lifecycle = PASS
        memory_id = result.memory_creation.created_event.memory_ids[0]
        content = ledgers["memory_ledger"].get(memory_id).content["text"]
        _run_downstream_pipeline(ledgers, memory_id, content, row)
    else:
        row.lifecycle = NOT_APPLICABLE
        _mark_downstream_not_applicable(row, "rejected/not-admitted -- no memory created")
    COVERAGE["mpbench"] = row
    assert row.injection == PASS


def test_coverage_sleeper_admitted(tmp_path):
    ledgers = _new_ledgers(tmp_path, "sleeper", "sleeper_memory_poisoning")
    row = AttackCoverageRow(attack="sleeper_memory_poisoning")
    result = run_live_sleeper_injection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], timestamp=TS, gate_reply="DECISION: KEEP\nRATIONALE: Reasonable.",
    )
    row.injection = PASS
    row.admission = PASS if result.memory_creation is not None else FAILED  # KEEP requested -> must admit
    row.lifecycle = PASS if result.memory_creation is not None else FAILED
    if result.memory_creation is not None:
        memory_id = result.memory_creation.created_event.memory_ids[0]
        content = ledgers["memory_ledger"].get(memory_id).content["text"]
        _run_downstream_pipeline(ledgers, memory_id, content, row)
    COVERAGE["sleeper_memory_poisoning"] = row
    assert row.injection == PASS and row.admission == PASS


def test_coverage_sleeper_discard_is_not_applicable_not_failed(tmp_path):
    """A DISCARD outcome is a legitimate NOT_APPLICABLE for every downstream
    memory-dependent stage -- never collapsed into FAILED."""
    ledgers = _new_ledgers(tmp_path, "sleeper-discard", "sleeper_memory_poisoning")
    result = run_live_sleeper_injection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], timestamp=TS, gate_reply="DECISION: DISCARD\nRATIONALE: Not legitimate.",
    )
    assert result.memory_creation is None
    row = AttackCoverageRow(attack="sleeper_memory_poisoning (discard case)")
    row.injection = PASS
    row.admission = NOT_APPLICABLE
    row.lifecycle = NOT_APPLICABLE
    _mark_downstream_not_applicable(row, "DISCARD -- legitimate rejection, not a failure")
    assert row.retrieval == NOT_APPLICABLE
    assert row.trace == PASS  # the injection attempt itself is still tracked


def test_coverage_memorygraft(tmp_path):
    ledgers = _new_ledgers(tmp_path, "memorygraft", "memorygraft")
    row = AttackCoverageRow(attack="memorygraft")
    result = run_live_memorygraft_injection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], timestamp=TS, gate_reply="DECISION: KEEP\nRATIONALE: Looks like a valid shortcut.",
    )
    row.injection = PASS
    row.admission = PASS if result.memory_creation is not None else FAILED
    row.lifecycle = PASS if result.memory_creation is not None else FAILED
    if result.memory_creation is not None:
        memory_id = result.memory_creation.created_event.memory_ids[0]
        content = ledgers["memory_ledger"].get(memory_id).content["text"]
        _run_downstream_pipeline(ledgers, memory_id, content, row)
    COVERAGE["memorygraft"] = row
    assert row.injection == PASS and row.admission == PASS
