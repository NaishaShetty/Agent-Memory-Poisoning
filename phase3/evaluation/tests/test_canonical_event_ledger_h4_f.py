"""Phase 3.3-H.4-F (Configuration Fingerprinting) contract tests.

Covers every invariant in section 8 and every adversarial case in section 9 of
PHASE3_3_H4_F_MISSION.md. Uses H.1's `CanonicalMemoryLedger`, H.2/H.4-BC's
`CanonicalEventLedger`, and this stage's own `RunConfigRecord`/`RunConfigLedger` directly --
no foundation/vendor dependency anywhere in this file.
"""

from __future__ import annotations

import pytest

from phase3.evaluation.foundations.canonical import (
    CanonicalMemoryRecord,
    LIFECYCLE_CREATED,
    MEMORY_TYPE_FOUNDATION,
    SOURCE_TYPE_PHASE2_UMR,
)
from phase3.evaluation.foundations.canonical_event import (
    CanonicalEvent,
    CanonicalEventValidationError,
    EVENT_CREATED,
    EVENT_REJECTED,
    EVENT_RELATIONSHIP_DETECTED,
    EVENT_RETIRED,
    EVENT_RETRIEVED,
    EVENT_SELECTED,
    EVENT_SUPERSEDED,
    EVENT_USED,
    REJECTED_REASON_BELOW_RERANK_THRESHOLD,
    RELATIONSHIP_EQUIVALENT_TO,
)
from phase3.evaluation.foundations.event_ledger import (
    APPEND_CREATED,
    APPEND_IDEMPOTENT,
    CanonicalEventLedger,
    UnknownConfigFingerprintError,
    check_config_resolution,
)
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger
from phase3.evaluation.foundations.run_config import (
    APPEND_CREATED as CFG_APPEND_CREATED,
    APPEND_IDEMPOTENT as CFG_APPEND_IDEMPOTENT,
    RunConfigCollisionError,
    RunConfigLedger,
    RunConfigRecord,
    RunConfigValidationError,
    compute_config_fingerprint,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _memory_record(memory_id: str = "loco-mem-001") -> CanonicalMemoryRecord:
    return CanonicalMemoryRecord(
        memory_id=memory_id,
        memory_type=MEMORY_TYPE_FOUNDATION,
        content={"text": f"user fact for {memory_id}."},
        source={"source_type": SOURCE_TYPE_PHASE2_UMR, "reference_id": "umr-77"},
        parent_ids=(),
        creation_event="evt-seed",
        creation_timestamp="2026-01-01T00:00:00Z",
        lifecycle_state=LIFECYCLE_CREATED,
    )


def _config_record(
    embedding_model="text-embedding-3-large",
    embedding_model_revision="v1",
    retrieval_k=10,
    retrieval_mechanism="dense_knn",
    selection_mechanism="rerank_topk",
    adapter_revision="mem0-adapter@abc123",
    reranker_model=None,
    reranker_model_revision=None,
    sampling_seed=None,
    created_at="2026-01-01T00:00:00Z",
) -> RunConfigRecord:
    fp = compute_config_fingerprint(
        embedding_model=embedding_model,
        embedding_model_revision=embedding_model_revision,
        retrieval_k=retrieval_k,
        retrieval_mechanism=retrieval_mechanism,
        selection_mechanism=selection_mechanism,
        adapter_revision=adapter_revision,
        reranker_model=reranker_model,
        reranker_model_revision=reranker_model_revision,
        sampling_seed=sampling_seed,
    )
    return RunConfigRecord(
        config_fingerprint=fp,
        embedding_model=embedding_model,
        embedding_model_revision=embedding_model_revision,
        retrieval_k=retrieval_k,
        retrieval_mechanism=retrieval_mechanism,
        selection_mechanism=selection_mechanism,
        adapter_revision=adapter_revision,
        created_at=created_at,
        reranker_model=reranker_model,
        reranker_model_revision=reranker_model_revision,
        sampling_seed=sampling_seed,
    )


def _memory_and_event_ledgers(tmp_path, config_ledger=None, memory_ids=("loco-mem-001",)):
    memory_ledger = CanonicalMemoryLedger(tmp_path / "memory-ledger")
    for mid in memory_ids:
        memory_ledger.put(_memory_record(mid))
    event_ledger = CanonicalEventLedger(tmp_path / "event-ledger", memory_ledger, config_ledger=config_ledger)
    return memory_ledger, event_ledger


def _retrieved_event(event_id, memory_id, config_fingerprint, task_id="task-1") -> CanonicalEvent:
    return CanonicalEvent(
        event_id=event_id,
        event_type=EVENT_RETRIEVED,
        memory_ids=(memory_id,),
        task_id=task_id,
        timestamp="2026-01-01T00:05:00Z",
        actor="candidate_discovery",
        reason="matched query embedding.",
        config_fingerprint=config_fingerprint,
    )


def _selected_event(event_id, memory_id, config_fingerprint, task_id="task-1") -> CanonicalEvent:
    return CanonicalEvent(
        event_id=event_id,
        event_type=EVENT_SELECTED,
        memory_ids=(memory_id,),
        task_id=task_id,
        timestamp="2026-01-01T00:06:00Z",
        actor="evidence_selection",
        reason="selected for reasoning context.",
        config_fingerprint=config_fingerprint,
    )


# ---------------------------------------------------------------------------
# Section 8, item 1: deterministic fingerprint derivation
# ---------------------------------------------------------------------------


def test_fingerprint_deterministic_for_identical_fields():
    a = _config_record()
    b = _config_record()
    assert a.config_fingerprint == b.config_fingerprint


def test_fingerprint_changes_when_any_field_changes():
    base = _config_record()
    variants = [
        _config_record(embedding_model="different-model"),
        _config_record(embedding_model_revision="v2"),
        _config_record(retrieval_k=20),
        _config_record(retrieval_mechanism="bm25"),
        _config_record(selection_mechanism="threshold_filter"),
        _config_record(adapter_revision="mem0-adapter@def456"),
    ]
    for variant in variants:
        assert variant.config_fingerprint != base.config_fingerprint


def test_created_at_does_not_affect_fingerprint():
    a = _config_record(created_at="2026-01-01T00:00:00Z")
    b = _config_record(created_at="2026-06-01T00:00:00Z")
    assert a.config_fingerprint == b.config_fingerprint


# ---------------------------------------------------------------------------
# Section 8, item 2: RunConfigRecord is an immutable dataclass
# ---------------------------------------------------------------------------


def test_run_config_record_is_frozen():
    record = _config_record()
    with pytest.raises(Exception):
        record.embedding_model = "mutated"


# ---------------------------------------------------------------------------
# Section 8, item 3: RunConfigLedger is append-only
# ---------------------------------------------------------------------------


def test_run_config_ledger_has_no_update_or_delete_api(tmp_path):
    config_ledger = RunConfigLedger(tmp_path / "config-ledger")
    assert not hasattr(config_ledger, "update")
    assert not hasattr(config_ledger, "delete")
    assert not hasattr(config_ledger, "update_record")
    assert not hasattr(config_ledger, "delete_record")


# ---------------------------------------------------------------------------
# Section 8, item 4/5: config_fingerprint required for retrieved/selected, forbidden
# elsewhere
# ---------------------------------------------------------------------------


def test_retrieved_requires_config_fingerprint():
    with pytest.raises(CanonicalEventValidationError, match="config_fingerprint"):
        CanonicalEvent(
            event_id="evt-r-no-cfg",
            event_type=EVENT_RETRIEVED,
            memory_ids=("loco-mem-001",),
            task_id="task-1",
            timestamp="2026-01-01T00:05:00Z",
            actor="candidate_discovery",
            reason="matched query embedding.",
        )


def test_selected_requires_config_fingerprint():
    with pytest.raises(CanonicalEventValidationError, match="config_fingerprint"):
        CanonicalEvent(
            event_id="evt-s-no-cfg",
            event_type=EVENT_SELECTED,
            memory_ids=("loco-mem-001",),
            task_id="task-1",
            timestamp="2026-01-01T00:06:00Z",
            actor="evidence_selection",
            reason="selected for reasoning context.",
            config_fingerprint="",
        )


@pytest.mark.parametrize(
    "event_type,extra_kwargs",
    [
        (EVENT_CREATED, {"new_state": LIFECYCLE_CREATED}),
        (EVENT_USED, {"task_id": "task-1"}),
        (EVENT_REJECTED, {"task_id": "task-1", "reason": REJECTED_REASON_BELOW_RERANK_THRESHOLD}),
    ],
)
def test_config_fingerprint_forbidden_on_non_retrieval_selection_events(event_type, extra_kwargs):
    kwargs = dict(
        event_id="evt-bad-cfg",
        event_type=event_type,
        memory_ids=("loco-mem-001",),
        timestamp="2026-01-01T00:00:00Z",
        actor="creation_policy",
        reason="ingested.",
        config_fingerprint="CFG-should-not-be-here",
    )
    kwargs.update(extra_kwargs)
    with pytest.raises(CanonicalEventValidationError, match="config_fingerprint"):
        CanonicalEvent(**kwargs)


def test_config_fingerprint_forbidden_on_relationship_detected():
    with pytest.raises(CanonicalEventValidationError, match="config_fingerprint"):
        CanonicalEvent(
            event_id="evt-rel-bad-cfg",
            event_type=EVENT_RELATIONSHIP_DETECTED,
            memory_ids=("loco-mem-001", "loco-mem-002"),
            timestamp="2026-01-01T00:00:00Z",
            actor="creation_policy",
            reason="detected.",
            relationship_type=RELATIONSHIP_EQUIVALENT_TO,
            mechanism="embedding_similarity_threshold",
            config_fingerprint="CFG-should-not-be-here",
        )


# ---------------------------------------------------------------------------
# Section 8, item 6: eager resolution when config_ledger is supplied
# ---------------------------------------------------------------------------


def test_append_succeeds_when_config_fingerprint_resolves(tmp_path):
    config_ledger = RunConfigLedger(tmp_path / "config-ledger")
    config = _config_record()
    config_ledger.append(config)
    _, event_ledger = _memory_and_event_ledgers(tmp_path, config_ledger=config_ledger)
    event = _retrieved_event("evt-r1", "loco-mem-001", config.config_fingerprint)
    assert event_ledger.append(event) == APPEND_CREATED


def test_append_raises_unknown_config_fingerprint_when_supplied_ledger_lacks_it(tmp_path):
    config_ledger = RunConfigLedger(tmp_path / "config-ledger")
    _, event_ledger = _memory_and_event_ledgers(tmp_path, config_ledger=config_ledger)
    event = _retrieved_event("evt-r1", "loco-mem-001", "CFG-does-not-exist")
    with pytest.raises(UnknownConfigFingerprintError):
        event_ledger.append(event)
    assert event_ledger.get_event("evt-r1") is None


# ---------------------------------------------------------------------------
# Section 8, item 7: deferred resolution when config_ledger is NOT supplied
# ---------------------------------------------------------------------------


def test_append_succeeds_without_config_ledger_even_for_unresolvable_fingerprint(tmp_path):
    _, event_ledger = _memory_and_event_ledgers(tmp_path, config_ledger=None)
    event = _retrieved_event("evt-r1", "loco-mem-001", "CFG-does-not-exist")
    assert event_ledger.append(event) == APPEND_CREATED


def test_check_config_resolution_reports_unresolvable_fingerprint(tmp_path):
    _, event_ledger = _memory_and_event_ledgers(tmp_path, config_ledger=None)
    event_ledger.append(_retrieved_event("evt-r1", "loco-mem-001", "CFG-does-not-exist"))
    config_ledger = RunConfigLedger(tmp_path / "config-ledger")
    violations = check_config_resolution(event_ledger, config_ledger)
    assert [e.event_id for e in violations] == ["evt-r1"]


def test_check_config_resolution_reports_nothing_when_all_resolve(tmp_path):
    config_ledger = RunConfigLedger(tmp_path / "config-ledger")
    config = _config_record()
    config_ledger.append(config)
    _, event_ledger = _memory_and_event_ledgers(tmp_path, config_ledger=None)
    event_ledger.append(_retrieved_event("evt-r1", "loco-mem-001", config.config_fingerprint))
    assert check_config_resolution(event_ledger, config_ledger) == []


def test_check_config_resolution_ignores_non_retrieval_selection_events(tmp_path):
    _, event_ledger = _memory_and_event_ledgers(tmp_path, config_ledger=None)
    event_ledger.append(
        CanonicalEvent(
            event_id="evt-created",
            event_type=EVENT_CREATED,
            memory_ids=("loco-mem-001",),
            timestamp="2026-01-01T00:00:00Z",
            actor="creation_policy",
            reason="ingested.",
            new_state=LIFECYCLE_CREATED,
        )
    )
    config_ledger = RunConfigLedger(tmp_path / "config-ledger")
    assert check_config_resolution(event_ledger, config_ledger) == []


# ---------------------------------------------------------------------------
# Section 8, item 8: serialization round trip
# ---------------------------------------------------------------------------


def test_to_dict_from_dict_round_trip_for_retrieved_with_config_fingerprint():
    event = _retrieved_event("evt-r1", "loco-mem-001", "CFG-abc")
    assert CanonicalEvent.from_dict(event.to_dict()) == event
    assert event.to_dict()["config_fingerprint"] == "CFG-abc"


def test_to_dict_omits_config_fingerprint_for_other_event_types():
    event = CanonicalEvent(
        event_id="evt-created",
        event_type=EVENT_CREATED,
        memory_ids=("loco-mem-001",),
        timestamp="2026-01-01T00:00:00Z",
        actor="creation_policy",
        reason="ingested.",
        new_state=LIFECYCLE_CREATED,
    )
    assert event.to_dict()["config_fingerprint"] is None


def test_identity_fields_include_config_fingerprint():
    a = _retrieved_event("evt-r1", "loco-mem-001", "CFG-abc")
    b = _retrieved_event("evt-r1", "loco-mem-001", "CFG-abc")
    assert a.identity_fields() == b.identity_fields()


# ---------------------------------------------------------------------------
# Section 8, item 9: two events referencing the same fingerprint resolve identically
# ---------------------------------------------------------------------------


def test_two_events_same_fingerprint_resolve_to_bit_identical_config(tmp_path):
    config_ledger = RunConfigLedger(tmp_path / "config-ledger")
    config = _config_record()
    config_ledger.append(config)
    _, event_ledger = _memory_and_event_ledgers(
        tmp_path, config_ledger=config_ledger, memory_ids=("loco-mem-001", "loco-mem-002")
    )
    event_ledger.append(_retrieved_event("evt-r1", "loco-mem-001", config.config_fingerprint))
    event_ledger.append(_retrieved_event("evt-r2", "loco-mem-002", config.config_fingerprint))
    resolved_1 = config_ledger.get(event_ledger.get_event("evt-r1").config_fingerprint)
    resolved_2 = config_ledger.get(event_ledger.get_event("evt-r2").config_fingerprint)
    assert resolved_1 == resolved_2
    assert resolved_1.to_dict() == config.to_dict()


# ---------------------------------------------------------------------------
# Section 9, item 1: reranker_model set without reranker_model_revision
# ---------------------------------------------------------------------------


def test_reranker_model_without_revision_is_rejected():
    with pytest.raises(RunConfigValidationError, match="reranker_model_revision"):
        _config_record(reranker_model="cross-encoder-v1", reranker_model_revision=None)


def test_reranker_model_revision_without_model_is_rejected():
    fp = compute_config_fingerprint(
        embedding_model="e",
        embedding_model_revision="v1",
        retrieval_k=10,
        retrieval_mechanism="dense_knn",
        selection_mechanism="rerank_topk",
        adapter_revision="a1",
        reranker_model=None,
        reranker_model_revision="rev-only",
    )
    with pytest.raises(RunConfigValidationError, match="reranker_model_revision must be None"):
        RunConfigRecord(
            config_fingerprint=fp,
            embedding_model="e",
            embedding_model_revision="v1",
            retrieval_k=10,
            retrieval_mechanism="dense_knn",
            selection_mechanism="rerank_topk",
            adapter_revision="a1",
            created_at="2026-01-01T00:00:00Z",
            reranker_model=None,
            reranker_model_revision="rev-only",
        )


def test_reranker_model_with_revision_is_accepted():
    record = _config_record(reranker_model="cross-encoder-v1", reranker_model_revision="rev1")
    assert record.reranker_model == "cross-encoder-v1"
    assert record.reranker_model_revision == "rev1"


# ---------------------------------------------------------------------------
# Section 9, item 2: sampling_seed materially affects the fingerprint
# ---------------------------------------------------------------------------


def test_sampling_seed_none_vs_set_changes_fingerprint():
    without_seed = _config_record(sampling_seed=None)
    with_seed = _config_record(sampling_seed=42)
    assert without_seed.config_fingerprint != with_seed.config_fingerprint


def test_different_sampling_seeds_change_fingerprint():
    seed_1 = _config_record(sampling_seed=1)
    seed_2 = _config_record(sampling_seed=2)
    assert seed_1.config_fingerprint != seed_2.config_fingerprint


# ---------------------------------------------------------------------------
# Section 9, item 3/4: collision vs idempotency
# ---------------------------------------------------------------------------


def test_run_config_ledger_collision_on_differing_payload(tmp_path):
    config_ledger = RunConfigLedger(tmp_path / "config-ledger")
    original = _config_record()
    config_ledger.append(original)
    # Same fingerprint, but a different created_at -- a genuinely different recorded fact.
    colliding = RunConfigRecord(
        config_fingerprint=original.config_fingerprint,
        embedding_model=original.embedding_model,
        embedding_model_revision=original.embedding_model_revision,
        retrieval_k=original.retrieval_k,
        retrieval_mechanism=original.retrieval_mechanism,
        selection_mechanism=original.selection_mechanism,
        adapter_revision=original.adapter_revision,
        created_at="2026-12-31T23:59:59Z",
    )
    with pytest.raises(RunConfigCollisionError):
        config_ledger.append(colliding)
    assert config_ledger.get(original.config_fingerprint).created_at == original.created_at


def test_run_config_ledger_idempotent_reappend(tmp_path):
    config_ledger = RunConfigLedger(tmp_path / "config-ledger")
    record = _config_record()
    assert config_ledger.append(record) == CFG_APPEND_CREATED
    assert config_ledger.append(record) == CFG_APPEND_IDEMPOTENT
    assert len(config_ledger.all_records()) == 1


# ---------------------------------------------------------------------------
# Section 9, item 5: temporal ordering is explicitly unchecked (documented limitation)
# ---------------------------------------------------------------------------


def test_config_fingerprint_resolution_is_atemporal_by_design(tmp_path):
    """A retrieved event's own `timestamp` may predate the referenced config record's
    `created_at` -- this stage deliberately does NOT check temporal ordering (mission
    section 9, item 5's documented default: "leave unchecked at this stage"). Appending
    such an event succeeds as long as the fingerprint resolves at all."""
    config_ledger = RunConfigLedger(tmp_path / "config-ledger")
    config = _config_record(created_at="2026-06-01T00:00:00Z")
    config_ledger.append(config)
    _, event_ledger = _memory_and_event_ledgers(tmp_path, config_ledger=config_ledger)
    earlier_event = CanonicalEvent(
        event_id="evt-earlier",
        event_type=EVENT_RETRIEVED,
        memory_ids=("loco-mem-001",),
        task_id="task-1",
        timestamp="2026-01-01T00:00:00Z",  # earlier than config.created_at
        actor="candidate_discovery",
        reason="matched query embedding.",
        config_fingerprint=config.config_fingerprint,
    )
    assert event_ledger.append(earlier_event) == APPEND_CREATED


# ---------------------------------------------------------------------------
# Persistence / reload
# ---------------------------------------------------------------------------


def test_run_config_ledger_persists_and_reloads(tmp_path):
    config_ledger = RunConfigLedger(tmp_path / "config-ledger")
    record = _config_record(reranker_model="cross-encoder-v1", reranker_model_revision="rev1", sampling_seed=7)
    config_ledger.append(record)
    reloaded = RunConfigLedger(tmp_path / "config-ledger")
    fetched = reloaded.get(record.config_fingerprint)
    assert fetched == record


def test_event_ledger_backward_compatible_without_config_ledger_param(tmp_path):
    """Every existing call site constructing `CanonicalEventLedger(storage_dir,
    memory_ledger)` (positionally, with no third argument) continues to work unmodified."""
    memory_ledger = CanonicalMemoryLedger(tmp_path / "memory-ledger")
    memory_ledger.put(_memory_record())
    event_ledger = CanonicalEventLedger(tmp_path / "event-ledger", memory_ledger)
    event = _retrieved_event("evt-r1", "loco-mem-001", "CFG-anything-unchecked")
    assert event_ledger.append(event) == APPEND_CREATED
