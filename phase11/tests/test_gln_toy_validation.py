"""Phase 11.3 -- the GLN must pass its own constructed toy validation with a
known right answer BEFORE it is trusted on real project data."""

from __future__ import annotations

from phase11.gln.toy_validation import run_toy_validation


def test_gln_toy_validation_passes():
    result = run_toy_validation()
    assert result.passed, result


def test_gln_toy_validation_is_deterministic():
    first = run_toy_validation()
    second = run_toy_validation()
    assert first == second
