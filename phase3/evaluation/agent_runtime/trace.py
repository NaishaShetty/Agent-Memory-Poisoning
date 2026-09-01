"""Phase 3.3-B -- `evaluate_and_trace()`: takes an `AgentRunOutcome` (produced by
`runner.run_agent_task()`, which never saw gold data) plus evaluator-only inputs supplied
separately by the CALLER, and produces the Part-18 trace from
`PHASE3_3_EXPERIMENTAL_SPEC.md`.

This is the one place gold data and agent-produced data are ever brought together, and it
happens entirely OUTSIDE the agent runtime (`runner.py` never imports this module) --
mirroring `EVALUATION_CONTRACT.md`'s standing separation between agent execution and
evaluation. Every classification below is a direct, unmodified call into existing Phase
3.2 code (`agent.outcomes`, `agent.diagnostics`, `foundations.lifecycle`) -- this module
adds no new metric and no new failure-stage vocabulary.
"""

from __future__ import annotations

import dataclasses
from typing import Any, Mapping, Optional, Sequence

from phase3.evaluation.agent.diagnostics import (
    STATUS_UNDEFINED_USAGE_NOT_OBSERVABLE,
    classify_observed_failure_stage,
    classify_retrieval_utilization,
)
from phase3.evaluation.agent.outcomes import classify_agent_success
from phase3.evaluation.foundations.adapter import MemoryFoundationAdapter
from phase3.evaluation.foundations.lifecycle import build_lifecycle_trace
from phase3.evaluation.metrics.selection import strict_tsr
from phase3.evaluation.security.reproducibility import fingerprint, safe_environment_metadata

from .citation import classify_citation_based_usage
from .identity import (
    STATUS_RESOLVED,
    resolve_source_identities,
    verify_collision_safety,
)
from .runner import AgentRunOutcome

NOT_OBSERVABLE = "NOT_OBSERVABLE"


def _lifecycle_summary(
    outcome: AgentRunOutcome, store_memory_ids: Sequence[str]
) -> Mapping[str, Any]:
    """Per-memory-id lifecycle trace for every SELECTED memory id, using
    `foundations.lifecycle.build_lifecycle_trace()` verbatim. Reports `NOT_OBSERVABLE`
    for MEMORY_USED/MEMORY_CONTRIBUTED (this runtime does not implement usage
    attribution -- see runner.py's module docstring) rather than fabricating either
    stage, per PHASE3_3_EXPERIMENTAL_SPEC.md Part 8/Part 12's explicit instruction.
    """
    usage_result = classify_retrieval_utilization(outcome.execution_result)
    usage_observable = usage_result.status != STATUS_UNDEFINED_USAGE_NOT_OBSERVABLE

    per_memory = {}
    for memory_id in outcome.selected_memory_ids:
        trace = build_lifecycle_trace(
            memory_id=memory_id,
            store_memory_ids=set(store_memory_ids) | set(outcome.retrieved_memory_ids),
            retrieved_memory_ids=outcome.retrieved_memory_ids,
            selected_memory_ids=outcome.selected_memory_ids,
            agent_visible_payload=outcome.agent_visible_context,
            usage_result=usage_result if usage_observable else None,
            contribution_result=None,  # requires a paired NO_MEMORY comparison; see below
        )
        stages = list(trace.stages_reached)
        if not usage_observable:
            stages.append(NOT_OBSERVABLE)  # explicit marker, never silently omitted
        per_memory[memory_id] = stages
    return per_memory


