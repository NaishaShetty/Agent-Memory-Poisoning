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

## Running the tests (Phase 3.2-C)

```
python -m pytest phase3/evaluation/tests/test_evaluation_contracts.py phase3/evaluation/tests/test_core_memory_metrics.py -q
```

150 tests total (the original 62 `test_evaluation_contracts.py` tests, unmodified, plus 88
`test_core_memory_metrics.py` tests), all passing, run twice to confirm determinism.

---

# Phase 3.2-D — Evidence Equivalence + Provenance / Lineage

Status: **METRIC IMPLEMENTATION** (additive to 3.2-C — no existing metric in `types.py`,
`retrieval.py`, `selection.py`, or `evidence.py` was modified). This stage implements
`equivalence.py` and `provenance.py`: deterministic structural diagnostics over EXPLICIT
`equivalent_to` and `parent_ids` relationships (per `memory_schema.json` /
`relationship_schema.md`) — never inferred from content, embeddings, or an LLM.

## The central distinction

```
MEMORY IDENTITY  ≠  INFORMATION EQUIVALENCE  ≠  EVIDENCE RELEVANCE  ≠  EVIDENCE INDEPENDENCE  ≠  PROVENANCE
```

Two memory objects can be exact content duplicates and still be two distinct identities
(`M42` ≠ `M91`). Two distinct identities can be declared equivalent without that implying
they share a parent, without that implying either is gold evidence for any task, and without
that implying they are independent corroborating sources. A memory's provenance (where it
came from) is a separate question from all of the above. This package keeps every one of
these as its own explicit, separately-computed concept — nothing is merged or inferred across
them.

## `equivalence.py`

**Representation.** Equivalence is the explicit `equivalent_to` field each memory record may
carry (`memory_schema.json`), extracted as `(declaring_id, target_id)` edges via
`extract_equivalence_edges()`. There is no other source of equivalence anywhere in this
package — no string similarity, no embeddings, no LLM judgment.

