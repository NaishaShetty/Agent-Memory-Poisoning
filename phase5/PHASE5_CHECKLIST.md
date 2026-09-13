# MAMBench — Phase 5: Instrumentation & Monitoring — Checklist

Canonical, living status tracker for Phase 5. Update this file as each stage completes.

```
[x] 5.1  Observability Requirements & Instrumentation Contract       — PASS
[x] 5.2  Canonical Event Schema                                      — PASS
[x] 5.3  Experiment / Run / Episode Identity                         — PASS
[x] 5.4  Memory Lifecycle Instrumentation                            — PASS
[x] 5.5  Retrieval & Selection Instrumentation                       — PASS
[x] 5.6  Agent Decision & Action Instrumentation                     — PASS
[x] 5.7  Provenance, Lineage & Memory Interaction Instrumentation    — PASS
[x] 5.8  Trace Assembly & Propagation Graph                          — PASS
[x] 5.8A Memory Behavior Dataset Derivation                          — PASS
[x] 5.9  Validation, Non-Interference & Instrumentation Freeze       — PASS
```

PHASE 5 STATUS: COMPLETE — FROZEN. See "Official Freeze Statement" at the end of this
document for the canonical declaration and final regression counts.

## Stage deliverables so far

- 5.1 → `PHASE5_5_1_INSTRUMENTATION_CONTRACT.md` (15 requirements, OR-1..OR-15)
- 5.2 → `PHASE5_5_2_CANONICAL_EVENT_SCHEMA.md`, `schema/event.py`, `tests/test_phase5_event_schema.py`
- 5.3 → `PHASE5_5_3_RUN_IDENTITY.md`, `identity/run_identity.py`, `tests/test_run_identity.py`
- 5.4 → `PHASE5_5_4_MEMORY_LIFECYCLE_INSTRUMENTATION.md`, `wiring/memory_lifecycle.py`, `schema/event_ledger.py`, `tests/test_memory_lifecycle_wiring.py`
  - Review fixes (round 1): `wiring/completeness.py`, `wiring/attack_integration.py`, `PHASE5_5_4_SEVEN_ATTACK_INTEGRATION_CHECKLIST.md`, `tests/test_completeness.py`, `tests/test_attack_integration.py`
  - Review fixes (round 2): derivation/supersession completeness, `attack_integration.build_attack_canonical_memory_record`/`instrument_attack_memory_lifecycle` (full chain wiring, all 7 attacks), `Phase5EventLedger` duplicate-memory_id invariant + concurrency docs, `wiring/live_attack_runs.py` (pre-5.9 gate: 7/7 live instrumented attack paths VERIFIED), `tests/test_phase5_event_ledger.py`, `tests/test_live_attack_runs.py`
  - Phase 5 suite: 86 passed. Frozen Phase 3/4 regression: 1845 passed, 17 skipped (pre-existing), 0 failures.
- 5.5 → `PHASE5_5_5_RETRIEVAL_SELECTION_INSTRUMENTATION.md`, `wiring/retrieval_instrumentation.py`, `tests/test_retrieval_instrumentation.py`
  - Review fixes: OR-7 rendered-context persistence (`rendered_messages`/`rendered_context_fingerprint` on `Phase5Event`), `canonical_status` explicit gap-state field, `tests/test_stage4_to_stage5_chain.py` (live Stage 5.4→5.5 chain), item 4 (A-MEM/real-vendor) formally gated pre-5.8 (see "Pre-5.8 gate" section below), not fixed.
  - Phase 5 suite: 101 passed. Frozen Phase 3/4 regression: 1845 passed, 17 skipped (pre-existing), 0 failures.
- 5.6 → `PHASE5_5_6_AGENT_DECISION_ACTION_INSTRUMENTATION.md`, `wiring/agent_decision_instrumentation.py`, `tests/test_agent_decision_instrumentation.py`, `tests/test_full_pipeline_chain.py` (proactive full 5.4→5.5→5.6 chain test)
  - Phase 5 suite: 109 passed. Frozen Phase 3/4 regression: 1845 passed, 17 skipped (pre-existing), 0 failures.
