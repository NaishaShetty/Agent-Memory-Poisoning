# Phase 3.2-H — Evaluation Integration + Regression

Status: **INTEGRATION LAYER**. This stage does not introduce a single new metric,
condition, leakage rule, or fingerprint algorithm. It proves that everything built in
3.2-B through 3.2-G composes into one deterministic, model-independent, end-to-end
evaluation path — and that the "missing ground truth" distinctions those stages defined
survive composition instead of collapsing into a false 0/failure at the seams.

No LLM. No Qwen. No real agent. No retrieval/reranking/candidate-generation
implementation. No dataset modification. Every computational step below is a call into
an existing `phase3/evaluation/{contracts,metrics,agent,security,datasets}` module.

## The pipeline

```
EvaluationCase (dataset_id, case_id, condition, record, memories, retrieved/selected ids)
        │
        ▼
1. Condition validation ─────────────── agent.conditions.ALL_CONDITIONS membership
        │
        ▼
2. Contract-shape validation ────────── jsonschema.Draft202012Validator against
        │                                agent_visible_context.schema.json
        │                                (canonical conditions only — provisional
        │                                 conditions skip this, matching
        │                                 agent.conditions's own documented behavior)
        ▼
3. Leakage validation ───────────────── security.leakage.validate_against_boundary
        │                                (which itself calls
        │                                 contracts.boundary.validate_agent_visible
        │                                 first, never bypassed)
        ▼
4. Agent execution ──────────────────── agent.outcomes.run_synthetic_agent, or a
        │                                caller-supplied AgentExecutionResult
        ▼
5. Metric computation ───────────────── one call per metric family, GATED by the
        │                                dataset profile's metric_support entry
        │                                (validation.metric_support_gate) — every
        │                                attempted family calls the REAL function:
        │                                retrieval.recall_at_k / reciprocal_rank /
        │                                selection_capacity_report,
        │                                selection.strict_tsr / selection_count,
        │                                evidence.evidence_precision / evidence_recall /
        │                                evidence_coverage / irrelevant_memory_rate /
        │                                redundancy,
        │                                equivalence.equivalence_classes,
        │                                provenance.provenance_completeness_report /
        │                                independence_report,
        │                                agent.outcomes.evaluate_answer_correctness /
        │                                classify_agent_success,
        │                                agent.diagnostics.classify_retrieval_utilization /
        │                                classify_observed_failure_stage
        ▼
6. Agent-level diagnostics ──────────── (folded into step 5's per-family dispatch above)
        ▼
7. Trace + EvaluationResult assembly ── plain dicts shaped like trace_artifact.schema.json
        │                                / evaluation_result.schema.json, both
        │                                schema-validated the same way as step 2
        ▼
8. Fingerprinting ───────────────────── security.reproducibility.fingerprint /
                                         canonical_serialize / build_manifest
        │
        ▼
EvaluationCaseResult (metrics, agent_execution_result, agent_success, leakage_result,
                      trace, evaluation_result, fingerprints, warnings)
```

Two cross-case diagnostics live outside the per-case loop, since they are genuinely
aggregate: `evaluate_paired_case()` (→ `agent.paired.classify_memory_contribution`) and
`evaluate_gold_evidence_ceiling()` (→ `agent.diagnostics.observed_gold_evidence_ceiling`).
Both are reused verbatim, never reimplemented.

## Component composition (proof of reuse, not reimplementation)

