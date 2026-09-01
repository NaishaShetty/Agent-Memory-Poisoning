# Phase 3.3-A — Real LLM + Agent Experimental Specification

**Status:** DESIGN / SPECIFICATION ONLY. No implementation.
**Stage:** Phase 3.3-A (first stage of Phase 3.3).
**Precondition:** Phase 3.2 is COMPLETE and validated (`PASS_WITH_DOCUMENTED_LIMITATIONS`,
see [`phase3/evaluation/PHASE3_2_FINAL_VALIDATION.md`](../evaluation/PHASE3_2_FINAL_VALIDATION.md)).
**Boundary:** This document does not redesign Phase 3.2, does not modify canonical
evaluation semantics, does not implement attacks, and does not begin the full
experimental campaign. It defines the experiment before the experiment is run.

**Naming note.** Several vocabularies referenced informally in prior planning
conversations do not exist verbatim in the frozen Phase 3.2 contracts. Where that is
the case, this document cites the actual frozen names and marks the informal name as
"(informal name used above)" so the two are not confused in later stages. Specifically:
the failure-classification enum's real names are `RETRIEVAL_FAILURE`,
`SELECTION_FAILURE`, `EVIDENCE_UNAVAILABLE`, `AGENT_FAILURE_WITH_EVIDENCE`,
`AGENT_EXECUTION_FAILURE`, `SUCCESS`, `UNDEFINED_EVALUATION` (seven values,
`phase3/evaluation/agent/diagnostics.py`); and no formal `SOURCE_MEMORY_ID` /
`ADAPTER_MEMORY_ID` / `FOUNDATION_MEMORY_ID` / `GOLD_EVIDENCE_ID` / `EXPERIMENT_ID`
namespace exists yet — Part 19 below newly *defines* these as a 3.3-A-scoped
convention on top of the existing `task_id` / `memory_id` / `event_id` join keys from
[`TRACEABILITY_CONTRACT.md`](../contracts/TRACEABILITY_CONTRACT.md).

---

## Part 1 — Experimental Philosophy

Phase 3.2 built and validated four independent layers without ever wiring them to a
real model:

```
Evaluation infrastructure   (phase3/evaluation/metrics, agent/, security/)
        ≠
Agent implementation        (does not exist yet — 3.3 scope)
        ≠
Memory foundation           (phase3/evaluation/foundations, foundations_real)
        ≠
LLM                         (does not exist yet — 3.3 scope)
        ≠
Dataset                     (phase3/evaluation/datasets, DATASET_CAPABILITY_MATRIX.md)
```

These five must remain independently substitutable experimental variables. Concretely,
the Phase 3.3 architecture must support all of the following without touching the other
four components' code:

- Swap the LLM (e.g. a different `LLMProvider` implementation) with the same agent,
  foundation, and dataset.
- Swap the memory foundation (Mem0 → Graphiti) with the same agent, LLM, and dataset.
- Disable memory entirely (no-memory control) with the same agent and LLM.
- Swap the dataset with the same agent, LLM, and foundation.
- Replace the agent's internal retrieval/reranking/selection policy without touching
  the evaluator, the foundation adapter interface, or the metrics layer.

The evaluator (`phase3/evaluation/metrics`, `phase3/evaluation/agent/diagnostics.py`,
`phase3/evaluation/agent/paired.py`) never becomes aware of *which* LLM, provider, or
foundation produced a trace — it only consumes the frozen `AgentExecutionResult` /
`TraceArtifact` shapes. This is the same separation `CLEAN_AGENT_INTERFACES.md` already
establishes between memory layer and reasoning layer; Phase 3.3 extends it to cover the
LLM provider and the concrete foundation choice as well.

## Part 2 — Experimental Variables

### Independent variables

| Variable | Values (3.3-A scope) | Notes |
|---|---|---|
| LLM / model | one real model per run, provider-abstracted (Part 4) | model identity + weight hash recorded per `REPRODUCIBILITY_CONTRACT.md` |
| Memory foundation | `NONE`, `Mem0`, `Graphiti`, `A-MEM`, (`Letta` if executable, Part 10) | via `MemoryFoundationAdapter` |
| Memory enabled/disabled | `enabled`, `disabled` | disabled = condition A (Part 11) |
| Retrieval configuration | top_k, foundation-native retrieval params | recorded, not frozen (Phase 3.1 left these open) |
| Dataset | Tier 1 required, Tier 2 optional (Part 13) | Tier 3 excluded by policy (Part 28) |
| Task type | dataset-native (QA, lifecycle, agentic-task where defined) | not all datasets expose all task types |

### Dependent variables

Reuse Phase 3.2's frozen metric set exactly — no new combined score is invented:

- Recall@K (K ∈ {1,5,10,20,50,100,200})
- MRR
- Strict TSR (`strict_tsr()`, frozen formula — Part 16)
- Evidence-equivalent success (diagnostic, alongside strict TSR, never replacing it)
- Evidence precision, evidence recall, evidence coverage
- Answer correctness (`evaluate_answer_correctness()`)
- Agent/task success where defined (`classify_agent_success()`)
- Memory utilization (`classify_retrieval_utilization`)
- Memory contribution (`classify_memory_contribution`, 4-way, non-causal)
- Failure stage (7-value enum, Part 17)
- Latency (per stage, Part 25)
- Memory overhead (foundation storage/compute cost, Part 25)

