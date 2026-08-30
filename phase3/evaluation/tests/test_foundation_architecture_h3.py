"""Phase 3.2-H.3 (second stage) tests for `phase3/evaluation/foundations/` -- the Memory
Foundation Integration Architecture.

Scope: this suite tests the NEW, purely-additive foundation-architecture package only. It
does not modify, re-run, or depend on any prior test file's internals -- all prior files
(705 tests, per this stage's baseline run) must remain green, unmodified, alongside this
file. Every test asserts an EXACT expectation (status string, field value, ordering,
membership) -- never a bare "doesn't crash."
"""

from __future__ import annotations

import inspect
import pathlib
import re

import pytest

from phase3.evaluation.agent.conditions import (
    CONDITION_NO_MEMORY,
    CONDITION_SELECTED_MEMORY_AVAILABLE,
    build_agent_visible_context,
)
from phase3.evaluation.agent.outcomes import (
    AgentExecutionResult,
    EXECUTION_STATUS_SUCCESS,
)
from phase3.evaluation.foundations import (
    adapter as adapter_mod,
    capability_audit,
    fingerprinting,
    lifecycle,
    matrix,
    model_dependency,
    registry,
    reset_isolation,
    security as foundations_security,
    trace as trace_mod,
)
from phase3.evaluation.foundations.mocks.mock_amem import MockAMemAdapter
from phase3.evaluation.foundations.mocks.mock_graphiti import MockGraphitiAdapter
from phase3.evaluation.foundations.mocks.mock_letta import MockLettaAdapter
from phase3.evaluation.foundations.mocks.mock_mem0 import MockMem0Adapter
from phase3.evaluation.security.leakage import STATUS_LEAKAGE_DETECTED, STATUS_NO_LEAKAGE
from phase3.evaluation.security.reproducibility import fingerprint

ALL_MOCK_CLASSES = (MockMem0Adapter, MockLettaAdapter, MockGraphitiAdapter, MockAMemAdapter)
ALL_MOCK_FOUNDATION_IDS = (
    capability_audit.FOUNDATION_MEM0,
    capability_audit.FOUNDATION_LETTA,
    capability_audit.FOUNDATION_GRAPHITI,
    capability_audit.FOUNDATION_AMEM,
)


def _new_adapters():
    return [cls() for cls in ALL_MOCK_CLASSES]


# ---------------------------------------------------------------------------
# 1. MemoryFoundationAdapter interface contract
# ---------------------------------------------------------------------------

REQUIRED_METHODS = (
    "foundation_identity",
    "capabilities",
    "initialize",
    "reset",
    "add_memory",
    "retrieve",
    "update_memory",
    "delete_memory",
    "inspect_memory",
    "export_state",
    "normalize_trace",
    "shutdown",
)


class TestAdapterInterfaceContract:
    def test_all_required_methods_are_abstract_on_base(self):
        abstract_names = adapter_mod.MemoryFoundationAdapter.__abstractmethods__
        for name in REQUIRED_METHODS:
            assert name in abstract_names

    @pytest.mark.parametrize("cls", ALL_MOCK_CLASSES)
    def test_mock_implements_every_required_method(self, cls):
        instance = cls()
        for name in REQUIRED_METHODS:
            assert hasattr(instance, name)
            assert callable(getattr(instance, name))

    @pytest.mark.parametrize("cls", ALL_MOCK_CLASSES)
    def test_foundation_identity_status_is_prepared_candidate(self, cls):
        identity = cls().foundation_identity()
        assert identity.status == registry.PREPARED_CANDIDATE

    def test_cannot_instantiate_base_class_directly(self):
        with pytest.raises(TypeError):
            adapter_mod.MemoryFoundationAdapter()


# ---------------------------------------------------------------------------
# 2. Capability reporting matches the audit
# ---------------------------------------------------------------------------


