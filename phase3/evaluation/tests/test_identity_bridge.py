"""Phase 3.3-C tests for `phase3.evaluation.agent_runtime.identity`.

Test kinds:
- UNIT_TEST: pure functions (`verify_collision_safety`) with hand-constructed
  `IdentityResolution` objects, no foundation at all.
- INTEGRATION_TEST: `resolve_source_identity`/`resolve_source_identities` exercised
  against `MockMem0Adapter` (an existing Phase 3.2 deterministic test double) -- proves
  the identity-bridge code path works against the real `MemoryFoundationAdapter`
  interface, without requiring the real `mem0ai` library.
- REAL_RUNTIME_TEST: the SAME resolution logic exercised against `RealMem0Adapter`
  backed by the real, installed `mem0ai` library. Only runs where `mem0ai` is importable
  (`C:\\h4venv`, per `foundations_real/environment.py`) -- `pytest.skip()`s with an
  explicit reason everywhere else, mirroring `test_foundation_conformance_h4.py`'s own
  established skip pattern. NEVER reports a mock/integration result as this.
"""

from __future__ import annotations

import pytest

from phase3.evaluation.agent_runtime.identity import (
    STATUS_INSPECT_UNAVAILABLE,
    STATUS_NOT_RESOLVABLE,
    STATUS_RESOLVED,
    IdentityResolution,
    resolve_source_identities,
    resolve_source_identity,
    verify_collision_safety,
)
from phase3.evaluation.foundations.mocks.mock_mem0 import MockMem0Adapter


class TestIdentityResolutionInvariants:
    """UNIT_TEST -- the dataclass's own __post_init__ guards."""

    def test_resolved_requires_non_none_source_id(self):
        with pytest.raises(ValueError):
            IdentityResolution(
                foundation_memory_id="f1", adapter_memory_id=None, source_memory_id=None,
                status=STATUS_RESOLVED,
            )

    def test_not_resolvable_forbids_a_source_id_value(self):
        with pytest.raises(ValueError):
            IdentityResolution(
                foundation_memory_id="f1", adapter_memory_id=None, source_memory_id="sneaky",
                status=STATUS_NOT_RESOLVABLE,
            )

    def test_rejects_unknown_status(self):
        with pytest.raises(ValueError):
            IdentityResolution(
                foundation_memory_id="f1", adapter_memory_id=None, source_memory_id=None,
                status="MADE_UP_STATUS",
            )


class TestCollisionSafetyUnit:
    """UNIT_TEST -- pure function, hand-constructed resolutions, no foundation."""

    def _resolved(self, fid: str, source_id: str) -> IdentityResolution:
        return IdentityResolution(
            foundation_memory_id=fid, adapter_memory_id=None, source_memory_id=source_id,
            status=STATUS_RESOLVED,
        )

    def _unresolved(self, fid: str) -> IdentityResolution:
        return IdentityResolution(
            foundation_memory_id=fid, adapter_memory_id=None, source_memory_id=None,
            status=STATUS_NOT_RESOLVABLE,
        )

    def test_no_collision_when_all_source_ids_distinct(self):
        resolutions = {"f1": self._resolved("f1", "s1"), "f2": self._resolved("f2", "s2")}
        report = verify_collision_safety(resolutions)
        assert report.collision_free is True
        assert report.duplicate_source_ids == {}
        assert report.resolved_count == 2

    def test_collision_detected_when_two_foundation_ids_share_a_source_id(self):
        """Reproduces the real, observed Mem0 behavior: re-ingesting the same source
        record without a RESET creates a second, distinct foundation record -- this must
        be REPORTED, not silently collapsed or deleted."""
        resolutions = {
            "f1": self._resolved("f1", "s1"),
            "f2": self._resolved("f2", "s1"),  # same source id, different foundation id
            "f3": self._resolved("f3", "s2"),
        }
        report = verify_collision_safety(resolutions)
        assert report.collision_free is False
        assert report.duplicate_source_ids == {"s1": ("f1", "f2")}
        assert report.resolved_count == 3

    def test_not_resolvable_and_inspect_unavailable_counted_separately_not_as_collisions(self):
        resolutions = {
            "f1": self._resolved("f1", "s1"),
            "f2": self._unresolved("f2"),
            "f3": IdentityResolution(
                foundation_memory_id="f3", adapter_memory_id=None, source_memory_id=None,
                status=STATUS_INSPECT_UNAVAILABLE,
            ),
        }
        report = verify_collision_safety(resolutions)
        assert report.collision_free is True
        assert report.resolved_count == 1
        assert report.not_resolvable_count == 1
        assert report.inspect_unavailable_count == 1

    def test_no_records_never_fabricates_a_false_collision(self):
        report = verify_collision_safety({})
        assert report.collision_free is True
        assert report.duplicate_source_ids == {}


