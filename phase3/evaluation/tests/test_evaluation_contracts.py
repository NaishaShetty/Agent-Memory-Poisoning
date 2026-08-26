"""Phase 3.2-B tests for the evaluation data-contract schemas, fixtures, and boundary module.

Scope note: this test suite validates STRUCTURE only -- JSON Schema conformance, the
agent-visible/evaluator-only separation, and cross-fixture leakage absence. It does not
compute or assert any metric value (Recall@K, MRR, TSR, etc.) -- those do not exist yet
and are explicitly out of scope until Phase 3.2-C.

Uses `jsonschema` (already importable in this environment; not added to requirements.txt
since this is a repo-root file conventionally owned by Phase 1/2 tooling -- see the 3.2-B
README for this design note).
"""

from __future__ import annotations

import copy
import importlib.util
import inspect
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

CONTRACTS_DIR = Path(__file__).resolve().parent.parent / "contracts"
FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"

SCHEMA_FILES = {
    "evaluation_run": CONTRACTS_DIR / "evaluation_run.schema.json",
    "agent_visible_context": CONTRACTS_DIR / "agent_visible_context.schema.json",
    "evaluator_reference": CONTRACTS_DIR / "evaluator_reference.schema.json",
    "agent_execution_result": CONTRACTS_DIR / "agent_execution_result.schema.json",
    "trace_artifact": CONTRACTS_DIR / "trace_artifact.schema.json",
    "evaluation_result": CONTRACTS_DIR / "evaluation_result.schema.json",
}


def load_schema(name: str) -> dict:
    with open(SCHEMA_FILES[name], "r", encoding="utf-8") as f:
        return json.load(f)


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def validator_for(name: str) -> Draft202012Validator:
    schema = load_schema(name)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


# ---------------------------------------------------------------------------
# boundary.py import (module under test, loaded by path since phase3/ has no
# package __init__ chain wired into the root test config)
# ---------------------------------------------------------------------------

_boundary_spec = importlib.util.spec_from_file_location(
    "phase3_evaluation_boundary", CONTRACTS_DIR / "boundary.py"
)
boundary = importlib.util.module_from_spec(_boundary_spec)
_boundary_spec.loader.exec_module(boundary)  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# 1. All schemas are themselves valid Draft 2020-12 schemas
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(SCHEMA_FILES))
def test_schema_itself_is_valid_draft_2020_12(name):
    schema = load_schema(name)
    Draft202012Validator.check_schema(schema)


@pytest.mark.parametrize("name", sorted(SCHEMA_FILES))
def test_schema_requires_schema_version(name):
    schema = load_schema(name)
    assert "schema_version" in schema.get("required", []), (
        f"{name} schema must require schema_version"
    )
    assert schema["properties"]["schema_version"]["type"] == "string"


# ---------------------------------------------------------------------------
# 2. Fixture -> schema mapping and validation
# ---------------------------------------------------------------------------

FIXTURE_SCENARIOS = [
    "no_memory",
    "gold_evidence",
    "retrieved_memory",
]

RUN_LEVEL_FILES = {
    "evaluation_run": "evaluation_run",
    "agent_visible_context": "agent_visible_context",
    "evaluator_reference": "evaluator_reference",
    "agent_execution_result": "agent_execution_result",
    "trace_artifact": "trace_artifact",
    "evaluation_result": "evaluation_result",
}


@pytest.mark.parametrize("scenario", FIXTURE_SCENARIOS)
@pytest.mark.parametrize("schema_name,file_stem", sorted(RUN_LEVEL_FILES.items()))
def test_run_scenario_fixture_validates(scenario, schema_name, file_stem):
    fixture_path = FIXTURES_DIR / scenario / f"{file_stem}.json"
    assert fixture_path.exists(), f"missing fixture {fixture_path}"
    payload = load_json(fixture_path)
    validator_for(schema_name).validate(payload)


def test_derived_memory_fixtures_validate_against_memory_schema():
    memory_schema_path = (
        Path(__file__).resolve().parent.parent.parent / "schemas" / "memory_schema.json"
    )
    schema = load_json(memory_schema_path)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    for fname in ("memory_foundation_a.json", "memory_foundation_b.json", "memory_derived_c.json"):
        payload = load_json(FIXTURES_DIR / "derived_memory" / fname)
        validator.validate(payload)


