"""Phase 13 -- tests for the real counterfactual influence-attribution
harness. Fast (reads the already-recorded real ledger entry -- the real
baseline/masked LLM calls happen once, via
`python -m phase13.influence_attribution_case`, not per test run).
"""

from __future__ import annotations

import pytest

from attribution.wiring.influence import attribute_influence
from phase13.ledger_setup import DEFAULT_LEDGER_DIR
from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger

ESTABLISHED_TASK_ID = "phase13-influence-task-established"
ESTABLISHED_MEMORY_ID = "REAL-FARMA-1"
NOT_ESTABLISHED_TASK_ID = "phase13-influence-task-not-established"
NOT_ESTABLISHED_MEMORY_ID = "REAL-DSRM-1"


def _event_recorded() -> bool:
    memory_ledger = CanonicalMemoryLedger(DEFAULT_LEDGER_DIR / "memory")
    event_ledger = CanonicalEventLedger(DEFAULT_LEDGER_DIR / "events", memory_ledger)
    return any(e.event_id == f"evt-phase13-influence-{ESTABLISHED_TASK_ID}" for e in event_ledger.all_events())


@pytest.mark.skipif(not _event_recorded(), reason="real influence counterfactual case not recorded yet")
def test_established_case_is_correctly_attributed_as_influential():
    memory_ledger = CanonicalMemoryLedger(DEFAULT_LEDGER_DIR / "memory")
    event_ledger = CanonicalEventLedger(DEFAULT_LEDGER_DIR / "events", memory_ledger)
    result = attribute_influence(
        ESTABLISHED_MEMORY_ID, run_id="test", event_ledger=event_ledger, task_id=ESTABLISHED_TASK_ID,
    )
    assert result.status == "INFLUENCE_ESTABLISHED"
    assert result.evidence_event_ids == (f"evt-phase13-influence-{ESTABLISHED_TASK_ID}",)


@pytest.mark.skipif(not _event_recorded(), reason="real influence counterfactual case not recorded yet")
def test_not_established_case_has_no_fabricated_negative_event():
    """The NOT_ESTABLISHED case must be represented by the ABSENCE of a real
    counterfactually_influential event, per this schema's own design -- never
    a fabricated 'negative' CanonicalEvent."""
    memory_ledger = CanonicalMemoryLedger(DEFAULT_LEDGER_DIR / "memory")
    event_ledger = CanonicalEventLedger(DEFAULT_LEDGER_DIR / "events", memory_ledger)
    assert not any(
        e.event_id == f"evt-phase13-influence-{NOT_ESTABLISHED_TASK_ID}" for e in event_ledger.all_events()
    )
    result = attribute_influence(
        NOT_ESTABLISHED_MEMORY_ID, run_id="test", event_ledger=event_ledger, task_id=NOT_ESTABLISHED_TASK_ID,
    )
    assert result.status == "INFLUENCE_NOT_ESTABLISHED"


@pytest.mark.skipif(not _event_recorded(), reason="real influence counterfactual case not recorded yet")
def test_influence_established_does_not_leak_across_unrelated_task():
    """Regression mirroring attribution/tests.py's own Scenario G2 discipline:
    the real established finding for ESTABLISHED_TASK_ID must not make
    ESTABLISHED_MEMORY_ID appear influential under a DIFFERENT, unrelated
    task_id it was never tested against."""
    memory_ledger = CanonicalMemoryLedger(DEFAULT_LEDGER_DIR / "memory")
    event_ledger = CanonicalEventLedger(DEFAULT_LEDGER_DIR / "events", memory_ledger)
    result = attribute_influence(
        ESTABLISHED_MEMORY_ID, run_id="test", event_ledger=event_ledger, task_id="some-other-task-never-tested",
    )
    assert result.status == "INFLUENCE_NOT_ESTABLISHED"