- 5.7 → `PHASE5_5_7_PROVENANCE_LINEAGE_INSTRUMENTATION.md`, `wiring/lineage.py`, `tests/test_lineage.py`, `tests/test_real_vendor_compatibility_gate.py`, `tests/test_full_pipeline_chain.py` (extended with lineage assertions)
  - Review fixes: `tainted_memory_evidence()` (genuine per-hop PROPAGATED_TO grounding), `derive_co_retrieved_edges()`/`derive_co_selected_edges()` (deterministic pairwise edges), 2 future-ready real-vendor compatibility tests (skip, NOT VALIDATED)
  - Phase 5 suite: 136 passed, 2 skipped (by design). Frozen Phase 3/4 regression: 1845 passed, 17 skipped (pre-existing), 0 failures.
  - **Reopened (2026-09-13, by explicit user instruction, after the Post-Phase-5 freeze)**: closed the `REFERENCES` gap the hardening pass had deliberately left open. Added `derive_references_edges()` — a structural, deterministic content-citation signal (a memory's content literally containing another real memory's `[memory_id]` bracket citation), grounded in the citing memory's real creation-type event, never an agent-behavior/usage claim (the hardening report's Sec 10 rejection of inferring "the model referenced this" from semantic similarity is unchanged and not revisited). 6 new tests. Phase 5 suite: 194 passed, 2 skipped. `build_propagation_graph()` (Stage 5.8) was intentionally NOT updated in this same reopening — deliberately scoped narrower, flagged as a follow-up. **Refrozen.** See `PHASE5_5_7_PROVENANCE_LINEAGE_INSTRUMENTATION.md`'s "Reopening" section for full detail.
  - **Follow-up reconciled (2026-09-13, same day, final Phase 5.8–5.9 reconciliation pass)**: the `build_propagation_graph()` follow-up flagged above was itself resolved — see the 5.8 entry immediately below.
- 5.8 → `PHASE5_5_8_TRACE_ASSEMBLY_PROPAGATION_GRAPH.md`, `wiring/trace_assembly.py`, `tests/test_trace_assembly.py`
  - Phase 5 suite: 145 passed, 2 skipped (by design). Frozen Phase 3/4 regression: 1845 passed, 17 skipped (pre-existing), 0 failures.
  - Clarified (2026-09-12): attribution is intentionally NOT implemented in Phase 5. Phase 5 instruments and preserves the evidence required for later attack-origin attribution/lineage reconstruction; ExperimentTrace/PropagationGraph make no attribution claim. Not a gap — a scope boundary. (Attribution has since been implemented separately, 2026-09-13 — see "Attribution layer" section below; this scope statement about Phase 5 itself is unaffected.)
  - **Reconciled (2026-09-13, final Phase 5.8–5.9 reconciliation pass)**: `build_propagation_graph()` now also composes `derive_references_edges()` (Stage 5.7's own reopening, above) — evidence-based decision: this function's own documented contract has always been "every applicable Stage 5.7 `derive_*` function," and the pre-existing composition of `USED_BY`/`RETRIEVED_WITH`/`SELECTED_WITH` already showed the graph represents the COMPLETE Stage 5.7 relationship vocabulary, not a propagation/lineage-only subset — so `REFERENCES` belonged once a real producer existed. 8 new tests (real edge composed + grounded, no edge without exact citation, no edge from word overlap, no self-reference, never `INFLUENCED`, deterministic, fresh-reload-stable, run-isolated). Phase 5 suite: 203 passed, 2 skipped. **Refrozen.** See `PHASE5_5_8_TRACE_ASSEMBLY_PROPAGATION_GRAPH.md`'s "Reconciliation" section for full detail.
- 5.8A → `PHASE5_5_8A_MEMORY_BEHAVIOR_DATASET.md`, `wiring/memory_behavior_dataset.py`, `tests/test_memory_behavior_dataset.py`, `datasets/memory_behavior_dataset_sample.jsonl` (real generated 10-record dataset)
  - Phase 5 suite: 154 passed, 2 skipped (by design). Frozen Phase 3/4 regression: 1845 passed, 17 skipped (pre-existing), 0 failures.
  - **Reconciled (2026-09-13, final Phase 5.8–5.9 reconciliation pass)**: no code change needed — `_relationship_record()` already builds a `memory_relationship` record generically from any `MemoryInteractionEdge`, so `REFERENCES` records flow through the existing category automatically once Stage 5.8 supplies the edge. No seventh dataset category created. 1 new test confirming this. See `PHASE5_5_8A_MEMORY_BEHAVIOR_DATASET.md`'s "Reconciliation" section.
- 5.9 → `PHASE5_5_9_VALIDATION_NONINTERFERENCE_FREEZE.md`, `wiring/validation.py`, `tests/test_phase5_9_validation.py`. Real finding during development: provenance-isolation check's original `attack_id`/`artifact_id` markers produced a false positive (FARMA's `artifact_id` legitimately equals the agent-visible `memory_id` under DIRECT_ASSIGNMENT) — corrected to check only `injection_id`. Definitive non-interference test: identical real computation via raw primitives vs. Phase 5 wiring, all master-prompt-named observables identical. **Instrumentation Contract (5.1) and Canonical Event Schema (5.2) now FROZEN.**
  - Phase 5 suite: 160 passed, 2 skipped (by design). Frozen Phase 3/4 regression: 1845 passed, 17 skipped (pre-existing), 0 failures — confirmed (see Official Freeze Statement below for the final, post-reconciliation counts).
  - **Reconciled (2026-09-13, final Phase 5.8–5.9 reconciliation pass)**: re-verified every validation dimension against the final 5.7 (`REFERENCES` reopening) + 5.8 (`REFERENCES` composed into `build_propagation_graph()`) state — completeness (OR-1..15 still 15/15 DIRECT), ordering, run/episode consistency, provenance isolation, non-interference, determinism, fresh reload, and attribution readiness all confirmed unaffected or improved, none regressed. See `PHASE5_5_9_VALIDATION_NONINTERFERENCE_FREEZE.md`'s "Reconciliation" section for the full, itemized re-verification.

