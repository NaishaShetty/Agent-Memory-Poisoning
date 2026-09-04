# Phase 3.3-H.2 — Canonical Append-Only Event Ledger

Status: **COMPLETE AND FROZEN** (pending human review), including the H.2-R remediation
pass (sections 23-29) and the H.2-R2 final hardening pass (sections 30-36). Architectural
remediation stage; not an evaluation campaign.

## 1. Problem

MAMBench produces runtime/foundation traces (`foundations/trace.py::FoundationTraceArtifact`,
`agent_runtime/trace.py::evaluate_and_trace()`, `contracts/trace_artifact.schema.json`), but
none of them is a durable, benchmark-owned, append-only HISTORY of what happened to a given
canonical memory over its lifecycle. Each existing trace captures a snapshot scoped to one
task's execution or one foundation call; none answers "given this canonical memory id, list
everything that has ever happened to it" independent of which task or which foundation call
produced each fact. This is the audit's "fragmented traceability" / "persistent canonical
event history" finding.

## 2. Relationship to H.1

H.1 ([PHASE3_3_H1_CANONICAL_MEMORY_LEDGER.md](PHASE3_3_H1_CANONICAL_MEMORY_LEDGER.md))
answers "what is this memory?" via `CanonicalMemoryRecord`/`CanonicalMemoryLedger`. H.2
answers "what happened to this memory?" via `CanonicalEvent`/`CanonicalEventLedger`, built
directly on top of H.1: a `CanonicalEventLedger` is constructed WITH a `CanonicalMemoryLedger`
instance specifically so it can enforce memory linkage (section 5) without a second,
separate existence-check mechanism. No H.1 file was modified.

## 3. Event ontology

Taken **verbatim** from `phase3/schemas/relationship_schema.md` section 3 — its own exact
(lowercase) spelling, no second vocabulary invented:

`created`, `retrieved`, `selected`, `used`, `derived`, `superseded`, `retired`
(`phase3/evaluation/foundations/canonical_event.py::EVENT_TYPES`).

Per-type rules, all taken directly from the schema doc's stated semantics:

- `retrieved`/`selected`/`used` are **always task-scoped** → `task_id` is required
  (non-empty) for these three, and left exactly as the caller supplies it (possibly `None`)
  for the other four — never fabricated.
- `created`/`superseded`/`retired` are the **state-changing** events → `new_state` is
  required for all three; `previous_state` is additionally required for `superseded`/
  `retired` (but not `created`, which has no prior state — nothing existed before it).
  Both, when present, must be one of `canonical.LIFECYCLE_STATES` (`CREATED`/`ACTIVE`/
  `RETIRED` — reused verbatim from H.1, not a second lifecycle vocabulary).
- Every other event type (`retrieved`, `selected`, `used`, `derived`) **must not** carry
  `previous_state`/`new_state` at all — the schema doc scopes those fields to the three
  state-changing types only, and this module enforces that scope rather than leaving it as
  an unenforced convention.

**Documented gap:** the schema doc defines no `experiment_reset` (or equivalent) event
type. H.2 does not invent one — see section 14.

## 4. Event identity

`CanonicalEvent.event_id` is **benchmark-owned**: supplied by the caller (never a vendor
event id, database row number, or timestamp), validated for well-formedness by the
dataclass, uniqueness/collision enforced by `CanonicalEventLedger.append()` — the exact
same ownership pattern H.1 uses for `memory_id` (see H.1 doc section 5), applied here to
events rather than memories. No auto-minting (uuid/hash) is introduced; nothing in the
mission requires one, and avoiding it keeps append calls deterministic and trivially
testable (mirrors the repo's own `DeterministicClock` "never `uuid4()`/`random`" ethos —
`foundations/mocks/common.py`).

## 5. Memory linkage

Every `CanonicalEvent.memory_ids` entry must already exist in the `CanonicalMemoryLedger`
the `CanonicalEventLedger` was constructed with. `append()` checks every referenced id
BEFORE performing any write; a reference to an unknown canonical memory raises
`UnknownCanonicalMemoryError` and leaves no trace at all (not even a partial event record).
`relationship_schema.md` states no forward-reference allowance for an event pointing at a
not-yet-created memory, so none is implemented — and the event ledger never creates a
memory record as a side effect of recording an event (tested explicitly:
`test_event_ledger_never_creates_a_memory_as_a_side_effect`).

## 6. Foundation linkage

`foundation_name`/`foundation_memory_id` are optional secondary identifiers on an event
(e.g. a `retrieved` event recording which vendor and which vendor-native id produced the
candidate). `foundation_memory_id` requires `foundation_name` to also be set — an alias is
meaningless without knowing which vendor it belongs to. The canonical `memory_ids` field
remains authoritative regardless; a vendor id here is never treated as, or substitutable
for, the memory's canonical identity (mirrors H.1's alias discipline exactly).

