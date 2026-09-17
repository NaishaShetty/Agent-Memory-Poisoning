"""Phase 6.6 -- Retrieval-Time Defense: pool-level consensus/divergence signal.

WHAT THIS IS, AND WHAT IT IS HONESTLY NOT
--------------------------------------------------------------------------------
`DEFENSE_LITERATURE_AUDIT.md` (Track A.5) found A-MemGuard the strongest external
D3 candidate: for a retrieved candidate set, convert each candidate into a
structured entity-relation path, then use an LLM-as-judge to find cross-candidate
consensus and flag divergent paths as anomalous.

This module adapts the CONCEPT (cross-candidate agreement as a trust signal) using
an interpretable, deterministic, no-LLM-call proxy: lexical (token-set) overlap
between a candidate and the rest of its pool. This is NOT a reproduction of
A-MemGuard's actual mechanism (no entity-relation extraction, no LLM judge) --
it is a much cruder approximation, chosen deliberately to keep this stage's
baseline interpretable and cheap (per the project's "establish interpretable
baselines before a black-box detector" instruction), at the cost of almost
certainly being both less accurate AND less semantically aware than the real
A-MemGuard mechanism. Whether it captures enough of the real signal to be useful
is an open empirical question for Stage 6.9, not assumed.

THE INHERITED, DISCLOSED WEAKNESS -- MITIGATED, NOT SOLVED (2026-09-14 follow-up)
--------------------------------------------------------------------------------
`DEFENSE_LITERATURE_AUDIT.md` A.5 already disclosed A-MemGuard's real structural
weakness: because the mechanism rewards cross-candidate AGREEMENT, a coordinated
attacker who plants several mutually-consistent poisoned memories can make the
POISON look like the consensus and a lone true, minority-held fact look like the
anomaly. The original version of this module inherited that weakness undamped.

A genuine, partial mitigation is implemented below: NEAR-DUPLICATE DEDUPLICATION
WITH DAMPENED CLUSTER WEIGHTING. Candidates are first greedily clustered by
pairwise similarity (`NEAR_DUPLICATE_THRESHOLD`); when computing candidate i's
divergence, each OTHER candidate j's vote is weighted by
`1 / cluster_size(j) ** DEDUP_DAMPENING_EXPONENT` (0.5 by default -- a square-root
dampening, not full 1/k deduplication). This directly targets FARMA's and
MemoryGraft's own real mechanism, which the Methodology Draft describes as raising
"retrieval probability through volume... rather than through semantic centrality" --
i.e. an attack that wins by REPEATING near-identical content, which is exactly what
this dampening discounts.

WHY SQUARE-ROOT DAMPENING, NOT FULL DEDUPLICATION (1/k, collapsing every cluster to
one effective vote): a stronger experiment (not shipped) confirmed that full
deduplication REMOVES the genuine-majority signal entirely -- a real 2-witness
majority against a true 1-witness minority becomes indistinguishable from 1-vs-1,
destroying the mechanism's ability to do the ordinary, correct thing (trust
corroborated content more than an uncorroborated outlier) for entirely benign
cases. Square-root dampening keeps some majority-trust signal (tripling honest
corroborating copies still counts for more than one) while sub-linearly discounting
manufactured volume. This is a disclosed, versioned, uncalibrated compromise
(`DEDUP_DAMPENING_EXPONENT`), not a claim of an optimal setting.

WHAT THIS MITIGATION DOES NOT SOLVE (verified by
`test_paraphrased_coordinated_poison_still_evades_dedup` in
`test_retrieval_defense.py`, not merely asserted): clustering only catches
NEAR-LITERAL repetition. An attacker who paraphrases each planted record
differently enough to fall below `NEAR_DUPLICATE_THRESHOLD` produces separate,
un-clustered singleton "votes" -- exactly as exploitable as before dampening was
added. No purely content-based, no-external-verification mechanism can fully
solve this: distinguishing "three independent witnesses genuinely agree" from
"one attacker wrote three different lies that happen to agree with each other"
requires information this signal, by the Signal Contract's own design (Stage
6.4), does not have access to (attacker identity, corroboration from a source
outside the candidate pool itself). This remains an open, structural limitation,
carried forward rather than claimed solved.

UPDATE (2026-09-17) -- THE MIN-CLUSTER-SIZE GATE IS NOW THE SHIPPED DEFAULT
--------------------------------------------------------------------------------
Stage 6.9 discovered a second, independent, real bug: a fully topically-diverse
benign retrieval pool (every candidate its own singleton, no near-duplicate
cluster anywhere) produced a **100% false-positive rate**, because "divergence
from the rest of the pool" was computed even when there was no real majority to
diverge FROM (`DEFENSE_COMPOSITION_AND_ABLATION.md`'s "Major Finding"). A fix
(`pool_consensus_divergence_signals_with_min_cluster_gate()` in
`phase6/evaluation/ablations/calibration.py`) was built and validated at the
time, but was deliberately NOT adopted as the Stage 6.6 default then, pending
explicit authorization. That authorization was given (2026-09-17); the gate is
now merged directly into this function as `MIN_CLUSTER_SIZE_TO_FLAG` (default
2), replacing the old, buggy always-flag behavior. Verified before shipping:
the gate only changes output when NO cluster reaches the minimum size -- every
case where a real majority exists (the ordinary case this signal is designed
to catch) is computed identically to before.
"""

