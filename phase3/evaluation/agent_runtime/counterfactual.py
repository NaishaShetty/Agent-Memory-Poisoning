"""Phase 3.3-H.4-A (Counterfactual Influence Measurement) -- `run_counterfactual_mask()`,
`select_counterfactual_pairs()`, and the `counterfactually_influential` finding types.

READ `MEMORY_FOUNDATION_STRENGTHENING_PLAN_REVISED.md` §1 AND §11.3 BEFORE USING ANYTHING
IN THIS MODULE
================================================================================
This module implements `counterfactually_influential`, NOT `used_causal`. The operational
claim a `CounterfactualComparisonResult` with `status=COUNTERFACTUALLY_INFLUENTIAL` makes
is strictly: "masking this memory changed the specified observable (the generated answer,
under `diff_criterion`) under the frozen intervention protocol." It is NEVER causal
attribution in any stronger sense -- not "this memory caused the answer," not "the model
relied on this memory," not "this is the source of the answer." Nothing produced by this
module may be reported, logged, or documented as proving a memory was "the" cause of an
answer. This is also NOT `tainted_by` (H.4-G's lineage-reachability query, in
`foundations/taint_propagation.py`) -- that traversal never runs generation at all; this
module's whole mechanism IS re-running generation once, with one memory masked.
================================================================================

DESIGN CORRECTION FOUND BY INSPECTING `runner.py::run_agent_task()` -- STATED EXPLICITLY,
NOT SILENTLY SUBSTITUTED
--------------------------------------------------------------------------------
The plan's own conceptual description ("re-run reasoning with one selected memory masked
out") could be read as "re-run the whole pipeline" -- retrieval included. This module does
NOT do that: `foundation.retrieve()`/`foundation.inspect_memory()` are never called anywhere
in this file (confirmed: no `MemoryFoundationAdapter`/`foundation` parameter exists on
`run_counterfactual_mask()` at all -- it needs none, since the masked context is built
purely from the baseline `AgentRunOutcome.agent_visible_context` already in hand).
Retrieval happens EXACTLY ONCE, in the pre-existing baseline run; the masked run reuses that
same retrieval result with one `memory_content` entry removed, then re-renders and
re-generates only. This is a STRONGER reproducibility guarantee than the plan's literal
wording implies: if a foundation's `retrieve()` were not perfectly deterministic (timing,
foundation-internal state, a non-frozen embedding call), a naive "re-run retrieval for the
masked pass too" design could let the masked run's OWN retrieved set differ from the
baseline's for reasons having nothing to do with the masking -- contaminating the
comparison with a confound this design eliminates by construction.

WHY `generation_config_fingerprint` IS NEVER RECOMPUTED
--------------------------------------------------------------------------------
`CounterfactualRunOutcome` does not carry its own, independently-computed
`generation_config_fingerprint` field at all -- the masked run is generated with the exact
same `config` object as the baseline (`config.llm_provider`, `config.generation_config`
untouched), so the baseline's own `AgentRunOutcome.generation_config_fingerprint` value
already IS the masked run's value, by construction. Recomputing it would imply it could
legitimately differ, which would be a bug if it ever did.

HASHING -- REUSES H.4-F's ESTABLISHED AUTHORITY, NO SECOND SCHEME
--------------------------------------------------------------------------------
`CounterfactualComparisonResult.baseline_answer_hash`/`masked_answer_hash` are
`security.reproducibility.fingerprint()` of the raw answer string -- the same content-hash
authority `event_identity.py`/`run_config.py` already established, not a second, novel
hashing scheme. Hashing (rather than storing the raw answer text) mirrors `leakage.py`'s
own "never persist the actual value in a report" discipline, applied to answer text that
this module's own result type will end up serialized into the canonical event ledger (§6).
"""

from __future__ import annotations

import copy
import random
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from phase3.evaluation.agent.outcomes import EXECUTION_STATUS_ERROR, EXECUTION_STATUS_SUCCESS
from phase3.evaluation.contracts.boundary import AgentVisibilityViolation, validate_agent_visible
from phase3.evaluation.foundations.canonical_event import MASKING_METHOD_SELECTED_SET_REMOVAL
from phase3.evaluation.security.leakage import STATUS_LEAKAGE_DETECTED, validate_no_leakage
from phase3.evaluation.security.reproducibility import fingerprint

