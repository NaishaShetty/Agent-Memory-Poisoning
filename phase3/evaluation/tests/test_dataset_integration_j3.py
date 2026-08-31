"""Phase 3.2-J.3 -- integration tests for PerLTQA (zh, USABLE) and ConvoMem
(USABLE_WITH_LIMITATIONS) through the real MAMBench evaluation pipeline
(`integration.dataset_adapter` + `integration.pipeline`), the `DatasetAdapter`
abstraction, and the mock memory-foundation layer.

Scope: exercises the REAL, already-normalized J.1/J.2 records for both datasets --
not synthetic toy fixtures (Part 26's explicit instruction) -- through the SAME
generic pipeline code the 4 active datasets use. No canonical metric, Strict TSR,
condition, or leakage rule is redefined anywhere in this file.
"""
from __future__ import annotations

import json
import os

import pytest

from phase3.datasets.candidates.convomem import evaluation_bridge as cb
from phase3.datasets.candidates.perltqa import evaluation_bridge as pb
from phase3.evaluation.agent.conditions import CONDITION_GOLD_EVIDENCE, CONDITION_NO_MEMORY
from phase3.evaluation.extensions.adapters.convomem_adapter import ConvoMemAdapter
from phase3.evaluation.extensions.adapters.convomem_adapter import load_task_records as cm_load_tasks
from phase3.evaluation.extensions.adapters.convomem_adapter import load_memory_records as cm_load_mems
from phase3.evaluation.extensions.adapters.perltqa_adapter import PerLTQAAdapter
from phase3.evaluation.extensions.adapters.perltqa_adapter import load_task_records as pq_load_tasks
from phase3.evaluation.extensions.adapters.perltqa_adapter import load_memory_records as pq_load_mems
from phase3.evaluation.extensions.identity import (
    decode_convomem_memory_identity,
    decode_perltqa_memory_identity,
    encode_convomem_memory_identity,
    encode_perltqa_memory_identity,
)
from phase3.evaluation.foundations.mocks.mock_amem import MockAMemAdapter
from phase3.evaluation.foundations.mocks.mock_graphiti import MockGraphitiAdapter
from phase3.evaluation.foundations.mocks.mock_letta import MockLettaAdapter
from phase3.evaluation.foundations.mocks.mock_mem0 import MockMem0Adapter
from phase3.evaluation.integration import dataset_adapter as da
from phase3.evaluation.integration import pipeline
from phase3.evaluation.integration import validation as val

_REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def _load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Fixtures (session-scoped, real data loaded once)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def perltqa_universe():
    return pb.load_evaluation_universe()


@pytest.fixture(scope="module")
def convomem_universe():
    return cb.load_evaluation_universe()


@pytest.fixture(scope="module")
def perltqa_profile():
    return pb.load_evaluation_profile()


@pytest.fixture(scope="module")
def convomem_profile():
    return cb.load_evaluation_profile()


# ===========================================================================
# PERLTQA
# ===========================================================================


class TestPerLTQASourceIdentity:
    def test_registry_status(self):
        path = os.path.join(_REPO_ROOT, "phase3", "datasets", "candidates", "perltqa", "manifests", "registry_entry.json")
        entry = _load_json(path)
        assert entry["dataset_name"] == "perltqa"

    def test_evaluation_profile_dataset_id(self, perltqa_profile):
        assert perltqa_profile["dataset_id"] == "perltqa"
        assert perltqa_profile["profile_status"] == "REVIEWED"


class TestPerLTQAZhPreservation:
    def test_questions_contain_chinese_characters_not_romanized(self, perltqa_universe):
        tasks, _ = perltqa_universe
        chinese_count = 0
        for t in tasks[:200]:
            q = t["agent_visible"]["question"]
            if any("一" <= ch <= "鿿" for ch in q):
                chinese_count += 1
        assert chinese_count > 190  # overwhelming majority (zh release)

    def test_answers_are_not_ascii_only(self, perltqa_universe):
        tasks, _ = perltqa_universe
        non_ascii_answers = sum(1 for t in tasks[:200] if any(ord(c) > 127 for c in t["evaluator_only"]["gold_answer"]))
        assert non_ascii_answers > 190


