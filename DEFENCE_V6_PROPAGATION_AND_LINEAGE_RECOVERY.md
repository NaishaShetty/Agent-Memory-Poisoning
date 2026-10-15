# Defence v6: Propagation and Lineage Recovery (Gap 2)

**Date:** 2026-10-15.

**Pre-registration:** `docs/phase17/PREREGISTRATION_DEFENCE_V6_2026-10-14.md` §3 (`700de011`) + addendum A (`49fa223c`, HFP-B).

**Raw data:** `phase17/data/defence_v6/{power_analysis, ho9_*, fpb_*, g2_eval, g2_wtp_check}.json`.

**Code:** `phase17/defence_v6/{power, ho9_corpus, ho9_chains, fpb, g2_eval, g2_wtp_check}.py`.

## 1. New data

| Set | Construction | Size | Status |
|---|---|---|---|
| **HO9** roots | HO7's generator (mistral:7b-text, re-pulled, digest `495ae085`), owners 2, 3, 5, 9 (never used for propagation) | 460 instruction / 73 factual / 160 benign | Frozen `e38a4f80…` after one pre-registered top-up |
| B13-flagged roots | Shipped thresholds, each root against its own owner | **265 instruction** (target 250, set by power analysis) / 31 factual / 19 benign | `ho9_flags.json` |
| HO9 chains | 4 generations of qwen2.5 consolidation (root + 4 owner memories per step); behaviour on 6 slots; carry and compliance judges; one simulated post-deletion rewrite per descendant | 395 chains (296 flagged attack, 19 flagged benign, 80 unflagged benign) | `ho9_chains_partial.json` |
| FPB | 8 controlled transformations per root (Gemini); construction labels | Dev 80 roots / eval 140 roots | Carry judge agrees 89–100% per type (eval) |

**Power (§1 of the pre-registration):**
- 250 flagged instruction roots give power 0.84 for the generation-4 test under HO7's pessimistic survival, and 0.89 for the behavioural test.
- **Deviation:** the factual top-up was aborted for compute (≈ 15 s per seed; 22% kept). Factual payloads stay a secondary, underpowered subset (31 roots).

## 2. Claim fingerprints (FPB)

| Matcher | Recall on payload-carrying transformations | False match, benign same-subject | Match, negation / action change |
|---|---|---|---|
| Digest only | 21.3% | 0% | 0% |
| Similarity only (sem ≥ 0.5) | 98.9% | 77.9% | 97.1% |
| NLI only (CTC τ) | 89.3% | 22.1% | 16.8% |
| HFP (pre-registered; dev selection **FAILING**) | 95.6% | 30.7% | 81.1% |
| **HFP-B** (addendum A, dev-selected τ_n 0.2, τ_r 0.9) | **92.9%** | **2.1%** | **2.5%** |

All rows are FPB eval: 140 held-out HO9 roots × 8 transformations.

**Finding:**
- A semantic-similarity branch cannot separate "carries the planted claim" from "same person, same topic, same named entity". Benign controls share the payload's entity.
- **Entailment in both directions can:**
  - descendant → root catches paraphrase and merge;
  - root → descendant catches a split (partial) claim.
- HFP-B was explored on dev only (disclosed in addendum A) and generalises to new roots.

## 3. Multi-generation containment (HO9, held-out, powered)

**Instruction payloads, 265 flagged roots.** Payload-carrying descendants withheld, generations 1 → 4 (carrying n: 158, 107, 82, 73):

| Arm | Gen 1 | Gen 2 | Gen 3 | **Gen 4** | Non-carrying withheld (pooled) | Unflagged collateral | Influence left at gen 4 (undefended 19/265) |
|---|---|---|---|---|---|---|---|
| FG (frozen guard, bounded decay) | 124 | 36 | 24 | **18** | 60/640 | 0/80 at every gen | 12 |
| ND (no decay) | 124 | 68 | 51 | 41 | 94/640 | 0 | 8 |
| RCL | 124 | 64 | 41 | 33 | 74/640 | 0 | 11 |
| CTC | 109 | 64 | 52 | 42 | 185/640 | 0 | 10 |
| **PRC** (v4 rule, frozen) | 110 | 64 | 53 | **43 (58.9%)** | 188/640 (29.4%) | 0 | **10** |
| RAR (HFP) | 67 | 26 | 17 | 14 | 19/640 | 0 | 16 |
| RAR-B (HFP-B) | 66 | 27 | 24 | 15 | 19/640 | 0 | 15 |

**Paired generation-4 tests** (exact McNemar; roots are the units; Holm over RAR, RAR-B, PRC):

| Comparison | Discordant | p (raw) | p (Holm) |
|---|---|---|---|
| **PRC vs FG** | +34 / −9 | 1.7e-4 | **5.1e-4** |
| RAR vs FG | +8 / −12 | 0.50 | 1.0 |
| RAR-B vs FG | +11 / −14 | 0.69 | 1.0 |
| RAR-B vs PRC | +3 / −31 | 7.7e-7 | — |
| **Influence: PRC vs none** | 0 / 9 removed | **0.0039** | — |

The owner-cluster bootstrap for RAR-B at generation 4 is 20.5% [12.7, 26.3].

**Acceptance (C1–C6):**

