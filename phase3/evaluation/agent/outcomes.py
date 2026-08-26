"""Agent execution result representation, deterministic answer correctness, agent success
classification, and a synthetic (test-only) deterministic agent adapter.

Phase 3.2-E scope note: `AgentExecutionResult` here is a NEW dataclass, not a re-import of
`agent_execution_result.schema.json`'s shape. It is intentionally structurally similar
(explicit `task_id`, `condition`, `answer`, `execution_status`, `selected_memory_ids`,
`trace_ref` fields all mirror the 3.2-B schema) but adds one field the frozen schema does
not define: `used_memory_ids` -- the memory ids the agent's response actually drew on,
as distinct from `selected_memory_ids` (what evidence selection handed the reasoning
layer). This distinction is required by the retrieval-utilization diagnostic in
`diagnostics.py` (SELECTED_BUT_NOT_USED vs. SELECTED_AND_USED), and no such field exists
anywhere in `agent_execution_result.schema.json`. Rather than modify that frozen 3.2-B
schema to add a field (an avoidable change -- this is a synthetic diagnostic package, not
a schema producer), this module defines its own dataclass for internal 3.2-E use. A real
future agent-execution pipeline that wants schema-level `used_memory_ids` support would
need a genuine, separately-justified schema revision; this dataclass does not attempt to
pre-empt that decision.

Execution-status vocabulary is reused verbatim from `agent_execution_result.schema.json`'s
`execution_status` enum (SUCCESS/ERROR/SKIPPED/TIMEOUT) rather than re-invented, per the
3.2-E task brief's instruction to reuse existing vocabularies where they fit.

Pure functions/dataclasses: no filesystem/network/LLM/embeddings access, no randomness, no
global/mutable state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence, Tuple

from phase3.evaluation.metrics.types import MetricResult

# ---------------------------------------------------------------------------
# Execution status vocabulary (mirrors agent_execution_result.schema.json verbatim)
# ---------------------------------------------------------------------------

EXECUTION_STATUS_SUCCESS = "SUCCESS"
EXECUTION_STATUS_ERROR = "ERROR"
EXECUTION_STATUS_SKIPPED = "SKIPPED"
EXECUTION_STATUS_TIMEOUT = "TIMEOUT"

EXECUTION_STATUSES: Tuple[str, ...] = (
    EXECUTION_STATUS_SUCCESS,
    EXECUTION_STATUS_ERROR,
    EXECUTION_STATUS_SKIPPED,
    EXECUTION_STATUS_TIMEOUT,
)

# ---------------------------------------------------------------------------
# Agent success classification vocabulary
# ---------------------------------------------------------------------------

SUCCESS_ANSWER_CORRECT = "ANSWER_CORRECT"
SUCCESS_ANSWER_INCORRECT = "ANSWER_INCORRECT"
SUCCESS_EXECUTION_FAILURE = "EXECUTION_FAILURE"
SUCCESS_EVALUATION_UNDEFINED = "EVALUATION_UNDEFINED"


# ---------------------------------------------------------------------------
# AgentExecutionResult
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AgentExecutionResult:
    """The result of one (synthetic, 3.2-E-scope) agent execution for one task/condition.

    Explicit, separate fields -- never one overloaded boolean (per the 3.2-E task brief).
    `success` is deliberately NOT a field here: "success" is a downstream classification
    computed by `classify_agent_success()` from `execution_status` + `answer` + an
    evaluator-only `expected_answer` (never stored on this object, since this object is
    agent-execution-side and must never carry evaluator-only data, per
    LEAKAGE_AND_VISIBILITY_CONTRACT.md and the same separation principle
    `agent_execution_result.schema.json` already enforces for the 3.2-B artifact).

    Attributes
    ----------
    task_id, condition:
        Identity fields. `condition` is any of `conditions.ALL_CONDITIONS` (canonical or
        provisional).
    answer:
        The raw answer/output produced, or ``None`` if execution did not complete
        (`execution_status != SUCCESS`).
    execution_status:
        One of `EXECUTION_STATUSES`. Not a correctness judgment -- mirrors
        `agent_execution_result.schema.json`'s documented meaning exactly.
    selected_memory_ids:
        Memory ids evidence selection chose to pass to reasoning (empty for NO_MEMORY).
    used_memory_ids:
        Memory ids the agent's answer actually drew on, per whatever trace/attribution
        mechanism produced this result. ``None`` (distinct from an empty tuple) means
        "usage was not exposed/observable by this execution's trace" -- see
        `diagnostics.classify_retrieval_utilization()`'s explicit UNDEFINED handling of
        this case. An empty tuple means "usage was observable, and nothing was used."
    execution_metadata:
        Free-form execution metadata (e.g. timing), analogous to
        `agent_execution_result.schema.json`'s `timing` field but left untyped here since
        this dataclass is not itself schema-validated.
    trace_ref:
        Opaque reference to a TraceArtifact, if any. ``None`` if not produced/available.
    """

    task_id: str
    condition: str
    answer: Optional[str] = None
    execution_status: str = EXECUTION_STATUS_SUCCESS
    selected_memory_ids: Tuple[str, ...] = field(default_factory=tuple)
    used_memory_ids: Optional[Tuple[str, ...]] = None
    execution_metadata: Mapping[str, Any] = field(default_factory=dict)
    trace_ref: Optional[str] = None

    def __post_init__(self) -> None:
        if self.execution_status not in EXECUTION_STATUSES:
            raise ValueError(
                f"execution_status {self.execution_status!r} is not one of "
                f"{EXECUTION_STATUSES!r}"
            )


# ---------------------------------------------------------------------------
# Deterministic answer correctness
# ---------------------------------------------------------------------------


def evaluate_answer_correctness(
    execution_result: AgentExecutionResult, expected_answer: Optional[str]
) -> MetricResult:
    """Deterministic EXACT-MATCH answer correctness -- no LLM, no embeddings, no fuzzy/
    semantic comparison anywhere.

    Definition
    ----------
    - If `execution_result.execution_status != EXECUTION_STATUS_SUCCESS`: undefined --
      there is no answer to compare (`status=SUCCESS_EXECUTION_FAILURE`, distinct from
      "evaluated and found undefined").
    - If `expected_answer is None`: undefined -- no evaluator-supplied expected answer to
      compare against (`status=SUCCESS_EVALUATION_UNDEFINED`). Never guess.
    - If `execution_result.answer is None` despite a SUCCESS status (a defensive,
      shouldn't-normally-happen case): undefined, same status.
    - Otherwise: exact string match after a single, explicit, deterministic normalization
      step (`str.strip()` on both sides only -- no case-folding, no punctuation removal,
      no tokenization, no fuzzy/semantic comparison of any kind). Equal -> ANSWER_CORRECT
      (`value=1.0`); not equal -> ANSWER_INCORRECT (`value=0.0`).

    DECISION (3.2-E): `.strip()` is the ONLY normalization applied. This is a deliberately
    minimal, fully deterministic choice -- it tolerates incidental leading/trailing
    whitespace (a common, meaning-preserving artifact of string assembly) without
    introducing any of the ambiguity a looser normalization (case-folding, punctuation
    stripping, whitespace collapsing) would invite. No contract document specifies an
    answer-correctness normalization; this is this stage's own explicit, minimal choice,
    documented rather than left implicit.
    """
    if execution_result.execution_status != EXECUTION_STATUS_SUCCESS:
        return MetricResult(
            metric_name="ANSWER_CORRECTNESS",
            value=None,
            status=SUCCESS_EXECUTION_FAILURE,
            detail={
                "task_id": execution_result.task_id,
                "execution_status": execution_result.execution_status,
            },
            note="execution_status != SUCCESS; there is no answer to judge for correctness.",
        )

    if expected_answer is None:
        return MetricResult(
            metric_name="ANSWER_CORRECTNESS",
            value=None,
            status=SUCCESS_EVALUATION_UNDEFINED,
            detail={"task_id": execution_result.task_id},
            note="No evaluator-supplied expected_answer was provided; correctness is undefined.",
        )

    if execution_result.answer is None:
        return MetricResult(
            metric_name="ANSWER_CORRECTNESS",
            value=None,
            status=SUCCESS_EVALUATION_UNDEFINED,
            detail={"task_id": execution_result.task_id},
            note="execution_status is SUCCESS but answer is None; correctness is undefined.",
        )

    is_correct = execution_result.answer.strip() == expected_answer.strip()
    return MetricResult(
        metric_name="ANSWER_CORRECTNESS",
        value=1.0 if is_correct else 0.0,
        status=SUCCESS_ANSWER_CORRECT if is_correct else SUCCESS_ANSWER_INCORRECT,
        detail={
            "task_id": execution_result.task_id,
            "answer": execution_result.answer,
            "expected_answer": expected_answer,
        },
        note="Deterministic exact-match (after .strip() only) -- no fuzzy/semantic comparison.",
    )


# ---------------------------------------------------------------------------
# Agent success classification
# ---------------------------------------------------------------------------


def classify_agent_success(
    execution_result: AgentExecutionResult, expected_answer: Optional[str]
) -> MetricResult:
    """ANSWER_CORRECT / ANSWER_INCORRECT / EXECUTION_FAILURE / EVALUATION_UNDEFINED.

    Computed ONLY from `execution_result` (this module's own dataclass) and an
    evaluator-only `expected_answer` string -- NEVER from `strict_tsr`,
    `evidence_recall`, or any other memory-level metric in
    `phase3/evaluation/metrics/`. Agent success and memory-level metrics answer two
    different questions (per EVALUATION_CONTRACT.md sections 1 and 3) and this function's
    signature enforces that by construction: it has no parameter shaped like a memory-id
    list or a `MetricResult` from the metrics package.

    This is a thin wrapper over `evaluate_answer_correctness()` -- the status vocabulary
    is identical (`SUCCESS_ANSWER_CORRECT`, `SUCCESS_ANSWER_INCORRECT`,
    `SUCCESS_EXECUTION_FAILURE`, `SUCCESS_EVALUATION_UNDEFINED`), reported here under the
    metric name `AGENT_SUCCESS_CLASSIFICATION` for callers that want the "agent success"
    framing distinct from the narrower "answer correctness" framing, even though the
    computation is the same at this stage (3.2-E does not define any other agent-success
    signal -- e.g. abstention handling -- beyond answer correctness).
    """
    correctness = evaluate_answer_correctness(execution_result, expected_answer)
    return MetricResult(
        metric_name="AGENT_SUCCESS_CLASSIFICATION",
        value=correctness.value,
        status=correctness.status,
        detail=dict(correctness.detail),
        note=correctness.note,
    )


# ---------------------------------------------------------------------------
# Synthetic (test-only) deterministic agent adapter
# ---------------------------------------------------------------------------
#
# NOT a real agent. NOT Qwen. This is scaffolding to exercise the evaluation mechanics
# defined in this package under controlled, fully deterministic behaviors -- purely for
# phase3/evaluation/tests/test_agent_evaluation.py's fixtures.

BEHAVIOR_CORRECT_IF_EVIDENCE_PRESENT = "CORRECT_IF_EVIDENCE_PRESENT"
BEHAVIOR_ALWAYS_CORRECT = "ALWAYS_CORRECT"
BEHAVIOR_ALWAYS_WRONG = "ALWAYS_WRONG"
BEHAVIOR_IGNORE_EVIDENCE_ALWAYS_WRONG = "IGNORE_EVIDENCE_ALWAYS_WRONG"
BEHAVIOR_ALWAYS_FAIL_EXECUTION = "ALWAYS_FAIL_EXECUTION"

SYNTHETIC_BEHAVIORS: Tuple[str, ...] = (
    BEHAVIOR_CORRECT_IF_EVIDENCE_PRESENT,
    BEHAVIOR_ALWAYS_CORRECT,
    BEHAVIOR_ALWAYS_WRONG,
    BEHAVIOR_IGNORE_EVIDENCE_ALWAYS_WRONG,
    BEHAVIOR_ALWAYS_FAIL_EXECUTION,
)

_WRONG_ANSWER_SENTINEL = "SYNTHETIC_AGENT_WRONG_ANSWER"


def run_synthetic_agent(
    task_id: str,
    condition: str,
    behavior: str,
    agent_visible_context: Mapping[str, Any],
    expected_answer: Optional[str] = None,
    selected_memory_ids: Sequence[str] = (),
    used_memory_ids: Optional[Sequence[str]] = None,
) -> AgentExecutionResult:
    """Deterministically map an `AgentVisibleContext`-shaped payload + a configured
    `behavior` to an `AgentExecutionResult`. TEST-ONLY SCAFFOLDING -- not a real agent,
    not Qwen, not any candidate reasoning model. Exists solely so this package's
    evaluation mechanics (correctness, success classification, paired comparison,
    diagnostics) can be exercised end-to-end against controlled, fully deterministic
    inputs, per the 3.2-E task brief's explicit "synthetic deterministic agent... purely
    for exercising the evaluation mechanics in tests" requirement.

    Parameters
    ----------
    behavior:
        One of `SYNTHETIC_BEHAVIORS`:
        - `CORRECT_IF_EVIDENCE_PRESENT`: returns `expected_answer` verbatim if
          `agent_visible_context["memory_content"]` is non-empty, else returns a fixed
          wrong-answer sentinel. Models "memory helps when present."
        - `ALWAYS_CORRECT`: returns `expected_answer` verbatim regardless of context.
          Models "the agent doesn't need memory for this task" (used to construct the
          NO_OBSERVED_MEMORY_CONTRIBUTION "memory unnecessary" fixture).
        - `ALWAYS_WRONG`: returns the wrong-answer sentinel regardless of context. Models
          "the agent never gets this task right regardless of memory."
        - `IGNORE_EVIDENCE_ALWAYS_WRONG`: identical behavior to `ALWAYS_WRONG` but named
          separately per the task brief's explicit behavior list, to make a fixture's
          intent ("evidence was present, but the agent didn't use it correctly, or a
          conflicting memory confused it") self-documenting at the call site even though
          the mechanical effect is the same as `ALWAYS_WRONG`.
        - `ALWAYS_FAIL_EXECUTION`: returns `execution_status=EXECUTION_STATUS_ERROR`,
          `answer=None`, regardless of context. Models an execution failure distinct from
          an incorrect answer.
    agent_visible_context:
        A payload as returned by `conditions.build_agent_visible_context()` (or any dict
        with a `memory_content` key) -- read ONLY for its `memory_content` presence/
        absence; this function never reads or requires an evaluator-only field, and
        raises no error if none is present (there is none to read).
    expected_answer:
        Evaluator-only expected answer, threaded through only so `CORRECT_IF_EVIDENCE_
        PRESENT`/`ALWAYS_CORRECT` can produce a matching answer deterministically for
        test fixtures. This function does not store or leak `expected_answer` into the
        returned `AgentExecutionResult.answer` under any OTHER behavior -- only these two
        behaviors ever echo it.
    """
    if behavior not in SYNTHETIC_BEHAVIORS:
        raise ValueError(f"Unknown synthetic behavior {behavior!r}; must be one of {SYNTHETIC_BEHAVIORS!r}")

    if behavior == BEHAVIOR_ALWAYS_FAIL_EXECUTION:
        return AgentExecutionResult(
            task_id=task_id,
            condition=condition,
            answer=None,
            execution_status=EXECUTION_STATUS_ERROR,
            selected_memory_ids=tuple(selected_memory_ids),
            used_memory_ids=tuple(used_memory_ids) if used_memory_ids is not None else None,
            execution_metadata={"synthetic_behavior": behavior},
        )

    has_evidence = bool(agent_visible_context.get("memory_content"))

    if behavior == BEHAVIOR_ALWAYS_CORRECT:
        answer = expected_answer
    elif behavior == BEHAVIOR_CORRECT_IF_EVIDENCE_PRESENT:
        answer = expected_answer if has_evidence else _WRONG_ANSWER_SENTINEL
    else:  # ALWAYS_WRONG, IGNORE_EVIDENCE_ALWAYS_WRONG
        answer = _WRONG_ANSWER_SENTINEL

    return AgentExecutionResult(
        task_id=task_id,
        condition=condition,
        answer=answer,
        execution_status=EXECUTION_STATUS_SUCCESS,
        selected_memory_ids=tuple(selected_memory_ids),
        used_memory_ids=tuple(used_memory_ids) if used_memory_ids is not None else None,
        execution_metadata={"synthetic_behavior": behavior},
    )