class TestPerLTQANativeEvidenceIdentity:
    def test_encoded_evidence_ids_decode_back_to_native_pair(self, perltqa_universe):
        tasks, _ = perltqa_universe
        adapter = PerLTQAAdapter()
        non_profile = [t for t in tasks if t["section"] != "PROFILE"][:100]
        checked = 0
        for t in non_profile:
            for eid in adapter.encoded_evidence_ids(t):
                character, native_id = decode_perltqa_memory_identity(eid)
                assert character == t["character"]
                assert native_id  # native id copied verbatim, never invented
                checked += 1
        assert checked > 0

    def test_memory_identity_collision_free(self):
        """Regression guard on the full 7,521-memory-unit corpus (not a sample)."""
        mems = pq_load_mems()
        adapter = PerLTQAAdapter()
        ids = [adapter.memory_identity(m).value for m in mems]
        assert len(ids) == 7521
        assert len(set(ids)) == 7521

    def test_evidence_never_fabricated_for_profile_section(self, perltqa_universe):
        tasks, _ = perltqa_universe
        adapter = PerLTQAAdapter()
        profile_recs = [t for t in tasks if t["section"] == "PROFILE"][:50]
        for t in profile_recs:
            assert adapter.encoded_evidence_ids(t) == []
            field = adapter.evidence_basis(t)
            assert field.availability == "NOT_PROVIDED_BY_SOURCE"


class TestPerLTQAClassificationPreservation:
    def test_profile_labels_are_source_native_values(self, perltqa_universe):
        tasks, _ = perltqa_universe
        adapter = PerLTQAAdapter()
        # Real, full-corpus-verified set of 15 distinct profile-section classification
        # labels (some character records split "Awards and Role Models" into separate
        # "Awards"/"Role Models" fields -- a genuine, real source-side inconsistency,
        # not something this adapter invents or reconciles).
        known_labels = {
            "Gender", "Nickname", "Title", "Age", "Occupation", "Nationality",
            "Physical Characteristics", "Hobbies", "Achievements",
            "Ethnic Background", "Education Background", "Employer",
            "Awards and Role Models", "Awards", "Role Models",
        }
        profile_recs = [t for t in tasks if t["section"] == "PROFILE"][:100]
        seen = set()
        for t in profile_recs:
            label = adapter.classification_label(t).value
            assert label in known_labels  # never an invented category
            seen.add(label)
        assert len(seen) > 1


class TestPerLTQASemanticEpisodicPreservation:
    def test_memory_kind_values_are_source_taxonomy_not_flattened(self):
        mems = pq_load_mems()
        kinds = {m["memory_kind"] for m in mems}
        assert kinds == {"PROFILE", "SOCIAL_RELATIONSHIP", "EVENTS", "DIALOGUES"}

    def test_native_memory_content_stays_structured_not_flattened_to_string(self):
        mems = pq_load_mems()
        adapter = PerLTQAAdapter()
        events_rec = next(m for m in mems if m["memory_kind"] == "EVENTS")
        content = adapter.native_memory(events_rec).value
        assert isinstance(content, dict)  # structured, per Part 4's explicit instruction


