"""Phase 5.3 -- tests for ExperimentRunRecord/Ledger and EventRunMembership/Ledger."""

from __future__ import annotations

import pytest

from phase5.identity.run_identity import (
    EVENT_SCHEMA_CANONICAL_EVENT,
    EVENT_SCHEMA_PHASE5_EVENT,
    APPEND_CREATED,
    APPEND_IDEMPOTENT,
    EventRunMembership,
    EventRunMembershipLedger,
    ExperimentRunLedger,
    ExperimentRunRecord,
    MembershipCollisionError,
    RunCollisionError,
    RunIdentityValidationError,
    UnknownRunError,
    generate_episode_id,
    generate_run_id,
)

TS = "2026-09-12T00:00:00+00:00"


def _run_record(run_id=None, **overrides):
    experiment_id = overrides.pop("experiment_id", "phase4-farma-campaign")
    dataset = overrides.pop("dataset", "locomo")
    scope = overrides.pop("scope", {"attack_id": "farma", "campaign": "milestone5"})
    actor = overrides.pop("actor", "milestone5_campaign.py")
    started_at = overrides.pop("started_at", TS)
    if run_id is None:
        run_id = generate_run_id(experiment_id, dataset, scope, actor, started_at)
    return ExperimentRunRecord(
        experiment_id=experiment_id,
        run_id=run_id,
        dataset=dataset,
        scope=scope,
        started_at=started_at,
        actor=actor,
        reason=overrides.pop("reason", "FARMA milestone-5 campaign execution"),
        **overrides,
    )


def test_run_id_generation_is_deterministic():
    id1 = generate_run_id("exp-1", "locomo", {"attack_id": "farma"}, "actor", TS)
    id2 = generate_run_id("exp-1", "locomo", {"attack_id": "farma"}, "actor", TS)
    assert id1 == id2
    assert id1.startswith("RUN-")

    id3 = generate_run_id("exp-1", "locomo", {"attack_id": "minja"}, "actor", TS)
    assert id3 != id1


def test_episode_id_groups_by_dataset_and_session_or_haystack():
    run_id = "RUN-abc"
    e1 = generate_episode_id(run_id, "locomo", "conversation-7")
    e2 = generate_episode_id(run_id, "locomo", "conversation-7")
    e3 = generate_episode_id(run_id, "locomo", "conversation-8")
    assert e1 == e2
    assert e1 != e3
    assert e1.startswith("EPI-")


def test_register_run_then_reload_from_disk(tmp_path):
    record = _run_record()
    ledger = ExperimentRunLedger(tmp_path / "runs")
    assert ledger.register(record) == APPEND_CREATED
    assert ledger.register(record) == APPEND_IDEMPOTENT  # identical re-register is a no-op

    reloaded = ExperimentRunLedger(tmp_path / "runs")
    assert reloaded.get(record.run_id) == record
    assert reloaded.runs_for_experiment("phase4-farma-campaign") == (record,)


def test_register_run_collision_raises(tmp_path):
    ledger = ExperimentRunLedger(tmp_path / "runs")
    record = _run_record()
    ledger.register(record)
    different = _run_record(run_id=record.run_id, reason="a completely different reason")
    with pytest.raises(RunCollisionError):
        ledger.register(different)


def test_membership_requires_run_to_already_be_registered(tmp_path):
    run_ledger = ExperimentRunLedger(tmp_path / "runs")
    membership_ledger = EventRunMembershipLedger(tmp_path / "membership", run_ledger)

    membership = EventRunMembership(
        event_id="EVT-somehash",
        event_schema=EVENT_SCHEMA_CANONICAL_EVENT,
        run_id="RUN-not-registered",
        recorded_at=TS,
    )
    with pytest.raises(UnknownRunError):
        membership_ledger.append(membership)


def test_membership_append_idempotent_and_collision(tmp_path):
    run_ledger = ExperimentRunLedger(tmp_path / "runs")
    record = _run_record()
    run_ledger.register(record)
    membership_ledger = EventRunMembershipLedger(tmp_path / "membership", run_ledger)

    episode_id = generate_episode_id(record.run_id, "locomo", "conversation-7")
    membership = EventRunMembership(
        event_id="P5EVT-somehash",
        event_schema=EVENT_SCHEMA_PHASE5_EVENT,
        run_id=record.run_id,
        episode_id=episode_id,
        recorded_at=TS,
    )
    assert membership_ledger.append(membership) == APPEND_CREATED
    assert membership_ledger.append(membership) == APPEND_IDEMPOTENT

    conflicting = EventRunMembership(
        event_id="P5EVT-somehash",
        event_schema=EVENT_SCHEMA_PHASE5_EVENT,
        run_id=record.run_id,
        episode_id="EPI-different",
        recorded_at=TS,
    )
    with pytest.raises(MembershipCollisionError):
        membership_ledger.append(conflicting)

    assert membership_ledger.run_for_event("P5EVT-somehash") == membership
    assert membership_ledger.events_for_run(record.run_id) == ("P5EVT-somehash",)
    assert membership_ledger.events_for_episode(episode_id) == ("P5EVT-somehash",)


def test_membership_ledger_reconstructs_from_disk(tmp_path):
    run_ledger = ExperimentRunLedger(tmp_path / "runs")
    record = _run_record()
    run_ledger.register(record)
    membership_ledger = EventRunMembershipLedger(tmp_path / "membership", run_ledger)
    membership = EventRunMembership(
        event_id="EVT-x",
        event_schema=EVENT_SCHEMA_CANONICAL_EVENT,
        run_id=record.run_id,
        recorded_at=TS,
    )
    membership_ledger.append(membership)

    reloaded_run_ledger = ExperimentRunLedger(tmp_path / "runs")
    reloaded_membership_ledger = EventRunMembershipLedger(tmp_path / "membership", reloaded_run_ledger)
    assert reloaded_membership_ledger.run_for_event("EVT-x") == membership


def test_run_record_rejects_empty_experiment_id():
    with pytest.raises(RunIdentityValidationError, match="experiment_id"):
        _run_record(experiment_id="")
