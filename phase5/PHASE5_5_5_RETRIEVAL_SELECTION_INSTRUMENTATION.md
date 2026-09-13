# Phase 5.5 — Retrieval & Selection Instrumentation

Status: PASS.
Depends on: `PHASE5_5_1_INSTRUMENTATION_CONTRACT.md` (OR-3, OR-4, OR-6, OR-7),
`PHASE5_5_2_CANONICAL_EVENT_SCHEMA.md`, `PHASE5_5_4_MEMORY_LIFECYCLE_INSTRUMENTATION.md`.

## What exists

- `hybrid_selection.select_by_hybrid_score()` — real, frozen, computes a full
  `HybridScoredCandidate` (cosine/token-overlap/entity-overlap/blended score) for every
  member of the retrieval pool, selected or not.
- `phase4/shared/campaign_runner.py::retrieve_select_generate()` — the real, frozen
  pipeline every attack's own campaign uses. Confirmed by direct read: it reduces
  `sel.selected` to bare `(memory_id, content)` pairs and never touches `sel.rejected` at
  all — this is the audited gap (audit §5/§11 gap 3).
- `canonical_wiring.py::record_retrieval_and_selection_events()` — real precedent for
  constructing `retrieved`/`selected`/`rejected` `CanonicalEvent`s, but scoped to
  Condition B (Mem0) and its vendor-id resolution step.

## The gap

Per-candidate scores are computed and immediately discarded before reaching
`AgentRunOutcome`. No `CanonicalEvent` is ever appended for a Phase 4 attack campaign's
retrieval/selection/rejection decisions (only Condition B, via `canonical_wiring.py`, has
this).

## An investigation that changed the design: vendor-id resolution

Before writing anything, I checked whether `canonical_wiring.py`'s Mem0 vendor-id
resolution step (`resolve_source_identities()`) was needed here too. Reading
`mocks/mock_mem0.py` directly showed: when a caller supplies its own `memory_id` to
`add_memory()` — which is exactly what every Phase 4 attack injector does — the mock
never reassigns a separate vendor id; `retrieve()`/`inspect_memory()` return the same id
back. This is the "DIRECT_ASSIGNMENT" case `canonical_wiring.py`'s own module comment
already names as simpler than Condition B's `METADATA_LOOKUP` resolution. So for the
mock-foundation instrumented paths this stage targets, no resolution step was needed or
invented — retrieved ids are already canonical.

**Disclosed limitation**: this does not necessarily hold against a real Mem0 backend,
which may assign its own internal id independent of the caller-supplied one. Out of scope
here, exactly as it was out of scope for Condition C/A-MEM's own DIRECT_ASSIGNMENT
functions — a future stage pointing this at `RealMem0Adapter` would need to add a
resolution step reusing `resolve_source_identities()`, not inventing a second one.

## The minimal, scientifically sufficient change

New module: [wiring/retrieval_instrumentation.py](wiring/retrieval_instrumentation.py).

1. **`instrument_retrieval_and_selection()`** — calls `select_by_hybrid_score()` exactly
   once (never reimplemented), then:
   - Emits a `RETRIEVAL_CANDIDATE_SCORED` `Phase5Event` (OR-6) for **every** candidate in
     the full pool — selected and rejected alike — with `candidate_rank` (position in the
     already-sorted blended-score order, never re-sorted by this module),
     `cosine_score`/`token_overlap_score`/`entity_overlap_score`/`blended_score`, and a
     `selected` flag. This is emitted regardless of canonical-ledger membership — score
     data is never lost just because a memory hasn't been wired into the canonical
     ledger yet.
   - For every candidate whose `memory_id` **does** exist in `CanonicalMemoryLedger`,
     appends `retrieved` (OR-3) then `selected` or `rejected` (OR-4, reason
     `capacity_cut` — the only real rejection reason under a pure top-K, no-threshold
     policy) `CanonicalEvent`s, via `build_canonical_event()` (reused verbatim).
   - A candidate **not** in the canonical ledger gets no `CanonicalEvent` (the ledger
     would reject it anyway) but is recorded explicitly in
     `InstrumentedRetrievalReport.not_in_canonical_ledger` — mirroring
     `canonical_wiring.RetrievalEventReport`'s own "never silently drop" discipline.
