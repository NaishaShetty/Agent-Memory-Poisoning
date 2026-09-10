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
    # NOTE: the entity regex is intentionally the exact, unmodified logic validated
    # across research Rounds 5-11 -- it treats any capitalized word as a candidate
    # "entity," including a sentence-initial word like "Where". This is a known,
    # already-accepted quirk of the VALIDATED mechanism, not something to tune here
    # (the task's own instruction: do not tune weights/thresholds/pool size).
    # q_entities={Where,Evan,2022} (3); c_entities={Evan,Paris,2022}; overlap=2 -> 2/3
    assert _entity_overlap_recall("Where did Evan go in 2022", "Evan went to Paris in 2022") == pytest.approx(2 / 3)
    # lowercase-only query has no capitalized/digit entities -> 0.0 by construction
    assert _entity_overlap_recall("no entities here", "still none") == 0.0


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
