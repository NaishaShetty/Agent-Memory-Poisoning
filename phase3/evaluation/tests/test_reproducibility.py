"""Phase 3.2-F tests for `phase3/evaluation/security/reproducibility.py`.

Scope note: does not modify any existing test file; all prior 334 tests must remain
green, unmodified, alongside this file.
"""

from __future__ import annotations

import ast
import hashlib
import inspect

import pytest


def _non_docstring_source(module) -> str:
    """Return `module`'s source with every module/class/function DOCSTRING statement
    stripped out, so a substring search for a dangerous pattern (e.g. the builtin
    `hash(`, or a literal `data/raw` path) does not false-positive on this module's own
    prose EXPLAINING why that pattern must not be used elsewhere."""
    source = inspect.getsource(module)
    tree = ast.parse(source)
    doc_ranges = []

    def _collect(node):
        body = getattr(node, "body", None)
        if isinstance(body, list) and body and isinstance(body[0], ast.Expr) and isinstance(
            body[0].value, ast.Constant
        ):
            if isinstance(body[0].value.value, str):
                doc_ranges.append((body[0].lineno, body[0].end_lineno))
        for child in ast.iter_child_nodes(node):
            _collect(child)

    _collect(tree)
    excluded = set()
    for start, end in doc_ranges:
        excluded.update(range(start, end + 1))
    lines = source.splitlines()
    return "\n".join(line for i, line in enumerate(lines, start=1) if i not in excluded)

from phase3.evaluation.agent.conditions import CONDITION_RETRIEVED_MEMORY, build_agent_visible_context
from phase3.evaluation.agent.outcomes import (
    run_synthetic_agent,
    BEHAVIOR_CORRECT_IF_EVIDENCE_PRESENT,
)

from phase3.evaluation.security import reproducibility as repro_mod
from phase3.evaluation.security.reproducibility import (
    canonical_serialize,
    fingerprint,
    digest_bytes,
    safe_environment_metadata,
    build_manifest,
    validate_manifest_completeness,
    manifest_semantic_fingerprint,
    verify_artifact_integrity,
    verify_reproducibility,
    reconstruct_and_verify,
    STATUS_ARTIFACT_INTEGRITY_OK,
    STATUS_ARTIFACT_INTEGRITY_FAILURE,
    VERIFY_REPRODUCIBLE_MATCH,
    VERIFY_ARTIFACT_MISMATCH,
    VERIFY_CONFIGURATION_MISMATCH,
    VERIFY_INPUT_MISMATCH,
    VERIFY_INCOMPLETE_MANIFEST,
    VERIFY_UNDEFINED,
    REQUIRED_MANIFEST_FIELDS,
    MANIFEST_METADATA_ONLY_FIELDS,
    SEED_NOT_APPLICABLE,
)


def _base_manifest(**overrides):
    kwargs = dict(
        run_id="run-1",
        task_ids=["t1", "t2"],
        conditions=[CONDITION_RETRIEVED_MEMORY],
        input_fingerprint=fingerprint({"task_id": "t1"}),
        agent_visible_context_fingerprint=fingerprint({"memory_content": []}),
        evaluator_reference_fingerprint=fingerprint({"gold_answer": "x"}),
        configuration_fingerprint=fingerprint({"top_k": 10}),
        code_version="0.1.0",
        contract_version="3.2-b.1",
        metric_version="3.2-c.1",
        timestamp="2026-08-26T00:00:00Z",
        artifact_refs=[{"name": "memory_store.json", "digest": digest_bytes(b"hello world")}],
    )
    kwargs.update(overrides)
    return build_manifest(**kwargs)


# ---------------------------------------------------------------------------
# Canonical serialization: stable key ordering, lists NOT sorted
# ---------------------------------------------------------------------------


def test_canonical_serialize_sorts_dict_keys():
    a = canonical_serialize({"b": 1, "a": 2})
    b = canonical_serialize({"a": 2, "b": 1})
    assert a == b


