"""Phase 6.6 (2026-09-14 semantic-escalation follow-up) -- decision-layer
(DOWNRANK/QUARANTINE outcome) comparison between D1 (lexical) and D2
(semantic) divergence metrics, using the real embedding model.

HONEST FINDING, CORRECTED FROM AN EARLIER DRAFT OF THIS FILE: for the
constructed coordinated-poisoning-vs-unrelated-topic-truth scenario, swapping
the divergence metric from lexical to semantic does NOT change the
decision-layer outcome under the CURRENT shared thresholds
(THRESHOLD_DOWNRANK=0.6, DEDUP_DAMPENING_EXPONENT=0.5) -- both metrics still
downrank the true, off-topic fact rather than the manufactured-consensus
poison. An earlier draft of this test asserted the opposite outcome and
happened to pass for the wrong reason (see
`test_semantic_vs_lexical_consensus.py`'s
`test_dedup_dampening_narrows_but_does_not_flip_the_unrelated_topic_case` for
the full mathematical explanation: dampening cannot reduce a singleton's own
divergence score in a two-cluster pool, no matter the exponent, short of an
extreme value that would break genuine-majority detection elsewhere).

This file exists to keep that corrected finding permanently checked at the
DECISION layer (not just the raw-signal layer), and to make explicit what it
implies: realizing a decision-layer benefit from the semantic metric would
require METRIC-SPECIFIC threshold calibration (the same fixed 0.6 threshold
was chosen without reference to the semantic metric's own score distribution)
-- an open item for Stage 6.9, not silently resolved here.

UPDATE (2026-09-17): Stage 6.9's own item was adopted -- `THRESHOLD_DOWNRANK`
is now `0.3` (see `consensus_guard.py`'s own Update note), calibrated against
the disjoint dev corpus, never this file's own fixture. The tests below were
updated accordingly: the raw-signal-level finding (semantic correctly
recognizes the real majority cluster, still scoring the truth highest) is
timeless and unchanged; the decision-layer tests now reflect the real,
lower-threshold behavior directly rather than the historical 0.6 case, which
is why `THRESHOLD_DOWNRANK` is no longer imported here as a bare comparison
value.
"""

from __future__ import annotations

from phase6.defense.policy.states import TRUSTED
from phase6.defense.retrieval.consensus_guard import (
    RetrievalCandidate,
    evaluate_retrieval_defense,
    semantic_divergence_fn,
)
from phase6.defense.retrieval.signals import pool_consensus_divergence_signals

_PARAPHRASED_POISON_TEXTS = [
    "The deployment passed the safety review and was cleared for release",
    "Our safety review confirmed the deployment was cleared for release",
    "The release was cleared after the deployment passed its safety review",
]
_LONE_TRUTH_TEXT = "The database migration caused unexpected downtime for several hours"


def _pool():
    candidates = [
        RetrievalCandidate(
            memory_id=f"MEM-POISON-{i}",
            content_text=text,
            cosine_score=0.7,
            token_overlap_score=0.5,
            entity_overlap_score=0.2,
            raw_blended_score=0.5 * 0.7 + 0.3 * 0.5 + 0.2 * 0.2,
            security_state=TRUSTED,
        )
        for i, text in enumerate(_PARAPHRASED_POISON_TEXTS)
    ]
    truth = RetrievalCandidate(
        memory_id="MEM-TRUTH",
        content_text=_LONE_TRUTH_TEXT,
        cosine_score=0.7,
        token_overlap_score=0.5,
        entity_overlap_score=0.2,
        raw_blended_score=0.5 * 0.7 + 0.3 * 0.5 + 0.2 * 0.2,
        security_state=TRUSTED,
    )
    return candidates + [truth]


def _evidence_refs_for(memory_id):
    return (f"EVT-{memory_id}",)


