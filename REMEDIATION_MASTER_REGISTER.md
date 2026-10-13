# Remediation Master Register

**Source review:** `docs/review/INDEPENDENT_IEEE_REVIEW_2026-10-12.md`.
**Branch:** `remediation/2026-10-12`. **Checkpoint tag:** `pre-remediation-2026-10-12` (= `d853404a`).
The pre-remediation copies of both `.docx` deliverables (which had uncommitted changes) are saved outside the repo; their hashes are in §6.

Issue identifiers keep the review's IDs (M = methodology, D = discrepancy, P0–P3 = action plan) where possible.

- **G1-*, G2-*, G3-*** are the three research gaps (provenance/governance, self-propagation, sleeper).
- **NOV-*** are novelty findings.
- **REP-*** are reproducibility findings.
- **NEW-*** are defects found during the remediation itself.

Statuses: OPEN, INVESTIGATING, FIX IMPLEMENTED, VALIDATION PASSED, VALIDATION FAILED, BLOCKED, ACCEPTED LIMITATION.

"Area" uses these abbreviations:

| Code | Area |
|---|---|
| Prov | provenance / governance (Gap 1) |
| Prop | self-propagation (Gap 2) |
| Sleep | sleeper / dormant (Gap 3) |
| Valid | attack validity |
| Stat | statistics |
| Doc | documentation |
| Repro | reproducibility |

---

## 1. Methodology (M)

