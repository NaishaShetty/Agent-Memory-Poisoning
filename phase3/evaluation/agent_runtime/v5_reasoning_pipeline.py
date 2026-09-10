"""Phase 3.3-V5 -- bounded multi-stage reasoning pipeline (roadmap item 12).

WHY THIS EXISTS -- grounded in two real, disclosed findings this pass produced
--------------------------------------------------------------------------------
1. THE "QUOTE-THEN-HEDGE" PATTERN: two separate pilots this session
   (`pilot_hedging_fix_v4.py`, and the date-normalization rescoring's case #10)
   found the SAME real behavior twice, independently -- the model sometimes states
   the correct fact and then still refuses to commit to it as the answer ("The
   memory does not specify the exact duration... It only mentions that he 'is gonna
   be in Japan for a few months.'"). A single-pass generate-and-stop pipeline (V1-V4's
   architecture) has no mechanism to catch this. V5 adds ONE extra, bounded
   verification call that is shown the draft answer and explicitly asked whether it
   commits to a directly-stated fact -- not a confidence instruction to the answer
   model itself (which Rounds 1 and 9's failed hedging fixes already proved backfires
   via an over-usable refusal phrase), but a SEPARATE, narrow check performed by a
   second call.
2. TRUNCATION IS A REAL, MEASURED RISK OF ADDING GENERATION STAGES:
   `pilot_qwen3_4b_thinking_v2.py` measured 7/15 (47%) empty answers on Condition C
   when a thinking-capable model's token budget was insufficient. This pipeline is
   therefore built with a HARD, small bound (at most 3 LLM calls total: draft,
   verify, and at most ONE revision -- never more), every stage's `finish_reason` is
   recorded, and the pipeline NEVER loops on a verification failure -- if the single
   allowed revision still doesn't pass, the pipeline returns the revision anyway
   (never blocks, never retries indefinitely) with the verification outcome disclosed
   in the trace.

BOUNDED BY CONSTRUCTION, NOT BY CONVENTION
--------------------------------------------------------------------------------
There is no loop construct anywhere in `generate_verified_answer()` -- the call
sequence is drafted directly as (up to) three sequential, unconditional-in-count
function calls. A caller can verify the bound by reading the function body, not by
trusting a max-iterations parameter that could be set arbitrarily high.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Optional, Tuple

from phase3.evaluation.llm.provider import GenerationConfig, LLMProvider, LLMProviderError

# FIXED 2026-09-09: this was previously a DIFFERENT prompt (dropped V1-V4's explicit
# "do not explain your reasoning, just give the answer" anti-verbosity instruction),
# which broke V5_BASE's claimed equivalence to V3's evidence construction + single-
# pass generation -- discovered when V5_VERIFIED underperformed V3 on every metric
# at full n=120 scale and a direct prompt diff found this mismatch. Now IDENTICAL,
# verbatim, to `agent_runtime/messages.py::DEFAULT_SYSTEM_PROMPT` (V1-V4's prompt),
# imported directly rather than duplicated as a literal so the two can never drift
# apart silently again.
from phase3.evaluation.agent_runtime.messages import DEFAULT_SYSTEM_PROMPT as DRAFT_SYSTEM_PROMPT

VERIFY_SYSTEM_PROMPT = (
    "You are checking a draft answer against the evidence it was based on. Output "
    "ONLY a JSON object, no other text, with exactly these keys: \"commits_to_answer\" "
    "(true if the draft directly asserts a specific answer; false if it hedges, "
    "refuses, or says the information is unavailable), \"grounded\" (true if every "
    "claim in the draft is actually supported by the evidence shown; false if it "
    "asserts something the evidence does not state), \"verdict\" (\"ACCEPT\" if the "
    "draft is already the best honest answer given the evidence -- including cases "
    "where hedging IS correct because the evidence genuinely lacks the answer -- or "
    "\"REVISE\" if the evidence contains a clear, direct answer that the draft failed "
    "to state), \"instruction\" (a short, specific instruction for what to fix, only "
    "if verdict is \"REVISE\"; empty string otherwise)."
)


@dataclass(frozen=True)
class StageCall:
    stage: str  # "DRAFT" | "VERIFY" | "REVISE"
    answer_or_output: Optional[str]
    latency_sec: float
    finish_reason: Optional[str]
    attempts: int


@dataclass(frozen=True)
class V5AnswerResult:
    final_answer: Optional[str]
    draft_answer: Optional[str]
    verification: Optional[dict]  # parsed VERIFY-stage JSON, or None if verification disabled/failed to parse
    verification_parse_error: Optional[str]
    was_revised: bool
    stage_calls: Tuple[StageCall, ...]
    total_latency_sec: float


def _build_user_prompt(question: str, evidence_text: str) -> str:
    return f"Memory content:\n{evidence_text}\n\nQuestion: {question}"


_V5_MAX_ATTEMPTS = 2  # V5-local, minimal retry bound -- mirrors runner.py's retry intent
                       # (one retry on a transient provider error) without depending on
                       # generate_with_retries(), which discards finish_reason and cannot
                       # be modified without risking V1-V4's shared behavior.


def _generate(messages, llm_provider: LLMProvider, generation_config: GenerationConfig, stage: str) -> StageCall:
    """V5-specific generation wrapper: calls `llm_provider.generate()` directly (the
    same public provider interface `generate_with_retries()` itself calls) so
    `finish_reason` -- needed to detect truncation, per this module's docstring --
    is preserved instead of being discarded. Retries up to `_V5_MAX_ATTEMPTS` times
    on a transient `LLMProviderError`, exactly the behavior `generate_with_retries()`
    provides, just with the one additional field kept."""
    attempts = 0
    for attempts in range(1, _V5_MAX_ATTEMPTS + 1):
        t0 = time.time()
        try:
            result = llm_provider.generate(messages, generation_config)
            return StageCall(stage=stage, answer_or_output=result.text, latency_sec=time.time() - t0, finish_reason=result.finish_reason, attempts=attempts)
        except LLMProviderError:
            if attempts == _V5_MAX_ATTEMPTS:
                return StageCall(stage=stage, answer_or_output=None, latency_sec=time.time() - t0, finish_reason=None, attempts=attempts)
    return StageCall(stage=stage, answer_or_output=None, latency_sec=0.0, finish_reason=None, attempts=attempts)


def _parse_verification_json(text: Optional[str]) -> Tuple[Optional[dict], Optional[str]]:
    if text is None:
        return None, "verify stage produced no output"
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[a-zA-Z]*\n?", "", stripped)
        stripped = re.sub(r"\n?```$", "", stripped).strip()
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError as exc:
        return None, f"JSONDecodeError: {exc}"
    if not isinstance(parsed, dict) or "verdict" not in parsed:
        return None, "parsed JSON missing required 'verdict' key"
    return parsed, None


def generate_verified_answer(
    question: str,
    evidence_text: str,
    llm_provider: LLMProvider,
    generation_config: GenerationConfig,
    enable_verification: bool,
) -> V5AnswerResult:
    """At most 3 LLM calls, always in this fixed order: DRAFT, [VERIFY, [REVISE]].
    If `enable_verification` is False, this is exactly V1-V4's single-pass behavior
    (one DRAFT call, returned as-is) -- the ablation flag genuinely disables the
    mechanism, not just hides its effect.
    """
    t_start = time.time()
    stage_calls = []

    draft_messages = [
        {"role": "system", "content": DRAFT_SYSTEM_PROMPT},
        {"role": "user", "content": _build_user_prompt(question, evidence_text)},
    ]
    draft_call = _generate(draft_messages, llm_provider, generation_config, "DRAFT")
    stage_calls.append(draft_call)

    if not enable_verification or draft_call.answer_or_output is None:
        return V5AnswerResult(
            final_answer=draft_call.answer_or_output, draft_answer=draft_call.answer_or_output,
            verification=None, verification_parse_error=None, was_revised=False,
            stage_calls=tuple(stage_calls), total_latency_sec=time.time() - t_start,
        )

    verify_user_content = (
        f"Question: {question}\n\nEvidence:\n{evidence_text}\n\nDraft answer:\n{draft_call.answer_or_output}"
    )
    verify_messages = [
        {"role": "system", "content": VERIFY_SYSTEM_PROMPT},
        {"role": "user", "content": verify_user_content},
    ]
    verify_call = _generate(verify_messages, llm_provider, generation_config, "VERIFY")
    stage_calls.append(verify_call)

    verification, parse_error = _parse_verification_json(verify_call.answer_or_output)

    if verification is None or verification.get("verdict") != "REVISE":
        return V5AnswerResult(
            final_answer=draft_call.answer_or_output, draft_answer=draft_call.answer_or_output,
            verification=verification, verification_parse_error=parse_error, was_revised=False,
            stage_calls=tuple(stage_calls), total_latency_sec=time.time() - t_start,
        )

    instruction = verification.get("instruction") or "State the answer directly if the evidence supports one."
    revise_messages = [
        {"role": "system", "content": DRAFT_SYSTEM_PROMPT},
        {"role": "user", "content": _build_user_prompt(question, evidence_text)},
        {"role": "assistant", "content": draft_call.answer_or_output},
        {"role": "user", "content": f"Revise your answer. {instruction}"},
    ]
    revise_call = _generate(revise_messages, llm_provider, generation_config, "REVISE")
    stage_calls.append(revise_call)

    final = revise_call.answer_or_output if revise_call.answer_or_output is not None else draft_call.answer_or_output
    return V5AnswerResult(
        final_answer=final, draft_answer=draft_call.answer_or_output,
        verification=verification, verification_parse_error=parse_error, was_revised=revise_call.answer_or_output is not None,
        stage_calls=tuple(stage_calls), total_latency_sec=time.time() - t_start,
    )


__all__ = [
    "StageCall",
    "V5AnswerResult",
    "generate_verified_answer",
    "DRAFT_SYSTEM_PROMPT",
    "VERIFY_SYSTEM_PROMPT",
]
