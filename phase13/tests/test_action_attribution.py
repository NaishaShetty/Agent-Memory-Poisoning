"""Phase 13 -- tests for real ACTION attribution. Fast (reads the
already-recorded real ledger; the one real agent run needed is the SAME
already-cached-by-determinism established case `influence_attribution_case.py`
uses -- temperature=0, seed=42)."""

from __future__ import annotations

import pytest

from phase13.action_attribution import evaluate_action_attribution
from phase13.ledger_setup import DEFAULT_LEDGER_DIR


def _ledger_exists() -> bool:
    return (DEFAULT_LEDGER_DIR / "memory" / "records.jsonl").exists()


@pytest.mark.skipif(not _ledger_exists(), reason="real attribution ledger not built yet")
def test_action_attribution_matches_direct_exposure_attribution():
    result = evaluate_action_attribution()
    assert result["action_status"] == "EXPOSURE_ESTABLISHED"
    assert result["matches_direct_exposure"] is True


@pytest.mark.skipif(not _ledger_exists(), reason="real attribution ledger not built yet")
def test_action_attribution_correctly_reports_a_real_negative():
    result = evaluate_action_attribution()
    assert result["negative_case_status"] == "EXPOSURE_NOT_ESTABLISHED"