class TestCapabilityAuditGrounding:
    @pytest.mark.parametrize("foundation_id", capability_audit.ALL_FOUNDATIONS)
    def test_every_dimension_present_and_valid(self, foundation_id):
        audit = capability_audit.ALL_AUDITS[foundation_id]
        assert set(audit.rows.keys()) == set(capability_audit.CAPABILITY_DIMENSIONS)
        for row in audit.rows.values():
            assert row.status in capability_audit.AUDIT_STATES
            assert row.reason
            assert row.source

    def test_mem0_graph_is_not_supported_per_oss_removal(self):
        row = capability_audit.MEM0_AUDIT.rows["graph"]
        assert row.status == capability_audit.AUDIT_NOT_SUPPORTED

    def test_graphiti_graph_is_supported(self):
        row = capability_audit.GRAPHITI_AUDIT.rows["graph"]
        assert row.status == capability_audit.AUDIT_SUPPORTED

    def test_amem_linking_is_supported(self):
        row = capability_audit.AMEM_AUDIT.rows["linking"]
        assert row.status == capability_audit.AUDIT_SUPPORTED

    def test_amem_update_is_supported_distinctively(self):
        row = capability_audit.AMEM_AUDIT.rows["update"]
        assert row.status == capability_audit.AUDIT_SUPPORTED

    def test_letta_has_no_fabricated_supported_rows_for_unfetched_detail(self):
        # Letta's docs.letta.com/concepts/memory fetch 404'd -- rows this stage could not
        # confirm must be UNKNOWN or PARTIAL, never SUPPORTED.
        for dim in ("retrieval", "update", "deletion", "linking", "memory_identifiers"):
            row = capability_audit.LETTA_AUDIT.rows[dim]
            assert row.status != capability_audit.AUDIT_SUPPORTED

    @pytest.mark.parametrize("cls,foundation_id", list(zip(ALL_MOCK_CLASSES, ALL_MOCK_FOUNDATION_IDS)))
    def test_mock_capabilities_method_returns_the_real_audit(self, cls, foundation_id):
        instance = cls()
        assert instance.capabilities() is capability_audit.ALL_AUDITS[foundation_id]


# ---------------------------------------------------------------------------
# 3. Unsupported operations report the correct status, never silently 0/False/[]/None
# ---------------------------------------------------------------------------


class TestUnsupportedOperationsNeverFabricate:
    @pytest.mark.parametrize("cls", (MockLettaAdapter, MockGraphitiAdapter, MockAMemAdapter))
    def test_delete_memory_is_not_supported_by_architecture(self, cls):
        instance = cls()
        result = instance.delete_memory("nonexistent")
        assert result.availability == adapter_mod.FOUNDATION_NOT_SUPPORTED_BY_ARCHITECTURE
        assert result.value is None
        assert result.note != ""

    def test_mem0_delete_of_nonexistent_id_is_available_not_unsupported(self):
        # Mem0's documented CRUD delete: an empty confirmation is a genuine AVAILABLE
        # no-op result -- distinguishing this from NOT_SUPPORTED_BY_ARCHITECTURE is the
        # exact discipline the task brief requires.
        instance = MockMem0Adapter()
        result = instance.delete_memory("nonexistent")
        assert result.availability == adapter_mod.FOUNDATION_AVAILABLE
        assert result.value == {"memory_id": "nonexistent", "existed": False}

    def test_update_of_nonexistent_id_is_available_genuine_noop_not_unsupported(self):
        for instance in _new_adapters():
            if isinstance(instance, MockGraphitiAdapter):
                content = {}
            else:
                content = {"text": "irrelevant"}
            result = instance.update_memory("nonexistent-id", content)
            assert result.availability == adapter_mod.FOUNDATION_AVAILABLE
            assert result.value["updated"] is False

    def test_inspect_of_nonexistent_id_is_not_supported_never_empty_dict(self):
        for instance in _new_adapters():
            result = instance.inspect_memory("nonexistent-id")
            assert result.availability == adapter_mod.FOUNDATION_NOT_SUPPORTED_BY_ARCHITECTURE
            assert result.value is None
            # Never silently {} standing in for "not found."
            assert result.value != {}


# ---------------------------------------------------------------------------
# 4. Native memory-ID preservation through a mock round-trip
# ---------------------------------------------------------------------------


class TestMemoryIdPreservation:
    def test_mem0_preserves_caller_supplied_id(self):
        instance = MockMem0Adapter()
        result = instance.add_memory("caller-id-123", {"text": "hello"})
        assert result.value["memory_id"] == "caller-id-123"
        inspected = instance.inspect_memory("caller-id-123")
        assert inspected.value["memory_id"] == "caller-id-123"

    def test_amem_preserves_caller_supplied_id_through_linking(self):
        instance = MockAMemAdapter()
        instance.add_memory("note-a", {"text": "x"}, {"tags": ["shared"]})
        instance.add_memory("note-b", {"text": "y"}, {"tags": ["shared"]})
        inspected = instance.inspect_memory("note-a")
        assert inspected.value["memory_id"] == "note-a"
        assert "note-b" in inspected.value["linked_memory_ids"]

    def test_graphiti_preserves_episode_id(self):
        instance = MockGraphitiAdapter()
        instance.add_memory("ep-x", {"entities": [{"name": "A"}], "relationships": []})
        inspected = instance.inspect_memory("ep-x")
        assert inspected.value["memory_id"] == "ep-x"


# ---------------------------------------------------------------------------
# 5. Lifecycle trace: correct ordered sequence + MEMORY_CAUSED never appears
# ---------------------------------------------------------------------------


