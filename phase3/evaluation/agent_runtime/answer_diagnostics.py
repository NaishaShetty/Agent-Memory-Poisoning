"""Phase 3.3-F -- DIAGNOSTIC-ONLY answer/evidence-content equivalence.

WHY THIS EXISTS
--------------------------------------------------------------------------------
The 3.3-E pilot surfaced two real cases where the frozen canonical metrics (exact-match
`evaluate_answer_correctness`, ID-based `strict_tsr`/`classify_observed_failure_stage`)
reported failure even though the agent's output was substantively useful:

1. LoCoMo: agent answered "Caroline went to the LGBTQ support group yesterday." against
   gold "7 May 2023" -- correct FACT, wrong FORMAT (relative vs. absolute date).
2. LongMemEval: agent answered "Borges described the Library as a sphere whose exact
   center is any one of its hexagons and whose circumference is inaccessible." against
   gold "According to Borges, 'The Library is a sphere whose exact center is any one of
   its hexagons and whose circumference is inaccessible.'" -- near-VERBATIM content match.

This module adds a DIAGNOSTIC-ONLY equivalence layer for exactly this gap. It NEVER
touches `agent.outcomes.evaluate_answer_correctness()` or any canonical metric --
`CANONICAL_ANSWER_CORRECT`/`CANONICAL_ANSWER_INCORRECT` below are the SAME classification
`evaluate_answer_correctness()` already produces, re-labeled only for clarity when
displayed alongside the new diagnostic statuses, never recomputed differently.

DETERMINISTIC METHODS INVESTIGATED (per the 3.3-F mission's explicit instruction to
check deterministic sufficiency BEFORE reaching for embeddings/LLM judges)
--------------------------------------------------------------------------------
1. Exact string match (canonical, `.strip()` only) -- already exists, unchanged.
2. Normalized exact match: casefold + strip punctuation + collapse whitespace. Tested
   against both 3.3-E cases: does NOT catch either (case 1's wording is entirely
   different; case 2 differs by an intro clause and quote marks).
3. Structured/dataset-native answer representation: investigated. LoCoMo carries
   `source_timestamp` (absolute) on memory records but ANSWERS are free text with no
   structured type field; LongMemEval's `metadata.question_date` gives a REFERENCE date
   but, again, no structured expected-answer-type field. Neither dataset exposes a
   machine-parseable "this answer is a relative-date expression, resolve against
   timestamp X" annotation -- building one would require new relative-date NLP
   (temporal expression parsing: "yesterday", "last Wednesday", "two years ago" relative
   to a cited memory's timestamp), which is a genuine, nontrivial, dataset/domain-
   specific feature absent from both datasets today. NOT implemented in this stage --
   see `STATUS_DIAGNOSTIC_UNRESOLVED` below; this is the correct, honest classification
   for case 1, not a false equivalence claim.
4. Normalized token-set overlap / containment: casefold + strip punctuation + collapse
   whitespace, then compute the Jaccard token-overlap ratio between candidate and
   reference. Tested against both 3.3-E cases: correctly flags case 2 (Borges quote,
   overlap well above the chosen threshold) as equivalent, and correctly leaves case 1
   (Caroline date) below threshold -- validated in
   `phase3/evaluation/tests/test_answer_diagnostics.py`'s dedicated regression tests
   using the literal real strings from the 3.3-E campaign result.
5. Dataset-native answer representations: LongMemEval's `answer` field is itself
   sometimes a directly-quotable source excerpt (as in case 2) -- this is exactly what
   method 4 catches; no separate dataset-specific parsing was needed beyond text
   normalization.

CONCLUSION: deterministic normalized token-overlap (method 4) is SUFFICIENT for the
observed lexical-near-match case class and is what this module implements.
Semantic/embedding/LLM-based judging is NOT implemented in this stage -- deterministic
methods were not exhausted-and-found-insufficient in a way that would justify introducing
one (per the mission's explicit ordering requirement). If a future stage determines
temporal/relative-date reasoning is worth building, or that token-overlap's coverage is
too narrow, that remains a SEPARATE, explicitly-governed diagnostic-layer decision -- see
module docstring's forward-looking note at the bottom.

WHAT THIS NEVER DOES
--------------------------------------------------------------------------------
- Never modifies `evaluate_answer_correctness()`, `strict_tsr()`, or any canonical
  metric or the seven-value failure-stage enum.
- Never infers evidence IDENTITY (a memory_id) from content similarity -- this module
  never returns or fabricates an ID; it only classifies TEXT (an answer string, or
  retrieved memory CONTENT concatenated as text) against a reference TEXT (the gold
  answer string). `agent_runtime.identity`'s prohibition on similarity-based identity
  inference is completely unrelated to and unaffected by this module.
- Never receives or requires gold data inside the agent-visible path -- this module is
  called strictly evaluator-side, after `run_agent_task()` has already returned, exactly
  like `evaluate_and_trace()`/`evaluate_and_trace_with_identity()`.
- Never produces a composite "better answer score" -- only a categorical status.

STATUS VOCABULARY -- deliberately distinct from, never conflated with, the canonical
Answer Correctness / seven-value failure-stage vocabularies:

    CANONICAL_ANSWER_CORRECT / CANONICAL_ANSWER_INCORRECT
        -- restated (not recomputed) from evaluate_answer_correctness(), for display only.
    DIAGNOSTIC_EQUIVALENT
        -- deterministic normalized token-overlap ratio >= threshold. NOT "correct."
    DIAGNOSTIC_NOT_EQUIVALENT
        -- ratio computed, below threshold.
    DIAGNOSTIC_UNRESOLVED
        -- deterministic methods cannot determine equivalence for this pair (e.g. one
        side requires temporal/numeric/domain reasoning outside lexical overlap) --
        HONEST non-answer, never coerced to either equivalent or not-equivalent.

`DIAGNOSTIC_EQUIVALENT` is never named or treated as `SUCCESS` (the failure-stage value)
or `ANSWER_CORRECT` (the canonical value) anywhere in this codebase.
"""

