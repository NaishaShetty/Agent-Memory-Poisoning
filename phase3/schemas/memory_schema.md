# Memory Ontology & Schema (Narrative)

Status: **FROZEN DECISION** for the concepts and fields below; **NOT FROZEN** for creation
thresholds, equivalence thresholds, or algorithmic implementation (see
[PHASE3_CLEAN_AGENT_FOUNDATION_SPEC.md](../specification/PHASE3_CLEAN_AGENT_FOUNDATION_SPEC.md)
section 4 for the frozen/experimental ledger).

This document is the narrative companion to [memory_schema.json](memory_schema.json), which
is the machine-checkable field definition. If the two ever disagree, `memory_schema.json` is
authoritative for field names/types and this document is authoritative for semantics.

## 1. Why this exists

Phase 4 attack-origin attribution requires that every memory be reconstructable end to end:
`memory → source → parents → derivation → lifecycle → retrieval → selection → reasoning
influence`. That reconstruction is only possible if the concepts below are kept distinct and
never silently collapsed into one another, which is exactly the failure mode this document
guards against (see section 27 of the master spec, "Important Design Distinctions").

## 2. Memory identity

Every memory has a unique, stable, **immutable** identity (`memory_id`). Identity is assigned
once at creation and never reassigned, reused, or mutated — not even when a memory is
superseded or retired. Two memories are never merged into a single identity after creation
(see "Duplicate" below for how near-duplicates are handled instead: as a relationship, not a
merge).

## 3. Memory types

### 3.1 Foundation memory

A memory that originates directly from the frozen Phase 2 substrate (the Unified Memory
Record produced by Phase 1–2 preprocessing), or — once a creation policy is defined in a
later Phase 3 stage — a legitimate direct observation ingested under that policy. Foundation
memories have no `parent_ids`; their provenance is the Phase 2 UMR record itself.

### 3.2 Derived memory

A new, persistent memory generated from one or more existing memories:

```
A + B → C
```

`C` is derived and explicitly lists `A` and `B` as its `parent_ids`. Derived memory is
**not inherently bad** — historical Phase 3 evidence showed derived-memory competition could
causally reduce strict TSR in specific configurations, but also that suppressing derived
memory outright is not the answer. The clean agent represents derived memory explicitly (type,
parents, derivation event) so that its contribution and interaction effects can be measured,
not assumed.

Retrieving or transiently reasoning over `A` and `B` does **not** create `C`. A derived memory
must be produced through an explicit, logged memory-creation event (see
[relationship_schema.md](relationship_schema.md) and the lifecycle model in the master spec).

### 3.3 Equivalent memory

A separate memory object (distinct identity) that conveys materially equivalent information to
another memory. Equivalence is represented as an explicit `equivalent_to` relationship between
two independently-identified memories — equivalent memories are **never** collapsed into one
identity. This preserves the ability to later analyze whether multiple equivalent memories
represent genuinely independent corroboration or the same underlying fact restated (see
"Evidence independence" below).

### 3.4 Duplicate

A memory that would add no meaningful new information beyond an existing memory. Duplicates
are normally rejected at memory-creation time by the (not-yet-frozen) creation policy, rather
than created and later merged. Historical memory identities are never silently merged after
creation.

## 4. Four distinct concepts that must never collapse into one

| Concept | Question it answers |
|---|---|
| Identity | Is this the exact same memory object? |
| Equivalence | Does this convey materially the same information as another memory? |
| Evidence relevance | Is this memory relevant evidence for *this* task? |
| Evidence independence | Does this memory represent an independent source of corroboration, or a restatement of another selected memory? |

Provenance identity (which source/parents a memory has) is a fifth, related but distinct axis
— see [relationship_schema.md](relationship_schema.md).

A memory does not carry a permanent `is_evidence = true` flag. Evidence status is always the
result of `memory + task → evidence assessment`, performed at evaluation/selection time, never
baked into the memory record itself.

## 5. Parent / ancestor / descendant

- **Parent**: a direct source memory of a derived memory. A derived memory may have multiple
  parents:

  ```
  A ──┐
      ├──→ C
  B ──┘
  ```

- **Ancestor / descendant**: memories reachable by transitively following explicit parent
  edges. Ancestry is always computed by walking explicit `parent_ids` edges — it is **not**
  a precomputed "lineage family" set. The historical Phase 3 "giant lineage-family
  abstraction" (which could merge unrelated lineages through multi-parent derivation) is
  explicitly rejected; see [relationship_schema.md](relationship_schema.md) section 3.

## 6. Conflict and supersession

Conflicting memories are **preserved**, never silently overwritten:

```
A: "User prefers tea."
B: "User now prefers coffee."

A ── conflicts_with ── B
```

If `B` legitimately supersedes `A` (the creation policy determines this — not frozen in 3.1):

```
A ── superseded_by ── B
```

`A` transitions to a retired lifecycle state but is **never deleted**.

## 7. Core fields (see memory_schema.json for the authoritative field list)

Every memory record must eventually carry:

- `memory_id` — immutable unique identity.
- `memory_type` — `foundation | derived`.
- `content` — the memory's content payload.
- `source` — pointer to the Phase 2 UMR record (foundation) or derivation event (derived).
- `parent_ids` — explicit list, empty for foundation memories.
- `creation_event` — pointer to the logged creation event.
- `creation_timestamp` — when the memory was created.
- `lifecycle_state` — see the lifecycle model in the master spec (`CREATED | ACTIVE |
  RETIRED`).

## 8. What this document does not decide

The exact memory-creation policy (novelty thresholds, duplicate-detection thresholds,
semantic-equivalence thresholds) is explicitly **not frozen** here — it is listed as an
experimental decision for a later Phase 3 stage. See section 4 (frozen vs experimental
ledger) of the master specification.
