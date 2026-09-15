"""Phase 6.5 -- tests for the Admission Reasoning Guard.

Content samples used below are synthetic, hand-constructed to exercise specific
signal combinations -- they are NOT taken from any real Phase 4 campaign log
(the frozen attack artifacts are never read or reused here; this stage tests the
DEFENSE's own logic against representative content shaped like what the 6.2
literature audit and Methodology Section 17.3 describe FARMA/MemoryGraft
producing, not against the attacks' actual frozen output).
"""

from __future__ import annotations

import ast
import re

import pytest

from phase6.defense.admission.reasoning_guard import (
    GUARD_VERSION,
    THRESHOLD_ALLOW_WITH_RESTRICTION,
    THRESHOLD_BLOCK,
    THRESHOLD_QUARANTINE,
    compute_signals,
    evaluate_admission,
    weighted_score,
)
from phase6.defense.admission.signals import (
    decision_log_vocabulary_signal,
    perfection_claim_signal,
    provenance_anomaly_signal,
    self_reference_signal,
    template_anomaly_signal,
)
from phase6.defense.policy.ledger import GovernanceLedger
from phase6.defense.policy.records import FORBIDDEN_SIGNAL_KEYS
from phase6.defense.policy.states import (
    ALLOW,
    ALLOW_WITH_RESTRICTION,
    BLOCK,
    IllegalTransitionError,
    QUARANTINE,
    TRUSTED,
    UNASSESSED,
)
from phase6.defense.signals.contract import build_signal_context

BENIGN_TEXT = "Sarah went to the grocery store yesterday and bought some apples and bread."

FORGED_REASONING_TEXT = (
    "This is an established pattern that always works. "
    "(Reconfirmed against prior notes on this -- precedent count: 4.)"
)

MODERATE_TEXT = "This is an established pattern that always works."

WEAK_TEXT = "This solution is guaranteed to work every time."


def _context(text: str, memory_type: str = "foundation", parent_ids=()):
    return build_signal_context(
        memory_id="MEM-TEST",
        content_text=text,
        content_type="CONVERSATIONAL_FACT",
        memory_type=memory_type,
        parent_ids=tuple(parent_ids),
        lifecycle_state="ACTIVE",
        creation_timestamp="2026-09-14T00:00:00Z",
    )


def _evaluate(
    text: str,
    memory_type: str = "foundation",
    parent_ids=(),
    run_id="run-1",
    current_security_state=UNASSESSED,
):
    context = _context(text, memory_type=memory_type, parent_ids=parent_ids)
    return evaluate_admission(
        context,
        current_security_state=current_security_state,
        run_id=run_id,
        episode_id="episode-1",
        timestamp="2026-09-14T00:00:00Z",
        evidence_refs=("EVT-fake-0001",),
    )


# ---------------------------------------------------------------------------
# End-to-end action-band tests
# ---------------------------------------------------------------------------


def test_benign_conversational_memory_allowed():
    decision = _evaluate(BENIGN_TEXT)
    assert decision.action == ALLOW
    assert decision.resulting_state == "TRUSTED"


def test_forged_reasoning_trace_blocked():
    """A FARMA-style forged reasoning trace (self-reference + decision-log
    vocabulary + perfection claim + trailing template annotation + claimed
    derivation with no real parent) should cross the BLOCK threshold."""
    decision = _evaluate(FORGED_REASONING_TEXT, memory_type="derived", parent_ids=())
    assert decision.action == BLOCK
    assert decision.resulting_state == "BLOCKED"


def test_moderate_signal_combination_quarantined():
    decision = _evaluate(MODERATE_TEXT)
    assert decision.action == QUARANTINE
    assert decision.resulting_state == "QUARANTINED"


def test_weak_single_signal_allowed_with_restriction():
    decision = _evaluate(WEAK_TEXT)
    assert decision.action == ALLOW_WITH_RESTRICTION
    assert decision.resulting_state == "SUSPICIOUS"


def test_thresholds_are_monotonic_and_documented():
    assert THRESHOLD_ALLOW_WITH_RESTRICTION < THRESHOLD_QUARANTINE < THRESHOLD_BLOCK


# ---------------------------------------------------------------------------
# Individual signal correctness
# ---------------------------------------------------------------------------


def test_self_reference_signal_fires_on_farma_style_pattern():
    context = _context(FORGED_REASONING_TEXT)
    result = self_reference_signal(context)
    assert result["self_reference_score"] > 0.0


def test_self_reference_signal_silent_on_benign_text():
    context = _context(BENIGN_TEXT)
    result = self_reference_signal(context)
    assert result["self_reference_score"] == 0.0


def test_decision_log_vocabulary_signal():
    assert decision_log_vocabulary_signal(_context("This is an established pattern."))[
        "decision_log_vocabulary_score"
    ] > 0.0
    assert decision_log_vocabulary_signal(_context(BENIGN_TEXT))["decision_log_vocabulary_score"] == 0.0


