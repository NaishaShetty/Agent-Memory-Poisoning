# Phase 3.2-H.3 (second stage) — Memory Foundation Integration Architecture

This document is a **sibling** to `PHASE3_2_H3_FRAMEWORK_EXTENSION_SPEC.md` (the first
H.3 stage: evidence-basis abstraction, dataset adapters, agentic memory diagnostics, all
under `phase3/evaluation/extensions/`). It does **not** rewrite or duplicate that
document — it cross-references it explicitly throughout and covers only the
**second, purely additive** H.3 stage: building the architecture for evaluating
DATASET x MEMORY FOUNDATION x AGENT x EVALUATION x ATTACK as separate dimensions, under
the new `phase3/evaluation/foundations/` package.

## 1. Motivation

MAMBench currently evaluates dataset x agent x evaluation x attack. It has no concept of
the underlying *memory foundation* (Mem0, Letta, Graphiti, A-MEM) an agent's memory might
actually be built on. Real deployments increasingly build agent memory on top of one of
these libraries, each with genuinely different architecture (flat scored records vs.
core/archival memory blocks vs. a temporal knowledge graph vs. dynamically-linked,
self-evolving notes). Understanding how retrieval, persistence, updating, propagation,
manipulation, and poisoning impact differ *by foundation* — not just by dataset — is a
distinct research question this stage builds the scaffolding for, without answering it.

## 2. Existing H.3 work — explicit "this is unchanged" statement

`phase3/evaluation/extensions/{evidence_basis,answer_matching,agentic_memory}.py` and
`extensions/adapters/{base,membench_adapter,memoryagentbench_adapter,memoryarena_adapter}.py`
are **completely unmodified** by this stage. No file under `phase3/evaluation/extensions/`
was edited; this stage only added one new sibling file (this document) and one new,
separate package, `phase3/evaluation/foundations/`. `agentic_memory.py`'s
MEMORY_AVAILABLE/USED/CONTRIBUTED/CAUSED discipline is mirrored, not replaced, by
`foundations/lifecycle.py` (see section 7).

## 3. Foundation motivation and selection

Mem0, Letta, Graphiti, and A-MEM were named explicitly in the task brief as the four
foundations to audit. Graphiti (not "Zep") is treated as the canonical open-source
temporal-graph foundation per the brief's own instruction; this stage's fetch of
`help.getzep.com/graphiti/*` found no meaningful distinction from a separate "Zep" product
worth a separate entry. A-mem and A-mem-sys were audited **separately** (see section 4) —
they are confirmed, from both repos' own READMEs, to be genuinely different artifacts
(paper-reproduction vs. packaged system), not interchangeable.

## 4. Capability audit (summary — full detail and per-row citations in
`phase3/evaluation/foundations/capability_audit.py`)