def test_canonical_serialize_does_not_sort_lists():
    forward = canonical_serialize({"retrieved_ranked_ids": ["mem-A", "mem-B", "mem-C"]})
    reversed_ = canonical_serialize({"retrieved_ranked_ids": ["mem-C", "mem-B", "mem-A"]})
    assert forward != reversed_


def test_canonical_serialize_sorts_sets_since_they_are_genuinely_unordered():
    a = canonical_serialize({"x": {"mem-B", "mem-A"}})
    b = canonical_serialize({"x": {"mem-A", "mem-B"}})
    assert a == b


def test_canonical_serialize_normalizes_tuples_as_lists_preserving_order():
    a = canonical_serialize({"x": ("mem-A", "mem-B")})
    b = canonical_serialize({"x": ["mem-A", "mem-B"]})
    assert a == b


def test_canonical_serialize_raises_type_error_for_non_serializable_object():
    class _Weird:
        pass

    with pytest.raises(TypeError):
        canonical_serialize({"x": _Weird()})


# ---------------------------------------------------------------------------
# Fingerprinting: SHA-256, never hash()
# ---------------------------------------------------------------------------


def test_fingerprint_is_sha256_hex_digest():
    fp = fingerprint({"a": 1})
    assert len(fp) == 64
    assert all(c in "0123456789abcdef" for c in fp)
    expected = hashlib.sha256(canonical_serialize({"a": 1}).encode("utf-8")).hexdigest()
    assert fp == expected


def test_module_never_uses_builtin_hash_for_fingerprinting():
    source = _non_docstring_source(repro_mod)
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        # `hash(` (the builtin) must never appear; hashlib.* calls are fine and expected.
        assert "hash(" not in stripped or "hashlib" in stripped


# ---------------------------------------------------------------------------
# Invariant: identical canonical inputs -> identical fingerprints
# ---------------------------------------------------------------------------


def test_invariant_identical_inputs_produce_identical_fingerprints():
    payload = {"task_id": "t1", "condition": CONDITION_RETRIEVED_MEMORY, "memory_content": ["m1", "m2"]}
    assert fingerprint(payload) == fingerprint(dict(payload))


def test_invariant_semantically_relevant_change_changes_fingerprint():
    a = {"task_id": "t1", "answer": "Paris"}
    b = {"task_id": "t1", "answer": "Lyon"}
    assert fingerprint(a) != fingerprint(b)


def test_invariant_dict_key_insertion_order_does_not_change_fingerprint():
    a = {"x": 1, "y": 2}
    b = {"y": 2, "x": 1}
    assert fingerprint(a) == fingerprint(b)


# ---------------------------------------------------------------------------
# Environment metadata: safe subset only
# ---------------------------------------------------------------------------


def test_safe_environment_metadata_has_only_expected_keys():
    meta = safe_environment_metadata()
    assert set(meta.keys()) == {"python_version", "platform"}


def test_safe_environment_metadata_never_includes_env_vars_or_secrets():
    source = inspect.getsource(repro_mod)
    for forbidden_token in ("os.environ", "getenv", "API_KEY", "SECRET", "TOKEN", "PASSWORD"):
        assert forbidden_token not in source


# ---------------------------------------------------------------------------
# Reproducibility manifest structure
# ---------------------------------------------------------------------------


def test_build_manifest_has_all_required_fields():
    manifest = _base_manifest()
    is_complete, missing = validate_manifest_completeness(manifest)
    assert is_complete
    assert missing == []
    assert REQUIRED_MANIFEST_FIELDS <= set(manifest.keys())


def test_build_manifest_defaults_seed_to_not_applicable_when_no_randomness():
    manifest = _base_manifest()
    assert manifest["seed"] == SEED_NOT_APPLICABLE


def test_build_manifest_seed_can_be_explicit():
    manifest = _base_manifest(seed="42")
    assert manifest["seed"] == "42"


# ---------------------------------------------------------------------------
# Scenario 11: manifest missing required field -> INCOMPLETE_MANIFEST
# ---------------------------------------------------------------------------