| ID | Original claim / behaviour | Evidence | Sev. | Area | Action | Code? | Recompute / new exp.? | Files | Verification | Status / remaining limitation |
|---|---|---|---|---|---|---|---|---|---|---|
| M1 | Security results described as running on real persistent-memory systems | `attack_validity_audit.py:94` puts the note directly into the prompt; `harm_study_v2.py:15-21,179-198` uses a list plus MiniLM top-5; real Mem0/A-MEM only in §32.5 (9 cases, Mem0 `infer=False`) | Major | All | State the evaluation unit per experiment (`EXPERIMENTAL_VALIDITY_AUDIT.md` §1); the paper's threat model and limitations say it | No | No (a Mem0 `infer=True` replication remains P2) | EXPERIMENTAL_VALIDITY_AUDIT.md, paper | Each experiment traced to its code path | **ACCEPTED LIMITATION**: disclosed; no security result claims a real memory system |
| M2 | B13 "reaches what content-only cannot" via provenance | Evaluator assigns `tool_output` to every attack (`eval_round6.py:94`; `eval_round7_holdouts._decide`); `b13_live.py:202-205` never excludes `user_turn` | Major | Prov | Decompose B13 into components on HO4/HO7/HO8; analyse user-channel poisoning; tests | Yes (analysis + tests) | Recompute from cached components; HO7 components recomputed and asserted equal to stored B13 | `remediation/b13_decomposition.py`, `tests/test_remediation.py` | Components reproduce stored B13 item for item (3 hold-outs); 4 property tests pass | **VALIDATION PASSED**. Finding: channel + content rules = B12 exactly; **all** of B13's gain is corroboration; user-channel poisoning 0% excluded by construction |
| M3 | 42.5% working rate stated as a property of the attacks | C0 judge kappa ≈ 0.5–0.6 against humans; the vote judge finds more compliance on dev | Major | Valid | Re-judge cached answers (fitted probe) with C1 and C3; report the C0 vs vote range per population | Yes | Judge calls only (10,512) | `remediation/validity_judge_sensitivity.py` | Cached C0 reproduces the published audit 2628/2628; unit test on denominators | **VALIDATION PASSED**: population rates are judge-robust (25.3% → 27.1% overall; own 40.8% → 44.3%), but 509/2628 instances (19%) flip status; the fitted probe's task-alone base rate (25.7% C0 / 47.4% vote) exceeds the project's own 20% rule, so the rates are lower bounds for high-base-rate populations (T2) |
| M4 | Union-over-probes rule presented as pre-committed | `attack_validity_audit.py:280-300`; adopted after the first audit | Moderate | Valid | Disclose; report fitted-probe-only rates beside the union (T2) | No | No | EXPERIMENTAL_VALIDITY_AUDIT.md | — | **ACCEPTED LIMITATION** (disclosed) |
| M5 | Pooled 42.5% headline | `working_set.json`: own 482/804 (60.0%), external 635/1824 (34.8%); Gandalf is 38% of the denominator | Moderate | Valid | Authoritative T1 leads with the split; Mosscap sample disclosed | Yes | Recompute | `authoritative_tables.t1_validity` | Test: totals equal the population sums | **VALIDATION PASSED** |
| M6 | Forking paths across 7 rounds and 25+ configurations | Many development redesigns | Moderate | Stat | Every paper claim labelled pre-registered hold-out / pre-registered dev / exploratory; only the first class in the abstract | No | No | paper, EXPERIMENTAL_VALIDITY_AUDIT.md | — | **FIX IMPLEMENTED** in the paper; ACCEPTED LIMITATION for development results |
| M7 | HO8 anomaly / union generalisation | `eval_holdout8.py:200-206,360-366`: clusters fit on HO8 benign, threshold = percentile of the evaluated half | **Major** | Sleep | Recompute with (a) dev-fitted, (b) leak-free owner-adaptive, (c) the shipped committed centroids; keep the original | Yes | Embeddings only | `remediation/ho8_anomaly_devfit.py` | Original reproduces exactly (145/160, 9/85; 141/160, 8/85); test that `_dev_fit` never reads HO8 | **VALIDATION PASSED**. Result: shipped/dev-fitted signal flags **137/171 (80%)** and **142/171** HO8 benign; leak-free owner-adaptive 131/160 at 4/85. Generalisation claim withdrawn |
| M8 | "39/47 held, CALIBRATED" | 38 of 48 predictions directional; HO8's 7 not counted | Moderate | Stat | Tally by kind, HO8 included, U-2 flagged NOT SCORED | Yes | Recompute | `remediation/predictions_tally.py` | Test reconstructs 34/41 and 39/47; 45/53 including HO8 | **VALIDATION PASSED** |
| M9 | Harm levels at 7B | All agent-side runs on qwen2.5:7b | Moderate | All | Disclose | No | No | paper | — | **ACCEPTED LIMITATION** |
| M10 | Human validation thin; annotator identity unknown | 100 items, 2 annotators; no record of who they were | Moderate | Valid | Report kappa with n; state that annotator identity and independence are **not recorded** in the repository (not invented) | No | No | EXPERIMENTAL_VALIDITY_AUDIT.md §6 | Searched `docs/phase17/human_labels`; no annotator metadata | **ACCEPTED LIMITATION**; the owner must supply annotator details before submission (FINAL report, action item) |
| M11 | B13 FPR quoted at the no-evidence condition beside with-evidence recall | Tables 5D/6/14/16 | Moderate | Prov | T4 pairs every recall with the same-condition FPR (untrusted and user_turn) | Yes | Recompute | `authoritative_tables.t4_*` | — | **VALIDATION PASSED** |
| M12 | HO3 development set was the hold-out | Already corrected (§10C) | — | Stat | Keep HO3 out of headline claims | No | No | paper | — | **VALIDATION PASSED** (no headline uses HO3) |

## 2. Discrepancies (D)

