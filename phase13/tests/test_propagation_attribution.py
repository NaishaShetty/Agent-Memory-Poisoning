"""Phase 13 -- tests for real PROPAGATION attribution. Fast (pure ledger
reads, no LLM calls)."""

from __future__ import annotations

import pytest

from phase13.ledger_setup import DEFAULT_LEDGER_DIR
from phase13.propagation_attribution import compute_propagation_attribution


def _ledger_exists() -> bool:
    return (DEFAULT_LEDGER_DIR / "memory" / "records.jsonl").exists()


@pytest.mark.skipif(not _ledger_exists(), reason="real attribution ledger not built yet")
def test_all_real_derived_memories_are_correctly_reconstructed():
    outcome = compute_propagation_attribution()
    assert outcome["n_derived_memories_checked"] > 0
    assert outcome["propagation_reconstruction_accuracy"] == 1.0


@pytest.mark.skipif(not _ledger_exists(), reason="real attribution ledger not built yet")
def test_multi_source_cases_are_correctly_flagged_ambiguous_here_too():
    outcome = compute_propagation_attribution()
    results = outcome["results"]
    multi_source_ids = [mid for mid, r in results.items() if r.status == "MULTIPLE_POSSIBLE_SOURCES"]
    assert len(multi_source_ids) >= 3  # the 3 real multi-source cases built earlier in Phase 13


@pytest.mark.skipif(not _ledger_exists(), reason="real attribution ledger not built yet")
def test_a_real_memory_with_no_attack_ancestor_is_correctly_not_reachable():
    outcome = compute_propagation_attribution()
    if outcome["negative_case_status"] is not None:
        assert outcome["negative_case_status"] == "NO_ATTACK_ORIGIN"
