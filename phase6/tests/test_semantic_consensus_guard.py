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
"""

from __future__ import annotations

from phase6.defense.policy.states import TRUSTED
from phase6.defense.retrieval.consensus_guard import (
    RetrievalCandidate,
    THRESHOLD_DOWNRANK,
    evaluate_retrieval_defense,
    semantic_divergence_fn,
)

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


def test_lexical_default_downranks_the_truth_not_the_poison():
    result = evaluate_retrieval_defense(
        _pool(),
        run_id="run-1",
        episode_id="episode-1",
        timestamp="2026-09-14T00:00:00Z",
        evidence_refs_for=_evidence_refs_for,
    )
    truth_adjusted = next(c for c in result.adjusted_candidates if c.memory_id == "MEM-TRUTH")
    poison_adjusted = [c for c in result.adjusted_candidates if c.memory_id != "MEM-TRUTH"]
    assert truth_adjusted.penalty_applied > 0.0
    assert all(p.penalty_applied == 0.0 for p in poison_adjusted)


def test_semantic_metric_alone_does_not_flip_this_decision_at_the_shared_threshold():
    """The corrected, honest finding: swapping divergence_fn to semantic,
    with every other guard setting unchanged, produces the SAME qualitative
    outcome as lexical for this content -- truth is still the only candidate
    downranked. This is not a defect in the semantic mechanism itself (its
    underlying clustering is independently verified correct in
    test_semantic_vs_lexical_consensus.py); it is evidence that
    THRESHOLD_DOWNRANK, calibrated with no reference to the semantic metric's
    own score distribution, does not automatically transfer between metrics."""
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

    assert truth_adjusted.consensus_divergence_score > THRESHOLD_DOWNRANK
    assert all(p.consensus_divergence_score < THRESHOLD_DOWNRANK for p in poison_adjusted)
    # Same qualitative outcome as lexical -- the metric swap alone did not
    # change WHO gets flagged for this content.
    assert truth_adjusted.penalty_applied > 0.0
    assert all(p.penalty_applied == 0.0 for p in poison_adjusted)
