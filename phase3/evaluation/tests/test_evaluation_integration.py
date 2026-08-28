"""Phase 3.2-H tests for `phase3/evaluation/integration/` (evaluation integration +
regression).

Scope note: this suite does not modify, re-run, or depend on any prior test file's
internals -- `test_evaluation_contracts.py` (62), `test_core_memory_metrics.py` (88),
`test_evidence_equivalence.py` (32), `test_provenance_lineage.py` (58),
`test_agent_evaluation.py`, `test_leakage.py`, `test_determinism.py`,
`test_reproducibility.py`, `test_dataset_profiles.py` must all remain green, unmodified,
alongside this file (504 tests total baseline per the 3.2-H task brief).

All fixtures here are small, hand-authored, deterministic Python literals shaped like
(but never copied from) real LoCoMo/LongMemEval/MSC/Conversation Chronicles records,
exercised through the real dataset profiles shipped in
`phase3/evaluation/datasets/profiles/`.
"""

from __future__ import annotations

import copy
import dataclasses
import importlib
import inspect
import pkgutil
from pathlib import Path

import pytest
from jsonschema import ValidationError

from phase3.evaluation.agent.conditions import (
    CONDITION_GOLD_EVIDENCE,
    CONDITION_NO_MEMORY,
    CONDITION_RETRIEVED_MEMORY,
)
from phase3.evaluation.agent.outcomes import (
    BEHAVIOR_ALWAYS_CORRECT,
    BEHAVIOR_ALWAYS_WRONG,
    BEHAVIOR_CORRECT_IF_EVIDENCE_PRESENT,
    AgentExecutionResult,
    EXECUTION_STATUS_SUCCESS,
)
from phase3.evaluation.datasets import capability as cap
from phase3.evaluation.metrics.retrieval import (
    CLASSIFICATION_RETRIEVAL_MISS,
    CLASSIFICATION_SELECTION_MISS,
)
from phase3.evaluation.metrics.types import STATUS_OK, STATUS_UNDEFINED_EMPTY_GOLD
from phase3.evaluation.security.leakage import validate_against_boundary, validate_no_leakage
from phase3.evaluation.security.reproducibility import fingerprint

from phase3.evaluation.integration.dataset_adapter import (
    build_evaluation_case,
    build_evaluator_reference,
)
from phase3.evaluation.integration.pipeline import evaluate_case
from phase3.evaluation.integration.result import STATUS_NOT_ATTEMPTED
from phase3.evaluation.integration.validation import (
    ProfileEvaluationInconsistency,
    assert_strict_tsr_gate_consistent,
    assert_task_layer_gate_consistent,
    metric_support_gate,
    task_layer_gate,
)

INTEGRATION_DIR = Path(__file__).resolve().parent.parent / "integration"

LOCOMO_PROFILE = cap.load_profile("locomo")
LONGMEMEVAL_PROFILE = cap.load_profile("longmemeval")
MSC_PROFILE = cap.load_profile("msc")
CONVCHRON_PROFILE = cap.load_profile("conversation_chronicles")


# ---------------------------------------------------------------------------
# Shared synthetic fixtures (small, hand-authored, dataset-shaped, never real data)
# ---------------------------------------------------------------------------

_LOCOMO_MEMORIES = {
    "mem-a": {"content": "Caroline attended the LGBTQ support group on May 8, 2023."},
    "mem-b": {"content": "Caroline's dog is named Biscuit."},
}


def _locomo_case(
    task_id,
    condition,
    answer="May 8, 2023",
    evidence_memory_ids=("mem-a",),
    retrieved_memory_ids=("mem-a", "mem-b"),
    selected_memory_ids=("mem-a",),
    memories=None,
):
    record = {"answer": answer, "evidence_memory_ids": list(evidence_memory_ids)}
    return build_evaluation_case(
        dataset_id="locomo",
        profile=LOCOMO_PROFILE,
        task_id=task_id,
        prompt="When did Caroline attend the support group?",
        condition=condition,
        record=record,
        memories=memories if memories is not None else _LOCOMO_MEMORIES,
        retrieved_memory_ids=retrieved_memory_ids,
        selected_memory_ids=selected_memory_ids,
    )


# ---------------------------------------------------------------------------
# Scenario 1 -- fully evaluable task (LoCoMo-shaped, evaluates to SUCCESS)
# ---------------------------------------------------------------------------


def test_scenario_1_fully_evaluable_task_success():
    case = _locomo_case("s1", CONDITION_RETRIEVED_MEMORY)
    result = evaluate_case(case, LOCOMO_PROFILE, synthetic_behavior=BEHAVIOR_CORRECT_IF_EVIDENCE_PRESENT)

    assert result.metrics["STRICT_TSR"].status == STATUS_OK
    assert result.metrics["STRICT_TSR"].value == 1.0
    assert result.agent_success.status == "ANSWER_CORRECT"
    assert result.leakage_result.status == "NO_LEAKAGE"
    assert result.evaluation_result["result_status"] in ("COMPLETE", "PARTIAL")


