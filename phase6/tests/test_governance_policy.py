"""Phase 6.3 -- tests for the Memory Governance Policy state machine, decision
record, and append-only ledger.

Covers the Phase 6 brief's testing requirements: normal behavior, malformed
inputs, deterministic behavior, edge cases, provenance correctness, evaluator
leakage, duplicate behavior, serialization, reproducibility, and failure
handling -- plus the state-machine-specific scenarios Section 2.2 of
`docs/phase6/MEMORY_GOVERNANCE_POLICY.md` commits to.
"""

from __future__ import annotations

import pytest

from phase6.defense.policy.ledger import (
    APPEND_CREATED,
    APPEND_IDEMPOTENT,
    GovernanceLedger,
    GovernanceLedgerCollisionError,
)
from phase6.defense.policy.records import (
    CURRENT_POLICY_VERSION,
    EvaluatorOnlyLeakageError,
    MGPDecisionRecord,
    build_decision,
    mint_decision_id,
)
from phase6.defense.policy.states import (
    ALLOW,
    ALLOW_WITH_RESTRICTION,
    BLOCK,
    BLOCKED,
    DOWNRANK,
    IllegalTransitionError,
    QUARANTINE,
    QUARANTINED,
    RELEASE,
    RELEASED,
    REQUIRE_VALIDATION,
    SUSPICIOUS,
    TRUSTED,
    UNASSESSED,
    resulting_state_for,
    validate_transition,
)


def _decision(memory_id="MEM-1", action=ALLOW, run_id="run-1", signals=None, **overrides):
    kwargs = dict(
        candidate_memory_id=memory_id,
        signals_used=signals or {"content_length": 42},
        action=action,
        reason="test-only synthetic reason grounded in the signals above",
        run_id=run_id,
        episode_id="episode-1",
        timestamp="2026-09-13T00:00:00Z",
        evidence_refs=["EVT-fake-0001"],
    )
    kwargs.update(overrides)
    return build_decision(**kwargs)


# ---------------------------------------------------------------------------
# States / transitions
# ---------------------------------------------------------------------------


def test_all_six_states_and_seven_actions_present():
    from phase6.defense.policy.states import ACTIONS, SECURITY_STATES

    assert set(SECURITY_STATES) == {
        "UNASSESSED",
        "TRUSTED",
        "SUSPICIOUS",
        "QUARANTINED",
        "BLOCKED",
        "RELEASED",
    }
    assert set(ACTIONS) == {
        "ALLOW",
        "ALLOW_WITH_RESTRICTION",
        "REQUIRE_VALIDATION",
        "QUARANTINE",
        "BLOCK",
        "RELEASE",
        "DOWNRANK",
    }


def test_legal_transition_from_unassessed():
    assert validate_transition(UNASSESSED, ALLOW) == TRUSTED
    assert validate_transition(UNASSESSED, ALLOW_WITH_RESTRICTION) == SUSPICIOUS
    assert validate_transition(UNASSESSED, QUARANTINE) == QUARANTINED
    assert validate_transition(UNASSESSED, BLOCK) == BLOCKED


def test_trusted_cannot_jump_directly_to_blocked():
    """Policy document Section 2.2's rationale: every BLOCK must have an
    intermediate SUSPICIOUS/QUARANTINED record in its history."""
    with pytest.raises(IllegalTransitionError):
        validate_transition(TRUSTED, BLOCK)


def test_released_cannot_jump_directly_to_blocked():
    with pytest.raises(IllegalTransitionError):
        validate_transition(RELEASED, BLOCK)


def test_quarantined_cannot_go_directly_to_trusted():
    """Must resolve via RELEASE, not a direct ALLOW."""
    with pytest.raises(IllegalTransitionError):
        validate_transition(QUARANTINED, ALLOW)


def test_quarantined_resolves_via_release_or_block():
    assert validate_transition(QUARANTINED, RELEASE) == RELEASED
    assert validate_transition(QUARANTINED, BLOCK) == BLOCKED


def test_blocked_is_terminal():
    for action in (ALLOW, ALLOW_WITH_RESTRICTION, REQUIRE_VALIDATION, QUARANTINE, RELEASE):
        with pytest.raises(IllegalTransitionError):
            validate_transition(BLOCKED, action)


