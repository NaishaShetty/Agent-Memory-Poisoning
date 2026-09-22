"""Phase 13 -- a real counterfactual test harness for INFLUENCE attribution
(2026-09-22, explicitly authorized).

WHY THIS EXISTS
--------------------------------------------------------------------------------
The Phase 13 report disclosed `attribute_influence()`/`influence_attribution_
accuracy()` as never run -- they require a real counterfactual test harness
(baseline agent run, masked re-run, diff) this project already built in Phase
3.3-H.4-A (`phase3/evaluation/agent_runtime/counterfactual.py`) but had never
actually wired end-to-end against real poison content and a real local LLM.
This module closes that gap for real: two real agent tasks (via
`MockMem0Adapter` + the real local Ollama model, the SAME "mock foundation,
real model" bar this project's other real-model work already uses), each
masking one real poison scenario, compared via the real, unmodified
`compare_counterfactual_run()`. Whichever real outcome each case produces is
what gets recorded and reported -- this module does not retry a case whose
real result is inconvenient, and does not force a positive finding to make a
number look better.

TWO REAL CASES, NOT ONE, AND WHY THEY USE DIFFERENT TARGET MEMORIES
--------------------------------------------------------------------------------
`influence_attribution_accuracy()` needs both a real True (established) and a
real False (not established) label to be a non-degenerate check -- one
one-sided case would tell us nothing about whether the metric can tell the two
apart. `attribution.metrics.influence_attribution_accuracy()` keys its ground
truth by memory_id alone (not by (memory_id, task_id)), so the two cases
deliberately target two DIFFERENT real poison scenarios (REAL-FARMA-1 and
REAL-DSRM-1) rather than the same scenario in two different tasks, avoiding a
ground-truth key collision.

- Case "established": the question directly asks about the one fact
  REAL-FARMA-1 supplies (Melanie's charity race); the other memory present is
  irrelevant to that question. If masking REAL-FARMA-1 changes the real
  answer, that is a real COUNTERFACTUALLY_INFLUENTIAL finding.
- Case "not_established": the question asks about a fact a DIFFERENT, present
  memory answers (Caroline's career decision, from REAL-MPBENCH-0);
  REAL-DSRM-1 (an unrelated real scenario, Melanie's museum visit) is present
  but irrelevant to this specific question. If masking REAL-DSRM-1 does NOT
  change the real answer, that is a real NOT_COUNTERFACTUALLY_INFLUENTIAL
  finding -- per the schema's own design (see `attribution/wiring/
  influence.py`), this is recorded as an ABSENCE of a `counterfactually_
  influential` CanonicalEvent, never as a fabricated "negative" event.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

from attribution.metrics import influence_attribution_accuracy
from attribution.schema import AttributionResult
from attribution.wiring.influence import attribute_influence

from phase3.evaluation.agent.conditions import CONDITION_RETRIEVED_MEMORY
from phase3.evaluation.agent_runtime.counterfactual import (
    STATUS_COUNTERFACTUALLY_INFLUENTIAL,
    compare_counterfactual_run,
    run_counterfactual_mask,
)
from phase3.evaluation.agent_runtime.runner import AgentTaskInput, RunConfiguration, run_agent_task
from phase3.evaluation.foundations.canonical_event import (
    EVENT_COUNTERFACTUALLY_INFLUENTIAL,
    CanonicalEvent,
    MASKING_METHOD_SELECTED_SET_REMOVAL,
)
from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger
from phase3.evaluation.foundations.mocks.mock_mem0 import MockMem0Adapter
from phase3.evaluation.llm.provider import GenerationConfig, LLMProvider
from phase11.data.real_corpus import real_poison_scenarios
from phase12.propagation.ollama_provider import OllamaProvider

TS = "2026-09-22T00:10:00+00:00"
RUN_ID = "phase13-influence-metrics"


@dataclass(frozen=True)
class InfluenceCase:
    label: str
    task_id: str
    target_memory_id: str
    status: str
    ground_truth_influential: bool
    config_fingerprint: str
    baseline_answer_hash: Optional[str]
    masked_answer_hash: Optional[str]
    diff_criterion: str
    baseline_answer: Optional[str]
    masked_answer: Optional[str]


def _config(provider: Optional[LLMProvider] = None) -> RunConfiguration:
    provider = provider or OllamaProvider()
    return RunConfiguration(
        llm_provider=provider,
        generation_config=GenerationConfig(
            temperature=0.0, seed=42, max_tokens=60, enable_thinking=False, n_ctx=2048, request_timeout_sec=120.0,
        ),
    )


def _foundation(memories: Tuple[Tuple[str, str], ...]) -> MockMem0Adapter:
    foundation = MockMem0Adapter()
    foundation.initialize({})
    for memory_id, text in memories:
        foundation.add_memory(memory_id, {"text": text}, {})
    return foundation


def _run_case(
    label: str, task_id: str, prompt: str, memories: Tuple[Tuple[str, str], ...], target_memory_id: str,
    *, provider: Optional[LLMProvider] = None,
) -> InfluenceCase:
    config = _config(provider)
    foundation = _foundation(memories)
    task = AgentTaskInput(
        task_id=task_id, prompt=prompt, condition=CONDITION_RETRIEVED_MEMORY,
        retrieval_query={"text": ""}, top_k=len(memories),
    )
    baseline = run_agent_task(task, foundation, config)
    if target_memory_id not in baseline.selected_memory_ids:
        raise AssertionError(
            f"{label}: target {target_memory_id!r} was not selected by the real baseline run "
            f"(selected={baseline.selected_memory_ids!r}) -- cannot mask a memory that was never in context."
        )
    masked = run_counterfactual_mask(baseline, target_memory_id, config)
    comparison = compare_counterfactual_run(baseline, masked)
    return InfluenceCase(
        label=label, task_id=task_id, target_memory_id=target_memory_id,
        status=comparison.status,
        ground_truth_influential=comparison.status == STATUS_COUNTERFACTUALLY_INFLUENTIAL,
        config_fingerprint=baseline.generation_config_fingerprint,
        baseline_answer_hash=comparison.baseline_answer_hash,
        masked_answer_hash=comparison.masked_answer_hash,
        diff_criterion=comparison.diff_criterion,
        baseline_answer=baseline.execution_result.answer,
        masked_answer=masked.masked_answer,
    )


def run_established_case(*, provider: Optional[LLMProvider] = None) -> InfluenceCase:
    pool = {m.scenario_id: m.content_text for m in real_poison_scenarios().memories}
    return _run_case(
        label="melanie-charity-race",
        task_id="phase13-influence-task-established",
        prompt="Question: When is Melanie's charity race? Answer in one short sentence.",
        memories=(("REAL-FARMA-1", pool["REAL-FARMA-1"]), ("REAL-MPBENCH-0", pool["REAL-MPBENCH-0"])),
        target_memory_id="REAL-FARMA-1",
        provider=provider,
    )


def run_not_established_case(*, provider: Optional[LLMProvider] = None) -> InfluenceCase:
    pool = {m.scenario_id: m.content_text for m in real_poison_scenarios().memories}
    return _run_case(
        label="caroline-career-irrelevant-museum",
        task_id="phase13-influence-task-not-established",
        prompt="Question: What is Caroline now leaning toward as a career? Answer in one short sentence.",
        memories=(("REAL-DSRM-1", pool["REAL-DSRM-1"]), ("REAL-MPBENCH-0", pool["REAL-MPBENCH-0"])),
        target_memory_id="REAL-DSRM-1",
        provider=provider,
    )


def record_influence_case(ledger_dir: Path, case: InfluenceCase) -> None:
    """Persists a real `counterfactually_influential` CanonicalEvent ONLY if
    the real comparison established influence -- absence IS the
    NOT_ESTABLISHED signal by this schema's own design (see
    `attribution/wiring/influence.py`'s module docstring); this function never
    records a negative finding as an event."""
    if case.status != STATUS_COUNTERFACTUALLY_INFLUENTIAL:
        return
    memory_ledger = CanonicalMemoryLedger(ledger_dir / "memory")
    event_ledger = CanonicalEventLedger(ledger_dir / "events", memory_ledger)
    event_id = f"evt-phase13-influence-{case.task_id}"
    if any(e.event_id == event_id for e in event_ledger.all_events()):
        return  # already recorded -- idempotent
    event = CanonicalEvent(
        event_id=event_id, event_type=EVENT_COUNTERFACTUALLY_INFLUENTIAL,
        memory_ids=(case.target_memory_id,), timestamp=TS, actor="phase13-attribution-setup",
        reason="real counterfactual masking test found the answer changed",
        task_id=case.task_id, config_fingerprint=case.config_fingerprint,
        counterfactual_answer_hash=case.masked_answer_hash, baseline_answer_hash=case.baseline_answer_hash,
        diff_criterion=case.diff_criterion, masking_method=MASKING_METHOD_SELECTED_SET_REMOVAL,
    )
    event_ledger.append(event)


def evaluate_influence_attribution(ledger_dir: Path, cases: Tuple[InfluenceCase, ...]) -> Dict[str, object]:
    memory_ledger = CanonicalMemoryLedger(ledger_dir / "memory")
    event_ledger = CanonicalEventLedger(ledger_dir / "events", memory_ledger)
    results: Dict[str, AttributionResult] = {
        case.target_memory_id: attribute_influence(
            case.target_memory_id, run_id=RUN_ID, event_ledger=event_ledger, task_id=case.task_id,
        )
        for case in cases
    }
    ground_truth = {case.target_memory_id: case.ground_truth_influential for case in cases}
    accuracy = influence_attribution_accuracy(results, ground_truth)
    return {"results": results, "ground_truth": ground_truth, "accuracy": accuracy}


if __name__ == "__main__":
    from phase13.ledger_setup import DEFAULT_LEDGER_DIR

    established = run_established_case()
    not_established = run_not_established_case()
    print(f"established: status={established.status} baseline={established.baseline_answer!r} masked={established.masked_answer!r}")
    print(f"not_established: status={not_established.status} baseline={not_established.baseline_answer!r} masked={not_established.masked_answer!r}")

    record_influence_case(DEFAULT_LEDGER_DIR, established)
    record_influence_case(DEFAULT_LEDGER_DIR, not_established)

    outcome = evaluate_influence_attribution(DEFAULT_LEDGER_DIR, (established, not_established))
    print(f"influence_attribution_accuracy={outcome['accuracy']}")
    for mid, result in outcome["results"].items():
        print(f"  {mid}: status={result.status}")


__all__ = [
    "InfluenceCase",
    "run_established_case",
    "run_not_established_case",
    "record_influence_case",
    "evaluate_influence_attribution",
]