class TestLifecycleTrace:
    def test_full_sequence_reached_when_everything_lines_up(self):
        payload = build_agent_visible_context(
            condition=CONDITION_SELECTED_MEMORY_AVAILABLE,
            task_id="t1",
            prompt="What did I say?",
            memory_items=[{"memory_id": "m1", "content": {"text": "prior fact"}}],
        )
        usage = AgentExecutionResult(
            task_id="t1",
            condition=CONDITION_SELECTED_MEMORY_AVAILABLE,
            answer="prior fact",
            execution_status=EXECUTION_STATUS_SUCCESS,
            selected_memory_ids=("m1",),
            used_memory_ids=("m1",),
        )
        usage_result = lifecycle.classify_memory_usage(usage)
        assert usage_result.status == "SELECTED_AND_USED"

        no_mem = AgentExecutionResult(
            task_id="t1",
            condition=CONDITION_NO_MEMORY,
            answer="wrong",
            execution_status=EXECUTION_STATUS_SUCCESS,
            selected_memory_ids=(),
            used_memory_ids=(),
        )
        with_mem = AgentExecutionResult(
            task_id="t1",
            condition=CONDITION_SELECTED_MEMORY_AVAILABLE,
            answer="prior fact",
            execution_status=EXECUTION_STATUS_SUCCESS,
            selected_memory_ids=("m1",),
            used_memory_ids=("m1",),
        )
        contribution_result = lifecycle.classify_memory_foundation_contribution(
            no_mem, with_mem, "prior fact", "prior fact"
        )
        assert contribution_result.status == "POSITIVE_MEMORY_CONTRIBUTION"

        trace = lifecycle.build_lifecycle_trace(
            memory_id="m1",
            store_memory_ids={"m1", "m2"},
            retrieved_memory_ids=["m2", "m1"],
            selected_memory_ids=["m1"],
            agent_visible_payload=payload,
            usage_result=usage_result,
            contribution_result=contribution_result,
        )
        assert trace.stages_reached == (
            lifecycle.MEMORY_AVAILABLE,
            lifecycle.MEMORY_RETRIEVED,
            lifecycle.MEMORY_SELECTED,
            lifecycle.MEMORY_EXPOSED,
            lifecycle.MEMORY_USED,
            lifecycle.MEMORY_CONTRIBUTED,
        )

    def test_stops_at_first_stage_not_reached(self):
        trace = lifecycle.build_lifecycle_trace(
            memory_id="m1",
            store_memory_ids={"m1"},
            retrieved_memory_ids=[],  # never retrieved
        )
        assert trace.stages_reached == (lifecycle.MEMORY_AVAILABLE,)

    def test_not_available_yields_empty_stages(self):
        trace = lifecycle.build_lifecycle_trace(
            memory_id="ghost",
            store_memory_ids={"m1"},
        )
        assert trace.stages_reached == ()

    def test_memory_caused_never_appears_in_lifecycle_stages_constant(self):
        assert lifecycle.MEMORY_CAUSED not in lifecycle.LIFECYCLE_STAGES

    def test_memory_caused_never_returned_by_build_lifecycle_trace(self):
        # Exhaustive scripted scenario -- even at full success, MEMORY_CAUSED cannot appear.
        payload = build_agent_visible_context(
            condition=CONDITION_SELECTED_MEMORY_AVAILABLE,
            task_id="t2",
            prompt="p",
            memory_items=[{"memory_id": "m9", "content": {"text": "x"}}],
        )
        usage = AgentExecutionResult(
            task_id="t2", condition=CONDITION_SELECTED_MEMORY_AVAILABLE, answer="x",
            execution_status=EXECUTION_STATUS_SUCCESS, selected_memory_ids=("m9",), used_memory_ids=("m9",),
        )
        usage_result = lifecycle.classify_memory_usage(usage)
        no_mem = AgentExecutionResult(
            task_id="t2", condition=CONDITION_NO_MEMORY, answer="wrong",
            execution_status=EXECUTION_STATUS_SUCCESS, selected_memory_ids=(), used_memory_ids=(),
        )
        contribution_result = lifecycle.classify_memory_foundation_contribution(no_mem, usage, "x", "x")
        trace = lifecycle.build_lifecycle_trace(
            memory_id="m9", store_memory_ids={"m9"}, retrieved_memory_ids=["m9"],
            selected_memory_ids=["m9"], agent_visible_payload=payload,
            usage_result=usage_result, contribution_result=contribution_result,
        )
        assert lifecycle.MEMORY_CAUSED not in trace.stages_reached


# ---------------------------------------------------------------------------
# 6. Retrieval ordering preserved (not sorted)
# ---------------------------------------------------------------------------


