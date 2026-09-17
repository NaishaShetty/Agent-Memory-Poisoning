"""Phase 6.8 -- the Sleeper Guard: admission-time and retrieval-time decision
layers for dormant, document-embedded write-instruction content.

TWO DECISION POINTS, MATCHING THE ATTACK'S OWN TWO-PHASE STRUCTURE
--------------------------------------------------------------------------------
`evaluate_sleeper_admission()` -- runs at write time, using ONLY the content-
structural signal (`imperative_write_directive_signal`). This is the
"dormant poison before activation" case: catching a document-embedded
write-instruction at the moment it is ingested, before it has ever been
retrieved at all.

`evaluate_sleeper_retrieval_risk()` -- runs at retrieval time, MULTIPLYING the
content-structural signal by a real, legitimate dormancy signal (how much this
retrieval looks like a first activation). This is deliberately GATED, not
additive: `dormancy_activation_score` alone -- a memory simply being retrieved
for the first time -- must NEVER trigger anything on its own, because the vast
majority of first-time retrievals are completely ordinary (Stage 6.8's required
"benign dormant-looking memory" scenario). Only the COMBINATION of a directive-
structured payload AND a first-activation-shaped retrieval event is treated as
meaningful -- multiplying two independent [0,1] scores, rather than summing or
averaging them, is what enforces this gate: if either factor is 0, the product
is 0.

BOTH LAYERS CAP AT QUARANTINE, NEVER BLOCK
--------------------------------------------------------------------------------
Unlike Stage 6.5's Reasoning Guard (five independently-weighted signals
combined into one score, which CAN reach BLOCK), this module relies on a
single regex-based structural heuristic per decision. That heuristic was
validated against a real true/false-positive test set before being shipped
(see `signals.py`'s module docstring), but a single, untested-at-scale,
natural-language pattern match is deliberately treated as weaker evidence than
Stage 6.5's multi-signal corroboration -- the same "indirect/single-source
evidence caps below BLOCK" discipline Stage 6.7's propagation containment
already established for lineage evidence, applied here for the analogous
reason (a single structural heuristic, however precise on its own test set, is
not enough alone to justify the strongest, least-reversible action).
"""

from __future__ import annotations

from typing import Optional, Sequence

from phase6.defense.policy.records import MGPDecisionRecord, build_decision
from phase6.defense.policy.states import (
    ALLOW,
    DOWNRANK,
    QUARANTINE,
    validate_transition,
)
from phase6.defense.sleeper.signals import (
    age_based_dormancy_gate_signal,
    dormancy_activation_signal,
    imperative_write_directive_signal,
)
from phase6.defense.signals.contract import SignalContext

GUARD_VERSION = "sleeper-guard-1.0.0"

# Uncalibrated v1 threshold (disclosed, versioned starting default). The
# admission-time signal is binary (0.0/1.0 -- see signals.py), so this
# threshold's only real effect is "fires at all vs. does not."
ADMISSION_THRESHOLD_QUARANTINE = 0.5

# Retrieval-time thresholds on the GATED product
# (imperative_write_directive_score * dormancy_activation_score).
RETRIEVAL_THRESHOLD_QUARANTINE = 0.5
RETRIEVAL_THRESHOLD_ALLOW_WITH_RESTRICTION = 0.2


def evaluate_sleeper_admission(
    context: SignalContext,
    *,
    run_id: str,
    episode_id: str,
    timestamp: str,
    evidence_refs: Sequence[str],
) -> MGPDecisionRecord:
    """Admission-time check: does this content structurally resemble a
    document-embedded, persistent write-instruction (Sleeper's own documented
    mechanism), independent of any retrieval history (there is none yet at
    admission time)."""
    signal = imperative_write_directive_signal(context)
    score = signal["imperative_write_directive_score"]
    action = QUARANTINE if score >= ADMISSION_THRESHOLD_QUARANTINE else ALLOW
    reason = (
        f"imperative_write_directive_score={score:.1f} ({GUARD_VERSION}); "
        f"action={action}"
    )
    return build_decision(
        candidate_memory_id=context.memory_id,
        signals_used=signal,
        action=action,
        reason=reason,
        run_id=run_id,
        episode_id=episode_id,
        timestamp=timestamp,
        evidence_refs=evidence_refs,
    )