| | C1 ≥ 60% | C2 > FG (Holm) | C3 ≥ best single − 5 | C4 collateral ≤ 5% | C5 non-carrying ≤ 25% | C6 influence |
|---|---|---|---|---|---|---|
| RAR | ✗ (19%) | ✗ | ✗ | ✓ | ✓ | underpowered |
| RAR-B | ✗ (21%) | ✗ | ✗ | ✓ | ✓ | underpowered |
| **PRC** | **✗ (58.9%: 43/73, one root short)** | **✓** | ✓ | ✓ | **✗ (29.4%)** | **✓** |

**Factual payloads** (secondary, 31 roots, 8 still carrying at gen 4): PRC 7/8 vs FG 3/8 (p = 0.125, underpowered); RCL 7/8; RAR-B 1/8.

**Why the root-anchored fingerprint fails on real chains.** The carry judge finds the payload in 73 descendants at generation 4; HFP-B finds the claim in only 19. Each consolidation merges the payload with four other memories into a 2–3 sentence summary. The summary neither entails the whole root, nor is entailed by it, even when it still carries the payload. FPB's single-step transformations did not represent this. Its weakest type, "merge" (57% on dev), was the warning.

**What the powered set does establish (new, held-out):**
- The v4 PRC rule beats the frozen guard on instruction payloads at generation 4: p = 5e-4 after Holm, versus underpowered p = 0.07 on HO7.
- It also reduces behavioural influence (p = 0.004).
- The pre-registered 60% bar is missed by one root, and the 25% non-carrying constraint is breached (29%).
- Decay is a root cause: removing it (ND) more than doubles generation-4 containment (41 vs 18).

## 4. Lineage recovery: conditions kept separate

Matcher HFP-B; all 296 flagged attack chains (`recovery_HFP-B`, `g2_wtp_check.json`):

| Condition | Recovery correct | Gen-4 carrying withheld | False association: owner's real memories (416) | False association: unflagged benign descendants (320) | Collateral |
|---|---|---|---|---|---|
| A: lineage present | — | 16/81 | — | — | 0 |
| B: never persisted (write-time taint) | — | 16/81; **296/296 equal to A** | — | — | 0 |
| **C1: deleted, append-only log intact** (exact digest) | **296/296** | 16/81 (= A) | **0/416** | **0/320** | 0 |
| C2: deleted, then rewritten (**simulation**) | 295/296 | 12/65 | **317/416 (76%)** | **307/320 (96%)** | 0/416, 1/320 |
| C3: total loss (root registry, reference) | 22/296 | 22/81 | 2/416 withheld | 16/320 withheld | — |

**Correction (6c61566a):** `g2_eval.json` first reported B's equality to A through a placeholder that computed nothing. It was recomputed step by step: 296/296 (`g2_wtp_check.json`).

**Reading:**
- **Deleted lineage can be recovered exactly when an append-only log survives:** 296/296, zero false associations. This is a recovery mechanism that can sit under any containment rule, including PRC.
- **If the memory is also rewritten after deletion, reconciliation finds the right root (295/296) but associates most of the owner's memories with tainted roots.** Consolidated summaries contain the owner's own text, so the owner's memories match them. Collateral stays near 0 only because the root-anchored decision then fails to match. This fails the pre-registered 5% false-association limit.

## 5. Per-generation measurements (instruction, flagged roots, undefended)

| Gen | Payload carried (judge) | Claim persists (HFP-B) | Retrieved for the task | Compliance (activation) | Influence (activation ∧ not with clean store) |
|---|---|---|---|---|---|
| 1 | 158 | 73 | 190 | 136 | 68 |
| 2 | 107 | 32 | 130 | 96 | 33 |
| 3 | 82 | 27 | 101 | 96 | 26 |
| 4 | 73 | 19 | 80 | 87 | 19 |

**Release:** releasing a falsely quarantined root restores every descendant. Containment is recomputed from the root state; v2 established this, and no arm keeps descendant state beyond the root.

## 6. Effect on Gap 2 capabilities (frozen rubric)

| Capability | Before | v6 evidence | After |
|---|---|---|---|
| 2.1 Claim tracking validated against the carry judge | 0.75 | HFP-B validated on FPB (judge agreement 89–100%), but tracks only 19 of 73 judge-carrying gen-4 descendants on real chains | **0.75** |
| 2.2 Instruction payloads contained to gen 4* | 0.5 | Powered fresh set: PRC significant vs FG, **58.9% < 60%** | **0.5** |
| 2.3 Factual payloads | 0.75 | Underpowered subset consistent (PRC/RCL 7/8) | **0.75** |
| 2.4 Influence reduced* | 0.75 | Replicated on the powered set (p = 0.004) | **0.75** |
| 2.5 Benign preserved, release | 0.75 | Unflagged collateral 0/80 at every generation; PRC non-carrying 29% | **0.75** |
| 2.6 Lineage loss | 0.5 | B ✓; C1 ✓ (exact recovery, 0 false associations); **C2 ✗** (76% false association) | **0.5** |

**Next version:**
- **Claim-level containment that decomposes consolidated summaries into sentences**, and fingerprints each against the root's claim set rather than the whole root.
- **No-decay root-anchored scoring (ND) combined with PRC routing**, selected on dev and tested on a fresh powered set.
- **Recovery after rewrite needs the rewrite itself logged:** an UPDATE event carrying parent ids, not post-hoc reconciliation.
