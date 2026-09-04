"""Phase 3.3-H.1 (Canonical Memory Ledger) contract tests.

Covers the 20 test items and 8 invariants listed in the H.1 mission brief. Uses the
existing `Mock*Adapter` foundations (never the real ones -- no network/LLM/embeddings
dependency, and zero risk of touching the live 3.3-G.1 A-MEM campaign process) plus one
local `_FailingAdapter` fake to exercise the FOUNDATION_FAILED path deterministically.
"""

from __future__ import annotations

import json
from typing import Any, Mapping, Optional

import pytest

from phase3.evaluation.foundations.adapter import (
    FOUNDATION_UNAVAILABLE,
    FoundationField,
    FoundationIdentity,
    MemoryFoundationAdapter,
)
from phase3.evaluation.foundations.canonical import (
    CanonicalMemoryRecord,
    CanonicalValidationError,
    LIFECYCLE_ACTIVE,
    LIFECYCLE_CREATED,
    MEMORY_TYPE_DERIVED,
    MEMORY_TYPE_FOUNDATION,
    SOURCE_TYPE_PHASE2_UMR,
)
from phase3.evaluation.foundations.canonical_write import (
    STATUS_ALIAS_PERSISTENCE_FAILED,
    STATUS_CANONICAL_AND_FOUNDATION,
    STATUS_CANONICAL_ONLY,
    STATUS_FOUNDATION_FAILED,
    write_canonical_memory,
)
from phase3.evaluation.foundations.ledger import (
    CanonicalAliasError,
    CanonicalCollisionError,
    CanonicalMemoryLedger,
    PUT_CREATED,
    PUT_IDEMPOTENT,
)
from phase3.evaluation.foundations.mocks.mock_amem import MockAMemAdapter
from phase3.evaluation.foundations.mocks.mock_graphiti import MockGraphitiAdapter
from phase3.evaluation.foundations.mocks.mock_mem0 import MockMem0Adapter
from phase3.evaluation.foundations.security import FoundationBoundaryViolation


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _record(
    memory_id: str = "loco-mem-001",
    memory_type: str = MEMORY_TYPE_FOUNDATION,
    content: Optional[Mapping[str, Any]] = None,
    parent_ids=(),
    source: Optional[Mapping[str, Any]] = None,
) -> CanonicalMemoryRecord:
    return CanonicalMemoryRecord(
        memory_id=memory_id,
        memory_type=memory_type,
        content=content if content is not None else {"text": "user: I moved to Denver in 2019."},
        source=source if source is not None else {"source_type": SOURCE_TYPE_PHASE2_UMR, "reference_id": "umr-77"},
        parent_ids=tuple(parent_ids),
        creation_event="evt-001",
        creation_timestamp="2026-01-01T00:00:00Z",
        lifecycle_state=LIFECYCLE_CREATED,
    )


class _FailingAdapter(MemoryFoundationAdapter):
    """Local fake whose `add_memory` always reports FOUNDATION_UNAVAILABLE -- used to
    prove vendor-write failure is observable and never silently swallowed (invariant: a
    canonical record must survive a foundation failure)."""

    def foundation_identity(self) -> FoundationIdentity:
        return FoundationIdentity("failing", "Failing", "0.0.1", "PREPARED_CANDIDATE")

    def capabilities(self) -> Mapping[str, Any]:
        return {}

    def initialize(self, configuration: Mapping[str, Any]) -> FoundationField:
        return FoundationField(True, "AVAILABLE", "initialize")

    def reset(self) -> FoundationField:
        return FoundationField(True, "AVAILABLE", "reset")

    def add_memory(self, memory_id, content, metadata=None) -> FoundationField:
        return FoundationField(None, FOUNDATION_UNAVAILABLE, "add_memory", "simulated foundation outage")

    def retrieve(self, query, top_k=None) -> FoundationField:
        return FoundationField([], "AVAILABLE", "retrieve")

    def update_memory(self, memory_id, content, metadata=None) -> FoundationField:
        return FoundationField(None, FOUNDATION_UNAVAILABLE, "update_memory")

    def delete_memory(self, memory_id) -> FoundationField:
        return FoundationField(None, FOUNDATION_UNAVAILABLE, "delete_memory")

    def inspect_memory(self, memory_id) -> FoundationField:
        return FoundationField(None, FOUNDATION_UNAVAILABLE, "inspect_memory")

    def export_state(self) -> FoundationField:
        return FoundationField({}, "AVAILABLE", "export_state")

    def normalize_trace(self, operation_result: FoundationField) -> Mapping[str, Any]:
        return {}

    def shutdown(self) -> FoundationField:
        return FoundationField(True, "AVAILABLE", "shutdown")


