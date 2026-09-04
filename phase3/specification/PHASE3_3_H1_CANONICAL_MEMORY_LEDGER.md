# Phase 3.3-H.1 — Canonical Memory Ledger

Status: **COMPLETE** (architectural remediation stage; not an evaluation campaign).

## 1. Problem

`phase3/schemas/memory_schema.json` defines MAMBench's canonical memory ontology, but prior
to this stage nothing in the runtime enforced it. `MemoryFoundationAdapter.add_memory()`
accepts a bare `(memory_id, content, metadata)` triple with no structural relationship to
the schema's required fields (`memory_type`, `source`, `parent_ids`, `creation_event`,
`creation_timestamp`, `lifecycle_state`). In practice, a vendor foundation (Mem0/A-MEM/
Graphiti) was the only thing that ever durably held anything resembling a "memory" — the
canonical object existed only on paper (`memory_schema.md`), never as an authoritative,
independently-reconstructible runtime record. This is the audit's "Canonical memory object
is not authoritative at runtime" finding.

## 2. Current architecture (write path, as audited)

```
Source / Dataset row (e.g. LoCoMo memory_records.jsonl, LongMemEval haystack turn)
      |
      v
Inline dict construction at the call site
  ({"text": f"{role}: {content}"}, metadata={...})
      |
      v
MemoryFoundationAdapter.add_memory(memory_id, content, metadata)   <-- abstract interface,
      |                                                                 phase3/evaluation/foundations/adapter.py
      v
Concrete adapter (RealMem0Adapter / RealAMemAdapter / RealGraphitiAdapter / RealLettaAdapter
  or MockMem0Adapter / MockAMemAdapter / MockGraphitiAdapter / MockLettaAdapter)
      |
      v
Vendor store (mem0ai / A-mem-sys / graphiti-core / Letta, or an in-memory mock)
```

Per-stage properties found during the audit:

| Stage | Object type | Identity | Content | Metadata | Provenance | Timestamp | Lifecycle | Parentage | Vendor ID |
|---|---|---|---|---|---|---|---|---|---|
| Dataset row | dataset-native dict | dataset's own id (e.g. LoCoMo `memory_id`) | free text | dataset fields | implicit (dataset name) | not modeled | not modeled | not modeled | n/a |
| Call site | bare dict | caller-chosen `memory_id` (often = dataset id) | `{"text": ...}` | ad hoc per call site | not modeled | not modeled | not modeled | not modeled | n/a |
| `add_memory()` | positional args | `Optional[str]` | `Mapping[str, Any]` | `Optional[Mapping]` | none | none | none | none | n/a |
| Concrete adapter | foundation-native | vendor's own id (Mem0 always mints its own UUID; Graphiti/A-MEM honor a caller-supplied id) | foundation-transformed | foundation-stored verbatim (Mem0) or partially (A-MEM/Graphiti) | none | foundation-native, if any | none (A-MEM's `MemoryNote` has a `context`/`tags`, not a lifecycle state) | A-MEM performs its own "dynamic linking," not the schema's `parent_ids` | assigned here |
| Vendor store | vendor-native | vendor id | vendor-native | vendor-native | none | vendor-native | none | none | authoritative-by-default (the bug) |

Every current caller of `add_memory()` (found by repo-wide search, not assumed):

- `phase3/evaluation/agent_runtime/campaign_formal_runner.py` — **actively running** the
  3.3-G.1 A-MEM × LongMemEval N=120 campaign at the time this stage was implemented (three
  worker processes, verified via `Get-CimInstance Win32_Process`). **Left untouched.**
- `phase3/evaluation/agent_runtime/campaign_runner.py` (superseded, non-active).
- `phase3/evaluation/agent_runtime/pilot_amem_locomo.py`, `pilot_mem0_locomo.py`,
  `pilot_mem0_locomo_resolved.py`, `pilot_secondary_datasets.py` (historical pilots).
