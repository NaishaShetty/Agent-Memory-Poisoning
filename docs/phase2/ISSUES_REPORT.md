# Phase 2.1 Issue / Status Report (Task 10)

Categories: **A** VERIFIED/READY · **B** VERIFIED WITH KNOWN LIMITATION ·
**C** CONDITIONALLY AVAILABLE · **D** UNAVAILABLE · **E** UNVERIFIED ·
**F** BLOCKING ISSUE.

No issue below is invented — each is copied or closely paraphrased from
the frozen Phase 1 record (`data/reports/*.json`, `data/metadata/*.json`)
or from the Phase 2.1 audit's direct artifact inspection. None are
resolved here; resolutions (if any) belong to the phase noted.

## Core memory foundation (the four datasets this phase freezes)

| # | Resource | Category | Issue | Evidence | Impact | Blocks Phase 2? | Planned resolution phase |
|---|---|---|---|---|---|---|---|
| 1 | LongMemEval | **B** | 2 records contain U+FFFD (mojibake) replacement characters, deliberately preserved rather than repaired; this is the one hard FAIL in `phase1_validation_report.json` (`encoding_correctness`, `overall_status: "FAIL"`). **Update (Phase 2.1-R):** re-verified at the byte level against the raw source file — the defect is confirmed pre-existing in the raw file (not introduced by Phase 1 processing), formalized as a provenance case study with explicit `provenance_status: VERIFIED_WITH_ISSUE` / `admission_status: QUARANTINED`, and both records are now programmatically excluded from any trusted clean-memory baseline via `preprocessing/trusted_baseline.py`. See `docs/phase2/LONGMEMEVAL_PROVENANCE_CASE_STUDY.md`. | `phase1_validation_report.json`, `longmemeval_statistics.json` (`valid_flagged: 2`), `data/metadata/longmemeval_provenance_exceptions.json` | Two records in ~1.27M total memory records carry a known source-data defect; downstream consumers must not silently "fix" these two records' text, and must not admit them to a trusted-clean baseline | No — pre-existing source defect, explicitly flagged, enforced-excluded, not a processing bug | Formalized as a case study in Phase 2.1-R; a future provenance-governance defense (Phase 6) is the natural consumer, not a repair target |
| 2 | LongMemEval | **B** | `longmemeval_m_cleaned.json` (~2.7GB variant) was never acquired | `dataset_manifest.json known_limitations`, `pipeline_config.yaml` comment | Phase 2+ cannot use the m_cleaned haystack scale unless it is separately acquired | No — oracle + s_cleaned variants are sufficient for the approved foundation | Deferred; acquire in a later phase only if m_cleaned scale is actually needed |
| 3 | LoCoMo | **B** | 444 of 1,986 QA instances (~22%) are missing an answer field; 4 missing evidence. **Update (Phase 2.1-R):** all 444 confirmed to be category-5 adversarial questions with no ground-truth answer by dataset design (not an unexplained gap); a canonical QA reconciliation layer (`data/processed/locomo/qa_reconciled.jsonl`) now classifies every record explicitly and exposes `answer_evaluation_eligible`/`evidence_evaluation_eligible` flags so future metrics don't silently assume complete ground truth. See `docs/phase2/LOCOMO_QA_RECONCILIATION.md`. | `locomo_inspection.json`, `data/processed/locomo/qa_reconciled.jsonl` | Any Phase 2+ work treating LoCoMo QA as a complete gold-answer set will be wrong for ~22% of instances; the reconciliation layer prevents this by making eligibility explicit and machine-checkable | No — documented, classified, not a processing defect | Resolved at the classification level in Phase 2.1-R; future metric-specific filtering is a Phase 2.2+/Phase 4 consumer concern |
| 4 | MSC | **B** | Dataset license is not explicitly published for MSC itself (only the ParlAI framework code is confirmed MIT) | `dataset_manifest.json`: `"unavailable / not explicitly published... Do not assume a license not explicitly stated."` | Any redistribution/publication use of MSC data needs a licensing determination before Phase 2+ ships it externally | No — internal research use proceeds; redistribution is the open question | Legal/licensing review, timing not yet determined |
| 5 | Conversation Chronicles | **B** | 93% of raw episodes (190,000 of 200,000) deliberately excluded via a documented sampling cap, not a silent drop | `pipeline_config.yaml`, `conversation_chronicles_statistics.json` (`sampled_out_record_count: 10920679`) | Phase 2+ analyses must not describe this dataset's processed set as "the full dataset" | No — intentional, seeded, reproducible scoping decision | N/A, revisit only if full-scale CC is later required |
| 6 | All four | **A** | (For contrast) `unique_memory_ids`, `no_cross_dataset_id_collision`, `valid_source_references`, `valid_provenance`, `no_broken_task_evidence_links`, `valid_event_ordering`, `schema_consistency`, `no_train_test_leakage` all PASS | `phase1_validation_report.json` | — | — | — |

