"""Phase 3.3-DATASET -- real execution of Condition B (GOLD_EVIDENCE) per
`EVALUATION_CONTRACT.md` sections 5-6.

WHY THIS IS A SEPARATE MODULE, NOT AN EXTENSION OF `runner.py`
--------------------------------------------------------------------------------
`runner.py::AgentTaskInput.__post_init__()` deliberately raises if
`condition == CONDITION_GOLD_EVIDENCE`, with an explicit comment: "GOLD_EVIDENCE is
deliberately excluded here -- it is an evaluator-side control condition, never
something the agent runtime assembles from a foundation." That design is correct and
is NOT changed here -- `runner.py` stays exactly as-is (zero lines touched). This
module is the evaluator-side counterpart the comment refers to: it builds the same
kind of `AgentRunOutcome` `runner.py` produces, using the SAME reusable primitives
(`generate_with_retries`, `render_messages`, `build_agent_visible_context`, the same
boundary/leakage checks), but for a payload built directly from gold evidence CONTENT
supplied by the caller -- never from a foundation's `retrieve()`/`inspect_memory()`.

WHAT MAKES THIS "CONDITION B" AND NOT A LEAK
--------------------------------------------------------------------------------
Per `agent/conditions.py`'s own `CONDITION_GOLD_EVIDENCE` docstring and
`agent/dataset_adapter.py::build_agent_visible_context_for_case()`'s established
precedent (reused here, not reimplemented): gold evidence CONTENT is legitimately
agent-visible under this condition, by design -- what must never leak is the literal
benchmark `gold_evidence_id` string. Every evidence item handed to the agent is
re-keyed under an opaque `"evidence-slot-{n}"` id before assembly, exactly matching
`dataset_adapter.py`'s existing convention, so no evaluator-only identifier ever
reaches `agent_visible_context`.

NO FOUNDATION INVOLVEMENT, BY CONSTRUCTION
--------------------------------------------------------------------------------
Per `EVALUATION_CONTRACT.md` section 5, Condition B hands evidence content directly,
skipping retrieval and selection entirely -- there is no foundation call in this
module at all. `retrieved_memory_ids`/`selected_memory_ids` on the returned outcome
are therefore always empty tuples, and `foundation_identity` is always `None` --
never fabricated, never copied from a sibling condition's real foundation state.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import List, Mapping, Optional, Sequence, Tuple

from phase3.evaluation.agent.conditions import CONDITION_GOLD_EVIDENCE, build_agent_visible_context
from phase3.evaluation.agent.outcomes import (
    EXECUTION_STATUS_ERROR,
    EXECUTION_STATUS_SUCCESS,
    AgentExecutionResult,
)
from phase3.evaluation.agent_runtime.messages import render_messages
from phase3.evaluation.agent_runtime.runner import (
    AgentRunOutcome,
    GenerationAttempt,
    RunConfiguration,
    generate_with_retries,
)
from phase3.evaluation.contracts.boundary import AgentVisibilityViolation


class GoldEvidenceRuntimeLeakageError(RuntimeError):
    """Same two-check discipline as `runner.py::AgentRuntimeLeakageError` (boundary
    check, then structural leakage check) -- see that class's docstring."""


@dataclass(frozen=True)
class GoldEvidenceTaskInput:
    """Everything `run_gold_evidence_task()` needs. Structurally carries no
    `expected_answer` field -- the evaluator supplies gold ANSWER separately, after
    execution, exactly as `runner.py::AgentTaskInput` does for the other conditions.

    `evidence_items` is `[{"gold_evidence_id": ..., "content": ...}, ...]` -- the
    CALLER's job to have already looked up real content for each gold evidence id
    (e.g. from a pool's ingested raw rows); this module performs no dataset I/O. The
    literal `gold_evidence_id` values here are used ONLY to preserve caller-side
    traceability in the returned outcome's `execution_metadata` -- they are never
    written into `agent_visible_context` (see module docstring).
    """

    task_id: str
    prompt: str
    evidence_items: Sequence[Mapping[str, str]]


def run_gold_evidence_task(
    task: GoldEvidenceTaskInput,
    config: RunConfiguration,
) -> AgentRunOutcome:
    """Condition B (GOLD_EVIDENCE) sibling of `runner.py::run_agent_task()`. Same
    generation call, same system prompt, same `RunConfiguration` -- so a Condition A/B/C
    comparison for one task is genuinely "identical model/prompt/decoding," differing
    only in what memory content (if any) is present, per `EVALUATION_CONTRACT.md`
    section 5's own requirement.
    """
    t0 = time.time()

    memory_items = [
        {"memory_id": f"evidence-slot-{idx + 1}", "content": item["content"]}
        for idx, item in enumerate(task.evidence_items)
        if item.get("content") is not None
    ]

    try:
        agent_visible_context = build_agent_visible_context(
            condition=CONDITION_GOLD_EVIDENCE,
            task_id=task.task_id,
            prompt=task.prompt,
            memory_items=memory_items,
        )
    except AgentVisibilityViolation as exc:
        raise GoldEvidenceRuntimeLeakageError(
            f"Boundary check rejected the assembled agent-visible context: {exc}"
        ) from exc

    exposed_ids = tuple(item["memory_id"] for item in memory_items)

    messages = render_messages(agent_visible_context, config.system_prompt)

    generation_text, attempts_tuple = generate_with_retries(messages, config)
    attempts: List[GenerationAttempt] = list(attempts_tuple)

    if generation_text is not None:
        execution_result = AgentExecutionResult(
            task_id=task.task_id,
            condition=CONDITION_GOLD_EVIDENCE,
            answer=generation_text,
            execution_status=EXECUTION_STATUS_SUCCESS,
            selected_memory_ids=(),
            used_memory_ids=None,
            execution_metadata={
                "attempts": len(attempts),
                "gold_evidence_ids_supplied": [
                    item.get("gold_evidence_id") for item in task.evidence_items
                ],
            },
        )
    else:
        execution_result = AgentExecutionResult(
            task_id=task.task_id,
            condition=CONDITION_GOLD_EVIDENCE,
            answer=None,
            execution_status=EXECUTION_STATUS_ERROR,
            selected_memory_ids=(),
            used_memory_ids=None,
            execution_metadata={
                "attempts": len(attempts),
                "last_error": attempts[-1].error if attempts else None,
            },
        )

    return AgentRunOutcome(
        task_id=task.task_id,
        condition=CONDITION_GOLD_EVIDENCE,
        memory_available=True,
        retrieved_memory_ids=(),
        selected_memory_ids=(),
        exposed_memory_ids=exposed_ids,
        agent_visible_context=agent_visible_context,
        execution_result=execution_result,
        attempts=tuple(attempts),
        generation_config_fingerprint=config.llm_provider.configuration_fingerprint(
            config.generation_config
        ),
        model_metadata=config.llm_provider.model_metadata(),
        total_latency_sec=time.time() - t0,
        foundation_identity=None,
    )


__all__ = [
    "GoldEvidenceRuntimeLeakageError",
    "GoldEvidenceTaskInput",
    "run_gold_evidence_task",
]
