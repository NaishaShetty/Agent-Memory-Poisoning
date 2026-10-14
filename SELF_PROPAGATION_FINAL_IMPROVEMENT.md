# Self-Propagation: Final Improvement (Gap 2)

**Date:** 2026-10-14. Deliverable 3.

**Pre-registrations:**
- v3 WS-B (CTC);
- v4 WS-B4 (PRC).

**Tables:** T22 (v2 RCL), T25 (v3/v4).

**Raw data:**
- `phase17/data/defence_v3/{ho8_chains_partial, ctc_*}.json`;
- `phase17/data/defence_v4/{ho7_chains_partial, prc_eval}.json`.

## 1. Lifecycle diagnosis (from all chain sets)

**Why containment decays:**
- **(a) The frozen guard's arithmetic:** per-hop attenuation plus distance decay. A grandparent can never reach the threshold.
- **(b) Semantic drift under consolidation.** RCL withholds iff sem(descendant, root) ≥ 0.5. Instruction payloads get paraphrased below that while the claim persists: dev median 0.63 → 0.46 by generation 4.
- **(c) Payload persistence itself falls:**

  | Set | Flagged roots still carrying the payload at generation 4 |
  |---|---|
  | HO8 instruction | 18/68 |
  | HO7 pooled | 10/70 |

  So small denominators are intrinsic to generation-4 tests.

**What lineage cannot see:**
- (d) lineage loss, or a missing root flag;
- (e) roots B13 missed at admission.

**Measured influence.** Memory-attributable behavioural influence also decays without any defence:

| Set | Undefended influence, gen 1 → gen 4 |
|---|---|
| HO8 | 35 → 12 of 118 |
| HO7 | 15 → 3 of 70 |
| HO4 | 21 → 12 of 79 |

## 2. Candidates, with selection on dev only

| Candidate | Definition | Selected / constructed | Held-out set |
|---|---|---|---|
| **CTC** (v3) | NLI entailment of the root claim by the descendant, τ = 0.00474 | Selected on dev chains | HO8 (new) |
| **PRC** (v4, no new parameter) | Route each root by the frozen `_DIRECTIVE` regex or B12: instruction → CTC; otherwise → RCL | Constructed from v3 held-out findings | **Fresh HO7 chains** |

## 3. Results

Payload-carrying descendants of flagged roots withheld, generation 1 → 4. Every arm acts only on flagged roots; an evaluation-code defect in v3 scoring was fixed, see §5.

| Set | Frozen guard | RCL | CTC | **PRC** | RCL ∨ CTC (reported only) |
|---|---|---|---|---|---|
| **HO7 fresh, pooled (70 flagged)** | 38/45 → 2/10 | 38/45 → 6/10 | 37/45 → 7/10 | **39/45 → 8/10** | 42/45 → 9/10 |
| HO7 instruction (55) | 28/35 → 2/8 | 28/35 → 4/8 | 29/35 → 6/8 | 29/35 → 6/8 | 32/35 → 7/8 |
| HO7 factual (15) | 10/10 → 0/2 | 10/10 → 2/2 | 8/10 → 1/2 | 10/10 → 2/2 | 10/10 → 2/2 |
| HO8 instruction (68; v3 held-out) | 54/60 → 6/18 | 54/60 → 9/18 | 38/60 → 15/18 | 37/60 → 15/18 | 58/60 → 16/18 |
| HO8 factual (50) | 29/32 → 7/17 | 29/32 → 11/17 | 23/32 → 3/17 | 28/32 → 11/17 | 30/32 → 12/17 |
| HO4 factual (79; v2 held-out) | 67/69 → 5/18 | 67/69 → 15/18 | 50/69 → 7/18 | 56/69 → 14/18 | 68/69 → 16/18 |

**Behavioural influence remaining at generation 4:**

| Set | No containment | Frozen guard | RCL | PRC | RCL ∨ CTC |
|---|---|---|---|---|---|
| HO7 | 3/70 | 2 | 1 | 0 | 0 |
| HO8 | 12/118 | 10 | 4 | 5 | 4 |
| HO4 | 12/79 | 8 | 4 | 6 | 4 |