def evaluate_and_trace(
    outcome: AgentRunOutcome,
    *,
    experiment_id: str,
    dataset: str,
    dataset_revision: str,
    record_id: str,
    expected_answer: Optional[str],
    gold_evidence_ids: Sequence[str],
    store_memory_ids: Sequence[str] = (),
) -> Mapping[str, Any]:
    """Produce the Part-18 trace. `expected_answer`/`gold_evidence_ids` are evaluator-only
    and are NEVER passed to `runner.run_agent_task()` -- they reach this function only
    after the agent has already produced `outcome`, which is the load-bearing ordering
    that keeps the evaluator outside the agent.
    """
    success = classify_agent_success(outcome.execution_result, expected_answer)
    failure_stage = classify_observed_failure_stage(
        outcome.execution_result,
        expected_answer,
        gold_evidence_ids,
        retrieved_memory_ids=outcome.retrieved_memory_ids,
    )

    lifecycle = _lifecycle_summary(outcome, store_memory_ids)

    configuration = {
        "condition": outcome.condition,
        "generation_config_fingerprint": outcome.generation_config_fingerprint,
        "model_metadata": dict(outcome.model_metadata),
        "foundation_identity": dict(outcome.foundation_identity)
        if outcome.foundation_identity
        else None,
        "attempts": [
            {
                "attempt_number": a.attempt_number,
                "succeeded": a.succeeded,
                "latency_sec": a.latency_sec,
                "error": a.error,
            }
            for a in outcome.attempts
        ],
    }

    trace = {
        "experiment_id": experiment_id,
        "dataset": dataset,
        "dataset_revision": dataset_revision,
        "record_id": record_id,
        "model": outcome.model_metadata.get("repo_id"),
        "model_revision": outcome.model_metadata.get("repo_revision"),
        "foundation": (outcome.foundation_identity or {}).get("foundation_name"),
        "foundation_version": (outcome.foundation_identity or {}).get("adapter_version"),
        "configuration": {**configuration, "environment": dict(safe_environment_metadata())},
        "task": {"task_id": outcome.task_id, "prompt": None},  # prompt intentionally
        # omitted here -- it's already fully captured in agent_visible_context below,
        # no need to duplicate PII/content twice in one trace object.
        "memory_available": outcome.memory_available,
        "retrieved_memories": list(outcome.retrieved_memory_ids),
        "selected_memories": list(outcome.selected_memory_ids),
        "exposed_memories": list(outcome.exposed_memory_ids),
        "used_memories": NOT_OBSERVABLE,  # honest -- see module docstring
        "contributed_memories": NOT_OBSERVABLE,  # requires a paired NO_MEMORY run; not
        # computed by a single-condition trace -- see paired_memory_contribution() below
        # for the function that DOES compute this, given two traces.
        "lifecycle_per_memory": lifecycle,
        "agent_output": outcome.execution_result.answer,
        "evaluation_result": {
            "success_status": success.status,
            "success_value": success.value,
        },
        "failure_stage": failure_stage.status,
        "latency": {
            "total_latency_sec": outcome.total_latency_sec,
            "attempt_latencies_sec": [a.latency_sec for a in outcome.attempts],
        },
        "fingerprints": {
            "generation_config_fingerprint": outcome.generation_config_fingerprint,
            "trace_fingerprint": None,  # filled in below, after everything else is final
        },
    }
    # The trace's own fingerprint must be computed over everything ELSE in the trace, so
    # it is filled in as the last step, over a copy with the placeholder still present
    # (a stable, if slightly recursive-looking, convention -- the placeholder value
    # `None` is itself part of what gets hashed, not omitted, so re-fingerprinting is
    # deterministic and reproducible from the trace dict alone).
    trace["fingerprints"]["trace_fingerprint"] = fingerprint(trace)
    return trace


