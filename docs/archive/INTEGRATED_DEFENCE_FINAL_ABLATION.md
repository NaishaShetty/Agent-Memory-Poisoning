# Integrated Defence: Final Ablation

**Date:** 2026-10-14. Deliverable 5. Composed from the workstream outputs (tables T21–T26). There are no new model calls here.

## 1. Components, and whether they earned a place

| Component | Workstream verdict | In the recommended stack? |
|---|---|---|
| B13 at admission (corroboration) | Baseline; owner-stable (T19) | Yes (baseline) |
| **VPL**: verified, payload-only lineage | Not a B13 replacement (gain on 1 of 3 sets). Safe under wrong lineage; recovers explicit payloads after Mem0 | **Yes, as a narrow, safe add-on** |
| SAG-B13 (v2) | Rejected (benign cost) | No |
| **RCL** containment | Accepted on HO4 (v2); strong on factual payloads in HO8 and HO7 | **Yes** |
| CTC containment | Not accepted. Strong on instruction payloads, weak on factual | Only through routing |
| **PRC** (route RCL / CTC by payload type) | Not accepted on fresh HO7 (C2 p = 0.07; C6 underpowered); passes all criteria on repeated HO8 | **Candidate**, with the evidence stated |
| N1 / INTENT sleeper detectors | Failed (benign limits) | No |
| **VoA** (flag-and-confirm) | Not accepted (works raw, fails after Mem0) | **Only for un-rewritten memories**, a narrow use |

## 2. Ablation on the shared held-out sets

### Admission sets (attacks excluded / benign excluded)

| Set | D0: B13 stored | D1: + VPL | D1, wrong lineage | D1, lineage missing |
|---|---|---|---|---|
| MEM-1 | 59 / 37 | 60 / 37 | 59 / 37 | 59 / 37 |
| MEM-2 | 23 / 2 | 58 / 3 | 26 / 3 | 23 / 2 |
| SA-3 eval (ungrounded) | 18 / 9 | 20 / 9 | 18 / 9 | 18 / 9 |

### Propagation (withheld among payload-carrying descendants at generation 4; unflagged collateral)

| Set | D0: frozen guard | D2: + RCL | D2′: + PRC | Collateral |
|---|---|---|---|---|
| HO7 (fresh) | 2/10 | 6/10 | 8/10 | 0/40 |
| HO8 | 13/35 | 20/35 | 26/35 | 0/40 |
| HO4 | 5/18 | 15/18 | 14/18 | 0/40 |

### Sleeper activation (SA-4 raw, attacks acting without confirmation; legitimate rules surfaced)

| Config | Attacks | Legitimate rules surfaced |
|---|---|---|
| D0 (undefended / B13 admits) | 15/45 | 31/45 |
| B13 exclusion | 2/45 | 14/45 |
| D3: VoA (B13 flag) | 3/45 | 32/45 |
| D3: VoA (N1 ∨ B13) | 2/45 | 33/45 |

## 3. Interactions and failure modes

- **Shared dependency.** VPL, RCL, CTC and PRC all depend on **correct lineage**.
  - VPL's link verification makes **wrong** lineage harmless: it inherits nothing.
  - **Missing** lineage leaves every one of them at baseline.
  - **No component recovers lost lineage.**
- **VoA and VPL compose:** the raw flag reaches the stored memory through the verified link (41/45). But **Mem0's rewriting defeats VoA's behavioural effect.** That interaction, not a missing flag, is why the integrated sleeper path fails after transformation.
- **No new false-positive mode** appeared in composition:
  - unflagged collateral stays 0;
  - VPL adds ≤ 1.7 benign points;
  - VoA adds confirmation questions instead of exclusions. Its burden is 25/45 legitimate trigger answers asking, against 16/45 undefended.

## 4. Overhead (indicative, v2 timing + v3/v4)

| Component | Cost |
|---|---|
| Corroboration | 0.52 s per memory |
| CTC NLI | ≈ 0.1 s per descendant per flagged root (xsmall cross-encoder, CPU) |
| RCL | 0.019 s |
| VPL | One embedding comparison per link |
| VoA | No model call. One prepended frame, plus the extra user turn when the agent asks |

## 5. Does the integrated defence outperform the baseline?

**Yes, on three specific, held-out-measured axes:**
- explicit payloads after extraction (MEM-2 23 → 58);
- multi-generation containment (gen-4 withheld 2 → 8 of 10 on HO7, 13 → 26 of 35 on HO8, 5 → 14–15 of 18 on HO4; 0 collateral);
- un-rewritten sleeper activation without benign loss (15 → 2–3, legitimate rules kept).

**No, on:**
- implicit-sleeper detection;
- transformed-sleeper activation;
- lineage loss;
- user-channel poisoning.

**The simplest defensible stack is B13 + VPL + RCL.** PRC is the next increment, but its fresh-set evidence is underpowered.
