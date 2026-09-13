"""Phase 5.7 -- empirical confirmation for the pre-5.8 gate (A-MEM / real Mem0
compatibility, opened during the Stage 5.5 review).

This does NOT close the gate. It replaces "disclosed per `canonical_write.py`'s own
docstring that RealMem0Adapter/RealAMemAdapter require the isolated C:\\h4venv
interpreter" with an empirical finding from actually attempting it, in THIS repository's
main environment, in this session: both real adapters import (the Python class
definitions themselves have no import-time dependency on `mem0ai`/`amem`), but
`.initialize({})` on both reports `FOUNDATION_UNAVAILABLE` -- the real vendor SDKs are
confirmed not importable from inside `.initialize()` in this environment, exactly as
`canonical_write.py`'s module docstring said. Retrieval-instrumentation's vendor-id-
resolution design decision (Stage 5.5) therefore remains genuinely untested against a
real vendor backend -- this test exists so that fact is verified, not merely asserted
from a docstring, and so a future session with access to the h4venv interpreter has a
concrete, minimal starting point (rather than needing to rediscover this from scratch).
"""

from __future__ import annotations

import pytest

from phase3.evaluation.foundations.adapter import FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL, FOUNDATION_UNAVAILABLE


def test_real_mem0_adapter_confirmed_unavailable_in_this_environment():
    from phase3.evaluation.foundations_real.mem0_real_adapter import RealMem0Adapter

    adapter = RealMem0Adapter()
    field = adapter.initialize({})
    assert field.availability == FOUNDATION_UNAVAILABLE, (
        "If this ever starts passing (availability != UNAVAILABLE), the real Mem0 SDK has "
        "become reachable in this environment -- that is exactly the trigger the pre-5.8 "
        "gate (PHASE5_CHECKLIST.md) asks for: add a real vendor-id-resolution compatibility "
        "test for Stage 5.5's retrieval instrumentation before Stage 5.8 relies on it."
    )


def test_real_amem_adapter_confirmed_unavailable_in_this_environment():
    from phase3.evaluation.foundations_real.amem_real_adapter import RealAMemAdapter

    adapter = RealAMemAdapter()
    field = adapter.initialize({})
    assert field.availability == FOUNDATION_UNAVAILABLE, (
        "If this ever starts passing (availability != UNAVAILABLE), the real A-MEM SDK has "
        "become reachable in this environment -- see the pre-5.8 gate in PHASE5_CHECKLIST.md."
    )


# ---------------------------------------------------------------------------
# Stage 5.7 review fix, item 4: a FULL, real (not stubbed) compatibility test, written
# now so a future session with access to the isolated C:\h4venv interpreter (where
# mem0ai/amem are actually importable) can run it immediately -- self-skips in any
# environment where the real backend is confirmed unavailable, per the two tests above.
# Verifies the exact chain the gate names:
#   caller memory_id -> vendor admission -> vendor-returned ID -> canonical identity
#   resolution -> retrieval candidate ID -> Phase 5 retrieval event
# and reports, as a real assertion (not a guess), whether Stage 5.5's DIRECT_ASSIGNMENT
# design decision (Stage 5.5's own disclosed limitation) actually holds for a real Mem0
# backend or not.
# ---------------------------------------------------------------------------

TS = "2026-09-12T00:00:00+00:00"


