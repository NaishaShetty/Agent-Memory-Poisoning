# Final Remediation Report

**Date:** 2026-10-12. **Branch:** `remediation/2026-10-12`, from checkpoint tag `pre-remediation-2026-10-12` (`d853404a`). Nothing was pushed or submitted.

**Companion files**

| File | Contents |
|---|---|
| `REMEDIATION_MASTER_REGISTER.md` | Every issue and its status |
| `THREE_RESEARCH_GAPS_AUDIT.md` | One assessment per research gap |
| `EXPERIMENTAL_VALIDITY_AUDIT.md` | Evaluation units, validity, hold-outs, statistics |
| `RELATED_WORK_AND_NOVELTY.md` | Primary-source comparison |
| `results/TABLE_INDEX.md` | Every authoritative table and the code behind it |
| `paper/` | The manuscript |
| `docs/release/` | Reproduction and licensing |
| `IEEE_SUBMISSION_READINESS_CHECKLIST.md` | Submission checklist |

---

## 1. Outcome in one paragraph

The project's most defensible contribution is the causal attack-validity protocol with defence detection reported on both denominators. With that protocol, three single-use memory-poisoning hold-outs show the following. Corroborating untrusted personal claims against the owner's conversation (B13) reaches 50–74% of note-shaped poisoning where a fused content classifier reaches 20–43%, at an 8.8–15.3% untrusted-channel benign cost. **All** of that gain is corroboration: the channel label adds no recall, and poison on the user channel is never excluded.

Two earlier claims did not survive re-analysis:
- the hold-out-8 sleeper anomaly and "generalised union" result, which had been calibrated on its own hold-out;
- the hand-typed "39-point" lead.

Both are corrected at their source.

The remediation also found that:
- the validity audit's fitted probe is leading;
- B13's thresholds were calibrated on the owners of hold-out 8 and SA-1;
- the harm study force-inserts the poison 71% of the time.

All three are disclosed.

Two new pre-registered experiments measured the evidence that was missing:
- sleeper activation with benign lookalikes, for Gap 3;
- two-generation propagation, for Gap 2.

The results are in §4.

The manuscript is drafted, built from generated numbers. It is **not yet ready to submit**. It needs owner decisions (venue, licence, annotator details) and compilation (§8).

---

## 2. Issues resolved and unresolved

Full detail is in `REMEDIATION_MASTER_REGISTER.md`. Summary by status:

| Status | Issues |
|---|---|
| **VALIDATION PASSED** | M2, M3, M5, M7, M8, M11, M12; D1–D7, D10, D12, D15, D16; G1-1–3, G2-2–4, G3-1, G3-3, G3-5; NOV-8, NOV-9; REP-2; NEW-1, NEW-2, NEW-3, NEW-5 |
| **FIX IMPLEMENTED** (paper or documentation; no separate validation possible beyond review) | M6, M13, D8, D11, D13, D14, P0-1–3, P1-6, NOV-1–6, REP-3, REP-6, G3-2, G3-4 |
| **ACCEPTED LIMITATION** (disclosed) | M1, M4, M9, M10 (pending owner input), D9, G1-4, NOV-7, NEW-4, REP-5 |
| **BLOCKED on the owner** | P0-9 / REP-1 (licence), M10 / P1-5 (annotator details), A1–A2 (venue) |
| **OPEN** | P2-1 (Mem0 `infer=True` replication), P2-2 (more human labels), P2-3 (stronger agent on a hold-out) |

---

## 3. Files modified or added

**Code and analyses (new):** `phase17/remediation/`

| Module | Purpose |
|---|---|
| `validity_judge_sensitivity.py` | Re-judge the validity audit with C1 and C3 |
| `ho8_anomaly_devfit.py` | Hold-out 8 anomaly thresholds without leakage |
| `b13_decomposition.py` | Split B13 into its rules |
| `predictions_tally.py` | Reconcile prediction counts |
| `sleeper_corpus.py` | Build and freeze the SA-1 corpus |
| `sleeper_activation_eval.py` | SA-1 |
| `propagation_2gen.py` | P2 |
| `authoritative_tables.py` | Generate every table from artifacts |
| `paper_numbers.py`, `paper_prose.py` | Generate the paper's numbers and outcome text |
| `patch_methodology_docx.py` | Logged corrections to the Methodology |

**Tests (new):** `phase17/tests/test_remediation.py` (18 tests).