# ---------------------------------------------------------------------------
# Scenario 2 -- retrieval miss (RETRIEVAL_FAILURE, gold absent from retrieved candidates)
# ---------------------------------------------------------------------------


def test_scenario_2_retrieval_miss():
    case = _locomo_case(
        "s2",
        CONDITION_RETRIEVED_MEMORY,
        retrieved_memory_ids=("mem-b",),  # gold "mem-a" never retrieved
        selected_memory_ids=("mem-b",),
    )
    result = evaluate_case(case, LOCOMO_PROFILE, synthetic_behavior=BEHAVIOR_ALWAYS_WRONG)

    capacity = result.metrics["SELECTION_CAPACITY_DIAGNOSTICS"]
    assert capacity.detail["per_gold"]["mem-a"] == CLASSIFICATION_RETRIEVAL_MISS
    failure_stage = result.metrics["FAILURE_STAGE_CLASSIFICATION"]
    assert failure_stage.status == "RETRIEVAL_FAILURE"


# ---------------------------------------------------------------------------
# Scenario 3 -- selection miss (SELECTION_FAILURE, gold retrieved but not selected)
# ---------------------------------------------------------------------------


def test_scenario_3_selection_miss():
    case = _locomo_case(
        "s3",
        CONDITION_RETRIEVED_MEMORY,
        retrieved_memory_ids=("mem-a", "mem-b"),
        selected_memory_ids=("mem-b",),  # gold retrieved but not selected
    )
    result = evaluate_case(case, LOCOMO_PROFILE, synthetic_behavior=BEHAVIOR_ALWAYS_WRONG)

    capacity = result.metrics["SELECTION_CAPACITY_DIAGNOSTICS"]
    assert capacity.detail["per_gold"]["mem-a"] == CLASSIFICATION_SELECTION_MISS
    failure_stage = result.metrics["FAILURE_STAGE_CLASSIFICATION"]
    assert failure_stage.status == "SELECTION_FAILURE"


# ---------------------------------------------------------------------------
# Scenario 4 -- agent answer incorrect despite evidence (AGENT_FAILURE_WITH_EVIDENCE)
# ---------------------------------------------------------------------------


def test_scenario_4_agent_failure_with_evidence():
    case = _locomo_case(
        "s4",
        CONDITION_RETRIEVED_MEMORY,
        retrieved_memory_ids=("mem-a", "mem-b"),
        selected_memory_ids=("mem-a",),  # gold selected: memory succeeded
    )
    # BEHAVIOR_ALWAYS_WRONG: agent ignores the correctly-selected evidence and answers wrong.
    result = evaluate_case(case, LOCOMO_PROFILE, synthetic_behavior=BEHAVIOR_ALWAYS_WRONG)

    assert result.metrics["STRICT_TSR"].value == 1.0  # memory succeeded
    assert result.agent_success.status == "ANSWER_INCORRECT"  # agent did not
    assert result.metrics["FAILURE_STAGE_CLASSIFICATION"].status == "AGENT_FAILURE_WITH_EVIDENCE"


# ---------------------------------------------------------------------------
# Scenario 5 -- missing answer (answer=null -> UNDEFINED, not ANSWER_INCORRECT)
# ---------------------------------------------------------------------------


def test_scenario_5_missing_answer_is_undefined_not_incorrect():
    case = _locomo_case("s5", CONDITION_RETRIEVED_MEMORY, answer=None)
    result = evaluate_case(case, LOCOMO_PROFILE, synthetic_behavior=BEHAVIOR_ALWAYS_CORRECT)

    correctness = result.metrics["AGENT_ANSWER_CORRECTNESS"]
    assert correctness.status == "EVALUATION_UNDEFINED"
    assert correctness.status != "ANSWER_INCORRECT"
    assert correctness.value is None


# ---------------------------------------------------------------------------
# Scenario 6 -- missing evidence IDs (evidence_memory_ids=[] -> Strict TSR UNDEFINED, not 0)
# ---------------------------------------------------------------------------


def test_scenario_6_missing_evidence_ids_is_undefined_not_zero():
    case = _locomo_case("s6", CONDITION_RETRIEVED_MEMORY, evidence_memory_ids=())
    result = evaluate_case(case, LOCOMO_PROFILE, synthetic_behavior=BEHAVIOR_ALWAYS_CORRECT)

    strict_tsr = result.metrics["STRICT_TSR"]
    assert strict_tsr.status == STATUS_UNDEFINED_EMPTY_GOLD
    assert strict_tsr.value is None
    assert strict_tsr.value != 0.0


# ---------------------------------------------------------------------------
# Scenario 7 -- MSC no-task-layer
# ---------------------------------------------------------------------------


def _no_task_layer_case(dataset_id, profile, task_id):
    memories = {"m1": {"content": "session content"}, "m2": {"content": "more content"}}
    return build_evaluation_case(
        dataset_id=dataset_id,
        profile=profile,
        task_id=task_id,
        prompt="n/a",
        condition=CONDITION_NO_MEMORY,
        record={},
        memories=memories,
        selected_memory_ids=["m1", "m2"],
    )


