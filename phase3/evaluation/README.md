# Phase 3.2-B — Evaluation Run & Data Contract

Status: **DATA CONTRACT ONLY.** This stage defines JSON Schema contracts, a runtime
boundary-enforcement module, and synthetic fixtures for the objects the Phase 3 evaluation
layer will pass around. **No metric is computed anywhere in this stage.** No Recall@K, MRR,
TSR, evidence-equivalent scoring, precision/recall, provenance/lineage/lifecycle metrics,
memory-contribution deltas, leakage-detector runtime, determinism harness, dataset adapter,
Qwen integration, retrieval, reranking, selection, or memory creation/storage code exists
here. Only synthetic, hand-authored fixture data is used — nothing is copied from a real
dataset.

## Purpose

Phase 3.1 froze the specification, memory ontology, relationship/event model, layer
separation, evaluation methodology, leakage/visibility rules, traceability requirements, and
reproducibility requirements (see `phase3/specification/`, `phase3/schemas/`,
`phase3/contracts/`). Phase 3.2-A (`phase3/evaluation/AUDIT.md`) surveyed all existing
evaluation-relevant code (all of it in `phase3_reference/`, historical-only) and concluded
that Phase 3.2 must design and implement a new, tested evaluation layer from scratch, and
that no shared, standardized evaluation-run artifact schema exists anywhere in the
repository.

Phase 3.2-B is that missing shared schema layer. It defines the six data-contract objects
every later evaluation component (3.2-C metrics, a future agent runner, a future leakage
audit tool) will read and write, **before** any of those components are built, so they are
all built against one stable, tested envelope instead of each inventing its own ad-hoc JSON
shape (which is exactly what the historical corpus did — see AUDIT.md section 10,
"Evaluation-run artifacts (general): every historical experiment writes its own ad-hoc JSON
report format").

## The six contracts

All in `phase3/evaluation/contracts/`, JSON Schema Draft 2020-12, each requiring a
`schema_version` string field (convention: `"<phase>-<stage>.<revision>"`, e.g.
`"3.2-b.1"`, chosen for this stage and used consistently across all six):

1. **`evaluation_run.schema.json`** — `EvaluationRun`. Identity + pointers only: `run_id`,
   `task_id`, `dataset_identity`, and `condition` are immutable identity fields (documented
   as such in their schema `description`s); the rest are opaque `*_ref` string pointers to
   the other five artifacts. Never embeds agent-visible or evaluator-only content directly.
2. **`agent_visible_context.schema.json`** — `AgentVisibleContext`. Everything the reasoning
   layer may legitimately see: task, legitimate observations, selected/retrieved memory
   *content*, legitimate tool results, permitted provenance. `additionalProperties: false`
   and the forbidden fields (gold answers, gold evidence IDs, evaluator labels/scores,
   retrieval ground truth, internal evaluator metadata, attack labels, hidden benchmark
   metadata) are never listed as properties anywhere in the schema.
3. **`evaluator_reference.schema.json`** — `EvaluatorReference`. Everything agent-hidden:
   gold answer, gold evidence IDs, evidence-equivalence references, task labels, benchmark
   annotations, expected evidence content, evaluation metadata. Evaluator-only, by
   construction never read by agent execution.
4. **`agent_execution_result.schema.json`** — `AgentExecutionResult`. Raw agent output:
   response text, selected/retrieved memory IDs, execution status/error, timing, trace ref.
   No metric or gold-comparison field anywhere.
5. **`trace_artifact.schema.json`** — `TraceArtifact`. Structural placeholder for the full
   task-execution chain from `TRACEABILITY_CONTRACT.md` section 2 (task → candidate
   discovery → candidate set → reranking → selection → selected evidence → reasoning
   context → reasoning output → final response). Every field past `schema_version`/`task_id`
   is optional/nullable, since candidate discovery, reranking, selection, and reasoning
   don't exist yet (per AUDIT.md, no historical component ever wired these into one live
   run) — this schema lets 3.2-C+ populate fields incrementally without a breaking change.
6. **`evaluation_result.schema.json`** — `EvaluationResult`. The scoring envelope: run
   identity, evaluator/metric-set versions, `result_status`, `metrics` (a deliberately empty
   placeholder object), warnings/errors, timestamp, input artifact refs. `metrics` carries no
   named property — 3.2-C populates it without changing this schema.

## Why the agent-visible / evaluator-only separation is structural, not naming

