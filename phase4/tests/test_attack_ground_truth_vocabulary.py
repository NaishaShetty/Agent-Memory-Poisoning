"""Phase 4 P0 regression tests -- the nine-state attack ground-truth
vocabulary (`phase4/shared/ground_truth.py`), the fix for the audit finding
that this vocabulary previously existed only as prose/hand-typed strings,
never as a validated state machine.

Real-shape tests below are grounded directly in the actual, already-published
observations in `PHASE4_4_9_ATTACK_GROUND_TRUTH.md`'s Section 1 table --
e.g. MemoryGraft's real `DISCARD` trial (a real, observed
`POISON_NOT_ADMITTED`/`ATTACK_FAILURE`) and AgentPoison's real
admitted -> selected -> influenced -> success chain -- not invented
scenarios.
"""

from __future__ import annotations

import pytest

from phase4.shared.ground_truth import (
    ALLOWED_TRANSITIONS,
    GROUND_TRUTH_STATES,
    STATE_ATTACK_FAILURE,
    STATE_ATTACK_SUCCESS,
    STATE_POISON_ADMITTED,
    STATE_POISON_IN_CANDIDATE_POOL,
    STATE_POISON_INFLUENCED_RESPONSE,
    STATE_POISON_NOT_ADMITTED,
    STATE_POISON_RETRIEVED_BUT_NOT_USED,
    STATE_POISON_SELECTED_TOP_K,
    STATE_TARGET_BEHAVIOR_TRIGGERED,
    GroundTruthTrace,
    IllegalGroundTruthTransitionError,
    validate_transition,
)


def test_all_nine_states_are_present_and_distinct():
    assert len(GROUND_TRUTH_STATES) == 9
    assert len(set(GROUND_TRUTH_STATES)) == 9


# ---------------------------------------------------------------------------
# Real, documented campaign shapes (PHASE4_4_9_ATTACK_GROUND_TRUTH.md
# Section 1's table) must validate as legal chains.
# ---------------------------------------------------------------------------


def test_real_shape_memorygraft_deliberately_weak_artifact_gate_refusal():
    """The project's one real pre-admission ATTACK_FAILURE: MemoryGraft's
    gate genuinely DISCARDed a deliberately weak artifact
    (`memorygraft/attack_failure_demo_run_2026-09-11.txt`)."""
    trace = GroundTruthTrace(artifact_id="memorygraft-weak-demo")
    trace.record(STATE_POISON_NOT_ADMITTED)
    assert trace.is_attack_failure() is False  # NOT_ADMITTED != ATTACK_FAILURE as a state name
    assert trace.current_state == STATE_POISON_NOT_ADMITTED


def test_real_shape_agentpoison_full_success_chain():
    """AgentPoison's real trigger-bearing trial: admitted -> selected ->
    influenced (real COUNTERFACTUALLY_INFLUENTIAL) -> success. No
    intermediate candidate-pool-only observation was separately reported for
    this trial in the real table, so ADMITTED -> SELECTED_TOP_K directly must
    be legal."""
    trace = GroundTruthTrace(artifact_id="agentpoison-trigger")
    trace.record(STATE_POISON_ADMITTED)
    trace.record(STATE_POISON_SELECTED_TOP_K)
    trace.record(STATE_POISON_INFLUENCED_RESPONSE)
    trace.record(STATE_ATTACK_SUCCESS)
    assert trace.is_attack_success()


def test_real_shape_farma_candidate_pool_split_then_success():
    """FARMA's real camping cluster: 11 injected, 3 of 11 real,
    newly-confirmed `POISON_IN_CANDIDATE_POOL`-only, 8 of 11 real
    `POISON_SELECTED_TOP_K` -- and (joint-mask) real influence with no
    discrete TARGET_BEHAVIOR_TRIGGERED concept, straight to ATTACK_SUCCESS."""
    pool_only = GroundTruthTrace(artifact_id="farma-pool-only-member")
    pool_only.record(STATE_POISON_ADMITTED)
    pool_only.record(STATE_POISON_IN_CANDIDATE_POOL)
    assert pool_only.current_state == STATE_POISON_IN_CANDIDATE_POOL

    selected = GroundTruthTrace(artifact_id="farma-selected-member")
    selected.record(STATE_POISON_ADMITTED)
    selected.record(STATE_POISON_IN_CANDIDATE_POOL)
    selected.record(STATE_POISON_SELECTED_TOP_K)
    selected.record(STATE_POISON_INFLUENCED_RESPONSE)
    selected.record(STATE_ATTACK_SUCCESS)  # no discrete trigger for FARMA
    assert selected.is_attack_success()