from .messages import render_messages
from .runner import AgentRunOutcome, GenerationAttempt, RunConfiguration, generate_with_retries

# ---------------------------------------------------------------------------
# Diff criterion (mission section 4 -- decided now, not left open)
# ---------------------------------------------------------------------------

DIFF_CRITERION_EXACT_NORMALIZED_MATCH = "exact_normalized_match"
DIFF_CRITERIA: Tuple[str, ...] = (DIFF_CRITERION_EXACT_NORMALIZED_MATCH,)

_WHITESPACE_RUN = re.compile(r"\s+")


def _normalize_exact(answer: str) -> str:
    """The ONE documented normalization `exact_normalized_match` applies: strip leading/
    trailing whitespace, collapse internal whitespace runs to a single space. NO
    case-folding, NO punctuation stripping -- deliberately, so `"Paris"` vs `"paris"` is
    NOT treated as the same answer (mission section 9's own required adversarial case).
    """
    return _WHITESPACE_RUN.sub(" ", answer.strip())


def _answers_match(criterion: str, a: str, b: str) -> bool:
    if criterion == DIFF_CRITERION_EXACT_NORMALIZED_MATCH:
        return _normalize_exact(a) == _normalize_exact(b)
    raise ValueError(
        f"diff_criterion {criterion!r} is not one of {DIFF_CRITERIA!r}. This mission ships "
        "exactly one criterion (exact_normalized_match) -- no semantic/LLM-judge criterion "
        "exists in this framework; see module docstring for why."
    )


# ---------------------------------------------------------------------------
# Status vocabulary (mission section 5 -- closed set, never a bare boolean)
# ---------------------------------------------------------------------------

STATUS_COUNTERFACTUALLY_INFLUENTIAL = "COUNTERFACTUALLY_INFLUENTIAL"
STATUS_NOT_COUNTERFACTUALLY_INFLUENTIAL = "NOT_COUNTERFACTUALLY_INFLUENTIAL"
STATUS_INCONCLUSIVE_BASELINE_FAILURE = "INCONCLUSIVE_BASELINE_FAILURE"
STATUS_INCONCLUSIVE_GENERATION_FAILURE = "INCONCLUSIVE_GENERATION_FAILURE"

COUNTERFACTUAL_STATUSES: Tuple[str, ...] = (
    STATUS_COUNTERFACTUALLY_INFLUENTIAL,
    STATUS_NOT_COUNTERFACTUALLY_INFLUENTIAL,
    STATUS_INCONCLUSIVE_BASELINE_FAILURE,
    STATUS_INCONCLUSIVE_GENERATION_FAILURE,
)

class CounterfactualMaskingError(ValueError):
    """Raised for a caller error: masking a memory that was never selected, or any other
    precondition `run_counterfactual_mask()` requires before attempting a masked re-run.
    Never silently produces a partial/misleading result for a malformed request."""


# ---------------------------------------------------------------------------
# Deliverable 1 -- the masked re-run mechanism
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CounterfactualRunOutcome:
    """The masked run's own outcome -- deliberately NOT a full `AgentRunOutcome` (no
    `retrieved_memory_ids`/`selected_memory_ids`/`foundation_identity` fields; retrieval
    never runs a second time, so there is nothing new to report there -- see module
    docstring's design-correction section)."""

    masked_memory_id: str
    masked_agent_visible_context: Mapping[str, Any]
    masked_answer: Optional[str]
    masked_execution_status: str
    masked_attempts: Tuple[GenerationAttempt, ...]


def _remove_memory_content_entry(agent_visible_context: Mapping[str, Any], memory_id: str) -> Dict[str, Any]:
    """Deep copy of `agent_visible_context` with the ONE `memory_content` entry whose
    `memory_id == memory_id` removed. No other field is touched."""
    masked = copy.deepcopy(dict(agent_visible_context))
    masked["memory_content"] = [
        item
        for item in masked.get("memory_content", [])
        if not (isinstance(item, Mapping) and item.get("memory_id") == memory_id)
    ]
    return masked