def test_released_can_be_reflagged_in_either_direction():
    assert validate_transition(RELEASED, ALLOW_WITH_RESTRICTION) == SUSPICIOUS
    assert validate_transition(RELEASED, QUARANTINE) == QUARANTINED


def test_downrank_never_produces_a_persisted_state():
    assert resulting_state_for(DOWNRANK) is None
    assert validate_transition(TRUSTED, DOWNRANK) is None
    assert validate_transition(QUARANTINED, DOWNRANK) is None


def test_unknown_state_or_action_rejected():
    with pytest.raises(ValueError):
        validate_transition("NOT_A_STATE", ALLOW)
    with pytest.raises(ValueError):
        resulting_state_for("NOT_AN_ACTION")


# ---------------------------------------------------------------------------
# Decision record: normal behavior, malformed inputs, provenance correctness
# ---------------------------------------------------------------------------


def test_normal_decision_construction():
    record = _decision()
    assert record.resulting_state == TRUSTED
    assert record.policy_version == CURRENT_POLICY_VERSION
    assert record.decision_id.startswith("MGPDEC-")


def test_reason_required_non_empty():
    with pytest.raises(ValueError):
        _decision(reason="")
    with pytest.raises(ValueError):
        MGPDecisionRecord(
            decision_id="x",
            candidate_memory_id="MEM-1",
            policy_version=CURRENT_POLICY_VERSION,
            signals_used={},
            action=ALLOW,
            resulting_state=TRUSTED,
            reason="   ",
            run_id="run-1",
            episode_id=None,
            timestamp="2026-09-13T00:00:00Z",
            evidence_refs=("EVT-1",),
        )


def test_evidence_refs_required():
    """A decision with no evidence reference is a bare claim -- Policy document
    Section 4 forbids it."""
    with pytest.raises(ValueError):
        MGPDecisionRecord(
            decision_id="x",
            candidate_memory_id="MEM-1",
            policy_version=CURRENT_POLICY_VERSION,
            signals_used={},
            action=ALLOW,
            resulting_state=TRUSTED,
            reason="some reason",
            run_id="run-1",
            episode_id=None,
            timestamp="2026-09-13T00:00:00Z",
            evidence_refs=(),
        )


def test_resulting_state_must_match_action():
    """resulting_state can never be set independently of the action that
    produced it -- states.py is the single source of truth."""
    with pytest.raises(ValueError):
        MGPDecisionRecord(
            decision_id="x",
            candidate_memory_id="MEM-1",
            policy_version=CURRENT_POLICY_VERSION,
            signals_used={},
            action=ALLOW,  # produces TRUSTED
            resulting_state=BLOCKED,  # mismatched on purpose
            reason="some reason",
            run_id="run-1",
            episode_id=None,
            timestamp="2026-09-13T00:00:00Z",
            evidence_refs=("EVT-1",),
        )


def test_unknown_action_rejected_at_construction():
    with pytest.raises(ValueError):
        _decision(action="NOT_AN_ACTION")


# ---------------------------------------------------------------------------
# Evaluator-only leakage
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "forbidden_key",
    [
        "attack_id",
        "attacker_originated",
        "poison_admitted",
        "counterfactually_influential",
        "sleeper_trigger",
        "attribution_influence",
    ],
)
def test_evaluator_only_field_refused(forbidden_key):
    with pytest.raises(EvaluatorOnlyLeakageError):
        _decision(signals=dict({forbidden_key: True}, benign_signal=1))


def test_legitimate_signals_pass_through_unmodified():
    record = _decision(signals={"cosine_to_history": 0.83, "self_reference_count": 2})
    assert record.signals_used == {"cosine_to_history": 0.83, "self_reference_count": 2}


# ---------------------------------------------------------------------------
# Deterministic identity / reproducibility
# ---------------------------------------------------------------------------


def test_decision_id_is_deterministic():
    id_a = mint_decision_id("MEM-1", CURRENT_POLICY_VERSION, {"x": 1}, ALLOW, "run-1")
    id_b = mint_decision_id("MEM-1", CURRENT_POLICY_VERSION, {"x": 1}, ALLOW, "run-1")
    assert id_a == id_b


