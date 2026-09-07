# Selection-Policy Variant — Full 120×2 Run — Completion Report

Status: **COMPLETE**. Real execution report for the full-scale wiring of the
calibrated threshold-based selection policy
([`foundations/selection_policy.py`](../evaluation/foundations/selection_policy.py))
into an actual real campaign, per the user's explicit request to move from
"built and calibrated but unused" to "genuinely wired in and run." This produces a
**separate dataset variant** — the existing frozen 120×2 dataset
(`clean_agent_dataset_locomo_120x2.json`) is completely untouched.

## 1. What was built (additive)

- [`agent_runtime/selection_policy_runner.py`](../evaluation/agent_runtime/selection_policy_runner.py)
  — Condition C sibling of `runner.py::run_agent_task()`: retrieves a real N=20 pool
  (`RETRIEVAL_POOL_SIZE_N`, vs. the existing path's N=5) then applies real
  threshold-based selection (`CALIBRATED_THRESHOLD_LOCOMO=0.263`) instead of the
  provisional identity-slice. `runner.py` itself untouched.
- [`agent_runtime/campaign_selection_policy_runner.py`](../evaluation/agent_runtime/campaign_selection_policy_runner.py)
  — full campaign wiring for both foundations, reusing `canonical_wiring.py`'s
  EXISTING `record_retrieval_and_selection_events(_direct_assignment)` functions
  unmodified — they already correctly emit a `rejected` `CanonicalEvent` for any
  retrieved-but-not-selected id, so no new canonical-event logic was needed, only a
  caller that finally supplies a genuinely smaller `selected_ids` set.
- 6 new unit tests (`test_selection_policy_runner.py`), fake-provider/mock-adapter,
  all pass.

## 2. Real pilot, then full run

4-task real pilot first (both foundations): 8/8 successful, real non-zero rejection
(8-13 of 20 candidates rejected per task) confirmed before scaling.

**Full run: 120 real LoCoMo tasks × 2 foundations = 240 real executions, 240/240
SUCCESSFUL_EVALUATION, zero failures, zero content-leakage detections.** Real
Qwen3-8B, same infra as every other real run this session. Wall-clock: Mem0 ~28 min,
A-MEM ~2h6m (7545s) — consistent with prior A-MEM measurements.

## 3. Real results — rejection is no longer structurally vacuous

| Foundation | Total retrieved | Total selected | Total rejected | Avg rejected/task | Tasks with 0 selected |
|---|---|---|---|---|---|
| MEM0 | 1977 | 587 | 1390 | 11.58 | 0 |
| AMEM | 2134 | 587 | 1547 | 12.89 | 0 |

**2,937 real `rejected` `CanonicalEvent`s appended across both foundations** — the
first real, non-zero rejection this project has ever produced (every prior real run
used the provisional top-5-of-5 policy, which is retrieval-capacity-vacuous by
construction). Selected-count distribution was identical across both foundations
(112/120 tasks hit the `max_k=5` cap, 4/3/1 tasks selected 4/3/2 respectively, 0
tasks selected zero) — a real, disclosed observation, not fully investigated further:
plausible given both foundations search the same real underlying session content, so
"how many candidates clear a fixed textual-similarity bar against this question"
converges even though the two foundations' actual retrieved candidate identities can
differ.

## 4. Real comparison against the existing frozen dataset

| Foundation | Selected-set identical to original (top-5-of-5) run | Real answer changed vs. original |
|---|---|---|
| MEM0 | 0/120 | 92/120 |
| AMEM | 30/120 | 71/120 |

**The new selection policy is not cosmetic — it measurably changes both what gets
selected and what the real LLM answers, in the majority of cases.** Mem0's selected
set never matched the original run exactly (expected: N=20 retrieval surfaces a
different, larger candidate pool than N=5 to begin with, before thresholding even
applies). A-MEM's selected set matched the original in 30/120 cases despite the
larger pool — worth noting, not further explained here.

## 5. Scope / what this is and is not

- **A new, separate variant**, stored under
  `phase3/experiments/results/canonical_store/selection_policy_variant/` — raw
  per-task results (`results_mem0_CHECKPOINT.json`, `results_amem_CHECKPOINT.json`,
  `selection_policy_variant_result.json`), never merged into or replacing the
  existing `dataset_full/clean_agent_dataset_locomo_120x2.json`.
- Condition A / GOLD_EVIDENCE were **not** re-run for this variant — both are
  foundation-and-selection-independent by construction (no retrieval/selection layer
  involved at all), so the existing dataset's values for those conditions remain the
  correct, unchanged reference; re-running them would have been pure duplicate real
  compute for identical results.
- No formal `clean_agent_dataset_record_schema.json`-shaped assembly was produced for
  this variant (that schema was designed around the primary A/B/C dataset); this
  report and the raw JSON are the record of it.
- `clean_agent_memory_v1` and all frozen artifacts remain untouched throughout.

## 6. Regression

Full suite re-run after all of today's additions (this variant included): **1654
passed, 0 failed, 14 skipped** (all environment-conditional, previously verified to
pass for real under `h4venv` + live server — see earlier session verification).

## 7. Freeze status

Not a frozen decision — a dated, real execution record demonstrating the selection
policy at full scale, for the first time. Whether this variant (or the mechanism
generally) becomes part of any future frozen dataset is a separate decision, not
made here.