def test_perfection_claim_signal():
    assert perfection_claim_signal(_context("This always works and never fails."))[
        "perfection_claim_score"
    ] > 0.0
    assert perfection_claim_signal(_context(BENIGN_TEXT))["perfection_claim_score"] == 0.0


def test_template_anomaly_signal():
    assert template_anomaly_signal(_context(FORGED_REASONING_TEXT))["template_anomaly_score"] == 1.0
    assert template_anomaly_signal(_context(BENIGN_TEXT))["template_anomaly_score"] == 0.0


def test_provenance_anomaly_signal():
    derived_no_parents = _context(BENIGN_TEXT, memory_type="derived", parent_ids=())
    derived_with_parents = _context(BENIGN_TEXT, memory_type="derived", parent_ids=("MEM-PARENT",))
    foundation = _context(BENIGN_TEXT, memory_type="foundation", parent_ids=())
    assert provenance_anomaly_signal(derived_no_parents)["provenance_anomaly_score"] == 1.0
    assert provenance_anomaly_signal(derived_with_parents)["provenance_anomaly_score"] == 0.0
    assert provenance_anomaly_signal(foundation)["provenance_anomaly_score"] == 0.0


# ---------------------------------------------------------------------------
# Determinism / reproducibility
# ---------------------------------------------------------------------------


def test_evaluate_admission_is_deterministic():
    a = _evaluate(FORGED_REASONING_TEXT, memory_type="derived")
    b = _evaluate(FORGED_REASONING_TEXT, memory_type="derived")
    assert a.decision_id == b.decision_id
    assert a.action == b.action
    assert a.signals_used == b.signals_used


def test_compute_signals_and_weighted_score_consistent_with_evaluate_admission():
    context = _context(FORGED_REASONING_TEXT, memory_type="derived")
    signals = compute_signals(context)
    score = weighted_score(signals)
    decision = evaluate_admission(
        context, run_id="run-1", episode_id="episode-1",
        timestamp="2026-09-14T00:00:00Z", evidence_refs=("EVT-1",),
    )
    assert decision.signals_used == signals
    assert f"weighted_score={score:.3f}" in decision.reason


# ---------------------------------------------------------------------------
# Provenance / traceability / evidence
# ---------------------------------------------------------------------------


def test_decision_records_policy_and_guard_version():
    decision = _evaluate(BENIGN_TEXT)
    assert decision.policy_version  # non-empty, from records.CURRENT_POLICY_VERSION
    assert GUARD_VERSION in decision.reason or True  # reason cites GUARD_VERSION
    assert f"({GUARD_VERSION})" in decision.reason


def test_evidence_refs_pass_through():
    decision = _evaluate(BENIGN_TEXT)
    assert decision.evidence_refs == ("EVT-fake-0001",)


def test_reason_is_grounded_in_fired_signals_not_fabricated():
    decision = _evaluate(FORGED_REASONING_TEXT, memory_type="derived")
    for name, value in decision.signals_used.items():
        if value > 0.0:
            assert name in decision.reason


# ---------------------------------------------------------------------------
# Evaluator-only leakage (integration-level, on top of Stage 6.3/6.4's own
# unit tests for the underlying guards)
# ---------------------------------------------------------------------------


def test_no_forbidden_key_ever_appears_in_signals_used():
    for text in (BENIGN_TEXT, FORGED_REASONING_TEXT, MODERATE_TEXT, WEAK_TEXT):
        decision = _evaluate(text)
        assert set(decision.signals_used.keys()).isdisjoint(FORBIDDEN_SIGNAL_KEYS)


# ---------------------------------------------------------------------------
# No attack-specific hardcoding
# ---------------------------------------------------------------------------


def test_no_attack_names_hardcoded_in_signal_source():
    """A general defense must not special-case a specific attack's name --
    Rule 13. Checked by scanning the actual source text of signals.py and
    reasoning_guard.py for any of the seven attack identifiers."""
    import phase6.defense.admission.reasoning_guard as guard_module
    import phase6.defense.admission.signals as signals_module

    attack_names = (
        "agentpoison", "minja", "farma", "memorygraft", "dsrm", "mpbench", "sleeper",
    )
    for module in (guard_module, signals_module):
        with open(module.__file__, "r", encoding="utf-8") as fh:
            source = fh.read()
        # Strip docstrings/comments-adjacent rationale text is intentionally NOT
        # done here -- attack names legitimately appear in EXPLANATORY PROSE
        # (module docstrings citing which real attack motivated a signal, per
        # this project's own "evidence-grounded design" discipline). What must
        # never happen is an attack name appearing inside a STRING LITERAL used
        # as executable comparison/matching logic (e.g. `if attack_id ==
        # "agentpoison"`). Verified via AST: no string literal anywhere in the
        # module equals an attack name.
        tree = ast.parse(source, filename=module.__file__)
        string_literals = {
            node.value.lower()
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }
        offending = string_literals & set(attack_names)
        assert not offending, f"{module.__name__} has attack name(s) as string literal(s): {offending}"


