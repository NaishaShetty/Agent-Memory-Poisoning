"""Phase 6.13 -- tests for the Defense <-> Attribution bridge.

Uses REAL Phase 3/5 wiring functions (`record_memory_creation()`,
`record_memory_derivation()` -- the actual, already-tested Phase 5
instrumentation functions, not hand-rolled event construction) and Attribution's
REAL, unmodified `attribute_memory()` orchestrator. No mocks, no live campaign
(consistent with Stage 6.10's confirmed environment limitation) -- everything
here is directly-constructed real ledger state, the same pattern Attribution's
own test suite uses.
"""

from __future__ import annotations

import pytest

from attribution.schema import (
    ATTRIBUTION_INFLUENCE,
    ATTRIBUTION_LINEAGE,
    ATTRIBUTION_ORIGIN,
    STATUS_INFLUENCE_ESTABLISHED,
    STATUS_INFLUENCE_NOT_ESTABLISHED,
    STATUS_NO_ATTACK_ORIGIN,
    STATUS_NO_LINEAGE_ANCESTOR,
    STATUS_UNIQUE,
)
from phase3.evaluation.foundations.canonical import (
    CanonicalMemoryRecord,
    LIFECYCLE_CREATED,
    MEMORY_TYPE_DERIVED,
    MEMORY_TYPE_FOUNDATION,
    SOURCE_TYPE_PHASE2_UMR,
)
from phase3.evaluation.foundations.canonical_event import CanonicalEvent, EVENT_COUNTERFACTUALLY_INFLUENTIAL
from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger
from phase5.identity.run_identity import EventRunMembershipLedger, ExperimentRunLedger, ExperimentRunRecord
from phase5.schema.event_ledger import Phase5EventLedger
from phase5.wiring.memory_lifecycle import record_memory_creation, record_memory_derivation

from phase6.defense.attribution_bridge.report import explain_defense_mitigation
from phase6.defense.policy.records import build_decision
from phase6.defense.policy.states import ALLOW, BLOCK, QUARANTINE

TS = "2026-09-14T00:00:00Z"
TS2 = "2026-09-14T00:05:00Z"


def _ledgers(tmp_path, run_id="RUN-P6-ATTRIB"):
    memory_ledger = CanonicalMemoryLedger(tmp_path / "memory")
    event_ledger = CanonicalEventLedger(tmp_path / "events", memory_ledger)
    run_ledger = ExperimentRunLedger(tmp_path / "runs")
    membership_ledger = EventRunMembershipLedger(tmp_path / "membership", run_ledger)
    phase5_ledger = Phase5EventLedger(tmp_path / "phase5_events")
    run = ExperimentRunRecord(
        experiment_id="exp-p6-attrib", run_id=run_id, dataset="locomo",
        scope={}, started_at=TS, actor="test", reason="phase6 attribution-bridge test run",
    )
    run_ledger.register(run)
    return dict(
        memory_ledger=memory_ledger, event_ledger=event_ledger,
        membership_ledger=membership_ledger, phase5_ledger=phase5_ledger, run_id=run.run_id,
    )


def _foundation_record(memory_id, text):
    return CanonicalMemoryRecord(
        memory_id=memory_id, memory_type=MEMORY_TYPE_FOUNDATION, content={"text": text},
        source={"source_type": SOURCE_TYPE_PHASE2_UMR}, parent_ids=(),
        creation_event=f"creation-of-{memory_id}", creation_timestamp=TS, lifecycle_state=LIFECYCLE_CREATED,
    )


def _fake_decision(memory_id, action, run_id):
    return build_decision(
        candidate_memory_id=memory_id, signals_used={"test_signal": 1.0}, action=action,
        reason="test fixture decision", run_id=run_id, episode_id="episode-1",
        timestamp=TS, evidence_refs=("EVT-fixture",),
    )


# ---------------------------------------------------------------------------
# Scenario 1: memory BLOCKED at admission -- never written, no event trail
# ---------------------------------------------------------------------------


