"""Phase 13 -- tests for real EXPOSURE/REFERENCES attribution against the real
corpus. Fast for the REFERENCES half (pure ledger reads). The EXPOSURE half
needs the two real agent decisions `influence_attribution_case.py` produces
to already be recorded -- skipped if they are not.
"""

from __future__ import annotations

import pytest

from attribution.wiring.references import attribute_references
from phase13.exposure_and_references_attribution import (
    CITED_MEMORY_ID,
    CITING_MEMORY_ID,
    evaluate_exposure_attribution,
    evaluate_references_attribution,
    record_real_citing_memory,
    record_real_exposure_decisions,
    run_real_corpus_baseline,
)
from phase13.ledger_setup import DEFAULT_LEDGER_DIR
from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger
from phase5.schema.event_ledger import Phase5EventLedger


def _ledger_exists() -> bool:
    return (DEFAULT_LEDGER_DIR / "memory" / "records.jsonl").exists()


def _citing_memory_recorded() -> bool:
    memory_ledger = CanonicalMemoryLedger(DEFAULT_LEDGER_DIR / "memory")
    return memory_ledger.get(CITING_MEMORY_ID) is not None


def _exposure_decisions_recorded() -> bool:
    phase5_event_ledger = Phase5EventLedger(DEFAULT_LEDGER_DIR / "phase5_events")
    return any(
        e.event_type == "agent_decision" and str(getattr(e, "decision_id", "")).startswith("phase13-exposure-decision-")
        for e in phase5_event_ledger.all_events()
    )


@pytest.mark.skipif(not _ledger_exists(), reason="real attribution ledger not built yet")
def test_real_corpus_baseline_has_no_natural_citations():
    """Real, informative negative baseline: none of the 15 real poison
    scenarios' natural conversational content happens to contain a literal
    `[memory_id]` bracket citation."""
    baseline = run_real_corpus_baseline()
    assert len(baseline) == 15
    assert all(status == "REFERENCES_NOT_ESTABLISHED" for status in baseline.values())


@pytest.mark.skipif(not (_ledger_exists() and _citing_memory_recorded()), reason="real REFERENCES structural test memory not recorded yet")
def test_references_structural_positive_case_is_correctly_established():
    memory_ledger = CanonicalMemoryLedger(DEFAULT_LEDGER_DIR / "memory")
    event_ledger = CanonicalEventLedger(DEFAULT_LEDGER_DIR / "events", memory_ledger)
    result = attribute_references(CITING_MEMORY_ID, run_id="test", memory_ledger=memory_ledger, event_ledger=event_ledger)
    assert result.status == "REFERENCES_ESTABLISHED"
    assert result.candidate_source_ids == (CITED_MEMORY_ID,)


@pytest.mark.skipif(not (_ledger_exists() and _citing_memory_recorded()), reason="real REFERENCES structural test memory not recorded yet")
def test_cited_memory_does_not_itself_cite_anything():
    """The cited real memory (REAL-FARMA-1) itself contains no citation --
    REFERENCES is directional, never symmetric by construction."""
    memory_ledger = CanonicalMemoryLedger(DEFAULT_LEDGER_DIR / "memory")
    event_ledger = CanonicalEventLedger(DEFAULT_LEDGER_DIR / "events", memory_ledger)
    result = attribute_references(CITED_MEMORY_ID, run_id="test", memory_ledger=memory_ledger, event_ledger=event_ledger)
    assert result.status == "REFERENCES_NOT_ESTABLISHED"


@pytest.mark.skipif(not (_ledger_exists() and _exposure_decisions_recorded()), reason="real exposure decisions not recorded yet")
def test_exposed_memories_are_correctly_established():
    decision_ids = record_real_exposure_decisions(DEFAULT_LEDGER_DIR)
    cases = evaluate_exposure_attribution(DEFAULT_LEDGER_DIR, decision_ids)
    exposed_cases = {c.memory_id: c for c in cases if c.memory_id != "REAL-AGENTPOISON-0"}
    assert exposed_cases["REAL-FARMA-1"].status == "EXPOSURE_ESTABLISHED"
    assert exposed_cases["REAL-DSRM-1"].status == "EXPOSURE_ESTABLISHED"


@pytest.mark.skipif(not (_ledger_exists() and _exposure_decisions_recorded()), reason="real exposure decisions not recorded yet")
def test_a_memory_never_in_context_is_correctly_not_exposed():
    """REAL-AGENTPOISON-0 was never part of either real task's context --
    a genuine real negative, requiring no special construction."""
    decision_ids = record_real_exposure_decisions(DEFAULT_LEDGER_DIR)
    cases = evaluate_exposure_attribution(DEFAULT_LEDGER_DIR, decision_ids)
    negative_cases = [c for c in cases if c.memory_id == "REAL-AGENTPOISON-0"]
    assert len(negative_cases) == 2
    assert all(c.status == "EXPOSURE_NOT_ESTABLISHED" for c in negative_cases)


@pytest.mark.skipif(not (_ledger_exists() and _exposure_decisions_recorded()), reason="real exposure decisions not recorded yet")
def test_dsrm1_is_exposed_but_not_influential_a_real_concrete_case_of_the_distinction():
    """The methodology's own central point (Section 5) -- exposure without
    influence -- shown here on real data rather than only the hand-authored
    Scenario E: REAL-DSRM-1 is really exposed to its real decision, and
    (per influence_attribution_case.py's own already-recorded real result)
    masking it did NOT change the real answer -- INFLUENCE_NOT_ESTABLISHED."""
    from attribution.wiring.influence import attribute_influence

    decision_ids = record_real_exposure_decisions(DEFAULT_LEDGER_DIR)
    cases = evaluate_exposure_attribution(DEFAULT_LEDGER_DIR, decision_ids)
    dsrm_case = next(c for c in cases if c.memory_id == "REAL-DSRM-1")
    assert dsrm_case.status == "EXPOSURE_ESTABLISHED"

    event_ledger = CanonicalEventLedger(DEFAULT_LEDGER_DIR / "events", CanonicalMemoryLedger(DEFAULT_LEDGER_DIR / "memory"))
    influence_result = attribute_influence(
        "REAL-DSRM-1", run_id="test", event_ledger=event_ledger, task_id="phase13-influence-task-not-established",
    )
    assert influence_result.status == "INFLUENCE_NOT_ESTABLISHED"
