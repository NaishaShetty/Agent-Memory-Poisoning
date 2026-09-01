"""Phase 3.3-F.1 UNIT_TESTs for the PerLTQA/ConvoMem sampling in
`pilot_secondary_datasets.py`, over the REAL, unmodified normalized packages
(`phase3/datasets/candidates/{perltqa,convomem}/normalized/`). Read-only -- no dataset
content is modified anywhere in this test file.
"""

from __future__ import annotations

from phase3.evaluation.agent_runtime.pilot_secondary_datasets import (
    CONVOMEM_DIR,
    PERLTQA_DIR,
    _RESOLVED_CONVOMEM_STATUSES,
    _import_bridge,
    _safe_collection_name,
    _sample_convomem,
    _sample_perltqa,
)


class TestPerLTQASamplingDeterminism:
    def test_deterministic_across_repeated_calls(self):
        bridge = _import_bridge(PERLTQA_DIR)
        sample1 = _sample_perltqa(bridge, n=3)
        sample2 = _sample_perltqa(bridge, n=3)
        ids1 = [e["task"]["source_record_id"] for e in sample1]
        ids2 = [e["task"]["source_record_id"] for e in sample2]
        assert ids1 == ids2

    def test_excludes_profile_section_not_resolvable_from_source(self):
        """PerLTQA's own PROFILE-section tasks are marked
        evidence_memory_ids='NOT_RESOLVABLE_FROM_SOURCE' by the dataset's own
        normalization -- this is a dataset property, not this script's choice, and the
        sample must honestly exclude them rather than fabricate evidence."""
        bridge = _import_bridge(PERLTQA_DIR)
        sample = _sample_perltqa(bridge, n=3)
        for entry in sample:
            assert entry["task"]["section"] != "PROFILE"

    def test_every_sampled_task_has_non_empty_scoped_memory_pool(self):
        bridge = _import_bridge(PERLTQA_DIR)
        sample = _sample_perltqa(bridge, n=3)
        for entry in sample:
            assert len(entry["scoped_memories"]) > 0

    def test_chinese_text_preserved_verbatim_not_translated(self):
        """The question text must contain real CJK characters -- if it were silently
        translated to English, this would fail."""
        bridge = _import_bridge(PERLTQA_DIR)
        sample = _sample_perltqa(bridge, n=3)
        for entry in sample:
            question = entry["task"]["agent_visible"]["question"]
            assert any("一" <= ch <= "鿿" for ch in question), question

    def test_evidence_ids_use_native_character_scoped_encoding(self):
        """PerLTQA's evidence ids are the `PERLTQA<character>::...` encoding (per
        identity.py / the evaluation bridge), not a bare unscoped id -- confirms native
        evidence representation is preserved, not flattened or re-derived."""
        bridge = _import_bridge(PERLTQA_DIR)
        sample = _sample_perltqa(bridge, n=3)
        for entry in sample:
            for eid in entry["record"]["evidence_memory_ids"]:
                assert eid.startswith("PERLTQA<")

    def test_samples_cover_multiple_categories(self):
        bridge = _import_bridge(PERLTQA_DIR)
        sample = _sample_perltqa(bridge, n=3)
        categories = {e["category"] for e in sample}
        assert len(categories) >= 2


class TestConvoMemSamplingDeterminism:
    def test_deterministic_across_repeated_calls(self):
        bridge = _import_bridge(CONVOMEM_DIR)
        sample1 = _sample_convomem(bridge, n=3)
        sample2 = _sample_convomem(bridge, n=3)
        ids1 = [e["task"]["source_record_id"] for e in sample1]
        ids2 = [e["task"]["source_record_id"] for e in sample2]
        assert ids1 == ids2

    def test_only_fully_resolved_evidence_tasks_are_sampled(self):
        """Every location in every sampled task's evidence_resolution must be a
        genuinely resolved status -- tasks with any UNRESOLVED/AMBIGUOUS location are
        excluded from THIS evaluability-dependent pilot (not deleted from the corpus --
        see test_unresolved_records_remain_in_source_file below)."""
        bridge = _import_bridge(CONVOMEM_DIR)
        sample = _sample_convomem(bridge, n=3)
        for entry in sample:
            resolution = entry["task"]["evaluator_only"]["evidence_resolution"]
            assert all(loc["status"] in _RESOLVED_CONVOMEM_STATUSES for loc in resolution)

    def test_unresolved_records_remain_in_source_file(self):
        """The dataset's genuinely UNRESOLVED-evidence records (this stage's own
        investigation found 95 of them) must still be present in the raw normalized
        file -- never deleted merely because this pilot doesn't sample them."""
        bridge = _import_bridge(CONVOMEM_DIR)
        tasks, _ = bridge.load_evaluation_universe()
        unresolved_count = sum(
            1 for t in tasks
            if any(loc["status"] == "UNRESOLVED" for loc in t["evaluator_only"]["evidence_resolution"])
        )
        assert unresolved_count > 0  # confirms they are still there, not silently removed

    def test_evidence_ids_use_adapter_derived_identity_encoding(self):
        bridge = _import_bridge(CONVOMEM_DIR)
        sample = _sample_convomem(bridge, n=3)
        for entry in sample:
            for eid in entry["record"]["evidence_memory_ids"]:
                assert eid.startswith("CONVOMEM<")

    def test_samples_cover_multiple_categories(self):
        bridge = _import_bridge(CONVOMEM_DIR)
        sample = _sample_convomem(bridge, n=3)
        categories = {e["category"] for e in sample}
        assert len(categories) >= 2


class TestSafeCollectionName:
    """Regression coverage for the real Windows-filesystem-path bug found during this
    stage's own pilot run (a raw Chinese/`?`-containing task_id crashed Qdrant's local
    on-disk collection creation)."""

    def test_ascii_safe_output(self):
        name = _safe_collection_name("perltqa", "dialogues::李华::2_0_1#1::布朗运动实验给李华和李明有什么收获？")
        assert all(ord(c) < 128 for c in name)
        assert "?" not in name
        assert "::" not in name

    def test_deterministic(self):
        task_id = "some::task::id?"
        assert _safe_collection_name("ds", task_id) == _safe_collection_name("ds", task_id)

    def test_distinct_task_ids_produce_distinct_names(self):
        assert _safe_collection_name("ds", "task-1") != _safe_collection_name("ds", "task-2")
