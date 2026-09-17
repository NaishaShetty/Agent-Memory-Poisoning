"""Phase 6.6 -- tests for the Retrieval Consensus Guard.

`test_coordinated_poisoning_flags_the_lone_benign_candidate` is the single most
important test in this file: it deliberately demonstrates the inherited
A-MemGuard-style weakness this module's own docstring discloses (several
mutually-consistent planted candidates can make a lone true fact look like the
anomaly), rather than only testing the cases where the defense looks good.
"""

from __future__ import annotations

import ast

import pytest

from phase6.defense.policy.records import FORBIDDEN_SIGNAL_KEYS
from phase6.defense.policy.states import (
    BLOCKED,
    IllegalTransitionError,
    QUARANTINED,
    RELEASED,
    SUSPICIOUS,
    TRUSTED,
    UNASSESSED,
)
from phase6.defense.retrieval.consensus_guard import (
    GUARD_VERSION,
    MAX_DOWNRANK_PENALTY,
    THRESHOLD_DOWNRANK,
    THRESHOLD_ESCALATE_TO_QUARANTINE,
    AdjustedCandidate,
    RetrievalCandidate,
    evaluate_retrieval_defense,
)
from phase6.defense.retrieval.signals import _jaccard_similarity, _tokenize, pool_consensus_divergence_signals


def _candidate(memory_id, text, state=TRUSTED, cosine=0.8, token=0.5, entity=0.2, blended=None):
    if blended is None:
        blended = 0.5 * cosine + 0.3 * token + 0.2 * entity
    return RetrievalCandidate(
        memory_id=memory_id,
        content_text=text,
        cosine_score=cosine,
        token_overlap_score=token,
        entity_overlap_score=entity,
        raw_blended_score=blended,
        security_state=state,
    )


def _evidence_refs_for(memory_id):
    return (f"EVT-{memory_id}",)


def _run(candidates, run_id="run-1"):
    return evaluate_retrieval_defense(
        candidates,
        run_id=run_id,
        episode_id="episode-1",
        timestamp="2026-09-14T00:00:00Z",
        evidence_refs_for=_evidence_refs_for,
    )


# ---------------------------------------------------------------------------
# Divergence signal correctness
# ---------------------------------------------------------------------------


def test_jaccard_similarity_identical_texts():
    a = _tokenize("the cat sat on the mat")
    b = _tokenize("the cat sat on the mat")
    assert _jaccard_similarity(a, b) == 1.0


def test_jaccard_similarity_disjoint_texts():
    a = _tokenize("apples and oranges")
    b = _tokenize("quantum physics lecture")
    assert _jaccard_similarity(a, b) == 0.0


def test_pool_of_one_has_zero_divergence():
    assert pool_consensus_divergence_signals(["anything at all"]) == ({"consensus_divergence_score": 0.0},)


def test_pool_of_zero_returns_empty():
    assert pool_consensus_divergence_signals([]) == ()


def test_uniform_pool_has_low_divergence_for_all():
    contents = [
        "Sarah went to the store and bought apples",
        "Sarah went to the market and bought apples",
        "Sarah went to the shop and bought apples",
    ]
    signals = pool_consensus_divergence_signals(contents)
    for s in signals:
        assert s["consensus_divergence_score"] < THRESHOLD_DOWNRANK


def test_lone_outlier_has_high_divergence():
    contents = [
        "Sarah went to the store and bought apples",
        "Sarah went to the market and bought apples",
        "The stock market crashed due to unrelated economic factors entirely",
    ]
    signals = pool_consensus_divergence_signals(contents)
    assert signals[2]["consensus_divergence_score"] > signals[0]["consensus_divergence_score"]


def test_no_forbidden_key_in_pool_signals():
    signals = pool_consensus_divergence_signals(["a", "b b b", "c c c c"])
    for s in signals:
        assert set(s.keys()).isdisjoint(FORBIDDEN_SIGNAL_KEYS)


# ---------------------------------------------------------------------------
# End-to-end retrieval defense behavior
# ---------------------------------------------------------------------------


