# MAMBench Phase 4 — Cross-Attack Architecture & Design Gap Review

Status: **ARCHITECTURE REVIEW — planning only.** No code written, no
repository cloned or modified, no Phase 3 artifact modified, no memory
written, no attack campaign run, no contract frozen. This document reviews
all six attack plans **collectively** against
[PHASE4_4_2_COMMON_ATTACK_CONTRACT.md](PHASE4_4_2_COMMON_ATTACK_CONTRACT.md)
and [PHASE4_PRE_FLIGHT_DECISIONS.md](PHASE4_PRE_FLIGHT_DECISIONS.md), per
the six per-attack plans:
[AgentPoison](PHASE4_4_3_AGENTPOISON_INTEGRATION_PLAN.md),
[FARMA](PHASE4_4_4_FARMA_RECONSTRUCTION_PLAN.md),
[MINJA](PHASE4_4_3_MINJA_INTEGRATION_PLAN.md),
[MemoryGraft](PHASE4_4_3_MEMORYGRAFT_INTEGRATION_PLAN.md),
[DSRM](PHASE4_4_4_DSRM_RECONSTRUCTION_PLAN.md),
[MPBench](PHASE4_4_5_MPBENCH_INTEGRATION_PLAN.md), and the
[4.1 synthesis](PHASE4_4_1_SYNTHESIS.md).

## 1. Executive Conclusion

The six plans, produced one at a time, each made **locally reasonable**
design choices. Reviewed collectively, three convergent gaps emerge that
no single plan surfaced on its own, because each plan solved its own
version of the same problem independently:

1. **Four different plans independently invented four different ways to
   represent attacker-authored memory content** (FARMA's `reasoning_trace`,
   MemoryGraft's `req/resp/tag/semantic_targets`, DSRM's reinterpreted
   "claim," MPBench's `context/expected_memory`) without a shared
   convention — real duplication risk, not a contract failure but a
   coordination failure the contract should close.
2. **The contract has no explicit structure for multi-step / multi-artifact
   attacks** (MINJA's query sequence, FARMA's seed+amplification cycles) —
   every plan describes this in prose ("record the full sequence as
   provenance") but the 4.2 schema has no field that actually holds it.
3. **Every plan that writes memory through the agent's own normal path
   (not a direct adapter write) has no mechanism to mark the resulting
   memory as attacker-originated** for the existing provenance/taint
   machinery to find later — a real, previously undiscussed gap that
   affects MINJA, DSRM's covert path, and MemoryGraft if the more faithful
   ingestion-path injection is chosen.

None of these are structural failures of the 4.2 contract's core shape
(`AttackRequest` → `AttackAdapter` → `PoisonArtifact`/`InjectionEvent` →
`AttackResult` remains sound). All three are **closable with targeted
additions**, not a redesign. Two additional real gaps were found in the
counterfactual-measurement and selection/retrieval lifecycle areas
(Sections 7, G-004/G-005/G-007). **Outcome: 4.2 requires minor revision
(OUTCOME B), not a structural overhaul.**

## 2. Cross-Attack Matrix

| Dimension | AgentPoison | FARMA | MINJA | MemoryGraft | DSRM | MPBench |
|---|---|---|---|---|---|---|
| Implementation type | REFERENCE_IMPLEMENTATION | MAMBench_RECONSTRUCTION | REFERENCE_IMPLEMENTATION | REFERENCE_IMPLEMENTATION | MAMBench_RECONSTRUCTION | DATASET_BENCHMARK_RESOURCE (taxonomy reconstruction) |
| Original threat model | Poison a RAG knowledge base to backdoor retrieval via an optimized trigger | Forge a "reasoning trace" claiming a safety step is complete | Query-only interaction induces the agent to write its own poisoned memory | Ingest content the agent persists as a validated "successful experience" | Craft an adversarial decision disguised as past experience to bias tool selection | Adversarial payload delivered via untrusted environmental content during normal task execution |
| Attacker capability | WHITE_BOX_EMBEDDER | DIRECT_MEMORY_WRITE | QUERY_ONLY | INDIRECT_INGESTION | DIRECT_MEMORY_WRITE or INDIRECT_INGESTION (both variants) | Spans QUERY_ONLY → INDIRECT_INGESTION across 4 channels; no privileged access in any channel |
| Attacker knowledge | Full retriever architecture/parameters (white-box) or query-only (black-box, per dossier — **not built into any repo variant**, UNVALIDATED whether repo supports it) | Public memory schema, trace-type taxonomy, examples | Public agent documentation; no execution visibility | UNKNOWN / NOT VERIFIED (dossier gap, unresolved) | Full retriever knowledge (white-box) or retriever-exists-only (black-box) — both variants confirmed real | Public agent documentation only |
| Target surface | Retrieval, memory content | Memory content, admission, propagation | Memory admission (via agent self-write), retrieval | Memory admission, content, retrieval, propagation | Memory content, retrieval, reasoning/evidence interpretation | Spans admission/content/retrieval/propagation per class |
| Poison artifact | Optimized trigger token seq. + malicious demonstration | Seed + amplification "reasoning trace" entries | Full bridging query sequence (not a single artifact) | Poisoned req/resp "experience" record | Adversarial decision (Planning Text + Tool Selection + Reasoning Text) | Varies per class; schema fixed (context/expected_memory/retrieval_query) |
| Generation mechanism | BERT-family gradient optimization (MMD + variance fitness) | LLM-generated seed/amplification templates (MAMBench-designed, no source templates) | Bridging-step + indication-prompt + progressive-shortening LLM generation | LLM-generated req/resp + explicit semantic_targets phrase list | Self-Refine (similarity-gated) + CoT-Strategy (3-step) modules | Meta-Llama-3.1-70B-Instruct template-based generation (source); MAMBench substitute TBD |
| Injection mechanism | DIRECT_WRITE | DIRECT_WRITE (iterative) | QUERY_SEQUENCE | Adapter-side DIRECT_WRITE approximating AGENT_MEDIATED_WRITE (fidelity compromise — see Section 6) | DIRECT_WRITE or AGENT_MEDIATED_WRITE (both in scope) | Varies: C1 direct-instruction, C2 inferred, C3/C4 N/A for V3-Hybrid |
| Memory-write path | Real Mem0/A-MEM write API | Real Mem0/A-MEM write API | V3-Hybrid's own normal ingestion (unmodified) | Real Mem0/A-MEM write API (as ordinary ingested content) | Real Mem0/A-MEM write API | Real Mem0/A-MEM ingestion (C2-applicable classes only) |
| Agent-mediated component | No | No (base); store_evasion targets a specific memory category the agent maintains | **Yes — the entire mechanism** | Partially claimed by source, **not confirmed present in V3-Hybrid** (Section 6) | Yes for the covert-path variant | C2 classes rely on the agent's ingestion-policy judgment |
| Retrieval dependency | Yes — core mechanism | Yes | Yes | Yes | Yes | Yes (RSR phase) |
| Selection dependency | Yes, unvalidated against hybrid_selection.py's rerank | Yes, unvalidated | Yes | Yes, unvalidated | Yes, unvalidated | Yes, unvalidated |
| Reasoning dependency | No | Yes (agent must accept the forged claim as settled) | Yes (agent must accept the bridging claim) | No (imitation, not reasoning acceptance) | **Yes — explicit design target** | Varies by class |
| Persistence dependency | Single-write, single-session sufficient | **Core claim requires multi-session dilution test** | Multi-turn within a session (progressive shortening) | **Core claim requires multi-session dominance test** | Single-write sufficient | Two-phase (write session + follow-up session) — inherently multi-session |
| Multi-session dependency | No | Yes | Partial (multi-turn, same session) | Yes | No | Yes |
| Provenance requirements | Standard (adapter is the writer) | Standard (adapter is the writer) | **Non-standard — see Gap G-003** | **Non-standard if ingestion path used — see G-003** | Standard (DIRECT_WRITE) / non-standard (covert path) | Standard for C2 classes |
| Counterfactual requirement | Single-record mask sufficient | **Group/joint mask needed (N seed + amplification records) — G-007** | Single-record mask sufficient (final written record) | **Group mask needed (10 poisoned records) — G-007** | Single-record mask sufficient | Per MPBench's own RSR framing — single or group depending on class |
| Ground-truth requirement | AgentPoison's own ASR_A/ASR_R/RR-style, remapped to 4.2 vocabulary | New MAMBench-defined (no source metric to inherit) | New MAMBench-defined | New MAMBench-defined (poisoned-retrieval proportion) | DSRM's own ASR_A/ASR_R/RR (same names as AgentPoison, different definitions — G-012) | MPBench's own ASR/RSR (structurally closest match to 4.2 vocabulary) |
| LoCoMo translation required | Yes — domain + retriever architecture | Yes — "reasoning trace" memory category invented | Yes — bridging content only, technique is domain-agnostic | Yes — req/resp schema + persistence-decision mismatch (Section 6) | Yes — "tool selection" reinterpreted as "claim selection" | Yes — 7 original domains → 1; 4 of 6 classes affected |
| V3-Hybrid incompatibility | Embedder architecture (BERT-hardcoded optimizer vs. Mem0's MiniLM) — UNVALIDATED | No persisted "reasoning memory" category exists | None identified — lowest-friction attack architecturally | No confirmed agent-driven persistence-decision step in Condition C | No tool-invocation mechanism exists | No compaction (C3) or skill-synthesis (C4) mechanism exists |
| Proposed adaptation | Extract domain-agnostic optimization core, target Mem0's real embedder | `reasoning_trace` content-type tag on ordinary memory | Reimplement technique against V3-Hybrid's real backend, not the OpenAI-hardcoded reference script | DIRECT_WRITE of poisoned content as ordinary ingested memory (disclosed fidelity compromise) | Reinterpret "tool selection" as "which memory content the agent treats as authoritative" | Scope to C2-applicable classes only; C1 REQUIRES_REVIEW (see Section 6); C3/C4 NOT_APPLICABLE |
| Current uncertainty | Embedder-load compatibility (Milestone 1, shared with DSRM white-box — G-013); optimization-core extractability | `reasoning_trace` metadata feasibility pending canonical-schema read (G-006) | `victim_target.json`'s "four pair types" unread (dossier gap) | Whether V3-Hybrid has any agent-driven persistence-decision step at all (Section 6) — likely **no** | Whether the black-box/white-box split transfers cleanly to a non-tool-invoking agent | Whether C1 classes have any real write-command surface in a QA agent (Section 6 — leaning NOT_APPLICABLE) |

Cells not resolvable from the six plans' own evidence are marked
`UNKNOWN`/`UNVALIDATED`/`REQUIRES_REVIEW` inline rather than guessed.

## 3. Shared Requirements

### 3.1 Memory content types

**Finding**: four attacks (FARMA, MemoryGraft, DSRM, MPBench) each need a
way to represent attacker-authored content that *looks like* a specific
memory genre (reasoning log, experience, settled claim, general fact) —
and each plan invented its own representation independently.

**Resolution**: a single shared metadata convention, **not** a Phase 3
canonical-schema change: every `PoisonArtifact` written to real memory
carries a `content_type` tag ∈ `{conversational_fact, reasoning_trace,
experience_precedent, general_fact}`, stored as ordinary metadata on the
existing `CanonicalMemoryRecord`. **This is contingent on G-006** (whether
`ledger.py`/`canonical.py` actually supports open metadata fields — not
independently verified by direct code read in any of the six plans; each
plan *assumed* this works). Classify: `SHARED_PHASE4_INFRASTRUCTURE`
(a Phase 4 convention over existing Phase 3 storage), pending verification.

### 3.2 Injection paths

Four paths are real and distinct, confirmed across the six plans:
`DIRECT_WRITE` (AgentPoison, FARMA, DSRM-base), `AGENT_MEDIATED_WRITE`
(DSRM-covert, MemoryGraft-as-claimed), `QUERY_SEQUENCE` (MINJA), and
`INDIRECT_INGESTION` as a source-side threat-model label that, on close
inspection (Section 6), **collapses into `DIRECT_WRITE` in practice** for
every attack examined, because V3-Hybrid has no agent-driven "decide what
to persist" step distinct from its ingestion pipeline. This is itself a
finding: **`INDIRECT_INGESTION` should remain in `attacker_capability`
(describing what the *original* threat model assumes) but the contract's
`injection_method` enum should not promise a MAMBench-side mechanism that
doesn't exist for any of the six attacks in practice.**

### 3.3 Attack lifecycle

The handoff's 12-state chain (`generated → injected → admitted → stored →
retrieved → selected → exposed → used → propagated → influenced →
detected → attributed`) is **not fully represented** in the 4.2 contract's
8-state ground-truth vocabulary. Specifically:

- `retrieved` and `selected` are collapsed into one `POISON_RETRIEVED`
  state, but V3-Hybrid's actual `hybrid_selection.py` has a real two-stage
  architecture (pool=20 → rerank → top-8) that every retrieval-dependent
  attack (five of six) needs distinguished — **Gap G-004**.
- `detected` and `attributed` have no explicit states at all — not
  currently needed by any of the six attacks' own success criteria (none
  target a live MAMBench-side defense), but worth a placeholder for 4.10's
  future negative-control/defense work rather than silently omitted.

### 3.4 Provenance

The existing ledger/event/versioning/provenance-graph/taint infrastructure
is **sufficient for `DIRECT_WRITE` attacks** (the adapter is the writer;
provenance is trivial to establish). It is **not sufficient as currently
described** for any attack that writes through the agent's own normal
path — **Gap G-003**, the most severe finding of this review (see Section 7).

### 3.5 Counterfactual evaluation

The existing masking mechanism is sufficient **per single memory record**,
regardless of injection path (it doesn't care how the memory got there).
It has **no defined protocol for multi-artifact attacks** (FARMA's
seed+amplification set, MemoryGraft's 10-record pool, MPBench's multi-
instance classes) — **Gap G-007**. The conservative resolution (call the
existing single-mask mechanism N times for per-record attribution, plus
once with all N masked jointly for aggregate effect) requires no Phase 3
code change if the underlying mechanism accepts an arbitrary memory-id
argument — this needs direct verification, not assumption.

## 4. Attack-Specific Requirements (must stay isolated in adapters)

These must **not** be generalized into shared Phase 4 infrastructure —
each is a genuine per-attack mechanism, not a shared need:

- **AgentPoison**: BERT-family gradient trigger optimization, MMD/variance
  fitness scoring. Stays entirely inside `AgentPoisonAdapter.generate()`.
- **FARMA**: precedent-count phrasing generator, store-evasion targeting
  logic, adaptive-paraphrase pass. Stays inside `FARMAAdapter`.
- **MINJA**: the specific bridging-step / indication-prompt / progressive-
  shortening sequence-construction algorithm. Stays inside `MINJAAdapter`
  — only its *output* (the query sequence) needs a shared representation
  (Section 7, G-001).
- **MemoryGraft**: the `semantic_targets` paraphrase-anchor selection
  heuristic. Stays inside `MemoryGraftAdapter` — only the resulting
  content's `content_type` tag is shared (Section 3.1).
- **DSRM**: the Self-Refine similarity-gated loop, CoT-Strategy 3-step
  generation, HotFlip white-box optimization. Stays inside `DSRMAdapter`.
- **MPBench**: the six-class taxonomy and domain/adversarial-goal
  vocabulary is **genuinely reusable as a shared classification/tagging
  system** across attacks (e.g. FARMA and MemoryGraft's outputs can both
  be labeled `false_precedent_insertion` for cross-attack comparison) —
  this is the one MPBench artifact that *should* generalize, distinct from
  any adapter mechanism.

## 5. V3-Hybrid Boundary Analysis

| Proposed change | Why needed | Changes victim semantics? | Phase 3 modification? | Recommendation |
|---|---|---:|---:|---|
| Isolated environments per reference attack (AgentPoison/MINJA/MemoryGraft) | Dependency conflicts (torch versions, Python versions) | No | No | Proceed — `SHARED_PHASE4_INFRASTRUCTURE` |
| New `load_db_locomo`-style loader for AgentPoison | Replace ASB-specific loaders | No | No | Proceed — `ATTACK_SPECIFIC_EXTENSION`, lives in adapter code |
| AgentPoison optimizer targets Mem0's real embedder object | Faithful trigger optimization against the real target | No (embedder is used, not altered) | No | Proceed — `ATTACK_INSTRUMENTATION`, pending Milestone 1 validation |
| `content_type` metadata tag on written memory | Shared representation for 4 attacks (Section 3.1) | No, if metadata is genuinely open (G-006) | Only if metadata is *not* currently open — then it is a real schema extension | Conditional — verify G-006 before proceeding; if schema extension needed, treat as `SHARED_PHASE4_INFRASTRUCTURE` added *alongside* the frozen schema, never replacing it |
| Attacker-authored-turn tagging at workload-construction time (G-003) | Let provenance/taint queries find agent-mediated poison | No — happens in Phase 4's input construction, before V3-Hybrid's unmodified functions run | No | Proceed — `SHARED_PHASE4_INFRASTRUCTURE`. **Key principle**: if a change lives in what data is fed *into* V3-Hybrid's existing, unmodified functions, it is not a victim modification, regardless of how attack-specific that data is. |
| Exposing `hybrid_selection.py`'s intermediate top-20 pool (G-004/G-005) | Distinguish `POISON_IN_CANDIDATE_POOL` from `POISON_SELECTED_TOP_K` | No — read-only observability, zero behavior change, **if** the pool is already computed internally | Only if an accessor/return-value needs adding | Proceed cautiously — classify as `ATTACK_INSTRUMENTATION` (read-only), not `VICTIM_AGENT_MODIFICATION`, but verify via direct code read before assuming the intermediate value is even computed as a distinct artifact |
| Multi-artifact joint counterfactual masking (G-007) | FARMA/MemoryGraft's multi-record attacks | No, if achieved by calling the existing single-mask mechanism N+1 times | Only if the mechanism cannot accept a list and needs a real code change | Proceed with the N-call approach first; escalate to a real Phase 3 extension only if that fails, and treat any such extension as additive, not a change to single-mask behavior |
| Multi-session/persistence campaign construct (G-008) | FARMA dilution test, MemoryGraft cross-session dominance | No — a campaign-orchestration concern, not agent behavior | Depends on whether V3-Hybrid's checkpoint/resume mechanism generalizes to deliberate multi-session continuity (unconfirmed) | `REQUIRES_REVIEW` before commitment — do not assume either way |
| Persisting Condition B's verify/revise reasoning into memory, to give FARMA/DSRM a real "reasoning memory" | Would make reasoning_trace attacks "more faithful" | **Yes — this would give V3-Hybrid a persistence behavior it never had** | **Yes** | **REJECT.** This is the clearest `VICTIM_AGENT_MODIFICATION` candidate surfaced by this review. Use the metadata-tag simulation (Section 3.1) instead — inject content that *reads* as a memory, never wire actual persistence into Condition B. |
| Building MPBench's C3 (compaction) or C4 (skill synthesis) mechanisms into V3-Hybrid | Would let MPBench's Salience-Driven Compaction Poisoning / Skill-Procedure Insertion classes run | **Yes — adds capabilities V3-Hybrid never had** | **Yes** | **REJECT — confirmed `NOT_APPLICABLE`.** Already correctly identified in the MPBench plan; reaffirmed here as the clearest example of the "do not force-fit" rule. |
| Building an "explicit write-command surface" for MPBench's C1 classes (Explicit/Conditional Command Insertion) in a QA agent | Would let C1 classes run against V3-Hybrid | **Likely yes — no such surface exists in a single-pass QA agent; inventing one gives the agent new command-interpretation behavior** | **Likely yes** | **Lean REJECT / `NOT_APPLICABLE`**, revising the MPBench plan's earlier "partial/secondary" framing to be more conservative — see Section 6 |

## 6. Major Design Decisions

### FARMA

`reasoning_trace` should be an ordinary `CanonicalMemoryRecord` plus a
shared `content_type` metadata tag (Section 3.1) — **not** a Phase 3
canonical-schema change, contingent on G-006's verification. Evaluated via
V3-Hybrid's existing 8-metric correctness stack (does the answer reflect
the forged content vs. gold evidence) plus a real counterfactual mask
before any influence claim.

### MINJA

Yes — query-only poisoning is representable **without** granting the
attacker any artificial memory-write capability: the adapter issues real
queries through V3-Hybrid's own unmodified interface, and whatever Mem0/
A-MEM would normally write in response is what gets written. No new
capability is granted to the attacker or the agent. The complete query
sequence must be represented as an ordered provenance structure
(`InjectionSequence`, G-001) linking each query to whatever memory/event it
produced — this is a contract gap (Section 7), not a conceptual problem.

### MemoryGraft

**On stricter review than the original plan gave it, MemoryGraft's
indirect-ingestion mechanism cannot be fully faithfully represented.** The
source mechanism depends on DataInterpreter's own judgment to persist a
"successful experience" — a decision process. V3-Hybrid's Condition C
ingestion (per everything established across all six plans) stores given
LoCoMo conversation turns; there is no confirmed agent-driven "was this
successful, should I remember it" judgment step for MAMBench to fool. The
original MemoryGraft plan's claim that writing through "the same real
ingestion path" is "a faithful match to the source mechanism" **is only
true of the write mechanism, not the decision mechanism it was meant to
exploit.** **Revised classification: `PARTIALLY_APPLICABLE`**, with the
deviation explicitly disclosed in reproducibility metadata (`fidelity_deviation`,
G-010) rather than presented as equivalent. If V3-Hybrid later gains a
genuine agent-driven persistence-decision step, this can be revisited —
but that would itself need to arise from a real, separately-justified
Phase 3/4 need, not be built merely to make this attack more faithful
(which would risk `VICTIM_AGENT_MODIFICATION`, Section 5).

### DSRM

The "tool selection → memory/claim selection" translation **is**
scientifically defensible as an `ATTACK_SURFACE_EXTENSION`, not a victim
modification: V3-Hybrid already selects which memory content to base its
answer on as ordinary QA behavior — DSRM's reconstruction targets that
existing decision, it does not add a new one. This is defensible **only**
if the `DomainTranslationRecord` is filled out honestly as
`mechanism_reinterpreted` (not `mechanism_preserved`), and any
`ATTACK_SUCCESS` claim is scoped to "the answer reflects the forged claim,"
never described as "the agent invoked a malicious tool" (which cannot
happen in a tool-less agent).

### MPBench

**Directly applicable**: Policy Conformant Fact Injection, False Precedent
Insertion (both channel C2 — matches V3-Hybrid's real ingestion-policy
write path). **Requires further review, leaning `NOT_APPLICABLE`**:
Explicit/Conditional Command Insertion (C1) — a single-pass conversational
QA agent has no user-facing "remember this" command channel the way a
personal assistant (OpenClaw/HERMES) does; inventing one risks
`VICTIM_AGENT_MODIFICATION` per Section 5. This revises the original
MPBench plan's softer "partial, secondary extension" framing downward.
**`NOT_APPLICABLE`, confirmed**: Salience-Driven Compaction Poisoning (C3,
no compaction mechanism), Skill-Procedure Insertion (C4, no skill-synthesis
mechanism) — do not build either merely for completeness.

### AgentPoison

Its white-box embedder requirement's compatibility with Mem0's real
`all-MiniLM-L6-v2` remains **genuinely unvalidated** (the plan's own
Milestone 1, not yet run). This should **stay an attack-specific adapter
concern**, not become a generalized "common embedder interface" in the 4.2
contract — no other attack needs gradient access to the embedder
(MemoryGraft only needs embeddings for retrieval, a much weaker
requirement). Generalizing this into the contract would be over-fitting the
schema to one attack's unusual need. **Gap G-013** notes this validation
is a shared prerequisite with DSRM's white-box variant and should be
tracked once, not twice.

## 7. Collective Gap Register

| ID | Gap / issue | Affected attacks | Severity | Category | Required? | Proposed resolution | Phase 3 impact |
|---|---|---|---|---|---|---|---|
| G-001 | No explicit multi-step/multi-artifact provenance structure (`InjectionSequence`) for query-sequence and amplification attacks | MINJA, FARMA, DSRM (SRM iteration logging) | HIGH | CONTRACT / PROVENANCE | Yes | Add an `InjectionSequence` type: an ordered list of `PoisonArtifact`/`InjectionEvent` references with dependency links | None — pure Phase 4 contract addition |
| G-002 | No shared `content_type` metadata convention for attacker-authored memory; four plans invented four different schemes independently | FARMA, MemoryGraft, DSRM, MPBench | HIGH | MEMORY | Yes | One shared enum + metadata field on `PoisonArtifact`/written records | None if metadata is open (pending G-006) |
| G-003 | No mechanism to mark agent-mediated-write-produced memory as attacker-originated for provenance/taint queries to find | MINJA, DSRM (covert), MemoryGraft (if ingestion path used) | **BLOCKING** | PROVENANCE | Yes | Attacker-authored-turn tagging applied at Phase 4's workload-construction step, consumed by the existing `attack_origin_lineage()` query | None — tagging happens before V3-Hybrid's unmodified functions run |
| G-004 | Ground-truth vocabulary collapses pool-membership vs. final-selection, which `hybrid_selection.py`'s real pool=20→top-8 architecture requires distinguishing | All Condition-C attacks (5 of 6) | HIGH | SELECTION / GROUND_TRUTH | Yes | Split `POISON_RETRIEVED` into `POISON_IN_CANDIDATE_POOL` and `POISON_SELECTED_TOP_K` | None if the pool is already computed internally (pending G-005) |
| G-005 | Unconfirmed whether `hybrid_selection.py` exposes the intermediate top-20 pool or only the final top-8 | Same as G-004 | MEDIUM | RETRIEVAL | To resolve G-004 | Direct code read before implementation | None (read-only); `ATTACK_INSTRUMENTATION` only if an accessor must be added |
| G-006 | Unconfirmed whether `CanonicalMemoryRecord` supports open metadata or has a fixed schema | Blocks G-002 | HIGH | MEMORY / PROVENANCE | To resolve G-002 | Direct code read of `canonical.py`/`ledger.py` before implementation | None expected (likely already open, per Phase 3's metadata-driven leakage scan) — **not yet verified** |
| G-007 | No multi-artifact/joint counterfactual masking protocol for N-record attacks | FARMA, MemoryGraft, MPBench | HIGH | COUNTERFACTUAL | Yes | Per-record + joint masking via repeated calls to the existing single-mask mechanism | None expected if the mechanism accepts an arbitrary memory-id argument (unverified) |
| G-008 | No campaign-level multi-session/persistence construct; `AttackRequest.workload` is singular | FARMA (dilution), MemoryGraft (cross-session dominance) | MEDIUM | PERSISTENCE | Yes | Add a `session_sequence` field: an ordered list of workload pools sharing one persistent memory store | `REQUIRES_REVIEW` — depends on whether V3-Hybrid's checkpoint/resume mechanism generalizes to this |
| G-009 | No `NOT_APPLICABLE`/`PARTIALLY_APPLICABLE` value in the contract's execution-status vocabulary | MPBench (C3/C4), any attack/foundation mismatch | MEDIUM | CONTRACT | Yes | Add both values alongside `SUCCESS`/`PARTIAL`/`FAILED` | None |
| G-010 | MemoryGraft's `DIRECT_WRITE`-approximating-`AGENT_MEDIATED_WRITE` choice is a fidelity compromise, previously under-disclosed | MemoryGraft | MEDIUM | INJECTION / REPRODUCIBILITY | Recommended | Add a `fidelity_deviation` field to reproducibility metadata whenever injection_method diverges from the source's actual mechanism | None |
| G-011 | No gating rule preventing a campaign from running against an `UNVALIDATED` `DomainTranslationRecord` | All six (process-level) | LOW | REPRODUCIBILITY | Recommended | `adapter.validate()` refuses (or requires explicit override) execution when `validation_status == UNVALIDATED` | None |
| G-012 | Multiple attacks reuse the name "ASR" for different underlying definitions (AgentPoison's ASR_A/ASR_R/RR vs. DSRM's identically-named-but-differently-scoped metrics vs. FARMA's ASR vs. MPBench's ASR/RSR) | AgentPoison, DSRM, FARMA, MPBench | MEDIUM | GROUND_TRUTH | Recommended | Mandate the 4.2 contract's own ground-truth vocabulary as the primary record for every adapter; source-paper metric names reported only as labeled secondary cross-references | None |
| G-013 | AgentPoison's embedder-compatibility spike (Milestone 1) is a shared prerequisite with DSRM's white-box variant but not tracked as a single shared gate | AgentPoison, DSRM (white-box) | LOW | OTHER | Recommended (bookkeeping) | Track once, referenced by both adapters' `validate()` | None |
| G-014 | Unverified whether attacker-tagged content could unexpectedly interact with Phase 3's existing leakage-scan or regression suite | All six | LOW | OTHER | Recommended | Run the existing Phase 3 regression suite against one representative poisoned campaign before treating tagging as safe | Verification only — no code change expected |

## 8. Required / Recommended / Optional Changes

### REQUIRED

- G-001 — `InjectionSequence` structure
- G-002 — shared `content_type` metadata convention (pending G-006)
- G-003 — attacker-authored-turn tagging for provenance discoverability
- G-004 — pool-vs-selection ground-truth state split (pending G-005)
- G-006 — verify canonical-schema metadata openness before relying on it
- G-007 — multi-artifact joint counterfactual masking protocol
- G-008 — multi-session campaign construct (pending Phase 3 checkpoint-
  mechanism review)
- G-009 — `NOT_APPLICABLE`/`PARTIALLY_APPLICABLE` status values

### RECOMMENDED

- G-010 — fidelity-deviation disclosure field
- G-011 — validation-status gating before campaign execution
- G-012 — mandated shared ground-truth vocabulary as the primary record

### OPTIONAL

- G-013 — shared-prerequisite bookkeeping across AgentPoison/DSRM
- G-014 — pre-emptive regression-suite verification pass

This list is deliberately not inflated: several plausible-sounding
additions (e.g. a full "reasoning-bearing memory" architecture change, a
generalized embedder-abstraction layer, building MPBench's C1/C3/C4
mechanisms) were considered and explicitly rejected in Sections 5–6 rather
than added here.

## 9. 4.2 Contract Stress Test

| Contract element | Required? | Sufficient? | Finding |
|---|---|---|---|
| `AttackRequest` core fields | Yes | Mostly | Missing `session_sequence` (G-008); `attacker_knowledge` needs a structured sub-field for "confirmed vs. assumed" per the matrix's many `UNKNOWN` cells |
| `DomainTranslationRecord` | Yes | Yes, with a process gap | Structure is sound; needs a validation-status gate before execution (G-011) |
| `AttackAdapter` interface (validate/prepare/generate/inject/execute/collect) | Yes | Yes | No changes needed — every one of the six adapters maps cleanly onto this lifecycle |
| `PoisonArtifact` | Yes | Partially | Needs the `content_type` tag (G-002) and a place to reference its position in an `InjectionSequence` (G-001) |
| `InjectionEvent` | Yes | Partially | Needs an `attacker_originated` flag/marker for agent-mediated writes (G-003) |
| `AttackResult` | Yes | Mostly | `execution_status` needs `NOT_APPLICABLE`/`PARTIALLY_APPLICABLE` (G-009); ground truth needs the pool/selection split (G-004) |
| Ground-truth vocabulary (8 states) | Yes | Partially | Needs the G-004 split; otherwise sound and correctly conservative about causal claims |
| Reproducibility metadata | Yes | Partially | Needs `fidelity_deviation` (G-010) |

**No missing top-level concept was found.** Every gap identified is an
addition to an existing structure, not a new structure the contract
entirely lacks (`InjectionSequence` is new, but it composes existing
`PoisonArtifact`/`InjectionEvent` types rather than replacing them).

## 10. Minimum Coherent Phase 4 Architecture

- **Shared infrastructure**: the 4.2 contract's `AttackRequest`/
  `AttackAdapter`/`AttackResult` triad, unchanged in shape; plus the eight
  REQUIRED additions from Section 8, layered onto the existing structure.
- **Attack adapter boundary**: exactly as designed in the six plans — each
  attack's algorithmic core (Section 4) stays inside its own adapter;
  nothing here changes that boundary.
- **Memory representation**: real `CanonicalMemoryRecord`s, tagged with a
  shared `content_type` metadata convention (G-002), pending schema
  verification (G-006) — no new memory storage system.
- **Injection representation**: four `injection_method` values
  (`DIRECT_WRITE`, `AGENT_MEDIATED_WRITE`, `QUERY_SEQUENCE`, with
  `INDIRECT_INGESTION` retained only as an `attacker_capability` label, not
  a distinct mechanism — Section 3.2), composed via `InjectionSequence`
  (G-001) for multi-step attacks.
- **Event/provenance integration**: existing Phase 3 ledgers/graph/taint
  machinery, reused unchanged, plus the attacker-authored-turn tagging
  convention (G-003) applied entirely within Phase 4's campaign-input
  construction — never inside V3-Hybrid's own functions.
- **Lifecycle tracking**: the ground-truth vocabulary, extended with the
  pool/selection split (G-004).
- **Ground truth**: the 4.2 vocabulary as the mandatory primary record for
  all six attacks (G-012), with source-paper metric names as secondary,
  clearly labeled references only.
- **Counterfactual evaluation**: the existing single-mask mechanism,
  invoked per-record and jointly for multi-artifact attacks (G-007) —
  no new measurement mechanism, just a calling convention.
- **Environment/reproducibility**: the existing `EnvironmentRecord`
  mechanism (Decision 3) plus `fidelity_deviation` disclosure (G-010) and
  validation-status gating (G-011).
- **Attack-specific modules**: six adapters, each owning its algorithmic
  core, unchanged from the six plans' own designs.
- **`NOT_APPLICABLE` handling**: an explicit status value (G-009), used
  for MPBench's C3/C4 (and likely C1, pending further review) — never
  worked around by inventing a victim capability.

## 11. Implementation Sequence

1. **Shared infrastructure changes**: resolve G-005/G-006 (direct code
   reads of `hybrid_selection.py` and `canonical.py`/`ledger.py` — no
   implementation, just verification); then implement G-001, G-002
   (pending G-006), G-003, G-004, G-009 as contract/convention additions.
2. **Contract finalization**: revise
   [PHASE4_4_2_COMMON_ATTACK_CONTRACT.md](PHASE4_4_2_COMMON_ATTACK_CONTRACT.md)
   with the REQUIRED changes from Section 8; re-run the Section 9 stress
   test against the revised schema before treating it as final.
3. **Lowest-risk attack implementation**: MINJA (query-only, no embedder
   risk, no persistence-decision mismatch) — arguably lower-risk than the
   original AgentPoison-first pilot ordering, given this review's findings.
4. **Higher-risk reconstructions**: FARMA, then DSRM (shares the embedder-
   compatibility gate with AgentPoison, G-013).
5. **Cross-attack validation**: AgentPoison (resolve Milestone 1 first),
   MemoryGraft (with the disclosed fidelity deviation), MPBench (C2 classes
   only, per Section 6).
6. **Campaign infrastructure**: multi-session support (G-008), once its
   Phase 3 checkpoint-mechanism dependency is resolved.
7. **Ground-truth expansion**: full 4.9 ground-truth stage, built on the
   now-extended vocabulary.
8. **Reproducibility**: full 4.11 stage, incorporating G-010/G-011.
9. **Freeze**: 4.12, only after all six adapters have passed their own
   contract re-validation milestones (already specified in each plan).

## 12. Explicit "Do Not Do Yet" List

- Do not implement any attack adapter.
- Do not clone any repository into the project.
- Do not write to any real or test memory store.
- Do not run any campaign.
- Do not modify `canonical.py`, `ledger.py`, `hybrid_selection.py`, or any
  other Phase 3 file — including for "read-only instrumentation" — until
  the direct code reads in Step 1 above have actually happened and the
  need is confirmed, not assumed.
- Do not freeze the 4.2 contract in its current form — it requires the
  REQUIRED revisions from Section 8 first.
- Do not build any V3-Hybrid capability rejected in Section 5 (persisted
  reasoning memory, compaction, skill synthesis, an explicit write-command
  surface) under any framing, including "just for one attack" or "behind a
  flag."
- Do not treat any attack's retrieval as proof of selection, exposure, use,
  or influence — the pool/selection split (G-004) and counterfactual
  requirements (G-007) remain binding on every future campaign.

## 13. Final Gate

**`4.2 REVISION REQUIRED`**

The six plans collectively demonstrate the contract's core shape is sound
— every attack maps onto `AttackRequest`/`AttackAdapter`/`AttackResult`
without forcing a shared mechanism, and no `VICTIM_AGENT_MODIFICATION` is
necessary to represent any of the six attacks faithfully. But eight
concrete, previously undiscovered gaps (Section 8, REQUIRED) must be
resolved in the contract and verified against actual Phase 3 code
(G-005, G-006) before any attack implementation begins. The mapping that
exists today is theoretically complete but not yet auditable,
provenance-preserving, or reproducible in the specific ways this review
identified — the standard this review was asked to hold it to.
