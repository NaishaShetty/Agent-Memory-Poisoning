# Phase 3.3-H.3 — Immutable Memory Versioning, Supersession & Retirement

Status: **COMPLETE**. Architectural remediation stage; not an evaluation or poisoning
campaign.

## 1. Problem

H.1 established `CanonicalMemoryRecord`/`CanonicalMemoryLedger` as the authoritative,
foundation-independent memory identity, and deliberately deferred "formal versioning": its
own collision policy rejects any differing rewrite of an existing `memory_id`, "to protect
the ontology until H.3 introduces formal versioning." H.2 established the event history
substrate, including `superseded`/`retired` event TYPES, but implemented no POLICY for when
or how a memory legitimately transitions between lifecycle states, nor any mechanism to
record WHICH memory superseded another. H.3 exists to close exactly this gap: immutable
memory versions, supersession, and retirement, without ever overwriting history.

## 2. Relationship to H.1 (frozen, unmodified)

**Zero lines of `canonical.py`, `ledger.py`, or `canonical_write.py` were changed.**
`CanonicalMemoryRecord` remains exactly as H.1 defined it: immutable, one per `memory_id`,
forever. H.3 adds a new, additive module (`memory_versioning.py`) that reads
`CanonicalMemoryLedger` (via `exists()`/`get()` only) and never calls `put()` with a second,
differing record for an existing `memory_id`.

**Critical clarification this stage makes explicit:** `CanonicalMemoryRecord.lifecycle_state`
(and `.superseded_by`, `.equivalent_to`, `.conflicts_with`) are frozen at whatever value they
had AT CREATION time — since the record is an immutable dataclass, they can never reflect a
LATER transition. Reading `CanonicalMemoryRecord.lifecycle_state` after creation and treating
it as "the memory's current state" would be a bug. The authoritative current state is always
`memory_versioning.get_current_version()` — see section 8.

## 3. Relationship to frozen H.2/H.2-R/H.2-R2

**Zero lines of `canonical_event.py` or `event_ledger.py` were changed.** H.3 drives
`CanonicalEventLedger.append()` (unmodified) with `superseded`/`retired` events exactly as
H.2/H.2-R2 already validate them (single `memory_id`, required `previous_state`/`new_state`,
H.2-R2's single-occurrence-per-type enforcement). H.3 does not add a `superseded_by`-style
field to `CanonicalEvent` — see section 5's explicit reasoning for why a separate side-record
was used instead.

## 4. Canonical memory identity vs. version identity — the central design decision

**This is the most consequential decision in this stage, and it DEPARTS from the H.3 mission
brief's own illustrative diagram.** That diagram ("version 1 CREATED -> version 2 SUPERSEDES
version 1 -> version 3 SUPERSEDES version 2") describes multiple immutable CONTENT variants
sharing one logical memory identity. Direct evidence from the FROZEN `memory_schema.md`/
`memory_schema.json` establishes a different model:

> `memory_schema.md` §2: "Identity is assigned once at creation and never reassigned,
> reused, or mutated — not even when a memory is superseded or retired. Two memories are
> never merged into a single identity after creation."
>
> `memory_schema.md` §6: "If B legitimately supersedes A ...: A — superseded_by → B. A
> transitions to a retired lifecycle state but is never deleted."
>
> `memory_schema.json`'s `superseded_by`: "the memory_id of the memory that legitimately
> supersedes this one."
>
> `relationship_schema.md` §2: `superseded_by: A → B`, "one-to-one per memory (a memory has
> at most one superseder)" — an edge between TWO DISTINCT memory identities.

**Decision:** "supersession" never means "memory M1 gets new content." Content, `source`,
`parent_ids`, `memory_type`, `creation_event`, and `creation_timestamp` are permanently fixed
per `memory_id`, forever. What legitimately changes over one `memory_id`'s lifetime is
exactly the relationship/lifecycle fields H.1 punted on: `lifecycle_state` and
`superseded_by` (this stage does NOT extend `equivalent_to`/`conflicts_with` — see section
18). "A memory version," in this stage's model, is therefore an immutable SNAPSHOT of
`(lifecycle_state, superseded_by)` for one permanent `memory_id`, taken at one point in that
memory's recorded history — never a second content variant.