## 7. Task linkage

`task_id` is required for the three task-scoped event types (section 3) and left as an
honest `Optional[str]` — never invented — for the rest. No event type in this framework's
vocabulary requires a `task_id` when the schema doc does not say it is task-scoped.

## 8. Actor semantics

`actor: str` (required, non-empty). The schema doc's own examples
(`candidate_discovery`, `evidence_selection`, `creation_policy`) are finer-grained than the
five coarse categories (`benchmark`/`foundation`/`agent`/`evaluator`/`system`) an
enumeration might suggest, so this module does **not** add a second, closed `actor`
category enum beyond what the schema doc actually defines — doing so would be exactly the
"speculative field" the H.1/H.2 mission briefs both warn against. A caller is free to use
either granularity of string; nothing in this module restricts `actor` to a closed set. If
a later stage needs a coarse category cross-cut, it can be added additively without
touching this field's meaning.

## 9. Timestamp semantics

`timestamp: str`, required, ISO-8601 UTC, validated with the same
`datetime.fromisoformat`-based check H.1's `CanonicalMemoryRecord.creation_timestamp` uses
(duplicated as a small, self-contained ~8-line function rather than imported from
`canonical.py`, matching the repository's own preference for small, explicit, per-module
validators over cross-module private-function coupling). Never fabricated for a historical
event — every event in this stage is manually, explicitly constructed by a caller who
supplies its own timestamp.

## 10. Append-only persistence

`events.jsonl` under a `storage_dir`, one JSON line per successful `append()` — the exact
persistence discipline H.1's `records.jsonl`/`aliases.jsonl` already use: open in append
mode, write one fully-formed line, `flush()`, `os.fsync()`. Reload is a pure, order-
preserving fold over this file (`CanonicalEventLedger._load()`), which is what makes
"event ledger persistence" and "event ledger reload" provable rather than assumed.

## 11. Immutability

There is no `update_event()` or `delete_event()` method anywhere in `CanonicalEventLedger`
— enforced by the public API's literal shape, not by a runtime guard a caller could route
around. `test_no_update_event_api`/`test_no_delete_event_api` assert this absence
structurally (`not hasattr(...)`), so a future change reintroducing either method fails a
test that explains why not to. `CanonicalEvent` itself is a frozen dataclass — attempting to
mutate a field after construction raises.

If a historical fact later needs correcting, the schema doc's own model already provides
the answer: record a NEW event (e.g. a `superseded`/`retired` event on the affected memory)
that captures the correction as new history — H.2 does not invent a distinct "correction"
event type of its own; that determination belongs to whichever future stage actually needs
it (H.3, most likely, for `superseded`).

## 12. Query API

`CanonicalEventLedger`: `append`, `get_event`, `events_for_memory`, `events_for_task`,
`events_for_foundation`, `reconstruct_memory_history` (identical to `events_for_memory` —
kept as a separately-named entry point because the mission brief names this exact
capability explicitly), `all_events`. Every query reads only this ledger's own in-memory/
on-disk state; none ever calls a `MemoryFoundationAdapter` method.

## 13. Reconstruction

`reconstruct_memory_history(memory_id)` returns every event referencing that memory, **in
append (persisted) order** — never re-sorted by `timestamp`. This is a deliberate choice
per the mission's "do not infer semantic ordering solely from timestamps" instruction: the
ledger's own append-order sequence (`CanonicalEventLedger._order`) is the authoritative
ordering signal; `timestamp` remains available on each event as a separate, informational
field, but two events appended out of chronological timestamp order are still returned in
the order they were actually appended (tested:
`test_event_ordering_is_append_order_not_timestamp_order`). No Mem0/A-MEM/Graphiti/Letta
adapter object is ever constructed by this reconstruction path — it is impossible for it to
depend on one, since nothing in `canonical_event.py`/`event_ledger.py` imports
`MemoryFoundationAdapter` at all.

## 14. Reset vs. retirement distinction