class TestRetrievalOrderingPreserved:
    def test_mem0_retrieve_preserves_score_desc_then_insertion_order(self):
        instance = MockMem0Adapter()
        instance.add_memory("a", {"text": "banana split"})
        instance.add_memory("b", {"text": "apple pie"})
        instance.add_memory("c", {"text": "apple banana smoothie"})
        result = instance.retrieve({"text": "apple"})
        ids = [item["memory_id"] for item in result.value]
        # "b" and "c" score 1.0 (insertion order preserved among ties); "a" scores 0.0
        # (no filtering -- all candidates are returned, ranked) and sorts last.
        assert ids == ["b", "c", "a"]

    def test_classify_memory_retrieval_preserves_caller_order(self):
        result = lifecycle.classify_memory_retrieval("x", ["z", "y", "x"])
        assert result.detail["retrieved_memory_ids"] == ["z", "y", "x"]
        assert result.detail["rank"] == 2

    def test_classify_memory_retrieval_never_reorders_to_check_membership(self):
        reversed_order = list(reversed(["m1", "m2", "m3"]))
        result = lifecycle.classify_memory_retrieval("m2", reversed_order)
        assert result.detail["retrieved_memory_ids"] == reversed_order


# ---------------------------------------------------------------------------
# 7. State snapshot structure and fingerprint determinism
# ---------------------------------------------------------------------------


class TestStateFingerprinting:
    @pytest.mark.parametrize("cls", ALL_MOCK_CLASSES)
    def test_identical_states_produce_identical_fingerprints(self, cls):
        a = cls()
        b = cls()
        if cls is MockGraphitiAdapter:
            a.add_memory("e1", {"entities": [{"name": "X"}], "relationships": []})
            b.add_memory("e1", {"entities": [{"name": "X"}], "relationships": []})
        elif cls is MockAMemAdapter:
            a.add_memory("n1", {"text": "hi"}, {"tags": ["t"]})
            b.add_memory("n1", {"text": "hi"}, {"tags": ["t"]})
        else:
            a.add_memory("m1", {"text": "hi"})
            b.add_memory("m1", {"text": "hi"})
        state_a = a.export_state().value
        state_b = b.export_state().value
        assert fingerprinting.fingerprint_state(state_a) == fingerprinting.fingerprint_state(state_b)

    def test_different_states_produce_different_fingerprints(self):
        a = MockMem0Adapter()
        b = MockMem0Adapter()
        a.add_memory("m1", {"text": "hello"})
        b.add_memory("m1", {"text": "goodbye"})
        assert fingerprinting.fingerprint_state(a.export_state().value) != fingerprinting.fingerprint_state(
            b.export_state().value
        )

    def test_fingerprint_state_is_repeatable(self):
        a = MockMem0Adapter()
        a.add_memory("m1", {"text": "hello"})
        snapshot = a.export_state().value
        assert fingerprinting.fingerprint_state(snapshot) == fingerprinting.fingerprint_state(snapshot)


# ---------------------------------------------------------------------------
# 8. Reset/isolation check (A->B->A) against mocks
# ---------------------------------------------------------------------------


class TestResetIsolation:
    def test_mem0_mock_reset_isolates_state(self):
        instance = MockMem0Adapter()

        def run_a():
            instance.reset()
            instance.add_memory("shared-id", {"text": "A's content"})
            return fingerprinting.fingerprint_state(instance.export_state().value)

        def run_b():
            instance.reset()
            instance.add_memory("shared-id", {"text": "B's DIFFERENT content"})
            return fingerprinting.fingerprint_state(instance.export_state().value)

        result = reset_isolation.check_foundation_reset_isolation(run_a, run_b)
        assert result.status == reset_isolation.STATUS_ISOLATED

    def test_contamination_is_detected_when_reset_is_skipped(self):
        instance = MockAMemAdapter()

        def run_a():
            instance.add_memory("m1", {"text": "seed"}, {"tags": ["t"]})
            return fingerprinting.fingerprint_state(instance.export_state().value)

        def run_b():
            # Deliberately never resets -- contaminates shared state.
            instance.add_memory("m2", {"text": "intruder"}, {"tags": ["t"]})
            return fingerprinting.fingerprint_state(instance.export_state().value)

        result = reset_isolation.check_foundation_reset_isolation(run_a, run_b)
        assert result.status == reset_isolation.STATUS_CONTAMINATED

    @pytest.mark.parametrize("foundation_id", capability_audit.ALL_FOUNDATIONS)
    def test_real_foundation_status_is_honestly_reproducibility_limitation(self, foundation_id):
        result = reset_isolation.foundation_reset_isolation_status(foundation_id)
        assert result.status == reset_isolation.STATUS_REPRODUCIBILITY_LIMITATION


