# Phase 3.1 — Clean Agent Foundation Specification

Status: **CANONICAL SPECIFICATION FOR PHASE 3.1**. This document is the top-level reference;
where a topic has its own contract or schema document, this document summarizes the decision
and links out rather than duplicating the full text. If this document and a linked
contract/schema ever appear to disagree, the linked contract/schema is authoritative for its
own domain and this document should be corrected to match.

This is a **specification and architecture-definition document only**. No retrieval,
reranking, selection, memory-creation, Qwen integration, or attack/defense code is implemented
as part of Phase 3.1.

---

## 1. Problem statement

MAMBench (Memory and Agent Manipulation Benchmark) is a scientifically defensible benchmark
for memory/agent manipulation and poisoning research. Before Phase 4 introduces attacks
(AgentPoison, MINJA, DSRM, MemoryGraft), Phase 3 must establish a trustworthy clean baseline,
so that the central scientific question is answerable:

> Did memory manipulation change agent behavior?

rather than the confounded question:

> Was the agent already behaving incorrectly before the attack?

This requires two traceability chains — the task-execution pipeline and the per-memory
history — both defined fully in
[../contracts/TRACEABILITY_CONTRACT.md](../contracts/TRACEABILITY_CONTRACT.md):

```
Task → Memory state → Candidate discovery → Reranking → Evidence selection
     → Reasoning context → Qwen3-8B → Answer/decision → Evaluation

Memory → Source → Parents → Derivation → Lifecycle → Retrieval → Selection
       → Reasoning influence
```

## 2. Phase 1–2 invariants

Phase 1 and Phase 2 are frozen. Phase 3 reads the frozen substrate; it does not rebuild it.
The complete boundary — what is frozen, what is historical-only, what is new — is defined in
[PHASE3_RESTART_BOUNDARY.md](PHASE3_RESTART_BOUNDARY.md) and is incorporated here by
reference. Nothing in this specification overrides that boundary.

## 3. Historical Phase 3 lessons incorporated

The previous Phase 3 attempt (now archived at `phase3_reference/`, historical-only per
[PHASE3_RESTART_BOUNDARY.md](PHASE3_RESTART_BOUNDARY.md)) produced concrete findings this
specification is built around:

- **TSR was too narrow** — strict TSR (literal gold-evidence-ID membership) was implicitly
  treated as complete agent success. Resolved by the two-layer evaluation model in
  [../contracts/EVALUATION_CONTRACT.md](../contracts/EVALUATION_CONTRACT.md).
- **Candidate generation was the dominant failure** — historical root-cause analysis found
  ~72.4% candidate-generation failures, ~14.8% selection-capacity failures, ~12.8%
  identity/evaluation artifacts. Resolved by explicitly separating candidate discovery,
  reranking, and selection as distinct layers (section 15 below;
  [../contracts/CLEAN_AGENT_INTERFACES.md](../contracts/CLEAN_AGENT_INTERFACES.md)) and by
  requiring these failure modes be measured separately (evaluation contract section 2).
- **Derived memory competition was real, but derived memory is not inherently bad** — resolved
  by representing derived memory explicitly rather than suppressing it (section 7 below;
  [../schemas/memory_schema.md](../schemas/memory_schema.md) section 3.2).
- **Giant lineage-family abstraction is rejected** — resolved by requiring explicit pairwise
  parent/derivation edges only (section 9 below;
  [../schemas/relationship_schema.md](../schemas/relationship_schema.md) section 2.1).
- **Semantic-only retrieval is not accepted as the final replacement for lexical retrieval** —
  both channels recovered genuine misses the other didn't; neither is assumed final (section
  16 below).
- **Isolated gains do not imply compositional validity** — resolved by mandatory
  isolation+composition testing before any mechanism is accepted
  ([EXPERIMENT_GOVERNANCE.md](EXPERIMENT_GOVERNANCE.md) section 3).
- **LLM reasoning must be first-class** — the old Phase 3 lacked an answer-generation stage;
  this specification introduces Qwen3-8B as a separable reasoning layer from the start
  (section 20 below).

## 4. Complete limitations ledger — frozen vs. experimental vs. diagnostic vs. future

This is the authoritative classification. Every design element in this specification and its
linked documents falls into exactly one of these categories:

**Frozen design decisions:**
- Layer separation (candidate discovery / reranking / selection / reasoning) —
  [../contracts/CLEAN_AGENT_INTERFACES.md](../contracts/CLEAN_AGENT_INTERFACES.md).
- Memory ontology (foundation/derived/equivalent/duplicate, identity immutability) —
  [../schemas/memory_schema.md](../schemas/memory_schema.md).
