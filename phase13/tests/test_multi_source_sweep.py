"""Phase 13 -- tests for the real multi-source sweep. Fast (reads the
already-recorded real ledger entries -- the real LLM calls happen once, via
`python -m phase13.multi_source_sweep`, not per test run). Also covers the
sweep's own recording-refusal logic with a cheap, deterministic, no-LLM
regression case built from an already-observed real negative result.
"""

from __future__ import annotations

import pytest

from attribution.metrics import ambiguity_rate, lineage_reconstruction_accuracy
from attribution.wiring.lineage import attribute_lineage
from phase13.ledger_setup import DEFAULT_LEDGER_DIR
from phase13.multi_source_sweep import SweepCaseResult, record_sweep_case
from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger

THREE_SOURCE_DERIVED_ID = "REAL-MULTI-SOURCE-DERIVED-3SRC-1"
THREE_SOURCE_IDS = ("REAL-FARMA-1", "REAL-SLEEPER-0", "REAL-DSRM-0")
TWO_SOURCE_DERIVED_ID = "REAL-MULTI-SOURCE-DERIVED-SLEEPER-1"
TWO_SOURCE_IDS = ("REAL-FARMA-1", "REAL-SLEEPER-0")


def _case_recorded(derived_id: str) -> bool:
    memory_ledger = CanonicalMemoryLedger(DEFAULT_LEDGER_DIR / "memory")
    return memory_ledger.get(derived_id) is not None


def test_record_sweep_case_refuses_a_real_negative_result():
    """Regression, deterministic, no LLM call: the FIRST real 3-source combo
    tried (DSRM-1 + FARMA-1 + MPBENCH-1, reverse_interleaved ordering) really
    measured similarities (0.708, 0.480, 0.656) with the middle one under the
    calibrated 0.5347 threshold -- confirms `record_sweep_case()`'s refusal
    path actually fires on a real, already-observed negative case, not just
    in theory."""
    case = SweepCaseResult(
        label="3-source-melanie-dsrm1-farma-mpbench-NEGATIVE-FINDING",
        source_ids=("REAL-DSRM-1", "REAL-FARMA-1", "REAL-MPBENCH-1"),
        ordering="reverse_interleaved",
        summary_text="Gina and Jon had a conversation, with Melanie mentioned in the context.",
        similarities=(0.7078001499176025, 0.4799644947052002, 0.6558812856674194),
        all_reflected=False,
    )
    with pytest.raises(ValueError, match="Refusing to record"):
        record_sweep_case(DEFAULT_LEDGER_DIR, "some-id-that-must-never-be-created", case)
    memory_ledger = CanonicalMemoryLedger(DEFAULT_LEDGER_DIR / "memory")
    assert memory_ledger.get("some-id-that-must-never-be-created") is None


@pytest.mark.skipif(not _case_recorded(THREE_SOURCE_DERIVED_ID), reason="real 3-source sweep case not recorded yet")
def test_three_source_case_is_correctly_flagged_as_ambiguous():
    memory_ledger = CanonicalMemoryLedger(DEFAULT_LEDGER_DIR / "memory")
    event_ledger = CanonicalEventLedger(DEFAULT_LEDGER_DIR / "events", memory_ledger)
    result = attribute_lineage(THREE_SOURCE_DERIVED_ID, run_id="test", event_ledger=event_ledger, full_chain=True)
    assert result.status == "MULTIPLE_POSSIBLE_SOURCES"
    assert set(result.candidate_source_ids) == set(THREE_SOURCE_IDS)


@pytest.mark.skipif(not _case_recorded(THREE_SOURCE_DERIVED_ID), reason="real 3-source sweep case not recorded yet")
def test_three_source_lineage_reconstruction_accuracy_is_correct():
    memory_ledger = CanonicalMemoryLedger(DEFAULT_LEDGER_DIR / "memory")
    event_ledger = CanonicalEventLedger(DEFAULT_LEDGER_DIR / "events", memory_ledger)
    result = attribute_lineage(THREE_SOURCE_DERIVED_ID, run_id="test", event_ledger=event_ledger, full_chain=True)
    accuracy = lineage_reconstruction_accuracy({THREE_SOURCE_DERIVED_ID: result}, {THREE_SOURCE_DERIVED_ID: THREE_SOURCE_IDS})
    assert accuracy == 1.0


@pytest.mark.skipif(not _case_recorded(TWO_SOURCE_DERIVED_ID), reason="real sweep 2-source case not recorded yet")
def test_second_two_source_case_is_correctly_flagged_as_ambiguous():
    memory_ledger = CanonicalMemoryLedger(DEFAULT_LEDGER_DIR / "memory")
    event_ledger = CanonicalEventLedger(DEFAULT_LEDGER_DIR / "events", memory_ledger)
    result = attribute_lineage(TWO_SOURCE_DERIVED_ID, run_id="test", event_ledger=event_ledger, full_chain=True)
    assert result.status == "MULTIPLE_POSSIBLE_SOURCES"
    assert set(result.candidate_source_ids) == set(TWO_SOURCE_IDS)


@pytest.mark.skipif(
    not (_case_recorded(THREE_SOURCE_DERIVED_ID) and _case_recorded(TWO_SOURCE_DERIVED_ID)),
    reason="real sweep cases not recorded yet",
)
def test_ambiguity_rate_reflects_multiple_real_branches_not_just_one():
    """Regression for the sweep's own purpose: with the original single
    multi-source case PLUS these two additional real sweep cases, more than
    one real derivation event must now be ambiguous -- distinguishing "a
    systematic sweep found several real hard cases" from "only the one
    originally built case exists."""
    memory_ledger = CanonicalMemoryLedger(DEFAULT_LEDGER_DIR / "memory")
    event_ledger = CanonicalEventLedger(DEFAULT_LEDGER_DIR / "events", memory_ledger)
    derived_events = [e for e in event_ledger.all_events() if e.event_type == "derived"]
    results = [
        attribute_lineage(e.target_memory_id, run_id="test", event_ledger=event_ledger, full_chain=True)
        for e in derived_events
    ]
    ambiguous_count = sum(1 for r in results if r.status == "MULTIPLE_POSSIBLE_SOURCES")
    assert ambiguous_count >= 2