def test_decision_id_is_order_independent_over_signal_dict():
    """Signal dict key order must not affect identity -- signals_used is
    logically unordered."""
    id_a = mint_decision_id("MEM-1", CURRENT_POLICY_VERSION, {"a": 1, "b": 2}, ALLOW, "run-1")
    id_b = mint_decision_id("MEM-1", CURRENT_POLICY_VERSION, {"b": 2, "a": 1}, ALLOW, "run-1")
    assert id_a == id_b


def test_decision_id_changes_with_any_defining_field():
    base = mint_decision_id("MEM-1", CURRENT_POLICY_VERSION, {"x": 1}, ALLOW, "run-1")
    assert base != mint_decision_id("MEM-2", CURRENT_POLICY_VERSION, {"x": 1}, ALLOW, "run-1")
    assert base != mint_decision_id("MEM-1", "mgp-2.0.0", {"x": 1}, ALLOW, "run-1")
    assert base != mint_decision_id("MEM-1", CURRENT_POLICY_VERSION, {"x": 2}, ALLOW, "run-1")
    assert base != mint_decision_id("MEM-1", CURRENT_POLICY_VERSION, {"x": 1}, BLOCK, "run-1")
    assert base != mint_decision_id("MEM-1", CURRENT_POLICY_VERSION, {"x": 1}, ALLOW, "run-2")


def test_decision_id_never_uses_uuid4_or_timestamp():
    """Identity is independent of when the decision object is constructed --
    two decisions differing only in timestamp/reason share a decision_id."""
    a = _decision(timestamp="2026-01-01T00:00:00Z", reason="reason A")
    b = _decision(timestamp="2099-01-01T00:00:00Z", reason="reason B")
    assert a.decision_id == b.decision_id


# ---------------------------------------------------------------------------
# GovernanceLedger: append-only, serialization, duplicate handling, projection
# ---------------------------------------------------------------------------


def test_append_and_read_back(tmp_path):
    ledger = GovernanceLedger(tmp_path)
    record = _decision()
    result = ledger.append(record)
    assert result == APPEND_CREATED
    assert ledger.decisions_for("MEM-1") == (record,)


def test_idempotent_reappend_is_a_noop(tmp_path):
    ledger = GovernanceLedger(tmp_path)
    record = _decision()
    assert ledger.append(record) == APPEND_CREATED
    assert ledger.append(record) == APPEND_IDEMPOTENT
    assert len(ledger.decisions_for("MEM-1")) == 1


def test_colliding_decision_id_with_different_payload_raises(tmp_path):
    """This should be unreachable in practice given mint_decision_id()'s
    determinism, but if it ever happens, the ledger must refuse to overwrite
    history (Rule 16), not silently accept the new payload."""
    ledger = GovernanceLedger(tmp_path)
    record = _decision()
    ledger.append(record)
    # Construct a record that reuses the same decision_id but differs in a
    # field identity_fields() does NOT cover (reason) plus one it DOES cover,
    # by hand-crafting a mismatched record via direct dataclass construction.
    tampered = MGPDecisionRecord(
        decision_id=record.decision_id,
        candidate_memory_id="MEM-1-DIFFERENT",  # differs from identity_fields()
        policy_version=record.policy_version,
        signals_used=record.signals_used,
        action=record.action,
        resulting_state=record.resulting_state,
        reason="a different reason",
        run_id=record.run_id,
        episode_id=record.episode_id,
        timestamp=record.timestamp,
        evidence_refs=record.evidence_refs,
    )
    with pytest.raises(GovernanceLedgerCollisionError):
        ledger.append(tampered)


def test_serialization_round_trip_across_reload(tmp_path):
    """A ledger reloaded from disk must reconstruct byte-identical decisions --
    same discipline Phase 5's own ledgers already require."""
    ledger = GovernanceLedger(tmp_path)
    record = _decision(signals={"a": 1, "b": "text", "c": 3.5})
    ledger.append(record)

    reloaded = GovernanceLedger(tmp_path)
    (reloaded_record,) = reloaded.decisions_for("MEM-1")
    assert reloaded_record == record


def test_current_state_is_unassessed_with_no_decisions(tmp_path):
    ledger = GovernanceLedger(tmp_path)
    assert ledger.current_state("MEM-NEVER-SEEN") == UNASSESSED