class TestPerLTQAPipelineIntegration:
    def test_profile_evaluation_profile_passes_invariants(self, perltqa_profile):
        val.assert_all_invariants(perltqa_profile)  # raises on violation

    def test_gold_evidence_case_full_pipeline_real_record(self, perltqa_universe, perltqa_profile):
        tasks, mems = perltqa_universe
        non_profile = [t for t in tasks if t["section"] != "PROFILE"]
        t = non_profile[0]
        rec = pb.to_evaluation_record(t)
        scoped = pb.scoped_memories_for_task(t, mems)
        case = da.build_evaluation_case(
            dataset_id="perltqa", profile=perltqa_profile, task_id=t["source_record_id"],
            prompt=t["agent_visible"]["question"], condition=CONDITION_GOLD_EVIDENCE,
            record=rec, memories=scoped, selected_memory_ids=rec["evidence_memory_ids"],
        )
        assert case.task_applicable
        result = pipeline.evaluate_case(case, perltqa_profile, synthetic_behavior="ALWAYS_CORRECT")
        assert result.metrics["STRICT_TSR"].status == "OK"
        assert result.metrics["RECALL_AT_K"].status == "OK"
        assert result.metrics["AGENT_ANSWER_CORRECTNESS"].status == "ANSWER_CORRECT"
        assert result.leakage_result.status == "NO_LEAKAGE"

    def test_profile_section_case_never_fabricates_strict_tsr(self, perltqa_universe, perltqa_profile):
        """Evidence-free (profile-section) case must be UNDEFINED_EMPTY_GOLD, never 0."""
        tasks, mems = perltqa_universe
        t = next(x for x in tasks if x["section"] == "PROFILE")
        rec = pb.to_evaluation_record(t)
        scoped = pb.scoped_memories_for_task(t, mems)
        case = da.build_evaluation_case(
            dataset_id="perltqa", profile=perltqa_profile, task_id=t["source_record_id"],
            prompt=t["agent_visible"]["question"], condition=CONDITION_NO_MEMORY,
            record=rec, memories=scoped, selected_memory_ids=[],
        )
        result = pipeline.evaluate_case(case, perltqa_profile, synthetic_behavior="ALWAYS_CORRECT")
        assert result.metrics["STRICT_TSR"].status == "UNDEFINED_EMPTY_GOLD"
        assert result.metrics["STRICT_TSR"].value is None
        assert result.metrics["AGENT_ANSWER_CORRECTNESS"].status == "ANSWER_CORRECT"

    def test_determinism_two_runs_identical_fingerprint(self, perltqa_universe, perltqa_profile):
        tasks, mems = perltqa_universe
        t = tasks[3]
        rec = pb.to_evaluation_record(t)
        scoped = pb.scoped_memories_for_task(t, mems)
        case = da.build_evaluation_case(
            dataset_id="perltqa", profile=perltqa_profile, task_id=t["source_record_id"],
            prompt=t["agent_visible"]["question"], condition=CONDITION_NO_MEMORY,
            record=rec, memories=scoped,
        )
        r1 = pipeline.evaluate_case(case, perltqa_profile, synthetic_behavior="ALWAYS_CORRECT")
        r2 = pipeline.evaluate_case(case, perltqa_profile, synthetic_behavior="ALWAYS_CORRECT")
        assert r1.fingerprints["overall"] == r2.fingerprints["overall"]


class TestPerLTQAFoundationMapping:
    @pytest.mark.parametrize("adapter_cls", [MockMem0Adapter, MockGraphitiAdapter, MockAMemAdapter, MockLettaAdapter])
    def test_real_memory_unit_add_and_retrieve(self, perltqa_universe, adapter_cls):
        _, mems = perltqa_universe
        source_memory_id, entry = next(iter(mems.items()))
        foundation = adapter_cls()
        foundation.initialize({})
        result = foundation.add_memory(
            None, entry["structured_content"],
            metadata={"source_memory_id": source_memory_id, "dataset_id": "perltqa"},
        )
        assert result.availability == "AVAILABLE"
        foundation_memory_id = result.value["memory_id"]
        # Part 15: FOUNDATION_DERIVED_IDENTITY must be distinguishable from SOURCE_MEMORY_ID
        # -- checked at the id level (uniform across all 4 architecturally-different mocks);
        # inspect_memory()'s RETURN SHAPE is deliberately foundation-native (e.g. Graphiti's
        # graph nodes/edges vs. Mem0's flat metadata dict) and is not asserted uniformly here.
        assert foundation_memory_id != source_memory_id
        inspected = foundation.inspect_memory(foundation_memory_id)
        assert inspected.availability == "AVAILABLE"
        foundation.reset()


# ===========================================================================
# CONVOMEM
# ===========================================================================


class TestConvoMemSourceIdentity:
    def test_evaluation_profile_dataset_id_and_status(self, convomem_profile):
        assert convomem_profile["dataset_id"] == "convomem"
        assert "USABLE_WITH_LIMITATIONS" in convomem_profile["role"]

    def test_registry_status_still_prepared_candidate_activation(self):
        path = os.path.join(_REPO_ROOT, "phase3", "datasets", "candidates", "convomem", "manifests", "registry_entry.json")
        entry = _load_json(path)
        assert entry["activation_status"] == "PREPARED_CANDIDATE"  # unchanged by J.3