def test_scenario_7_msc_no_task_layer():
    case = _no_task_layer_case("msc", MSC_PROFILE, "msc-1")
    assert case.task_applicable is False
    assert "no task layer" in case.task_not_applicable_reason

    result = evaluate_case(case, MSC_PROFILE)

    for family in (
        "STRICT_TSR",
        "RECALL_AT_K",
        "MRR",
        "AGENT_ANSWER_CORRECTNESS",
        "AGENT_SUCCESS",
    ):
        m = result.metrics[family]
        assert m.status == STATUS_NOT_ATTEMPTED, f"{family}: {m.status}"
        assert m.detail["scope"] == "DATASET"
        assert m.detail["reason"]  # never a blank/silent reason

    # Task-independent metrics still attempted.
    assert result.metrics["SELECTION_COUNT"].status == STATUS_OK
    assert result.metrics["SELECTION_COUNT"].value == 2.0
    assert result.metrics["PROVENANCE_VALIDATION"].status == STATUS_OK
    assert result.metrics["REDUNDANCY"].status == STATUS_OK


# ---------------------------------------------------------------------------
# Scenario 8 -- Conversation Chronicles no-task-layer (same principle)
# ---------------------------------------------------------------------------


def test_scenario_8_conversation_chronicles_no_task_layer():
    case = _no_task_layer_case("conversation_chronicles", CONVCHRON_PROFILE, "cc-1")
    assert case.task_applicable is False

    result = evaluate_case(case, CONVCHRON_PROFILE)

    for family in ("STRICT_TSR", "AGENT_ANSWER_CORRECTNESS", "AGENT_SUCCESS", "MEMORY_CONTRIBUTION"):
        assert result.metrics[family].status == STATUS_NOT_ATTEMPTED

    assert result.metrics["SELECTION_COUNT"].status == STATUS_OK
    assert result.metrics["REDUNDANCY"].status == STATUS_OK


# ---------------------------------------------------------------------------
# Scenario 9 -- leakage attempt (forbidden key injected via a buggy adapter path)
# ---------------------------------------------------------------------------


def test_scenario_9_leakage_attempt_is_rejected_by_pipeline():
    case = _locomo_case("s9", CONDITION_RETRIEVED_MEMORY)
    good_context = case.agent_visible_context
    assert validate_against_boundary(good_context).status == "NO_LEAKAGE"

    # Simulate a buggy adapter path that injects a forbidden evaluator-only key directly
    # into what is about to be treated as an agent-visible payload.
    leaked_context = dict(good_context)
    leaked_context["gold_evidence_ids"] = ["mem-a"]

    leakage_result = validate_against_boundary(leaked_context)
    assert leakage_result.status == "LEAKAGE_DETECTED"

    # And the wider structural leakage scan agrees.
    wider = validate_no_leakage(leaked_context, condition=CONDITION_RETRIEVED_MEMORY)
    assert wider.status == "LEAKAGE_DETECTED"


# ---------------------------------------------------------------------------
# Scenario 10 -- deterministic rerun (identical result object AND identical fingerprint)
# ---------------------------------------------------------------------------


def test_scenario_10_deterministic_rerun():
    case = _locomo_case("s10", CONDITION_RETRIEVED_MEMORY)
    result_a = evaluate_case(case, LOCOMO_PROFILE, synthetic_behavior=BEHAVIOR_CORRECT_IF_EVIDENCE_PRESENT)
    result_b = evaluate_case(case, LOCOMO_PROFILE, synthetic_behavior=BEHAVIOR_CORRECT_IF_EVIDENCE_PRESENT)

    assert result_a == result_b
    assert result_a.fingerprints == result_b.fingerprints
    assert result_a.fingerprints["overall"] == result_b.fingerprints["overall"]
    # A different case_id must NOT collide.
    other_case = _locomo_case("s10-other", CONDITION_RETRIEVED_MEMORY)
    result_c = evaluate_case(other_case, LOCOMO_PROFILE, synthetic_behavior=BEHAVIOR_CORRECT_IF_EVIDENCE_PRESENT)
    assert result_c.fingerprints["overall"] != result_a.fingerprints["overall"]


# ---------------------------------------------------------------------------
# GOLD_EVIDENCE content-vs-ID distinction (integration-level, not just the unit test in
# security/) -- content allowed under GOLD_EVIDENCE, literal gold evidence ID never allowed.
# ---------------------------------------------------------------------------


def test_gold_evidence_condition_exposes_content_never_literal_id():
    case = _locomo_case("gold-1", CONDITION_GOLD_EVIDENCE)
    ctx = case.agent_visible_context
    memory_content = ctx["memory_content"]
    assert len(memory_content) == 1
    # Content IS present.
    assert memory_content[0]["content"] == _LOCOMO_MEMORIES["mem-a"]["content"]
    # The literal gold evidence id ("mem-a") must NEVER appear as a memory_id in the
    # agent-visible payload under GOLD_EVIDENCE.
    assert memory_content[0]["memory_id"] != "mem-a"
    assert memory_content[0]["memory_id"].startswith("evidence-slot-")

    # And this holds under every condition, not just GOLD_EVIDENCE: no agent-visible
    # payload may ever carry a literal "gold_evidence_ids" key.
    result = evaluate_case(case, LOCOMO_PROFILE, synthetic_behavior=BEHAVIOR_ALWAYS_CORRECT)
    assert result.leakage_result.status == "NO_LEAKAGE"


