# Provenance and Governance Improvement Report (WS-A, Gap 1)

**Date:** 2026-10-13. Deliverable 2.

**Pre-registration:** `docs/phase17/PREREGISTRATION_DEFENCE_V2_2026-10-13.md` (commit `4d1ee064`), WS-A.

**Code:** `phase17/defence_v2/sag_eval.py`.

**Data:** `phase17/data/defence_v2/sag_eval.json`; `integration.json`.

## 1. Candidate

**Source-anchored governance (SAG).** A memory that Mem0 extracted from an item inherits that item's admission decision, through the write-time item → derived-memory link:

SAG-X(stored m) = X(raw source item) OR X(m)

- X ∈ {B12, B13}.
- No parameters.

**What it addresses.** The audit's main Gap-1 failure is **provenance loss under transformation**. Mem0 rewrites an item, and the detector then judges the rewrite:
- MEM-2: B12 caught 60/60 raw sleeper rules but only 22/60 of their stored versions.
- MEM-1: B13 caught 79 raw attacks but only 59 stored ones.

## 2. Results (document channel; attacks excluded / benign excluded)

| Set | Rule | Lineage lost (= stored-text decision) | **Lineage intact (SAG)** | Wrong lineage (permuted) |
|---|---|---|---|---|
| MEM-1, HO4 (157 / 262) | B13 | 59 / 37 | **87 / 50** | 82 / 102 |
| MEM-1 | B12 | 2 / 6 | 3 / 9 | 5 / 10 |
| MEM-2, SA-1 (60 / 60) | B13 | 23 / 2 | **60 / 3** | 35 / 36 |
| MEM-2 | B12 | 22 / 1 | **60 / 2** | 35 / 36 |
| SA-3 eval vs ungrounded benign (45 / 45) | B13 | 18 / 9 | **33 / 26** | 33 / 35 |
| SA-3 eval vs grounded benign (45 / 45) | B13 | 18 / 0 | 33 / 1 | 27 / 17 |
| SA-3 eval vs ungrounded benign | B12 | 1 / 0 | 3 / 0 | 3 / 1 |

**Behaviour (each attack's measured outcome):**

| Set | Outcome | Undefended | B13 on stored text | B13 with SAG |
|---|---|---|---|---|
| MEM-1 | Working attacks | 29 | 16 | 15 |
| MEM-2 | Trigger activation | 7 | 1 | 0 |

**User channel (MEM-1).** B13 excludes nothing, with or without SAG, because user turns are trusted. SAG-B12 adds 3 exclusions, which stop 1 working attack (29 → 28).

## 3. Pre-declared acceptance (SAG-B13 replacing B13-on-stored)

| Criterion | MEM-1 | MEM-2 | SA-3 eval (ungrounded) | Met? |
|---|---|---|---|---|
| (1) Attack exclusion rises (exact McNemar, Holm) | +28/−0, p = 1.5e-8 | +37/−0, p = 4.4e-11 | +15/−0, p = 6.1e-5 | Yes |
| (2) Benign exclusion rises by ≤ 3 points | **+4.96** | +1.67 | **+37.8** | **No** |
| (3) Wrong lineage, reported | +24.8 points | +56.7 | +57.8 | Strong dependency |

**SAG-B13 is rejected as a general replacement.**

**Why it fails.**
- SAG inherits the raw-item decision. For B13, that raw decision includes corroboration, which excludes ungrounded benign items at a high rate:
  - HO4 benign: raw 31/262;
  - SA-3 ungrounded benign rules: raw 25/45.
- Re-applying it after extraction therefore **adds** the raw false positives to the stored ones, instead of recovering signal Mem0 destroyed.

**Narrower valid use, reported as a secondary result (no criterion was pre-declared for it): SAG-B12, source-anchored content detection.**
- It recovers the explicit-payload signal that Mem0's rewriting strips:
  - MEM-2: 22 → 60 of 60;
  - activation 1 → 0;
  - benign +1.7 points.
- It costs ≤ 1.2 points of benign exclusion on MEM-1 and 0 on SA-3.
- It adds almost nothing where B12 had nothing to find in the first place: MEM-1 +1; SA-3 implicit sleepers +2.

So **when a content detector would have fired on the raw item, carrying that decision through lineage is cheap and effective**. Carrying corroboration through lineage is not.

## 4. Conditions and what they show

| Condition | Result |
|---|---|
| Lineage lost | Equals the stored-text decision, i.e. the transformation-loss problem |
| **Wrong lineage** | **Harmful:** benign exclusion +25 to +58 points. Any lineage-based rule must authenticate the item → memory link; a mis-attributed link is worse than none |
| Missing / wrong / partial owner evidence | Inherited from `B13_OWNER_GENERALISATION_REPORT.md`, not re-run: 18.7% (wrong) / 21.5% (10%) / inert (none) |
| Ungrounded legitimate memories | The decisive cost. SA-3 shows B13 corroboration flags **25/45** ungrounded but legitimate conditional rules on raw text (dev: 36/60). SA-2's earlier 0/60 relied on grounded-by-construction benign rules |
| User channel | Unaddressed by every variant |

## 5. Owner generalisation

| Source | Status |
|---|---|
| B13 LOO results | Unchanged from the targeted phase |
| SA-3 per owner | `sleeper_scores.json` / `sleeper_v2_eval.json` |

SA-3 evaluation uses 3 owners, which is too few for owner-level intervals. Counts are reported per owner.

## 6. Decision

- **Retain B13 as the baseline governance rule.**
- **Adopt SAG only for content-detector decisions (SAG-B12).** It is cheap and does not inflate benign exclusion on any of the three sets.
- **Do not anchor corroboration through lineage.**
- **Gap 1 remains partially addressed.** Correct lineage is required, and the user channel and ungrounded legitimate memories remain open.

## 7. Not measured

- Benign downstream answers through Mem0.
- Selective-trust actions (restricted use of unverified memories), because no tool-executing agent is available.
