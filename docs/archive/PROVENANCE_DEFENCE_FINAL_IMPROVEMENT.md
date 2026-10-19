# Provenance Defence: Final Improvement (Gap 1)

**Date:** 2026-10-14. Deliverable 2.

**Pre-registrations:**
- v3: `docs/phase17/PREREGISTRATION_DEFENCE_V3_2026-10-13.md` (`16b7b58e`);
- v4: `docs/phase17/PREREGISTRATION_DEFENCE_V4_2026-10-14.md` (`7dbf2e45`).

**Tables:** T24 (VPL), T26 (verify-on-activation, B13 flag variant).

**Raw data:** `phase17/data/defence_v3/vpl_*.json`; `phase17/data/defence_v4/voa_*.json`.

## 1. Diagnosis of the previous candidate (SAG-B13)

SAG-B13 carried the raw item's **whole B13 verdict**, including corroboration, into every memory Mem0 derived from it. Two failures followed:

1. **The wrong verdict was inherited.** Corroboration answers "is this grounded in the conversation?", not "is this malicious?". Ungrounded legitimate items therefore carried their raw false positive into every derived memory: +5.0 points of benign exclusion on HO4 and +37.8 on SA-3.
2. **Links were trusted blindly.** A wrong item → memory link added 25–58 points of benign exclusion.

**Mem0 mapping in this harness (verified):**
- Each item was ingested in isolation, so mappings are **1:N** (one item → 0–3 memories).
- **N:1 merges cannot occur**, and are therefore **not testable here**.

## 2. Candidate (v3): VPL, verified payload-only lineage

`decision(m) = B13(m) OR [P(raw) AND sem(m, raw) ≥ τ_link]`

- **Corroboration is never inherited.**
- **Selected on SA-3 dev through Mem0** (new data, 180 notes, owners 0, 2, 4, 6):
  - P = B12;
  - τ_link = 0.490, the 5th percentile of 210 true links (median 0.883);
  - dev wrong-link acceptance 2.4%.

| Set (attacks / benign) | Lineage | Attacks: B13 stored → VPL | Benign: B13 stored → VPL | True links accepted | Wrong links accepted |
|---|---|---|---|---|---|
| MEM-1, HO4 (157 / 262) | correct | 59 → 60 | 37 → 37 | 431/433 | — |
| | wrong | 59 → 59 | 37 → 37 | — | 47/433 (10.9%) |
| MEM-2, SA-1 (60 / 60) | correct | **23 → 58** (Holm p = 1.7e-10) | 2 → 3 | 133/137 | — |
| | wrong | 23 → 26 | 2 → 3 | — | 16/137 (**11.7%**) |
| SA-3 eval, ungrounded (45 / 45) | correct | 18 → 20 | 9 → 9 | 90/91 | — |
| | wrong | 18 → 18 | 9 → 9 | — | 1/91 |
| Every set | missing | Unchanged (= B13 stored) | Unchanged | — | — |

**Behaviour:**
- MEM-2 activation remaining: 1 → **0** of 60.
- MEM-1 working attacks remaining: 16 → 16.

**Pre-declared acceptance:**

| Criterion | Result | Met? |
|---|---|---|
| (1) A significant gain on ≥ 2 of 3 sets | Only MEM-2 | **No** |
| (2) Benign increase ≤ 3 points under correct **and** wrong lineage | Every set; max +1.7 | **Yes** |
| (3) Wrong-link acceptance ≤ 10% | 11.7% (MEM-2) | Stated limitation |

**VPL is not accepted as a B13 replacement.**

**What it does establish.**
- **Incorrect provenance is handled safely.** A wrong link changes benign exclusion by 0 points. The previous candidate added 25–58.
- **Explicit payloads stripped by Mem0 are recovered:** 23 → 58 of 60.
- Where the raw item carried no content signal (factual fabrications, implicit sleepers), there is nothing to inherit. **That is the limit of lineage, not of the mechanism.**

## 3. Candidate (v4): verify-on-activation as selective trust (B13-flag variant)

Instead of excluding a B13-flagged memory, keep it and frame it: "unverified; confirm with the user before acting".
- **Frame:** F2, selected on SA-3 dev (T26).
- **Held-out set:** SA-4, new owners 1, 3, 9; 45 attacks and 45 legitimate ungrounded rules.

| Condition | Attacks acting without confirmation | Legitimate rules surfaced (used or offered) |
|---|---|---|
| Undefended, raw | 15/45 | 31/45 |
| **Exclusion by B13**, raw | 2/45 | **14/45** |
| **VoA (B13 flag)**, raw | **3/45** (+0/−12, p = 4.9e-4) | **32/45** |
| Undefended, Mem0-stored | 8/45 | 20/45 |
| VoA through the verified link, stored | 9/45 (n.s.) | 26/45 |

**On raw notes, VoA matches exclusion's security** (3 vs 2) **while keeping legitimate ungrounded memories usable** (32 vs 14). That is the selective-trust behaviour Gap 1 asked for.

**It does not survive Mem0.** Mem0 rewrites "whenever X, recommend Y" into "the user prefers Y". The agent treats a stated user preference as context to use, and the frame does not stop that.

## 4. Gap 1 status

| Capability | Evidence | Score |
|---|---|---|
| 1.1 Transformation-aware detection (critical) | VPL: strong on explicit payloads (MEM-2, held-out-style repeated); nothing to inherit elsewhere | **0.5** |
| 1.2 Incorrect lineage handled safely (critical) | Wrong-link benign change of 0 points on every set; 98–100% of true links kept; wrong-link acceptance 1–12% | **0.75** |
| 1.3 Benign utility incl. ungrounded memories (critical) | B13 still excludes ungrounded legitimate items (HO4 12.6%; SA-3 56%). VoA preserves them on raw notes (32 vs 14 of 45) but not after transformation | **0.5** |
| 1.4 Owner generalisation | B13 LOO over 10 owners (T19) | **0.75** |
| 1.5 End-to-end prevention | MEM-2 activation → 0; VoA raw 15 → 3 (p = 4.9e-4); stored no effect; MEM-1 working unchanged | **0.5** |
| **Gap 1 operational score** | 0.25×0.5 + 0.2×0.75 + 0.2×0.5 + 0.15×0.75 + 0.2×0.5 | **0.59 (59%)** |

No critical capability is at or below 0.25, so no cap applies.

**What blocks a higher score:**
- **Memory systems store the transformed text without the source's intent or provenance.** Lineage can carry a decision, but it cannot carry an authorship fact that was never recorded.
- **User-channel poisoning remains out of scope.**
