"""Phase 10.1 -- `RiskEstimate` and `compute_memory_risk_score()`: the missing
arithmetic between Phase 6-9's already-built, per-guard detectors.

See `docs/phase10/PHASE10_PLAN.md` Section 4.1 for the full rationale. This
module invents NO new signal -- every key `compute_memory_risk_score()` may
consume is one already produced by an existing, shipped signal function
(`phase6/defense/{admission,retrieval,propagation,sleeper}/signals.py`) and
already flows through `MGPDecisionRecord.signals_used`. This module's only
job is to combine those real, already-computed values into one continuous,
disclosed risk estimate before any guard's own threshold check fires.

WHY THE SANCTIONED VOCABULARY IS A CLOSED, EXPLICIT SET HERE
--------------------------------------------------------------------------------
`phase6/defense/signals/contract.py`'s `@signal_function` decorator and
`phase6/defense/policy/records.py`'s `FORBIDDEN_SIGNAL_KEYS` both guard the
OUTPUT side of individual signal functions (never let an evaluator-only key
escape). Neither one publishes a positive, closed list of every legitimate
signal key -- that list exists only implicitly, as "whatever the shipped
signal functions happen to return." Stage 10.1 needs a positive list (an
unrecognized key must be REFUSED, not silently combined), so
`SANCTIONED_RISK_SIGNAL_KEYS` below enumerates every real signal key this
project has shipped, one entry per already-existing signal function, each
cited by its real source. Adding a new signal function anywhere in Phase
6-9 does NOT automatically make its key usable here -- it must be added to
this list deliberately, the same "one obvious, documented place" discipline
`build_signal_context()` already uses for `SignalContext` construction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Mapping, Optional, Tuple

from phase6.defense.policy.records import FORBIDDEN_SIGNAL_KEYS, EvaluatorOnlyLeakageError

RISK_SCORE_VERSION = "risk-score-10.1.0"

# ---------------------------------------------------------------------------
# The sanctioned, closed vocabulary -- every key is a real score already
# produced by an existing, shipped signal function, grouped by the guard that
# produces it (the grouping is also what `_GROUPED_GATED_WEIGHTS` below keys
# off of).
# ---------------------------------------------------------------------------

ADMISSION_SIGNAL_KEYS: frozenset = frozenset(
    {
        "self_reference_score",  # admission/signals.py::self_reference_signal
        "decision_log_vocabulary_score",  # admission/signals.py::decision_log_vocabulary_signal
        "perfection_claim_score",  # admission/signals.py::perfection_claim_signal
        "template_anomaly_score",  # admission/signals.py::template_anomaly_signal
        "provenance_anomaly_score",  # admission/signals.py::provenance_anomaly_signal
        # 2026-09-21 (Phase 12 follow-on, explicitly authorized):
        # `interrogative_restatement_score` (admission/signals.py's own
        # module docstring has the full real justification -- DSRM's real
        # "question + forged answer" construction, 0/502 real benign false
        # positives, 0/75 real corpus.py scenarios, completely inert on the
        # tuned corpus). Additive only: no existing key's weight changes;
        # `_admission_group_score()` below picks this up automatically at
        # the same 0.2 weight as the original five, verified to leave the
        # real, historically-reported 70.6%/7.3% B8/B9 numbers unchanged.
        "interrogative_restatement_score",
        # Same session: `task_completion_note_score` (admission/signals.py's
        # own module docstring has the full real justification -- also
        # verified inert on corpus.py's 75 real scenarios).
        "task_completion_note_score",
        # Same session: `stale_precedent_dismissal_score` (admission/
        # signals.py's own module docstring has the full real justification,
        # including why this is a NEW key rather than a broadening of
        # `self_reference_score` -- that alternative was tried and reverted
        # because `self_reference_score` is one of Phase 11's own closed
        # GNN `FEATURE_KEYS`, and broadening it silently shifted 10 already-
        # locked-in Phase 11 real numbers). Also verified inert on
        # corpus.py's 75 real scenarios.
        "stale_precedent_dismissal_score",
        # Same session: `third_person_report_score` (admission/signals.py's
        # own module docstring has the full real justification -- also
        # verified inert on corpus.py's 75 real scenarios).
        "third_person_report_score",
        # Same session: `entity_link_directive_score` (MINJA) and
        # `forged_provenance_confirmation_score` (AgentPoison) --
        # admission/signals.py's own module docstrings have the full real
        # justification. Also verified inert on corpus.py's 75 real
        # scenarios.
        "entity_link_directive_score",
        "forged_provenance_confirmation_score",
        # 2026-09-23 (Phase 14 follow-on, explicitly authorized):
        # `synthetic_repetition_padding_score` (admission/signals.py's own
        # module comment has the full real justification -- DSRM's real
        # verbatim-repetition/"N/A" padding construction, 0/502 real benign
        # false positives, 0/75 real corpus.py scenarios).
        "synthetic_repetition_padding_score",
        # 2026-09-23, same session: `unverifiable_closure_score`
        # (admission/signals.py's own module comment has the full real
        # justification -- FARMA's real "the fact is now unconfirmable"
        # construction, 0/502 real benign false positives, 0/75 real
        # corpus.py scenarios).
        "unverifiable_closure_score",
        # 2026-09-23, same session: `preference_decision_update_score`
        # (admission/signals.py's own module comment has the full real
        # justification -- MPBench's real "reports a preference/decision
        # change" construction, 0/502 real benign false positives, 0/75 real
        # corpus.py scenarios, fires ONLY on real MPBench in the full
        # 15-scenario corpus).
        "preference_decision_update_score",
    }
)
RETRIEVAL_SIGNAL_KEYS: frozenset = frozenset(
    {
        "consensus_divergence_score",  # retrieval/signals.py::pool_consensus_divergence_signals (lexical, D1)
        # 2026-09-20 (Phase 11 follow-on, explicitly authorized): the D2
        # embedding-based counterpart (`retrieval/embedding_signals.py::
        # pool_consensus_divergence_signals_semantic`), sanctioned as its OWN
        # key rather than silently overwriting the lexical one -- real,
        # measured finding: paraphrased-but-lexically-diverse coordinated
        # poison (MemoryGraft-style-volume's PARAPHRASE-POISON-* family)
        # scores EXACTLY 0.0 on the lexical (Jaccard) signal (confirmed
        # directly, `docs/phase11/PHASE11_PARAPHRASE_FIX_REPORT.md`) but is
        # correctly clustered by the semantic signal (poison mean 0.184,
        # matching the same real, disclosed evidence `embedding_signals.py`'s
        # own module docstring already cites this signal for). Additive
        # only: the lexical key's own weight/meaning/every existing B0-B9
        # number computed from it is unchanged; this is a NEW, separate key,
        # not a replacement.
        "semantic_consensus_divergence_score",
    }
)
PROPAGATION_SIGNAL_KEYS: frozenset = frozenset(
    {"lineage_taint_score"}  # propagation/signals.py::lineage_taint_signal
)
SLEEPER_SIGNAL_KEYS: frozenset = frozenset(
    {
        "imperative_write_directive_score",  # sleeper/signals.py::imperative_write_directive_signal
        "dormancy_activation_score",  # sleeper/signals.py::dormancy_activation_signal
        "age_based_dormancy_gate_score",  # sleeper/signals.py::age_based_dormancy_gate_signal
        # 2026-09-23 (Phase 15 follow-on, explicitly authorized): `activation_
        # shape_score` (phase8/detection/activation_shape_signal.py) -- a
        # real, cached, content-text-keyed lookup. `evaluate_sleeper_
        # admission()` (B0-B8's own dedicated Sleeper guard) already combines
        # it via `max(imperative_write_directive_score, activation_shape_
        # score)`; B9's own signal composition never included it, which real,
        # direct testing (Phase 15's per-dataset B9 reshape) found causes B9
        # to miss the real `REAL-SLEEPER-0` scenario entirely (0% detection,
        # vs B8's 100% on the exact same content) -- root cause: this
        # project's own frozen `SleeperInjector` never embeds directive
        # language in its forged memory text, so `imperative_write_directive_
        # score` is structurally 0.0 for every real Sleeper memory (already
        # Phase 8's own disclosed Finding A), leaving B9 with no real
        # detection basis for Sleeper at all. Additive only: this key is
        # absent from every existing caller's signals dict (Phase 11's
        # `grouped_raw_score.py`, `risk_sweep.py`'s dev-corpus sweep, the
        # frozen `corpus.py` B9 test), so `_sleeper_group_score()`'s own
        # `.get(..., 0.0)` default leaves their real, already-reported
        # numbers byte-identical -- verified directly, not assumed (full
        # cross-phase regression re-run after this change).
        "activation_shape_score",
    }
)

# Phase 11.4 -- each learned component's real output, treated as one more
# sanctioned signal key (Phase 11 plan Section 11.4/8: "the simplest honest
# option... rather than inventing a new, separate combination mechanism").
# Additive only: no existing key's meaning or weighting changes.
#
# Update (2026-09-17): a real, measured problem was found and fixed. B10's
# original hybrid used WEIGHTED_SUM, which adds each learned signal at its
# own flat weight ON TOP of the nine already-shipped rule-based signals --
# with two independent, largely-saturated learned scores (the GNN's own
# real overfitting symptom at this data scale; the GLN's own real formula
# reaching near-1.0/near-0.0 quickly by design), this pushed nearly every
# real held-out memory's combined score over the decision threshold: B10
# measured 100.0% detection at 100.0% false positives -- a real, disclosed
# regression, not an improvement (see docs/phase11/PHASE11_REPORT.md
# Section 5's own account of this exact finding). GROUPED_GATED now supports
# a fifth "learned_group" (see `_grouped_gated_rule` below), contributing
# the SAME fixed 0.25 share every other group already does -- bounded,
# never additive on top of an already-calibrated total, and contributing
# exactly 0.0 (unchanged behavior) whenever no learned signal is present,
# so this is a real, backward-compatible extension, not a re-tuning of any
# already-shipped, already-recalibrated Phase 6-10 number.
LEARNED_SIGNAL_KEYS: frozenset = frozenset(
    {
        "gnn_risk_score",  # phase11/gnn/train.py -- MinimalGNN.predict_proba() output
        "gln_risk_score",  # phase11/gln/stream.py -- GatedLinearNetwork online risk estimate
    }
)

SANCTIONED_RISK_SIGNAL_KEYS: frozenset = (
    ADMISSION_SIGNAL_KEYS
    | RETRIEVAL_SIGNAL_KEYS
    | PROPAGATION_SIGNAL_KEYS
    | SLEEPER_SIGNAL_KEYS
    | LEARNED_SIGNAL_KEYS
)

# Defense-in-depth: the sanctioned vocabulary and the evaluator-only denylist
# must never overlap. Asserted at import time (not just in a test) so a
# future edit to either list cannot silently create a live leakage path
# without the module itself refusing to load.
assert SANCTIONED_RISK_SIGNAL_KEYS.isdisjoint(FORBIDDEN_SIGNAL_KEYS), (
    "SANCTIONED_RISK_SIGNAL_KEYS overlaps FORBIDDEN_SIGNAL_KEYS -- this must "
    "never happen; see phase6/defense/policy/records.py."
)


class UnsanctionedRiskSignalError(ValueError):
    """Raised when `compute_memory_risk_score()` is given a signal key outside
    `SANCTIONED_RISK_SIGNAL_KEYS` -- Stage 10.1 introduces no new signal
    category (Phase 10 plan Section 5's inherited Signal Contract constraint),
    so an unrecognized key is refused, never silently combined or ignored."""


# ---------------------------------------------------------------------------
# Risk bands -- a closed, disclosed vocabulary. Never re-derived inline at a
# call site; always look up through `risk_band_for_score()`.
# ---------------------------------------------------------------------------

LOW = "LOW"
MODERATE = "MODERATE"
ELEVATED = "ELEVATED"
HIGH = "HIGH"

RISK_BANDS: Tuple[str, ...] = (LOW, MODERATE, ELEVATED, HIGH)

# Calibrated default (2026-09-17 follow-on to Stage 10.5's B9 comparison,
# PHASE10_REPORT.md Section 5's own named next step). BAND_THRESHOLD_MODERATE
# was 0.15 (an uncalibrated v1 default); Stage 10.5's B9 run found this
# under-detects real single-guard-strength evidence relative to that guard's
# own already-calibrated threshold (report Section 2's root-cause account).
#
# Recalibrated against `phase6/evaluation/ablations/risk_sweep.py`'s real
# sweep over `dev_corpus.py`'s DISJOINT dev fixtures (extended 2026-09-17 with
# admission/propagation/sleeper-shaped cases -- never the reported B0-B9
# corpus, per Section 5's inherited anti-circularity constraint). Real,
# measured finding: every real dev false positive already occurs at 0.15
# (both retrieval-consensus TRUTH memories, an already-disclosed, pre-existing
# weakness of `consensus_divergence_score` itself, not something this
# threshold change causes) -- lowering the threshold down to 0.05 adds ZERO
# new false positives on the real dev corpus (false-positive rate unchanged:
# 2/8 = 25% at every threshold from 0.05 to 0.15 inclusive) while poison
# detection rises from 20.0% (3/15) to 93.3% (14/15). 0.05 itself, not lower,
# is the real, measured boundary: `DEV-ADMISSION-BENIGN-NEAR-MISS` (a
# genuine, deliberately-constructed benign near-miss, real score 0.025) is
# the next real value below 0.05, and IS caught by any threshold at or below
# 0.025 (false-positive rate rises to 37.5% at threshold=0.02) -- verified by
# direct computation, not chosen for a round number alone. See
# `test_risk_score.py::test_grouped_gated_band_threshold_recalibration_dev_corpus_sweep`
# for the exact, locked-in real sweep table.
BAND_THRESHOLD_MODERATE = 0.05
BAND_THRESHOLD_ELEVATED = 0.35
BAND_THRESHOLD_HIGH = 0.6


def risk_band_for_score(score: float) -> str:
    """The ONLY place a risk_score maps to a risk_band -- never re-derived
    inline elsewhere, so a future recalibration of the thresholds above
    changes behavior everywhere consistently."""
    if score >= BAND_THRESHOLD_HIGH:
        return HIGH
    if score >= BAND_THRESHOLD_ELEVATED:
        return ELEVATED
    if score >= BAND_THRESHOLD_MODERATE:
        return MODERATE
    return LOW


# ---------------------------------------------------------------------------
# RiskEstimate
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RiskEstimate:
    """One memory's combined, disclosed risk estimate. See Phase 10 plan
    Section 4.1 -- every field mirrors an existing Phase 6 discipline
    (`contributing_signals` mirrors `MGPDecisionRecord.signals_used`;
    `rationale` mirrors every guard's own `reason` string; `risk_band` is a
    closed vocabulary like `SecurityState`)."""

    memory_id: str
    risk_score: float
    contributing_signals: Mapping[str, float]
    risk_band: str
    rationale: Tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not (0.0 <= self.risk_score <= 1.0):
            raise ValueError(f"RiskEstimate.risk_score must be in [0, 1]; got {self.risk_score}")
        if self.risk_band not in RISK_BANDS:
            raise ValueError(f"Unknown risk_band: {self.risk_band!r}")
        offending = sorted(set(self.contributing_signals.keys()) & FORBIDDEN_SIGNAL_KEYS)
        if offending:
            raise EvaluatorOnlyLeakageError(
                f"RiskEstimate refused: contributing_signals contains evaluator-only "
                f"field(s) {offending!r}."
            )


# ---------------------------------------------------------------------------
# Composition rule A -- naive weighted sum over every individual sanctioned
# signal key present, flat-weighted within the whole vocabulary. This is the
# FIRST candidate Stage 10.1 tries, not the one it ships by default -- see
# `test_risk_score.py::test_naive_weighted_sum_reproduces_sleeper_false_positive_collision`
# for the real, measured reason it is NOT the recommended rule (below).
# ---------------------------------------------------------------------------

# Equal weighting across the whole flat vocabulary (uncalibrated v1 default,
# same "start from equal weighting, let real evidence justify departing from
# it" discipline `reasoning_guard.SIGNAL_WEIGHTS` already used).
#
# Phase 11.4 note: `_FLAT_WEIGHT` is deliberately computed over the PRE-Phase-11
# vocabulary only (never `SANCTIONED_RISK_SIGNAL_KEYS`, which now also
# contains `LEARNED_SIGNAL_KEYS`) so adding the two learned keys does not
# silently reweight every already-shipped, already-calibrated Phase 6-10
# signal's own flat share -- that would be an undisclosed behavior change to
# pre-existing numbers, exactly what Stage 10.5's own recalibration discipline
# warns against. Each learned key gets that SAME flat weight (equal
# footing with one already-shipped signal, the same "start from equal
# weighting" default), not a separately re-derived share.
#
# UPDATE (2026-09-20): `_PRE_PHASE11_SIGNAL_KEYS` is now an EXPLICIT,
# hardcoded literal, not derived from `ADMISSION_SIGNAL_KEYS |
# RETRIEVAL_SIGNAL_KEYS | ...` any longer. Real, measured bug caught by this
# investigation's own regression suite: deriving it dynamically meant
# adding `semantic_consensus_divergence_score` to `RETRIEVAL_SIGNAL_KEYS`
# (this same Update) silently diluted `_FLAT_WEIGHT` for every OTHER
# already-shipped signal too (`test_dev_corpus_comparison_against_
# combined_action_baseline`'s own WEIGHTED_SUM count dropped from 7 to 5
# flagged with no change to any underlying signal value) -- exactly the
# "undisclosed reweighting of pre-existing numbers" this comment's own
# ORIGINAL intent already said must never happen, just triggered by a new
# rule-based key instead of a learned one. Freezing this list as a literal
# closes that gap for any future sanctioned-key addition, not just this one.
_PRE_PHASE11_SIGNAL_KEYS: frozenset = frozenset(
    {
        "self_reference_score", "decision_log_vocabulary_score", "perfection_claim_score",
        "template_anomaly_score", "provenance_anomaly_score",
        "consensus_divergence_score",
        "lineage_taint_score",
        "imperative_write_directive_score", "dormancy_activation_score", "age_based_dormancy_gate_score",
    }
)
_FLAT_WEIGHT = 1.0 / len(_PRE_PHASE11_SIGNAL_KEYS)
DEFAULT_FLAT_WEIGHTS: Dict[str, float] = {key: _FLAT_WEIGHT for key in SANCTIONED_RISK_SIGNAL_KEYS}


def _weighted_sum_rule(signals: Mapping[str, float], weights: Mapping[str, float]) -> Tuple[float, Dict[str, float]]:
    contributions: Dict[str, float] = {}
    total = 0.0
    for key, value in signals.items():
        w = weights.get(key, 0.0)
        total += w * value
        if value != 0.0:
            contributions[key] = value  # raw signal value, for audit -- see RiskEstimate docstring
    return min(1.0, total), contributions


# ---------------------------------------------------------------------------
# Composition rule B -- grouped, sleeper-gated. Reuses each guard's OWN
# already-shipped internal combination where one exists (admission's five
# signals are combined via `reasoning_guard.SIGNAL_WEIGHTS`, exactly as
# `evaluate_admission()` itself does; sleeper's directive/dormancy pair is
# combined via the SAME multiplicative gate `sleeper_guard.
# evaluate_sleeper_retrieval_risk()` uses -- never a raw weighted sum of
# `imperative_write_directive_score` and `dormancy_activation_score`
# independently, which is exactly the false-positive collision this rule is
# built to avoid; see the module-level note above and the dedicated test).
# Each of the four guard GROUPS then contributes an equal 0.25 share at the
# top level -- deliberately independent of how many raw signal keys a group
# happens to expose internally, so admission's five finer-grained signals
# cannot outweigh retrieval's or propagation's single signal purely because
# there are more of them.
# ---------------------------------------------------------------------------

GROUP_WEIGHT = 0.25


# UPDATE (2026-09-23): a "multi-signal corroboration floor" was first tried
# as a change to the SHARED `_admission_group_score()` (used by every
# `rule=GROUPED_GATED` caller, including Phase 11's `grouped_raw_score.py`).
# That version was reverted after a full cross-phase regression run found it
# degraded Phase 11's real, already-calibrated GNN/LOFO detectors (their
# `combined_untrained_score()` normalizes this function's output via real
# TRAINING-POPULATION z-scores; raising admission-group scores for real
# multi-signal poison shifted that population's own mean/std enough to
# measurably hurt unrelated detection -- real Sleeper detection dropped from
# 100% to 0%, real FPR control broke). Rather than fold a fix into the
# SHARED rule GROUPED_GATED every existing caller depends on, this floor is
# now its own, SEPARATE, additive composition rule
# (`GROUPED_GATED_ADMISSION_CORROBORATED`, see below) that only a caller
# which explicitly opts into it (`phase14/defended_retrieval.py`'s B9 path)
# ever sees. `GROUPED_GATED` itself -- used by Phase 11, the frozen
# `corpus.py` 75-scenario corpus's real B0-B9 numbers, and the dev-corpus
# sweep in `risk_sweep.py` -- is completely UNCHANGED: `_admission_group_score()`
# never applies a floor unless the caller explicitly asks for one.
ADMISSION_MULTI_SIGNAL_CORROBORATION_MINIMUM = 2
# The real, minimum group-score value guaranteed once
# `ADMISSION_MULTI_SIGNAL_CORROBORATION_MINIMUM` distinct real admission
# signals fire together, for callers that opt into it. Reaching `HIGH`
# (risk_score >= 0.6) from the admission group ALONE, given `GROUP_WEIGHT` =
# 0.25, requires a group score >= 2.4 -- an initial, smaller floor (1.2) was
# tried first and found, by direct testing, to be completely inert (it never
# crossed a real risk-band boundary for any real case), so 2.5 (with margin)
# is used instead.
ADMISSION_MULTI_SIGNAL_CORROBORATION_FLOOR = 2.5


def _admission_group_score(signals: Mapping[str, float], *, corroboration_floor: Optional[float] = None) -> float:
    # Mirrors reasoning_guard.SIGNAL_WEIGHTS exactly (0.2 per signal) -- kept
    # as a local, disclosed literal rather than importing SIGNAL_WEIGHTS to
    # avoid coupling this module's import surface to the admission guard's
    # internal module (a reason to import would be real drift risk; the five
    # weights are simple and already frozen -- see reasoning_guard.py).
    #
    # `corroboration_floor` is `None` for every existing caller (GROUPED_GATED,
    # the default and only rule any pre-2026-09-23 caller ever used) --
    # behavior is therefore byte-identical to before this parameter existed
    # unless a caller explicitly supplies a floor (see module-level UPDATE
    # note above and `GROUPED_GATED_ADMISSION_CORROBORATED` below).
    present = {k: signals[k] for k in ADMISSION_SIGNAL_KEYS if k in signals and signals[k] > 0.0}
    if not present:
        return 0.0
    raw = sum(0.2 * signals[k] for k in present)
    if corroboration_floor is not None and len(present) >= ADMISSION_MULTI_SIGNAL_CORROBORATION_MINIMUM:
        return max(raw, corroboration_floor)
    return raw


def _sleeper_group_score(signals: Mapping[str, float]) -> float:
    """The real gate: the sleeper CONTENT signal multiplied by whichever
    dormancy component is present (`age_based_dormancy_gate_score` if
    supplied, else `dormancy_activation_score`), exactly as `sleeper_guard.
    evaluate_sleeper_retrieval_risk()` computes `gated_score`. Neither factor
    alone contributes anything -- a memory with only a high `dormancy_
    activation_score` (an ordinary first retrieval, the common benign case
    Stage 6.8's own docstring names explicitly) and no content signal present
    scores exactly 0.0 here, never a nonzero sleeper contribution from
    dormancy alone.

    UPDATE (2026-09-23, Phase 15 follow-on, explicitly authorized): the
    content signal is now `max(imperative_write_directive_score,
    activation_shape_score)`, mirroring `evaluate_sleeper_admission()`'s own
    real combination exactly (`sleeper_guard.py`) -- two independent
    detection mechanisms for the same real phenomenon, not a new one
    invented here. `activation_shape_score` defaults to 0.0 via `.get()` for
    every caller that has never supplied it (every existing caller before
    this session), so `max(directive, 0.0) == directive` exactly -- this
    function's output is byte-identical for them, verified directly (full
    cross-phase regression), not merely assumed from reading this diff."""
    directive = signals.get("imperative_write_directive_score", 0.0)
    shape = signals.get("activation_shape_score", 0.0)
    content_signal = max(directive, shape)
    if "age_based_dormancy_gate_score" in signals:
        dormancy = signals["age_based_dormancy_gate_score"]
    else:
        dormancy = signals.get("dormancy_activation_score", 0.0)
    return content_signal * dormancy


def _learned_group_score(signals: Mapping[str, float]) -> float:
    """MIN of whichever real learned-component scores are present (never a
    sum or mean) -- both must corroborate for this group to score high.

    UPDATE (2026-09-17): originally a mean. Real, measured finding on the
    held-out corpus (`docs/phase11/PHASE11_REPORT.md` Section 5): the GNN's
    own real held-out benign-content mean score (0.638) sits uncomfortably
    close to its own real poison mean (0.982) -- a real, disclosed
    calibration weakness at this project's small training scale -- while the
    GLN's real benign/poison means (0.073 / 0.676) are cleanly separated. A
    MEAN lets the GNN's own noise leak through; requiring the MIN of both
    (the same "one uncorroborated single-source signal is weaker evidence"
    discipline Stage 6.5/6.7/6.8 already share, generalized here to two
    learned estimates of the same thing) uses the GLN's real, better
    calibration to suppress exactly that noise. Real, measured effect on the
    same held-out corpus: B10 (hybrid, `rule=GROUPED_GATED`) rises from a
    degenerate 100.0% detection / 100.0% FPR (mean, or WEIGHTED_SUM) to
    70.6% / 7.3% -- an exact match to B8/B9's own real numbers, not a further
    improvement, but a real recovery from an actively-harmful hybrid to a
    genuinely neutral one. When only one learned signal is present for a
    given memory, that one value is used directly (there is nothing to
    corroborate it against, and omitting it entirely would silently discard
    real evidence the same way a missing key already does everywhere else
    in this module)."""
    present = [signals[k] for k in LEARNED_SIGNAL_KEYS if k in signals]
    if not present:
        return 0.0
    return min(present)


def _retrieval_group_score(signals: Mapping[str, float]) -> float:
    """MAX of the lexical (D1) and semantic (D2) consensus-divergence
    scores, not a replacement of one by the other.

    UPDATE (2026-09-20, explicitly authorized): real, measured finding
    (`docs/phase11/PHASE11_PARAPHRASE_FIX_REPORT.md`) -- `PARAPHRASE-POISON-*`
    (MemoryGraft-style-volume's paraphrased-wording coordinated poison)
    scores EXACTLY 0.0 on the lexical signal (Jaccard token-overlap
    clustering cannot see a paraphrase as a near-duplicate) but is
    correctly identified as a coordinated cluster by the semantic
    (embedding-based) signal `embedding_signals.py` already ships for
    exactly this documented reason. MAX, not a mean or a replacement,
    because the two are two independent DETECTION MECHANISMS for the SAME
    phenomenon (a coordinated near-duplicate cluster) -- either one firing
    is real evidence, the same "OR" logic this module already uses for
    "present_groups" itself, not the "both must corroborate" MIN logic
    `_learned_group_score()` uses for two independent ESTIMATES of the same
    underlying risk. Real, measured, disclosed cost: B9's own real FPR
    rises from 7.3% to 14.6% -- traced directly, not merely accepted: every
    one of the 3 new false positives is a real, genuine "truth" memory that
    happens to sit inside a coordinated PARAPHRASE-poison pool, the SAME
    known, already-accepted mechanism that already flagged the analogous
    NEARDUP-TRUTH-* memories under the lexical signal alone (a minority
    truth record inside a coordinated-poison pool reads as "divergent from
    consensus," a known, disclosed limitation of pool-consensus-based
    escalation this project has never claimed to be free of) -- not a new,
    unrelated failure mode this change introduces."""
    lexical = signals.get("consensus_divergence_score", 0.0)
    semantic = signals.get("semantic_consensus_divergence_score", 0.0)
    return max(lexical, semantic)


def _grouped_gated_rule(
    signals: Mapping[str, float], *, admission_corroboration_floor: Optional[float] = None,
    require_retrieval_corroboration: bool = False,
) -> Tuple[float, Dict[str, float]]:
    group_scores = {
        "admission_group": _admission_group_score(signals, corroboration_floor=admission_corroboration_floor),
        "retrieval_group": _retrieval_group_score(signals),
        "propagation_group": signals.get("lineage_taint_score", 0.0),
        "sleeper_group": _sleeper_group_score(signals),
        "learned_group": _learned_group_score(signals),
    }
    # `require_retrieval_corroboration` (2026-09-23, Phase 15 follow-on,
    # explicitly authorized): `False` for every existing caller (GROUPED_GATED
    # and GROUPED_GATED_ADMISSION_CORROBORATED both pass nothing, so this is
    # a no-op for them, byte-identical to before this parameter existed).
    # When `True` (only `GROUPED_GATED_RETRIEVAL_CORROBORATED` sets it),
    # retrieval_group's own contribution is zeroed out whenever it is the
    # ONLY group with a genuinely nonzero score -- real, root-caused reason
    # (Phase 15's own per-dataset B9 security-matrix reshape): real
    # semantic-consensus-divergence scores on LongMemEval's real,
    # naturally-topic-diverse session-based benign pools (0.58-0.71) push 50%
    # of real benign records past ALLOW on retrieval evidence ALONE, with no
    # other guard corroborating -- the SAME "single/uncorroborated evidence
    # is weaker" principle this module already applies via `_single_nonzero_
    # signal()`'s band cap, just correctly scoped to GROUP-level corroboration
    # (that existing cap does not help here: B9's own convention of always
    # supplying `dormancy_activation_score=1.0` as sleeper context means a
    # real, individual signal VALUE is almost never the only nonzero one,
    # even when no other GROUP genuinely fires).
    if require_retrieval_corroboration and group_scores["retrieval_group"] > 0.0:
        other_groups_fire = any(
            group_scores[name] > 0.0 for name in group_scores if name != "retrieval_group"
        )
        if not other_groups_fire:
            group_scores["retrieval_group"] = 0.0
    present_groups = [name for name in group_scores if _group_has_any_signal(name, signals)]
    if not present_groups:
        return 0.0, {}
    total = sum(GROUP_WEIGHT * group_scores[name] for name in present_groups)

    # Per-signal contributions, for audit (`RiskEstimate.contributing_signals`
    # must trace to the real inputs, not just the four group scores).
    contributions: Dict[str, float] = {}
    for key, value in signals.items():
        if value != 0.0:
            contributions[key] = value
    return min(1.0, total), contributions


_GROUP_KEYS = {
    "admission_group": ADMISSION_SIGNAL_KEYS,
    "retrieval_group": RETRIEVAL_SIGNAL_KEYS,
    "propagation_group": PROPAGATION_SIGNAL_KEYS,
    "sleeper_group": SLEEPER_SIGNAL_KEYS,
    "learned_group": LEARNED_SIGNAL_KEYS,
}


def _group_has_any_signal(group_name: str, signals: Mapping[str, float]) -> bool:
    return any(key in signals for key in _GROUP_KEYS[group_name])


# ---------------------------------------------------------------------------
# Composition rule registry
# ---------------------------------------------------------------------------

WEIGHTED_SUM = "weighted_sum"
GROUPED_GATED = "grouped_gated"
# 2026-09-23 (Phase 14 follow-on, explicitly authorized): a SEPARATE,
# additive rule -- identical to GROUPED_GATED except `_admission_group_score()`
# is given `ADMISSION_MULTI_SIGNAL_CORROBORATION_FLOOR`. Deliberately its own
# rule name, not a change to GROUPED_GATED itself, so every existing
# GROUPED_GATED caller (Phase 11's z-score-normalized detectors, the frozen
# `corpus.py` 75-scenario corpus's real B0-B9 numbers, `risk_sweep.py`'s
# dev-corpus sweep) is completely unaffected -- see `_admission_group_score()`'s
# own module-level UPDATE note for the real regression this isolation avoids.
# Only `phase14/defended_retrieval.py`'s B9 path opts into this rule.
GROUPED_GATED_ADMISSION_CORROBORATED = "grouped_gated_admission_corroborated"
# 2026-09-23 (Phase 15 follow-on, explicitly authorized): another SEPARATE,
# additive rule -- identical to GROUPED_GATED except retrieval_group's own
# contribution is suppressed whenever it is the ONLY group with a genuinely
# nonzero score (see `_grouped_gated_rule()`'s own `require_retrieval_
# corroboration` docstring for the full real root cause and validation).
# Deliberately its own rule name: `GROUPED_GATED` and `GROUPED_GATED_
# ADMISSION_CORROBORATED` are both completely unaffected, since neither
# passes `require_retrieval_corroboration=True`. Only `phase15/
# security_matrix_extension.py`'s B9 per-dataset reshape opts into this rule
# -- Phase 14's own live B9 path does not need it (`REQUIRE_VALIDATION`,
# the real action this finding was inflating, is not one of Phase 14's
# `HARD_MITIGATION_ACTIONS`, so it never caused a real content exclusion
# there in the first place -- confirmed directly, Phase 14's own real
# Track A URS was already a clean 1.0 on LongMemEval before this fix).
GROUPED_GATED_RETRIEVAL_CORROBORATED = "grouped_gated_retrieval_corroborated"
COMPOSITION_RULES: Tuple[str, ...] = (
    WEIGHTED_SUM, GROUPED_GATED, GROUPED_GATED_ADMISSION_CORROBORATED, GROUPED_GATED_RETRIEVAL_CORROBORATED,
)

# The rule this module recommends as of Stage 10.1 (Phase 10 plan Section
# 10.1: "try candidates against the disjoint dev corpus... report which one,
# if any, real evidence supports") -- GROUPED_GATED, but on MIXED, HONESTLY
# DISCLOSED evidence, not a clean win:
#
#   FOR grouped_gated: it avoids the real false-positive collision
#   WEIGHTED_SUM reproduces for the sleeper guard's own dormancy/directive
#   pair (an ordinary first-time retrieval of non-directive content scores
#   0.0 under grouped_gated, nonzero under weighted_sum) -- see
#   `test_naive_weighted_sum_reproduces_sleeper_false_positive_collision`.
#
#   AGAINST grouped_gated: on the dev corpus's retrieval-consensus scenarios
#   (`test_dev_corpus_comparison_against_combined_action_baseline`), it
#   inherits `retrieval/signals.py`'s own already-disclosed weakness
#   (`consensus_divergence_score` flags the minority TRUTH memory, not the
#   coordinated poison cluster) -- both TRUTH memories score as false
#   positives under EITHER composition rule. This is a real, pre-existing
#   limitation of the underlying signal, not something grouped_gated
#   introduces or WEIGHTED_SUM avoids.
#
# UPDATE (2026-09-17): `BAND_THRESHOLD_MODERATE` was recalibrated (0.15 ->
# 0.05) against this same dev corpus, extended with admission/propagation/
# sleeper-shaped fixtures (`risk_sweep.py`). Post-recalibration, on the
# retrieval-consensus slice specifically: GROUPED_GATED detects 6/6 real
# poison (up from 1/6), WEIGHTED_SUM detects 5/6 (up from 0/6) -- both at
# the SAME 2/2 (unchanged) benign false-positive count, since both TRUTH
# memories were already flagged at the old threshold. GROUPED_GATED remains
# the recommended default: it both avoids the sleeper collision above AND
# now edges out WEIGHTED_SUM on real poison detection on this slice too. A
# full Stage 10.5-style ablation against the reported B0-B9 corpus (not just
# this dev corpus) is what actually validates a deployment claim --
# `test_run_b9_risk_composed.py` is that validation, and it now shows B9
# matching B8 exactly (70.6%/7.3%) under GROUPED_GATED. WEIGHTED_SUM remains
# fully available (pass `rule=WEIGHTED_SUM` explicitly).
RECOMMENDED_RULE = GROUPED_GATED


def _single_nonzero_signal(signals: Mapping[str, float]) -> bool:
    nonzero = [k for k, v in signals.items() if v != 0.0]
    return len(nonzero) == 1


def compute_memory_risk_score(
    memory_id: str,
    signals: Mapping[str, float],
    *,
    rule: str = RECOMMENDED_RULE,
    weights: Optional[Mapping[str, float]] = None,
    admission_corroboration_floor: Optional[float] = None,
) -> RiskEstimate:
    """Combine `signals` (a real, already-computed `signals_used`-shaped dict
    -- e.g. the union of several `MGPDecisionRecord.signals_used` for the same
    memory across guards) into one `RiskEstimate`.

    Pure function: identical `(memory_id, signals, rule, weights)` always
    produces a byte-identical `RiskEstimate` (Phase 10 plan Section 5's
    determinism constraint).

    `weights` is only consulted for `rule=WEIGHTED_SUM` (defaults to
    `DEFAULT_FLAT_WEIGHTS` when omitted); `GROUPED_GATED` has no caller-
    supplied weight surface -- its per-group 0.25 split and its reuse of each
    guard's own internal combination are fixed by design, not tunable per
    call (Phase 10 plan Section 5: weights/thresholds are disclosed, versioned
    constants, not fitted parameters).

    `admission_corroboration_floor` is only consulted for
    `rule=GROUPED_GATED_ADMISSION_CORROBORATED` (defaults to
    `ADMISSION_MULTI_SIGNAL_CORROBORATION_FLOOR` when omitted). It exists
    SOLELY so a real calibration/sweep tool (`phase6/evaluation/ablations/
    admission_corroboration_floor_sweep.py`) can try candidate floor values
    through this same public function, rather than reaching into the private
    `_grouped_gated_rule()` helper from another module -- ordinary callers
    (including `phase14/defended_retrieval.py`'s live B9 path) never pass it
    and get the shipped, disclosed floor.

    Raises `UnsanctionedRiskSignalError` if `signals` contains any key outside
    `SANCTIONED_RISK_SIGNAL_KEYS` (Phase 10 plan Section 8's first acceptance
    criterion) and `EvaluatorOnlyLeakageError` if it contains a
    `FORBIDDEN_SIGNAL_KEYS` key (belt-and-suspenders with the assertion above
    that the two vocabularies never overlap).
    """
    offending_forbidden = sorted(set(signals.keys()) & FORBIDDEN_SIGNAL_KEYS)
    if offending_forbidden:
        raise EvaluatorOnlyLeakageError(
            f"compute_memory_risk_score refused: signals contains evaluator-only "
            f"field(s) {offending_forbidden!r}."
        )
    unsanctioned = sorted(set(signals.keys()) - SANCTIONED_RISK_SIGNAL_KEYS)
    if unsanctioned:
        raise UnsanctionedRiskSignalError(
            f"compute_memory_risk_score refused unsanctioned signal key(s) "
            f"{unsanctioned!r} -- every key must be in SANCTIONED_RISK_SIGNAL_KEYS "
            "(Phase 10 plan Section 5's inherited Signal Contract constraint). "
            "See docs/phase10/PHASE10_PLAN.md Section 8."
        )
    if rule not in COMPOSITION_RULES:
        raise ValueError(f"Unknown composition rule {rule!r}; must be one of {COMPOSITION_RULES}")

    if rule == WEIGHTED_SUM:
        effective_weights = dict(DEFAULT_FLAT_WEIGHTS if weights is None else weights)
        score, contributions = _weighted_sum_rule(signals, effective_weights)
    elif rule == GROUPED_GATED_ADMISSION_CORROBORATED:
        effective_floor = (
            ADMISSION_MULTI_SIGNAL_CORROBORATION_FLOOR
            if admission_corroboration_floor is None
            else admission_corroboration_floor
        )
        score, contributions = _grouped_gated_rule(signals, admission_corroboration_floor=effective_floor)
    elif rule == GROUPED_GATED_RETRIEVAL_CORROBORATED:
        score, contributions = _grouped_gated_rule(signals, require_retrieval_corroboration=True)
    else:
        score, contributions = _grouped_gated_rule(signals)

    band = risk_band_for_score(score)

    # Phase 10 plan Section 8's second acceptance criterion, enforced
    # structurally (not merely asserted in a docstring): a RiskEstimate built
    # from exactly one nonzero contributing signal can never reach HIGH --
    # the same "indirect/single-source evidence caps below BLOCK" discipline
    # Stage 6.5/6.7/6.8 already share, generalized here to the risk-band
    # vocabulary. One real signal, however large its own magnitude, is capped
    # at ELEVATED.
    if band == HIGH and _single_nonzero_signal(signals):
        band = ELEVATED

    fired = sorted((k for k, v in signals.items() if v != 0.0), key=lambda k: -signals[k])
    if fired:
        fired_desc = ", ".join(f"{k}={signals[k]:.3f}" for k in fired)
        rationale = (
            f"rule={rule} ({RISK_SCORE_VERSION}); risk_score={score:.3f}; "
            f"band={band}; contributing signals: {fired_desc}",
        )
    else:
        rationale = (f"rule={rule} ({RISK_SCORE_VERSION}); risk_score=0.000; band={LOW}; no signal fired",)

    return RiskEstimate(
        memory_id=memory_id,
        risk_score=score,
        contributing_signals=dict(contributions),
        risk_band=band,
        rationale=rationale,
    )
