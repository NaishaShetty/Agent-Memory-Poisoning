# Pre-registration: hold-out 3 (in-the-wild jailbreaks), and the B16 radius

Written **before** any config was scored on hold-out 3 or on the fresh adaptive seeds. The
corpus was built and frozen first; its digest is recorded below and a CI test recomputes it.

## Why this exists

Two of round 6's results are not held out, and saying so repeatedly is not the same as fixing
it:

- **B17** (`B13 OR B14`) and **B18** (`B17 OR deberta@oracle`) were both chosen *after* reading
  hold-out results. Their published numbers are descriptive.
- **B16's radius**: the frozen dev radius 0.97 showed no effect (4/30 vs 5/30, p=1.0); a
  radius of 0.90 eliminated adaptive evasion entirely (0/30, p=0.0625) but was chosen after
  seeing that, on the same 43 seeds.

Both are selection on the thing being measured. This document fixes what will be measured, on
what, with which frozen numbers, and what the predictions are — before the measurement.

## The frozen artifacts

| artifact | identity | frozen |
|---|---|---|
| hold-out 3 attacks | 1,000 in-the-wild jailbreak prompts, `TrustAIRLab/in-the-wild-jailbreak-prompts` (MIT), human-authored (Reddit/Discord) | SHA-256 `655d01a1d68fb13cf58d45b493eaa5c2cc8d74f14780a19d0abe57994198b581`, 2026-10-04T16:50:50Z |
| hold-out 3 benign | 995 `regular_*` prompts from the same platforms, deduplicated against the attacks | same digest |
| deberta oracle threshold | 0.998609, from `eval_round5.json::baseline_thresholds` | round 5, unchanged |
| B13 / B14 / B15 | unchanged, as published | rounds 4–6 |
| B16 radius under test | **0.90** | fixed here, before the fresh-seed run |

Nothing is re-fitted on hold-out 3. No threshold, weight, or radius is chosen from it.

## Analysis 1 — stateless configs on hold-out 3

**Configs:** B12, B13, B14, B15, B17, B18, plus all five published baselines at their round-5
dev and oracle thresholds.

**Primary outcome:** exclusion rate on the 1,000 attacks.
**Primary cost:** exclusion rate on the 995 matched benign prompts. This is the harder FPR test
this project has had — benign text from the *same* source and platforms as the attacks, so a
detector cannot score well merely by distinguishing Reddit from this project's own benign
corpora.

**Predictions, recorded in advance:**

1. **B18 ≥ B17 on attack recall.** The whole claim for B18 is that deberta carries independent
   signal out of distribution. If B18 ≤ B17 here, that claim fails on its first clean test.
2. **B18 > B14 by a clear margin on attack recall** (I expect ≥ 5 points), for the same reason.
3. **B13 will be poor here, well below B14/B18** — hold-out 3 is a jailbreak corpus, and B13's
   signals are provenance and corroboration, which these items do not engage. If B13 scores
   *well* here, I have misunderstood what B13 keys on.
4. **Benign FPR will be materially worse for every config than the 1–3/1088 measured on the
   ordinary benign populations**, because this benign text is long, argumentative, and from the
   same distribution as the attacks. I expect the published-baseline FPRs to degrade most.
5. **No config will exceed ~85% attack recall** at an acceptable FPR, because this corpus
   contains long persona prompts whose malice is contextual.

A result that contradicts 1 or 2 falsifies B18 and will be reported as such.

## Analysis 2 — B16's radius on FRESH adaptive seeds

**Seeds:** attack instances NOT among the 43 used in the round-6 adaptive runs, drawn from
populations the adaptive attacker has never been pointed at. Selection is by a fixed rule
(stratified by family, seeded), written before the run.

**Configs:** B15 (stateless control) and B16 at radius **0.90**, which is fixed above. The
radius will not be adjusted after seeing these results; if 0.90 fails here, B16 fails.

**Primary outcome:** genuine adaptive evasion of initially-excluded seeds, paired, exact
McNemar.

**Prediction:** B16@0.90 reduces genuine adaptive evasion relative to B15 on fresh seeds, in
the same direction as the exploratory run. I do **not** predict 0/N again; the exploratory
result was 5 events and the point estimate is unstable.

**What would falsify it:** no reduction, or a reduction with p > 0.1 at n ≥ 20 initially
excluded seeds.

**Cost that must be reported with any positive result:** the ledger-poisoning blast radius at
0.90 is 29.7% of benign traffic inside one poisoned entry's radius, against 0.7% at 0.97. A
reduction in adaptive evasion does not by itself justify that, and the recommendation must state
the trade rather than the recall alone.

## Standing commitments

- Both hold-out 3 numbers (attack recall and matched-benign FPR) are reported together, always.
- Working-attack denominators are reported for hold-out 3 as for every other population, via
  `attack_validity_audit`. Until that audit covers it, its recall numbers carry the caveat.
- Every number from these two analyses is reported whether or not it favours the configs I
  built, including the predictions above that turn out wrong.