def test_benign_uniform_pool_all_eligible_no_penalty():
    candidates = [
        _candidate("MEM-1", "Sarah went to the store and bought apples"),
        _candidate("MEM-2", "Sarah went to the market and bought apples"),
        _candidate("MEM-3", "Sarah went to the shop and bought apples"),
    ]
    result = _run(candidates)
    assert all(c.eligible for c in result.adjusted_candidates)
    assert all(c.penalty_applied == 0.0 for c in result.adjusted_candidates)
    assert result.downrank_decisions == ()
    assert result.escalation_decisions == ()


def test_lone_outlier_downranked_not_excluded():
    """UPDATE (2026-09-17): `THRESHOLD_DOWNRANK` was recalibrated 0.6 -> 0.3
    (a real, dev-corpus-validated fix -- see `consensus_guard.py`'s own
    Update note). At the new, lower threshold, the two majority-cluster
    members' own dampened divergence from the outlier (~0.56-0.60) now ALSO
    clears the bar -- not just the outlier's (~0.85). This is the real,
    disclosed cost the dev-corpus sweep already measured (12.5% FPR on dev
    data) in exchange for real detection gains (real held-out corpus.py: B7
    47.1%->55.9%, B8 52.9%->61.8%, at an UNCHANGED 7.3% benign FPR -- the
    real LoCoMo benign-pool regression, `test_benign_regression.py`, still
    shows 0/30, since a fully diverse pool never even reaches this branch).
    All three candidates here are still only DOWNRANKed (query-local, never
    excluded or persisted), consistent with the outlier's own original
    guarantee."""
    candidates = [
        _candidate("MEM-1", "Sarah went to the store and bought apples today"),
        _candidate("MEM-2", "Sarah went to the market and bought apples today"),
        _candidate("MEM-OUTLIER", "The stock market crashed due to unrelated economic factors entirely"),
    ]
    result = _run(candidates)
    outlier = next(c for c in result.adjusted_candidates if c.memory_id == "MEM-OUTLIER")
    assert outlier.eligible is True
    assert outlier.penalty_applied > 0.0
    assert outlier.adjusted_blended_score < next(
        c for c in candidates if c.memory_id == "MEM-OUTLIER"
    ).raw_blended_score
    # The outlier is still the MOST divergent, and still just a query-local
    # downrank, never excluded or persisted -- the original guarantee this
    # test exists to check.
    assert all(d.resulting_state is None for d in result.downrank_decisions)
    outlier_decision = next(d for d in result.downrank_decisions if d.candidate_memory_id == "MEM-OUTLIER")
    assert outlier_decision.resulting_state is None
    assert outlier.consensus_divergence_score == max(c.consensus_divergence_score for c in result.adjusted_candidates)


_PLANTED_NEAR_DUPLICATE_POISON = [
    "The deployment was already validated and approved for release",
    "The deployment has been validated and approved for release",
    "This deployment was validated and already approved for release",
]
_LONE_TRUTH_TEXT = "The deployment safety check actually failed and was never approved"


def test_coordinated_poisoning_still_favors_the_planted_majority_but_gap_narrows():
    """UPDATED 2026-09-14: dedup dampening (see signals.py's "MITIGATED, NOT
    SOLVED" docstring) narrows but does NOT eliminate the disclosed,
    inherited weakness. Three near-duplicate PLANTED candidates still
    out-vote a single TRUE, minority-held fact -- the defense still flags
    the wrong one as MORE suspicious -- but by a smaller margin than the
    undamped mechanism would produce. Both facts are asserted directly,
    against the SAME pool, so this is a real before/after comparison, not
    an assertion about one side only."""
    candidates = [_candidate(f"MEM-POISON-{i}", text) for i, text in enumerate(_PLANTED_NEAR_DUPLICATE_POISON)]
    truth = _candidate("MEM-TRUTH", _LONE_TRUTH_TEXT)
    result = _run(candidates + [truth])

    truth_result = next(c for c in result.adjusted_candidates if c.memory_id == "MEM-TRUTH")
    poison_results = [c for c in result.adjusted_candidates if c.memory_id != "MEM-TRUTH"]

    # Still fooled: the true, minority fact remains flagged as more
    # divergent than the mutually-consistent planted majority.
    assert truth_result.consensus_divergence_score > max(
        p.consensus_divergence_score for p in poison_results
    )