def test_current_state_reflects_full_lifecycle_walk(tmp_path):
    """UNASSESSED -> TRUSTED -> SUSPICIOUS -> QUARANTINED -> RELEASED ->
    QUARANTINED -> BLOCKED, exercising every legal edge in Section 2.2's table
    at least once."""
    ledger = GovernanceLedger(tmp_path)
    mem = "MEM-WALK"

    ledger.append(_decision(mem, action=ALLOW, run_id="run-1", signals={"s": 1}))
    assert ledger.current_state(mem) == TRUSTED

    ledger.append(_decision(mem, action=ALLOW_WITH_RESTRICTION, run_id="run-1", signals={"s": 2}))
    assert ledger.current_state(mem) == SUSPICIOUS

    ledger.append(_decision(mem, action=QUARANTINE, run_id="run-1", signals={"s": 3}))
    assert ledger.current_state(mem) == QUARANTINED

    ledger.append(_decision(mem, action=RELEASE, run_id="run-1", signals={"s": 4}))
    assert ledger.current_state(mem) == RELEASED

    ledger.append(_decision(mem, action=QUARANTINE, run_id="run-1", signals={"s": 5}))
    assert ledger.current_state(mem) == QUARANTINED

    ledger.append(_decision(mem, action=BLOCK, run_id="run-1", signals={"s": 6}))
    assert ledger.current_state(mem) == BLOCKED


def test_current_state_ignores_downrank(tmp_path):
    """A query-local DOWNRANK must never change the memory's persisted state."""
    ledger = GovernanceLedger(tmp_path)
    mem = "MEM-DOWNRANK"
    ledger.append(_decision(mem, action=ALLOW, run_id="run-1", signals={"s": 1}))
    assert ledger.current_state(mem) == TRUSTED
    ledger.append(_decision(mem, action=DOWNRANK, run_id="run-2", signals={"s": 2}))
    assert ledger.current_state(mem) == TRUSTED  # unchanged


def test_decisions_for_returns_only_that_memorys_decisions(tmp_path):
    ledger = GovernanceLedger(tmp_path)
    ledger.append(_decision("MEM-A", action=ALLOW, run_id="run-1"))
    ledger.append(_decision("MEM-B", action=BLOCK, run_id="run-1"))
    assert len(ledger.decisions_for("MEM-A")) == 1
    assert len(ledger.decisions_for("MEM-B")) == 1
    assert ledger.decisions_for("MEM-A")[0].candidate_memory_id == "MEM-A"


def test_all_decisions_preserves_append_order(tmp_path):
    ledger = GovernanceLedger(tmp_path)
    first = _decision("MEM-A", action=ALLOW, run_id="run-1", signals={"n": 1})
    second = _decision("MEM-B", action=BLOCK, run_id="run-1", signals={"n": 2})
    ledger.append(first)
    ledger.append(second)
    assert ledger.all_decisions() == (first, second)


def test_no_delete_or_update_methods_exist():
    """Architectural invariant (Policy document Section 6): no way to mutate
    or erase history."""
    assert not hasattr(GovernanceLedger, "delete")
    assert not hasattr(GovernanceLedger, "update")


# ---------------------------------------------------------------------------
# Phase 3 lifecycle boundary -- architectural separation
# ---------------------------------------------------------------------------


def test_mgp_modules_never_import_phase3_memory_versioning():
    """MGP's security state is a completely separate concept from Phase 3's
    lifecycle status (active/superseded/retired) -- Policy document Section 1.
    This is checked by parsing actual `import`/`from ... import` statements
    (via `ast`), not by a substring scan -- a substring scan would also flag
    this module's own explanatory prose ABOUT why no such import exists, which
    is exactly backwards."""
    import ast

    import phase6.defense.policy.ledger as ledger_module
    import phase6.defense.policy.records as records_module
    import phase6.defense.policy.states as states_module

    for module in (ledger_module, records_module, states_module):
        source = module.__file__
        with open(source, "r", encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=source)
        imported_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_names.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_names.add(node.module)
        offending = {name for name in imported_names if "memory_versioning" in name}
        assert not offending, (
            f"{module.__name__} imports {offending!r} -- MGP security state "
            "and Phase 3 lifecycle status must remain architecturally separate "
            "(Policy document Section 1)."
        )
