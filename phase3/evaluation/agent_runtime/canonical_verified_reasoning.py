"""Phase 3.3-V3-HYBRID -- canonical bounded draft/verify/revise reasoning pipeline.

PROVENANCE, STATED PLAINLY
--------------------------------------------------------------------------------
This logic was originally developed and validated during V5 experimentation
(`agent_runtime/v5_reasoning_pipeline.py`), where it was found to produce a real,
reproduced correctness gain specifically on Condition B (gold evidence) -- see
`PHASE3_V4_DIAGNOSIS_AND_85_90_ROADMAP.md` and the V5 Stage 2 pilot results for the
original validation evidence. It did NOT transfer as a reliable improvement to
Condition C (retrieved memory), which is why V3-Hybrid uses it ONLY for Condition
B, leaving Condition A and Condition C as V3's own unmodified single-pass behavior.

WHY THIS FILE EXISTS SEPARATELY FROM v5_reasoning_pipeline.py
--------------------------------------------------------------------------------
V3-Hybrid is the final, canonical Phase 3 memory foundation, and Phase 4 must not
need to import anything from V5's experimental namespace. The ORIGINAL
`v5_reasoning_pipeline.py` is left untouched as the historical V5 artifact it
always was (never modified, never deleted -- V5 remains inspectable exactly as it
was validated). This file is a byte-for-byte logical duplicate, promoted to
canonical status because the mechanism itself is now permanent, validated
architecture for the final foundation, not merely a historical experiment result.
No behavior was changed in this promotion -- this is a relocation, not a redesign.

BOUNDED BY CONSTRUCTION, NOT BY CONVENTION
--------------------------------------------------------------------------------
There is no loop construct anywhere in `generate_verified_answer()` -- the call
sequence is drafted directly as (up to) three sequential, unconditional-in-count
function calls (DRAFT, optionally VERIFY, optionally REVISE). A caller can verify
the bound by reading the function body, not by trusting a max-iterations parameter
that could be set arbitrarily high. `enable_verification=False` reproduces V1-V4's
single-pass behavior exactly.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Optional, Tuple

from phase3.evaluation.llm.provider import GenerationConfig, LLMProvider, LLMProviderError

# Identical, verbatim, to V1-V4's own DEFAULT_SYSTEM_PROMPT -- imported directly so
# the two can never drift apart silently (this was the exact root cause of a real
# regression found during V5 validation: an earlier, different draft prompt broke
# equivalence to V3's baseline and was fixed by importing this constant directly).
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
class VerifiedAnswerResult:
    final_answer: Optional[str]
    draft_answer: Optional[str]
    verification: Optional[dict]
    verification_parse_error: Optional[str]
    was_revised: bool
    stage_calls: Tuple[StageCall, ...]
    total_latency_sec: float


def _build_user_prompt(question: str, evidence_text: str) -> str:
    return f"Memory content:\n{evidence_text}\n\nQuestion: {question}"


_MAX_ATTEMPTS = 2  # minimal retry bound on a transient provider error, mirroring
                    # the shared runner's retry intent without depending on
                    # generate_with_retries() (which discards finish_reason).


def _generate(messages, llm_provider: LLMProvider, generation_config: GenerationConfig, stage: str) -> StageCall:
    for attempts in range(1, _MAX_ATTEMPTS + 1):
        t0 = time.time()
        try:
            result = llm_provider.generate(messages, generation_config)
            return StageCall(stage=stage, answer_or_output=result.text, latency_sec=time.time() - t0, finish_reason=result.finish_reason, attempts=attempts)
        except LLMProviderError:
            if attempts == _MAX_ATTEMPTS:
                return StageCall(stage=stage, answer_or_output=None, latency_sec=time.time() - t0, finish_reason=None, attempts=attempts)
    return StageCall(stage=stage, answer_or_output=None, latency_sec=0.0, finish_reason=None, attempts=_MAX_ATTEMPTS)


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
) -> VerifiedAnswerResult:
    """At most 3 LLM calls, always in this fixed order: DRAFT, [VERIFY, [REVISE]]."""
    t_start = time.time()
    stage_calls = []

    draft_messages = [
        {"role": "system", "content": DRAFT_SYSTEM_PROMPT},
        {"role": "user", "content": _build_user_prompt(question, evidence_text)},
    ]
    draft_call = _generate(draft_messages, llm_provider, generation_config, "DRAFT")
    stage_calls.append(draft_call)

    if not enable_verification or draft_call.answer_or_output is None:
        return VerifiedAnswerResult(
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
        return VerifiedAnswerResult(
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
    return VerifiedAnswerResult(
        final_answer=final, draft_answer=draft_call.answer_or_output,
        verification=verification, verification_parse_error=parse_error, was_revised=revise_call.answer_or_output is not None,
        stage_calls=tuple(stage_calls), total_latency_sec=time.time() - t_start,
    )


__all__ = [
    "StageCall",
    "VerifiedAnswerResult",
    "generate_verified_answer",
    "DRAFT_SYSTEM_PROMPT",
    "VERIFY_SYSTEM_PROMPT",
]