# ---------------------------------------------------------------------------
# Profile-consistency invariants -- deliberately-broken payloads proving the check is
# not a no-op (mirrors test_dataset_profiles.py's pattern).
# ---------------------------------------------------------------------------


def test_strict_tsr_gate_invariant_passes_on_real_profiles():
    for profile in (LOCOMO_PROFILE, LONGMEMEVAL_PROFILE, MSC_PROFILE, CONVCHRON_PROFILE):
        assert_strict_tsr_gate_consistent(profile)  # must not raise


def test_strict_tsr_gate_invariant_catches_deliberately_broken_profile():
    broken = copy.deepcopy(MSC_PROFILE)
    broken["metric_support"]["STRICT_TSR"] = {
        "status": "SUPPORTED",
        "reason": "deliberately broken for this test",
    }
    with pytest.raises(ProfileEvaluationInconsistency):
        assert_strict_tsr_gate_consistent(broken)


def test_task_layer_gate_invariant_catches_deliberately_broken_profile():
    broken = copy.deepcopy(MSC_PROFILE)
    broken["metric_support"]["AGENT_ANSWER_CORRECTNESS"] = {
        "status": "SUPPORTED",
        "reason": "deliberately broken for this test",
    }
    with pytest.raises(ProfileEvaluationInconsistency):
        assert_task_layer_gate_consistent(broken)


def test_pipeline_refuses_to_run_against_a_broken_profile():
    broken = copy.deepcopy(MSC_PROFILE)
    broken["metric_support"]["STRICT_TSR"] = {"status": "SUPPORTED", "reason": "broken"}
    case = _no_task_layer_case("msc", broken, "msc-broken")
    with pytest.raises(ProfileEvaluationInconsistency):
        evaluate_case(case, broken)


# ---------------------------------------------------------------------------
# Per-dataset regression: LoCoMo/LongMemEval task-capable, MSC/ConvChron NOT_ATTEMPTED
# with a stated reason, never silently 0/UNAVAILABLE-as-false.
# ---------------------------------------------------------------------------


def test_longmemeval_task_capable():
    record = {"answer": "the answer", "evidence_memory_ids": ["ev-1"]}
    memories = {"ev-1": {"content": "relevant content"}}
    case = build_evaluation_case(
        dataset_id="longmemeval",
        profile=LONGMEMEVAL_PROFILE,
        task_id="lme-1",
        prompt="some long-horizon question?",
        condition=CONDITION_RETRIEVED_MEMORY,
        record=record,
        memories=memories,
        retrieved_memory_ids=["ev-1"],
        selected_memory_ids=["ev-1"],
    )
    assert case.task_applicable is True
    result = evaluate_case(case, LONGMEMEVAL_PROFILE, synthetic_behavior=BEHAVIOR_ALWAYS_CORRECT)
    assert result.metrics["STRICT_TSR"].status == STATUS_OK
    assert result.metrics["STRICT_TSR"].value == 1.0
    assert result.agent_success.status == "ANSWER_CORRECT"


@pytest.mark.parametrize(
    "dataset_id,profile",
    [("msc", MSC_PROFILE), ("conversation_chronicles", CONVCHRON_PROFILE)],
)
def test_msc_and_convchron_task_metrics_never_silently_zero_or_false(dataset_id, profile):
    case = _no_task_layer_case(dataset_id, profile, f"{dataset_id}-regress")
    result = evaluate_case(case, profile)
    task_dependent = (
        "RECALL_AT_K",
        "MRR",
        "STRICT_TSR",
        "EVIDENCE_PRECISION",
        "EVIDENCE_RECALL",
        "AGENT_ANSWER_CORRECTNESS",
        "AGENT_SUCCESS",
        "MEMORY_CONTRIBUTION",
        "OBSERVED_GOLD_EVIDENCE_CEILING",
        "FAILURE_STAGE_CLASSIFICATION",
    )
    for family in task_dependent:
        m = result.metrics[family]
        assert m.value is None
        assert m.status == STATUS_NOT_ATTEMPTED
        assert m.status != STATUS_OK  # never silently "computed"


# ---------------------------------------------------------------------------
# Leakage integration: injection vectors -- direct dict, nested dict, list, tuple,
# dataclass, serialization round-trip. Reuses security.leakage's functions through the
# pipeline path (validate_against_boundary / validate_no_leakage), never hand-rolled.
# ---------------------------------------------------------------------------


def test_leakage_direct_dict_injection():
    payload = {"task": {"prompt": "q"}, "gold_answer": "leak"}
    assert validate_no_leakage(payload).status == "LEAKAGE_DETECTED"


def test_leakage_nested_dict_injection():
    payload = {"task": {"prompt": "q"}, "debug": {"nested": {"gold_evidence_ids": ["x"]}}}
    assert validate_no_leakage(payload).status == "LEAKAGE_DETECTED"