# ---------------------------------------------------------------------------
# 9. Configuration fingerprint determinism and secret-exclusion
# ---------------------------------------------------------------------------


class TestConfigurationFingerprinting:
    def test_identical_configs_fingerprint_identically(self):
        cfg1 = fingerprinting.build_foundation_configuration(
            foundation_id="MEM0", foundation_version="1.0", adapter_version="mock-mem0-0.1.0",
            configuration_parameters={"top_k": 5}, storage_backend="in_memory_mock",
            retrieval_parameters={"strategy": "substring"}, embedding_configuration_id="none",
            llm_configuration_id="none", normalization_version="v1",
        )
        cfg2 = fingerprinting.build_foundation_configuration(
            foundation_id="MEM0", foundation_version="1.0", adapter_version="mock-mem0-0.1.0",
            configuration_parameters={"top_k": 5}, storage_backend="in_memory_mock",
            retrieval_parameters={"strategy": "substring"}, embedding_configuration_id="none",
            llm_configuration_id="none", normalization_version="v1",
        )
        assert fingerprinting.fingerprint_configuration(cfg1) == fingerprinting.fingerprint_configuration(cfg2)

    def test_different_configs_fingerprint_differently(self):
        base_kwargs = dict(
            foundation_id="MEM0", foundation_version="1.0", adapter_version="mock-mem0-0.1.0",
            storage_backend="in_memory_mock", retrieval_parameters={}, embedding_configuration_id="none",
            llm_configuration_id="none", normalization_version="v1",
        )
        cfg1 = fingerprinting.build_foundation_configuration(configuration_parameters={"top_k": 5}, **base_kwargs)
        cfg2 = fingerprinting.build_foundation_configuration(configuration_parameters={"top_k": 6}, **base_kwargs)
        assert fingerprinting.fingerprint_configuration(cfg1) != fingerprinting.fingerprint_configuration(cfg2)

    def test_secret_shaped_field_is_rejected_in_configuration_parameters(self):
        with pytest.raises(fingerprinting.ConfigurationSecretError):
            fingerprinting.build_foundation_configuration(
                foundation_id="MEM0", foundation_version="1.0", adapter_version="v1",
                configuration_parameters={"openai_api_key": "sk-super-secret"},
                storage_backend="in_memory_mock", retrieval_parameters={},
                embedding_configuration_id="none", llm_configuration_id="none", normalization_version="v1",
            )

    def test_secret_shaped_field_is_rejected_by_reject_secrets_directly(self):
        with pytest.raises(fingerprinting.ConfigurationSecretError):
            fingerprinting.reject_secrets({"nested": {"auth_token": "abc123"}})

    def test_clean_payload_passes_reject_secrets(self):
        clean = {"top_k": 5, "storage_backend": "in_memory_mock"}
        assert fingerprinting.reject_secrets(clean) == clean


# ---------------------------------------------------------------------------
# 10. Foundation fingerprint determinism / canonical serialization repeatability
# ---------------------------------------------------------------------------


class TestFingerprintDeterminismGeneral:
    def test_canonical_serialize_repeatable(self):
        obj = {"b": 2, "a": [1, 2, 3]}
        assert fingerprinting.canonical_serialize(obj) == fingerprinting.canonical_serialize(obj)

    def test_fingerprint_reused_verbatim_matches_security_reproducibility(self):
        obj = {"x": 1}
        assert fingerprinting.fingerprint_state(obj) == fingerprint(obj)


# ---------------------------------------------------------------------------
# 11. Model-dependency reporting matches the audit
# ---------------------------------------------------------------------------


class TestModelDependencyBoundary:
    def test_mem0_llm_required(self):
        decl = model_dependency.declaration_for(capability_audit.FOUNDATION_MEM0)
        assert decl.llm == model_dependency.MODEL_REQUIRED
        assert decl.embedding == model_dependency.EMBEDDING_REQUIRED

    def test_graphiti_external_service_required(self):
        decl = model_dependency.declaration_for(capability_audit.FOUNDATION_GRAPHITI)
        assert decl.external_service == model_dependency.EXTERNAL_SERVICE_REQUIRED

    @pytest.mark.parametrize("foundation_id", capability_audit.ALL_FOUNDATIONS)
    def test_declaration_values_are_from_the_vocabulary(self, foundation_id):
        decl = model_dependency.declaration_for(foundation_id)
        assert decl.llm in ("MODEL_REQUIRED", "MODEL_NOT_REQUIRED", "UNKNOWN")
        assert decl.embedding in ("EMBEDDING_REQUIRED", "EMBEDDING_NOT_REQUIRED", "UNKNOWN")
        assert decl.external_service in (
            "EXTERNAL_SERVICE_REQUIRED", "EXTERNAL_SERVICE_NOT_REQUIRED", "UNKNOWN",
        )
        assert decl.local_model in ("LOCAL_MODEL_SUPPORTED", "LOCAL_MODEL_NOT_SUPPORTED", "UNKNOWN")


