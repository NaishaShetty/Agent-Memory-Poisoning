# Phase 3.2-C — Core Memory Metrics

Status: **METRIC IMPLEMENTATION**. This stage implements the ten metric families scoped for
Phase 3.2-C below, as pure, tested, deterministic functions over the artifacts defined in
Phase 3.2-B (`phase3/evaluation/contracts/*.schema.json`). It does not implement evidence-
equivalent/semantic scoring, provenance/lineage/lifecycle metrics, memory/gold-memory
contribution, retrieval/reranking/selection, dataset adapters, Qwen, or leakage/
determinism harnesses — see "Out of scope" below.

All functions live in `phase3/evaluation/metrics/`:
- `types.py` — the shared `MetricResult` dataclass and status-vocabulary constants.
- `retrieval.py` — Recall@K, MRR, selection-capacity diagnostics.
- `selection.py` — selection count/cardinality, Strict TSR.
- `evidence.py` — evidence precision, evidence recall, evidence coverage, irrelevant-
  memory rate, redundancy (identity-duplication only).

Tests: `phase3/evaluation/tests/test_core_memory_metrics.py` (new file; does not modify
`test_evaluation_contracts.py`, whose 62 tests remain green unmodified).

## Design principles

- **Pure functions.** Every metric function is `inputs -> MetricResult`. No filesystem,
  network, LLM, embeddings, or randomness access anywhere in this package, and no global/
  mutable state.
- **Deterministic.** Same inputs always produce the same `MetricResult`.
- **No silent zero-conversion.** An undefined case (empty gold set, empty selection, `k <=
  0`, empty task set, etc.) is never quietly reported as `0.0`. It is reported as
  `value=None` with an explicit `status` explaining why, so a caller can distinguish
  "computed zero" from "undefined here."
- **One shared result type.** Every function returns a `MetricResult`
  (`metric_name`, `value`, `status`, `detail`, `note`) — see `types.py`. `detail` always
  carries enough structure (counts, denominators, the exact k requested vs. used, etc.) to
  debug the computation without re-deriving it.
- **Evaluator-side only.** Every function that needs gold data takes it as a plain ID list
  or an `EvaluatorReference`-shaped value — never an `AgentVisibleContext`-shaped object.
  This is enforced by an automated test
  (`test_no_metric_function_takes_agent_visible_context`,
  `test_metrics_module_never_imports_agent_visible_context_type`) as well as by convention.

## The ten metrics

### 1. Recall@K

**Purpose.** Did candidate discovery/retrieval surface at least one gold-evidence id
within the top K of a single ranked retrieval list, for one task?

**Definition.**
```
recall_at_k(retrieved_ranked_ids, gold_ids, k) =
    1  if set(retrieved_ranked_ids[:k]) & set(gold_ids) is non-empty
    0  otherwise
```
The prefix `retrieved_ranked_ids[:k]` is **not deduplicated** — a duplicate id occupying
two prefix slots is examined as-is; no contract document specifies dedup behavior, so the
literal order-preserving prefix is used.

**Inputs.** `retrieved_ranked_ids: Sequence[str]` (rank-ordered), `gold_ids:
Sequence[str]`, `k: int`.

**Outputs.** `MetricResult` with `value` in `{0.0, 1.0}` or `None` (see edge cases).

**Edge cases.**
- `k <= 0` → undefined (`STATUS_UNDEFINED_K_NON_POSITIVE`).
- `gold_ids` empty → undefined (`STATUS_UNDEFINED_EMPTY_GOLD`) — deliberately not treated
  as vacuously 0 or vacuously 1.
- `retrieved_ranked_ids` empty, `gold_ids` non-empty → well-defined `0.0`.
- `k > len(retrieved_ranked_ids)` → well-defined; evaluated over the whole (shorter) list,
  `detail["k_effective"]` records the clamp, `note` states it explicitly.
- Duplicate ids in `retrieved_ranked_ids` → not deduplicated (see Definition above).

**Duplicate behavior.** Not deduplicated in the retrieved list (see above).

**Multi-gold behavior.** "Any" semantics — a hit on *any* gold id within the prefix counts;
this is a single task-level 0/1, not a per-gold-id breakdown (for the per-gold-id
breakdown, see Selection-capacity diagnostics below).

**Evaluator-only dependency.** Both `retrieved_ranked_ids` and `gold_ids` are evaluator-
supplied; `gold_ids` must come from `EvaluatorReference.gold_evidence_ids`.

