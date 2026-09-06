# Memory Foundation Strengthening Plan

Status: **PROPOSAL — NOT FROZEN**. This document is a plan for closing H.4–H.7 (and
retrofitting H.1–H.3 where a gap was found), written against the actual frozen state of
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

## 0. Why this plan exists

The frozen baseline campaign (LoCoMo/LongMemEval × Mem0/A-MEM) proved the pipeline runs
end to end and produces comparable metrics. It did not yet prove the four things a
poisoning-attribution paper actually needs to claim:

1. A memory's *exposure* to the reasoning layer and its *causal influence* on the answer
   are different facts, currently conflated under one `used` event.
2. Rejected candidates — a defense-success signal — are invisible in the event log.
3. Relationship edges (`equivalent_to`, `conflicts_with`, `superseded_by`) have no recorded
   detection provenance — they exist, but nothing says when/how they were established.
4. Foundation qualification is currently a one-time structural check, not a regression gate
   tied to a frozen fixture version.
5. The leakage audit (frozen, "no experimental exceptions") is currently a procedural
   checklist, not an enforced one.
6. Determinism inputs (embedding/rerank model version, seed) live in run config, not in the
   event ledger itself — so a ledger entry alone can't prove reproducibility.
7. There is no way to mark "this memory's lineage includes a confirmed attack" without
   mutating frozen history.

Each initiative below closes exactly one of these, in the same additive, non-destructive
style the project has used throughout.

## 1. Initiative A — Split `used` into exposure vs. causal influence

**Problem:** [relationship_schema.md:49](../schemas/relationship_schema.md) defines `used`
as "included in the reasoning context actually sent to the reasoning layer." That is
exposure. Phase 4's core claim — "an injected/poisoned memory affected agent behavior" —
needs causal influence, which exposure alone cannot establish (a model can ignore included
context, or an answer can be overdetermined by other memories).

**Decision:** Do not redefine `used` (would break H.2/H.3 compatibility and every existing
event). Add a new, additive event type, `used_causal`, emitted only for tasks where a
counterfactual check was run.

**Mechanism (foundation-independent by construction, per H.6's own goal):**
For a sampled subset of (task, selected-memory) pairs — not necessarily every pair, since
this is expensive — re-run reasoning with that one memory masked out of the selected set,
holding reasoning-layer config fixed exactly as [PHASE4_INTERFACE_REQUIREMENTS.md §2](PHASE4_INTERFACE_REQUIREMENTS.md)
already requires for clean-vs-manipulated comparisons. If the answer differs (by an
explicit, pre-registered diff criterion — exact-match, semantic-equivalence check, or
evidence-citation change), log `used_causal` with `counterfactual_answer_hash`,
`baseline_answer_hash`, and `diff_criterion`. If it does not differ, no `used_causal` event
is emitted — the memory remains `used` (exposed) but its causal status is explicitly
"not confirmed," never silently assumed either way.

**Schema addition to relationship_schema.md's event table:**

| Event | Meaning |
|---|---|
| `used_causal` | Counterfactual masking confirmed the answer causally depended on this memory |

Required fields beyond the base event fields (§3 of relationship_schema.md):
`counterfactual_answer_hash`, `baseline_answer_hash`, `diff_criterion`,
`masking_method` (e.g. `"selected_set_removal"`).

**Non-goal:** This does not attempt to run the counterfactual for every selected memory on
every task — cost-prohibitive at LongMemEval scale. Sampling strategy (which tasks, which
memories) is an experimental decision for the H.5 implementation stage, not frozen here.

## 2. Initiative B — Add the `rejected` event type the traceability contract already requires

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

**Why now, not later:** A foundation that cannot round-trip "this memory supersedes that
one" cleanly, and is used anyway for a supersession-based poisoning experiment, produces
results that measure adapter bugs, not attacks. This is a correctness precondition, not an
optimization.

## 5. Initiative E — Make the leakage audit executable, not procedural

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

## 6. Initiative F — Pin determinism inputs into the event ledger itself

**Problem:** [PHASE4_INTERFACE_REQUIREMENTS.md §2](PHASE4_INTERFACE_REQUIREMENTS.md)
requires that a clean run and a manipulated run be identical "except for the injected
manipulation," but the properties that would prove this (embedding model version, rerank
model version, retrieval `k`, sampling seed) currently live in a run-level experiment
manifest, not in the per-event record. A ledger entry alone cannot prove which model
versions produced it.

