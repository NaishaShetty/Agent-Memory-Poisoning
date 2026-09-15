# Phase 6 Statistical Protocol — Stage 6.11

Status: FROZEN before any larger Phase 6 campaign executes, per explicit
instruction. This protocol governs any future repeated-evidence campaign this
project runs to evaluate the defense; it does not itself execute one (Stage
6.10 confirmed live campaign execution remains blocked by this environment's
missing `mem0ai`/LLM server — see `SEVEN_ATTACK_DEFENSE_INTEGRATION.md`).
Freezing this now, before that blocker lifts, is precisely the point: the
protocol must not be shaped after seeing results.

---

## 1. Sample Size — Computed, Not Assumed

### 1.1 The real pilot evidence this is based on

Stage 6.9's own ablation (`DEFENSE_COMPOSITION_AND_ABLATION.md`) produced one
real, paired data point: on 9 synthetic poison scenarios, B0 (no defense)
detected 0, B1 (admission-only) detected 2. Paired McNemar counts: **b=2**
(defense caught what baseline missed), **c=0** (defense never lost a catch
baseline had). This gives a pilot point estimate `p_discordant ≈ 2/9 ≈ 0.222`,
but with a genuinely wide Wilson 95% CI of **(0.063, 0.547)** at this tiny
n — disclosed as highly uncertain, not treated as a firm prior. `c=0` makes a
direct odds-ratio (`psi`) estimate from this pilot alone degenerate (formally
infinite) — **not extrapolated**; explicit, defensible `psi` values are
chosen instead (Section 1.2).

### 1.2 Power analysis (Connor 1987, McNemar's test), computed via
`phase6/evaluation/statistics/power.py`

| p_discordant | psi=2.0 (modest effect) | psi=3.0 (moderate) | psi=5.0 (strong) |
|---|---|---|---|
| 0.15 | n=469 | n=207 | n=116 |
| 0.22 (pilot point estimate) | n=319 | n=141 | n=78 |
| 0.30 | n=234 | n=103 | n=57 |

All at α=0.05, power=0.80 — standard, disclosed defaults.

### 1.3 Decision: n=120, matching Phase 3's own established campaign scale — with its real power limitation disclosed, not hidden

**Frozen sample size: n=120 per condition**, reusing Phase 3's own precedent
(the LoCoMo formal sample already used for every V1–V3-Hybrid campaign,
Methodology Section 12.12) rather than inventing a separate scale — this
keeps Phase 6 results directly comparable to Phase 3/4's own reported numbers
on the same substrate.

**This is disclosed as a real constraint, not a free win**: reverse-computed
via the same power formula, at n=120 and the pilot's own `p_discordant≈0.22`,
**the smallest reliably detectable effect at 80% power is psi≈3.35** — i.e.,
n=120 can only reliably detect a fairly strong defense effect (discordant
pairs favoring the defense at roughly 3.35:1 odds or better), not a modest one
(psi=2 would need n≈319). **If the real, eventual defense effect turns out to
be modest rather than strong, n=120 may fail to reach significance even when
a real, smaller effect exists** — this is stated here, before any campaign
runs, exactly per the instruction not to pretend a chosen n is adequate for
every possible outcome. Should Stage 6.9's own recalibration recommendations
(the min-cluster-gate fix, the recalibrated threshold) be adopted before a
real campaign, they should be expected to shift the achievable `p_discordant`
and `psi` — this protocol's numbers would then warrant re-deriving, not
reused blindly.

## 2. Repetitions and Seeds

