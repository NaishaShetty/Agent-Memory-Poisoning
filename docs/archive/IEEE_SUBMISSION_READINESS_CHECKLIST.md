# IEEE Submission Readiness Checklist

**Date:** 2026-10-12. **Deliverable 10.**

Every item is objective: it either can be checked from a file or command, or it is marked as needing a decision from the owner. "Readiness" here means ready for an **independent pre-submission review**. It does not mean ready to submit.

**Status legend:** ✅ done · ⚠️ done with a disclosed limitation · ⛔ blocked on owner · ❌ not done

---

## A. Venue and format

| # | Item | Status | Evidence / action |
|---|---|---|---|
| A1 | Target venue chosen | ⛔ | See the venue note below. |
| A2 | Official call for papers re-checked (page limit, anonymity, required sections) | ⛔ | No official 2027 call was found for S&P or EuroS&P. The owner must confirm before formatting to a limit. |
| A3 | IEEE template | ✅ | `paper/main.tex` uses `IEEEtran` (conference, compsoc). |
| A4 | Compiles to PDF | ❌ | No TeX toolchain on this machine (pdflatex, xelatex and pandoc are absent). Compile on Overleaf or TeX Live and check the page count. |
| A5 | Anonymised | ✅ | No author names, institutions or repository URLs in `paper/`. The Open Science section refers to an anonymised repository. |
| A6 | Ethics and Open Science sections | ✅ | Present in `paper/main.tex`. |
| A7 | Page budget | ❌ | Unknown until compiled (A4). The draft body is about 3,700 words plus 4 tables, likely 6–8 two-column pages: **under** typical limits, not over. Expand from `THREE_RESEARCH_GAPS_AUDIT.md` and `results/tables` as needed. The best candidates are a B13 method figure, the per-family table, SA-1 and P2 tables, and the formulas appendix. |
| A8 | LaTeX structure lint | ✅ | Environments balanced; all citations resolve, none unused; all `\ref`s have labels; braces balanced. Checked with a lint script, not a compile. |

**Venue note (A1).** The SaTML 2027 paper deadline was **29 September 2026, so it has passed** (satml.org/participate-cfp, read 2026-10-12). The likely options about a month out are:

- **IEEE S&P 2027.** Aggregators report about 10–17 November 2026. No official call has been found.
- **IEEE EuroS&P 2027.** The call is not yet published; the 2026 edition's deadline was 13 November 2025.
- **IEEE TIFS or TDSC.** Rolling submission, longer format.

The owner decides.

## B. Scientific content

| # | Item | Status | Evidence |
|---|---|---|---|
| B1 | Research questions answerable and answered | ⚠️ | Gaps 1–3 assessed separately with new pre-registered experiments (P2, SA-1). Gap 1 demonstrated within its assumptions; Gaps 2 and 3 partial (`THREE_RESEARCH_GAPS_AUDIT.md`). |
| B2 | No unsupported "first" or novelty claims | ✅ | The paper's contributions are narrowed per `RELATED_WORK_AND_NOVELTY.md` §3; no "first" claim is made. |
| B3 | Related work from primary sources | ⚠️ | Main texts were read. Two papers are not yet read (NOV-9). |
| B4 | Threat model states the load-bearing assumptions | ✅ | `main.tex` §3 covers channel labels and user-channel poisoning. |
| B5 | Evaluation units stated (no "real memory system" overclaim) | ✅ | Table 1 of the paper; `EXPERIMENTAL_VALIDITY_AUDIT.md` §1. |
| B6 | Hold-out leakage removed from generalisation claims | ✅ | The HO8 anomaly is corrected; HO3 is excluded; HO8 and SA-1 owners are labelled. |
| B7 | Every headline number traceable | ✅ | Macros are generated from `results/tables`, and a test fails on undefined or pending macros. |
| B8 | Statistics: paired tests, intervals, multiplicity, pre-registered vs exploratory | ✅ | The paper's §9 and the audit's §4. |
| B9 | Failed and negative results retained | ✅ | All predictions are tallied by kind, failures included. |
| B10 | Limitations explicit | ✅ | Paper §10; audits. |

## C. Reproducibility and release

| # | Item | Status | Evidence |
|---|---|---|---|
| C1 | Environment and dependencies pinned | ✅ | `requirements-lock.txt`; `docs/release/REPRODUCE.md`. |
| C2 | Model digests | ✅ | 7 tags recorded; 5 re-verified identical after the re-pull. |
| C3 | Frozen manifests and integrity checks | ✅ | SHA-256 per hold-out and SA-1; `verify_frozen()` runs before every evaluation. |
| C4 | One command per principal table | ✅ | `python -m phase17.remediation.authoritative_tables`. |
| C5 | Licence | ⛔ | Owner decision. The constraints (CC BY-NC sources) are in `docs/release/LICENSING_AND_DATA_RIGHTS.md`. |
| C6 | Anonymised artifact repository | ⛔ | Needs the owner. It cannot be published until the licence is decided. |
| C7 | Known non-determinism documented | ✅ | `REPRODUCE.md` §3. |

## D. Integrity of the record

| # | Item | Status | Evidence |
|---|---|---|---|
| D1 | Every review finding has a status | ✅ | `REMEDIATION_MASTER_REGISTER.md`. |
| D2 | Pre-registrations committed before their runs | ✅ | `5bf5a230` and `4bab38c7` precede the SA-1 and P2 artifacts (`git log`). |
| D3 | Internal numerical contradictions reconciled | ✅ | D1–D16. |
| D4 | Annotator information (identity, independence, instructions) | ⛔ | Not recorded in the repository; the owner must supply it. |
| D5 | Test suite run and documented | ✅ | Frozen suite: 2,690 passed / 0 failed / 30 skipped. Phase 17 live: 196 passed / 0 failed. Phase 17 structural + remediation: 97 passed. 4/4 mutations caught. Slow tests not run (`FINAL_REMEDIATION_REPORT.md` §5). |

## E. Owner actions before submission (minimum set)

1. Choose the venue (A1–A2) and compile the paper (A4, A7).
2. Decide the licence and create the anonymised artifact repository (C5–C6).
3. Supply the annotator details (D4).
4. Read the two unread related papers (NOV-9).
5. Decide whether to run the optional P2-1 check (HO4 through Mem0 with extraction on). It would address the largest external-validity limitation (M1).
