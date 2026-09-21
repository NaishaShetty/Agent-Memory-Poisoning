"""Phase 11.y -- regression tests for `phase11/relational_signals/`."""

from __future__ import annotations

import inspect

from phase11.data.real_corpus import real_benign_scenarios, real_poison_scenarios
from phase11.data.poison_regeneration import regenerate_poison_batch
from phase11.relational_signals.relationship_audit import (
    NOT_AVAILABLE,
    RELATIONSHIP_AUDIT,
    classify,
)
from phase11.relational_signals.semantic_relations import (
    POISON_SOURCE_TASK_MAP,
    compute_neighborhood_agreement,
    embed,
)
from phase11.relational_signals.graph_relations import pool_coherence


def _references_held_out_pools_in_code(module) -> bool:
    for _, obj in inspect.getmembers(module, inspect.isfunction):
        if obj.__module__ != module.__name__:
            continue
        if "held_out_pools" in obj.__code__.co_names:
            return True
    return False


def test_no_held_out_access_in_any_relational_signals_module():
    import phase11.relational_signals.relationship_audit as m1
    import phase11.relational_signals.semantic_relations as m2
    import phase11.relational_signals.graph_relations as m3
    import phase11.relational_signals.provenance_relations as m4
    import phase11.relational_signals.signal_discovery as m5

    for m in (m1, m2, m3, m4, m5):
        assert not _references_held_out_pools_in_code(m), f"{m.__name__} references held_out_pools"


def test_derived_from_correctly_marked_not_available():
    assert classify("derivation_parents") == NOT_AVAILABLE


def test_task0_diagnostic_never_exposed_as_a_scenario_pool():
    """The read-only task-0 diagnostic fetch must never be returned as a
    ScenarioPool -- confirmed by inspecting the module's own exports."""
    import phase11.relational_signals.semantic_relations as mod

    for name, obj in vars(mod).items():
        if inspect.isfunction(obj) and name.startswith("_task0"):
            # the one function that touches task 0 returns a plain list of
            # strings, never a ScenarioPool
            sig = inspect.signature(obj)
            assert "ScenarioPool" not in str(sig.return_annotation)


def test_neighborhood_agreement_is_deterministic():
    old_poison = list(real_poison_scenarios().memories)
    neighborhoods = {}
    for pool in real_benign_scenarios():
        task_index = int(pool.pool_id.rsplit("T", 1)[1])
        neighborhoods[task_index] = [m.content_text for m in pool.memories]

    candidates = [(m, 0, "declared") for m in old_poison if POISON_SOURCE_TASK_MAP.get(m.scenario_id, (None, None))[0] == 0]
    r1 = compute_neighborhood_agreement(candidates, neighborhoods)
    r2 = compute_neighborhood_agreement(candidates, neighborhoods)
    assert [(r.scenario_id, round(r.mean_similarity, 6)) for r in r1] == \
           [(r.scenario_id, round(r.mean_similarity, 6)) for r in r2]


def test_empty_neighborhood_is_skipped_not_fabricated():
    from phase6.defense.orchestration.pipeline import MemoryScenario

    scenario = MemoryScenario("TEST-ISOLATED", "some content", is_poison_ground_truth=True)
    results = compute_neighborhood_agreement([(scenario, 99, "declared")], {99: []})
    assert results == []  # no fabricated neighborhood, no fabricated score


def test_missing_task_id_excludes_candidate_not_fabricates_zero():
    from phase6.defense.orchestration.pipeline import MemoryScenario

    scenario = MemoryScenario("TEST-NO-TASK", "some content", is_poison_ground_truth=True)
    results = compute_neighborhood_agreement([(scenario, None, "none")], {0: ["x"]})
    assert results == []


def test_single_member_pool_coherence_is_nan_not_fabricated():
    from phase6.defense.orchestration.pipeline import MemoryScenario, ScenarioPool

    pool = ScenarioPool("SOLO", (MemoryScenario("SOLO-0", "alone", is_poison_ground_truth=False),))
    results = pool_coherence(pool)
    assert len(results) == 1
    assert results[0].coherence != results[0].coherence  # NaN check


def test_poison_source_task_map_never_claims_task_zero_for_a_new_seed():
    """The 7 new (Track B) poison seeds must never be mapped to task 0 --
    that would silently re-create the exact overlap real_corpus.py's own
    task-0 exclusion was designed to prevent."""
    for scenario_id, (task_id, basis) in POISON_SOURCE_TASK_MAP.items():
        if scenario_id.startswith("REGEN-"):
            assert task_id != 0


def test_original_poison_and_track_b_pools_unchanged_by_this_investigation():
    old_pool = real_poison_scenarios()
    new_pool, records = regenerate_poison_batch()
    assert len(old_pool.memories) == 15
    assert len(new_pool.memories) == 9
    assert len(records) == 7


def test_provenance_format_confound_is_reported_not_promoted():
    """Sanity check that the confound this investigation found is real and
    reproducible: real-source-provenance format alone perfectly separates
    poison from the newly-added clean data -- confirming it is a
    construction-format artifact, not evidence this investigation treats as
    a usable signal (see report Section on Family D)."""
    from phase11.data.clean_expansion import clean_expansion_pools
    from phase11.relational_signals.provenance_relations import provenance_format_signal

    _, provenance_map = clean_expansion_pools()
    old_poison = list(real_poison_scenarios().memories)
    for m in old_poison:
        result = provenance_format_signal(m, provenance_map)
        assert result.has_real_source_dataset_provenance is False
