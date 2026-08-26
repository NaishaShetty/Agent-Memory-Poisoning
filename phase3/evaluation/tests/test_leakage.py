"""Phase 3.2-F tests for `phase3/evaluation/security/leakage.py`.

Scope note: this suite does not modify, re-run, or depend on any of the five existing
test files (334 tests total baseline as of 3.2-E), all of which must remain green,
unmodified, alongside this file.
"""

from __future__ import annotations

import copy
import inspect
import json

import pytest

from phase3.evaluation.contracts.boundary import FORBIDDEN_KEYS
from phase3.evaluation.metrics.types import MetricResult, STATUS_OK

from phase3.evaluation.agent.conditions import (
    ALL_CONDITIONS,
    CANONICAL_CONDITIONS,
    PROVISIONAL_CONDITIONS,
    CONDITION_NO_MEMORY,
    CONDITION_GOLD_EVIDENCE,
    CONDITION_RETRIEVED_MEMORY,
    CONDITION_SELECTED_MEMORY_AVAILABLE,
    CONDITION_DERIVED_MEMORY_AVAILABLE,
    CONDITION_CONFLICTING_MEMORY_AVAILABLE,
    build_agent_visible_context,
)
from phase3.evaluation.agent.outcomes import AgentExecutionResult, EXECUTION_STATUS_SUCCESS

from phase3.evaluation import security as security_pkg
from phase3.evaluation.security import leakage as leakage_mod
from phase3.evaluation.security.leakage import (
    STATUS_NO_LEAKAGE,
    STATUS_LEAKAGE_DETECTED,
    STATUS_VALIDATION_UNDEFINED,
    VIOLATION_FORBIDDEN_KEY,
    VIOLATION_METRIC_RESULT_SHAPE,
    PROTECTED_FIELD_NAMES,
    validate_no_leakage,
    validate_against_boundary,
    check_serialization_round_trip,
)


# ---------------------------------------------------------------------------
# Scenario 1: Clean NO_MEMORY -> NO_LEAKAGE
# ---------------------------------------------------------------------------


def test_scenario_clean_no_memory_context_is_no_leakage():
    ctx = build_agent_visible_context(
        condition=CONDITION_NO_MEMORY, task_id="task-1", prompt="What is the capital of France?"
    )
    result = validate_no_leakage(ctx, condition=CONDITION_NO_MEMORY)
    assert result.status == STATUS_NO_LEAKAGE
    assert result.findings == ()


# ---------------------------------------------------------------------------
# Scenario 2: Gold IDs inserted -> LEAKAGE_DETECTED
# ---------------------------------------------------------------------------


def test_scenario_gold_ids_inserted_is_leakage_detected():
    ctx = build_agent_visible_context(
        condition=CONDITION_RETRIEVED_MEMORY,
        task_id="task-2",
        prompt="Where does Alice work?",
        memory_items=[{"memory_id": "mem-1", "content": "Alice works at Acme."}],
    )
    tampered = dict(ctx)
    tampered["gold_evidence_ids"] = ["locomo-mem-8842"]
    result = validate_no_leakage(tampered, condition=CONDITION_RETRIEVED_MEMORY)
    assert result.status == STATUS_LEAKAGE_DETECTED
    assert any("gold_evidence_ids" in p for p in result.leaked_paths)
    assert VIOLATION_FORBIDDEN_KEY in result.violation_types


# ---------------------------------------------------------------------------
# Scenario 3: Nested evaluator label -> LEAKAGE_DETECTED
# ---------------------------------------------------------------------------


def test_scenario_nested_evaluator_label_is_leakage_detected():
    payload = {
        "task": {"task_id": "t3", "prompt": "hi"},
        "memory_content": [{"memory_id": "m1", "content": "some fact"}],
        "debug": {"metadata": {"evaluation": {"evaluation_label": "CORRECT"}}},
    }
    result = validate_no_leakage(payload)
    assert result.status == STATUS_LEAKAGE_DETECTED
    assert any("evaluation_label" in p for p in result.leaked_paths)


def test_scenario_nested_selected_gold_pattern_is_leakage_detected():
    payload = {"task": {"task_id": "t3b"}, "debug": {"selected_gold": ["mem-1", "mem-2"]}}
    result = validate_no_leakage(payload)
    assert result.status == STATUS_LEAKAGE_DETECTED
    assert any("selected_gold" in p for p in result.leaked_paths)


