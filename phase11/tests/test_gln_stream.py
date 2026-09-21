"""Phase 11.3 -- the real per-memory event stream runs end to end and
produces a real, measured answer (any of the three honest outcomes) to
Phase 10's own open risk-decay question."""

from __future__ import annotations

from phase11.gln.stream import run_risk_decay_study


def test_risk_decay_study_runs_end_to_end_with_real_n():
    result = run_risk_decay_study()
    assert result["held_out_benign"]["n"] > 0
    assert result["held_out_poison"]["n"] > 0
    for key in ("mean_risk_at_first_retrieval", "mean_risk_after_sustained_safe_use"):
        assert 0.0 <= result["held_out_benign"][key] <= 1.0