def evaluate_sleeper_retrieval_risk(
    memory_id: str,
    content_context: SignalContext,
    prior_retrieval_count: int,
    current_security_state: str,
    *,
    run_id: str,
    episode_id: str,
    timestamp: str,
    evidence_refs: Sequence[str],
    as_of_timestamp: Optional[str] = None,
) -> MGPDecisionRecord:
    """Retrieval-time check: does the COMBINATION of directive-structured
    content and a first-activation-shaped retrieval pattern suggest a dormant
    payload is triggering now. `action` is query-local (`DOWNRANK`) below the
    QUARANTINE band, matching Stage 6.6's D3-local/persistent split -- a
    genuinely low-risk retrieval should not write a persistent state change.

    `validate_transition()` is called before returning whenever the action
    would be persistent (QUARANTINE), exactly as every other Phase 6 decision
    layer does.

    `as_of_timestamp` (OPTIONAL, default `None`): the real, precisely-targeted
    fix for Phase 8.9's calibration finding (see `docs/phase6/SLEEPER_DEFENSE.md`
    limitations item 3's Update). The collision the calibration study proved is
    specific to `prior_retrieval_count == 0`: `dormancy_activation_signal(0)`
    is ALWAYS exactly `1.0` by construction, so it cannot distinguish a memory
    retrieved the instant it was created (ordinary, the common case for most
    real memories) from one that sat genuinely dormant before its first real
    activation -- the real Sleeper campaign's own real activation point (Phase
    8's cross-signal trial) actually occurs at `prior_retrieval_count == 1`,
    NOT `0`, so it is untouched by this change.

    When `as_of_timestamp` is supplied AND `prior_retrieval_count == 0`, the
    dormancy component used in `gated_score` is REPLACED by `age_based_
    dormancy_gate_signal()` -- real elapsed time between `content_context.
    creation_timestamp` and this retrieval -- instead of the naive, always-1.0
    ceiling. For `prior_retrieval_count >= 1`, `as_of_timestamp` has no effect:
    `dormancy_activation_signal()`'s existing, already-adequate decay curve is
    used exactly as before (multiplying a further decaying age factor onto an
    already-decayed score would push the real attack's own real activation
    point, `gated_score == 0.5` at `n=1`, below the QUARANTINE threshold --
    verified by direct computation before this narrower design was chosen).

    When `as_of_timestamp` is omitted (the default) or `prior_retrieval_count
    != 0`, this function's behavior is IDENTICAL to before this parameter
    existed -- every existing caller and test is unaffected.
    """
    directive_signal = imperative_write_directive_signal(content_context)
    dormancy_signal = dormancy_activation_signal(prior_retrieval_count)
    signals_used = {**directive_signal, **dormancy_signal}

    dormancy_component = dormancy_signal["dormancy_activation_score"]
    if as_of_timestamp is not None and prior_retrieval_count == 0:
        age_signal = age_based_dormancy_gate_signal(content_context.creation_timestamp, as_of_timestamp)
        dormancy_component = age_signal["age_based_dormancy_gate_score"]
        signals_used = {**signals_used, **age_signal}

    gated_score = directive_signal["imperative_write_directive_score"] * dormancy_component

    if gated_score >= RETRIEVAL_THRESHOLD_QUARANTINE:
        action = QUARANTINE
        validate_transition(current_security_state, action)
    elif gated_score >= RETRIEVAL_THRESHOLD_ALLOW_WITH_RESTRICTION:
        action = DOWNRANK  # query-local -- no persisted state change
    else:
        # Below the DOWNRANK band: a bare-nonzero gated score here (directive
        # pattern present, but on content retrieved many times before, so
        # dormancy_activation_score is already small) is deliberately treated
        # as ALLOW, not a persistent ALLOW_WITH_RESTRICTION -- a single,
        # regex-based structural match on well-established, already-vetted
        # content is not meaningful evidence on its own (an earlier draft of
        # this function incorrectly escalated any nonzero score to a
        # persistent SUSPICIOUS state; fixed here before shipping, per this
        # project's own "verify before claiming correct" discipline).
        action = ALLOW

    age_gate_used = as_of_timestamp is not None and prior_retrieval_count == 0
    age_gate_note = f", age_gate_dormancy={dormancy_component:.3f}" if age_gate_used else ""
    reason = (
        f"gated_score={gated_score:.3f} ({GUARD_VERSION}); "
        f"directive={directive_signal['imperative_write_directive_score']:.1f}, "
        f"dormancy={dormancy_signal['dormancy_activation_score']:.3f}{age_gate_note}; action={action}"
    )
    return build_decision(
        candidate_memory_id=memory_id,
        signals_used=signals_used,
        action=action,
        reason=reason,
        run_id=run_id,
        episode_id=episode_id,
        timestamp=timestamp,
        evidence_refs=evidence_refs,
    )