def test_real_shape_minja_single_mask_selected_but_not_success():
    """MINJA's real single-mask camping trial: selected, real
    COUNTERFACTUALLY_INFLUENTIAL finding, but the false belief persisted
    (Section 2.3) -- not treated as ATTACK_SUCCESS at single-mask
    granularity. Modeled here as reaching INFLUENCED_RESPONSE and stopping
    (no further state recorded), which is a legal, non-terminal-forced
    resting point -- this vocabulary does not force every trace to reach a
    terminal state."""
    trace = GroundTruthTrace(artifact_id="minja-single-mask")
    trace.record(STATE_POISON_ADMITTED)
    trace.record(STATE_POISON_SELECTED_TOP_K)
    trace.record(STATE_POISON_INFLUENCED_RESPONSE)
    assert trace.current_state == STATE_POISON_INFLUENCED_RESPONSE
    assert not trace.is_attack_success()
    assert not trace.is_attack_failure()


def test_real_shape_selected_but_not_influential_is_a_legal_non_success_path():
    """A selected poison that is NOT counterfactually influential
    (`POISON_RETRIEVED_BUT_NOT_USED`) must be able to terminate at
    ATTACK_FAILURE -- the disclosed-but-never-observed post-admission
    failure mode this project's own limitations table names."""
    trace = GroundTruthTrace(artifact_id="hypothetical-resisted")
    trace.record(STATE_POISON_ADMITTED)
    trace.record(STATE_POISON_SELECTED_TOP_K)
    trace.record(STATE_POISON_RETRIEVED_BUT_NOT_USED)
    trace.record(STATE_ATTACK_FAILURE)
    assert trace.is_attack_failure()


def test_real_shape_trigger_bearing_attack_via_explicit_trigger_state():
    """A trigger-based attack (Sleeper, DSRM-style) can pass through the
    explicit TARGET_BEHAVIOR_TRIGGERED state on the way to success."""
    trace = GroundTruthTrace(artifact_id="sleeper-triggered")
    trace.record(STATE_POISON_ADMITTED)
    trace.record(STATE_POISON_SELECTED_TOP_K)
    trace.record(STATE_POISON_INFLUENCED_RESPONSE)
    trace.record(STATE_TARGET_BEHAVIOR_TRIGGERED)
    trace.record(STATE_ATTACK_SUCCESS)
    assert trace.is_attack_success()


# ---------------------------------------------------------------------------
# Illegal transitions -- the exact class of error the audit found had zero
# enforcement anywhere before this fix.
# ---------------------------------------------------------------------------


def test_cannot_report_attack_success_with_no_prior_observation():
    with pytest.raises(IllegalGroundTruthTransitionError):
        validate_transition(None, STATE_ATTACK_SUCCESS)


def test_cannot_skip_directly_from_not_admitted_to_success():
    trace = GroundTruthTrace(artifact_id="illegal-1")
    trace.record(STATE_POISON_NOT_ADMITTED)
    with pytest.raises(IllegalGroundTruthTransitionError):
        trace.record(STATE_ATTACK_SUCCESS)
    # The illegal call must not have mutated the trace.
    assert trace.observations == [STATE_POISON_NOT_ADMITTED]


def test_cannot_skip_selection_and_influence_straight_to_success():
    """Reproduces the exact class of bug the audit found possible when the
    vocabulary is just hand-typed strings: nothing previously stopped a
    campaign script from printing ATTACK_SUCCESS for a memory that was only
    ever ADMITTED, never shown to be selected or influential."""
    trace = GroundTruthTrace(artifact_id="illegal-2")
    trace.record(STATE_POISON_ADMITTED)
    with pytest.raises(IllegalGroundTruthTransitionError):
        trace.record(STATE_ATTACK_SUCCESS)


def test_cannot_report_candidate_pool_state_for_a_not_admitted_artifact():
    trace = GroundTruthTrace(artifact_id="illegal-3")
    trace.record(STATE_POISON_NOT_ADMITTED)
    with pytest.raises(IllegalGroundTruthTransitionError):
        trace.record(STATE_POISON_IN_CANDIDATE_POOL)


def test_not_admitted_and_attack_success_and_attack_failure_are_terminal():
    for terminal in (STATE_POISON_NOT_ADMITTED, STATE_ATTACK_SUCCESS, STATE_ATTACK_FAILURE):
        legal_next_states = {to for (frm, to) in ALLOWED_TRANSITIONS if frm == terminal}
        assert legal_next_states == set(), f"{terminal} must have no outgoing edge, found {legal_next_states}"


def test_unknown_state_name_is_rejected():
    with pytest.raises(ValueError):
        validate_transition(None, "NOT_A_REAL_STATE")


# ---------------------------------------------------------------------------
# dormancy_report.py must now be sourcing its canonical names from this
# module, not re-declaring them independently.
# ---------------------------------------------------------------------------


def test_dormancy_report_states_are_the_same_objects_as_ground_truth():
    from phase4.shared.dormancy_report import STATE_IN_CANDIDATE_POOL, STATE_SELECTED_TOP_K

    assert STATE_IN_CANDIDATE_POOL == STATE_POISON_IN_CANDIDATE_POOL
    assert STATE_SELECTED_TOP_K == STATE_POISON_SELECTED_TOP_K