def test_leakage_list_injection():
    payload = {"task": {"prompt": "q"}, "items": [{"ok": 1}, {"expected_answer": "leak"}]}
    assert validate_no_leakage(payload).status == "LEAKAGE_DETECTED"


def test_leakage_tuple_injection():
    payload = {"task": {"prompt": "q"}, "items": ({"ok": 1}, {"strict_tsr": 1.0})}
    assert validate_no_leakage(payload).status == "LEAKAGE_DETECTED"


def test_leakage_dataclass_injection():
    @dataclasses.dataclass(frozen=True)
    class Wrapper:
        note: str
        expected_answer: str

    payload = Wrapper(note="hi", expected_answer="leak")
    assert validate_no_leakage(payload).status == "LEAKAGE_DETECTED"


def test_leakage_serialization_round_trip_clean_payload_stays_clean():
    case = _locomo_case("leak-rt", CONDITION_RETRIEVED_MEMORY)
    from phase3.evaluation.security.leakage import check_serialization_round_trip

    original, round_tripped = check_serialization_round_trip(
        case.agent_visible_context, condition=CONDITION_RETRIEVED_MEMORY
    )
    assert original.status == "NO_LEAKAGE"
    assert round_tripped.status == "NO_LEAKAGE"


def test_leakage_serialization_round_trip_dirty_payload_stays_dirty():
    from phase3.evaluation.security.leakage import check_serialization_round_trip

    dirty = {"task": {"prompt": "q"}, "gold_answer": "leak"}
    original, round_tripped = check_serialization_round_trip(dirty)
    assert original.status == "LEAKAGE_DETECTED"
    assert round_tripped.status == "LEAKAGE_DETECTED"


# ---------------------------------------------------------------------------
# Determinism: same case run twice -> identical result + identical fingerprint (via
# security.reproducibility.fingerprint).
# ---------------------------------------------------------------------------


def test_determinism_fingerprint_identity_directly():
    case = _locomo_case("det-1", CONDITION_RETRIEVED_MEMORY)
    r1 = evaluate_case(case, LOCOMO_PROFILE, synthetic_behavior=BEHAVIOR_ALWAYS_CORRECT)
    r2 = evaluate_case(case, LOCOMO_PROFILE, synthetic_behavior=BEHAVIOR_ALWAYS_CORRECT)
    assert fingerprint(r1.evaluation_result) == fingerprint(r2.evaluation_result)
    assert fingerprint(r1.trace["final_response"]) == fingerprint(r2.trace["final_response"])


def test_determinism_repeated_n_times():
    from phase3.evaluation.security.determinism import check_repeated_run_determinism

    case = _locomo_case("det-n", CONDITION_RETRIEVED_MEMORY)

    def _run():
        return evaluate_case(case, LOCOMO_PROFILE, synthetic_behavior=BEHAVIOR_ALWAYS_CORRECT).fingerprints["overall"]

    determinism = check_repeated_run_determinism(_run, n=5)
    assert determinism.status == "DETERMINISTIC"


# ---------------------------------------------------------------------------
# Full end-to-end trace test: asserts on real intermediate values at each pipeline stage.
# ---------------------------------------------------------------------------


def test_full_end_to_end_trace_intermediate_values():
    case = _locomo_case("trace-1", CONDITION_RETRIEVED_MEMORY)

    # Stage: dataset -> case
    assert case.dataset_id == "locomo"
    assert case.task_applicable is True
    assert case.evaluator_reference["gold_evidence_ids"] == ["mem-a"]
    assert case.evaluator_reference["gold_answer"] == "May 8, 2023"

    # Stage: case -> condition -> context
    ctx = case.agent_visible_context
    assert ctx["condition"] == CONDITION_RETRIEVED_MEMORY
    assert ctx["task"]["prompt"] == "When did Caroline attend the support group?"
    assert [m["memory_id"] for m in ctx["memory_content"]] == ["mem-a"]
    assert "gold_evidence_ids" not in ctx
    assert "gold_answer" not in ctx

    result = evaluate_case(case, LOCOMO_PROFILE, synthetic_behavior=BEHAVIOR_CORRECT_IF_EVIDENCE_PRESENT)

    # Stage: context -> metrics
    assert result.metrics["STRICT_TSR"].value == 1.0
    assert result.metrics["EVIDENCE_RECALL"].value == 1.0
    assert result.metrics["SELECTION_COUNT"].value == 1.0

    # Stage: metrics -> diagnostics
    assert result.metrics["FAILURE_STAGE_CLASSIFICATION"].status == "SUCCESS"
    assert result.metrics["RETRIEVAL_UTILIZATION"].status in (
        "SELECTED_AND_USED",
        "UNDEFINED_USAGE_NOT_OBSERVABLE",
    )

    # Stage: diagnostics -> leakage
    assert result.leakage_result.status == "NO_LEAKAGE"

    # Stage: leakage -> result / trace
    assert result.evaluation_result["run_id"] == "integration-locomo-trace-1-RETRIEVED_MEMORY"
    assert result.trace["task_id"] == "trace-1"
    assert result.trace["selected_evidence"] == ["mem-a"]
    assert result.trace["final_response"] == "May 8, 2023"

    # Stage: trace -> fingerprint
    assert isinstance(result.fingerprints["overall"], str)
    assert len(result.fingerprints["overall"]) == 64  # SHA-256 hex digest length


