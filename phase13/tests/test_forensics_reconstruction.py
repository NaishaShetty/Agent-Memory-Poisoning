"""Phase 13 -- tests for real FORENSICS reconstruction. Fast (reads the
already-recorded real ledger; the one real agent run needed for the DECISION
case is the SAME already-deterministic established case
`influence_attribution_case.py` uses)."""

from __future__ import annotations

import pytest

from phase13.forensics_reconstruction import run_decision_case, run_memory_case
from phase13.ledger_setup import DEFAULT_LEDGER_DIR


def _ledger_exists() -> bool:
    return (DEFAULT_LEDGER_DIR / "memory" / "records.jsonl").exists()


@pytest.mark.skipif(not _ledger_exists(), reason="real attribution ledger not built yet")
def test_decision_case_exposes_and_origins_both_real_memories():
    case = run_decision_case()
    assert set(case.walked_memory_ids) == {"REAL-FARMA-1", "REAL-MPBENCH-0"}
    assert all(v.status == "EXPOSURE_ESTABLISHED" for v in case.exposure.values())
    assert case.per_memory_origin["REAL-FARMA-1"].attack_id == "farma"
    assert case.per_memory_origin["REAL-MPBENCH-0"].attack_id == "mpbench"
    # Two distinct real attack families were exposed to the same real decision --
    # the "worst hop wins" rule must not round this up to single-origin confidence.
    assert case.chain_confidence == "MULTIPLE_PLAUSIBLE_ORIGINS"


@pytest.mark.skipif(not _ledger_exists(), reason="real attribution ledger not built yet")
def test_memory_case_skips_exposure_and_reports_the_real_branch():
    case = run_memory_case()
    assert case.exposure == {}
    lineage = case.per_memory_lineage["REAL-MULTI-SOURCE-DERIVED-1"]
    assert lineage.status == "MULTIPLE_POSSIBLE_SOURCES"
    assert set(lineage.candidate_source_ids) == {"REAL-DSRM-1", "REAL-FARMA-1"}
    assert case.per_memory_origin["REAL-DSRM-1"].attack_id == "dsrm"
    assert case.per_memory_origin["REAL-FARMA-1"].attack_id == "farma"
    assert case.chain_confidence == "MULTIPLE_PLAUSIBLE_ORIGINS"


@pytest.mark.skipif(not _ledger_exists(), reason="real attribution ledger not built yet")
def test_reconstruction_is_deterministic_across_repeated_calls():
    """Section 9's own non-negotiable determinism rule: re-running against
    unchanged ledger state must produce a byte-identical reconstruction_id."""
    first = run_memory_case()
    second = run_memory_case()
    assert first.reconstruction_id == second.reconstruction_id