**Relationship to other metrics.** **Recall@K ≠ final evidence recall** (see #7). Recall@K
is rank-cutoff-bound and operates on the *retrieved* order; evidence recall operates on the
*final selected* set with no rank concept. Worked example proving the distinction (also a
test): `retrieved=[A,B,C,D]`, `selected=[A,C]`, `gold=[A,D]` → `Recall@4 = 1`,
`evidence_recall = 1/2`.

**What it does NOT measure.** Whether the selected/final evidence set is precise or
complete (that's evidence precision/recall), whether the agent's *answer* was correct, or
identity-vs-semantic distinctions.

### 2. MRR (Mean Reciprocal Rank)

**Purpose.** How early, on average across a task set, does the first gold hit appear in
the ranked retrieval list?

**Definition.**
```
reciprocal_rank(retrieved_ranked_ids, gold_ids) =
    1 / r   where r is the 1-indexed position of the FIRST retrieved id that is in gold_ids
    0       if no such id exists (STATUS_NO_HIT — a well-defined, meaningful outcome)

mean_reciprocal_rank(task_retrievals, task_golds) = mean(reciprocal_rank(...) for each task)
```

**Inputs.** `reciprocal_rank`: one ranked list + one gold list. `mean_reciprocal_rank`: a
list of ranked lists + a same-length list of gold lists (one task set).

**Outputs.** `reciprocal_rank` → value in `[0, 1]` or `None`. `mean_reciprocal_rank` →
value in `[0, 1]` or `None`.

**Edge cases.**
- `gold_ids` empty (per task) → undefined for that task (`STATUS_UNDEFINED_EMPTY_GOLD`);
  such tasks are excluded from the mean, and the exclusion count is reported in
  `detail["excluded_empty_gold_tasks"]` rather than silently folded into a 0.
- `retrieved_ranked_ids` empty (gold non-empty) → well-defined `0.0`, `STATUS_NO_HIT`.
- Empty task set (`len(task_retrievals) == 0`) → undefined
  (`STATUS_UNDEFINED_EMPTY_TASK_SET`), never silently `0/0 -> 0`.
- If every task in the set has empty gold → undefined
  (`STATUS_UNDEFINED_EMPTY_GOLD`, at the aggregate level).
- Mismatched `task_retrievals`/`task_golds` lengths → raises `ValueError` (a caller
  contract violation, not a metric-definition ambiguity).

**Duplicate behavior.** First occurrence (lowest index) of a gold id determines rank;
later duplicate occurrences of the same id are irrelevant.

**Multi-gold behavior.** "First hit of any gold id" — same as Recall@K's "any" semantics,
but reported as a rank rather than a binary hit/miss.

**Evaluator-only dependency.** Gold lists are evaluator-supplied (`gold_evidence_ids`).

**Relationship to other metrics.** Complementary to Recall@K — Recall@K asks "hit within
K?" as a binary; MRR asks "how early?" as a continuous [0,1] score. `Recall@K(k) == 1` for
some task iff that task's `reciprocal_rank >= 1/k`.

**What it does NOT measure.** Selection or precision/recall of the final evidence set;
answer correctness.

### 3. Strict TSR

**Purpose.** Diagnostic/comparability metric only (per `EVALUATION_CONTRACT.md` section 3)
— retained for continuity with historical Phase 3 results, explicitly **not** a definition
of agent success.

**Definition.**
```
strict_tsr(selected_or_used_ids, gold_evidence_ids) =
    1  if len(set(selected_or_used_ids) & set(gold_evidence_ids)) > 0
    0  otherwise
```
This is the exact historical formula from
`phase3_reference/clean_agent_v1/src/reference_agent.py`
(`set(used_memory_ids) & set(evidence_memory_ids)`), reused verbatim per
`EVALUATION_CONTRACT.md` section 3 and `phase3/evaluation/AUDIT.md` section 4/8. **The new
metrics module never imports `phase3_reference/` code** — the historical-compatibility
test (`test_historical_strict_tsr_compatibility` in
`test_core_memory_metrics.py`) re-derives the formula inline as a literal expression over
synthetic cases and asserts numeric equality with `strict_tsr()`'s output, rather than
importing the historical module.

**Inputs.** `selected_or_used_ids: Sequence[str]` (from `AgentExecutionResult`, evaluator-
side read), `gold_evidence_ids: Sequence[str]` (from `EvaluatorReference`).

**Outputs.** `value` always in `{0.0, 1.0}` — never any other value, never `None` (unlike
precision/recall, an empty selected or empty gold set still yields a well-defined,
meaningful `0` here: "no overlap because there is nothing to overlap with" is not
ambiguous the way a ratio's zero-denominator is).

**Edge cases.** Empty `selected_or_used_ids` and/or empty `gold_evidence_ids` → both well-
defined as `0.0`; `detail["selected_empty"]` / `detail["gold_empty"]` flag which, so a
caller can distinguish "0 because nothing matched" from "0 because there was nothing to
match."

**Duplicate behavior.** Both sides converted to sets before intersecting; duplicates have
no effect on the result.

**Multi-gold behavior.** "Any overlap" — a single 0/1 per task, not a per-gold-id count.

**Evaluator-only dependency.** Consumes `EvaluatorReference.gold_evidence_ids` +
`AgentExecutionResult.selected_memory_ids`/`used_memory_ids`. Never derived from
`AgentVisibleContext` — agent-visible data never carries `gold_evidence_ids` at all (per
`LEAKAGE_AND_VISIBILITY_CONTRACT.md`).

**★ STRICT TSR ≠ agent task success.** This is the single most important labeling
decision in this package, per `EVALUATION_CONTRACT.md` sections 1 and 3:
`TSR ≠ QA accuracy`, `TSR ≠ reasoning accuracy`, `TSR ≠ complete agent success`. A selected
memory that is semantically equivalent to or a content-duplicate of gold evidence, but
carries a different `memory_id`, still scores a Strict TSR **failure** — that gap is the
evidence-equivalent-success diagnostic's job (`EVALUATION_CONTRACT.md` section 4), which is
explicitly **out of scope** for Phase 3.2-C (see below).

**What it does NOT measure.** Answer correctness, reasoning quality, evidence-equivalent
success, or evidence precision/recall/coverage.

### 4. Selection count

**Purpose.** How many distinct memories did evidence selection choose to pass to
reasoning, for one task (and, aggregated, across a set of runs)?

**Definition.**
```
selection_count(selected_ids) = |set(selected_ids)|        (distinct cardinality)
```
`detail["raw_count"]` also reports `len(selected_ids)` (duplicate-inclusive) for callers
who want that interpretation without recomputing it.

**Duplicate behavior (explicit default).** Duplicates count **once** — `selected_ids` is
treated as a set. Rationale: `selected_memory_ids` conceptually means "which distinct
memories occupy the reasoning context"; a memory "selected twice" still occupies the
context once.

**Aggregation.** `selection_count_aggregate(selected_id_lists)` computes mean/median/min/
max selection count across a list of runs. An empty list of runs is undefined
(`STATUS_UNDEFINED_EMPTY_SEQUENCE`), not silently `0`.

**Inputs/Outputs.** `Sequence[str]` in, `MetricResult` with `value >= 0` out (never
undefined for a single non-aggregate call — cardinality of the empty set is unambiguously
`0`, unlike a ratio).

**Evaluator-only dependency.** None strictly required — this metric can be computed purely
from `AgentExecutionResult.selected_memory_ids`, with no gold comparison at all. It is
grouped here as a "core memory metric" rather than agent-visible output because it
characterizes the memory/selection subsystem's behavior, not the reasoning layer's.

**What it does NOT measure.** Whether the selected memories were *correct* (that's evidence
precision/recall/Strict TSR).

### 5. Selection-capacity diagnostics (retrieval-miss vs. selection-miss vs. hit)

**Purpose.** For each gold-evidence id in a task, classify *why* it did or didn't make it
into the final selected set — was it never even retrieved (a candidate-discovery/retrieval
problem), or was it retrieved but dropped by selection (a selection-layer problem)? Per
`EVALUATION_CONTRACT.md` section 2 and the historical ~72.4%/14.8%/12.8% root-cause split
this must never be collapsed into one bucket.

**Definition.** For each `gold_id`:
```
HIT             if gold_id in selected_ids
SELECTION_MISS  elif gold_id in retrieved_ids
RETRIEVAL_MISS  else
```
Exactly one of the three applies per gold id — mutually exclusive, collectively
exhaustive.

**Inputs.** `retrieved_ids` and `selected_ids` (both from `AgentExecutionResult`), and
`gold_ids` (from `EvaluatorReference.gold_evidence_ids`).

**Outputs.** `selection_capacity_report()`'s `value` is the convenience hit-rate
(`count(HIT) / len(gold_ids)`); the load-bearing output is `detail["per_gold"]` (id →
classification) and `detail["counts"]` (three separate counters — `RETRIEVAL_MISS` and
`SELECTION_MISS` are never merged).

**Edge cases.** Empty `gold_ids` → undefined (`STATUS_UNDEFINED_EMPTY_GOLD`), empty
`per_gold`/`counts`.

**Multi-gold behavior.** Native — this metric is inherently per-gold-id; multiple gold ids
each get their own classification in `detail["per_gold"]`.

**★ Retrieval failure ≠ selection failure.** These are deliberately kept as two distinct,
never-merged classifications (`classify_gold_id_capacity` returns exactly one of
`RETRIEVAL_MISS`/`SELECTION_MISS`/`HIT`, never a combined "not-found" bucket), per the
historical root-cause finding that these two failure modes have very different remediation
paths (fix candidate discovery vs. fix selection budget/logic).

**What it does NOT measure.** Any single scalar summary across many tasks (this module
reports per-task classifications; aggregation across a task set, if wanted, is a
straightforward mean over `selection_capacity_report(...).value` per task, left to the
caller — not implemented as a separate aggregate function here since the per-gold-id
breakdown is the primary artifact, not the aggregate scalar).

### 6. Evidence precision

**Purpose.** Of what evidence selection actually chose, how much was gold?

**Definition.**
```
evidence_precision(selected_ids, gold_ids) = |set(selected_ids) ∩ set(gold_ids)| / |set(selected_ids)|
```

**Edge cases.** `selected_ids` empty → undefined (`STATUS_UNDEFINED_EMPTY_SELECTED`) — a
0/0 ratio has no principled reading here ("no evidence was selected" is neither "all
relevant" nor "none relevant").

**Range.** `[0, 1]` when defined.

**Relationship to other metrics.** Complement of irrelevant-memory rate (#9) under the
shared relevance definition — see #9.

### 7. Evidence recall

**Purpose.** Of all the gold evidence that exists, how much did the final selected set
recover?

**Definition.**
```
evidence_recall(selected_ids, gold_ids) = |set(selected_ids) ∩ set(gold_ids)| / |set(gold_ids)|
```

**Edge cases.** `gold_ids` empty → undefined (`STATUS_UNDEFINED_EMPTY_GOLD`).

**Range.** `[0, 1]` when defined.

**★ Recall@K ≠ final evidence recall.** See #1's worked example
(`retrieved=[A,B,C,D]`, `selected=[A,C]`, `gold=[A,D]` → `Recall@4=1`,
`evidence_recall=1/2`) — these are proven distinguishable, not merely asserted distinct, by
a dedicated test.

### 8. Evidence coverage — **PROVISIONAL, UNRESOLVED AMBIGUITY**

**Status of the ambiguity.** Neither `EVALUATION_CONTRACT.md` nor
`PHASE3_CLEAN_AGENT_FOUNDATION_SPEC.md` gives evidence coverage a precise formula — both
simply list it by name next to evidence precision/recall (`EVALUATION_CONTRACT.md` section
2). `phase3/evaluation/AUDIT.md` sections 3 and 10 independently confirm "no historical
implementation located anywhere." **This module does not invent a formula silently, and
does not equate coverage with Recall@K or with evidence recall.** The interpretation below
is implemented and clearly labeled as provisional; a future contract revision may replace
it.

**Implemented (provisional) definition.**
```
evidence_coverage(all_candidate_ids_across_run, gold_ids) =
    |distinct(all_candidate_ids_across_run) ∩ distinct(gold_ids)| / |distinct(gold_ids)|
```
i.e. the fraction of distinct gold ids that appear **anywhere in the full candidate pool**
supplied for a run — no rank cutoff, no restriction to the final selected set. This differs
from:
- **Recall@K** (#1): rank-cutoff-bound, evaluated against one ranked retrieval list, "any
  gold in top-K" as a binary per task.
- **Evidence recall** (#7): bound to the *final selected* set, no candidate-pool or rank
  concept at all.

Evidence coverage, as implemented here, sits at a different level: "was the gold evidence
ever *findable*, anywhere in whatever candidate ids the run produced" — a superset-level
question. This is the most conservative reading defensible from the contract text (it does
not assume a rank cutoff or a specific selection outcome, which the contract text does not
mention for this metric), but it is explicitly NOT frozen.

**Edge cases.** `gold_ids` empty → undefined (`STATUS_UNDEFINED_EMPTY_GOLD`).

**Action for a future stage.** If a later contract revision fixes evidence coverage's
formula, `evidence_coverage()` must be updated (or superseded) accordingly, and this README
section revised — do not let this provisional definition silently calcify into "the"
definition without a contract update.

### 9. Irrelevant-memory rate

**Purpose.** Of what was selected, how much was *not* gold?

**Definition.**
```
irrelevant_memory_rate(selected_ids, gold_ids) = |set(selected_ids) - set(gold_ids)| / |set(selected_ids)|
```

**Edge cases.** `selected_ids` empty → undefined (`STATUS_UNDEFINED_EMPTY_SELECTED`),
mirroring evidence precision.

**Relationship to evidence precision — stated explicitly, not silently duplicated.**
Under this module's shared "relevant == member of gold_ids" definition and the same
non-empty-selected denominator:
```
irrelevant_memory_rate(selected, gold) == 1 - evidence_precision(selected, gold)
```
for every input where both are defined. This identity is proven by a dedicated test
(`test_irrelevant_memory_rate_is_exact_complement_of_precision`), not left as an unstated
coincidence. The two functions still compute independently (via set difference vs. set
intersection) rather than one calling the other, so each remains independently readable.

### 10. Redundancy (identity-duplication only)

**Purpose.** How many exact-identity duplicate memory ids appear within a retrieved-or-
selected id sequence?

**Definition.**
```
duplicate_count   = len(id_sequence) - len(set(id_sequence))
redundancy_rate   = duplicate_count / len(id_sequence)     (when id_sequence non-empty)
```

**Edge cases.** Empty `id_sequence` → rate undefined (`STATUS_UNDEFINED_EMPTY_SEQUENCE`);
`detail["duplicate_count"]` is still reported as `0` since a count (unlike a rate) is
well-defined even for an empty sequence.

**★ Identity duplication ≠ semantic equivalence.** This function measures ONLY exact
`memory_id` string repetition within a sequence (e.g. the same memory surfaced twice by a
retrieval or selection pass). It does **not** detect two *different* memory ids whose
*content* means the same thing (an `equivalent_to` relationship per `memory_schema.md`
section 3.3) or a content-level duplicate. Semantic/evidence-equivalence scoring is
explicitly **Phase 3.2-D** work (see `EVALUATION_CONTRACT.md` section 4's "evidence-
equivalent success"), not implemented anywhere in this package.

## The four load-bearing distinctions (explicit callouts)

- **STRICT TSR ≠ agent task success.** See metric #3. TSR is a literal-identity
  diagnostic, retained for historical comparability, never a complete success measure
  (`EVALUATION_CONTRACT.md` sections 1 and 3).
- **Recall@K ≠ final evidence recall.** See metrics #1 and #7. Recall@K is rank-cutoff-
  bound over one ranked retrieval list; evidence recall is selected-set-bound with no rank
  concept. Proven distinguishable via a worked example, not merely asserted.
- **Identity duplication ≠ semantic equivalence.** See metric #10. Redundancy here counts
  only exact `memory_id` repeats; semantic/evidential equivalence between *different* ids
  is out of scope (Phase 3.2-D).
- **Retrieval failure ≠ selection failure.** See metric #5. `RETRIEVAL_MISS` (never
  surfaced by candidate discovery) and `SELECTION_MISS` (surfaced but dropped by selection)
  are kept as two distinct, never-merged classifications.

## Out of scope for Phase 3.2-C (explicitly NOT implemented here)

Per the 3.2-C task brief and `EVALUATION_CONTRACT.md`/`PHASE3_CLEAN_AGENT_FOUNDATION_SPEC.md`
section 21-22, this package does **not** implement: evidence-equivalent/semantic scoring
(Phase 3.2-D), provenance completeness/lineage correctness/lifecycle validity/orphan/
invalid-transition metrics, memory contribution / gold-memory contribution deltas, gold-
memory ceiling, retrieval utilization, agent answer correctness (EM/F1/abstention), task
success beyond Strict TSR as defined above, a leakage detector, a determinism/
reproducibility harness, dataset adapters, Qwen integration, or retrieval/reranking/
selection/memory-creation/storage implementations. All of the above remain future Phase 3
stages' scope.

## Running the tests

```
python -m pytest phase3/evaluation/tests/ -q
```

As of this stage: 150 tests total (the original 62 `test_evaluation_contracts.py` tests,
unmodified, plus 88 new `test_core_memory_metrics.py` tests), all passing, run twice to
confirm determinism.
