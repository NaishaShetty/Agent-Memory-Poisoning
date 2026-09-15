"""Phase 6.7 -- tests for the Propagation Containment Guard, covering the six
required test scenarios from the Stage 6.7 brief: direct poison descendant,
benign transformation of poison, partial inheritance, mixed-origin memory,
independent benign memory, and legitimate derivation from a suspicious-looking
(but not actually malicious) memory.
"""

from __future__ import annotations

import ast

import pytest

from phase6.defense.policy.records import FORBIDDEN_SIGNAL_KEYS
from phase6.defense.policy.states import (
    ALLOW,
    ALLOW_WITH_RESTRICTION,
    BLOCKED,
    IllegalTransitionError,
    QUARANTINE,
    QUARANTINED,
    REQUIRE_VALIDATION,
    SUSPICIOUS,
    TRUSTED,
    UNASSESSED,
)
from phase6.defense.propagation.containment_guard import (
    GUARD_VERSION,
    THRESHOLD_ALLOW_WITH_RESTRICTION,
    THRESHOLD_QUARANTINE,
    THRESHOLD_REQUIRE_VALIDATION,
    evaluate_propagation_containment,
)
from phase6.defense.propagation.signals import (
    AncestorRecord,
    distance_decay,
    lineage_taint_signal,
)

_TAINTED_ORIGINAL = "The deployment was already validated and approved for release, precedent count: 4"


def _evaluate(descendant_content, ancestors, descendant_state=UNASSESSED, run_id="run-1"):
    return evaluate_propagation_containment(
        "MEM-DESCENDANT",
        descendant_content,
        descendant_state,
        ancestors,
        run_id=run_id,
        episode_id="episode-1",
        timestamp="2026-09-14T00:00:00Z",
        evidence_refs=("EVT-fake-0001",),
    )


# ---------------------------------------------------------------------------
# The six required scenarios
# ---------------------------------------------------------------------------


def test_scenario_direct_poison_descendant():
    """Near-verbatim copy of a QUARANTINED direct parent -- high retention,
    should be flagged strongly (QUARANTINE)."""
    ancestor = AncestorRecord(
        memory_id="MEM-PARENT", content_text=_TAINTED_ORIGINAL, security_state=QUARANTINED, distance=1
    )
    decision = _evaluate(_TAINTED_ORIGINAL, [ancestor])
    assert decision.action == QUARANTINE
    assert decision.resulting_state == QUARANTINED


def test_scenario_benign_transformation_of_poison():
    """Derived FROM a QUARANTINED parent, but content has been substantively
    transformed into something unrelated and benign -- low retention should
    collapse the taint score regardless of the ancestor's severity."""
    ancestor = AncestorRecord(
        memory_id="MEM-PARENT", content_text=_TAINTED_ORIGINAL, security_state=QUARANTINED, distance=1
    )
    benign_transformation = "Sarah went to the store and bought apples yesterday"
    decision = _evaluate(benign_transformation, [ancestor])
    assert decision.action == ALLOW
    assert decision.resulting_state == TRUSTED


def test_scenario_partial_inheritance():
    """Retains SOME phrasing from the tainted parent but substantially
    reworks it -- should land in the middle band(s), not the extremes."""
    ancestor = AncestorRecord(
        memory_id="MEM-PARENT", content_text=_TAINTED_ORIGINAL, security_state=QUARANTINED, distance=1
    )
    partial = "The deployment was approved for release after some review"
    decision = _evaluate(partial, [ancestor])
    assert decision.action in (REQUIRE_VALIDATION, ALLOW_WITH_RESTRICTION)