# ---------------------------------------------------------------------------
# Architectural tests -- no forbidden imports, no writes to data/raw or data/processed.
# ---------------------------------------------------------------------------

_FORBIDDEN_IMPORTS = (
    "phase3_reference",
    "qwen",
    "transformers",
    "sentence_transformers",
    "openai",
    "anthropic",
    "torch",
    "tensorflow",
    "sklearn",
    "requests",
    "urllib3",
    "httpx",
    "socket",
)


def _integration_module_files():
    for path in sorted(INTEGRATION_DIR.glob("*.py")):
        yield path


def test_no_forbidden_imports_anywhere_in_integration_package():
    for path in _integration_module_files():
        text = path.read_text(encoding="utf-8")
        lowered = text.lower()
        for forbidden in _FORBIDDEN_IMPORTS:
            # Only match actual import statements, not incidental substrings.
            assert f"import {forbidden}" not in lowered, f"{path.name} imports {forbidden!r}"
            assert f"from {forbidden}" not in lowered, f"{path.name} imports from {forbidden!r}"


def test_no_writes_to_protected_data_directories():
    protected_markers = ("data/raw", "data/processed", "data\\raw", "data\\processed")
    write_modes = ('"w"', "'w'", '"a"', "'a'", '"w+"', "'w+'", '"r+"', "'r+'")
    for path in _integration_module_files():
        text = path.read_text(encoding="utf-8")
        for marker in protected_markers:
            if marker in text:
                # If the protected path string appears at all, it must never be paired
                # with a write-mode file open anywhere in the same file.
                for mode in write_modes:
                    assert mode not in text, (
                        f"{path.name} references {marker!r} and also opens a file in a "
                        f"write mode ({mode}) -- protected data directories must never be "
                        "written to."
                    )


def test_integration_modules_only_read_files_in_read_mode():
    for path in _integration_module_files():
        text = path.read_text(encoding="utf-8")
        assert '"w")' not in text and "'w')" not in text
        assert '"a")' not in text and "'a')" not in text


# ---------------------------------------------------------------------------
# Contract-shape validation sanity: a genuinely malformed AgentVisibleContext must fail
# jsonschema validation via the pipeline's own validate_agent_visible_context_shape.
# ---------------------------------------------------------------------------


def test_malformed_agent_visible_context_fails_schema_validation():
    from phase3.evaluation.integration.pipeline import validate_agent_visible_context_shape

    malformed = {"schema_version": "3.2-b.1", "condition": "NO_MEMORY"}  # missing required "task"
    with pytest.raises(ValidationError):
        validate_agent_visible_context_shape(malformed, CONDITION_NO_MEMORY)


def test_provisional_condition_skips_schema_validation_with_warning():
    from phase3.evaluation.agent.conditions import CONDITION_SELECTED_MEMORY_AVAILABLE
    from phase3.evaluation.integration.pipeline import validate_agent_visible_context_shape

    payload = {"schema_version": "3.2-b.1", "task": {"prompt": "x"}, "condition": CONDITION_SELECTED_MEMORY_AVAILABLE, "memory_content": []}
    warnings = validate_agent_visible_context_shape(payload, CONDITION_SELECTED_MEMORY_AVAILABLE)
    assert len(warnings) == 1
    assert "PROVISIONAL" in warnings[0]


# ---------------------------------------------------------------------------
# metric_support_gate / task_layer_gate direct unit coverage (used heavily by pipeline).
# ---------------------------------------------------------------------------


def test_metric_support_gate_matches_profile_literally():
    attempt, reason = metric_support_gate(MSC_PROFILE, "STRICT_TSR")
    assert attempt is False
    assert "UNAVAILABLE" in reason

    attempt2, reason2 = metric_support_gate(LOCOMO_PROFILE, "STRICT_TSR")
    assert attempt2 is True
    assert reason2 == ""


def test_metric_support_gate_rejects_unknown_metric_family():
    with pytest.raises(KeyError):
        metric_support_gate(LOCOMO_PROFILE, "NOT_A_REAL_METRIC")


def test_task_layer_gate_locomo_vs_msc():
    ok_locomo, reason_locomo = task_layer_gate(LOCOMO_PROFILE)
    assert ok_locomo is True
    assert reason_locomo == ""

    ok_msc, reason_msc = task_layer_gate(MSC_PROFILE)
    assert ok_msc is False
    assert reason_msc != ""


# ---------------------------------------------------------------------------
# build_evaluator_reference never invents ground truth.
# ---------------------------------------------------------------------------