# ---------------------------------------------------------------------------
# 12. MOCK_CONFORMANCE vs REAL_FOUNDATION_CONFORMANCE is never conflated
# ---------------------------------------------------------------------------


class TestMockVsRealConformance:
    @pytest.mark.parametrize("cls", ALL_MOCK_CLASSES)
    def test_all_traces_are_tagged_mock_conformance(self, cls):
        instance = cls()
        if cls is MockGraphitiAdapter:
            result = instance.add_memory("m1", {"entities": [], "relationships": []})
        elif cls is MockAMemAdapter:
            result = instance.add_memory("m1", {"text": "x"}, {"tags": []})
        else:
            result = instance.add_memory("m1", {"text": "x"})
        trace = instance.normalize_trace(result)
        assert trace["conformance_tag"] == "MOCK_CONFORMANCE"

    def test_trace_artifact_rejects_any_other_conformance_tag(self):
        with pytest.raises(ValueError):
            trace_mod.build_trace(
                foundation_id="MEM0", adapter_version="v1", operation=trace_mod.OPERATION_ADD_MEMORY,
                timestamp="T1", conformance_tag="REAL_FOUNDATION_CONFORMANCE",
            )

    def test_no_function_in_foundations_package_can_return_real_conformance(self):
        # Grep the entire foundations package source for the literal string; it must only
        # ever appear inside prose (docstrings/comments/error messages) explaining that it
        # is NOT achievable -- never as a returned/assigned value in executable code that
        # could produce it as an artifact's conformance_tag.
        package_dir = pathlib.Path(__file__).resolve().parents[1] / "foundations"
        offending = []
        for pyfile in package_dir.rglob("*.py"):
            text = pyfile.read_text(encoding="utf-8")
            for lineno, line in enumerate(text.splitlines(), start=1):
                if "REAL_FOUNDATION_CONFORMANCE" not in line:
                    continue
                stripped = line.strip()
                # Permitted: docstring/comment lines, or a ValueError message string
                # explaining the rejection (as in FoundationTraceArtifact.__post_init__
                # and this very test file). Never permitted: `= "REAL_FOUNDATION_CONFORMANCE"`
                # as a live assignment/return outside of a raise/string-literal context.
                if re.search(r"conformance_tag\s*=\s*[\"']REAL_FOUNDATION_CONFORMANCE[\"']\s*$", stripped):
                    offending.append(f"{pyfile}:{lineno}")
        assert offending == [], f"Found live REAL_FOUNDATION_CONFORMANCE assignment(s): {offending}"

    @pytest.mark.parametrize("foundation_id", capability_audit.ALL_FOUNDATIONS)
    def test_registry_never_claims_active_status(self, foundation_id):
        assert registry.status_of(foundation_id) == registry.PREPARED_CANDIDATE
        assert registry.status_of(foundation_id) != "ACTIVE"


# ---------------------------------------------------------------------------
# 13. Evaluator/agent separation for every foundation-adapter method call
# ---------------------------------------------------------------------------


class TestSecurityBoundary:
    def test_clean_payload_passes(self):
        result = foundations_security.check_foundation_call_boundary({"text": "clean content"})
        assert result.status == STATUS_NO_LEAKAGE

    def test_gold_answer_shaped_field_is_caught_in_add_memory_content(self):
        with pytest.raises(foundations_security.FoundationBoundaryViolation):
            foundations_security.enforce_foundation_call_boundary({"gold_answer": "the secret answer"})

    @pytest.mark.parametrize("cls", ALL_MOCK_CLASSES)
    def test_add_memory_rejects_contaminated_content(self, cls):
        instance = cls()
        with pytest.raises(foundations_security.FoundationBoundaryViolation):
            instance.add_memory("m1", {"gold_evidence_ids": ["e1"]})

    @pytest.mark.parametrize("cls", ALL_MOCK_CLASSES)
    def test_add_memory_rejects_contaminated_metadata(self, cls):
        instance = cls()
        with pytest.raises(foundations_security.FoundationBoundaryViolation):
            instance.add_memory("m1", {"text": "clean"}, {"evaluation_score": 0.9})

    @pytest.mark.parametrize("cls", ALL_MOCK_CLASSES)
    def test_retrieve_rejects_contaminated_query(self, cls):
        instance = cls()
        with pytest.raises(foundations_security.FoundationBoundaryViolation):
            instance.retrieve({"gold_answer": "leak"})

    def test_metadata_secret_is_rejected(self):
        instance = MockMem0Adapter()
        with pytest.raises(fingerprinting.ConfigurationSecretError):
            instance.add_memory("m1", {"text": "clean"}, {"api_key": "sk-leak"})