class _NoIdAdapter(_FailingAdapter):
    """Reports AVAILABLE but returns a value shape with no extractable vendor id --
    exercises ALIAS_PERSISTENCE_FAILED without any real adapter behaving this way."""

    def add_memory(self, memory_id, content, metadata=None) -> FoundationField:
        return FoundationField({"unexpected_shape": True}, "AVAILABLE", "add_memory")


# ---------------------------------------------------------------------------
# 1. canonical record creation / 2. schema validation
# ---------------------------------------------------------------------------


def test_canonical_record_creation_valid():
    record = _record()
    assert record.memory_id == "loco-mem-001"
    assert record.memory_type == MEMORY_TYPE_FOUNDATION
    assert record.parent_ids == ()


@pytest.mark.parametrize(
    "kwargs,message_fragment",
    [
        ({"memory_id": ""}, "memory_id"),
        ({"memory_type": "bogus"}, "memory_type"),
        ({"source": {"source_type": "bogus"}}, "source_type"),
        ({"memory_type": MEMORY_TYPE_DERIVED, "parent_ids": ()}, "non-empty for memory_type=derived"),
        ({"memory_type": MEMORY_TYPE_FOUNDATION, "parent_ids": ("p1",)}, "empty for memory_type=foundation"),
    ],
)
def test_schema_validation_rejects_malformed_records(kwargs, message_fragment):
    base = dict(
        memory_id="x",
        memory_type=MEMORY_TYPE_FOUNDATION,
        content={"text": "hi"},
        source={"source_type": SOURCE_TYPE_PHASE2_UMR},
        parent_ids=(),
    )
    base.update(kwargs)
    with pytest.raises(CanonicalValidationError, match=message_fragment):
        CanonicalMemoryRecord(
            creation_event="evt",
            creation_timestamp="2026-01-01T00:00:00Z",
            lifecycle_state=LIFECYCLE_CREATED,
            **base,
        )


def test_derived_record_requires_parent_ids():
    record = _record(memory_id="derived-1", memory_type=MEMORY_TYPE_DERIVED, parent_ids=("loco-mem-001",))
    assert record.parent_ids == ("loco-mem-001",)


def test_invalid_timestamp_rejected():
    with pytest.raises(CanonicalValidationError):
        CanonicalMemoryRecord(
            memory_id="x",
            memory_type=MEMORY_TYPE_FOUNDATION,
            content={"text": "hi"},
            source={"source_type": SOURCE_TYPE_PHASE2_UMR},
            parent_ids=(),
            creation_event="evt",
            creation_timestamp="not-a-timestamp",
            lifecycle_state=LIFECYCLE_CREATED,
        )


# ---------------------------------------------------------------------------
# 3/4. canonical ID uniqueness / collision
# ---------------------------------------------------------------------------


def test_canonical_id_uniqueness_and_idempotent_rewrite(tmp_path):
    ledger = CanonicalMemoryLedger(tmp_path / "ledger")
    record = _record()
    assert ledger.put(record) == PUT_CREATED
    # Byte-identical rewrite -- documented idempotent behavior, not a silent overwrite of
    # different data.
    assert ledger.put(_record()) == PUT_IDEMPOTENT
    assert len(ledger.list_records()) == 1


def test_canonical_id_collision_fails_loudly(tmp_path):
    ledger = CanonicalMemoryLedger(tmp_path / "ledger")
    ledger.put(_record())
    colliding = _record(content={"text": "DIFFERENT CONTENT ENTIRELY"})
    with pytest.raises(CanonicalCollisionError):
        ledger.put(colliding)
    # The original record must survive the rejected collision untouched.
    assert ledger.get("loco-mem-001").content == {"text": "user: I moved to Denver in 2019."}


# ---------------------------------------------------------------------------
# 5/6. provenance preservation / exact content preservation
# ---------------------------------------------------------------------------


def test_provenance_and_content_preserved_exactly(tmp_path):
    ledger = CanonicalMemoryLedger(tmp_path / "ledger")
    record = _record(source={"source_type": SOURCE_TYPE_PHASE2_UMR, "reference_id": "umr-99", "dataset": "locomo"})
    ledger.put(record)
    fetched = ledger.get(record.memory_id)
    assert fetched.source == {"source_type": SOURCE_TYPE_PHASE2_UMR, "reference_id": "umr-99", "dataset": "locomo"}
    assert fetched.content == record.content