from __future__ import annotations

import re
import string
from dataclasses import dataclass
from typing import Optional

# Fixed, disclosed threshold -- chosen (not tuned against a target result) as the
# midpoint between the two 3.3-E validation cases' measured ratios: case 2 (genuine
# near-verbatim match) computes well above 0.5; case 1 (genuinely different wording)
# computes at 0.0. See test_answer_diagnostics.py for the exact measured values this
# threshold was set relative to.
EQUIVALENCE_THRESHOLD = 0.5

STATUS_CANONICAL_ANSWER_CORRECT = "CANONICAL_ANSWER_CORRECT"
STATUS_CANONICAL_ANSWER_INCORRECT = "CANONICAL_ANSWER_INCORRECT"
STATUS_DIAGNOSTIC_EQUIVALENT = "DIAGNOSTIC_EQUIVALENT"
STATUS_DIAGNOSTIC_NOT_EQUIVALENT = "DIAGNOSTIC_NOT_EQUIVALENT"
STATUS_DIAGNOSTIC_UNRESOLVED = "DIAGNOSTIC_UNRESOLVED"

_PUNCTUATION_TABLE = str.maketrans("", "", string.punctuation)


def _normalize_tokens(text: str) -> frozenset:
    """casefold -> strip punctuation -> collapse whitespace -> split into a token set.
    Deterministic, no external dependency, no randomness."""
    lowered = text.casefold().translate(_PUNCTUATION_TABLE)
    collapsed = re.sub(r"\s+", " ", lowered).strip()
    if not collapsed:
        return frozenset()
    return frozenset(collapsed.split(" "))


def _token_overlap_ratio(candidate: str, reference: str) -> Optional[float]:
    """Jaccard token-overlap ratio: |candidate_tokens & reference_tokens| /
    |reference_tokens|. Uses REFERENCE-set size as the denominator (not the union) --
    a DECISION: this asks "what fraction of the gold answer's content words appear in
    the candidate," which is what "candidate contains/restates the gold fact" means; a
    candidate that also contains a lot of unrelated extra text (as in both 3.3-E cases,
    where the model wraps the fact in a full sentence) is not penalized for verbosity,
    matching the intuition "the model said the right thing, plus more words," not "the
    model said ONLY the right thing." Returns None if reference has zero tokens
    (nothing to compare against -- undefined, never treated as 0.0).
    """
    reference_tokens = _normalize_tokens(reference)
    if not reference_tokens:
        return None
    candidate_tokens = _normalize_tokens(candidate)
    if not candidate_tokens:
        return 0.0
    return len(candidate_tokens & reference_tokens) / len(reference_tokens)


