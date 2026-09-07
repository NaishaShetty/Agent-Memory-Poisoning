"""Phase 3.3-DATASET (selection-policy variant) -- the real, threshold-based
selection mechanism (`foundations/selection_policy.py`) wired into an actual agent
run, for the first time. `runner.py` itself is UNTOUCHED -- this is a sibling
module, same discipline as `gold_evidence_runner.py`: reuses
`generate_with_retries`/`render_messages`/the same boundary+leakage checks, adds a
new retrieval+selection path rather than editing the existing provisional one.

WHY A SEPARATE PATH, NOT A FLAG ON `run_agent_task()`
--------------------------------------------------------------------------------
`runner.py::select_from_retrieved()`'s own module docstring documents it as the
PROVISIONAL policy every currently-passing test and every already-executed real
campaign (including the frozen 120x2 dataset) depends on. Changing its behavior
in place would silently change what every existing real artifact represents.
This module produces a genuinely SEPARATE variant instead -- same reasoning layer,
same model/prompt/decoding (per `EVALUATION_CONTRACT.md`'s own requirement that only
the memory layer differ), different selection mechanism.

RETRIEVAL POOL SIZE
--------------------------------------------------------------------------------
Retrieves `RETRIEVAL_POOL_SIZE_N` (20, calibrated in `selection_policy.py`)
candidates instead of the provisional path's `top_k=5` -- this is the whole point:
`select_from_retrieved()`'s near-vacuity (retrieve and select both capped at 5) is
exactly what made `rejected` events structurally impossible before. Retrieving a
genuinely larger pool, then thresholding down, is what makes real rejection
possible for the first time.
"""

from __future__ import annotations

import time
from typing import Any, List, Mapping, Optional, Tuple

from phase3.evaluation.agent.conditions import CONDITION_RETRIEVED_MEMORY, build_agent_visible_context
from phase3.evaluation.agent.outcomes import (
    EXECUTION_STATUS_ERROR,
    EXECUTION_STATUS_SUCCESS,
    AgentExecutionResult,
)
from phase3.evaluation.agent_runtime.messages import render_messages
from phase3.evaluation.agent_runtime.runner import (
    AgentRunOutcome,
    AgentRuntimeLeakageError,
    AgentTaskInput,
    GenerationAttempt,
    RunConfiguration,
    _extract_content_text,
    _extract_memory_id,
    generate_with_retries,
)
from phase3.evaluation.contracts.boundary import AgentVisibilityViolation
from phase3.evaluation.foundations.adapter import (
    FOUNDATION_AVAILABLE,
    FOUNDATION_PARTIAL,
    MemoryFoundationAdapter,
)
from phase3.evaluation.foundations.selection_policy import (
    CALIBRATED_THRESHOLD_LOCOMO,
    RETRIEVAL_POOL_SIZE_N,
    SelectionResult,
    select_by_threshold,
)


def _retrieve_and_select_with_threshold(
    foundation: MemoryFoundationAdapter, task: AgentTaskInput, threshold: float,
) -> Tuple[Tuple[str, ...], Tuple[str, ...], Tuple[str, ...], List[Mapping[str, Any]], Optional[SelectionResult]]:
    """Returns (retrieved_ids, selected_ids, rejected_ids, memory_items_for_context,
    selection_result). `selection_result` is `None` iff retrieval itself was
    unavailable (nothing to select from) -- distinct from a `SelectionResult` with
    zero selected items, which is a real, meaningful "nothing cleared the bar"
    outcome, per `selection_policy.py`'s own explicit design (never fixed-k)."""
    retrieve_field = foundation.retrieve(task.retrieval_query, top_k=RETRIEVAL_POOL_SIZE_N)
    if retrieve_field.availability not in (FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL):
        return (), (), (), [], None

    raw_items = retrieve_field.value or []
    retrieved_ids = tuple(
        mid for mid in (_extract_memory_id(item) for item in raw_items) if mid is not None
    )

    candidates: List[Tuple[str, str]] = []
    content_by_id: Mapping[str, str] = {}
    for memory_id in retrieved_ids:
        inspect_field = foundation.inspect_memory(memory_id)
        if inspect_field.availability not in (FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL):
            continue
        content_text = _extract_content_text(inspect_field.value or {})
        candidates.append((memory_id, content_text))

    selection_result = select_by_threshold(task.prompt, candidates, threshold=threshold)
    selected_ids = tuple(c.memory_id for c in selection_result.selected)
    rejected_ids = tuple(c.memory_id for c in selection_result.rejected)
    memory_items = [{"memory_id": c.memory_id, "content": c.content} for c in selection_result.selected]

    return retrieved_ids, selected_ids, rejected_ids, memory_items, selection_result


