# Defence v6: Final Report

**Date:** 2026-10-15. **Branch:** `remediation/2026-10-12`. **Commits:** `2fcedf1c` (Phase 0) … this report. **Nothing was pushed.**

**Constraints honoured:**
- `phase17/data/run_all_logs/` was not touched.
- Earlier results, pre-registrations and judge caches were left in place; the shared caches changed **by additions only** (verified per commit).

**Reports:**

| # | Report |
|---|---|
| 1 | `DEFENCE_V6_BASELINE_AND_ROOT_CAUSE_AUDIT.md` |
| 2 | `DEFENCE_V6_PROVENANCE_AND_GOVERNANCE.md` |
| 3 | `DEFENCE_V6_PROPAGATION_AND_LINEAGE_RECOVERY.md` |
| 4 | `DEFENCE_V6_SLEEPER_INFORMATION_BOUNDARY.md` |
| 5 | `DEFENCE_V6_INTEGRATION_AND_ABLATION.md` |
| 6 | `DEFENCE_V6_GAP_CLOSURE_ASSESSMENT.md` |
| 7 | This report |

## 1. Outcome

| Gap | Before | After | Change driven by |
|---|---|---|---|
| 1. Provenance and governance | 59% | **64%** | End-to-end prevention of explicit attacks after Mem0 (8 → 0, p = 0.008) |
| 2. Self-propagation and containment | 65% | **65%** | None: PRC is now significant on a powered set but misses the 60% bar by one root |
| 3. Dormant and implicit sleepers | 29% | **34%** | Two-stage defence: implicit activation 19 → 4/48 (Holm p = 8.2e-4), legitimate rules kept usable |

**No gap reaches 75%.** The scores are not combined.

## 2. Answers to the final questions

1. **Can provenance be preserved reliably across Mem0 extraction and UPDATE events?**
   Yes, but only outside Mem0's payload.
   - Mem0 2.0.19's extraction is ADD-only: 0 natural UPDATEs in 680 ingestions.
   - The channel survives extraction natively (622/622).
   - A forced API UPDATE relabelled the source to "user" in Mem0's metadata 183/183 times, and Mem0's history recorded no writer (0/183).
   - The append-only ledger kept the true source 183/183.
   - These labels are application-recorded, not authenticated.

2. **Can the defence distinguish source identity from claim maliciousness?**
   Yes, in representation and use. The ledger keeps channel and principal, claim, evidence support (B13), maliciousness (B12 on the source claim) and link validity separate. PAB13 uses source to decide whether corroboration applies: user-channel legitimate rules go from 9/23 excluded to 0/23, with detection unchanged. It cannot authenticate the source.

3. **Can incorrect lineage be detected without excessive benign blocking?**
   Yes.
   - FLV accepted 0/265 wrong links and 258/265 correct ones.
   - Under 5 corruption types, benign exclusion rose by ≤ 0 points.
   - Without validation, duplicates add +7.3 points, and a forged "user" relabel disables implicit detection (31 → 0).

4. **Can root claims be tracked across repeated instruction-style paraphrasing?**
   Partly.
   - On single-step transformations, the entailment-led fingerprint HFP-B tracks 92.9% with 2.1% benign false match.
   - Through 4 real consolidations, it finds the claim in only 19 of 73 judge-carrying descendants.
   - Containment by PRC (route + NLI/similarity) holds 43/73 at generation 4, against 18/73 for the frozen guard.

5. **Can lineage be recovered when it was deleted after writing?**
   - **Yes, exactly, if an append-only taint log survives:** 296/296 correct, 0 false associations.
   - **No, if the memory was also rewritten afterwards** (simulated): the right root is found 295/296 times, but 76% of the owner's memories attach to tainted roots.

6. **Can implicit sleepers be detected after Mem0 transformation?**
   Not within the pre-registered limits.
   - The frozen operating point detects 79% (38/48) but flags 11.1% of legitimate ungrounded rules (limit 10%).
   - Two non-selected conditions met the limits on eval; they are exploratory.

