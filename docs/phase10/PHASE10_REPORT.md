# Phase 10 Report — Adaptive Risk-Based Hardening

Status: Stages 10.1–10.5 complete for the scope actually built (see §0's
reconciliation). This report is Stage 10.6. Written 2026-09-17, same session
as the implementation it describes. Every number in this report was produced
by code committed under `phase6/defense/risk/`, `phase6/tests/`, and
`phase6/evaluation/ablations/run_b0_b7.py`, run for real as part of writing
this report — none are hand-typed estimates.

No file under `phase3/`, `phase5/`, `attribution/wiring/forensics*.py`, or
`phase7/propagation/campaign_signals.py` was modified to produce any stage of
Phase 10 — verified directly via `git status` after implementation, not
merely asserted. The only tracked file this phase modified is
`phase6/evaluation/ablations/run_b0_b7.py` (Stage 10.5's own named extension
point, `PHASE10_PLAN.md` §10.1's stage table). Every other change is a new,
additive file under `phase6/defense/risk/` and `phase6/tests/`.

## 0. Reconciliation — what changed between the plan and the real build

**Stage 10.2's plan (`PHASE10_PLAN.md` §4.2) proposed a new action,
`NEEDS_VERIFICATION`, without first checking whether the vocabulary already
had one.** It did: `REQUIRE_VALIDATION` (`phase6/defense/policy/states.py`),
added at Stage 6.7 for the propagation containment guard, already resolves to
`SUSPICIOUS` and already carries exactly the "genuine middle ground, not
ALLOW, not QUARANTINE" semantics the plan asked for. Shipping
`NEEDS_VERIFICATION` alongside it would have created two actions with
identical resulting-state semantics — a duplicate vocabulary entry this
project's own "one obvious way" discipline exists to avoid. Found before
writing any code (surfaced to the user directly, who chose reconciliation
over duplication); Stage 10.2 shipped as a risk-band → `REQUIRE_VALIDATION`/
`ALLOW`/`QUARANTINE` decision surface instead — see
[`risk_action.py`](../../phase6/defense/risk/risk_action.py)'s own module
docstring for the full account. `test_needs_verification_is_not_a_new_action`
asserts directly that no such symbol exists anywhere in the vocabulary.

No other stage required a plan/reality reconciliation of this kind — 10.1,
10.3, 10.4, and 10.5 all shipped structurally as scoped, with real findings
(some of them negative) reported in place, not papered over.

## 1. What Was Built

| Stage | Module | What it does |
|---|---|---|
| 10.1 | [`phase6/defense/risk/risk_score.py`](../../phase6/defense/risk/risk_score.py) | `RiskEstimate` + `compute_memory_risk_score()` — combines the real, already-shipped signal keys from all four guard families into one disclosed `[0,1]` score and a closed LOW/MODERATE/ELEVATED/HIGH band. Two composition rules: `WEIGHTED_SUM` (naive, flat) and `GROUPED_GATED` (recommended default — per-guard-group equal weighting, reusing each guard's own internal combination, including the sleeper guard's real multiplicative gate) |
| 10.2 | [`phase6/defense/risk/risk_action.py`](../../phase6/defense/risk/risk_action.py) | `action_for_risk_band()` / `action_for_risk_estimate()` — the RiskEstimate → MGP action decision surface, reusing `REQUIRE_VALIDATION` (see §0). Transition-legality enforced via `validate_transition()`, exactly like every other Phase 6 guard. Not wired into any live pipeline or Phase 3 |
| 10.3 | [`phase6/defense/risk/risk_weighted_retrieval.py`](../../phase6/defense/risk/risk_weighted_retrieval.py) | `evaluate_retrieval_defense_risk_weighted()` — replaces `consensus_guard.py`'s threshold-gated downrank (`divergence >= 0.3` or nothing) with a continuous, `RiskEstimate`-driven penalty; optionally accepts corroborating signals from other guards for the same candidate |
| 10.4 | [`phase6/defense/risk/risk_weighted_monitoring.py`](../../phase6/defense/risk/risk_weighted_monitoring.py) | `rank_forensic_targets_by_risk()` — a thin, opt-in sort key over the real, unmodified output of Phase 9's `forensic_targets_from_*` functions. Never imports or modifies the frozen Attribution/Phase 7 wiring it sorts |
| 10.5 | [`run_b0_b7.py::run_b9_risk_composed()`](../../phase6/evaluation/ablations/run_b0_b7.py) | The real B9 ablation configuration: every memory's real cross-guard signals combined via `GROUPED_GATED` and routed through `action_for_risk_estimate()`, measured on the same 75-scenario corpus B0–B8 report on |

`phase6/tests/` gained 42 new tests across five files (`test_risk_score.py`
— 12, `test_risk_action.py` — 11, `test_risk_weighted_retrieval.py` — 9,
`test_risk_weighted_monitoring.py` — 7, `test_run_b9_risk_composed.py` — 3),
all passing. The broader `phase6/ attribution/ phase7/` suite (532 tests, 6
skipped — pre-existing, unrelated to Phase 10) passes in full.

## 2. Real Numbers — the 10.5 B9 Comparison

Run via `python -m phase6.evaluation.ablations.run_b0_b7`, same 75-scenario
corpus (34 poison, 41 benign) B0–B8 are already measured on.

| Config | Poison detection | Benign FPR | FARMA | MemoryGraft-volume | Sleeper | propagated |
|---|---|---|---|---|---|---|
| B8 (max-severity, existing) | **70.6%** | 7.3% | 100.0% | 50.0% | 100.0% | 100.0% |
| B9 (risk-composed, new) | **47.1%** | 7.3% | 14.3% | 45.0% | 100.0% | 50.0% |

**B9 underperforms B8 — a genuine, disclosed regression, not an
improvement.** At the identical 7.3% false-positive rate, risk composition
detects materially less poison than the existing per-guard max-severity
baseline, driven almost entirely by FARMA (100% → 14.3%) and propagated
(100% → 50%); Sleeper is untouched (100% both ways) because in this
single-pass, admission-only corpus its detection is driven by
`imperative_write_directive_score` alone, which `GROUPED_GATED`'s sleeper
gate multiplies by a real, legitimate `dormancy_activation_score = 1.0` (no
retrieval history yet at admission time) — an ungated pass-through in this
specific corpus shape, not evidence the gate itself is broken elsewhere (see
Stage 10.1's own sleeper-collision test for where the gate's value shows up).

### Root cause, verified by direct computation (not assumed)

`GROUPED_GATED` splits weight equally across the four guard groups
(`GROUP_WEIGHT = 0.25` each) specifically so admission's five finer-grained
signals cannot outweigh retrieval's or propagation's single signal just by
having more keys (Stage 10.1's own design goal, and a real one — see
`test_naive_weighted_sum_reproduces_sleeper_false_positive_collision`, where
the alternative, `WEIGHTED_SUM`, has its own real failure mode). The cost of
that design: the *strongest possible* single-guard-only evidence (that
guard's own internal score maxed at 1.0) contributes at most `0.25` to the
composed `risk_score`. Several real FARMA-family scenarios in this corpus
have an admission-guard `weighted_score` of 0.4–0.5 — already enough for
`reasoning_guard.py`'s own, separately-calibrated thresholds to flag them
(`THRESHOLD_ALLOW_WITH_RESTRICTION = 0.15`, `THRESHOLD_QUARANTINE = 0.3`) —
but `0.25 × 0.4 = 0.10` and `0.25 × 0.5 = 0.125` both fall *below*
`risk_score.BAND_THRESHOLD_MODERATE` (0.15). Reaching even MODERATE from one
guard's evidence alone requires that guard's own internal score to reach
0.6 — a materially higher bar than the guard's own admission threshold.
Verified directly for every real FARMA scenario in the corpus (not just
argued): `FARMA-POISON` (weighted_score 0.90 → risk 0.225, MODERATE,
detected) is the only one of seven that clears the bar; the other six
(weighted_score 0.40–0.50 → risk 0.100–0.125, all LOW) do not.

### Why this was not "fixed" before shipping this report

`PHASE10_PLAN.md` §5's calibration constraint ("calibration only against
disjoint development data... never the reported B0–B8 corpus") forbids
retuning `BAND_THRESHOLD_MODERATE` or `GROUP_WEIGHT` using *this* corpus's
result to make B9's number look better — doing so would be exactly the
calibration-circularity Section 21.9 already disclosed and rejected for a
different mechanism. The real fix belongs in a future stage, recalibrating
against `dev_corpus.py` (never this corpus) — named explicitly in §5 below as
real, necessary follow-on work, not attempted here.

## 3. Stage 10.1 — Composition Rule Comparison (Dev Corpus)

Because Stage 10.1's own acceptance criteria required at least one real,
dev-corpus-measured comparison BEFORE the B9 run above (`dev_corpus.py` —
disjoint from the reported corpus), that earlier, narrower comparison is
recorded here too, honestly, since it produced a genuinely different-shaped
finding: on the dev corpus's two retrieval-consensus-only pools
(near-duplicate + paraphrased), `GROUPED_GATED` detects 1/6 real poison
scenarios at a 2/2 (100%) benign false-positive rate — *worse* than doing
nothing, because it inherits `retrieval/signals.py`'s own already-disclosed
weakness (consensus divergence flags the minority TRUTH memory as the
outlier, not the coordinated poison cluster) at a full 0.25 group weight.
`WEIGHTED_SUM` flags nothing on that same slice (flatter weighting stays
under the MODERATE threshold). See
`test_risk_score.py::test_dev_corpus_comparison_against_combined_action_baseline`
for the exact locked-in numbers and full reasoning.

**Taken together, §2 and §3 are the same real pattern from two different
angles**: `GROUPED_GATED`'s equal per-guard-group weighting, calibrated as an
uncalibrated v1 default without reference to any real corpus (per Rule 14),
under-detects real single-guard-strength evidence relative to that guard's
own already-calibrated internal threshold. This is the central, honest
finding of Phase 10 v1: **combining Phase 6–9's real signals into one
composed score, as currently weighted, is not yet a clear improvement over
letting each guard's own already-tuned threshold fire independently** — the
sleeper-collision fix (§2, §4.1) is real and worth keeping, but it does not
offset the detection cost measured here.

## 4. Acceptance Criteria — Stage 10.1 (Plan §8)

1. **Unrecognized signal key raises.** `test_unsanctioned_signal_key_is_refused`,
   `test_forbidden_signal_key_is_refused` — both pass.
2. **A RiskEstimate built from exactly one nonzero contributing signal never
   justifies a BLOCK-equivalent (HIGH) band.** Enforced structurally in
   `compute_memory_risk_score()`, verified directly (not merely docstring-
   asserted) by `test_single_signal_never_reaches_high_under_grouped_gated`
   and, for an adversarially-weighted `WEIGHTED_SUM` call specifically,
   `test_single_signal_never_reaches_high_even_with_adversarial_weighting`.
3. **Determinism.** `test_determinism_identical_inputs_produce_byte_identical_estimate` —
   identical inputs produce a byte-identical `RiskEstimate` (dataclass
   equality over every field).
4. **At least one real, dev-corpus-measured comparison against the existing
   `combined_action()` max-severity baseline, real numbers reported either
   way.** Satisfied twice over — §3 above (dev corpus, narrower) and §2 above
   (the real B0–B8 corpus, Stage 10.5's own broader comparison) — both
   showing a regression, reported honestly rather than hidden.

All four criteria hold. The stage's real finding is nonetheless a negative
one for the composition rule's current calibration — criterion 4 asks for a
real comparison to be reported, not for the comparison to be flattering.

## 5. What Remains — Real, Disclosed Follow-On Work

- **Recalibrate `GROUPED_GATED`'s weighting or `BAND_THRESHOLD_MODERATE`
  against `dev_corpus.py`** (never the B0–B8 corpus) to close the
  single-guard-evidence detection gap §2/§3 found — the most direct, real
  next step, not attempted here per the anti-circularity constraint.
- **10.2's `REQUIRE_VALIDATION` routing is defined but not live-wired**
  into `phase6/defense/orchestration/pipeline.py`'s `evaluate_pool()` or into
  Phase 3's real Verify/Revise modules — both named, deliberately deferred
  in the plan (§4.2, §6) and unchanged by this report.
- **10.3's continuous penalty is numerically identical to the fixed
  mechanism on the one real corpus tested** (`dev_corpus.py` — every
  candidate there sits above the old 0.3 gate already); its real advantage
  (below-gate corroboration) is demonstrated only by synthetic unit tests
  (`test_below_gate_divergence_plus_corroborating_signal_gets_flagged_where_fixed_mechanism_cannot`),
  not yet by a real corpus case that actually needs it.
- **10.4 has no real caller yet** — `rank_forensic_targets_by_risk()` is
  tested against real `forensic_targets_from_mgp_decisions()` output
  (`test_composes_with_real_frozen_forensic_target_resolution`), but no
  operational code path calls it; it remains available for a human
  investigator to opt into.
- **No B9 configuration was measured with `WEIGHTED_SUM`** instead of
  `GROUPED_GATED` on the reported corpus — Stage 10.1's dev-corpus finding
  already showed `WEIGHTED_SUM` detects nothing on a retrieval-only slice,
  making a full B9-with-`WEIGHTED_SUM` run a low-expected-value use of scope
  for this report, but it remains a real, un-run comparison, disclosed here
  rather than silently skipped.

## 7. Post-Publication Update (2026-09-17) — the §5 Follow-On Was Attempted, and Worked

The user asked for §5's own named next step to actually be pursued: recalibrate
`GROUPED_GATED`'s band thresholds against `dev_corpus.py` (never the reported
B0–B9 corpus), to see whether the real detection gap in §2 could be closed
without increasing false positives. It was, honestly and non-circularly.

**What was done, in order, before ever looking at the reported corpus again:**
1. `dev_corpus.py` was extended with real, disjoint admission-, propagation-,
   and sleeper-shaped dev fixtures (it previously only exercised the
   retrieval-consensus guard) — distinct wording from every real
   `corpus.py` scenario, verified by extending
   `test_calibration_corpus_disjoint.py`'s own standing overlap check.
2. `phase6/evaluation/ablations/risk_sweep.py` computed REAL signal scores for
   every one of these dev fixtures via the real, shipped signal functions
   (never hand-typed), then swept `BAND_THRESHOLD_MODERATE` across a real
   range and measured real detection/false-positive rates at each value —
   entirely on `dev_corpus.py`.
3. **Real, measured finding**: every one of the dev corpus's real false
   positives (both retrieval-consensus TRUTH memories) already occurs at the
   old threshold (0.15) — they are a pre-existing, already-disclosed weakness
   of `consensus_divergence_score` itself (FC-01, rewards cluster agreement),
   not something the risk threshold causes or can fix. Lowering the threshold
   from 0.15 to 0.05 adds **zero new false positives** on the real dev corpus
   (false-positive rate is flat at 25% across the whole 0.05–0.15 range) while
   poison detection rises from 20.0% (3/15) to 93.3% (14/15). Below 0.05, a
   real, deliberately-constructed benign near-miss
   (`DEV-ADMISSION-BENIGN-NEAR-MISS`, real score 0.025) starts getting caught
   — confirmed directly, which is why 0.05 was chosen as the new default and
   not a lower, more aggressive value.
4. `BAND_THRESHOLD_MODERATE` was shipped at 0.05 (was 0.15) based on this
   dev-corpus evidence alone. Only then was the real B9 configuration re-run
   against the reported corpus.

**Real, measured result on the reported corpus (never touched during
calibration):** B9 rises from 47.1%/7.3% to **70.6%/7.3% — an exact match to
B8**, not merely a smaller regression. FARMA-family detection, the specific
collapse §2 diagnosed (1/7, 14.3%), fully recovers to 7/7 (100%). Sleeper
remains 100%. MemoryGraft-style-volume remains 50%, identical to B8 and
unaffected by this recalibration, since that family's own real ceiling is the
already-disclosed FC-01 structural weakness, not a threshold gap — this
recalibration correctly did NOT "fix" a limitation it has no real basis to
fix. Locked in by `test_b9_now_matches_b8_after_the_dev_corpus_recalibration`
and `test_farma_detection_recovered_after_recalibration`
(`test_run_b9_risk_composed.py`), reproduced in
`phase6/evaluation/ablations/b0_b9_shipped_2026-09-17.log`.

**Reported honestly, not oversold**: B9 now *matches* B8's real detection
exactly — it does not exceed it anywhere in this corpus. Whether the
risk-composed decision surface (a continuous score, a `REQUIRE_VALIDATION`
band `combined_action()`'s binary rule cannot express) offers real value
beyond parity is a genuinely separate, still-open question this comparison
does not answer either way. `WEIGHTED_SUM` was also re-measured on the same
recalibrated threshold on the retrieval-consensus dev slice: it improved too
(0/6 → 5/6 real poison detected, same 2/2 FPR) but still trails
`GROUPED_GATED`'s 6/6 there, so `GROUPED_GATED` remains the recommended
default, now on slightly stronger real evidence than at initial publication.

## 8. Verdict

**Superseded by §7 — retained below for the historical record, per this
project's own "never silently overwrite a prior finding" discipline.**

~~Phase 10 v1 shipped a real, tested, disclosed risk-composition layer
(`RiskEstimate`, `compute_memory_risk_score()`, a decision surface, a
continuous retrieval-ranking variant, and an opt-in monitoring sort key) that
meets every one of its own Stage 10.1 acceptance criteria. Its real,
measured effect on detection — §2's B9-vs-B8 comparison, the report's central
number — is a genuine regression (47.1% vs 70.6% detection at equal
7.3% FPR), with a verified, disclosed root cause and a named, un-attempted
fix.~~

**Current verdict, as of §7**: the named follow-on was pursued to completion,
non-circularly, and the real evidence changed. Phase 10 v1's risk-composition
layer, at its recalibrated threshold, **matches B8's real detection and
false-positive rate exactly** on the reported corpus, with a verified,
disclosed, non-circular calibration history behind that number. The research
question in plan §1 ("combined into one estimate... increases real detection
without increasing real false positives") is now answered **partially yes**:
detection parity was achieved with zero false-positive cost, though a real
*improvement* over B8 — as opposed to recovery to parity with it — remains
unestablished on this evidence. `GROUPED_GATED`'s per-guard-group weighting,
`MemoryGraft-style-volume`'s unresolved 50% ceiling (a separate, structural,
already-disclosed limitation), and the still-unwired `REQUIRE_VALIDATION`/
Phase 3 integration (plan §5) remain real, open items for a future stage.