The 3.2-A audit's central risk finding was that the historical
`phase3_reference/clean_agent_v1/src/reference_agent.py`'s `TaskRunner.run_task` computed
both the agent's trajectory and its TSR judgment inside **one function**, reading
`evidence_memory_ids` (gold) in the same call that produced `used_memory_ids` (agent
output). The module's own docstring flagged this as "not how the agent decides usage," but
nothing *enforced* that beyond a comment.

This stage prevents that class of conflation two independent ways:

- **Schema-level.** `AgentVisibleContext` and `EvaluatorReference` are two separate JSON
  Schema documents. Neither schema lists the other plane's fields as properties, and both
  set `additionalProperties: false`, so a payload carrying a forbidden key fails validation
  structurally — not because a convention says not to add it. `test_no_god_object_schema_contains_both_planes`
  asserts no schema in the set defines content fields from both planes at once.
- **Runtime-level (defense in depth).** `phase3/evaluation/contracts/boundary.py`'s
  `validate_agent_visible(payload)` recursively scans a payload for a list of forbidden keys
  (gold answer/evidence IDs, evaluation labels/scores, retrieval ground truth, internal
  ranks, attack labels, etc.) at any nesting depth and raises if found — this catches a
  hand-constructed dict that skipped JSON Schema validation entirely. Its signature takes
  **only** the agent-visible payload; it has no `evaluator_reference` parameter, anywhere,
  by design. This operationalizes "the agent path must not import or depend on
  EvaluatorReference" as a checkable fact (see
  `test_validate_agent_visible_signature_has_no_evaluator_reference_param`), not an aspiration.

## Current scope — what is explicitly NOT implemented

- No metric computation (Recall@K, MRR, TSR, evidence-equivalent success, precision/recall/
  coverage, redundancy, provenance/lineage/lifecycle validity, memory/gold-memory
  contribution deltas) — that is **Phase 3.2-C**.
- No leakage-detector runtime, no determinism/reproducibility harness, no dataset adapter, no
  retrieval/reranking/selection code, no memory creation/storage code, no Qwen integration,
  no real agent execution, no Phase 4 attack/defense code.
- `EvaluationResult.metrics` is an intentionally empty placeholder object.
- `TraceArtifact`'s pipeline-stage fields are nearly all `null` in every fixture, because the
  layers that would populate them (candidate discovery, reranking, selection, reasoning
  context assembly, reasoning layer) are not built yet.

## Fixtures (`phase3/evaluation/fixtures/`)

All fixtures are small, hand-authored, deterministic JSON — **not** copied from LoCoMo,
LongMemEval, MSC, or Conversation Chronicles (all of which remain frozen Phase 1/2
substrate; `tests/fixtures/{locomo,longmemeval}/` were confirmed empty by AUDIT.md and are
untouched by this stage). Synthetic fixtures are used instead of real dataset samples so
that (a) no real gold-answer/evidence content needs to be reproduced or redistributed here,
and (b) the fixtures can be constructed specifically to exercise the leakage-boundary
behavior under test, independent of any particular dataset's actual content.

- **`no_memory/`** — Condition A. `AgentVisibleContext` contains only the task prompt, no
  memory content. `EvaluatorReference` separately holds a gold answer and gold evidence ID.
- **`gold_evidence/`** — Condition B. `AgentVisibleContext` contains the task plus the gold
  evidence **content** (text), under its own opaque `memory_id` (`"evidence-slot-1"`), not
  the benchmark's literal gold evidence ID (`"locomo-mem-8842"`). This is a deliberate design
  choice: `LEAKAGE_AND_VISIBILITY_CONTRACT.md` section 1 and `CLEAN_AGENT_INTERFACES.md`
  section 2.4 list "gold evidence IDs" as agent-hidden, **absolute, with no condition-based
  exception** — so even under the gold-evidence control condition, the literal ID string
  never appears in the agent-visible document, only the content does.
- **`retrieved_memory/`** — Condition C. `AgentVisibleContext` contains task + retrieved/
  selected memory content (two memories, distinct opaque IDs), `EvaluatorReference` held
  separately.
- **`derived_memory/`** — Two foundation memories (`mem-found-A`, `mem-found-B`) and one
  derived memory (`mem-derived-C`) with explicit `parent_ids` pointing at both, per
  `memory_schema.json` section 3.2 and the "explicit pairwise edges only, no giant lineage
  families" rule.
- **`conflicting_memory/`** — Two memories joined by a symmetric `conflicts_with` edge; one
  is marked `superseded_by` the other and transitions to `RETIRED`, but both records still
  exist as separate files (never deleted), per `memory_schema.md` section 6.