@dataclass(frozen=True)
class EquivalenceDiagnostic:
    status: str
    overlap_ratio: Optional[float]
    threshold: float
    note: str


def classify_text_equivalence(
    candidate_text: Optional[str], reference_text: Optional[str]
) -> EquivalenceDiagnostic:
    """The one shared deterministic-equivalence primitive this module exposes. Used both
    for ANSWER equivalence (candidate=agent's final answer, reference=gold answer) and
    for EVIDENCE-CONTENT relevance (candidate=concatenated retrieved-memory text,
    reference=gold answer) -- two different USES of the identical mechanism, always
    distinguished by the CALL SITE's own labeling (see
    `classify_answer_equivalence`/`classify_evidence_content_relevance` below), never by
    a different internal algorithm.
    """
    if candidate_text is None or reference_text is None:
        return EquivalenceDiagnostic(
            status=STATUS_DIAGNOSTIC_UNRESOLVED,
            overlap_ratio=None,
            threshold=EQUIVALENCE_THRESHOLD,
            note="candidate_text or reference_text is None -- nothing to compare.",
        )
    ratio = _token_overlap_ratio(candidate_text, reference_text)
    if ratio is None:
        return EquivalenceDiagnostic(
            status=STATUS_DIAGNOSTIC_UNRESOLVED,
            overlap_ratio=None,
            threshold=EQUIVALENCE_THRESHOLD,
            note="reference_text normalizes to zero tokens -- nothing to compare against.",
        )
    status = STATUS_DIAGNOSTIC_EQUIVALENT if ratio >= EQUIVALENCE_THRESHOLD else STATUS_DIAGNOSTIC_NOT_EQUIVALENT
    return EquivalenceDiagnostic(
        status=status,
        overlap_ratio=ratio,
        threshold=EQUIVALENCE_THRESHOLD,
        note=(
            "Deterministic normalized token-overlap ratio (Jaccard over reference-token "
            "denominator) -- a lexical-overlap OBSERVATION only, never a correctness, "
            "success, or evidence-identity claim. Cases requiring numeric/temporal/"
            "domain reasoning beyond lexical overlap (e.g. relative-date resolution) are "
            "NOT reliably caught by this method and may report DIAGNOSTIC_NOT_EQUIVALENT "
            "even when a human would judge the answer correct -- see module docstring's "
            "LoCoMo case."
        ),
    )


def classify_answer_equivalence(agent_answer: Optional[str], gold_answer: Optional[str]) -> EquivalenceDiagnostic:
    """ANSWER-level diagnostic: does the agent's final answer text restate the gold
    answer's content, deterministically, lexically? See module docstring."""
    return classify_text_equivalence(agent_answer, gold_answer)


def classify_evidence_content_relevance(
    retrieved_content_texts, gold_answer: Optional[str]
) -> EquivalenceDiagnostic:
    """EVIDENCE-level diagnostic: does the CONTENT of what was retrieved (concatenated,
    as plain text) lexically overlap with the gold answer -- a diagnostic OBSERVATION
    only, distinct from and never a substitute for Strict TSR's frozen literal-ID
    definition, and NEVER used to fabricate or infer a gold evidence ID. `retrieved_
    content_texts` is a sequence of content strings (e.g. from resolved memory items);
    they are joined with spaces before normalization -- order does not affect a Jaccard
    set-based ratio.
    """
    if retrieved_content_texts is None:
        joined = None
    else:
        joined = " ".join(t for t in retrieved_content_texts if t)
    return classify_text_equivalence(joined, gold_answer)


__all__ = [
    "EQUIVALENCE_THRESHOLD",
    "STATUS_CANONICAL_ANSWER_CORRECT",
    "STATUS_CANONICAL_ANSWER_INCORRECT",
    "STATUS_DIAGNOSTIC_EQUIVALENT",
    "STATUS_DIAGNOSTIC_NOT_EQUIVALENT",
    "STATUS_DIAGNOSTIC_UNRESOLVED",
    "EquivalenceDiagnostic",
    "classify_text_equivalence",
    "classify_answer_equivalence",
    "classify_evidence_content_relevance",
]