def test_build_evaluator_reference_faithfully_propagates_none_and_empty():
    ref_null_answer = build_evaluator_reference(
        "locomo", {"answer": None, "evidence_memory_ids": ["m1"]}, LOCOMO_PROFILE, "t"
    )
    assert ref_null_answer["gold_answer"] is None

    ref_empty_evidence = build_evaluator_reference(
        "locomo", {"answer": "x", "evidence_memory_ids": []}, LOCOMO_PROFILE, "t"
    )
    assert ref_empty_evidence["gold_evidence_ids"] == []

    ref_missing_evidence_field = build_evaluator_reference(
        "locomo", {"answer": "x"}, LOCOMO_PROFILE, "t"
    )
    assert ref_missing_evidence_field["gold_evidence_ids"] == []


def test_build_evaluator_reference_refuses_for_no_task_layer_dataset():
    ref = build_evaluator_reference("msc", {}, MSC_PROFILE, "msc-t")
    assert ref["applicable"] is False
    assert "reason" in ref and ref["reason"]
    assert "gold_answer" not in ref
    assert "gold_evidence_ids" not in ref


# ---------------------------------------------------------------------------
# 3.2-H remediation: EvaluatorReference schema fix for missing gold_answer
#
# `evaluator_reference.schema.json`'s `gold_answer` previously required `type: "string"`
# (no null) -- unable to represent LoCoMo's real question_type "5" null-answer records.
# The schema now declares `gold_answer: {"type": ["string", "null"]}`; the key remains
# REQUIRED (omitting it is still a violation), only its value may legitimately be null.
# These tests prove the fix directly against the schema and end-to-end through the
# pipeline -- not merely that the pipeline "runs without exception."
# ---------------------------------------------------------------------------

from jsonschema import Draft202012Validator

from phase3.evaluation.integration.pipeline import validate_evaluator_reference_shape


def _load_evaluator_reference_schema():
    import json

    with open(INTEGRATION_DIR.parent / "contracts" / "evaluator_reference.schema.json", "r", encoding="utf-8") as f:
        return json.load(f)


_EVALUATOR_REFERENCE_SCHEMA = _load_evaluator_reference_schema()


def test_evaluator_reference_schema_accepts_null_gold_answer():
    payload = {
        "schema_version": "3.2-b.1",
        "task_id": "t1",
        "gold_answer": None,
        "gold_evidence_ids": [],
    }
    Draft202012Validator(_EVALUATOR_REFERENCE_SCHEMA).validate(payload)  # must not raise


def test_evaluator_reference_schema_accepts_non_null_gold_answer():
    payload = {
        "schema_version": "3.2-b.1",
        "task_id": "t1",
        "gold_answer": "May 8, 2023",
        "gold_evidence_ids": ["mem-a"],
    }
    Draft202012Validator(_EVALUATOR_REFERENCE_SCHEMA).validate(payload)  # must not raise


def test_evaluator_reference_schema_accepts_empty_string_gold_answer():
    """Empty string is a real, distinct value from null -- both must validate."""
    payload = {
        "schema_version": "3.2-b.1",
        "task_id": "t1",
        "gold_answer": "",
        "gold_evidence_ids": [],
    }
    Draft202012Validator(_EVALUATOR_REFERENCE_SCHEMA).validate(payload)  # must not raise


def test_evaluator_reference_schema_still_requires_the_key_present():
    """Making the VALUE nullable must not make the KEY optional -- omitting `gold_answer`
    entirely remains a schema violation (mirrors
    test_evaluation_contracts.py::test_evaluator_reference_missing_gold_answer_fails,
    re-asserted here against the fixed schema to prove the fix didn't loosen this)."""
    payload = {"schema_version": "3.2-b.1", "task_id": "t1", "gold_evidence_ids": []}
    with pytest.raises(ValidationError):
        Draft202012Validator(_EVALUATOR_REFERENCE_SCHEMA).validate(payload)


def test_evaluator_reference_schema_rejects_malformed_gold_answer_type():
    """The schema must remain strict about TYPE -- only string or null, never a number,
    list, or object, even after the nullability fix."""
    for bad_value in (42, ["not", "a", "string"], {"nested": "object"}, True):
        payload = {
            "schema_version": "3.2-b.1",
            "task_id": "t1",
            "gold_answer": bad_value,
            "gold_evidence_ids": [],
        }
        with pytest.raises(ValidationError):
            Draft202012Validator(_EVALUATOR_REFERENCE_SCHEMA).validate(payload)


def test_pipeline_validate_evaluator_reference_shape_accepts_null_answer():
    case = _locomo_case("remediation-1", CONDITION_RETRIEVED_MEMORY, answer=None)
    validate_evaluator_reference_shape(case.evaluator_reference)  # must not raise


def test_pipeline_validate_evaluator_reference_shape_accepts_non_null_answer():
    case = _locomo_case("remediation-2", CONDITION_RETRIEVED_MEMORY, answer="May 8, 2023")
    validate_evaluator_reference_shape(case.evaluator_reference)  # must not raise


def test_pipeline_validate_evaluator_reference_shape_rejects_missing_key():
    broken = {"schema_version": "3.2-b.1", "task_id": "t1", "gold_evidence_ids": []}
    with pytest.raises(ValidationError):
        validate_evaluator_reference_shape(broken)


