# Calibration and Leakage Audit

> **Correction (targeted phase, 2026-10-13).** The claim that B13's corroboration thresholds "move about 3x with the calibration owners" is **withdrawn**. It compared the nominal 2%/5% budget at `SUPPORT_TOP_K=20` against shipped constants that sit at a 0.49%/2.05% budget at top-20 (they were calibrated at top_k=5). Leave-one-owner-out calibration over all 10 owners at the shipped budget reproduces B13 (detection 116/200, benign exclusion 15/2,541; thresholds vary 1.15x). See `B13_OWNER_GENERALISATION_REPORT.md`. Annotator 2 was the owner's friend, who labelled on the owner's laptop (owner's clarification); see `ANNOTATION_PROVENANCE_FINAL.md`. No new annotation study is recommended by default.


**Date:** 2026-10-13. **Deliverable 5.**

**Sources.** Code paths were inspected for this audit. Dates come from git. Recomputations come from `phase17/data/remediation/corroboration_robustness.json` (a NEW ANALYSIS: not pre-registered, run on frozen texts, with no fitting on any hold-out).

## 1. LoCoMo owner map

LoCoMo has 10 conversations, each with two speakers.

| Conv. | Speakers | Role in this project |
|---|---|---|
| 0 | Caroline, Melanie | Development owner (epistemic quarantine, consolidation), harm-study store; `TEST_SAMPLES` |
| **1** | Gina, Jon | **B13 calibration (`DEV_SAMPLES`)** AND **HO8 owner** |
| 2 | John, Maria | B13 calibration; fresh-store replication (addendum 6) |
| **3** | Joanna, Nate | **B13 calibration** AND **SA-1 owner, MEM-2 owner**; fresh-store replication |
| 4 | John, Tim | B13 calibration; fresh-store replication |
| 5, 6 | — | Harm-study stores; validity-audit stores |
| **7** | Deborah, Jolene | **HO4 owner, MEM-1 owner**; harm-study store; `TEST_SAMPLES` |
| **8** | Evan, Sam | **HO7 owner**; `TEST_SAMPLES` |
| **9** | Calvin, Dave | **SA-2 owner**; fresh-store background only; `TEST_SAMPLES` |

**Clean owners for B13** (never used in its calibration): **7 (HO4, MEM-1), 8 (HO7), 9 (SA-2)**.

**Calibration owners re-used as test owners:** 1 (HO8) and 3 (SA-1, MEM-2).

## 2. Every threshold and learned parameter