| ID | Location | Conflict | Resolution evidence | Status | Fix |
|---|---|---|---|---|---|
| D1 | Methodology §33 | 17/20, 34/41 and 39/47 printed side by side | Reconstructed: 17/20 = commit `175263b8` (HO4/5 + B, B-5 pending); 34/41 = before addenda 6 and 8; 39/47 = the current file. All three are different scopes; the 34/41 bracket was a stale duplicate | **VALIDATION PASSED** | Stale bracket removed by `patch_methodology_docx.py` (logged); 17/20 marked as a snapshot |
| D2 | Results abstract | "four new corpora … 39/47" omits HO8 | HO8 is the fifth corpus; 45/53 incl. HO8; U-2 not scored | **VALIDATION PASSED** | Generator fixed (`build_results_analysis_docx.py`) |
| D3 | Results §2.2, §10 | "Three frozen hold-outs"; "no configuration has more than one clean estimate" | 8 hold-outs | **VALIDATION PASSED** | Generator fixed |
| D4 | Results §11, §13A | 13D→13E; "4 and 7" → "4, 7 and 8"; "conditional backdoors untested" | HO8 tested them (B13 28/40) | **VALIDATION PASSED** | Generator fixed |
| D5 | Results Table 4 vs Table 19 | J0 undefended 87/309 vs 99/309 on "identical answers" | `harm_judge_fix.rejudge` scores a **regenerated** run (noise_repeats rep1), not harm_study_v2's answers. J0 judged rep1 as 94 (noise_repeats), then 99 (rejudge): **judge-only variation of 5 items** | **VALIDATION PASSED** (explained) | T8 states the answer provenance; the "identical answers" wording is corrected in the paper. Limitation: judge nondeterminism at n=309 ≈ 1.6 points |
| D6 | Results abstract/§7; Methodology §33 | "nearly 39 points" | Computed lead = **32.1 (B13) / 37.2 (B17)** points over deberta@dev (14.1%); the string was hard-coded | **VALIDATION PASSED** | Generator now computes it; methodology patched |
| D7 | Results §13E | Anomaly "at 9 benign FP"; "union beats every single detector on unseen attacks" | M7 | **VALIDATION PASSED** | Generator paragraph rewritten with the corrected arms; methodology bracket |
| D8 | Methodology abstract/§1/§2/§3 | Stale scope (first 13 phases; RQs about QA; related work "future work") | — | **FIX IMPLEMENTED** | A dated pointer paragraph and a related-work bracket in the methodology; the **new manuscript** (`paper/`) replaces these for submission |
| D9 | Results structure | 9.3 before 9.2; 10A, 10C, 10B; 13D/E before 13C | — | **ACCEPTED LIMITATION** | Not renumbered: cross-references from logs and the methodology point at these numbers. The paper does not reuse the structure |
| D10 | Abstract, §12, §33 | "provably cannot" | Structural zero | **VALIDATION PASSED** | "by construction" (methodology patched, both occurrences; paper) |
| D11 | Results abstract | Ledger headline at r=0.90 | Recommended r=0.95 | **FIX IMPLEMENTED** | The paper leads with r=0.95 (5/130, 6.4% blast radius) |
| D12 | Several | B13 FPR condition mixing | = M11 | **VALIDATION PASSED** | T4 |
| D13 | Methodology §16; Results | 8 "needs verification" citations; no Results bibliography; ~10 missing key works | `RELATED_WORK_AND_NOVELTY.md` | **FIX IMPLEMENTED** | The paper bibliography is built from verified sources; methodology markers left as historical (see §5 of the final report) |
| D14 | Results §13D | "first measurement" of consolidation laundering | PPMF, TMA-NM, MemLineage | **FIX IMPLEMENTED** | Not used in the paper; RELATED_WORK §2 |
| D15 | "2,628 attack instances" | Includes a 300-item Mosscap sample | `working_set.json` | **VALIDATION PASSED** | "2,628 audited instances across 20 populations" (T1, paper) |
| D16 (new) | Results Fig. 3 / §13E | "Router does not beat the union" read as a hold-out result | U-2 was pre-registered for HO8 but never computed there | **VALIDATION PASSED** | Tallied NOT SCORED; the text says development-only |

## 3. Action plan items (P0–P3) not covered above

