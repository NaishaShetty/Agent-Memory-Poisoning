"""Phase 13 -- tests for the real attribution metrics computation. Fast
(reads the already-persisted real ledger at `phase13/data/real_attribution_
ledgers/` -- no LLM calls). Requires that ledger to already exist (run
`phase13.ledger_setup.build_persistent_real_ledgers()` first if it does not).
"""

from __future__ import annotations

import pytest

from phase13.attribution_metrics import compute_attribution_metrics
from phase13.ledger_setup import DEFAULT_LEDGER_DIR


def _ledger_exists() -> bool:
    return (DEFAULT_LEDGER_DIR / "memory" / "records.jsonl").exists()


@pytest.mark.skipif(not _ledger_exists(), reason="real attribution ledger not built yet")
def test_source_accuracy_is_real_and_correct():
    result = compute_attribution_metrics()
    assert result.n_poison_scenarios == 15
    assert result.origin_family_match_accuracy == 1.0
    assert result.origin_injection_id_accuracy == 1.0
    expected_families = {
        "REAL-DSRM-0": "dsrm", "REAL-DSRM-1": "dsrm", "REAL-DSRM-2": "dsrm",
        "REAL-FARMA-0": "farma", "REAL-FARMA-1": "farma", "REAL-FARMA-2": "farma",
        "REAL-MPBENCH-0": "mpbench", "REAL-MPBENCH-1": "mpbench", "REAL-MPBENCH-2": "mpbench",
        "REAL-MINJA-0": "minja", "REAL-MINJA-1": "minja", "REAL-MINJA-2": "minja",
        "REAL-AGENTPOISON-0": "agentpoison", "REAL-MEMORYGRAFT-0": "memorygraft",
        "REAL-SLEEPER-0": "sleeper_memory_poisoning",
    }
    assert result.per_scenario_origin == expected_families


@pytest.mark.skipif(not _ledger_exists(), reason="real attribution ledger not built yet")
def test_origin_ambiguity_and_false_attribution_are_structurally_zero():
    """Real, expected, NOT a surprising finding: `attribute_origin()`'s own
    docstring discloses that `MULTIPLE_POSSIBLE_SOURCES` is structurally
    unreachable for origin (the ledger's own `DuplicateMemoryClaimError`
    invariant prevents two attack_injection events from claiming the same
    memory_id) -- 0% ambiguity here tests that the invariant holds, not
    that attribution made a hard judgment call correctly."""
    result = compute_attribution_metrics()
    assert result.origin_ambiguity_rate == 0.0
    assert result.origin_false_attribution_rate == 0.0


@pytest.mark.skipif(not _ledger_exists(), reason="real attribution ledger not built yet")
def test_path_fidelity_matches_real_pr_derivation_count():
    """Real cross-check: the number of derivation events attribution finds
    must match PR's own real, measured propagation count for this specific
    ledger build (whatever it is -- not asserted to any fixed number, since
    the underlying LLM is not perfectly deterministic run to run).

    UPDATE (2026-09-22, explicitly authorized): `lineage_ambiguity_rate`
    was originally asserted at 0.0 -- true before `phase13/
    multi_source_lineage_case.py` added one real, genuine multi-source
    derivation to the ledger. It is no longer 0.0 by construction (one
    real branching case now exists) -- this test now asserts path fidelity
    stays 100% (the metric correctly reconstructs the real parent set even
    for the branching case) without pinning the exact ambiguity rate,
    which depends on how many derivation events PR's own non-deterministic
    run produced this build (see `test_multi_source_lineage_case.py` for
    the dedicated, precise check that this specific case is ambiguous)."""
    result = compute_attribution_metrics()
    assert result.n_derivation_events > 0
    assert result.path_fidelity_accuracy == 1.0
    assert 0.0 <= result.lineage_ambiguity_rate <= 1.0


@pytest.mark.skipif(not _ledger_exists(), reason="real attribution ledger not built yet")
def test_time_to_attribute_is_measured_not_assumed():
    result = compute_attribution_metrics()
    assert result.mean_time_to_attribute_origin_ms > 0.0
    assert result.mean_time_to_attribute_lineage_ms is None or result.mean_time_to_attribute_lineage_ms > 0.0


def _independent_ground_truth_exists() -> bool:
    from phase13.ledger_setup import INDEPENDENT_GROUND_TRUTH_FILENAME

    return (DEFAULT_LEDGER_DIR / INDEPENDENT_GROUND_TRUTH_FILENAME).exists()


@pytest.mark.skipif(
    not (_ledger_exists() and _independent_ground_truth_exists()),
    reason="real ledger or independent injection ground truth not built yet",
)
def test_false_attribution_rate_is_now_checked_against_independent_ground_truth():
    """UPDATE (2026-09-22, explicitly authorized): `origin_false_attribution_
    rate` used to be checked ONLY against ground truth reconstructed from the
    same persisted ledger record `attribute_origin()` itself reads -- a
    tautological check that could never surface a real bug. This asserts the
    independent (pre-round-trip) comparison actually ran (is not silently
    falling back to the circular one) and both real rates -- with this
    project's ledger/injection wiring intact -- come out 0.0, a real,
    non-circular confirmation rather than a structurally guaranteed one."""
    result = compute_attribution_metrics()
    assert result.origin_false_attribution_rate == 0.0
    assert result.origin_false_attribution_rate_circular == 0.0
