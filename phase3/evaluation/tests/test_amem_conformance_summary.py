"""Fix (2026-09-15) regression tests -- `RealAMemAdapter.conformance_summary()`,
closing the audit finding that the real, disclosed Ollama-unreachable confound
(every `add_memory()` call after the first genuinely attempts a real Ollama
connection this environment cannot reach, per the module's own docstring) was
recorded per-call but never aggregated into a quantified rate a campaign
consumer could read at a glance.

Constructs `RealAMemAdapter()` directly (no A-mem-sys import needed -- all
dataclass fields default, and `_record()` is called directly here to
populate `_records`) so this test exercises the real aggregation logic
without requiring the external `C:\\h4venv` environment this repository does
not have access to.
"""

from __future__ import annotations

from phase3.evaluation.foundations_real.amem_real_adapter import RealAMemAdapter
from phase3.evaluation.foundations_real.conformance_record import (
    ENVIRONMENT_LIMITATION,
    MODEL_DEPENDENT,
    REAL_FOUNDATION_CONFORMANCE,
)


def test_empty_adapter_reports_zero_operations():
    adapter = RealAMemAdapter()
    summary = adapter.conformance_summary()
    assert summary["total_operations"] == 0
    assert summary["model_dependent_count"] == 0
    assert summary["model_dependent_rate_by_operation"] == {}


def test_reproduces_the_real_disclosed_add_memory_pattern():
    """Reproduces the exact real pattern the module docstring discloses: the
    FIRST add_memory() call is pure REAL_FOUNDATION_CONFORMANCE (no LLM call
    attempted at all), every SUBSEQUENT call produces TWO records -- one
    REAL_FOUNDATION_CONFORMANCE (the real storage/embedding path, which
    genuinely succeeds) and one MODEL_DEPENDENT (the real, genuinely-attempted
    but Ollama-unreachable evolution step) -- exactly what add_memory()'s own
    code does."""
    adapter = RealAMemAdapter()
    adapter._import_ok = True

    # First call: pure REAL_FOUNDATION_CONFORMANCE, no evolution attempt.
    adapter._record("ADD_MEMORY", conformance_tag=REAL_FOUNDATION_CONFORMANCE, code_path_executed=True, reason="")
    # Three more calls, each producing the real two-record pattern.
    for _ in range(3):
        adapter._record("ADD_MEMORY", conformance_tag=REAL_FOUNDATION_CONFORMANCE, code_path_executed=True, reason="")
        adapter._record("ADD_MEMORY", conformance_tag=MODEL_DEPENDENT, code_path_executed=True, reason="Ollama unreachable.")

    summary = adapter.conformance_summary()
    assert summary["total_operations"] == 7  # 1 + 3*2
    assert summary["model_dependent_count"] == 3
    # 3 MODEL_DEPENDENT out of 7 total ADD_MEMORY records -> quantified, not buried.
    assert summary["model_dependent_rate_by_operation"]["ADD_MEMORY"] == 3 / 7
    assert summary["counts_by_operation_and_tag"][f"ADD_MEMORY:{MODEL_DEPENDENT}"] == 3
    assert summary["counts_by_operation_and_tag"][f"ADD_MEMORY:{REAL_FOUNDATION_CONFORMANCE}"] == 4


def test_different_operations_tracked_independently():
    adapter = RealAMemAdapter()
    adapter._import_ok = True
    adapter._record("ADD_MEMORY", conformance_tag=MODEL_DEPENDENT, code_path_executed=True, reason="x")
    adapter._record("RETRIEVE", conformance_tag=REAL_FOUNDATION_CONFORMANCE, code_path_executed=True)
    adapter._record("RETRIEVE", conformance_tag=REAL_FOUNDATION_CONFORMANCE, code_path_executed=True)

    summary = adapter.conformance_summary()
    assert summary["model_dependent_rate_by_operation"]["ADD_MEMORY"] == 1.0
    assert "RETRIEVE" not in summary["model_dependent_rate_by_operation"] or summary["model_dependent_rate_by_operation"]["RETRIEVE"] == 0.0


def test_environment_limitation_records_do_not_count_as_model_dependent():
    """A run where A-mem-sys was never even importable (ENVIRONMENT_LIMITATION)
    must not be conflated with the genuinely-attempted-but-Ollama-unreachable
    MODEL_DEPENDENT case -- these are different, disclosed facts."""
    adapter = RealAMemAdapter()
    adapter._import_ok = False
    adapter._record("ADD_MEMORY", conformance_tag=ENVIRONMENT_LIMITATION, reason="A-mem-sys not importable.")

    summary = adapter.conformance_summary()
    assert summary["model_dependent_count"] == 0
    assert summary["counts_by_operation_and_tag"][f"ADD_MEMORY:{ENVIRONMENT_LIMITATION}"] == 1