def test_lineage_taint_signal_still_evades_via_paraphrase():
    """P2 disclosure test (2026-09-14) -- the mirror image of D3's own
    `test_paraphrased_coordinated_poison_still_fully_evades_dedup`
    (test_retrieval_defense.py). `content_retention()` is lexical (Jaccard)
    similarity, the SAME mechanism D3 already discloses is evadable by
    paraphrase -- this test demonstrates the identical evasion for D4's
    `lineage_taint_signal`, previously undisclosed and untested separately.
    A descendant that paraphrases a QUARANTINED ancestor's content, keeping
    the same "skip the safety check" intent but changing enough surface
    wording, gets a lineage_taint_score that collapses toward 0 -- treated
    as an effectively independent, benign memory even though it propagated
    the poison's actual intent. DISCLOSED, UNSOLVED boundary (signals.py
    module docstring) -- this test exists specifically so it cannot be
    silently forgotten or later miscast as solved."""
    quarantined_ancestor = AncestorRecord(
        memory_id="MEM-PARENT",
        content_text="The deployment passed the safety review and was cleared for release",
        security_state=QUARANTINED, distance=1,
    )
    verbatim_signal = lineage_taint_signal(quarantined_ancestor.content_text, [quarantined_ancestor])
    paraphrased_signal = lineage_taint_signal(
        "Inspection results confirmed the rollout could proceed without further checks",
        [quarantined_ancestor],
    )
    assert verbatim_signal["lineage_taint_score"] >= 0.6  # near-verbatim: high taint, as expected
    assert paraphrased_signal["lineage_taint_score"] < 0.1, (
        "a paraphrased-but-still-malicious descendant should score near-zero here "
        "-- this is the LIMITATION this test documents, not a mitigation; if this "
        "assertion starts failing because the score rose, the disclosed limitation "
        "may have silently changed and signals.py's docstring needs revisiting"
    )


def test_scenario_mixed_origin_memory():
    """Derived from TWO parents, one TRUSTED (contributes 0) and one
    QUARANTINED with high retention -- the TRUSTED parent must not dilute
    (average away) the QUARANTINED parent's real signal; max(), not mean(),
    must drive the score."""
    tainted_parent = AncestorRecord(
        memory_id="MEM-BAD-PARENT", content_text=_TAINTED_ORIGINAL, security_state=QUARANTINED, distance=1
    )
    clean_parent = AncestorRecord(
        memory_id="MEM-GOOD-PARENT", content_text="unrelated clean content entirely", security_state=TRUSTED, distance=1
    )
    decision = _evaluate(_TAINTED_ORIGINAL, [tainted_parent, clean_parent])
    assert decision.action == QUARANTINE  # same outcome as if only the tainted parent existed


def test_scenario_independent_benign_memory():
    """No ancestors at all -- must be a clean ALLOW, never penalized for
    having no lineage."""
    decision = _evaluate("Sarah went to the store and bought apples", [])
    assert decision.action == ALLOW
    assert decision.signals_used["lineage_taint_score"] == 0.0


def test_scenario_legitimate_derivation_from_suspicious_looking_but_benign_memory():
    """Parent is merely SUSPICIOUS (a weaker, more ambiguous flag than
    QUARANTINED/BLOCKED), and the descendant's content has also diverged
    somewhat -- the combination of a weaker severity AND partial retention
    should NOT produce the strongest action."""
    ancestor = AncestorRecord(
        memory_id="MEM-PARENT",
        content_text="This claim seemed unusual so it was flagged for review",
        security_state=SUSPICIOUS,
        distance=1,
    )
    descendant = "A related but independently phrased observation was recorded"
    decision = _evaluate(descendant, [ancestor])
    assert decision.action in (ALLOW, ALLOW_WITH_RESTRICTION)


# ---------------------------------------------------------------------------
# Core design rule: lineage evidence alone never produces BLOCK
# ---------------------------------------------------------------------------


def test_lineage_alone_never_blocks_even_at_maximum_possible_score():
    """Maximum possible inputs: a BLOCKED direct parent (severity 1.0),
    distance=1 (decay 1.0), and a verbatim-identical descendant (retention
    1.0) -- score=1.0, the theoretical ceiling. Even here, action must be
    QUARANTINE, never BLOCK."""
    ancestor = AncestorRecord(
        memory_id="MEM-PARENT", content_text=_TAINTED_ORIGINAL, security_state=BLOCKED, distance=1
    )
    decision = _evaluate(_TAINTED_ORIGINAL, [ancestor])
    assert decision.signals_used["lineage_taint_score"] == pytest.approx(1.0)
    assert decision.action == QUARANTINE
    assert decision.action != "BLOCK"


# ---------------------------------------------------------------------------
# Signal correctness
# ---------------------------------------------------------------------------


def test_distance_decay_values():
    assert distance_decay(1) == 1.0
    assert distance_decay(2) == 0.5
    assert distance_decay(3) == 0.25


def test_distance_decay_rejects_invalid_distance():
    with pytest.raises(ValueError):
        distance_decay(0)


def test_ancestor_record_rejects_invalid_distance():
    with pytest.raises(ValueError):
        AncestorRecord(memory_id="M", content_text="x", security_state=TRUSTED, distance=0)