from __future__ import annotations

import re
from typing import Dict, Sequence, Tuple

from phase6.defense.policy.records import FORBIDDEN_SIGNAL_KEYS, EvaluatorOnlyLeakageError
from phase6.defense.retrieval.dedup_consensus import cluster_by_similarity_matrix, dampened_divergence, has_real_majority_cluster

_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9']+")

# Uncalibrated v1 defaults (module docstring above) -- versioned via
# SIGNALS_VERSION so a future recalibration (Stage 6.9) is traceable.
# 1.2.0 (2026-09-17): adopts the min-cluster-size gate as the shipped default
# (see MIN_CLUSTER_SIZE_TO_FLAG below and the module docstring's "Update").
SIGNALS_VERSION = "retrieval-signals-1.2.0"
NEAR_DUPLICATE_THRESHOLD = 0.7
DEDUP_DAMPENING_EXPONENT = 0.5  # 0.0 = no dampening (original behavior); 1.0 = full dedup

# Stage 6.9's real, measured finding (docstring "Update" below): the ungated
# mechanism produces a 100% false-positive rate on a fully topically-diverse
# benign pool (every candidate its own singleton cluster -- no real majority
# exists at all). Gating on "does a real majority cluster exist" closes this
# without weakening genuine majority-vs-minority detection (verified: this
# gate only changes behavior when NO cluster reaches this size; the divergence
# computation itself, whenever a real majority DOES exist, is unchanged).
MIN_CLUSTER_SIZE_TO_FLAG = 2


def _tokenize(text: str) -> frozenset:
    return frozenset(match.group(0).lower() for match in _TOKEN_PATTERN.finditer(text))


def _jaccard_similarity(a: frozenset, b: frozenset) -> float:
    if not a and not b:
        return 1.0  # two empty texts are trivially "identical" -- avoids 0/0
    union = a | b
    if not union:
        return 1.0
    return len(a & b) / len(union)


def pool_consensus_divergence_signals(
    contents: Sequence[str],
    *,
    near_duplicate_threshold: float = NEAR_DUPLICATE_THRESHOLD,
    dampening_exponent: float = DEDUP_DAMPENING_EXPONENT,
    min_cluster_size_to_flag: int = MIN_CLUSTER_SIZE_TO_FLAG,
) -> Tuple[Dict[str, float], ...]:
    """For each candidate in `contents`, compute its dedup-weighted LEXICAL
    (Jaccard token-set) divergence against every OTHER candidate in the same
    pool. Returns one `{"consensus_divergence_score": v}` dict per input
    candidate, in the same order.

    Clustering and dampening are delegated to `dedup_consensus.py`'s
    similarity-metric-agnostic core -- this function's own job is only to
    build the Jaccard similarity matrix. See `embedding_signals.py` for the
    semantic (cosine-similarity) counterpart built on the SAME core, which is
    what makes the two directly, fairly comparable (Stage 6.6's D1-vs-D2
    experiment).

    A pool of size 0 or 1 has no "rest of pool" to compare against -- every
    candidate gets a divergence score of 0.0 (no signal, not a maximal-anomaly
    default; an isolated candidate is not evidence of anything on its own).

    MIN-CLUSTER-SIZE GATE (shipped default as of 2026-09-17, see module
    docstring's "Update"): if no cluster in the pool reaches
    `min_cluster_size_to_flag` (default 2 -- i.e. every candidate is its own
    singleton, no real majority exists anywhere in the pool), every
    candidate's score is forced to 0.0 rather than the ungated mechanism's
    meaningless-but-nonzero values in that regime. Pass `min_cluster_size_to_
    flag=1` to recover the original, pre-2026-09-17 ungated behavior exactly
    (kept only for `test_ablation_framework.py`'s own B0-B7 historical
    reproduction, not recommended for new use).
    """
    tokenized = [_tokenize(text) for text in contents]
    n = len(tokenized)
    similarity_matrix = [[_jaccard_similarity(tokenized[i], tokenized[j]) for j in range(n)] for i in range(n)]
    cluster_of = cluster_by_similarity_matrix(similarity_matrix, near_duplicate_threshold)

    if not has_real_majority_cluster(cluster_of, min_cluster_size_to_flag):
        return tuple({"consensus_divergence_score": 0.0} for _ in range(n))

    divergences = dampened_divergence(similarity_matrix, cluster_of, dampening_exponent)

    results = []
    for divergence in divergences:
        signal = {"consensus_divergence_score": divergence}
        offending = set(signal.keys()) & FORBIDDEN_SIGNAL_KEYS
        if offending:  # unreachable given the fixed key name, kept for parity/defense-in-depth
            raise EvaluatorOnlyLeakageError(f"pool_consensus_divergence_signals leaked {offending!r}")
        results.append(signal)
    return tuple(results)