| Pipeline step | Real function called | Module |
|---|---|---|
| Condition membership | `ALL_CONDITIONS` | `agent/conditions.py` (3.2-E) |
| Agent-visible context assembly | `build_agent_visible_context` | `agent/conditions.py` (3.2-E) |
| Boundary enforcement | `validate_agent_visible` | `contracts/boundary.py` (3.2-B) |
| Leakage validation | `validate_against_boundary` | `security/leakage.py` (3.2-F) |
| Synthetic execution | `run_synthetic_agent` | `agent/outcomes.py` (3.2-E) |
| Recall@K / MRR / selection-capacity | `recall_at_k` / `reciprocal_rank` / `selection_capacity_report` | `metrics/retrieval.py` (3.2-C) |
| Strict TSR / selection count | `strict_tsr` / `selection_count` | `metrics/selection.py` (3.2-C) |
| Evidence precision/recall/coverage, irrelevant rate, redundancy | `evidence_precision` / `evidence_recall` / `evidence_coverage` / `irrelevant_memory_rate` / `redundancy` | `metrics/evidence.py` (3.2-C) |
| Equivalence components | `equivalence_classes` | `metrics/equivalence.py` (3.2-D) |
| Provenance / lineage independence | `provenance_completeness_report` / `independence_report` | `metrics/provenance.py` (3.2-D) |
| Answer correctness / agent success | `evaluate_answer_correctness` / `classify_agent_success` | `agent/outcomes.py` (3.2-E) |
| Memory contribution | `classify_memory_contribution` | `agent/paired.py` (3.2-E) |
| Gold-evidence ceiling / retrieval utilization / failure-stage | `observed_gold_evidence_ceiling` / `classify_retrieval_utilization` / `classify_observed_failure_stage` | `agent/diagnostics.py` (3.2-E) |
| Fingerprinting | `fingerprint` / `canonical_serialize` / `build_manifest` | `security/reproducibility.py` (3.2-F) |
| Dataset capability gating | `metric_support_gate` / `condition_support_gate` / `task_layer_gate` | `datasets/*.json` profiles (3.2-G), consumed via `integration/validation.py` |

## The central distinction: NOT_ATTEMPTED vs. a metric's own native undefined status

This stage introduces exactly one new status, `STATUS_NOT_ATTEMPTED` (`result.py`), and
nothing else. It answers a question no prior stage needed to ask:

> Was this metric's precondition ruled out **at the dataset level**, by the dataset's own
> evaluation profile, before this specific case's data was even looked at?

That is a different question from a metric's own **native** undefined status (e.g.
`STATUS_UNDEFINED_EMPTY_GOLD`, already defined in `metrics/types.py` since 3.2-C), which
answers: *was this metric's precondition ruled out by this case's actual data, on a
dataset that otherwise supports the metric in general?* Both are preserved, never
collapsed into each other or into `0`/`False`.

**Concrete before/after examples:**