def test_real_mem0_retrieval_identity_chain_when_available(tmp_path):
    from phase3.evaluation.foundations_real.mem0_real_adapter import RealMem0Adapter

    adapter = RealMem0Adapter()
    init_field = adapter.initialize({})
    if init_field.availability not in (FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL):
        pytest.skip(
            f"RealMem0Adapter unavailable in this environment ({init_field.availability}): "
            f"{init_field.note} -- this test is written in full for a future h4venv-enabled "
            "session; NOT VALIDATED here."
        )

    from phase3.evaluation.foundations.canonical import (
        CanonicalMemoryRecord, LIFECYCLE_CREATED, MEMORY_TYPE_FOUNDATION, SOURCE_TYPE_PHASE2_UMR,
    )
    from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger
    from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger
    from phase5.identity.run_identity import EventRunMembershipLedger, ExperimentRunLedger, ExperimentRunRecord
    from phase5.schema.event_ledger import Phase5EventLedger
    from phase5.wiring.memory_lifecycle import record_memory_creation
    from phase5.wiring.retrieval_instrumentation import instrument_retrieval_and_selection

    # --- 1. caller memory_id -> 2. vendor admission -> 3. vendor-returned ID ---
    caller_memory_id = "phase5-real-vendor-chain-test-001"
    add_field = adapter.add_memory(
        memory_id=caller_memory_id, content={"text": "test content for identity chain"},
        metadata={"user_id": "phase5-test-user"},
    )
    assert add_field.availability in (FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL)
    vendor_returned_id = add_field.value.get("memory_id")
    assert vendor_returned_id is not None

    # THE open question Stage 5.5 disclosed: does the vendor preserve the caller's own id
    # (DIRECT_ASSIGNMENT, confirmed for MockMem0Adapter) or reassign its own
    # (METADATA_LOOKUP, per canonical_wiring.py's Condition B)?
    identity_is_direct_assignment = vendor_returned_id == caller_memory_id

    # --- 4. canonical memory identity resolution (via Stage 5.4's real wiring) ---
    memory_ledger = CanonicalMemoryLedger(tmp_path / "memory")
    event_ledger = CanonicalEventLedger(tmp_path / "events", memory_ledger)
    run_ledger = ExperimentRunLedger(tmp_path / "runs")
    membership_ledger = EventRunMembershipLedger(tmp_path / "membership", run_ledger)
    phase5_ledger = Phase5EventLedger(tmp_path / "phase5_events")
    run = ExperimentRunRecord(
        experiment_id="real-vendor-chain", run_id="RUN-real-vendor", dataset="locomo",
        scope={}, started_at=TS, actor="test", reason="real vendor identity chain test",
    )
    run_ledger.register(run)
    record_memory_creation(
        memory_ledger=memory_ledger, event_ledger=event_ledger, membership_ledger=membership_ledger,
        run_id=run.run_id,
        record=CanonicalMemoryRecord(
            memory_id=caller_memory_id, memory_type=MEMORY_TYPE_FOUNDATION,
            content={"text": "test content for identity chain"}, source={"source_type": SOURCE_TYPE_PHASE2_UMR},
            parent_ids=(), creation_event="real-vendor-chain-test-creation", creation_timestamp=TS,
            lifecycle_state=LIFECYCLE_CREATED,
        ),
        actor="test", reason="canonical record for real-vendor chain test", timestamp=TS,
    )

    # --- 5. retrieval candidate ID (real retrieve() call) ---
    retrieve_field = adapter.retrieve({"text": "test content", "user_id": "phase5-test-user"}, top_k=5)
    assert retrieve_field.availability in (FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL)
    retrieved_ids = [item.get("memory_id") for item in (retrieve_field.value or [])]
    assert vendor_returned_id in retrieved_ids or caller_memory_id in retrieved_ids

    # --- 6. Phase 5 retrieval event, over the REAL retrieved id ---
    candidates = [(item.get("memory_id"), "test content for identity chain") for item in (retrieve_field.value or [])]
    report = instrument_retrieval_and_selection(
        memory_ledger=memory_ledger, event_ledger=event_ledger, phase5_event_ledger=phase5_ledger,
        membership_ledger=membership_ledger, run_id=run.run_id, task_id="task-real-vendor",
        query="test content", candidates=candidates, config_fingerprint="CFG-real-vendor-test",
        actor="test", timestamp=TS,
    )

    # THE KEY, HONEST FINDING -- reported as a real assertion either way, never assumed:
    if identity_is_direct_assignment:
        assert report.not_in_canonical_ledger == [], (
            "Vendor uses DIRECT_ASSIGNMENT (returned id == caller-supplied id) -- Stage 5.5's "
            "no-resolution-needed design decision is CONFIRMED correct for this real backend."
        )
    else:
        assert vendor_returned_id in report.not_in_canonical_ledger, (
            "Vendor REASSIGNS ids (METADATA_LOOKUP-style) -- Stage 5.5's design decision does "
            "NOT hold for this real backend. A resolution step (reuse "
            "agent_runtime.identity.resolve_source_identities(), per canonical_wiring.py's "
            "Condition B) is required before retrieval instrumentation can be trusted here."
        )


def test_real_mem0_identity_continuity_across_update_when_available(tmp_path):
    """Verifies identity continuity across a memory UPDATE (the closest real-adapter
    analogue to supersession available via the plain MemoryFoundationAdapter interface --
    `update_memory()`) -- does the vendor-returned id stay the same after an update, or
    does it change? Skips (NOT VALIDATED) in any environment without a reachable real
    backend, exactly like the test above."""
    from phase3.evaluation.foundations_real.mem0_real_adapter import RealMem0Adapter

    adapter = RealMem0Adapter()
    init_field = adapter.initialize({})
    if init_field.availability not in (FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL):
        pytest.skip(
            f"RealMem0Adapter unavailable in this environment ({init_field.availability}) -- "
            "NOT VALIDATED here; written for a future h4venv-enabled session."
        )

    caller_memory_id = "phase5-real-vendor-continuity-test-001"
    add_field = adapter.add_memory(
        memory_id=caller_memory_id, content={"text": "original content"}, metadata={"user_id": "phase5-test-user"},
    )
    original_vendor_id = add_field.value.get("memory_id")

    update_field = adapter.update_memory(caller_memory_id, content={"text": "updated content"})
    assert update_field.availability in (FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL)

    inspect_field = adapter.inspect_memory(caller_memory_id)
    assert inspect_field.availability in (FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL)
    assert inspect_field.value.get("content", {}).get("text") == "updated content", (
        "Identity continuity broken: the same caller memory_id no longer resolves to the "
        "updated content after update_memory() -- Stage 5.4's supersession wiring would "
        "need to account for this before trusting real-vendor updates."
    )
