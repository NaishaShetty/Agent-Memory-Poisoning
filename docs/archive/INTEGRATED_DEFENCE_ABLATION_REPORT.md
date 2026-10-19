# Integrated Defence Ablation Report (WS-D)

**Date:** 2026-10-13. Deliverable 5.

**Code:** `phase17/defence_v2/integration.py`.

**Data:** `phase17/data/defence_v2/integration.json`.

Everything here is composed from the workstream outputs. The only new measurement is timing.

## 1. What could be integrated

**Rule from the pre-registration:** only components that passed their own workstream are recommended.

| Component | Own workstream verdict | Integrated? |
|---|---|---|
| SAG on B13 (corroboration through lineage) | **Failed:** benign +5.0 / +1.7 / +37.8 points | Shown in the ablation only |
| SAG on B12 (content decision through lineage) | Narrow positive (secondary, no pre-declared criterion) | Recommended for content signals |
| RCL (root-anchored containment) | **Accepted on HO4**; decays on instruction-type dev payloads | Recommended, with its dependency |
| WS-C signal (B13 ∧ INTENT-v2) | **Failed** (3/45) | Shown in the ablation only |

## 2. Admission sets

Attacks excluded / benign excluded. D2 (RCL) acts only on descendants and does not change admission.

| Set | D0: B13 on the text in front of it | D1: + SAG | D1, wrong lineage | D3: WS-C signal on stored text | D4: SAG + WS-C signal |
|---|---|---|---|---|---|
| MEM-1, HO4 (157 / 262) | 59 / 37 | 87 / 50 | 82 / 102 | — | — |
| MEM-2, SA-1 (60 / 60) | 23 / 2 | 60 / 3 | 35 / 36 | — | — |
| SA-3 eval vs ungrounded benign (45 / 45) | 18 / 9 | 33 / 26 | 33 / 35 | 1 / 1 | 4 / 1 |
| SA-3 eval vs grounded benign (45 / 45) | 18 / 0 | 33 / 1 | 27 / 17 | 1 / 0 | 4 / 1 |

**Behavioural outcomes remaining:**

| Set | Undefended | D0 | D1 |
|---|---|---|---|
| MEM-1, working attacks | 29 | 16 | 15 |
| MEM-2, activation | 7 | 1 | 0 |

**SA-3 activation on trigger:**

| Condition | Attacks (of 45) | Ungrounded benign (of 45) |
|---|---|---|
| Undefended | 21 | 16 |
| B13 | 10 | 4 |
| Selected WS-C signal | 19 | 16 |

## 3. Propagation (HO4 held-out)

Withheld among payload-carrying descendants of flagged roots, generations 1–4:

| Config | Gen 1 | Gen 2 | Gen 3 | Gen 4 |
|---|---|---|---|---|
| D0: frozen guard | 67/69 | 16/36 | 6/22 | 5/18 |
| D2: RCL | 67/69 | 32/36 | 20/22 | 15/18 |
| D2 + RECHECK | 67/69 | 32/36 | 21/22 | 15/18 |

**Influence remaining at generation 4** (of 79 laundering roots):

| Config | Remaining |
|---|---|
| No containment | 12 |
| D0 | 8 |
| D2 | 4 |
| D2 + RECHECK | 4 |

**RECHECK costs collateral:** 2 → 7 of 40 unflagged benign descendants. It adds only 1 withheld descendant.

**Dev chains (diagnostic):** D0 76 → 5; D2 76 → 10 of the payload-carrying descendants.

## 4. Interactions

**SAG and RCL compose naturally.** RCL's root state *is* the raw-item admission decision, which is SAG's decision. The two share one requirement: **correct lineage**.
- With wrong lineage, SAG raises benign exclusion by 25–58 points.
- With missing lineage, RCL withholds nothing.

So the integrated design's main new failure mode is **lineage integrity**. A single corrupted link both admits poison and blocks legitimate memory.

**Corroboration interacts badly with ungrounded legitimate memory everywhere it appears:**
- at admission (SA-3: 25/45 flagged);
- through SAG (SA-3: 26/45);
- in RECHECK (7/40 collateral).

## 5. Overhead

Indicative, one machine, warm models (`integration.json`):

| Component | Cost per memory |
|---|---|
| Corroboration (NLI, top-20 premises) | 0.52 s |
| INTENT judge (llama3.1:8b, per prompt) | 0.18 s |
| RCL | 0.019 s per descendant per flagged root (one embedding comparison) |
| SAG | One lineage lookup; no model call |

## 6. Conclusion

**The best defensible combination is:**
- B13 at admission;
- SAG for content-detector decisions;
- RCL for descendants.

**It improves on the baseline only:**
- on lifecycle loss of explicit payloads (MEM-2: activation 7 → 0);
- on multi-generation containment of factual claims (HO4: influence 12 → 4 at generation 4, against 8 for the frozen guard).

**It does not improve:**
- implicit-sleeper detection;
- user-channel poisoning;
- ungrounded-benign costs.

All of it depends on correct lineage metadata.
