"""Phase 9, Stage 9.3 -- `attribution.wiring.forensics_entrypoints` tests.

Verifies the thin resolution from a real Phase 6 `MGPDecisionRecord` and real Phase 7
`CampaignSignalResult`/`ContentSimilarityCluster` results to `(TARGET_MEMORY, id)`
forensic targets, and that the resolved targets actually work when fed into
`reconstruct_attack_origin()`.
"""

from __future__ import annotations

import pytest

from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger
from phase3.evaluation.foundations.memory_versioning import SupersessionLedger

from phase5.identity.run_identity import EventRunMembershipLedger, ExperimentRunLedger, ExperimentRunRecord
from phase5.schema.event_ledger import Phase5EventLedger
from phase5.wiring.live_attack_runs import run_live_farma_injection

from phase6.defense.policy.records import build_decision
from phase6.defense.policy.states import ALLOW, BLOCK, QUARANTINE

from phase7.propagation.campaign_signals import CampaignSignalResult, ContentSimilarityCluster
from phase7.propagation.signals import SignalResult

from attribution.schema import TARGET_MEMORY
from attribution.wiring.forensics import CHAIN_SINGLE_ORIGIN_HIGH_CONFIDENCE, reconstruct_attack_origin
from attribution.wiring.forensics_entrypoints import (
    forensic_target_from_mgp_decision,
    forensic_targets_from_campaign_signal,
    forensic_targets_from_content_similarity_clusters,
    forensic_targets_from_mgp_decisions,
)

TS = "2026-09-17T00:00:00+00:00"


def _make_ledgers(tmp_path, run_id="RUN-forensics-entrypoints"):
    memory_ledger = CanonicalMemoryLedger(tmp_path / "memory")
    event_ledger = CanonicalEventLedger(tmp_path / "events", memory_ledger)
    supersession_ledger = SupersessionLedger(tmp_path / "supersessions")
    run_ledger = ExperimentRunLedger(tmp_path / "runs")
    membership_ledger = EventRunMembershipLedger(tmp_path / "membership", run_ledger)
    phase5_ledger = Phase5EventLedger(tmp_path / "phase5_events")
    run = ExperimentRunRecord(
        experiment_id="exp-forensics-entrypoints", run_id=run_id, dataset="locomo",
        scope={}, started_at=TS, actor="test", reason="forensics entrypoints test run",
    )
    run_ledger.register(run)
    return dict(
        memory_ledger=memory_ledger, event_ledger=event_ledger, supersession_ledger=supersession_ledger,
        membership_ledger=membership_ledger, phase5_ledger=phase5_ledger, run_id=run.run_id,
    )


@pytest.fixture
def ledgers(tmp_path):
    return _make_ledgers(tmp_path)


def _decision(action, candidate_memory_id, run_id):
    return build_decision(
        candidate_memory_id=candidate_memory_id, signals_used={"some_signal": True},
        action=action, reason="a real, evidence-grounded reason for this decision",
        run_id=run_id, episode_id=None, timestamp=TS, evidence_refs=("EVT-1",),
    )


# ---------------------------------------------------------------------------
# MGPDecisionRecord resolution
# ---------------------------------------------------------------------------

def test_quarantine_and_block_resolve_to_memory_target(ledgers):
    quarantine = _decision(QUARANTINE, "mem-q", ledgers["run_id"])
    block = _decision(BLOCK, "mem-b", ledgers["run_id"])

    assert forensic_target_from_mgp_decision(quarantine) == (TARGET_MEMORY, "mem-q")
    assert forensic_target_from_mgp_decision(block) == (TARGET_MEMORY, "mem-b")


def test_allow_resolves_to_none(ledgers):
    allow = _decision(ALLOW, "mem-a", ledgers["run_id"])
    assert forensic_target_from_mgp_decision(allow) is None


def test_batch_resolution_dedupes_and_sorts(ledgers):
    decisions = [
        _decision(QUARANTINE, "mem-z", ledgers["run_id"]),
        _decision(ALLOW, "mem-ignored", ledgers["run_id"]),
        _decision(BLOCK, "mem-a", ledgers["run_id"]),
        _decision(QUARANTINE, "mem-a", ledgers["run_id"]),
    ]
    targets = forensic_targets_from_mgp_decisions(decisions)
    assert targets == ((TARGET_MEMORY, "mem-a"), (TARGET_MEMORY, "mem-z"))


def test_mgp_decision_target_feeds_reconstruct_attack_origin(ledgers):
    injection_result = run_live_farma_injection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], timestamp=TS,
    )
    memory_id = injection_result.memory_creation.created_event.memory_ids[0]
    decision = _decision(QUARANTINE, memory_id, ledgers["run_id"])

    target_type, target_id = forensic_target_from_mgp_decision(decision)
    reconstruction = reconstruct_attack_origin(
        target_type, target_id, run_id=ledgers["run_id"],
        event_ledger=ledgers["event_ledger"], phase5_event_ledger=ledgers["phase5_ledger"],
    )

    assert reconstruction.chain_confidence == CHAIN_SINGLE_ORIGIN_HIGH_CONFIDENCE
    assert reconstruction.per_memory_origin[memory_id].attack_id == "farma"


# ---------------------------------------------------------------------------
# Campaign signal / content-similarity cluster resolution
# ---------------------------------------------------------------------------

def test_campaign_signal_resolves_to_root_memory_targets():
    result = CampaignSignalResult(
        value=3.0, evidence_kinds=("OBSERVED_EVENT",),
        per_root={
            "mem-root-2": SignalResult(value=1.5, evidence_kinds=("OBSERVED_EVENT",), detail={}),
            "mem-root-1": SignalResult(value=1.5, evidence_kinds=("OBSERVED_EVENT",), detail={}),
        },
    )
    targets = forensic_targets_from_campaign_signal(result)
    assert targets == ((TARGET_MEMORY, "mem-root-1"), (TARGET_MEMORY, "mem-root-2"))


def test_content_similarity_clusters_resolve_and_dedupe():
    clusters = [
        ContentSimilarityCluster(root_ids=("mem-c", "mem-a"), min_pairwise_similarity=0.8),
        ContentSimilarityCluster(root_ids=("mem-a", "mem-b"), min_pairwise_similarity=0.75),
    ]
    targets = forensic_targets_from_content_similarity_clusters(clusters)
    assert targets == ((TARGET_MEMORY, "mem-a"), (TARGET_MEMORY, "mem-b"), (TARGET_MEMORY, "mem-c"))


def test_campaign_root_target_feeds_reconstruct_attack_origin(ledgers):
    injection_result = run_live_farma_injection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], timestamp=TS,
    )
    memory_id = injection_result.memory_creation.created_event.memory_ids[0]
    result = CampaignSignalResult(
        value=1.0, evidence_kinds=("OBSERVED_EVENT",),
        per_root={memory_id: SignalResult(value=1.0, evidence_kinds=("OBSERVED_EVENT",), detail={})},
    )

    (target_type, target_id), = forensic_targets_from_campaign_signal(result)
    reconstruction = reconstruct_attack_origin(
        target_type, target_id, run_id=ledgers["run_id"],
        event_ledger=ledgers["event_ledger"], phase5_event_ledger=ledgers["phase5_ledger"],
    )

    assert reconstruction.chain_confidence == CHAIN_SINGLE_ORIGIN_HIGH_CONFIDENCE
    assert reconstruction.per_memory_origin[memory_id].attack_id == "farma"
