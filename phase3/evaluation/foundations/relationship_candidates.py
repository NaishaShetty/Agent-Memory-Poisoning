"""Phase 3.3-DATASET (research track, continued) -- a candidate-flagging layer for
`equivalent_to`, per the follow-up decision: the cascade mechanism
(`similarity.py` cosine gate + real LLM-judge confirmation) does not clear the
precision bar needed to silently write `relationship_detected` events into the
canonical event ledger (best real F1 measured: 0.533,
`PHASE3_RESEARCH_TRACK_RELATIONSHIP_DETECTION_QUALIFICATION.md`) -- but the system
does not have to trust it that much to be useful.

WHAT THIS MODULE DOES, AND DOES NOT DO
--------------------------------------------------------------------------------
Surfaces SUGGESTED candidate pairs, each carrying an explicit
`status="SUGGESTED_LOW_CONFIDENCE"` marker and the real cascade evidence
(cosine score, LLM-judge label) -- for human/future-automated REVIEW, never
auto-committed. This module NEVER calls `CanonicalEventLedger.append()`, never
constructs a `relationship_detected` `CanonicalEvent`, and never touches any
existing canonical ledger. A caller who wants to actually commit a reviewed
candidate must do so explicitly and separately, using the SAME
`emit_superseded_by_detected()`-style pattern `creation_policy.py` already
establishes for `superseded_by` -- this module supplies candidates, never
decisions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence, Tuple

from phase3.evaluation.foundations.similarity import score_candidates
from phase3.evaluation.llm.provider import GenerationConfig, LLMProvider

STATUS_SUGGESTED_LOW_CONFIDENCE = "SUGGESTED_LOW_CONFIDENCE"

GATE_THRESHOLD = 0.65  # cosine gate, matching the calibrated cascade (100% real recall, 254-pair set)

# conflicts_with gate is deliberately lower than equivalent_to's -- the design
# review's own real finding (PHASE3_EQUIVALENT_CONFLICTS_DESIGN_CALIBRATION.md
# section 4) is that genuine real conflicts (cf1-cf3 in that synthetic probe) scored
# cosine 0.72-0.91, i.e. the same "topically close" band as equivalence, so reusing
# the same 0.65 gate is correct and intentional here, not a separate calibration.
CONFLICTS_WITH_GATE_THRESHOLD = 0.65

_LLM_JUDGE_PROMPT = """You are classifying the relationship between two real conversational memory statements.
Respond with EXACTLY ONE WORD: EQUIVALENT, CONFLICTING, ELABORATION, or NEUTRAL.
- EQUIVALENT: both statements assert essentially the same fact or sentiment (paraphrases, even if worded very differently or spoken by different people).

Statement A: {a}
Statement B: {b}

Answer with one word only:"""

_CONFLICTS_WITH_JUDGE_PROMPT = """You are classifying the relationship between two real conversational memory statements, BOTH FROM THE SAME REAL CONVERSATION SESSION (same sitting, no time has passed between them).
Respond with EXACTLY ONE WORD: EQUIVALENT, CONFLICTING, ELABORATION, or NEUTRAL.
- CONFLICTING: the statements assert mutually incompatible facts about the same subject, both presented as true right now.

Statement A: {a}
Statement B: {b}