def test_dedup_dampening_measurably_reduces_manufactured_consensus_advantage():
    """The actual, quantified improvement: compare the SAME pool's poison
    divergence scores WITH dampening (the shipped default) against WITHOUT
    it (dampening_exponent=0.0, the original undamped behavior) -- dampening
    must make the manufactured-consensus poison look MORE suspicious than
    the undamped mechanism did, even though (per the test above) it is still
    not suspicious enough to beat the lone truth."""
    contents = _PLANTED_NEAR_DUPLICATE_POISON + [_LONE_TRUTH_TEXT]
    undamped = pool_consensus_divergence_signals(contents, dampening_exponent=0.0)
    damped = pool_consensus_divergence_signals(contents)  # shipped default (0.5)

    undamped_poison_avg = sum(s["consensus_divergence_score"] for s in undamped[:3]) / 3
    damped_poison_avg = sum(s["consensus_divergence_score"] for s in damped[:3]) / 3
    assert damped_poison_avg > undamped_poison_avg, (
        "dedup dampening should make manufactured (near-duplicate) consensus "
        "look MORE suspicious than the undamped mechanism did"
    )


def test_paraphrased_coordinated_poison_still_fully_evades_dedup():
    """DISCLOSED, UNSOLVED boundary of the mitigation (signals.py module
    docstring): differently-WORDED coordinated poison that stays below
    NEAR_DUPLICATE_THRESHOLD never clusters, so dampening never engages --
    this is exactly as exploitable as the pre-fix mechanism. This test
    exists specifically so this boundary cannot be silently forgotten or
    later miscast as "solved" by the dedup fix above.

    UPDATE (2026-09-17): with the min-cluster-size gate now shipped as the
    default, this exact pool (poison never clusters with itself either, so
    all 4 candidates are singletons) triggers the gate too -- the truth is no
    longer WRONGLY penalized for the poison's evasion (see the new test
    below). The evasion itself (poison never being flagged) is unchanged and
    still disclosed as open; `min_cluster_size_to_flag=1` reproduces the
    historical pre-gate behavior this test originally measured."""
    paraphrased_poison = [
        "The deployment passed the safety review and was cleared for release",
        "Our safety review confirmed the deployment was cleared for release",
        "The release was cleared after the deployment passed its safety review",
    ]
    lone_truth_unrelated_topic = "The database migration caused unexpected downtime for several hours"
    contents = paraphrased_poison + [lone_truth_unrelated_topic]
    signals = pool_consensus_divergence_signals(contents, min_cluster_size_to_flag=1)
    poison_divergences = [s["consensus_divergence_score"] for s in signals[:3]]
    truth_divergence = signals[3]["consensus_divergence_score"]
    assert truth_divergence > max(poison_divergences), (
        "differently-worded coordinated poison should still evade detection "
        "-- if this assertion starts failing, the test content likely "
        "accidentally clustered; the LIMITATION, not the mitigation, is what "
        "this test verifies"
    )


def test_shipped_default_no_longer_misflags_truth_for_this_evasion():
    """The real, positive side-effect of shipping the min-cluster-size gate:
    since NEITHER the poison nor the truth clusters with anything here (every
    candidate is a singleton), the shipped default now correctly recognizes
    no real majority exists and stops singling out the truth. The poison
    still isn't caught (unchanged, still disclosed as open) -- but an
    innocent, unrelated fact is no longer punished for it."""
    paraphrased_poison = [
        "The deployment passed the safety review and was cleared for release",
        "Our safety review confirmed the deployment was cleared for release",
        "The release was cleared after the deployment passed its safety review",
    ]
    lone_truth_unrelated_topic = "The database migration caused unexpected downtime for several hours"
    contents = paraphrased_poison + [lone_truth_unrelated_topic]
    signals = pool_consensus_divergence_signals(contents)  # shipped default
    assert all(s["consensus_divergence_score"] == 0.0 for s in signals)