def test_conflicting_memory_fixtures_validate_against_memory_schema():
    memory_schema_path = (
        Path(__file__).resolve().parent.parent.parent / "schemas" / "memory_schema.json"
    )
    schema = load_json(memory_schema_path)
    validator = Draft202012Validator(schema)
    for fname in ("memory_a.json", "memory_b.json"):
        payload = load_json(FIXTURES_DIR / "conflicting_memory" / fname)
        validator.validate(payload)


def test_equivalent_memory_fixtures_validate_against_memory_schema():
    memory_schema_path = (
        Path(__file__).resolve().parent.parent.parent / "schemas" / "memory_schema.json"
    )
    schema = load_json(memory_schema_path)
    validator = Draft202012Validator(schema)
    for fname in ("memory_a.json", "memory_b.json"):
        payload = load_json(FIXTURES_DIR / "equivalent_memory" / fname)
        validator.validate(payload)


# ---------------------------------------------------------------------------
# 3. Relationship semantics: derived, conflicting, equivalent
# ---------------------------------------------------------------------------


def test_derived_memory_has_explicit_parent_ids_and_no_giant_family():
    derived = load_json(FIXTURES_DIR / "derived_memory" / "memory_derived_c.json")
    assert derived["memory_type"] == "derived"
    assert set(derived["parent_ids"]) == {"mem-found-A", "mem-found-B"}

    found_a = load_json(FIXTURES_DIR / "derived_memory" / "memory_foundation_a.json")
    found_b = load_json(FIXTURES_DIR / "derived_memory" / "memory_foundation_b.json")
    assert found_a["memory_type"] == "foundation"
    assert found_a["parent_ids"] == []
    assert found_b["memory_type"] == "foundation"
    assert found_b["parent_ids"] == []


def test_conflicting_memory_preserves_both_records_via_conflicts_with():
    mem_a = load_json(FIXTURES_DIR / "conflicting_memory" / "memory_a.json")
    mem_b = load_json(FIXTURES_DIR / "conflicting_memory" / "memory_b.json")
    assert "mem-pref-coffee" in mem_a["conflicts_with"]
    assert "mem-pref-tea" in mem_b["conflicts_with"]
    # A is superseded (retired) but NOT deleted -- both memory records still exist as files
    assert mem_a["lifecycle_state"] == "RETIRED"
    assert mem_a["superseded_by"] == "mem-pref-coffee"
    assert mem_b["lifecycle_state"] == "ACTIVE"


def test_equivalent_memory_preserves_distinct_identity():
    mem_a = load_json(FIXTURES_DIR / "equivalent_memory" / "memory_a.json")
    mem_b = load_json(FIXTURES_DIR / "equivalent_memory" / "memory_b.json")
    # distinct identities
    assert mem_a["memory_id"] != mem_b["memory_id"]
    # joined by an explicit, symmetric equivalent_to relationship
    assert mem_b["memory_id"] in mem_a["equivalent_to"]
    assert mem_a["memory_id"] in mem_b["equivalent_to"]
    # no scoring/confidence field is present on either record (no metric computed)
    assert "equivalence_score" not in mem_a
    assert "equivalence_score" not in mem_b


# ---------------------------------------------------------------------------
# 4. Deliberately invalid/mutated fixtures (constructed in-test) must fail
# ---------------------------------------------------------------------------


def _valid_evaluation_run():
    return load_json(FIXTURES_DIR / "no_memory" / "evaluation_run.json")


def test_evaluation_run_missing_required_field_fails():
    payload = _valid_evaluation_run()
    del payload["run_id"]
    with pytest.raises(ValidationError):
        validator_for("evaluation_run").validate(payload)


def test_evaluation_run_invalid_condition_enum_fails():
    payload = _valid_evaluation_run()
    payload["condition"] = "MANIPULATED_MEMORY"  # not a valid enum value
    with pytest.raises(ValidationError):
        validator_for("evaluation_run").validate(payload)


def test_evaluation_run_malformed_ref_type_fails():
    payload = _valid_evaluation_run()
    payload["trace_ref"] = 12345  # refs must be strings
    with pytest.raises(ValidationError):
        validator_for("evaluation_run").validate(payload)


def test_evaluation_run_empty_ref_string_fails():
    payload = _valid_evaluation_run()
    payload["evaluation_result_ref"] = ""  # minLength: 1
    with pytest.raises(ValidationError):
        validator_for("evaluation_run").validate(payload)


def test_evaluation_run_missing_schema_version_fails():
    payload = _valid_evaluation_run()
    del payload["schema_version"]
    with pytest.raises(ValidationError):
        validator_for("evaluation_run").validate(payload)


