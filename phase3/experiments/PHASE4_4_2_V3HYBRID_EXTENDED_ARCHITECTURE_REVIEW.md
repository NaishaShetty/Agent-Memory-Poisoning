# Phase 4.2 — V3-Hybrid-Extended Architecture Review

Status: **ARCHITECTURAL REVIEW — planning only.** No frozen Phase 3 code
was modified. Three files were read directly to verify claims before
relying on them:
`phase3/evaluation/foundations/hybrid_selection.py`,
`phase3/evaluation/foundations/canonical.py`,
`phase3/evaluation/agent_runtime/counterfactual.py`. All three verifications
below are confirmed by that direct read, not assumed.

## Verified Phase 3 Facts (used throughout this review)

1. **`hybrid_selection.py`**: `RETRIEVAL_POOL_SIZE_N = 20`,
   `DEFAULT_TOP_K = 8`. `HybridSelectionResult` already returns **both**
   `selected` and `rejected` tuples as separate fields — the pool/selection
   distinction (G-004) is **already structurally available** in the
   function's return value; no accessor needs to be added.
2. **`canonical.py`**: `CanonicalMemoryRecord.content: Mapping[str, Any]` is
   confirmed open/unstructured. `content_type` (G-002) belongs **inside**
   `content`, as an ordinary key, never as a new top-level field on the
   record — the docstring is explicit that this module enforces the frozen
   schema's fields "verbatim" and "does not invent, rename, or extend any of
   these values."
3. **`counterfactual.py`**: `run_counterfactual_mask(baseline, masked_memory_id:
   str, config)` takes exactly **one** memory id and removes exactly one
   entry via `_remove_memory_content_entry`. **Correction to Revision 2**:
   repeated calls with different single ids produce N separate
   single-masked contexts, each missing only one memory — this is **not**
   equivalent to one joint intervention removing a set simultaneously.
   Genuine joint masking (G-007) requires a new Phase 4-side function that
   removes a *set* of ids from the agent-visible context in one pass before
   the single rerun — additive, external to the frozen function, never a
   modification of `run_counterfactual_mask` itself.
4. **Also directly relevant, from the Phase 3 handoff's own documentation**
   (not re-verified by code read in this pass, but load-bearing for
   Section 2 below): Mem0's real adapter is configured with **`infer=False`**
   — "no LLM call ever made inside Mem0's own `add()`." This means the
   canonical V3-Hybrid path has **deliberately disabled** Mem0's native
   salience/fact-extraction judgment (`infer=True` is a real, off-the-shelf
   Mem0 library mode Phase 3 chose not to use, for its own — different —
   scientific reasons: cleaner provenance, no internal-LLM confound).

## A. Current Contract Assessment (What Revision 2 Already Gets Right)

- The core `AttackRequest → AttackAdapter → PoisonArtifact/InjectionEvent →
  AttackResult` shape needed no structural change — every one of the six
  attacks maps onto it (confirmed again below under the new architecture
  lens).
- `InjectionSequence` (G-001) is architecture-agnostic and needs no change
  here — it represents step ordering, independent of which victim
  architecture executes the steps.
- `attacker_originated` (G-003) is likewise unaffected — it is a property
  of *how* a memory was written, not *which* victim architecture wrote it.
- Revision 2 correctly avoided inventing a parallel provenance system and
  correctly rejected persisting Condition B reasoning into memory as a
  `VICTIM_AGENT_MODIFICATION` — that conclusion is **reaffirmed**, not
  revisited, by this review.
- Revision 2's two biggest **errors**, both corrected in this review:
  (a) G-002 was described as "ordinary metadata on the existing
  `CanonicalMemoryRecord`" without specifying *where* — now corrected to
  live inside the already-open `content` mapping, per verified fact #2;
  (b) G-007 was described as achievable via "repeated calls" to the
  existing single-mask mechanism — now corrected, per verified fact #3, to
  require genuine new (additive) instrumentation.

## B. Extension Architecture Rationale

