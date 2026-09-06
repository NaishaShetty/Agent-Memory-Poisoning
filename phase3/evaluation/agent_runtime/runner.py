"""Phase 3.3-B -- the canonical clean-baseline agent loop
(`PHASE3_3_EXPERIMENTAL_SPEC.md` Part 7):

    Task -> Task interpretation -> Memory availability -> Memory retrieval ->
    Memory selection -> Agent-visible context -> LLM generation -> Answer

Evaluation, failure classification, and trace assembly happen OUTSIDE this module (see
`trace.py`) -- per the mission's explicit "the evaluator must remain outside the agent"
requirement, `run_agent_task()` below has NO parameter shaped like a gold answer, gold
evidence id list, evaluator result, hidden label, or failure classification. This is
enforced by construction: read the signature of `AgentTaskInput` and `run_agent_task()`
below and confirm there is nothing there to leak, the same way
`phase3/evaluation/contracts/boundary.py::validate_agent_visible()`'s signature has no
`evaluator_reference` parameter for the same structural reason.

SELECTION POLICY (explicitly PROVISIONAL, not a frozen algorithm)
--------------------------------------------------------------------------------
`PHASE3_CLEAN_AGENT_FOUNDATION_SPEC.md` section 30 and `CLEAN_AGENT_INTERFACES.md`
section 3 both leave the exact candidate-discovery/reranking/selection algorithm
unfrozen -- "not yet built" per LoCoMo's own dataset profile
(`condition_support.RETRIEVED_MEMORY.status: SUPPORTED_WITH_ADAPTER`). This module's
selection policy is therefore documented here, plainly, as the SIMPLEST policy that lets
the pilot exercise the full RETRIEVED_MEMORY condition end-to-end: select every retrieved
memory id, in the foundation's own returned order, up to `top_k`. No reranking, no
relevance thresholding. Any future 3.3-C+ stage that wants a smarter selection policy
replaces `select_from_retrieved()` below -- it does not need to touch anything else in
this module, the evaluator, or the trace schema.

MEMORY USAGE IS NOT OBSERVABLE HERE, HONESTLY
--------------------------------------------------------------------------------
`AgentExecutionResult.used_memory_ids` is left `None` (never fabricated as an empty
tuple, which would falsely claim "observed and unused" -- see
`agent/outcomes.py`'s own documented distinction) because this runtime has no
attribution mechanism telling it which selected memory, if any, the LLM's answer
actually drew on. `agent.diagnostics.classify_retrieval_utilization()` already handles
this case correctly (`STATUS_UNDEFINED_USAGE_NOT_OBSERVABLE`), and
`foundations.lifecycle.build_lifecycle_trace()` already stops at `MEMORY_EXPOSED` when
usage is unknown -- both are reused verbatim, unmodified, exactly for this reason.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, List, Mapping, Optional, Sequence, Tuple

from phase3.evaluation.agent.conditions import (
    CONDITION_NO_MEMORY,
    CONDITION_RETRIEVED_MEMORY,
    build_agent_visible_context,
)
from phase3.evaluation.agent.outcomes import (
    EXECUTION_STATUS_ERROR,
    EXECUTION_STATUS_SUCCESS,
    AgentExecutionResult,
)
from phase3.evaluation.contracts.boundary import AgentVisibilityViolation
from phase3.evaluation.foundations.adapter import (
    FOUNDATION_AVAILABLE,
    FOUNDATION_PARTIAL,
    MemoryFoundationAdapter,
)
from phase3.evaluation.llm.provider import (
    GenerationConfig,
    LLMProvider,
    LLMProviderError,
)
from phase3.evaluation.security.leakage import (
    STATUS_LEAKAGE_DETECTED,
    validate_no_leakage,
)

from .messages import DEFAULT_SYSTEM_PROMPT, render_messages

RUNNABLE_CONDITIONS: Tuple[str, ...] = (CONDITION_NO_MEMORY, CONDITION_RETRIEVED_MEMORY)


class AgentRuntimeLeakageError(RuntimeError):
    """Raised if the assembled agent-visible context fails EITHER the boundary check
    (`build_agent_visible_context` -> `AgentVisibilityViolation`) or the wider structural
    leakage check (`security.leakage.validate_no_leakage`). Two independent checks are
    run deliberately -- see `boundary.py`'s own module docstring on defense in depth."""