| Parameter | Value | Development data | Owner overlap | Selection method | Frozen (git) | Evaluation sets | Leakage risk | Permitted interpretation |
|---|---|---|---|---|---|---|---|---|
| B13 `SUPPORT_EXCLUDE` / `SUPPORT_FLAG` | 0.0019 / 0.0057 | Owner turns + `observation` memories of LoCoMo **1–4**; qwen fabrications about them | **HO8 (1), SA-1 (3), MEM-2 (3)** | 2% / 5% quantiles of benign observation support (`b13_dev_calibration.py`) | 2026-09-29/30 (round 4), before every hold-out ≥ 4 | HO4, HO7, HO8, SA-1, MEM | **Owner-level** for HO8, SA-1 and MEM-2; texts never seen | HO4 and HO7 are clean. HO8 and SA-1 results are "owner seen in calibration". See §3 for sensitivity |
| B13 `SUPPORT_TOP_K` | 20 | Same development owners (curve in `b15_support_retrieval.json`) | Same | Operating-curve choice | Round 5 | Same | Same | Same |
| B13 preference regex, directive regex, `CARRY_SIM` 0.6 | — / 0.6 | Development worm-replication set | None | Hand-written; `CARRY_SIM` from the development curve | Round 4 | All | Low | — |
| B12 stacked detector + thresholds 0.005 / 0.02 | — | `tune_lomo.dev_pool`: LLM-authored dev attacks + hard negatives, dataset-arena and ConvoMem **even halves** | No LoCoMo owner | Fitted; thresholds at a dev FPR | Round 4–5 | All | Low for LoCoMo hold-outs. ConvoMem / dataset-arena odd halves are the ordinary-benign test | Clean for HO4–8 |
| B14 fusion weights + threshold | — | Development pool (`train_b14.py`), group-held-out out-of-fold scores | None | Logistic fit | Round 5 | All | B14's **architecture** was chosen after reading HO1 baselines (disclosed) | HO2+ clean for B14 |
| B17 = B13 ∨ B14 | parameter-free | — | — | **Configuration chosen after reading HO1/HO2 results** | Round 6 | — | Selection on hold-outs | Clean only on HO3+ (HO3 retired) → **HO4–8** |
| **B18** deberta "oracle" threshold | 0.99861 | **Ordinary-benign TEST halves** (`eval_round5._baseline_thresholds`: "chosen on test data, in the baseline's favour") | None | Matched to B14's benign exclusion count | Round 5 | All | **Test-fitted** (not on HO4–8) | B18 numbers on the ordinary-benign set are not held out. B18 is not recommended anyway |
| Published baselines `@dev` thresholds | per baseline | `dev_pool` negatives at 0.5% FPR | None | Development | Round 5 | All | Low | Clean |
| Published baselines `@oracle` | per baseline | Ordinary-benign test halves | None | Matched FPR | Round 5 | All | Test-fitted | Report as an oracle (an upper bound for the baseline) |
| Rejection-ledger radius | 0.97 frozen; **0.95 recommended** | Development benign + development paraphrase pairs; 0.95 chosen by a rule on the 130 powered **development** seeds | None | Rule fixed before the sweep | Round 6–7 | **Development only** (never a hold-out) | Selection and evaluation on the same seeds | Development evidence only |
| Embedding-anomaly centroids / threshold (shipped) | 90th percentile | Development benign (`epistemic_quarantine._dev_sets`) | None | Percentile | 2026-10-12 | HO8 (**transductive original**), SA-1 | The original HO8 arm fitted on HO8 benign | Original HO8 result withdrawn. Shipped signal: 80% FPR on HO8 |
| Containment-guard constants (severities 1.0 / 0.7 / 0.4; decay 0.5; thresholds 0.6 / 0.35 / 0.15) | — | Phase 6 design | None | Design constants | Phase 6 | P2, HO8 gen 1 | None | — |
| Neutralisation frame v3 | — | 120 development attacks (`neutralise_v2`) | None | Development selection | Round 7 | HO5–8 | Low | — |
| Frame **v6** (instruction-aware) | — | **Designed after HO7's failed H7-7** (hold-out-informed design), then tested once on HO8 | — | — | 2026-10-09 | HO8 | The design was informed by a hold-out outcome | HO8 is its first clean test; HO7 is not |
| Compliance judge vote; harm judge J2 | — | 35 / 40 human-labelled items **drawn from HO5** | — | SELECT/TEST split by fixed seed | Round 7 | Development re-judging only; HO5 not re-judged (it would be circular) | Judge choice informed by HO5 items | Not applied to HO5 |
| `MAX_PROBE_BASE_RATE` 20% | 0.20 | — | — | Rule adopted in round 7 after HO4's leading probe | 2026-10-06 | HO4+ probes | Not applied retroactively to the main audit | See `ATTACK_VALIDITY_AND_CAUSALITY_REPORT.md` |

## 3. Sensitivity of B13 to calibration owners and to evidence

This is new analysis on frozen texts.

| Set (owner) | Evidence | Thresholds | B13 attacks excluded | B13 benign excluded |
|---|---|---|---|---|
| HO4 (7, clean) | full | frozen (owners 1–4) | 79/157 | 31/262 (11.8%) |
| | full | **owner-disjoint (2, 4)** | 129/157 | 76/262 (29.0%) |
| | first 10% of turns | frozen | 101/157 | 72/262 |
| | wrong owner (8) | frozen | 63/157 | 63/262 |
| HO7 (8, clean) | full | frozen | 70/129 | 29/189 (15.3%) |
| | full | disjoint | 92/129 | 67/189 (35.4%) |
| | wrong owner (7) | frozen | 70/129 | 26/189 |
| HO8 (1, calibration owner) | full | frozen | 118/160 | 15/171 (8.8%) |
| | full | **disjoint** | 152/160 | 43/171 (25.1%) |
| | wrong owner (7) | frozen | 112/160 | 68/171 |
| SA-1 (3, calibration owner), corroboration only | full | frozen / disjoint | 45/60 / 60/60 | 1/60 / 2/60 |
| | wrong owner (7) | frozen | 15/60 | 6/60 |