def test_scenario_nested_metadata_correct_flag_is_leakage_detected():
    payload = {"task_id": "t3c", "metadata": {"evaluation": {"correct": True}}}
    result = validate_no_leakage(payload)
    assert result.status == STATUS_LEAKAGE_DETECTED
    assert any("correct" in p for p in result.leaked_paths)


# ---------------------------------------------------------------------------
# Scenario 4: Allowed gold evidence content, no IDs -> NO_LEAKAGE
# ---------------------------------------------------------------------------


def test_scenario_gold_evidence_content_without_ids_is_no_leakage():
    ctx = build_agent_visible_context(
        condition=CONDITION_GOLD_EVIDENCE,
        task_id="task-4",
        prompt="What did Bob eat?",
        memory_items=[{"memory_id": "evidence-slot-1", "content": "Bob ate a sandwich."}],
    )
    result = validate_no_leakage(ctx, condition=CONDITION_GOLD_EVIDENCE)
    assert result.status == STATUS_NO_LEAKAGE


def test_false_positive_control_gold_colored_shoes_is_not_flagged():
    """The single most important false-positive-control example from the task brief:
    content that happens to contain the SUBSTRING "gold" inside a string VALUE must never
    be flagged -- this module matches KEYS, never scans string content."""
    payload = {
        "task": {"task_id": "t-shoes", "prompt": "What did the user buy?"},
        "memory_content": [
            {"memory_id": "mem-7", "content": "The user bought gold-colored shoes."}
        ],
    }
    result = validate_no_leakage(payload)
    assert result.status == STATUS_NO_LEAKAGE


# ---------------------------------------------------------------------------
# Condition coverage: all 6 conditions (3 canonical + 3 provisional)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("condition", ALL_CONDITIONS, ids=lambda c: c)
def test_all_six_conditions_produce_clean_agent_visible_context(condition):
    ctx = build_agent_visible_context(
        condition=condition,
        task_id=f"task-{condition}",
        prompt="Task prompt.",
        memory_items=[{"memory_id": "mem-A", "content": "Content A."}],
    )
    result = validate_no_leakage(ctx, condition=condition)
    assert result.status == STATUS_NO_LEAKAGE


@pytest.mark.parametrize("condition", ALL_CONDITIONS, ids=lambda c: c)
def test_all_six_conditions_flag_tampered_gold_field(condition):
    ctx = build_agent_visible_context(
        condition=condition,
        task_id=f"task-{condition}",
        prompt="Task prompt.",
        memory_items=[{"memory_id": "mem-A", "content": "Content A."}],
    )
    tampered = dict(ctx)
    tampered["gold_answer"] = "Paris"
    result = validate_no_leakage(tampered, condition=condition)
    assert result.status == STATUS_LEAKAGE_DETECTED


def test_unrecognized_condition_is_validation_undefined():
    result = validate_no_leakage({"a": 1}, condition="NOT_A_REAL_CONDITION")
    assert result.status == STATUS_VALIDATION_UNDEFINED


# ---------------------------------------------------------------------------
# Malformed input never silently coerced to NO_LEAKAGE
# ---------------------------------------------------------------------------


class _Unstructured:
    """An arbitrary object with no dict/list/tuple/dataclass/scalar shape."""


def test_malformed_input_is_validation_undefined_not_no_leakage():
    result = validate_no_leakage(_Unstructured())
    assert result.status == STATUS_VALIDATION_UNDEFINED
    assert result.status != STATUS_NO_LEAKAGE


def test_scalar_payload_is_no_leakage():
    assert validate_no_leakage("just a string").status == STATUS_NO_LEAKAGE
    assert validate_no_leakage(42).status == STATUS_NO_LEAKAGE
    assert validate_no_leakage(None).status == STATUS_NO_LEAKAGE


# ---------------------------------------------------------------------------
# MetricResult-shape detection
# ---------------------------------------------------------------------------


def test_metric_result_dataclass_embedded_in_payload_is_leakage_detected():
    mr = MetricResult(metric_name="STRICT_TSR", value=1.0, status=STATUS_OK, detail={})
    payload = {"task_id": "t5", "debug_info": mr}
    result = validate_no_leakage(payload)
    assert result.status == STATUS_LEAKAGE_DETECTED
    assert VIOLATION_METRIC_RESULT_SHAPE in result.violation_types