Revision 2 treated "no V3-Hybrid mechanism exists" as equivalent to
`NOT_APPLICABLE`. That conflates two genuinely different situations: an
attack mechanism V3-Hybrid *structurally cannot* support without inventing
new agent capabilities (MPBench C3/C4, C1), versus an attack mechanism that
depends on a **real, already-existing, already-implemented capability that
Phase 3 chose to disable** for its own separate reasons (Mem0's native
`infer=True` salience mode). The second case is not "inventing a
mechanism" — it is exercising a documented library feature under a new,
explicitly versioned experimental label, which is exactly the kind of
"generic, legitimate memory-agent capability with independent scientific
value" Section 3 requires. `V3-Hybrid-Extended` exists to hold that one
class of case, and only that class — not as a general license to build
whatever an attack needs.

## C. Extension Governance Rules

A proposed capability may become part of `V3-Hybrid-Extended` only if it
passes **all** of:

1. **Generic**: describable and motivatable without naming any specific
   attack.
2. **Attack-independent**: has a real research question it answers even in
   a fully benign (no-attack) setting.
3. **Minimal invention**: strongly preferred (not strictly required, but
   heavily weighted) if it activates an *existing, already-implemented*
   capability under a new label, rather than requiring new infrastructure
   built from scratch. This is the decisive factor distinguishing the
   accepted candidate below from the two rejected ones.
4. **Versioned and isolated**: has its own `capability_id`/version, never
   silently merged into canonical V3-Hybrid results.
5. **Fidelity honesty**: even when accepted, any remaining deviation from
   the source attack's actual mechanism must be disclosed, not smoothed
   over.

## D. Extension Candidates

### Candidate 1 — Generic Memory Compaction

```text
Extension: memory_compaction
Purpose: Consolidate accumulated memory when a context/storage limit is
  reached, mirroring how personal-assistant agents (OpenClaw/HERMES, per
  MPBench's own study) manage growing session history.
Legitimate agent capability represented: session/context-window
  summarization — a real, general memory-agent design pattern.
Why it is attack-independent (claimed): compaction behavior could in
  principle be studied for its effect on benign QA accuracy alone.
Attacks enabled: MPBench C3 (Salience-Driven Compaction Poisoning).
Existing architecture affected: none directly, BUT V3-Hybrid's Condition
  A/B/C process a FIXED, pre-selected top-8 evidence set per query — there
  is no growing, unbounded session history and no context-limit trigger
  condition anywhere in its actual design for compaction to legitimately
  attach to.
Frozen Phase 3 components affected: none directly, but the extension has
  no natural anchor point in V3-Hybrid's real pipeline — it would have to
  be built as a wholly invented session/history structure.
New Phase 4 components required: an entirely new multi-turn session
  model, a context-limit trigger, and a summarization step — none derived
  from anything V3-Hybrid already does.
Scientific risks: this candidate FAILS criterion 3 (minimal invention) —
  unlike the accepted candidate below, nothing here activates an existing
  capability; everything is invented. The "attack-independent" framing is
  true in the abstract but not true FOR V3-HYBRID specifically, since
  V3-Hybrid's architecture gives compaction no natural role to play absent
  the desire to run MPBench C3.
Fidelity implications: any resulting "compaction" mechanism would be a
  MAMBench-invented construct with no grounding in V3-Hybrid's real
  behavior — results would measure whether an invented layer can be
  poisoned, not whether V3-Hybrid itself is vulnerable to anything.
Decision: REJECT — NOT SCIENTIFICALLY JUSTIFIED.
```

### Candidate 2 — Generic Agent-Mediated (Salience-Based) Write

