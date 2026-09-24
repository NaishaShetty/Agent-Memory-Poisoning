# Phase 15 Plan — The Cross-Cutting Sweep

Status: **proposal, not a decision** — same discipline `PHASE12_PLAN.md` and `PHASE14_PLAN.md`
used. Nothing below is implemented; Section 6's open questions need real answers before any code
is written.

## 1. Research Question

*"Across every real defense configuration this project has built (B0–B10), every real attack
family (7), and every real dataset (4), does security detection, attribution quality, and agent
utility cost tell a CONSISTENT story — or does some real combination this project has never looked
at together reveal a gap none of Phases 12–14 could see on their own, working one metric family at
a time?"*

Per `docs/phase12/PHASE12_PLAN.md` Section 2 (the project's own original division of this arc,
never revisited until now): Phase 15 is "the full attack × dataset × workload × defense-
configuration matrix, all three metric families together." The workload axis was already
discussed and dropped during Phase 12 (`PHASE12_SECURITY_METRICS_REPORT.md` line 489) — it is not
reopened here. This leaves a real 3-dimensional matrix: **attack family × dataset × defense
configuration**, with security, attribution, and utility as three real measurements taken at each
cell, not three separate matrices.

## 2. What Already Exists, Per Axis — and the Real Gap Each One Has

| Axis | What Phase 12/13/14 already measured | The real gap |
|---|---|---|
| **Security** (Phase 12) | `phase12/evaluation_matrix.py::run_security_matrix()` already swept **B0–B8 (9 configs) × 4 datasets (LoCoMo, LongMemEval, MSC, ConversationChronicles) × 7 attack families** — the closest thing to a real cross-cutting matrix that already exists. | **B9 and B10 are NOT in this matrix.** They were measured separately (`phase11/gnn/real_attack_corpus_detector.py`, a different corpus/harness/report format) — real, trustworthy numbers, but not in the same per-cell shape as B0–B8's matrix, so they cannot currently be compared cell-for-cell against the rest. |
| **Attribution** (Phase 13) | `phase13.attribution_metrics.compute_attribution_metrics()` measured real source accuracy, path fidelity, and confidence correlation against **one fixed, shared ledger** (15 real poison scenarios + 4 multi-source cases, 19 real derivation events total). | **No per-dataset or per-defense-configuration breakdown exists at all.** Every attribution number in Phase 13 is a single aggregate over one ledger — never swept across LoCoMo vs. LongMemEval vs. MSC vs. ConversationChronicles, and never computed "under B3" vs. "under B7" the way security's matrix is. This is the single largest real gap of the three axes. |
| **Utility** (Phase 14) | `phase14/campaign.py::run_full_pilot()` measured real task success, URS, and poison protection for **B0/B1/B9 only, on LoCoMo/LongMemEval only** (MSC/ConversationChronicles structurally excluded — real, permanent, 0-byte task layer, unrelated to Phase 15). Track B's 9 real cases span only 3 of the 7 attack families (DSRM/FARMA/MPBench) and are reported pooled, never broken out per family. | **B2–B8 and B10 have never been utility-tested at all.** Track B has no per-attack-family breakdown even for the 3 families it does cover. |

**The real, named gap Phase 15 exists to close**: three real, independently-built metric
pipelines, each with its own real scope, sample size, and report format, that have never been
placed side by side for the SAME cell (same attack, same dataset, same defense configuration) —
so no one has ever been able to ask "does the config that maximizes security here cost the most
utility, and does its attribution quality hold up too" with a real, direct answer instead of
cross-referencing three separately-scoped reports by eye.

## 3. The Central Design Choice: Stitch Together, Don't Rebuild

Given the real gap above, there are two fundamentally different ways to build Phase 15, and this
plan recommends the first:

**(A) Stitch together what already exists, and fill in only the real, identified missing
cells.** Phase 12's B0–B8 × 4-dataset × 7-family security numbers are already real and correct —
re-running them would waste real compute and risk silently producing a different number for a
cell this project has already reported. The real new work under this option is narrow: (1) reshape
B9/B10's already-real numbers into the same per-cell format Phase 12 uses so they join the same
matrix; (2) build a real, NEW per-dataset/per-config attribution sweep, since none exists at any
scale today; (3) extend Phase 14's utility campaign to the configs it has never tested. This
reuses Phase 12–14's own infrastructure directly, matches this project's own stated discipline
("sequenced after so the same evaluation-run scaffolding is reused rather than rebuilt a third
time" — Phase 12 plan, Section 2), and keeps every already-reported, already-trusted number
untouched.

**(B) Rebuild a single, unified pipeline from scratch that recomputes security, attribution, and
utility together for every cell.** More architecturally "clean," but real, substantial risk: it
would re-derive numbers Phase 12/13/14 already validated (risking a silent discrepancy that then
needs its own root-cause investigation, exactly the kind of regression Phase 14's own B9 fix
required this session), and the utility axis alone is real, expensive LLM-inference work (Phase
14's 300-task run took ~2 hours) — redoing that for every new cell multiplies real cost for no
real benefit over reusing what B0/B1/B9 already measured.

**Recommendation: (A).** This is the same "don't rebuild a third time" reasoning the original
Phase 12 plan already used to justify Phase 14 running after 12/13, applied one level up.

## 4. Proposed Scope, Per Axis

### 4.1 Security — cheap, real, mostly a reshape

Add B9/B10 to `run_security_matrix()`'s own per-cell output shape, reusing Phase 11's own
already-computed, already-trusted real detection numbers (`real_attack_corpus_detector.py`) rather
than re-running detection. Real cost: signal computation only, no LLM calls — the cheapest axis by
far (Phase 12's original 9-config × 4-dataset × 7-family sweep completed in signal-computation
time, not LLM-inference time). This closes the ONLY real gap on this axis.

### 4.2 Attribution — the real, substantial new-work item

This is genuinely new work, not a reshape: building a real ledger for each (dataset, defense
configuration) cell Phase 15 wants attribution numbers for, then running
`compute_attribution_metrics()` against each one. At full scope (11 configs × 4 datasets = 44
cells), this is a real, nontrivial engineering and compute lift — Section 6 asks whether full
scope is warranted, or whether a smaller, deliberately-scoped slice is more honest given the real
cost.

**A real, disclosed alternative worth naming explicitly**: attribution's own mechanism (tracing
which memory an agent's answer came from, and whether a guard's action was correctly attributed)
is arguably not dataset-specific or even strongly configuration-specific the way DETECTION is —
the ledger records the same kind of event regardless of which dataset the underlying content came
from. If real testing confirms this (a small, targeted check: does attribution accuracy actually
vary by dataset or config in a real, measured way, or is Phase 13's existing single-ledger number
already representative), the honest conclusion might be that attribution stays a single
cross-cutting artifact rather than a full 44-cell sweep — a real, evidence-based scope decision,
not an assumption made to avoid the work.

### 4.3 Utility — a real technical shortcut worth using

Track A's own `reuse_if_context_unchanged` mechanism (built during Phase 14) means a config only
costs a FRESH real LLM call when it actually excludes something — B0's answer is reused verbatim
otherwise. Milder configs (B2–B6) are expected, based on Phase 12's own detection numbers, to
exclude real content far less often than B7–B9, meaning **extending Track A to B2–B10 is likely
much cheaper than re-running the full campaign 8 more times** — most of the real LLM-call cost was
already paid computing B0. This should be verified directly (not assumed) before committing to a
pilot size across all 11 configs. Track B's per-attack-family breakdown (currently pooled across
DSRM/FARMA/MPBench) is a real, cheap reporting change, not new measurement — the data already
exists per-case (`TrackBCase.attack_family`), it is simply never grouped by it in
`run_track_b()`'s own summary.

## 5. What Phase 15 Does Not Do

- Does not re-run or re-derive any of Phase 12's real B0–B8 security numbers, Phase 13's real
  15/19-scenario attribution numbers, or Phase 14's real n=300/9 utility numbers — those are
  reused verbatim, not recomputed, per Section 3's recommendation.
- Does not reopen the workload axis (dropped, confirmed, during Phase 12).
- Does not add MSC/ConversationChronicles to the utility axis — their real, structural 0-byte
  task-layer limitation (confirmed in Phase 14) is unrelated to Phase 15 and does not change here.
- Does not write the synthesis report presenting security/attribution/utility together with an
  explicit trade-off curve (Phase 16) — Phase 15 produces the real, populated matrix Phase 16
  would need to write that report from; it does not write the narrative itself.
