# Phase 3.3-V5 — Experiment Plan

Follows the V5 spec's required 4-stage sequence. **The 720-task Stage 4 campaign
requires explicit user approval and is not started by this plan or by any script in
this directory.**

## Stage 1 — Unit/integration validation (this pass)

- [x] `campaign_v5_runner.py` imports cleanly, no signature mismatches against reused
  V1-V4 primitives.
- [x] Full existing test suite (`phase3/evaluation/tests/`, 71+ files) run after
  adding all V5 files — zero new failures, same pass/skip counts as the pre-V5
  baseline.
- [x] 19 new V5-specific unit tests (`test_v5_structured_memory.py`,
  `test_v5_reasoning_pipeline.py`) — bounded call-count assertions (never more than
  3 LLM calls in the reasoning pipeline), malformed-JSON handling, empty-evidence
  short-circuit (zero LLM calls), entity-normalization scope, consolidation
  provenance-preservation, ablation-flag composition. All passing with mocked
  providers — no real server dependency for this layer.
- [x] Repository-level audit: `git status`/`git diff --stat` confirm no V1-V4 file
  (`campaign_v2_runner.py`, `campaign_v3_runner.py`, `campaign_formal_runner.py`,
  `hybrid_selection.py`, `temporal_resolution.py`, the two real adapters) was
  modified by this work — new files only, plus the pre-existing (prior-session,
  disclosed) modifications to `canonical_wiring.py`/`normalized_correctness.py`/
  `dataset_record_assembler.py`, confirmed unchanged again since V5 work began.
- [x] Mem0 adapter smoke test (`initialize` -> `reset` -> `shutdown`, via the
  required isolated `C:\h4venv` interpreter) — AVAILABLE.
- [x] A-MEM adapter smoke test (same lifecycle, same isolated interpreter) —
  AVAILABLE.
- [ ] Reproducibility check: same task, same `V5Config`, `temperature=0`/`seed=42` ->
  byte-identical final answer across two runs. (Deferred to Stage 2 — reusing real
  pilot task executions rather than a separate throwaway check, since the pilot
  itself provides this evidence for free.)

## Stage 2 — Small pilot (n≈15-20, both foundations)

Script: `pilot_v5_stage2.py` (to be run after this plan is reviewed).

- Population: reuse the same LoCoMo task IDs already used throughout this project's
  n=15 dev pilots where possible (for direct comparability with prior rounds'
  numbers, e.g. `pilot_qwen3_4b_thinking_v2.py`'s 15 tasks), extended to ~20 if a
  larger n is needed to cover both foundations meaningfully.
- Conditions: B and C (Mem0), C (A-MEM). Condition A is not re-run (V5 reuses V1's
  Condition A verbatim; re-running it would only remeasure noise, not V5's actual
  additions).
- Configs compared: `V5_BASE` vs `V5_STRUCTURED` vs `V5_VERIFIED` vs `V5_FULL`, all
  at `enable_thinking=False` (V1-V4's baseline generation config) first — model
  config is a SEPARATE variable, tested only after the architecture ablations are
  understood on the proven baseline model config.
- Every meaningful flip (any task whose LLM-judge status changes between `V5_BASE`
  and any other config) is manually inspected and read in full — same discipline
  applied throughout this project's hedging/terseness/date-normalization pilots.
- Truncation/latency accounting: `finish_reason` and per-stage latency are recorded
  for every generation call (already built into the trace's `"v5"` block) and
  reported explicitly, not just aggregate correctness — directly motivated by the
  4B-thinking pilot's real 47% truncation finding.

**Promotion criterion to Stage 3**: at least one V5 config shows a real,
hand-verified semantic-correctness improvement over `V5_BASE` with zero new
hallucination (a confidently-wrong answer where `V5_BASE` correctly hedged) and no
truncation-driven answer loss exceeding what `V5_BASE` itself shows.

**NO-GO trigger**: if every V5 config's real (hand-verified, not just aggregate)
correctness is flat or worse than `V5_BASE`, or if truncation/hallucination
increases, report that honestly and do not proceed to Stage 3/4 — per the spec's
explicit instruction to report the real result, not the desired one.

## Stage 3 — Targeted failure evaluation

Script: `pilot_v5_stage3_targeted.py`. Reuses the SAME real, already-identified hard
cases from this project's own diagnosis work, rather than a fresh arbitrary sample —
so V5's effect on each named failure mode can be checked against a case already
known to exhibit it:

| Failure mode | Reused case population |
|---|---|
| Multi-hop / counting | "How many children does Melanie have?" (gold=3) — the case that directly motivated the structured-memory layer |
| Temporal (range-vs-point) | The 9 real date-range-vs-point cases from the §15.1 date-normalization rescoring |
| Entity/coreference | The "purple guitar" case (gold evidence attributes the color to the wrong turn/speaker) |
| Evidence aggregation / hedging | The 14 real V3 Condition-B hedge cases from `v4_hedge_cases.json` (4 genuine hedging failures, 7 genuine evidence-mismatch cases used as a hallucination regression check, 3 other) |
| Incompleteness | The 2-3 genuinely completeness-fixable cases from the §15.2 quantification pass |

For each, run `V5_BASE` and `V5_FULL` (plus any config Stage 2 flagged as
promising) and report per-case: did the specific failure mechanism change, and —
critically for the hedging population's evidence-mismatch half — did the model
start hallucinating on cases where hedging was the CORRECT, honest response.

## Stage 4 — Full campaign (120 tasks x 2 foundations x 3 conditions = 720 executions)

**NOT started by this plan. Requires explicit user approval per the spec's own
instruction ("Do not start the 720-task campaign until I explicitly approve it").**
If approved: same checkpointed/resumable pattern as V2/V3 (`_save()` after every
task/pool), same frozen 120-task LoCoMo formal sample (seed 33005), campaign_id
namespaced so results write to `V5_STORE` only, never touching v1/v2_candidate/
v3_candidate.

## Comparison against V1-V4

Read-only against each version's existing frozen artifacts (`dataset_full/
clean_agent_dataset_v{1,2,3}...json`) — no V1-V4 campaign is rerun. Metrics compared
side by side (exact/normalized/content-recall/date-normalized/LLM-judge), plus
V5-specific fields (latency, token/call count, truncation rate, hallucination rate
on the disclosed hedging-regression population) that have no V1-V4 counterpart and
are reported as V5-only, not backfilled or estimated for the earlier versions.