## Workload resources (not part of the approved foundation; recorded for completeness)

| # | Resource | Category | Issue | Blocks Phase 2? |
|---|---|---|---|---|
| 7 | ToolBench | **D** | Only README/LICENSE fetched; 541MB+ bulk data requires RapidAPI keys not configured | No (not an approved input) |
| 8 | WebShop | **D** | Only README/LICENSE fetched; 1.18M-product corpus not downloaded, environment not run | No |
| 9 | EHRAgent | **D** | No accessible task data; underlying MIMIC-III/eICU require PhysioNet credentialing | No |
| 10 | MIMIC-III / eICU | **C** | Gated behind PhysioNet credentialed access + CITI training + signed DUA; explicitly optional | No |
| 11 | API-Bank | **C** | Only test-data split acquired (1,062 records); training split and evaluator scripts not run | No |
| 12 | StrategyQA | **C** | Supporting Wikipedia-paragraphs corpus downloaded but not parsed | No |
| 13 | SWE-bench Verified | **C** | Metadata only; no repositories cloned, no patches executed | No |
| 14 | tau-bench | **C** | `historical_trajectories/` (pre-recorded runs) not fetched | No |
| 15 | tau2-bench | **C** | Only 1 of 3+ domains (airline) acquired, by deliberate scoping | No |

## Sleeper resources

| # | Resource | Category | Issue | Blocks Phase 2? |
|---|---|---|---|---|
| 16 | Hidden in Memory | **D** | Paper verified, no public implementation found | No |
| 17 | Sleeper Dataset Generator | **E** | Name in the original research plan does not exactly match any found resource; closest match (anthropics/sleeper-agents-paper) used as a probable-but-unconfirmed mapping | No, but flagged for verification before being treated as authoritative in a later phase |
| 18 | Final sleeper/backdoor dataset | **D** | Not generated — by explicit instruction (Task 9/11 forbid generating it in Phase 2.1, and Phase 1 already deferred it) | No — this is expected, not a gap |

## Attack resources (all explicitly out of Phase 2.1's clean-foundation scope)

| # | Resource | Category | Issue | Blocks Phase 2? |
|---|---|---|---|---|
| 19 | AgentPoison | **D** | Code publicly available (MIT) but not cloned or executed here | No |
| 20 | MINJA | **D** | Code publicly available (MIT) but not cloned or executed here | No |
| 21 | DSRM | **B** (resolved from **F**) | **Update (Phase 2.1-R):** identity resolved using a supplied authoritative citation (Jing, Li, Dong, Zhou, Liu, 2026, *Engineering Applications of Artificial Intelligence*, Vol. 167, Art. 113968). Mechanism documented (deceptive semantic reasoning over RAG tool-selection, black-box/white-box settings). No public implementation exists — `IMPLEMENTATION_AVAILABILITY` remains unresolved, not overclaimed. See `docs/phase2/DSRM_RESOLUTION.md`. | `preprocessing/registry.py`, `data/metadata/resource_registry.json`, `data/metadata/phase2_input_manifest.json` | Previously blocked any later phase from treating DSRM as a known method; now unblocked for Phase 4 attack-track integration (as a reconstruction target, not a ready implementation) | No — resolved at the identity level; remains correctly unapproved as a Phase 2.1 input (attack category, out of scope) | Phase 4 (attack/poisoned-memory generation), if pursued as a reconstruction |
| 22 | MemoryGraft | **D** | Paper verified, zero matching public repos found | No |
| 23 | FARMA | **D** | Paper verified, no public repo found | No |
| 24 | MPBench | **D** | Paper verified; a second target-name claim from one research pass could not be confirmed and was excluded rather than guessed | No |