- **Missing answer ≠ incorrect answer.** A LoCoMo task record with `answer: null`
  (question_type `"5"`, per the profile's own documented finding) never produces
  `ANSWER_INCORRECT`. `agent.outcomes.evaluate_answer_correctness` returns its own
  `EVALUATION_UNDEFINED` status — the pipeline does not substitute a guess.
- **Missing evidence ≠ retrieval failure, and Strict TSR ≠ 0.** A case whose
  `gold_evidence_ids` is empty (`evidence_availability=PARTIAL` for that record) produces
  `STATUS_UNDEFINED_EMPTY_GOLD` for `STRICT_TSR`, not a `0.0` — see
  `pipeline._compute_strict_tsr`'s explicit case-level guard, which is layered *on top
  of*, never inside, `selection.strict_tsr` (that function itself is untouched — 3.2-C
  remains frozen).
- **No task layer ≠ task failure.** For MSC/Conversation Chronicles
  (`workload_availability.explicit_task_records = NOT_PROVIDED_BY_SOURCE`, confirmed by
  literal 0-byte `task_records.jsonl` files at 3.2-G), every task-dependent metric family
  (`RECALL_AT_K`, `MRR`, `STRICT_TSR`, `EVIDENCE_*`, `AGENT_ANSWER_CORRECTNESS`,
  `AGENT_SUCCESS`, `MEMORY_CONTRIBUTION`, `OBSERVED_GOLD_EVIDENCE_CEILING`,
  `FAILURE_STAGE_CLASSIFICATION`) returns `NOT_ATTEMPTED` with `scope="DATASET"` and an
  explicit reason quoting the profile field — never `0`, never `False`, never silently
  skipped from the result. Memory-only families (`SELECTION_COUNT`, `REDUNDANCY`,
  `PROVENANCE_VALIDATION`, `LINEAGE_DIAGNOSTICS`, `EQUIVALENCE_DIAGNOSTICS`) remain fully
  attemptable for these two datasets, since they need no task/gold basis at all — this is
  exactly the asymmetry the profile-consistency invariants in `validation.py` enforce and
  test.

## Checked invariants (genuine assertions, not prose)

`validation.py`'s `assert_all_invariants()` — invoked at the top of every
`pipeline.evaluate_case()` call, before any metric is computed — enforces:

- **`assert_strict_tsr_gate_consistent`**: if `evidence_availability` is not
  AVAILABLE/PARTIAL for a dataset, `metric_support.STRICT_TSR` must not be
  SUPPORTED/SUPPORTED_WITH_ADAPTER.
- **`assert_answer_availability_gate_consistent`**: same relationship for
  `answer_availability` → `AGENT_ANSWER_CORRECTNESS`/`AGENT_SUCCESS`.
- **`assert_task_layer_gate_consistent`**: if there is no task layer at all, none of the
  13 task-dependent metric families may be marked SUPPORTED, while the 6 memory-only
  families remain untouched by this constraint.

Each is proven non-trivial in `test_evaluation_integration.py` via a deliberately-broken
in-test profile that the invariant correctly rejects (mirroring the pattern already used
in `test_dataset_profiles.py`) — not merely asserted true against the four real profiles,
which would risk being a no-op check.

## Leakage integration

Every case with an `agent_visible_context` is run through
`security.leakage.validate_against_boundary`, which itself calls
`contracts.boundary.validate_agent_visible` first (never bypassed) before layering the
wider recursive/serialization checks on top. Tested at the integration level (not just
relying on `security/`'s own unit tests) across direct dict, nested dict, list, tuple,
dataclass, and JSON serialization round-trip injection vectors, plus the specific
GOLD_EVIDENCE distinction: evidence **content** is permitted into the agent-visible
context under that condition, but the literal benchmark `gold_evidence_id` string is
never used as the exposed memory's id — content is re-keyed under an opaque
`evidence-slot-{n}` handle instead (see `dataset_adapter.build_agent_visible_context_for_case`).

## Determinism & reproducibility

The same `EvaluationCase` run twice through `evaluate_case()` produces an identical
`EvaluationCaseResult` and identical fingerprints (`security.reproducibility.fingerprint`
over the trace/evaluation_result/metrics/overall) — no new fingerprint algorithm, no new
canonicalization rule. Ranking-sensitive inputs (`retrieved_memory_ids`) are never
reordered by this layer.

## Traceability

Every `EvaluationCaseResult` carries a `trace` dict shaped like
`trace_artifact.schema.json` (candidate_set = retrieved ids, selected_evidence = selected
ids, reasoning_context = a reference to the condition + memory count, final_response = the
agent's raw answer — candidate_discovery/reranking/reasoning_output remain `null`, since
no retrieval/reranking/reasoning implementation exists anywhere in Phase 3.2, per that
schema's own field descriptions) and an `evaluation_result` dict shaped like
`evaluation_result.schema.json`, both schema-validated the same way as the agent-visible
context.

## Contract inconsistency: discovered, then resolved (3.2-H remediation)

`evaluator_reference.schema.json`'s `gold_answer` field was originally typed `"string"`
with no `null` option. The LoCoMo dataset profile (3.2-G) documents `answer_availability:
PARTIAL` with real `null` answers for `question_type "5"` records. `dataset_adapter.py`'s
`EvaluatorReference`-shaped dict faithfully carries `gold_answer: None` for such a record
— correct with respect to the source data, but not valid against the schema as originally
written.

**Audit before remediating.** Before touching the schema, `agent.outcomes
.evaluate_answer_correctness` was inspected and found to *already* treat
`expected_answer is None` as `SUCCESS_EVALUATION_UNDEFINED` (a 3.2-E decision, unrelated
to this gap, made independently of any dataset consideration) — i.e. the production code
this schema is meant to describe already assumed `gold_answer: Optional[str]`. The schema
was the only place still out of sync. This made the fix small and low-risk: **align the
schema with behavior the code already implements and already has passing tests for**,
rather than inventing a new representation.

**Resolution (PROVISIONAL, per `evaluator_reference.schema.json`'s own updated
description):** `gold_answer` is now `{"type": ["string", "null"]}`. The key remains
**required** — omitting it entirely is still a schema violation
(`test_evaluator_reference_schema_still_requires_the_key_present` proves this was not
loosened) — only its *value* may legitimately be `null`. `null` and `""` (empty string)
are **explicitly distinct, never collapsed**: `null` means "no gold answer exists in the
source record at all" (→ `EVALUATION_UNDEFINED`, never `ANSWER_INCORRECT`); `""` means
"the source record's gold answer literally is the empty string" (→ a real, defined
exact-match comparison, proven by `test_empty_string_gold_answer_is_not_treated_as_
undefined`, which shows an empty gold answer compared against a non-empty synthetic
answer correctly evaluates to `ANSWER_INCORRECT`, not `UNDEFINED`).

`pipeline.py` now schema-validates the resulting `EvaluatorReference` shape too (via the
new `validate_evaluator_reference_shape()`, called for every task-applicable case before
any metric is computed), stripping only this integration layer's own bookkeeping keys
(`applicable`, `dataset_id`) that are not part of the frozen schema.

No dataset file was touched. No answer was fabricated, filled, or inferred. No metric
definition, Strict TSR, evidence metric, or dataset profile changed. This is the only
change made to any protected 3.2-B/C/D/E/F/G surface in the entire 3.2-H stage (including
this remediation), and it is additive/widening (a previously-invalid-but-honest value is
now accepted), never a removal or weakening of an existing guarantee.

## Supported scenarios

1. Fully evaluable task → `SUCCESS`
2. Retrieval miss → `RETRIEVAL_FAILURE` (via `classify_gold_id_capacity`, reused)
3. Selection miss → `SELECTION_FAILURE`
4. Agent answer incorrect despite selected evidence → `AGENT_FAILURE_WITH_EVIDENCE`
   (Strict TSR = 1, answer incorrect — memory success ≠ agent success, demonstrated)
5. Missing answer → answer correctness `EVALUATION_UNDEFINED`, never `ANSWER_INCORRECT`
6. Missing evidence IDs → Strict TSR `STATUS_UNDEFINED_EMPTY_GOLD`, never `0.0`
7. MSC, no task layer → task metrics `NOT_ATTEMPTED` (scope=DATASET); memory-only
   diagnostics remain attemptable
8. Conversation Chronicles, no task layer → same principle
9. Leakage attempt → detected and rejected by the pipeline's own leakage step
10. Deterministic rerun → identical result and fingerprint

## Provisional decisions

- `STATUS_NOT_ATTEMPTED` and its `scope` (`DATASET`/`CASE`) distinction — **PROVISIONAL**:
  a new integration-level status, not frozen by any prior contract.
- The opaque `evidence-slot-{n}` re-keying convention for GOLD_EVIDENCE content —
  **PROVISIONAL**: mirrors the existing 3.2-B fixture's design choice but is this stage's
  own extension of it into a general adapter.
- `_compute_strict_tsr`'s case-level empty-gold guard (returning
  `STATUS_UNDEFINED_EMPTY_GOLD` instead of trusting `strict_tsr()`'s own well-defined
  `0.0` for this specific integration use) — **PROVISIONAL**: an additive, case-level
  interpretation layered on top of the unmodified 3.2-C function, not a redefinition of it.
- Aggregation: this stage deliberately does **not** aggregate metrics across cases from
  different datasets (per the task brief's explicit prohibition on mixing incomparable
  datasets) — `evaluate_paired_case`/`evaluate_gold_evidence_ceiling` operate over an
  explicit, caller-supplied set of same-dataset, same-task results only.

## What this stage does NOT do

No LLM, no Qwen, no real agent, no real retrieval/reranking/candidate-generation, no
dataset modification of any kind, no new dataset registry, no new metric formula, no
schema rewrite. This stage proves the measurement instrument works before a model is
placed inside it.