# ---------------------------------------------------------------------------
# 7/8/9. ledger persistence / reload / reconstruction
# ---------------------------------------------------------------------------


def test_ledger_persists_and_reloads_from_disk(tmp_path):
    storage_dir = tmp_path / "ledger"
    ledger1 = CanonicalMemoryLedger(storage_dir)
    ledger1.put(_record())
    ledger1.set_alias("loco-mem-001", "mem0", "vendor-uuid-123")

    ledger2 = CanonicalMemoryLedger(storage_dir)  # fresh instance, same directory
    reloaded = ledger2.get("loco-mem-001")
    assert reloaded is not None
    assert reloaded.content == {"text": "user: I moved to Denver in 2019."}
    assert ledger2.get_aliases("loco-mem-001") == {"mem0": "vendor-uuid-123"}


def test_records_and_aliases_are_valid_jsonl(tmp_path):
    storage_dir = tmp_path / "ledger"
    ledger = CanonicalMemoryLedger(storage_dir)
    ledger.put(_record())
    ledger.set_alias("loco-mem-001", "mem0", "vendor-uuid-123")
    for line in (storage_dir / "records.jsonl").read_text(encoding="utf-8").splitlines():
        json.loads(line)  # must not raise
    for line in (storage_dir / "aliases.jsonl").read_text(encoding="utf-8").splitlines():
        json.loads(line)


# ---------------------------------------------------------------------------
# 10/11/12. canonical <-> vendor alias mapping, multiple foundations
# ---------------------------------------------------------------------------


def test_alias_mapping_both_directions(tmp_path):
    ledger = CanonicalMemoryLedger(tmp_path / "ledger")
    ledger.put(_record())
    ledger.set_alias("loco-mem-001", "mem0", "vendor-uuid-123")
    assert ledger.get_aliases("loco-mem-001") == {"mem0": "vendor-uuid-123"}
    assert ledger.resolve_alias("mem0", "vendor-uuid-123") == "loco-mem-001"
    assert ledger.resolve_alias("mem0", "unknown-id") is None


def test_multiple_foundations_share_one_canonical_identity(tmp_path):
    ledger = CanonicalMemoryLedger(tmp_path / "ledger")
    ledger.put(_record())
    ledger.set_alias("loco-mem-001", "mem0", "mem0-uuid")
    ledger.set_alias("loco-mem-001", "a-mem", "amem-note-id")
    ledger.set_alias("loco-mem-001", "graphiti", "graphiti-episode-id")
    assert ledger.get_aliases("loco-mem-001") == {
        "mem0": "mem0-uuid",
        "a-mem": "amem-note-id",
        "graphiti": "graphiti-episode-id",
    }
    assert ledger.resolve_alias("a-mem", "amem-note-id") == "loco-mem-001"


def test_alias_requires_existing_canonical_record(tmp_path):
    ledger = CanonicalMemoryLedger(tmp_path / "ledger")
    with pytest.raises(CanonicalAliasError):
        ledger.set_alias("nonexistent", "mem0", "vendor-uuid")


# ---------------------------------------------------------------------------
# 13/14/15. vendor id is never the canonical identity; canonical survives vendor
# failure; vendor failure is explicitly observable
# ---------------------------------------------------------------------------


def test_vendor_generated_id_cannot_replace_canonical_id(tmp_path):
    ledger = CanonicalMemoryLedger(tmp_path / "ledger")
    foundation = MockMem0Adapter()
    foundation.initialize({})
    record = _record()
    result = write_canonical_memory(ledger, record, foundation=foundation, foundation_name="mem0")
    assert result.status == STATUS_CANONICAL_AND_FOUNDATION
    # The canonical identity is untouched by whatever the vendor returned.
    assert ledger.get(record.memory_id).memory_id == record.memory_id
    assert result.foundation_memory_id == record.memory_id  # MockMem0Adapter honors the id
    # But even if it hadn't, the vendor id would only ever live in the alias table:
    assert ledger.resolve_alias("mem0", result.foundation_memory_id) == record.memory_id


def test_canonical_record_survives_vendor_failure(tmp_path):
    ledger = CanonicalMemoryLedger(tmp_path / "ledger")
    record = _record()
    result = write_canonical_memory(ledger, record, foundation=_FailingAdapter(), foundation_name="failing")
    assert result.status == STATUS_FOUNDATION_FAILED
    # Canonical record persisted despite the foundation outage.
    assert ledger.exists(record.memory_id)
    assert ledger.get(record.memory_id).content == record.content


