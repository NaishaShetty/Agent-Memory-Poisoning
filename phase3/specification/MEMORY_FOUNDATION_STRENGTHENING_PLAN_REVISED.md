# Memory Foundation Strengthening Plan

Status: **PROPOSAL — NOT FROZEN**
**REVISED AFTER ARCHITECTURAL REVIEW**

This document is a plan for closing H.4–H.7 (and retrofitting H.1–H.3 where a gap was
found), written against the actual frozen state of
[PHASE3_3_H1_CANONICAL_MEMORY_LEDGER.md](PHASE3_3_H1_CANONICAL_MEMORY_LEDGER.md),
[PHASE3_3_H2_CANONICAL_EVENT_LEDGER.md](PHASE3_3_H2_CANONICAL_EVENT_LEDGER.md),
[PHASE3_3_H3_MEMORY_VERSIONING.md](PHASE3_3_H3_MEMORY_VERSIONING.md),
[../schemas/memory_schema.md](../schemas/memory_schema.md),
[../schemas/relationship_schema.md](../schemas/relationship_schema.md),
[../contracts/TRACEABILITY_CONTRACT.md](../contracts/TRACEABILITY_CONTRACT.md),
[../contracts/LEAKAGE_AND_VISIBILITY_CONTRACT.md](../contracts/LEAKAGE_AND_VISIBILITY_CONTRACT.md),
[PHASE4_INTERFACE_REQUIREMENTS.md](PHASE4_INTERFACE_REQUIREMENTS.md), and
[DATASET_CAPABILITY_MATRIX.md](DATASET_CAPABILITY_MATRIX.md). Nothing here modifies a
frozen file. Each initiative below is either (a) an additive schema/event extension, in the
same style H.3 used to extend H.1/H.2 without touching them, or (b) a new standing process
(a gate, an audit) layered on top of existing frozen behavior.

This is a **document/architecture revision only**. No code, schema, contract, adapter,
test, or experiment artifact is modified by this document. No H.1/H.2/H.3/G/G.1 content is
touched.

## Architectural Review Revisions

Architectural review identified three weaknesses in the original proposal. This revision
makes three corrections, and updates every section whose language depended on the
corrected concepts:

1. **Counterfactual influence is distinguished from stronger causal attribution.** The
   original Initiative A's `used_causal` event implied unrestricted causal responsibility
   ("the answer causally depended on this memory") from a single masking intervention,
   which the experiment design does not support. The event is renamed
   `counterfactually_influential` and defined strictly as interventional/counterfactual
   dependence under a fixed masking protocol — not causal proof.
2. **Determinism provenance is referenced through immutable configuration fingerprints
   rather than duplicated in every event.** The original Initiative F proposed embedding
   full configuration (embedding model version, rerank model version, `k`, seed) directly
   into every `retrieved`/`selected` event, creating redundancy and a consistency risk if
   two events for the same run ever disagreed. Events now carry a single
   `config_fingerprint` reference to an immutable, versioned configuration record.
3. **Poisoning readiness now has hard blockers that cannot be waived by "READY WITH
   LIMITATIONS."** The original rubric allowed any row to sit at "READY WITH LIMITATIONS"
   and still be poisoning-eligible. Some gaps (provenance, leakage, lifecycle
   reconstruction, exposure/use traceability, counterfactual measurement, attack
   attribution, qualification integrity, history reconstructability, interpretive
   ambiguity) are now hard blockers: unresolved, they make a pairing **not eligible for
   poisoning** regardless of how other rows score. Readiness is also now claim-specific,
   not a single global verdict.

Everything else in the original proposal — initiatives B, C, D (except the addition noted
in §4 below), E, G; the dataset and foundation plans; the sequencing rationale; the
non-scope boundaries — is preserved. Only the sections affected by the three corrections,
and sections that referenced the corrected language, are changed.

## 0. Why this plan exists

The frozen baseline campaign (LoCoMo/LongMemEval × Mem0/A-MEM) proved the pipeline runs
end to end and produces comparable metrics. It did not yet prove the things a
poisoning-attribution paper actually needs to claim:

1. A memory's *exposure* to the reasoning layer and its *counterfactual influence* on the
   answer are different facts, currently conflated under one `used` event. (Note: this is
   revised from the original "causal influence" framing — see Architectural Review
   Revisions, item 1.)
2. Rejected candidates — a defense-success signal — are invisible in the event log.
3. Relationship edges (`equivalent_to`, `conflicts_with`, `superseded_by`) have no recorded
   detection provenance — they exist, but nothing says when/how they were established.