- `phase3/evaluation/agent_runtime/campaign_formal_amem_probe.py`.
- Test files exercising the adapter contract directly
  (`test_foundation_architecture_h3.py`, `test_foundation_conformance_h4.py`,
  `test_cross_foundation_identity.py`, `test_identity_bridge.py`,
  `test_trace_identity_integration.py`, `test_agent_runtime.py`,
  `test_dataset_integration_j3.py`, `test_campaign_formal_checkpoint.py`).

Every current implementation of `MemoryFoundationAdapter` (found by repo-wide search, not
assumed): `RealMem0Adapter`, `RealAMemAdapter`, `RealGraphitiAdapter`, `RealLettaAdapter`
(`foundations_real/`), and `MockMem0Adapter`, `MockAMemAdapter`, `MockGraphitiAdapter`,
`MockLettaAdapter` (`foundations/mocks/`). All eight implement the identical
`add_memory(memory_id, content, metadata=None) -> FoundationField` signature, and all eight
return `value` as a mapping carrying a `"memory_id"` key on success (verified directly by
reading each implementation's `add_memory` body — see section 6).

An existing identity bridge (`phase3/evaluation/agent_runtime/identity.py`, Phase 3.3-C/D)
already resolves `FOUNDATION_MEMORY_ID -> SOURCE_MEMORY_ID` via two empirically-verified
strategies (`METADATA_LOOKUP` for Mem0, `DIRECT_ASSIGNMENT` for Graphiti/A-MEM). This module
is reused, not duplicated — see section 5.

## 3. Target architecture

```
Source / Dataset
      |
      v
CanonicalMemoryRecord            (phase3/evaluation/foundations/canonical.py)
      |
      +----------------------------------+
      |                                  |
      v                                  v
CanonicalMemoryLedger              write_canonical_memory()  (phase3/evaluation/foundations/canonical_write.py)
(phase3/evaluation/foundations/          |  translates the canonical record into the
 ledger.py)                              |  EXISTING add_memory(memory_id, content, metadata)
      ^                                  v
      |                            Foundation Adapter (unmodified)
      +---- alias table -----------------|
                                          v
                                   Vendor Memory Store (Mem0 / A-MEM / Graphiti / Letta)
```

`CanonicalMemoryLedger` is the authoritative, foundation-independent store. A vendor's own
id is recorded as an **alias**, never as a substitute canonical identity.

## 4. `CanonicalMemoryRecord`

`phase3/evaluation/foundations/canonical.py` — a frozen `dataclass` whose fields are exactly
`memory_schema.json`'s: `memory_id`, `memory_type`, `content`, `source`, `parent_ids`,
`creation_event`, `creation_timestamp`, `lifecycle_state`, plus the optional
`equivalent_to`/`conflicts_with`/`superseded_by`. No speculative field was added.
Construction validates every required-ness/enum/cross-field constraint the schema states
(e.g. `parent_ids` empty iff `memory_type == "foundation"`) and raises
`CanonicalValidationError` on any violation — invalid records cannot be constructed at all,
so "validated at the write boundary" is enforced by the type itself, not by a separate
caller-remembered check.

Construction additionally runs `content` through the existing
`foundations.security.enforce_foundation_call_boundary` (itself a thin, verbatim reuse of
`security.leakage.validate_no_leakage`) — no evaluator-only/gold-shaped key can enter a
canonical record's content, by construction.

## 5. Identity ownership

**MAMBench owns canonical memory identity.** `CanonicalMemoryRecord.memory_id` is supplied
by the caller (typically the pre-existing dataset-native id, e.g. LoCoMo's `memory_id` —
this preserves compatibility with the existing `identity.py` bridge and with gold-evidence
matching logic elsewhere in the framework, which already keys off this same id) and is
validated for well-formedness by the dataclass; **uniqueness/collision** is enforced by
`CanonicalMemoryLedger.put()` (section 6), which is the true point of "MAMBench decides
whether this id is new, a legitimate idempotent rewrite, or a collision" — not a hash
function or a minting scheme. This stage does not introduce a competing ID-minting scheme
(e.g. `MAM-MEM-000001`) because doing so would fork the identity space away from every
existing dataset-driven id already threaded through retrieval/evaluation.

Vendor identity is a **strict alias**: `CanonicalMemoryLedger`'s alias table maps
`(memory_id) -> {foundation_name: foundation_memory_id}` in the forward direction and
`(foundation_name, foundation_memory_id) -> memory_id` in reverse. A canonical record's
`memory_id` field is never overwritten by a vendor-returned id, and the ledger's `put()`
never even looks at what a foundation would return — the canonical write happens strictly
*before* any foundation call (see section 7).

The existing `identity.py` bridge (`resolve_source_identity` / `resolve_via_direct_assignment`
/ `verify_collision_safety`) is **not duplicated**. It solves a different, complementary
problem: reading a *dataset's* source identity back out of a *foundation's* stored metadata,
after the fact, without a canonical ledger's help. H.1's alias table instead records, at
write time, the mapping this benchmark itself already knows precisely because it did the
canonical write — the two are compatible (both key off the same underlying identifiers) and
`write_canonical_memory()`'s foundation-metadata construction (section 8) populates
`metadata["source_memory_id"]` so `identity.py`'s `METADATA_LOOKUP` strategy keeps working
unchanged for any caller not yet migrated to the ledger.

## 6. `CanonicalMemoryLedger`

`phase3/evaluation/foundations/ledger.py`. Storage: two append-only JSONL files per
`storage_dir` (`records.jsonl`, `aliases.jsonl`); the in-memory index is a pure fold over
both files, in order, on construction — this is what makes "canonical ledger reload" and
"canonical reconstruction" provable rather than assumed (see the H.1 test suite).

Operations: `put`, `get`, `exists`, `list_records`, `set_alias`, `get_aliases`,
`resolve_alias`. No update/delete/lifecycle-transition operation exists yet — out of scope
(section 12).

**Collision policy:** `put()` on an existing `memory_id` compares
`CanonicalMemoryRecord.identity_fields()` (every schema field except nothing — the full
record). Identical → `PUT_IDEMPOTENT` (documented, tested no-op). Different →
`CanonicalCollisionError`, raised immediately, never caught internally. The pre-existing
record is left untouched either way.

**Concurrency — explicit limitation:** single-process, single-writer. Each write is one
`open(..., "a")` / `write()` / `flush()` / `os.fsync()` per JSONL line, so a crash mid-run
loses at most an in-flight, not-yet-durable write — never corrupts a prior line. There is no
cross-process file lock. This is a stated H.1 limitation (section 12), not a defect: no
caller adopts the ledger in this stage (section 9), so nothing exercises multi-process
contention against it yet.

## 7. Authoritative write order

`phase3/evaluation/foundations/canonical_write.py::write_canonical_memory()`:

1. `ledger.put(record)` — canonical write. Raises `CanonicalCollisionError` immediately on a
   genuine collision (never caught by this function).
2. If no `foundation` was supplied: return `CANONICAL_ONLY`. (A legitimate first-class
   outcome, not a degraded case.)
3. `foundation.add_memory(memory_id=record.memory_id, content=..., metadata=...)` — the
   **existing, unmodified** adapter call.
4. If the foundation call did not report `AVAILABLE`/`PARTIAL`: return `FOUNDATION_FAILED`.
   The canonical record from step 1 is already durable — this is invariant 6.
5. Extract the vendor id from the foundation's returned value (`value["memory_id"]` — the
   convention every one of the eight existing adapters follows, verified directly). If
   absent, or if no `foundation_name` was given: return `ALIAS_PERSISTENCE_FAILED`.