def test_metric_result_shaped_dict_without_matching_key_name_is_still_flagged():
    """Even if none of metric_name/value/status/detail is itself in PROTECTED_FIELD_NAMES,
    the SHAPE match (superset of the four MetricResult fields) must still be caught."""
    payload = {
        "container": {
            "metric_name": "SOMETHING",
            "value": 0.5,
            "status": "OK",
            "detail": {},
        }
    }
    assert not ({"metric_name", "value", "status", "detail"} & PROTECTED_FIELD_NAMES)
    result = validate_no_leakage(payload)
    assert result.status == STATUS_LEAKAGE_DETECTED
    assert VIOLATION_METRIC_RESULT_SHAPE in result.violation_types


def test_dict_missing_one_metric_result_field_is_not_flagged_as_metric_shape():
    payload = {"container": {"metric_name": "X", "value": 1.0, "status": "OK"}}
    result = validate_no_leakage(payload)
    assert result.status == STATUS_NO_LEAKAGE


# ---------------------------------------------------------------------------
# Serialization leakage (explicit round-trip checks)
# ---------------------------------------------------------------------------


def test_serialization_round_trip_preserves_leakage_free_status():
    ctx = build_agent_visible_context(
        condition=CONDITION_RETRIEVED_MEMORY,
        task_id="task-6",
        prompt="Task.",
        memory_items=[{"memory_id": "mem-1", "content": "fact"}],
    )
    original, round_tripped = check_serialization_round_trip(ctx, condition=CONDITION_RETRIEVED_MEMORY)
    assert original.status == STATUS_NO_LEAKAGE
    assert round_tripped.status == STATUS_NO_LEAKAGE


def test_serialization_round_trip_still_catches_leakage():
    ctx = build_agent_visible_context(
        condition=CONDITION_RETRIEVED_MEMORY, task_id="task-7", prompt="Task."
    )
    tampered = dict(ctx)
    tampered["evaluation_metadata"] = {"internal_rank": 3}
    original, round_tripped = check_serialization_round_trip(tampered)
    assert original.status == STATUS_LEAKAGE_DETECTED
    assert round_tripped.status == STATUS_LEAKAGE_DETECTED


def test_clean_payload_does_not_acquire_evaluator_fields_on_deserialization():
    """Reverse direction: a clean serialized payload, deserialized back, must not
    spontaneously acquire an evaluator-only key. json.loads(json.dumps(x)) cannot invent
    new keys, but this test proves it directly rather than assuming it."""
    ctx = build_agent_visible_context(condition=CONDITION_NO_MEMORY, task_id="t8", prompt="hi")
    serialized = json.dumps(ctx, sort_keys=True)
    deserialized = json.loads(serialized)
    assert set(deserialized.keys()) == set(ctx.keys())
    result = validate_no_leakage(deserialized)
    assert result.status == STATUS_NO_LEAKAGE


def test_non_json_serializable_payload_raises_type_error_not_silently_skipped():
    class _Weird:
        pass

    with pytest.raises(TypeError):
        check_serialization_round_trip({"x": _Weird()})


# ---------------------------------------------------------------------------
# validate_against_boundary reuses boundary.py rather than duplicating its logic
# ---------------------------------------------------------------------------


def test_validate_against_boundary_rejects_top_level_forbidden_key():
    payload = {"task": {"task_id": "t9"}, "gold_answer": "leak"}
    result = validate_against_boundary(payload)
    assert result.status == STATUS_LEAKAGE_DETECTED


def test_validate_against_boundary_accepts_clean_payload():
    ctx = build_agent_visible_context(condition=CONDITION_NO_MEMORY, task_id="t10", prompt="hi")
    result = validate_against_boundary(ctx)
    assert result.status == STATUS_NO_LEAKAGE


def test_protected_field_names_is_superset_of_boundary_forbidden_keys():
    assert FORBIDDEN_KEYS <= PROTECTED_FIELD_NAMES


# ---------------------------------------------------------------------------
# Scenario 14: manifest presented as agent-visible context -> LEAKAGE_DETECTED
# ---------------------------------------------------------------------------