- Relationship/event types — [../schemas/relationship_schema.md](../schemas/relationship_schema.md).
- Lifecycle state model (`CREATED → ACTIVE → RETIRED`, reuse as event not state) — section 12.
- Qwen3-8B information-visibility rules (what it may/must not receive) —
  [../contracts/CLEAN_AGENT_INTERFACES.md](../contracts/CLEAN_AGENT_INTERFACES.md) section 2,
  [../contracts/LEAKAGE_AND_VISIBILITY_CONTRACT.md](../contracts/LEAKAGE_AND_VISIBILITY_CONTRACT.md).
- Two-layer evaluation model and the A/B/C control methodology —
  [../contracts/EVALUATION_CONTRACT.md](../contracts/EVALUATION_CONTRACT.md).
- The four-dataset set and their assigned roles —
  [DATASET_CAPABILITY_MATRIX.md](DATASET_CAPABILITY_MATRIX.md).
- Traceability requirements — [../contracts/TRACEABILITY_CONTRACT.md](../contracts/TRACEABILITY_CONTRACT.md).
- Experiment governance process — [EXPERIMENT_GOVERNANCE.md](EXPERIMENT_GOVERNANCE.md).
- Freeze gate conditions — [PHASE3_FREEZE_GATE.md](PHASE3_FREEZE_GATE.md).
- Phase 4 interface requirements — [PHASE4_INTERFACE_REQUIREMENTS.md](PHASE4_INTERFACE_REQUIREMENTS.md).

**Candidate hypotheses requiring experimentation (NOT frozen):**
- Exact top-K values at any stage.
- Exact retrieval weights and lexical/semantic fusion formula.
- Exact embedding model choice.
- Exact reranking formula.
- Exact memory-creation novelty/duplicate thresholds.
- Exact semantic-equivalence thresholds.
- Exact evidence-selection budget.
- Exact Qwen prompt wording.
- Exact token/context budget.
- Whether/how foundation vs. derived memory should be weighted differently in ranking (see
  section 16 — explicitly not "always prefer foundation" nor "always reject derived").

**Diagnostic-only mechanisms (informative, not adopted as architecture):**
- Any root-cause or capacity-failure analysis technique used to characterize the system (e.g.
  the historical candidate-generation-failure breakdown) informs measurement but is not itself
  part of the agent's runtime behavior.

**Future decisions (explicitly out of scope for 3.1):**
- The exact memory-creation policy algorithm (section 11).
- Whether a workload/task layer is ever added for MSC or Conversation Chronicles
  ([DATASET_CAPABILITY_MATRIX.md](DATASET_CAPABILITY_MATRIX.md) section 4).
- Any Phase 4 attack or defense implementation.

## 5. Memory ontology

Summary; full definitions in [../schemas/memory_schema.md](../schemas/memory_schema.md).
Every memory has an immutable identity. Memories are typed `foundation` (from the frozen
Phase 2 substrate, or a future legitimate-observation policy) or `derived` (produced from one
or more existing memories via a logged creation event). Equivalent memories and duplicates are
distinct concepts from identity — see sections 6–8.

## 6. Foundation memory model

A foundation memory's provenance is the Phase 2 Unified Memory Record itself; it has no
parents. See [../schemas/memory_schema.md](../schemas/memory_schema.md) section 3.1.

## 7. Derived memory model

A derived memory is produced from one or more parents via an explicit, logged creation event
(`A + B → C`). Derived memory is not inherently penalized or preferred — see section 16 for
how this interacts with retrieval, and
[../schemas/memory_schema.md](../schemas/memory_schema.md) section 3.2 for the full model.

## 8. Equivalent memory model

A distinct memory identity that conveys materially equivalent information to another,
represented via an explicit `equivalent_to` relationship — never collapsed into one identity.
See [../schemas/memory_schema.md](../schemas/memory_schema.md) section 3.3 and
[../schemas/relationship_schema.md](../schemas/relationship_schema.md) section 2.

## 9. Duplicate model

A memory adding no meaningful new information; normally rejected at creation time by the
(not-yet-frozen) creation policy rather than merged after the fact. See
[../schemas/memory_schema.md](../schemas/memory_schema.md) section 3.4.

## 10. Memory creation semantics

A creation decision must consider novelty, duplication, semantic equivalence, information
value, provenance availability, source validity, and lifecycle implications. A legitimate
observation may become a foundation memory through the (future) creation policy; a derived
interpretation persisted from existing memories/observations becomes a derived memory.
Temporary reasoning context is **not** automatically persistent memory — only an explicit
creation event produces a new memory record. The exact creation policy algorithm is an
experimental decision for a later Phase 3 stage, not frozen during 3.1 (see section 4).

## 11. Provenance model