27 capability dimensions (a literal count of the task brief's enumerated list; the brief
calls this "26" but a literal reading of "memory creation, storage, retrieval, update,
deletion, linking, graph, temporal state, session state, memory identifiers, metadata,
retrieval ordering, retrieval scores, lifecycle observability, traceability, state export,
resetability, isolation, configuration capture, agent integration, LLM dependency,
embedding dependency, external service dependency, local execution, determinism, attack
injection points, license/research-use considerations" yields 27) were classified
SUPPORTED / PARTIAL / NOT_SUPPORTED / NOT_APPLICABLE / UNKNOWN for each foundation,
grounded in actual WebFetch reads of:

- Mem0: `github.com/mem0ai/mem0` README, `docs.mem0.ai/open-source/python-quickstart`,
  `docs.mem0.ai/open-source/graph_memory/overview`.
- Letta: `github.com/letta-ai/letta` README only — `docs.letta.com/overview` and
  `docs.letta.com/concepts/memory` did not yield the requested detail
  (`concepts/memory` returned HTTP 404 at fetch time). Letta's audit rows are
  consequently mostly UNKNOWN/PARTIAL, honestly, rather than filled in from general
  training-data familiarity with Letta/MemGPT's published architecture.
- Graphiti: `help.getzep.com/graphiti/getting-started/welcome`,
  `help.getzep.com/graphiti/graphiti/overview`.
- A-MEM: `github.com/WujiangXu/A-mem` (paper-reproduction repo), `github.com/WujiangXu/A-mem-sys`
  (packaged-system repo), `arxiv.org/abs/2502.12110` (abstract).

**Key findings:**
- Mem0 OSS: graph memory (`linking`/`graph`) is `NOT_SUPPORTED` — the graph-memory
  migration guide states graph memory was **removed** from open-source Mem0 (~4000 lines
  of driver code deleted) and is now Mem0-Platform-only.
- Graphiti: `graph`/`temporal_state`/`linking` all `SUPPORTED` — bi-temporal edges with
  `valid_at`/`invalid_at` tracking are the framework's headline feature.
- A-MEM: `update` and `linking` both `SUPPORTED`, and genuinely distinctively so — "new
  memories can trigger updates to the contextual representations and attributes of
  EXISTING historical memories," a capability neither Mem0 nor Graphiti's audit rows claim.
- A-mem vs. A-mem-sys: confirmed NOT interchangeable. `A-mem`'s own README states it "is
  specifically designed to reproduce results presented in our paper" and points to
  `A-mem-sys` for actual agent-building use; `A-mem-sys` documents concrete implementation
  choices (ChromaDB, `all-MiniLM-L6-v2`, OpenAI/Ollama/SGLang/OpenRouter LLM backends) that
  `A-mem`'s README does not commit to.

## 5. Architecture

`phase3/evaluation/foundations/` (new package):

```
adapter.py             MemoryFoundationAdapter interface, FoundationField, FoundationIdentity
capability_audit.py    the grounded four-foundation audit (section 4)
lifecycle.py           7-stage lifecycle vocabulary (section 7)
trace.py               FoundationTraceArtifact (section 8)
fingerprinting.py      config/state fingerprint helpers (reuses security.reproducibility)
model_dependency.py    9-value model-dependency vocabulary, per-foundation declarations
security.py            boundary-check wrapper for foundation adapter calls
reset_isolation.py     A->B->A isolation check + REPRODUCIBILITY_LIMITATION (section 9)
registry.py            PREPARED_CANDIDATE registry for all four foundations
matrix.py              7 datasets x 5 foundations x 20 capabilities matrix (section 12)
mocks/                 MockMem0Adapter, MockLettaAdapter, MockGraphitiAdapter, MockAMemAdapter
```

## 6. Adapter contract

`MemoryFoundationAdapter` (abstract base, `adapter.py`) mirrors
`extensions/adapters/base.py::DatasetAdapter`'s never-fabricating discipline for a
genuinely different kind of thing: a *dataset* is read-only and has no lifecycle; a
*memory foundation* is stateful with real operations (`initialize`, `reset`, `add_memory`,
`retrieve`, `update_memory`, `delete_memory`, `inspect_memory`, `export_state`,
`normalize_trace`, `shutdown`). Every method returns `FoundationField`, never a bare
value. `FOUNDATION_FIELD_STATES` reuses `datasets.capability.CAPABILITY_STATES` verbatim
plus exactly one new value, `NOT_SUPPORTED_BY_ARCHITECTURE` (the foundation-level
analogue of `NOT_PROVIDED_BY_SOURCE`, which is dataset-record-specific by name). A
foundation's genuine "successfully did X, nothing more to report" semantic (e.g. Mem0
deleting a nonexistent id) is `FOUNDATION_AVAILABLE` with an explanatory note — never
conflated with `NOT_SUPPORTED_BY_ARCHITECTURE`. Tested explicitly in
`test_foundation_architecture_h3.py::TestUnsupportedOperationsNeverFabricate`.

## 7. Lifecycle model

Seven-stage vocabulary: `MEMORY_AVAILABLE -> MEMORY_RETRIEVED -> MEMORY_SELECTED ->
MEMORY_EXPOSED -> MEMORY_USED -> MEMORY_CONTRIBUTED -> (MEMORY_CAUSED, never
implemented)`. The last four stages **reuse, verbatim**, `agentic_memory.py`'s exact
discipline: `MEMORY_USED` = `agent.diagnostics.classify_retrieval_utilization`,
`MEMORY_CONTRIBUTED` = `agent.paired.classify_memory_contribution`, both re-exported
unchanged. `MEMORY_AVAILABLE`/`RETRIEVED`/`SELECTED`/`EXPOSED` are new, structural,
foundation-specific stages `agentic_memory.py` had no analogue for (MemoryArena's flat
chain data never needed a "retrieval call ran and returned candidates" concept). MEMORY_
CAUSED is a named constant excluded from `LIFECYCLE_STAGES` and from every function's
achievable return set — enforced by a dedicated test that builds a full-success scripted
scenario and asserts `MEMORY_CAUSED` still never appears.