def test_reproducibility_manifest_as_agent_visible_context_is_leakage_detected():
    """Proves manifest != AgentVisibleContext: a reproducibility manifest, if a caller
    mistakenly handed it to something expecting AgentVisibleContext, must fail the leakage
    validator. This is deliberately imported lazily to keep leakage.py/reproducibility.py
    decoupled at import time; the test itself is what proves the structural distinction."""
    from phase3.evaluation.security.reproducibility import build_manifest

    manifest = build_manifest(
        run_id="run-1",
        task_ids=["t1"],
        conditions=[CONDITION_RETRIEVED_MEMORY],
        input_fingerprint="a" * 64,
        agent_visible_context_fingerprint="b" * 64,
        evaluator_reference_fingerprint="c" * 64,
        configuration_fingerprint="d" * 64,
        code_version="0.1.0",
        contract_version="3.2-b.1",
        metric_version="3.2-c.1",
        timestamp="2026-08-26T00:00:00Z",
    )
    result = validate_no_leakage(manifest)
    assert result.status == STATUS_LEAKAGE_DETECTED
    assert any("evaluator_reference_fingerprint" in p for p in result.leaked_paths)


# ---------------------------------------------------------------------------
# Invariant / property tests
# ---------------------------------------------------------------------------


def test_invariant_leakage_free_context_remains_leakage_free_after_serialization():
    for condition in ALL_CONDITIONS:
        ctx = build_agent_visible_context(
            condition=condition,
            task_id=f"inv-{condition}",
            prompt="p",
            memory_items=[{"memory_id": "m1", "content": "c"}],
        )
        original, round_tripped = check_serialization_round_trip(ctx, condition=condition)
        assert original.status == STATUS_NO_LEAKAGE
        assert round_tripped.status == STATUS_NO_LEAKAGE


def test_invariant_evaluator_only_fields_remain_absent_after_serialization():
    ctx = build_agent_visible_context(condition=CONDITION_NO_MEMORY, task_id="inv2", prompt="p")
    serialized_keys = set(json.loads(json.dumps(ctx)).keys())
    assert not (serialized_keys & PROTECTED_FIELD_NAMES)


def test_validate_no_leakage_does_not_mutate_input():
    ctx = build_agent_visible_context(
        condition=CONDITION_RETRIEVED_MEMORY,
        task_id="t-mut",
        prompt="p",
        memory_items=[{"memory_id": "m1", "content": "c"}],
    )
    before = copy.deepcopy(ctx)
    validate_no_leakage(ctx, condition=CONDITION_RETRIEVED_MEMORY)
    assert ctx == before


# ---------------------------------------------------------------------------
# Architectural tests
# ---------------------------------------------------------------------------

_FORBIDDEN_IMPORTS = (
    "sentence_transformers",
    "openai",
    "torch",
    "sklearn",
    "requests",
    "urllib",
    "phase3_reference",
    "qwen",
    "transformers",
    "anthropic",
)

_SECURITY_MODULES = (leakage_mod,)


@pytest.mark.parametrize("module", _SECURITY_MODULES, ids=lambda m: m.__name__)
def test_security_modules_never_import_forbidden_libraries(module):
    source = inspect.getsource(module)
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith(("import ", "from ")):
            for forbidden in _FORBIDDEN_IMPORTS:
                assert forbidden not in stripped.lower()


def test_no_leakage_module_does_direct_dataset_loading():
    source = inspect.getsource(leakage_mod)
    for forbidden_token in ("pd.read_", "pickle.load"):
        assert forbidden_token not in source
    # open()/Path() are not used anywhere in this module.
    for forbidden_token in ("open(", "Path("):
        assert forbidden_token not in source


def test_leakage_module_never_reads_real_dataset_paths():
    source = inspect.getsource(leakage_mod)
    for forbidden_token in ("data/raw", "data/processed", "data/metadata", "data/reports"):
        assert forbidden_token not in source


def test_no_metric_result_object_flows_into_agent_visible_context_construction_path():
    """No AgentVisibleContext-shaped construction path (build_agent_visible_context) can
    receive evaluator-only fields -- reuses conditions.py's own boundary check, and this
    test additionally proves a MetricResult passed as a memory item is caught, even though
    boundary.py's narrower walker only descends into dict/list and would not by itself
    descend into a dataclass instance embedded as a leaf value. The leakage module's
    recursive check (which DOES normalize/descend into dataclasses via `_normalize`)
    catches this case."""
    mr = MetricResult(metric_name="STRICT_TSR", value=1.0, status=STATUS_OK, detail={})
    payload = {"task": {"task_id": "t"}, "memory_content": [{"memory_id": "m1", "score_obj": mr}]}
    result = validate_no_leakage(payload)
    assert result.status == STATUS_LEAKAGE_DETECTED
    assert VIOLATION_METRIC_RESULT_SHAPE in result.violation_types
