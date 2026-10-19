# Defence v6: Integration and Ablation

**Date:** 2026-10-15.

**Pre-registration:** §5. **Code:** `phase17/defence_v6/integration.py`. **Data:** `integration_eval.json`.

Everything is computed from the per-item decisions of the Gap-1 and Gap-3 evaluations: SA-6 eval, Mem0-stored, trigger message. Excluded memories get the clean-store answer. No new model calls.

## 1. Arms

| Arm | Implicit unconfirmed activation (48) | Explicit (48) | Ungrounded legitimate excluded (144) | Legitimate memories available (192) |
|---|---|---|---|---|
| Undefended stored (reference, `g3_eval`) | 19 | 8 | 0 | 100% |
| 1. Baseline: B12 ∨ B13 exclusion | 7 | 3 | 35 | 81.8% |
| 2. Best provenance: PCL exclusion | 7 | 0 | 35 | 80.2% |
| 3. Best propagation: PRC | — (separate substrate: HO9, see the Gap-2 report; gen-4 influence 19 → 10/265) | | | |
| 4. Best sleeper: TS | 4 | 0 | **0** | **100%** |
| 5. Combined: PCL exclusion, else TS | **2** | 0 | 35 | 80.2% |

**Paired tests:**

| Comparison | Discordant | p |
|---|---|---|
| Combined vs baseline, implicit | +0 / −5 | 0.063 |
| Combined vs TS, implicit | +0 / −2 | 0.50 |
| Combined vs baseline, legitimate excluded | +18 / −15 | 0.73 |

**Reading:**
- **The combined system is not superior to TS alone.** It removes two more implicit activations (not significant) at the cost of excluding 35 legitimate memories that TS keeps usable.
- **For sleepers, TS alone has the best security and utility trade-off.**
- **PCL's value lies elsewhere:** detection-time exclusion of explicit attacks hidden by rewriting (Gap-1 report), and end-to-end prevention without relying on the agent's compliance with a frame.

## 2. Ablations of the combined system

| Ablation | Implicit unconfirmed | Explicit | Legitimate excluded | Test vs combined |
|---|---|---|---|---|
| **Ledger → Mem0 native metadata** (after an API UPDATE relabels attack memories as the user's) | **19** | 5 | 17 | Implicit +17/−0, **p = 2e-5** |
| Claim-level → item-level inheritance | 2 | 0 | 35 | Identical on single notes (differs on MSD; Gap-1 report) |
| PAB13 → B13 (corroborate everything) | 2 | 0 | **50** | Legitimate excluded +15/−0, **p = 6e-5** |
| Stage-2 restore → frame on stored text | 2 | 0 | 35 | +1/−1, p = 1.0 |

**Questions the pre-registration asked:**

| Question | Answer |
|---|---|
| Does provenance preservation improve sleeper defence? | **Yes, decisively** under laundering: without the ledger, the protection disappears (2 → 19) |
| Does aggressive provenance propagation increase false positives? | Yes, for corroboration: applying B13 to every memory instead of only untrusted-sourced ones excludes 15 more legitimate memories. Claim-level inheritance of B12 also adds false positives on unusual harmless rules (Gap-1 report) |
| Does a sleeper detector add value beyond claim-level provenance? | **Detection** at the frozen point did not meet its limits. The **Stage-2 restore** adds value over exclusion-based provenance: TS gets implicit activation to 4 with no exclusions, where PCL leaves 7 |
| Does the combined system improve behaviour, not only intermediate metrics? | Over the undefended store, yes (19 → 2 implicit, 8 → 0 explicit). Over TS alone, no significant gain |

## 3. Overhead

| Item | Value |
|---|---|
| Mem0 ingest (median) | 12.6 s per item |
| Ledger bookkeeping (median) | 0.001 s (0.013% of ingest) |
| TS at retrieval | One ledger lookup per retrieved memory; no model call |
| HFP-B (propagation, if used) | Two NLI calls per (descendant, root) pair on CPU |

## 4. Recommended configuration

The evidence supports this configuration; it is not proven optimal:

1. **Ledger always on.** Union semantics, FLV validation, and never trusting Mem0's native label after an UPDATE.
2. **PAB13 at admission.** Corroborate only memories with a non-user source.
3. **TS at retrieval** for untrusted-sourced conditional memories.
4. **PRC with an append-only taint log** for propagation (log-based recovery of deleted lineage).
5. **PCL exclusion only** where agent compliance with a frame cannot be relied on. It costs about 16 points of benign memories in mixed-source documents.