## 8. Trace contract

`FoundationTraceArtifact` (`trace.py`) — a new, **separate, additive** dataclass, not an
extension of the existing (protected) `contracts/trace_artifact.schema.json`. Every
optional field (native scores, metadata, state/configuration fingerprints, lifecycle
state, attack-surface stage, errors, unsupported-operation markers) may be legitimately
absent; a `present: FrozenSet[str]` field records exactly which optional fields the
caller actually populated, so "absent because unsupported" is directly checkable without
relying on ambiguous `None`. `conformance_tag` is currently structurally restricted to
the single literal value `"MOCK_CONFORMANCE"` — the dataclass's own `__post_init__`
raises `ValueError` for any other value, which is how this stage prevents
`REAL_FOUNDATION_CONFORMANCE` from ever being producible in code, not merely by
convention.

## 9. Reset/isolation

`reset_isolation.py` mirrors `security.determinism.check_run_isolation`'s A->B->A pattern
exactly (reused, not reimplemented) for foundation STATE. Exercised successfully against
the four mock adapters (`check_foundation_reset_isolation`). For the four **real**
foundations, `foundation_reset_isolation_status()` always returns
`REPRODUCIBILITY_LIMITATION`, explicitly and honestly, since no real foundation actually
runs in this stage — deferred to H.4.

## 10. State fingerprinting

`fingerprinting.fingerprint_state()` wraps `security.reproducibility.fingerprint()`
verbatim over a foundation's `export_state()` result. No new hashing system; no list
reordering (the underlying `canonical_serialize` already preserves list/sequence order).

## 11. Configuration fingerprinting

`fingerprinting.build_foundation_configuration()` assembles foundation name/version,
adapter version, configuration parameters, storage backend, retrieval parameters,
embedding/LLM configuration **identifiers** (never secrets), normalization version, and
`security.reproducibility.safe_environment_metadata()` (reused verbatim). `reject_secrets()`
recursively rejects any key matching a secret/credential-shaped name fragment
(`api_key`, `token`, `secret`, `password`, `credential`, `bearer`, `private_key`, ...) at
any nesting depth, raising `ConfigurationSecretError` — proven by a dedicated test that a
key-shaped field (`openai_api_key`) is rejected outright, never silently stripped and
fingerprinted anyway.

## 12. Model dependency boundary

`model_dependency.py`: a pure 9-value classification vocabulary
(`MODEL_REQUIRED`/`MODEL_NOT_REQUIRED`, `EMBEDDING_REQUIRED`/`EMBEDDING_NOT_REQUIRED`,
`EXTERNAL_SERVICE_REQUIRED`/`EXTERNAL_SERVICE_NOT_REQUIRED`,
`LOCAL_MODEL_SUPPORTED`/`LOCAL_MODEL_NOT_SUPPORTED`, `UNKNOWN`) projected directly from
each foundation's `capability_audit.py` rows (`llm_dependency`, `embedding_dependency`,
`external_service_dependency`, `local_execution`) — no independent judgment, no runtime
dependency injection, no real model ever loaded.

## 13. Security boundary

`security.py`'s `enforce_foundation_call_boundary()` reuses
`security.leakage.validate_no_leakage` verbatim. Every mock adapter's `add_memory`/
`update_memory`/`retrieve` runs its `content`/`metadata`/`query` argument through this
check before touching internal state (`mocks/common.py::check_call_payload`). Dedicated
tests prove a `gold_answer`/`gold_evidence_ids`/`evaluation_score`-shaped field is caught
for every one of the four mock adapters (13 parametrized cases in
`TestSecurityBoundary`), and that a credential-shaped metadata field is separately caught
by `fingerprinting.reject_secrets`.

## 14. Phase 4 attack surface (identification only — nothing implemented)