**PHASE 5 STATUS: ALL 10 STAGES COMPLETE.**

## Post-freeze hardening pass (2026-09-13)

See [PHASE5_POST_FREEZE_HARDENING_REPORT.md](PHASE5_POST_FREEZE_HARDENING_REPORT.md) for
the full report. Summary: OR-1..OR-15 contract coverage matrix built (15/15 DIRECT,
1 real gap found and closed — OR-12 had schema support but no producer,
`derive_ground_truth_transitions()` added additively); non-interference expanded from
1/7 to 7/7 attacks verified; seven-attack end-to-end coverage matrix added; ordering
validation strengthened (+2 invariants); attribution readiness audited across 5 chains
(all AVAILABLE where real evidence exists, correctly MISSING otherwise); task-level
trace projection added (`assemble_task_trace()`); A-MEM gate re-verified unavailable
(not faked); REFERENCES/finish_reason/taint-multi-path/whole-ledger-scan each assessed
and deliberately left as-is with documented reasoning. No frozen Phase 3/4/5 semantics
modified. Phase 5 suite: 188 passed, 2 skipped (by design). Frozen Phase 3/4 regression (run fresh
after every remediation): 1845 passed, 17 skipped (pre-existing), 0 failures.
**Nothing found BLOCKING for Phase 6.**

## Open item carried past freeze — real-vendor (A-MEM / real Mem0) retrieval-identity compatibility

Originally added, by explicit user instruction during the Stage 5.5 review (2026-09-12),
as a "pre-5.8 gate" — at the time, a condition to check before Stage 5.8 could assume
retrieval instrumentation was valid for a real-vendor run. **Phase 5 is now complete and
frozen (all 10 stages, including this one, passed with this item explicitly disclosed as
open at every stage) — this is no longer a gate blocking any further Phase 5 progression,
since there is no further Phase 5 stage.** It remains, unchanged, a genuine open
limitation: `PARTIALLY CLOSED` per the Post-Phase-5 hardening pass's classification
(re-verified unavailable, not faked; compatibility tests are written and ready to run the
moment a real-vendor environment is reachable). Do not fabricate validation for it. Do
not revisit or attempt to close it as part of this or any other Phase 5 maintenance pass
— it is explicitly named in the "do not reopen" list for exactly this reason.

