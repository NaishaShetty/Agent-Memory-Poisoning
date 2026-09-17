"""Phase 6.16 -- benign utility & regression tests, run against a REAL
benign corpus extracted from the actual, licensed LoCoMo dataset (see
`benign_corpus.py`'s own docstring for provenance), not synthetic sentences.

`test_shipped_retrieval_consensus_has_100_percent_false_positive_rate_on_
real_data` is the single most important test in this file: it is a
DELIBERATE, PERMANENT regression test proving Stage 6.9's diverse-benign-pool
finding is not an artifact of a hand-constructed synthetic example -- it
reproduces at 100% on real, licensed conversational data. It is kept
failing-by-design (asserting the bug's presence) for the same reason Stage
6.6's own coordinated-poisoning demonstration test is kept failing-by-design:
a disclosed limitation must remain checked, not quietly fixed and forgotten.
"""

from __future__ import annotations

import time

import pytest

from phase6.defense.admission.reasoning_guard import evaluate_admission
from phase6.defense.policy.states import ALLOW
from phase6.defense.retrieval.consensus_guard import RetrievalCandidate, evaluate_retrieval_defense
from phase6.defense.signals.contract import build_signal_context
from phase6.defense.sleeper.sleeper_guard import evaluate_sleeper_admission
from phase6.evaluation.ablations.calibration import pool_consensus_divergence_signals_with_min_cluster_gate
from phase6.evaluation.regression.benign_corpus import REAL_BENIGN_POOLS, REAL_BENIGN_TURNS


def _context(i, text):
    return build_signal_context(
        memory_id=f"MEM-REAL-{i}", content_text=text, content_type="CONVERSATIONAL_FACT",
        memory_type="foundation", parent_ids=(), lifecycle_state="ACTIVE",
        creation_timestamp="2026-09-14T00:00:00Z",
    )


def _pool_candidates(pool_idx, pool):
    return [
        RetrievalCandidate(
            memory_id=f"P{pool_idx}-{j}", content_text=t, cosine_score=0.7, token_overlap_score=0.5,
            entity_overlap_score=0.2, raw_blended_score=0.5 * 0.7 + 0.3 * 0.5 + 0.2 * 0.2,
            security_state="TRUSTED",
        )
        for j, t in enumerate(pool)
    ]


# ---------------------------------------------------------------------------
# Corpus sanity
# ---------------------------------------------------------------------------


def test_corpus_has_real_diverse_content():
    assert len(REAL_BENIGN_TURNS) == 30
    assert len(set(REAL_BENIGN_TURNS)) == 30  # no accidental duplicates
    assert len(REAL_BENIGN_POOLS) == 6


# ---------------------------------------------------------------------------
# Admission layer -- REAL result: zero false positives
# ---------------------------------------------------------------------------


def test_admission_layer_zero_false_positives_on_real_benign_corpus():
    flags = []
    for i, text in enumerate(REAL_BENIGN_TURNS):
        decision = evaluate_admission(
            _context(i, text), run_id="reg", episode_id="e1",
            timestamp="2026-09-14T00:00:00Z", evidence_refs=("E1",),
        )
        if decision.action != ALLOW:
            flags.append((i, decision.action, text))
    assert flags == []


def test_admission_layer_real_measured_latency_is_sub_millisecond():
    """Upgrades Stage 6.12's disclosed-but-unmeasured 'expected sub-
    millisecond' cost estimate to a REAL measurement."""
    start = time.perf_counter()
    for i, text in enumerate(REAL_BENIGN_TURNS):
        evaluate_admission(
            _context(i, text), run_id="reg", episode_id="e1",
            timestamp="2026-09-14T00:00:00Z", evidence_refs=("E1",),
        )
    elapsed = time.perf_counter() - start
    per_item = elapsed / len(REAL_BENIGN_TURNS)
    assert per_item < 0.001  # real assertion: genuinely sub-millisecond