def run_counterfactual_mask(
    baseline: AgentRunOutcome,
    masked_memory_id: str,
    config: RunConfiguration,
) -> CounterfactualRunOutcome:
    """Construct and generate the masked counterpart of `baseline`, per module docstring's
    design correction: retrieval is NEVER re-invoked -- the masked context is built purely
    from `baseline.agent_visible_context`, and this function accepts no foundation
    parameter at all because it needs none.

    Raises `CounterfactualMaskingError` if `masked_memory_id` was not actually selected for
    `baseline` (masking an unselected id is a caller error, not a valid "no influence"
    result), or if the masked context somehow fails the SAME leakage/boundary checks the
    baseline context already passed (structurally should be impossible -- removal can only
    shrink the payload -- but verified here, never assumed).
    """
    if masked_memory_id not in baseline.selected_memory_ids:
        raise CounterfactualMaskingError(
            f"masked_memory_id {masked_memory_id!r} is not in baseline.selected_memory_ids "
            f"{baseline.selected_memory_ids!r} -- a caller must only mask a memory that was "
            "actually selected for the baseline run."
        )

    masked_context = _remove_memory_content_entry(baseline.agent_visible_context, masked_memory_id)

    try:
        validate_agent_visible(masked_context)
    except AgentVisibilityViolation as exc:
        raise CounterfactualMaskingError(
            f"masked context for {masked_memory_id!r} unexpectedly failed the boundary check "
            f"that the baseline context already passed: {exc}"
        ) from exc

    leakage_result = validate_no_leakage(masked_context, condition=baseline.condition)
    if leakage_result.status == STATUS_LEAKAGE_DETECTED:
        raise CounterfactualMaskingError(
            f"masked context for {masked_memory_id!r} unexpectedly failed the structural "
            f"leakage check that the baseline context already passed: {leakage_result.summary}"
        )

    messages = render_messages(masked_context, config.system_prompt)
    masked_answer, masked_attempts = generate_with_retries(messages, config)
    masked_status = EXECUTION_STATUS_SUCCESS if masked_answer is not None else EXECUTION_STATUS_ERROR

    return CounterfactualRunOutcome(
        masked_memory_id=masked_memory_id,
        masked_agent_visible_context=masked_context,
        masked_answer=masked_answer,
        masked_execution_status=masked_status,
        masked_attempts=masked_attempts,
    )


# ---------------------------------------------------------------------------
# Deliverables 2/3 -- the diff criterion, the result type
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CounterfactualComparisonResult:
    """Result of comparing a baseline run against its masked counterpart.

    LINEAGE-REACHABILITY DISCLAIMER (mirrors `taint_propagation.TaintReport`'s own): a
    `COUNTERFACTUALLY_INFLUENTIAL` status means only that masking `masked_memory_id`
    changed the observed answer under `diff_criterion` -- it is never a stronger causal
    claim, and it must never be reported as, or substituted for, a `tainted_by` finding
    or vice versa. See module docstring.
    """

    task_id: str
    masked_memory_id: str
    baseline_answer_hash: Optional[str]
    masked_answer_hash: Optional[str]
    diff_criterion: str
    status: str
    masking_method: str = MASKING_METHOD_SELECTED_SET_REMOVAL

    def __post_init__(self) -> None:
        if self.status not in COUNTERFACTUAL_STATUSES:
            raise ValueError(f"status {self.status!r} is not one of {COUNTERFACTUAL_STATUSES!r}.")
        if self.diff_criterion not in DIFF_CRITERIA:
            raise ValueError(f"diff_criterion {self.diff_criterion!r} is not one of {DIFF_CRITERIA!r}.")


