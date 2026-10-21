"""Structural tests for SA-8 (owner-disjointness, job shape, prior-text pool) that do not
require the corpus to have been generated yet. Scoring/gate tests live elsewhere and are
skipped until phase17/data/defence_v8/sa8_corpus.json exists.
"""
from __future__ import annotations

import json

import pytest

from phase17.defence_v7 import sa7_corpus as S7
from phase17.defence_v8 import cc_owners, sa8_corpus as S8


def test_cc_owner_selection_is_reproducible():
    assert cc_owners.select_owner_episodes() == list(cc_owners.OWNER_EPISODE.values())


def test_sa8_owners_disjoint_from_every_prior_sa_owner():
    # SA-1..SA-7 all drew owners from LoCoMo sample indices 0-9.
    locomo_owners = set(range(10))
    sa8_owners = set(S8.DEV_OWNERS) | set(S8.EVAL_OWNERS)
    assert sa8_owners.isdisjoint(locomo_owners)
    assert sa8_owners == set(cc_owners.OWNER_EPISODE.keys())


def test_sa8_dev_eval_owners_disjoint():
    assert set(S8.DEV_OWNERS).isdisjoint(S8.EVAL_OWNERS)
    assert len(S8.DEV_OWNERS) == 4
    assert len(S8.EVAL_OWNERS) == 6


def test_sa8_kinds_match_sa7_frozen_kinds():
    assert S8.KINDS == S7.KINDS


def test_sa8_jobs_cover_every_owner_kind_batch_once():
    jobs = S8._jobs()
    assert len(jobs) == len(S8.DEV_OWNERS + S8.EVAL_OWNERS) * len(S8.KINDS) * S8.BATCHES
    seen = {(o, k, b) for o, k, b, _ in jobs}
    assert len(seen) == len(jobs), "duplicate (owner, kind, batch) job"
    seeds = [seed for *_, seed in jobs]
    assert len(set(seeds)) == len(seeds), "seed collision across jobs"


def test_sa8_prior_texts_include_sa7():
    prior = S8._prior_texts()
    sa7_items = json.loads(S7.CACHE.read_text(encoding="utf-8"))["items"]
    assert len(prior) >= len(sa7_items)
    # spot-check: SA-7's own notes must be present for the near-dup "seen" index to catch them
    sample = sa7_items[0]["note"]
    assert sample in prior


def test_sa8_corpus_not_yet_scored_is_skipped_cleanly():
    if not S8.CACHE.exists():
        pytest.skip("SA-8 not generated yet")
    data = json.loads(S8.CACHE.read_text(encoding="utf-8"))
    assert data["items"], "SA-8 cache exists but has zero items"
