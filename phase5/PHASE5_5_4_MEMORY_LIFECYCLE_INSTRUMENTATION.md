# Phase 5.4 — Memory Lifecycle Instrumentation

Status: PASS (revised after review — see §"Review fixes" below; original content
retained above it, not overwritten).
Depends on: `PHASE5_5_1_INSTRUMENTATION_CONTRACT.md` (OR-1, OR-2, OR-5, OR-11),
`PHASE5_5_2_CANONICAL_EVENT_SCHEMA.md`, `PHASE5_5_3_RUN_IDENTITY.md`.

## What exists

- `canonical_write.write_canonical_memory()` — the real, tested, authoritative write
  path (canonical record → `CanonicalMemoryLedger` → foundation → alias).
- `event_identity.build_canonical_event()` — mints an id and constructs a `CanonicalEvent`
  in one call.
- `memory_versioning.supersede_memory()` — H.3's authoritative supersession mechanism.
- `canonical_wiring.py` — proves this exact "build events, call the existing mechanism"
  pattern already works, for Phase 3's Condition B (Mem0) campaign path only.
- Confirmed by direct read: `CanonicalEventLedger.append()` requires the referenced
  `memory_id` to already exist in `CanonicalMemoryLedger` — so `created`/`derived` events
  must always be appended *after* `write_canonical_memory()`, never before.

## The gap

Per the audit, this is the single most load-bearing finding: **no wiring between Phase 4
attack campaigns and the Phase 3 ledgers at all.** Every real attack injector writes
memories via bare `foundation.add_memory()`; none call `write_canonical_memory()`; no
`created` `CanonicalEvent` is ever appended for an attack-injected memory.

## The minimal, scientifically sufficient change

New module: [wiring/memory_lifecycle.py](wiring/memory_lifecycle.py), providing three
functions that **call, never reimplement**, the existing Phase 3 mechanisms:

1. **`record_memory_creation()`** (OR-1) — calls `write_canonical_memory()`, then appends
   a `created` `CanonicalEvent` (via `build_canonical_event()`), then registers
   `EventRunMembership`. If an `attack_context` mapping is supplied (normalized
   `attack_id`/`injection_id`/`artifact_id`/`admission_status` — never an attack's own
   differently-shaped result dataclass, so the function itself contains zero
   attack-specific branching, satisfying the "common across all seven attacks"
   constraint), it additionally appends an `attack_injection` `Phase5Event` (OR-11) and
   registers its membership too. Steps 1–3 are unconditional; attack instrumentation is
   strictly additive on top, never a fork in the memory-lifecycle path — a clean memory
   and an attacker-originated memory are instrumented identically at the base level.
2. **`record_memory_derivation()`** (OR-5) — same pattern for a `derived` event: the
   derived memory must exist first, then the `derived` event is appended with
   `source_memory_ids`/`target_memory_id` exactly as `CanonicalEvent`'s own validation
   requires.
3. **`record_memory_lifecycle_transition()`** (OR-2) — a thin wrapper over
   `memory_versioning.supersede_memory()`, registering membership only for whichever
   event ids that function reports as actually appended (its own documented "honest
   partial state" semantics are preserved, never assumed-complete).

**New persistence introduced**: `schema/event_ledger.py::Phase5EventLedger` — the
append-only JSONL store for `Phase5Event` (Stage 5.2 defined the schema but not its
storage; this is the first stage that actually needs to durably record one). Mirrors
`CanonicalEventLedger`'s exact discipline (JSONL, fsync, idempotent-vs-collision policy,
fold-on-reload) — no new persistence mechanism invented.

## What was NOT done