6. `ledger.set_alias(record.memory_id, foundation_name, vendor_id)`. On failure (e.g. the
   canonical record vanished between steps 1 and 6 in some future concurrent-writer
   scenario): return `ALIAS_PERSISTENCE_FAILED`.
7. Otherwise return `CANONICAL_AND_FOUNDATION` with the resolved `foundation_memory_id`.

### Old path (unchanged, still in use by every existing caller)

```
caller constructs (memory_id, content, metadata) inline
      -> foundation.add_memory(memory_id, content, metadata)
```

### New, recommended path

```
caller constructs CanonicalMemoryRecord (validated, schema-shaped)
      -> write_canonical_memory(ledger, record, foundation=..., foundation_name=...)
```

No existing call site was migrated to the new path in this stage — see section 9 for why,
and section 13 for what that means going forward.

## 8. Failure semantics / consistency model

Four explicit, mutually exclusive statuses (`canonical_write.WRITE_STATUSES`):

| Status | Canonical record | Foundation write | Alias |
|---|---|---|---|
| `CANONICAL_ONLY` | persisted | not attempted (no foundation given) | n/a |
| `CANONICAL_AND_FOUNDATION` | persisted | succeeded | persisted |
| `FOUNDATION_FAILED` | persisted | failed | not attempted |
| `ALIAS_PERSISTENCE_FAILED` | persisted | succeeded | failed / not recorded |

