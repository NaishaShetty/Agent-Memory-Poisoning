"""Phase 11.1 P0 standing regression test -- the train/dev/held-out split
(`phase11/data/split.py`) must never overlap, on either content or scenario
id, in any of its three pairwise combinations. Mirrors
`phase6/tests/test_calibration_corpus_disjoint.py`'s exact pattern, extended
to three-way disjointness (train vs dev vs held-out) rather than two-way.
"""

from __future__ import annotations

import itertools

from phase11.data import split


def _content_and_ids(pools):
    texts, ids = set(), set()
    for pool in pools:
        for m in pool.memories:
            texts.add(m.content_text)
            ids.add(m.scenario_id)
    return texts, ids


def test_train_dev_held_out_share_no_content():
    splits = split.all_splits()
    per_split = {name: _content_and_ids(pools)[0] for name, pools in splits.items()}
    for a, b in itertools.combinations(per_split, 2):
        overlap = per_split[a] & per_split[b]
        assert overlap == set(), (
            f"Phase 11 split {a!r} and {b!r} share content: {overlap!r}. "
            "Training/tuning on content that is later reported as a held-out "
            "number is circular -- see split.py's module docstring."
        )


def test_train_dev_held_out_share_no_scenario_ids():
    splits = split.all_splits()
    per_split = {name: _content_and_ids(pools)[1] for name, pools in splits.items()}
    for a, b in itertools.combinations(per_split, 2):
        overlap = per_split[a] & per_split[b]
        assert overlap == set()


def test_held_out_split_is_the_same_object_b0_b9_already_report_against():
    """Not just disjoint -- literally the same real corpus, so a Phase 11
    number sits next to B0-B9's own real numbers honestly (Plan Section 4.1)."""
    from phase6.evaluation.ablations import corpus as reported_corpus

    held_out = split.held_out_pools()
    reported = reported_corpus.all_pools()
    assert [p.pool_id for p in held_out] == [p.pool_id for p in reported]


def test_every_split_is_non_empty():
    for name, pools in split.all_splits().items():
        total = sum(len(p.memories) for p in pools)
        assert total > 0, f"Phase 11 split {name!r} has no scenarios"


def test_real_corpus_shares_no_content_with_held_out_or_dev():
    """2026-09-17 real-data-expansion follow-on -- `real_corpus.py`'s real
    LoCoMo/attack-injector content is a disjoint universe from `corpus.py`'s
    hand-authored synthetic text by construction (see its module docstring),
    verified directly rather than only assumed."""
    from phase11.data.real_corpus import real_corpus_pools

    real_texts, real_ids = _content_and_ids(real_corpus_pools())
    held_out_texts, held_out_ids = _content_and_ids(split.held_out_pools())
    dev_texts, dev_ids = _content_and_ids(split.all_dev_pools())

    assert real_texts & held_out_texts == set()
    assert real_ids & held_out_ids == set()
    assert real_texts & dev_texts == set()
    assert real_ids & dev_ids == set()


def test_real_corpus_is_non_empty():
    from phase11.data.real_corpus import real_corpus_pools

    total = sum(len(p.memories) for p in real_corpus_pools())
    assert total > 0