`relationship_schema.md` defines no `experiment_reset` (or equivalent) event type. H.2 does
not invent one — inventing a new event type outside the frozen schema doc would itself be
exactly the "silently add speculative semantics" the mission prohibits. Instead, the
distinction the mission asks H.2 to preserve is satisfied **structurally, by omission**:
nothing in this stage auto-generates any event from a `MemoryFoundationAdapter.reset()`/
`delete_memory()` call (there is no runtime wiring between the two at all — see section 16),
so there is no code path anywhere that could label a foundation reset as a `retired` event.
A `retired` event can only ever be constructed by a caller explicitly supplying a genuine
`previous_state`/`new_state` lifecycle transition (validated against
`canonical.LIFECYCLE_STATES`); a bare "the foundation was reset" signal does not satisfy
that constructor and is rejected (tested:
`test_experiment_reset_is_not_a_retirement_event`). A future stage that wants an explicit
`EXPERIMENT_RESET` concept must add it to `relationship_schema.md` first (a schema change,
out of H.2's scope) rather than have H.2 improvise one silently.

## 15. Trace reconciliation strategy

Investigated, not implemented, per the mission's explicit "if doing so would touch active
G.1 execution: STOP and defer it" instruction:

- `foundations/trace.py::FoundationTraceArtifact` has no `event_id` field today. Adding one
  would be an additive (non-breaking, all-fields-optional-already) dataclass change, but
  `FoundationTraceArtifact` instances are produced synchronously inside every
  `MemoryFoundationAdapter` mock's `normalize_trace()` call — including, transitively,
  `RealAMemAdapter`'s equivalent path used by the live 3.3-G.1 process. Adding a field is
  low-risk in the abstract, but this stage draws the line at "zero files on the G.1 import
  path are touched, full stop," so this is deferred rather than judged case-by-case.
- `agent_runtime/trace.py::evaluate_and_trace()`'s trace dict and
  `contracts/trace_artifact.schema.json` are both explicitly documented as "protected
  surface, additive only" (`trace.py`'s own module docstring). Neither is imported by
  anything in this stage.
- **Conclusion:** no trace-reconciliation code was added in H.2. The canonical event
  ledger exists as independent, additive infrastructure; reconciling it with the three
  existing trace shapes (via a shared, optional `event_id`/`canonical_memory_id` field
  each could carry) is deferred to a future, manually-reviewed stage once H.2 has itself
  been reviewed.

## 16. Security boundary

The canonical event ledger is evaluator/benchmark-side infrastructure and may legitimately
carry evaluator-only information in `reason`/`actor` free text (e.g. "matches
gold_evidence_ids for this task") — this is explicitly allowed, unlike H.1's
`CanonicalMemoryRecord.content`, which runs through `enforce_foundation_call_boundary` and
therefore CANNOT carry such information (`CanonicalEvent` deliberately does not run its
fields through that same check, since it is not destined for agent or foundation
visibility). Two tests establish the actual safety property this implies:

1. **Zero import coupling**: `phase3/evaluation/agent/conditions.py` and
   `phase3/evaluation/agent_runtime/runner.py` (the agent-visible-context and agent-
   execution modules) contain no reference to `event_ledger`/`canonical_event` anywhere in
   their source — there is no import edge through which a canonical event could reach
   agent-visible context or a model prompt automatically.
2. **Unweakened boundary check**: if a caller mistakenly tried to smuggle event data into
   an agent-visible payload under a forbidden key anyway, the pre-existing, un-modified
   `contracts.boundary.validate_agent_visible()` still catches it — this stage neither
   weakens nor bypasses that check.

## 17. Concurrency model

Identical to H.1's `CanonicalMemoryLedger`: single-process, single-writer. No cross-process
file lock. Not a regression — no caller adopts this ledger yet.

## 18. Crash/durability semantics

Each `append()` performs one `open(..., "a")` / `write()` (of one already-fully-formed
JSON line) / `flush()` / `os.fsync()` before returning. A process crash mid-run loses at
most an in-flight, not-yet-durable append — never corrupts a prior line. A malformed line
appended by some other process/bug is NOT silently skipped on reload: `_load()` calls
`json.loads()` per line with no try/except, so a corrupted `events.jsonl` raises
`json.JSONDecodeError` loudly at construction time rather than silently dropping history
(tested: `test_malformed_jsonl_line_raises_rather_than_silently_skipping`).

## 19. Invariants (see test suite for the corresponding test)

1. Every persisted event has exactly one `event_id` — the ledger's record dict is keyed by
   `event_id` alone.
2. Event IDs are benchmark-owned — no vendor/database/timestamp-derived id is ever
   accepted as one; `append()` never calls a foundation.
3. Events are append-only — `_order` only ever grows via `append()`; there is no removal
   path.
4. Existing events cannot be modified/deleted through the API — no `update_event()`/
   `delete_event()` method exists; `CanonicalEvent` is a frozen dataclass.
5. Memory-related events reference canonical memory IDs — `append()` validates every
   `memory_ids` entry against the linked `CanonicalMemoryLedger` before writing anything.
6. Vendor IDs are secondary aliases only — `foundation_memory_id` never substitutes for
   `memory_ids`, and no ledger operation ever promotes one.
7. Event history can be reconstructed without vendor availability — no method in
   `event_ledger.py` imports or calls `MemoryFoundationAdapter`.
8. A vendor reset/delete cannot erase canonical event history — the event ledger has zero
   code path triggered by, or dependent on, a foundation call.
9. Event history for one canonical memory cannot contaminate another —
   `events_for_memory()`/`reconstruct_memory_history()` filter strictly by membership in
   `memory_ids`; tested directly with two isolated memories and interleaved event ids.
10. Event-ledger contents are never automatically inserted into agent-visible context — no
    import edge exists between this module and any agent-facing module (section 16).
11. Experiment reset is not silently equivalent to semantic retirement — by omission
    (section 14): nothing auto-generates a `retired` event from any foundation operation.
12. An event collision cannot silently overwrite historical evidence — `append()` raises
    `CanonicalEventCollisionError` on a differing-payload re-use of an existing `event_id`,
    and leaves the existing event untouched.

## 20. Tests

See `PHASE3_3_H2_IMPLEMENTATION_REPORT.md` for the full before/after regression counts and
the per-item test mapping.

## 21. Limitations

- Single-process/single-writer ledger (section 17) — same explicit limitation as H.1.
- No trace reconciliation implemented (section 15) — deliberately deferred.
- No `experiment_reset` event type exists (section 14) — a genuine vocabulary gap in
  `relationship_schema.md` itself, not something H.2 is positioned to fix (would require a
  schema-doc change, out of scope here).
- `actor` is an unconstrained non-empty string, not a closed enum (section 8) — a
  deliberate choice to avoid inventing a vocabulary the frozen schema doc doesn't define,
  documented as a possible future addition if a real need for a coarse category cross-cut
  emerges.
- No call site (task runner, foundation adapter, pilot script) was wired to actually call
  `CanonicalEventLedger.append()` yet — H.2 provides the substrate; a future stage decides
  when/how each existing runtime moment (ingestion, retrieval, selection, ...) starts
  recording events into it. This mirrors H.1's own deferred call-site migration.

## 22. Deferred to H.3

Immutable memory versioning, supersession-chain semantics, and retirement/tombstone
workflows. H.2 makes `superseded`/`retired` REPRESENTABLE as event types (with their
required state-transition fields validated), but implements no policy about when either
should actually be emitted, nor any change to `CanonicalMemoryLedger.put()`'s current
collision-only semantics.

---

# H.2-R Remediation (post-implementation review, pre-H.3)

Three gaps were found in post-implementation review of the sections above and closed here,
narrowly, before H.3 begins. Nothing above this line was changed; H.2's original 1230
passed/14 skipped baseline remains valid, extended by 32 new tests (`test_h2_remediation.py`)
plus one existing H.2 test updated for the new required `derived`-event lineage fields (see
section 26).

## 23. Experiment/run boundary semantics

**Gap:** the original H.2 design correctly refused to reinterpret a foundation reset as a
`retired` memory event (section 14), but never gave experiment/run boundaries (e.g. the
RESET+INGEST cycle `campaign_formal_runner.py`'s own docstring describes running once per
unique `(dataset, session_or_haystack)` isolation group) ANY representation at all.
Omission is not the same claim as "reconstructable."

**Considered:** (1) an 8th `CanonicalEvent` type (e.g. `experiment_reset`), relaxing
`memory_ids` to allow empty for it; (2) a genuinely separate record/ledger with no
`memory_ids` field. (1) was rejected: it requires changing the frozen
`relationship_schema.md` event-type table for a concept the doc never anticipated, AND it
weakens the `memory_ids`-non-empty invariant H.2 established for every other event type.
(2) was chosen — see `phase3/evaluation/foundations/experiment_boundary.py`'s module
docstring for the full reasoning.

**Implementation:** `ExperimentBoundaryRecord` (fields: `boundary_id`, `boundary_type` —
currently only `BOUNDARY_RESET`, the one boundary operation this framework's existing
runtime behavior actually performs — `scope` (free-form, mirrors `EvaluationRun
.configuration_identity`'s "record some identity, don't over-specify its shape" design),
`timestamp`, `actor`, `reason`) and `ExperimentBoundaryLedger` (append-only `boundaries
.jsonl`, same collision/idempotency/persistence discipline as `CanonicalMemoryLedger`/
`CanonicalEventLedger`, but with **zero dependency on either** — a boundary concerns no
canonical memory, so there is nothing to link-check).

**Why confusion is structurally impossible, not merely avoided:** `ExperimentBoundaryRecord`
has no `memory_ids`, `lifecycle_state`, `previous_state`, or `new_state` field — it is not a
`CanonicalEvent` subtype, shares no identity namespace, and no code anywhere converts one
into the other (`event_ledger.py`'s own source contains no reference to
`experiment_boundary` at all — tested directly). A `RESET`, a `retired` memory event, and a
`superseded` memory event are three different Python objects that cannot be mistaken for
one another by any runtime code path, not merely "correctly labeled" ones.

**No schema change was made.** `relationship_schema.md` is unmodified.

## 24. Event ID generation authority

**Gap:** H.2's `CanonicalEventLedger` verifies `event_id` uniqueness/collision but never
established WHO mints one — every caller was on its own.

**Implementation:** `phase3/evaluation/foundations/event_identity.py::generate_event_id()`
— the MAMBench Event ID Factory. Purely additive: `CanonicalEvent.event_id` remains a
plain caller-supplied `str`; every existing H.2 caller/test is unaffected. A caller MAY use
the factory to obtain a value to pass in, or continue supplying its own.

**Why content-derived (SHA-256 fingerprint), not `uuid4()`:** reuses
`security.reproducibility.fingerprint()` verbatim — the repository's existing,
already-everywhere reproducibility primitive (e.g. `agent_runtime/trace.py`'s
`trace_fingerprint`) — rather than inventing a second hashing scheme. Given identical
inputs (`event_type`, `memory_ids`, `timestamp`, `actor`, `reason`, `task_id`,
`previous_state`/`new_state`, `foundation_name`/`foundation_memory_id`,
`source_memory_ids`/`target_memory_id`), the factory always returns the identical id — this
reinforces, rather than fights, `CanonicalEventLedger`'s own idempotent-duplicate policy: a
caller describing the truly-identical historical fact twice naturally coalesces onto one
id. `uuid4()` was rejected specifically because it would make two calls describing the
identical fact mint two different ids, and because every other identity-bearing construct
in this framework's reproducibility story (`DeterministicClock`, `fingerprint()` itself)
already avoids non-reproducible randomness for the same reason.

**The factory never bypasses ledger validation** — it returns a plain string; collision/
idempotency is still decided exclusively by `CanonicalEventLedger.append()`, unchanged.

## 25. Identity namespace separation

Six distinct identifier namespaces exist in this framework, NEVER conflated:

| Namespace | Owner | Example | Prefix |
|---|---|---|---|
| canonical memory id | MAMBench (H.1) | `loco-mem-001` (dataset-native) | none (dataset convention) |
| memory version id | *(H.3, not yet implemented)* | — | — |
| canonical event id | MAMBench (H.2 / H.2-R factory) | `EVT-<sha256>` | `EVT-` |
| experiment boundary id | MAMBench (H.2-R) | caller-supplied | `BND-` (convention, not enforced) |
| foundation/vendor memory id | vendor foundation | Mem0's own UUID | vendor-native |
| task id | dataset/evaluation harness | LongMemEval's task id | dataset-native |

No function anywhere in `canonical.py`/`canonical_event.py`/`event_ledger.py`/
`event_identity.py`/`experiment_boundary.py` compares an id from one namespace against
another for equality as if they were interchangeable. Memory versioning (H.3) will
introduce a seventh namespace; H.2-R deliberately does not anticipate its shape.

## 26. Multi-memory lineage semantics

**Gap:** `derived` events used a flat `memory_ids` tuple with no way to distinguish source
(parent) memories from the derived (child) memory except an unstated, brittle "last
element is the target" positional convention that nothing enforced.

**Resolution — reuses the EXISTING ontology, invents no new one:**
`relationship_schema.md` section 2 already defines this relationship directionally
(`parent_of`/`derived_from: A -> C`), and `memory_schema.json` already models it on the
CHILD record via `parent_ids` (required non-empty for `memory_type=derived`). H.2-R adds
exactly two new optional `CanonicalEvent` fields — `source_memory_ids` (mirrors the
derived memory's own `parent_ids`) and `target_memory_id` (the one derived memory's own
`memory_id`) — required together for `event_type='derived'`, forbidden for every other
type. `memory_ids` remains present (used uniformly by the ledger's linkage check and
`events_for_memory()`), but for `derived` events must exactly equal `set(source_memory_ids)
| {target_memory_id}` — checked explicitly at construction, never auto-derived (this
codebase's established convention, per `canonical.py`/`ledger.py`, is to fail loudly on an
inconsistent caller input, not silently fix it).

**What was deliberately NOT added:** a `superseded_by_memory_id`-style field for
`superseded` events. `relationship_schema.md`'s `superseded_by` is also directional
(A -> B), but recording "superseded BY which memory" at the event level starts to overlap
with H.3's actual job of defining what a superseder pointer means operationally (one-to-one
enforcement, validation, version-chain semantics) — adding it now would be implementing a
slice of H.3 prematurely. `superseded`/`retired` events keep their original H.2
single-memory shape, unchanged.

No relationship type beyond `derived` needed a fix: `relationship_schema.md`'s event-type
table (section 3, seven types) contains no formal `conflicts_with`/`equivalent_to` EVENT
type — those are RELATIONSHIP types (section 2), already representable directly on
`CanonicalMemoryRecord.equivalent_to`/`conflicts_with` (H.1, unmodified). No new event type
was invented for them.

## 27. Migration compatibility

Every H.2 caller/test continues to work unmodified except one: `test_canonical_event_
ledger_h2.py::test_non_task_scoped_event_does_not_require_task_id` constructed a `derived`
event with a bare `memory_ids=("m1", "m2")` and no lineage fields — this is exactly the
ambiguous shape section 26 closes, so this ONE test was updated to also supply
`source_memory_ids=("m1",)`/`target_memory_id="m2"`. No other H.2 file, test, or documented
behavior changed. `CanonicalMemoryLedger`, `canonical_write.py`, and every non-`derived`
`CanonicalEvent` construction path are byte-for-byte unaffected.

## 28. Updated invariants (H.2-R additions to section 19)

13. Experiment boundaries are a structurally distinct type from `CanonicalEvent` — no
    shared base class, no shared identity namespace, no conversion path between them.
14. Event IDs belong to a benchmark-owned namespace (`EVT-` prefix by convention when
    factory-generated) and are never equal to, or derived from, a memory/vendor/task id.
15. `derived` event lineage roles (`source_memory_ids`/`target_memory_id`) are never
    inferred from `memory_ids`' element order — verified directly by constructing two
    `derived` events with the same `memory_ids` set in different orders and asserting
    identical resolved roles.
16. A memory id appearing only via `foundation_memory_id`/vendor space can never satisfy
    `source_memory_ids`/`target_memory_id`'s canonical-memory-linkage check — the same
    `CanonicalMemoryLedger.exists()` check every other `memory_ids` entry undergoes applies
    uniformly, since `memory_ids` is required to already contain every lineage role's id.

## 29. Updated limitations (H.2-R additions to section 21)

- `ExperimentBoundaryLedger` shares H.2's single-process/single-writer limitation; no
  cross-process lock.
- `BOUNDARY_TYPES` currently contains only `BOUNDARY_RESET` — the one boundary operation
  this framework's documented runtime behavior actually performs. A future stage needing a
  second kind (e.g. an explicit campaign start/end marker) can extend the tuple additively;
  none was added speculatively here.
- The `BND-` boundary-id prefix is a human convention (`experiment_boundary
  .BOUNDARY_ID_PREFIX`), not enforced by `ExperimentBoundaryRecord`'s validation — a
  boundary id lacking the prefix is still accepted. Mirrors `event_identity.py`'s
  `looks_like_generated_event_id()`, which is likewise advisory only.
- No call site (`campaign_formal_runner.py` or otherwise) was wired to actually construct
  an `ExperimentBoundaryRecord` on a real reset — this stage provides the representation,
  not runtime integration, matching H.2's own deferred-integration posture (section 21).

---

# H.2-R2 Final Hardening (last H.2 pass before H.3 review)

Four areas were investigated per the H.2-R2 mission; two produced real, implemented
remediations (A, C's ownership-contract formalization + merge utility, D's integration
factories), one produced a deliberate no-change decision with documented rationale (B), and
one item search turned up an additional, independent identity-integrity gap beyond what the
mission's own framing anticipated (the single-occurrence invariant, folded into A). Nothing
in sections 1-29 above was changed except the exact two backward-compatible additions listed
in section 34.

## 30. Event identity semantics (Area A) — formally resolved

**Decision:** identical canonical event content is the SAME historical fact. Every field
`CanonicalEvent` carries is part of the observation itself; there is no additional
"occurrence" field distinguishing two calls that supply identical values for every one of
them, and this stage does not invent one. `event_identity.generate_event_id()`'s
content-derived design already encoded this decision (H.2-R); H.2-R2 formalizes it as a
documented invariant in `event_ledger.py`'s own module docstring and proves, by direct test,
that it does NOT erase genuine multiplicity: `retrieved`/`selected`/`used` events for the
same memory legitimately recur across different tasks (a different `task_id` is a real
content difference, producing a different id) — both the coalescing and the multiplicity
paths are exercised directly (`test_h2_r2_hardening.py` items 1-7).

**A second, independent gap was found while investigating this area** (not explicitly
named in the mission's own framing, but squarely within "is this a real correctness
issue"): nothing prevented two DIFFERENT (non-idempotent) `created`/`derived`/`superseded`/
`retired` events from being appended for the SAME memory — e.g. two distinct "created"
events, with different `event_id`s because they differ in `timestamp`/`reason`, both
claiming to be memory M1's origin. `memory_schema.json` models `creation_event`,
`superseded_by`, and `lifecycle_state` as SINGULAR per-memory fields, so this is a genuine
data-integrity gap, not a legitimate multiplicity case. **Implemented:** `CanonicalEvent`
now requires exactly one `memory_id` for `created`/`superseded`/`retired` (matching the
schema's singular fields; `derived`'s existing source/target consistency check already
pins its own "one target" semantics); `CanonicalEventLedger.append()` now rejects a second,
non-idempotent event of a single-occurrence type for a memory that already has one
(`SingleOccurrenceViolationError`). `created`/`derived` share one "creation slot" (a memory
is either foundation-created XOR derived, never both, per `memory_type`'s enum);
`superseded`/`retired` each own a separate slot. This enforces event-ledger DATA INTEGRITY
only — it decides nothing about WHEN a `superseded`/`retired` event should be emitted
(that remains H.3's job).

**Backward compatibility:** every existing H.2/H.2-R fixture already used exactly one
`memory_id` for `created`/`superseded`/`retired` (verified directly by inspection before
implementing — see the implementation report), so this constraint broke zero existing
tests.

## 31. Namespace enforcement (Area B) — deliberate no-format-change decision

**Investigated:** whether the `EVT-`/`BND-` prefixes (H.2-R, advisory) should become
mandatory, runtime-enforced formats.

**Decision: NO.** Enforcing `EVT-` as mandatory would retroactively invalidate every
pre-existing H.2/H.2-R caller-supplied `event_id` fixture (`"evt-001"`, `"e1"`..`"e9"`,
etc.) for a purely cosmetic reason — exactly the "arbitrary formatting more important than
semantic identity" outcome the mission itself warns against, and rewriting those fixtures
with no real migration need would violate the mission's own "do not silently break
historical H.2 fixtures" instruction. `memory_id`/`task_id`/`foundation_memory_id` also
carry no repository-standardized prefix, so imposing one only on events/boundaries (per
`B3`'s own instruction not to impose artificial prefixes where the repository has not
already defined one) would be an isolated, inconsistent special case.

**Namespace separation is instead enforced STRUCTURALLY, not by string format:**
`CanonicalEventLedger` and `ExperimentBoundaryLedger` are different classes with entirely
separate internal dictionaries and on-disk files (`events.jsonl` vs. `boundaries.jsonl`).
Proven directly (`test_h2_r2_hardening.py::test_12_event_and_boundary_ledgers_never_cross_
contaminate_even_on_id_collision`): the exact same literal string, used as both an
`event_id` in one ledger and a `boundary_id` in another, produces two independently
resolvable, never-conflated records — there is no shared table where a cross-namespace
collision could even occur, which is a stronger guarantee than a prefix convention could
ever provide (a prefix only helps a human reading a log; it does nothing to stop a
future function from being written that iterates one ledger's ids and mistakenly querying
the other). The `EVT-`/`BND-` prefixes remain exactly as advisory as before (H.2-R) —
`looks_like_generated_event_id()`/`looks_like_generated_boundary_id()`, used for nothing
but human/debugging convenience.

Memory/vendor/task ids: unchanged, no prefix imposed, per section B3's own instruction.

## 32. Boundary-ledger concurrency/ownership contract (Area C)

**Investigated:** whether `ExperimentBoundaryLedger`'s single-process/single-writer model
is sufficient for "the eventual MAMBench architecture," given formal campaigns run
multiple worker processes (`campaign_formal_runner.py`'s `c_longmemeval_worker` sharding,
confirmed directly: 3 live worker PIDs during this stage's own implementation).

**Evidence:** `campaign_formal_runner.py`'s own module docstring already states its answer
to exactly this problem for its checkpoint files: "each worker writes to its OWN checkpoint
file... to avoid any concurrent-write race condition — merged only after all workers
finish a batch, by `merge_longmemeval_worker_checkpoints()`." This is a real, already-
working, already-tested repository convention for multi-worker concurrency: ELIMINATE
concurrent writers to one file by giving each worker its own file, then merge — not make
concurrent writers to one shared file safe via locking.

**Decision:** retain the single-process/single-writer `ExperimentBoundaryLedger`
unchanged (no cross-process file lock introduced — the mission explicitly discourages
"distributed infrastructure" that is not genuinely required, and none is: no caller
actually shares one boundary-ledger `storage_dir` across processes in this stage).
**Implemented:** `experiment_boundary.merge_experiment_boundary_ledgers()` — the direct
analogue of `merge_longmemeval_worker_checkpoints()` — folds N independent per-worker
`ExperimentBoundaryLedger`s (each at its own `storage_dir`) into one target ledger via the
target's own `append()`, so a genuine conflict between two workers' boundary records (same
`boundary_id`, different payload) is still caught by the existing
`ExperimentBoundaryCollisionError` path during the merge itself, never silently resolved.
Tested directly: independent-worker isolation, successful merge, no lost records, conflict
detection during merge, and reload consistency of the merged result
(`test_h2_r2_hardening.py` items 16-20).

This ownership contract ("one `storage_dir`, one owning writer; merge afterward, never
concurrent write") is now the explicit, documented, tested model — not merely an unstated
assumption.

## 33. Integration API readiness (Area D)

**One documented construction surface per type, without removing the low-level
constructors:**

- `event_identity.build_canonical_event(event_type, memory_ids, timestamp, actor, reason,
  **kwargs)` — mints the `event_id` via `generate_event_id()` using the identical field set
  and constructs the `CanonicalEvent` in one call, so future runtime call sites do not each
  independently reinvent "call the factory, then build the event." The low-level
  `CanonicalEvent(...)` constructor remains fully available (used throughout this stage's
  own tests, deliberately, to prove the factory adds no special privilege).
- `experiment_boundary.build_reset_boundary(scope, timestamp, actor, reason)` — the
  analogous single surface for `BOUNDARY_RESET`, the only boundary type this framework's
  documented behavior actually needs (no speculative `START`/`END`/`CHECKPOINT` variant was
  added).

**Neither factory bypasses ledger validation** — both return a plain constructed object;
`CanonicalEventLedger.append()`/`ExperimentBoundaryLedger.append()` remain the sole
authority over collision/idempotency/linkage/single-occurrence, unchanged, and this is
proven directly by forging a conflicting event under a factory-generated id by hand and
confirming the ledger still rejects it (`test_22_factory_cannot_bypass_ledger_collision_
validation`).

**No runtime call-site migration was performed.** `campaign_formal_runner.py` — the live
G.1 execution path — contains no reference to `event_identity`/`experiment_boundary`/
`event_ledger`/`canonical_event` anywhere in its source (verified directly, tested:
`test_24_no_automatic_runtime_wiring`). The two factories exist as integration-READY, not
integration-DONE, infrastructure, matching every prior H.1/H.2/H.2-R stage's own posture.

## 34. Backward-compatible implementation changes

Exactly two files gained new validation, both additive and non-breaking:

- `canonical_event.py`: `created`/`superseded`/`retired` now require `len(memory_ids)==1`
  (every existing fixture already satisfied this).
- `event_ledger.py`: `append()` gained the single-occurrence check (section 30) — a NEW
  rejection path, never previously reachable, so no previously-accepted append becomes
  rejected unless it was already describing an actual data-integrity violation.

No field was removed, renamed, or had its default changed anywhere in `canonical.py`,
`ledger.py`, `canonical_write.py`, `canonical_event.py`, `event_ledger.py`,
`event_identity.py`, or `experiment_boundary.py`.

## 35. Updated invariants (H.2-R2 additions)

16. Identical canonical event content is, by definition, the same historical fact — never
    accidentally distinct, never accidentally coalesced (multiplicity is preserved exactly
    where a real content difference — e.g. `task_id` — exists).
17. A memory has at most one `created`-or-`derived` event, at most one `superseded` event,
    and at most one `retired` event, ever — enforced by `CanonicalEventLedger.append()`,
    independent of any versioning/supersession POLICY (H.3's job).
18. `CanonicalEventLedger` and `ExperimentBoundaryLedger` share no identity table — a
    literal string collision between an `event_id` and a `boundary_id` across the two
    never causes either lookup to return the other's record.
19. `ExperimentBoundaryLedger`'s ownership contract (one `storage_dir`, one writer) is
    explicit and testable, not an implicit assumption; multi-worker scenarios are handled
    by per-worker isolation + `merge_experiment_boundary_ledgers()`, never by concurrent
    writes to one file.
20. `build_canonical_event()`/`build_reset_boundary()` never grant any privilege the
    low-level constructors + ledger `append()` do not already enforce.

## 36. Remaining accepted limitations (after H.2-R2)

- `CanonicalEventLedger` itself (as opposed to `ExperimentBoundaryLedger`) still has no
  analogous `merge_*` utility — not built in this stage, since the mission's Area C was
  scoped to the boundary ledger specifically; the identical pattern would apply if/when a
  multi-worker event-ledger merge is ever needed.
- `EVT-`/`BND-` remain advisory prefixes, not enforced formats (section 31's deliberate
  decision).
- No call site anywhere constructs a real `CanonicalEvent`/`ExperimentBoundaryRecord` from
  live runtime behavior yet (section 33) — H.2 in its entirety (H.2/H.2-R/H.2-R2) remains
  integration-ready infrastructure, not yet integrated.
- The single-occurrence invariant (section 30) checks only what THIS ledger instance has
  recorded — exactly as vendor-independent and single-process-scoped as every other
  guarantee in this framework; it is not a claim about global uniqueness across ledgers a
  future multi-process integration might create (mirroring `CanonicalMemoryLedger`'s own
  documented collision-detection scope limitation from H.1).

**H.2 (H.2 base + H.2-R + H.2-R2) is recommended FROZEN, pending human review of this
report.** No further H.2 hardening pass is anticipated before H.3.
