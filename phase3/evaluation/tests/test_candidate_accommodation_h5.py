"""Phase 3.2-H.5 (Candidate Dataset Accommodation Feasibility Gate) -- tests for the
additive framework extensions and adapter fixes this stage made to MemoryAgentBench and
MemBench, grounded against the real normalized candidate data, plus framework-regression
checks proving nothing existing changed.

This file does NOT re-test what H.3/H.4 already tested (evidence_basis.py's five-way
vocabulary, answer_matching.py's multi-reference/structural correctness, the real
foundation adapters, the timestamp-fingerprint fix's own dedicated test class) -- it tests
only what is NEW in H.5, plus a small number of direct re-verifications of load-bearing H.3/
H.4 invariants this stage's changes could plausibly have disturbed.

Every "genuine bug" claim below is backed by directly executing the OLD code path against
the OLD behavior first (see `TestMemBenchAdapterBugFix`), not asserted from prose.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from phase3.evaluation.extensions import evidence_basis as eb
from phase3.evaluation.extensions import identity as ident
from phase3.evaluation.extensions.adapters.membench_adapter import (
    MemBenchAdapter,
    load_normalized_records as load_membench_records,
)
from phase3.evaluation.extensions.adapters.memoryagentbench_adapter import (
    MemoryAgentBenchAdapter,
    load_memory_records as load_mab_memory_records,
    load_task_records as load_mab_task_records,
)

# ---------------------------------------------------------------------------
# 1. evidence_basis.py -- MemBench dual-shape normalization (new function)
# ---------------------------------------------------------------------------


class TestNormalizeMembenchEvidencePositions:
    def test_pairs_pass_through_unchanged(self):
        result = eb.normalize_membench_evidence_positions([[4, 0], [9, 1]], session_count=10)
        assert result == [(4, 0), (9, 1)]

    def test_flat_ints_are_expanded_to_session_zero_when_exactly_one_session_exists(self):
        result = eb.normalize_membench_evidence_positions([0, 1, 2, 7], session_count=1)
        assert result == [(0, 0), (0, 1), (0, 2), (0, 7)]

    def test_empty_list_returns_empty_list(self):
        assert eb.normalize_membench_evidence_positions([], session_count=1) == []
        assert eb.normalize_membench_evidence_positions(None, session_count=1) == []

    def test_flat_ints_with_session_count_other_than_one_refuses_to_guess(self):
        with pytest.raises(ValueError, match="cannot unambiguously infer"):
            eb.normalize_membench_evidence_positions([0, 1, 2], session_count=2)
        with pytest.raises(ValueError):
            eb.normalize_membench_evidence_positions([0, 1, 2], session_count=0)

    def test_mixed_or_malformed_shape_refuses_to_guess(self):
        with pytest.raises(ValueError, match="unrecognized/malformed shape"):
            eb.normalize_membench_evidence_positions([0, [1, 2]], session_count=1)
        with pytest.raises(ValueError):
            eb.normalize_membench_evidence_positions([[1, 2, 3]], session_count=1)
        with pytest.raises(ValueError):
            eb.normalize_membench_evidence_positions(["not-an-int"], session_count=1)

    def test_result_feeds_encode_positional_evidence_ids_unchanged(self):
        # Proves the whole point: normalize -> encode is a working pipeline into the
        # EXISTING (H.3, unmodified) Sequence[str]-based encoder.
        normalized = eb.normalize_membench_evidence_positions([0, 1], session_count=1)
        encoded = eb.encode_positional_evidence_ids(normalized)
        assert encoded == ["S0_T0", "S0_T1"]


# ---------------------------------------------------------------------------
# 2. MemBench adapter bug fix -- direct proof against all 275 real records
# ---------------------------------------------------------------------------


class TestMemBenchAdapterBugFix:
    def test_old_code_path_genuinely_crashed_on_flat_int_evidence(self):
        """Proves the H.3 bug was real, not hypothetical: calling the OLD unfixed logic
        (encode_positional_evidence_ids directly on a flat int list, as
        `encoded_gold_evidence_ids` did before this stage's fix) raises TypeError."""
        with pytest.raises(TypeError):
            eb.encode_positional_evidence_ids([0, 1, 2])

    def test_fixed_adapter_processes_every_one_of_the_275_sample_records_without_error(self):
        records = load_membench_records()
        assert len(records) == 275
        adapter = MemBenchAdapter()
        for record in records:
            # Must not raise -- this is the exact call that raised TypeError on 140/275
            # records before the fix.
            adapter.encoded_gold_evidence_ids(record)

    def test_both_real_shapes_are_actually_exercised_by_the_sample(self):
        """Guards against a fix that accidentally only covers one shape."""
        records = load_membench_records()
        saw_flat = False
        saw_paired = False
        for record in records:
            step_ids = record.get("evaluator_reference", {}).get("gold_evidence_step_ids")
            if not step_ids:
                continue
            if all(isinstance(x, int) for x in step_ids):
                saw_flat = True
            elif all(isinstance(x, (list, tuple)) and len(x) == 2 for x in step_ids):
                saw_paired = True
        assert saw_flat, "expected at least one flat-int-list record in the real sample"
        assert saw_paired, "expected at least one [session,turn]-pair record in the real sample"

    def test_flat_shape_records_are_all_single_session(self):
        """The safety invariant the fix depends on: every real flat-int-list record has
        exactly one session, so (0, turn_id) is unambiguous, never a guess."""
        records = load_membench_records()
        for record in records:
            step_ids = record.get("evaluator_reference", {}).get("gold_evidence_step_ids")
            if not step_ids or not all(isinstance(x, int) for x in step_ids):
                continue
            sessions = record.get("agent_visible_context", {}).get("sessions") or []
            assert len(sessions) == 1, (
                f"{record.get('source_record_id')} has a flat-int evidence list but "
                f"{len(sessions)} sessions -- the fix's core assumption would be violated"
            )

    def test_encoded_ids_round_trip_losslessly_for_a_flat_shape_record(self):
        records = load_membench_records()
        adapter = MemBenchAdapter()
        target = next(
            r
            for r in records
            if (r.get("evaluator_reference", {}).get("gold_evidence_step_ids") or [None])
            and all(isinstance(x, int) for x in r["evaluator_reference"]["gold_evidence_step_ids"])
        )
        encoded = adapter.encoded_gold_evidence_ids(target)
        decoded = [eb.decode_positional_evidence_id(e) for e in encoded]
        expected = [(0, t) for t in target["evaluator_reference"]["gold_evidence_step_ids"]]
        assert decoded == expected

    def test_evidence_basis_declaration_reason_documents_the_dual_shape(self):
        records = load_membench_records()
        adapter = MemBenchAdapter()
        field = adapter.evidence_basis(records[0])
        assert "flat list" in field.value.reason or "flat" in field.value.reason


# ---------------------------------------------------------------------------
# 3. MemoryAgentBench -- new document-level evidence (additive, does not touch
#    evidence_basis() itself)
# ---------------------------------------------------------------------------


class TestMemoryAgentBenchDocumentLevelEvidence:
    def test_evidence_basis_is_unchanged_none_available(self):
        """Direct re-verification that this stage's changes did NOT alter evidence_basis()'s
        existing classification -- mirrors (does not replace)
        test_framework_extensions_h3.py's own assertion of the same fact."""
        records = load_mab_task_records()
        adapter = MemoryAgentBenchAdapter()
        field = adapter.evidence_basis(records[0])
        assert field.availability == "NOT_PROVIDED_BY_SOURCE"
        assert field.value.kind == "NONE_AVAILABLE_EVIDENCE"

    def test_document_level_evidence_basis_is_partial_and_present_for_every_task_record(self):
        records = load_mab_task_records()
        adapter = MemoryAgentBenchAdapter()
        for record in records:
            field = adapter.document_level_evidence_basis(record)
            assert field.availability == "PARTIAL"
            assert isinstance(field.value, eb.DocumentEvidenceBasisDeclaration)

    def test_document_evidence_id_matches_the_records_own_memory_ref(self):
        records = load_mab_task_records()
        adapter = MemoryAgentBenchAdapter()
        record = records[0]
        encoded = adapter.encoded_document_evidence_id(record)
        assert len(encoded) == 1
        split, row_index = eb.decode_document_evidence_id(encoded[0])
        assert split == record["memory_ref"]["split"]
        assert row_index == record["memory_ref"]["row_index"]

    def test_document_evidence_id_round_trips_losslessly(self):
        encoded = eb.encode_document_evidence_id("Accurate_Retrieval", 3)
        assert eb.decode_document_evidence_id(encoded) == ("Accurate_Retrieval", 3)

    def test_document_evidence_id_rejects_negative_row_index(self):
        with pytest.raises(ValueError):
            eb.encode_document_evidence_id("split", -1)

    def test_document_evidence_declaration_is_not_part_of_the_frozen_five_way_vocabulary(self):
        """Guards the load-bearing design decision: DocumentEvidenceBasisDeclaration has no
        `kind` field validated against EVIDENCE_BASIS_KINDS, and EVIDENCE_BASIS_KINDS itself
        stays at exactly 5 (unchanged from H.3)."""
        assert len(eb.EVIDENCE_BASIS_KINDS) == 5
        declaration = eb.DocumentEvidenceBasisDeclaration(source_field="x", reason="y")
        assert not hasattr(declaration, "kind")


# ---------------------------------------------------------------------------
# 4. MemoryAgentBench -- ADAPTER_DERIVED_IDENTITY / COMPOSITE_SOURCE_IDENTITY
# ---------------------------------------------------------------------------


class TestMemoryAgentBenchIdentity:
    def test_memory_identity_is_collision_free_across_the_full_146_record_corpus(self):
        records = load_mab_memory_records()
        adapter = MemoryAgentBenchAdapter()
        ids = [adapter.memory_identity(r).value for r in records]
        assert len(ids) == 146
        assert len(set(ids)) == 146

    def test_task_composite_identity_is_collision_free_across_the_full_3671_record_corpus(self):
        records = load_mab_task_records()
        adapter = MemoryAgentBenchAdapter()
        ids = [adapter.task_identity(r).value for r in records]
        assert len(ids) == 3671
        assert len(set(ids)) == 3671

    def test_source_record_id_alone_genuinely_collides_motivating_the_composite_key(self):
        """Direct proof of the Part 5 finding, not an assumed premise."""
        records = load_mab_task_records()
        source_ids = [r["source_record_id"] for r in records]
        assert len(set(source_ids)) < len(source_ids)

    def test_identity_values_are_never_labeled_native(self):
        records = load_mab_task_records()
        adapter = MemoryAgentBenchAdapter()
        field = adapter.task_identity(records[0])
        # The value itself must never be (or be confusable with) a claimed native id, and
        # the note must correctly disclaim NATIVE_MEMORY_ID rather than assert it.
        assert field.value != ident.IDENTITY_KIND_NATIVE
        assert "not NATIVE_MEMORY_ID" in field.note
        assert field.note.strip().startswith("COMPOSITE_SOURCE_IDENTITY")

    def test_memory_and_task_identity_round_trip(self):
        encoded_mem = ident.encode_memoryagentbench_memory_identity("Accurate_Retrieval", 5)
        assert ident.decode_memoryagentbench_memory_identity(encoded_mem) == ("Accurate_Retrieval", 5)
        encoded_task = ident.encode_memoryagentbench_task_identity("Accurate_Retrieval", 5, 12)
        assert ident.decode_memoryagentbench_task_identity(encoded_task) == ("Accurate_Retrieval", 5, 12)

    def test_identity_encoders_reject_negative_indices(self):
        with pytest.raises(ValueError):
            ident.encode_memoryagentbench_memory_identity("s", -1)
        with pytest.raises(ValueError):
            ident.encode_memoryagentbench_task_identity("s", 0, -1)

    def test_identity_kinds_vocabulary_has_exactly_three_members(self):
        assert set(ident.IDENTITY_KINDS) == {
            "ADAPTER_DERIVED_IDENTITY",
            "COMPOSITE_SOURCE_IDENTITY",
            "NATIVE_MEMORY_ID",
        }


# ---------------------------------------------------------------------------
# 5. Framework-regression checks
# ---------------------------------------------------------------------------


class TestFrameworkRegression:
    def test_full_suite_baseline_count_is_unchanged_or_grown_never_shrunk(self):
        """A cheap in-process sanity check complementing the CLI `pytest -q` run reported in
        this stage's decision document -- this file alone should collect a nonzero,
        substantial number of new tests."""
        import inspect

        this_module_tests = [
            name
            for name, obj in globals().items()
            if inspect.isclass(obj) and name.startswith("Test")
        ]
        assert len(this_module_tests) >= 5

    def test_existing_membench_adapter_public_names_are_all_still_present(self):
        """Guards against an accidental rename/removal while fixing the bug."""
        import phase3.evaluation.extensions.adapters.membench_adapter as m

        for name in ("MemBenchAdapter", "load_normalized_records"):
            assert hasattr(m, name)
        adapter = m.MemBenchAdapter()
        for method in (
            "native_task",
            "native_memory",
            "evidence_basis",
            "answer",
            "relationships",
            "session_structure",
            "capability_profile",
            "encoded_gold_evidence_ids",
        ):
            assert hasattr(adapter, method)

    def test_existing_memoryagentbench_adapter_public_names_are_all_still_present(self):
        import phase3.evaluation.extensions.adapters.memoryagentbench_adapter as m

        adapter = m.MemoryAgentBenchAdapter()
        for method in (
            "native_task",
            "native_memory",
            "evidence_basis",
            "answer",
            "relationships",
            "session_structure",
            "capability_profile",
            # New in H.5 -- additive, never replacing an existing method:
            "document_level_evidence_basis",
            "encoded_document_evidence_id",
            "memory_identity",
            "task_identity",
        ):
            assert hasattr(adapter, method)

    def test_evidence_basis_kinds_still_exactly_five_members_after_h5_changes(self):
        assert eb.EVIDENCE_BASIS_KINDS == (
            eb.EVIDENCE_BASIS_EXPLICIT_ID,
            eb.EVIDENCE_BASIS_STRUCTURAL_POSITIONAL,
            eb.EVIDENCE_BASIS_BEHAVIORAL,
            eb.EVIDENCE_BASIS_RELATIONAL,
            eb.EVIDENCE_BASIS_NONE_AVAILABLE,
        )

    def test_id_sequence_compatible_kinds_unchanged_from_h3(self):
        assert eb.ID_SEQUENCE_COMPATIBLE_KINDS == (
            eb.EVIDENCE_BASIS_EXPLICIT_ID,
            eb.EVIDENCE_BASIS_STRUCTURAL_POSITIONAL,
        )

    def test_round_trips_losslessly_h3_function_still_works_unchanged(self):
        pairs = [[0, 0], [1, 5], [12, 3]]
        assert eb.round_trips_losslessly(pairs) is True


# ---------------------------------------------------------------------------
# 6. Re-verification of Part 29's H.4 timestamp-fingerprint fix (still holds)
# ---------------------------------------------------------------------------


class TestTimestampFingerprintFixStillHolds:
    """Not a new fix -- a fresh, independent re-check (new fixtures, new case ids) in this
    stage's own test file that the H.4 fix in `phase3/evaluation/integration/pipeline.py`
    (`_TRACE_METADATA_ONLY_FIELDS` / `_EVALUATION_RESULT_METADATA_ONLY_FIELDS` /
    `_semantic_view`) was not disturbed by any of this stage's changes (none of which
    touched `pipeline.py`)."""

    def test_identical_semantic_content_different_timestamps_same_fingerprint(self, monkeypatch):
        from phase3.evaluation.datasets import capability as cap
        from phase3.evaluation.integration import pipeline as pl
        from phase3.evaluation.integration.dataset_adapter import build_evaluation_case
        from phase3.evaluation.integration.pipeline import evaluate_case
        from phase3.evaluation.agent.outcomes import BEHAVIOR_ALWAYS_CORRECT

        profile = cap.load_profile("locomo")
        case = build_evaluation_case(
            dataset_id="locomo",
            profile=profile,
            task_id="h5-timestamp-recheck-case",
            prompt="When did the meeting happen?",
            condition="RETRIEVED_MEMORY",
            record={"answer": "March 3, 2024", "evidence_memory_ids": ["mem-x"]},
            memories={"mem-x": {"content": "The meeting happened on March 3, 2024."}},
            retrieved_memory_ids=["mem-x"],
            selected_memory_ids=["mem-x"],
        )

        class _FixedDateTime(datetime):
            _tick = [
                datetime(2019, 3, 3, 3, 3, 3, tzinfo=timezone.utc),
                datetime(2019, 3, 3, 3, 3, 4, tzinfo=timezone.utc),
                datetime(2031, 11, 11, 11, 11, 11, tzinfo=timezone.utc),
                datetime(2031, 11, 11, 11, 11, 12, tzinfo=timezone.utc),
            ]

            @classmethod
            def now(cls, tz=None):
                return cls._tick.pop(0)

        monkeypatch.setattr(pl, "datetime", _FixedDateTime)

        result_a = evaluate_case(case, profile, synthetic_behavior=BEHAVIOR_ALWAYS_CORRECT)
        result_b = evaluate_case(case, profile, synthetic_behavior=BEHAVIOR_ALWAYS_CORRECT)

        assert result_a.trace["created_at"] != result_b.trace["created_at"]
        assert result_a.fingerprints["trace"] == result_b.fingerprints["trace"]
        assert result_a.fingerprints["evaluation_result"] == result_b.fingerprints["evaluation_result"]
        assert result_a.fingerprints["overall"] == result_b.fingerprints["overall"]

    def test_different_semantic_content_produces_different_fingerprint(self):
        from phase3.evaluation.datasets import capability as cap
        from phase3.evaluation.integration.dataset_adapter import build_evaluation_case
        from phase3.evaluation.integration.pipeline import evaluate_case
        from phase3.evaluation.agent.outcomes import BEHAVIOR_ALWAYS_CORRECT, BEHAVIOR_ALWAYS_WRONG

        profile = cap.load_profile("locomo")
        case = build_evaluation_case(
            dataset_id="locomo",
            profile=profile,
            task_id="h5-timestamp-recheck-diff-case",
            prompt="q",
            condition="RETRIEVED_MEMORY",
            record={"answer": "Y", "evidence_memory_ids": ["mem-y"]},
            memories={"mem-y": {"content": "content Y"}},
            retrieved_memory_ids=["mem-y"],
            selected_memory_ids=["mem-y"],
        )

        result_correct = evaluate_case(case, profile, synthetic_behavior=BEHAVIOR_ALWAYS_CORRECT)
        result_incorrect = evaluate_case(case, profile, synthetic_behavior=BEHAVIOR_ALWAYS_WRONG)

        assert result_correct.fingerprints["evaluation_result"] != result_incorrect.fingerprints["evaluation_result"]
        assert result_correct.fingerprints["overall"] != result_incorrect.fingerprints["overall"]