def test_scenario_manifest_missing_required_field_is_incomplete():
    manifest = _base_manifest()
    del manifest["seed"]
    is_complete, missing = validate_manifest_completeness(manifest)
    assert not is_complete
    assert missing == ["seed"]

    result = verify_reproducibility(manifest, current_artifacts={})
    assert result.status == VERIFY_INCOMPLETE_MANIFEST
    assert "seed" in result.detail["missing_fields"]


# ---------------------------------------------------------------------------
# Timestamp is metadata-only: must NOT affect the semantic fingerprint
# ---------------------------------------------------------------------------


def test_invariant_timestamp_does_not_alter_semantic_fingerprint():
    manifest_1 = _base_manifest(timestamp="2026-08-26T00:00:00Z")
    manifest_2 = _base_manifest(timestamp="2030-01-01T12:34:56Z")
    assert manifest_1 != manifest_2  # the raw dicts differ
    assert manifest_semantic_fingerprint(manifest_1) == manifest_semantic_fingerprint(manifest_2)


def test_timestamp_is_declared_metadata_only():
    assert "timestamp" in MANIFEST_METADATA_ONLY_FIELDS


# ---------------------------------------------------------------------------
# Artifact integrity
# ---------------------------------------------------------------------------


def test_artifact_integrity_ok_when_unmodified():
    data = b"memory store contents"
    digest = digest_bytes(data)
    result = verify_artifact_integrity("store.json", digest, data)
    assert result.status == STATUS_ARTIFACT_INTEGRITY_OK


def test_invariant_changed_artifact_changes_digest():
    original = b"memory store contents"
    modified = b"memory store CONTENTS (tampered)"
    assert digest_bytes(original) != digest_bytes(modified)


# ---------------------------------------------------------------------------
# Scenario 8: artifact modified after manifest creation -> ARTIFACT_MISMATCH
# ---------------------------------------------------------------------------


def test_scenario_artifact_modified_after_manifest_creation_is_mismatch():
    original_data = b"hello world"
    manifest = _base_manifest(
        artifact_refs=[{"name": "memory_store.json", "digest": digest_bytes(original_data)}]
    )
    tampered_data = b"hello world -- tampered"
    result = verify_reproducibility(
        manifest, current_artifacts={"memory_store.json": tampered_data}
    )
    assert result.status == VERIFY_ARTIFACT_MISMATCH
    assert result.detail["mismatched_artifact"] == "memory_store.json"


def test_scenario_artifact_unmodified_after_manifest_creation_is_no_mismatch():
    original_data = b"hello world"
    manifest = _base_manifest(
        artifact_refs=[{"name": "memory_store.json", "digest": digest_bytes(original_data)}]
    )
    result = verify_reproducibility(
        manifest,
        current_artifacts={"memory_store.json": original_data},
        current_input_fingerprint=manifest["input_fingerprint"],
        current_configuration_fingerprint=manifest["configuration_fingerprint"],
    )
    assert result.status == VERIFY_REPRODUCIBLE_MATCH


# ---------------------------------------------------------------------------
# Scenario 9: configuration modified -> CONFIGURATION_MISMATCH
# ---------------------------------------------------------------------------


def test_scenario_configuration_modified_is_mismatch():
    manifest = _base_manifest()
    result = verify_reproducibility(
        manifest,
        current_artifacts={},
        current_configuration_fingerprint=fingerprint({"top_k": 999}),
    )
    assert result.status == VERIFY_CONFIGURATION_MISMATCH


def test_invariant_changed_config_parameter_changes_config_fingerprint():
    a = fingerprint({"top_k": 10})
    b = fingerprint({"top_k": 20})
    assert a != b


# ---------------------------------------------------------------------------
# Scenario 10: input modified -> INPUT_MISMATCH
# ---------------------------------------------------------------------------


def test_scenario_input_modified_is_mismatch():
    manifest = _base_manifest()
    result = verify_reproducibility(
        manifest,
        current_artifacts={},
        current_configuration_fingerprint=manifest["configuration_fingerprint"],
        current_input_fingerprint=fingerprint({"task_id": "DIFFERENT"}),
    )
    assert result.status == VERIFY_INPUT_MISMATCH


# ---------------------------------------------------------------------------
# Precedence: INCOMPLETE_MANIFEST beats everything else
# ---------------------------------------------------------------------------