@dataclass(frozen=True)
class AgentTaskInput:
    """Everything the agent runtime needs to run one task. Deliberately, structurally,
    carries NOTHING evaluator-only -- no expected_answer, no gold_evidence_ids field
    exists anywhere on this dataclass.
    """

    task_id: str
    prompt: str
    condition: str  # one of RUNNABLE_CONDITIONS
    retrieval_query: Optional[Mapping[str, Any]] = None
    top_k: int = 5

    def __post_init__(self) -> None:
        if self.condition not in RUNNABLE_CONDITIONS:
            raise ValueError(
                f"condition {self.condition!r} is not runnable by this agent loop; "
                f"must be one of {RUNNABLE_CONDITIONS!r}. GOLD_EVIDENCE is deliberately "
                "excluded here -- it is an evaluator-side control condition, never "
                "something the agent runtime assembles from a foundation."
            )
        if self.condition == CONDITION_RETRIEVED_MEMORY and self.retrieval_query is None:
            raise ValueError("retrieval_query is required when condition=RETRIEVED_MEMORY")


@dataclass(frozen=True)
class GenerationAttempt:
    """One recorded LLM call attempt -- success or failure. Every attempt this module
    makes is appended to `AgentRunOutcome.attempts`, so a caller can see exactly how many
    times generation was tried, never silently substituting a later successful retry for
    an earlier failure without a trace of the failure remaining visible."""

    attempt_number: int
    succeeded: bool
    latency_sec: float
    error: Optional[str] = None


@dataclass(frozen=True)
class AgentRunOutcome:
    """Everything `run_agent_task()` produces. Combined with an evaluator-only
    `expected_answer`/`gold_evidence_ids` supplied separately by the caller, `trace.py`'s
    `evaluate_and_trace()` turns this into the full Part-18 trace."""

    task_id: str
    condition: str
    memory_available: bool
    retrieved_memory_ids: Tuple[str, ...]
    selected_memory_ids: Tuple[str, ...]
    exposed_memory_ids: Tuple[str, ...]
    agent_visible_context: Mapping[str, Any]
    execution_result: AgentExecutionResult
    attempts: Tuple[GenerationAttempt, ...]
    generation_config_fingerprint: str
    model_metadata: Mapping[str, Any]
    total_latency_sec: float
    foundation_identity: Optional[Mapping[str, Any]]


@dataclass(frozen=True)
class RunConfiguration:
    llm_provider: LLMProvider
    generation_config: GenerationConfig
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    max_retries: int = 0  # explicit; 0 means "exactly one attempt, no retry"


def select_from_retrieved(
    retrieved_memory_ids: Sequence[str], top_k: int
) -> Tuple[str, ...]:
    """PROVISIONAL selection policy -- see module docstring. Order-preserving, no
    reranking, no thresholding: the first `top_k` retrieved ids, in the foundation's own
    returned order."""
    return tuple(retrieved_memory_ids[:top_k])


def _extract_memory_id(item: Any) -> Optional[str]:
    """Foundation adapters in this codebase do not agree on `retrieve()`'s per-item
    shape -- e.g. `RealMem0Adapter.retrieve()` returns bare id strings
    (`value=[r["id"] for r in results]`) while `MockMem0Adapter.retrieve()` returns
    `{"memory_id": ..., "content": ..., "score": ...}` dicts. Both are legitimate,
    documented, foundation-native shapes (`adapter.py`'s own docstring only promises an
    ORDER-PRESERVING sequence, not a fixed item shape) -- this function normalizes
    EXTRACTION of the id only, without flattening or discarding whatever else a richer
    item shape carries (the full native item is preserved untouched in
    `retrieve_field.value`, which the trace can still reference)."""
    if isinstance(item, str):
        return item
    if isinstance(item, Mapping):
        return item.get("memory_id") or item.get("id")
    return None


