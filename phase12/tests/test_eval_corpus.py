"""Phase 12 -- tests for the new, separate evaluation corpus."""

from __future__ import annotations

import pytest

from phase12.eval_corpus import (
    ALL_DATASETS,
    assert_disjoint_from_held_out_pools,
    combined_new_corpus_pools,
    per_dataset_eval_corpora,
)


@pytest.fixture(scope="module")
def corpora():
    return per_dataset_eval_corpora()


def test_all_four_datasets_present(corpora):
    assert set(corpora.keys()) == set(ALL_DATASETS)


def test_every_dataset_has_real_benign_content(corpora):
    for dataset_name, corpus in corpora.items():
        assert corpus.n_benign > 0, f"{dataset_name} has no real benign scenarios"


def test_every_dataset_shares_the_same_real_poison_pool(corpora):
    poison_ids = {corpus.poison_pool.pool_id for corpus in corpora.values()}
    assert len(poison_ids) == 1


def test_poison_pool_covers_all_seven_attack_families(corpora):
    families = {
        m.attack_family_ground_truth
        for corpus in corpora.values()
        for m in corpus.poison_pool.memories
        if m.is_poison_ground_truth
    }
    assert families == {"dsrm", "farma", "mpbench", "minja", "agentpoison", "memorygraft", "sleeper_memory_poisoning"}


def test_no_scenario_id_collisions_within_combined_corpus(corpora):
    pools = combined_new_corpus_pools(corpora)
    seen = set()
    for pool in pools:
        for m in pool.memories:
            assert m.scenario_id not in seen, f"duplicate scenario id {m.scenario_id}"
            seen.add(m.scenario_id)


def test_disjoint_from_held_out_pools(corpora):
    assert_disjoint_from_held_out_pools(corpora)  # raises AssertionError on any overlap
