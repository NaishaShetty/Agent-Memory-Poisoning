"""Phase 3.3-D tests for the DIRECT_ASSIGNMENT identity strategy (Graphiti, A-MEM) and
cross-foundation collision behavior, extending 3.3-C's identity bridge tests.

Test kinds:
- UNIT_TEST: `resolve_via_direct_assignment()` with hand-constructed `add_memory()`-shaped
  return values, no foundation at all.
- REAL_RUNTIME_TEST: exercised against `RealGraphitiAdapter` (in-process Kuzu, no
  external service) and `RealAMemAdapter` (real A-mem-sys + real sentence-transformers +
  real ChromaDB), both requiring the real libraries only importable under `C:\\h4venv`.
  Skips cleanly when unavailable, mirroring `test_identity_bridge.py`'s established
  pattern. NEVER reports a mock result as one of these.

Empirically established in this stage (verified directly against both real libraries,
never assumed): unlike Mem0, both Graphiti's `EntityNode` and A-mem-sys's `MemoryNote`
accept and HONOR a caller-supplied id -- `add_memory()`'s own
`requested_id_honored` field, already produced unmodified by both existing real
adapters, tells the truth about whether this happened for a given call.
"""

from __future__ import annotations

import pytest

from phase3.evaluation.agent_runtime.identity import (
    STATUS_NOT_RESOLVABLE,
    STATUS_RESOLVED,
    STRATEGY_DIRECT_ASSIGNMENT,
    STRATEGY_METADATA_LOOKUP,
    resolve_via_direct_assignment,
    verify_collision_safety,
)


class TestResolveViaDirectAssignmentUnit:
    def test_resolved_when_id_was_honored(self):
        resolution = resolve_via_direct_assignment(
            "loco-src-1", {"memory_id": "loco-src-1", "requested_id_honored": True}
        )
        assert resolution.status == STATUS_RESOLVED
        assert resolution.source_memory_id == "loco-src-1"
        assert resolution.foundation_memory_id == "loco-src-1"
        assert resolution.strategy == STRATEGY_DIRECT_ASSIGNMENT

    def test_not_resolvable_when_id_was_not_honored(self):
        """Never assume success -- if the foundation silently assigned its own id
        despite a request, this must report NOT_RESOLVABLE, not RESOLVED."""
        resolution = resolve_via_direct_assignment(
            "loco-src-1", {"memory_id": "some-other-uuid", "requested_id_honored": False}
        )
        assert resolution.status == STATUS_NOT_RESOLVABLE
        assert resolution.source_memory_id is None

    def test_not_resolvable_when_no_id_was_requested(self):
        resolution = resolve_via_direct_assignment(
            None, {"memory_id": "auto-assigned-uuid", "requested_id_honored": None}
        )
        assert resolution.status == STATUS_NOT_RESOLVABLE
        assert resolution.source_memory_id is None

    def test_no_foundation_call_is_made(self):
        """Structural guard: this function's signature takes only local values, no
        MemoryFoundationAdapter parameter -- it cannot possibly make a network/process
        call, unlike resolve_source_identity()."""
        import inspect

        sig = inspect.signature(resolve_via_direct_assignment)
        assert "foundation" not in sig.parameters

    def test_default_identity_resolution_strategy_is_metadata_lookup_for_backward_compat(self):
        """3.3-C's IdentityResolution instances (constructed without `strategy`) must
        keep defaulting to METADATA_LOOKUP -- this is the backward-compatibility
        guarantee the 3.3-D extension must preserve."""
        from phase3.evaluation.agent_runtime.identity import IdentityResolution

        r = IdentityResolution(
            foundation_memory_id="f1", adapter_memory_id=None, source_memory_id="s1",
            status=STATUS_RESOLVED,
        )
        assert r.strategy == STRATEGY_METADATA_LOOKUP


class TestCollisionSafetyAcrossStrategies:
    def test_collision_report_works_regardless_of_which_strategy_produced_the_resolutions(self):
        resolutions = {
            "f1": resolve_via_direct_assignment("src-A", {"memory_id": "f1", "requested_id_honored": True}),
            "f2": resolve_via_direct_assignment("src-A", {"memory_id": "f2", "requested_id_honored": True}),
        }
        report = verify_collision_safety(resolutions)
        assert report.collision_free is False
        assert "src-A" in report.duplicate_source_ids


