# Final Gap-Closure Report

> **Correction (targeted phase, 2026-10-13).** The claim that B13's corroboration thresholds "move about 3x with the calibration owners" is **withdrawn**. It compared the nominal 2%/5% budget at `SUPPORT_TOP_K=20` against shipped constants that sit at a 0.49%/2.05% budget at top-20 (they were calibrated at top_k=5). Leave-one-owner-out calibration over all 10 owners at the shipped budget reproduces B13 (detection 116/200, benign exclusion 15/2,541; thresholds vary 1.15x). See `B13_OWNER_GENERALISATION_REPORT.md`. Annotator 2 was the owner's friend, who labelled on the owner's laptop (owner's clarification); see `ANNOTATION_PROVENANCE_FINAL.md`. No new annotation study is recommended by default.


**Date:** 2026-10-13. **Deliverable 1.**

**Branch:** `remediation/2026-10-12`, continued. Nothing was pushed or published.

**Pre-registration:** `docs/phase17/PREREGISTRATION_GAPCLOSURE_2026-10-13.md`
- commit `f177c77c`, made before any run;
- addendum B, commit `8786ac7d`, covering two defects found before any analysis.

**Evidence labels:**

| Label | Meaning |
|---|---|
| PRE-REG | Pre-registered, as above |
| NEW | New analysis, not pre-registered |
| CACHED | Recomputed from saved outputs, with no model calls |
| REPRO | Reproduction check against published artifacts |

---

## Stage A: audit and baseline reproduction

| Item | Command | Outcome |
|---|---|---|
| Working tree | `git status` | Clean except 3 pre-existing logs in `phase17/data/run_all_logs/` (not ours, untouched) |
| SA-1 rebuilt from caches after refactoring its evaluator | `python -c "from phase17.remediation.sleeper_activation_eval import run; run()"` | **Identical** to the committed artifact. This is a cache rebuild, not fresh model outputs |
| HO4 B13 decisions recomputed on the raw notes | inside `mem0_pipeline_eval` | 79/157, **item for item** equal to the published decisions |
| B13 corroboration firings recomputed (HO4, HO7, HO8) | `python -m phase17.remediation.corroboration_robustness` | **Item for item** equal to the cached components |
| Validity audit C0 verdicts | `validity_judge_sensitivity.rows()` | 2,628/2,628 equal to the published audit |
| Frozen regression suite on CPU (`CUDA_VISIBLE_DEVICES=-1`) | `pytest phase6/ … phase3/ -m "not slow"` | **1 failed**, 2,689 passed, 30 skipped. The failure is device-dependent (REP-7): the same test **passes with the GPU visible**, verified by running it both ways |
| Final suites, GPU visible | see §8 | Frozen suite 2,690 passed / 0 failed / 30 skipped / 9 deselected (slow) (`remediation/logs/final_gap_regression_frozen_gpu.log`). Phase 17 `pytest phase17/ phase17/leakage_audit.py -m "not slow"`: 202 passed / 0 failed (`final_gap_phase17_gpu.log`), including all 23 remediation tests. Not run: `slow`-marked tests; isolated A-MEM/Mem0 environment stages. Mutation checks: both new Mem0-defect tests fail on the defective versions (verified) |

**Not reproduced.**
- Model-generated quantities (agent answers, judge verdicts) were not regenerated from scratch, except where an experiment re-ran them by design.
- Run-to-run spread is documented in `docs/release/REPRODUCE.md`. A complete historical re-run was not attempted.

---

## Stage B: real memory pipeline (Mem0 2.0.19, `infer=True`)

**Setup.** Owner baselines were ingested naturally once: 42 and 43 memories. Each item was then ingested naturally, as a shared document and as the user's own message.

| Experiment | n | Main results |
|---|---|---|
| **MEM-1**, HO4 (clean owner) | 157 attacks, 262 benign | **Stages:** stored 157 → carries the claim 155 → retrieved for its task 48 → changed the answer 29.<br>**Defences on stored memories:** B12 2, B13 without corroboration 2, **B13 59**. Benign: B13 37/262.<br>**Working under B13:** 16 (p = 2.4e-4). User channel: 29 working, 0 excluded.<br>**Predictions:** 5 of 6 held; **M1-5 FAILED** (retrieval 48/157, predicted ≥ 50%) |
| **MEM-2**, SA-1 | 60 + 60 | **Storage:** 54 of 240 ingestions stored nothing. The conditional form survived in only 10/58 stored attacks.<br>**Behaviour:** trigger retrieval 55/60, but activation only **7/60**; dormancy 0/60.<br>**Detection:** B12 on stored memories **22/60**, against 60/60 on the raw notes; benign 1/60.<br>**Predictions:** 5 of 5 held |

**Artifacts:** `REAL_MEMORY_PIPELINE_EVALUATION.md`; T16.

---

## Stage C: attack validity and causal attribution

| Analysis | Kind | Result |
|---|---|---|
| Memory-attributable compliance (net, paired) | CACHED / NEW | Own +43.2 (C0) / +47.1 (vote); external +13.3 / +13.7. Fitted-probe task-alone rate 25.7% / 47.4%. Admissible populations: 8/20 (C0), 2/20 (vote) |
| Defence recall on 5 denominators | CACHED / NEW | **Rankings identical** for own and external; B13 vs B14 keeps its direction and significance in every case |
| ADJ-1, blind Gemini adjudication | PRE-REG | Split **60/60** on 120 disagreements; κ = 0.145 with each judge. **ADJ-1a FAILED.** About 19% of labels are ambiguous |
| PR-1, non-leading probe | PRE-REG | Base rate 5/150 (**PR-1a held**). Working 36 vs 73 (**PR-1b FAILED**). Agreement 54%. Net effect stays positive (+24 / +37) |