**Code (modified; documentation only, behaviour unchanged):**
- `phase6/defense/sleeper/signals.py`
- `phase6/defense/sleeper/sleeper_guard.py`
- `phase17/build_sleeper_anomaly_centroids.py`

All three corrected the hold-out-8 claim.

**Generator (modified):** `phase17/build_results_analysis_docx.py`
- D2–D4, D6, D7 corrections.
- A new §15 reporting the remediation.

**Documents:**
- `Methodology Draft.docx`: patched; log in `remediation/logs/methodology_patch_log.json`.
- `MAMBench Results Analysis.docx`: rebuilt.
- `phase17/OLLAMA_MODEL_PINS.md`: extended.

**Pre-registration:** `docs/phase17/PREREGISTRATION_REMEDIATION_2026-10-12.md`, commits `5bf5a230` (design) and `4bab38c7` (addendum A).

**New artifacts:** `phase17/data/remediation/*`. Every pre-existing artifact and frozen corpus is unchanged.

---

## 4. Experiments run and results changed by the corrections

| Analysis / experiment | Kind | Result | Effect on the claims |
|---|---|---|---|
| Judge sensitivity of the validity audit (10,512 judge calls on cached answers) | Recompute | Fitted-probe working rate: 25.3% (C0) vs 27.1% (vote); own populations 40.8% vs 44.3%. 509 of 2,628 instances change status. The fitted probe's task-alone base rate is 25.7% (C0) and 47.4% (vote), above the project's 20% rule. | Population rates hold; instance membership does not; the rates are lower bounds where the probe leads. |
| HO8 anomaly / union, re-thresholded | Recompute | Original reproduced exactly. Leak-free owner-adaptive: 131/160 at 4/85. Dev-fitted: 138–158/160 at 99–142/171. **Shipped signal: 159/160 at 137/171 (80%) benign.** | The "generalised union / planted-memory detector" claim is withdrawn. |
| B13 decomposition (HO4, HO7, HO8) | Recompute; HO7 components recomputed, item-for-item equal | B13 without corroboration = B12 on every hold-out. Corroboration contributes +76, +22 and +59 attacks, at +27, +21 and +8 benign false positives. User-channel poisoning: 0 excluded. | Provenance claim narrowed to corroboration under a channel assumption. |
| Prediction tally | Recompute | 17/20, 34/41 and 39/47 are reproducible snapshots of different scopes. With HO8 included: 45/53 held. U-2 never scored. | D1, D2 resolved. |
| Baseline lead | Recompute | 32.1 points (B13) / 37.2 (B17) over deberta@dev. | Replaces "nearly 39". |
| Harm discrepancy | Trace | Different answer sets; judge-only variation of 5/309. | D5 explained. |
| **SA-1** (pre-registered) | New experiment | Dormant: 0/60 activation on unrelated messages. Activated: 23/60 (C0) / 42/60 (vote) on natural triggers via real retrieval. B12/B13 excluded 60/60 attacks and 2–3/60 benign conditional lookalikes before activation, because the payloads are explicit. Phase 8 guard 0/60; anomaly flags 60/60 lookalikes; v6 frame cuts activation 23 → 5. SA-1 to SA-9 all HELD. | Gap 3 partly demonstrated, for explicit-payload conditional rules. Stealthy sleepers are not addressed. |
| **P2** (pre-registered) | New experiment | Payload survives a 2nd consolidation in 98/249; laundering harm 22/161. Best containment withholds 24/71 carrying descendants (75% at gen 1 → 34% at gen 2), only via state inheritance; 0 without. Harm 22 → 13. P2-1/2/3/4 HELD, P2-5 FAILED. | Gap 2: containment decays across generations; development only. |

---

## 5. Tests executed (actual commands and outcomes)

All runs below took place on 2026-10-12, on branch `remediation/2026-10-12`, with Ollama 0.40.3 on CUDA and the model digests verified. Logs are in `remediation/logs/`.