| ID | Item | Status |
|---|---|---|
| P0-1 | Write a new manuscript | **FIX IMPLEMENTED** (`paper/`); readiness in the checklist |
| P0-2 | Related work from primary sources | **FIX IMPLEMENTED** (`RELATED_WORK_AND_NOVELTY.md`). Limitation: the tail of the appendices of 5 long papers was not read; SMSR (2606.12703) and Forensic trajectory signatures (2606.30566) not read (NOV-9) |
| P0-3 | Narrow novelty claims | **FIX IMPLEMENTED** in the paper (no "first" claims) |
| P0-4 | Channel-label assumption | = M2, **VALIDATION PASSED** |
| P0-5 | Evaluation unit | = M1 |
| P0-6 | HO8 threshold | = M7 |
| P0-7 | Inconsistencies | D1–D16 above |
| P0-8 | Bibliography | = D13 |
| P0-9 | Licence | **BLOCKED** on an owner decision. Constraints documented (`docs/release/LICENSING_AND_DATA_RIGHTS.md`: LoCoMo and toxic-chat are CC BY-NC 4.0; MSC has no explicit licence; InjecAgent not recorded). No licence applied, deliberately |
| P1-1 | Judge sensitivity | = M3 |
| P1-2 | HO8 dev-fitted threshold | = M7 |
| P1-3 | Lead with the split | = M5 |
| P1-4 | Claim labelling | = M6/M8 |
| P1-5 | Annotator provenance | = M10 (BLOCKED on owner information) |
| P1-6 | Ledger presentation | **FIX IMPLEMENTED** (paper; T9) |
| P2-1 | Mem0 `infer=True` replication of HO4 | **OPEN** (not run; stated as a limitation and future work) |
| P2-2 | More human labels | **OPEN** |
| P2-3 | Stronger agent on a hold-out | **OPEN** (dev-only evidence exists) |
| P2-4 | Channel-only / component baseline for B13 | **VALIDATION PASSED** via M2's decomposition (channel+rules arm; channel-only = exclude-all-untrusted, 100% FPR) |
| P3-* | Future work items | ACCEPTED LIMITATION |

## 4. The three research gaps (details in `THREE_RESEARCH_GAPS_AUDIT.md`)

| ID | Issue | Status |
|---|---|---|
| G1-1 | Missing provenance must not be silently trusted | **VALIDATION PASSED**: test `test_missing_provenance_is_not_silently_trusted`; a non-exact label is also untrusted |
| G1-2 | User-channel poisoning / source mislabelling | **VALIDATION PASSED** (analysis): excluded 0% by construction; flagged-but-admitted 3/157, 48/129, 59/160 |
| G1-3 | Does corroboration add value beyond source labels? | **VALIDATION PASSED**: yes; it is the whole gain (HO4 +76, HO7 +22, HO8 +59 attacks; +27/+21/+8 benign FP) |
| G1-4 | Metadata forgery vs channel mislabelling | **ACCEPTED LIMITATION**: forgery tested only on 5 constructed sentences (§32.7); mislabelling analysed (G1-2); no adversarial channel-label attack exists in the code |
| G1-5 | Provenance through consolidation | See G2 (derived memories record their parents; the taint inherits only through admission states) |
| G2-1 | Laundering through one consolidation | Existing: dev 0→33/161 harm; HO8 108 carry-and-excluded |
| G2-2 | Over-blocking of legitimate derived memory | **NEW finding (VALIDATION PASSED)**: semantic containment withholds 22/59 (37%) of NON-carrying summaries of excluded poisons (dev) |
| G2-3 | Containment depends on admission | **VALIDATION PASSED**: containment acts only on descendants of B13-excluded poisons; 46 carrying summaries of B13-missed poisons untouched (dev). Test: no ground-truth label is a containment input |
| G2-4 | Multi-generation propagation | **VALIDATION PASSED** (experiment run): P2 found 98/249 summaries still carrying the payload at generation 2, and laundering harm of 22/161. The best containment arm withholds 24/71 carrying descendants (75% at gen 1 → 34% at gen 2), only via state inheritance; harm 22 → 13. P2-1/2/3/4 HELD; P2-5 FAILED (over-blocking 7/90, lower than predicted). Development data only |
| G3-1 | Activation never measured with a real trigger | The harm study's backdoor task was leading. SA-1 then measured dormancy (0/60 activation on unrelated messages) and natural activation (23/60 C0, 42/60 vote). Content detection excluded 60/60 before activation at 2/60 lookalike cost, because the payloads are explicit; no sleeper-specific signal worked. SA-1 through SA-9 HELD | **VALIDATION PASSED** (experiment run). Limitation: stealthy sleepers not addressed |
| G3-2 | No benign conditional lookalikes | SA-1 includes 60; **FIX IMPLEMENTED** |
| G3-3 | SA-1 corpus confound | The first build was 0/60 vs 49/60 first-person; discarded before freezing, rebuilt with a shared instruction and gate | **VALIDATION PASSED** (test) |
| G3-4 | Shipped anomaly signal documented with a hold-out-fitted number | `phase6/defense/sleeper/signals.py`, `sleeper_guard.py`, `build_sleeper_anomaly_centroids.py` cited 145/160; the shipped centroids flag 137/171 HO8 benign | **FIX IMPLEMENTED** (docstrings corrected, behaviour unchanged; the augmented guard stays opt-in) |
| G3-5 | Labels must not reach the detector | Test: `_admission(notes)` takes text only | **VALIDATION PASSED** |