# ---------------------------------------------------------------------------
# 14. Dataset x foundation applicability spot-checks against the matrix
# ---------------------------------------------------------------------------


class TestDatasetFoundationMatrix:
    def test_matrix_has_700_cells(self):
        assert len(matrix.FULL_MATRIX) == 7 * 5 * 20

    def test_native_is_not_applicable_for_operational_capabilities(self):
        cell = matrix.compute_cell(matrix.DATASET_LOCOMO, matrix.FOUNDATION_NATIVE, "memory_creation")
        assert cell.status == matrix.MATRIX_NOT_APPLICABLE

    def test_native_is_supported_for_retrieval(self):
        cell = matrix.compute_cell(matrix.DATASET_LOCOMO, matrix.FOUNDATION_NATIVE, "retrieval")
        assert cell.status == matrix.MATRIX_SUPPORTED

    def test_mem0_graph_not_provided_for_any_dataset(self):
        for dataset_id in matrix.ALL_DATASETS:
            cell = matrix.compute_cell(dataset_id, capability_audit.FOUNDATION_MEM0, "graph")
            assert cell.status == matrix.MATRIX_NOT_PROVIDED

    def test_graphiti_graph_supported_for_locomo(self):
        cell = matrix.compute_cell(matrix.DATASET_LOCOMO, capability_audit.FOUNDATION_GRAPHITI, "graph")
        assert cell.status == matrix.MATRIX_SUPPORTED

    def test_temporal_state_gated_by_dataset_precondition(self):
        # MSC's temporal precondition is only PARTIAL (ordered-sequence-only, not
        # absolute timestamps) -- even though Graphiti's own audit row is SUPPORTED, the
        # matrix cell must be capped at PARTIAL, never silently upgraded to SUPPORTED.
        cell = matrix.compute_cell(matrix.DATASET_MSC, capability_audit.FOUNDATION_GRAPHITI, "temporal_state")
        assert cell.status == matrix.MATRIX_PARTIAL

    def test_unknown_dataset_precondition_yields_unknown_not_guessed(self):
        cell = matrix.compute_cell(
            matrix.DATASET_MEMORYAGENTBENCH, capability_audit.FOUNDATION_MEM0, "session_state"
        )
        assert cell.status == matrix.MATRIX_UNKNOWN

    def test_all_cells_use_valid_status(self):
        for cell in matrix.FULL_MATRIX.values():
            assert cell.status in matrix.MATRIX_STATES
            assert cell.reason


# ---------------------------------------------------------------------------
# 15. Phase 4 attack-surface exposure (identification only, no attack implemented)
# ---------------------------------------------------------------------------


class TestPhase4AttackSurfaceIdentification:
    def test_all_eight_interception_points_have_a_named_stage(self):
        expected = {
            "INPUT_INGESTION", "MEMORY_CREATION", "MEMORY_UPDATE", "MEMORY_LINKING",
            "STORAGE", "RETRIEVAL", "SELECTION", "AGENT_CONTEXT",
        }
        assert set(trace_mod.ALL_ATTACK_SURFACE_STAGES) == expected

    def test_every_stage_maps_to_at_least_one_operation(self):
        for stage in trace_mod.ALL_ATTACK_SURFACE_STAGES:
            assert len(trace_mod.ATTACK_SURFACE_OPERATION_MAP[stage]) >= 1

    def test_trace_artifact_can_carry_an_attack_surface_stage(self):
        t = trace_mod.build_trace(
            foundation_id="MEM0", adapter_version="v1", operation=trace_mod.OPERATION_ADD_MEMORY,
            timestamp="T1", attack_surface_stage=trace_mod.ATTACK_SURFACE_MEMORY_CREATION,
        )
        assert t.attack_surface_stage == trace_mod.ATTACK_SURFACE_MEMORY_CREATION
        assert "attack_surface_stage" in t.present

    def test_invalid_attack_surface_stage_rejected(self):
        with pytest.raises(ValueError):
            trace_mod.build_trace(
                foundation_id="MEM0", adapter_version="v1", operation=trace_mod.OPERATION_ADD_MEMORY,
                timestamp="T1", attack_surface_stage="NOT_A_REAL_STAGE",
            )

    def test_no_attack_logic_implemented_only_identification(self):
        # Structural proof: the module defines constants/mappings only, no function whose
        # name suggests it executes/simulates an attack.
        import phase3.evaluation.foundations.trace as tm

        forbidden_substrings = ("inject_attack", "poison(", "execute_attack", "simulate_attack")
        source = inspect.getsource(tm)
        for forbidden in forbidden_substrings:
            assert forbidden not in source


