"""Phase 5.4 (review fix, issue 3) -- dedicated tests for `Phase5EventLedger`'s
duplicate-`memory_id` invariant for `attack_injection` events, plus a reload/reconstruction
check. General append/idempotent/collision behavior is already exercised indirectly via
`test_memory_lifecycle_wiring.py` and `test_attack_integration.py`; this file targets the
one new invariant this ledger enforces that theirs do not specifically probe.
"""

from __future__ import annotations

import pytest

from phase5.schema.event import ADMISSION_STATUS_ADMITTED, ADMISSION_STATUS_REJECTED, ATTACK_INJECTION, generate_phase5_event_id, Phase5Event
from phase5.schema.event_ledger import APPEND_CREATED, APPEND_IDEMPOTENT, DuplicateMemoryClaimError, Phase5EventLedger

TS = "2026-09-12T00:00:00+00:00"


def _injection_event(attack_id, artifact_id, memory_id, admission_status=ADMISSION_STATUS_ADMITTED, injection_id=None, reason="admitted"):
    kwargs = dict(
        event_type=ATTACK_INJECTION, timestamp=TS, actor="test", reason=reason,
        attack_id=attack_id, injection_id=injection_id or f"INJ-{attack_id}-{artifact_id}",
        artifact_id=artifact_id, admission_status=admission_status, memory_id=memory_id,
    )
    event_id = generate_phase5_event_id(**kwargs)
    return Phase5Event(event_id=event_id, **kwargs)


def test_two_different_attacks_cannot_both_claim_the_same_memory_id(tmp_path):
    ledger = Phase5EventLedger(tmp_path)
    first = _injection_event("farma", "artifact-1", "mem-shared")
    ledger.append(first)

    second = _injection_event("agentpoison", "poison-1", "mem-shared")
    with pytest.raises(DuplicateMemoryClaimError, match="already claimed"):
        ledger.append(second)

    # The first event's write must be unaffected by the rejected second attempt.
    assert ledger.exists(first.event_id)
    assert not ledger.exists(second.event_id)


def test_same_attack_two_different_artifacts_cannot_both_claim_the_same_memory_id(tmp_path):
    ledger = Phase5EventLedger(tmp_path)
    first = _injection_event("farma", "artifact-1", "mem-shared-2")
    ledger.append(first)
    second = _injection_event("farma", "artifact-2", "mem-shared-2")
    with pytest.raises(DuplicateMemoryClaimError):
        ledger.append(second)


def test_idempotent_reappend_of_the_identical_event_is_unaffected_by_the_invariant(tmp_path):
    ledger = Phase5EventLedger(tmp_path)
    event = _injection_event("farma", "artifact-3", "mem-idempotent")
    assert ledger.append(event) == APPEND_CREATED
    assert ledger.append(event) == APPEND_IDEMPOTENT  # exact same event_id + payload


def test_two_rejected_injections_with_no_memory_id_never_trigger_the_invariant(tmp_path):
    """memory_id=None for a rejected/non-admitted injection -- the invariant must only
    ever compare non-None memory_ids, never treat two `None`s as a collision."""
    ledger = Phase5EventLedger(tmp_path)
    first = _injection_event("farma", "artifact-4", None, admission_status=ADMISSION_STATUS_REJECTED, reason="rejected")
    second = _injection_event("agentpoison", "poison-4", None, admission_status=ADMISSION_STATUS_REJECTED, reason="rejected")
    ledger.append(first)
    ledger.append(second)  # must not raise
    assert ledger.exists(first.event_id)
    assert ledger.exists(second.event_id)


def test_reload_from_disk_preserves_the_invariant_against_previously_persisted_events(tmp_path):
    """The invariant must hold even against events written by a PREVIOUS ledger instance
    (i.e. it is checked against reloaded on-disk state, not just in-process history)."""
    ledger = Phase5EventLedger(tmp_path)
    first = _injection_event("farma", "artifact-5", "mem-reloaded")
    ledger.append(first)

    reloaded = Phase5EventLedger(tmp_path)
    second = _injection_event("agentpoison", "poison-5", "mem-reloaded")
    with pytest.raises(DuplicateMemoryClaimError):
        reloaded.append(second)
