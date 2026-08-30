"""Phase 3.2-H.3 (Memory Foundation Integration Architecture) -- reset/isolation
checking for foundation adapter STATE, mirroring
`phase3.evaluation.security.determinism.check_run_isolation`'s A->B->A pattern.

WHY A REPRODUCIBILITY_LIMITATION STATUS, HONESTLY, FOR ALL FOUR FOUNDATIONS
--------------------------------------------------------------------------------
`determinism.check_run_isolation` executes run A, then run B, then run A again, and
compares A's two results. That pattern is directly reusable against a MOCK foundation
adapter (constructed fresh, or reset between calls) -- and this module does exactly that,
via `check_foundation_reset_isolation` below. But NONE of the four real foundations
(Mem0/Letta/Graphiti/A-MEM) is actually running in this framework-architecture stage (per
the mission's explicit scope), so this module's A->B->A check can only ever be exercised
against the deterministic mock adapters under `foundations/mocks/` -- it CANNOT yet verify
that a REAL Mem0/Letta/Graphiti/A-MEM `reset()` call genuinely isolates state the way the
mock's does. `REPRODUCIBILITY_LIMITATION` is the honest, explicit status this module
returns (via `foundation_reset_isolation_status`) for every one of the four real
foundations, pending H.4's real-conformance verification -- never silently reported as
`RUN_ISOLATED` for a foundation that was never actually run.

Pure functions: no filesystem/network/LLM/embeddings access, no randomness beyond what a
caller-supplied `run_a_fn`/`run_b_fn` might introduce (none of this module's own code
introduces any).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from phase3.evaluation.foundations.capability_audit import ALL_FOUNDATIONS
from phase3.evaluation.security.determinism import (
    STATUS_CONTAMINATED,
    STATUS_ISOLATED,
    RunIsolationResult,
    check_run_isolation,
)

STATUS_REPRODUCIBILITY_LIMITATION = "REPRODUCIBILITY_LIMITATION"


@dataclass(frozen=True)
class FoundationResetIsolationResult:
    status: str
    detail: Mapping[str, Any] = field(default_factory=dict)


def check_foundation_reset_isolation(
    run_a_fn: Callable[[], Any],
    run_b_fn: Callable[[], Any],
) -> FoundationResetIsolationResult:
    """A->B->A isolation check against a MOCK foundation adapter's state (e.g. `run_a_fn`
    exports state after an `add_memory()` + `retrieve()` scenario, `run_b_fn` runs a
    DIFFERENT scenario on the SAME adapter instance after a `reset()` call in between).

    REUSES `security.determinism.check_run_isolation` verbatim -- this function is a thin
    wrapper that renames the returned status constants (`RUN_ISOLATED`/`RUN_CONTAMINATED`)
    to this module's own vocabulary so callers never need to import `security.determinism`
    directly for this specific check, while the underlying comparison logic is completely
    unmodified.
    """
    result: RunIsolationResult = check_run_isolation(run_a_fn, run_b_fn)
    return FoundationResetIsolationResult(status=result.status, detail=dict(result.detail))


def foundation_reset_isolation_status(foundation_id: str) -> FoundationResetIsolationResult:
    """The HONEST, stage-appropriate status for one of the four REAL foundations (not a
    mock): always `REPRODUCIBILITY_LIMITATION`, since no real foundation is actually
    running in this stage and this module's A->B->A check has therefore never been
    exercised against it. Raises `KeyError` for an unrecognized foundation id.
    """
    if foundation_id not in ALL_FOUNDATIONS:
        raise KeyError(f"foundation_id {foundation_id!r} is not one of {ALL_FOUNDATIONS!r}")
    return FoundationResetIsolationResult(
        status=STATUS_REPRODUCIBILITY_LIMITATION,
        detail={
            "foundation_id": foundation_id,
            "reason": (
                "No real foundation integration exists in this framework-architecture "
                "stage; reset/isolation can only be verified against the deterministic "
                "mock adapter for this foundation. Real-conformance verification is "
                "explicitly deferred to a future H.4 stage."
            ),
        },
    )


__all__ = [
    "STATUS_REPRODUCIBILITY_LIMITATION",
    "STATUS_ISOLATED",
    "STATUS_CONTAMINATED",
    "FoundationResetIsolationResult",
    "check_foundation_reset_isolation",
    "foundation_reset_isolation_status",
]