Every memory carries a `source` pointer (to the Phase 2 UMR record for foundation memories, or
to a derivation event for derived memories) and, for derived memories, an explicit
`parent_ids` list. Full field definitions:
[../schemas/memory_schema.json](../schemas/memory_schema.json). Full provenance/traceability
requirements: [../contracts/TRACEABILITY_CONTRACT.md](../contracts/TRACEABILITY_CONTRACT.md).

## 12. Lineage model

Ancestor/descendant relationships are computed by transitively walking explicit `parent_ids`
edges at query time — never precomputed into a merged "lineage family." This directly
addresses the historical giant-family-abstraction failure (section 3). Full model:
[../schemas/relationship_schema.md](../schemas/relationship_schema.md) section 2.1.

## 13. Lifecycle model

Canonical states: `CREATED → ACTIVE → RETIRED`. Reuse (retrieval, selection, usage) is
modeled as a logged **event**, not a state. Every transition must be traceable to its source
event, timestamp, component/actor, reason, previous state, and new state. Retired memories are
never deleted. Full event log definition:
[../schemas/relationship_schema.md](../schemas/relationship_schema.md) section 3.

## 14. Conflict model

Conflicting memories are preserved via an explicit `conflicts_with` relationship — never
silently overwritten. Legitimate supersession is represented via `superseded_by`, retiring the
superseded memory without deleting it. See
[../schemas/memory_schema.md](../schemas/memory_schema.md) section 6.

## 15. Retrieval architecture

```
TASK
 ↓
Lexical candidate discovery + Semantic candidate discovery
 ↓
Candidate union
 ↓
Duplicate/equivalence handling
 ↓
Provenance-aware processing
 ↓
Deterministic reranking
 ↓
Evidence selection
 ↓
Compact reasoning context
 ↓
Qwen3-8B
```

Three layers are explicitly distinguished and must not collapse into one another:

- **Candidate discovery** — "could this memory be relevant?" (wide net, not required to be
  precise).
- **Reranking** — "how relevant is this candidate?" (scores/orders; does not decide final
  membership).
- **Evidence selection** — "which evidence should actually be passed to reasoning?" (applies
  budget, redundancy, and independence considerations).
- **Reasoning** — "what should the agent conclude/do?" (never re-implements the above).

No specific top-K value (top-10/50/100/200 or otherwise) is hard-coded as final architecture
at any stage — all are experimental parameters (section 4). Full interface contract:
[../contracts/CLEAN_AGENT_INTERFACES.md](../contracts/CLEAN_AGENT_INTERFACES.md) section 1.

## 16. Lexical/semantic strategy

Historical evidence: semantic-only retrieval regressed important metrics but recovered genuine
lexical misses. Lexical and semantic retrieval are therefore treated as **potentially
complementary channels**, both feeding the same candidate-union step above. The final fusion
formula and relative weighting are explicitly experimental (section 4) — this specification
does not assume the final retrieval architecture before experimentation.

## 17. Candidate discovery vs reranking vs selection

See section 15. This distinction is load-bearing for the historical root-cause finding
(section 3) that ~72.4% of failures were candidate-generation failures — a fact that is only
diagnosable if these layers are measured separately, which the evaluation contract requires
(section 2 there).

## 18. Evidence selection

The layer that converts a reranked candidate set into the actual reasoning context, applying
budget and independence considerations. Independence (whether multiple selected memories
represent genuinely separate corroboration vs. restatements of the same fact via
`equivalent_to` or shared ancestry) is evaluated here, not baked into memory identity — see
section 5 and [../schemas/memory_schema.md](../schemas/memory_schema.md) section 4.

## 19. Reasoning-layer architecture

The reasoning layer is implemented and configured independently of the memory implementation
(swapping one must not require changing the other). Full contract:
[../contracts/CLEAN_AGENT_INTERFACES.md](../contracts/CLEAN_AGENT_INTERFACES.md) section 1.

## 20. Qwen3-8B interface

Qwen3-8B is the current candidate reasoning model, pinned by weight hash, prompt version, and
decoding configuration; isolated from the memory implementation; and bound by strict
information-visibility rules (may receive: system instructions, task, selected memory context,
legitimate observations; must never receive: gold answers, gold evidence IDs, evaluation
labels, hidden benchmark metadata, internal scores/ranks, attack labels). Full contract:
[../contracts/CLEAN_AGENT_INTERFACES.md](../contracts/CLEAN_AGENT_INTERFACES.md) section 2;
leakage enforcement detail:
[../contracts/LEAKAGE_AND_VISIBILITY_CONTRACT.md](../contracts/LEAKAGE_AND_VISIBILITY_CONTRACT.md).

## 21. Memory-level metrics