- Does not retrain, recalibrate, or change any Phase 6–14 defense threshold based on what the
  matrix finds — a real, disclosed follow-on for a later phase if Phase 15's own findings make
  one necessary (same discipline Phase 14's own plan already stated for itself).

## 6. Open Questions — RESOLVED (2026-09-23)

Answers given: (1) attribution: reuse existing numbers; (2) utility: start with B0-B7; (3-5)
implementer's call, tested properly, any gaps fixed. Resolutions as implemented (details in
`PHASE15_CROSS_CUTTING_REPORT.md`): (1) reused, plus a real second ledger (origin + lineage) as
empirical confirmation; (2) B0-B7 wired via `evaluate_pool()`, then B8 and live B10 added; (3) B9
reshaped per dataset (two real bugs fixed) and B10 decomposed per dataset with held-out
calibration; (4) MSC/ConversationChronicles included for security, excluded for utility (0-byte
task layer); (5) one report per phase with a Phase 16 synthesis. The original questions are kept
below as the historical record.

## 6 (original). Open Questions Requiring Your Confirmation Before Implementation

1. **Attribution scope**: full 44-cell sweep (11 configs × 4 datasets), or a smaller, deliberately
   -scoped slice (e.g., only the configs/datasets Phase 12's security matrix already flags as
   interesting — a detection cliff, a high-FPR cell), or accept the "single cross-cutting
   artifact" conclusion from Section 4.2 if a real, targeted check confirms attribution doesn't
   meaningfully vary by dataset/config? This is the single biggest scope/cost decision in this
   plan.
2. **Utility config expansion**: extend Track A/B to all of B2–B10 (11 configs total), or a
   smaller subset (e.g., just the configs Phase 12 shows have a real, meaningfully different
   security/FPR profile, since two configs with identical detection would be expected to cost
   the same real utility)? Section 4.3's reuse-mechanism argument suggests full expansion may be
   affordable, but this should be confirmed with a real, small pilot before committing to all 11.
3. **B9/B10 security reshape**: confirm reusing Phase 11's existing real detection numbers
   (`real_attack_corpus_detector.py`) is acceptable, versus wanting them re-measured inside
   Phase 12's own `evaluation_matrix.py` harness directly for exact format consistency (a real,
   small amount of extra work, mainly relevant if the two harnesses' corpora differ in a way that
   would make the numbers not directly comparable — worth a real, direct check either way).
4. **New real MSC/ConversationChronicles security+attribution numbers**: Phase 12 already
   includes these two datasets in its security matrix (they have real content, just no task
   layer) — should Phase 15's NEW attribution sweep (Question 1) include them too, given
   attribution doesn't need a task/QA layer either?
5. **Report format**: one single `docs/phase15/PHASE15_CROSS_CUTTING_REPORT.md` with one big
   real matrix table, or one matrix per metric family with a short cross-referencing section
   tying them together? The former is more literally "one matrix, three metrics per cell"; the
   latter may be more readable given the real matrix could have 300+ cells at full scope.

## 7. Deliverables (once scope is confirmed)

1. `phase15/` — new, additive module tree (a matrix-assembly module that reads Phase 12/13/14's
   own real outputs plus any new attribution/utility cells Section 6 authorizes; no existing
   Phase 6–14 file modified except where Section 6.2's small utility pilot requires extending
   `phase14/campaign.py`'s own already-parameterized functions, the same way this session already
   added `per_task_cap`/`configuration` parameters elsewhere).
2. A real, executed cross-cutting matrix at the scope Section 6 confirms, with every cell's real
   security/attribution/utility numbers (or an honest "not applicable" for cells that are
   structurally excluded, e.g. utility × MSC).
3. `docs/phase15/PHASE15_CROSS_CUTTING_REPORT.md` — the real, measured results, following the
   same disclosure discipline as every prior phase report (root-caused suspicious patterns,
   honestly-reported negative/mixed findings, an explicit "what remains open" section).
4. A regression suite extending, never replacing, the existing baseline.
5. A recommendation for Phase 16's own synthesis-report scope, informed by what Phase 15 actually
   finds (e.g., if the matrix reveals a real security-vs-utility trade-off at a specific
   config/dataset/attack cell, Phase 16's trade-off curve should foreground it).
