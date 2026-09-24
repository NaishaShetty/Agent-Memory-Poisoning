"""Phase 14 -- tests for the real Consolidation Guard stage check on Track B.
Real (each test makes real local-LLM calls via Ollama)."""

from __future__ import annotations

import pytest

from phase12.propagation.ollama_provider import OllamaProvider
from phase14.track_b_consolidation_stage import run_all_consolidation_stage_cases


@pytest.mark.slow
def test_all_nine_real_cases_are_protected_at_the_consolidation_stage():
    provider = OllamaProvider()
    if not provider.health_check():
        pytest.skip("Ollama server not reachable at 127.0.0.1:11434 -- this test requires it")

    results = run_all_consolidation_stage_cases(provider=provider)
    assert len(results) == 9
    unprotected = [r.case.target_scenario_id for r in results if not r.protected]
    assert not unprotected, f"real, unprotected cases at the consolidation stage: {unprotected}"