4. Foundation qualification is currently a one-time structural check, not a regression gate
   tied to a frozen fixture version and a resolvable configuration.
5. The leakage audit (frozen, "no experimental exceptions") is currently a procedural
   checklist, not an enforced one.
6. Determinism inputs (embedding/rerank model version, seed) live in run config, with no
   reliable, resolvable link from a specific ledger event back to the exact configuration
   that produced it.
7. There is no way to mark "this memory's lineage includes a confirmed attack" without
   mutating frozen history.
8. Readiness has so far been framed as one global verdict per foundation/dataset pairing.
   A single verdict cannot express that a foundation may be sound for one scientific claim
   (e.g. lifecycle behavior) while lacking the instrumentation for a stronger one (e.g.
   attack-origin attribution).

Each initiative below closes exactly one of these, in the same additive, non-destructive
style the project has used throughout.

## 1. Initiative A — Distinguish exposure, counterfactual influence, and causal attribution

**Problem:** The original proposal defined `used` (exposure, unchanged — see
[relationship_schema.md:49](../schemas/relationship_schema.md)) and a new `used_causal`
event described as confirming "the answer causally depended on this memory." A difference
between a baseline answer and an answer after masking one memory establishes that the
output is *sensitive to that intervention*. It does not, by itself, establish unrestricted
causal responsibility — other memories, prompt structure, or model stochasticity could
also explain the difference, and a single masking experiment cannot rule those out. The
original wording overclaimed relative to what the experiment supports.

**Three concepts that must not collapse into one:**

| Concept | Question it answers | Established by |
|---|---|---|
| Exposure | Was this memory included in the reasoning context sent to the reasoning layer? | The existing `used` event (unchanged) |
| Counterfactual influence | Did masking/removing this memory, under the frozen intervention protocol, change the specified observable? | The masking experiment described below |
| Causal attribution | Was this memory the (or a) genuine cause of the answer, in a sense that survives confounds, alternative explanations, and repeated/ablation-robust testing? | **Not established by this experiment** — would require a stronger experimental design (e.g. systematic multi-memory ablation, repeated trials controlling for stochasticity, or a formal causal-inference framework) that is out of scope for this plan |

MAMBench will use the middle claim — counterfactual influence — as its operative notion of
"this memory mattered," unless and until a later experimental design provides stronger
causal identification. No document, report, or metric produced under this plan may
describe a `counterfactually_influential` event as proof of causal attribution.

**Decision:** Do not redefine `used` (would break H.2/H.3 compatibility and every existing
event). Add a new, additive event type. Per the review's preference for conservative
terminology where no compatibility reason favors the stronger name (this is a wholly new
event type, not a rename of something already in use), the event is named
`counterfactually_influential` rather than `used_causal`.

**Operational definition (the only definition this event carries):**

> "Counterfactual masking of this memory changed the specified observable under the
> benchmark's frozen intervention protocol."

This event must **not** be read, documented, or reported as meaning "this memory was
proven to be the unique or ultimate cause of the answer."

