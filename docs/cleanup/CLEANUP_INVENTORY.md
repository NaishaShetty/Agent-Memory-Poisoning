# Cleanup inventory (2026-10-18) — classification only, nothing deleted or moved

Scope: every tracked or untracked documentation file (.md .docx .pdf .txt .tex .rst) outside vendored dataset candidates,
`phase3_reference/` and the protected `phase17/data/run_all_logs/`, plus two gitignored DOCX versions. `code refs` counts
source, test, workflow and Makefile files mentioning the file's basename (a deliberate over-count: it errs toward keeping).
No two files are byte-identical, and no Markdown pair shares more than half of its lines.

## Summary

| Classification | Files |
|---|---|
| MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | 270 |
| KEEP (essential artifact) | 92 |
| KEEP (essential artifact) + MERGE into comprehensive DOCX | 46 |
| NEEDS MANUAL REVIEW | 4 |
| ARCHIVE (historical evidence, kept in place) | 2 |
| RETAIN AS RESULTS ANALYSIS | 1 |
| RETAIN AS METHODOLOGY DRAFT | 1 |
| DELETE (verified redundant) | 1 |
| MERGE into comprehensive DOCX / NEEDS MANUAL REVIEW | 1 |

## Every file

| Path | Classification | Reason | Lines | Last change | Code refs | Test refs |
|---|---|---|---|---|---|---|
| `ANNOTATION_PROVENANCE_FINAL.md` | KEEP (essential artifact) + MERGE into comprehensive DOCX | live register / licensing and annotation provenance (legal) | 81 | 2026-10-13 | 2 | 0 |
| `ATTACK_VALIDITY_AND_CAUSALITY_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | defence-programme or remediation report (successive, non-duplicate); summarise, keep original | 187 | 2026-10-13 | 0 | 0 |
| `B13_IMPROVEMENT_COMPARISON.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | defence-programme or remediation report (successive, non-duplicate); summarise, keep original | 112 | 2026-10-13 | 0 | 0 |
| `B13_OWNER_GENERALISATION_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | defence-programme or remediation report (successive, non-duplicate); summarise, keep original; cited by code | 255 | 2026-10-13 | 1 | 0 |
| `CALIBRATION_AND_LEAKAGE_AUDIT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | defence-programme or remediation report (successive, non-duplicate); summarise, keep original | 108 | 2026-10-13 | 0 | 0 |
| `DATA_LICENSING_AND_ANNOTATION_AUDIT.md` | KEEP (essential artifact) + MERGE into comprehensive DOCX | live register / licensing and annotation provenance (legal) | 117 | 2026-10-13 | 1 | 0 |
| `DEFENCE_BASELINE_AND_ARCHITECTURE_AUDIT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | defence-programme or remediation report (successive, non-duplicate); summarise, keep original | 165 | 2026-10-13 | 0 | 0 |
| `DEFENCE_IMPROVEMENT_FINAL_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | defence-programme or remediation report (successive, non-duplicate); summarise, keep original | 128 | 2026-10-13 | 0 | 0 |
| `DEFENCE_V5_TARGETED_FIXES_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | defence-programme or remediation report (successive, non-duplicate); summarise, keep original | 95 | 2026-10-14 | 0 | 0 |
| `DEFENCE_V6_BASELINE_AND_ROOT_CAUSE_AUDIT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | defence-programme or remediation report (successive, non-duplicate); summarise, keep original | 89 | 2026-10-14 | 0 | 0 |
| `DEFENCE_V6_FINAL_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | defence-programme or remediation report (successive, non-duplicate); summarise, keep original | 162 | 2026-10-15 | 0 | 0 |
| `DEFENCE_V6_GAP_CLOSURE_ASSESSMENT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | defence-programme or remediation report (successive, non-duplicate); summarise, keep original | 97 | 2026-10-15 | 0 | 0 |
| `DEFENCE_V6_INTEGRATION_AND_ABLATION.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | defence-programme or remediation report (successive, non-duplicate); summarise, keep original | 68 | 2026-10-15 | 0 | 0 |
| `DEFENCE_V6_PROPAGATION_AND_LINEAGE_RECOVERY.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | defence-programme or remediation report (successive, non-duplicate); summarise, keep original | 130 | 2026-10-15 | 0 | 0 |
| `DEFENCE_V6_PROVENANCE_AND_GOVERNANCE.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | defence-programme or remediation report (successive, non-duplicate); summarise, keep original | 130 | 2026-10-15 | 0 | 0 |
| `DEFENCE_V6_SLEEPER_INFORMATION_BOUNDARY.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | defence-programme or remediation report (successive, non-duplicate); summarise, keep original | 146 | 2026-10-15 | 0 | 0 |
| `DEFENCE_V7_FINAL_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | defence-programme or remediation report (successive, non-duplicate); summarise, keep original | 83 | 2026-10-18 | 0 | 0 |
| `EXPERIMENTAL_VALIDITY_AUDIT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | defence-programme or remediation report (successive, non-duplicate); summarise, keep original | 201 | 2026-10-12 | 0 | 0 |
| `FINAL_DEFENCE_BASELINE_AUDIT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | defence-programme or remediation report (successive, non-duplicate); summarise, keep original; cited by code | 131 | 2026-10-13 | 5 | 0 |
| `FINAL_DEFENCE_IMPROVEMENT_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | defence-programme or remediation report (successive, non-duplicate); summarise, keep original | 156 | 2026-10-14 | 0 | 0 |
| `FINAL_GAP_CLOSURE_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | defence-programme or remediation report (successive, non-duplicate); summarise, keep original; cited by code | 145 | 2026-10-13 | 5 | 1 |
| `FINAL_REMEDIATION_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | defence-programme or remediation report (successive, non-duplicate); summarise, keep original | 183 | 2026-10-12 | 0 | 0 |
| `FINAL_SUBMISSION_READINESS_CHECKLIST.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | defence-programme or remediation report (successive, non-duplicate); summarise, keep original | 75 | 2026-10-13 | 0 | 0 |
| `FINAL_TARGETED_IMPROVEMENT_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | defence-programme or remediation report (successive, non-duplicate); summarise, keep original | 168 | 2026-10-13 | 0 | 0 |
| `IEEE_SUBMISSION_READINESS_CHECKLIST.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | defence-programme or remediation report (successive, non-duplicate); summarise, keep original | 75 | 2026-10-12 | 0 | 0 |
| `IMPLICIT_SLEEPER_DETECTION_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | defence-programme or remediation report (successive, non-duplicate); summarise, keep original | 121 | 2026-10-13 | 0 | 0 |
| `IMPLICIT_SLEEPER_FINAL_IMPROVEMENT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | defence-programme or remediation report (successive, non-duplicate); summarise, keep original | 95 | 2026-10-14 | 0 | 0 |
| `INTEGRATED_DEFENCE_ABLATION_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | defence-programme or remediation report (successive, non-duplicate); summarise, keep original | 111 | 2026-10-13 | 0 | 0 |
| `INTEGRATED_DEFENCE_FINAL_ABLATION.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | defence-programme or remediation report (successive, non-duplicate); summarise, keep original | 80 | 2026-10-14 | 0 | 0 |
| `MAMBench Results Analysis.docx` | RETAIN AS RESULTS ANALYSIS | latest authoritative results; generated by build_results_analysis_docx.py | 11021 | 2026-10-18 | 6 | 0 |
| `Methodology Draft.docx` | RETAIN AS METHODOLOGY DRAFT | latest authoritative methodology; regenerated by phase17 updaters; test-read | 52676 | 2026-10-18 | 22 | 1 |
| `Methodology.pdf` | ARCHIVE (historical evidence, kept in place) | August 2026 methodology export, described as preserved unmodified; superseded | 835 | 2026-08-25 | 2 | 0 |
| `NOVELTY_MATRIX.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | defence-programme or remediation report (successive, non-duplicate); summarise, keep original | 63 | 2026-10-13 | 0 | 0 |
| `PHASE5_HANDOFF_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | defence-programme or remediation report (successive, non-duplicate); summarise, keep original; cited by code | 278 | 2026-09-13 | 3 | 1 |
| `PHASE6_HANDOFF_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | defence-programme or remediation report (successive, non-duplicate); summarise, keep original | 284 | 2026-09-13 | 0 | 0 |
| `PROBE_AND_ATTACK_VALIDITY_FINAL.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | defence-programme or remediation report (successive, non-duplicate); summarise, keep original; cited by code | 202 | 2026-10-13 | 1 | 0 |
| `PROVENANCE_DEFENCE_FINAL_IMPROVEMENT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | defence-programme or remediation report (successive, non-duplicate); summarise, keep original | 96 | 2026-10-14 | 0 | 0 |
| `PROVENANCE_GOVERNANCE_IMPROVEMENT_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | defence-programme or remediation report (successive, non-duplicate); summarise, keep original | 100 | 2026-10-13 | 0 | 0 |
| `README.md` | KEEP (essential artifact) | navigation page (rewritten 2026-10-18) | 250 | 2026-10-09 | 26 | 6 |
| `REAL_MEMORY_PIPELINE_EVALUATION.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | defence-programme or remediation report (successive, non-duplicate); summarise, keep original; cited by code | 172 | 2026-10-13 | 1 | 0 |
| `RELATED_WORK_AND_NOVELTY.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | defence-programme or remediation report (successive, non-duplicate); summarise, keep original; cited by code | 254 | 2026-10-12 | 1 | 0 |
| `REMEDIATION_MASTER_REGISTER.md` | KEEP (essential artifact) + MERGE into comprehensive DOCX | live register / licensing and annotation provenance (legal) | 207 | 2026-10-18 | 4 | 1 |
| `RESEARCH_GAP_75_PERCENT_ASSESSMENT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | defence-programme or remediation report (successive, non-duplicate); summarise, keep original | 90 | 2026-10-14 | 0 | 0 |
| `RESEARCH_GAP_CLOSURE_ASSESSMENT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | defence-programme or remediation report (successive, non-duplicate); summarise, keep original | 69 | 2026-10-13 | 0 | 0 |
| `SELF_PROPAGATION_CONTAINMENT_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | defence-programme or remediation report (successive, non-duplicate); summarise, keep original | 118 | 2026-10-13 | 0 | 0 |
| `SELF_PROPAGATION_FINAL_IMPROVEMENT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | defence-programme or remediation report (successive, non-duplicate); summarise, keep original | 128 | 2026-10-14 | 0 | 0 |
| `STATISTICAL_VALIDITY_AUDIT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | defence-programme or remediation report (successive, non-duplicate); summarise, keep original | 68 | 2026-10-13 | 0 | 0 |
| `THREE_GAPS_FINAL_STATUS.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | defence-programme or remediation report (successive, non-duplicate); summarise, keep original | 133 | 2026-10-13 | 0 | 0 |
| `THREE_RESEARCH_GAPS_AUDIT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | defence-programme or remediation report (successive, non-duplicate); summarise, keep original | 284 | 2026-10-12 | 0 | 0 |
| `attribution/ATTRIBUTION_IMPLEMENTATION_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 199 | 2026-09-13 | 0 | 0 |
| `attribution/ATTRIBUTION_METHODOLOGY.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original; read by tests | 218 | 2026-09-13 | 7 | 1 |
| `docs/BENCHMARK_CARD.md` | KEEP (essential artifact) + MERGE into comprehensive DOCX | operational guide or benchmark specification cited by code, Makefile or tests | 239 | 2026-09-30 | 3 | 0 |
| `docs/METHODOLOGY.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original; read by tests | 301 | 2026-09-28 | 9 | 1 |
| `docs/PROJECT_STRUCTURE.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original; read by tests | 43 | 2026-09-28 | 1 | 1 |
| `docs/history/README_snapshots_through_2026-10-09.md` | ARCHIVE (historical evidence, kept in place) | pre-2026-10-18 README snapshots, verbatim | 304 | untracked | 0 | 0 |
| `docs/phase10/PHASE10_PLAN.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 231 | 2026-09-17 | 3 | 0 |
| `docs/phase10/PHASE10_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original; read by tests | 275 | 2026-09-17 | 5 | 1 |
| `docs/phase11/PHASE11_BLEND_WIRING_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 177 | 2026-10-18 | 3 | 0 |
| `docs/phase11/PHASE11_FARMA_AND_REAL_CORPUS_CALIBRATION_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 107 | 2026-09-21 | 0 | 0 |
| `docs/phase11/PHASE11_FINAL_GAP_CLOSURE_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original; read by tests | 233 | 2026-09-21 | 4 | 1 |
| `docs/phase11/PHASE11_FPR_MINIMIZATION_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 97 | 2026-09-21 | 0 | 0 |
| `docs/phase11/PHASE11_LOFO_AUDIT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original; read by tests | 376 | 2026-09-21 | 4 | 1 |
| `docs/phase11/PHASE11_LOFO_BASELINE_C_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 124 | 2026-09-21 | 3 | 0 |
| `docs/phase11/PHASE11_LOFO_FPR_AND_FARMA_FIX_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original; read by tests | 132 | 2026-09-21 | 7 | 1 |
| `docs/phase11/PHASE11_LOFO_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 195 | 2026-09-21 | 1 | 0 |
| `docs/phase11/PHASE11_LOFO_THRESHOLD_FIX_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 117 | 2026-09-21 | 1 | 0 |
| `docs/phase11/PHASE11_LOFO_WEIGHT_DECAY_SWEEP_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original; read by tests | 90 | 2026-09-21 | 3 | 1 |
| `docs/phase11/PHASE11_OUTSIDE_THE_BOX_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 115 | 2026-09-21 | 2 | 0 |
| `docs/phase11/PHASE11_PARAPHRASE_FIX_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original; read by tests | 156 | 2026-09-21 | 10 | 4 |
| `docs/phase11/PHASE11_PLAN.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 251 | 2026-09-21 | 1 | 0 |
| `docs/phase11/PHASE11_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 358 | 2026-09-21 | 4 | 0 |
| `docs/phase11/PHASE11_X_DATASET_AUDIT_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 484 | 2026-09-21 | 1 | 0 |
| `docs/phase11/PHASE11_X_OPTION2_EXPANDED_FEATURES_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 396 | 2026-09-21 | 4 | 0 |
| `docs/phase11/PHASE11_X_REDESIGN_DESIGN.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 476 | 2026-09-21 | 0 | 0 |
| `docs/phase11/PHASE11_X_TRACK_AB_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 416 | 2026-09-21 | 1 | 0 |
| `docs/phase11/PHASE11_Y_RELATIONAL_SIGNAL_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 367 | 2026-09-21 | 1 | 0 |
| `docs/phase11/PHASE11_Z_PLAN.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 186 | 2026-09-21 | 1 | 0 |
| `docs/phase11/PHASE11_Z_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 193 | 2026-09-21 | 0 | 0 |
| `docs/phase12/PHASE12_PLAN.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 187 | 2026-09-21 | 1 | 0 |
| `docs/phase12/PHASE12_SECURITY_METRICS_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original; read by tests | 575 | 2026-09-22 | 6 | 1 |
| `docs/phase13/PHASE13_ATTRIBUTION_METRICS_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 483 | 2026-09-22 | 3 | 0 |
| `docs/phase13/PHASE13_PLAN.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 105 | 2026-09-22 | 3 | 0 |
| `docs/phase14/PHASE14_PLAN.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 150 | 2026-09-24 | 2 | 0 |
| `docs/phase14/PHASE14_UTILITY_METRICS_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original; read by tests | 358 | 2026-09-24 | 3 | 1 |
| `docs/phase15/PHASE15_CROSS_CUTTING_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original; read by tests | 427 | 2026-09-24 | 3 | 1 |
| `docs/phase15/PHASE15_PLAN.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 177 | 2026-09-24 | 2 | 0 |
| `docs/phase16/PHASE16_SYNTHESIS_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 175 | 2026-09-27 | 1 | 0 |
| `docs/phase17/BENCHMARK_SPECIFICATION.md` | KEEP (essential artifact) + MERGE into comprehensive DOCX | operational guide or benchmark specification cited by code, Makefile or tests | 116 | 2026-09-27 | 2 | 0 |
| `docs/phase17/HANDOFF_CHECKLIST.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 106 | 2026-10-09 | 0 | 0 |
| `docs/phase17/HANDOFF_PROMPT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 171 | 2026-10-06 | 0 | 0 |
| `docs/phase17/HOLDOUT8_PLANNED_PREDICTIONS.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 42 | 2026-10-09 | 0 | 0 |
| `docs/phase17/PHASE17_ABLATION_GENERALIZATION_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 355 | 2026-09-28 | 0 | 0 |
| `docs/phase17/PHASE17_CURRENT_RESULTS.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original; read by tests | 690 | 2026-09-30 | 6 | 1 |
| `docs/phase17/PHASE17_FINAL_RESULTS.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original; read by tests | 390 | 2026-10-06 | 5 | 1 |
| `docs/phase17/PHASE17_GENERALIZATION_FIX_PLAN.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 15 | 2026-09-27 | 0 | 0 |
| `docs/phase17/PHASE17_PLAN.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 163 | 2026-09-27 | 7 | 0 |
| `docs/phase17/PHASE17_REVIEW4_RESULTS.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 559 | 2026-10-02 | 4 | 0 |
| `docs/phase17/PHASE17_ROUND3_FIXES.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 159 | 2026-09-28 | 0 | 0 |
| `docs/phase17/PHASE17_ROUND4_DEEPDIVE.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 133 | 2026-09-28 | 0 | 0 |
| `docs/phase17/PHASE17_ROUND5_FIXES.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original; read by tests | 108 | 2026-09-30 | 2 | 1 |
| `docs/phase17/PHASE17_ROUND5_RESULTS.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 406 | 2026-10-02 | 0 | 0 |
| `docs/phase17/PHASE17_WORKSTREAMS_FINAL_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 271 | 2026-09-28 | 0 | 0 |
| `docs/phase17/PREREGISTRATION_2_CALIBRATION.md` | KEEP (essential artifact) | pre-registration / freeze record: research-integrity evidence | 64 | 2026-10-06 | 4 | 0 |
| `docs/phase17/PREREGISTRATION_B13.md` | KEEP (essential artifact) | pre-registration / freeze record: research-integrity evidence | 120 | 2026-09-30 | 9 | 1 |
| `docs/phase17/PREREGISTRATION_DEFENCE_V2_2026-10-13.md` | KEEP (essential artifact) | pre-registration / freeze record: research-integrity evidence | 247 | 2026-10-13 | 9 | 0 |
| `docs/phase17/PREREGISTRATION_DEFENCE_V3_2026-10-13.md` | KEEP (essential artifact) | pre-registration / freeze record: research-integrity evidence | 164 | 2026-10-13 | 5 | 0 |
| `docs/phase17/PREREGISTRATION_DEFENCE_V4_2026-10-14.md` | KEEP (essential artifact) | pre-registration / freeze record: research-integrity evidence | 117 | 2026-10-14 | 4 | 0 |
| `docs/phase17/PREREGISTRATION_DEFENCE_V5_2026-10-14.md` | KEEP (essential artifact) | pre-registration / freeze record: research-integrity evidence | 209 | 2026-10-14 | 4 | 0 |
| `docs/phase17/PREREGISTRATION_DEFENCE_V6_2026-10-14.md` | KEEP (essential artifact) | pre-registration / freeze record: research-integrity evidence | 366 | 2026-10-15 | 6 | 0 |
| `docs/phase17/PREREGISTRATION_GAPCLOSURE_2026-10-13.md` | KEEP (essential artifact) | pre-registration / freeze record: research-integrity evidence | 184 | 2026-10-13 | 7 | 0 |
| `docs/phase17/PREREGISTRATION_HOLDOUT3.md` | KEEP (essential artifact) | pre-registration / freeze record: research-integrity evidence | 89 | 2026-10-04 | 8 | 1 |
| `docs/phase17/PREREGISTRATION_REMEDIATION_2026-10-12.md` | KEEP (essential artifact) | pre-registration / freeze record: research-integrity evidence | 139 | 2026-10-12 | 3 | 0 |
| `docs/phase17/PREREGISTRATION_ROUND7.md` | KEEP (essential artifact) | pre-registration / freeze record: research-integrity evidence | 307 | 2026-10-09 | 9 | 0 |
| `docs/phase17/PREREGISTRATION_TARGETED_2026-10-13.md` | KEEP (essential artifact) | pre-registration / freeze record: research-integrity evidence | 235 | 2026-10-13 | 4 | 0 |
| `docs/phase17/ROUND6_UNFAVOURABLE_RESOLUTION.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 94 | 2026-10-04 | 0 | 0 |
| `docs/phase17/ROUND7_LOG.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 885 | 2026-10-12 | 2 | 0 |
| `docs/phase17/ROUND7_RESULTS.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 66 | 2026-10-12 | 3 | 0 |
| `docs/phase17/v7/AUDIT_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 114 | 2026-10-18 | 1 | 0 |
| `docs/phase17/v7/EXPERIMENT_MATRIX.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 30 | 2026-10-18 | 1 | 0 |
| `docs/phase17/v7/FINAL_RESEARCH_ASSESSMENT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 153 | 2026-10-18 | 0 | 0 |
| `docs/phase17/v7/IMPLEMENTATION_NOTES.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original; read by tests | 79 | 2026-10-18 | 1 | 1 |
| `docs/phase17/v7/PROVENANCE_AND_SCOPE.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 34 | 2026-10-18 | 1 | 0 |
| `docs/phase17/v7/REPRODUCIBILITY.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 77 | 2026-10-18 | 1 | 0 |
| `docs/phase17/v7/RESULTS.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original; read by tests | 168 | 2026-10-18 | 17 | 3 |
| `docs/phase17/v7/RESUME_V7.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 59 | 2026-10-18 | 0 | 0 |
| `docs/phase17/v7/RUBRIC_MAPPING.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 50 | 2026-10-18 | 2 | 0 |
| `docs/phase17/v7/SA7_PREREGISTRATION.md` | KEEP (essential artifact) | pre-registration / freeze record: research-integrity evidence | 350 | 2026-10-18 | 14 | 0 |
| `docs/phase2/BENCHMARK_METADATA_AND_MANIFESTS.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 302 | 2026-08-25 | 2 | 0 |
| `docs/phase2/BENCHMARK_ORGANIZATION.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 321 | 2026-09-16 | 2 | 0 |
| `docs/phase2/BENCHMARK_SUBSTRATE_VALIDATION.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 245 | 2026-08-25 | 1 | 0 |
| `docs/phase2/DATA_BOUNDARY.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original; read by tests | 121 | 2026-08-25 | 1 | 1 |
| `docs/phase2/DATA_VERSIONING_POLICY.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original; read by tests | 82 | 2026-08-25 | 1 | 1 |
| `docs/phase2/DSRM_RESOLUTION.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 154 | 2026-08-25 | 0 | 0 |
| `docs/phase2/ISSUES_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 91 | 2026-08-25 | 0 | 0 |
| `docs/phase2/LOCOMO_QA_RECONCILIATION.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 179 | 2026-08-25 | 1 | 0 |
| `docs/phase2/LONGMEMEVAL_PROVENANCE_CASE_STUDY.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 202 | 2026-08-25 | 1 | 0 |
| `docs/phase2/PHASE2_2_VALIDATION_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 95 | 2026-08-25 | 0 | 0 |
| `docs/phase2/PHASE2_7_COMPLETION_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 184 | 2026-08-25 | 0 | 0 |
| `docs/phase2/PHASE2_FREEZE.md` | KEEP (essential artifact) | pre-registration / freeze record: research-integrity evidence | 258 | 2026-08-25 | 1 | 0 |
| `docs/phase2/PROVENANCE_TRACE.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 134 | 2026-08-25 | 0 | 0 |
| `docs/phase2/REPRODUCIBILITY_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 103 | 2026-08-25 | 1 | 0 |
| `docs/phase2/TEMPORAL_NORMALIZATION.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 293 | 2026-08-25 | 5 | 0 |
| `docs/phase2/UNIFIED_MEMORY_RECORD.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 271 | 2026-08-25 | 3 | 0 |
| `docs/phase2/UNIFIED_MEMORY_RECORD_EXAMPLES.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 198 | 2026-08-25 | 0 | 0 |
| `docs/phase2/VALIDATION_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 50 | 2026-08-25 | 0 | 0 |
| `docs/phase4/SLEEPER_RESOURCE_PROVENANCE_RECONCILIATION.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 115 | 2026-09-16 | 0 | 0 |
| `docs/phase6/ADAPTIVE_ATTACKER_EVALUATION.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original; read by tests | 148 | 2026-09-16 | 2 | 1 |
| `docs/phase6/ADAPTIVE_ATTACKER_KNOWLEDGE.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 76 | 2026-09-16 | 3 | 0 |
| `docs/phase6/ADMISSION_DEFENSE.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 95 | 2026-09-16 | 1 | 0 |
| `docs/phase6/BENIGN_UTILITY_AND_REGRESSION.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 146 | 2026-09-16 | 1 | 0 |
| `docs/phase6/CROSS_ATTACK_GENERALIZATION.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original; read by tests | 145 | 2026-09-16 | 2 | 1 |
| `docs/phase6/DEFENSE_ATTRIBUTION_INTEGRATION.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 109 | 2026-09-16 | 0 | 0 |
| `docs/phase6/DEFENSE_COMPARISON_MATRIX.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 35 | 2026-09-16 | 0 | 0 |
| `docs/phase6/DEFENSE_COMPOSITION_AND_ABLATION.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 302 | 2026-09-17 | 7 | 0 |
| `docs/phase6/DEFENSE_FAILURE_ANALYSIS.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 133 | 2026-09-16 | 0 | 0 |
| `docs/phase6/DEFENSE_GAP_ANALYSIS.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 126 | 2026-09-16 | 0 | 0 |
| `docs/phase6/DEFENSE_LITERATURE_AUDIT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 236 | 2026-09-16 | 3 | 0 |
| `docs/phase6/DEFENSE_SCOPE_MATRIX.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 83 | 2026-09-16 | 1 | 0 |
| `docs/phase6/DEFENSE_SIGNAL_CONTRACT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 187 | 2026-09-16 | 3 | 0 |
| `docs/phase6/DEFENSE_THREAT_MODEL.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 111 | 2026-09-16 | 1 | 0 |
| `docs/phase6/EVALUATION_PROTOCOL.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 156 | 2026-09-16 | 1 | 0 |
| `docs/phase6/MEMORY_FOUNDATION_GENERALIZATION.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 136 | 2026-09-16 | 0 | 0 |
| `docs/phase6/MEMORY_GOVERNANCE_POLICY.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original; read by tests | 234 | 2026-09-16 | 5 | 1 |
| `docs/phase6/PHASE6_CHARTER.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 180 | 2026-09-16 | 0 | 0 |
| `docs/phase6/PHASE6_CHECKLIST.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 59 | 2026-09-16 | 0 | 0 |
| `docs/phase6/PHASE6_FREEZE.md` | KEEP (essential artifact) | pre-registration / freeze record: research-integrity evidence | 109 | 2026-09-16 | 0 | 0 |
| `docs/phase6/PHASE6_LIMITATIONS.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 55 | 2026-09-16 | 0 | 0 |
| `docs/phase6/PHASE6_RESULTS.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original; read by tests | 325 | 2026-09-17 | 1 | 1 |
| `docs/phase6/PROPAGATION_CONTAINMENT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 117 | 2026-09-16 | 1 | 0 |
| `docs/phase6/REPRODUCIBILITY_AND_ARTIFACTS.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 123 | 2026-09-16 | 0 | 0 |
| `docs/phase6/RETRIEVAL_DEFENSE.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 279 | 2026-09-17 | 3 | 0 |
| `docs/phase6/SEVEN_ATTACK_DEFENSE_INTEGRATION.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 178 | 2026-09-16 | 2 | 0 |
| `docs/phase6/SLEEPER_DEFENSE.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original; read by tests | 220 | 2026-09-17 | 9 | 2 |
| `docs/phase6/STAGE_6_9_QUEUE.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 197 | 2026-09-17 | 2 | 0 |
| `docs/phase6/STATISTICAL_PROTOCOL.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 226 | 2026-09-16 | 0 | 0 |
| `docs/phase7/PHASE7_PLAN.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 239 | 2026-09-17 | 2 | 0 |
| `docs/phase7/PHASE7_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original; read by tests | 814 | 2026-09-17 | 5 | 1 |
| `docs/phase8/PHASE8_PLAN.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original; read by tests | 310 | 2026-09-17 | 8 | 1 |
| `docs/phase8/PHASE8_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 489 | 2026-09-17 | 0 | 0 |
| `docs/phase9/PHASE9_PLAN.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 235 | 2026-09-17 | 0 | 0 |
| `docs/phase9/PHASE9_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 273 | 2026-09-17 | 0 | 0 |
| `docs/release/LICENSING_AND_DATA_RIGHTS.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 42 | 2026-10-12 | 0 | 0 |
| `docs/release/REPRODUCE.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 88 | 2026-10-12 | 0 | 0 |
| `docs/review/INDEPENDENT_IEEE_REVIEW_2026-10-12.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 613 | 2026-10-12 | 2 | 0 |
| `meth_extract.txt` | DELETE (verified redundant) | plain-text extract of an older Methodology (2026-10-05); unreferenced; full content is in the DOCX and git history | 1204 | 2026-10-05 | 0 | 0 |
| `paper/SUPPLEMENTARY.md` | KEEP (essential artifact) | manuscript sources; numbers.tex is generated and test-checked | 18 | 2026-10-12 | 0 | 0 |
| `paper/main.tex` | KEEP (essential artifact) | manuscript sources; numbers.tex is generated and test-checked | 129 | 2026-10-13 | 1 | 1 |
| `paper/numbers.tex` | KEEP (essential artifact) | manuscript sources; numbers.tex is generated and test-checked | 110 | 2026-10-13 | 3 | 1 |
| `paper/tab_decomp.tex` | KEEP (essential artifact) | manuscript sources; numbers.tex is generated and test-checked | 9 | 2026-10-12 | 2 | 0 |
| `paper/tab_mp.tex` | KEEP (essential artifact) | manuscript sources; numbers.tex is generated and test-checked | 10 | 2026-10-12 | 2 | 0 |
| `paper/tab_twoden.tex` | KEEP (essential artifact) | manuscript sources; numbers.tex is generated and test-checked | 8 | 2026-10-12 | 2 | 0 |
| `phase17/ISOLATED_ENVIRONMENTS.md` | KEEP (essential artifact) + MERGE into comprehensive DOCX | operational guide or benchmark specification cited by code, Makefile or tests | 69 | 2026-09-28 | 2 | 1 |
| `phase17/OLLAMA_MODEL_PINS.md` | KEEP (essential artifact) + MERGE into comprehensive DOCX | operational guide or benchmark specification cited by code, Makefile or tests | 53 | 2026-10-12 | 2 | 1 |
| `phase17/RESUME_AFTER_SHUTDOWN.md` | KEEP (essential artifact) + MERGE into comprehensive DOCX | operational guide or benchmark specification cited by code, Makefile or tests | 93 | 2026-10-08 | 3 | 1 |
| `phase17/RUNNING_THE_PIPELINE.md` | KEEP (essential artifact) + MERGE into comprehensive DOCX | operational guide or benchmark specification cited by code, Makefile or tests | 129 | 2026-10-08 | 3 | 0 |
| `phase17/data/HUMAN_EVAL_INSTRUCTIONS.md` | KEEP (essential artifact) | instructions given to the human annotators: annotation provenance | 29 | 2026-09-27 | 2 | 0 |
| `phase17/data/_phase_audit.txt` | KEEP (essential artifact) | experiment output / audit log | 248 | 2026-10-12 | 4 | 1 |
| `phase17/data/_phase_audit2.txt` | KEEP (essential artifact) | experiment output / audit log | 21 | 2026-10-05 | 2 | 0 |
| `phase17/data/security_utility_frontier.md` | KEEP (essential artifact) | generated result table (phase17/security_utility_frontier.py) | 7 | 2026-09-27 | 1 | 0 |
| `phase3/PHASE3_COMPLETE_HISTORY_AND_ARCHIVE.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 266 | 2026-09-10 | 0 | 0 |
| `phase3/README.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original; read by tests | 121 | 2026-09-10 | 26 | 6 |
| `phase3/contracts/CLEAN_AGENT_INTERFACES.md` | KEEP (essential artifact) + MERGE into comprehensive DOCX | specification of the frozen victim architecture | 100 | 2026-08-31 | 4 | 0 |
| `phase3/contracts/EVALUATION_CONTRACT.md` | KEEP (essential artifact) + MERGE into comprehensive DOCX | specification of the frozen victim architecture | 105 | 2026-08-31 | 13 | 1 |
| `phase3/contracts/LEAKAGE_AND_VISIBILITY_CONTRACT.md` | KEEP (essential artifact) + MERGE into comprehensive DOCX | specification of the frozen victim architecture | 66 | 2026-08-31 | 5 | 1 |
| `phase3/contracts/REPRODUCIBILITY_CONTRACT.md` | KEEP (essential artifact) + MERGE into comprehensive DOCX | specification of the frozen victim architecture | 65 | 2026-08-31 | 4 | 0 |
| `phase3/contracts/TRACEABILITY_CONTRACT.md` | KEEP (essential artifact) + MERGE into comprehensive DOCX | specification of the frozen victim architecture | 102 | 2026-08-31 | 1 | 0 |
| `phase3/evaluation/AUDIT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original; read by tests | 567 | 2026-08-26 | 17 | 1 |
| `phase3/evaluation/PHASE3_2_FINAL_VALIDATION.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 548 | 2026-08-31 | 0 | 0 |
| `phase3/evaluation/README.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original; read by tests | 205 | 2026-08-26 | 26 | 6 |
| `phase3/evaluation/agent/README.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original; read by tests | 238 | 2026-08-26 | 26 | 6 |
| `phase3/evaluation/datasets/PHASE3_2_H2_CANDIDATE_DECISION.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 649 | 2026-08-31 | 0 | 0 |
| `phase3/evaluation/datasets/PHASE3_2_H4_DATASET_FOUNDATION_CONFORMANCE.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original; read by tests | 483 | 2026-08-31 | 3 | 1 |
| `phase3/evaluation/datasets/PHASE3_2_H5_CANDIDATE_ACCOMMODATION.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 310 | 2026-08-31 | 0 | 0 |
| `phase3/evaluation/datasets/PHASE3_2_J1_CONVOMEM_PERLTQA_SCREENING.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 394 | 2026-08-31 | 0 | 0 |
| `phase3/evaluation/datasets/PHASE3_2_J2_CONVOMEM_FEASIBILITY.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original; read by tests | 323 | 2026-08-31 | 1 | 1 |
| `phase3/evaluation/datasets/PHASE3_2_J3_INTEGRATION_AND_FINAL_REVALIDATION.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 278 | 2026-08-31 | 0 | 0 |
| `phase3/evaluation/datasets/README.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original; read by tests | 226 | 2026-08-26 | 26 | 6 |
| `phase3/evaluation/extensions/PHASE3_2_H3_FRAMEWORK_AND_FOUNDATION_EXTENSION_SPEC.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 320 | 2026-08-31 | 2 | 0 |
| `phase3/evaluation/extensions/PHASE3_2_H3_FRAMEWORK_EXTENSION_SPEC.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 284 | 2026-08-31 | 5 | 0 |
| `phase3/evaluation/foundations_real/h4venv_lockfile_2026-09-12.txt` | KEEP (essential artifact) | experiment output / audit log | 142 | 2026-09-13 | 0 | 0 |
| `phase3/evaluation/foundations_real/main_repo_lockfile_2026-09-12.txt` | KEEP (essential artifact) | experiment output / audit log | 34 | 2026-09-13 | 0 | 0 |
| `phase3/evaluation/integration/README.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original; read by tests | 260 | 2026-08-28 | 26 | 6 |
| `phase3/evaluation/metrics/README.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original; read by tests | 635 | 2026-08-26 | 26 | 6 |
| `phase3/evaluation/security/README.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original; read by tests | 308 | 2026-08-26 | 26 | 6 |
| `phase3/experiments/PHASE3_3_7_FREEZE_CERTIFICATION.md` | KEEP (essential artifact) | pre-registration / freeze record: research-integrity evidence | 108 | 2026-09-07 | 0 | 0 |
| `phase3/experiments/PHASE3_3_DATASET_FULL_120x2_COMPLETION_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original; read by tests | 115 | 2026-09-07 | 2 | 1 |
| `phase3/experiments/PHASE3_3_DATASET_PILOT_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 96 | 2026-09-07 | 0 | 0 |
| `phase3/experiments/PHASE3_3_FOUNDATION_STRENGTHENING_FIVE_CONCERNS_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 161 | 2026-09-07 | 0 | 0 |
| `phase3/experiments/PHASE3_3_G1_AMEM_LONGMEMEVAL_COMPLETION.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 280 | 2026-09-04 | 1 | 0 |
| `phase3/experiments/PHASE3_3_G_FORMAL_CAMPAIGN_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original; read by tests | 344 | 2026-09-04 | 3 | 1 |
| `phase3/experiments/PHASE3_3_H1_IMPLEMENTATION_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 163 | 2026-09-04 | 1 | 0 |
| `phase3/experiments/PHASE3_3_H2_IMPLEMENTATION_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 139 | 2026-09-04 | 0 | 0 |
| `phase3/experiments/PHASE3_3_H2_R2_FINAL_HARDENING_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 177 | 2026-09-04 | 0 | 0 |
| `phase3/experiments/PHASE3_3_H2_REMEDIATION_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 217 | 2026-09-04 | 0 | 0 |
| `phase3/experiments/PHASE3_3_H3_IMPLEMENTATION_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 219 | 2026-09-04 | 0 | 0 |
| `phase3/experiments/PHASE3_3_H3_R2_IMPLEMENTATION_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 143 | 2026-09-06 | 1 | 0 |
| `phase3/experiments/PHASE3_3_H3_R_IMPLEMENTATION_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original; read by tests | 179 | 2026-09-06 | 2 | 1 |
| `phase3/experiments/PHASE3_3_H4_AMEM_INSPECT_FIX_IMPLEMENTATION_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 60 | 2026-09-07 | 0 | 0 |
| `phase3/experiments/PHASE3_3_H4_A_IMPLEMENTATION_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 194 | 2026-09-06 | 0 | 0 |
| `phase3/experiments/PHASE3_3_H4_A_LOCOMO_AMEM_RUN_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 127 | 2026-09-07 | 0 | 0 |
| `phase3/experiments/PHASE3_3_H4_A_LOCOMO_N20_RUN_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 55 | 2026-09-07 | 0 | 0 |
| `phase3/experiments/PHASE3_3_H4_A_LOCOMO_SAMPLE_RUN_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original; read by tests | 101 | 2026-09-07 | 1 | 1 |
| `phase3/experiments/PHASE3_3_H4_A_RUN_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 130 | 2026-09-07 | 0 | 0 |
| `phase3/experiments/PHASE3_3_H4_BC_IMPLEMENTATION_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 140 | 2026-09-06 | 0 | 0 |
| `phase3/experiments/PHASE3_3_H4_CONTENT_LEAKAGE_WIRE_IMPLEMENTATION_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 74 | 2026-09-07 | 0 | 0 |
| `phase3/experiments/PHASE3_3_H4_D_A_RUN_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original; read by tests | 66 | 2026-09-07 | 1 | 1 |
| `phase3/experiments/PHASE3_3_H4_D_IMPLEMENTATION_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 205 | 2026-09-06 | 1 | 0 |
| `phase3/experiments/PHASE3_3_H4_D_RUN_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 137 | 2026-09-07 | 0 | 0 |
| `phase3/experiments/PHASE3_3_H4_ENVIRONMENT_RECORD_IMPLEMENTATION_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 85 | 2026-09-07 | 0 | 0 |
| `phase3/experiments/PHASE3_3_H4_E_IMPLEMENTATION_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 176 | 2026-09-06 | 1 | 0 |
| `phase3/experiments/PHASE3_3_H4_F_IMPLEMENTATION_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 175 | 2026-09-06 | 0 | 0 |
| `phase3/experiments/PHASE3_3_H4_G_IMPLEMENTATION_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 150 | 2026-09-06 | 0 | 0 |
| `phase3/experiments/PHASE3_3_H4_MULTI_BOUNDARY_REAL_DEMONSTRATION_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 57 | 2026-09-07 | 0 | 0 |
| `phase3/experiments/PHASE3_3_H4_PROVENANCE_GRAPH_EXTENSION_IMPLEMENTATION_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 76 | 2026-09-07 | 0 | 0 |
| `phase3/experiments/PHASE3_3_H4_PROVENANCE_GRAPH_IMPLEMENTATION_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 97 | 2026-09-07 | 0 | 0 |
| `phase3/experiments/PHASE3_3_H4_READINESS_ASSESSMENT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 178 | 2026-09-07 | 0 | 0 |
| `phase3/experiments/PHASE3_3_H4_REFERENCE_AGENT_AND_PORTABILITY_IMPLEMENTATION_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 66 | 2026-09-07 | 0 | 0 |
| `phase3/experiments/PHASE3_3_H4_WIRE_C_IMPLEMENTATION_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 98 | 2026-09-07 | 1 | 0 |
| `phase3/experiments/PHASE3_3_H4_WIRE_IMPLEMENTATION_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original; read by tests | 249 | 2026-09-07 | 2 | 1 |
| `phase3/experiments/PHASE3_3_SELECTION_AND_CREATION_POLICY_IMPLEMENTATION_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 79 | 2026-09-07 | 0 | 0 |
| `phase3/experiments/PHASE3_3_SELECTION_POLICY_VARIANT_120x2_COMPLETION_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 97 | 2026-09-07 | 0 | 0 |
| `phase3/experiments/PHASE3_FINAL_FREEZE_AND_CERTIFICATION_REPORT.md` | KEEP (essential artifact) | pre-registration / freeze record: research-integrity evidence | 342 | 2026-09-07 | 0 | 0 |
| `phase3/experiments/PHASE3_FINAL_STATUS_DONE_NOT_DONE.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 175 | 2026-09-07 | 2 | 0 |
| `phase3/experiments/PHASE3_REFERENCE_SEGREGATION_AUDIT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 136 | 2026-09-07 | 0 | 0 |
| `phase3/experiments/PHASE3_REPOSITORY_CLEANUP_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 133 | 2026-09-07 | 0 | 0 |
| `phase3/experiments/PHASE3_RESEARCH_TRACK_RELATIONSHIP_DETECTION_QUALIFICATION.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 437 | 2026-09-07 | 1 | 0 |
| `phase3/experiments/PHASE3_SELECTION_FINAL_DIAGNOSTIC.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 129 | 2026-09-07 | 0 | 0 |
| `phase3/experiments/PHASE4_4_10_CROSS_ATTACK_VALIDATION.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 149 | 2026-09-12 | 0 | 0 |
| `phase3/experiments/PHASE4_4_11_PHASE4_REPRODUCIBILITY.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 169 | 2026-09-12 | 1 | 0 |
| `phase3/experiments/PHASE4_4_12_PHASE4_FREEZE.md` | KEEP (essential artifact) | pre-registration / freeze record: research-integrity evidence | 186 | 2026-09-12 | 0 | 0 |
| `phase3/experiments/PHASE4_4_1_AGENTPOISON_DOSSIER.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 227 | 2026-09-12 | 2 | 0 |
| `phase3/experiments/PHASE4_4_1_DSRM_DOSSIER.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 331 | 2026-09-12 | 0 | 0 |
| `phase3/experiments/PHASE4_4_1_FARMA_DOSSIER.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 257 | 2026-09-12 | 0 | 0 |
| `phase3/experiments/PHASE4_4_1_MEMORYGRAFT_DOSSIER.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 285 | 2026-09-12 | 3 | 0 |
| `phase3/experiments/PHASE4_4_1_MINJA_DOSSIER.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 197 | 2026-09-12 | 1 | 0 |
| `phase3/experiments/PHASE4_4_1_MPBENCH_DOSSIER.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 338 | 2026-09-12 | 0 | 0 |
| `phase3/experiments/PHASE4_4_1_SLEEPER_MEMORY_POISONING_DOSSIER.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 338 | 2026-09-12 | 1 | 0 |
| `phase3/experiments/PHASE4_4_1_SYNTHESIS.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 220 | 2026-09-12 | 0 | 0 |
| `phase3/experiments/PHASE4_4_2_COMMON_ATTACK_CONTRACT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 844 | 2026-09-12 | 13 | 0 |
| `phase3/experiments/PHASE4_4_2_V3HYBRID_EXTENDED_ARCHITECTURE_REVIEW.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 307 | 2026-09-12 | 1 | 0 |
| `phase3/experiments/PHASE4_4_3_AGENTPOISON_INTEGRATION_PLAN.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 482 | 2026-09-12 | 2 | 0 |
| `phase3/experiments/PHASE4_4_3_MEMORYGRAFT_INTEGRATION_PLAN.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 361 | 2026-09-12 | 2 | 0 |
| `phase3/experiments/PHASE4_4_3_MINJA_INTEGRATION_PLAN.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 282 | 2026-09-12 | 3 | 0 |
| `phase3/experiments/PHASE4_4_3_SLEEPER_MEMORY_POISONING_INTEGRATION_PLAN.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 251 | 2026-09-12 | 2 | 0 |
| `phase3/experiments/PHASE4_4_4_DSRM_RECONSTRUCTION_PLAN.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 407 | 2026-09-12 | 5 | 0 |
| `phase3/experiments/PHASE4_4_4_FARMA_RECONSTRUCTION_PLAN.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 504 | 2026-09-12 | 7 | 0 |
| `phase3/experiments/PHASE4_4_5_MPBENCH_INTEGRATION_PLAN.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 388 | 2026-09-12 | 3 | 0 |
| `phase3/experiments/PHASE4_4_6_POISON_ARTIFACT_AND_INJECTION_MODEL.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 206 | 2026-09-12 | 2 | 0 |
| `phase3/experiments/PHASE4_4_7_ATTACK_PHASE3_INTEGRATION.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 174 | 2026-09-12 | 1 | 0 |
| `phase3/experiments/PHASE4_4_8_CONTROLLED_ATTACK_CAMPAIGNS.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 234 | 2026-09-12 | 0 | 0 |
| `phase3/experiments/PHASE4_4_8_SLEEPER_MEMORY_POISONING_CAMPAIGN.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 147 | 2026-09-12 | 1 | 0 |
| `phase3/experiments/PHASE4_4_9_ATTACK_GROUND_TRUTH.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original; read by tests | 305 | 2026-09-16 | 7 | 2 |
| `phase3/experiments/PHASE4_CROSS_ATTACK_ARCHITECTURE_REVIEW.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 436 | 2026-09-12 | 0 | 0 |
| `phase3/experiments/PHASE4_HANDOFF_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 257 | 2026-09-10 | 0 | 0 |
| `phase3/experiments/PHASE4_MPBENCH_SCOPE_AND_PRIORITY_POLICY.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 311 | 2026-09-12 | 0 | 0 |
| `phase3/experiments/PHASE4_PRE_FLIGHT_DECISIONS.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 166 | 2026-09-12 | 10 | 0 |
| `phase3/experiments/research_variant/PHASE3_RESEARCH_IMPROVEMENT_PLAN.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 770 | 2026-09-10 | 7 | 0 |
| `phase3/experiments/research_variant/PHASE3_V2_FINAL_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 174 | 2026-09-10 | 0 | 0 |
| `phase3/experiments/research_variant/PHASE3_V2_VALIDATION_FINALIZATION_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 133 | 2026-09-10 | 1 | 0 |
| `phase3/experiments/research_variant/PHASE3_V3_DIAGNOSIS_AND_ROADMAP.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original; read by tests | 418 | 2026-09-10 | 3 | 1 |
| `phase3/experiments/research_variant/PHASE3_V3_FULL_SCALE_VALIDATION_REPORT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 102 | 2026-09-10 | 0 | 0 |
| `phase3/experiments/research_variant/PHASE3_V3_ROUND1_TEMPORAL_RESOLUTION_PILOT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 73 | 2026-09-10 | 1 | 0 |
| `phase3/experiments/research_variant/PHASE3_V3_ROUND2_TEMPORAL_RESOLUTION_FULL_CATEGORY2.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 89 | 2026-09-10 | 0 | 0 |
| `phase3/experiments/research_variant/PHASE3_V3_ROUND3_TEMPORAL_RESOLUTION_CONDITION_C.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 67 | 2026-09-10 | 0 | 0 |
| `phase3/experiments/research_variant/PHASE3_V4_DIAGNOSIS_AND_85_90_ROADMAP.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original; read by tests | 534 | 2026-09-10 | 4 | 1 |
| `phase3/experiments/research_variant/PHASE3_V5_ARCHITECTURE.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 156 | 2026-09-10 | 1 | 0 |
| `phase3/experiments/research_variant/PHASE3_V5_DESIGN_RATIONALE.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 142 | 2026-09-10 | 5 | 0 |
| `phase3/experiments/research_variant/PHASE3_V5_EXPERIMENT_PLAN.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 104 | 2026-09-10 | 4 | 0 |
| `phase3/schemas/memory_schema.md` | KEEP (essential artifact) + MERGE into comprehensive DOCX | specification of the frozen victim architecture | 143 | 2026-08-31 | 8 | 1 |
| `phase3/schemas/relationship_schema.md` | KEEP (essential artifact) + MERGE into comprehensive DOCX | specification of the frozen victim architecture | 167 | 2026-09-06 | 13 | 2 |
| `phase3/specification/DATASET_CAPABILITY_MATRIX.md` | KEEP (essential artifact) + MERGE into comprehensive DOCX | specification of the frozen victim architecture | 72 | 2026-08-31 | 4 | 0 |
| `phase3/specification/EXPERIMENT_GOVERNANCE.md` | KEEP (essential artifact) + MERGE into comprehensive DOCX | specification of the frozen victim architecture | 85 | 2026-08-31 | 0 | 0 |
| `phase3/specification/MEMORY_FOUNDATION_STRENGTHENING_PLAN.md` | KEEP (essential artifact) + MERGE into comprehensive DOCX | specification of the frozen victim architecture | 316 | 2026-09-06 | 0 | 0 |
| `phase3/specification/MEMORY_FOUNDATION_STRENGTHENING_PLAN_REVISED.md` | KEEP (essential artifact) + MERGE into comprehensive DOCX | specification of the frozen victim architecture | 612 | 2026-09-06 | 3 | 0 |
| `phase3/specification/PHASE3_3_B0_LLM_FEASIBILITY.md` | KEEP (essential artifact) + MERGE into comprehensive DOCX | specification of the frozen victim architecture | 356 | 2026-09-01 | 4 | 1 |
| `phase3/specification/PHASE3_3_EXPERIMENTAL_SPEC.md` | KEEP (essential artifact) + MERGE into comprehensive DOCX | specification of the frozen victim architecture | 872 | 2026-09-01 | 9 | 1 |
| `phase3/specification/PHASE3_3_F1_F2_SECONDARY_DATASET_TEMPORAL_DIAGNOSTIC.md` | KEEP (essential artifact) + MERGE into comprehensive DOCX | specification of the frozen victim architecture | 247 | 2026-09-01 | 0 | 0 |
| `phase3/specification/PHASE3_3_F_PRECAMPAIGN_METHODOLOGY.md` | KEEP (essential artifact) + MERGE into comprehensive DOCX | specification of the frozen victim architecture | 369 | 2026-09-01 | 2 | 0 |
| `phase3/specification/PHASE3_3_H1_CANONICAL_MEMORY_LEDGER.md` | KEEP (essential artifact) + MERGE into comprehensive DOCX | specification of the frozen victim architecture | 340 | 2026-09-04 | 3 | 0 |
| `phase3/specification/PHASE3_3_H2_CANONICAL_EVENT_LEDGER.md` | KEEP (essential artifact) + MERGE into comprehensive DOCX | specification of the frozen victim architecture | 644 | 2026-09-04 | 4 | 1 |
| `phase3/specification/PHASE3_3_H3_MEMORY_VERSIONING.md` | KEEP (essential artifact) + MERGE into comprehensive DOCX | specification of the frozen victim architecture | 346 | 2026-09-04 | 1 | 1 |
| `phase3/specification/PHASE3_3_H3_R2_MISSION.md` | KEEP (essential artifact) + MERGE into comprehensive DOCX | specification of the frozen victim architecture | 183 | 2026-09-06 | 0 | 0 |
| `phase3/specification/PHASE3_3_H3_R_MISSION.md` | KEEP (essential artifact) + MERGE into comprehensive DOCX | specification of the frozen victim architecture | 204 | 2026-09-06 | 0 | 0 |
| `phase3/specification/PHASE3_3_H4_AMEM_INSPECT_FIX_MISSION.md` | KEEP (essential artifact) + MERGE into comprehensive DOCX | specification of the frozen victim architecture | 158 | 2026-09-07 | 0 | 0 |
| `phase3/specification/PHASE3_3_H4_A_MISSION.md` | KEEP (essential artifact) + MERGE into comprehensive DOCX | specification of the frozen victim architecture | 317 | 2026-09-06 | 1 | 1 |
| `phase3/specification/PHASE3_3_H4_BC_MISSION.md` | KEEP (essential artifact) + MERGE into comprehensive DOCX | specification of the frozen victim architecture | 233 | 2026-09-06 | 1 | 1 |
| `phase3/specification/PHASE3_3_H4_D_MISSION.md` | KEEP (essential artifact) + MERGE into comprehensive DOCX | specification of the frozen victim architecture | 262 | 2026-09-06 | 1 | 1 |
| `phase3/specification/PHASE3_3_H4_E_MISSION.md` | KEEP (essential artifact) + MERGE into comprehensive DOCX | specification of the frozen victim architecture | 260 | 2026-09-06 | 1 | 1 |
| `phase3/specification/PHASE3_3_H4_F_MISSION.md` | KEEP (essential artifact) + MERGE into comprehensive DOCX | specification of the frozen victim architecture | 277 | 2026-09-06 | 1 | 1 |
| `phase3/specification/PHASE3_3_H4_G_MISSION.md` | KEEP (essential artifact) + MERGE into comprehensive DOCX | specification of the frozen victim architecture | 220 | 2026-09-06 | 1 | 1 |
| `phase3/specification/PHASE3_3_H4_WIRE_MISSION.md` | KEEP (essential artifact) + MERGE into comprehensive DOCX | specification of the frozen victim architecture | 242 | 2026-09-07 | 0 | 0 |
| `phase3/specification/PHASE3_ACTIVE_CLEAN_BASELINE_CLARIFICATION.md` | KEEP (essential artifact) + MERGE into comprehensive DOCX | specification of the frozen victim architecture | 61 | 2026-09-07 | 0 | 0 |
| `phase3/specification/PHASE3_ACTIVE_FOUNDATION_SCOPE.md` | KEEP (essential artifact) + MERGE into comprehensive DOCX | specification of the frozen victim architecture | 59 | 2026-09-07 | 0 | 0 |
| `phase3/specification/PHASE3_CLEAN_AGENT_FOUNDATION_SPEC.md` | KEEP (essential artifact) + MERGE into comprehensive DOCX | specification of the frozen victim architecture | 358 | 2026-08-31 | 5 | 0 |
| `phase3/specification/PHASE3_CLEAN_DATASET_CONSTRUCTION_PLAN.md` | KEEP (essential artifact) + MERGE into comprehensive DOCX | specification of the frozen victim architecture | 133 | 2026-09-07 | 2 | 0 |
| `phase3/specification/PHASE3_EQUIVALENT_CONFLICTS_DESIGN_CALIBRATION.md` | KEEP (essential artifact) + MERGE into comprehensive DOCX | specification of the frozen victim architecture | 401 | 2026-09-07 | 1 | 0 |
| `phase3/specification/PHASE3_FREEZE_GATE.md` | KEEP (essential artifact) | pre-registration / freeze record: research-integrity evidence | 79 | 2026-08-31 | 0 | 0 |
| `phase3/specification/PHASE3_PROVENANCE_GRAPH_DESIGN_REVIEW.md` | KEEP (essential artifact) + MERGE into comprehensive DOCX | specification of the frozen victim architecture | 170 | 2026-09-07 | 2 | 1 |
| `phase3/specification/PHASE3_RESTART_BOUNDARY.md` | KEEP (essential artifact) + MERGE into comprehensive DOCX | specification of the frozen victim architecture | 85 | 2026-08-31 | 2 | 1 |
| `phase3/specification/PHASE3_SELECTION_AND_CREATION_POLICY_DESIGN_REVIEW.md` | KEEP (essential artifact) + MERGE into comprehensive DOCX | specification of the frozen victim architecture | 203 | 2026-09-07 | 3 | 0 |
| `phase3/specification/PHASE4_INTERFACE_REQUIREMENTS.md` | KEEP (essential artifact) + MERGE into comprehensive DOCX | specification of the frozen victim architecture | 73 | 2026-08-31 | 1 | 0 |
| `phase4/attacks/_cross_attack_dormancy_reruns_2026-09-11.txt` | KEEP (essential artifact) | attack reconstruction notes beside the attack code | 427 | 2026-09-12 | 0 | 0 |
| `phase4/attacks/agentpoison/milestone2_smoke_test_run_2026-09-11.txt` | KEEP (essential artifact) | attack reconstruction notes beside the attack code | 19 | 2026-09-12 | 0 | 0 |
| `phase4/attacks/agentpoison/milestone5_campaign_run_2026-09-11.txt` | KEEP (essential artifact) | attack reconstruction notes beside the attack code | 60 | 2026-09-12 | 3 | 0 |
| `phase4/attacks/dsrm/milestone2_3_dry_run_2026-09-11.txt` | KEEP (essential artifact) | attack reconstruction notes beside the attack code | 55 | 2026-09-12 | 2 | 1 |
| `phase4/attacks/dsrm/milestone3_csrm_truncation_bug_2026-09-11.txt` | KEEP (essential artifact) | attack reconstruction notes beside the attack code | 32 | 2026-09-12 | 0 | 0 |
| `phase4/attacks/dsrm/milestone4_campaign_run_2026-09-11.txt` | KEEP (essential artifact) | attack reconstruction notes beside the attack code | 59 | 2026-09-12 | 1 | 0 |
| `phase4/attacks/dsrm/milestone5_white_box_run_2026-09-11.txt` | KEEP (essential artifact) | attack reconstruction notes beside the attack code | 11 | 2026-09-12 | 0 | 0 |
| `phase4/attacks/dsrm/white_box_campaign_run_2026-09-11.txt` | KEEP (essential artifact) | attack reconstruction notes beside the attack code | 58 | 2026-09-12 | 0 | 0 |
| `phase4/attacks/farma/milestone2_dry_run_2026-09-11.txt` | KEEP (essential artifact) | attack reconstruction notes beside the attack code | 21 | 2026-09-12 | 0 | 0 |
| `phase4/attacks/farma/milestone3_dry_run_2026-09-11.txt` | KEEP (essential artifact) | attack reconstruction notes beside the attack code | 52 | 2026-09-12 | 0 | 0 |
| `phase4/attacks/farma/milestone4_dry_run_2026-09-11.txt` | KEEP (essential artifact) | attack reconstruction notes beside the attack code | 67 | 2026-09-12 | 0 | 0 |
| `phase4/attacks/farma/milestone5_campaign_run_2026-09-11.txt` | KEEP (essential artifact) | attack reconstruction notes beside the attack code | 67 | 2026-09-12 | 3 | 0 |
| `phase4/attacks/farma/milestone6_adaptive_paraphrase_run_2026-09-11.txt` | KEEP (essential artifact) | attack reconstruction notes beside the attack code | 66 | 2026-09-12 | 0 | 0 |
| `phase4/attacks/farma/milestone6_store_evasion_run_2026-09-11.txt` | KEEP (essential artifact) | attack reconstruction notes beside the attack code | 63 | 2026-09-12 | 0 | 0 |
| `phase4/attacks/memorygraft/attack_failure_demo_run_2026-09-11.txt` | KEEP (essential artifact) | attack reconstruction notes beside the attack code | 9 | 2026-09-12 | 1 | 1 |
| `phase4/attacks/memorygraft/calibration_run_2026-09-11.txt` | KEEP (essential artifact) | attack reconstruction notes beside the attack code | 34 | 2026-09-12 | 2 | 0 |
| `phase4/attacks/memorygraft/calibration_run_2026-09-11_v2.txt` | KEEP (essential artifact) | attack reconstruction notes beside the attack code | 53 | 2026-09-12 | 6 | 3 |
| `phase4/attacks/memorygraft/foolability_run_2026-09-11.txt` | KEEP (essential artifact) | attack reconstruction notes beside the attack code | 49 | 2026-09-12 | 1 | 1 |
| `phase4/attacks/memorygraft/format_laundering_run_2026-09-11.txt` | KEEP (essential artifact) | attack reconstruction notes beside the attack code | 55 | 2026-09-12 | 0 | 0 |
| `phase4/attacks/memorygraft/milestone3_4_campaign_run_2026-09-11.txt` | KEEP (essential artifact) | attack reconstruction notes beside the attack code | 58 | 2026-09-12 | 0 | 0 |
| `phase4/attacks/minja/milestone3_dry_run_2026-09-11.txt` | KEEP (essential artifact) | attack reconstruction notes beside the attack code | 86 | 2026-09-12 | 0 | 0 |
| `phase4/attacks/minja/milestone4_campaign_run_2026-09-11.txt` | KEEP (essential artifact) | attack reconstruction notes beside the attack code | 69 | 2026-09-12 | 1 | 0 |
| `phase4/attacks/mpbench/amem_campaign_run_2026-09-11.txt` | KEEP (essential artifact) | attack reconstruction notes beside the attack code | 100 | 2026-09-12 | 0 | 0 |
| `phase4/attacks/mpbench/amem_campaign_run_2026-09-15_p2fix.txt` | KEEP (essential artifact) | attack reconstruction notes beside the attack code | 112 | 2026-09-16 | 0 | 0 |
| `phase4/attacks/mpbench/milestone4_dry_run_2026-09-11.txt` | KEEP (essential artifact) | attack reconstruction notes beside the attack code | 60 | 2026-09-12 | 0 | 0 |
| `phase4/attacks/mpbench/milestone5_campaign_run_2026-09-11.txt` | KEEP (essential artifact) | attack reconstruction notes beside the attack code | 78 | 2026-09-12 | 3 | 0 |
| `phase4/attacks/sleeper_memory_poisoning/campaign_run_2026-09-11.txt` | KEEP (essential artifact) | attack reconstruction notes beside the attack code | 110 | 2026-09-12 | 3 | 0 |
| `phase4/attacks/sleeper_memory_poisoning/trigger_sensitivity_run_2026-09-11.txt` | KEEP (essential artifact) | attack reconstruction notes beside the attack code | 60 | 2026-09-12 | 1 | 0 |
| `phase5/PHASE5_5_1_INSTRUMENTATION_CONTRACT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 170 | 2026-09-13 | 0 | 0 |
| `phase5/PHASE5_5_2_CANONICAL_EVENT_SCHEMA.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 114 | 2026-09-13 | 0 | 0 |
| `phase5/PHASE5_5_3_RUN_IDENTITY.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 98 | 2026-09-13 | 0 | 0 |
| `phase5/PHASE5_5_4_MEMORY_LIFECYCLE_INSTRUMENTATION.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 339 | 2026-09-13 | 0 | 0 |
| `phase5/PHASE5_5_4_SEVEN_ATTACK_INTEGRATION_CHECKLIST.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 115 | 2026-09-13 | 0 | 0 |
| `phase5/PHASE5_5_5_RETRIEVAL_SELECTION_INSTRUMENTATION.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 203 | 2026-09-13 | 0 | 0 |
| `phase5/PHASE5_5_6_AGENT_DECISION_ACTION_INSTRUMENTATION.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 110 | 2026-09-13 | 0 | 0 |
| `phase5/PHASE5_5_7_PROVENANCE_LINEAGE_INSTRUMENTATION.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 247 | 2026-09-13 | 0 | 0 |
| `phase5/PHASE5_5_8A_MEMORY_BEHAVIOR_DATASET.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 144 | 2026-09-13 | 0 | 0 |
| `phase5/PHASE5_5_8_TRACE_ASSEMBLY_PROPAGATION_GRAPH.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original; read by tests | 183 | 2026-09-13 | 2 | 1 |
| `phase5/PHASE5_5_9_VALIDATION_NONINTERFERENCE_FREEZE.md` | KEEP (essential artifact) | pre-registration / freeze record: research-integrity evidence | 222 | 2026-09-13 | 0 | 0 |
| `phase5/PHASE5_CHECKLIST.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original; read by tests | 209 | 2026-09-13 | 1 | 1 |
| `phase5/PHASE5_POST_FREEZE_HARDENING_REPORT.md` | KEEP (essential artifact) | pre-registration / freeze record: research-integrity evidence | 358 | 2026-09-13 | 1 | 0 |
| `phase5/PHASE5_REPOSITORY_OBSERVABILITY_AUDIT.md` | MERGE into comprehensive DOCX + ARCHIVE (historical evidence, kept in place) | phase report / freeze record; summarise, keep original | 316 | 2026-09-13 | 1 | 0 |
| `phase6/artifacts/worked_example_governance_ledger/README.md` | KEEP (essential artifact) | describes a committed worked-example artifact beside it | 49 | 2026-09-16 | 26 | 6 |
| `ref_Egyption_informatics.txt` | NEEDS MANUAL REVIEW | full text of a third-party paper committed to the repository; unreferenced; redistribution rights unclear | 1810 | 2026-10-05 | 0 | 0 |
| `ref_Engineering_applicat.txt` | NEEDS MANUAL REVIEW | full text of a third-party paper committed to the repository; unreferenced; redistribution rights unclear | 2304 | 2026-10-05 | 0 | 0 |
| `ref_From_Untrusted_Input.txt` | NEEDS MANUAL REVIEW | full text of a third-party paper committed to the repository; unreferenced; redistribution rights unclear | 1485 | 2026-10-05 | 0 | 0 |
| `requirements-lock.txt` | KEEP (essential artifact) | experiment output / audit log | 206 | 2026-09-28 | 0 | 0 |
| `requirements.txt` | KEEP (essential artifact) | experiment output / audit log | 46 | 2026-09-28 | 8 | 3 |
| `results/TABLE_INDEX.md` | KEEP (essential artifact) | experiment output tables | 32 | 2026-10-14 | 2 | 0 |
| `results/tables/T10_propagation.md` | KEEP (essential artifact) | experiment output tables | 329 | 2026-10-12 | 0 | 0 |
| `results/tables/T11_sleeper.md` | KEEP (essential artifact) | experiment output tables | 1379 | 2026-10-13 | 0 | 0 |
| `results/tables/T12_predictions.md` | KEEP (essential artifact) | experiment output tables | 303 | 2026-10-13 | 0 | 0 |
| `results/tables/T13_validity_adjusted.md` | KEEP (essential artifact) | experiment output tables | 238 | 2026-10-13 | 0 | 0 |
| `results/tables/T14_adjudication.md` | KEEP (essential artifact) | experiment output tables | 70 | 2026-10-13 | 0 | 0 |
| `results/tables/T15_corroboration_robustness.md` | KEEP (essential artifact) | experiment output tables | 187 | 2026-10-13 | 0 | 0 |
| `results/tables/T16_mem0_pipeline.md` | KEEP (essential artifact) | experiment output tables | 341 | 2026-10-13 | 0 | 0 |
| `results/tables/T17_sa2.md` | KEEP (essential artifact) | experiment output tables | 141 | 2026-10-13 | 0 | 0 |
| `results/tables/T18_probe_robustness.md` | KEEP (essential artifact) | experiment output tables | 74 | 2026-10-13 | 0 | 0 |
| `results/tables/T19_b13_owner_loo.md` | KEEP (essential artifact) | experiment output tables | 1837 | 2026-10-13 | 0 | 0 |
| `results/tables/T1_validity.md` | KEEP (essential artifact) | experiment output tables | 204 | 2026-10-12 | 0 | 0 |
| `results/tables/T20_validity_final.md` | KEEP (essential artifact) | experiment output tables | 1106 | 2026-10-13 | 0 | 0 |
| `results/tables/T21_sag.md` | KEEP (essential artifact) | experiment output tables | 130 | 2026-10-13 | 0 | 0 |
| `results/tables/T22_propagation_v2.md` | KEEP (essential artifact) | experiment output tables | 265 | 2026-10-13 | 0 | 0 |
| `results/tables/T23_sleeper_v2.md` | KEEP (essential artifact) | experiment output tables | 365 | 2026-10-13 | 0 | 0 |
| `results/tables/T24_vpl.md` | KEEP (essential artifact) | experiment output tables | 930 | 2026-10-14 | 0 | 0 |
| `results/tables/T25_containment_v3_v4.md` | KEEP (essential artifact) | experiment output tables | 11382 | 2026-10-14 | 0 | 0 |
| `results/tables/T26_sleeper_v3_v4.md` | KEEP (essential artifact) | experiment output tables | 1586 | 2026-10-14 | 0 | 0 |
| `results/tables/T2_judge_sensitivity.md` | KEEP (essential artifact) | experiment output tables | 222 | 2026-10-12 | 0 | 0 |
| `results/tables/T3_two_denominators.md` | KEEP (essential artifact) | experiment output tables | 129 | 2026-10-12 | 0 | 0 |
| `results/tables/T4_memory_poisoning_holdouts.md` | KEEP (essential artifact) | experiment output tables | 138 | 2026-10-12 | 0 | 0 |
| `results/tables/T5_b13_decomposition.md` | KEEP (essential artifact) | experiment output tables | 37 | 2026-10-12 | 0 | 0 |
| `results/tables/T6_injection_holdouts.md` | KEEP (essential artifact) | experiment output tables | 160 | 2026-10-12 | 0 | 0 |
| `results/tables/T7_baselines.md` | KEEP (essential artifact) | experiment output tables | 78 | 2026-10-12 | 0 | 0 |
| `results/tables/T8_harm.md` | KEEP (essential artifact) | experiment output tables | 46 | 2026-10-12 | 0 | 0 |
| `results/tables/T9_adaptive.md` | KEEP (essential artifact) | experiment output tables | 235 | 2026-10-12 | 0 | 0 |
| `MAMBench Process Documentation.docx` | MERGE into comprehensive DOCX / NEEDS MANUAL REVIEW | Aug-2026 process document (gitignored); a source for the comprehensive DOCX; delete only after its content is verified there | - | 2026-08-21 (gitignored) | 0 | 0 |
| `phase3/experiments/MAMBench_Phases_1-2_Methodology_Draft.docx` | NEEDS MANUAL REVIEW | early Phases 1-2 methodology draft (gitignored); superseded by Methodology Draft.docx; keep or remove locally | - | 2026-09-07 (gitignored) | 0 | 0 |

## Actions taken (2026-10-19, on the owner's decision)

Paths in the table above are as they were at inventory time.

| Action | Files | Recoverable from |
|---|---|---|
| Deleted (`git rm`) | `meth_extract.txt` (verified redundant); `ref_Egyption_informatics.txt`, `ref_Engineering_applicat.txt`, `ref_From_Untrusted_Input.txt` (third-party paper full texts, unreferenced) | git history |
| Removed to the Windows Recycle Bin (never in git) | `MAMBench Process Documentation.docx`, `phase3/experiments/MAMBench_Phases_1-2_Methodology_Draft.docx` | Recycle Bin |
| Moved to `docs/` (`git mv`, living or legal) | `REMEDIATION_MASTER_REGISTER.md`, `DATA_LICENSING_AND_ANNOTATION_AUDIT.md`, `ANNOTATION_PROVENANCE_FINAL.md`, `RELATED_WORK_AND_NOVELTY.md`, `NOVELTY_MATRIX.md` | — |
| Moved to `docs/archive/` (`git mv`, historical) | the other 40 root-level reports and `Methodology.pdf` (August 2026 methodology export); content unchanged except three relative links re-rooted in `PHASE5_HANDOFF_REPORT.md` | — |

References updated: README links, `conftest.py` skip reason, `scripts/build_comprehensive_documentation.py`. Mentions of these files by bare name in code docstrings and in the two research documents still identify them uniquely and were left unchanged.
