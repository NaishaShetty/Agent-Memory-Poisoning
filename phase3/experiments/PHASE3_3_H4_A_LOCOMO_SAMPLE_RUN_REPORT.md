# Phase 3.3-H.4-A — Real, Sampled LoCoMo/Mem0 Counterfactual Run — Execution Report

Status: **COMPLETE**. Execution report, not an implementation report — no code was
modified for this run itself (canonical_wiring.py's existing, already-built Condition B
functions were reused directly). This is the run [PHASE3_3_H4_A_RUN_REPORT.md](PHASE3_3_H4_A_RUN_REPORT.md)'s
own §5 named as still outstanding: a real, sampled measurement against actual LoCoMo data,
not a fabricated smoke case. Resolves the remaining part of readiness-assessment hard
blocker #5 for the Mem0/LoCoMo pairing.

## 1. Method

Real, seeded LoCoMo sample: `sample_locomo_tasks_formal(n=6)` — the exact same sampling
function/eligibility rule/seed (`SAMPLING_SEED`) that produced the frozen G-formal
baseline, requested at a small n rather than 120. Produced 6 tasks across 5 distinct
conversation pools (one pool contributed 2 tasks).

For each pool: real ingestion via `write_ingested_canonical_memory()` into a real Mem0
collection (17-25 memories per pool), real retrieval + real Qwen3-8B generation via
`run_agent_task()` (`top_k=5`, `clean_baseline_generation_config()` — same pinned model as
every other real run this session), real canonical `retrieved`/`selected` event recording
via `record_retrieval_and_selection_events()` (Condition B's own, already-live H.4-WIRE
mechanism — this run is also the first real exercise of that machinery against actual
dataset content, not just the earlier fabricated dry run). For every memory the agent
actually selected, `run_counterfactual_mask()` + `compare_counterfactual_run()` — the real,
unmodified Initiative A mechanism.

Gold `answer`/`evidence_memory_ids` were read only for this script's own post-hoc
reporting, never passed into `AgentTaskInput`/the prompt — same leakage-boundary
discipline as every other real run this session.

## 2. Results

| Task | Retrieved/Selected | Agent Answer | Gold Answer |
|---|---|---|---|
| `ecf5a096...` | 5/5 | "Caroline went to the LGBTQ support group yesterday." | "7 May 2023" |
| `9f278780...` | 5/5 | "Melanie painted the lake sunrise last year. [8c6766e3-...]" | "2022" |
| `6b06956f...` | 5/5 | "Last Wednesday. [776d1866-...]" | "Wednesday before 9 February, 2023" |
| `e24aa329...` | 5/5 | "None of the provided memories mention Sam's activities on December 4, 2023..." | "Attending a Weight Watchers meeting" |
| `afef9ecc...` | 5/5 | "Nate made vegan ice cream and shared it with his vegan diet group [88dc74e5-...]" | "vegan ice cream" |
| `e9d52c07...` | 5/5 | "Calvin mentions being excited to explore streets similar to those in the photo Dave shared [9be6ca46-...]" | "Shinjuku" |

**Counterfactual comparisons: 30 total (5 masked memories × 6 tasks) — 17
`COUNTERFACTUALLY_INFLUENTIAL`, 13 `NOT_COUNTERFACTUALLY_INFLUENTIAL`, 0 inconclusive.**
Every one of the 36 real LLM calls (6 baseline + 30 masked) completed successfully; the
mechanism never hit an `INCONCLUSIVE_*` path in this sample.

## 3. Honest observations, not smoothed over

**This measures counterfactual influence, not answer correctness — and the two are
visibly orthogonal in this sample.** Several agent answers are plausible-sounding but
wrong relative to gold (e.g. "yesterday" instead of "7 May 2023"; task `e24aa329...`
retrieved five memories yet the agent reported none were relevant, missing the gold answer
entirely). This is expected and out of scope for this mechanism — Initiative A was never
designed to measure or improve answer quality, only whether masking a specific memory
changes the produced answer. Retrieval/generation quality is a separate, pre-existing
concern this run does not speak to.

**The `exact_normalized_match` diff criterion's known sensitivity to trivial formatting
manifested for real, here, not just as a documented hypothetical.** Task `9f278780...`'s
masked answers frequently differ from baseline only by a trailing period or bracket
placement around a citation tag (e.g. baseline `"...last year. [8c6766e3-...]"` vs. masked
`"...last year [8c6766e3-...]."`) — both scored `COUNTERFACTUALLY_INFLUENTIAL` under the
mission's own deliberately conservative, whitespace-only normalization (no punctuation
stripping, no case-folding). This is the documented, deliberate precision/recall tradeoff
from [PHASE3_3_H4_A_MISSION.md §9](../specification/PHASE3_3_H4_A_MISSION.md) — "err toward
detecting influence rather than normalizing it away" — working exactly as specified, but
it means some fraction of the 17 `COUNTERFACTUALLY_INFLUENTIAL` results in this sample
reflect citation-tag reformatting rather than a substantive change in what the answer
claims. A future, stricter-normalization or semantic-diff criterion (explicitly deferred,
per the mission's own non-goal) would likely report a somewhat lower influential count
against the *same* underlying model behavior.

**Neither of these observations invalidates the measurement — they scope its
interpretation.** The mechanism did exactly what it was built to do: it detected every
case where masking changed the model's literal output, honestly, without any tolerance
built in for "that doesn't count." Whether a downstream consumer wants that literal
sensitivity or a coarser one is a `diff_criterion` choice for a future stage, not a defect
in this run.

## 4. Artifacts

`phase3/experiments/canonical_store/h4a-real-locomo-smoke-1/` (correction: this is where
`open_pool_canonical_ledgers()` actually writes — `<experiments_dir>/canonical_store/...`,
not `<experiments_dir>/results/canonical_store/...` as originally stated here; caught
while writing the companion A-MEM report) — per-pool `memory/`/`events/`/`run_config/` (5
pools). This run's own `run_summary.json` (full task-by-task and comparison-by-comparison
detail) is at `phase3/experiments/results/canonical_store/h4a-real-locomo-smoke-1/
run_summary.json`. Both untracked, kept as evidence.

## 5. Updated readiness status

Per [PHASE3_3_H4_READINESS_ASSESSMENT.md](PHASE3_3_H4_READINESS_ASSESSMENT.md) §6 item 3:
this **is** the real, sampled LoCoMo/Mem0 counterfactual run that item asked for. Hard
blocker #5 (counterfactual influence measurement) is now satisfied for the Mem0/LoCoMo
pairing with real, non-fabricated evidence — n=6 tasks is a small sample (not the full
120-task campaign scale), which should be stated explicitly wherever this evidence is
cited, but it is real evidence, not a mechanism demonstration.

## 6. Freeze status

Not a frozen decision — a dated execution record.