- **`equivalent_memory/`** — Two **distinct** memory identities joined by a symmetric
  `equivalent_to` edge. Identity is never merged; no equivalence score/confidence field is
  computed or stored (per `PHASE3_CLEAN_AGENT_FOUNDATION_SPEC.md` section 4, the exact
  semantic-equivalence threshold remains an experimental decision for a later stage).

## Design decisions made where the contract docs were silent

- **`schema_version` convention**: `"<phase>-<stage>.<revision>"` (e.g. `"3.2-b.1"`), pinned
  via JSON Schema `const` in each schema for this stage, so a wrong/missing version fails
  validation immediately. No contract doc fixed a convention, so the simplest stable string
  scheme was chosen.
- **Artifact reference (`*_ref`) representation**: opaque, non-empty strings.
  `TRACEABILITY_CONTRACT.md` section 6 explicitly leaves the physical storage/indexing
  mechanism undecided; this stage therefore does not assume a filesystem path, URI scheme, or
  database key — refs are just opaque identifiers a later stage's storage layer resolves. The
  fixtures happen to use relative file paths as a convenience for the tests in this repo, not
  as a normative format.
- **`configuration_identity` shape**: left as a free-form, `minProperties: 1` object rather
  than a tightly-typed structure, because the exact configuration surface (retrieval/
  reranking/selection parameters, prompt wording, decoding config) is explicitly listed as
  experimental/not-frozen in `PHASE3_CLEAN_AGENT_FOUNDATION_SPEC.md` section 4 — over-typing
  it here would prematurely freeze something the spec deliberately leaves open.
- **`memory_id` in `AgentVisibleContext.memory_content`**: allowed as an opaque per-memory
  handle, distinct from `EvaluatorReference.gold_evidence_ids`. An agent legitimately knows
  which memory it was handed; what must never leak is the benchmark's gold-labelling of that
  memory. The `gold_evidence/` fixture deliberately uses a different ID string for this
  reason (see above).
- **Event log schema**: `relationship_schema.md` section 3 defines the required event
  fields narratively but Phase 3.1 published no machine-checkable JSON Schema for it. This
  stage did not invent one (out of scope — no new frozen schema was requested), and instead
  ships hand-authored `events.json` files in the relationship fixture directories as plain
  illustrations of the required fields, validated only for field presence in the relationship
  tests, not against a formal schema.
- **jsonschema dependency**: `jsonschema==4.26.0` was already importable in this environment.
  It was used directly without adding it to the root `requirements.txt`, since that file is a
  Phase 1/2-owned repo-root artifact and this stage's scope rules direct leaving ambiguous
  ownership untouched. If a clean environment lacks it, install `jsonschema` before running
  these tests.

## Running the tests

```
pytest phase3/evaluation/tests/ -v
```

The root `pytest.ini` scopes default collection to `tests/` at the repo root, so the
`phase3/evaluation/tests/` path must be passed explicitly (as shown above) — this mirrors how
the existing root test suite is invoked and avoids changing `pytest.ini` for a directory
outside its current scope. All 62 tests pass as of this stage. Coverage: every schema
validates itself as a legal Draft 2020-12 schema; every fixture validates against its
schema; deliberately mutated invalid payloads (missing required fields, bad enum values,
malformed refs, missing/invalid `schema_version`) fail validation; `boundary.py` rejects
forbidden keys even when hand-constructed outside schema validation, including nested ones;
cross-fixture checks confirm no gold answer/evidence-ID value from any `evaluator_reference.json`
appears anywhere in its sibling `agent_visible_context.json`; relationship fixtures
(derived/conflicting/equivalent) are checked for the specific semantics
(explicit parent edges, both-preserved conflicts, distinct-identity equivalence); and
`validate_agent_visible`'s signature is asserted to have no evaluator-reference-shaped
parameter.

## What Phase 3.2-C builds next

Phase 3.2-C implements the **core memory metrics** that operate on the artifacts this stage
defines — chiefly `AgentExecutionResult` (what the agent actually did) compared against
`EvaluatorReference` (gold answer/evidence), populating `EvaluationResult.metrics`:
Recall@{1,5,10,20,50,100,200}, MRR, evidence precision/recall/coverage, selected-/irrelevant-
memory counts, redundancy, the candidate-generation-vs-selection-capacity failure split,
creation/rejection/duplicate/equivalence/reuse rates, foundation-vs-derived usage and
derivation depth, provenance completeness, lineage correctness, lifecycle validity/orphan/
invalid-transition rates, strict TSR (reported only alongside evidence-equivalent success,
never alone, per `EVALUATION_CONTRACT.md`), and the A/B/C agent-level accuracy deltas. None
of that exists yet — this stage only defines the stable envelope 3.2-C will populate.
