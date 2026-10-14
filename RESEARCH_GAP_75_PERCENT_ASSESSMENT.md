# Research Gap 75% Assessment

**Date:** 2026-10-14. Deliverable 6.

**Rubric:** `FINAL_DEFENCE_BASELINE_AUDIT.md` §3 (committed in `16b7b58e`, before any v3/v4 outcome). Weights, the evidence required for each score and the critical-capability caps are unchanged.

**Per-capability evidence:** in the three workstream reports. Every score cites a table.

## Scores

| Gap | Score | Held-out or dev | 75% target |
|---|---|---|---|
| **1. Provenance and governance** | **59%** | Held-out for 1.2, 1.3 and 1.5 (SA-3 eval, SA-4); repeated for MEM-1/MEM-2; LOO for 1.4 | **Not reached** |
| **2. Self-propagation and containment** | **58%** | Held-out on HO4 (v2), HO8 (v3) and HO7 (fresh, v4); dev diagnostic only | **Not reached** |
| **3. Dormant / implicit sleepers** | **29%** | Held-out (SA-3 eval, SA-4); a critical capability scores 0 | **Not reached** |

**No combined number is reported.** Combining them would hide Gap 3's failure.

## Per-capability (score / weight)

| Gap | Capability | Score | Weight |
|---|---|---|---|
| 1 | 1.1 Transformation-aware detection* | 0.5 | 0.25 |
| 1 | 1.2 Wrong lineage handled safely* | 0.75 | 0.20 |
| 1 | 1.3 Benign utility incl. ungrounded* | 0.5 | 0.20 |
| 1 | 1.4 Owner generalisation | 0.75 | 0.15 |
| 1 | 1.5 End-to-end prevention | 0.5 | 0.20 |
| 2 | 2.1 Claim tracking | 0.75 | 0.10 |
| 2 | 2.2 Instruction payloads to generation 4* | 0.5 | 0.25 |
| 2 | 2.3 Factual payloads to generation 4 | 0.75 | 0.15 |
| 2 | 2.4 Influence reduced* | 0.75 | 0.20 |
| 2 | 2.5 Benign preserved and recovery | 0.75 | 0.15 |
| 2 | 2.6 Lineage loss | 0 | 0.15 |
| 3 | 3.1 Dormancy and activation measured | 0.75 | 0.15 |
| 3 | 3.2 Implicit detection after transformation* | 0 | 0.30 |
| 3 | 3.3 Benign preserved while detecting* | 0 | 0.25 |
| 3 | 3.4 Activation prevented | 0.5 | 0.20 |
| 3 | 3.5 Explicit sleepers after transformation | 0.75 | 0.10 |

\* Critical capability.

## How the scores moved during this programme

These are the same rubric applied retrospectively to the evidence before v3, recorded for transparency.

| Gap | Before v3 (v2 evidence only) | After v3 + v4 | Main contributors |
|---|---|---|---|
| 1 | ≈ 0.40 | 0.59 | 1.2: SAG harmful → VPL harmless under wrong lineage. 1.3 / 1.5: VoA preserves legitimate memories on raw text |
| 2 | ≈ 0.44 | 0.58 | 2.2: instruction-style containment 32% (dev) → 83% (HO8) and 80% (HO7). 2.4: HO8 influence reduction |
| 3 | ≈ 0.19 | 0.29 | 3.4: VoA raw activation 15 → 2 without benign loss |

These figures carry the same rounding as the rubric.

## Why 75% is not reached, per gap

**Gap 1:**
- **Provenance in real memory systems is the stored text alone.** Lineage can carry a decision across a rewrite, and VPL shows that can be made safe. It cannot recover authorship that was never recorded.
- **Ungrounded legitimate memories** remain excluded by B13. VoA preserves them only before rewriting.

**Gap 2:**
- **Containment needs intact lineage** (2.6 = 0).
- **Instruction-payload containment** clears every pre-set threshold except significance. Generation-4 denominators are small because payloads themselves die out (10–18 carrying roots).

**Gap 3:**
- **The decisive information (authorship) is absent from the text.**
- **Detection is not achievable at acceptable false positives with any tested signal.**
- **The best mechanism (VoA) is defeated by Mem0's rewriting** of rules into preference facts.

## Minimum additional capability for higher scores

| Gap | Need |
|---|---|
| 1 / 3 | A memory store that records **writer identity and source channel per memory** and keeps it through extraction. Adding source-span links to Mem0's ADD/UPDATE events would be enough to test this |
| 2 | Larger generation-4 samples (≈ 300 flagged roots per payload type) to power the pre-registered tests; and a lineage-recovery method (content-addressed claim IDs) tested against lineage loss |
| 3 | A memory system preserving conditional instruction form, or a real user-confirmation study measuring decline rates |