This was not a free design choice; it followed from the mission's own STOP conditions (#1
"cannot support version semantics without inventing a new ontology," #5 "would require
changing H.1 canonical identity semantics without explicit justification," #9 "would
silently invalidate existing data") and its own explicit instruction: "if a field's
ownership is ambiguous: STOP, inspect existing schema/documentation, resolve from repository
evidence, do not invent semantics casually." The evidence resolves the ambiguity; this
document records that resolution rather than treating it as a silent implementation detail.

## 5. Version record

`memory_versioning.py::CanonicalMemoryVersion` (frozen dataclass):

| Field | Meaning |
|---|---|
| `version_id` | `f"{memory_id}::v{version_number}"` — see section 6 |
| `memory_id` | the permanent H.1 canonical identity this version belongs to |
| `version_number` | 1-based position in this memory's lifecycle-event sequence |
| `lifecycle_state` | one of `canonical.LIFECYCLE_STATES`, from the causing event's `new_state` |
| `superseded_by` | `None`, or the superseding memory's `memory_id` (from a linked `SupersessionRecord`) |
| `established_by_event_id` | the `CanonicalEvent.event_id` that caused this version to exist — a REFERENCE, never a duplicated copy of that event's content |
| `recorded_at` | the causing event's own `timestamp` — never fabricated, never `datetime.now()` |

**No `content`/`source`/`parent_ids`/`memory_type` field** — those belong to logical memory
identity (H.1, `CanonicalMemoryRecord`), never to a version (`test_invariant_content_never_
referenced_by_version` asserts this structurally). **No separate `versions.jsonl` store
exists** — a version is a pure, deterministic PROJECTION over the (already-durable) H.2
event log plus this stage's own small `SupersessionRecord` side-table, per the mission's own
"Do NOT duplicate the complete event history inside every version. Use references." A
`SupersessionRecord` (`superseded_memory_id`, `superseding_memory_id`,
`superseded_event_id`) is the ONE new persisted fact this stage introduces — see section 5.1
for why it could not simply be a new `CanonicalEvent` field.

### 5.1 Why `SupersessionRecord`, not a new `CanonicalEvent` field

H.2-R2 (frozen) requires `len(memory_ids)==1` for a `superseded` event and forbids
`source_memory_ids`/`target_memory_id` on any non-`derived` event type — there is genuinely
no existing `CanonicalEvent` field that can carry "which memory superseded this one" without
modifying `canonical_event.py`, which is frozen. `SupersessionRecord` is therefore a new,
additive, append-only side-record (`supersessions.jsonl`) — mirroring H.2-R's own precedent
of introducing `ExperimentBoundaryRecord` as a genuinely separate type when a frozen type's
shape could not express a new fact, rather than weakening the frozen type.

## 6. Version ID semantics — an explicit, different decision from H.2's event identity

