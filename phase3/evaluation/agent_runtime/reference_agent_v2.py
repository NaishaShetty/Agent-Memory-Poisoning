"""Phase 3.3-DATASET (agent V2 candidate) -- a bounded, reproducible upgrade to the
reference agent, per the user's explicit spec:

    retrieval -> benchmark-owned selection -> bounded reasoning ->
    optional ONE-TIME retrieval refinement -> final answer

plus explicit logging of retrieved/selected/considered/used memories, a small
bounded retry/self-correction step, and structured internal state.

EXPLICITLY OUT OF SCOPE (per the user's own instruction, enforced by construction)
--------------------------------------------------------------------------------
- No tools, no function-calling, no external actions of any kind.
- No open-ended loop -- refinement fires AT MOST ONCE per task, structurally (a
  `while` loop cannot iterate here; the code path is a fixed if/else, not a loop).
- No multi-agent behavior -- one reasoning model, one system prompt, throughout.
- No new nondeterminism -- the refinement TRIGGER is a literal-phrase check on the
  first answer (same substring-check discipline `citation.py` already established
  for "used" detection), never an LLM judgment call about whether to refine.

RELATIONSHIP TO V1 (`runner.py::run_agent_task()`)
--------------------------------------------------------------------------------
V1 is completely untouched. This is a genuinely separate module, reusing V1's own
building blocks (`generate_with_retries`, `render_messages`, the same boundary/
leakage checks) rather than replacing or wrapping it. Per the user's own framing,
this is a CANDIDATE -- see `agent_v2_qualification.py` for the separate, explicit
V1-vs-V2 qualification comparison. V2 becomes canonical only if that qualification
demonstrates a real improvement; until then V1 remains the baseline every existing
real campaign and the frozen dataset already used.

WHY SELECTION IS "BENCHMARK-OWNED" HERE, NOT V1's PROVISIONAL POLICY
--------------------------------------------------------------------------------
Reuses `foundations/selection_policy.py`'s real, calibrated threshold mechanism
(`select_by_threshold`, `CALIBRATED_THRESHOLD_LOCOMO`) -- the same mechanism
`selection_policy_runner.py` already proved works at full real scale (120x2,
2,937 real `rejected` events). V2 does not invent a second selection mechanism.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, List, Mapping, Optional, Tuple

from phase3.evaluation.agent.conditions import CONDITION_RETRIEVED_MEMORY, build_agent_visible_context
from phase3.evaluation.agent.outcomes import (
    EXECUTION_STATUS_ERROR,
    EXECUTION_STATUS_SUCCESS,
    AgentExecutionResult,
)
from phase3.evaluation.agent_runtime.citation import CitationDiagnostic, classify_citation_based_usage
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

# Deterministic, literal-phrase check for "the answer signals insufficient
# information" -- same substring-only discipline `citation.py` already uses for
# "used" detection, never a semantic/LLM judgment. Disclosed here as exactly what
# it is: a fixed, small, case-insensitive phrase list, not a claim of true
# understanding of insufficiency.
INSUFFICIENT_INFO_PHRASES: Tuple[str, ...] = (
    "i don't know", "i do not know", "cannot determine", "can't determine",
    "no information", "not mentioned", "unable to answer", "not enough information",
    "unclear from", "not specified", "no mention", "does not mention",
    "doesn't mention", "don't have information", "do not have information",
    "cannot provide", "can't provide", "no relevant information",
    "not provide any relevant", "cannot be answered", "can't be answered",
)  # Phase 3.3-DATASET real pilot (agent_v2_real_pilot_results.json) found the
   # original list missed real model phrasings ("does not mention", "don't have
   # information") -- widened from REAL observed output, not guessed in advance.

MAX_REFINEMENT_ATTEMPTS = 1  # structurally bounded -- never a loop


def _signals_insufficient_information(answer: Optional[str]) -> bool:
    if not answer:
        return False
    lowered = answer.lower()
    return any(phrase in lowered for phrase in INSUFFICIENT_INFO_PHRASES)


def _retrieve_and_select(
    foundation: MemoryFoundationAdapter, retrieval_query: Mapping[str, Any], prompt: str, threshold: float,
) -> Tuple[Tuple[str, ...], List[Mapping[str, Any]], Optional[SelectionResult]]:
    """One retrieval+selection pass. Returns (retrieved_ids, memory_items_for_context,
    selection_result)."""
    retrieve_field = foundation.retrieve(retrieval_query, top_k=RETRIEVAL_POOL_SIZE_N)
    if retrieve_field.availability not in (FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL):
        return (), [], None

    raw_items = retrieve_field.value or []
    retrieved_ids = tuple(
        mid for mid in (_extract_memory_id(item) for item in raw_items) if mid is not None
    )

    candidates: List[Tuple[str, str]] = []
    for memory_id in retrieved_ids:
        inspect_field = foundation.inspect_memory(memory_id)
        if inspect_field.availability not in (FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL):
            continue
        candidates.append((memory_id, _extract_content_text(inspect_field.value or {})))

    selection_result = select_by_threshold(prompt, candidates, threshold=threshold)
    memory_items = [{"memory_id": c.memory_id, "content": c.content} for c in selection_result.selected]
    return retrieved_ids, memory_items, selection_result


@dataclass(frozen=True)
class AgentV2RunState:
    """Structured internal state -- every stage of the bounded pipeline, explicit
    and inspectable, never collapsed into just a final answer. This is the
    concrete answer to "explicit logging of which memories were retrieved,
    selected, considered, and actually used":

    - `initial_retrieved_ids` / `initial_selected_ids`: first retrieval+selection pass.
    - `refinement_triggered`: whether the bounded, one-time refinement fired.
    - `refinement_reason`: the literal insufficiency phrase(s) that triggered it, or None.
    - `refinement_query`: the refined retrieval query actually used, or None.
    - `refinement_retrieved_ids` / `refinement_selected_ids`: the refinement pass's own
      retrieval+selection, or empty tuples if refinement never fired.
    - `considered_memory_ids`: the UNION of every memory id ever placed in the agent's
      visible context across BOTH passes -- "considered" means "the agent was shown
      this," nothing stronger.
    - `used_memory_ids`: `classify_citation_based_usage()`'s real, honest,
      citation-presence-only signal (never a causal-usage claim -- see that
      module's own docstring), computed against the FINAL answer and
      `considered_memory_ids`.
    - `attempts`: every real generation attempt across both passes, in order.
    """

    initial_retrieved_ids: Tuple[str, ...]
    initial_selected_ids: Tuple[str, ...]
    initial_answer: Optional[str]
    refinement_triggered: bool
    refinement_reason: Optional[str]
    refinement_query: Optional[Mapping[str, Any]]
    refinement_retrieved_ids: Tuple[str, ...]
    refinement_selected_ids: Tuple[str, ...]
    considered_memory_ids: Tuple[str, ...]
    used_memory_ids: Optional[Tuple[str, ...]]
    citation_diagnostic: Optional[CitationDiagnostic]
    attempts: Tuple[GenerationAttempt, ...]
    final_answer: Optional[str]


def run_agent_task_v2(
    task: AgentTaskInput,
    foundation: MemoryFoundationAdapter,
    config: RunConfiguration,
    threshold: float = CALIBRATED_THRESHOLD_LOCOMO,
) -> Tuple[AgentRunOutcome, AgentV2RunState]:
    """The bounded V2 pipeline. Returns `(outcome, state)` -- `outcome` is
    `AgentRunOutcome`-shaped (same contract every other condition/trace-assembly
    function already consumes, so `evaluate_and_trace(_with_identity)` work
    unmodified against it); `state` is the full `AgentV2RunState` for anything
    that needs the richer, stage-by-stage detail V1's outcome shape cannot carry.
    """
    t0 = time.time()

    if task.condition != CONDITION_RETRIEVED_MEMORY:
        raise ValueError(f"run_agent_task_v2 only supports condition=RETRIEVED_MEMORY; got {task.condition!r}.")

    identity = foundation.foundation_identity()
    foundation_identity_dict = {
        "foundation_id": identity.foundation_id, "foundation_name": identity.foundation_name,
        "adapter_version": identity.adapter_version, "status": identity.status,
    }

    # --- Pass 1: retrieval -> benchmark-owned selection -> bounded reasoning ---
    retrieved_1, memory_items_1, selection_1 = _retrieve_and_select(
        foundation, task.retrieval_query, task.prompt, threshold
    )
    try:
        context_1 = build_agent_visible_context(
            condition=task.condition, task_id=task.task_id, prompt=task.prompt, memory_items=memory_items_1,
        )
    except AgentVisibilityViolation as exc:
        raise AgentRuntimeLeakageError(f"Boundary check rejected pass-1 context: {exc}") from exc

    messages_1 = render_messages(context_1, config.system_prompt)
    answer_1, attempts_1 = generate_with_retries(messages_1, config)
    all_attempts: List[GenerationAttempt] = list(attempts_1)

    selected_1 = tuple(c.memory_id for c in selection_1.selected) if selection_1 else ()
    considered = set(item["memory_id"] for item in memory_items_1)

    # --- Optional, structurally bounded (max 1) retrieval refinement ---
    refinement_triggered = False
    refinement_reason = None
    refinement_query = None
    retrieved_2: Tuple[str, ...] = ()
    selected_2: Tuple[str, ...] = ()
    final_answer = answer_1
    final_context = context_1

    if _signals_insufficient_information(answer_1):
        matched = [p for p in INSUFFICIENT_INFO_PHRASES if p in (answer_1 or "").lower()]
        refinement_triggered = True
        refinement_reason = matched[0] if matched else None

        # Refined query: same retrieval_query, widened with the task prompt itself
        # as explicit additional query text -- a deterministic, disclosed widening
        # (not a second LLM call to "decide" how to refine), bounded to exactly
        # this one refinement.
        base_query = dict(task.retrieval_query or {})
        refined_text = f"{base_query.get('text', '')} {task.prompt}".strip()
        refinement_query = {**base_query, "text": refined_text}

        retrieved_2, memory_items_2, selection_2 = _retrieve_and_select(
            foundation, refinement_query, task.prompt, threshold
        )
        selected_2 = tuple(c.memory_id for c in selection_2.selected) if selection_2 else ()
        considered |= set(item["memory_id"] for item in memory_items_2)

        # Union memory_content for the refined context: pass-1 selection PLUS
        # anything new pass-2 surfaced -- never drops what pass 1 already found.
        merged_items_by_id = {item["memory_id"]: item for item in memory_items_1}
        merged_items_by_id.update({item["memory_id"]: item for item in memory_items_2})
        try:
            final_context = build_agent_visible_context(
                condition=task.condition, task_id=task.task_id, prompt=task.prompt,
                memory_items=list(merged_items_by_id.values()),
            )
        except AgentVisibilityViolation as exc:
            raise AgentRuntimeLeakageError(f"Boundary check rejected pass-2 (refinement) context: {exc}") from exc

        messages_2 = render_messages(final_context, config.system_prompt)
        answer_2, attempts_2 = generate_with_retries(messages_2, config)
        all_attempts.extend(attempts_2)
        final_answer = answer_2 if answer_2 is not None else answer_1

    exposed_ids = tuple(
        item.get("memory_id") for item in final_context.get("memory_content", [])
        if isinstance(item, Mapping)
    )
    citation = classify_citation_based_usage(final_answer, exposed_ids) if final_answer is not None else None

    if final_answer is not None:
        execution_result = AgentExecutionResult(
            task_id=task.task_id, condition=task.condition, answer=final_answer,
            execution_status=EXECUTION_STATUS_SUCCESS,
            selected_memory_ids=selected_2 if refinement_triggered else selected_1,
            used_memory_ids=citation.cited_memory_ids if citation else None,
            execution_metadata={"attempts": len(all_attempts), "refinement_triggered": refinement_triggered},
        )
    else:
        execution_result = AgentExecutionResult(
            task_id=task.task_id, condition=task.condition, answer=None,
            execution_status=EXECUTION_STATUS_ERROR,
            selected_memory_ids=selected_2 if refinement_triggered else selected_1,
            used_memory_ids=None,
            execution_metadata={
                "attempts": len(all_attempts), "refinement_triggered": refinement_triggered,
                "last_error": all_attempts[-1].error if all_attempts else None,
            },
        )

    outcome = AgentRunOutcome(
        task_id=task.task_id, condition=task.condition, memory_available=True,
        retrieved_memory_ids=retrieved_2 if refinement_triggered else retrieved_1,
        selected_memory_ids=execution_result.selected_memory_ids, exposed_memory_ids=exposed_ids,
        agent_visible_context=final_context, execution_result=execution_result,
        attempts=tuple(all_attempts),
        generation_config_fingerprint=config.llm_provider.configuration_fingerprint(config.generation_config),
        model_metadata=config.llm_provider.model_metadata(), total_latency_sec=time.time() - t0,
        foundation_identity=foundation_identity_dict,
    )

    state = AgentV2RunState(
        initial_retrieved_ids=retrieved_1, initial_selected_ids=selected_1, initial_answer=answer_1,
        refinement_triggered=refinement_triggered, refinement_reason=refinement_reason,
        refinement_query=refinement_query, refinement_retrieved_ids=retrieved_2, refinement_selected_ids=selected_2,
        considered_memory_ids=tuple(sorted(considered)),
        used_memory_ids=citation.cited_memory_ids if citation else None,
        citation_diagnostic=citation, attempts=tuple(all_attempts), final_answer=final_answer,
    )

    return outcome, state


__all__ = [
    "INSUFFICIENT_INFO_PHRASES",
    "MAX_REFINEMENT_ATTEMPTS",
    "AgentV2RunState",
    "run_agent_task_v2",
]
