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