**Validation (`validate_equivalence_edges()`).** Reports, per edge, any of:
`UNKNOWN_MEMORY_REFERENCE` (endpoint not in the supplied memory set), `SELF_EQUIVALENCE_DECLARED`
(**DECISION E2**: a memory declared equivalent to itself is invalid, not a no-op — identity and
equivalence are different concepts), `ASYMMETRIC_DECLARATION` (**DECISION E1**: symmetry must be
explicitly declared on both sides — `A.equivalent_to ∋ B` AND `B.equivalent_to ∋ A` — matching
how the 3.2-B `equivalent_memory/` fixtures already declare it both ways; a one-sided declaration
is reported, never silently auto-symmetrized, since that would let a memory unilaterally assert
equivalence without the other side's agreement).

**Equivalence classes (`equivalence_classes()`).** Deterministic connected components over
edges declared symmetrically (`require_symmetric=True` default) — e.g. `A≡B`, `B≡C` → one
component `{A,B,C}`. Every memory in the input set appears in exactly one component (isolated
memories form singleton components). Output is sorted/deterministic across repeated calls.
Unknown references (ids not in the supplied memory set) never leak into a component — the
node universe is exactly the supplied memory set when one is given.

**Identity preservation.** `equivalence_classes()` returns *groups of ids* — never a merged
or rewritten id. Two equivalent memories remain two distinct identities forever; nothing in
this package ever collapses `A` and `B` into a single id because `A≡B`.

**What equivalence does NOT imply.** Parent/child relationship, provenance, independent
origin, or task relevance — each is computed independently, only in `provenance.py`.

## `provenance.py`

**Provenance completeness (`validate_provenance()` / `provenance_completeness_report()`).**
Three-way classification, never silently coerced to COMPLETE: `PROVENANCE_COMPLETE` (no
findings), `PROVENANCE_INCOMPLETE` (no hard violation, but a field needed to fully verify
provenance is missing — currently: a derived memory missing `source.reference_id`),
`PROVENANCE_INVALID` (a hard structural violation — missing/invalid `memory_type`,
missing/invalid `source`, a foundation memory falsely claiming parents
(`FOUNDATION_WITH_PARENTS`), a derived memory with no parents (`DERIVED_WITHOUT_PARENTS`), or
an orphan parent reference).

**Parent-edge validation (`validate_parent_edges()`) / orphan detection
(`orphan_parent_count()`).** Every `(parent_id, child_id)` edge implied by `parent_ids` is
validated independently — multi-parent children (`A→C`, `B→C`) keep both edges separately,
never collapsed into a family/group id. A parent_id absent from the supplied memory set is
reported as `ORPHAN_PARENT_REFERENCE`, never repaired or silently dropped.

**Cycle detection (`detect_cycles()`).** Iterative DFS (not recursive — safe against stack
depth blowups) with `visited`/`in_progress` sets. On finding a repeated in-progress node, it
reports the cycle and stops descending through it — it does not attempt to route around the
cycle to keep computing a set, since which edge to drop to "fix" the cycle would be an
arbitrary, integrity-hiding choice.

**Ancestry (`ancestors()`) / descendants (`descendants()`).** Transitive traversal of
`parent_ids` edges at query time (never a precomputed/cached "lineage family" object, which
`relationship_schema.md` explicitly rejects). Excludes the node itself unless
`include_self=True`. Safe on cyclic input: traversal detects a cycle via the same
visited/in-progress technique, stops extending through the repeated node, and reports
`cycle_detected=True` rather than silently returning a possibly-incomplete set with no
indication anything was wrong.

**Root/origin analysis (`root_origins()`).** All lineage roots (memories with no parents)
reachable from a node. Multi-parent derivation keeps every root explicit —
`root_origins(C) = {A, B}` for `A→C`, `B→C` — never arbitrarily picks one.

**Shared-origin detection (`shared_origin_report()`).** For a set of selected memory ids,
reports which root origins are ancestors of 2+ of them — the structural basis for detecting
non-independent corroboration due to common lineage (as distinct from equivalence).

**Lineage depth (`lineage_depth()`) — DECISION P1, PROVISIONAL.** `depth(root) = 0`,
`depth(child) = 1 + depth(parent)`. For multi-parent nodes with parents at different depths,
this implementation uses **MIN**-depth-of-parents, not max — i.e. the shortest legitimate
derivation chain. Neither `memory_schema.md`, `relationship_schema.md`, nor
`TRACEABILITY_CONTRACT.md` specifies min-vs-max for multi-parent derivation, and
`phase3/evaluation/AUDIT.md` flags derivation depth as a not-yet-frozen choice. MIN was chosen
because a diagnostic meant to flag anomalously deep derivation chains should not let a single
short parent path silently understate depth risk in the other direction — but this is
explicitly **PROVISIONAL**, not canonical; a future contract revision may specify max-depth
instead, and this function would need to be revisited. Undefined (not computed) for any node
participating in a cycle.

## Evidence independence diagnostic (`independence_report()`)

**What it is.** A structured (never single-boolean, never a combined score) report over a set
of selected memory ids, built ONLY from explicit lineage (`parent_ids`) and equivalence
(`equivalent_to`) relationships. For every pair, exactly one classification applies:

- `EQUIVALENT_INFORMATION` — same equivalence component.
- `DIRECT_ANCESTOR_DESCENDANT` — one is a lineage ancestor of the other (checked after
  equivalence, so an equivalent pair is never double-reported as ancestor/descendant).
- `SHARED_LINEAGE_ORIGIN` — not equivalent, not ancestor/descendant, but their root-origin
  sets intersect (e.g. `A→B`, `A→C`; `B`,`C` selected → both trace back to `A`).
- `MULTI_ORIGIN_DERIVED` — a per-item (not pairwise) tag: the item itself has more than one
  root origin (e.g. `A→C`, `B→C`; `C` selected → `C` is tagged multi-origin-derived, and is
  never counted as "two memories" — it retains both parent identities explicitly).
- `LINEAGE_INDEPENDENT` — none of the above hold for this pair.
- `UNKNOWN` — one or both ids are absent from the supplied memory set.

### ★ `LINEAGE_INDEPENDENT` does NOT mean epistemically independent

This is the single most important semantic boundary in this stage:

> **`LINEAGE_INDEPENDENT` means only: no explicit `parent_ids` or `equivalent_to` edge
> connects these two memories, and they do not share a detected root origin, in the data
> available to this function.**
>
> It is **NEVER** proof of epistemic/causal independence. Two `LINEAGE_INDEPENDENT` memories
> could still restate the same underlying fact through a completely undeclared channel (e.g.
> both hand-authored by the same curator from the same external source, with no
> `parent_ids`/`equivalent_to` edge ever recorded). This module has no way to see that, by
> design — there is no semantic model here. Always read this classification as
> "*lineage*-independent", never as "independent" unqualified.

`detail["per_item"]` reports each selected id's equivalence component, direct parents, and
root origins; `detail["pairwise"]` reports the per-pair classification. `value` is the count
of `LINEAGE_INDEPENDENT` pairs — a convenience count only, explicitly **not** an opaque
"independence score": no combined evidence-quality or independence score is computed anywhere
in this package.

## CANONICAL / PROVISIONAL / DIAGNOSTIC-ONLY classification

| Diagnostic | Classification | Rationale |
|---|---|---|
| `equivalence_classes` / equivalence components | CANONICAL | Directly implements the explicit `equivalent_to` relation defined in `memory_schema.json`/`relationship_schema.md`; connected-components over explicit symmetric edges is the only defensible reading. |
| `validate_equivalence_edges` findings (unknown ref / self-equivalence / asymmetric) | CANONICAL | Structural validation against the schema's own field semantics; no invented convention beyond DECISION E1/E2, both of which are explicitly documented, non-silent choices grounded in existing fixture conventions. |
| `validate_parent_edges` / `orphan_parent_count` | CANONICAL | Directly implements `parent_ids` structural validation per `relationship_schema.md` section 2.1's explicit-edges-only rule. |
| `detect_cycles` | CANONICAL | Lineage is expected acyclic; detecting a cycle is a structural fact, not an invented metric. |
| `ancestors` / `descendants` / `root_origins` | CANONICAL | Transitive traversal of explicit `parent_ids` edges, exactly as `memory_schema.md` section 5 specifies (no precomputed lineage-family abstraction). |
| `shared_origin_report` | DIAGNOSTIC ONLY | A derived convenience view (root-origin intersection across a selected set) — useful for corroboration analysis, not itself a frozen contract metric. |
| `lineage_depth` | **PROVISIONAL** | Min-vs-max for multi-parent depth is not specified anywhere in the Phase 3.1 contracts (see DECISION P1) — this implementation's MIN-depth convention may be superseded by a future contract revision. |
| `validate_provenance` / `provenance_completeness_report` (COMPLETE/INCOMPLETE/INVALID) | CANONICAL | Structural validation directly against `memory_schema.json`'s required fields per memory type; the three-way split (vs. silently coercing to valid) is the explicit non-negotiable requirement from the 3.2-D task brief. |
| `independence_report` / `LINEAGE_INDEPENDENT` and sibling classifications | DIAGNOSTIC ONLY | A structural diagnostic built from the CANONICAL primitives above (equivalence components, ancestry, root origins) — explicitly scoped, per DECISION P3, to never claim epistemic independence. The vocabulary (`LINEAGE_INDEPENDENT`, `SHARED_LINEAGE_ORIGIN`, etc.) is this stage's own construction, not a frozen Phase 3.1 term. |

## Why no semantic model is used at this stage

Phase 3.1 intentionally did not freeze a semantic/embedding-based equivalence algorithm — see
`EVALUATION_CONTRACT.md` and `phase3/evaluation/AUDIT.md`'s findings on evidence-equivalent
scoring being unimplemented anywhere historically. Inventing one now, inside a stage whose
purpose is to establish *structural* (identity/lineage/explicit-relation) evaluation, would
conflate two different scientific questions: "what does the data explicitly assert" (this
stage) versus "what does the content actually mean" (a future, separately-justified semantic
method). Using embeddings or an LLM here would also reintroduce exactly the
kind of unreproducible, model-dependent judgment MAMBench's evaluator is designed to avoid.
Equivalence, in this package, is **only** what an evaluator explicitly declared — nothing is
guessed from content.

## Integration with 3.2-C

None of `types.py`, `retrieval.py`, `selection.py`, or `evidence.py` was modified by this
stage. `provenance.py` and `equivalence.py` are additive modules; a caller who has both a
3.2-C metric result (e.g. `selected_ids = [A, B, C]`) and a 3.2-D lineage graph (e.g. `A→B`,
`A→C`) can combine them (e.g. "3 memory ids, but only 1 lineage origin") without either module
needing to know about the other's existence. If a future stage needs a provenance-aware
evidence-recall or TSR variant, it should be implemented as a new diagnostic, not a retroactive
redefinition of the existing 3.2-C metrics.

## Running the tests (Phase 3.2-D)

```
python -m pytest phase3/evaluation/tests/ -q
```

240 tests total as of this stage: the original 150 (`test_evaluation_contracts.py` +
`test_core_memory_metrics.py`, both unmodified), plus 90 new tests across
`test_evidence_equivalence.py` and `test_provenance_lineage.py`, all passing, run twice to
confirm determinism.
