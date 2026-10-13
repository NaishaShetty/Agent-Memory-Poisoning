# Final Targeted Improvement Report

**Date:** 2026-10-13. Targeted phase, deliverable 6.

**Branch:** `remediation/2026-10-12`. Starting HEAD: `e3f57f65`.

**Pre-registration:** `docs/phase17/PREREGISTRATION_TARGETED_2026-10-13.md`, commit `dff63620`. It was committed before any outcome was computed. Nothing was pushed.

## 1. Overall findings

1. **B13 generalises across owners.** Its earlier "calibration instability" was an artefact of my own analysis.
   - Leave-one-owner-out calibration over all 10 LoCoMo owners reproduces the shipped operating point:

     | Measure | LOO | Shipped thresholds |
     |---|---|---|
     | Detection | 116/200 (58.0%) | 117/200 |
     | Benign exclusion | 15/2,541 (0.59%) | 14/2,541 |

   - Thresholds vary 1.15× across owners. No owner exceeds 1.5% benign exclusion.
   - The earlier "≈3×" compared a 2% budget against constants that sit at a 0.5% budget once retrieval was widened (top_k 5 → 20). It is withdrawn.
2. **What B13 actually depends on is the evidence.**

   | Evidence condition | Benign exclusion |
   |---|---|
   | Correct owner's conversation | 0.59% |
   | Wrong owner's conversation | 18.7% |
   | First 10% of the conversation | 21.5% |

   With no conversation, corroboration is inert, and B12 detects 0/200 of these fabrications. Benign notes the conversation never mentions are the residual cost (HO4: 33/262).
3. **No B13 improvement was retained.** The pre-registered conservative policy (defer unrelated, exclude contradicted):
   - detected 6 points less (CI −10.5 to −2.0);
   - excluded 0.55 points more benign (CI +0.32 to +0.83);
   - failed open under wrong evidence.

   It was rejected. No other candidate was justified by the dev-owner results.
4. **The attack-validity conclusions stand, and are now explained.** A new empty-memory arm shows that the fitted probe leaks the note's content. The empty store is judged compliant more often than the clean store: 59 vs 38 of 150 under C0.

   The memory-attributable effect (poisoned − clean) is positive with cluster-robust intervals in all four probe × judge cells:

   | Probe | C0 | Vote |
   |---|---|---|
   | Fitted | +47.3 | +48.0 |
   | Non-leading | +24.0 | +37.3 |

   The non-leading probe lowers working counts mainly because the agent has no occasion to act on the note (50 of 52 lost items). Defence ranking is identical in all 9 definition × probe cells.
5. **Annotation is recorded correctly.** Annotator 2 was your friend, who labelled on your laptop. The labels support the limited claims they are used for (choosing between judges; J0 under-counts harm). No defence, ranking or net-effect conclusion depends on them. No new annotation study is recommended by default.

## 2. Experiments run

| Experiment | Kind | New model calls | Output |
|---|---|---|---|
| B13 LOO over 10 owners × 4 evidence conditions + none; policies A-ship, A-nom, A-frozen, B, C | Pre-specified re-analysis | NLI profiles (GPU, no LLM); B12/B13 judge tiers for the owner populations (cache-filled) | `b13_owner_loo.json`, T19 |
| Hold-outs HO4, HO7, HO8, SA-1, SA-2 under LOO thresholds | Repeated evaluation (exploratory) | NLI only | same |
| U2: task completion on the 55 affected QA items × 4 stores | Pre-registered secondary | 220 qwen answers + 220 llama3.1 verdicts | `b13_loo_utility.json` |
| Empty-memory arm, 150 items × 2 probes | Pre-registered | 300 qwen answers + 900 judge verdicts | `validity_final.json`, T20 |
| Clustered net effect, definitions, judge disagreement, sensitivity bounds | Pre-registered analysis of cached data | None | same |
| p-value re-derivation with scipy | Audit | None | `stats_audit.json` |
| Annotation provenance and κ with bootstrap CIs | Audit | None | `annotation_provenance.json` |

**Reproduction checks:**
- The decomposition equals direct `apply_defense("B13")` on 60/60 items.
- Recomputed corroboration equals the cached components item for item on HO4, HO7 and HO8.
- A-frozen reproduces the published HO4, HO7 and HO8 counts exactly.
- The PR-1 item sample is reproduced exactly.

## 3. Predictions (pre-registered)

| ID | Status | Value |
|---|---|---|
| L1 thresholds within ×1.5 | **HELD** | 1.15 |
| L2 per-owner benign exclusion ≤ 5% | **HELD** | Max 1.5% |
| L3 LOO detection within ±10 of frozen | **HELD** | 58.0% vs 58.5% |
| L4 wrong owner ≥ 3× benign exclusion | **HELD** | 31.6× |
| L5 trunc10 ≥ 2× | **HELD** | 36× |
| B1 policy B fails the criterion | **HELD** | Fails 3 of 4 conditions |
| V1 none within ±5 of clean | **FAILED** | Fitted −14.0 (C0) / −24.7 (vote); non-leading 0.0 / −4.7 |
| V2 memory effect > 0, cluster CI excludes 0 | **HELD** | All 4 cells |
| V3 B13 above B12 on every definition | **FAILED** | Ties on every working subset; ahead only on the full population |