def _extract_content_text(native: Any) -> str:
    """Same normalization discipline as `_extract_memory_id`, for `inspect_memory()`'s
    returned content -- `RealMem0Adapter` (`Memory.get()`, verified directly against the
    installed mem0ai source in `C:\\h4venv`) nests text under a `"memory"` string key;
    `MockMem0Adapter` nests it under a `"content"` MAPPING key (e.g. `{"text": "..."}`,
    whatever `add_memory()` was originally called with). Checks a small set of plausible
    keys, one level deep, before falling back to a stringified repr -- never assumes one
    foundation's shape universally, never silently drops content it cannot parse."""
    if not isinstance(native, Mapping):
        return str(native)
    candidate = native.get("memory") or native.get("text") or native.get("content")
    if isinstance(candidate, Mapping):
        candidate = candidate.get("text") or candidate.get("memory")
    if isinstance(candidate, str) and candidate:
        return candidate
    return str(native)


def _retrieve_and_select(
    foundation: MemoryFoundationAdapter, task: AgentTaskInput
) -> Tuple[Tuple[str, ...], Tuple[str, ...], List[Mapping[str, Any]]]:
    """Returns (retrieved_ids, selected_ids, memory_items_for_context).

    `memory_items_for_context` is built by calling `foundation.inspect_memory()` for
    each selected id to obtain its content -- `retrieve()`'s contract
    (`MemoryFoundationAdapter.retrieve`) only guarantees an ordered sequence, not
    content, so a second real foundation call is required to get displayable text. This
    is a genuine, observable foundation operation, not a shortcut.
    """
    retrieve_field = foundation.retrieve(task.retrieval_query, top_k=task.top_k)
    if retrieve_field.availability not in (FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL):
        return (), (), []

    raw_items = retrieve_field.value or []
    retrieved_ids = tuple(
        mid for mid in (_extract_memory_id(item) for item in raw_items) if mid is not None
    )
    selected_ids = select_from_retrieved(retrieved_ids, task.top_k)

    memory_items: List[Mapping[str, Any]] = []
    for memory_id in selected_ids:
        inspect_field = foundation.inspect_memory(memory_id)
        if inspect_field.availability not in (FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL):
            continue
        content_text = _extract_content_text(inspect_field.value or {})
        memory_items.append({"memory_id": memory_id, "content": content_text})

    return retrieved_ids, selected_ids, memory_items


def generate_with_retries(
    messages: List[Mapping[str, str]], config: RunConfiguration
) -> Tuple[Optional[str], Tuple[GenerationAttempt, ...]]:
    """The generation-retry loop, factored out of `run_agent_task()` (Phase 3.3-H.4-A)
    so `agent_runtime/counterfactual.py`'s masked re-run can reuse the EXACT same
    retry/attempt-recording behavior rather than reimplementing it a second time.
    Returns `(generation_text, attempts)` -- `generation_text` is `None` iff every
    attempt (up to `config.max_retries + 1`) failed. Purely additive: `run_agent_task()`
    below now calls this helper instead of inlining the loop, with no change to its own
    observable behavior (every existing test in `test_agent_runtime.py` passes unchanged).
    """
    attempts: List[GenerationAttempt] = []
    max_attempts = config.max_retries + 1
    generation_text: Optional[str] = None
    for attempt_number in range(1, max_attempts + 1):
        attempt_t0 = time.time()
        try:
            generation_result = config.llm_provider.generate(messages, config.generation_config)
            attempts.append(
                GenerationAttempt(
                    attempt_number=attempt_number,
                    succeeded=True,
                    latency_sec=time.time() - attempt_t0,
                )
            )
            generation_text = generation_result.text
            break
        except LLMProviderError as exc:
            attempts.append(
                GenerationAttempt(
                    attempt_number=attempt_number,
                    succeeded=False,
                    latency_sec=time.time() - attempt_t0,
                    error=repr(exc),
                )
            )
    return generation_text, tuple(attempts)


