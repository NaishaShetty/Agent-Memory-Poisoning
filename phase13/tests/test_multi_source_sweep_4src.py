"""Phase 13 -- tests for the real 4-source multi-source sweep case. Fast
(reads the already-recorded real ledger entry -- the real LLM call happens
once, via `python -m phase13.multi_source_sweep`, not per test run)."""

from __future__ import annotations

import pytest

from attribution.wiring.lineage import attribute_lineage
from phase13.ledger_setup import DEFAULT_LEDGER_DIR
from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger

FOUR_SOURCE_DERIVED_ID = "REAL-MULTI-SOURCE-DERIVED-4SRC-1"
FOUR_SOURCE_IDS = ("REAL-DSRM-0", "REAL-FARMA-0", "REAL-MPBENCH-2", "REAL-SLEEPER-0")


def _case_recorded() -> bool:
    memory_ledger = CanonicalMemoryLedger(DEFAULT_LEDGER_DIR / "memory")
    return memory_ledger.get(FOUR_SOURCE_DERIVED_ID) is not None


@pytest.mark.skipif(not _case_recorded(), reason="real 4-source sweep case not recorded yet")
def test_four_source_case_names_all_four_real_sources():
    memory_ledger = CanonicalMemoryLedger(DEFAULT_LEDGER_DIR / "memory")
    event_ledger = CanonicalEventLedger(DEFAULT_LEDGER_DIR / "events", memory_ledger)
    result = attribute_lineage(FOUR_SOURCE_DERIVED_ID, run_id="test", event_ledger=event_ledger, full_chain=True)
    assert result.status == "MULTIPLE_POSSIBLE_SOURCES"
    assert set(result.candidate_source_ids) == set(FOUR_SOURCE_IDS)