class TestConvoMemEvidenceResolutionPreservation:
    def test_j2_waterfall_statuses_survive_into_task_records(self, convomem_universe):
        tasks, _ = convomem_universe
        statuses = set()
        for t in tasks:
            res = t["evaluator_only"]["evidence_resolution"]
            if isinstance(res, list):
                statuses.update(r["status"] for r in res)
        expected = {"EXACT_RAW", "TRUNCATED_UNIQUE", "UNRESOLVED", "MULTIMESSAGE_UNIQUE", "TRUNCATED_AMBIGUOUS", "MULTIMESSAGE_AMBIGUOUS"}
        assert statuses & expected  # real statuses present, not collapsed

    def test_full_corpus_resolution_rate_still_96_98_percent(self):
        path = os.path.join(
            _REPO_ROOT, "phase3", "datasets", "candidates", "convomem", "reports", "evidence_audit_j2_data.json"
        )
        audit = _load_json(path)
        assert 0.965 <= audit["resolved_rate"] <= 0.975  # never silently reported as 100%


class TestConvoMemUnresolvedAndAmbiguousHandling:
    def test_unresolved_evidence_never_becomes_zero_or_fabricated(self, convomem_universe, convomem_profile):
        tasks, mems = convomem_universe

        def is_unresolved(t):
            r = t["evaluator_only"]["evidence_resolution"]
            return not isinstance(r, list) or all(
                x["status"] in ("UNRESOLVED", "TOO_SHORT", "TRUNCATED_AMBIGUOUS", "MULTIMESSAGE_AMBIGUOUS") for x in r
            )

        t = next(x for x in tasks if is_unresolved(x))
        rec = cb.to_evaluation_record(t)
        assert rec["evidence_memory_ids"] == []
        scoped = cb.scoped_memories_for_task(t, mems)
        case = da.build_evaluation_case(
            dataset_id="convomem", profile=convomem_profile, task_id=t["source_record_id"],
            prompt=t["agent_visible"]["question"], condition=CONDITION_NO_MEMORY,
            record=rec, memories=scoped,
        )
        result = pipeline.evaluate_case(case, convomem_profile, synthetic_behavior="ALWAYS_CORRECT")
        assert result.metrics["STRICT_TSR"].status == "UNDEFINED_EMPTY_GOLD"
        assert result.metrics["STRICT_TSR"].value is None
        assert result.metrics["AGENT_ANSWER_CORRECTNESS"].status == "ANSWER_CORRECT"

    def test_ambiguous_spans_preserve_all_candidate_locations(self, convomem_universe):
        tasks, _ = convomem_universe
        adapter = ConvoMemAdapter()
        ambiguous_found = [t for t in tasks if adapter.ambiguous_locations(t)]
        assert ambiguous_found
        amb = adapter.ambiguous_locations(ambiguous_found[0])[0]
        assert len(amb["locations"]) >= 2  # never collapsed to one


class TestConvoMemDerivedIdentity:
    def test_encoded_evidence_ids_decode_back_to_conversation_and_index(self, convomem_universe):
        tasks, _ = convomem_universe
        adapter = ConvoMemAdapter()
        checked = 0
        for t in tasks[:200]:
            for eid in adapter.encoded_evidence_ids(t):
                if "_M" in eid and "-" not in eid.split("_M")[-1]:
                    cid, idx = decode_convomem_memory_identity(eid)
                    assert cid
                    assert idx >= 0
                    checked += 1
        assert checked > 0

    def test_identity_never_labeled_native(self):
        """ADAPTER_DERIVED_IDENTITY, never NATIVE_MEMORY_ID, per Part 7/Part 15."""
        eid = encode_convomem_memory_identity("some-conv-id", 3)
        # This is a naming/labeling discipline check at the adapter layer, not the
        # encoder itself (the encoder has no "kind" field) -- verified via the task
        # record's evidence_identity_kind string in normalize.py.
        tasks = cm_load_tasks()
        t = next(x for x in tasks if isinstance(x["evaluator_only"]["evidence_resolution"], list))
        assert "ADAPTER_DERIVED_IDENTITY" in t["evaluator_only"]["evidence_identity_kind"]
        assert "NOT a native evidence-ID field" in t["evaluator_only"]["evidence_identity_kind"]