def test_vendor_failure_is_explicitly_observable(tmp_path):
    ledger = CanonicalMemoryLedger(tmp_path / "ledger")
    result = write_canonical_memory(ledger, _record(), foundation=_FailingAdapter(), foundation_name="failing")
    assert result.status == STATUS_FOUNDATION_FAILED
    assert "simulated foundation outage" in result.note
    assert result.foundation_memory_id is None


def test_alias_persistence_failed_when_vendor_id_not_extractable(tmp_path):
    ledger = CanonicalMemoryLedger(tmp_path / "ledger")
    result = write_canonical_memory(ledger, _record(), foundation=_NoIdAdapter(), foundation_name="no-id")
    assert result.status == STATUS_ALIAS_PERSISTENCE_FAILED
    assert ledger.exists("loco-mem-001")
    assert ledger.get_aliases("loco-mem-001") == {}


def test_canonical_only_write_when_no_foundation_supplied(tmp_path):
    ledger = CanonicalMemoryLedger(tmp_path / "ledger")
    result = write_canonical_memory(ledger, _record(), foundation=None)
    assert result.status == STATUS_CANONICAL_ONLY
    assert ledger.exists("loco-mem-001")


def test_collision_is_never_swallowed_by_write_canonical_memory(tmp_path):
    ledger = CanonicalMemoryLedger(tmp_path / "ledger")
    write_canonical_memory(ledger, _record(), foundation=None)
    with pytest.raises(CanonicalCollisionError):
        write_canonical_memory(ledger, _record(content={"text": "different"}), foundation=None)


# ---------------------------------------------------------------------------
# 16/17/18. reconstruction does not require vendor inspection, per foundation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "foundation_factory,foundation_name",
    [
        (MockMem0Adapter, "mem0"),
        (MockAMemAdapter, "a-mem"),
        (MockGraphitiAdapter, "graphiti"),
    ],
)
def test_reconstruction_independent_of_vendor_inspection(tmp_path, foundation_factory, foundation_name):
    ledger = CanonicalMemoryLedger(tmp_path / f"ledger-{foundation_name}")
    foundation = foundation_factory()
    foundation.initialize({})
    record = _record(
        content={"text": "user: I moved to Denver in 2019."} if foundation_name != "graphiti"
        else {"entities": [{"name": "Denver"}], "relationships": []},
    )
    result = write_canonical_memory(ledger, record, foundation=foundation, foundation_name=foundation_name)
    assert result.status == STATUS_CANONICAL_AND_FOUNDATION

    # Blow away the vendor's own state entirely (simulates the vendor being completely
    # unavailable / A-MEM's known content-loss-on-inspect finding from the audit) --
    # canonical reconstruction must not care. After reset(), the vendor genuinely has
    # nothing left to inspect for this id (never AVAILABLE with real content).
    foundation.reset()
    post_reset_inspect = foundation.inspect_memory(result.foundation_memory_id)
    assert post_reset_inspect.value is None

    reconstructed = ledger.get(record.memory_id)
    assert reconstructed is not None
    assert reconstructed.content == record.content
    assert reconstructed.source == record.source


# ---------------------------------------------------------------------------
# 19/20. no evaluator/gold data can enter the canonical record; leakage checks pass
# ---------------------------------------------------------------------------


def test_no_evaluator_gold_data_can_enter_canonical_record():
    with pytest.raises(FoundationBoundaryViolation):
        CanonicalMemoryRecord(
            memory_id="x",
            memory_type=MEMORY_TYPE_FOUNDATION,
            content={"text": "hi", "gold_evidence_ids": ["a", "b"]},
            source={"source_type": SOURCE_TYPE_PHASE2_UMR},
            parent_ids=(),
            creation_event="evt",
            creation_timestamp="2026-01-01T00:00:00Z",
            lifecycle_state=LIFECYCLE_CREATED,
        )


def test_clean_canonical_record_passes_leakage_checks():
    # A well-formed record (no evaluator-only keys) must construct without raising --
    # the boundary check must not be over-eager.
    record = _record()
    assert record.content == {"text": "user: I moved to Denver in 2019."}


# ---------------------------------------------------------------------------
# Serialization round trip (supports invariants 1/2/3 by construction)
# ---------------------------------------------------------------------------


def test_to_dict_from_dict_round_trip():
    record = _record()
    assert CanonicalMemoryRecord.from_dict(record.to_dict()) == record


def test_identity_fields_distinguish_identical_from_different():
    a = _record()
    b = _record()
    c = _record(content={"text": "different"})
    assert a.identity_fields() == b.identity_fields()
    assert a.identity_fields() != c.identity_fields()