# ---------------------------------------------------------------------------
# 16. No fabricated evidence/provenance anywhere; native semantic preservation
# ---------------------------------------------------------------------------


class TestNativeSemanticPreservation:
    def test_graphiti_relationship_structure_is_nested_not_flattened(self):
        instance = MockGraphitiAdapter()
        instance.add_memory(
            "ep1", {"entities": [{"name": "A"}, {"name": "B"}], "relationships": [{"source": "A", "target": "B", "type": "KNOWS"}]}
        )
        inspected = instance.inspect_memory("ep1").value
        assert "graph" in inspected
        assert isinstance(inspected["graph"], dict)
        assert "nodes" in inspected["graph"] and "edges" in inspected["graph"]
        assert not isinstance(inspected["graph"], list)

    def test_amem_memory_evolution_mutates_existing_note(self):
        instance = MockAMemAdapter()
        instance.add_memory("n1", {"text": "first"}, {"tags": ["shared"]})
        before = instance.inspect_memory("n1").value["linked_memory_ids"]
        assert before == []
        instance.add_memory("n2", {"text": "second"}, {"tags": ["shared"]})
        after = instance.inspect_memory("n1").value["linked_memory_ids"]
        assert after == ["n2"]

    def test_mem0_has_no_graph_field_fabricated_in_inspect(self):
        instance = MockMem0Adapter()
        instance.add_memory("m1", {"text": "x"})
        inspected = instance.inspect_memory("m1").value
        assert "graph" not in inspected
        assert "linked_memory_ids" not in inspected

    def test_bi_temporal_invalidation_on_graphiti_update(self):
        instance = MockGraphitiAdapter()
        instance.add_memory("ep1", {"entities": [{"name": "A"}], "relationships": [{"source": "A", "target": "B", "type": "OWNS"}]})
        first_edges = instance.inspect_memory("ep1").value["graph"]["edges"]
        assert all(e["invalid_at"] is None for e in first_edges)
        instance.update_memory("ep1", {"relationships": [{"source": "A", "target": "C", "type": "OWNS"}]})
        edges_after = instance.inspect_memory("ep1").value["graph"]["edges"]
        old_edge = [e for e in edges_after if e["target"] == "B"][0]
        new_edge = [e for e in edges_after if e["target"] == "C"][0]
        assert old_edge["invalid_at"] is not None
        assert new_edge["invalid_at"] is None


# ---------------------------------------------------------------------------
# 17. All four foundations' status is exactly PREPARED_CANDIDATE
# ---------------------------------------------------------------------------


class TestRegistryStatus:
    def test_all_four_are_prepared_candidate(self):
        for foundation_id in capability_audit.ALL_FOUNDATIONS:
            entry = registry.FOUNDATION_REGISTRY[foundation_id]
            assert entry.status == "PREPARED_CANDIDATE"

    def test_registry_entry_rejects_non_prepared_candidate_status(self):
        with pytest.raises(ValueError):
            registry.FoundationRegistryEntry(
                foundation_id=capability_audit.FOUNDATION_MEM0,
                display_name="Mem0",
                status="ACTIVE",
                notes="should fail",
            )


# ---------------------------------------------------------------------------
# 18. FoundationField / FoundationTraceArtifact structural guarantees
# ---------------------------------------------------------------------------


class TestFoundationFieldStructural:
    def test_invalid_availability_rejected(self):
        with pytest.raises(ValueError):
            adapter_mod.FoundationField(value=None, availability="NOT_A_REAL_STATUS")

    def test_valid_availability_accepted(self):
        field_ = adapter_mod.FoundationField(value=1, availability=adapter_mod.FOUNDATION_AVAILABLE)
        assert field_.availability == adapter_mod.FOUNDATION_AVAILABLE

    def test_trace_present_field_tracks_supplied_optional_fields_only(self):
        t = trace_mod.build_trace(
            foundation_id="MEM0", adapter_version="v1", operation=trace_mod.OPERATION_RETRIEVE,
            timestamp="T1", memory_ids=("m1",),
        )
        assert "memory_ids" in t.present
        assert "native_scores" not in t.present
        assert t.native_scores is None

    def test_unrecognized_optional_field_rejected(self):
        with pytest.raises(ValueError):
            trace_mod.build_trace(
                foundation_id="MEM0", adapter_version="v1", operation=trace_mod.OPERATION_RETRIEVE,
                timestamp="T1", not_a_real_field=1,
            )

    def test_invalid_operation_rejected(self):
        with pytest.raises(ValueError):
            trace_mod.FoundationTraceArtifact(
                foundation_id="MEM0", adapter_version="v1", operation="NOT_A_REAL_OP", timestamp="T1",
            )