class TestConvoMemPipelineIntegration:
    def test_profile_passes_invariants(self, convomem_profile):
        val.assert_all_invariants(convomem_profile)

    def test_resolved_case_full_pipeline_real_record(self, convomem_universe, convomem_profile):
        tasks, mems = convomem_universe
        resolved = [
            t for t in tasks
            if isinstance(t["evaluator_only"]["evidence_resolution"], list)
            and any(r["status"] in ("EXACT_RAW", "TRUNCATED_UNIQUE") for r in t["evaluator_only"]["evidence_resolution"])
        ]
        t = resolved[0]
        rec = cb.to_evaluation_record(t)
        scoped = cb.scoped_memories_for_task(t, mems)
        case = da.build_evaluation_case(
            dataset_id="convomem", profile=convomem_profile, task_id=t["source_record_id"],
            prompt=t["agent_visible"]["question"], condition=CONDITION_GOLD_EVIDENCE,
            record=rec, memories=scoped, selected_memory_ids=rec["evidence_memory_ids"],
        )
        result = pipeline.evaluate_case(case, convomem_profile, synthetic_behavior="ALWAYS_CORRECT")
        assert result.metrics["STRICT_TSR"].status == "OK"
        assert result.leakage_result.status == "NO_LEAKAGE"

    def test_determinism_two_runs_identical_fingerprint(self, convomem_universe, convomem_profile):
        tasks, mems = convomem_universe
        t = tasks[7]
        rec = cb.to_evaluation_record(t)
        scoped = cb.scoped_memories_for_task(t, mems)
        case = da.build_evaluation_case(
            dataset_id="convomem", profile=convomem_profile, task_id=t["source_record_id"],
            prompt=t["agent_visible"]["question"], condition=CONDITION_NO_MEMORY,
            record=rec, memories=scoped,
        )
        r1 = pipeline.evaluate_case(case, convomem_profile, synthetic_behavior="ALWAYS_CORRECT")
        r2 = pipeline.evaluate_case(case, convomem_profile, synthetic_behavior="ALWAYS_CORRECT")
        assert r1.fingerprints["overall"] == r2.fingerprints["overall"]


class TestConvoMemFoundationMapping:
    @pytest.mark.parametrize("adapter_cls", [MockMem0Adapter, MockGraphitiAdapter, MockAMemAdapter, MockLettaAdapter])
    def test_real_message_add_and_retrieve(self, convomem_universe, adapter_cls):
        _, mems = convomem_universe
        source_memory_id, entry = next(iter(mems.items()))
        foundation = adapter_cls()
        foundation.initialize({})
        result = foundation.add_memory(
            None, {"text": entry["content"], "speaker": entry.get("speaker")},
            metadata={"source_memory_id": source_memory_id, "dataset_id": "convomem"},
        )
        assert result.availability == "AVAILABLE"
        foundation_memory_id = result.value["memory_id"]
        assert foundation_memory_id != source_memory_id
        inspected = foundation.inspect_memory(foundation_memory_id)
        assert inspected.availability == "AVAILABLE"
        foundation.reset()


class TestConvoMemLicensing:
    def test_license_still_unresolved_not_silently_promoted(self):
        path = os.path.join(_REPO_ROOT, "phase3", "datasets", "candidates", "convomem", "manifests", "registry_entry.json")
        entry = _load_json(path)
        assert "LICENSE_UNRESOLVED" in entry["license"]


# ===========================================================================
# CROSS-DATASET: memory identity namespace separation (Part 15)
# ===========================================================================


class TestMemoryIdentityNamespaceSeparation:
    def test_perltqa_and_convomem_id_encodings_are_never_confusable(self):
        pq_id = encode_perltqa_memory_identity("X", "1_0")
        cm_id = encode_convomem_memory_identity("Y", 1)
        assert pq_id.startswith("PERLTQA<")
        assert cm_id.startswith("CONVOMEM<")
        assert pq_id != cm_id
        with pytest.raises(ValueError):
            decode_convomem_memory_identity(pq_id)
        with pytest.raises(ValueError):
            decode_perltqa_memory_identity(cm_id)

    def test_foundation_derived_id_distinct_from_source_memory_id(self):
        """A foundation's own assigned id (mock auto-id) must never collide with, or be
        mistaken for, the source-native/adapter-derived memory id passed as metadata."""
        foundation = MockMem0Adapter()
        foundation.initialize({})
        source_id = encode_perltqa_memory_identity("X", "1_0")
        result = foundation.add_memory(None, {"text": "content"}, metadata={"source_memory_id": source_id})
        foundation_id = result.value["memory_id"]
        assert foundation_id != source_id  # FOUNDATION_DERIVED_IDENTITY != SOURCE_MEMORY_ID
        assert foundation_id.startswith("mem0-auto-")
        foundation.reset()