7. **What information is necessary for reliable sleeper detection?**
   **Who wrote the rule, recorded for every memory.**
   - Content alone flags 23% of legitimate rules.
   - The channel removes user-channel false positives but not those from document-borne or unrecorded legitimate rules.
   - A simulated authenticated principal still flags 32%, all of it from missing provenance.
   - The original record restores signal lost to rewriting (explicit 32 → 46).

8. **Does preserving the original source record improve sleeper detection?**
   Yes, against the transformed text: implicit 34 → 38, explicit 32 → 46, at 15 → 16 ungrounded false positives. It also enables the two-stage defence's activation control.

9. **Can activation and harmful behavioural influence be reduced?**
   Yes, on held-out data after Mem0 transformation.
   - Sleepers: implicit unconfirmed activation 19 → 4/48 and explicit 8 → 0/48 under TS, with legitimate untrusted-channel rules still used (60 → 70/121).
   - Propagation: generation-4 influence 19 → 10/265 under PRC (p = 0.004).

10. **Does the integrated defence outperform the baseline without unacceptable utility loss?**
    Partly.
    - The combined system cuts implicit activation to 2 against the baseline's 7 (p = 0.06, not significant).
    - It is not significantly better than TS alone (4), and it excludes 35 legitimate memories that TS keeps.
    - **TS alone has the best trade-off.** The ledger is essential: without it, activation returns (2 → 19, p = 2e-5).

11. **What are the new evidence-based closure scores?**
    Gap 1 **64%**, Gap 2 **65%**, Gap 3 **34%**, under the frozen rubric.

12. **Which critical limitations still prevent 75%?**
    - **Gap 1:** 1.1 and 1.3 are capped by noisy source verdicts. B12 flags unusual harmless rules; corroboration flags legitimate document-borne rules.
    - **Gap 2:** 2.2 is one root short of 60%, with non-carrying collateral at 29%; 2.6 fails after a post-deletion rewrite.
    - **Gap 3:** 3.2 and 3.3 together carry 55% of the weight and both score 0, because legitimate rules from untrusted or unrecorded sources look like attacks.

13. **Which exact API, metadata or architectural changes would enable further progress?**
    - **Mem0:**
      - persist an authenticated writer principal and a source-span pointer on every ADD and UPDATE, including the infer path's batch history (today `actor_id` is stripped and not written);
      - make UPDATE append a writer, not overwrite it;
      - keep the extracted memory's source text.
    - **Application:** require a recorded source for every memory (no missing provenance), and log consolidation and UPDATE events with parent ids so that recovery after a rewrite is a lookup, not a similarity match.
    - **Containment:** sentence-level claim fingerprints against the root's claim set; no-decay scoring (ND more than doubled generation-4 containment) combined with PRC routing.

14. **Is the programme ready to freeze?**
    - **Yes, as a record:**
      - every pre-registered test has been run and reported;
      - every defect is disclosed, with its defective output kept;
      - the documents are regenerated from the artifacts;
      - Phase 17 tests pass (244/0);
      - the frozen suite has 3,001 passed and 1 thread-count-sensitive failure in a Phase 11 GNN test that v6 does not touch (passes with default threads; see §6).
    - **No, as a closure claim:** none of the three gaps reaches 75%, and further progress needs the interface changes in Q13, not more tuning.

## 3. Claim-to-source map

| Headline claim | Source file → key | Commit |
|---|---|---|
| 0 natural UPDATEs; forced UPDATE relabels 183/183; ledger keeps 183/183 | `sa6_mem0_stage.json`; `g1_eval.json` → provenance, forced_update | `0419f468`, `acc5bd52` |
| PCL explicit 44/48 vs B13 16/48 (single); 38/48 vs 10/48 (MSD); MSD benign +16 points | `g1_eval.json` → single_notes.P1a, msd.P1b | `acc5bd52` |
| FLV: wrong-link acceptance 0/265; corruption table | `g1_eval.json` → flv | `acc5bd52` |
| HFP-B 92.9% / 2.1% / 2.5% on FPB eval | `fpb_eval.json` → arms.HFP-B.all | `d3ec93fd` |
| PRC 43/73 vs FG 18/73 at gen 4, Holm p = 6.8e-4; influence 19 → 10 | `g2_eval.json` → by_payload.instruction; `closure_v6.json` → holm | `2057eb0e`, `fab582da` |
| Recovery C1 296/296 (0 false associations); C2 76% false association; B = A 296/296 | `g2_eval.json` → recovery_HFP-B; `g2_wtp_check.json` | `2057eb0e`, `6c61566a` |
| TS implicit 19 → 4/48, explicit 8 → 0; legitimate 60 → 70/121 | `g3_eval.json` → behaviour | `c10e03b3` |
| Operating point D 38/48, 16/144, 0/48 | `g3_eval.json` → P2_operating_point | `c10e03b3` |
| Native-metadata ablation 2 → 19 (p = 2e-5) | `integration_eval.json` → paired_tests | `fab582da` |
| Closure 64 / 65 / 34 | `closure_v6.json` | `fab582da` |

