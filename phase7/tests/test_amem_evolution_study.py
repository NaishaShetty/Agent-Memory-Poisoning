"""Phase 7.22 -- tests for amem_evolution_study.py: the first real exercise of
A-MEM's real note-evolution mechanism in this project's history, now that
Decision 2's llama-server backend is wired and reachable (2026-09-16). Self-skips
(mirroring phase5/tests/test_real_vendor_compatibility_gate.py's own
convention) in any environment where the real A-MEM stack, OR its live LLM
backend specifically, is unavailable -- run this under C:\\h4venv's interpreter
with a real, reachable llama-server (started with --reasoning off) to
actually validate it.
"""

from __future__ import annotations

import pytest

from phase7.propagation.amem_evolution_study import is_real_amem_available, run_amem_real_evolution_study


def _skip_if_unavailable():
    if not is_real_amem_available():
        pytest.skip(
            "RealAMemAdapter unavailable in this environment -- this test is written in full for a "
            "real-A-MEM-stack session (C:\\h4venv's interpreter) with a reachable llama-server; NOT VALIDATED here."
        )
    from phase3.evaluation.foundations_real.amem_real_adapter import _llama_server_reachable
    from phase3.evaluation.llm.provider import LlamaServerEndpoint

    if not _llama_server_reachable(LlamaServerEndpoint().base_url):
        pytest.skip(
            "The real A-MEM stack is importable, but its live LLM backend (llama-server, Decision 2's "
            "default) is not reachable right now -- a real, transient infrastructure gap distinct from the "
            "stack being unavailable; skip rather than fail, mirroring this project's own live-infra convention."
        )


def test_real_amem_evolution_actually_fires_when_available():
    _skip_if_unavailable()
    result = run_amem_real_evolution_study()

    assert result.total_notes == 3
    # The real, measured outcome (verified 2026-09-16, with a reachable
    # llama-server backend): notes 2 and 3 each evolve a real link to the
    # immediately preceding note's REAL memory_id (never a stale placeholder).
    # Real LLM sampling is not fully deterministic, so a genuine non-evolving
    # run remains possible even with the backend reachable -- if this ever
    # flakes despite the reachability check above, treat it the same way
    # test_foundation_conformance_h4.py's own analogous test was fixed: check
    # the real code path ran, not which of the two real outcomes it produced.
    assert result.real_evolution_confirmed is True
    assert result.evolved_count >= 1


def test_evolved_links_reference_real_memory_ids_not_stale_placeholders():
    _skip_if_unavailable()
    result = run_amem_real_evolution_study()
    known_ids = {o.memory_id for o in result.note_outcomes}
    for outcome in result.note_outcomes:
        if outcome.evolved:
            assert all(link in known_ids for link in outcome.links)
            assert "memory_id_1" not in outcome.links  # the old stale-failure placeholder, must not appear


def test_first_note_never_evolves_no_neighbors_exist_yet():
    _skip_if_unavailable()
    result = run_amem_real_evolution_study()
    first = result.note_outcomes[0]
    assert first.links == ()
    assert first.evolved is False