def evaluate_and_trace_with_identity(
    outcome: AgentRunOutcome,
    foundation: MemoryFoundationAdapter,
    *,
    experiment_id: str,
    dataset: str,
    dataset_revision: str,
    record_id: str,
    expected_answer: Optional[str],
    gold_evidence_ids: Sequence[str],
    ingested_source_memory_ids: Sequence[str] = (),
    metadata_key: str = "source_memory_id",
) -> Mapping[str, Any]:
    """Phase 3.3-C: `evaluate_and_trace()` extended with the SOURCE_MEMORY_ID identity
    bridge (`identity.py`). Produces every field `evaluate_and_trace()` produces PLUS the
    identity-resolution and collision-safety detail Part 14 of the 3.3-C mission
    requires, and -- where identity resolution actually succeeds -- re-evaluates
    `classify_observed_failure_stage()` and `strict_tsr()` (both REUSED VERBATIM, never
    modified) against the SOURCE-space translation of what was retrieved/selected,
    since `gold_evidence_ids` is always expressed in source-dataset id space.

    This does NOT loosen Strict TSR or the failure-stage vocabulary -- it supplies the
    SAME frozen functions with the CORRECT-space inputs once that correct-space mapping
    has been established via `inspect_memory()`-sourced metadata only (see identity.py's
    module docstring for the full investigation and the explicit prohibition on any
    similarity-based inference). Ids that do not resolve are excluded from the
    source-space comparison, honestly (never guessed, never silently dropped from the
    trace -- `identity_resolutions` records every one of them with its real status).
    """
    all_ids = tuple(dict.fromkeys(outcome.retrieved_memory_ids + outcome.selected_memory_ids))
    resolutions = resolve_source_identities(foundation, all_ids, metadata_key=metadata_key)
    collision_report = verify_collision_safety(resolutions)

    def _translate(ids: Sequence[str]) -> tuple:
        out = []
        for fid in ids:
            r = resolutions.get(fid)
            if r is not None and r.status == STATUS_RESOLVED:
                out.append(r.source_memory_id)
        return tuple(out)

    retrieved_source_ids = _translate(outcome.retrieved_memory_ids)
    selected_source_ids = _translate(outcome.selected_memory_ids)

    # Re-evaluate the FROZEN failure-stage classifier with source-space inputs -- the
    # execution_result copy differs ONLY in selected_memory_ids (translated); answer,
    # execution_status, condition, task_id are untouched. dataclasses.replace() is used
    # because AgentExecutionResult is frozen (immutable by design).
    translated_execution_result = dataclasses.replace(
        outcome.execution_result, selected_memory_ids=selected_source_ids
    )
    resolved_failure_stage = classify_observed_failure_stage(
        translated_execution_result,
        expected_answer,
        gold_evidence_ids,
        retrieved_memory_ids=retrieved_source_ids,
    )
    resolved_strict_tsr = (
        strict_tsr(selected_source_ids, gold_evidence_ids)
        if (selected_source_ids or gold_evidence_ids)
        else None
    )

    citation = classify_citation_based_usage(
        outcome.execution_result.answer, outcome.exposed_memory_ids
    )

    base_trace = dict(
        evaluate_and_trace(
            outcome,
            experiment_id=experiment_id,
            dataset=dataset,
            dataset_revision=dataset_revision,
            record_id=record_id,
            expected_answer=expected_answer,
            gold_evidence_ids=gold_evidence_ids,
            store_memory_ids=ingested_source_memory_ids,
        )
    )

    # Namespace-distinct identity block -- Part 14's explicit requirement that the trace
    # "clearly distinguish foundation identity / source identity / gold identity."
    base_trace["identity"] = {
        "retrieved_memories_foundation_space": list(outcome.retrieved_memory_ids),
        "selected_memories_foundation_space": list(outcome.selected_memory_ids),
        "retrieved_memories_source_space": list(retrieved_source_ids),
        "selected_memories_source_space": list(selected_source_ids),
        "gold_evidence_ids_source_space": list(gold_evidence_ids),
        "resolutions": {
            fid: {
                "adapter_memory_id": r.adapter_memory_id,
                "source_memory_id": r.source_memory_id,
                "status": r.status,
            }
            for fid, r in resolutions.items()
        },
        "collision_report": {
            "collision_free": collision_report.collision_free,
            "duplicate_source_ids": dict(collision_report.duplicate_source_ids),
            "resolved_count": collision_report.resolved_count,
            "not_resolvable_count": collision_report.not_resolvable_count,
            "inspect_unavailable_count": collision_report.inspect_unavailable_count,
            "note": collision_report.note,
        },
    }

    # Identity-resolved re-evaluation, kept SEPARATE from the base (foundation-id-space)
    # failure_stage/evaluation_result fields above -- never overwrites them, so a reader
    # can always see both "what the raw foundation-id comparison found" (base_trace's
    # original fields, unchanged from evaluate_and_trace) and "what the correct,
    # source-id-space comparison finds once identity is resolved" (this block).
    base_trace["resolved_evaluation"] = {
        "failure_stage": resolved_failure_stage.status,
        "strict_tsr": {
            "value": resolved_strict_tsr.value,
            "status": resolved_strict_tsr.status,
        }
        if resolved_strict_tsr is not None
        else None,
        "note": (
            "Computed via the SAME frozen classify_observed_failure_stage()/strict_tsr() "
            "functions as base_trace, fed source-space-translated retrieved/selected ids "
            "instead of raw foundation ids. strict_tsr is None only when there were no "
            "selected ids AND no gold ids to compare (strict_tsr is otherwise always "
            "defined, including 0 for a genuine miss)."
        ),
    }

    base_trace["citation_diagnostic"] = {
        "status": citation.status,
        "cited_memory_ids": list(citation.cited_memory_ids),
        "note": citation.note,
    }

    # Recompute the trace fingerprint over the now-complete (identity-extended) trace --
    # the base evaluate_and_trace() call above already fingerprinted a SHORTER version
    # of this dict; that inner fingerprint is preserved under a distinct key so neither
    # value is silently discarded, and the outer one is authoritative for this function's
    # actual returned trace.
    base_trace["fingerprints"] = {
        **base_trace["fingerprints"],
        "base_trace_fingerprint": base_trace["fingerprints"]["trace_fingerprint"],
        "trace_fingerprint": fingerprint(base_trace),
    }
    return base_trace