```text
Extension: agent_mediated_write
Purpose: Allow memory-write decisions to be driven by the memory
  foundation's own salience/fact-extraction judgment, rather than only
  ingesting raw conversation turns verbatim.
Legitimate agent capability represented: this is Mem0's own NATIVE,
  documented `infer=True` mode — a real, general design choice already
  implemented in the library MAMBench already depends on, not an invented
  mechanism. Comparing infer=True vs. infer=False memory-write behavior is
  itself a legitimate, attack-independent research question about
  memory-agent design tradeoffs (directly in the spirit of Phase 3's own
  H4 foundation-strengthening precedent of empirically comparing design
  choices).
Why it is attack-independent: the infer=True/infer=False comparison has
  real scientific value on its own — e.g. does salience-based writing
  change benign task accuracy, retrieval composition, or provenance
  clarity — independent of whether any attack ever runs against it.
Attacks enabled: MemoryGraft (materially improved, though still not full,
  fidelity — see below); optionally FARMA's and DSRM's secondary
  "covert-path" threat-model variants (not their primary, published/
  reconstructed mechanisms, which are DIRECT_WRITE and remain APPLICABLE
  under canonical V3-Hybrid without this extension).
Existing architecture affected: only the Mem0 adapter's own constructor
  argument (`infer=True` instead of Phase 3's chosen `infer=False`) — no
  new code, no new architecture, a pre-existing configuration switch used
  under a new, explicitly versioned experimental condition.
Frozen Phase 3 components affected: NONE. The canonical path keeps
  infer=False untouched; V3-Hybrid-Extended is an additional, separately
  versioned run of the identical adapter code with one different
  constructor argument.
New Phase 4 components required: a versioned `VictimArchitecture`
  configuration entry (`v3_hybrid_extended@agent_mediated_write@v1`)
  recording that this capability is active; no new adapter code.
Scientific risks: re-introduces exactly the confound Phase 3 deliberately
  eliminated (an internal Mem0 LLM call outside MAMBench's own controlled
  pipeline) — must be prominently disclosed as a known confound specific
  to V3-Hybrid-Extended results, never silently pooled with canonical
  V3-Hybrid results (governance rule 4/principle E).
Fidelity implications: PARTIAL even when active. Mem0's `infer=True`
  judges conversational-fact salience; MemoryGraft's source mechanism
  (DataInterpreter) judges CODE-EXECUTION-OUTCOME success. These are
  different judgment mechanisms in the same general class (an LLM decides
  what's worth keeping), not the same mechanism. Must be disclosed as
  PARTIALLY_APPLICABLE even under the extension, never claimed as fully
  faithful.
Decision: CONDITIONAL ACCEPT — the only candidate of the three that
  survives criterion 3 (minimal invention), because it activates an
  existing, already-implemented library capability under a new versioned
  label rather than inventing new infrastructure. Accept subject to: (a)
  explicit versioning, (b) never silently pooled with canonical results,
  (c) the confound disclosed prominently, (d) fidelity capped at
  PARTIALLY_APPLICABLE even when used, never claimed as full fidelity.
```

### Candidate 3 — Generic Experience → Procedure Transformation

```text
Extension: experience_to_procedure
Purpose: Synthesize a completed multi-step task execution into a reusable
  "procedure" memory loaded for future similar tasks (skill creation, as
  in HERMES).
Legitimate agent capability represented: procedural memory is a real,
  general category of agent memory.
Why it is attack-independent (claimed): skill-reuse could in principle be
  studied for its effect on benign task efficiency alone.
Attacks enabled: MPBench C4 (Skill-Procedure Insertion) only.
Existing architecture affected: none directly, BUT V3-Hybrid's Condition
  C is single-pass QA — there is no multi-step tool-based task execution,
  no "task completion" event, and no notion of a distillable procedure
  anywhere in its design.
Frozen Phase 3 components affected: none directly, but building this
  requires inventing an entirely new task structure (tool use,
  task-completion detection, skill synthesis) with zero grounding in
  V3-Hybrid's existing design — a LARGER invention than the rejected
  compaction candidate, not a smaller one.
New Phase 4 components required: a full tool-use/task-execution layer
  that does not exist in any form today.
Scientific risks: the clearest failure of criterion 3 among the three
  candidates — this is not "activating an existing capability," it is
  building an entirely new agent capability class from nothing, motivated
  by exactly one attack class.
Fidelity implications: any resulting "skill" memory would be a wholly
  MAMBench-invented construct with no relationship to HERMES's actual
  skill-synthesis mechanism.
Decision: REJECT — NOT SCIENTIFICALLY JUSTIFIED.
```

