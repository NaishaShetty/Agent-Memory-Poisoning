"""Structural tests for SA-9 (owner-disjointness, job shape, prior-text pool), mirroring
test_sa8_corpus.py. Scoring tests are skipped until the corpus exists."""
from __future__ import annotations

import json

import pytest

from phase17.defence_v7 import sa7_corpus as S7
from phase17.defence_v8 import longmemeval_owners as L
from phase17.defence_v8 import sa8_corpus as S8
from phase17.defence_v8 import sa9_corpus as S9


def test_longmemeval_owner_selection_is_reproducible():
    assert L.select_owner_episodes() == list(L.OWNER_EPISODE.values())


def test_sa9_owners_disjoint_from_every_prior_sa_owner():
    locomo_owners = set(range(10))
    cc_owners = set(range(100, 110))
    sa9_owners = set(S9.DEV_OWNERS) | set(S9.EVAL_OWNERS)
    assert sa9_owners.isdisjoint(locomo_owners)
    assert sa9_owners.isdisjoint(cc_owners)
    assert sa9_owners == set(L.OWNER_EPISODE.keys())


def test_sa9_dev_eval_owners_disjoint():
    assert set(S9.DEV_OWNERS).isdisjoint(S9.EVAL_OWNERS)
    assert len(S9.DEV_OWNERS) == 4
    assert len(S9.EVAL_OWNERS) == 6


def test_sa9_kinds_match_sa7_frozen_kinds():
    assert S9.KINDS == S7.KINDS


def test_sa9_jobs_cover_every_owner_kind_batch_once():
    jobs = S9._jobs()
    assert len(jobs) == len(S9.DEV_OWNERS + S9.EVAL_OWNERS) * len(S9.KINDS) * S9.BATCHES
    seen = {(o, k, b) for o, k, b, _ in jobs}
    assert len(seen) == len(jobs)
    seeds = [seed for *_, seed in jobs]
    assert len(set(seeds)) == len(seeds)


def test_sa9_seed_base_disjoint_from_sa8():
    assert S9.SEED_BASE != S8.SEED_BASE


def test_sa9_prior_texts_include_sa8():
    prior = S9._prior_texts()
    sa8_items = json.loads(S8.CACHE.read_text(encoding="utf-8"))["items"]
    assert len(prior) >= len(sa8_items)
    assert sa8_items[0]["note"] in prior


def test_sa9_corpus_not_yet_scored_is_skipped_cleanly():
    if not S9.CACHE.exists():
        pytest.skip("SA-9 not generated yet")
    data = json.loads(S9.CACHE.read_text(encoding="utf-8"))
    assert data["items"]