**Mechanism (foundation-independent by construction, per H.6's own goal):**
For a sampled subset of (task, selected-memory) pairs — not necessarily every pair, since
this is expensive — re-run reasoning with that one memory masked out of the selected set,
holding reasoning-layer config fixed exactly as [PHASE4_INTERFACE_REQUIREMENTS.md §2](PHASE4_INTERFACE_REQUIREMENTS.md)
already requires for clean-vs-manipulated comparisons. If the specified observable (e.g.
the answer, by an explicit, pre-registered diff criterion — exact-match,
semantic-equivalence check, or evidence-citation change) differs, log
`counterfactually_influential` with `counterfactual_answer_hash`, `baseline_answer_hash`,
and `diff_criterion`. If it does not differ, no event is emitted — the memory remains
`used` (exposed) but its counterfactual status is explicitly "not confirmed," never
silently assumed either way.

**Schema addition to relationship_schema.md's event table:**

| Event | Meaning |
|---|---|
| `counterfactually_influential` | Counterfactual masking of this memory, under the frozen intervention protocol, changed the specified observable. This is an interventional-dependence finding, not a causal-attribution finding. |

Required fields beyond the base event fields (§3 of relationship_schema.md):
`counterfactual_answer_hash`, `baseline_answer_hash`, `diff_criterion`,
`masking_method` (e.g. `"selected_set_removal"`), `config_fingerprint` (see Initiative F —
the counterfactual run and the baseline run must be provably identical except for the
masked memory, which requires both to reference the same resolvable configuration record).

**Non-goal:** This does not attempt to run the counterfactual for every selected memory on
every task — cost-prohibitive at LongMemEval scale. Sampling strategy (which tasks, which
memories) is an experimental decision for the H.5 implementation stage, not frozen here.
This initiative also does not attempt to establish causal attribution in the stronger
sense defined above — that remains an explicitly open research question, not a deliverable
of this plan.

## 2. Initiative B — Add the `rejected` event type the traceability contract already requires

*(Unchanged from the original proposal.)*

**Problem:** [TRACEABILITY_CONTRACT.md §5](../contracts/TRACEABILITY_CONTRACT.md) requires
traceability "for both accepted and rejected candidates where the rejection itself is
diagnostically relevant," but no `rejected` event type exists in
[relationship_schema.md §3](../schemas/relationship_schema.md). A candidate that is
retrieved but not selected currently vanishes from the log with no recorded reason.

**Decision:** Add `rejected` as a first-class event type, emitted by the evidence-selection
stage for every retrieved candidate that does not make it into the selected set.

| Event | Meaning |
|---|---|
| `rejected` | Memory was retrieved as a candidate but not selected for the reasoning context |

Required field: `reason`, drawn from a closed enum defined at the H.5 implementation stage
(e.g. `below_rerank_threshold`, `capacity_cut`, `deduplicated_against_selected_equivalent`,
`retired_lifecycle_state`). Closed enum, not free text, so rejection reasons are
aggregable across the full campaign.

**Why this matters for poisoning specifically:** "the attack memory was retrieved but
correctly rejected" is a defense-success story. Without this event, a defense that works
is indistinguishable from a defense that was never tested, because there is no record the
attack memory was ever a candidate.

## 3. Initiative C — Record detection provenance for relationship edges

*(Unchanged from the original proposal.)*

**Problem:** `equivalent_to`, `conflicts_with`, `superseded_by` are edges in
[relationship_schema.md §2](../schemas/relationship_schema.md), but nothing records *when*
or *by what mechanism* an edge was established. This is a reproducibility gap: a conflict
edge is currently unfalsifiable after the fact — there's no way to tell whether it was
detected at write-time by the (not-yet-frozen) creation policy or backfilled later during
analysis.

**Decision:** Add a `relationship_detected` event, emitted whenever any of the three edge
types is created, independent of the (still not-yet-frozen) policy that decides *whether*
to create one.

| Event | Meaning |
|---|---|
| `relationship_detected` | An `equivalent_to`/`conflicts_with`/`superseded_by` edge was established between two memories |

Required fields: `relationship_type`, `memory_ids` (the pair), `mechanism` (e.g.
`"embedding_similarity_threshold"`, `"llm_judge"`, `"manual_annotation"`), `score` (if
mechanism produces one), `threshold` (if applicable). Note `superseded_by`'s own
`SupersessionRecord` (H.3 §5.1) already carries the *linkage*; this event carries the
*detection provenance* that led to calling `supersede_memory()` in the first place — the
two are complementary, not redundant, exactly the way H.3 kept `CanonicalEvent` and
`SupersessionRecord` as separate, non-overlapping facts.

**Sequencing note:** This event type can be frozen now (it's pure logging), but it cannot
be *populated* until the creation policy (memory_schema.md §8, still not frozen) actually
exists — same dependency H.3 §18 already documented for `equivalent_to`/`conflicts_with`
evolution generally.

## 4. Initiative D — Promote the H.3 fixtures into a frozen, versioned qualification gate

**Problem:** `conflicting_memory/`, `equivalent_memory/`, `derived_memory/`, `lineage/`
fixtures currently establish one-time "structural conformance" per foundation. There is no
requirement that a foundation re-pass them after an adapter change, and no version pinning
tying a specific fixture set to a specific published result.

**Decision:**
1. Freeze the fixture set itself (`fixture_set_version`, e.g. `qualification_fixtures_v1`),
   stored alongside the frozen baseline metrics the same way LoCoMo/LongMemEval numbers are
   frozen in the experimental spec.
2. Every foundation adapter (`mem0_real_adapter.py`, `amem_real_adapter.py`,
   `graphiti_real_adapter.py`, and `letta_real_adapter.py` once promoted from
   deferred) must re-run the full fixture battery and pass before any experiment run
   citing that adapter is considered valid.
3. Each experiment manifest records which `fixture_set_version` + adapter commit/version
   the run was qualified against. A run whose adapter changed after its last qualification
   pass is flagged, not silently trusted.
4. Qualification asserts the *canonical ledger* reconstructs the expected relationship
   graph from each fixture — never that the foundation's own internal store did, since
   foundation internals are explicitly untrusted (per the existing "vendor IDs are aliases"
   principle).

**Addition required by Initiative F (configuration fingerprinting):** a qualification
result is itself a claim that depends on a specific configuration, not only on adapter
code. A qualification record must therefore identify all four of:

```
foundation qualification
  + adapter revision
  + fixture_set_version
  + config_fingerprint (the immutable configuration record active during that
    qualification run, per Initiative F)
```

so that a qualification record can always answer: "which foundation implementation,
fixture version, and deterministic configuration produced this qualification result?"
This does not duplicate configuration data — the qualification record references the same
`config_fingerprint` mechanism Initiative F defines for `retrieved`/`selected` events; it
is the same fingerprint concept applied to a different kind of record, not a second,
parallel configuration store.

**Why now, not later:** A foundation that cannot round-trip "this memory supersedes that
one" cleanly, and is used anyway for a supersession-based poisoning experiment, produces
results that measure adapter bugs, not attacks. This is a correctness precondition, not an
optimization.

## 5. Initiative E — Make the leakage audit executable, not procedural

*(Unchanged from the original proposal.)*

**Problem:** [LEAKAGE_AND_VISIBILITY_CONTRACT.md §3](../contracts/LEAKAGE_AND_VISIBILITY_CONTRACT.md)
is marked "no experimental exceptions" but is currently enforced by manual re-verification
"whenever the context-assembly code changes" — a process requirement, not a mechanism.

**Decision:** Two independent, automated enforcement layers, since the contract's own
severity ("no experimental exceptions") warrants defense in depth:

1. **Static layer:** a CI check that fails the build if any import/call path from
   `data/metadata/` or `data/reports/` reaches the reasoning-context assembly function.
   Implementable as an import-graph analysis (e.g. `ast`-based) scoped to the
   context-assembly module and its transitive callees.
2. **Runtime layer:** a per-task assertion that scans the fully-assembled context string
   sent to the reasoning layer for the task's own gold-answer substring(s) and gold
   evidence ID(s) before the call is made. A match raises immediately (fail-closed, not
   fail-open) rather than logging a warning — leakage found after the fact invalidates the
   run already in progress.

Both layers are additive tooling around the existing frozen context-assembly boundary in
[CLEAN_AGENT_INTERFACES.md §2.4](../contracts/CLEAN_AGENT_INTERFACES.md) — neither requires
modifying that frozen interface.

## 6. Initiative F — Determinism provenance via immutable configuration fingerprints

**Problem:** [PHASE4_INTERFACE_REQUIREMENTS.md §2](PHASE4_INTERFACE_REQUIREMENTS.md)
requires that a clean run and a manipulated run be identical "except for the injected
manipulation." The original proposal attempted to establish this by embedding the full
determinism configuration (`embedding_model_version`, `rerank_model_version`,
`retrieval_k`, `sampling_seed`) directly inside every `retrieved`/`selected` event. On
review, this creates redundancy across potentially thousands of events per run, a
consistency risk (two events from the same run could disagree if written incorrectly), and
unnecessary coupling between the event schema and run configuration.

**Decision — two-tier provenance, not duplication:**

```
EVENT
  ↓  (references, does not duplicate)
CONFIG FINGERPRINT
  ↓  (resolves to)
IMMUTABLE CONFIGURATION RECORD
```

1. **Configuration record (run-level/config-level provenance):** The complete
   deterministic configuration for a run lives in a single, immutable, versioned
   experiment/run configuration record — not duplicated per event. This record contains
   whatever parameters are necessary to reproduce the relevant retrieval/selection
   operation, including where applicable: embedding model, embedding model revision,
   reranker model, reranker revision, retrieval `k`, sampling seed, retrieval mechanism,
   selection mechanism, relevant implementation/adapter revision, and any other
   deterministic input already required by the experiment contract. Only parameters
   necessary to establish reproducibility of the relevant operation are included — this is
   not an invitation to record every possible runtime setting.
2. **Configuration fingerprint:** The configuration record is assigned a deterministic
   `config_fingerprint` (naming/derivation mechanism, e.g. content hash vs. sequential ID,
   is not frozen here — an H.5 implementation decision, unless existing architecture
   already mandates a specific scheme).
3. **Event-level provenance:** `retrieved` and `selected` events (only these two — not
   every event type, to avoid bloating events that don't depend on these inputs) carry a
   single additional required field: `config_fingerprint`, referencing the applicable
   configuration record. The event does not carry the configuration values themselves.

**Distinction this initiative enforces:** run-level/config-level provenance answers "what
exact configuration defined this run?" Event-level provenance answers "which configuration
produced this particular retrieval/selection event?" The event ledger is the auditable
*reference* point, never the authoritative *storage* location for the complete experiment
configuration — the experiment/run configuration record remains authoritative.

**Invariant:** Every `retrieved`/`selected` event must reference exactly one immutable
configuration fingerprint. The referenced configuration must be resolvable. If the
fingerprint cannot be resolved (the configuration record is missing, corrupted, or was
mutated after the run began), the event is not considered reproducibly interpretable —
this is treated as an observability gap on that event, not silently ignored. A
configuration record must itself be immutable once the experiment that references it
begins; no in-place edits to a configuration record already referenced by any emitted
event.

**Why a reference, not inline duplication:** A manifest/configuration record describes an
intended run configuration; duplicating it per event does not add reproducibility
strength beyond what a single resolvable reference already provides, and it introduces the
possibility that two events silently disagree about what configuration was active. A
resolvable fingerprint reference, backed by an immutable record, gives the same
reproducibility guarantee ("which model version produced this event is provable, not
assumed") without the duplication risk the original design carried.

## 7. Initiative G — Add `tainted_by` as a non-destructive attack-propagation relationship

*(Unchanged from the original proposal, with one clarifying addition at the end
distinguishing it from Initiative A's counterfactual-influence claim.)*

**Problem:** `derived_from` (relationship_schema.md §2) records provenance at creation
time and is immutable. When Phase 4 later confirms an ancestor memory was a successful
attack, there is no way to mark its descendants as attack-tainted without retroactively
editing frozen derivation edges — which the project's own immutability principle forbids.

**Decision:** Add `tainted_by` as a new relationship type, computed by traversal over
`derived_from` edges exactly the way ancestry/descendant sets already are
(relationship_schema.md §2.1 — "always computed... at query time," never precomputed into
a merged object). `tainted_by` is not itself a new stored edge; it is a query:
"given a set of confirmed-attack `memory_id`s (an input from Phase 4, not Phase 3), which
currently-active memories are reachable from them via `derived_from`." This requires no
schema mutation and no new persisted state in Phase 3 — only a documented, frozen query
shape that Phase 4 can rely on existing.

**Why this must be decided now rather than in Phase 4:** the traversal function's
signature and the definition of "reachable" (does a `conflicts_with` or `equivalent_to`
edge propagate taint, or only `derived_from`?) needs to be fixed before Phase 4 attack
implementations are written against it, the same way
[PHASE4_INTERFACE_REQUIREMENTS.md](PHASE4_INTERFACE_REQUIREMENTS.md) fixed the interface
boundary before any attack existed. **Decision: only `derived_from` propagates taint.**
`equivalent_to`/`conflicts_with` are symmetric relevance/contradiction facts, not
provenance facts, and conflating them with taint propagation would let an attack "infect"
an unrelated memory merely by superficial similarity — exactly the kind of collapse
[memory_schema.md §4](../schemas/memory_schema.md) warns against.

**Clarification (added on review):** `tainted_by` is a lineage-reachability fact, not a
counterfactual-influence or causal-attribution fact. A memory being `tainted_by` a
confirmed attack means it is *reachable* from that attack via recorded derivation — it does
not, by itself, mean the tainted memory was ever selected, exposed, or
counterfactually influential in any specific task's answer (Initiative A). The two facts
are complementary and must be reported separately: `tainted_by` answers "could this
memory have been affected," while `counterfactually_influential` answers "did masking this
specific memory change this specific answer." Reporting one as if it implies the other
would be exactly the kind of concept-collapse this plan otherwise guards against.

## 8. Dataset-specific plan

| Dataset | Role (frozen, per DATASET_CAPABILITY_MATRIX.md) | What this plan adds for it |
|---|---|---|
| LoCoMo | Primary QA/reasoning | Full battery: Initiatives A (counterfactual-influence sampling), B, D, E, F apply directly — it already has gold evidence for the `diff_criterion` used in counterfactual comparisons. Eligible for claim-specific poisoning readiness up to "counterfactual influence measured" (see §11); causal-attribution-level claims remain out of scope for all datasets per Initiative A. |
| LongMemEval | Primary, larger-scale | Same as LoCoMo, but Initiative A's counterfactual sampling must be budget-aware — full re-run per selected memory is not affordable at this scale; sample size/selection strategy is an H.5 experimental decision, not fixed here. Initiative F's `config_fingerprint` is especially load-bearing here since this dataset is explicitly used to stress candidate-generation recall at scale — a silent, unresolvable configuration change between runs would otherwise be invisible. |
| MSC | Lifecycle/provenance/reuse, no task layer | No `counterfactually_influential` events (no answer/observable to diff against without a task layer) — Initiatives C, D, F, G apply directly. Per claim-specific readiness (§11), MSC pairings can be eligible for lifecycle/provenance/propagation claims (including Initiative G's taint-propagation query) but are **not eligible** for any poisoning claim framed in terms of counterfactual answer influence, since the instrumentation for that claim does not apply here. |
| Conversation Chronicles | Longitudinal lifecycle/provenance/reuse | Same profile and same claim-specific restriction as MSC. Its long-horizon structure makes it the best stress test for Initiative D's qualification battery (long derivation chains, many supersession events over time). |
| PerLTQA-ZH, ConvoMem (secondary) | Not yet role-assigned | No initiative here depends on these; do not extend this plan to them until they receive a role per [DATASET_CAPABILITY_MATRIX.md §4](DATASET_CAPABILITY_MATRIX.md)'s own deferral. |
| MemoryAgentBench, MemBench, MemoryArena (candidate-only) | Not adopted | Explicitly out of scope for this plan. If adopted later, they inherit whatever `fixture_set_version` (Initiative D) is current at that time — never grandfathered against an older qualification pass. |

## 9. Foundation-specific plan

| Foundation | Status | What this plan requires before poisoning use |
|---|---|---|
| Mem0 | Primary, baseline complete | Must re-pass Initiative D's frozen fixture battery under `fixture_set_version` v1, with a resolvable `config_fingerprint` for that qualification run, before any poisoning run cites current baseline numbers as its clean comparator. |
| A-MEM | Primary, baseline complete | Same as Mem0. |
| Graphiti | Primary, adapter exists, no baseline campaign run yet | Must complete Initiative D qualification (adapter revision + fixture_set_version + config_fingerprint, all resolvable) *before* any baseline campaign is run against it, not after — unlike Mem0/A-MEM, there is no prior baseline to grandfather, so this is the first foundation to run the full new gate end to end, which makes it a good validation case for the gate itself. Per claim-specific readiness, Graphiti should be treated as eligible only for whichever claims its qualification and instrumentation actually cover — it does not inherit Mem0/A-MEM's claim-eligibility by similarity. |
| Letta | Secondary/deferred | Remains deferred. Per the existing experimental spec: "do not claim conformance from adapter existence alone." Initiative D applies to Letta the moment it is un-deferred — no separate lighter-weight path. |

## 10. Sequencing

Dependencies, not arbitrary priority:

1. **Initiative B (`rejected` event)** and **Initiative C (`relationship_detected` event)**
   first — pure additive schema/event definitions, no dependency on anything else, and
   every later initiative's observability is stronger once these exist.
2. **Initiative F (configuration-fingerprint mechanism for `retrieved`/`selected`)** next —
   also additive, and Initiative A's counterfactual comparisons are only trustworthy once
   this is in place (a counterfactual re-run must itself be provably referencing the same
   resolvable configuration record as its baseline).
3. **Initiative E (executable leakage audit)** — independent of the others, but should
   land before any further campaign runs, given the contract's "no exceptions" severity.
4. **Initiative D (frozen qualification gate, now including resolvable config-fingerprint
   identification per §4)** — depends on the fixture set already existing (it does) and on
   Initiative F's fingerprint mechanism existing (new dependency introduced by this
   revision); formalize the freeze and wire it as a gate before Graphiti's first baseline
   campaign (§9), so Graphiti becomes the first foundation qualified under the new process
   rather than grandfathered.
5. **Initiative A (`counterfactually_influential`)** — depends on F being in place; this is
   the most expensive initiative (requires re-running reasoning) and should be
   scoped/sampled deliberately, likely as its own H.5 sub-stage. Its claim scope (§11) must
   also be documented at the same time it is implemented, not after.
6. **Initiative G (`tainted_by` query)** — can be specified and frozen at any point (it's
   a read-only traversal contract) but has no consumer until Phase 4 exists; freezing it
   now is about giving Phase 4 a stable interface to build against, matching how
   [PHASE4_INTERFACE_REQUIREMENTS.md](PHASE4_INTERFACE_REQUIREMENTS.md) was frozen before
   any attack was implemented.

## 11. Readiness rubric

The original rubric used a single per-row READY / READY WITH LIMITATIONS / NOT READY
verdict, with any row at "READY WITH LIMITATIONS" still counting toward overall
eligibility. On review, this is too permissive: some gaps are not degradations in
confidence — they are conditions under which a poisoning claim cannot be interpreted at
all. The rubric is redesigned around **hard blockers**, **acceptable limitations**, and
**claim-specific eligibility**.

### 11.1 Hard blockers

The following, if unresolved, make a foundation/dataset pairing **not eligible for
poisoning** — regardless of how any other row scores. "READY WITH LIMITATIONS" cannot
override a hard blocker.

1. Provenance integrity (H.1–H.3, canonical identity and lineage).
2. Lifecycle/history integrity (immutable versioning, supersession, retirement — H.3).
3. Leakage prevention (Initiative E).
4. Memory exposure/use traceability (`used`, `rejected` — Initiatives B and the existing
   `used` event).
5. Counterfactual influence measurement (Initiative A), **wherever the specific claim being
   made is a counterfactual-influence or attack-impact claim** — not required for claims
   that don't depend on it (see §11.3).
6. Attack traceability / attack-origin attribution interfaces (Initiative G,
   [PHASE4_INTERFACE_REQUIREMENTS.md](PHASE4_INTERFACE_REQUIREMENTS.md)), wherever the
   specific claim depends on attribution.
7. Foundation qualification integrity (Initiative D — resolvable adapter revision +
   fixture_set_version + config_fingerprint).
8. Ability to reconstruct the relevant memory/event history for the claim being made.
9. Absence of unresolved ambiguity that could change the interpretation of an attack
   result (e.g. an unresolvable `config_fingerprint`, per Initiative F's invariant).

### 11.2 Acceptable limitations

A limitation may be documented and accepted — it does not have to be a hard blocker — only
if it demonstrably cannot invalidate the specific claim being made. Examples:

- Counterfactual sampling rather than exhaustive coverage (Initiative A), provided the
  sampling methodology is documented and the claim is scoped to the sampled cases.
- Computational budget constraints.
- Dataset-specific coverage limitations (e.g. MSC/Conversation Chronicles lacking a task
  layer — acceptable for lifecycle claims, a hard blocker for counterfactual-influence
  claims made against those datasets, per §8).
- A foundation not supporting a capability that is outside the specific experiment's scope.
- Non-critical observability gaps shown not to affect the claimed result.

A limitation is **not** acceptable merely because it is inconvenient to fix — it must be
explicitly shown, not assumed, that it cannot invalidate the particular claim.

### 11.3 Claim-specific readiness

Readiness is not a single global verdict. The question is always: "is this
foundation/dataset pairing ready to support *this specific* scientific claim?" A pairing
may be ready for one claim and not another. At minimum, distinguish:

| Claim | Requires (in addition to general provenance/lifecycle/leakage blockers) |
|---|---|
| Retrieval/selection quality (no poisoning claim) | Standard evaluation metrics only — no hard blockers beyond provenance/leakage. |
| Lifecycle / provenance / propagation behavior | Initiatives C, D, G. Does not require a task/answer layer — MSC/Conversation Chronicles eligible. |
| Counterfactual poisoning impact (this plan's operative "influence" claim) | Initiative A fully implemented and documented per §1, plus Initiative F (resolvable config fingerprints for both baseline and masked runs), plus a task/answer layer (LoCoMo/LongMemEval only). |
| Attack-origin attribution | Initiative G, [PHASE4_INTERFACE_REQUIREMENTS.md](PHASE4_INTERFACE_REQUIREMENTS.md) capabilities, plus everything counterfactual poisoning impact requires. |
| Causal attribution (in the stronger sense defined in §1) | **Not supported by any pairing under this plan.** No claim of this strength may be made until a future, separate experimental design is specified. |

A foundation/dataset pairing may therefore be, for example, "READY WITH LIMITATIONS" for
lifecycle testing while simultaneously "NOT ELIGIBLE FOR POISONING" for counterfactual
poisoning impact — these are not in tension; they are answers to two different questions.

### 11.4 Eligibility rule

Replacing the original "every row is at least READY WITH LIMITATIONS" rule:

> A foundation/dataset pairing is **POISONING ELIGIBLE for a given claim** if and only if:
>
> 1. All hard blockers (§11.1) relevant to that specific claim are resolved (PASS), and
> 2. every capability the claim depends on (per the claim-specific table in §11.3) is
>    qualified, and
> 3. any remaining limitations are explicitly documented and shown, not assumed, not to
>    invalidate that specific claim (§11.2).
>
> A pairing that fails any of these for a given claim is **NOT ELIGIBLE FOR POISONING**
> for that claim, even if it is "READY WITH LIMITATIONS" or fully ready for a different,
> less demanding claim (e.g. general lifecycle experimentation).

This keeps foundation-perfectionism from blocking claims the instrumentation genuinely
supports, while preventing a documented limitation on one axis from being read as blanket
permission for a claim it does not actually support.

## 12. What this plan does not decide

- The exact `diff_criterion`(s) for Initiative A's counterfactual comparison (exact-match
  vs. semantic-equivalence vs. evidence-citation change) — an H.5 experimental decision.
- The closed enum of `rejected` reasons (Initiative B) beyond the illustrative examples
  given — final enum is an H.5 implementation decision.
- The creation-policy thresholds that decide *when* to emit a `relationship_detected`
  event (Initiative C) — remains deferred exactly as memory_schema.md §8 already defers it.
- Sampling strategy/cost budget for Initiative A at LongMemEval scale.
- The exact derivation/naming scheme for `config_fingerprint` (Initiative F) — content
  hash, sequential ID, or another scheme — unless existing architecture already mandates
  one; this is an H.5 implementation decision, not frozen here.
- Whether a future, stronger experimental design could someday support causal attribution
  (§1) rather than counterfactual influence — left as an open research question, not
  addressed by this plan.
- Whether PerLTQA-ZH/ConvoMem/candidate-only datasets ever receive a role — deferred to
  their own future capability-gap analysis per DATASET_CAPABILITY_MATRIX.md §4.
- Any Phase 4 attack or defense implementation — this plan only freezes the interfaces and
  observability Phase 4 will consume, per the existing non-scope boundary in
  [PHASE4_INTERFACE_REQUIREMENTS.md §4](PHASE4_INTERFACE_REQUIREMENTS.md).

## Revision Review

### A — Counterfactual Influence

**What changed:** The `used_causal` event is renamed `counterfactually_influential` and
given a strict operational definition — "counterfactual masking of this memory, under the
frozen intervention protocol, changed the specified observable" — with an explicit
statement that this is not causal proof. A three-row table (exposure / counterfactual
influence / causal attribution) is introduced in Initiative A and referenced from the
dataset plan (§8), foundation plan (§9), and readiness rubric (§11.3) so the distinction is
consistent everywhere the concept is used, not just where it was first defined.

**Why:** A single masking intervention establishes sensitivity to that intervention, not
unrestricted causal responsibility. The original wording would have let a future report
claim more than the experiment design can support — exactly the kind of overclaim a
poisoning-attribution paper cannot survive peer review with.

### F — Determinism Provenance

**What changed:** Full configuration duplication inside every `retrieved`/`selected` event
is replaced with a single `config_fingerprint` reference field on those events, resolving
to one immutable, versioned configuration record that is the sole authoritative store of
the actual parameter values. An explicit invariant (every event must reference exactly one
resolvable fingerprint; unresolvable = not reproducibly interpretable) and an explicit
non-goal (the event ledger is never the authoritative configuration store) are added.
Initiative D is updated so qualification records use the same fingerprint mechanism rather
than a second, parallel configuration record.

**Why:** Duplicating full configuration per event scales badly, risks two events silently
disagreeing about what configuration produced them, and couples the event schema to run
configuration unnecessarily. A single resolvable reference gives the same reproducibility
guarantee without the duplication risk.

### Readiness Gate

**What changed:** The rubric is restructured around hard blockers (§11.1, cannot be waived
by "READY WITH LIMITATIONS"), acceptable limitations (§11.2, must be shown not to
invalidate the specific claim, not merely asserted), and claim-specific readiness (§11.3,
"ready for what" rather than one global verdict), with a revised eligibility rule (§11.4)
requiring all relevant hard blockers resolved and all claim-dependent capabilities
qualified before a pairing is poisoning-eligible for that claim.

**Why:** The original rule let any row sit at "READY WITH LIMITATIONS" and still count
toward overall eligibility, which would have permitted a poisoning claim to be made on top
of an unresolved leakage, provenance, or attribution gap as long as it was "documented."
Some gaps are not matters of degree — they invalidate the interpretability of the result
outright, and the rubric now says so explicitly.

### Compatibility

All three revisions are additive or reference-based, exactly like the original proposal's
own initiatives. No change requires modifying `CanonicalMemoryRecord`, `CanonicalEvent`,
`CanonicalMemoryLedger`, `CanonicalEventLedger`, `SupersessionRecord`, or any other H.1/H.2/
H.3-frozen type or file. `counterfactually_influential` is a new event type, not a
redefinition of `used`. `config_fingerprint` is a new optional-then-required field on two
event types, following the same additive pattern H.3 used when it added
`SupersessionRecord` as a new side-table rather than modifying `CanonicalEvent`. No G/G.1
content is referenced or altered by this revision.

### Implementation Impact

Proposal revision only; no implementation performed.

### Freeze Status

The proposal remains: **PROPOSAL — NOT FROZEN**.