No "memory quality" composite is defined. Foundation comparison (Part 31) and dataset
comparison (Part 32) report the above metrics side by side, never averaged into one
number.

## Part 3 — Controlled Variables

Every experimental condition records the following; any variable that differs between
two conditions being compared must be logged as part of that comparison's
configuration diff, not left implicit:

- System prompt (version-pinned)
- Task prompt (version-pinned, per dataset adapter)
- Model identity + weight hash
- Temperature, top-p, top-k, max output tokens
- Context window budget
- Retrieval K and foundation-native retrieval parameters
- Foundation configuration (`initialize(configuration)` payload, secret-free per
  `fingerprinting.reject_secrets`)
- Embedding model (where the foundation uses one)
- Dataset revision / dataset fingerprint
- Preprocessing version, normalization version
- Random seed (where the provider supports one — Part 5)
- Environment (`safe_environment_metadata()`, to be extended per Part 33)
- Tool configuration (if the agent exposes tools beyond memory retrieval — none in
  3.3-A scope)
- Timeout policy
- Retry policy

This list is the superset of `REPRODUCIBILITY_CONTRACT.md`'s "must be recorded per
run" fields plus the LLM-specific fields `CLEAN_AGENT_INTERFACES.md` §2.1 already
requires for the reasoning layer.

## Part 4 — Model Provider Abstraction

A single `LLMProvider` interface is specified (not implemented in 3.3-A). It must
support at minimum an OpenAI-compatible provider, a Gemini provider, and a local-model
provider without the agent or evaluator code branching on which one is in use.

```
LLMProvider (abstract)
    generate(messages, config) -> LLMResponse
    model_metadata() -> ModelMetadata            # identity, weight hash if known, revision
    configuration_fingerprint() -> str            # deterministic hash of decoding config
```

- `generate(...)` is the only call the agent makes to produce text. It accepts the
  assembled reasoning-context messages and a decoding config (temperature, top-p,
  top-k, max tokens, seed if supported); it returns text plus raw usage/latency
  metadata.
- `model_metadata()` exposes identity for the reproducibility record (Part 33) — never
  provider credentials.
- `configuration_fingerprint()` is a stable hash of the decoding configuration, used
  the same way `reproducibility.fingerprint()` hashes other configuration blocks.

Provider-specific details (HTTP client, SDK, auth mechanism, streaming protocol) stay
entirely inside the concrete provider implementation and are never visible to the
agent, the evaluator, or the trace schema. The evaluator only ever sees
`ModelMetadata` and the fingerprint, mirroring how it already only sees
`FoundationIdentity` rather than a foundation's internal client. This is a design
requirement for 3.3-B, not implemented here.

## Part 5 — LLM Stochasticity

**Deterministic** (per `REPRODUCIBILITY_CONTRACT.md`, unchanged by 3.3):
preprocessing, normalization, dataset adapters, memory identity assignment, evidence
mapping, metric computation (`phase3/evaluation/metrics/*`), trace generation for
non-LLM stages, configuration fingerprints.