- No Phase 4 attack injector (`FARMAInjector`, etc.) was modified. Adoption (calling
  `record_memory_creation()` from an attack's own campaign script) is a separate,
  per-campaign integration step, deliberately left for later — this stage's job was to
  make the common instrumentation available, not to retrofit all 7 attacks in one pass.
- No frozen Phase 3 file was edited. `write_canonical_memory`, `build_canonical_event`,
  and `supersede_memory` are called exactly as they exist.
- No attack-specific logic lives inside `phase5/wiring/`. `record_memory_creation()`
  never inspects which attack it's being called for — the caller normalizes first.

## Evidence

- [phase5/wiring/memory_lifecycle.py](wiring/memory_lifecycle.py)
- [phase5/schema/event_ledger.py](schema/event_ledger.py)
- [phase5/tests/test_memory_lifecycle_wiring.py](../tests/test_memory_lifecycle_wiring.py)
  — 7 tests against real, file-backed Phase 3 ledgers (no mocking of the ledgers
  themselves): clean-memory creation, attacker-originated creation with a real
  `attack_injection` event recorded and queryable by `attack_id`, the required-ledger
  guard, derivation (parent → child, `source_memory_ids`/`target_memory_id` correctness),
  a full supersession/retirement round trip via the real `supersede_memory()`, and an
  explicit non-interference check confirming `write_canonical_memory()`'s own collision
  behavior is unchanged whether or not this wiring module is used first.
- Full Phase 5 suite: `python -m pytest phase5/tests/ -q` → 27 passed.
- Regression check:
  `python -m pytest phase3/evaluation/tests/test_canonical_event_ledger_h2.py phase3/evaluation/tests/test_h2_remediation.py phase3/evaluation/tests/test_h3_versioning.py phase4/tests -q`
  → 230 passed, unchanged.

## Coverage check

OR-1 (creation), OR-2 (lifecycle transition), OR-5 (derivation), OR-11 (attack injection)
are all satisfied. OR-3/OR-4 (raw candidate retrieval, selection/rejection) remain
Stage 5.5's scope — this stage deliberately did not reach into the retrieval funnel.

---

## Review fixes (post-PASS)

A review of the original Stage 5.4 pass raised three issues. All three are fixed below,
with tests, without reopening the original design decisions that still hold.

### Issue 1 — OR-11 was not independent of memory creation

**Problem**: the original `record_memory_creation()` only recorded an `attack_injection`
event as a side effect of creating a memory — so a **rejected** injection attempt (no
memory ever created) had no instrumentation path at all, contradicting OR-11's own
requirement ("independently of memory creation").

**Fix**: extracted `record_attack_injection()` as a standalone function in
[wiring/memory_lifecycle.py](wiring/memory_lifecycle.py) — takes only normalized keyword
arguments (`attack_id`, `injection_id`, `artifact_id`, `admission_status`, optional
`memory_id`), records the injection attempt unconditionally (admitted, rejected, or any
other admission outcome — see Issue 3's MemoryGraft finding), and validates the
`memory_id`/`admission_status` pairing symmetrically (required when admitted, forbidden
otherwise). `record_memory_creation()` now calls this same function internally for its
own (admitted-only) case, rather than duplicating the event-construction logic — and now
explicitly **refuses** to be called with a rejected `admission_status`, since it always
creates a memory and a rejected artifact has none to create; that case must go through
`record_attack_injection()` directly.

Evidence: `phase5/tests/test_memory_lifecycle_wiring.py` — `test_record_attack_injection_admitted_independent_of_memory_creation`
(proves no memory is written by this call), `test_record_attack_injection_rejected_is_recorded_with_no_memory_id`,
`test_record_attack_injection_rejects_inconsistent_memory_id`,
`test_record_memory_creation_refuses_rejected_admission_status`.

### Issue 2 — partial/incomplete instrumentation sequences were not detectable

**Problem**: `record_memory_creation()`/`record_attack_injection()` write across
independent ledgers sequentially (memory → event → membership, or event → membership).
Every ledger already fails loudly on a bad write, but nothing let a later reader ask "did
this specific memory's/injection's instrumentation actually finish?" — a real, already
observed failure shape (`EventRunMembershipLedger.append()` checks `run_id` existence
*before* writing, so an unregistered `run_id` raises `UnknownRunError` strictly *after*
the preceding event write already committed, leaving a durable, un-membershipped orphan).

**Fix**: new module [wiring/completeness.py](wiring/completeness.py) —
`check_memory_creation_completeness()` and `check_attack_injection_completeness()`,
read-only queries (never repair, never retry) that independently re-derive, from current
ledger state, whether every expected stage (memory exists / event recorded / membership
recorded / membership matches the expected `run_id`) actually happened, returning
`is_complete` plus a `missing_stages()` list naming exactly what's absent. No ledger
semantics, transaction model, or atomicity guarantee was changed — this is pure
observation of existing, unmodified ledger behavior, consistent with this framework's own
"honest partial state, never silently repaired" convention (`supersede_memory()`'s own
docstring).

Evidence: [phase5/tests/test_completeness.py](../tests/test_completeness.py) — 8 tests,
including two that reproduce the real orphaning failure mode end-to-end (call the wiring
function with an unregistered `run_id`, catch the raised `UnknownRunError`, then prove
the completeness check correctly reports `is_complete=False` for the resulting durable
orphan — for both the memory-creation and the attack-injection path), a wrong-run-id
mismatch case, and a non-interference check proving the completeness queries themselves
never mutate ledger state.

### Issue 3 — only one attack (FARMA, in tests) was ever wired

**Problem**: the original stage demonstrated the shared instrumentation against FARMA
only; the other 6 frozen attacks had no adaptation to the common shape and no integration
checklist tracking that gap.

**Fix**: new module [wiring/attack_integration.py](wiring/attack_integration.py) — one
`normalize_<attack>_injection()` function per attack (mapping each attack's own real,
differently-named result fields — `poison_id`/`step_id`/`scenario_id`/`artifact_id` — into
one common `NormalizedInjection` shape), registered in a `NORMALIZERS` dict, dispatched
through exactly one shared function, `instrument_attack_injection()`, which is the only
call site for `record_attack_injection()`. No attack-specific branching exists outside
the 7 small, independent normalizer functions — each is pure field mapping, calling no
ledger itself. Also added `generate_injection_id()` (same deterministic-fingerprint
discipline as `generate_run_id()`/`generate_episode_id()`), closing the audit's finding
that `injection_id` was named in the abstract attack contract but never implemented.

New tracking artifact: [PHASE5_5_4_SEVEN_ATTACK_INTEGRATION_CHECKLIST.md](PHASE5_5_4_SEVEN_ATTACK_INTEGRATION_CHECKLIST.md)
— all 7/7 attacks PASS (normalizer exists, registered, tested against that attack's real,
unmodified result type).

**Notable finding surfaced while wiring all 7**: MemoryGraft has a genuine third
admission outcome, `ADMISSION_NOT_ADMITTED` (its persistence gate can discard an artifact
before any write is attempted), not just `ADMITTED`/`REJECTED` like the other six. This
was not previously documented at the cross-attack level. No schema change was needed —
`Phase5Event.admission_status` already accepted any non-empty string (a Stage 5.2
design decision that turned out to matter here) — but it is called out explicitly in the
checklist rather than silently normalized away.

**Scope kept out deliberately**: no Phase 4 attack file (injector, adapter, or frozen
campaign script) was modified — adoption of `instrument_attack_injection()` inside a
*live* campaign run is a separate step from having the shared instrumentation exist and
be correct, and per the master prompt Phase 4's frozen artifacts are not edited. Full
`record_memory_creation()` wiring for all 7 (constructing a `CanonicalMemoryRecord` from
each attack's `stored_text`) was also deliberately not forced in this pass, since the
correct `source`/content mapping per attack has not been reviewed and none of
`memory_schema.json`'s three existing `source_type` values literally means
"attacker-injected" — flagged explicitly in the checklist as a follow-on, not silently
dropped.

### Full verification after the first three fixes

- `python -m pytest phase5/tests/ -q` → **57 passed** (27 original + 8 completeness +
  19 attack-integration + 3 new/changed memory-lifecycle tests replacing the one test
  the `record_memory_creation()` refactor obsoleted).

---

## Second review pass — four targeted fixes

A second review, after explicitly being asked to flag remaining gaps rather than declare
PASS blindly, surfaced four more items. All four are fixed below.

### Fix 1 — completeness checks for derivation and supersession

**Problem**: `check_memory_creation_completeness()` covered foundation-origin creation
only in name; derivation and supersession (`record_memory_derivation()`/
`record_memory_lifecycle_transition()`) had no equivalent completeness check, so an
orphaned derived or superseded/retired event would go undetected.

**Fix**: confirmed `check_memory_creation_completeness()` already structurally covers
derivation (its `_CREATION_EVENT_TYPES` tuple includes `EVENT_DERIVED`, not just
`EVENT_CREATED`) — documented this explicitly and added tests proving it (a complete
derivation case and a real orphaned-derived-event case, reproduced the same way as the
foundation-creation orphan). For supersession, added a genuinely new
`MemorySupersessionCompleteness`/`check_memory_supersession_completeness()` in
[wiring/completeness.py](wiring/completeness.py), checking: the `superseded` event
recorded + membershipped, the `SupersessionRecord` link itself present
(`SupersessionLedger.superseder_of()`), and the `retired` event recorded + membershipped
— each independently, so a reader can tell exactly which of the three facts is missing.

Evidence: [phase5/tests/test_completeness.py](../tests/test_completeness.py) gained 5
tests — complete-derivation, orphaned-derivation (reproducing the real `UnknownRunError`
failure mode), complete-supersession, orphaned-supersession (both events durably written,
both memberships missing — proving the checker distinguishes "the underlying fact
exists" from "it's attributed to this run"), and never-recorded-supersession.

### Fix 2 — audited all 7 attacks' content/source mapping; wired admitted memories to canonical creation

**Problem**: the original pass left `record_memory_creation()` wiring entirely out for
all 7 attacks, citing an unresolved `source_type` mapping.

**Fix**: a real audit (documented in full in
[wiring/attack_integration.py](wiring/attack_integration.py)'s module docstring) found:
CONTENT is resolvable for all 7 — 6 attacks expose it as `.stored_text` directly on their
result; MemoryGraft's real written text (`artifact.resp`) is available to whichever
caller holds the original artifact, just not on `MemoryGraftInjectionResult` itself, so
`instrument_attack_memory_lifecycle()` accepts an explicit `stored_text_override` for
that one case — not a guess, the literal text the frozen injector itself wrote. SOURCE
remains genuinely ambiguous: none of `memory_schema.json`'s three `source_type` values
(`phase2_umr`, `derivation_event`, `future_observation`) is written to mean
"attacker-injected"; `future_observation`'s own description says "future
LEGITIMATE-observation," which attacker content is not. The judgment call made (fully
documented, not hidden): use `future_observation` as the structurally-closest fit, always
paired with an explicit, never-omitted `attacker_originated: True` +
`attack_id`/`artifact_id` marker in the same `source` object, so no reader mistakes it for
a claim of legitimacy. This is flagged as a disclosed architectural decision a future
reviewer may want to revisit (e.g. by adding a fourth, reviewed `source_type` to the
frozen schema) — not asserted as final.

New functions: `build_attack_canonical_memory_record()` (the one place this judgment call
is made) and `instrument_attack_memory_lifecycle()` (the full injection → admission →
memory creation → `created`-event orchestrator, returning `AttackMemoryLifecycleResult`).
Rejected/non-admitted injections (any `admission_status != ADMITTED`, including
MemoryGraft's `NOT_ADMITTED`) never attempt memory creation — `memory_creation` is simply
`None` on the result, satisfying contract OR-11 as before.

Evidence: [phase5/tests/test_attack_integration.py](../tests/test_attack_integration.py)
gained 9 tests — a full injection→memory→created-event chain test for all 7 attacks
(6 direct, MemoryGraft via `stored_text_override`), a test proving MemoryGraft's admitted
case raises rather than silently skipping when no override is given, a
rejected/not-admitted test proving no memory creation is attempted, and a
required-`memory_id` validation test for `build_attack_canonical_memory_record()`.

### Fix 3 — concurrency documentation + duplicate-`memory_id` invariant

**Problem**: `Phase5EventLedger`'s single-writer/no-cross-process-lock limitation
(inherited from every other ledger in this framework) was never stated explicitly for
Phase 5's own new ledger; and nothing prevented two different `attack_injection` events
from both claiming the same `memory_id`.

**Fix**: added an explicit "CONCURRENCY — EXPLICIT LIMITATION" section to
[schema/event_ledger.py](schema/event_ledger.py)'s module docstring, stating the
inherited limitation plainly rather than leaving it implicit. Separately — this is
Phase 5's own new, additive ledger, not a frozen one, so hardening it does not violate
"do not redesign frozen ledgers" — added a real invariant: `Phase5EventLedger.append()`
now raises `DuplicateMemoryClaimError` if a new (non-idempotent) `attack_injection` event
would claim a `memory_id` already claimed by a different existing `attack_injection`
event (checked before the write, mirroring `CanonicalEventLedger`'s own
single-occurrence-check timing). An idempotent re-append of the literal same event is
unaffected.

Evidence: new [phase5/tests/test_phase5_event_ledger.py](../tests/test_phase5_event_ledger.py)
— 5 tests: two different attacks colliding on one `memory_id`, the same attack with two
different artifacts colliding, idempotent re-append unaffected, two rejected
(`memory_id=None`) injections never falsely triggering the invariant, and the invariant
holding against events reloaded from a previous ledger instance (not just in-process
history).

### Fix 4 — pre-5.9 gate: live instrumented runs for all 7 attacks

**Problem**: every attack-integration test to this point hand-constructed an
`InjectionResult` dataclass directly — proving the *adapter* (normalizer) layer is
correct, but never actually invoking a real attack's real `.inject()` method. The user's
gate explicitly requires distinguishing "7/7 adapters exist" from "7/7 attacks actually
produce instrumentation in live runs," and blocks Stage 5.9 until the latter is
demonstrated for all 7.

**Fix**: new, additive module [wiring/live_attack_runs.py](wiring/live_attack_runs.py) —
one `run_live_<attack>_injection()` function per attack. Each constructs a real
`MockMem0Adapter` (the same real Phase 3 mock every attack's own frozen unit test already
uses) and the attack's own real artifact/sequence/scenario type, calls the REAL,
unmodified `Injector.inject()` method (not a hand-built result), and routes the real
result through `instrument_attack_memory_lifecycle()`. DSRM needs no LLM (confirmed by
reading its own test file — the LLM machinery there is for CSRM/self-refine generation
upstream of `inject()`, not `inject()` itself); Sleeper and MemoryGraft have a real
in-`inject()` LLM judgment gate, so their runners use a scripted `LlamaServerProvider`
transport — the exact same dependency-injection pattern (and, functionally, the same
technique) each attack's own frozen test file already uses to avoid a real network call,
copied here rather than imported from a test module (production/wiring code should not
depend on test files). No Phase 4 attack file — injector, adapter, or frozen campaign
script — was read for anything beyond import, let alone modified.

New pre-5.9 gate tracking: see the updated
[PHASE5_5_4_SEVEN_ATTACK_INTEGRATION_CHECKLIST.md](PHASE5_5_4_SEVEN_ATTACK_INTEGRATION_CHECKLIST.md),
which now records **7/7 live instrumented attack paths verified** as a separate row from
adapter-level PASS.

Evidence: new [phase5/tests/test_live_attack_runs.py](../tests/test_live_attack_runs.py)
— 10 tests: one live-run-produces-full-chain test per attack (MINJA asserts all 3 of its
real per-step results; Sleeper and MemoryGraft each get both a KEEP/admitted and a
DISCARD/not-admitted live run, the latter proving "rejected/non-admitted injections
remain represented without requiring a memory record" live, not just in a unit test), and
one final gate test that runs all 7 in sequence and asserts the full expected `attack_id`
set was actually produced — this is the literal, automated check for the gate's
`7/7 live instrumented attack paths verified = PASS` condition.

### Full verification after all four fixes

- `python -m pytest phase5/tests/ -q` → **86 passed** (57 + 5 completeness (derivation +
  supersession) + 9 attack-integration (full chain) + 5 event-ledger invariant +
  10 live-attack-run).
- Frozen Phase 3/4 regression: `python -m pytest phase3/evaluation/tests phase4/tests -q`
  → **1845 passed, 17 skipped** (pre-existing skips, unrelated to this work), 0 failures,
  in 389s. Zero impact on frozen baselines.

**STAGE 5.4 STATUS: PASS (post-second-review-fix). Pre-5.9 gate: 7/7 live instrumented
attack paths verified.**
