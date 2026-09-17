"""Phase 7.6 -- tests for run_farma_crowding_study(): a real, repeatable
measurement of FARMA's amplification-cluster crowding effect on top-K
retrieval, closing PHASE5_HANDOFF_REPORT.md Sec 5's named open question.
"""

from __future__ import annotations

import pytest

from phase5.wiring.lineage import EVIDENCE_OBSERVED_EVENT, REFERENCES
from phase7.propagation.crowding_study import run_farma_crowding_study


def test_farma_crowding_study_runs_a_real_trial_and_reports_a_real_measurement(tmp_path):
    result = run_farma_crowding_study(storage_dir=tmp_path / "farma-crowding")

    assert result.top_k == 8
    assert len(result.farma_cluster_memory_ids) == 11  # seed + 10 amplification cycles (paper default)
    assert len(result.benign_candidate_memory_ids) == 5
    assert len(result.selected_memory_ids) == result.top_k

    # farma_slots_occupied is a real count over the real selected set, never
    # assumed -- report it and let the reader see the actual measurement.
    assert 0 <= result.farma_slots_occupied <= result.top_k
    assert result.farma_slot_fraction == pytest.approx(result.farma_slots_occupied / result.top_k)

    assert result.footprint.member_ids == tuple(sorted(result.farma_cluster_memory_ids))
    assert result.re_entry_rate.evidence_kinds in ((), (EVIDENCE_OBSERVED_EVENT,))


def test_farma_amplification_content_dominates_the_unrelated_benign_pool(tmp_path):
    # This is the actual, real reproduction of the handoff report's anecdote:
    # FARMA's cluster all shares near-identical target_question token/entity
    # overlap ("Melanie", "camping"), while the benign candidates are
    # deliberately topically unrelated -- the real, frozen hybrid-selection
    # algorithm should prefer the FARMA cluster for a query matching its own
    # target_question, crowding out most or all of the unrelated benign pool.
    result = run_farma_crowding_study(storage_dir=tmp_path / "farma-crowding-dominance")
    assert result.farma_slots_occupied >= result.top_k - 1, (
        f"expected FARMA's amplification cluster to occupy nearly all {result.top_k} slots against an "
        f"unrelated benign pool; only occupied {result.farma_slots_occupied}. Selected: {result.selected_memory_ids}"
    )


def test_crowding_study_is_deterministic_given_the_same_real_inputs(tmp_path):
    r1 = run_farma_crowding_study(storage_dir=tmp_path / "run1")
    r2 = run_farma_crowding_study(storage_dir=tmp_path / "run2")
    assert r1.selected_memory_ids == r2.selected_memory_ids
    assert r1.farma_slots_occupied == r2.farma_slots_occupied


def test_smaller_amplification_cluster_still_produces_a_valid_measurement(tmp_path):
    result = run_farma_crowding_study(storage_dir=tmp_path / "small-cluster", num_amplification_cycles=2)
    assert len(result.farma_cluster_memory_ids) == 3  # seed + 2 cycles
    assert 0 <= result.farma_slots_occupied <= result.top_k


def test_re_entry_rate_reflects_whether_the_single_task_was_crowded(tmp_path):
    result = run_farma_crowding_study(storage_dir=tmp_path / "re-entry-check")
    crowded = result.farma_slots_occupied >= 2
    expected_rate = 1.0 if crowded else 0.0
    assert result.re_entry_rate.value == pytest.approx(expected_rate)
    assert result.re_entry_rate.detail["crowded_task_ids"] == ((result.task_id,) if crowded else ())


def test_farma_own_cites_self_reference_is_invisible_to_the_references_edge_type(tmp_path):
    # Regression for the disclosed finding in crowding_study.py's own
    # docstring: FARMA's real, structured self-citation (cites) is never
    # rendered into stored content as a literal [memory_id] substring, so
    # derive_references_edges() finds nothing for this cluster even though the
    # attack's own "self-referential reinforcement" is real at the metadata
    # level. If this ever starts failing, FARMA's render_content_text() (or
    # derive_references_edges()) changed in a way that makes this citation
    # visible, and crowding_study.py's docstring should be updated accordingly.
    result = run_farma_crowding_study(storage_dir=tmp_path / "cites-visibility-check")
    references_within_cluster = [
        fe for fe in result.footprint.edges_of_type(REFERENCES)
        if fe.edge.source_id in result.farma_cluster_memory_ids and fe.edge.target_id in result.farma_cluster_memory_ids
    ]
    assert references_within_cluster == []
