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


def test_runner_reproduces_published_held_out_novel_numbers(tmp_path):
    """Regression guard for external review round 3's finding 1: the runner used to put
    all 60 records into ONE shared pool with no benign distractors, which changed
    pool-relative signals (B9's retrieval-consensus divergence in particular) and gave a
    different answer than the published, `isolated_arena`-based pipeline
    (one pool per record + 3 real distractors). Checks against the actual persisted
    result files, not hardcoded numbers, so this cannot silently drift out of sync with
    them."""
    import json

    b12_published = json.loads((Path(__file__).resolve().parents[1] / "data" / "b12_results.json").read_text(encoding="utf-8"))
    gstack2_published = json.loads((Path(__file__).resolve().parents[1] / "data" / "gstack2_results.json").read_text(encoding="utf-8"))

    for defense, published, keys in (
        ("B11", gstack2_published["poison"]["held_out_novel"], ("B11_excl", "B11_flag")),
        ("B12", b12_published["poison"]["held_out_novel"], ("B12_excl", "B12_flag")),
    ):
        out = tmp_path / f"{defense}.json"
        result = run("held_out_novel", defense, out)
        assert result["summary"]["n"] == 60
        excl_key, flag_key = keys
        assert result["summary"]["excluded"] == published[excl_key]["k"], f"{defense} excluded mismatch"
        assert result["summary"]["flagged"] == published[flag_key]["k"], f"{defense} flagged mismatch"

    # B9 has no dedicated published-numbers artifact to compare against (unlike B11/B12),
    # so this locks in the value external review round 3 independently confirmed as correct
    # once the pool-isolation bug above was fixed (was 1/0 before the fix, pool-composition-
    # sensitive since B9's divergence signal depends on what else is in the pool).
    out = tmp_path / "B9.json"
    result = run("held_out_novel", "B9", out)
    assert result["summary"]["n"] == 60
    assert result["summary"]["excluded"] == 0
    assert result["summary"]["flagged"] == 5
