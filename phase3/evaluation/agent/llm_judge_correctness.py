"""Phase 3.3-RESEARCH -- an LLM-judge answer-correctness check, built as the next tier
after content-recall (word overlap) and semantic-similarity (embedding cosine) both
showed real, disclosed blind spots -- neither can reliably detect negation/contradiction,
and semantic-similarity's literature-default threshold under-credited many genuinely
correct short-phrase answers. An LLM judge is the one approach among these that can
actually reason about entailment, paraphrase, AND negation together.

NOT A FIFTH REPLACEMENT METRIC -- AN ADDITIVE, DIFFERENTLY-SHAPED ONE
--------------------------------------------------------------------------------
Unlike the three purely deterministic metrics in this package, this one requires a real
`LLMProvider` call per judgment -- it is not free, not instant, and not perfectly
reproducible in the strictest sense (though `temperature=0` makes it close to
deterministic in practice for a given server/model). Reported alongside, never in place
of, the exact-match/normalized/content-recall/semantic-similarity metrics.

DISCLOSED LIMITATION -- SAME-MODEL-FAMILY JUDGE, NOT INDEPENDENT
--------------------------------------------------------------------------------
The judge model (Qwen3-8B via the same `llama-server.exe` this codebase already uses
for the agent itself) is the SAME model family generating the answers being judged in
this research phase. This is not a fully independent judge (no separate, larger, or
differently-trained model was used) -- a real, disclosed limitation, not a claim of
gold-standard human-equivalent judgment. Treat this metric's numbers as a further,
useful bound, not as ground truth, exactly like the other three.

JUDGE PROTOCOL -- FIXED IN ADVANCE
--------------------------------------------------------------------------------
Single fixed system+user prompt template, `temperature=0`, `max_tokens=8` (enough for a
one-word answer plus a little slack, never enough to let the judge "reason itself into"
a long justification that could destabilize the single-word parse). The judge is told
explicitly that paraphrase/synonym answers count as correct but negation/contradiction/
different-specific-fact substitution does NOT -- directly targeting the exact blind spot
the two deterministic metrics share. Response is parsed for a leading "YES"/"NO" token
(case-insensitive); anything else is `SUCCESS_EVALUATION_UNDEFINED`, never guessed.
"""

from __future__ import annotations

from typing import Optional

from phase3.evaluation.agent.outcomes import (
    EXECUTION_STATUS_SUCCESS,
    SUCCESS_ANSWER_CORRECT,
    SUCCESS_ANSWER_INCORRECT,
    SUCCESS_EVALUATION_UNDEFINED,
    SUCCESS_EXECUTION_FAILURE,
    AgentExecutionResult,
)
from phase3.evaluation.llm.provider import GenerationConfig, LLMProvider, LLMProviderError
from phase3.evaluation.metrics.types import MetricResult

METRIC_NAME = "ANSWER_CORRECTNESS_LLM_JUDGE"

JUDGE_SYSTEM_PROMPT = (
    "You are grading whether a candidate answer correctly matches a reference (gold) "
    "answer to a factual question. The candidate does not need to match the gold "
    "answer's exact wording -- synonyms, paraphrases, and reasonable elaborations "
    "count as correct, AS LONG AS the core fact or claim matches and is not "
    "contradicted, negated, or substituted with a different specific fact (a wrong "
    "date, wrong name, wrong object, opposite meaning, etc. all count as incorrect). "
    "Reply with exactly one word: YES or NO. No explanation."
)

JUDGE_MAX_TOKENS = 8
JUDGE_TEMPERATURE = 0.0


def _build_judge_messages(question: str, gold: str, answer: str):
    user_content = (
        f"Question: {question}\n"
        f"Gold answer: {gold}\n"
        f"Candidate answer: {answer}\n"
        f"Does the candidate answer correctly match the gold answer? Reply YES or NO."
    )
    return [
        {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def _parse_verdict(text: str) -> Optional[bool]:
    if not text:
        return None
    lowered = text.strip().lower()
    if lowered.startswith("yes"):
        return True
    if lowered.startswith("no"):
        return False
    return None


def evaluate_answer_correctness_llm_judge(
    execution_result: AgentExecutionResult,
    expected_answer: Optional[str],
    question: str,
    llm_provider: LLMProvider,
) -> MetricResult:
    if execution_result.execution_status != EXECUTION_STATUS_SUCCESS:
        return MetricResult(
            metric_name=METRIC_NAME, value=None, status=SUCCESS_EXECUTION_FAILURE,
            detail={"task_id": execution_result.task_id, "execution_status": execution_result.execution_status},
            note="execution_status != SUCCESS; there is no answer to judge for correctness.",
        )
    if expected_answer is None:
        return MetricResult(
            metric_name=METRIC_NAME, value=None, status=SUCCESS_EVALUATION_UNDEFINED,
            detail={"task_id": execution_result.task_id},
            note="No evaluator-supplied expected_answer was provided; correctness is undefined.",
        )
    if execution_result.answer is None:
        return MetricResult(
            metric_name=METRIC_NAME, value=None, status=SUCCESS_EVALUATION_UNDEFINED,
            detail={"task_id": execution_result.task_id},
            note="execution_status is SUCCESS but answer is None -- defensive, shouldn't normally happen.",
        )

    messages = _build_judge_messages(question, expected_answer, execution_result.answer)
    config = GenerationConfig(
        temperature=JUDGE_TEMPERATURE, seed=42, max_tokens=JUDGE_MAX_TOKENS,
        enable_thinking=False, n_ctx=4096,
    )
    try:
        result = llm_provider.generate(messages, config)
    except LLMProviderError as exc:
        return MetricResult(
            metric_name=METRIC_NAME, value=None, status=SUCCESS_EVALUATION_UNDEFINED,
            detail={"task_id": execution_result.task_id, "error": repr(exc)},
            note="LLM judge call failed; correctness is undefined, not guessed.",
        )

    verdict = _parse_verdict(result.text)
    if verdict is None:
        return MetricResult(
            metric_name=METRIC_NAME, value=None, status=SUCCESS_EVALUATION_UNDEFINED,
            detail={"task_id": execution_result.task_id, "raw_judge_output": result.text},
            note="Judge output did not parse as a clear YES/NO; correctness is undefined, not guessed.",
        )

    return MetricResult(
        metric_name=METRIC_NAME,
        value=1.0 if verdict else 0.0,
        status=SUCCESS_ANSWER_CORRECT if verdict else SUCCESS_ANSWER_INCORRECT,
        detail={"task_id": execution_result.task_id, "raw_judge_output": result.text},
        note=(
            "Same-model-family LLM judge (Qwen3-8B), temperature=0, fixed prompt. NOT an "
            "independent judge, NOT ground truth -- report alongside, never in place of, "
            "the other correctness metrics."
        ),
    )


__all__ = [
    "METRIC_NAME",
    "JUDGE_SYSTEM_PROMPT",
    "JUDGE_MAX_TOKENS",
    "JUDGE_TEMPERATURE",
    "evaluate_answer_correctness_llm_judge",
]