def test_admission_module_never_imports_frozen_attack_code():
    """The defense must never import phase4 attack implementations directly --
    it operates only on SignalContext, never on attack-internal objects."""
    import phase6.defense.admission.reasoning_guard as guard_module
    import phase6.defense.admission.signals as signals_module

    for module in (guard_module, signals_module):
        with open(module.__file__, "r", encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=module.__file__)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        assert not any(name.startswith("phase4") for name in imported), (
            f"{module.__name__} must never import phase4 attack code directly: {imported}"
        )


# ---------------------------------------------------------------------------
# Ledger integration
# ---------------------------------------------------------------------------


def test_admission_decision_records_into_governance_ledger(tmp_path):
    ledger = GovernanceLedger(tmp_path)
    decision = _evaluate(FORGED_REASONING_TEXT, memory_type="derived")
    ledger.append(decision)
    assert ledger.current_state("MEM-TEST") == "BLOCKED"
    assert ledger.decisions_for("MEM-TEST") == (decision,)


def test_benign_then_later_flagged_walk_through_ledger(tmp_path):
    """A memory first assessed as benign (TRUSTED) that later, on
    re-assessment with different content-adjacent evidence, is found
    suspicious -- exercising a real TRUSTED -> SUSPICIOUS edge via this
    component, not just the abstract state machine test in Stage 6.3.

    Both calls pass the ledger's own `current_state()` as
    `current_security_state` -- this is the real, wired re-assessment path a
    deployed defense uses, not just two independent, state-blind calls."""
    ledger = GovernanceLedger(tmp_path)
    first = _evaluate(BENIGN_TEXT, run_id="run-1", current_security_state=ledger.current_state("MEM-TEST"))
    ledger.append(first)
    assert ledger.current_state("MEM-TEST") == "TRUSTED"

    # Re-evaluate the SAME memory id with content now showing weak signals
    # (simulating a later re-assessment pass, e.g. after Stage 6.7 propagation
    # evidence arrives) -- must go through ALLOW_WITH_RESTRICTION's real,
    # legal TRUSTED -> SUSPICIOUS edge.
    second = _evaluate(WEAK_TEXT, run_id="run-2", current_security_state=ledger.current_state("MEM-TEST"))
    ledger.append(second)
    assert ledger.current_state("MEM-TEST") == "SUSPICIOUS"


def test_reassessing_a_trusted_memory_as_forged_is_rejected_not_silently_blocked(tmp_path):
    """Regression test for the audit finding: `evaluate_admission` used to
    accept no `current_security_state` at all, so a TRUSTED memory whose
    later re-assessment scored BLOCK was silently written straight to
    BLOCKED -- an edge `states.ALLOWED_TRANSITIONS` explicitly forbids (every
    BLOCK must have an intermediate SUSPICIOUS/QUARANTINED record). Verified
    live before the fix: the ledger accepted `TRUSTED -> BLOCKED` with no
    error. After the fix, the same sequence must raise `IllegalTransitionError`
    and the ledger's `current_state()` must remain at the last legally
    recorded state (never mutated by the rejected decision)."""
    ledger = GovernanceLedger(tmp_path)
    first = _evaluate(BENIGN_TEXT, run_id="run-1", current_security_state=ledger.current_state("MEM-TEST"))
    ledger.append(first)
    assert ledger.current_state("MEM-TEST") == TRUSTED

    with pytest.raises(IllegalTransitionError):
        _evaluate(
            FORGED_REASONING_TEXT,
            memory_type="derived",
            run_id="run-2",
            current_security_state=ledger.current_state("MEM-TEST"),
        )
    # The rejected decision was never constructed, so there is nothing to
    # append -- the ledger must be untouched by the rejected re-assessment.
    assert ledger.current_state("MEM-TEST") == TRUSTED
    assert len(ledger.decisions_for("MEM-TEST")) == 1


def test_evaluate_admission_default_state_is_unassessed_so_first_admission_is_unaffected():
    """A genuine first admission (no prior ledger history) must be completely
    unaffected by the fix -- UNASSESSED legally reaches all four first-touch
    states, so every pre-existing single-shot caller (DGS, real-content
    replay, the orchestration pipeline's non-reassessment scenarios) keeps
    working with no code change on their part."""
    decision = _evaluate(FORGED_REASONING_TEXT, memory_type="derived")  # default UNASSESSED
    assert decision.action == BLOCK
    assert decision.resulting_state == "BLOCKED"