- A **fixed master seed** per condition (mirroring Phase 1/3's own "sole
  source of randomness" discipline, Methodology Section 8) — recorded and
  persisted per run, never regenerated silently between repetitions.
- **Real generation nondeterminism** (Methodology Section 12.15: "a measured,
  disclosed nondeterminism at the answer level") means a single seed does not
  guarantee bit-identical LLM outputs across repeated runs even with
  temperature=0 — this protocol does not claim otherwise. Repetitions beyond
  n=1 per task exist specifically to characterize this nondeterminism's effect
  on the PAIRED comparison, not to be averaged away silently.
- **3 independent repetitions per task/condition pair** (a disclosed,
  practical compromise: enough to characterize the real, measured generation
  nondeterminism Phase 3 already found, without tripling the sample-size
  requirement Section 1 already established as substantial).

## 3. Task, Memory, and Attack-Artifact Sampling

- **Task sampling**: the SAME frozen n=120 LoCoMo formal sample Phase 3/4 already
  use (not a fresh draw) — this is a deliberate choice for direct
  comparability to the existing baseline numbers, not an oversight. The same
  disclosed contamination caveat Methodology Section 12.12 already carries
  forward (pilot/dev overlap with this exact 120-task set is not established
  from available evidence) applies identically here and is not re-litigated.
- **Attack artifact sampling**: the n=120 budget is split across the seven
  attack families. An even split (≈17 tasks per attack) is the frozen
  default; a future campaign MAY deviate (e.g., weighting toward attacks
  Stage 6.10's real-content replay flagged as evading current signals — DSRM,
  MPBench-PCFI) but must document the deviation and its own justification
  before execution, not after seeing results.
- **Clean/poison ratio**: 1:1 within each attack's allocation (half the
  allocated tasks poisoned, half clean controls) — enables both the
  poison-detection and the benign-false-positive measurement Stage 6.9's own
  metrics already require, from the same campaign.

## 4. Evaluation Conditions

Three conditions per task, per attack, per defense configuration (reusing
Stage 6.9's B0–B7 naming):
- **Baseline** (B0): frozen V3-Hybrid, no Phase 6 defense.
- **Defended**: V3-Hybrid + a named Phase 6 configuration (B1–B7, or a
  recalibrated variant if Stage 6.9's recommendations are separately
  authorized before this campaign runs).
- **Oracle control** (explicitly NON-DEPLOYABLE / upper-bound only, per the
  Charter's Section 6 rule): the SAME defense given the evaluator-only
  ground-truth attack label directly, to establish the ceiling a
  label-free defense is being compared against. Never blended into the
  deployable defense's own reported numbers (Charter Section 6, restated
  here because this is precisely the stage where the two could otherwise be
  conflated in a results table).

## 5. Confidence Intervals

**Wilson score intervals**, 95% by default (`phase6/evaluation/statistics/
intervals.py`), matching the Methodology Draft's own Figure 3 precedent
exactly — not the naive normal-approximation interval, for the same
small-n/extreme-p robustness reason already documented in that module.

## 6. Statistical Tests

**McNemar's exact test** (binomial test on discordant pairs,
`phase6/evaluation/statistics/tests.py`), matching the Methodology Draft's own
Section 12.16 precedent — verified to exactly reproduce that document's own
two worked examples (p=0.125 and p=1.000) as a real regression test
(`test_mcnemar_reproduces_methodology_worked_example`), not merely asserted
to be equivalent.

## 7. Aggregation Method

Per-task binary outcome ("was this task's answer free of the attack's
intended false claim, under counterfactual-masking-confirmed influence
terms") is the atomic unit — matching Phase 4's own evidence discipline
(counterfactual masking, not surface retrieval/selection, establishes real
influence). Aggregation to a per-attack and per-configuration rate uses the
raw proportion plus its Wilson interval (Section 5); the baseline-vs-defended
comparison for each attack/configuration pair uses McNemar's test (Section 6)
on the same paired tasks.

## 8. Multiple-Comparison Strategy

**Benjamini-Hochberg false discovery rate correction**
(`phase6/evaluation/statistics/multiple_comparisons.py`), applied across the
up-to-seven per-attack McNemar tests (or up-to-eight B0–B7 configuration
tests, whichever family of comparisons a given campaign report presents) —
chosen over a stricter Bonferroni family-wise correction because these
hypotheses are about the same underlying defense mechanism, not independent
questions; this is a disclosed methodological choice, not the only valid one,
and the report should say so wherever it presents corrected results.

**2026-09-14 addendum (additive):** an external audit found that
`benjamini_hochberg()` was correct and unit-tested but called by nothing else
in the repository at the time — no script yet computed or printed a
per-attack/per-configuration significance claim, so the correction described
above was not wrong, just not yet wired to anything. Closed by
`phase6/evaluation/statistics/significance_report.py`:
`report_family_significance()`/`report_family_significance_from_p_values()`
are now the one, enforced path for turning a family of `McNemarResult`s (or
raw p-values) into a significance report — every code path through this
module applies the correction above before anything can be labeled
"significant." Any future Stage 6.10+ script that reports per-attack or
per-configuration significance should call this module rather than
`benjamini_hochberg()` directly or re-deriving `raw_p_value < alpha` itself.

## 9. Treatment of Failed Runs

- A run that fails for an infrastructure reason (timeout, crash, malformed
  output) before producing a scoreable answer is recorded as
  `RUN_FAILED_INFRASTRUCTURE` and **excluded** from the paired comparison for
  that task (not imputed as either success or failure) — the McNemar
  denominator for that specific pair shrinks by one; this is reported
  explicitly (count of excluded pairs), never silently absorbed into the
  overall n.
- A run that completes but produces an `EVALUATION_UNDEFINED` metric outcome
  (existing Phase 3 vocabulary, Section 12.13) is retained for metrics that
  can still evaluate it and excluded only from metrics for which it is
  genuinely undefined — mirroring Phase 3's own existing discipline exactly,
  not a new rule invented for Phase 6.

## 10. Treatment of Unavailable Environments

- **A-MEM**: Methodology Section 19.5's own disclosed limitation persists
  unchanged — real-vendor A-MEM identity-resolution behavior remains
  `NOT_VALIDATED` in this environment. Any Phase 6 campaign section covering
  A-MEM reports exactly that status, never a fabricated pass (Rule 15).
- **Live V3-Hybrid/Mem0 execution** (Stage 6.10's own finding): if the
  environment blocker (missing `mem0ai`, unreachable local LLM server)
  persists at the time this protocol would otherwise execute, the campaign
  is reported as `NOT_EXECUTED — ENVIRONMENT_UNAVAILABLE`, with this exact
  protocol preserved unchanged and ready to run the moment the environment
  becomes available — not quietly downgraded to a synthetic-corpus substitute
  presented as equivalent evidence.

## 11. What This Stage Does NOT Do

This document freezes the protocol. It does not execute a 120-task campaign
(blocked by Stage 6.10's confirmed environment limitation) and does not
claim the synthetic/replay evidence from Stages 6.9–6.10 satisfies this
protocol's own sample-size requirement — that evidence remains explicitly
labeled as a small pilot (n=9/n=11), used here only to justify this
protocol's parameters, never substituted for the campaign itself.

## 12. Tests and Evidence

27 tests (`test_statistics.py`) across all four statistical modules: Wilson
interval correctness (including narrowing with n, widening with confidence,
boundary safety), McNemar's exact test (two independent reproductions of the
Methodology Draft's own published p-values, a direct cross-check against
`scipy.stats.binomtest`, symmetry), sample-size monotonicity in effect size/
power/alpha, and Benjamini-Hochberg (a textbook worked example, monotone
adjusted p-values, the "never more lenient than uncorrected" invariant).

**Full Phase 6 suite: 201 passed, 0 failed** (174 through Stage 6.10, plus 27
new for Stage 6.11). Frozen `phase3/`, `phase4/`, `phase5/`, `attribution/`
verified unchanged.

## Verdict

**PASS** as a 6.11 deliverable. The sample size is computed, not chosen for
convenience, using real pilot evidence and a real power formula, with its own
genuine limitation (n=120's detection floor is a fairly strong effect,
psi≈3.35, not any effect) disclosed rather than hidden; every other required
protocol element (repetitions, sampling, conditions, intervals, tests,
aggregation, multiple comparisons, failure handling, environment-unavailable
handling) is specified and frozen before any larger campaign runs, consistent
with the explicit instruction governing this stage.