class TestRealGraphitiIdentityBridge:
    """REAL_RUNTIME_TEST -- requires real `graphiti-core`/`kuzu` (only importable under
    `C:\\h4venv`). Run via:
        C:\\h4venv\\Scripts\\python.exe -m pytest phase3\\evaluation\\tests\\test_cross_foundation_identity.py -v
    """

    def _real_foundation(self):
        from phase3.evaluation.foundations_real.graphiti_real_adapter import RealGraphitiAdapter

        foundation = RealGraphitiAdapter()
        init_field = foundation.initialize({})
        if init_field.availability != "AVAILABLE":
            pytest.skip("graphiti-core/kuzu not importable in this interpreter -- REAL_RUNTIME_TEST skipped.")
        foundation.reset()
        return foundation

    def test_real_graphiti_honors_caller_supplied_id(self):
        foundation = self._real_foundation()
        add_result = foundation.add_memory(
            "real-graphiti-probe-src-1", {"name": "probe", "summary": "identity probe"}, {"group_id": "test"}
        )
        resolution = resolve_via_direct_assignment("real-graphiti-probe-src-1", add_result.value)
        assert resolution.status == STATUS_RESOLVED
        assert resolution.source_memory_id == "real-graphiti-probe-src-1"
        assert resolution.foundation_memory_id == "real-graphiti-probe-src-1"
        foundation.shutdown()

    def test_real_graphiti_reingest_without_reset_upserts_not_duplicates(self):
        """Documents a REAL, empirically-observed behavioral DIFFERENCE from Mem0:
        Graphiti's EntityNode.save() is an upsert keyed on uuid -- re-adding the same id
        silently OVERWRITES content in place rather than creating a second record. This
        must be reported honestly, not assumed identical to Mem0's duplication behavior."""
        foundation = self._real_foundation()
        r1 = foundation.add_memory("dup-src", {"name": "original", "summary": "original content"}, {"group_id": "t"})
        r2 = foundation.add_memory("dup-src", {"name": "overwritten", "summary": "new content"}, {"group_id": "t"})
        assert r1.value["memory_id"] == r2.value["memory_id"]  # SAME id, not a new one
        inspected = foundation.inspect_memory("dup-src")
        assert inspected.value["name"] == "overwritten"  # content was replaced in place
        foundation.shutdown()

    def test_real_graphiti_reset_provides_isolation(self):
        foundation = self._real_foundation()
        foundation.add_memory("iso-1", {"name": "round1", "summary": "x"}, {"group_id": "iso"})
        foundation.reset()
        gone = foundation.retrieve({"memory_id": "iso-1"})
        assert gone.availability == "UNAVAILABLE"
        foundation.shutdown()


class TestRealAMemIdentityBridge:
    """REAL_RUNTIME_TEST -- requires the real A-mem-sys source checkout + sentence-
    transformers + ChromaDB (only available under `C:\\h4venv`, per
    `foundations_real/environment.py::AMEM_SYS_SOURCE`)."""

    def _real_foundation(self):
        from phase3.evaluation.foundations_real.amem_real_adapter import RealAMemAdapter

        foundation = RealAMemAdapter()
        init_field = foundation.initialize({})
        if init_field.availability != "AVAILABLE":
            pytest.skip("A-mem-sys not importable in this interpreter -- REAL_RUNTIME_TEST skipped.")
        foundation.reset()
        return foundation

    def test_real_amem_honors_caller_supplied_id(self):
        foundation = self._real_foundation()
        add_result = foundation.add_memory(
            "real-amem-probe-src-1",
            {"text": "identity probe content"},
            {"tags": ["probe"], "keywords": ["probe"], "context": "probe"},
        )
        resolution = resolve_via_direct_assignment("real-amem-probe-src-1", add_result.value)
        assert resolution.status == STATUS_RESOLVED
        assert resolution.source_memory_id == "real-amem-probe-src-1"
        foundation.shutdown()

    def test_real_amem_reingest_without_reset_upserts_not_duplicates(self):
        """Same empirically-observed upsert behavior as Graphiti (both differ from
        Mem0's duplication) -- A-mem-sys's `.memories` store is dict-keyed by note id."""
        foundation = self._real_foundation()
        foundation.add_memory("dup-src", {"text": "original content"}, {"tags": ["a"], "keywords": ["a"], "context": "a"})
        store_size_after_first = len(foundation._mem.memories)
        foundation.add_memory("dup-src", {"text": "overwritten content"}, {"tags": ["b"], "keywords": ["b"], "context": "b"})
        store_size_after_second = len(foundation._mem.memories)
        assert store_size_after_first == store_size_after_second  # no new entry created
        inspected = foundation.inspect_memory("dup-src")
        assert inspected.value["tags"] == ["b"]  # content was replaced in place
        foundation.shutdown()

    def test_real_amem_reset_provides_isolation(self):
        foundation = self._real_foundation()
        foundation.add_memory("iso-1", {"text": "round1 unique-marker-zzz"}, {"tags": ["r1"], "keywords": ["zzz"], "context": "r1"})
        foundation.reset()
        assert len(foundation._mem.memories) == 0
        foundation.shutdown()

    def test_real_amem_retrieve_by_text_works_for_real(self):
        """Unlike Graphiti (semantic search is MODEL_DEPENDENT), A-mem-sys's retrieve()
        performs real ChromaDB cosine-similarity search over real local embeddings --
        no LLM involved, verified to actually find the right note by content."""
        foundation = self._real_foundation()
        foundation.add_memory(
            "amem-retrieve-probe", {"text": "The LGBTQ support group meeting was on 7 May 2023."},
            {"tags": ["locomo"], "keywords": ["support group"], "context": "probe"},
        )
        result = foundation.retrieve({"text": "support group"}, top_k=5)
        assert result.availability == "AVAILABLE"
        assert "amem-retrieve-probe" in result.value
        foundation.shutdown()