**Gate**: `wiring/retrieval_instrumentation.py`'s design decision — that a Phase-4-attack
-supplied `memory_id` returned by `foundation.retrieve()` is already canonical, no vendor
-id resolution needed — was verified ONLY against `MockMem0Adapter`'s observed behavior
(confirmed by reading its source: a caller-supplied `memory_id` is never reassigned).
This has NOT been verified against `RealMem0Adapter` or any A-MEM adapter, which may
assign their own internal ids independent of the caller-supplied one — exactly the
scenario `canonical_wiring.py`'s own Condition B (`METADATA_LOOKUP` resolution via
`resolve_source_identities()`) exists to handle.

**Update (Stage 5.7, empirically confirmed, not just cited from a docstring)**: attempted
this directly — `RealMem0Adapter()`/`RealAMemAdapter()` both construct and import fine in
this environment (the class definitions have no import-time SDK dependency), but
`.initialize({})` on both reports `FOUNDATION_UNAVAILABLE` — the real `mem0ai`/`amem` SDKs
are confirmed NOT reachable from inside `.initialize()` in this main repo environment, in
this session. Per `canonical_write.py`'s own disclosure, the real SDKs require the
isolated `C:\h4venv` interpreter, which this session cannot reach.

**Update (Stage 5.7 review fix, item 4)**: [phase5/tests/test_real_vendor_compatibility_gate.py](../tests/test_real_vendor_compatibility_gate.py)
now has 4 tests total: 2 confirming `FOUNDATION_UNAVAILABLE` (passing), and 2 FULLY
WRITTEN (not stubs) compatibility tests that self-skip in this environment —
`test_real_mem0_retrieval_identity_chain_when_available` (verifies the complete
caller memory_id → vendor admission → vendor-returned ID → canonical identity resolution
→ retrieval candidate ID → Phase 5 retrieval event chain, and asserts — as a real,
honest check either way — whether Stage 5.5's DIRECT_ASSIGNMENT design decision actually
holds for a real Mem0 backend) and
`test_real_mem0_identity_continuity_across_update_when_available` (identity continuity
across a real `update_memory()` call). Both currently report **NOT VALIDATED —
FOUNDATION_UNAVAILABLE** (skipped, not passed, not marked as passing evidence) and are
ready to run immediately in a future `h4venv`-enabled session with no further design work.

**Historical requirement (satisfied by disclosure, not by closing the gap)**: Stage 5.8's
own documentation states plainly that its trace assembly was verified against
mock-foundation runs only, not real-vendor ones — do not fake or assume vendor-id
resolution. If a future session has access to the `C:\h4venv` interpreter, the two
fully-written compatibility tests below are ready to run immediately, with no further
design work, to actually close this gap.

**Status: OPEN (confirmed unreachable in this environment, not closed).** Tracked here so
it is not silently forgotten. Phase 5 is frozen with this item explicitly open — freezing
the schema does not mean pretending this is resolved (see
`PHASE5_5_9_VALIDATION_NONINTERFERENCE_FREEZE.md`'s "Explicitly NOT frozen" list).

## Stage 5.8A — added by user instruction (2026-09-12), inserted between 5.8 and 5.9

Scope: derive a **Memory Behavior Dataset** from the canonical event/trace/propagation
infrastructure built in 5.2–5.8. This is a derived analytical artifact only — never a
second source of truth. Must include structured records for: memory lifecycle,
retrieval/selection, agent interactions, memory-to-memory relationships,
propagation/lineage, attack/injection events, counterfactual evidence where applicable.
Every record must remain traceable back to its canonical event/trace identifiers (i.e.
cite real `event_id`/`P5EVT-...` ids, never re-derive facts independently). Derivation
must be deterministic and documented. Does not modify frozen Phase 3/4 semantics.
Deliverables: dataset schema, deterministic derivation procedure, generated dataset,
documentation, validation-ready provenance/linkage.

Placement is mandatory: 5.8 → 5.8A → 5.9, because 5.8A consumes 5.8's assembled
trace/propagation graph as its input and 5.9's non-interference/determinism validation
must cover 5.8A's derivation procedure too (determinism of a *derivation* is exactly the
kind of thing 5.9 already checks for).

