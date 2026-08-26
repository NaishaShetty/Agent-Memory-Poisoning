# Phase 3.2-E — Agent Evaluation Conditions

Status: **DIAGNOSTIC IMPLEMENTATION, MOSTLY PROVISIONAL**. This stage implements agent-level
evaluation conditions, a synthetic (test-only) agent execution result representation,
deterministic answer correctness, agent success classification, a paired-condition
comparison harness, a memory-contribution diagnostic, a gold-evidence ceiling diagnostic,
retrieval utilization diagnostics, and observed-failure-stage classification. It does
**not** implement leakage detection, reproducibility harnesses, real dataset adapters,
Qwen integration, retrieval/reranking/candidate-generation, memory creation/storage, or
Phase 4 attacks/defenses — all future Phase 3 stages.

All code lives in `phase3/evaluation/agent/`:
- `conditions.py` — condition vocabulary (3 schema-canonical + 3 provisional extensions)
  and `AgentVisibleContext` assembly/boundary-validation.
- `outcomes.py` — `AgentExecutionResult`, deterministic answer correctness, agent success
  classification, and the synthetic (NOT real, NOT Qwen) deterministic agent adapter.
- `paired.py` — paired-condition comparison harness and the memory-contribution
  diagnostic.
- `diagnostics.py` — gold-evidence ceiling, retrieval utilization, evidence-available/
  agent-failed, and observed-failure-stage classification.

Tests: `phase3/evaluation/tests/test_agent_evaluation.py` (94 new tests; does not modify
any of the four existing test files, whose 240 tests remain green unmodified).

This document is cross-linked from `phase3/evaluation/metrics/README.md`.

## Why this is a separate package from `phase3/evaluation/metrics/`

`phase3/evaluation/metrics/` computes MEMORY-level metrics (Recall@K, MRR, Strict TSR,
evidence precision/recall/coverage, provenance/lineage/equivalence) — per
`EVALUATION_CONTRACT.md` sections 1–4, these answer "did the memory subsystem do its
job?" This package answers the SEPARATE question "did the full agent (including
reasoning) do its job?" (`EVALUATION_CONTRACT.md` section 5). The two are deliberately
never merged: no function in this package imports or depends on `strict_tsr`,
`evidence_recall`, or any other `phase3/evaluation/metrics/` function to determine agent
success — agent success is computed ONLY from an `AgentExecutionResult` plus an
evaluator-only expected answer. See the worked counter-examples below.

## ★ Agent success ≠ Strict TSR (worked both ways)

**Case 1 — STRICT_TSR = 1, ANSWER_INCORRECT.** The agent's selection overlaps the gold
evidence id (`strict_tsr(["gold-1"], ["gold-1"]) == 1.0`), but the agent's answer is still
wrong (`"Lyon"` vs. expected `"Paris"`) — `classify_agent_success(...).status ==
ANSWER_INCORRECT`. Selecting the right memory does not guarantee correct reasoning over
it. See `test_invariant_agent_success_does_not_imply_strict_tsr`.

**Case 2 — STRICT_TSR = 0, ANSWER_CORRECT.** The agent's selection does NOT overlap the
literal gold evidence id (`strict_tsr(["non-gold-mem"], ["gold-1"]) == 0.0`), but the
agent's answer is still correct — e.g. the agent reasoned to the right answer via a
non-gold, equivalent, or otherwise differently-identified memory (or, in this stage's
synthetic fixtures, simply produced the correct answer regardless). See
`test_invariant_strict_tsr_does_not_imply_agent_success`.

Both directions are proven by dedicated tests, not merely asserted — this is the single
most important labeling boundary in this package, mirroring
`phase3/evaluation/metrics/README.md`'s "STRICT TSR ≠ agent task success" callout.

## Condition vocabulary