def test_evaluation_run_invalid_schema_version_fails():
    payload = _valid_evaluation_run()
    payload["schema_version"] = "not-a-real-version"
    with pytest.raises(ValidationError):
        validator_for("evaluation_run").validate(payload)


def test_agent_visible_context_rejects_gold_answer_field():
    payload = load_json(FIXTURES_DIR / "no_memory" / "agent_visible_context.json")
    mutated = copy.deepcopy(payload)
    mutated["gold_answer"] = "leaked gold answer"
    with pytest.raises(ValidationError):
        validator_for("agent_visible_context").validate(mutated)


def test_agent_visible_context_rejects_gold_evidence_ids_field():
    payload = load_json(FIXTURES_DIR / "no_memory" / "agent_visible_context.json")
    mutated = copy.deepcopy(payload)
    mutated["gold_evidence_ids"] = ["locomo-mem-8842"]
    with pytest.raises(ValidationError):
        validator_for("agent_visible_context").validate(mutated)


def test_agent_visible_context_missing_task_fails():
    payload = load_json(FIXTURES_DIR / "no_memory" / "agent_visible_context.json")
    mutated = copy.deepcopy(payload)
    del mutated["task"]
    with pytest.raises(ValidationError):
        validator_for("agent_visible_context").validate(mutated)


def test_evaluator_reference_missing_gold_answer_fails():
    payload = load_json(FIXTURES_DIR / "no_memory" / "evaluator_reference.json")
    mutated = copy.deepcopy(payload)
    del mutated["gold_answer"]
    with pytest.raises(ValidationError):
        validator_for("evaluator_reference").validate(mutated)


def test_agent_execution_result_invalid_status_enum_fails():
    payload = load_json(FIXTURES_DIR / "no_memory" / "agent_execution_result.json")
    mutated = copy.deepcopy(payload)
    mutated["execution_status"] = "PARTIALLY_DONE"
    with pytest.raises(ValidationError):
        validator_for("agent_execution_result").validate(mutated)


def test_evaluation_result_metrics_field_must_be_object():
    payload = load_json(FIXTURES_DIR / "no_memory" / "evaluation_result.json")
    mutated = copy.deepcopy(payload)
    mutated["metrics"] = "not-an-object"
    with pytest.raises(ValidationError):
        validator_for("evaluation_result").validate(mutated)


# ---------------------------------------------------------------------------
# 5. boundary.py: defense-in-depth runtime rejection
# ---------------------------------------------------------------------------


def test_boundary_accepts_clean_agent_visible_payload():
    payload = load_json(FIXTURES_DIR / "retrieved_memory" / "agent_visible_context.json")
    assert boundary.validate_agent_visible(payload) == payload


def test_boundary_rejects_forbidden_key_even_if_schema_would_allow_it():
    # Simulate a payload that (hypothetically) bypassed JSON Schema validation --
    # e.g. hand-constructed dict never run through the validator -- to prove
    # boundary.py is an independent, second line of defense.
    payload = {
        "schema_version": "3.2-b.1",
        "condition": "RETRIEVED_MEMORY",
        "task": {"prompt": "hi"},
        "gold_answer": "leaked",
    }
    with pytest.raises(boundary.AgentVisibilityViolation):
        boundary.validate_agent_visible(payload)


def test_boundary_rejects_nested_forbidden_key():
    payload = {
        "schema_version": "3.2-b.1",
        "condition": "RETRIEVED_MEMORY",
        "task": {"prompt": "hi"},
        "memory_content": [
            {
                "memory_id": "m1",
                "content": "text",
                "permitted_provenance": {"gold_evidence_ids": ["should-not-be-here"]},
            }
        ],
    }
    with pytest.raises(boundary.AgentVisibilityViolation):
        boundary.validate_agent_visible(payload)


def test_boundary_rejects_non_dict_payload():
    with pytest.raises(boundary.AgentVisibilityViolation):
        boundary.validate_agent_visible("not a dict")  # type: ignore[arg-type]


def test_validate_agent_visible_signature_has_no_evaluator_reference_param():
    """The agent-visible validation path must not accept/require an EvaluatorReference.

    This is the automated check for the load-bearing property described in
    boundary.py's module docstring: the function that gates what the agent sees
    must not be wired to depend on evaluator-only data by construction.
    """
    sig = inspect.signature(boundary.validate_agent_visible)
    param_names = {p.lower() for p in sig.parameters}
    assert not any("evaluator" in p for p in param_names), (
        f"validate_agent_visible must not have an evaluator_reference-shaped parameter, "
        f"found params: {sorted(sig.parameters)}"
    )
    assert len(sig.parameters) == 1, (
        "validate_agent_visible should take exactly one argument (the agent-visible payload)"
    )


