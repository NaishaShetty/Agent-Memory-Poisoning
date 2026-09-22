"""Phase 13 -- tests for the real Consolidation Guard ALLOW-path check.
Slow (one real `compute_pr()` run) -- skipped if Ollama is unreachable."""

from __future__ import annotations

import pytest

from phase12.propagation.ollama_provider import OllamaProvider
from phase13.guard_allow_path_check import compute_guard_allow_path_check


@pytest.mark.slow
def test_real_allow_decisions_are_well_founded():
    provider = OllamaProvider()
    if not provider.health_check():
        pytest.skip("Ollama server not reachable at 127.0.0.1:11434 -- this test requires it")

    result = compute_guard_allow_path_check(provider=provider)
    assert result.n_quarantine_decisions_found > 0
    if result.n_allow_decisions_found > 0:
        assert result.fraction_well_founded == 1.0
        for case in result.cases:
            assert case.well_founded