def compare_counterfactual_run(
    baseline: AgentRunOutcome,
    masked: CounterfactualRunOutcome,
    *,
    diff_criterion: str = DIFF_CRITERION_EXACT_NORMALIZED_MATCH,
) -> CounterfactualComparisonResult:
    """Compare `baseline.execution_result.answer` against `masked.masked_answer` under
    `diff_criterion`. A `None` answer on EITHER side is routed to an `INCONCLUSIVE_*`
    status BEFORE any diff attempt -- never diffed against a real answer as if it were
    meaningful content (mission section 4's required distinct outcome).
    """
    if baseline.execution_result.execution_status != EXECUTION_STATUS_SUCCESS or baseline.execution_result.answer is None:
        return CounterfactualComparisonResult(
            task_id=baseline.task_id,
            masked_memory_id=masked.masked_memory_id,
            baseline_answer_hash=None,
            masked_answer_hash=None,
            diff_criterion=diff_criterion,
            status=STATUS_INCONCLUSIVE_BASELINE_FAILURE,
        )

    baseline_answer_hash = fingerprint(baseline.execution_result.answer)

    if masked.masked_execution_status != EXECUTION_STATUS_SUCCESS or masked.masked_answer is None:
        return CounterfactualComparisonResult(
            task_id=baseline.task_id,
            masked_memory_id=masked.masked_memory_id,
            baseline_answer_hash=baseline_answer_hash,
            masked_answer_hash=None,
            diff_criterion=diff_criterion,
            status=STATUS_INCONCLUSIVE_GENERATION_FAILURE,
        )

    masked_answer_hash = fingerprint(masked.masked_answer)
    same = _answers_match(diff_criterion, baseline.execution_result.answer, masked.masked_answer)

    return CounterfactualComparisonResult(
        task_id=baseline.task_id,
        masked_memory_id=masked.masked_memory_id,
        baseline_answer_hash=baseline_answer_hash,
        masked_answer_hash=masked_answer_hash,
        diff_criterion=diff_criterion,
        status=STATUS_NOT_COUNTERFACTUALLY_INFLUENTIAL if same else STATUS_COUNTERFACTUALLY_INFLUENTIAL,
    )


# ---------------------------------------------------------------------------
# Deliverable 7 -- sampling strategy
# ---------------------------------------------------------------------------


def select_counterfactual_pairs(
    outcomes: Sequence[AgentRunOutcome],
    sample_size: Optional[int] = None,
    rng_seed: Optional[int] = None,
) -> Sequence[Tuple[str, str]]:
    """Every `(task_id, memory_id)` pair for every selected memory across `outcomes`
    (exhaustive, `sample_size=None`) or a deterministic, seeded, uniform-without-
    replacement sample of them (`sample_size` given).

    `rng_seed` is REQUIRED whenever `sample_size` is given (never an unseeded sample --
    reproducibility, per `REPRODUCIBILITY_CONTRACT.md`'s own spirit). If `sample_size`
    exceeds the number of available pairs, ALL available pairs are returned (capped, not
    an error) -- mission section 9's own required adversarial case.

    Deterministic: identical `outcomes` + `rng_seed` + `sample_size` always produce the
    identical pair list, regardless of any incidental dict/set iteration order (pairs are
    built by iterating `outcomes` and each outcome's own `selected_memory_ids` tuple, both
    already deterministically ordered).
    """
    all_pairs: List[Tuple[str, str]] = [
        (outcome.task_id, memory_id) for outcome in outcomes for memory_id in outcome.selected_memory_ids
    ]

    if sample_size is None:
        return tuple(all_pairs)

    if rng_seed is None:
        raise ValueError("rng_seed is required whenever sample_size is given -- never an unseeded sample.")

    if sample_size >= len(all_pairs):
        return tuple(all_pairs)

    rng = random.Random(rng_seed)
    return tuple(rng.sample(all_pairs, sample_size))


__all__ = [
    "DIFF_CRITERION_EXACT_NORMALIZED_MATCH",
    "DIFF_CRITERIA",
    "STATUS_COUNTERFACTUALLY_INFLUENTIAL",
    "STATUS_NOT_COUNTERFACTUALLY_INFLUENTIAL",
    "STATUS_INCONCLUSIVE_BASELINE_FAILURE",
    "STATUS_INCONCLUSIVE_GENERATION_FAILURE",
    "COUNTERFACTUAL_STATUSES",
    "MASKING_METHOD_SELECTED_SET_REMOVAL",
    "CounterfactualMaskingError",
    "CounterfactualRunOutcome",
    "CounterfactualComparisonResult",
    "run_counterfactual_mask",
    "compare_counterfactual_run",
    "select_counterfactual_pairs",
]
