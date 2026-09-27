"""Smoke test for the Phase 17 canonical benchmark runner."""
from pathlib import Path

from phase17.bench_runner import run


def test_runner_end_to_end(tmp_path):
    out = tmp_path / "smoke.json"
    result = run("held_out_novel", "B12", out)
    assert out.exists()
    assert result["manifest"]["defense"] == "B12"
    assert result["manifest"]["split"] == "held_out_novel"
    assert result["summary"]["n"] == 60
    assert 0 <= result["summary"]["excluded"] <= result["summary"]["n"]
    assert result["manifest"]["git_commit"]  # non-empty, either a real hash or the disclosed fallback string


def test_runner_rejects_unknown_names(tmp_path):
    import pytest

    with pytest.raises(ValueError):
        run("not_a_real_split", "B12", tmp_path / "x.json")
    with pytest.raises(ValueError):
        run("held_out_novel", "NOT_A_CONFIG", tmp_path / "x.json")