The mission explicitly warns not to blindly reuse H.2's content-derived
(`fingerprint()`-based) event-identity design, since "an event and a memory version are
different ontology objects." They are: a `CanonicalEvent` is independently AUTHORED by an
arbitrary caller (so two callers could coincidentally submit identical content, needing the
idempotent-vs-collision machinery H.2-R2 built). A `CanonicalMemoryVersion` is NEVER
independently authored — it is always COMPUTED, fresh, every call, from already-persisted,
already-protected state. There is no "duplicate submission" scenario to resolve for a value
nothing ever submits directly. Given that, `version_id = f"{memory_id}::v{version_number}"`
is simply the most direct, meaningful, benchmark-owned identity: deterministic (same
inputs → same output, trivially, since it's a pure string format), stable after
computation, and collision-free BY CONSTRUCTION (no two different `memory_id`s ever produce
the same `version_id`, since the memory_id is embedded verbatim).

## 7. Lineage

Strictly **linear**, never a general DAG: one `memory_id` has exactly one chain of lifecycle
versions, `version_number` 1, 2, 3, ... in the EXACT append order of its
`created`/`derived`/`superseded`/`retired` events (never re-sorted by timestamp — mirrors
every prior stage's ordering discipline). "Predecessor" is always `version_number - 1` of
the SAME `memory_id` — trivially guaranteed to exist by construction (versions are
enumerated by iterating the actual event sequence in order; there is no code path that could
produce a `version_number` without also producing every smaller one first).

**Cycle rejection:** the cross-MEMORY supersession graph (`A —superseded_by→ B` edges across
DIFFERENT `memory_id`s) is what could, in principle, form a cycle (`A→B→...→A`).
`supersede_memory()` rejects this: a memory whose CURRENT version is already `RETIRED` can
never be used as a superseder. Since a memory becomes `RETIRED` exactly when it is
superseded or otherwise retired, this single check makes every cycle of any length
structurally unreachable — the edge that would close a cycle always originates from a memory
some earlier edge in the same cycle already retired.

## 8. Current version semantics

`get_current_version()` = the LAST entry of `reconstruct_version_history()`'s ordered tuple —
never inferred from vendor state, filesystem order, or (critically)
`CanonicalMemoryRecord.lifecycle_state` (frozen at its at-creation value; see section 2).
This is the SOLE authoritative "what is memory X's state right now" query in this
framework.

## 9. Supersession semantics

`supersede_memory(event_ledger, memory_ledger, supersession_ledger, superseded_memory_id,
superseding_memory_id, *, superseded_event, retired_event)`:

1. Validate both memories exist; `superseded_memory_id` is not already `RETIRED`; it has no
   existing superseder; `superseding_memory_id` is not itself `RETIRED` (cycle rejection,
   section 7).
2. Append the `superseded` `CanonicalEvent` for A (durable independent of step 3).
3. Append the `SupersessionRecord` (A → B linkage).
4. Append the `retired` `CanonicalEvent` for A.

**Only one successor is permitted** (relationship_schema.md: "at most one superseder"),
enforced by `SupersessionLedger.append()`'s own collision check PLUS the current-version
`superseded_by is not None` precondition in `supersede_memory()` (belt and suspenders: the
second layer rejects the attempt before any event is even appended, giving a cleaner
`AlreadyRetiredError`/`SupersessionCollisionError` rather than a mid-sequence partial
failure for the common case). **A superseded version may not be superseded again** — once
`RETIRED`, `supersede_memory()`/`retire_memory()` both reject any further transition
(`AlreadyRetiredError`) — retirement is terminal.

H.3 does not decide WHAT causes a supersession — `memory_schema.md` §8 explicitly defers the
"creation policy" (novelty/equivalence thresholds) to a not-yet-frozen later stage. H.3
provides the MECHANISM (validated, auditable, append-only recording of a decision already
made elsewhere), never the POLICY.

## 10. Retirement / tombstone semantics

`retire_memory(event_ledger, memory_ledger, supersession_ledger, memory_id, *, retired_event)`
— retirement with NO successor (`superseded_by` stays `None` forever for this memory).
Validates the memory is not already `RETIRED`, then appends the `retired` event. Retirement
is represented purely as a `lifecycle_state=RETIRED` version snapshot — **no separate
tombstone structure was introduced**, since `memory_schema.json`'s own `lifecycle_state`
enum already IS the tombstone marker the mission's section 13 asks about, and inventing a
second, redundant structure for the same fact was explicitly discouraged ("Do not invent
redundant structures"). After retirement: `CanonicalMemoryRecord` is untouched and still
`exists()`; every prior version remains reconstructable; the `retired` event (and, if
supersession-driven, the `superseded` event + `SupersessionRecord`) remain in their
respective append-only stores forever.

**Retired vs. superseded vs. vendor-deleted/reset — explicitly distinct:** `retired`
(this memory's own terminal `lifecycle_state`) and `superseded_by` (a `SupersessionRecord`
linkage to a DIFFERENT memory) are independent, separately-observable facts (section 9's
"retirement vs supersession semantics remain distinct" test proves a plain retirement has
`superseded_by=None` forever, while a supersession-driven retirement always has it set). A
vendor foundation's `delete_memory()`/`reset()` has NO representation anywhere in this
module — see section 12 — and cannot be confused with either.

## 11. Event integration

`created`/`derived` → version 1. `superseded` → the version reflecting the A→B linkage.
`retired` → the version reflecting the terminal `lifecycle_state=RETIRED`. Exactly one
version is produced per lifecycle-relevant event, in the event ledger's own append order —
the most literal, uninvented reading of the mission's own suggested mapping, requiring no
"which events belong together" heuristic.

## 12. Reset distinction (mission section 21 / H.2's own established boundary)

No code in `memory_versioning.py` imports `experiment_boundary`/`ExperimentBoundaryRecord`,
nor `MemoryFoundationAdapter`/any foundation adapter, nor calls `foundation.reset()`/
`foundation.delete_memory()` — verified directly (`hasattr` checks on the actual imported
module, not string-matching this module's own prose, which legitimately discusses the
distinction). An `ExperimentBoundaryRecord` (H.2-R) and a `retired` `CanonicalEvent` remain
structurally unrelated types with no conversion path between them, exactly as H.2/H.2-R/
H.2-R2 established.

## 13. Persistence

One new file: `supersessions.jsonl`, identical discipline to every other ledger in this
framework (open-append/`write()`/`flush()`/`os.fsync()`; malformed lines raise
`json.JSONDecodeError` loudly on reload, never silently skipped). No `versions.jsonl` exists
(section 5). Single-process/single-writer, same explicit limitation as every prior ledger —
no cross-process lock; multi-worker supersession would need the same per-worker-isolation +
merge pattern H.2-R2 established for `ExperimentBoundaryLedger`, not implemented here since
no caller performs concurrent supersession writes (mission's adversarial CASE I: "do not
invent merge semantics unless actually required" — none is).

## 14. Failure semantics

`supersede_memory()`'s four-step write order (section 9) is explicitly NOT claimed atomic.
Each step's durability is independent and immediate (JSONL append+fsync). A failure between
steps leaves an HONEST partial state, always explicitly re-derivable by
`reconstruct_version_history()` afterward — never silently repaired, never corrupted:

| Failure point | Resulting state |
|---|---|
| Before step 2 (validation fails) | Nothing written; caller sees the raised exception |
| Between steps 2 and 3 | `superseded` event durable; version 2 exists with `superseded_by=None` (linkage genuinely absent, never fabricated) |
| Between steps 3 and 4 | `superseded` event + linkage durable; version 2 has `superseded_by` set but `lifecycle_state` still whatever the `superseded` event's own `new_state` was (in practice already `RETIRED`, since that is what the `superseded` event records — a `retired` event's absence means no THIRD version exists yet, not that the second version is wrong) |
| All four steps complete | Fully recorded, `STATUS_FULLY_SUPERSEDED` |

`supersede_memory()`'s return `status` always reflects exactly how far the operation
actually got (`STATUS_SUPERSEDED_EVENT_ONLY` if the linkage append raised
`SupersessionCollisionError`) — never a bare success/failure boolean.

There is no "version write" failure mode distinct from the underlying event/linkage writes,
because nothing separately persists a version (section 5) — this eliminates an entire
failure-mode category by construction rather than handling it (tested directly:
`test_36_version_write_failure_is_not_applicable_no_separate_version_store`).

## 15. Reconstruction

`reconstruct_version_history()`/`get_current_version()`/`get_version()` — all pure functions
over `CanonicalEventLedger` + `CanonicalMemoryLedger` + `SupersessionLedger`. None imports or
calls any `MemoryFoundationAdapter` method; none is affected by a vendor being unavailable,
deleted, reset, or having its own content updated. Proven directly by never constructing a
vendor/foundation object anywhere in `test_h3_versioning.py`.

## 16. Invariants

See `test_h3_versioning.py`'s "INVARIANTS" section for the corresponding test of each:

1. Canonical memory identity (`memory_id`) is stable across every version.
2. `version_id` is unique within its `memory_id` (and globally, since `memory_id` is
   embedded verbatim and `memory_id`s are themselves globally unique per H.1).
3. `CanonicalMemoryVersion` is an immutable (frozen) dataclass.
4. Historical versions are never deleted — no `update`/`delete` operation on a version
   exists anywhere in this module's public API.
5. Version lineage is acyclic (section 7).
6. A version's predecessor always belongs to the SAME `memory_id` (trivially, by
   construction — versions are only ever enumerated per-memory).
7. `get_current_version()` always refers to an actually-existing version (it IS one, by
   construction — never a dangling pointer).
8. Superseded versions remain reconstructable (`get_version()` with any valid
   `version_number`).
9. Retired versions remain reconstructable (same).
10. Vendor IDs never become canonical version IDs — no vendor id is ever consulted by this
    module at all.
11. Vendor deletion/reset cannot erase canonical versions — no vendor dependency exists.
12. Retirement never physically deletes history — `CanonicalMemoryRecord`/`CanonicalEvent`s
    remain exactly as H.1/H.2 persisted them; only NEW facts are appended.
13. Experiment RESET never implies retirement — zero import coupling (section 12).
14. Canonical events remain append-only — H.2's own `CanonicalEventLedger` is unmodified.
15. Version history can be reconstructed without vendors (section 15).
16. Content is never referenced by a version — versions carry no content field at all
    (section 5).

## 17. Compatibility

Every H.1/H.2/H.2-R/H.2-R2 API remains valid and untouched. `test_h3_versioning.py`'s
"COMPATIBILITY" section spot-checks each prior stage's own defining behavior (H.1's
frozen-at-creation `lifecycle_state`; H.2-R2's single-occurrence enforcement; H.2-R's
`ExperimentBoundaryRecord`/`build_reset_boundary()`; H.2-R2's `generate_event_id()`
determinism) still functions exactly as those stages' own test suites already prove, run
unmodified alongside these new tests.

## 18. Deferred runtime integration / explicit non-goals

- No call site (`campaign_formal_runner.py` or otherwise) constructs a `CanonicalMemoryVersion`
  or calls `supersede_memory()`/`retire_memory()` from live behavior — verified directly, zero
  references anywhere in `campaign_formal_runner.py`'s source.
- `equivalent_to`/`conflicts_with` evolution after creation is explicitly out of scope — these
  remain exactly as H.1 defined them (immutable, set once at construction). Whether/how they
  should become versionable is a genuinely separate, undecided question this stage does not
  resolve.
- Creation-policy decisions (WHEN a memory should be superseded/retired, novelty/equivalence
  thresholds) remain not-yet-frozen, per `memory_schema.md` §8 — H.3 supplies the mechanism
  a future policy would call, never the policy itself.
- Retrieval/selection awareness of `RETIRED` memories (e.g. excluding them from candidate
  discovery) is H.4's job.
- Memory-use attribution, causal contribution, foundation requalification, poisoning — all
  explicitly out of scope, matching the mission's own scope table.

## 19. Tests

See `PHASE3_3_H3_IMPLEMENTATION_REPORT.md` for exact before/after regression counts and the
full item-by-item mapping (`test_h3_versioning.py`, 52 tests, covering all 44 mission test
items, 16 invariants, and the adversarial cases A-I the mission's section 28 lists).

## 20. Limitations

- Single-process/single-writer `SupersessionLedger` (section 13).
- No merge utility for concurrent supersession writes (not needed by any current caller;
  the H.2-R2 boundary-merge pattern would generalize if it ever is).
- `equivalent_to`/`conflicts_with` versioning is an open question, not answered here
  (section 18).
- The cycle-rejection check (section 7) is a NECESSARY, not exhaustively-proven-sufficient,
  condition for acyclicity in the fully general case of a graph with many long chains — it
  is proven sufficient for the 2-cycle case directly (tested) and reasoned to generalize (a
  cycle's closing edge always originates from an already-retired node), but no formal graph-
  theoretic proof beyond that reasoning was constructed.
- No physical enforcement prevents a caller from constructing a `superseded`/`retired`
  `CanonicalEvent` directly via `event_ledger.append()`, bypassing `supersede_memory()`/
  `retire_memory()`'s precondition checks entirely (H.2's `append()` itself has no concept of
  H.3's version semantics, by design — H.2 is frozen). A caller that bypasses the H.3
  orchestration layer can produce event sequences H.3's OWN functions would have rejected
  (e.g. two DIFFERENT-content `retired` events would still be caught by H.2-R2's
  single-occurrence check, but a cycle across three or more memories constructed by manually
  calling `event_ledger.append()` directly, never through `supersede_memory()`, would NOT be
  caught by this stage's cycle check, since that check lives in the orchestration layer, not
  in `CanonicalEventLedger.append()` itself, which is frozen and unmodified). Documented as a
  known gap: callers are expected to use `supersede_memory()`/`retire_memory()`, never raw
  event construction, for lifecycle transitions.
