# Research Gap Closure Assessment

**Date:** 2026-10-13. Deliverable 6. Evidence labels:

| Label | Meaning |
|---|---|
| PRE-REG / held-out | Pre-registered (`4d1ee064`), evaluated on held-out data |
| DEV | Development data, diagnostic |
| REPEATED | Cached decisions on previously used sets |

## Gap 1: provenance and lifecycle governance — **PARTIALLY ADDRESSED (unchanged status)**

**Demonstrated:**
- Corroboration against the owner's conversation is the working component of B13. It is owner-stable (LOO, 10 owners) and survives Mem0 extraction (MEM-1).
- **New:** carrying a content detector's raw-item decision through write-time lineage (SAG-B12) recovers explicit payloads that extraction strips.
  - MEM-2: 22 → 60 of 60; activation 7 → 0 (1 → 0 vs stored-text B13).
  - Benign cost ≤ 1.7 points on all three sets.
  - REPEATED for MEM-1 and MEM-2; held-out for SA-3.

**Not demonstrated / failed:**
- **SAG with corroboration fails its pre-declared benign limit:** +5.0 points on HO4; +37.8 on SA-3 ungrounded rules.
- **Corroboration flags most legitimate ungrounded conditional memories:** SA-3 eval 25/45, dev 36/60.
- **Lineage must be authentic.** A wrong lineage costs +25 to +58 benign points.
- **User channel unaddressed.**
- **Selective trust and action gating untested,** because no tool-executing agent is available.

**Minimum evidence for "closed":**
- authenticated, system-recorded provenance;
- a benign-cost-controlled treatment of ungrounded memories;
- a downstream action test.

## Gap 2: self-propagating poisoning and containment — **PARTIALLY ADDRESSED (strengthened)**

**Demonstrated, PRE-REG held-out (HO4, 4 generations):**
- **Diagnosis:** the frozen guard's decay is structural (per-hop attenuation, distance decay), not only flag loss.
- **RCL keeps containment through generation 4:**

  | Measure | RCL | Frozen guard | No containment |
  |---|---|---|---|
  | Withheld among payload-carrying, gen 1 → gen 4 | 97% → 83% | 97% → 28% | — |
  | Memory-attributable influence at generation 4 | 4/79 | 8/79 | 12/79 |

  Unflagged-benign collateral is 0/40, and all four pre-declared criteria were met.
- **Recovery works:** releasing a wrongly flagged root unblocks its descendants (0/31 withheld).

**Not demonstrated:**
- **Instruction-type payloads (DEV, 13 families).** RCL decays: 75% → 32% at generation 4, because consolidation paraphrases below the similarity bar.
- **Inherited false positives.** Descendants of wrongly flagged roots stay withheld (12/31 at generation 4) until review.
- **Admission misses are invisible to lineage.**
- **Coverage is limited:** one consolidation prompt, one agent, one memory system.

**Minimum evidence for "closed":** a held-out test on instruction-type payloads, paraphrase-robust claim tracking, and a second consolidation strategy or memory system.

## Gap 3: sleeper poisoning — **DORMANCY AND ACTIVATION DEMONSTRATED; IMPLICIT-SLEEPER DETECTION OPEN (negative result)**

**Demonstrated (PRE-REG held-out, SA-3 eval):**
- Implicit sleepers are dormant and activate on their trigger: 21/45 vs 0/45 on unrelated messages; p = 9.5e-7.
- They still activate after Mem0 rewrites them: 15/45.
- Explicit sleepers are caught by content detection when the raw text is available. Through Mem0 this needs SAG (MEM-2: 60/60).

**Failed:**
- **No signal separates implicit sleepers from legitimate ungrounded conditional rules.** Tested: content, injection classifier, sleeper guard, anomaly, corroboration, and two LLM intent judges.
  - The dev-selected policy caught 3/45.
  - The strongest raw signals cost 27–56% of legitimate ungrounded rules.
- **SA-2's earlier corroboration result (40/60 vs 0/60) is qualified.** It held only against grounded-by-construction controls.

**Minimum evidence for "closed":**
- a detector meeting pre-declared limits on held-out owners, after transformation, against ungrounded benign controls;
- or a provenance or user-confirmation mechanism shown to prevent activation at acceptable cost.