def test_incomplete_manifest_takes_precedence_over_other_mismatches():
    manifest = _base_manifest()
    del manifest["configuration_fingerprint"]
    result = verify_reproducibility(
        manifest,
        current_artifacts={"memory_store.json": b"tampered"},
        current_configuration_fingerprint="anything",
    )
    assert result.status == VERIFY_INCOMPLETE_MANIFEST


# ---------------------------------------------------------------------------
# Scenario 13 / reconstruction: reconstructed evaluation from manifest/artifacts ->
# same deterministic result/fingerprint
# ---------------------------------------------------------------------------


def test_scenario_synthetic_run_reconstruction_matches():
    ctx = build_agent_visible_context(
        condition=CONDITION_RETRIEVED_MEMORY,
        task_id="t-recon",
        prompt="What is Bob's job?",
        memory_items=[{"memory_id": "mem-1", "content": "Bob is an engineer."}],
    )

    def run_fn():
        return run_synthetic_agent(
            task_id="t-recon",
            condition=CONDITION_RETRIEVED_MEMORY,
            behavior=BEHAVIOR_CORRECT_IF_EVIDENCE_PRESENT,
            agent_visible_context=ctx,
            expected_answer="engineer",
            selected_memory_ids=["mem-1"],
        )

    original_result = run_fn()
    manifest = _base_manifest(result_fingerprint=fingerprint(original_result))

    verification = reconstruct_and_verify(manifest, run_fn)
    assert verification.status == VERIFY_REPRODUCIBLE_MATCH
    assert verification.detail["matches"] is True


def test_reconstruction_detects_mismatch_when_rerun_differs():
    manifest = _base_manifest(result_fingerprint=fingerprint({"answer": "Paris"}))

    def run_fn():
        return {"answer": "Lyon"}

    verification = reconstruct_and_verify(manifest, run_fn)
    assert verification.status == VERIFY_INPUT_MISMATCH


def test_reconstruction_undefined_when_manifest_has_no_result_fingerprint():
    manifest = _base_manifest()
    verification = reconstruct_and_verify(manifest, lambda: {"x": 1})
    assert verification.status == VERIFY_UNDEFINED


# ---------------------------------------------------------------------------
# Manifest is structurally distinct from AgentVisibleContext (cross-checked also in
# test_leakage.py::test_reproducibility_manifest_as_agent_visible_context_is_leakage_detected)
# ---------------------------------------------------------------------------


def test_manifest_field_names_are_disjoint_from_agent_visible_context_shape():
    from phase3.evaluation.agent.conditions import build_agent_visible_context, CONDITION_NO_MEMORY

    ctx = build_agent_visible_context(condition=CONDITION_NO_MEMORY, task_id="t", prompt="p")
    manifest = _base_manifest()
    # AgentVisibleContext never carries any manifest-only fingerprint field.
    for manifest_only_field in (
        "evaluator_reference_fingerprint",
        "configuration_fingerprint",
        "code_version",
        "contract_version",
        "metric_version",
    ):
        assert manifest_only_field not in ctx
        assert manifest_only_field in manifest


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


def test_reproducibility_module_never_imports_forbidden_libraries():
    source = inspect.getsource(repro_mod)
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith(("import ", "from ")):
            for forbidden in _FORBIDDEN_IMPORTS:
                assert forbidden not in stripped.lower()


def test_reproducibility_module_never_reads_real_dataset_paths():
    source = _non_docstring_source(repro_mod)
    for forbidden_token in ("data/raw", "data/processed", "data/metadata", "data/reports"):
        assert forbidden_token not in source


def test_reproducibility_module_artifact_helpers_take_bytes_not_paths_by_default():
    """digest_bytes/verify_artifact_integrity operate on caller-supplied bytes -- they do
    not themselves open/discover files, per the module's own docstring guarantee."""
    sig = inspect.signature(digest_bytes)
    assert list(sig.parameters) == ["data"]
    sig2 = inspect.signature(verify_artifact_integrity)
    assert "current_data" in sig2.parameters