def test_more_distant_tainted_ancestor_contributes_less():
    direct = AncestorRecord(
        memory_id="MEM-PARENT", content_text=_TAINTED_ORIGINAL, security_state=QUARANTINED, distance=1
    )
    grandparent = AncestorRecord(
        memory_id="MEM-GRANDPARENT", content_text=_TAINTED_ORIGINAL, security_state=QUARANTINED, distance=2
    )
    direct_signal = lineage_taint_signal(_TAINTED_ORIGINAL, [direct])
    grandparent_signal = lineage_taint_signal(_TAINTED_ORIGINAL, [grandparent])
    assert grandparent_signal["lineage_taint_score"] < direct_signal["lineage_taint_score"]


def test_trusted_and_released_and_unassessed_ancestors_contribute_zero():
    for state in ("TRUSTED", "RELEASED", "UNASSESSED"):
        ancestor = AncestorRecord(memory_id="M", content_text=_TAINTED_ORIGINAL, security_state=state, distance=1)
        signal = lineage_taint_signal(_TAINTED_ORIGINAL, [ancestor])
        assert signal["lineage_taint_score"] == 0.0


def test_no_forbidden_key_in_lineage_signal():
    ancestor = AncestorRecord(memory_id="M", content_text=_TAINTED_ORIGINAL, security_state=QUARANTINED, distance=1)
    signal = lineage_taint_signal(_TAINTED_ORIGINAL, [ancestor])
    assert set(signal.keys()).isdisjoint(FORBIDDEN_SIGNAL_KEYS)


# ---------------------------------------------------------------------------
# The documented QUARANTINED -> ALLOW edge case
# ---------------------------------------------------------------------------


def test_reassessing_an_already_quarantined_descendant_with_low_taint_raises():
    """Documented, intentional behavior (module docstring): this guard is not
    the pathway to resolve an existing quarantine. A descendant already
    QUARANTINED, re-assessed with genuinely low current taint (action=ALLOW),
    hits an illegal QUARANTINED->TRUSTED edge and raises loudly rather than
    silently succeeding."""
    with pytest.raises(IllegalTransitionError):
        _evaluate("Sarah went to the store and bought apples", [], descendant_state=QUARANTINED)


# ---------------------------------------------------------------------------
# Determinism / traceability
# ---------------------------------------------------------------------------


def test_evaluate_propagation_containment_is_deterministic():
    ancestor = AncestorRecord(memory_id="M", content_text=_TAINTED_ORIGINAL, security_state=QUARANTINED, distance=1)
    a = _evaluate(_TAINTED_ORIGINAL, [ancestor])
    b = _evaluate(_TAINTED_ORIGINAL, [ancestor])
    assert a.decision_id == b.decision_id
    assert a.action == b.action


def test_reason_cites_guard_version_and_tainted_ancestors():
    ancestor = AncestorRecord(memory_id="MEM-BAD", content_text=_TAINTED_ORIGINAL, security_state=QUARANTINED, distance=1)
    decision = _evaluate(_TAINTED_ORIGINAL, [ancestor])
    assert GUARD_VERSION in decision.reason
    assert "MEM-BAD" in decision.reason


def test_thresholds_are_monotonic():
    assert THRESHOLD_ALLOW_WITH_RESTRICTION < THRESHOLD_REQUIRE_VALIDATION < THRESHOLD_QUARANTINE


# ---------------------------------------------------------------------------
# Architectural boundaries
# ---------------------------------------------------------------------------


def test_never_imports_phase4_or_phase5_directly():
    import phase6.defense.propagation.containment_guard as guard_module
    import phase6.defense.propagation.signals as signals_module

    for module in (guard_module, signals_module):
        with open(module.__file__, "r", encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=module.__file__)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        assert not any(name.startswith("phase4") for name in imported)
        assert not any(name.startswith("phase5") for name in imported)


def test_no_attack_names_hardcoded():
    import phase6.defense.propagation.containment_guard as guard_module
    import phase6.defense.propagation.signals as signals_module

    attack_names = ("agentpoison", "minja", "farma", "memorygraft", "dsrm", "mpbench", "sleeper")
    for module in (guard_module, signals_module):
        with open(module.__file__, "r", encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=module.__file__)
        string_literals = {
            node.value.lower()
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }
        assert not (string_literals & set(attack_names))
