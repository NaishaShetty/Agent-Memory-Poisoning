"""Phase 11.x Track B -- regression tests for `phase11/data/poison_regeneration.py`."""

from __future__ import annotations

import inspect
import re

from phase11.data import split
from phase11.data.poison_regeneration import (
    ATTACK_PIPELINE_DOCUMENTATION,
    regenerate_poison_batch,
)
from phase11.data.real_corpus import real_benign_scenarios, real_poison_scenarios


def _references_held_out_pools_in_code(module) -> bool:
    for _, obj in inspect.getmembers(module, inspect.isfunction):
        if obj.__module__ != module.__name__:
            continue
        if "held_out_pools" in obj.__code__.co_names:
            return True
    return False


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def test_no_held_out_access():
    import phase11.data.poison_regeneration as mod

    assert not _references_held_out_pools_in_code(mod)


def test_all_seven_attack_families_documented_before_generation():
    expected = {"dsrm", "farma", "mpbench", "minja", "agentpoison", "memorygraft", "sleeper_memory_poisoning"}
    assert set(ATTACK_PIPELINE_DOCUMENTATION) == expected
    required_fields = {
        "required_seed_fields", "supported_source_format", "attack_configuration", "randomness",
        "success_criteria", "validation_criteria", "expected_output",
        "can_operate_on_new_seed_without_modification",
    }
    for family, doc in ATTACK_PIPELINE_DOCUMENTATION.items():
        assert required_fields.issubset(doc), f"{family} missing required documentation"


def test_regeneration_batch_runs_and_all_seven_families_succeed():
    pool, records = regenerate_poison_batch()
    assert len(records) == 7  # one generation attempt per attack family
    families = {r.attack_family for r in records}
    assert families == set(ATTACK_PIPELINE_DOCUMENTATION)
    for r in records:
        assert r.success, f"{r.attack_family} generation failed: {r.validation_result}"
    assert len(pool.memories) == 9  # 6 single-memory attacks + MINJA's 3-step sequence


def test_new_seeds_never_target_task_id_zero():
    _, records = regenerate_poison_batch()
    for r in records:
        assert r.source_task_id != 0, f"{r.attack_family} must not reuse the already-used task_id=0"


def test_new_seeds_target_distinct_real_tasks():
    """Genuine subject-matter diversity: 7 new seeds must span 7 distinct
    real LoCoMo tasks, not silently reuse the same one."""
    _, records = regenerate_poison_batch()
    tasks = {r.source_task_id for r in records}
    assert len(tasks) == 7


def test_new_poison_shares_no_content_with_existing_poison_or_benign_or_dev_or_held_out():
    pool, _ = regenerate_poison_batch()
    new_texts = {m.content_text for m in pool.memories}
    new_norm = {_norm(t) for t in new_texts}

    old_poison_texts = {m.content_text for m in real_poison_scenarios().memories}
    benign_texts = {m.content_text for p in real_benign_scenarios() for m in p.memories}
    dev_texts = {m.content_text for p in split.dev_pools() for m in p.memories}
    held_out_texts = {m.content_text for p in split.held_out_pools() for m in p.memories}

    for other_name, other in [
        ("existing real poison", old_poison_texts), ("real benign LoCoMo", benign_texts),
        ("dev_pools", dev_texts), ("held_out_pools", held_out_texts),
    ]:
        assert new_texts.isdisjoint(other), f"exact content overlap with {other_name}"
        other_norm = {_norm(t) for t in other}
        assert new_norm.isdisjoint(other_norm), f"normalized content overlap with {other_name}"


def test_new_poison_scenario_ids_are_unique_and_do_not_collide():
    pool, _ = regenerate_poison_batch()
    old_pool = real_poison_scenarios()
    new_ids = {m.scenario_id for m in pool.memories}
    old_ids = {m.scenario_id for m in old_pool.memories}
    assert new_ids.isdisjoint(old_ids)


def test_new_poison_carries_real_labels_and_no_fabricated_lineage():
    pool, _ = regenerate_poison_batch()
    for m in pool.memories:
        assert m.is_poison_ground_truth is True
        assert m.attack_family_ground_truth is not None
        assert m.parent_ids == ()
        assert m.ancestors == ()


def test_original_fifteen_seed_poison_pool_is_unchanged():
    """The original real_corpus.py poison corpus must remain byte-identical
    after this Track B work -- additive only, never a silent replacement."""
    pool = real_poison_scenarios()
    assert len(pool.memories) == 15
    assert pool.pool_id == "POOL-REAL-POISON-ATTACKS"


def test_generation_records_report_every_required_audit_field():
    _, records = regenerate_poison_batch()
    for r in records:
        assert r.attack_family and r.source_dataset and r.new_seed_id and r.generation_run_id
        assert r.attack_configuration and r.validation_result and r.provenance
        assert r.genuinely_new is True