| Command (abbreviated) | Outcome | Log |
|---|---|---|
| `pytest phase6/ phase8/ phase11/ phase12/ phase13/ phase14/ phase15/ attribution/ phase7/ phase3/ -m "not slow"` (the frozen part of `make regression`) | **2,690 passed, 0 failed, 30 skipped, 9 deselected** (slow). The 30 skips are real-runtime tests: the Mem0/A-MEM adapters and llama-server are not installed in this interpreter, by design | `final_regression_frozen.log` |
| `pytest` on the `make phase17-structural` set + `phase17/tests/test_remediation.py` | **97 passed, 0 failed** | `final_regression_phase17.log` |
| `pytest phase17/ -m "not slow"` (`make phase17-live`: all Phase 17 tests, needs Ollama) | **196 passed, 0 failed** | `final_phase17_live.log` |
| `pytest phase17/tests/test_remediation.py` (alone, earlier) | 17 passed, after the PENDING values were resolved | — |
| Mutation check of the new security tests (4 injected defects: user channel untrusted; missing provenance trusted; decay changed; dev-fit reading HO8) | **4/4 caught** | this report |
| Baseline before changes (frozen suite) | **Incomplete.** Stopped at 26% (all passing) when it contended with the CPU-only Ollama for resources. No full pre-change baseline exists | `pretest_regression_frozen.log` |

**Not run:**
- Tests marked `slow`: 9 in the frozen suite and Phase 17's slow tests. These are hours of live LLM work.
- The isolated A-MEM / Mem0 environment stages (`make amem-live`, `make mem0-live`).

The project's earlier "3,511 passed" audit figure was **not** reproduced as a single number here. Its composition was not re-derived.

**REP-5 (llama2 during the frozen suite).** Every Ollama-backed test in that suite is either marked `slow` or skips when Ollama is unreachable, so the suite's outcome does not depend on Ollama. The specific test that loaded llama2 during the first run was not identified.

---

## 6. Remaining scientific limitations

1. No security result runs through a production memory system end to end.
2. Channel labels are evaluator-assigned. User-channel poisoning is not addressed.
3. Harm is measured given exposure, with 71% of poisons force-inserted.
4. The agent is 7B only. The harm judge is weak (kappa 0.2), and a better judge finds about twice the harm level.
5. The validity audit's fitted probe is leading, so instance-level working status depends on the judge.
6. Hold-out 8's and SA-1's owners were seen in B13's calibration.
7. The ledger and adaptive results are development-only, and cover a single attacker type.
8. Corroboration's benign cost (9–15%) restricts it to review-queue deployments.

---

## 7. Final status of each research gap

| Gap | Final status | Strongest defensible claim |
|---|---|---|
| **1. Provenance and governance** | **Demonstrated within stated assumptions; governance partial** | Corroboration of untrusted personal claims reaches 50–74% of note-shaped poisoning on three single-use hold-outs (20–43% for a fused content classifier), at 8.8–15.3% untrusted-benign cost. The channel label adds no recall and leaves the user channel open. Clean-owner evidence: HO4 and HO7. |
| **2. Self-propagation** | **Partially demonstrated** (development + HO8 gen 1) | A poison excluded at admission returns through consolidation (33/161 harmful at gen 1, 22/161 at gen 2). Semantic lineage taint withholds 75% → 34% of carrying descendants across two generations, only via inherited state, only for admission-detected poisons, at 37% → 8% loss of legitimate derived memory. |
| **3. Sleeper / dormant** | **Partially demonstrated** | Conditional rules are dormant and activate on natural triggers. Explicit-payload rules are stopped before activation by content detection at 2/60 benign-lookalike cost. Every sleeper-specific detector failed: the guard flags 0%, and the anomaly signal mostly detects distribution shift. Stealthy sleepers remain unsolved. |

The three gaps stay separate research questions on one lifecycle (`THREE_RESEARCH_GAPS_AUDIT.md` §4). None is solved.

---

## 8. Ready for independent submission review?

**Not yet ready for submission. Ready for an independent pre-submission review of the manuscript draft**, once these items are done:

1. **Compile** `paper/main.tex` (no TeX here) and fit it to the venue's page limit.
2. **Venue decision.** SaTML 2027's deadline has passed. S&P 2027 and EuroS&P 2027 deadlines are probably mid-November 2026, but the official calls are unconfirmed.
3. **Licence decision** and an anonymised artifact repository. Many venues now require artifacts at submission.
4. **Annotator details** (identity, independence, instructions).

The scientific content is now internally consistent and traceable to artifacts.

**What a reviewer will still see as the main weaknesses:**
- an in-context harness rather than a production memory system;
- a 7B agent;
- evaluator-assigned channels;
- development-only propagation and ledger results;
- moderate novelty relative to 2026 work (TMA-NM, MemLineage, MemPoison, MemSecBench).

**The largest single improvement available:** run hold-out 4 and SA-1 through Mem0 with LLM extraction enabled (register P2-1). It addresses the harness limitation directly.