**Stochastic** (new in 3.3, not present in Phase 3.2 since no real LLM existed):
LLM generation (`LLMProvider.generate`); any foundation-internal LLM-mediated
extraction or memory evolution (e.g. Mem0's own summarization/fact-extraction calls,
which are themselves LLM calls independent of the agent's reasoning LLM); any other
model-dependent operation inside a foundation adapter.

3.3-A does **not** promise bit-for-bit reproducibility of stochastic generation, even
when a provider exposes a `seed` parameter — seed support does not guarantee identical
output across provider-side model updates or non-deterministic accelerator kernels.
Instead, Part 23 defines a repeated-run methodology: every stochastic condition is run
N times, and results are reported as distributions (Part 24), not single values.

## Part 6 — Agent Contract

The Phase 3.3 agent accepts exactly:

```
Task                  # dataset-native question/instruction, from the AgentVisibleContext
Memory interface       # a MemoryFoundationAdapter instance, or None (no-memory condition)
LLM provider           # an LLMProvider instance
Configuration           # retrieval K, prompt version, decoding config, etc.
```

and produces exactly:

```
Answer                 # → AgentExecutionResult.answer
Agent trace             # → TraceArtifact (Part 18)
Memory interaction trace # retrieved/selected/exposed/used memory IDs (Part 8)
```

The agent must **not** receive: gold answer, gold evidence IDs, evaluator result,
failure classification, hidden benchmark-only metadata, or future task information —
this is `LEAKAGE_AND_VISIBILITY_CONTRACT.md`'s existing agent-hidden list, unchanged
and extended to cover the LLM call: the reasoning-context messages assembled for
`LLMProvider.generate()` must pass the same `boundary.validate_agent_visible()` check
that the diagnostic scaffold already applies to `AgentVisibleContext`.

## Part 7 — Agent Loop

Canonical execution loop, extending `CLEAN_AGENT_INTERFACES.md`'s existing pipeline
with the LLM call made concrete:

```
Task
 ↓
Task interpretation                 # dataset-adapter-specific; may be a no-op passthrough
 ↓
Memory availability                 # MEMORY_AVAILABLE — foundation present and initialized, or NONE
 ↓
Memory retrieval                    # MEMORY_RETRIEVED — adapter.retrieve(query, top_k)
 ↓
Memory selection                    # MEMORY_SELECTED — evidence selection (budget/redundancy/independence)
 ↓
Agent-visible context               # MEMORY_EXPOSED — assembled into AgentVisibleContext, boundary-checked
 ↓
LLM reasoning/generation            # LLMProvider.generate() — MEMORY_USED determined post hoc from output
 ↓
Answer/action                       # AgentExecutionResult
 ↓
Evaluation                          # outside the agent — evaluator only, MEMORY_CONTRIBUTED computed here
 ↓
Failure classification              # classify_observed_failure_stage()
```

Memory updates (foundation-native writes triggered by ingesting a conversation/session)
occur according to each foundation's own semantics — Mem0's extraction pipeline,
Graphiti's graph construction, A-MEM's agentic memory evolution are not forced into a
single shared internal algorithm. The agent loop above only specifies the *interface*
points (retrieval, selection, exposure, generation), not how a foundation implements
what happens inside `add_memory`.

## Part 8 — Memory Lifecycle

Reuse the existing six-stage lifecycle verbatim from
`phase3/evaluation/foundations/lifecycle.py`:

```
MEMORY_AVAILABLE → MEMORY_RETRIEVED → MEMORY_SELECTED → MEMORY_EXPOSED → MEMORY_USED → MEMORY_CONTRIBUTED
```

`MEMORY_CAUSED` remains the deliberately unreachable seventh constant — Phase 3.3 does
not implement it, does not return it, and does not add a causal-attribution stage. This
matches the mission's Part 8 instruction exactly and the code's existing, test-enforced
guarantee (`LIFECYCLE_STAGES` excludes it; a grep-based test asserts no function
returns it).

Where a foundation cannot natively expose a given stage (e.g. a foundation with no
distinguishable "selection" step separate from "retrieval"), the experiment records
that stage as `NOT_OBSERVABLE` for that foundation rather than inferring or fabricating
a value. This reuses the existing `CAPABILITY_STATES` vocabulary style
(`AVAILABLE`/`PARTIAL`/`UNAVAILABLE`/`UNKNOWN`/`NOT_PROVIDED_BY_SOURCE`/`PROVISIONAL`,
plus foundations' own `NOT_SUPPORTED_BY_ARCHITECTURE`) rather than inventing a new one.

## Part 9 — Memory Foundation Abstraction

Phase 3.3 reuses `phase3/evaluation/foundations/adapter.py`'s `MemoryFoundationAdapter`
unchanged — no second abstraction is created. The agent interacts with a foundation
exclusively through the eleven abstract methods already defined
(`foundation_identity`, `capabilities`, `initialize`, `reset`, `add_memory`,
`retrieve`, `update_memory`, `delete_memory`, `inspect_memory`, `export_state`,
`normalize_trace`, `shutdown`), each returning a `FoundationField`. Foundation-native
internal structure (Mem0's fact graph, Graphiti's temporal graph, A-MEM's link
network) is preserved as-is inside each adapter and never flattened into a common
internal representation.

3.3-A's only addition to this abstraction, if any, is at the *real-adapter*
implementation level (3.3-B scope, not this document): moving `foundation_identity().status`
from `PREPARED_CANDIDATE` to `ACTIVE` for foundations that pass real conformance
testing under a real LLM. That transition criterion is defined here (Part 10) but not
executed here.

## Part 10 — Foundation Conditions

| Condition | Composition | Status entering 3.3-A |
|---|---|---|
| No-memory baseline | Agent + LLM | mandatory (Part 11) |
| Memory baseline | Agent + LLM + Mem0 | real adapter exists (`mem0_real_adapter.py`); structural conformance passed in H.4; LLM-mediated behavior untested until 3.3-B |
| Graph memory | Agent + LLM + Graphiti | real adapter exists (`graphiti_real_adapter.py`); requires external graph/database infrastructure — document as environment-dependent, not assumed available |
| Agentic memory | Agent + LLM + A-MEM | real adapter exists (`amem_real_adapter.py`); structural conformance passed in H.4 |
| Letta | Agent + LLM + Letta | adapter exists (`letta_real_adapter.py`) but its real-library conformance test has never been run (H.4 focused on Mem0/Graphiti/A-MEM). **Deferred/environment-limited** unless a real executable environment for Letta is confirmed available before 3.3-B begins. Do not claim conformance from adapter existence alone. |

An adapter's mere existence is not conformance. "Real conformance evidence" means the
adapter has been exercised against the real foundation library/service and its
behavior characterized (as H.4 did structurally for Mem0/Graphiti/A-MEM) — Phase 3.3-A
does not claim this for LLM-mediated behavior, since no real LLM has been wired in yet.

## Part 11 — No-Memory Control

Mandatory. The no-memory baseline receives identical task, LLM, prompt, generation
settings, and evaluation procedure as every memory condition, with `Memory interface =
None`. This is condition **A** in `EVALUATION_CONTRACT.md`'s existing A/B/C
methodology (`Task → Qwen-equivalent LLM → Answer`, no memory layer at all) — 3.3-A
does not redefine A/B/C, it makes A/C real (with a real LLM) and treats B (gold-evidence
control) as still required per the frozen contract: **C must always be characterized
relative to both A and B in the same run**, never reported alone.

## Part 12 — Memory Ablation Design

Controlled conditions, mapped onto the existing six-stage lifecycle (Part 8):

```
A' — No memory                (baseline; Part 11)
B' — Memory available          MEMORY_AVAILABLE
C' — Memory retrieved          MEMORY_RETRIEVED
D' — Memory selected           MEMORY_SELECTED
E' — Memory exposed            MEMORY_EXPOSED
F' — Memory used                MEMORY_USED
```

(Primed to avoid collision with `EVALUATION_CONTRACT.md`'s A/B/C, which denote
no-memory / gold-evidence / retrieved-memory *conditions*, not lifecycle *stages* —
these are two orthogonal axes and must not be conflated in reporting.)

Not every foundation exposes every stage identically or observably (Part 8). Where a
stage cannot be directly observed for a given foundation, the report states
`NOT_OBSERVABLE` for that (foundation, stage) cell rather than inferring it from
adjacent stages or defaulting it to a fabricated value.

## Part 13 — Dataset Tiers

Unchanged from `DATASET_CAPABILITY_MATRIX.md`, restated here as experimental policy:

**Tier 1 — Primary baseline** (required for 3.3-A's minimum experiment matrix, Part 21):
LoCoMo, LongMemEval, MSC, Conversation Chronicles — all `ACTIVE` per the 3.2-I gate.

**Tier 2 — Expanded evaluation** (optional, added where scientifically meaningful):
PerLTQA (zh only — Part 14), ConvoMem (`USABLE_WITH_LIMITATIONS` — Part 15).

**Tier 3 — Candidate research datasets** (excluded from 3.3-A and from automatic
promotion — Part 28): MemoryAgentBench, MemBench, MemoryArena. Remain
`CANDIDATE_ONLY` / `PREPARED_CANDIDATE`. If a future stage evaluates one
experimentally, it must be explicitly labeled candidate-only in every result it
appears in, and its promotion (if ever proposed) must be a documented decision per
`EXPERIMENT_GOVERNANCE.md`'s four-value vocabulary, not an implicit side effect of the
harness being able to load it.

## Part 14 — PerLTQA

Chinese source-native evaluation only. No translation. Native (per-character-scoped)
memory/evidence IDs are used as-is — since IDs are not globally unique across
characters, the agent trace must key on a composite `(character_id, memory_id)` pair,
not `memory_id` alone. Preserve the dataset's own semantic/episodic/structured memory
classification without remapping it into Phase 3.2's foundation/derived ontology.
Language metadata (`zh`) is recorded on every record and every trace. English releases
(`en`/`en_v2`) remain out of scope for 3.3-A given their 81.3% broken non-profile
evidence — the only usable English subset (357-item profile) is not part of the
primary experiment matrix and, if used, must be labeled as the narrower subset it is.

## Part 15 — ConvoMem

Source-native answers only. Evidence resolution uses the existing deterministic J.2/J.3
exact/structural-match waterfall (97.0% resolved, 140,225/144,598 spans) — no fuzzy or
LLM-based matching is introduced in 3.3-A. Unresolved evidence (2.3% zero-resolved
items) remains unresolved: those records are excluded from strict-TSR-bearing metrics
for the affected items rather than silently scored as correct or incorrect. No
fabricated evidence is introduced to close the gap. `LICENSE_UNRESOLVED` remains open
(GitHub Apache-2.0 vs. HF dataset-card CC-BY-NC-4.0 vs. `dataset_info.json`
Apache-2.0) — 3.3-A treats ConvoMem under the more restrictive CC-BY-NC-4.0 reading for
any distribution/reporting decision, per the standing J.2 practical stance, and does
not attempt to resolve the license disagreement itself. Overall status stays
`USABLE_WITH_LIMITATIONS`, not upgraded to `FULLY_SUPPORTED`.

## Part 16 — Strict TSR

Frozen exactly as implemented in `phase3/evaluation/metrics/selection.py::strict_tsr()`:

```
strict_tsr = 1 if (set(selected_or_used_ids) ∩ set(gold_evidence_ids)) ≠ ∅ else 0
```

This is a literal-ID-membership diagnostic, verbatim from
`phase3_reference/clean_agent_v1/src/reference_agent.py` and unchanged through 3.2-I.
It is not general agent success, not answer correctness, not semantic similarity, and
not a causal-attribution metric. No component of Phase 3.3 redefines it, reweights it,
or substitutes evidence-equivalent success in its place — the two are always reported
side by side (`EVALUATION_CONTRACT.md` §4).

## Part 17 — Failure Classification

Reuse `phase3/evaluation/agent/diagnostics.py::classify_observed_failure_stage()`
verbatim — the actual frozen seven-value, precedence-ordered, mutually exclusive
vocabulary:

```
RETRIEVAL_FAILURE
SELECTION_FAILURE
EVIDENCE_UNAVAILABLE
AGENT_FAILURE_WITH_EVIDENCE
AGENT_EXECUTION_FAILURE
SUCCESS
UNDEFINED_EVALUATION
```

(This corrects the six-name informal list used in earlier planning — the code's real
names differ, e.g. there is no bare `EXECUTION_FAILURE` or `ANSWER_FAILURE` constant;
`AGENT_EXECUTION_FAILURE` and `AGENT_FAILURE_WITH_EVIDENCE` are the actual analogues.)
Mutual exclusivity is enforced by the existing fixed seven-step precedence order
(execution failure → success → undefined → no-memory condition → empty gold →
gold-evidence condition → per-gold retrieval/selection classification) and is
re-verified, not re-implemented, in 3.3-A. Every classification remains labeled
"OBSERVED", never "CAUSED" — consistent with Part 8's `MEMORY_CAUSED` exclusion.

## Part 18 — Experiment Trace

Minimum trace schema per experiment run, extending
`TRACEABILITY_CONTRACT.md`'s existing task-execution and memory-history traces with
the LLM- and foundation-instance-specific fields 3.3 introduces:

```
experiment_id
dataset
dataset_revision
record_id
model                     # LLMProvider.model_metadata()
model_revision
foundation                # FoundationIdentity.foundation_name, or "NONE"
foundation_version        # FoundationIdentity.adapter_version
configuration              # full controlled-variable block (Part 3)
task
memory_available           # bool, from MEMORY_AVAILABLE stage
retrieved_memories          # memory_ids, from MEMORY_RETRIEVED
selected_memories           # memory_ids, from MEMORY_SELECTED
exposed_memories            # memory_ids, from MEMORY_EXPOSED (post boundary-check)
used_memories                # memory_ids, from AgentExecutionResult.used_memory_ids
contributed_memories         # from classify_memory_contribution() — diagnostic, non-causal
agent_output                 # AgentExecutionResult.answer
evaluation_result             # from evaluator, joined post hoc — never fed back into the agent
failure_stage                  # classify_observed_failure_stage()
latency                         # per-stage breakdown, Part 25
fingerprints                     # configuration_fingerprint(), dataset fingerprint, etc.
```

Gold-only evaluator fields (`gold_answer`, `evidence_memory_ids`, `evaluation_result`,
`failure_stage`, and the rest of `security/leakage.py::PROTECTED_FIELD_NAMES`) must
never appear in the agent-visible portion of this trace — only in the
evaluator-appended portion, joined after the agent has produced its answer. This is
enforced by running `boundary.validate_agent_visible()` and
`security/leakage.py`'s structural leakage detector against the agent-visible slice of
every trace before it is considered valid (Part 26).

## Part 19 — Identity Namespaces

No such formal namespace exists in the frozen contracts today (see Naming note above).
3.3-A defines the following convention, layered on top of the existing `task_id` /
`memory_id` / `event_id` join keys from `TRACEABILITY_CONTRACT.md`, without altering
that contract:

- `SOURCE_MEMORY_ID` — the dataset's own native memory/turn/session identifier, as
  given by the dataset adapter, before any foundation ingests it.
- `ADAPTER_MEMORY_ID` — the identifier `MemoryFoundationAdapter.add_memory()` was
  called with (may equal `SOURCE_MEMORY_ID` or be `None` if the foundation assigns its
  own).
- `FOUNDATION_MEMORY_ID` — the identifier the foundation itself returns/assigns
  internally (e.g. Mem0's own memory ID after fact-extraction), which may differ from
  both of the above and is explicitly *not* ground truth (H.5 already established this
  distinction empirically: `SOURCE_MEMORY_ID` ≠ `FOUNDATION_DERIVED_IDENTITY` is
  test-verified as expected behavior, not a bug).
- `GOLD_EVIDENCE_ID` — the dataset's benchmark-designated correct-evidence identifier,
  used only by the evaluator, never exposed to the agent (Part 6).
- `EXPERIMENT_ID` — a per-run identifier scoping one (dataset, model, foundation,
  configuration) combination, joining all of the above across a run.

These four ID kinds must remain distinct fields in the trace schema (Part 18) even
when their values coincide for a particular record, so that foundation-generated IDs
are never silently treated as ground truth.

## Part 20 — Foundation Reset

Each experiment begins from a known foundation state:

```
RESET → INGEST → RUN → EVALUATE
```

`MemoryFoundationAdapter.reset()` already exists as an abstract method; 3.3-A requires
every concrete foundation condition to call it before ingest and to record its
`FoundationField` result (including `availability`) in the trace. Where a foundation
cannot guarantee true isolation (e.g. an external graph database that persists state
outside the adapter's control, or a hosted service with no hard reset), this is
recorded as a documented limitation on that foundation's condition, not silently
assumed away — runs on such a foundation are flagged as potentially contaminated by
prior runs rather than reported as independent trials.

## Part 21 — Experiment Matrix

3.3-A does not run the full Cartesian product. The minimum meaningful matrix for the
pilot and initial campaign (3.3-B+) is:

```
4 canonical (Tier 1) datasets × {no-memory, Mem0, Graphiti, A-MEM}
```
= 16 base cells, each further crossed with the A/B/C condition axis
(`EVALUATION_CONTRACT.md` §5) for the memory-bearing cells (no-memory only needs A).

Then, where scientifically meaningful:

```
+ PerLTQA (zh) × {no-memory, best-performing Tier-1 foundation}
+ ConvoMem × {no-memory, best-performing Tier-1 foundation}
```

Tier 2 datasets are added narrowly (not against all four foundations) because their
purpose is to test whether findings from Tier 1 generalize to a different language
(PerLTQA) or a different conversational structure (ConvoMem) — not to redundantly
re-run the full foundation sweep on data with known evidence-resolution gaps. Letta is
excluded from the matrix entirely until Part 10's deferred status is resolved.

Each cell's scientific purpose:
- **No-memory × dataset**: establishes the LLM's memory-free ceiling/floor per
  dataset — the mandatory control (Part 11) every other cell is compared against.
- **Foundation × dataset**: answers research questions 1–7, 9 (does memory help, where
  does it fail, does behavior differ by foundation and by dataset).
- **Tier 2 additions**: answers research question 9 specifically (do different
  datasets expose different memory behaviors) across language and structure axes.

## Part 22 — Pilot Before Full Campaign

A pilot (3.3-B/C scope, specified here so 3.3-B can execute against it) must verify,
on a small sample (e.g. single-digit records) from one Tier 1 dataset with one real
foundation:

- real LLM invocation succeeds end-to-end
- real agent execution completes the full loop (Part 7)
- memory insertion succeeds (`add_memory` real conformance)
- retrieval returns non-trivial results
- selection produces a bounded, non-empty-or-correctly-empty set
- context construction passes `boundary.validate_agent_visible()`
- answer generation produces well-formed output
- evaluation runs and produces all dependent variables (Part 2) without error
- trace generation produces a complete Part 18 trace
- leakage tests (Part 26) pass on the pilot's traces
- reset (Part 20) is confirmed to isolate the pilot from any prior state
- reproducibility metadata (Part 33) is fully populated, no missing fields

Only after every pilot check passes does the full campaign (Part 21) begin. A failing
pilot check blocks the campaign, not just that cell.

## Part 23 — Repeated Runs

Because LLM generation is stochastic (Part 5):

- Use a fixed seed where the provider supports one, recorded per run — but seed
  support is not treated as a reproducibility guarantee (Part 5).
- Repeat each (dataset, foundation, condition) cell N times.
- Initial repetition count for the pilot and early campaign: **N = 3**, distinct from
  and not a substitute for a later formal statistical-power determination once
  variance is empirically observed (that determination is 3.3-C+ scope).
- Do not cherry-pick: all N runs are retained and reported, including failed runs
  (Part 24).
- Failed runs (provider error, timeout, malformed output) are recorded with their
  failure mode, not discarded or silently re-run in place.

## Part 24 — Statistics

Per cell, report:

- Mean and standard deviation of every dependent variable across N runs.
- Median where the distribution is skewed (e.g. latency).
- Confidence intervals only where N is large enough to support them meaningfully — not
  claimed at N = 3 (Part 23); with N = 3 report the raw per-run values alongside
  mean/SD instead of a CI.
- Per-run results, not just aggregates — so a later reader can see individual-run
  variance, not just a summary that could hide instability.
- Failure-stage distribution (Part 29) per cell, across all N runs.

Where the experiment design does not support a causal conclusion (which is essentially
always at this stage — see `EXPERIMENT_GOVERNANCE.md`'s composition-testing
requirement and Part 8's `MEMORY_CAUSED` exclusion), report an association
("memory-enabled runs on LoCoMo showed higher answer correctness than no-memory runs
in this sample") — never a causal claim ("memory caused higher correctness").

## Part 25 — Latency / Cost

Record, where measurable:

- LLM generation latency (per call)
- Retrieval latency (`adapter.retrieve()` wall time)
- Foundation latency (other adapter operations — `add_memory`, `update_memory`, etc.)
- Total task latency (end to end, Part 7's loop)
- Memory operations count (adds/updates/deletes per task)
- Token usage, if the provider reports it
- External API cost, if the provider/foundation reports it

Costs are not compared across providers or foundations without accounting for
model/service differences (different models at different price points, different
foundations doing different amounts of LLM-mediated work internally) — a raw
dollar-per-run comparison across providers is not a valid conclusion from this design
and must not be reported as one.

## Part 26 — Leakage

Mandatory tests, extending `security/leakage.py`'s existing structural checks to cover
the new LLM call surface:

- Gold answer leakage: `gold_answer` never appears in the messages passed to
  `LLMProvider.generate()`.
- Gold evidence leakage: `evidence_memory_ids` / `GOLD_EVIDENCE_ID` never appear in
  agent-visible context.
- Evaluator-state leakage: `evaluation_result`, `failure_stage`, `strict_tsr` and other
  `PROTECTED_FIELD_NAMES` never appear pre-generation.
- Hidden-label leakage: any benchmark-only metadata field is excluded from the
  agent-visible slice.
- Foundation metadata leakage: a foundation's internal retrieval scores/ranks are not
  passed to the LLM (`CLEAN_AGENT_INTERFACES.md` §2.4 already forbids this for the
  reasoning layer; 3.3-A applies it literally to the real `generate()` call).
- Previous-task contamination: a foundation's memory state from a prior record/run
  does not leak into the current task's exposed context, verified against Part 20's
  reset guarantee.

The evaluator remains a process boundary outside the agent — it is never imported by,
called from, or reachable from agent or provider code.

## Part 27 — Security Boundary

Phase 3.3 is a clean baseline. No poisoning, sleeper memories, malicious memory
injections, attack payloads, or adversarial manipulation of any kind are introduced at
this stage. `PHASE4_INTERFACE_REQUIREMENTS.md` already defines the interface
attack/defense work will need later (attack-origin attribution, lineage
reconstruction, propagation/retrieval/selection/reasoning influence analysis,
decision-change attribution) — 3.3-A implements none of that scaffolding, it only
establishes the clean state those later measurements will be taken against. This
matches the mission statement exactly: 3.3 establishes the clean baseline; attacks are
later, separate work.

## Part 28 — Candidate Dataset Policy

MemoryAgentBench, MemBench, and MemoryArena are not activated because the harness can
technically load them. Their Phase 3.2 statuses (`CANDIDATE_ONLY` /
`PREPARED_CANDIDATE`, per `DATASET_CAPABILITY_MATRIX.md`) are unchanged by this
document. If later evidence justifies promotion, it must go through
`EXPERIMENT_GOVERNANCE.md`'s decision process (`ACCEPT` / `REJECT` /
`DIAGNOSTIC ONLY` / `REQUIRES FOLLOW-UP`) as an explicit, documented decision — never
an implicit side effect of Part 21's matrix construction being generic enough to
include them.

## Part 29 — Failure Analysis

Required reporting shape per cell (dataset × foundation × condition), using the real
Part 17 vocabulary:

```
TSR (strict) = X%
Evidence-equivalent success = X%

RETRIEVAL_FAILURE            = X%
SELECTION_FAILURE            = X%
EVIDENCE_UNAVAILABLE         = X%
AGENT_FAILURE_WITH_EVIDENCE  = X%
AGENT_EXECUTION_FAILURE      = X%
SUCCESS                      = X%
UNDEFINED_EVALUATION         = X%
```

Each percentage is computed from `classify_observed_failure_stage()` output across all
N runs (Part 23) of that cell. The goal is diagnosis (where in the pipeline does the
system fail) rather than a single leaderboard ranking — this report is always paired
with Part 31's per-foundation breakdown, not presented as a standalone score.

## Part 30 — Memory Effect Analysis

Defined comparisons, all diagnostic/associative (Part 24), none causal unless a future
stage adds the controls needed to justify that:

```
No Memory  vs  Memory Enabled        # condition A vs C, same LLM/prompt/dataset
Retrieved  vs  Not Retrieved         # within memory-enabled runs, by whether MEMORY_RETRIEVED was non-empty
Memory Used  vs  Memory Not Used     # within memory-enabled runs, by AgentExecutionResult.used_memory_ids, where observable
```

The third comparison is only reported where `MEMORY_USED` is actually observable for
that foundation (Part 8) — otherwise it is marked `NOT_OBSERVABLE`, not inferred from
`MEMORY_SELECTED`.

## Part 31 — Foundation Comparison

Foundations are compared on each of the following independently — no single arbitrary
aggregate score is produced:

- Retrieval (Recall@K, MRR)
- Evidence grounding (evidence precision/recall/coverage)
- Answer correctness
- Memory utilization
- Memory contribution
- Failure distribution (Part 29, per foundation)
- Latency (Part 25, per foundation)
- Memory overhead (per foundation)
- Stability (variance across the N repeated runs, Part 23–24)

## Part 32 — Dataset Comparison

Investigate whether datasets expose different memory behaviors along these axes:
conversational (LoCoMo, MSC), long-context (LongMemEval), multi-session
(Conversation Chronicles, MSC), multilingual (PerLTQA), structured memory (PerLTQA's
semantic/episodic/structured classification), agentic memory (A-MEM foundation
behavior specifically, and MemoryArena's `agentic_task_memory` capability if that
dataset is ever promoted — not in 3.3-A).

Language differences (PerLTQA zh) are never conflated with foundation-quality
differences — any PerLTQA result is reported as "this foundation's behavior on
Chinese-language, per-character-scoped memory," not folded into a cross-dataset
foundation ranking that implicitly treats language as a foundation property.

## Part 33 — Reproducibility

Every experiment records, extending `REPRODUCIBILITY_CONTRACT.md`'s existing list with
the LLM-specific fields Part 4–5 introduce:

```
dataset
dataset_revision
dataset_fingerprint
normalization_version
model
model_revision
foundation
foundation_version
embedding_model
prompt_version
retrieval_parameters
temperature
seed
environment
configuration_fingerprint
experiment_id
```

`safe_environment_metadata()` (`phase3/evaluation/security/reproducibility.py`) is
currently a placeholder (`python_version` + `platform` only), explicitly flagged in
Phase 3.2 as needing extension for a real-LLM stage. 3.3-B must extend it to include
model weight hash, prompt template version, and decoding config — specified here,
implemented later.

Never recorded: API keys, access tokens, passwords, or any other secret — enforced by
the existing `fingerprinting.reject_secrets` check on `initialize(configuration)`,
extended to cover `LLMProvider` configuration in 3.3-B.

## Part 34 — Experiment Directory Design

Proposed structure (not created in 3.3-A beyond this specification file and the
`phase3/specification/` directory that already exists):

```
phase3/
├── experiments/
│   ├── configs/       # per-run configuration files (Part 3)
│   ├── matrices/       # experiment matrix definitions (Part 21)
│   ├── pilots/          # pilot run definitions and results (Part 22)
│   ├── runs/              # raw run outputs
│   ├── traces/             # TraceArtifact instances (Part 18)
│   └── results/             # aggregated statistics (Part 24)
│
├── agent/               # already exists — diagnostic scaffold; real agent added here in 3.3-B
├── foundations/          # already exists — adapter interface, unchanged
├── evaluation/            # already exists — metrics/agent/security, unchanged
└── specification/          # this document lives here
```

No implementation code or subdirectories under `experiments/` are created by 3.3-A.

## Part 35 — Acceptance Criteria for 3.3-A

- [x] Research questions defined (Core Research Question + secondary 1–10, mission
  text, reproduced verbatim in the final report)
- [x] Hypotheses — none stated as pre-committed claims; the ten secondary questions
  are open questions this design is built to answer, not hypotheses assumed true
- [x] Variables defined (Part 2)
- [x] Controls defined (Part 3)
- [x] Agent contract defined (Part 6)
- [x] LLM abstraction defined (Part 4)
- [x] Foundation abstraction reused, not duplicated (Part 9)
- [x] Dataset tiers defined (Part 13)
- [x] No-memory baseline defined (Part 11)
- [x] Memory lifecycle defined (Part 8)
- [x] Failure classification defined (Part 17, corrected to real names)
- [x] Ablation strategy defined (Part 12)
- [x] Experiment matrix defined (Part 21)
- [x] Repetition strategy defined (Part 23)
- [x] Statistical reporting defined (Part 24)
- [x] Leakage boundary defined (Part 26)
- [x] Reproducibility requirements defined (Part 33)
- [x] Trace schema defined (Part 18)
- [x] Reset/isolation strategy defined (Part 20)
- [x] Clean-baseline boundary defined (Part 27)
- [x] Phase 4 boundary explicitly preserved (Part 27, Part 9's deferred activation note)

## Part 36 — Protected Surfaces

Verified not modified by 3.3-A (see Tests and git status below):

- Phase 1 (`data/metadata/`, `data/reports/phase1_*`, UMR artifacts) — untouched
- Phase 2 (`data/reports/phase2_*`, `docs/phase2/*`, `config/pipeline_config.yaml`) — untouched
- Active dataset files (`phase3/evaluation/datasets/*`) — untouched
- Candidate dataset files (`phase3/datasets/candidates/*`) — untouched
- Canonical metrics (`phase3/evaluation/metrics/*`) — untouched
- Strict TSR (`selection.py::strict_tsr()`) — untouched, cited verbatim only
- Evaluator contracts (`phase3/contracts/*.md`) — untouched, cited verbatim only
- Agent conditions (`phase3/evaluation/agent/*`) — untouched
- Leakage/security logic (`phase3/evaluation/security/*`) — untouched
- Foundation adapter semantics (`phase3/evaluation/foundations/*`,
  `foundations_real/*`) — untouched
- Phase 3.2 historical reports (`phase3/evaluation/PHASE3_2_FINAL_VALIDATION.md`,
  `AUDIT.md`) — untouched

This stage adds exactly one new file:
`phase3/specification/PHASE3_3_EXPERIMENTAL_SPEC.md`.

## Part 37 — Testing

Only the existing regression suite is run, to confirm 3.3-A introduced no regression.
No fake LLM tests, no fake foundation experiments, and no mock-reported-as-real
behavior are added — real execution tests belong to 3.3-B and later.

Commands run (results in the final report below):

```bash
python -m pytest phase3/evaluation/tests/ -q
python -m pytest phase3/evaluation/tests/ -q
python -m pytest phase3/evaluation/tests/ -q -W error
```

## Part 38 — Git Discipline

No `git add`, `commit`, `push`, `pull`, `rebase`, `reset`, or `clean` performed as part
of this stage. `git status --short` and `git diff --stat` are inspected and reported
in the final report, unstaged.

---

## Research Questions (verbatim, for traceability)

**Core:** How does a real LLM-driven agent behave when equipped with different
long-term memory foundations, and where in the memory-to-answer pipeline do failures
occur?

**Secondary:**
1. Does external memory improve task performance?
2. Does retrieval quality translate into answer quality?
3. Does retrieved memory actually get selected?
4. Does selected memory actually get used?
5. Does memory actually contribute to successful answers?
6. How do different memory foundations behave differently?
7. What failure stage dominates?
8. What are the latency and memory costs?
9. Do different datasets expose different memory behaviors?
10. How much of observed performance is attributable to memory versus the underlying
    LLM?

No component of this design supports causal claims beyond what
`EVALUATION_CONTRACT.md`'s A/B/C control methodology already licenses (Part 11); all
ten questions are answered with associative, diagnostic evidence (Part 24, Part 30).

---

## Remaining Questions Before 3.3-B

1. **Provider selection**: which concrete `LLMProvider` implementation(s) ship first —
   OpenAI-compatible, Gemini, or local? This spec deliberately leaves it open (Part 4);
   3.3-B must decide based on environment/credential availability.
2. **Letta environment**: is a real executable Letta environment available? If not,
   Letta stays deferred (Part 10) for the entire 3.3 series, not just 3.3-A.
3. **Graphiti infrastructure**: does the environment have the external graph/database
   infrastructure Graphiti needs? If not, Graphiti's condition (Part 10) may need to
   be deferred alongside Letta rather than assumed available for the pilot (Part 22).
4. **`safe_environment_metadata()` extension**: the concrete fields to add (model
   weight hash format, prompt template version scheme) need to be pinned before 3.3-B
   writes its first real trace.
5. **Statistical power**: N = 3 (Part 23) is a starting repetition count, not a final
   one — the formal power determination is explicitly deferred to a later stage once
   real variance is observed from the pilot.
6. **Embedding model choice**: left open per Phase 3.1's existing unresolved-items list
   (`PHASE3_CLEAN_AGENT_FOUNDATION_SPEC.md` §30) — 3.3-B inherits this as an open
   governed-experimentation item, not a 3.3-A decision.