**Collateral.** Unflagged-benign descendants withheld: **0/40 at every generation**, for every lineage arm and every set.

## 4. Acceptance

**CTC (HO8 instruction, v3):**

| Criterion | Result | Met? |
|---|---|---|
| Generation 4 ≥ 60% | 83% | Yes |
| Above the frozen guard | +9/−0, p = 0.004 | Yes |
| Above RCL | +7/−1, p = 0.07 | No |
| Influence reduction | — | Underpowered |

Not accepted. On factual payloads CTC is clearly worse than RCL.

**PRC (fresh HO7, v4 primary):**

| Criterion | Result | Met? |
|---|---|---|
| C1: generation 4 ≥ 60% | 80% | Yes |
| C2: above the frozen guard | +7/−1, p = 0.07 | **No** |
| C3: no worse than the best single rule, per payload type | Both | Yes |
| C4: unflagged collateral | 0% | Yes |
| C5: non-carrying withheld ≤ 25% | 24% | Yes |
| C6: influence reduction | 3 → 0 | **Underpowered** |

**Not accepted.**

**PRC on the repeated sets:**
- **HO8:** passes all six criteria (75% vs 37% at generation 4, p = 0.0023; influence 12 → 5, p = 0.016).
- **HO4:** fails C3, because routing classifies 34/79 factual roots as instructions (the `_DIRECTIVE` regex matches "always", "prefers"…).

**Reading across the three held-out chain sets.** RCL, CTC and PRC each beat the frozen guard at generations 2–4 on every set. The gains are large: on HO7 at generation 3, PRC holds 12/17 against the frozen guard's 4/17. But the **pre-registered generation-4 tests have too few payload-carrying descendants left** to reach significance on the fresh set. That is a power limit, not a reversal.

**No single rule wins on both payload types.** RCL ∨ CTC is the strongest arm everywhere, but it breaches the 25% non-carrying constraint it failed on dev (HO7: 50/182), so it is not recommended.

## 5. Defect found and fixed during v3

The first CTC scoring let the RCL and CTC arms act on **unflagged** benign roots, producing apparent collateral of 19–34 of 40.
- **Fix:** match the pre-registered definition (lineage acts only on flagged roots).
- **Regression test:** `test_ctc_lineage_arms_never_act_on_unflagged_roots`.
- **Defective output kept:** `ctc_eval_DEFECTIVE_unflagged_roots.json`.
- **Selection unaffected:** the dev metrics used only flagged roots.

## 6. Gap 2 status

| Capability | Evidence | Score |
|---|---|---|
| 2.1 Root claims tracked across consolidation | RCL/CTC validated against an independent carry judge on 4 chain sets | **0.75** |
| 2.2 Instruction-style contained to generation 4 (critical) | CTC 15/18 (HO8); PRC 6/8 (HO7 instruction). Above the frozen guard on both; pre-set significance missed on fresh HO7 (small n) | **0.5** |
| 2.3 Factual contained to generation 4 | RCL: HO4 15/18 (accepted, v2), HO8 11/17, HO7 2/2 | **0.75** |
| 2.4 Influence reduced, attributable (critical) | HO4 12 → 4 (p = 0.008, v2 accepted); HO8 PRC 12 → 5 (p = 0.016, repeated); HO7 underpowered | **0.75** |
| 2.5 Benign preserved and recovery | 0/40 unflagged collateral on every set; release restores; inherited false positives persist until release | **0.75** |
| 2.6 Robust to lineage loss or a missing root flag | Not achieved: lineage arms → 0 by construction; RECHECK caught 7/66 at 7/40 collateral (v2) | **0** |
| **Gap 2 operational score** | | **0.575 (58%)** |

**What blocks a higher score:**
- **Dependence on intact lineage.**
- **Payload attrition** makes late-generation tests small.
- **No rule** is simultaneously paraphrase-robust and low-collateral.
