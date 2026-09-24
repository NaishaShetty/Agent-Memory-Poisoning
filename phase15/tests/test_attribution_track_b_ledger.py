"""Phase 15 -- tests for the real, second attribution ledger (a genuinely
different real defense config + real distractor content). Real (no LLM
calls -- only ledger construction and graph-structural attribution)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from phase15.attribution_track_b_ledger import admitted_scenario_ids_under, build_and_check_origin_attribution

TRACK_B_FAMILIES = {"DSRM", "FARMA", "MPBENCH"}


def _clean(ledger_dir: Path) -> Path:
    if ledger_dir.exists():
        shutil.rmtree(ledger_dir)
    return ledger_dir


def test_b2_admits_all_nine_real_track_b_scenarios():
    """Real, already-established finding (Phase 14): B2 alone does not
    protect against isolated poison, so all 9 real cases stay admitted."""
    ids = admitted_scenario_ids_under("B2")
    assert len(ids) == 9
    assert {sid.split("-")[1] for sid in ids} == TRACK_B_FAMILIES


def test_b9_admits_none():
    """Real, already-established finding (Phase 14/15): B9 real-quarantines
    all 9 real Track B cases."""
    assert admitted_scenario_ids_under("B9") == ()


def test_real_origin_attribution_under_a_genuinely_different_config_and_distractor_content(tmp_path):
    """The real, new empirical confirmation this module exists for: origin
    attribution accuracy stays 100% under a real, second ledger built with
    DIFFERENT real distractor content (LoCoMo QA-counterfactual pool, not
    Phase 13's `_DISTRACTOR_TURNS`) and a real, non-B0 defense decision
    (B2) -- supporting the source-level graph-structural argument with real
    empirical data, not just re-asserting it."""
    ledger_dir = _clean(tmp_path / "attribution_track_b_b2")
    result = build_and_check_origin_attribution(ledger_dir, "B2")
    assert result["n_admitted"] == 9
    assert result["origin_attribution_accuracy"] == 1.0
    assert result["ambiguity_rate"] == 0.0


def test_b9_all_quarantined_case_handled_without_crashing(tmp_path):
    ledger_dir = _clean(tmp_path / "attribution_track_b_b9")
    result = build_and_check_origin_attribution(ledger_dir, "B9")
    assert result["n_admitted"] == 0
    assert "note" in result


@pytest.mark.slow
def test_lineage_check_on_second_ledger_runs_real_consolidation(tmp_path):
    """Real (needs a reachable local Ollama, like Phase 12/13's own PR step):
    the second ledger's lineage/path-fidelity check. Small real n (how many
    scenarios propagate depends on the real LLM), so this asserts structure
    and that any recorded derivation traces back correctly, not a pinned n."""
    from phase15.attribution_track_b_ledger import build_and_check_lineage

    result = build_and_check_lineage(_clean(tmp_path / "lineage_b2"), "B2")
    assert result["origin_attribution_accuracy"] == 1.0
    if result["n_derivation_events"]:
        assert result["path_fidelity_accuracy"] == 1.0