def paired_memory_contribution(
    no_memory_trace: Mapping[str, Any],
    with_memory_trace: Mapping[str, Any],
    expected_answer: Optional[str],
) -> Mapping[str, Any]:
    """Given a NO_MEMORY trace and a RETRIEVED_MEMORY trace for the SAME record_id, plus
    the evaluator-only `expected_answer` (identical for both, per
    `agent.paired.classify_memory_contribution`'s identity enforcement), compute the
    paired memory-contribution diagnostic -- reused verbatim, not reimplemented. Raises
    `PairedComparisonIdentityError` (propagated from `paired.py`, not re-caught) if the
    two traces do not share the same record_id.
    """
    from phase3.evaluation.agent.outcomes import AgentExecutionResult
    from phase3.evaluation.agent.paired import classify_memory_contribution

    if no_memory_trace["record_id"] != with_memory_trace["record_id"]:
        raise ValueError(
            "paired_memory_contribution requires two traces for the SAME record_id; got "
            f"{no_memory_trace['record_id']!r} vs {with_memory_trace['record_id']!r}."
        )

    no_mem_result = AgentExecutionResult(
        task_id=no_memory_trace["record_id"],
        condition=no_memory_trace["configuration"]["condition"],
        answer=no_memory_trace["agent_output"],
        execution_status="SUCCESS" if no_memory_trace["agent_output"] is not None else "ERROR",
        selected_memory_ids=tuple(no_memory_trace["selected_memories"]),
    )
    with_mem_result = AgentExecutionResult(
        task_id=with_memory_trace["record_id"],
        condition=with_memory_trace["configuration"]["condition"],
        answer=with_memory_trace["agent_output"],
        execution_status="SUCCESS" if with_memory_trace["agent_output"] is not None else "ERROR",
        selected_memory_ids=tuple(with_memory_trace["selected_memories"]),
    )
    contribution = classify_memory_contribution(
        no_mem_result,
        with_mem_result,
        expected_answer_no_memory=expected_answer,
        expected_answer_with_memory=expected_answer,
    )
    return {
        "record_id": no_memory_trace["record_id"],
        "status": contribution.status,
        "value": contribution.value,
        "detail": contribution.detail,
        "note": contribution.note,
    }


__all__ = [
    "NOT_OBSERVABLE",
    "evaluate_and_trace",
    "evaluate_and_trace_with_identity",
    "paired_memory_contribution",
]
