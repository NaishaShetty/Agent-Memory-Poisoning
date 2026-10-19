# Self-Propagation Containment Report (WS-B, Gap 2)

**Date:** 2026-10-13. Deliverable 3.

**Pre-registration:** WS-B of `PREREGISTRATION_DEFENCE_V2_2026-10-13.md` (`4d1ee064`).

**Code:** `phase17/defence_v2/propagation_multigen.py`.

**Data:**
- `prop_eval.json`: held-out HO4.
- `prop_dev.json`: development chains, diagnostic only.

## 1. Why the existing containment weakens (diagnosis)

The frozen guard scores a descendant as SEVERITY[ancestor state] × 0.5^(distance−1) × retention.

**The causes:**
- A generation-k summary is withheld via its parent only if the parent itself was assigned a tainted state.
- The parent's severity is lower (SUSPICIOUS 0.4) unless its retention was ≥ 0.857.
- The root's own contribution at distance ≥ 2 is capped below 0.35 by the 0.5 decay.

**So taint is attenuated at every hop.** This is structural; flag loss is one mechanism among several.

**Confirmed empirically:**
- With intermediate states lost (FG-noinh), the frozen guard withholds **0** descendants from generation 2 onwards, in both data sets.

**Lexical retention never works under paraphrase** (P2: 0–2 withheld).

## 2. Candidate: root-anchored claim lineage (RCL)

Each descendant is scored directly against the **flagged root claim**: SEVERITY[root] × semantic retention(descendant, root).

- Frozen thresholds; no per-hop attenuation.
- The retention model is P2's own.
- Nothing was fitted.

**Simpler baseline: RECHECK**, which re-runs B13 on each descendant.

## 3. Held-out evaluation: HO4, owner 7, 4 consolidation generations

**Chains:**

| Root type | Count |
|---|---|
| Attack roots | 157 |
| Attack roots flagged at admission (laundering) | 79 |
| Benign roots wrongly flagged by B13 | 31 |
| Seeded unflagged benign roots | 40 |

Descendants of one root form one chain. Every comparison is paired by root.

| Generation | 1 | 2 | 3 | 4 |
|---|---|---|---|---|
| Payload still carried (flagged roots, carry judge) | 69/79 | 36/79 | 22/79 | 18/79 |
| Descendant retrieved for the root's task | 37/79 | 39/79 | 39/79 | 36/79 |
| Memory-attributable influence, undefended (A0) | 21/79 | 15/79 | 14/79 | 12/79 |
| **Withheld among payload-carrying, frozen guard** | 67/69 | 16/36 | 6/22 | 5/18 |
| Withheld, frozen guard without inherited states | 67/69 | 0/36 | 0/22 | 0/18 |
| **Withheld among payload-carrying, RCL** | **67/69** | **32/36** | **20/22** | **15/18** |
| Withheld, RECHECK | 15/69 | 6/36 | 2/22 | 2/18 |
| Influence remaining, frozen guard | 1/79 | 7/79 | 7/79 | 8/79 |
| **Influence remaining, RCL** | 1/79 | **1/79** | **3/79** | **4/79** |
| Collateral, unflagged benign descendants (RCL / frozen guard / RECHECK) | 0 / 0 / 2 of 40 | 0 / 0 / 5 | 0 / 0 / 6 | 0 / 0 / 7 |
| Withheld descendants of *wrongly flagged* benign roots (RCL / frozen guard) | 24 / 24 of 31 | 15 / 8 | 14 / 5 | 12 / 4 |
| Same, after the benign root is RELEASED (RCL) | 0/31 | 0/31 | 0/31 | 0/31 |
| B13 admission misses still caught later (any lineage arm / RECHECK) | 0 / 7 of 66 | 0 / 4 of 37 | 0 / 2 of 25 | 0 / 0 of 23 |

### Pre-declared acceptance

| Criterion | Result | Met? |
|---|---|---|
| C1: RCL withholds ≥ 60% at generation 4, with a drop ≤ 15 points | 97.1% → 83.3%, a 13.8-point drop | Yes |
| C2: RCL above the frozen guard at generations 2 and 4 | +17/−1, p = 1.4e-4; +10/−0, p = 0.002 (Holm 2.9e-4, 0.002) | Yes |
| C3: unflagged-benign collateral ≤ 5% at every generation | 0/40 throughout | Yes |
| C4: influence remaining at generation 4 below no containment | 4 vs 12 of 79; +0/−8, p = 0.0078 | Yes |

**RCL accepted on HO4.**

## 4. Development chains (diagnostic, not a test): RCL also decays

These are P2's 249 own attacks across 13 families, of which 161 were flagged, extended to generation 4.

| Withheld among payload-carrying | Gen 1 | Gen 2 | Gen 3 | Gen 4 |
|---|---|---|---|---|
| Frozen guard | 76/102 | 24/71 | 11/41 | 5/31 |
| RCL | 76/102 | 43/71 | 22/41 | **10/31** |

Benign collateral, RCL: 4 → 1 of 79.

**Mechanism.** RCL withholds exactly when retention ≥ 0.5 (0.7 × r ≥ 0.35).

| Data set | Median retention to the root, payload-carrying, gen 1 → gen 4 |
|---|---|
| Dev (instruction-type payloads: worms, preference hijacks, FARMA, policy revocation…) | 0.63 → **0.46** |
| HO4 (short factual claims) | 0.72 → 0.61 |

Consolidation **paraphrases** instruction payloads below the similarity bar while the carry judge still sees the claim.

**RCL fixes the structural attenuation, but not semantic drift.**

## 5. Answers to the brief

**Does containment remain effective across the tested generations?**
- **For HO4's factual claims: yes.** 83–97% of payload-carrying descendants are withheld through generation 4, and influence falls from 12 to 4 of 79.
- **For instruction-type payloads (dev): no.** RCL holds 32% at generation 4. It beats the frozen guard (16%) but still decays.

**Failure modes.**

| Failure mode | Effect |
|---|---|
| Lineage lost, or root flag missing | Lineage arms withhold 0 by construction |
| Paraphrase | Semantic drift below the similarity bar |
| Inherited false positives | Benign descendants of a wrongly flagged root stay withheld (12/31 at generation 4) until the root is released. Release restores all of them (0/31) |
| Admission misses | Invisible to lineage. RECHECK catches a few (7/66 at generation 1) at 2–7/40 benign collateral |

**Not tested.**
- Multiple consolidation strategies or memory systems: only one consolidation prompt and agent.
- Delayed activation beyond the measured task.