# ---------------------------------------------------------------------------
# Sleeper layer -- REAL result: zero false positives
# ---------------------------------------------------------------------------


def test_sleeper_layer_zero_false_positives_on_real_benign_corpus():
    flags = []
    for i, text in enumerate(REAL_BENIGN_TURNS):
        decision = evaluate_sleeper_admission(
            _context(i, text), run_id="reg", episode_id="e1",
            timestamp="2026-09-14T00:00:00Z", evidence_refs=("E1",),
        )
        if decision.action != ALLOW:
            flags.append((i, decision.action, text))
    assert flags == []


# ---------------------------------------------------------------------------
# Retrieval layer -- the major real finding
# ---------------------------------------------------------------------------


def test_pre_fix_ungated_retrieval_consensus_had_100_percent_false_positive_rate_on_real_data():
    """UPDATE (2026-09-17): the bug this test originally pinned down as the
    SHIPPED default's behavior was fixed and shipped (see `signals.py`'s
    2026-09-17 Update) -- the min-cluster-size gate is now the default.
    `min_cluster_size_to_flag=1` reproduces the historical, pre-fix ungated
    behavior explicitly, so this real, measured historical finding (100% FP
    on genuine LoCoMo content) remains on record and reproducible, without
    misrepresenting it as still being what ships today."""
    from functools import partial

    from phase6.defense.retrieval.signals import pool_consensus_divergence_signals

    pre_fix_ungated = partial(pool_consensus_divergence_signals, min_cluster_size_to_flag=1)

    total_flags = 0
    total_candidates = 0
    for pool_idx, pool in enumerate(REAL_BENIGN_POOLS):
        candidates = _pool_candidates(pool_idx, pool)
        total_candidates += len(candidates)
        result = evaluate_retrieval_defense(
            candidates, run_id="reg", episode_id="e1", timestamp="2026-09-14T00:00:00Z",
            evidence_refs_for=lambda mid: (f"E-{mid}",),
            divergence_fn=pre_fix_ungated,
        )
        total_flags += len(result.downrank_decisions) + len(result.escalation_decisions)
    assert total_candidates == 30
    assert total_flags == 30  # 100% false-positive rate, the historical bug, reproduced on demand


def test_shipped_default_now_has_zero_false_positives_on_the_same_real_data():
    """The real, measured, current state as of the 2026-09-17 fix: calling
    `evaluate_retrieval_defense()` with NO override (i.e. exactly what every
    real caller gets) now produces zero false positives on the same real
    LoCoMo pools that used to be 100% false-flagged."""
    total_flags = 0
    for pool_idx, pool in enumerate(REAL_BENIGN_POOLS):
        candidates = _pool_candidates(pool_idx, pool)
        result = evaluate_retrieval_defense(
            candidates, run_id="reg", episode_id="e1", timestamp="2026-09-14T00:00:00Z",
            evidence_refs_for=lambda mid: (f"E-{mid}",),
        )
        total_flags += len(result.downrank_decisions) + len(result.escalation_decisions)
    assert total_flags == 0


def test_gated_retrieval_consensus_resolves_it_on_the_same_real_data():
    """The Stage 6.9 experimental fix, now ALSO the shipped default (see test
    above) -- this test keeps exercising the explicit `divergence_fn=`
    override path directly, so a future change to the shipped default's
    signature doesn't silently stop covering the calibration.py helper
    itself."""
    total_flags = 0
    for pool_idx, pool in enumerate(REAL_BENIGN_POOLS):
        candidates = _pool_candidates(pool_idx, pool)
        result = evaluate_retrieval_defense(
            candidates, run_id="reg", episode_id="e1", timestamp="2026-09-14T00:00:00Z",
            evidence_refs_for=lambda mid: (f"E-{mid}",),
            divergence_fn=pool_consensus_divergence_signals_with_min_cluster_gate,
        )
        total_flags += len(result.downrank_decisions) + len(result.escalation_decisions)
    assert total_flags == 0
