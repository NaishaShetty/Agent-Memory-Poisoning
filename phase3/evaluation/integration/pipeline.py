"""Phase 3.2-H — the single orchestration path.

`evaluate_case()` composes, in order:

1. Condition validation                  -- `agent.conditions.ALL_CONDITIONS` membership.
2. Contract-shape validation              -- `jsonschema.Draft202012Validator` against
                                              `agent_visible_context.schema.json` (canonical
                                              conditions only, matching
                                              `agent.conditions`'s own documented behavior
                                              for provisional conditions).
3. Leakage validation                     -- `security.leakage.validate_against_boundary`.
4. Agent execution                       -- either a caller-supplied
                                              `agent.outcomes.AgentExecutionResult`, or
                                              `agent.outcomes.run_synthetic_agent`.
5. Metric computation                    -- one function per
                                              `datasets.capability.METRIC_NAMES` family,
                                              gated by the dataset profile's
                                              `metric_support` entry (see `validation.py`),
                                              calling the REAL metric function from
                                              `phase3/evaluation/metrics/` for every family
                                              that is attempted -- never reimplemented here.
6. Agent-level diagnostics                -- `agent.diagnostics`/`agent.outcomes` functions.
7. Trace + EvaluationResult assembly      -- plain dicts shaped like
                                              `trace_artifact.schema.json` /
                                              `evaluation_result.schema.json`, schema-
                                              validated the same way.
8. Fingerprinting                         -- `security.reproducibility.fingerprint`/
                                              `canonical_serialize`/`build_manifest`.

No metric, condition, leakage rule, or fingerprint function is reimplemented anywhere in
this module -- every computational step is a call into an existing 3.2-B..3.2-G module.
See README.md for the full call inventory.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from jsonschema import Draft202012Validator

from phase3.evaluation.agent import diagnostics as a_diagnostics
from phase3.evaluation.agent import outcomes as a_outcomes
from phase3.evaluation.agent import paired as a_paired
from phase3.evaluation.agent.conditions import ALL_CONDITIONS, CANONICAL_CONDITIONS
from phase3.evaluation.datasets import capability as cap
from phase3.evaluation.metrics import equivalence as m_equivalence
from phase3.evaluation.metrics import evidence as m_evidence
from phase3.evaluation.metrics import provenance as m_provenance
from phase3.evaluation.metrics import retrieval as m_retrieval
from phase3.evaluation.metrics import selection as m_selection
from phase3.evaluation.metrics.types import MetricResult, STATUS_UNDEFINED_EMPTY_GOLD
from phase3.evaluation.security import leakage as sec_leakage
from phase3.evaluation.security import reproducibility as sec_repro

from . import validation as val
from .dataset_adapter import EvaluationCase
from .result import EvaluationCaseResult, STATUS_NOT_ATTEMPTED, not_attempted

_SCHEMAS_DIR = Path(__file__).resolve().parent.parent / "contracts"

# ---------------------------------------------------------------------------
# Phase 3.2-H.4 finding: `_build_trace`/`_build_evaluation_result` stamp a wall-clock
# `datetime.now(timezone.utc)` value into `created_at`/`evaluation_timestamp` on every
# call. Confirmed by inspection (not assumed) that `fingerprints["trace"]`,
# `fingerprints["evaluation_result"]`, and `fingerprints["overall"]` below are computed
# via `sec_repro.fingerprint()` directly over these dicts -- the RAW fingerprint, not
# `sec_repro.manifest_semantic_fingerprint()` (which excludes
# `sec_repro.MANIFEST_METADATA_ONLY_FIELDS`, i.e. `timestamp`, from its own object shape).
# This means two runs of `evaluate_case()` over IDENTICAL input, seconds apart, produced
# DIFFERENT `trace`/`evaluation_result`/`overall` fingerprints purely from wall-clock time
# -- a genuine reproducibility defect (not merely a metadata-only field sitting outside a
# fingerprint, the H.3-flagged concern this stage was asked to assess), because it reaches
# a *semantic* fingerprint field that downstream reproducibility checks treat as evidence
# of a re-run's result matching a prior one bit-for-bit.
#
# Minimal fix, mirroring `security.reproducibility.MANIFEST_METADATA_ONLY_FIELDS` /
# `manifest_semantic_fingerprint()`'s existing pattern exactly: exclude exactly the one
# wall-clock field from each dict before fingerprinting it, while leaving the RETURNED
# `trace`/`evaluation_result` dicts (and their schema validation) completely unchanged --
# a consumer that wants the real creation time still gets it in `case_result.trace[
# "created_at"]` / `case_result.evaluation_result["evaluation_timestamp"]`; only the
# FINGERPRINT computation is timestamp-invariant, exactly as `manifest_semantic_
# fingerprint()` already makes manifest fingerprints timestamp-invariant.
_TRACE_METADATA_ONLY_FIELDS: frozenset = frozenset({"created_at"})
_EVALUATION_RESULT_METADATA_ONLY_FIELDS: frozenset = frozenset({"evaluation_timestamp"})


def _semantic_view(payload: Mapping[str, Any], metadata_only_fields: frozenset) -> dict:
    """Same exclusion pattern as `sec_repro.manifest_semantic_fingerprint`'s inline
    semantic-view construction, generalized to any metadata-only field set. Does not
    reimplement `fingerprint`/`canonical_serialize` -- only builds the dict handed to it.
    """
    return {k: v for k, v in payload.items() if k not in metadata_only_fields}

_AGENT_RESULT_REQUIRED_METRIC_FAMILIES = (
    "RETRIEVAL_UTILIZATION",
    "FAILURE_STAGE_CLASSIFICATION",
    "AGENT_ANSWER_CORRECTNESS",
    "AGENT_SUCCESS",
)


def _load_schema(name: str) -> Mapping[str, Any]:
    path = _SCHEMAS_DIR / f"{name}.schema.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


_AGENT_VISIBLE_CONTEXT_SCHEMA = _load_schema("agent_visible_context")
_TRACE_ARTIFACT_SCHEMA = _load_schema("trace_artifact")
_EVALUATION_RESULT_SCHEMA = _load_schema("evaluation_result")
_EVALUATOR_REFERENCE_SCHEMA = _load_schema("evaluator_reference")

# Keys this integration layer's own EvaluatorReference-shaped dict carries for internal
# bookkeeping (see dataset_adapter.build_evaluator_reference) that are NOT part of the
# frozen evaluator_reference.schema.json (whose additionalProperties is false) -- excluded
# before schema validation, never sent to the schema itself.
_EVALUATOR_REFERENCE_INTEGRATION_ONLY_KEYS = frozenset({"applicable", "dataset_id"})


def validate_evaluator_reference_shape(evaluator_reference: Mapping[str, Any]) -> None:
    """Schema-validate the evaluator_reference.schema.json-relevant subset of an
    integration-built EvaluatorReference-shaped dict (3.2-H remediation: this schema now
    accepts `gold_answer: null`, per the fixed evaluator_reference.schema.json -- see
    README.md "Contract inconsistency resolved"). Raises `jsonschema.ValidationError` on a
    genuine violation (e.g. a missing `gold_answer` key, still required).
    """
    schema_shaped = {
        k: v for k, v in evaluator_reference.items() if k not in _EVALUATOR_REFERENCE_INTEGRATION_ONLY_KEYS
    }
    Draft202012Validator(_EVALUATOR_REFERENCE_SCHEMA).validate(schema_shaped)


# ---------------------------------------------------------------------------
# Step 1-2: condition + contract-shape validation
# ---------------------------------------------------------------------------


def validate_condition(condition: str) -> None:
    if condition not in ALL_CONDITIONS:
        raise ValueError(f"condition {condition!r} is not one of {ALL_CONDITIONS!r}")


def validate_agent_visible_context_shape(
    agent_visible_context: Mapping[str, Any], condition: str
) -> Sequence[str]:
    """Schema-validate `agent_visible_context` against `agent_visible_context.schema.json`
    for a CANONICAL condition (the schema's `condition` enum only accepts the three
    canonical values, per `agent.conditions`'s own documented behavior). For a PROVISIONAL
    condition, schema validation is skipped and a warning string is returned instead --
    this mirrors `agent.conditions.build_agent_visible_context`'s own documented choice,
    not a new decision invented here.

    Returns a (possibly empty) list of warning strings; raises `jsonschema.ValidationError`
    on a genuine schema violation for a canonical condition.
    """
    if condition not in CANONICAL_CONDITIONS:
        return [
            f"condition={condition!r} is PROVISIONAL (3.2-E, diagnostic-only); schema "
            "validation against agent_visible_context.schema.json's condition enum "
            "(three canonical values only) was skipped, matching agent.conditions's own "
            "documented behavior for provisional conditions."
        ]
    validator = Draft202012Validator(_AGENT_VISIBLE_CONTEXT_SCHEMA)
    validator.validate(agent_visible_context)
    return []


# ---------------------------------------------------------------------------
# Step 5: per-metric-family computation
# ---------------------------------------------------------------------------


def _compute_strict_tsr(selected_ids: Sequence[str], gold_ids: Sequence[str]) -> MetricResult:
    """Record-level wrapper: `selection.strict_tsr()` itself treats empty `gold_ids` as a
    well-defined 0.0/STATUS_OK (see its module docstring) -- for THIS integration, when the
    dataset profile has already confirmed evidence is available IN GENERAL but THIS case's
    `gold_evidence_ids` happens to be empty, we report the metric's sibling
    `STATUS_UNDEFINED_EMPTY_GOLD` status (imported verbatim from `metrics.types`, the exact
    status `recall_at_k`/`evidence_recall` already use for the identical precondition)
    instead of trusting strict_tsr's own OK/0.0 for this specific integration use --
    this is the "Strict TSR UNDEFINED, not 0" distinction the 3.2-H task brief requires.
    strict_tsr() itself is NOT modified; this is a thin, additive, case-level guard applied
    only inside the integration layer.
    """
    if not gold_ids:
        return MetricResult(
            metric_name="STRICT_TSR",
            value=None,
            status=STATUS_UNDEFINED_EMPTY_GOLD,
            detail={"selected_ids": list(selected_ids), "gold_empty": True},
            note=(
                "Record-level: gold_evidence_ids is empty for this specific case even "
                "though the dataset profile supports STRICT_TSR in general. Distinct from "
                "a dataset-level NOT_ATTEMPTED (see metric_support_gate)."
            ),
        )
    return m_selection.strict_tsr(selected_ids, gold_ids)


def _lineage_diagnostics(memories: Mapping[str, Any], selected_ids: Sequence[str]) -> MetricResult:
    """LINEAGE_DIAGNOSTICS family -> `provenance.independence_report()`, the function that
    most directly consumes lineage (`ancestors`/`descendants`/`root_origins`, all called
    internally by `independence_report`) over a selected-memory set."""
    if not selected_ids:
        return not_attempted(
            "LINEAGE_DIAGNOSTICS", "no selected_memory_ids for this case", scope="CASE"
        )
    return m_provenance.independence_report(memories, list(selected_ids))


def compute_metric(
    metric_family: str,
    profile: Mapping[str, Any],
    case: EvaluationCase,
    agent_result: Optional[a_outcomes.AgentExecutionResult],
) -> MetricResult:
    """Compute ONE metric family for one case, gated by the dataset profile's
    `metric_support` entry (`validation.metric_support_gate`). Never silently computes a
    metric the profile rules out; never silently skips one either -- always returns a
    `MetricResult` (real or NOT_ATTEMPTED)."""
    attempt, reason = val.metric_support_gate(profile, metric_family)
    if not attempt:
        return not_attempted(metric_family, reason, scope="DATASET")

    if metric_family in _AGENT_RESULT_REQUIRED_METRIC_FAMILIES and agent_result is None:
        return not_attempted(
            metric_family,
            "no agent execution result is available for this case (no task layer, or "
            "execution was never run)",
            scope="CASE",
        )

    gold_ids = list(case.evaluator_reference.get("gold_evidence_ids", [])) if case.task_applicable else []
    gold_answer = case.evaluator_reference.get("gold_answer") if case.task_applicable else None
    selected_ids = list(agent_result.selected_memory_ids) if agent_result is not None else list(case.selected_memory_ids)
    retrieved_ids = list(case.retrieved_memory_ids)

    if metric_family == "RECALL_AT_K":
        return m_retrieval.recall_at_k(retrieved_ids, gold_ids, k=5)
    if metric_family == "MRR":
        return m_retrieval.reciprocal_rank(retrieved_ids, gold_ids)
    if metric_family == "STRICT_TSR":
        return _compute_strict_tsr(selected_ids, gold_ids)
    if metric_family == "SELECTION_COUNT":
        return m_selection.selection_count(selected_ids)
    if metric_family == "SELECTION_CAPACITY_DIAGNOSTICS":
        return m_retrieval.selection_capacity_report(retrieved_ids, selected_ids, gold_ids)
    if metric_family == "EVIDENCE_PRECISION":
        return m_evidence.evidence_precision(selected_ids, gold_ids)
    if metric_family == "EVIDENCE_RECALL":
        return m_evidence.evidence_recall(selected_ids, gold_ids)
    if metric_family == "EVIDENCE_COVERAGE":
        return m_evidence.evidence_coverage(retrieved_ids, gold_ids)
    if metric_family == "IRRELEVANT_MEMORY_RATE":
        return m_evidence.irrelevant_memory_rate(selected_ids, gold_ids)
    if metric_family == "REDUNDANCY":
        return m_evidence.redundancy(selected_ids)
    if metric_family == "EQUIVALENCE_DIAGNOSTICS":
        if not case.memories:
            return not_attempted(metric_family, "no memories supplied for this case", scope="CASE")
        return m_equivalence.equivalence_classes(memories=case.memories)
    if metric_family == "PROVENANCE_VALIDATION":
        if not case.memories:
            return not_attempted(metric_family, "no memories supplied for this case", scope="CASE")
        return m_provenance.provenance_completeness_report(case.memories)
    if metric_family == "LINEAGE_DIAGNOSTICS":
        return _lineage_diagnostics(case.memories, selected_ids)
    if metric_family == "AGENT_ANSWER_CORRECTNESS":
        return a_outcomes.evaluate_answer_correctness(agent_result, gold_answer)
    if metric_family == "AGENT_SUCCESS":
        return a_outcomes.classify_agent_success(agent_result, gold_answer)
    if metric_family == "MEMORY_CONTRIBUTION":
        return not_attempted(
            metric_family,
            "MEMORY_CONTRIBUTION requires a paired NO_MEMORY/WITH_MEMORY comparison across "
            "two execution results for the same task -- use evaluate_paired_case() for this "
            "family, it is not a single-case metric",
            scope="CASE",
        )
    if metric_family == "OBSERVED_GOLD_EVIDENCE_CEILING":
        return not_attempted(
            metric_family,
            "OBSERVED_GOLD_EVIDENCE_CEILING is an aggregate over a SET of GOLD_EVIDENCE-"
            "condition results across multiple cases -- use evaluate_gold_evidence_ceiling(), "
            "it is not a single-case metric",
            scope="CASE",
        )
    if metric_family == "RETRIEVAL_UTILIZATION":
        return a_diagnostics.classify_retrieval_utilization(agent_result)
    if metric_family == "FAILURE_STAGE_CLASSIFICATION":
        return a_diagnostics.classify_observed_failure_stage(
            agent_result, gold_answer, gold_ids, retrieved_ids
        )

    raise KeyError(f"Unhandled metric family {metric_family!r}")


# ---------------------------------------------------------------------------
# Step 7: trace + evaluation-result assembly
# ---------------------------------------------------------------------------


def _build_trace(case: EvaluationCase, agent_result: Optional[a_outcomes.AgentExecutionResult]) -> dict:
    """Assemble a `TraceArtifact`-shaped dict (schema-validated by the caller). Every field
    past schema_version/task_id remains largely null/placeholder for candidate_discovery/
    reranking (those layers are not implemented anywhere in Phase 3.2, per
    trace_artifact.schema.json's own description) -- this integration populates only what
    it genuinely has: candidate_set (retrieved_memory_ids), selected_evidence
    (selected_memory_ids), reasoning_context (a reference to the agent-visible context),
    and final_response (the agent's raw answer).
    """
    trace: dict = {
        "schema_version": "3.2-b.1",
        "task_id": case.case_id,
        "run_id": None,
        "task": {"prompt": case.agent_visible_context["task"]["prompt"]} if case.agent_visible_context else None,
        "candidate_discovery": None,
        "candidate_set": list(case.retrieved_memory_ids) if case.retrieved_memory_ids else None,
        "reranking": None,
        "selection": None,
        "selected_evidence": (
            list(agent_result.selected_memory_ids) if agent_result is not None else (
                list(case.selected_memory_ids) if case.selected_memory_ids else None
            )
        ),
        "reasoning_context": (
            {"condition": case.condition, "memory_content_count": len(case.agent_visible_context.get("memory_content", []))}
            if case.agent_visible_context is not None
            else None
        ),
        "reasoning_output": None,
        "final_response": agent_result.answer if agent_result is not None else None,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    return trace


def _build_evaluation_result(
    case: EvaluationCase,
    metrics: Mapping[str, MetricResult],
    agent_success: Optional[MetricResult],
) -> dict:
    """Assemble an `EvaluationResult`-shaped dict. `metrics` is populated with every
    metric family's result serialized to a plain dict (metric_name/value/status/detail/
    note) -- `evaluation_result.schema.json`'s `metrics` field is an open/placeholder
    object by design (3.2-B), so this is a legitimate, additive population of it, not a
    schema violation.
    """
    result_status = "COMPLETE"
    if any(m.status == STATUS_NOT_ATTEMPTED for m in metrics.values()):
        result_status = "PARTIAL"

    return {
        "schema_version": "3.2-b.1",
        "run_id": f"integration-{case.dataset_id}-{case.case_id}-{case.condition}",
        "evaluator_version": "3.2-h.1",
        "metric_set_version": "3.2-h.1",
        "result_status": result_status,
        "metrics": {
            name: {
                "metric_name": m.metric_name,
                "value": m.value,
                "status": m.status,
                "detail": dict(m.detail),
                "note": m.note,
            }
            for name, m in metrics.items()
        },
        "warnings": [],
        "errors": [],
        "evaluation_timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


# ---------------------------------------------------------------------------
# Main orchestration entry point
# ---------------------------------------------------------------------------


def evaluate_case(
    case: EvaluationCase,
    profile: Mapping[str, Any],
    agent_execution_result: Optional[a_outcomes.AgentExecutionResult] = None,
    synthetic_behavior: Optional[str] = None,
) -> EvaluationCaseResult:
    """Run one `EvaluationCase` through the full integration pipeline.

    Parameters
    ----------
    agent_execution_result:
        A caller-supplied `AgentExecutionResult` (e.g. from a different synthetic path, or
        a future real agent). If given, `synthetic_behavior` is ignored.
    synthetic_behavior:
        One of `agent.outcomes.SYNTHETIC_BEHAVIORS`, used to run
        `agent.outcomes.run_synthetic_agent()` when `agent_execution_result` is not
        supplied and the case is task-applicable. If neither is supplied (or the case is
        not task-applicable), no agent is run and `agent_execution_result` stays `None`
        throughout.

    Raises
    ------
    validation.ProfileEvaluationInconsistency
        If the profile itself is internally inconsistent (checked BEFORE any metric is
        computed) -- this is a genuine, checked pre-flight assertion, never bypassed.
    jsonschema.ValidationError
        If a canonical-condition agent_visible_context fails schema validation.
    """
    val.assert_all_invariants(profile)
    validate_condition(case.condition)

    warnings: list = []

    if case.task_applicable:
        validate_evaluator_reference_shape(case.evaluator_reference)

    leakage_result = None
    if case.agent_visible_context is not None:
        warnings.extend(validate_agent_visible_context_shape(case.agent_visible_context, case.condition))
        leakage_result = sec_leakage.validate_against_boundary(case.agent_visible_context)
    else:
        warnings.append(
            f"no agent_visible_context for this case: {case.task_not_applicable_reason}"
        )

    agent_result = agent_execution_result
    if agent_result is None and case.task_applicable and case.agent_visible_context is not None and synthetic_behavior:
        agent_result = a_outcomes.run_synthetic_agent(
            task_id=case.case_id,
            condition=case.condition,
            behavior=synthetic_behavior,
            agent_visible_context=case.agent_visible_context,
            expected_answer=case.evaluator_reference.get("gold_answer"),
            selected_memory_ids=case.selected_memory_ids,
            used_memory_ids=case.used_memory_ids,
        )

    metrics: dict = {}
    for metric_family in cap.METRIC_NAMES:
        metrics[metric_family] = compute_metric(metric_family, profile, case, agent_result)

    agent_success = metrics.get("AGENT_SUCCESS")

    trace = _build_trace(case, agent_result)
    Draft202012Validator(_TRACE_ARTIFACT_SCHEMA).validate(trace)

    evaluation_result = _build_evaluation_result(case, metrics, agent_success)
    Draft202012Validator(_EVALUATION_RESULT_SCHEMA).validate(evaluation_result)

    trace_semantic = _semantic_view(trace, _TRACE_METADATA_ONLY_FIELDS)
    evaluation_result_semantic = _semantic_view(
        evaluation_result, _EVALUATION_RESULT_METADATA_ONLY_FIELDS
    )

    fingerprints = {
        "agent_visible_context": sec_repro.fingerprint(case.agent_visible_context)
        if case.agent_visible_context is not None
        else sec_repro.fingerprint(None),
        "evaluator_reference": sec_repro.fingerprint(case.evaluator_reference),
        # Timestamp-invariant: fingerprinted over the semantic view (created_at excluded),
        # mirroring `sec_repro.manifest_semantic_fingerprint`'s existing discipline. The
        # returned `trace` dict itself still carries the real `created_at` value.
        "trace": sec_repro.fingerprint(trace_semantic),
        # Timestamp-invariant for the same reason (evaluation_timestamp excluded).
        "evaluation_result": sec_repro.fingerprint(evaluation_result_semantic),
        "metrics": sec_repro.fingerprint(evaluation_result["metrics"]),
    }
    fingerprints["overall"] = sec_repro.fingerprint(
        {"evaluation_result": evaluation_result_semantic, "trace": trace_semantic}
    )

    return EvaluationCaseResult(
        dataset_id=case.dataset_id,
        case_id=case.case_id,
        condition=case.condition,
        metrics=metrics,
        agent_execution_result=agent_result,
        agent_success=agent_success,
        leakage_result=leakage_result,
        trace=trace,
        evaluation_result=evaluation_result,
        fingerprints=fingerprints,
        warnings=tuple(warnings),
    )


# ---------------------------------------------------------------------------
# Aggregate helpers (MEMORY_CONTRIBUTION / OBSERVED_GOLD_EVIDENCE_CEILING) --
# these are genuinely cross-case, so they live outside the single-case compute_metric().
# ---------------------------------------------------------------------------


def evaluate_paired_case(
    no_memory_result: a_outcomes.AgentExecutionResult,
    with_memory_result: a_outcomes.AgentExecutionResult,
    expected_answer: Optional[str],
) -> MetricResult:
    """MEMORY_CONTRIBUTION for one task, via `agent.paired.classify_memory_contribution`
    (reused verbatim, not reimplemented)."""
    return a_paired.classify_memory_contribution(
        no_memory_result, with_memory_result, expected_answer, expected_answer
    )


def evaluate_gold_evidence_ceiling(
    gold_evidence_results: Sequence[a_outcomes.AgentExecutionResult],
    expected_answers: Mapping[str, str],
) -> MetricResult:
    """OBSERVED_GOLD_EVIDENCE_CEILING over a set of GOLD_EVIDENCE-condition results, via
    `agent.diagnostics.observed_gold_evidence_ceiling` (reused verbatim)."""
    return a_diagnostics.observed_gold_evidence_ceiling(gold_evidence_results, expected_answers)
