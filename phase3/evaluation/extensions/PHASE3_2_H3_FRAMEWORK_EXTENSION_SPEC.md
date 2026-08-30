# Phase 3.2-H.3 — Evaluation Framework Extension Specification

Status: **DESIGN + IMPLEMENTATION RECORD**. This document is written to accompany the code
under `phase3/evaluation/extensions/` — it is the authoritative explanation of *why* each
extension exists, what it does NOT do, and what was deliberately rejected. Code without this
document would leave every non-obvious decision implicit; this document without the code
would be unverifiable prose. Read both together.

## 0. Central discipline

Phase 3.2-H.1 audited three candidate datasets (MemoryAgentBench, MemBench, MemoryArena) and
found that each has a real capability the existing Phase 3.2 evaluation framework cannot
measure. The question this stage answers is **not** "how do we make these three datasets pass
the existing metric suite" — it is: for each H.1-exposed limitation, is it a genuine
**framework** limitation (the measuring instrument itself is too narrow) or a genuine
**dataset** limitation (the source data simply does not contain what a metric needs)? Only the
former justifies new framework code. The latter is reported honestly as `NOT_ATTEMPTABLE` /
`NOT_PROVIDED_BY_SOURCE` and left alone — inventing data to make a dataset limitation
disappear is exactly the failure mode this stage exists to prevent.

## 1. Gap analysis

