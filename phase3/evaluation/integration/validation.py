"""Phase 3.2-H — cross-component consistency checks (the profile-to-evaluation invariants).

Every function here is a genuine, checked assertion used BY `pipeline.py` and separately
exercised by `phase3/evaluation/tests/test_evaluation_integration.py` (including a
deliberately-broken in-test payload proving the check is not a no-op, mirroring
`test_dataset_profiles.py`'s `check_strict_tsr_implies_evidence_ids` pattern) -- these are
not prose restatements.

No filesystem/network/LLM/embeddings dependency; no randomness; no global mutable state.
Reads only the in-memory profile dict a caller supplies (via
`phase3.evaluation.datasets.capability.load_profile` upstream, not here).
"""

from __future__ import annotations

from typing import Any, Mapping, Tuple

from phase3.evaluation.datasets import capability as cap

# ---------------------------------------------------------------------------
# Dataset-level (profile-derived) gates
# ---------------------------------------------------------------------------

TASK_LAYER_APPLICABLE_STATES: Tuple[str, ...] = (cap.CAPABILITY_AVAILABLE, cap.CAPABILITY_PARTIAL)
EVIDENCE_APPLICABLE_STATES: Tuple[str, ...] = (cap.CAPABILITY_AVAILABLE, cap.CAPABILITY_PARTIAL)
ANSWER_APPLICABLE_STATES: Tuple[str, ...] = (cap.CAPABILITY_AVAILABLE, cap.CAPABILITY_PARTIAL)

# metric_support / condition_support statuses this pipeline will actually ATTEMPT to
# compute against. UNAVAILABLE and UNDEFINED are never attempted (NOT_ATTEMPTED, dataset
# scope); SUPPORTED/SUPPORTED_WITH_ADAPTER/PROVISIONAL are attempted (PROVISIONAL results
# are tagged as such in the returned MetricResult's note, never silently promoted).
METRIC_SUPPORT_ATTEMPT_STATES: Tuple[str, ...] = (
    cap.SUPPORT_SUPPORTED,
    cap.SUPPORT_SUPPORTED_WITH_ADAPTER,
    cap.SUPPORT_PROVISIONAL,
)


def task_layer_gate(profile: Mapping[str, Any]) -> Tuple[bool, str]:
    """(applicable, reason). `reason` is always populated when not applicable, quoting the
    profile's own `workload_availability.explicit_task_records` status + reason.
    """
    entry = profile["workload_availability"]["explicit_task_records"]
    status = entry["status"]
    if status in TASK_LAYER_APPLICABLE_STATES:
        return True, ""
    return (
        False,
        f"dataset has no task layer (workload_availability.explicit_task_records="
        f"{status}): {entry['reason']}",
    )


def evidence_capability_gate(profile: Mapping[str, Any]) -> Tuple[bool, str]:
    """(applicable, reason) for `evidence_availability` at the DATASET level."""
    entry = profile["evidence_availability"]
    status = entry["status"]
    if status in EVIDENCE_APPLICABLE_STATES:
        return True, ""
    return False, f"evidence_availability={status}: {entry['reason']}"


def answer_capability_gate(profile: Mapping[str, Any]) -> Tuple[bool, str]:
    """(applicable, reason) for `answer_availability` at the DATASET level."""
    entry = profile["answer_availability"]
    status = entry["status"]
    if status in ANSWER_APPLICABLE_STATES:
        return True, ""
    return False, f"answer_availability={status}: {entry['reason']}"


def metric_support_gate(profile: Mapping[str, Any], metric_family: str) -> Tuple[bool, str]:
    """(should_attempt, reason_if_not) for one of `cap.METRIC_NAMES`, per THIS dataset's
    profile `metric_support` entry. Raises `KeyError` if `metric_family` is not one of the
    19 known families (a caller bug, not a data-driven case) -- this function never
    silently treats an unknown metric name as unavailable.
    """
    if metric_family not in cap.METRIC_NAMES:
        raise KeyError(f"{metric_family!r} is not one of the known metric families {cap.METRIC_NAMES!r}")
    entry = profile["metric_support"][metric_family]
    status = entry["status"]
    if status in METRIC_SUPPORT_ATTEMPT_STATES:
        return True, ""
    return False, f"metric_support.{metric_family}={status}: {entry['reason']}"


def condition_support_gate(profile: Mapping[str, Any], condition: str) -> Tuple[bool, str]:
    """(should_attempt, reason_if_not) for one of `cap.CONDITION_NAMES`, per THIS
    dataset's profile `condition_support` entry.
    """
    if condition not in cap.CONDITION_NAMES:
        raise KeyError(f"{condition!r} is not one of the known conditions {cap.CONDITION_NAMES!r}")
    entry = profile["condition_support"][condition]
    status = entry["status"]
    if status in METRIC_SUPPORT_ATTEMPT_STATES:
        return True, ""
    return False, f"condition_support.{condition}={status}: {entry['reason']}"


# ---------------------------------------------------------------------------
# Checked invariants (genuine assertions, not prose)
# ---------------------------------------------------------------------------


class ProfileEvaluationInconsistency(AssertionError):
    """Raised when a profile-to-evaluation invariant is violated -- i.e. the pipeline (or
    a caller) is about to compute a metric the profile itself says must not be computed as
    a normal 0/1/defined value for this dataset.
    """


