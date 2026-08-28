"""Phase 3.2-H — the integrated result data model.

Design principle (mirrors `metrics/types.py::MetricResult` and `agent/outcomes.py`'s
"never one overloaded field" convention): every per-metric slot in `EvaluationCaseResult`
holds either a real `MetricResult` (from `phase3/evaluation/metrics/`) or an explicit
NOT_ATTEMPTED marker -- itself represented as a `MetricResult` with
`status=STATUS_NOT_ATTEMPTED`, so callers can keep using the same uniform envelope/status
check everywhere, never a bare number and never `None` used as a stand-in for "we didn't
try this."

STATUS_NOT_ATTEMPTED is a NEW status this integration stage introduces -- it does not
exist in `phase3/evaluation/metrics/types.py`. It answers a question no prior stage asked:
"was this metric's precondition ruled out at the DATASET level (per the dataset's
evaluation profile), before we even looked at this specific case's data?" This is
distinct from a metric's own native undefined status (e.g. `STATUS_UNDEFINED_EMPTY_GOLD`),
which answers "was this metric's precondition ruled out by THIS CASE's actual data, on a
dataset that otherwise supports the metric?" See `validation.py` and `pipeline.py` for
where this distinction is applied, and README.md for the worked before/after examples.

This module has no filesystem/network/LLM/embeddings/randomness dependency and no
global/mutable state, matching every other module in `phase3/evaluation/`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence

from phase3.evaluation.metrics.types import MetricResult

# ---------------------------------------------------------------------------
# New integration-level status (PROVISIONAL; see module docstring)
# ---------------------------------------------------------------------------

STATUS_NOT_ATTEMPTED = "NOT_ATTEMPTED"


def not_attempted(metric_name: str, reason: str, scope: str, **detail: Any) -> MetricResult:
    """Build the uniform NOT_ATTEMPTED marker for one metric slot.

    Parameters
    ----------
    metric_name:
        The metric family name (matches `phase3.evaluation.datasets.capability.METRIC_NAMES`
        where applicable, or a metric's own `MetricResult.metric_name` string).
    reason:
        Human-readable reason, always traceable to a specific profile field or case fact
        (never a bare "not available").
    scope:
        One of `"DATASET"` (the profile rules this out for the whole dataset -- e.g. MSC's
        `workload_availability.explicit_task_records` is `NOT_PROVIDED_BY_SOURCE`) or
        `"CASE"` (this specific case's data rules it out, but the dataset in general
        supports the metric). This is exactly the distinction the 3.2-H task brief
        requires never be collapsed.
    """
    if scope not in ("DATASET", "CASE"):
        raise ValueError(f"scope must be 'DATASET' or 'CASE', got {scope!r}")
    return MetricResult(
        metric_name=metric_name,
        value=None,
        status=STATUS_NOT_ATTEMPTED,
        detail={"reason": reason, "scope": scope, **detail},
        note=f"NOT_ATTEMPTED ({scope}-level): {reason}",
    )


# ---------------------------------------------------------------------------
# Integrated result envelope
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EvaluationCaseResult:
    """The single integrated result object for one evaluation case run through the
    pipeline in `pipeline.py`.

    Attributes
    ----------
    dataset_id:
        One of `phase3.evaluation.datasets.capability.DATASET_IDS`.
    case_id:
        Identity for this synthetic/fixture case (analogous to `task_id`).
    condition:
        One of `phase3.evaluation.agent.conditions.ALL_CONDITIONS`.
    metrics:
        Mapping of metric-family name -> `MetricResult` (real OR NOT_ATTEMPTED marker).
        Never a bare float/int/bool anywhere in this mapping.
    agent_execution_result:
        The `phase3.evaluation.agent.outcomes.AgentExecutionResult` produced or supplied
        for this case, or `None` if the condition/dataset does not support agent execution
        at all (task layer unavailable).
    agent_success:
        `MetricResult` (via `outcomes.classify_agent_success`, or NOT_ATTEMPTED) --
        kept as its own named field (not folded into `metrics`) since it is the
        single most load-bearing agent-level outcome.
    leakage_result:
        `phase3.evaluation.security.leakage.LeakageResult` for the agent-visible context.
    trace:
        A `TraceArtifact`-shaped plain dict (see `pipeline.py::_build_trace`).
    evaluation_result:
        An `EvaluationResult`-shaped plain dict (see `pipeline.py::_build_evaluation_result`).
    fingerprints:
        Mapping of fingerprint name -> hex digest string, via
        `security.reproducibility.fingerprint`.
    warnings:
        Non-fatal notes accumulated during pipeline execution (e.g. "condition is
        PROVISIONAL, schema validation against agent_visible_context.schema.json was
        skipped").
    """

    dataset_id: str
    case_id: str
    condition: str
    metrics: Mapping[str, MetricResult] = field(default_factory=dict)
    agent_execution_result: Optional[Any] = None
    agent_success: Optional[MetricResult] = None
    leakage_result: Optional[Any] = None
    trace: Mapping[str, Any] = field(default_factory=dict)
    evaluation_result: Mapping[str, Any] = field(default_factory=dict)
    fingerprints: Mapping[str, str] = field(default_factory=dict)
    warnings: Sequence[str] = field(default_factory=tuple)