| H.1 finding | Classification | Reasoning |
|---|---|---|
| MemoryAgentBench: no gold-evidence-ID field anywhere (confirmed by full-corpus scan) | DATASET LIMITATION | The source genuinely never assigns evidence pointers. No amount of framework work fixes an absence in the source. Correctly reported `NOT_PROVIDED_BY_SOURCE`, not fabricated. |
| MemoryAgentBench: `answers[i]` is a list of acceptable alias strings, not one string | FRAMEWORK LIMITATION | `agent.outcomes.evaluate_answer_correctness` only accepts one `expected_answer: Optional[str]`. The source genuinely supplies multiple valid strings; forcing a caller to pick one would silently discard real gold information the source provides. → **Extension 2a** (`answer_matching.evaluate_answer_correctness_multi_reference`). |
| MemBench: gold evidence is `[session_index, turn_index]` positional pairs, not opaque ids | FRAMEWORK LIMITATION | The underlying positional information genuinely exists and is deterministic — it is not being invented. But every existing `Sequence[str]`-based metric assumes a source-native, re-segmentation-stable opaque id string. Silently stringifying the pair and calling it `gold_evidence_ids` would erase a real distinction (a positional pointer shifts if the transcript is re-segmented; an opaque id does not). → **Extension 1** (`evidence_basis.py`'s `EVIDENCE_BASIS_STRUCTURAL_POSITIONAL` classification + lossless encode/decode). |
| MemoryArena: no memory-unit layer, no gold-evidence-ID field at all (confirmed by full scan) | DATASET LIMITATION for identity/evidence metrics specifically | Correctly `NOT_ATTEMPTABLE` for Recall@K/Strict TSR/evidence precision-recall-coverage — no fabrication attempted. |
| MemoryArena: interdependent multi-session task chains with no existing metric anywhere in the suite | FRAMEWORK LIMITATION | MemoryArena's *own* H.1 profile names `agentic_task_memory` as its single most load-bearing, genuinely new capability, and its `mambench_compatibility.json` explicitly states no dedicated metric exists for it. The chain/subtask structure (`chain_length`, `subtask_index`, `source_task_id`) is itself genuinely source-provided — nothing here is invented, only a diagnostic framing for structure that already exists. → **Extension 3** (`agentic_memory.py`). |
| MemoryArena: `answers[i]` is `dict`/`list`/`str` depending on config | FRAMEWORK LIMITATION | `evaluate_answer_correctness`'s `.strip()` call assumes `str`; calling it on a `dict`/`list` raises `AttributeError`. The underlying answer is genuinely structured, not a string the canonical function was ever designed to accept. → **Extension 2b** (`answer_matching.evaluate_structural_answer_correctness`). |
| MemBench: no full raw corpus persisted in the committed candidate directory (H.1 disclosed limitation) | DATASET-GOVERNANCE / REPRODUCIBILITY ISSUE, not a framework gap | Out of scope for a framework-extension stage — noted here only so it isn't silently forgotten; H.2 (activation decision) should require resolving this before any activation of MemBench. |
| All three candidates: no dataset-adapter interface spanning three structurally different record shapes | FRAMEWORK LIMITATION | `phase3/evaluation/integration/dataset_adapter.py` (H) exists only for the four active datasets, built around the frozen active-dataset profile vocabulary. There was no common, typed, read-only accessor shape for the candidates. → **Extension 2 (interface)** (`extensions/adapters/base.py::DatasetAdapter`). |

## 2. Extensions implemented

### Extension 1 — Evidence-basis abstraction (`evidence_basis.py`)

**Why needed:** see gap analysis row 3 above. **Which dataset requires it:** MemBench
primarily (structural-positional evidence); the vocabulary is completed for the other
candidates too so the classification is total, not partial. **Research question it answers:**
"what *kind* of evidence pointer does a gold-evidence field actually denote, and is it safe to
feed to existing identity-based metrics unmodified?" **Why existing metrics can't answer it:**
they have no concept of evidence *kind* at all — a bare `Sequence[str]` carries no metadata
about whether the strings are source-stable ids or derived positional encodings.
**Coexistence:** total — this module never touches `phase3/evaluation/metrics/*.py`; it only
classifies and (for the positional case) deterministically, losslessly encodes/decodes a
pointer into a plain string the existing metrics already know how to consume.
**New ambiguity introduced:** callers must not conflate an encoded positional string with a
genuine source-native id when interpreting results — documented prominently in the module and
enforced by `is_id_sequence_compatible()`'s explicit vocabulary. **Classification:**
**NEW PROVISIONAL** (no contract document defines this vocabulary).

Five-way vocabulary: `EXPLICIT_ID_EVIDENCE` (already supported, named for completeness),
`STRUCTURAL_POSITIONAL_EVIDENCE` (new, MemBench), `BEHAVIORAL_EVIDENCE` (named here, realized
in Extension 3), `RELATIONAL_EVIDENCE` (already supported via 3.2-D equivalence/provenance,
named for completeness), `NONE_AVAILABLE_EVIDENCE` (MemoryAgentBench, MemoryArena).

Mathematical definition of the encoding: `encode(session_index, turn_index) =
"S{session_index}_T{turn_index}"`, a total, injective, deterministic function on
non-negative integer pairs; `decode` is its exact inverse; `round_trips_losslessly` is the
checked property `decode(encode(x)) == x` for every `x` in a caller-supplied pair sequence.

### Extension 2 — `DatasetAdapter` interface + three concrete adapters (`adapters/`)

**Why needed:** see gap analysis row 7. **Which datasets:** all three candidates.
**Research question:** "can each candidate's H.1-normalized data be accessed through one
uniform, typed, never-fabricating shape, so a future H.2 activation decision (and this
stage's own tests) have a concrete interface to evaluate against?" **Why existing code can't
answer it:** `integration/dataset_adapter.py` is built around the *active*-dataset profile
vocabulary and the frozen active-dataset schemas; the candidates are not going through
activation in this stage, so reusing that exact path would be premature (it would imply
activation-readiness this stage explicitly does not decide). **Coexistence:** total — this is
a new, separate interface; nothing in `integration/` is touched. **New ambiguity:** none — the
interface is deliberately minimal (seven methods, each returning an `AdapterField` with an
explicit availability status reused verbatim from `datasets.capability.CAPABILITY_STATES`).
**Classification:** **NEW PROVISIONAL**.

Every accessor method returns `AdapterField(value, availability, source_field, note)`. A
missing capability is `AdapterField(value=None, availability=CAPABILITY_NOT_PROVIDED_BY_SOURCE,
...)`, never a silent `0`/`False`/`[]`. `capability_profile()` is a read-only passthrough of
each candidate's already-computed H.1 profile JSON — this stage never recomputes or overrides
an H.1 finding.

### Extension 2a/2b — Additive answer-correctness generalizations (`answer_matching.py`)

**Why needed:** see gap analysis rows 2 and 6. **Non-redefinition proof (both functions):**
for the degenerate single-string / all-string-typed case respectively, each new function is
required (and tested) to produce bit-identical status/value output to the canonical
`agent.outcomes.evaluate_answer_correctness` on every shared fixture — they are strict
generalizations, never divergent reimplementations. **Classification:** **NEW PROVISIONAL**
(no contract document defines multi-reference or structural answer matching; both remain,
like the canonical function, deterministic exact-match diagnostics — no fuzzy/semantic
comparison of any kind).

Mathematical definitions:
```
evaluate_answer_correctness_multi_reference(result, candidates) =
    UNDEFINED   if result.execution_status != SUCCESS
    UNDEFINED   if candidates is None or empty
    UNDEFINED   if result.answer is None
    CORRECT     if exists c in candidates: result.answer.strip() == c.strip()
    INCORRECT   otherwise

evaluate_structural_answer_correctness(result, expected) =
    UNDEFINED   if result.execution_status != SUCCESS
    UNDEFINED   if expected is None
    UNDEFINED   if result.answer is None
    CORRECT     if normalize(result.answer) == normalize(expected)     [structural ==, order-sensitive for lists]
    INCORRECT   otherwise
  where normalize(v) = v.strip() if isinstance(v, str) else v
```

### Extension 3 — Agentic/chain memory diagnostics (`agentic_memory.py`)

**Why needed:** see gap analysis row 5 (the single largest genuinely-new capability
identified in H.1). **Which dataset:** MemoryArena, exclusively. **Research question:** "in an
interdependent multi-session task chain with no gold-memory-ID layer, can we still
distinguish (a) whether prior-subtask content was *structurally available*, (b) whether it
was *used*, and (c) whether it *changed the observed outcome* — without ever claiming it
*caused* the outcome, and without inventing a memory-ID scheme the source doesn't have?"
**Why existing metrics can't answer it:** every identity-based metric (Strict TSR, Recall@K,
evidence precision/recall) requires a `gold_evidence_ids`-shaped input that structurally
cannot exist for MemoryArena — this is not a coverage gap in an existing metric, it is a
different question that needs a different (already-existing, reused) diagnostic shape.
**Coexistence:** maximal reuse, zero reimplementation — see below.
**Classification:** **NEW PROVISIONAL** for the structural `MEMORY_AVAILABLE` classification
and the chain/adapter conventions; **INHERITED CANONICAL/PROVISIONAL** (unchanged) for
`MEMORY_USED` and `MEMORY_CONTRIBUTED`, since those re-export existing 3.2-E functions
verbatim.

The four-way distinction, exactly as the task brief requires, never conflated:

- **MEMORY_AVAILABLE** (NEW): a purely structural fact — `subtask_index > 0` within its
  chain. `classify_chain_memory_availability()`. Grounded directly in H.1-confirmed-available
  fields (`chain_length`/`subtask_index`); nothing invented.
- **MEMORY_USED**: re-export of `agent.diagnostics.classify_retrieval_utilization` — **zero
  new logic**, imported and aliased as `classify_chain_memory_usage`.
- **MEMORY_CONTRIBUTED**: re-export of `agent.paired.classify_memory_contribution` — **zero
  new logic**, imported and aliased as `classify_chain_memory_contribution`, including its
  existing `PairedComparisonIdentityError` identity-preservation discipline (same task,
  same expected answer, same condition-pairing rules) applied completely unmodified.
- **MEMORY_CAUSED**: **deliberately, explicitly NOT implemented anywhere in this framework.**
  A genuine causal claim requires an intervention design beyond a single paired observation
  (e.g. repeated sampling under controlled reasoning-layer noise) — squarely out of scope for
  a deterministic-diagnostics framework-extension stage. This is a permanent, not merely
  temporary, exclusion from this stage's scope; any future causal-language work must be
  designed as its own separate effort with its own experimental controls.

## 3. Extensions explicitly rejected

1. **A new schema-canonical `AGENTIC_TASK_CHAIN` evidence type + new gold-evidence-ID scheme
   for MemoryArena.** Rejected: MemoryArena genuinely has no per-memory-unit identity in the
   source (confirmed absent by full scan) — inventing one would fabricate ground truth,
   which every stage of this project's absolute rules forbids.
2. **A new PROVISIONAL condition (e.g. `PRIOR_SUBTASK_CONTEXT_AVAILABLE`) in
   `agent/conditions.py`.** Rejected: the existing provisional condition
   `CONDITION_SELECTED_MEMORY_AVAILABLE` ("agent-visible context contains task plus some
   selected memory content, without asserting the full retrieval+selection pipeline") is
   already a semantically exact fit for "the agent is given a prior subtask's Q&A as its
   selected memory for a later subtask." Per 3.2-E's own rule ("only add a new condition if
   the existing ones genuinely can't represent it"), no new condition constant was added —
   `agentic_memory.py` reuses `CONDITION_SELECTED_MEMORY_AVAILABLE` and
   `agent.conditions.build_agent_visible_context` verbatim.
3. **A MemoryArena-specific reimplementation of paired-comparison / memory-contribution
   logic.** Rejected: `agent.paired.classify_memory_contribution` and
   `agent.paired.paired_condition_comparison` operate entirely on `AgentExecutionResult` +
   `expected_answer` and have no opinion about what "memory" substantively means — they are
   reused verbatim; this stage supplies only the MemoryArena-specific data-shaping (which
   subtask counts as a chain's "memory item"), not a competing comparison algorithm.
4. **Semantic/embedding-based content evidence matching for MemBench/MemoryAgentBench, in
   lieu of deterministic ID/positional matching.** Rejected at the design level, per the task
   brief's absolute rule: deterministic lexical/exact/span-level evidence was sufficient for
   every case actually found in H.1 (MemBench's positional pairs are exact structural data,
   not fuzzy text); no semantic model was integrated or even stubbed in.
5. **Forcing all three candidates through the exact same evidence/answer/condition pathway
   ("harmonizing" them into one shape).** Rejected throughout — MemoryAgentBench keeps its
   multi-reference-string answer shape, MemBench keeps its positional-evidence shape,
   MemoryArena keeps its structural chain shape natively; only the classification vocabulary
   (`EvidenceBasisDeclaration`, `AdapterField`) is shared, never the underlying data
   representation.
6. **A single combined "memory quality" or "framework-extension coverage" score.** Never
   considered a viable design — every new construct here is a structural classification or a
   deterministic exact-match/equality check, never a blended/aggregate metric, consistent
   with every prior Phase 3.2 stage's explicit prohibition on inventing new benchmark scores.

## 4. Compatibility with existing metrics — explicit non-redefinition statement

No file under `phase3/evaluation/metrics/`, `phase3/evaluation/agent/`,
`phase3/evaluation/security/`, `phase3/evaluation/contracts/`, `phase3/evaluation/datasets/`,
or `phase3/evaluation/integration/` was modified by this stage. `git diff --stat` against
every one of them is empty (verified as part of validation below). Strict TSR remains exactly
`selected_memory_ids ∩ gold_evidence_ids ≠ ∅` — this stage does not call, wrap, or reinterpret
`strict_tsr()` at all; MemBench's positional evidence is made *compatible with* Strict TSR
(via the Extension 1 encoding) without Strict TSR's own definition changing by one character.

## 5. Evaluator/agent visibility boundary for every new construct

- `evidence_basis.py`: pure classification/encoding functions over already-known evidence
  values — no agent-visible/evaluator-only distinction applies (it operates purely on the
  evaluator side, on values that are, by construction, never passed to an agent).
- `answer_matching.py`: both functions consume `expected_answer`/`expected_answers` (always
  evaluator-only, per the same discipline as the canonical function they generalize) and an
  `AgentExecutionResult` (agent-visible-derived) — identical visibility shape to
  `agent.outcomes.evaluate_answer_correctness`, since neither new function accepts any
  additional evaluator-only parameter type the canonical function didn't already have.
- `agentic_memory.py`: `build_chain_agent_visible_context()` is a thin wrapper over
  `agent.conditions.build_agent_visible_context`, which itself calls
  `boundary.validate_agent_visible()` before returning — inherited, not reimplemented. Gold
  answers/evidence are never passed into this function; only prior-subtask question+answer
  content (itself agent-visible per the `CONDITION_SELECTED_MEMORY_AVAILABLE` semantics) is
  exposed.
- `adapters/base.py` + concrete adapters: `answer()` and `relationships()` are explicitly
  documented as evaluator-only accessors; `native_task()`/`native_memory()`/
  `session_structure()` are agent-visible-shaped. No adapter method mixes the two planes in
  one return value.

## 6. Reproducibility

Every new function in this stage is a pure, deterministic function of its inputs: no
filesystem access inside classification/encoding logic (only the explicit, documented
`load_*` helpers in each adapter module read files, and only from
`phase3/datasets/candidates/<id>/{normalized,profile}/`), no network, no LLM/embeddings, no
randomness. `encode_positional_evidence_id`/`decode_positional_evidence_id` round-trip
losslessly by construction (proven by `round_trips_losslessly()` and its dedicated test).

## 7. Provisional vs. canonical — full list

| Decision | Classification |
|---|---|
| `EvidenceBasisDeclaration` five-way vocabulary | NEW PROVISIONAL |
| Positional evidence encoding format (`"S{n}_T{m}"`) | NEW PROVISIONAL |
| `DatasetAdapter` interface shape (7 methods) | NEW PROVISIONAL |
| `AdapterField` envelope | NEW PROVISIONAL |
| `evaluate_answer_correctness_multi_reference` | NEW PROVISIONAL |
| `evaluate_structural_answer_correctness` | NEW PROVISIONAL |
| `classify_chain_memory_availability` / `MEMORY_AVAILABLE` vocabulary | NEW PROVISIONAL |
| Re-exported `classify_chain_memory_usage` (= `classify_retrieval_utilization`) | INHERITED, same classification as the original (3.2-E PROVISIONAL) |
| Re-exported `classify_chain_memory_contribution` (= `classify_memory_contribution`) | INHERITED, same classification as the original (3.2-E DIAGNOSTIC ONLY) |
| Reuse of `CONDITION_SELECTED_MEMORY_AVAILABLE` for chain data | INHERITED PROVISIONAL (unchanged from 3.2-E) |
| Strict TSR, Recall@K, MRR, evidence precision/recall/coverage, equivalence/provenance diagnostics | INHERITED CANONICAL/PROVISIONAL per their own 3.2-C/D classification, entirely unchanged |
| `MEMORY_CAUSED` | **NOT IMPLEMENTED** — no classification applies; explicitly out of scope |

## 8. Known limitations

- MemBench's full raw corpus is not persisted in the committed candidate directory (an H.1
  disclosed limitation, not something this stage fixes or hides) — any future activation
  decision for MemBench should require resolving this first.
- The positional-evidence encoding (`"S{n}_T{m}"`) is one defensible convention, not the only
  possible one; it is documented as provisional precisely so a future stage can replace it if
  a better convention emerges, without that being treated as backward-incompatible breakage
  of a frozen contract.
- `agentic_memory.py`'s chain/subtask adapter conventions (e.g.
  `prior_subtask_memory_id()`'s `"{chain_id}:subtask:{n}"` format) are this stage's own
  invented adapter-level identifiers, explicitly documented as NOT source-native memory ids —
  they exist only to let existing agent-visible-context-building machinery accept
  chain-derived content, never claimed as a benchmark ground-truth identity.
- No metric coverage exists (nor is any proposed) for MemBench's `noise`/`knowledge_update`
  temporal-conflict categories beyond what 3.2-D's existing equivalence/provenance machinery
  already offers — if MemBench is activated in a future stage, this may need a dedicated
  follow-up gap analysis of its own, out of scope here.

## 9. Phase 4 compatibility notes

The evidence-basis and adapter abstractions are additive classification/accessor layers over
data, not new trust boundaries — a future Phase 4 memory-poisoning study could attach an
"attack label" as a new evaluator-only field on top of any `AdapterField`/normalized record
without this stage's code needing to change, since nothing here assumes evidence/memory
content is trustworthy or untampered. The chain/subtask structure `agentic_memory.py` exposes
(prior-subtask content flowing into a later subtask) is exactly the kind of propagation path
a future poisoning study would want to instrument — this stage does not build that
instrumentation, but the `MEMORY_AVAILABLE`/`MEMORY_USED`/`MEMORY_CONTRIBUTED` distinction it
establishes is a prerequisite for asking "did a poisoned prior-subtask memory item get used,
and did it change the outcome" without conflating "used" with "contributed" the way a
poisoning study would need to keep separate.

## 10. Future LLM / Phase 3.3 integration boundary

A future model-integration stage will call `agent.outcomes.run_synthetic_agent`'s real-agent
successor with an `AgentVisibleContext` built by `agentic_memory.build_chain_agent_visible_context`
(or a future real-adapter equivalent) and will need to supply `AgentExecutionResult` objects
compatible with `evaluate_answer_correctness_multi_reference`/`evaluate_structural_answer_correctness`
for MemoryAgentBench/MemoryArena-shaped tasks respectively. No model dependency exists in this
stage's code; the interfaces are designed so a real agent's output can be dropped in without
any of this stage's classification/comparison logic changing.