## 4. Changes made

**New code:**
- `phase17/remediation/b13_owner_loo.py`
- `b13_loo_utility.py`
- `validity_final.py`
- `stats_audit.py`
- `annotation_provenance.py`
- `phase17/tests/test_targeted.py`: 9 tests

**Modified code:**
- `authoritative_tables.py`: T19 and T20; a correction note on T15.
- `paper_numbers.py`: `_targeted()` macros; Fisher labelled one-sided.
- `paper_prose.py`: Fisher labelled one-sided; a pre-existing invalid escape fixed, with byte-identical output.
- `build_results_analysis_docx.py`: new §17; the §16 corroboration paragraph corrected; "independent annotators" wording corrected.
- `compliance_judge_fix.py` and `final_inventory.py`: annotator wording.

**Manuscript (`paper/main.tex`):**
- The abstract's corroboration clause now reports the LOO result instead of the threefold claim.
- RQ1 gains the empty-memory arm and the clustered CI.
- The RQ2 corroboration paragraph is rewritten around LOO, the evidence conditions, the operating-point trade-off and policy B.
- Limitations (3) and (4) are rewritten: annotators; evidence dependence.

**Generated outputs and reports:**
- `paper/numbers.tex` regenerated: 109 macros, 0 pending.
- `MAMBench Results Analysis.docx` rebuilt (no missing artifacts).
- `results/tables/T19`, `T20` and `TABLE_INDEX.md` updated.
- New deliverables:
  - `B13_OWNER_GENERALISATION_REPORT.md`
  - `B13_IMPROVEMENT_COMPARISON.md`
  - `PROBE_AND_ATTACK_VALIDITY_FINAL.md`
  - `ANNOTATION_PROVENANCE_FINAL.md`
  - `STATISTICAL_VALIDITY_AUDIT.md`
  - this report
- Dated correction banners added to the six earlier reports that carried the withdrawn claim or the old annotator wording. Their history is kept.

**Unchanged:**
- B13's code and constants.
- All frozen hold-outs, with no fitting. HO3 untouched.
- All earlier result artifacts. New results go to new files.

## 5. Tests run

| Command | Device | Passed | Failed | Skipped | Not run |
|---|---|---|---|---|---|
| `pytest phase17/tests/test_targeted.py -q` | GPU visible | 9 | 0 | 0 | — |
| `pytest phase17/ phase17/leakage_audit.py -m "not slow" -q` | GPU visible | **211** | **0** | 0 | Phase 17 `slow` tests |
| `pytest phase6/ phase8/ phase11/ phase12/ phase13/ phase14/ phase15/ attribution/ phase7/ phase3/ -m "not slow" -q` | GPU visible | **2,690** | **0** | 30 | 9 `slow` (deselected) |

**Log:** `phase17/remediation/logs/targeted_frozen_gpu.log`.

**Not run this phase:**
- the CPU-only frozen suite: its one known failure is the documented device-dependent REP-7;
- `slow`-marked tests;
- the isolated Mem0 and A-MEM environment stages.

The Mem0-defect regression tests are preserved and pass. No test was removed or weakened.

## 6. Improvements retained or rejected

| Candidate | Decision | Reason |
|---|---|---|
| Owner-disjoint (LOO) calibration as the evaluation protocol | **Retained as the reporting protocol** | Reproduces B13 and gives owner-level uncertainty |
| Policy B (conservative, three outcomes) | **Rejected** | Fails the pre-declared criterion; fails open under wrong evidence |
| A-nom (2% operating point) | **Not adopted; reported as a trade-off** | +21.5 points detection for +1.6 points benign exclusion and −16 correct answers on the 55 affected QA items |
| Any further B13 change | **None implemented** | No dev-owner failure that one change addresses |

## 7. Remaining limitations (not all blockers)

- **Ten owners from one dataset.** Owner-level intervals describe these owners.
- **Evidence dependence.** B13 needs the right owner's conversation. Evidence poisoning and mis-attribution are out of scope.
- **Ungrounded benign notes** (12–18% exclusion on HO4 and HO7) are an intrinsic cost of corroboration.
- **User-channel poisoning is not addressed.** MEM-1: 29 working, 0 excluded.
- **Deferral semantics** (whether "unverified" memories are prevented from driving actions) were not measured.
- **Instance-level working labels are probe- and judge-dependent.** Bounds: 435–944 of 2,628.
- **Human labels come from two people connected to the author**, and are used only for judge choice.
- **Paper compilation** still needs a TeX toolchain, which is your action.

## 8. Can the experimental programme be frozen?

**Yes.** The two targeted questions are answered:

- B13's calibration generalises across the available owners. Its weakness is evidence quality, and that is now measured.
- The validity conclusions survive both probes and both judges, with the probe leak located.

No further experiment is required for the claims as now written. What remains is outside experimentation:
- compile the paper;
- choose the licence and build the artifact repository;
- choose the venue.
