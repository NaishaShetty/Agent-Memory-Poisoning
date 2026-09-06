# Relationship & Event Schema

Status: **FROZEN DECISION** for relationship/event types and their semantics; **NOT FROZEN**
for the algorithms that decide when to create a given relationship or event.

## 1. Purpose

Companion to [memory_schema.md](memory_schema.md). Where the memory schema defines what a
memory *is*, this document defines how memories *relate* to each other and *change over time*
— the substrate that makes traceability (see
[../contracts/TRACEABILITY_CONTRACT.md](../contracts/TRACEABILITY_CONTRACT.md)) possible.

## 2. Relationship types

| Relationship | Direction | Meaning | Cardinality |
|---|---|---|---|
| `parent_of` / `derived_from` | A → C | C was derived from A (inverse of `parent_ids`) | many-to-many |
| `equivalent_to` | A ↔ B | A and B convey materially equivalent information | symmetric, many-to-many |
| `conflicts_with` | A ↔ B | A and B assert incompatible information | symmetric, many-to-many |
| `superseded_by` | A → B | B legitimately supersedes A; A retires | one-to-one per memory (a memory has at most one superseder) |

### 2.1 Explicit edges only — no giant families

Ancestry and descendant sets are always computed by transitively walking `derived_from` edges
at query time:

```
A → C
B → C
C → D
```

`D`'s ancestors are `{C, A, B}`, computed by traversal — this is never precomputed into a
single merged "lineage family" object. The historical Phase 3 giant-family abstraction is
rejected specifically because it could merge unrelated lineages through shared multi-parent
derivation (e.g. two otherwise-unrelated facts both contributing to a common derived summary
would previously be pulled into the same family). Explicit pairwise edges avoid this by
construction: any traversal is scoped to the query that needs it, not baked into storage.

## 3. Event types

Every lifecycle-relevant occurrence is logged as an event, not encoded as a memory state:

| Event | Meaning |
|---|---|
| `created` | Memory was created (foundation ingestion or derivation) |
| `retrieved` | Memory was returned by candidate discovery for a task |
| `selected` | Memory was chosen by evidence selection for a task's reasoning context |
| `used` | Memory was included in the reasoning context actually sent to the reasoning layer |
| `derived` | Memory was used as a parent in producing a new derived memory |
| `superseded` | Memory was marked as superseded by another memory |
| `retired` | Memory transitioned to lifecycle_state=RETIRED |
| `rejected` | Memory was retrieved as a candidate but not selected for the reasoning context |
| `relationship_detected` | An `equivalent_to`/`conflicts_with`/`superseded_by` edge was established between two memories |

Every event must record, at minimum:

- `event_id` — unique identifier.
- `event_type` — one of the types above.
- `memory_id` — the memory the event concerns (or `memory_ids` for events touching several,
  e.g. `derived`, `conflicts_with` recognition).
- `task_id` — where applicable (`retrieved`, `selected`, `used` are always task-scoped).
- `timestamp` — ISO-8601 UTC.
- `actor` — which component/stage produced the event (e.g. `candidate_discovery`,
  `evidence_selection`, `creation_policy`).
- `reason` — short machine- or human-readable justification.
- `previous_state` / `new_state` — for state-changing events (`created`, `superseded`,
  `retired`).

This event log is the mechanism by which lifecycle transitions become traceable to source
event, timestamp, component, reason, and state change, per the lifecycle model in the master
specification.

### 3.1 `rejected` — required fields (Phase 3.3-H.4-BC)

Beyond the base fields above:

- `memory_id` — the rejected candidate (one memory per event).
- `task_id` — **required**. A rejection only has meaning relative to a specific
  candidate-selection decision for a specific task (mirrors the existing `retrieved`/
  `selected`/`used` requirement).
- `reason` — **not free text**. Must be exactly one of a closed enum:
  - `below_rerank_threshold`
  - `capacity_cut`
  - `deduplicated_against_selected_equivalent`
  - `retired_lifecycle_state`

  This enum may be extended later, but only via the same review discipline that froze it
  here — a silent addition is itself a schema change.