There is no fake distributed transaction: a `CANONICAL_AND_FOUNDATION` result is not a
"two-phase commit," it is "both steps happened to succeed, in this fixed order, and are
independently durable." No status ever claims a fully successful write when any component
step did not actually succeed.

## 9. Foundation adapter migration status

No `MemoryFoundationAdapter` implementation file was modified. `write_canonical_memory()`
is an explicit, documented **transitional compatibility wrapper**: it takes a
`CanonicalMemoryRecord` as its authoritative input (the mission's actual architectural
requirement) and translates it into the existing `add_memory(memory_id, content, metadata)`
call underneath, so every adapter already "speaks" the canonical contract with zero
modification.

| Foundation | Adapter file touched? | Status |
|---|---|---|
| Mem0 (real) | No | Compatible via transitional wrapper |
| Mem0 (mock) | No | Compatible via transitional wrapper; exercised directly in H.1 tests |
| A-MEM (real) | **No — deliberately** | Compatible via transitional wrapper; **untouched because its process is the live 3.3-G.1 execution path** (see section 2) |
| A-MEM (mock) | No | Compatible via transitional wrapper; exercised directly in H.1 tests |
| Graphiti (real) | No | Compatible via transitional wrapper |
| Graphiti (mock) | No | Compatible via transitional wrapper; exercised directly in H.1 tests |
| Letta (real) | No | Compatible via transitional wrapper (all methods `_deferred`, unrelated to H.1) |
| Letta (mock) | No | Compatible via transitional wrapper |

No foundation is `UNQUALIFIED_FOR_H1` — the wrapper approach means none needed to accept a
weakened contract.

Mocks were **not** made more permissive than real adapters: no mock file was changed at all,
so their existing (already-conformant) behavior is exactly what H.1 tests exercise.

## 10. Provenance and content authority

`CanonicalMemoryRecord.source` is preserved exactly as constructed — every key the schema's
`source` object permits (`source_type`, `reference_id`, and any additional
schema-permitted key, since `source.additionalProperties: true`) round-trips unchanged
through `to_dict()`/`from_dict()` and through ledger persistence/reload (tested).
`write_canonical_memory()` never reads provenance back out of a foundation's response —
provenance enters exclusively at `CanonicalMemoryRecord` construction time.

Content authority: the canonical `content` field is never rewritten by whatever a
foundation does to it internally (Mem0 stores a flat string, A-MEM extracts
keywords/context/tags, Graphiti derives graph nodes/edges) — those are the foundation's own
downstream representations, foundation-owned, and are never read back into the canonical
ledger.

## 11. Foundation alias table

Embedded in `CanonicalMemoryLedger` (section 6) rather than a separate module — the mission
allows this ("do NOT create a second independent identity translation system if an existing
component can be upgraded"; here, the ledger IS the new component the alias table
naturally belongs to, and no second system was created). Supports multiple foundations per
canonical id (tested: `test_multiple_foundations_share_one_canonical_identity`).