## 5. Novelty (NOV) and reproducibility (REP)

| ID | Item | Status |
|---|---|---|
| NOV-1 | Provenance-aware admission not new (TMA-NM, MemLineage, Aegis, PriceSafety) | **FIX IMPLEMENTED**: the claim is narrowed to owner-conversation corroboration + its decomposition |
| NOV-2 | Laundering through consolidation not new (TMA-NM, PPMF, MemLineage) | **FIX IMPLEMENTED** |
| NOV-3 | Trigger/non-trigger activation not new (MemPoison L3, HiddenMem, PPT) | **FIX IMPLEMENTED**: SA-1 framed as replication + lookalikes |
| NOV-4 | Storage/execution separation not new (IED, MemSecBench, HiddenMem) | **FIX IMPLEMENTED** |
| NOV-5 | Ledger = stateful detection (StatefulDet, Blacklight; A-MemGuard lessons) | **FIX IMPLEMENTED** |
| NOV-6 | Neutralisation = Spotlighting family | **FIX IMPLEMENTED** |
| NOV-7 | Real memory systems: MemSecBench/HiddenMem/TMA-NM stronger | ACCEPTED LIMITATION |
| NOV-8 | Defensible core: causal validity audit + two-denominator defence reporting | **VALIDATION PASSED** (no prior work found doing both; see the matrix) |
| NOV-9 | Previously unread papers: SMSR (2606.12703) and Leong (2606.30566) | **VALIDATION PASSED** at abstract level (RELATED_WORK §5). Both are added to the paper's related work and bibliography. Full texts are not read |
| REP-1 | Licence | BLOCKED (owner) |
| REP-2 | Model digests | **VALIDATION PASSED**: 7 tags recorded; 5 re-pulled and verified identical (the review's "no digests found" was partly wrong: 3 were pinned) |
| REP-3 | Hardware / environment | **FIX IMPLEMENTED** (`docs/release/REPRODUCE.md`) |
| REP-4 | Ollama CPU-only window 2026-10-11 17:33 → 2026-10-12 | **NEW, disclosed**: an interrupted auto-update removed CUDA libs; runs in that window used the CPU backend. Reinstall restored the GPU; the reinstall **also deleted the local model store** (re-pulled, digests identical) |
| REP-5 | `make regression` claims "no local LLM required" but a frozen-suite test loaded `llama2` | Every Ollama-backed test in that suite is `slow`-marked or self-skips when Ollama is unreachable, so the outcome is environment-independent (2,690 passed with Ollama up). The specific test was not identified | **ACCEPTED LIMITATION** (minor) |
| REP-7 (2026-10-13) | Device-dependent Phase 15 result. `phase15/tests/test_b10_per_dataset.py::test_corroboration_gate_fixes_the_real_heldout_false_positives_with_no_detection_loss` **passes with the GPU visible and fails on CPU only** (`CUDA_VISIBLE_DEVICES=-1`). The ungated B10 ConversationChronicles FPR is 10.4% on GPU vs 0.0% on CPU; the gated result (0% FPR, ≥ 90% detection) holds on both | **ACCEPTED LIMITATION**, documented. Phase 15's "gate fixes ConversationChronicles FPR" holds only on GPU. Regression counts are reported with the device stated. Not caused by the remediation (verified by running the single test both ways) |
| REP-6 | Single authoritative results pipeline | **FIX IMPLEMENTED**: `results/TABLE_INDEX.md` |

## 6. Defects introduced or found during the remediation (NEW)

| ID | Defect | Fix | Status |
|---|---|---|---|
| NEW-1 | Judge run initially executed on CPU (embedding jobs held the GPU when Ollama loaded; then Ollama had no CUDA at all) | Restarted after the Ollama repair; Python jobs now run with `CUDA_VISIBLE_DEVICES=-1` | VALIDATION PASSED |
| NEW-2 | `patch_methodology_docx.py` D8 correction not idempotent (second run duplicated a bracket) | Negative lookahead added; duplicate removed; idempotence re-verified (third run: all "already applied") | VALIDATION PASSED |
| NEW-3 | My review's §11 said no model digests were found; 3 were pinned in `phase17/OLLAMA_MODEL_PINS.md` | Corrected here (REP-2) | VALIDATION PASSED |
| NEW-4 | B13's corroboration thresholds were calibrated on LoCoMo conversations 1–4 (`provenance_sets.DEV_SAMPLES`). **Hold-out 8's owner (1) and SA-1's owner (3, chosen by this remediation) are calibration owners.** The hold-out-8 builder's "never evidence" claim is false for B13. | Disclosed in pre-registration addendum A (`4bab38c7`), committed before SA-1 ran; HO8/SA-1 B13 results are labelled "owner seen in B13 calibration"; clean-owner evidence = HO4 and HO7 | ACCEPTED LIMITATION (disclosed) |
| NEW-5 | SA-1's first run crashed at the end of its admission phase (numpy bool not JSON-serialisable), **before any agent call**, so no outcome was observed | Cast to bool; re-run as pre-registered. The crash log is kept as `remediation/logs/sleeper_activation_eval_run1_crashed.log` | VALIDATION PASSED (re-run) |
| M13 | "Unconditional harm" headline | The harm study force-inserts the poison into the top-5 when retrieval misses it; natural retrieval is 89/309 (28.8%) | Wording: "harm given exposure"; T8 and the paper state it | FIX IMPLEMENTED |

**Checkpoint hashes** of the pre-remediation `.docx` files (with their uncommitted edits):

| File | SHA-256 |
|---|---|
| Results | `3898ed8e…0882` |
| Methodology | `80deb5f5…dc12` |


## 7. Gap-closure round (2026-10-13)

Pre-registration: `docs/phase17/PREREGISTRATION_GAPCLOSURE_2026-10-13.md` (`f177c77c`; addendum B `8786ac7d`). Details: `FINAL_GAP_CLOSURE_REPORT.md`.

| ID | Issue | Action | Status |
|---|---|---|---|
| GC-1 | No real extraction-enabled pipeline (M1) | MEM-1 / MEM-2 through Mem0 `infer=True` | **VALIDATION PASSED**. M1-5 failed (retrieval 48/157); all other MEM predictions held |
| GC-2 | Leading probe (25.7% task-alone) | Net memory effect (CACHED) + PR-1 non-leading probe | **VALIDATION PASSED**: the effect is robust in existence, probe-dependent in size; PR-1b failed |
| GC-3 | 509 judge flips unexplained | ADJ-1 blind adjudication | **VALIDATION PASSED**: the adjudicator splits 60/60; labels are ambiguous (ADJ-1a failed) |
| GC-4 | Denominator-dependence of defence conclusions | Five denominators | **VALIDATION PASSED**: rankings identical |
| GC-5 | Corroboration assumptions untested | Evidence and calibration robustness (NEW) | **VALIDATION PASSED**: wrong owner and sparse evidence measured; thresholds about 3× calibration-sensitive |
| GC-6 | Explicit vs implicit sleeper confound | SA-2 | **VALIDATION PASSED**: content 0/60 on implicit rules; corroboration 40/60 vs 0/60 |
| GC-7 | Mem0 API defects (`get_all` top_k = 20; `search` ignores `limit`) | Fixed before analysis; tests added; mutation-checked | **VALIDATION PASSED** |
| GC-8 | B18 oracle threshold fitted on test data; v6 frame designed after the HO7 result; judge selection used HO5 items | Documented in `CALIBRATION_AND_LEAKAGE_AUDIT.md` | **ACCEPTED LIMITATION** |
| GC-9 | Annotator 1 = author; annotator 2 unverifiable | `DATA_LICENSING_AND_ANNOTATION_AUDIT.md` §3; the paper says so | **ACCEPTED LIMITATION** (owner action) |
| GC-10 | SA-1 evaluator test pinned a signature that the refactor changed | Test now checks the property (no label input) | **VALIDATION PASSED** |