Answer with one word only:"""


@dataclass(frozen=True)
class SuggestedEquivalentToCandidate:
    """One candidate pair, never committed -- carries its own real evidence so a
    reviewer (human or a future, better-qualified mechanism) can judge it without
    re-deriving the score."""

    memory_id_a: str
    memory_id_b: str
    content_a: str
    content_b: str
    cosine_score: float
    llm_judge_label: str
    status: str  # always STATUS_SUGGESTED_LOW_CONFIDENCE -- never a committed status


@dataclass(frozen=True)
class SuggestedConflictsWithCandidate:
    """`conflicts_with` sibling of `SuggestedEquivalentToCandidate`. The caller MUST
    scope `candidates` to a single ingestion pool (same requirement as
    `suggest_equivalent_to_candidates`) -- for `conflicts_with` this is not just a
    convention, it is the settled temporal-scoping constraint from
    `PHASE3_EQUIVALENT_CONFLICTS_DESIGN_CALIBRATION.md` section 9/11: comparing
    across sessions/pools requires conservative abstention until a temporal policy
    is empirically validated, which has not happened -- this function does not
    enforce the boundary itself (it has no pool identity to check), the caller must.
    """

    memory_id_a: str
    memory_id_b: str
    content_a: str
    content_b: str
    cosine_score: float
    llm_judge_label: str
    status: str  # always STATUS_SUGGESTED_LOW_CONFIDENCE -- never a committed status


def suggest_equivalent_to_candidates(
    candidates: Sequence[Tuple[str, str]],
    llm_provider: LLMProvider,
    generation_config: GenerationConfig,
    gate_threshold: float = GATE_THRESHOLD,
) -> List[SuggestedEquivalentToCandidate]:
    """`candidates` is `[(memory_id, content), ...]` for ONE pool (the caller's
    responsibility to scope this to a single ingestion pool -- this function does
    not enforce pool boundaries itself, matching `similarity.py`'s own scope: pure
    text-in, text-out).

    Runs the calibrated cascade (cosine gate, then real LLM-judge confirmation)
    over every unordered pair, but returns EVERY LLM-judge-confirmed pair as a
    `SUGGESTED_LOW_CONFIDENCE` candidate -- never writes anything, never claims a
    verified relationship. Real cost control: the cosine gate still runs first, so
    the (expensive) LLM call only happens for topically-similar pairs, exactly as
    the calibrated cascade already established.
    """
    suggestions: List[SuggestedEquivalentToCandidate] = []
    for i, (mid_a, content_a) in enumerate(candidates):
        others = [(mid, content) for mid, content in candidates[i + 1:]]
        if not others:
            continue
        scored = score_candidates(content_a, others)
        for s in scored:
            if s.score < gate_threshold:
                continue
            prompt = _LLM_JUDGE_PROMPT.format(a=content_a, b=s.content)
            gen = llm_provider.generate([{"role": "user", "content": prompt}], generation_config)
            answer = gen.text.strip().split()[0].upper().strip(".,:") if gen.text.strip() else "EMPTY"
            if answer == "EQUIVALENT":
                suggestions.append(SuggestedEquivalentToCandidate(
                    memory_id_a=mid_a, memory_id_b=s.memory_id,
                    content_a=content_a, content_b=s.content,
                    cosine_score=s.score, llm_judge_label=answer,
                    status=STATUS_SUGGESTED_LOW_CONFIDENCE,
                ))
    return suggestions


def suggest_conflicts_with_candidates(
    candidates: Sequence[Tuple[str, str]],
    llm_provider: LLMProvider,
    generation_config: GenerationConfig,
    gate_threshold: float = CONFLICTS_WITH_GATE_THRESHOLD,
) -> List[SuggestedConflictsWithCandidate]:
    """`conflicts_with` sibling of `suggest_equivalent_to_candidates()` -- same
    cascade shape (cosine gate, then real LLM-judge confirmation), same
    never-commits discipline. `candidates` MUST already be scoped to a single
    ingestion pool by the caller (see `SuggestedConflictsWithCandidate`'s
    docstring) -- this function trusts that scoping, it does not verify it.

    Uses `_CONFLICTS_WITH_JUDGE_PROMPT`, which explicitly tells the judge both
    statements are from the same real session (no time has passed) -- this is the
    real, disclosed reason a `conflicts_with` suggestion here is never conflated
    with a `superseded_by` candidate: the prompt itself rules out the
    "this could just be a later update" reading, consistent with the settled
    within-pool temporal-scoping constraint this function's docstring points to.
    """
    suggestions: List[SuggestedConflictsWithCandidate] = []
    for i, (mid_a, content_a) in enumerate(candidates):
        others = [(mid, content) for mid, content in candidates[i + 1:]]
        if not others:
            continue
        scored = score_candidates(content_a, others)
        for s in scored:
            if s.score < gate_threshold:
                continue
            prompt = _CONFLICTS_WITH_JUDGE_PROMPT.format(a=content_a, b=s.content)
            gen = llm_provider.generate([{"role": "user", "content": prompt}], generation_config)
            answer = gen.text.strip().split()[0].upper().strip(".,:") if gen.text.strip() else "EMPTY"
            if answer == "CONFLICTING":
                suggestions.append(SuggestedConflictsWithCandidate(
                    memory_id_a=mid_a, memory_id_b=s.memory_id,
                    content_a=content_a, content_b=s.content,
                    cosine_score=s.score, llm_judge_label=answer,
                    status=STATUS_SUGGESTED_LOW_CONFIDENCE,
                ))
    return suggestions


__all__ = [
    "STATUS_SUGGESTED_LOW_CONFIDENCE",
    "GATE_THRESHOLD",
    "CONFLICTS_WITH_GATE_THRESHOLD",
    "SuggestedEquivalentToCandidate",
    "SuggestedConflictsWithCandidate",
    "suggest_equivalent_to_candidates",
    "suggest_conflicts_with_candidates",
]