## E. Attack × Architecture Applicability Matrix

| Attack | Canonical V3-Hybrid | V3-Hybrid-Extended required? | Required capability | Applicability | Fidelity status | Reason |
|---|---|---|---|---|---|---|
| AgentPoison | Yes | No | — | `APPLICABLE` | Faithful (pending separate embedder-compatibility validation, unrelated to this review) | DIRECT_WRITE of the optimized trigger+demo pair needs no memory-write judgment |
| MINJA | Yes | No | — | `APPLICABLE` | Faithful | The bridging-sequence content is stored **verbatim** by Mem0 regardless of `infer` mode — MINJA's poisoning is in what the agent is fed, not in a salience judgment it must fool |
| FARMA | Yes (core: Algorithms 1–2 equivalent, DIRECT_WRITE) | No for the core reconstruction; optionally for an unpublished covert-path variant | `agent_mediated_write` (optional variant only) | `APPLICABLE` (core) | Faithful (core) | Source mechanism is adapter-mediated direct injection into the knowledge base, not an agent judgment MAMBench must fool |
| DSRM | Yes (Algorithms 1–2, DIRECT_WRITE, both black-box and white-box) | No for the published algorithms; optionally for the threat model's separately-mentioned covert path | `agent_mediated_write` (optional variant only) | `APPLICABLE` (core) | Faithful (core) | Same reasoning as FARMA — the reconstructable mechanism is adapter-mediated |
| MemoryGraft | Yes (adapter DIRECT_WRITE, per revised MemoryGraft plan) | Yes, for improved (still not full) fidelity | `agent_mediated_write` | `APPLICABLE` under canonical (disclosed deviation); `EXTENSION_REQUIRED` for improved fidelity | `PARTIALLY_APPLICABLE` under **both** paths | Canonical path substitutes a direct write for the source's persistence-decision judgment; the extended path substitutes a different (conversational-salience) judgment for the source's (code-execution-outcome) judgment — neither is the same mechanism |
| MPBench — C1 (Explicit/Conditional Command Insertion) | No | Would require inventing a write-command interface | `write_command_surface` (not proposed as a candidate — no independent justification found) | `NOT_APPLICABLE` | — | A single-pass QA agent has no user-facing command channel independent of conversation content; building one would be a `VICTIM_AGENT_MODIFICATION` with no justification beyond enabling C1 |
| MPBench — C2 (Policy Conformant Fact Injection / False Precedent Insertion) | Yes | No | — | `APPLICABLE` | Faithful | Matches V3-Hybrid's real ingestion-policy write path directly |
| MPBench — C3 (Salience-Driven Compaction Poisoning) | No | Candidate rejected (Section D-1) | `memory_compaction` (REJECTED) | `NOT_APPLICABLE` | — | No natural anchor point in V3-Hybrid's bounded, fixed-evidence-set architecture; would exist solely to enable C3 |
| MPBench — C4 (Skill-Procedure Insertion) | No | Candidate rejected (Section D-3) | `experience_to_procedure` (REJECTED) | `NOT_APPLICABLE` | — | Requires inventing tool-use/task-structure V3-Hybrid never had, solely to enable C4 |

**Verification against the given starting hypotheses**: AgentPoison
(Applicable) — confirmed. MINJA (Applicable via query-mediated write) —
confirmed, with the added clarification that it needs no salience
judgment, only verbatim ingestion. FARMA (reconstruction / possible
extension question) — **resolved**: applicable under canonical, no
extension needed for the core mechanism. DSRM (partial/reconstructed,
investigate required capabilities) — **resolved**: applicable under
canonical for both published algorithm variants; extension only relevant
to an optional, non-primary covert-path variant. MemoryGraft (partially
applicable; investigate legitimate persistence pathway) — **confirmed**,
and the investigated pathway (`agent_mediated_write`/Mem0 `infer=True`) is
real but only partially closes the fidelity gap, not fully. MPBench C1
(likely NOT_APPLICABLE) — **confirmed**. MPBench C3/C4 (investigate
generic extensions) — **investigated and both rejected**; NOT_APPLICABLE
confirmed, not converted to EXTENSION_REQUIRED.

