"""Phase 3.2-H.3 (Memory Foundation Integration Architecture) -- security boundary
integration for foundation adapter methods.

Every `MemoryFoundationAdapter` method that could conceivably receive evaluator-only data
(it shouldn't, by design -- a foundation adapter's `add_memory()`/`retrieve()`/etc. should
only ever see agent-visible content) is checked here against
`security.leakage.validate_against_boundary` / `contracts.boundary.validate_agent_visible`,
REUSED verbatim -- this module builds no parallel leakage-detection logic.

Pure functions: no filesystem/network/LLM/embeddings access, no randomness.
"""

from __future__ import annotations

from typing import Any, Mapping

from phase3.evaluation.contracts.boundary import AgentVisibilityViolation
from phase3.evaluation.security.leakage import (
    STATUS_LEAKAGE_DETECTED,
    STATUS_NO_LEAKAGE,
    LeakageResult,
    validate_no_leakage,
)


class FoundationBoundaryViolation(ValueError):
    """Raised when a call into a `MemoryFoundationAdapter` method carries evaluator-only
    data (e.g. a `gold_answer`-shaped field smuggled into `add_memory()`'s `content` or
    `metadata` argument).
    """


def check_foundation_call_boundary(payload: Mapping[str, Any]) -> LeakageResult:
    """Run `payload` (an adapter method's `content`/`metadata`/`query` argument, or any
    other data destined to reach a foundation adapter) through
    `security.leakage.validate_no_leakage` (REUSED verbatim, condition=None since a
    foundation-adapter call is not itself one of `agent.conditions.ALL_CONDITIONS`).

    Returns the `LeakageResult` unchanged -- callers that want a hard failure use
    `enforce_foundation_call_boundary` instead.
    """
    return validate_no_leakage(payload, condition=None)


def enforce_foundation_call_boundary(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    """Same check as `check_foundation_call_boundary`, but raises
    `FoundationBoundaryViolation` on `STATUS_LEAKAGE_DETECTED` rather than returning a
    result the caller might forget to inspect. Returns `payload` unchanged on success.
    """
    result = check_foundation_call_boundary(payload)
    if result.status == STATUS_LEAKAGE_DETECTED:
        raise FoundationBoundaryViolation(
            "Evaluator-only data detected in a payload destined for a "
            f"MemoryFoundationAdapter method call: {result.summary}"
        )
    return payload


__all__ = [
    "FoundationBoundaryViolation",
    "check_foundation_call_boundary",
    "enforce_foundation_call_boundary",
    "AgentVisibilityViolation",
    "STATUS_NO_LEAKAGE",
    "STATUS_LEAKAGE_DETECTED",
]