**Artifacts:** `ATTACK_VALIDITY_AND_CAUSALITY_REPORT.md`; T13, T14, T18.

---

## Stage D: the three gaps

See `THREE_GAPS_FINAL_STATUS.md`.

| Gap | New evidence this round | Status |
|---|---|---|
| **1. Provenance and governance** | MEM-1 (corroboration survives extraction); corroboration robustness: the wrong owner kills discrimination on HO4 and HO8, thresholds move about 3× with the calibration owners, and HO7 corroboration is weak even with the right owner | **Narrowed.** Demonstrated for the corroboration component under correct channel labels. Governance broadly, and calibration stability, remain open |
| **2. Self-propagation** | Per-generation table assembled from P2 + gen 1 + HO8. No new experiment, because the existing two-generation data answers the brief's questions; the flag-removal arm (S-noinh) already tested missing inheritance | **Unchanged: partially demonstrated.** Containment decays (75% → 34%) and depends on inheritance |
| **3. Sleepers** | SA-2: implicit rules: content 0/60, corroboration 40/60 vs 0/60 grounded benign, every sleeper-specific detector fails. MEM-2: extraction strips conditional form and explicit wording | **Narrowed.** Dormancy and activation demonstrated. Explicit vs implicit separated. Stealthy-sleeper detection is unsolved (a negative result) |

---

## Stage E: calibration, generalisation, false positives

`CALIBRATION_AND_LEAKAGE_AUDIT.md` covers:
- every threshold, with its development data, owner overlap and freeze;
- the owner map;
- permitted and prohibited claims.

**New findings this round**
- B18's deberta "oracle" threshold was **fitted on ordinary-benign test data**.
- Frame v6 was **designed after a hold-out-7 failure**.
- Judge selection used **items from HO5**.
- ~~The B13 operating point is **calibration-unstable**.~~ Withdrawn (see correction above): owner-disjoint calibration is stable; the cost depends on evidence quality and on how grounded benign notes are.

---

## Stage F: manuscript, reproducibility, release

- **`paper/main.tex`** was restructured around RQ1–RQ4, with:
  - a new threat-model table;
  - a new natural-pipeline section;
  - SA-2.

  83 generated macros, 0 pending. The LaTeX lints clean (no undefined macros, citations or references). **Not compiled** (no TeX toolchain here).
- **`MAMBench Results Analysis.docx`** gains a generated §16, rebuilt from the artifacts.
- **`DATA_LICENSING_AND_ANNOTATION_AUDIT.md`** records:
  - full licence inventory, from package metadata and `ollama show --license`;
  - **annotator 1 is the project owner**; annotator 2's independence is unverifiable (both sheets were saved under the owner's Office account).
- **`NOVELTY_MATRIX.md`** carries the requested columns.

---

## Gaps by severity, after this round

| # | Remaining gap | Severity | Closed / narrowed / open | Why |
|---|---|---|---|---|
| 1 | **Human validation**: annotator 1 is the author; annotator 2 is the author's friend (labelled on the author's laptop, blind by instruction) | Medium | **Disclosed** | Labels only choose between judges; defence, ranking and net-effect results do not depend on them (`ANNOTATION_PROVENANCE_FINAL.md`). Disclosed in the paper |
| 2 | Stealthy / implicit sleeper detection | High (scientific) | **Open (negative result)** | SA-2 shows only owner evidence separates them, and partly by construction |
| 3 | ~~Corroboration's calibration instability~~ (withdrawn; LOO over 10 owners is stable) — evidence dependence remains | Medium | **Narrowed** | LOO done (targeted phase). experiment |
| 4 | End-to-end evaluation covers one memory system and two corpora | Medium | **Narrowed** | MEM-1 and MEM-2 done; A-MEM with evolution not run |
| 5 | Propagation is development-only, two generations, retention-based taint | Medium | **Unchanged** | Documented |
| 6 | Instance-level working labels are probe- and judge-dependent | Medium | **Narrowed** | Population-level and ranking conclusions shown robust |
| 7 | User-channel poisoning | Medium (threat-model scope) | **Documented as a scope limit** | — |
| 8 | Licence; artifact repository; compilation | Blocking for release only | **Owner action** | — |
| 9 | Device-dependent Phase-15 baseline (REP-7) | Low | **Documented** | — |


---

## 8. Tests executed (exact)

| Command | Device | Passed | Failed | Skipped | Not run |
|---|---|---|---|---|---|
| `pytest phase6/ phase8/ phase11/ phase12/ phase13/ phase14/ phase15/ attribution/ phase7/ phase3/ -m "not slow" -q` | GPU visible | **2,690** | **0** | 30 (real Mem0/A-MEM/llama-server runtimes absent from the main interpreter) | 9 `slow` (deselected) |
| Same | CPU only (`CUDA_VISIBLE_DEVICES=-1`) | 2,689 | **1** (REP-7, device-dependent) | 30 | 9 |
| `pytest phase17/ phase17/leakage_audit.py -m "not slow" -q` | GPU visible | **202** | **0** | — | Phase 17 `slow` tests |
| `pytest phase17/tests/test_remediation.py -q` | CPU | 23 | 0 | — | — |

**Mutation checks**
- Earlier round: 4/4 injected defects caught.
- This round: the `top_k` test fails on the pre-fix `run_pipeline.py`, and the baseline-completeness test fails on the defective baseline (20 memories vs 47 ADD events).

**Not run anywhere:**
- the `slow` suites;
- the isolated `make amem-live` / `make mem0-live` stages;
- a complete pre-change baseline.