## 4. Deviations and unrun experiments

| Item | Status |
|---|---|
| HO9 author model was missing; re-installed with the user's permission (`mistral:7b-text`, digest 495ae085) | Deviation (environment). The first attempt produced 0 roots (`*_DEFECTIVE_*`) |
| Factual top-up aborted for compute (≈ 15 s per seed, 22% kept) | Deviation. The factual subset is underpowered (31 flagged roots) |
| Pre-registered HFP failed dev selection; HFP-B added by addendum A from dev evidence only | Disclosed; original HFP evaluated and reported |
| Gap-1 defects (FLV conflict exemption; inheritance from the wrong event) fixed before any outcome | Disclosed |
| Gap-1 claim-pooling defect found in the first eval run; corrected to the pre-registered per-event rule | Disclosed; `g1_*_DEFECTIVE_pooled_event_claims.json` kept |
| Condition B equality asserted by a placeholder in `g2_eval.json` | Recomputed (`g2_wtp_check.json`, 296/296) |
| Recovery C2 uses a **simulated** post-deletion rewrite | Labelled as a simulation |
| Condition S is a **simulation** of authenticated authorship | Never credited |
| Gap-3 dev behaviour run limited to `atk_implicit` + `ben_unground` (64 items) as a sanity check | No choices depended on it |
| Not run | A real user-confirmation study; authenticated identity in Mem0 (needs API change); a powered factual-payload set; a fresh held-out test of the exploratory conditions E and C∧K |

## 5. Recommended next-version architecture

1. **Write:** authenticated principal plus source pointer on every memory event (Mem0 change); no memory without a recorded source.
2. **Admission:** PAB13. Apply corroboration only to non-user-sourced memories; claim-level inheritance only through FLV-valid links.
3. **Propagation:** PRC with no-decay root scoring; sentence-level claim fingerprints; consolidation events logged with parent ids so recovery after a rewrite is exact.
4. **Retrieval:** the two-stage defence. Restore the original rule plus the unverified frame for untrusted-sourced conditional memories.
5. **Evaluate next:**
   - condition E (validated lineage) as the Gap-3 operating point, on a fresh set;
   - a confirmation loop with real users, to measure whether framed rules are declined.

## 6. Tests

| Suite | Result | Log |
|---|---|---|
| `pytest phase17/ phase17/leakage_audit.py -m "not slow"` | **244 passed / 0 failed** (230 earlier + 14 v6) | `phase17/defence_v6/logs/tests_phase17.log` |
| Frozen phases (3–8, 11–15), `-m "not slow"`, `OMP_NUM_THREADS=8` | 3,001 passed / **1 failed** / 32 skipped | `tests_frozen.log` |
| Frozen phases, default threads | **3,002 passed / 0 failed / 32 skipped / 9 deselected** | `tests_frozen_default_threads.log` |

**The one failure:**
- **Test:** `phase11/tests/test_gnn_train.py::test_real_benign_volume_stabilizes_detection_rate_across_seeds`.
- **Cause:** sensitive to the CPU thread count. With 8 OpenMP threads one training seed scores 0.706 instead of 1.0; with default threads all 6 tests in the file pass.
- **Relation to v6:** `phase11` is unchanged since v6 began. This is a pre-existing determinism issue in that test.
