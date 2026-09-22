"""Phase 13 -- tests for real, persistent event-ledger setup. Real, slow
(runs the full real `compute_pr()` measurement once, ~60 real local LLM
calls via Ollama) -- skipped if the local Ollama server is not reachable.
"""

from __future__ import annotations

import pytest

from phase11.data.real_corpus import real_poison_scenarios
from phase12.propagation.ollama_provider import OllamaProvider
from phase13.ledger_setup import assert_ledger_disjoint_from_held_out_pools, build_persistent_real_ledgers
from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger


@pytest.mark.slow
def test_build_persistent_real_ledgers_writes_every_real_poison_scenario(tmp_path):
    provider = OllamaProvider()
    if not provider.health_check():
        pytest.skip("Ollama server not reachable at 127.0.0.1:11434 -- this test requires it")

    ledger_dir = tmp_path / "real_attribution_ledgers"
    build_persistent_real_ledgers(ledger_dir, provider=provider)

    memory_ledger = CanonicalMemoryLedger(ledger_dir / "memory")
    pool = real_poison_scenarios()
    for m in pool.memories:
        record = memory_ledger.get(m.scenario_id)
        assert record is not None, f"expected {m.scenario_id} to be persisted"
        assert record.content["text"] == m.content_text

    # At least one real derived event should exist -- PR's own real
    # baseline measured 14/15 scenarios propagating in a majority of
    # their real, tested positions (see docs/phase12/
    # PHASE12_SECURITY_METRICS_REPORT.md Section 2.2).
    event_ledger = CanonicalEventLedger(ledger_dir / "events", memory_ledger)
    derived_events = [e for e in event_ledger.all_events() if e.event_type == "derived"]
    assert len(derived_events) > 0, "expected at least one real derivation event to be persisted"

    assert_ledger_disjoint_from_held_out_pools(ledger_dir)