def run_agent_task(
    task: AgentTaskInput,
    foundation: Optional[MemoryFoundationAdapter],
    config: RunConfiguration,
) -> AgentRunOutcome:
    """Execute the canonical agent loop for one task. `foundation=None` is the mandatory
    no-memory control (Part 11 of the 3.3-A spec) -- `task.condition` must be
    `CONDITION_NO_MEMORY` in that case (enforced below, not merely assumed)."""

    t0 = time.time()

    memory_available = foundation is not None
    if task.condition == CONDITION_NO_MEMORY and memory_available:
        raise ValueError(
            "condition=NO_MEMORY but a foundation was supplied -- the no-memory control "
            "requires foundation=None, per PHASE3_3_EXPERIMENTAL_SPEC.md Part 11 (the "
            "only intended difference between conditions must be the memory subsystem "
            "itself, never an accidentally-still-wired foundation)."
        )
    if task.condition == CONDITION_RETRIEVED_MEMORY and not memory_available:
        raise ValueError("condition=RETRIEVED_MEMORY requires a foundation, got None.")

    retrieved_ids: Tuple[str, ...] = ()
    selected_ids: Tuple[str, ...] = ()
    memory_items: List[Mapping[str, Any]] = []
    foundation_identity_dict: Optional[Mapping[str, Any]] = None

    if task.condition == CONDITION_RETRIEVED_MEMORY:
        identity = foundation.foundation_identity()
        foundation_identity_dict = {
            "foundation_id": identity.foundation_id,
            "foundation_name": identity.foundation_name,
            "adapter_version": identity.adapter_version,
            "status": identity.status,
        }
        retrieved_ids, selected_ids, memory_items = _retrieve_and_select(foundation, task)

    try:
        agent_visible_context = build_agent_visible_context(
            condition=task.condition,
            task_id=task.task_id,
            prompt=task.prompt,
            memory_items=memory_items,
        )
    except AgentVisibilityViolation as exc:
        raise AgentRuntimeLeakageError(
            f"Boundary check rejected the assembled agent-visible context: {exc}"
        ) from exc

    leakage_result = validate_no_leakage(agent_visible_context, condition=task.condition)
    if leakage_result.status == STATUS_LEAKAGE_DETECTED:
        raise AgentRuntimeLeakageError(
            f"Structural leakage check rejected the assembled agent-visible context: "
            f"{leakage_result.summary}"
        )

    exposed_ids = tuple(
        item.get("memory_id")
        for item in agent_visible_context.get("memory_content", [])
        if isinstance(item, Mapping)
    )

    messages = render_messages(agent_visible_context, config.system_prompt)

    execution_result: AgentExecutionResult
    generation_text, attempts_tuple = generate_with_retries(messages, config)
    attempts: List[GenerationAttempt] = list(attempts_tuple)

    if generation_text is not None:
        execution_result = AgentExecutionResult(
            task_id=task.task_id,
            condition=task.condition,
            answer=generation_text,
            execution_status=EXECUTION_STATUS_SUCCESS,
            selected_memory_ids=selected_ids,
            used_memory_ids=None,  # not observable -- see module docstring
            execution_metadata={"attempts": len(attempts)},
        )
    else:
        execution_result = AgentExecutionResult(
            task_id=task.task_id,
            condition=task.condition,
            answer=None,
            execution_status=EXECUTION_STATUS_ERROR,
            selected_memory_ids=selected_ids,
            used_memory_ids=None,
            execution_metadata={
                "attempts": len(attempts),
                "last_error": attempts[-1].error if attempts else None,
            },
        )

    return AgentRunOutcome(
        task_id=task.task_id,
        condition=task.condition,
        memory_available=memory_available,
        retrieved_memory_ids=retrieved_ids,
        selected_memory_ids=selected_ids,
        exposed_memory_ids=exposed_ids,
        agent_visible_context=agent_visible_context,
        execution_result=execution_result,
        attempts=tuple(attempts),
        generation_config_fingerprint=config.llm_provider.configuration_fingerprint(
            config.generation_config
        ),
        model_metadata=config.llm_provider.model_metadata(),
        total_latency_sec=time.time() - t0,
        foundation_identity=foundation_identity_dict,
    )


__all__ = [
    "RUNNABLE_CONDITIONS",
    "AgentRuntimeLeakageError",
    "AgentTaskInput",
    "GenerationAttempt",
    "AgentRunOutcome",
    "RunConfiguration",
    "select_from_retrieved",
    "generate_with_retries",
    "run_agent_task",
]