## Security-benchmark / comparison resources

| # | Resource | Category | Issue | Blocks Phase 2? |
|---|---|---|---|---|
| 25 | MemSecBench | **D** | Paper only, no code/data release found | No |
| 26 | MEMSAD | **D** | Paper only, no public implementation | No |
| 27 | MemAudit | **D** + **E** | Paper only; a second, unrelated paper shares the same title (arXiv:2605.02199) — do not conflate | No, but the naming collision must be tracked forward so a future citation search doesn't merge the two |
| 28 | A-MemGuard | **D** | Code available (MIT) but not cloned; reported >95% ASR reduction not independently verified | No |
| 29 | ASB | **D** | Code available (MIT) but not cloned | No |
| 30 | AgentDojo | **D** | Code available (MIT) but not cloned; scope is prompt injection, not memory poisoning specifically | No |
| 31 | InjecAgent | **D** | Code available (MIT) but not cloned | No |

## Repository / process-level findings from the Phase 2.1 audit itself

| # | Item | Category | Note | Blocks Phase 2? |
|---|---|---|---|---|
| 32 | No git repository | **F** for reproducibility guarantees, not for data validity | No commit hash or code-content hash ties any Phase 1 output to an exact code state (see `REPRODUCIBILITY_REPORT.md`) | Does not block Phase 2.2 starting, but should be resolved before results are published as reproducible |
| 33 | `registry.py` module docstring says "27 resources" vs. actual/computed 28 | **B** | Stale-by-one comment; the generated `resource_registry.json`'s `total_resources: 28` and the entry count agree with each other, so the data itself is not wrong, just one comment | No |
| 34 | `run_all_*.log` local-time vs UTC `run_timestamp` mismatch | **B** | Cosmetic; the value actually persisted in data is UTC | No |
| 35 | No standalone "Methodology" / "MAMBENCH PROCESS DOCUMENTATION" file found in the repository | **A** (resolved from **E**) | **Update (Phase 2.1-R):** `Methodology.pdf` and `PROCESS DOCUMENTATION.docx` (plus a full literature-review draft, `Agent Memory Poisoning 2.docx`) are present in the repository root as of this remediation pass — either added between sessions or missed by the original Phase 2.1 file search. Both were read in full (or, for the large literature-review draft, targeted-searched) during Phase 2.1-R and their content confirmed fully consistent with every prior Phase 2.1 claim (schema field names, provenance mechanism vocabulary, per-dataset issue list, DSRM/attack-resource treatment). All three files are now tracked in git (see git commit history). | No — was never blocking; now fully resolved with the authoritative documents in hand and confirmed consistent |

## Overall

- **Blocking issues for Phase 2.2 (category F that actually blocks):** none
  found among the four approved core datasets. Item 32 (no VCS) was
  flagged F in the sense that it would block publishing reproducibility
  claims externally; **resolved in Phase 2.1-R** (local git now
  initialized, baseline + remediation commits recorded — see
  `REPRODUCIBILITY_REPORT.md`). Item 21 (DSRM identity) was also flagged
  F and is **resolved in Phase 2.1-R** (see `DSRM_RESOLUTION.md`); its
  remaining state (no public implementation) is now an accurately
  recorded **B**, not a blocker. Neither ever blocked the Phase 2.1
  freeze itself or Phase 2.2 starting.
- **Every known Phase 1 issue remains visible** in this table, in
  `phase2_input_manifest.json`'s per-resource `known_issues` field, and in
  the underlying Phase 1 reports — none were silently resolved.