def run_agent_task_with_selection_policy(
    task: AgentTaskInput,
    foundation: MemoryFoundationAdapter,
    config: RunConfiguration,
    threshold: float = CALIBRATED_THRESHOLD_LOCOMO,
) -> Tuple[AgentRunOutcome, Tuple[str, ...], Optional[SelectionResult]]:
    """Condition C sibling of `runner.py::run_agent_task()`, using the real
    threshold-based selection policy instead of the provisional identity-slice.
    Returns `(outcome, rejected_memory_ids, selection_result)` -- `rejected_memory_ids`
    and `selection_result` are the NEW information this path adds beyond what
    `AgentRunOutcome` itself carries (that dataclass has no `rejected` field, by
    design, since `runner.py`'s provisional policy never rejects anything).
    """
    t0 = time.time()

    if task.condition != CONDITION_RETRIEVED_MEMORY:
        raise ValueError(
            f"run_agent_task_with_selection_policy only supports condition="
            f"RETRIEVED_MEMORY; got {task.condition!r}."
        )

    identity = foundation.foundation_identity()
    foundation_identity_dict = {
        "foundation_id": identity.foundation_id, "foundation_name": identity.foundation_name,
        "adapter_version": identity.adapter_version, "status": identity.status,
    }

    retrieved_ids, selected_ids, rejected_ids, memory_items, selection_result = (
        _retrieve_and_select_with_threshold(foundation, task, threshold)
    )

    try:
        agent_visible_context = build_agent_visible_context(
            condition=task.condition, task_id=task.task_id, prompt=task.prompt, memory_items=memory_items,
        )
    except AgentVisibilityViolation as exc:
        raise AgentRuntimeLeakageError(
            f"Boundary check rejected the assembled agent-visible context: {exc}"
        ) from exc

    exposed_ids = tuple(
        item.get("memory_id") for item in agent_visible_context.get("memory_content", [])
        if isinstance(item, Mapping)
    )

    messages = render_messages(agent_visible_context, config.system_prompt)
    generation_text, attempts_tuple = generate_with_retries(messages, config)
    attempts: List[GenerationAttempt] = list(attempts_tuple)

    if generation_text is not None:
        execution_result = AgentExecutionResult(
            task_id=task.task_id, condition=task.condition, answer=generation_text,
            execution_status=EXECUTION_STATUS_SUCCESS, selected_memory_ids=selected_ids,
            used_memory_ids=None, execution_metadata={"attempts": len(attempts)},
        )
    else:
        execution_result = AgentExecutionResult(
            task_id=task.task_id, condition=task.condition, answer=None,
            execution_status=EXECUTION_STATUS_ERROR, selected_memory_ids=selected_ids,
            used_memory_ids=None,
            execution_metadata={"attempts": len(attempts), "last_error": attempts[-1].error if attempts else None},
        )

    outcome = AgentRunOutcome(
        task_id=task.task_id, condition=task.condition, memory_available=True,
        retrieved_memory_ids=retrieved_ids, selected_memory_ids=selected_ids, exposed_memory_ids=exposed_ids,
        agent_visible_context=agent_visible_context, execution_result=execution_result,
        attempts=tuple(attempts),
        generation_config_fingerprint=config.llm_provider.configuration_fingerprint(config.generation_config),
        model_metadata=config.llm_provider.model_metadata(), total_latency_sec=time.time() - t0,
        foundation_identity=foundation_identity_dict,
    )
    return outcome, rejected_ids, selection_result


__all__ = ["run_agent_task_with_selection_policy"]
