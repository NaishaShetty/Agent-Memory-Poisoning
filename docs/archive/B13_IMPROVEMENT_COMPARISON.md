# B13 Improvement Comparison

**Date:** 2026-10-13. Targeted phase, deliverable 2.

**Pre-registration:** `PREREGISTRATION_TARGETED_2026-10-13.md` §2 (commit `dff63620`).

**Data:** `b13_owner_loo.json`, `b13_loo_utility.json`. Table: T19.

## 1. The three policies

| Policy | What it is | Calibration |
|---|---|---|
| **A, original B13** | Non-corroboration components OR (personal claim AND entailment < τx, or < τf for a preference claim) → QUARANTINE | τx and τf are leave-one-owner-out quantiles of benign-observation support (A-ship: 0.487% / 2.047%) |
| **B, conservative corroboration** | Reuses `corroboration_v2` (round 7) rather than a duplicate. Four outcomes: CONTRADICTED (contradiction ≥ τc) → QUARANTINE; UNRELATED (relatedness < τr) → **DEFER**, i.e. ALLOW_WITH_RESTRICTION, stored and retrievable, marked unverified, not excluded; UNSUPPORTED (related, A's rule fires) → QUARANTINE; otherwise pass | τx and τf as in A. τc and τr refit LOO by their documented rules: 0.5% benign contradiction budget; 5th percentile of the calibration owners' fabrication relatedness |
| **C, B12** | Content-only stacked detector plus judge tiers | None (no owner data) |

**Why B was the candidate.** It tests the hypothesis in the brief: that B13 wrongly treats *lack of corroboration* as grounds for exclusion, and that a policy separating contradiction, support and insufficient evidence would cut benign exclusions.

**What was already known before running it.** Round 7 had tested exactly this on the development bed:
- recall fell from 59.7% to 52.2%;
- benign FPR did not fall.

The expected outcome, B1 "B does not meet the criterion", was pre-registered.

## 2. Results (10 LOO owners, correct-owner evidence)

| Policy | Detection (of 200) | Benign excluded (of 2,541) | B: deferred | QA items losing all evidence (of 1,307) | Task correct on 55 affected QA items |
|---|---|---|---|---|---|
| **A-ship** | **116 (58.0%)** | **15 (0.59%)** | — | 7 | 29 |
| A-nom (same rule, looser point) | 159 (79.5%) | 55 (2.16%) | — | 28 | 13 |
| **B** | 104 (52.0%) | 29 (1.14%) | 12 attacks, 0 benign | 9 | 25 |
| **C, B12** | **0 (0%)** | 0 | — | 0 | (no defence = 34) |

**B compared with A-ship** (owner-cluster bootstrap):

| Measure | Point | 95% CI | Item level |
|---|---|---|---|
| Benign exclusion | **+0.55 points** | +0.32 to +0.83 | B adds 14 exclusions, removes 0 |
| Detection | **−6.0 points** | −10.5 to −2.0 | B loses 12, gains 0; p = 4.9e-4 |

On the 55 affected QA items, task completion was 25 under B against 29 under A (p = 0.22).

**Pre-declared improvement criterion for B:**

| Condition | Required | Observed | Met? |
|---|---|---|---|
| (1) Benign-exclusion difference CI entirely below 0 | < 0 | +0.32 to +0.83 | **Fails** |
| (2) Detection difference | ≥ −2 points, lower bound ≥ −10 | −6.0 | **Fails** |
| (3) No owner's benign exclusion rises by more than 2 points | ≤ 2 | Max +1.5 | Holds |
| (4) Attack exclusion on clean hold-outs not lower by more than 5% of attacks | ≤ 5% drop | HO4 82 → 68 (−14 of 157); HO7 74 → 68; SA-2 40 → 37 | **Fails** |

**B is rejected. Prediction B1 HELD.**

**Why B fails.** Both mechanisms work against it on this data:

1. **"Insufficient evidence" is where the signal is.** All 12 attacks that B stops excluding are *unrelated* to the conversation. Additive and preference fabrications are about things the owner never discussed, and so are new benign facts. A deferral rule cannot tell them apart. This repeats the round-7 diagnosis.
2. **The contradiction rule costs benign memories.** It excluded 14 extra benign memories and caught no extra fabrications. At a 0.5% benign budget it fires mostly on paraphrase-level NLI contradictions inside grounded memories.

**Under wrong-owner evidence, B fails open.** Relatedness collapses, so most attacks become DEFER:
- HO4: 119 of 157 attacks deferred; 17 excluded (A-ship: 66).
- SA-2: 54 of 60 deferred.

Deferral is only safe if "unverified" memories are prevented from driving actions. **That restriction semantics was not measured.**

## 3. C (B12): does corroboration add information?

**Yes, on this attack class.**

| Population | B12 | B13's other components | B13 (with corroboration) |
|---|---|---|---|
| 200 owner fabrications | **0** | 0 | 116 at 15/2,541 benign cost |
| SA-2 implicit sleepers | 0/60 | — | 40/60 |
| HO4 (157) | 3 | — | 82 |

Corroboration is the only component that reaches additive fabrication.

The reverse also holds:
- on instruction-shaped attacks (SA-1, much of HO7 and HO8), B12 already excludes most of them;
- with no evidence, B13 is no better than B12.

## 4. Was any other candidate justified? (pre-registration §2, §5)

The rule was:
- implement a further candidate only if the LOO results on **dev owners 1–4** showed a specific failure that one change addresses;
- evaluate it only on owners 0 and 5–9.

**Dev owners' LOO results:**
- benign exclusion 8/1,026 (0.78%);
- detection 52/80;
- thresholds within 0.00189–0.00212.

**There is no calibration failure to fix.** The failure modes the data do show are not ones a single policy change can address:

| Failure mode | Size | Why no policy change fixes it |
|---|---|---|
| Ungrounded benign notes | 12.6% excluded on HO4, 18% on HO7 | Indistinguishable from fabrications by construction (§2 above) |
| Wrong or incomplete evidence | 18.7–21.5% benign exclusion | A property of the evidence supplied, not of the decision rule |
| User-channel poisoning | — | Outside corroboration by design |

Changing the operating point (A-nom) is the one available lever, and it is a trade, not an improvement:
- **+21.5 points** of detection;
- **+1.57 points** of benign exclusion;
- task completion on affected items falls from 29 to 13.

**No candidate was implemented.** Original B13 (A-ship) remains the primary implementation, unchanged. Its code and thresholds are untouched.

## 5. Conclusion

- **B13 did not need an improvement for owner generalisation.** Owner-disjoint calibration reproduces it (58.0% vs 58.5% detection; 0.59% vs 0.55% benign exclusion).
- **The proposed conservative policy is worse on every pre-declared criterion but one,** and is rejected.
- **The remaining weaknesses are about evidence, not calibration.**
- **The A-ship vs A-nom trade-off** should be presented as a deployment choice, with the full curve.
