# Final Submission-Readiness Checklist

**Date:** 2026-10-13. **Deliverable 8.**

This supersedes `IEEE_SUBMISSION_READINESS_CHECKLIST.md` (2026-10-12). The venue and its cycle are handled by the owner. This checklist covers whether the work is **IEEE-worthy and defensible**.

**Status legend:** ✅ met · ⚠️ met with a disclosed limitation · ⛔ needs the owner · ❌ not met

## A. Scientific validity

| # | Criterion | Status | Evidence |
|---|---|---|---|
| A1 | Principal baselines reproduced, or non-reproducibility documented | ⚠️ | HO4 B13 item for item; corroboration firings item for item; SA-1 rebuilt from caches; audit C0 2,628/2,628. Model outputs were not regenerated wholesale (documented). The CPU/GPU dependence of one Phase-15 test is documented (REP-7) |
| A2 | Probe-induced compliance separated from memory-attributable behaviour | ✅ | The net paired effect is reported per population under two judges (T13). A non-leading probe was tested (PR-1, T18) |
| A3 | Judge disagreement quantified honestly | ✅ | 509/2,628 flips; blind adjudication split 60/60 (T14). Human-calibration caveats are stated |
| A4 | Working-attack denominator explicit | ✅ | Five denominators; rankings stable (T13, T3) |
| A5 | Harm conditional on exposure not presented as end-to-end | ✅ | Paper §5; real-pipeline stages in §6 / T16 (48/157 retrieved; 29 working) |

## B. Real memory pipeline

| # | Criterion | Status | Evidence |
|---|---|---|---|
| B1 | Real extraction-enabled pipeline evaluated | ✅ | Mem0 2.0.19 `infer=True`, HO4 + SA-1 (MEM-1 / MEM-2) |
| B2 | Ingestion, storage, retrieval, activation distinguished | ✅ | Stage tables in `REAL_MEMORY_PIPELINE_EVALUATION.md` §5 |
| B3 | Not generalised beyond the tested scenarios | ✅ | Stated in the paper (§6 and limitations) |

## C. The three gaps

| # | Criterion | Status | Evidence |
|---|---|---|---|
| C1 | Gap 1: source labels and corroboration separated | ✅ | Decomposition (T5); real pipeline (T16) |
| C2 | Gap 1: user-channel behaviour and assumptions explicit | ✅ | Threat-model table; 0 excluded by construction |
| C3 | Gap 1: benign rejection costs reported | ✅ | Every recall is paired with its same-condition FPR |
| C4 | Gap 1: owner overlap and generalisation limits disclosed | ✅ | `CALIBRATION_AND_LEAKAGE_AUDIT.md`; threshold sensitivity (T15) |
| C5 | Gap 2: survival and containment by generation | ✅ | Gen 1 and gen 2 table (`THREE_GAPS_FINAL_STATUS.md`) |
| C6 | Gap 2: persistence vs causal harm distinguished | ✅ | Carry judge vs harm judge |
| C7 | Gap 2: flag-inheritance dependence tested | ✅ | S-noinh arm: 0/71 withheld |
| C8 | Gap 3: dormancy and activation measured separately | ✅ | SA-1, SA-2, MEM-2 |
| C9 | Gap 3: explicit wording vs sleeper-specific evidence distinguished | ✅ | SA-2 (implicit: content detection 0/60); MEM-2 (wording stripped: 60 → 22/60) |
| C10 | Gap 3: benign conditional rules included | ✅ | 60 lookalikes in SA-1 and in SA-2 |
| C11 | Gap 3: failed sleeper detectors documented | ✅ | Guard 0 everywhere; anomaly non-discriminative |

## D. Reproducibility

| # | Criterion | Status | Evidence |
|---|---|---|---|
| D1 | Principal results trace to code, data, configuration and outputs | ✅ | `results/TABLE_INDEX.md` (T1–T18). Paper numbers are generated, and a test fails on undefined or pending macros |
| D2 | Executed test scope reported accurately | ✅ | `FINAL_GAP_CLOSURE_REPORT.md` §8 |
| D3 | No hold-out silently reused for calibration | ✅ | HO4 / SA-1 re-use for MEM is declared a second use of a new quantity; no fitting |
| D4 | Licensing documented | ⚠️ | Inventory complete. **No licence applied** (owner) |
| D5 | Annotation provenance documented | ⚠️ | Verified facts recorded; **annotator 2's independence is unverifiable** |
| D6 | Model digests and environment | ✅ | `docs/release/REPRODUCE.md`; Mem0 environment recorded |

## E. Manuscript

| # | Criterion | Status | Evidence |
|---|---|---|---|
| E1 | Every claim matches the authoritative artifacts | ✅ | Numbers generated; prose outcome-generated with HELD/FAILED labels |
| E2 | Three research gaps explicit | ✅ | RQ2–RQ4, plus RQ1 (validity) |
| E3 | Novelty separated from implementation and benchmark differences | ✅ | Contributions framed as evaluation methodology; `NOVELTY_MATRIX.md` §2 |
| E4 | Compiled and visually inspected | ❌ | **No TeX toolchain on this machine.** Source lints clean. Compile with `latexmk -pdf main.tex` (or Overleaf) in `paper/`, then check length, overflow and references |
| E5 | Abstract and conclusion no stronger than the results | ✅ | Both generated from the same artifacts; the sleeper claim is qualified by the Mem0 result |
| E6 | No generalisation claim from overlapping or contaminated hold-outs | ✅ | Clean-owner claims use HO4 and HO7 only |
| E7 | Anonymity | ✅ | No names, URLs or institutions in `paper/` |

## F. Owner actions remaining (minimum set)

1. **Compile** `paper/` and check page count, overflow and figures. A figure of the lifecycle-stage funnel from T16 would help reviewers.
2. **Annotators.** Record who annotator 2 was. Ideally, add an unaffiliated annotator on a fresh blind sample (about 100 items); the human-calibrated judge rests on this.
3. **Licence decision** and anonymised artifact repository (CC BY-NC constraints documented).
4. **Venue.** Owner-handled; check the official call before formatting to a page limit.
5. **Optional, highest scientific value next:** per-owner leave-one-out calibration of corroboration (Gap 1 stability), and a fresh independent human annotation (gap 1 in the severity table).