def test_pipeline_validate_evaluator_reference_shape_ignores_integration_only_keys():
    """`applicable`/`dataset_id` are this integration layer's own bookkeeping keys, not
    part of the frozen schema -- they must be stripped before validation, not cause a
    spurious additionalProperties failure."""
    case = _locomo_case("remediation-3", CONDITION_RETRIEVED_MEMORY, answer="x")
    assert "applicable" in case.evaluator_reference
    assert "dataset_id" in case.evaluator_reference
    validate_evaluator_reference_shape(case.evaluator_reference)  # must not raise


def test_null_gold_answer_end_to_end_through_pipeline_is_undefined_not_incorrect():
    """LoCoMo regression: a real question_type '5'-shaped record (answer=None) flows
    through the FULL pipeline (schema validation, leakage validation, metric computation,
    trace/result assembly, fingerprinting) and produces EVALUATION_UNDEFINED for both
    AGENT_ANSWER_CORRECTNESS and AGENT_SUCCESS -- never ANSWER_INCORRECT, never a raised
    exception, never a false failure."""
    case = _locomo_case("remediation-4", CONDITION_RETRIEVED_MEMORY, answer=None)
    result = evaluate_case(case, LOCOMO_PROFILE, synthetic_behavior=BEHAVIOR_ALWAYS_CORRECT)

    correctness = result.metrics["AGENT_ANSWER_CORRECTNESS"]
    success = result.metrics["AGENT_SUCCESS"]
    assert correctness.status == "EVALUATION_UNDEFINED"
    assert correctness.value is None
    assert success.status == "EVALUATION_UNDEFINED"
    assert success.value is None
    # Traceability: the trace and evaluation_result were still built and schema-valid.
    assert result.trace["task_id"] == "remediation-4"
    assert result.evaluation_result["result_status"] in ("COMPLETE", "PARTIAL")
    # Reproducibility: fingerprints were computed (not skipped/None) for this null-answer case.
    assert result.fingerprints["overall"]


def test_null_gold_answer_does_not_leak_into_agent_visible_context():
    """Even though gold_answer may now legally be null in EvaluatorReference, it must
    still never appear in AgentVisibleContext -- nullability of the evaluator-only field
    changes nothing about the visibility boundary."""
    case = _locomo_case("remediation-5", CONDITION_RETRIEVED_MEMORY, answer=None)
    assert "gold_answer" not in case.agent_visible_context
    leakage = validate_against_boundary(case.agent_visible_context)
    assert leakage.status == "NO_LEAKAGE"


def test_non_null_gold_answer_end_to_end_unchanged_by_remediation():
    """Regression: normal (non-null) LoCoMo answers still evaluate exactly as before --
    the schema fix does not change behavior for the common case."""
    case = _locomo_case("remediation-6", CONDITION_RETRIEVED_MEMORY, answer="May 8, 2023")
    result = evaluate_case(case, LOCOMO_PROFILE, synthetic_behavior=BEHAVIOR_ALWAYS_CORRECT)
    correctness = result.metrics["AGENT_ANSWER_CORRECTNESS"]
    assert correctness.status == "ANSWER_CORRECT"
    assert correctness.value == 1.0


def test_empty_string_gold_answer_is_not_treated_as_undefined():
    """Empty string is a real, distinct value from null: `evaluate_answer_correctness`
    treats `expected_answer is None` as undefined, but an empty string is not None -- it
    participates in normal exact-match comparison (an agent answering "" against a gold
    answer of "" would be judged CORRECT, not UNDEFINED). This is documented, not silently
    collapsed with the null case."""
    case = _locomo_case("remediation-7", CONDITION_RETRIEVED_MEMORY, answer="")
    result = evaluate_case(case, LOCOMO_PROFILE, synthetic_behavior=BEHAVIOR_ALWAYS_WRONG)
    correctness = result.metrics["AGENT_ANSWER_CORRECTNESS"]
    # BEHAVIOR_ALWAYS_WRONG answers something non-empty, so comparison against "" is a
    # real (defined) mismatch -- INCORRECT, not UNDEFINED. Proves "" is compared, not skipped.
    assert correctness.status == "ANSWER_INCORRECT"
    assert correctness.status != "EVALUATION_UNDEFINED"


def test_null_gold_answer_is_deterministic_across_repeated_runs():
    """Same remediation case run twice must produce identical result and fingerprint."""
    case1 = _locomo_case("remediation-8", CONDITION_RETRIEVED_MEMORY, answer=None)
    case2 = _locomo_case("remediation-8", CONDITION_RETRIEVED_MEMORY, answer=None)
    result1 = evaluate_case(case1, LOCOMO_PROFILE, synthetic_behavior=BEHAVIOR_ALWAYS_CORRECT)
    result2 = evaluate_case(case2, LOCOMO_PROFILE, synthetic_behavior=BEHAVIOR_ALWAYS_CORRECT)

    assert result1.metrics["AGENT_ANSWER_CORRECTNESS"].status == result2.metrics["AGENT_ANSWER_CORRECTNESS"].status
    assert result1.fingerprints["overall"] == result2.fingerprints["overall"]
    assert fingerprint(case1.evaluator_reference) == fingerprint(case2.evaluator_reference)