## F. Contract Changes Required

Applied to `PHASE4_4_2_COMMON_ATTACK_CONTRACT.md` as **Revision 3** (see
that document): a formal `VictimArchitecture`/`ExtensionCapability` schema,
an `applicability` enum (`APPLICABLE` | `EXTENSION_REQUIRED` |
`PARTIALLY_APPLICABLE` | `NOT_APPLICABLE`) distinct from `execution_status`,
a `required_capabilities[]` field on `AttackRequest`, the G-002 correction
(content_type inside `content`), and the G-007 correction (genuine joint
masking as new additive instrumentation, not repeated single calls).

## G. Phase 4.2 Consistency Audit

| Item | Status after this review |
|---|---|
| `InjectionSequence` (G-001) | Unaffected — architecture-agnostic, carried forward unchanged |
| `content_type` (G-002) | **Corrected** — now specified as living inside `CanonicalMemoryRecord.content`, verified open |
| `attacker_originated` (G-003) | Unaffected — carried forward unchanged |
| Candidate pool vs. top-k (G-004) | **Strengthened** — verified `HybridSelectionResult` already returns both `selected` and `rejected`; no accessor addition needed, resolving G-005 as **no code change required** |
| Counterfactual semantics / joint masking (G-007) | **Corrected** — genuine new additive Phase 4 instrumentation required; repeated single-masking is explicitly documented as NOT equivalent |
| `session_sequence` (G-008) | Unaffected — carried forward, still `PENDING_VERIFICATION` re: Phase 3 checkpoint/resume generalization (not addressed by this review's scope) |
| Applicability (G-009 and beyond) | **Expanded** — from a two-value `execution_status` addition into a proper four-value `applicability` enum, evaluated at `validate()` time, upstream of and distinct from `execution_status` |
| Architecture identity | **New** — `VictimArchitecture` formalizes canonical V3-Hybrid vs. V3-Hybrid-Extended as explicitly versioned, never-silently-mixed identities |
| Extension requirements | **New** — `ExtensionCapability` with governance rules (Section C) |
| Fidelity deviation | Addressed inline per attack (Section E) rather than via the previously-deferred G-010 field; a dedicated field remains RECOMMENDED, not applied, consistent with Revision 2's scope discipline |
| Provenance | Unaffected — `attacker_originated`/existing ledger reuse still holds regardless of which victim architecture is used |
| Reproducibility | **Strengthened** — `VictimArchitecture.architecture_version` is now a mandatory reproducibility field: no result is interpretable without knowing which architecture produced it |

## H. Freeze Recommendation

**`4.2 REVISION REQUIRED`** is now resolved by this review's own Contract
Changes (Section F, applied as Revision 3). Once Revision 3 is written (see
the companion contract document), the remaining blockers are the same two
narrow verification items already known and now *partially* resolved:

- G-005 (pool exposure): **RESOLVED** — confirmed by direct code read,
  `HybridSelectionResult` already exposes both `selected` and `rejected`.
- G-006 (metadata openness): **RESOLVED** — confirmed by direct code read,
  `content` is open.
- G-007's masking-mechanism shape: **RESOLVED as "needs new code"** — the
  question of *whether* new code is needed is answered (yes); the new
  Phase 4-side joint-masking function itself is not yet written (correctly
  deferred — this review's mandate is architecture, not implementation).

Given G-005 and G-006 are now fully resolved, only G-007's actual (small,
additive, non-Phase-3-modifying) implementation remains outstanding before
attack execution — this is an implementation task for a later phase, not
an open architectural question. **The contract itself, once Revision 3 is
applied, is internally consistent and ready to freeze** — see the
companion contract document's own final gate statement.