def test_lexical_pre_fix_ungated_downranked_the_truth_not_the_poison():
    """Historical finding (pre-2026-09-17), checked at the RAW SIGNAL level
    (not the decision layer, since `THRESHOLD_DOWNRANK` was separately
    recalibrated 0.6 -> 0.3 the same day -- see `consensus_guard.py`'s Update
    note -- and conflating the two changes in one decision-layer assertion
    would no longer isolate what this test is actually about): under the
    lexical metric, this pool's 3 poison paraphrases never cluster with each
    other (below the 0.7 Jaccard threshold), so the pre-fix ungated mechanism
    computed meaningless nonzero divergence for everyone -- and the raw score
    ranked the truth ABOVE the poison. `min_cluster_size_to_flag=1` reproduces
    that exact historical signal-level behavior; see the test below for what
    the SHIPPED default (gate + recalibrated threshold together) now does at
    the decision layer."""
    signals = pool_consensus_divergence_signals(
        [c.content_text for c in _pool()], min_cluster_size_to_flag=1
    )
    truth_score = signals[-1]["consensus_divergence_score"]
    poison_scores = [s["consensus_divergence_score"] for s in signals[:-1]]
    assert truth_score > max(poison_scores)


def test_lexical_shipped_default_no_longer_downranks_the_truth():
    """The real, measured effect of shipping the min-cluster-size gate on
    THIS exact pool: since the 3 poison paraphrases never lexically cluster
    (same reason as above), the shipped default recognizes no real majority
    exists anywhere and applies no penalty to anyone -- the truth is no
    longer wrongly downranked. (This does not newly catch the poison; see
    `test_semantic_metric_alone_does_not_flip_this_decision_at_the_shared_
    threshold` below for the separate, disclosed finding that a REAL semantic
    majority cluster among the poison still results in the poison, not the
    truth, being the low-divergence one -- an unrelated, structural weakness
    this gate does not touch.)"""
    result = evaluate_retrieval_defense(
        _pool(),
        run_id="run-1",
        episode_id="episode-1",
        timestamp="2026-09-14T00:00:00Z",
        evidence_refs_for=_evidence_refs_for,
    )
    assert all(c.penalty_applied == 0.0 for c in result.adjusted_candidates)


def test_semantic_metric_still_ranks_the_truth_above_the_poison_at_the_signal_level():
    """The structural finding this test exists to check (independent of
    whatever `THRESHOLD_DOWNRANK` happens to be calibrated to): under the
    semantic metric, the 3 poison paraphrases DO form a real cluster (unlike
    lexical), so they get dampened, low, mutually-agreeing divergence scores
    -- while the truth, correctly recognized as the real outlier, scores
    highest. This is the disclosed, structural "majority manipulation"
    weakness (FC-01): a real coordinated majority always outscores a lone
    truth on this signal, regardless of threshold calibration."""
    result = evaluate_retrieval_defense(
        _pool(),
        run_id="run-1",
        episode_id="episode-1",
        timestamp="2026-09-14T00:00:00Z",
        evidence_refs_for=_evidence_refs_for,
        divergence_fn=semantic_divergence_fn,
    )
    truth_adjusted = next(c for c in result.adjusted_candidates if c.memory_id == "MEM-TRUTH")
    poison_adjusted = [c for c in result.adjusted_candidates if c.memory_id != "MEM-TRUTH"]
    assert truth_adjusted.consensus_divergence_score > max(p.consensus_divergence_score for p in poison_adjusted)


def test_semantic_metric_at_recalibrated_threshold_now_also_downranks_the_poison():
    """UPDATE (2026-09-17): with `THRESHOLD_DOWNRANK` recalibrated 0.6 -> 0.3
    (a real, dev-corpus-validated fix, see `consensus_guard.py`'s Update
    note), the poison's own real semantic divergence (~0.43, dampened but
    still nonzero -- a cluster's members are never IDENTICAL) now ALSO clears
    the lower bar, in addition to the truth's (~0.86). This is a real,
    additional detection gain from the recalibration -- previously the poison
    was never penalized at all under this pool; now it is too, just less
    severely than the truth. Both remain query-local DOWNRANKs, never
    excluded or persisted."""
    result = evaluate_retrieval_defense(
        _pool(),
        run_id="run-1",
        episode_id="episode-1",
        timestamp="2026-09-14T00:00:00Z",
        evidence_refs_for=_evidence_refs_for,
        divergence_fn=semantic_divergence_fn,
    )
    truth_adjusted = next(c for c in result.adjusted_candidates if c.memory_id == "MEM-TRUTH")
    poison_adjusted = [c for c in result.adjusted_candidates if c.memory_id != "MEM-TRUTH"]
    assert truth_adjusted.penalty_applied > 0.0
    assert all(p.penalty_applied > 0.0 for p in poison_adjusted)
    # The truth is still penalized more severely than any individual poison member.
    assert truth_adjusted.penalty_applied > max(p.penalty_applied for p in poison_adjusted)