**Decision:** Extend the required fields for `retrieved` and `selected` events (only —
not every event type, to avoid bloating events that don't depend on these inputs) with:
`embedding_model_version`, `rerank_model_version` (if reranking is model-based),
`retrieval_k`, `sampling_seed` (if the retrieval/rerank mechanism is stochastic). This is
additive to the base event fields already required by
[relationship_schema.md §3](../schemas/relationship_schema.md) — `event_id`, `event_type`,
`memory_id`/`memory_ids`, `task_id`, `timestamp`, `actor`, `reason` — and does not modify
any existing frozen event's meaning.

**Why inline, not just in the manifest:** A manifest describes an intended run
configuration; it does not prove what a specific event actually used, and manifests get
separated from results over time (six months later, "which manifest produced this ledger"
is a lookup that can fail; "which model version is in this event" cannot).

## 7. Initiative G — Add `tainted_by` as a non-destructive attack-propagation relationship

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

## 8. Dataset-specific plan

| Dataset | Role (frozen, per DATASET_CAPABILITY_MATRIX.md) | What this plan adds for it |
|---|---|---|
| LoCoMo | Primary QA/reasoning | Full battery: Initiatives A (causal-use sampling), B, D, E, F apply directly — it already has gold evidence for `used_causal` diff criteria. |
| LongMemEval | Primary, larger-scale | Same as LoCoMo, but Initiative A's counterfactual sampling must be budget-aware — full re-run per selected memory is not affordable at this scale; sample size/selection strategy is an H.5 experimental decision, not fixed here. Initiative F's `retrieval_k` field is especially load-bearing here since this dataset is explicitly used to stress candidate-generation recall at scale — a silent `k` change between runs would be invisible without it. |
| MSC | Lifecycle/provenance/reuse, no task layer | No `used_causal` (no answer to diff against without a task layer) — Initiatives C, D, F, G apply directly; this is the dataset best suited to exercising Initiative G's taint-propagation query, since it's the primary lifecycle/reuse testbed. |
| Conversation Chronicles | Longitudinal lifecycle/provenance/reuse | Same profile as MSC. Its long-horizon structure makes it the best stress test for Initiative D's qualification battery (long derivation chains, many supersession events over time). |
| PerLTQA-ZH, ConvoMem (secondary) | Not yet role-assigned | No initiative here depends on these; do not extend this plan to them until they receive a role per [DATASET_CAPABILITY_MATRIX.md §4](DATASET_CAPABILITY_MATRIX.md)'s own deferral. |
| MemoryAgentBench, MemBench, MemoryArena (candidate-only) | Not adopted | Explicitly out of scope for this plan. If adopted later, they inherit whatever `fixture_set_version` (Initiative D) is current at that time — never grandfathered against an older qualification pass. |

## 9. Foundation-specific plan

| Foundation | Status | What this plan requires before poisoning use |
|---|---|---|
| Mem0 | Primary, baseline complete | Must re-pass Initiative D's frozen fixture battery under `fixture_set_version` v1 before any poisoning run cites current baseline numbers as its clean comparator. |
| A-MEM | Primary, baseline complete | Same as Mem0. |
| Graphiti | Primary, adapter exists, no baseline campaign run yet | Must complete Initiative D qualification *before* any baseline campaign is run against it, not after — unlike Mem0/A-MEM, there is no prior baseline to grandfather, so this is the first foundation to run the full new gate end to end, which makes it a good validation case for the gate itself. |
| Letta | Secondary/deferred | Remains deferred. Per the existing experimental spec: "do not claim conformance from adapter existence alone." Initiative D applies to Letta the moment it is un-deferred — no separate lighter-weight path. |

## 10. Sequencing

Dependencies, not arbitrary priority:

1. **Initiative B (`rejected` event)** and **Initiative C (`relationship_detected` event)**
   first — pure additive schema/event definitions, no dependency on anything else, and
   every later initiative's observability is stronger once these exist.
2. **Initiative F (determinism fields on `retrieved`/`selected`)** next — also additive,
   and Initiative A's counterfactual comparisons are only trustworthy once this is in
   place (a counterfactual re-run must itself be provably using the same model versions).
3. **Initiative E (executable leakage audit)** — independent of the others, but should
   land before any further campaign runs, given the contract's "no exceptions" severity.
4. **Initiative D (frozen qualification gate)** — depends on the fixture set already
   existing (it does); formalize the freeze and wire it as a gate before Graphiti's first
   baseline campaign (§9), so Graphiti becomes the first foundation qualified under the
   new process rather than grandfathered.
5. **Initiative A (`used_causal`)** — depends on F being in place; this is the most
   expensive initiative (requires re-running reasoning) and should be scoped/sampled
   deliberately, likely as its own H.5 sub-stage.
6. **Initiative G (`tainted_by` query)** — can be specified and frozen at any point (it's
   a read-only traversal contract) but has no consumer until Phase 4 exists; freezing it
   now is about giving Phase 4 a stable interface to build against, matching how
   [PHASE4_INTERFACE_REQUIREMENTS.md](PHASE4_INTERFACE_REQUIREMENTS.md) was frozen before
   any attack was implemented.

## 11. Readiness rubric (proposed, to replace open-ended "H.4-H.7 must establish...")

Define READY / READY WITH LIMITATIONS / NOT READY as a checklist evaluated independently
of raw retrieval-quality metrics (evidence precision, exact-answer correctness), per the
earlier discussion's point that these are retrieval-quality problems orthogonal to
substrate trustworthiness:

| Requirement | READY | READY WITH LIMITATIONS | NOT READY |
|---|---|---|---|
| Provenance (H.1-H.3) | Frozen, complete | — | — |
| Exposure vs. causal use distinguishable (Initiative A) | Implemented and run on ≥1 dataset per foundation | Implemented but only sampled, not exhaustive | Not implemented — `used` still conflates exposure and influence |
| Rejected-candidate traceability (Initiative B) | Implemented | — | Not implemented |
| Relationship detection provenance (Initiative C) | Implemented | Implemented for `superseded_by` only, not yet `equivalent_to`/`conflicts_with` | Not implemented |
| Foundation qualification gate (Initiative D) | Every foundation in use has passed the frozen, versioned battery | At least one foundation in use has passed; others pending | No foundation has passed a versioned gate |
| Leakage audit (Initiative E) | Both static and runtime checks implemented and passing | Only one layer implemented | Neither implemented, or manual-only |
| Determinism fields (Initiative F) | Present on all `retrieved`/`selected` events | Present in manifest only, not inline | Absent entirely |
| Attack-propagation interface (Initiative G) | Frozen and specified | Specified but not yet implemented as a callable query | Not specified |

A foundation/dataset pairing is only eligible for a poisoning experiment once every row is
at least "READY WITH LIMITATIONS," with the specific limitation documented in the
experiment manifest. This keeps foundation-perfectionism from blocking the actual research
question while still requiring every gap to be an explicit, written-down limitation rather
than a silent one.

## 12. What this plan does not decide

- The exact `diff_criterion`(s) for Initiative A's counterfactual comparison (exact-match
  vs. semantic-equivalence vs. evidence-citation change) — an H.5 experimental decision.
- The closed enum of `rejected` reasons (Initiative B) beyond the illustrative examples
  given — final enum is an H.5 implementation decision.
- The creation-policy thresholds that decide *when* to emit a `relationship_detected`
  event (Initiative C) — remains deferred exactly as memory_schema.md §8 already defers it.
- Sampling strategy/cost budget for Initiative A at LongMemEval scale.
- Whether PerLTQA-ZH/ConvoMem/candidate-only datasets ever receive a role — deferred to
  their own future capability-gap analysis per DATASET_CAPABILITY_MATRIX.md §4.
- Any Phase 4 attack or defense implementation — this plan only freezes the interfaces and
  observability Phase 4 will consume, per the existing non-scope boundary in
  [PHASE4_INTERFACE_REQUIREMENTS.md §4](PHASE4_INTERFACE_REQUIREMENTS.md).
