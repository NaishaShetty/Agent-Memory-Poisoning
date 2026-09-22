"""Phase 13 -- tests for the real multi-source lineage stress case. Fast
(reads the already-recorded real ledger entry -- the real LLM call and
similarity check happen once, via `python -m phase13.multi_source_lineage_case`,
not per test run).
"""

from __future__ import annotations

import pytest

from attribution.metrics import ambiguity_rate, lineage_reconstruction_accuracy
from attribution.wiring.lineage import attribute_lineage
from phase13.ledger_setup import DEFAULT_LEDGER_DIR
from phase13.multi_source_lineage_case import DERIVED_MEMORY_ID, SOURCE_SCENARIO_A, SOURCE_SCENARIO_B
from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger


def _case_recorded() -> bool:
    memory_ledger = CanonicalMemoryLedger(DEFAULT_LEDGER_DIR / "memory")
    return memory_ledger.get(DERIVED_MEMORY_ID) is not None


@pytest.mark.skipif(not _case_recorded(), reason="real multi-source case not recorded yet")
def test_multi_source_case_is_correctly_flagged_as_ambiguous():
    memory_ledger = CanonicalMemoryLedger(DEFAULT_LEDGER_DIR / "memory")
    event_ledger = CanonicalEventLedger(DEFAULT_LEDGER_DIR / "events", memory_ledger)
    result = attribute_lineage(DERIVED_MEMORY_ID, run_id="test", event_ledger=event_ledger, full_chain=True)
    assert result.status == "MULTIPLE_POSSIBLE_SOURCES"
    assert set(result.candidate_source_ids) == {SOURCE_SCENARIO_A, SOURCE_SCENARIO_B}


@pytest.mark.skipif(not _case_recorded(), reason="real multi-source case not recorded yet")
def test_lineage_reconstruction_accuracy_correctly_handles_the_real_branch():
    """Real, non-trivial check: `lineage_reconstruction_accuracy()` must
    still score this case correct (found == real ground truth set), even
    though the result status is MULTIPLE_POSSIBLE_SOURCES, not UNIQUE --
    the metric function's own real logic (not a special case added here)
    already handles this by comparing `candidate_source_ids` as a set."""
    memory_ledger = CanonicalMemoryLedger(DEFAULT_LEDGER_DIR / "memory")
    event_ledger = CanonicalEventLedger(DEFAULT_LEDGER_DIR / "events", memory_ledger)
    result = attribute_lineage(DERIVED_MEMORY_ID, run_id="test", event_ledger=event_ledger, full_chain=True)
    accuracy = lineage_reconstruction_accuracy(
        {DERIVED_MEMORY_ID: result}, {DERIVED_MEMORY_ID: (SOURCE_SCENARIO_A, SOURCE_SCENARIO_B)},
    )
    assert accuracy == 1.0


@pytest.mark.skipif(not _case_recorded(), reason="real multi-source case not recorded yet")
def test_ambiguity_rate_is_nonzero_once_a_genuine_branch_exists():
    """Regression for the real gap this case was built to close: prior to
    this case, `lineage_ambiguity_rate` was trivially 0.0% because no
    genuine multi-parent derivation existed in the real ledger. With one
    real branch present, the rate must be strictly positive."""
    memory_ledger = CanonicalMemoryLedger(DEFAULT_LEDGER_DIR / "memory")
    event_ledger = CanonicalEventLedger(DEFAULT_LEDGER_DIR / "events", memory_ledger)
    from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger as _CEL

    derived_events = [e for e in event_ledger.all_events() if e.event_type == "derived"]
    results = {
        e.target_memory_id: attribute_lineage(e.target_memory_id, run_id="test", event_ledger=event_ledger, full_chain=True)
        for e in derived_events
    }
    rate = ambiguity_rate(list(results.values()))
    assert rate > 0.0