def assert_strict_tsr_gate_consistent(profile: Mapping[str, Any]) -> None:
    """INVARIANT (per the 3.2-H task brief, restated from EVALUATION_CONTRACT.md section 3
    and DATASET_CAPABILITY_MATRIX.md): if `evidence_availability` is UNAVAILABLE/
    NOT_PROVIDED_BY_SOURCE/UNKNOWN for this dataset, then `metric_support.STRICT_TSR` must
    NOT be SUPPORTED/SUPPORTED_WITH_ADAPTER (i.e. Strict TSR must not be computed as a
    normal 0/1 when the dataset has no gold evidence basis at all).

    This mirrors `phase3/evaluation/datasets/validation.py::check_strict_tsr_implies_evidence_ids`
    exactly in spirit (that function already checks this INSIDE one profile's own internal
    consistency at 3.2-G) -- this integration-level version re-asserts the same invariant
    as a live, callable guard the PIPELINE itself invokes before computing Strict TSR,
    rather than only checking it once at profile-authoring time.

    Raises `ProfileEvaluationInconsistency` if violated.
    """
    evidence_status = profile["evidence_availability"]["status"]
    strict_tsr_status = profile["metric_support"]["STRICT_TSR"]["status"]
    if evidence_status not in EVIDENCE_APPLICABLE_STATES and strict_tsr_status in (
        cap.SUPPORT_SUPPORTED,
        cap.SUPPORT_SUPPORTED_WITH_ADAPTER,
    ):
        raise ProfileEvaluationInconsistency(
            f"Profile inconsistency for dataset_id={profile.get('dataset_id')!r}: "
            f"evidence_availability={evidence_status!r} but metric_support.STRICT_TSR="
            f"{strict_tsr_status!r} (should be UNAVAILABLE/UNDEFINED when evidence is not "
            "available at the dataset level)."
        )


def assert_answer_availability_gate_consistent(profile: Mapping[str, Any]) -> None:
    """INVARIANT: if `answer_availability` is UNAVAILABLE/NOT_PROVIDED_BY_SOURCE/UNKNOWN
    for this dataset, then `metric_support.AGENT_ANSWER_CORRECTNESS` and
    `metric_support.AGENT_SUCCESS` must NOT be SUPPORTED/SUPPORTED_WITH_ADAPTER.
    """
    answer_status = profile["answer_availability"]["status"]
    if answer_status in ANSWER_APPLICABLE_STATES:
        return
    for metric_family in ("AGENT_ANSWER_CORRECTNESS", "AGENT_SUCCESS"):
        status = profile["metric_support"][metric_family]["status"]
        if status in (cap.SUPPORT_SUPPORTED, cap.SUPPORT_SUPPORTED_WITH_ADAPTER):
            raise ProfileEvaluationInconsistency(
                f"Profile inconsistency for dataset_id={profile.get('dataset_id')!r}: "
                f"answer_availability={answer_status!r} but metric_support.{metric_family}="
                f"{status!r}."
            )


def assert_task_layer_gate_consistent(profile: Mapping[str, Any]) -> None:
    """INVARIANT: if `workload_availability.explicit_task_records` is UNAVAILABLE/
    NOT_PROVIDED_BY_SOURCE/UNKNOWN (no task layer at all), then NONE of the task-level
    metric families (RECALL_AT_K, MRR, STRICT_TSR, SELECTION_CAPACITY_DIAGNOSTICS,
    EVIDENCE_PRECISION, EVIDENCE_RECALL, EVIDENCE_COVERAGE, IRRELEVANT_MEMORY_RATE,
    AGENT_ANSWER_CORRECTNESS, AGENT_SUCCESS, MEMORY_CONTRIBUTION,
    OBSERVED_GOLD_EVIDENCE_CEILING, FAILURE_STAGE_CLASSIFICATION) may be SUPPORTED/
    SUPPORTED_WITH_ADAPTER -- these all require a task/gold basis that does not exist
    without a task layer. SELECTION_COUNT, REDUNDANCY, PROVENANCE_VALIDATION,
    LINEAGE_DIAGNOSTICS, EQUIVALENCE_DIAGNOSTICS, RETRIEVAL_UTILIZATION are explicitly
    EXCLUDED from this invariant -- they operate on memory-only or execution-only data and
    legitimately remain attemptable without a task layer (this is exactly the "no task
    layer != task failure" principle the 3.2-H task brief requires; see README.md).
    """
    task_ok, _ = task_layer_gate(profile)
    if task_ok:
        return
    task_dependent_families = (
        "RECALL_AT_K",
        "MRR",
        "STRICT_TSR",
        "SELECTION_CAPACITY_DIAGNOSTICS",
        "EVIDENCE_PRECISION",
        "EVIDENCE_RECALL",
        "EVIDENCE_COVERAGE",
        "IRRELEVANT_MEMORY_RATE",
        "AGENT_ANSWER_CORRECTNESS",
        "AGENT_SUCCESS",
        "MEMORY_CONTRIBUTION",
        "OBSERVED_GOLD_EVIDENCE_CEILING",
        "FAILURE_STAGE_CLASSIFICATION",
    )
    for metric_family in task_dependent_families:
        status = profile["metric_support"][metric_family]["status"]
        if status in (cap.SUPPORT_SUPPORTED, cap.SUPPORT_SUPPORTED_WITH_ADAPTER):
            raise ProfileEvaluationInconsistency(
                f"Profile inconsistency for dataset_id={profile.get('dataset_id')!r}: "
                "workload_availability.explicit_task_records is not available, but "
                f"metric_support.{metric_family}={status!r} (task-dependent metric must not "
                "be SUPPORTED without a task layer)."
            )


def assert_all_invariants(profile: Mapping[str, Any]) -> None:
    """Run every invariant above. Raises `ProfileEvaluationInconsistency` on the first
    violation found (each individual check already reports precisely which field/family
    is inconsistent)."""
    assert_strict_tsr_gate_consistent(profile)
    assert_answer_availability_gate_consistent(profile)
    assert_task_layer_gate_consistent(profile)