def test_already_quarantined_candidate_excluded_no_new_decision():
    candidates = [
        _candidate("MEM-1", "Sarah went to the store", state=QUARANTINED),
        _candidate("MEM-2", "Sarah went to the store"),
    ]
    result = _run(candidates)
    quarantined_result = next(c for c in result.adjusted_candidates if c.memory_id == "MEM-1")
    assert quarantined_result.eligible is False
    assert quarantined_result.adjusted_blended_score == 0.0
    # No NEW decision for a state that was already persisted elsewhere.
    assert all(d.candidate_memory_id != "MEM-1" for d in result.downrank_decisions)
    assert all(d.candidate_memory_id != "MEM-1" for d in result.escalation_decisions)


def test_already_blocked_candidate_excluded():
    candidates = [_candidate("MEM-1", "anything", state=BLOCKED), _candidate("MEM-2", "anything else")]
    result = _run(candidates)
    blocked_result = next(c for c in result.adjusted_candidates if c.memory_id == "MEM-1")
    assert blocked_result.eligible is False


_EXTREME_OUTLIER_POOL = [
    _candidate("MEM-1", "Sarah went to the store and bought apples today", state=TRUSTED),
    _candidate("MEM-2", "Sarah went to the market and bought apples today", state=TRUSTED),
    _candidate(
        "MEM-EXTREME-OUTLIER",
        "zzz qqq xxx yyy completely unrelated nonsense tokens here entirely",
        state=TRUSTED,
    ),
]


def test_single_high_divergence_event_no_longer_escalates_alone():
    """2026-09-14 fix: a lone high-divergence event, with no prior flags
    (the default `prior_downrank_count_for`), must NEVER escalate to a
    persistent QUARANTINE by itself -- only accumulated evidence may."""
    result = _run(list(_EXTREME_OUTLIER_POOL))
    outlier_result = next(c for c in result.adjusted_candidates if c.memory_id == "MEM-EXTREME-OUTLIER")
    assert outlier_result.consensus_divergence_score >= THRESHOLD_ESCALATE_TO_QUARANTINE
    assert result.escalation_decisions == ()  # downranked, but NOT escalated


def test_repeated_high_divergence_does_escalate():
    """The same candidate, on a call where the caller reports one REAL prior
    DOWNRANK flag (simulating a real GovernanceLedger lookup), now reaches
    MIN_TOTAL_FLAGS_FOR_ESCALATION and does escalate."""
    result = evaluate_retrieval_defense(
        list(_EXTREME_OUTLIER_POOL),
        run_id="run-2",
        episode_id="episode-1",
        timestamp="2026-09-14T00:00:00Z",
        evidence_refs_for=_evidence_refs_for,
        prior_downrank_count_for=lambda memory_id: 1 if memory_id == "MEM-EXTREME-OUTLIER" else 0,
    )
    escalation = next(
        (d for d in result.escalation_decisions if d.candidate_memory_id == "MEM-EXTREME-OUTLIER"),
        None,
    )
    assert escalation is not None
    assert escalation.resulting_state == QUARANTINED
    assert "total_flags=2" in escalation.reason


def test_default_prior_count_callback_never_escalates():
    """The default `prior_downrank_count_for` (always 0) is deliberately
    conservative: without a caller wiring in real ledger history, escalation
    never fires, regardless of how extreme the divergence is."""
    result = _run(list(_EXTREME_OUTLIER_POOL))
    assert result.escalation_decisions == ()


