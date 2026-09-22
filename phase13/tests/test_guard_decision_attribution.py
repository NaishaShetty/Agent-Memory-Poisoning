"""Phase 13 -- tests for real Consolidation Guard decision attribution.
Fast: reads the already-persisted real ledger; the one real, fresh
`compute_pr()` call this module needs happens once per test run (~60 real
local LLM calls, same cost `test_ledger_setup.py`'s own slow test already
pays) -- marked slow and skipped if Ollama is unreachable, consistent with
this project's existing discipline for real-LLM-cost tests.
"""

from __future__ import annotations

import pytest

from phase12.propagation.ollama_provider import OllamaProvider
from phase13.guard_decision_attribution import compute_guard_decision_attribution
from phase13.ledger_setup import DEFAULT_LEDGER_DIR


def _ledger_exists() -> bool:
    return (DEFAULT_LEDGER_DIR / "memory" / "records.jsonl").exists()


@pytest.mark.slow
@pytest.mark.skipif(not _ledger_exists(), reason="real attribution ledger not built yet")
def test_real_guard_interventions_are_found_and_traced():
    provider = OllamaProvider()
    if not provider.health_check():
        pytest.skip("Ollama server not reachable at 127.0.0.1:11434 -- this test requires it")

    result = compute_guard_decision_attribution(provider=provider)

    # Real, previously measured finding (docs/phase12's own report): the
    # Consolidation Guard's real catch rate on real propagated content is
    # very high on this corpus -- some real guard interventions must exist
    # for this test to be meaningful at all.
    assert result.n_guard_interventions_found > 0

    for case in result.cases:
        # Every real case included here is, by construction, one the real
        # guard actually intervened on (guarded_action != ALLOW).
        assert case.guarded_action != "ALLOW"
        # LINEAGE must trace the real derived memory back to EXACTLY its real
        # poisoned parent -- never ambiguous for these single-source PR cases.
        assert case.lineage_status == "UNIQUE"
        assert case.lineage_traced_correctly
        # ORIGIN must trace that real poisoned parent to its real, correct
        # attack family.
        assert case.origin_traced_correctly

    assert result.fraction_fully_traced == 1.0


@pytest.mark.slow
@pytest.mark.skipif(not _ledger_exists(), reason="real attribution ledger not built yet")
def test_only_scenarios_with_a_real_persisted_derived_memory_are_checked():
    """Every real scenario this module reports on must actually have a real
    derived memory in the persisted ledger -- a scenario whose fresh
    `compute_pr()` run didn't propagate, or whose persisted ledger never
    recorded a derived memory for it, must never be silently checked against
    a derived memory that does not exist (this module skips it instead)."""
    provider = OllamaProvider()
    if not provider.health_check():
        pytest.skip("Ollama server not reachable at 127.0.0.1:11434 -- this test requires it")

    result = compute_guard_decision_attribution(provider=provider)
    assert 0 < result.n_guard_interventions_found <= 15

    from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger

    memory_ledger = CanonicalMemoryLedger(DEFAULT_LEDGER_DIR / "memory")
    for case in result.cases:
        assert memory_ledger.get(case.derived_memory_id) is not None