| Condition | Classification | Notes |
|---|---|---|
| `NO_MEMORY` | CANONICAL | Exact string from `evaluation_run.schema.json`'s `condition` enum. Condition A. |
| `GOLD_EVIDENCE` | CANONICAL | Exact string from the schema enum. Condition B. |
| `RETRIEVED_MEMORY` | CANONICAL | Exact string from the schema enum. Condition C. |
| `SELECTED_MEMORY_AVAILABLE` | **PROVISIONAL** | 3.2-E synthetic-testing-only extension. Never written to a schema-validated `EvaluationRun.condition` field. |
| `DERIVED_MEMORY_AVAILABLE` | **PROVISIONAL** | 3.2-E synthetic-testing-only extension. |
| `CONFLICTING_MEMORY_AVAILABLE` | **PROVISIONAL** | 3.2-E synthetic-testing-only extension, used to exercise `NEGATIVE_MEMORY_EFFECT`. |

The `_AVAILABLE` suffix is a deliberate naming convention distinguishing the three
provisional extensions from the three schema-canonical values at a glance. See
`conditions.py`'s module docstring for the full rationale on why
`evaluation_run.schema.json` was NOT modified to add these.

## Agent execution result model

`outcomes.AgentExecutionResult` is a NEW dataclass (not a re-import of
`agent_execution_result.schema.json`), structurally similar to the 3.2-B schema
(`task_id`, `condition`, `answer`, `execution_status`, `selected_memory_ids`, `trace_ref`)
but adding one field the frozen schema does not define: `used_memory_ids` (distinct from
`selected_memory_ids`), required by the retrieval-utilization diagnostic below. See
`outcomes.py`'s module docstring for why this was implemented as a new dataclass rather
than a schema modification. Every field is explicit and separate — there is no single
overloaded success boolean anywhere on this object.

## Answer correctness — DETERMINISTIC, EXACT MATCH ONLY

`outcomes.evaluate_answer_correctness()` performs a deterministic exact-string-match
comparison (after `.strip()` only — no case-folding, no fuzzy/semantic comparison, no
embeddings, no LLM judge) between `AgentExecutionResult.answer` and an evaluator-supplied
`expected_answer`. Returns `EVALUATION_UNDEFINED` explicitly (never a guessed 0/1) when
`execution_status != SUCCESS`, when `expected_answer is None`, or when `answer is None`
despite a SUCCESS status.

## Agent success classification

`outcomes.classify_agent_success()`: `ANSWER_CORRECT` / `ANSWER_INCORRECT` /
`EXECUTION_FAILURE` / `EVALUATION_UNDEFINED`. Computed ONLY from `AgentExecutionResult` +
an evaluator-only expected answer string — never from any `phase3/evaluation/metrics/`
function.

## Memory contribution — DIAGNOSTIC ONLY, PROVISIONAL, NON-CAUSAL

`paired.classify_memory_contribution()` classifies a paired
(NO_MEMORY, WITH_MEMORY-condition) comparison for the SAME task into exactly one of:

| Case | NO_MEMORY | WITH_MEMORY | Classification |
|---|---|---|---|
| 1 | INCORRECT | CORRECT | `POSITIVE_MEMORY_CONTRIBUTION` |
| 2 | CORRECT | CORRECT | `NO_OBSERVED_MEMORY_CONTRIBUTION` (memory unnecessary) |
| 3 | INCORRECT | INCORRECT | `NO_OBSERVED_MEMORY_CONTRIBUTION` (memory didn't help) |
| 4 | CORRECT | INCORRECT | `NEGATIVE_MEMORY_EFFECT` |

If either side is `EXECUTION_FAILURE` or `EVALUATION_UNDEFINED`, the pair is
`UNDEFINED_MEMORY_CONTRIBUTION`. **This diagnostic is explicitly non-causal**: a
classification reports an OBSERVED paired outcome difference for one task under one
reasoning behavior — never a proof that memory access caused the difference. No single
frozen aggregate "memory contribution score" is computed anywhere in this package;
`paired.memory_contribution_tally()` provides only a per-category tally (mirroring
`provenance.py`'s `counts` pattern), plus a convenience fraction, never a combined score.

Classification: **DIAGNOSTIC ONLY / PROVISIONAL**. Not a restatement of any frozen
Phase 3.1/3.2-B contract text — the four-case vocabulary and its non-causal framing are
this stage's own construction (loosely analogous to, but distinct from, the
`memory contribution = accuracy(C) - accuracy(A)` scalar delta defined in
`EVALUATION_CONTRACT.md` section 5, which remains the frozen aggregate-accuracy-delta
definition; this per-task four-way classification is a complementary, finer-grained
diagnostic, not a replacement for that delta).

## Paired condition comparison — NOT "counterfactual"

`paired.paired_condition_comparison()` and `classify_memory_contribution()` deliberately
use "PAIRED CONDITION COMPARISON" terminology throughout, never "counterfactual." A
counterfactual claim requires holding one already-executed run fixed while hypothetically
varying a single input; this harness instead compares two SEPARATE, already-executed
`AgentExecutionResult`s and reports what was OBSERVED in each — a materially weaker and
more honest claim. Both functions enforce identical task/expected-answer identity across
the pair, raising `PairedComparisonIdentityError` on any mismatch (task_id, expected
answer, or condition role).

## Gold-evidence ceiling — OBSERVED, EMPIRICAL, NOT THEORETICAL

`diagnostics.observed_gold_evidence_ceiling()` reports the ANSWER_CORRECT rate across a
set of `GOLD_EVIDENCE`-condition (Condition B) results, labeled
`OBSERVED_GOLD_EVIDENCE_CEILING`. **This is explicitly NOT a theoretical ceiling** on
achievable accuracy — it is an empirical number for THIS task set, under THIS reasoning
behavior, in THIS run. Per `EVALUATION_CONTRACT.md` section 5, Condition B exists so
Condition C can be characterized relative to it, not so this number can be reported as an
abstract upper bound on agent capability in general.

Classification: **DIAGNOSTIC ONLY**.

## Retrieval utilization

`diagnostics.classify_retrieval_utilization()` compares `selected_memory_ids` against
`used_memory_ids`:

| State | Meaning |
|---|---|
| `NO_SELECTED_EVIDENCE` | Nothing was selected. |
| `SELECTED_BUT_NOT_USED` | Selected non-empty, but disjoint from used. |
| `SELECTED_AND_USED` | Selected and used intersect. |
| `UNDEFINED_USAGE_NOT_OBSERVABLE` | `used_memory_ids is None` — usage was not exposed by this execution's trace. Distinct from "known to be unused." |

Classification: **DIAGNOSTIC ONLY**.

## Evidence-available / agent-failed

`diagnostics.evidence_available_agent_failed()`: gold evidence available (an evaluator-
side boolean the CALLER supplies) + `ANSWER_INCORRECT` → `AGENT_FAILURE_WITH_EVIDENCE`.
Returns an explicit not-applicable status when evidence was unavailable — it never claims
retrieval/selection caused anything in that case; it simply declines to apply.

Classification: **DIAGNOSTIC ONLY**.

## Observed failure-stage classification

`diagnostics.classify_observed_failure_stage()` — **"OBSERVED_FAILURE_STAGE" framing,
never a causal claim**:

| Stage | Meaning |
|---|---|
| `SUCCESS` | Answer was correct. |
| `AGENT_EXECUTION_FAILURE` | Execution did not complete. |
| `EVIDENCE_UNAVAILABLE` | `NO_MEMORY` condition — no memory was made available by construction. |
| `RETRIEVAL_FAILURE` | Gold evidence absent from what was retrieved (via `retrieval.classify_gold_id_capacity`, reused verbatim). |
| `SELECTION_FAILURE` | Gold evidence retrieved but not selected. |
| `AGENT_FAILURE_WITH_EVIDENCE` | Gold evidence was available (selected, or handed directly under `GOLD_EVIDENCE`) but the answer was still wrong. |
| `UNDEFINED_EVALUATION` | No expected answer, or no gold evidence ids, supplied. |

A `RETRIEVAL_FAILURE` (or any other stage) classification reports only an OBSERVED
co-occurrence with an incorrect/failed answer — never that the stage CAUSED the failure.

Classification: **DIAGNOSTIC ONLY**.

## CANONICAL / PROVISIONAL / DIAGNOSTIC-ONLY table

| Item | Classification | Rationale |
|---|---|---|
| `CONDITION_NO_MEMORY` / `CONDITION_GOLD_EVIDENCE` / `CONDITION_RETRIEVED_MEMORY` | CANONICAL | Exact strings from `evaluation_run.schema.json`'s frozen `condition` enum. |
| `CONDITION_SELECTED_MEMORY_AVAILABLE` / `CONDITION_DERIVED_MEMORY_AVAILABLE` / `CONDITION_CONFLICTING_MEMORY_AVAILABLE` | **PROVISIONAL** | 3.2-E synthetic-testing-only extensions; never schema-validated, never written to a real `EvaluationRun`. |
| `AgentExecutionResult` (dataclass shape) | **PROVISIONAL** | Structurally mirrors `agent_execution_result.schema.json` but adds `used_memory_ids`, a field the frozen schema does not define. |
| `evaluate_answer_correctness` / `classify_agent_success` | **PROVISIONAL** | Exact-match correctness and the four-way success vocabulary are this stage's own construction; no contract document fixes an answer-correctness formula. |
| `paired_condition_comparison` | **PROVISIONAL** | The identity-enforced pairing mechanism is this stage's construction, built to satisfy `EVALUATION_CONTRACT.md` section 5's controlled-condition methodology but not itself a frozen contract object. |
| `classify_memory_contribution` / `memory_contribution_tally` | **DIAGNOSTIC ONLY, non-causal** | Complementary, finer-grained per-task classification alongside (not a replacement for) the frozen `accuracy(C) - accuracy(A)` delta in `EVALUATION_CONTRACT.md` section 5. |
| `observed_gold_evidence_ceiling` | **DIAGNOSTIC ONLY** | Empirical, run-specific number; explicitly not a theoretical ceiling. |
| `classify_retrieval_utilization` | **DIAGNOSTIC ONLY** | This stage's own vocabulary; no contract document defines it. |
| `evidence_available_agent_failed` | **DIAGNOSTIC ONLY** | This stage's own vocabulary. |
| `classify_observed_failure_stage` | **DIAGNOSTIC ONLY** | This stage's own vocabulary; explicitly framed as observation, not causal attribution, per the task brief's conservatism requirement. |

## Leakage boundary

`conditions.build_agent_visible_context()` reuses
`phase3/evaluation/contracts/boundary.py::validate_agent_visible()` (the existing,
stronger, defense-in-depth check) rather than inventing a parallel, weaker one. Every
synthetic fixture's `AgentVisibleContext` payload is validated at construction time and
re-validated independently in `test_agent_evaluation.py`'s
`test_no_forbidden_key_appears_in_any_scenario_agent_visible_context`. `NO_MEMORY`
contexts are structurally forced to carry an empty `memory_content`, regardless of what a
caller passes in.

## Out of scope for Phase 3.2-E

Leakage detection framework, reproducibility/determinism harness, real dataset adapters
(LoCoMo/LongMemEval/MSC/Conversation Chronicles), Qwen integration,
retrieval/reranking/candidate-generation implementation, memory creation/store, Phase 4
attacks/defenses. All remain future stages' scope — see
`PHASE3_CLEAN_AGENT_FOUNDATION_SPEC.md` section 4.

## Running the tests

```
python -m pytest phase3/evaluation/tests/ -q
```

334 tests total as of this stage: the original 240 (`test_evaluation_contracts.py` +
`test_core_memory_metrics.py` + `test_evidence_equivalence.py` +
`test_provenance_lineage.py`, all unmodified), plus 94 new tests in
`test_agent_evaluation.py`, all passing, run twice to confirm determinism.