Emission point: the evidence-selection stage, once per retrieved candidate that does not
appear in that task's selected set. Invariant: every `retrieved` event for a task must
eventually be paired with exactly one of a `selected` event or a `rejected` event for the
same `(memory_id, task_id)` pair — never both, never neither. This is a reconstruction-time
consistency check (over a task's complete event history), not an append-time constraint,
since `retrieved` necessarily precedes the eventual selection decision.

Two `rejected` events for the same `(memory_id, task_id)` pair with different `reason`
values are treated as a collision (consistent with every other event type's collision
discipline), not a legitimate re-evaluation — a candidate is rejected from a given task's
selection decision for exactly one reason.

### 3.2 `relationship_detected` — required fields (Phase 3.3-H.4-BC)

Beyond the base fields above:

- `memory_ids` — the pair of memory identities involved (always exactly two, always
  distinct — a memory cannot be "detected as equivalent to itself").
  - For `relationship_type=superseded_by`: order is semantic — `(superseded, superseding)`.
  - For `relationship_type=equivalent_to`/`conflicts_with` (symmetric relationships):
    ordered lexicographically by `memory_id`, so two calls describing the same pair in
    either call-order produce the same recorded order — not an arbitrary
    call-order-dependent order.
- `relationship_type` — one of `equivalent_to`, `conflicts_with`, `superseded_by`.
- `mechanism` — how the relationship was detected (e.g. `embedding_similarity_threshold`,
  `llm_judge`, `manual_annotation`). Not a closed enum at this stage — the creation policy
  that would populate it (see `memory_schema.md` §8) is not yet frozen — but the field must
  exist so a future policy has somewhere to write to.
- `score` — the mechanism's own confidence/similarity score, if it produces one. Optional.
- `threshold` — the decision threshold applied, if applicable. Optional.

A `relationship_detected` event records the evidence that a relationship was recognized. It
is complementary to, not a replacement for, the accepted-linkage record for a decision
already made (e.g. H.3's `SupersessionRecord` for `superseded_by`): detection may occur
without the corresponding action ever being taken (e.g. a detected `superseded_by`
candidate that no caller ever acts on via `supersede_memory()`) — that is a legitimate,
permanently-recorded, diagnostically interesting fact, not an error.

Neither `rejected` nor `relationship_detected` carries a `config_fingerprint` field (that
requirement is scoped to `retrieved`/`selected` only, per the revised memory-foundation
strengthening plan's Initiative F — see §3.3, now implemented).

### 3.3 `retrieved`/`selected` — `config_fingerprint` (Phase 3.3-H.4-F)

Beyond the base fields above:

- `config_fingerprint` — **required** (non-empty string). The deterministic identity of
  the `RunConfigRecord` (embedding model + revision, reranker model + revision, retrieval
  `k`, sampling seed, retrieval/selection mechanism, adapter revision) that produced this
  event, per `MEMORY_FOUNDATION_STRENGTHENING_PLAN_REVISED.md` §6. The configuration itself
  is never duplicated inline on the event — only referenced by fingerprint, so two events
  produced under the same configuration cannot silently disagree about what that
  configuration was.

Forbidden (must be absent/`None`) for every other event type, `rejected` and
`relationship_detected` included — the revised plan states neither needs one.

Resolvability: a `config_fingerprint` must resolve to an existing configuration record.
Analogous to a `memory_id`'s existence requirement (checked eagerly, at append time, when
the event ledger has a configuration ledger to check against) rather than to the
`retrieved`/`selected`/`rejected` cross-event invariant (§3.1, which is necessarily
reconstruction-time) — a configuration record must exist (the run must have started)
before any event referencing it can legitimately be appended.

## 4. Relationship to Phase 4 attribution

Phase 4 attack-origin reconstruction (see
[../specification/PHASE4_INTERFACE_REQUIREMENTS.md](../specification/PHASE4_INTERFACE_REQUIREMENTS.md))
depends on this event log being complete and queryable: given a changed decision, the chain
`decision → used → selected → retrieved → memory → derived_from* → source` must be walkable
in reverse without gaps.

## 5. What this document does not decide

The exact conditions under which the (not-yet-implemented) creation policy emits
`equivalent_to`, `conflicts_with`, or `superseded_by` edges — including any similarity
thresholds — are experimental decisions for a later Phase 3 stage, not frozen here.