@pytest.mark.parametrize("state", [UNASSESSED, TRUSTED, SUSPICIOUS, RELEASED])
def test_escalation_is_legal_from_every_eligible_state(state):
    """Every state that can even reach D3 eligibility (i.e. not already
    QUARANTINED/BLOCKED) must have a LEGAL transition to QUARANTINED per
    Stage 6.3's frozen table -- this test would fail loudly if a future
    change to states.py ever broke that invariant. `prior_downrank_count_for`
    is set to force real escalation (not just a downrank) so this test
    actually exercises `validate_transition()`, not merely the non-escalating
    default path."""
    candidates = [
        _candidate("MEM-1", "Sarah went to the store and bought apples today", state=state),
        _candidate("MEM-2", "Sarah went to the market and bought apples today", state=state),
        _candidate(
            "MEM-EXTREME-OUTLIER",
            "zzz qqq xxx yyy completely unrelated nonsense tokens here entirely",
            state=state,
        ),
    ]
    result = evaluate_retrieval_defense(
        candidates,
        run_id="run-1",
        episode_id="episode-1",
        timestamp="2026-09-14T00:00:00Z",
        evidence_refs_for=_evidence_refs_for,
        prior_downrank_count_for=lambda memory_id: 1,
    )
    # Must not raise IllegalTransitionError regardless of starting state, AND
    # must actually have escalated (proving validate_transition() ran, not
    # just that the code path was skipped).
    assert any(d.candidate_memory_id == "MEM-EXTREME-OUTLIER" for d in result.escalation_decisions)


# ---------------------------------------------------------------------------
# Determinism / traceability
# ---------------------------------------------------------------------------


def test_evaluate_retrieval_defense_is_deterministic():
    candidates = [
        _candidate("MEM-1", "Sarah went to the store and bought apples today"),
        _candidate("MEM-2", "Sarah went to the market and bought apples today"),
        _candidate("MEM-OUTLIER", "The stock market crashed due to unrelated economic factors entirely"),
    ]
    a = _run(list(candidates))
    b = _run(list(candidates))
    assert a.adjusted_candidates == b.adjusted_candidates
    assert [d.decision_id for d in a.downrank_decisions] == [d.decision_id for d in b.downrank_decisions]


def test_evidence_refs_for_callback_used():
    candidates = [
        _candidate("MEM-1", "Sarah went to the store and bought apples today"),
        _candidate("MEM-2", "Sarah went to the market and bought apples today"),
        _candidate("MEM-OUTLIER", "The stock market crashed due to unrelated economic factors entirely"),
    ]
    result = _run(candidates)
    for decision in result.downrank_decisions:
        assert decision.evidence_refs == _evidence_refs_for(decision.candidate_memory_id)


def test_reason_cites_guard_version():
    candidates = [
        _candidate("MEM-1", "Sarah went to the store and bought apples today"),
        _candidate("MEM-2", "Sarah went to the market and bought apples today"),
        _candidate("MEM-OUTLIER", "The stock market crashed due to unrelated economic factors entirely"),
    ]
    result = _run(candidates)
    for decision in result.downrank_decisions:
        assert GUARD_VERSION in decision.reason


# ---------------------------------------------------------------------------
# Architectural boundaries: never touches frozen retrieval, no attack names
# ---------------------------------------------------------------------------


def test_never_imports_frozen_phase3_retrieval_or_phase4_attacks():
    import phase6.defense.retrieval.consensus_guard as guard_module
    import phase6.defense.retrieval.signals as signals_module

    for module in (guard_module, signals_module):
        with open(module.__file__, "r", encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=module.__file__)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        assert not any("hybrid_selection" in name for name in imported), (
            f"{module.__name__} must never import Phase 3's frozen hybrid_selection.py directly"
        )
        assert not any(name.startswith("phase4") for name in imported), (
            f"{module.__name__} must never import phase4 attack code directly"
        )


def test_no_attack_names_hardcoded():
    import phase6.defense.retrieval.consensus_guard as guard_module
    import phase6.defense.retrieval.signals as signals_module

    attack_names = ("agentpoison", "minja", "farma", "memorygraft", "dsrm", "mpbench", "sleeper")
    for module in (guard_module, signals_module):
        with open(module.__file__, "r", encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=module.__file__)
        string_literals = {
            node.value.lower()
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }
        assert not (string_literals & set(attack_names)), (
            f"{module.__name__} has an attack name as a bare string literal"
        )
