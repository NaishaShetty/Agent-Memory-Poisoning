# Phase 3.3-H4-A — Larger Real Counterfactual Sample (n=20) — Execution Report

Status: **COMPLETE**. Execution report, not an implementation report — no code was
modified. Extends the n=6 measurements
([PHASE3_3_H4_A_LOCOMO_SAMPLE_RUN_REPORT.md](PHASE3_3_H4_A_LOCOMO_SAMPLE_RUN_REPORT.md),
[PHASE3_3_H4_A_LOCOMO_AMEM_RUN_REPORT.md](PHASE3_3_H4_A_LOCOMO_AMEM_RUN_REPORT.md)) to a
larger, still real, sample.

## 1. Method

Identical method to the n=6 runs, same real infrastructure (`RealMem0Adapter`/
`RealAMemAdapter`, pinned Qwen3-8B via `llama-server`, the real wired canonical event
instrumentation), same `sample_locomo_tasks_formal()` seed — requested at `n=20` instead
of `n=6`. 18 distinct conversation pools, 20 real LoCoMo tasks, 100 counterfactual
comparisons per foundation (5 selected memories × 20 tasks).

## 2. Results

| Foundation | Influential | Not influential | Inconclusive | Rate |
|---|---|---|---|---|
| Mem0 | 59 | 41 | 0 | 59% |
| A-MEM | 62 | 38 | 0 | 62% |

Wall-clock: Mem0 n=20 completed in 13m11s. A-MEM n=20 took noticeably longer (measured,
not estimated after the fact) — consistent with A-mem-sys's own "evolution" step
attempting an unreachable Ollama backend per memory ingested, adding real connection-
timeout overhead that does not affect correctness.

## 3. What this adds beyond the n=6 measurements

- **Both foundations now have a real, comparable measurement at 3x the earlier sample
  size**, and the two rates (59% vs. 62%) are close — no dramatic divergence in
  counterfactual sensitivity between the two foundations at this scale, consistent with
  the qualitative finding from the n=6 post-fix comparison (foundation answers were
  substantively similar for the same tasks).
- **Zero inconclusive results across 200 total comparisons** (100 per foundation) — every
  real LLM call across both runs completed successfully; the mechanism's
  `INCONCLUSIVE_GENERATION_FAILURE`/`INCONCLUSIVE_BASELINE_FAILURE` paths were never
  exercised for real at this scale, worth noting as an observation (not a gap — those
  paths are still correctly implemented and tested against constructed failure cases,
  per `test_counterfactual.py`).
- **This remains a "larger" sample, not a "full-scale" one** — 20 of the 120 tasks in the
  frozen G-formal baseline's own per-dataset scale. The honest characterization is
  "meaningfully larger real evidence," not "research-scale campaign."

## 4. Artifacts

`phase3/experiments/canonical_store/h4a-real-locomo-n20/` (Mem0, 18 pools) and
`phase3/experiments/canonical_store/h4a-real-locomo-n20-amem/` (A-MEM, 18 pools), plus
each run's own `run_summary.json` under `phase3/experiments/results/canonical_store/...`.
All untracked, kept as evidence.

## 5. Freeze status

Not a frozen decision — a dated execution record.