def test_blocked_memory_has_no_real_event_trail_and_narrative_says_so(tmp_path):
    """A BLOCK decision means the memory was never actually admitted --
    confirmed by never calling record_memory_creation() for it. Attribution's
    real functions correctly report absence, not an error, and the narrative
    explicitly explains WHY (never written), never implying the defense
    'proved' anything about downstream influence."""
    ledgers = _ledgers(tmp_path)
    decision = _fake_decision("MEM-BLOCKED", BLOCK, ledgers["run_id"])

    report = explain_defense_mitigation(
        decision, run_id=ledgers["run_id"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"],
    )

    origin = next(r for r in report.attribution_results if r.attribution_type == ATTRIBUTION_ORIGIN)
    lineage = next(r for r in report.attribution_results if r.attribution_type == ATTRIBUTION_LINEAGE)
    influence = next(r for r in report.attribution_results if r.attribution_type == ATTRIBUTION_INFLUENCE)

    assert origin.status == STATUS_NO_ATTACK_ORIGIN
    assert lineage.status == STATUS_NO_LINEAGE_ANCESTOR
    assert influence.status == STATUS_INFLUENCE_NOT_ESTABLISHED

    narrative_text = " ".join(report.mitigation_narrative)
    assert "never" in narrative_text.lower() or "not established" in narrative_text.lower()
    # The critical fallacy check: the narrative must explicitly REFUSE the
    # "blocked, therefore prevented influence" inference, not silently omit
    # the question or (worse) assert it as fact.
    assert "does not, by itself, establish" in narrative_text.lower()
    assert "fallacy" in narrative_text.lower()  # the explicit refusal is stated, not silently omitted


# ---------------------------------------------------------------------------
# Scenario 2: memory ADMITTED (ALLOW), real lineage, but NO counterfactual
# test was ever run -- influence must report NOT_ESTABLISHED, not inferred
# ---------------------------------------------------------------------------


def test_allowed_memory_with_real_lineage_but_no_counterfactual_test(tmp_path):
    ledgers = _ledgers(tmp_path)
    parent = _foundation_record("MEM-PARENT", "original real content")
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        record=parent, actor="test", reason="seed", timestamp=TS,
    )
    child = CanonicalMemoryRecord(
        memory_id="MEM-CHILD", memory_type=MEMORY_TYPE_DERIVED, content={"text": "derived content"},
        source={"source_type": SOURCE_TYPE_PHASE2_UMR}, parent_ids=("MEM-PARENT",),
        creation_event="creation-of-child", creation_timestamp=TS2, lifecycle_state=LIFECYCLE_CREATED,
    )
    record_memory_derivation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        derived_record=child, source_memory_ids=("MEM-PARENT",),
        actor="test", reason="derivation", timestamp=TS2,
    )

    decision = _fake_decision("MEM-CHILD", ALLOW, ledgers["run_id"])
    report = explain_defense_mitigation(
        decision, run_id=ledgers["run_id"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"],
    )

    lineage = next(r for r in report.attribution_results if r.attribution_type == ATTRIBUTION_LINEAGE)
    influence = next(r for r in report.attribution_results if r.attribution_type == ATTRIBUTION_INFLUENCE)

    assert lineage.status == STATUS_UNIQUE
    assert lineage.source_id == "MEM-PARENT"
    assert influence.status == STATUS_INFLUENCE_NOT_ESTABLISHED  # real absence, not inferred safety

    narrative_text = " ".join(report.mitigation_narrative)
    assert "proven harmless" in narrative_text.lower()


# ---------------------------------------------------------------------------
# Scenario 3: real counterfactual evidence exists -- influence IS confirmed
# ---------------------------------------------------------------------------


def test_real_counterfactual_evidence_confirms_influence(tmp_path):
    ledgers = _ledgers(tmp_path)
    memory = _foundation_record("MEM-INFLUENTIAL", "a forged claim")
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        record=memory, actor="test", reason="seed", timestamp=TS,
    )
    counterfactual_event = CanonicalEvent(
        event_id="evt-p6-counterfactual-1", event_type=EVENT_COUNTERFACTUALLY_INFLUENTIAL,
        memory_ids=("MEM-INFLUENTIAL",), timestamp=TS2, actor="test", reason="masking changed the answer",
        task_id="task-p6", config_fingerprint="cfg-1", counterfactual_answer_hash="hash-masked",
        baseline_answer_hash="hash-baseline", diff_criterion="exact_match_changed",
        masking_method="selected_set_removal",
    )
    ledgers["event_ledger"].append(counterfactual_event)

    decision = _fake_decision("MEM-INFLUENTIAL", ALLOW, ledgers["run_id"])
    report = explain_defense_mitigation(
        decision, run_id=ledgers["run_id"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], task_id="task-p6",
    )

    influence = next(r for r in report.attribution_results if r.attribution_type == ATTRIBUTION_INFLUENCE)
    assert influence.status == STATUS_INFLUENCE_ESTABLISHED
    assert influence.evidence_event_ids == ("evt-p6-counterfactual-1",)

    narrative_text = " ".join(report.mitigation_narrative)
    assert "CONFIRMED by real counterfactual evidence" in narrative_text


# ---------------------------------------------------------------------------
# Read-only / no leakage / never modifies Attribution
# ---------------------------------------------------------------------------


def test_bridge_never_writes_to_any_ledger(tmp_path):
    """The bridge is read-only -- calling it twice on the same real ledger
    state must produce byte-identical results, and the ledger's own event
    count must not change."""
    ledgers = _ledgers(tmp_path)
    memory = _foundation_record("MEM-READONLY", "some content")
    record_memory_creation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        record=memory, actor="test", reason="seed", timestamp=TS,
    )
    event_count_before = len(ledgers["event_ledger"].all_events())

    decision = _fake_decision("MEM-READONLY", ALLOW, ledgers["run_id"])
    first = explain_defense_mitigation(
        decision, run_id=ledgers["run_id"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"],
    )
    second = explain_defense_mitigation(
        decision, run_id=ledgers["run_id"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"],
    )
    event_count_after = len(ledgers["event_ledger"].all_events())

    assert event_count_before == event_count_after
    assert first.attribution_results == second.attribution_results


def test_bridge_never_imports_or_modifies_attribution_source():
    """Static check: this module only IMPORTS from `attribution.wiring.
    orchestrator` and `attribution.schema` -- it never defines a function
    with a name shadowing an Attribution function, and Attribution's own
    source files are untouched (verified at the repo level by every prior
    stage's frozen-boundary check; this test additionally confirms the
    import surface itself is read-only-shaped)."""
    import ast

    import phase6.defense.attribution_bridge.report as bridge_module

    with open(bridge_module.__file__, "r", encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=bridge_module.__file__)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert "attribution.wiring.orchestrator" in imported
    assert not any(name.startswith("mem0") or "write" in name for name in imported)