class TestResolveSourceIdentityIntegration:
    """INTEGRATION_TEST -- MockMem0Adapter, no real mem0ai required."""

    def _foundation(self) -> MockMem0Adapter:
        f = MockMem0Adapter()
        f.initialize({})
        return f

    def test_resolves_when_metadata_present(self):
        foundation = self._foundation()
        foundation.add_memory("m1", {"text": "some content"}, {"source_memory_id": "loco-abc123"})
        resolution = resolve_source_identity(foundation, "m1", adapter_memory_id="m1")
        assert resolution.status == STATUS_RESOLVED
        assert resolution.source_memory_id == "loco-abc123"
        assert resolution.adapter_memory_id == "m1"

    def test_not_resolvable_when_metadata_key_absent(self):
        """No fabrication: absent metadata key -> NOT_RESOLVABLE, never a guessed id,
        never the foundation id echoed back as a stand-in."""
        foundation = self._foundation()
        foundation.add_memory("m2", {"text": "some content"}, {"user_id": "u1"})
        resolution = resolve_source_identity(foundation, "m2")
        assert resolution.status == STATUS_NOT_RESOLVABLE
        assert resolution.source_memory_id is None

    def test_not_resolvable_when_no_metadata_at_all(self):
        foundation = self._foundation()
        foundation.add_memory("m3", {"text": "some content"}, None)
        resolution = resolve_source_identity(foundation, "m3")
        assert resolution.status == STATUS_NOT_RESOLVABLE
        assert resolution.source_memory_id is None

    def test_inspect_unavailable_for_nonexistent_id(self):
        foundation = self._foundation()
        resolution = resolve_source_identity(foundation, "does-not-exist")
        assert resolution.status == STATUS_INSPECT_UNAVAILABLE

    def test_batch_resolution_is_per_id_independent(self):
        foundation = self._foundation()
        foundation.add_memory("m1", {"text": "a"}, {"source_memory_id": "src-1"})
        foundation.add_memory("m2", {"text": "b"}, None)
        resolutions = resolve_source_identities(foundation, ["m1", "m2", "missing"])
        assert resolutions["m1"].status == STATUS_RESOLVED
        assert resolutions["m1"].source_memory_id == "src-1"
        assert resolutions["m2"].status == STATUS_NOT_RESOLVABLE
        assert resolutions["missing"].status == STATUS_INSPECT_UNAVAILABLE

    def test_never_uses_content_similarity_to_resolve(self):
        """Two memories with textually IDENTICAL content but different (or absent)
        source_memory_id metadata must never be confused -- resolution is metadata-key
        based only."""
        foundation = self._foundation()
        foundation.add_memory("m1", {"text": "identical content"}, {"source_memory_id": "src-1"})
        foundation.add_memory("m2", {"text": "identical content"}, {"source_memory_id": "src-2"})
        r1 = resolve_source_identity(foundation, "m1")
        r2 = resolve_source_identity(foundation, "m2")
        assert r1.source_memory_id == "src-1"
        assert r2.source_memory_id == "src-2"
        report = verify_collision_safety({"m1": r1, "m2": r2})
        assert report.collision_free is True  # distinct source ids, despite identical content


class TestRealMem0IdentityBridge:
    """REAL_RUNTIME_TEST -- requires the real `mem0ai` library (only importable under
    `C:\\h4venv`). Run via:

        C:\\h4venv\\Scripts\\python.exe -m pytest phase3\\evaluation\\tests\\test_identity_bridge.py -v

    Skips cleanly (not a failure) when `mem0ai` is not importable in the running
    interpreter.
    """

    def _real_foundation(self):
        from phase3.evaluation.foundations_real.mem0_real_adapter import RealMem0Adapter

        foundation = RealMem0Adapter()
        init_field = foundation.initialize({"collection_name": "test_identity_bridge_3_3c"})
        if init_field.availability != "AVAILABLE":
            pytest.skip("mem0ai not importable in this interpreter -- REAL_RUNTIME_TEST skipped.")
        foundation.reset()
        return foundation

    def test_real_mem0_resolves_explicit_source_metadata(self):
        foundation = self._real_foundation()
        add_result = foundation.add_memory(
            None, {"text": "Real Mem0 identity probe."}, {"source_memory_id": "real-probe-src-1"}
        )
        fid = add_result.value["memory_id"]
        resolution = resolve_source_identity(foundation, fid)
        assert resolution.status == STATUS_RESOLVED
        assert resolution.source_memory_id == "real-probe-src-1"
        foundation.shutdown()

    def test_real_mem0_reports_not_resolvable_without_metadata(self):
        foundation = self._real_foundation()
        add_result = foundation.add_memory(None, {"text": "No source id supplied."}, None)
        fid = add_result.value["memory_id"]
        resolution = resolve_source_identity(foundation, fid)
        assert resolution.status == STATUS_NOT_RESOLVABLE
        foundation.shutdown()

    def test_real_mem0_distinct_source_ids_do_not_collide(self):
        foundation = self._real_foundation()
        r1 = foundation.add_memory(None, {"text": "Turn A"}, {"source_memory_id": "src-AAA"})
        r2 = foundation.add_memory(None, {"text": "Turn B"}, {"source_memory_id": "src-BBB"})
        resolutions = resolve_source_identities(
            foundation, [r1.value["memory_id"], r2.value["memory_id"]]
        )
        report = verify_collision_safety(resolutions)
        assert report.collision_free is True
        assert report.resolved_count == 2
        foundation.shutdown()

    def test_real_mem0_reingesting_same_source_id_without_reset_creates_a_collision(self):
        """Documents the real, observed limitation: Mem0's real add() does not
        deduplicate, so this IS a genuine collision the bridge must detect, never hide."""
        foundation = self._real_foundation()
        r1 = foundation.add_memory(None, {"text": "Same content"}, {"source_memory_id": "src-DUP"})
        r2 = foundation.add_memory(None, {"text": "Same content"}, {"source_memory_id": "src-DUP"})
        assert r1.value["memory_id"] != r2.value["memory_id"]  # distinct foundation ids
        resolutions = resolve_source_identities(
            foundation, [r1.value["memory_id"], r2.value["memory_id"]]
        )
        report = verify_collision_safety(resolutions)
        assert report.collision_free is False
        assert "src-DUP" in report.duplicate_source_ids
        foundation.shutdown()
