"""Phase 3.2-F — determinism checks.

Three concerns, kept separate per the task brief:

1. Repeated-run determinism: run the SAME synthetic evaluation N times and assert
   identical results. Reuses `phase3/evaluation/agent/outcomes.py::run_synthetic_agent`
   (the existing 3.2-E synthetic agent) -- this module does NOT build a second synthetic
   agent.
2. Order-sensitivity classification: some metrics are CORRECTLY order-sensitive
   (Recall@K, MRR/reciprocal-rank -- reordering `retrieved_ranked_ids` changes the
   result, because rank position is the entire point of these metrics) and some are
   CORRECTLY order-independent (set-based metrics: evidence precision/recall/coverage,
   selection count, strict TSR, equivalence-component checks -- these operate on sets, so
   reordering their input lists must NOT change the result). This module documents and
   tests the distinction; it never "fixes" order-sensitivity by auto-sorting a
   rank-ordered input, since doing so would silently destroy the metric's actual meaning.
3. Run isolation: run A, then run B, then run A again, and assert A's two runs are
   identical -- proving run B did not mutate any shared state that affected run A's
   second execution.

Global mutable state audit (by inspection, for the record; see README for the write-up):
`phase3/evaluation/metrics/*.py` and `phase3/evaluation/agent/*.py` were read in full for
this stage. Every function reads only its own parameters; no module in either package
defines a module-level mutable container (list/dict/set) that any function reads from or
writes to across calls. The only module-level containers found are immutable
(`frozenset`, `tuple`, `Mapping` literals of constant strings/dataclasses used as static
vocabularies, e.g. `EXECUTION_STATUSES`, `CANONICAL_CONDITIONS`, `FORBIDDEN_KEYS`) or
per-call-local. Conclusion: **no global mutable state was found in either package by
inspection.** This module's run-isolation check exists to make that conclusion an
empirically-tested claim, not merely an assertion -- it is easy to introduce shared state
by accident in a future change, and this test would catch it.

Pure, deterministic functions only (aside from invoking whatever callables the caller
supplies): no filesystem/network/LLM/embeddings access, no randomness, no global/mutable
state of this module's own.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Optional, Sequence

# ---------------------------------------------------------------------------
# Status vocabulary
# ---------------------------------------------------------------------------

STATUS_DETERMINISTIC = "DETERMINISTIC"
STATUS_NON_DETERMINISTIC = "NON_DETERMINISTIC"
STATUS_ISOLATED = "RUN_ISOLATED"
STATUS_CONTAMINATED = "RUN_CONTAMINATED"
STATUS_UNDEFINED_NO_RUNS = "UNDEFINED_NO_RUNS"

# ---------------------------------------------------------------------------
# Order-sensitivity classification (PROVISIONAL enumeration; see README)
# ---------------------------------------------------------------------------

ORDER_SENSITIVE = "ORDER_SENSITIVE"
ORDER_INDEPENDENT = "ORDER_INDEPENDENT"
ORDER_SENSITIVITY_UNKNOWN = "ORDER_SENSITIVITY_UNKNOWN"

# Metric names (matching `MetricResult.metric_name` string values) that are CORRECTLY
# order-sensitive: reordering their ranked input list changes the result, and that is the
# intended, load-bearing behavior of the metric, never a bug.
ORDER_SENSITIVE_METRIC_NAMES: frozenset[str] = frozenset({"RECALL_AT_K", "RECIPROCAL_RANK", "MRR"})

# Metric names that are CORRECTLY order-independent: they operate on sets, so any
# permutation of their input list(s) must produce an identical result.
ORDER_INDEPENDENT_METRIC_NAMES: frozenset[str] = frozenset(
    {
        "EVIDENCE_PRECISION",
        "EVIDENCE_RECALL",
        "EVIDENCE_COVERAGE",
        "IRRELEVANT_MEMORY_RATE",
        "REDUNDANCY",
        "SELECTION_COUNT",
        "STRICT_TSR",
        "SELECTION_CAPACITY",
    }
)


def classify_order_sensitivity(metric_name: str) -> str:
    """Look up whether `metric_name` is expected ORDER_SENSITIVE, ORDER_INDEPENDENT, or
    ORDER_SENSITIVITY_UNKNOWN (a metric name not in either enumerated set -- e.g. a future
    metric this stage does not yet know about). Never guesses; an unknown name is reported
    as unknown, not silently defaulted to either category.
    """
    if metric_name in ORDER_SENSITIVE_METRIC_NAMES:
        return ORDER_SENSITIVE
    if metric_name in ORDER_INDEPENDENT_METRIC_NAMES:
        return ORDER_INDEPENDENT
    return ORDER_SENSITIVITY_UNKNOWN


# ---------------------------------------------------------------------------
# Repeated-run determinism
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DeterminismResult:
    status: str
    num_runs: int
    results: Sequence[Any] = field(default_factory=tuple)
    detail: Mapping[str, Any] = field(default_factory=dict)


def run_n_times(run_fn: Callable[[], Any], n: int) -> Sequence[Any]:
    """Invoke `run_fn` (a zero-argument callable, e.g. a closure wrapping
    `agent.outcomes.run_synthetic_agent(...)` with fixed arguments) exactly `n` times and
    return the list of results, in call order. Does not itself compare the results --
    see `check_repeated_run_determinism`.
    """
    return [run_fn() for _ in range(n)]


def check_repeated_run_determinism(run_fn: Callable[[], Any], n: int = 5) -> DeterminismResult:
    """Run `run_fn` `n` times and assert every result is `==`-equal to the first.

    Designed for `run_fn` returning a value with a structural `__eq__` -- e.g.
    `AgentExecutionResult` (a frozen dataclass, per `agent/outcomes.py`) or `MetricResult`
    (also a frozen dataclass, per `metrics/types.py`). Both compare by field value, so this
    directly answers "did the SAME synthetic evaluation, run N times, produce identical
    results" without this module needing any bespoke comparison logic per result type.

    Edge case: `n <= 0` -> undefined (`status=STATUS_UNDEFINED_NO_RUNS`), never silently
    reported as deterministic (there is nothing to compare).
    """
    if n <= 0:
        return DeterminismResult(
            status=STATUS_UNDEFINED_NO_RUNS,
            num_runs=0,
            results=(),
            detail={"n_requested": n},
        )

    results = run_n_times(run_fn, n)
    first = results[0]
    all_identical = all(r == first for r in results)

    return DeterminismResult(
        status=STATUS_DETERMINISTIC if all_identical else STATUS_NON_DETERMINISTIC,
        num_runs=n,
        results=tuple(results),
        detail={
            "all_identical": all_identical,
            "distinct_result_count": len({repr(r) for r in results}),
        },
    )


# ---------------------------------------------------------------------------
# Run isolation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RunIsolationResult:
    status: str
    detail: Mapping[str, Any] = field(default_factory=dict)


def check_run_isolation(
    run_a_fn: Callable[[], Any],
    run_b_fn: Callable[[], Any],
) -> RunIsolationResult:
    """Execute run A, then run B, then run A again; assert A's two executions are
    identical, proving run B did not mutate shared state that affected A's second
    execution.

    Parameters
    ----------
    run_a_fn, run_b_fn:
        Zero-argument callables. Each is expected to be independently deterministic (per
        `check_repeated_run_determinism`) -- this function does not re-verify that on its
        own; it isolates the narrower "did B contaminate A" question.

    Returns
    -------
    RunIsolationResult with status RUN_ISOLATED if `run_a_fn()`'s two invocations are
    `==`-equal, else RUN_CONTAMINATED.
    """
    a1 = run_a_fn()
    _b = run_b_fn()
    a2 = run_a_fn()

    isolated = a1 == a2
    return RunIsolationResult(
        status=STATUS_ISOLATED if isolated else STATUS_CONTAMINATED,
        detail={
            "a1": repr(a1),
            "a2": repr(a2),
            "isolated": isolated,
        },
    )


# ---------------------------------------------------------------------------
# Order-sensitivity behavioral proof helpers
# ---------------------------------------------------------------------------


def reorder(sequence: Sequence[Any]) -> list:
    """Return a permutation of `sequence` distinct from the input, when possible.

    Deterministic (not random): reverses the sequence. If the sequence has fewer than 2
    distinct-position elements such that reversal is a no-op (length 0 or 1, or a
    palindrome-like sequence of identical elements), the caller is responsible for
    supplying a fixture where reversal actually changes order -- this helper does not try
    to invent an alternate permutation strategy.
    """
    return list(reversed(list(sequence)))


def sets_equal_ignoring_order(a: Sequence[Any], b: Sequence[Any]) -> bool:
    """True iff `a` and `b` contain the same elements as sets (order and duplicate count
    ignored). Convenience for order-independence tests -- not itself a metric.
    """
    return set(a) == set(b)