## 12. Explicit non-goals of this stage

Per the mission's scope boundary, H.1 does **not** implement:

- The canonical event ledger (`created`/`retrieved`/`selected`/`used`/`derived`/
  `superseded`/`retired` — `relationship_schema.md` section 3). Deferred to **H.2**.
- Immutable update/versioning/supersession semantics. `put()` rejects any ambiguous
  mutation (different content under an existing id) rather than silently overwriting or
  versioning it — deferred to **H.3**.
- Retirement/tombstones.
- Retrieval reranking or selection algorithms.
- Memory-use instrumentation / causal contribution.
- Any change to Graphiti/A-MEM/Mem0 real-conformance behavior (evolution, semantic
  retrieval, formation) — those remain exactly as characterized by the existing H.3/H.4
  conformance work.
- Poisoning attacks, Phase 4, new datasets, new foundations.
- Migration of `campaign_formal_runner.py`, `campaign_runner.py`, or any pilot script to the
  new write path — deliberately deferred (section 13) to avoid any risk to the live 3.3-G.1
  process and to keep this stage's diff reviewable in isolation.

## 13. Deferred call-site migration

`write_canonical_memory()` exists and is fully tested, but no existing caller was switched
to it. This is intentional: `campaign_formal_runner.py` is the mission's explicitly
protected file (live G.1 process), and migrating any *other* caller (e.g. the superseded
`campaign_runner.py`, or the pilot scripts) without also migrating `campaign_formal_runner.py`
would leave the codebase with two divergent write paths for no immediate benefit, ahead of a
manual review this mission asks for at every stage boundary. Call-site migration is
therefore explicit follow-up work for a future, manually-reviewed stage — not silently
rolled into H.1.

## 14. Invariants (see test suite for the corresponding test)

1. Every persisted memory has exactly one canonical identity — `memory_id` is the sole key
   of `CanonicalMemoryLedger`'s record store.
2. Canonical identity is foundation-independent — `put()` never calls a foundation.
3. Canonical content is foundation-independent — `content` is set once, at construction,
   and never rewritten from a foundation response.
4. Vendor IDs are aliases, never canonical identities — enforced structurally: the alias
   table has no operation that can mutate `self._records`.
5. Canonical reconstruction does not require a vendor service — `ledger.get()` never calls
   `foundation.inspect_memory()` or any other adapter method.
6. Vendor deletion/update cannot erase the canonical record — no ledger operation is ever
   triggered by a foundation event; a foundation's own `reset()`/`delete_memory()` has zero
   code path back into the ledger.
7. A canonical ID collision cannot silently overwrite history — `put()` raises
   `CanonicalCollisionError` and leaves the existing record untouched.
8. Provenance cannot be reconstructed solely from vendor metadata — it is captured at
   `CanonicalMemoryRecord` construction, before any foundation call occurs.

## 15. Limitations

- Single-process ledger (section 6) — no cross-process locking.
- Validation is hand-written Python mirroring the schema's stated constraints
  field-by-field, not a generic `jsonschema.validate()` call against
  `memory_schema.json` directly, even though the repository does use the `jsonschema`
  library elsewhere (`datasets/validation.py`, `integration/pipeline.py`). This is a
  deliberate choice, not an oversight: the mission's preferred implementation is "an
  immutable Python dataclass... [that] must enforce the canonical schema rather than
  merely document it," which means validation belongs in `__post_init__` regardless of
  whether a generic schema validator is also run. A follow-up could add a `jsonschema`
  cross-check against the schema file itself as a belt-and-suspenders consistency test
  (to catch the schema and the dataclass drifting apart) — not implemented here, noted as
  a gap.
- No call sites migrated (section 13).
- Vendor-id extraction (`_extract_vendor_id`) depends on the informal but universally
  observed `value["memory_id"]` convention across all eight existing adapters; a future
  ninth adapter that violates this convention would report `ALIAS_PERSISTENCE_FAILED`
  rather than crash, but would not get a useful alias without an adapter-specific fix.
