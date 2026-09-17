"""Phase 7.7 -- tests for the adaptive-evasion check: paraphrase robustness and
the shallow-and-wide adaptive variant, both against real, live-instrumented
ledgers (not mocked signal calls).
"""

from __future__ import annotations

import pytest

from phase7.propagation.adaptive_evasion_check import run_paraphrase_robustness_check, run_shallow_and_wide_check


def test_structural_signals_are_bit_identical_under_paraphrase(tmp_path):
    result = run_paraphrase_robustness_check(storage_dir=tmp_path / "paraphrase")

    assert result.signals_match is True
    for name in result.verbatim_signals:
        v = result.verbatim_signals[name]
        p = result.paraphrased_signals[name]
        assert v.value == p.value, f"{name} differs under paraphrase: verbatim={v.value} paraphrased={p.value}"
        assert v.evidence_kinds == p.evidence_kinds

    # Sanity: the two scenarios' content really was different -- otherwise
    # this test would trivially pass for the wrong reason.
    assert result.verbatim_signals["fan_out_rate"].value > 0


def test_shallow_and_wide_deep_chain_maximizes_cycle_reinforcement_depth(tmp_path):
    result = run_shallow_and_wide_check(storage_dir=tmp_path / "evasion", n=4)
    assert result.deep_chain_depth.value == 4.0
    assert result.deep_chain_fan_out.value == 4.0


def test_shallow_and_wide_single_root_evades_depth_but_not_fan_out(tmp_path):
    result = run_shallow_and_wide_check(storage_dir=tmp_path / "evasion2", n=4)
    # Flattening the same 4 children under one root instead of a chain:
    # fan_out_rate is UNCHANGED (still counts all 4 real DERIVED_FROM edges
    # landing in the footprint) -- cycle_reinforcement_depth collapses to 1.
    assert result.wide_shallow_fan_out.value == 4.0
    assert result.wide_shallow_depth.value == 1.0
    assert result.wide_shallow_depth.value < result.deep_chain_depth.value


def test_shallow_and_wide_independent_roots_evade_both_signals(tmp_path):
    result = run_shallow_and_wide_check(storage_dir=tmp_path / "evasion3", n=4)
    # The real, disclosed structural blind spot: splitting the SAME total
    # volume (4 new memories) across 4 independent roots keeps EVERY
    # individual footprint's fan_out_rate/cycle_reinforcement_depth at the
    # per-hop minimum (1), even though the campaign-wide total is identical
    # to the deep-chain scenario.
    assert len(result.independent_roots_fan_out) == 4
    assert len(result.independent_roots_depth) == 4
    assert all(r.value == 1.0 for r in result.independent_roots_fan_out)
    assert all(r.value == 1.0 for r in result.independent_roots_depth)

    total_independent_fan_out = sum(r.value for r in result.independent_roots_fan_out)
    assert total_independent_fan_out == result.deep_chain_fan_out.value  # same real total volume
    # ...but the PER-FOOTPRINT signal never sees that total -- each root's own
    # fan_out_rate is far below the deep-chain root's single-footprint value.
    assert all(r.value < result.deep_chain_fan_out.value for r in result.independent_roots_fan_out)