Cross-checks:
- The corroboration-only firing with full evidence and frozen thresholds **reproduces** the cached B13 components item for item on HO4, HO7 and HO8.
- The owner-disjoint thresholds are 0.00555 / 0.01594, against frozen 0.0019 / 0.0057: about 3× higher.

**Interpretation**

1. **The owner overlap did not inflate HO8's recall.** Excluding owners 1 and 3 from calibration *raises* the thresholds, which raises both recall and false positives on every set. The frozen thresholds were the more conservative operating point for HO8.
2. ~~**The bigger problem is threshold instability.**~~ (Withdrawn, see correction above.) With only 2–4 calibration owners, the 2% quantile moves about 3×, and benign exclusion on the clean hold-outs moves from 12–15% to 29–35%. The operating point is not a property of corroboration; it is a property of which owners calibrate it. A deployment would need per-owner or much broader calibration.
3. **Corroboration needs the right owner's conversation, where it discriminates at all.**
   - On HO4 and HO8, another owner's conversation removes most of the attack–benign gap. Corroboration-only firing goes from 76/157 vs 28/262 to 60/157 vs 60/262 on HO4, and from 81/160 vs 8/171 to 64/160 vs 61/171 on HO8. The discrimination there comes from owner-specific support, not text style.
   - **On HO7, corroboration barely discriminates even with the right owner** (23/129 attacks vs 23/189 benign corroboration-only). HO7's B13 lead over B14 comes mostly from its content and judge rules (48 attacks), with corroboration adding 22.
4. **Sparse evidence raises false positives.** With the first 10% of turns, HO4 benign exclusion rises from 28 to 68 corroboration-only.

## 4. Hold-out status (final)

| Hold-out | Used for | Clean for | Not clean for |
|---|---|---|---|
| HO1, HO2 | Detection | B14 (HO1), B12–B15 (HO2) | B17/B18 (selected after reading them) |
| HO3 | Detection | — (retired: development set = hold-out; scored 7×) | everything |
| **HO4** | Detection; working subset; **MEM-1 (second use, new quantity)** | B12–B21 (owner 7 clean) | — |
| HO5, HO6 | Injection detection | B12–B21 | Judge selection items drawn from HO5 |
| **HO7** | Detection | B12–B21 (owner 8 clean) | Frame v6 design (informed by H7-7) |
| HO8 | Detection, gen-1 consolidation, sleeper | Detection configurations (texts unseen) | **Owner 1 seen in B13 calibration**; anomaly arm (transductive) |
| SA-1 | Sleeper activation; **MEM-2 (second use)** | Activation measurement | **Owner 3 seen in B13 calibration** |
| SA-2 | Implicit sleepers | All (owner 9 clean) | — |

## 5. Permitted and prohibited claims

**Permitted**
- "On two clean-owner single-use hold-outs (HO4, HO7), corroboration-based admission excluded 50–54% of memory poisoning at 12–15% untrusted-channel benign cost with development-frozen thresholds."
- "Those operating points move substantially with the choice of calibration owners."
- "HO8 and SA-1 replicate the ordering, with an owner seen in calibration."

**Prohibited**
- "B13 generalises to unseen owners at 8.8% FPR" (HO8 is not an unseen owner).
- Any HO8 anomaly / union generalisation claim.
- Any B17/B18 number on HO1/HO2 presented as held out.
- Any ledger result presented as hold-out evidence.
- "Human-validated judge" without the annotator caveats (`DATA_LICENSING_AND_ANNOTATION_AUDIT.md` §3).