`trace.py`'s `ALL_ATTACK_SURFACE_STAGES` names all eight interception points the mission
brief lists: `INPUT_INGESTION`, `MEMORY_CREATION`, `MEMORY_UPDATE`, `MEMORY_LINKING`,
`STORAGE`, `RETRIEVAL`, `SELECTION`, `AGENT_CONTEXT`, each mapped to the
`MemoryFoundationAdapter` operation(s) it corresponds to
(`ATTACK_SURFACE_OPERATION_MAP`). `FoundationTraceArtifact.attack_surface_stage` is an
optional field a trace can carry. No attack logic (no injection, no poisoning simulation,
no adversarial payload construction) exists anywhere in this package — asserted by a
dedicated test that greps `trace.py`'s source for forbidden attack-execution-suggesting
substrings. A-MEM's memory-evolution capability (section 4) is flagged in the audit as a
genuinely distinctive attack surface (one poisoned note can retroactively rewrite
others' attributes) but this is identification-only prose, never implemented behavior
beyond what `MockAMemAdapter.add_memory`'s documented linking mechanism already does as
its normal, non-adversarial operation.

## 15. Dataset x foundation matrix

`matrix.py`: 7 datasets (4 ACTIVE + 3 PREPARED_CANDIDATE) x 5 "foundations" (NATIVE +
Mem0/Letta/Graphiti/A-MEM) x 20 capabilities (a documented subset of the 27 audit
dimensions — the 7 foundation-level-only facts that don't vary by dataset are excluded).
Every one of the 700 cells is **computed**, not independently hand-authored, from two
already-grounded inputs: (a) for NATIVE, either `NOT_APPLICABLE` (MAMBench has no memory-
foundation operations layer of its own) or a lookup against the dataset's own existing
H/H.1 capability profile; (b) for a real foundation column, that foundation's own
`capability_audit.py` row, gated to `NOT_APPLICABLE`/`UNKNOWN` when the capability
(`session_state`/`temporal_state`) requires a dataset-level structural precondition this
stage did not confirm present. See `matrix.py`'s module docstring for the full rule and
every dataset-precondition citation (LoCoMo/LongMemEval confirmed
`TIMESTAMPED_ABSOLUTE`; MSC/Conversation Chronicles confirmed `ORDERED_SEQUENCE_ONLY`;
MemoryArena's `multi_session_memory`/`temporal_order` confirmed `PARTIAL` from its own
H.1 profile; MemoryAgentBench/MemBench's session/temporal preconditions are honestly
`UNKNOWN` where this stage did not re-derive their differently-shaped profile schema).

## 16. Evaluation interface

A foundation trace is meant to *supply information downstream evaluation logic can
consume* — it does not change any existing metric. `FoundationTraceArtifact`'s
`memory_ids`/`retrieval_ordering`/`native_scores`/`lifecycle_state` fields are shaped so
a future H.4 stage could feed them into the EXISTING (unmodified) Recall@K/MRR/Strict-TSR/
evidence-precision-recall machinery in `phase3/evaluation/metrics/` and the EXISTING
`agent.diagnostics`/`agent.paired` functions this stage's own `lifecycle.py` already
reuses verbatim — no new metric is invented, no existing metric is touched.

## 17. Alternatives considered and rejected

1. **Extend `trace_artifact.schema.json` in place** instead of a new dataclass. Rejected:
   that file is a protected, existing contract surface under this stage's own rules; a new,
   separate, additive structure avoids the STOP-and-report path entirely while still being
   usable by a future H.4 reconciliation.
2. **One shared "generic memory store" mock** implementing all four foundations against a
   single flat schema. Rejected: this is exactly the "four libraries implement the same
   function names" failure mode the mission's central discipline calls insufficient —
   Graphiti's graph richness and A-MEM's cross-note evolution would both be flattened away.
3. **Reuse `datasets.capability.CAPABILITY_STATES` verbatim for `FoundationField`, with no
   new value.** Rejected: `NOT_PROVIDED_BY_SOURCE` reads, by name, as a dataset-record
   fact; overloading it for "this foundation's architecture lacks this operation" would
   confuse two different claims. Exactly one new value was added instead
   (`NOT_SUPPORTED_BY_ARCHITECTURE`), documented as the narrowest possible extension.
4. **Independently hand-author all 700 dataset x foundation x capability matrix cells.**
   Rejected: fabricating 700 independent judgments this stage has no way to ground would
   violate the "never mark something supported because an adapter could fabricate it"
   rule far more than a smaller, honestly-computed, clearly-ruled matrix.
5. **Treat A-mem and A-mem-sys as one undifferentiated "A-MEM."** Rejected per the task
   brief's own explicit instruction; both repos were fetched and compared, and the
   difference is now a first-class, cited finding (section 4).
6. **Fill Letta's UNKNOWN audit rows from general training-data familiarity with Letta/
   MemGPT's published architecture**, since docs.letta.com did not yield the requested
   detail. Rejected: the mission's "mark UNKNOWN honestly" rule takes precedence over
   filling gaps with unconfirmed prior knowledge; every such row is capped at PARTIAL or
   UNKNOWN with the limitation stated explicitly, never silently upgraded to SUPPORTED.

## 18. Provisional decisions

- The 20-capability matrix subset (section 15) and the 27-dimension audit list (section 4)
  are this stage's own explicit, documented choices, not literal restatements of an
  external fixed list — flagged as provisional in the same spirit as the first H.3 stage's
  own `CONDITION_SELECTED_MEMORY_AVAILABLE`-style provisional extensions.
- `FoundationTraceArtifact` as a dataclass, not a JSON Schema, is provisional pending H.4's
  decision on whether a real schema-validated contract is worth authoring once a real
  foundation actually runs.

## 19. Known limitations

- Letta's audit is the thinnest of the four (docs.letta.com/concepts/memory 404'd);
  several rows are honestly UNKNOWN.
- The dataset x foundation matrix's `session_state`/`temporal_state` preconditions for
  MemoryAgentBench and MemBench are UNKNOWN, not derived, since their profile JSON schemas
  differ from the four active datasets' and from MemoryArena's and this stage did not
  re-derive them in full.
- No mock adapter attempts to reproduce any foundation's REAL ranking/scoring algorithm —
  each mock's retrieval scoring is a deliberately simple, deterministic stand-in
  documented as such, never claimed to predict real foundation behavior.
- Reset/isolation is verified only against the mocks; all four real foundations carry
  `REPRODUCIBILITY_LIMITATION` honestly, pending H.4.

## 20. Phase 3.3 integration boundary

This package is consumed only by future work, not by anything currently running in
Phase 3.2. No existing evaluation pipeline entry point imports `phase3/evaluation/
foundations/` anywhere in this stage. A future Phase 3.3 stage that wants to route a real
evaluation run through a real foundation would do so through this package's
`MemoryFoundationAdapter` interface and `FoundationTraceArtifact` shape, not by
special-casing any one foundation.

## 21. H.4 real-conformance plan

For each of Mem0/Letta/Graphiti/A-MEM, H.4 would need to: (1) install the real library in
an isolated environment; (2) implement a REAL adapter class (e.g. `Mem0Adapter`)
alongside (never replacing) the corresponding `Mock*Adapter`, both implementing the same
`MemoryFoundationAdapter` interface; (3) re-run every test in
`test_foundation_architecture_h3.py`'s structural-contract classes against the real
adapter, substituting real network/LLM/embedding calls for the mock's deterministic
stand-ins; (4) verify determinism/reset-isolation against the REAL system (expected to
require an explicit seed/mock-LLM strategy, since the audit found LLM-mediated extraction
in all four foundations inherently non-deterministic); (5) only then flip that
foundation's `registry.py` entry from `PREPARED_CANDIDATE` toward an `ACTIVE`-equivalent
status, and only then permit any trace's `conformance_tag` to become
`REAL_FOUNDATION_CONFORMANCE` (requiring a structural change to
`FoundationTraceArtifact.__post_init__`'s currently-single-value restriction, done
deliberately, not by relaxing it prematurely).

## 22. Summary

This stage builds the interface, lifecycle model, trace contract, fingerprinting,
security boundary, matrix, and four deterministic mock adapters needed to eventually
evaluate dataset x memory-foundation x agent x evaluation x attack — grounded in an actual
capability audit of all four foundations, never fabricating a capability none of them
documented, and never claiming real foundation conformance anywhere in the package.
