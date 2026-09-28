"""Tests for Phase 17 round-3 fix modules (structural checks; no live LLM calls)."""
from pathlib import Path

import pytest

from phase17.evasion_real_context import _SOURCE_SAMPLE
from phase17.gold_registry import gold_memories
from phase17.sanity_baselines import always_allow

# CORRECTION (external review round 3, follow-up, 2026-09-28): these four tests all
# transitively load data/raw/locomo/locomo10.json, real licensed dataset content that is
# deliberately excluded from git (see .gitignore) -- they failed in CI (not caught locally,
# where every dev environment already has this file) once the earlier pandas/jsonschema gap
# was fixed and let them actually run. Skipped, not removed, matching the existing pattern
# for LLM-dependent tests in this same file.
_needs_locomo_raw = pytest.mark.skipif(
    not Path("data/raw/locomo/locomo10.json").exists(),
    reason="data/raw/locomo/locomo10.json is real, licensed raw dataset content, deliberately "
           "excluded from git -- not present in a fresh checkout such as CI.",
)


@_needs_locomo_raw
def test_evasion_real_context_source_samples_cover_all_gold_parents():
    gold = gold_memories()
    assert set(_SOURCE_SAMPLE) == set(gold)
    assert all(isinstance(v, int) and v >= 0 for v in _SOURCE_SAMPLE.values())


@_needs_locomo_raw
def test_real_conversation_turns_are_nonempty_and_real():
    from phase17.evasion_real_context import _real_conversation_turns

    turns = _real_conversation_turns(0)
    assert len(turns) > 100  # LoCoMo sample 0 has hundreds of real turns
    assert all(isinstance(t, tuple) and len(t) == 2 for t in turns[:5])


@_needs_locomo_raw
def test_query_trigger_reference_queries_are_diverse():
    from phase17.query_trigger_signal import _reference_queries

    qs = _reference_queries()
    assert len(qs) > 500  # real cross-conversation LoCoMo QA questions
    assert len(set(qs)) > 400  # genuinely diverse, not one question repeated


@_needs_locomo_raw
def test_preference_corroboration_v2_conversation_loads():
    from phase17.preference_corroboration_v2 import _real_conversation_turns

    turns = _real_conversation_turns(0)
    assert len(turns) > 100
    assert any("like" in t.lower() or "enjoy" in t.lower() for t in turns)


def test_chinese_ensemble_modules_importable():
    import phase17.chinese_ensemble  # noqa: F401
    import phase17.multilingual_stacked  # noqa: F401


def test_llm_proxy_human_eval_categories_are_closed_vocabulary():
    from phase17.llm_proxy_human_eval import CATEGORIES

    assert set(CATEGORIES) == {"correct", "incorrect", "paraphrase", "partial", "abstains", "ambiguous"}


def test_agentpoison_reconstruction_retrieval_rate_lower_than_other_families():
    """Structural regression guard for the round-5 finding: recomputing (cheaply, with a
    small query sample) should keep showing AgentPoison as no more broadly retrievable
    than other families under the real target embedding model -- if a future change to
    the AgentPoison reconstruction makes this fail, that is itself worth knowing."""
    from sentence_transformers import SentenceTransformer

    from phase17.poison_sets import original_records

    m = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    orig = original_records()
    by_family = {}
    for r in orig:
        by_family.setdefault(r.family, r.text)
    assert "agentpoison" in by_family
    ap = by_family.pop("agentpoison")
    texts = [ap] + list(by_family.values())
    vecs = m.encode(texts, normalize_embeddings=True)
    queries = ["What did the user do last weekend?", "Where does the user work?", "What is the user's favorite food?",
              "Who is the user's best friend?", "What hobby does the user have?"]
    qv = m.encode(queries, normalize_embeddings=True)
    sims = vecs @ qv.T
    ap_mean = sims[0].mean()
    other_means = sims[1:].mean(axis=1)
    assert ap_mean <= other_means.max() + 0.2  # AgentPoison is not a dramatic outlier on the high side
