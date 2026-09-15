"""Unit tests for `foundations/hybrid_selection.py` -- V2's Condition C selection
mechanism. Deterministic tests only (real embedding model, no LLM/foundation calls)."""

from __future__ import annotations

import pytest

from phase3.evaluation.foundations.hybrid_selection import (
    DEFAULT_TOP_K,
    HYBRID_WEIGHT_COSINE,
    HYBRID_WEIGHT_ENTITY_OVERLAP,
    HYBRID_WEIGHT_TOKEN_OVERLAP,
    _entity_overlap_recall,
    _token_overlap_recall,
    select_by_hybrid_score,
)


def test_weights_sum_to_one():
    assert abs((HYBRID_WEIGHT_COSINE + HYBRID_WEIGHT_TOKEN_OVERLAP + HYBRID_WEIGHT_ENTITY_OVERLAP) - 1.0) < 1e-9


def test_token_overlap_recall_basic():
    # query tokens {what,color,is,the,car}=5; content tokens {the,car,is,bright,red};
    # overlap {the,car,is}=3 -> 3/5
    assert _token_overlap_recall("What color is the car", "The car is bright red") == pytest.approx(3 / 5)
    assert _token_overlap_recall("", "anything") == 0.0
    assert _token_overlap_recall("hello world", "") == 0.0


def test_entity_overlap_recall_basic():
    # P2 CORRECTION (2026-09-14): this test used to lock in a real bug as
    # "intentional" -- the un-corrected regex treated ANY capitalized word as a
    # candidate "entity," including a sentence-initial word with no entity meaning
    # (e.g. "Where"), inflating the 0.2-weighted entity-overlap term on nearly every
    # query. The `HYBRID_WEIGHT_*` blend itself (0.5/0.3/0.2, validated across
    # Rounds 5-11, never tuned on results) is UNCHANGED by this fix -- only the
    # entity-overlap TERM's own tokenization was a correctness bug, not a validated
    # design choice; see `_proper_nouns()`'s docstring in hybrid_selection.py for the
    # full account and the disclosed false-negative tradeoff this fix accepts.
    #
    # Corrected values for this same example:
    # q_entities: "Where" (sentence-initial, now excluded) + {Evan, 2022} -> {Evan, 2022} (2)
    # c_entities: "Evan" (sentence-initial in content, now excluded, the disclosed
    #   tradeoff) + {Paris, 2022} -> {Paris, 2022}
    # overlap = {2022} -> 1/2
    assert _entity_overlap_recall("Where did Evan go in 2022", "Evan went to Paris in 2022") == pytest.approx(1 / 2)
    # lowercase-only query has no capitalized/digit entities -> 0.0 by construction
    assert _entity_overlap_recall("no entities here", "still none") == 0.0


def test_entity_overlap_recall_sentence_initial_word_is_not_treated_as_an_entity():
    """The exact audit scenario, reproduced directly and discriminating: query
    and content both happen to start with the SAME non-entity word ("Where").
    Before this fix, that shared sentence-initial capitalization spuriously
    counted as an entity match (score 0.5, via "Where"=="Where"); after the
    fix, with no real shared entity ("John" never appears in the content),
    the score correctly drops to 0.0."""
    assert _entity_overlap_recall("Where did John go?", "Where did he go, nobody knows.") == 0.0


def test_entity_overlap_recall_still_detects_a_genuine_non_initial_proper_noun():
    """The fix must not blunt real entity detection -- a proper noun that is
    NOT the string's first word (in EITHER the query or the content) is still
    correctly matched."""
    assert _entity_overlap_recall("Where did John go?", "I saw John at the market.") == pytest.approx(1.0)


def test_select_by_hybrid_score_empty_candidates():
    result = select_by_hybrid_score("a question", [])
    assert result.selected == ()
    assert result.rejected == ()


def test_select_by_hybrid_score_respects_top_k():
    candidates = [(f"m{i}", f"content number {i} about topic X") for i in range(15)]
    result = select_by_hybrid_score("topic X question", candidates, top_k=8)
    assert len(result.selected) == 8
    assert len(result.rejected) == 7
    assert result.top_k == 8


def test_select_by_hybrid_score_fewer_candidates_than_top_k():
    candidates = [("m1", "some content"), ("m2", "other content")]
    result = select_by_hybrid_score("a query", candidates, top_k=8)
    assert len(result.selected) == 2
    assert len(result.rejected) == 0


def test_select_by_hybrid_score_selected_and_rejected_partition_all_candidates():
    candidates = [(f"m{i}", f"content {i}") for i in range(20)]
    result = select_by_hybrid_score("query text", candidates, top_k=DEFAULT_TOP_K)
    all_ids = {c.memory_id for c in result.selected} | {c.memory_id for c in result.rejected}
    assert all_ids == {c[0] for c in candidates}
    assert set(c.memory_id for c in result.selected).isdisjoint(c.memory_id for c in result.rejected)


def test_select_by_hybrid_score_prefers_exact_entity_match():
    """A candidate containing the query's exact proper-noun/date entity should
    outrank a topically-similar but entity-mismatched candidate."""
    candidates = [
        ("m_match", "Sarah went to the market on 5 May 2023 to buy vegetables"),
        ("m_nomatch", "Someone went to a market on some day to buy vegetables"),
    ]
    result = select_by_hybrid_score("When did Sarah go to the market, 5 May 2023?", candidates, top_k=1)
    assert result.selected[0].memory_id == "m_match"


def test_select_by_hybrid_score_deterministic():
    candidates = [(f"m{i}", f"deterministic content {i}") for i in range(10)]
    r1 = select_by_hybrid_score("deterministic query", candidates, top_k=5)
    r2 = select_by_hybrid_score("deterministic query", candidates, top_k=5)
    assert [c.memory_id for c in r1.selected] == [c.memory_id for c in r2.selected]
    assert [c.blended_score for c in r1.selected] == [c.blended_score for c in r2.selected]