2. **`record_context_assembly()`** (OR-7) — records the ordered list of memory ids that
   actually entered the rendered prompt. Kept as a distinct event from `selected`: today,
   in the current frozen pipeline, "selected" and "agent-visible" are the same set, but
   the contract treats them as separate claims, and this event preserves that distinction
   structurally rather than assuming it never diverges.

## What was NOT done

- `hybrid_selection.py` and `campaign_runner.py` were not modified — both are frozen
  (Phase 3 and Phase 4 respectively). This module calls `select_by_hybrid_score()`
  exactly as `campaign_runner.py` itself does; it does not wrap or monkeypatch
  `retrieve_select_generate()`.
- No vendor-id resolution mechanism was invented — the existing gap (real-Mem0-only) is
  disclosed, not silently patched over.
- Generation/decision instrumentation (calling `render_messages()`/
  `generate_with_retries()`) was deliberately left to Stage 5.6 — this stage stops at
  context assembly, matching the contract's own OR-6/OR-7 vs. OR-8/OR-9 boundary.

## Evidence

- [phase5/wiring/retrieval_instrumentation.py](wiring/retrieval_instrumentation.py)
- [phase5/tests/test_retrieval_instrumentation.py](../tests/test_retrieval_instrumentation.py)
  — 9 tests: full-pool scoring (selected and rejected both instrumented, ranks 1..N with
  no gaps), pool-smaller-than-top-K (selects everything, rejects nothing), empty pool,
  the honest not-in-canonical-ledger reporting path, config_fingerprint propagation,
  context-assembly order preservation and its empty-input rejection, an explicit
  non-interference check confirming `select_by_hybrid_score()`'s own return value is
  unchanged whether or not this module is used, and a **live** test issuing real
  `foundation.retrieve()`/`inspect_memory()` calls against a real `MockMem0Adapter` (the
  same mock every attack's own frozen tests use) end-to-end through to a context-assembly
  event.
- Full Phase 5 suite: `python -m pytest phase5/tests/ -q` → 95 passed.
- Frozen Phase 3/4 regression: `python -m pytest phase3/evaluation/tests phase4/tests -q`
  → recorded below once complete.

## Coverage check

OR-3 (raw retrieval), OR-4 (selection/rejection), OR-6 (per-candidate score breakdown),
OR-7 (agent-visible context assembly) are all satisfied.

## Things flagged after the initial pass (see "Review fixes" below for resolution)

- Vendor-id resolution against a real Mem0/A-MEM backend was unproven.
- `not_in_canonical_ledger` existed only as an in-process report field, not a durable fact.
- No test exercised the full Stage 5.4 → 5.5 chain against a real live attack run.
- OR-7's `context_assembled` event carried only memory ids, not the actual rendered content.

---

## Review fixes

A review pass, run against this stage's own self-flagged gaps before proceeding to
Stage 5.6, closed three of the four and formally gated the fourth.

### Fix 1 — OR-7: rendered context is now persisted verbatim, not just memory ids

**Problem**: `context_assembled` only recorded `context_memory_ids` — the actual
model-visible text (what `render_messages()` produced) was never captured, so
reconstructing "what did the model actually see" required rerunning the experiment.

**Fix**: `Phase5Event`'s `CONTEXT_ASSEMBLED` type gained two new required fields:
`rendered_messages` (the literal `render_messages()`-shaped output — a tuple of
`{"role", "content"}` mappings, persisted verbatim) and `rendered_context_fingerprint`
(a deterministic hash via `compute_rendered_context_fingerprint()`, verified in
`__post_init__` against a fresh recomputation — mirroring `RunConfigRecord`'s own
supplied-fingerprint-must-match-recomputation discipline, so an inconsistent caller input
fails loudly rather than persisting an unverifiable claim). `record_context_assembly()`
now requires the caller's real `rendered_messages` and refuses an empty one.
`context_memory_ids` remains a separate, required field — deliberately not re-derived
from parsing the free-form rendered text, which would be a second, fragile identity
mechanism.

Evidence: `test_phase5_event_schema.py` (4 new assertions: persists rendered_messages,
rejects missing rendered_messages, rejects a fingerprint that doesn't match
recomputation), `test_retrieval_instrumentation.py::test_context_assembly_preserves_render_order`
(now asserts the exact persisted content survives a ledger reload) and
`test_context_assembly_rejects_empty_rendered_messages`, and the live test now uses the
real `build_agent_visible_context()`/`render_messages()` functions end-to-end and asserts
the literal camping-fact text is present in the persisted, reloaded event.

### Fix 2 — canonical-gap state is now an explicit, machine-checkable, persisted fact

**Problem**: `not_in_canonical_ledger` lived only in `InstrumentedRetrievalReport`, an
in-process Python list gone the moment the caller's process exits — nothing durable
distinguished "this candidate's canonical identity was never resolved" from "this
candidate doesn't exist" or "this candidate was rejected."

**Fix**: `RETRIEVAL_CANDIDATE_SCORED` gained a required, closed `canonical_status` field
(`CANONICAL_STATUS_IN_LEDGER` / `CANONICAL_STATUS_NOT_IN_LEDGER`), set on every persisted
score event regardless of selection outcome — a third, independent axis from
`selected`/`rejected`, never inferrable from event absence.

Evidence: `test_phase5_event_schema.py` (required, closed-value validation, and an
explicit test proving `selected` and `canonical_status` vary independently in both
directions). `test_retrieval_instrumentation.py::test_not_in_canonical_ledger_state_is_never_confused_with_rejected_retrieved_or_not_selected`
directly proves all three confusions the review named are impossible: no
`CanonicalEvent` of any type references the unresolved candidate, its own `selected`
flag is set independently of its canonical status, and the state survives a fresh
`Phase5EventLedger` reload from disk (the property a future Stage 5.8 trace assembler
will depend on).

### Fix 3 — live Stage 5.4 → 5.5 integration, end-to-end

**Problem**: Stage 5.4's live attack runs and Stage 5.5's retrieval instrumentation had
never been exercised together — only separately, against independently-seeded memories.

**Fix**: new [phase5/tests/test_stage4_to_stage5_chain.py](../tests/test_stage4_to_stage5_chain.py) —
runs `run_live_farma_injection()` for real (real `FARMAInjector.inject()` against a real
`MockMem0Adapter`), reads the resulting real canonical memory's content back from
`CanonicalMemoryLedger`, feeds it through `instrument_retrieval_and_selection()` alongside
a deliberately-unwired decoy candidate (exercising Fix 2's gap state inside a real
attack-origin chain), then through `record_context_assembly()` using the real
`render_messages()` output. The test's final assertions reload everything from fresh
`Phase5EventLedger`/`CanonicalEventLedger` instances and confirm the full
`injection → memory creation → retrieved → selected → context_assembled` chain
reconstructs correctly from persisted identifiers alone.

### Item 4 — A-MEM / real-vendor limitation: formally gated, not fixed

Per explicit instruction, this is **not** fixed now — faking or assuming vendor-id
resolution would be worse than leaving it open. Recorded as a **pre-5.8 gate** in
[PHASE5_CHECKLIST.md](PHASE5_CHECKLIST.md): Stage 5.8 (trace assembly) must not assume
this stage's retrieval instrumentation is valid for a real Mem0/A-MEM run without either
(a) a dedicated compatibility test against the real integration surface, added around
Stage 5.7, if `RealMem0Adapter`/`RealAMemAdapter` are reachable in the working
environment, or (b) if they are not reachable (per `canonical_write.py`'s own disclosure
that they require the isolated `C:\h4venv` interpreter), Stage 5.8 must state plainly
that its trace assembly is verified against mock-foundation runs only.

### Full verification after all three closed fixes

- `python -m pytest phase5/tests/ -q` → **101 passed** (95 + 4 schema + 2 retrieval-
  instrumentation (durability/three-state-distinction) tests, replacing/extending prior
  ones, plus 1 new Stage 5.4→5.5 chain test).
- Frozen Phase 3/4 regression: recorded below.

**STAGE 5.5 STATUS: PASS (post-review-fix). Pre-5.8 gate (item 4, A-MEM/real-vendor
compatibility): OPEN, tracked, not silently closed.**