## Attribution layer (2026-09-13) — new, separate from Phase 5

A new top-level `attribution/` layer (sibling to `phase3/`/`phase4/`/`phase5/`) was
implemented on top of the frozen Phase 5 evidence substrate: attack-origin, lineage,
propagation, exposure, influence, and (after Stage 5.7's `REFERENCES` reopening)
references attribution — 6 distinct question types, never collapsed. Read-only; no
Phase 5 file was modified by attribution's own implementation (Stage 5.7's `REFERENCES`
reopening was a separate, explicitly-authorized Phase 5 change in its own right, not an
attribution change). See
[../attribution/ATTRIBUTION_METHODOLOGY.md](../attribution/ATTRIBUTION_METHODOLOGY.md) and
[../attribution/ATTRIBUTION_IMPLEMENTATION_REPORT.md](../attribution/ATTRIBUTION_IMPLEMENTATION_REPORT.md)
for full detail. Final verdict: **PASS**. This is Phase 5's own attribution-readiness
audit (post-freeze hardening pass, 5 chains) realized as real code. Attribution consumes
this evidence substrate; it does not modify it, and it is not part of Phase 5 semantics.

---

## Official Freeze Statement

**Phase 5 — Instrumentation & Monitoring is officially complete and frozen.** Stages
5.1–5.9, including Stage 5.8A, have been implemented, validated, hardened, and
regression-tested — including one explicitly-authorized reopening (Stage 5.7,
`REFERENCES`) and its matching Stage 5.8/5.8A reconciliation, both re-frozen after
verification. The Phase 5 evidence substrate is the authoritative observational layer
for MAMBench. Future work must not silently modify Phase 5 semantics. Any future change
must be additive, explicitly justified, regression-tested, and documented as a
post-freeze extension, following the exact precedent set by the 2026-09-13
reopening/reconciliation recorded in this file.

**Attribution is a separate analytical consumer of the frozen Phase 5 evidence
substrate and is not part of Phase 5 semantics.**

### Final regression counts (2026-09-13, post-reconciliation)

```
python -m pytest phase3/evaluation/tests phase4/tests -q   → 1845 passed, 17 skipped (pre-existing), 0 failures
python -m pytest phase5/tests -q                            → 203 passed, 2 skipped (by design), 0 failures
python -m pytest attribution/tests -q                        → 31 passed, 0 failures
Combined (one invocation, all four suites)                   → 2079 passed, 19 skipped, 0 failures
```

No frozen Phase 3 or Phase 4 file was modified. No frozen Phase 3 or Phase 4 test count
changed. Phase 5's own suite grew by exactly the tests added during the 2026-09-13
reopening/reconciliation (188 → 194 → 203); attribution's suite is unaffected by this
pass (31, unchanged from before it began).

### Remaining, explicitly classified, non-blocking limitations (not reopened by this pass)

- A-MEM / real-vendor identity resolution — `PARTIALLY CLOSED` / `FOUNDATION_UNAVAILABLE` in this environment. Not fabricated. See "Open item carried past freeze" above.
- `finish_reason` two-state granularity — `INTENTIONAL DESIGN` (frozen `generate_with_retries()` boundary).
- Multiple taint paths (`tainted_memory_evidence()` returns one shortest grounded path) — `OPTIONAL`, not materially needed.
- Whole-ledger scan performance — `OPTIONAL OPTIMIZATION`, no indexing subsystem introduced.
- `LIFECYCLE_STATUS_UNKNOWN_VERSIONING_GAP` — `OPEN BY DESIGN`, belongs to frozen Phase 3 behavior, untouched.

None of these were revisited or reclassified in this pass, per explicit instruction.

```
Phase 5
    |
OFFICIALLY FROZEN
    |
Attribution
    |
PASS
    |
Phase 6
```