Full list in [../contracts/EVALUATION_CONTRACT.md](../contracts/EVALUATION_CONTRACT.md)
section 2: Recall@{1,5,10,20,50,100,200}, MRR, evidence precision/recall/coverage, selected-
and irrelevant-memory counts, redundancy, candidate-generation vs. selection-capacity failure
counters (kept separate per the historical root-cause finding), creation/rejection/duplicate/
semantic-equivalence/reuse rates, foundation-vs-derived usage, derivation depth, provenance
completeness, lineage correctness, lifecycle validity, orphan rate, invalid-transition rate.

## 22. Agent-level metrics

Three controlled conditions (A: no-memory, B: gold-evidence, C: retrieved-memory), same
model/prompt/decoding/task set, with `memory contribution = accuracy(C) - accuracy(A)` and
`gold memory contribution = accuracy(B) - accuracy(A)`. Full definition:
[../contracts/EVALUATION_CONTRACT.md](../contracts/EVALUATION_CONTRACT.md) section 5.

## 23. Dataset capability matrix

LoCoMo and LongMemEval as primary QA/reasoning evaluation datasets; MSC and Conversation
Chronicles as lifecycle/provenance/reuse validation datasets, not forced into the TSR
framework without a legitimate workload layer. No dataset additions/removals in 3.1. Full
matrix: [DATASET_CAPABILITY_MATRIX.md](DATASET_CAPABILITY_MATRIX.md).

## 24. Leakage model

Two information planes (agent-visible / agent-hidden), with an explicit standing audit
requirement that `data/metadata/` and `data/reports/` never enter the reasoning-context
assembly path. Full contract:
[../contracts/LEAKAGE_AND_VISIBILITY_CONTRACT.md](../contracts/LEAKAGE_AND_VISIBILITY_CONTRACT.md).

## 25. Determinism/reproducibility model

Memory identity, storage, provenance, lifecycle, lexical retrieval, deterministic reranking,
trace generation, and evaluation bookkeeping are expected deterministic; Qwen3-8B reasoning is
the primary controlled-stochastic component, with variance measured and reported rather than
assumed away. Full contract:
[../contracts/REPRODUCIBILITY_CONTRACT.md](../contracts/REPRODUCIBILITY_CONTRACT.md).

## 26. Traceability model

Task-execution trace and memory-history trace, joinable by `task_id`/`memory_id`/`event_id`,
sufficient to support Phase 4 attack-origin reconstruction in reverse. Full contract:
[../contracts/TRACEABILITY_CONTRACT.md](../contracts/TRACEABILITY_CONTRACT.md).

## 27. Experiment strategy

Every future experiment specifies hypothesis, baseline, independent/dependent variables,
dataset/subset, expected result, failure criterion, composition test, and one of
`ACCEPT|REJECT|DIAGNOSTIC ONLY|REQUIRES FOLLOW-UP`. Negative results preserved, never hidden.
Full process: [EXPERIMENT_GOVERNANCE.md](EXPERIMENT_GOVERNANCE.md).

## 28. Freeze gate

Twenty conditions spanning integrity, schema stability, characterization, leakage, metrics,
composition testing, and Phase 4 readiness must all pass before `FREEZE`. Full gate:
[PHASE3_FREEZE_GATE.md](PHASE3_FREEZE_GATE.md).

## 29. Phase 4 readiness

The clean agent must support attack-entry analysis, attack-origin attribution, lineage
reconstruction, propagation analysis, retrieval/selection/reasoning influence analysis, and
decision-change attribution, while allowing memory manipulation with the reasoning layer held
fixed. Full requirements:
[PHASE4_INTERFACE_REQUIREMENTS.md](PHASE4_INTERFACE_REQUIREMENTS.md).

## 30. Unresolved assumptions / constraints

- The exact memory-creation policy, retrieval fusion formula, reranking formula, selection
  budget, semantic-equivalence threshold, embedding model, and Qwen prompt details are all
  unresolved by design (section 4) and will be resolved through
  [EXPERIMENT_GOVERNANCE.md](EXPERIMENT_GOVERNANCE.md)-governed experimentation in later
  Phase 3 stages.
- Whether MSC/Conversation Chronicles ever receive a task/workload layer is unresolved and
  deferred to a future capability-gap analysis.
- The physical storage/indexing mechanism for traceability data is unresolved and deferred to
  implementation.
- The exact statistical treatment of Qwen3-8B variance (trial count, confidence intervals) is
  unresolved and deferred to freeze-gate time.

## Cross-references

This document is the entry point; it intentionally does not duplicate the full text of the
schemas and contracts it summarizes. See [../README.md](../README.md) for the full directory
map and current Phase 3 status.
