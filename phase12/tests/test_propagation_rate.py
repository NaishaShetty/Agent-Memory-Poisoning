"""Phase 12 -- tests for the real Propagation Rate (PR) measurement.

`test_full_real_pr_measurement_end_to_end` makes 60 real local LLM calls
(via Ollama -- 4 context positions x 15 poison scenarios, see
`propagation_rate.py`'s own docstring for why 4 positions per scenario are
needed) and is therefore slow (a few minutes) -- it is the one test in this
file that genuinely exercises the real pipeline end-to-end; the others test
the mechanical/instrumentation pieces cheaply, without needing a real LLM
call each time.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from phase12.propagation.propagation_rate import (
    PROPAGATION_REFLECTS_POISON_THRESHOLD,
    PRPositionResult,
    PRScenarioResult,
    _record_real_derivation_events,
    _similarity,
    compute_pr,
)
from phase12.propagation.ollama_provider import OllamaProvider


def _make_scenario_result(scenario_id: str, poison_text: str, propagated: bool) -> PRScenarioResult:
    """Test helper: builds a `PRScenarioResult` as if every one of its 4
    positions agreed (all-propagated or all-not), for tests that only care
    about the aggregate `propagated`/`propagated_majority` outcome, not the
    real per-position detail."""
    summary = "a summary reflecting the poison" if propagated else "a summary about something else"
    poison_sim = 0.9 if propagated else 0.1
    max_distractor_sim = 0.1 if propagated else 0.6
    positions = tuple(
        PRPositionResult(
            position=i, summary_text=summary, poison_similarity=poison_sim,
            max_distractor_similarity=max_distractor_sim, propagated=propagated, guarded_action="ALLOW",
        )
        for i in range(4)
    )
    return PRScenarioResult(
        scenario_id=scenario_id, attack_family="test", poison_text=poison_text,
        positions=positions, propagated_fraction=1.0 if propagated else 0.0, propagated_majority=propagated,
        guard_catch_rate_of_propagated=0.0 if propagated else None,
        summary_text=summary, poison_similarity=poison_sim, max_distractor_similarity=max_distractor_sim,
        propagated=propagated,
    )


def test_similarity_is_high_for_identical_text_and_low_for_unrelated_text():
    from phase12.propagation.propagation_rate import _get_embedding_model

    model = _get_embedding_model()
    assert _similarity(model, "Caroline is going camping in June 2023.", "Caroline is going camping in June 2023.") > 0.99
    assert _similarity(model, "Caroline is going camping in June 2023.", "The weather forecast shows rain tomorrow.") < 0.4


def test_record_real_derivation_events_only_creates_a_derived_record_when_propagated(tmp_path):
    from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger

    results = (
        _make_scenario_result("TEST-PROPAGATED", "poison text", propagated=True),
        _make_scenario_result("TEST-NOT-PROPAGATED", "poison text", propagated=False),
    )
    _record_real_derivation_events(results, tmp_path)

    memory_ledger = CanonicalMemoryLedger(tmp_path / "memory")
    assert memory_ledger.get("TEST-PROPAGATED") is not None
    assert memory_ledger.get("TEST-PROPAGATED-derived-1") is not None
    assert memory_ledger.get("TEST-NOT-PROPAGATED") is not None
    assert memory_ledger.get("TEST-NOT-PROPAGATED-derived-1") is None


def test_ollama_provider_is_reachable():
    """A real, direct reachability check -- skips (not fails) if the local
    Ollama server this measurement depends on isn't running, since that is
    real external environment state, not a code defect."""
    provider = OllamaProvider()
    if not provider.health_check():
        pytest.skip("Ollama server not reachable at 127.0.0.1:11434 -- real PR measurement requires it")


@pytest.mark.slow
def test_full_real_pr_measurement_end_to_end():
    """Real, end-to-end: 60 real local LLM calls (4 context positions x 15
    poison scenarios -- see `propagation_rate.py`'s own docstring for why
    a single fixed position is not a reliable measurement), real embedding
    similarity checks, real ledger instrumentation. No specific PR value is
    asserted (a real 7B local model's real output is not something this
    test should pin to one number) -- only structural, real-measurement
    invariants, including internal consistency between the per-position
    detail and each scenario's own aggregate fraction."""
    provider = OllamaProvider()
    if not provider.health_check():
        pytest.skip("Ollama server not reachable at 127.0.0.1:11434 -- real PR measurement requires it")

    result = compute_pr()
    assert result.n_admitted == 15
    assert 0 <= result.n_propagated <= 15
    assert 0.0 <= result.overall_pr <= 1.0
    assert set(result.per_family_pr.keys()) == {
        "dsrm", "farma", "mpbench", "minja", "agentpoison", "memorygraft", "sleeper_memory_poisoning",
    }
    if result.overall_guard_catch_rate is not None:
        assert 0.0 <= result.overall_guard_catch_rate <= 1.0
    for r in result.per_scenario:
        assert len(r.positions) == 4
        assert {p.position for p in r.positions} == {0, 1, 2, 3}
        expected_fraction = sum(1 for p in r.positions if p.propagated) / 4
        assert r.propagated_fraction == expected_fraction
        assert r.propagated_majority == (expected_fraction >= 0.5)
        propagated_positions = [p for p in r.positions if p.propagated]
        if propagated_positions:
            expected_catch_rate = sum(1 for p in propagated_positions if p.guarded_action != "ALLOW") / len(propagated_positions)
            assert r.guard_catch_rate_of_propagated == expected_catch_rate
        else:
            assert r.guard_catch_rate_of_propagated is None
        for p in r.positions:
            assert p.guarded_action in ("ALLOW", "QUARANTINE")
            if p.propagated:
                assert p.poison_similarity >= PROPAGATION_REFLECTS_POISON_THRESHOLD
                assert p.poison_similarity > p.max_distractor_similarity