# ---------------------------------------------------------------------------
# 6. Cross-fixture leakage check: gold values absent from agent-visible JSON
# ---------------------------------------------------------------------------


def _all_strings(obj):
    """Yield every string leaf value in a nested JSON structure."""
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _all_strings(v)
    elif isinstance(obj, list):
        for item in obj:
            yield from _all_strings(item)


@pytest.mark.parametrize("scenario", FIXTURE_SCENARIOS)
def test_gold_values_absent_from_agent_visible_fixture(scenario):
    evaluator_ref = load_json(FIXTURES_DIR / scenario / "evaluator_reference.json")
    agent_visible = load_json(FIXTURES_DIR / scenario / "agent_visible_context.json")

    agent_visible_strings = set(_all_strings(agent_visible))

    # gold_answer text must not appear verbatim in the agent-visible document
    assert evaluator_ref["gold_answer"] not in agent_visible_strings

    # gold_evidence_ids values must not appear anywhere in the agent-visible document
    for gold_id in evaluator_ref["gold_evidence_ids"]:
        assert gold_id not in agent_visible_strings, (
            f"gold_evidence_id {gold_id!r} leaked into {scenario}/agent_visible_context.json"
        )


@pytest.mark.parametrize("scenario", FIXTURE_SCENARIOS)
def test_agent_visible_fixture_has_no_forbidden_keys_via_boundary(scenario):
    payload = load_json(FIXTURES_DIR / scenario / "agent_visible_context.json")
    # Should not raise.
    boundary.validate_agent_visible(payload)


# ---------------------------------------------------------------------------
# 7. AgentExecutionResult / agent-path must not require EvaluatorReference
# ---------------------------------------------------------------------------


def test_agent_execution_result_schema_has_no_evaluator_reference_property():
    schema = load_schema("agent_execution_result")
    props = schema.get("properties", {})
    assert not any("evaluator" in p.lower() or "gold" in p.lower() for p in props), (
        f"AgentExecutionResult must not define any evaluator/gold field, found: {list(props)}"
    )


def test_agent_visible_context_schema_has_no_evaluator_only_properties():
    schema = load_schema("agent_visible_context")
    props = set(schema.get("properties", {}))
    forbidden = {
        "gold_answer",
        "gold_evidence_ids",
        "evaluation_labels",
        "evaluation_scores",
        "retrieval_ground_truth",
        "evaluator_reference",
        "attack_labels",
        "hidden_benchmark_metadata",
    }
    assert not (props & forbidden), f"forbidden keys present as schema properties: {props & forbidden}"
    assert schema.get("additionalProperties") is False


def test_no_god_object_schema_contains_both_planes():
    """No single schema in this contract set may define fields from both
    AgentVisibleContext and EvaluatorReference simultaneously."""
    agent_visible_props = set(load_schema("agent_visible_context").get("properties", {}))
    evaluator_props = set(load_schema("evaluator_reference").get("properties", {}))
    # Only allowed overlap is bookkeeping fields shared by convention (schema_version, run_id).
    allowed_overlap = {"schema_version", "run_id"}
    overlap = (agent_visible_props & evaluator_props) - allowed_overlap
    assert overlap == set(), f"unexpected field overlap between the two planes: {overlap}"

    # Distinctive (non-identity) fields that are unique to each plane -- used to check
    # other schemas (e.g. EvaluationRun) for accidental content mixing. Plain identity
    # fields like "condition" and "task_id" are legitimately referenced by EvaluationRun
    # (an index/pointer record) without that constituting "mixing planes": EvaluationRun
    # carries no gold CONTENT and no agent-visible CONTENT, only identifiers and *_ref
    # pointers to the separate documents that do.
    identity_fields = {"schema_version", "run_id", "task_id", "condition"}
    distinctive_agent_visible = agent_visible_props - identity_fields
    distinctive_evaluator = evaluator_props - identity_fields

    for name in SCHEMA_FILES:
        schema = load_schema(name)
        props = set(schema.get("properties", {}))
        has_agent_only = bool(props & distinctive_agent_visible)
        has_eval_only = bool(props & distinctive_evaluator)
        assert not (has_agent_only and has_eval_only), (
            f"schema {name} appears to mix agent-visible and evaluator-only content fields"
        )
