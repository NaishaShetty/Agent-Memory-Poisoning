# Phase 5.9 — Validation, Non-Interference & Instrumentation Freeze

Status: PASS. This is the final stage of Phase 5. Reconciled (2026-09-13, final Phase
5.8–5.9 reconciliation pass) after Stage 5.7's `REFERENCES` reopening and Stage 5.8's
matching reconciliation — see "Reconciliation" section near the end of this document.

## Purpose

Validate the six dimensions the master prompt names, then freeze the Instrumentation
Contract (Stage 5.1) and Canonical Event Schema (Stage 5.2) — meaning every future
addition to them must be additive and reviewed, never a silent rewrite, exactly the
discipline this project already applies to frozen Phase 3/4 code.

## Validation results, by dimension

### Completeness
`validate_completeness()` ([wiring/validation.py](wiring/validation.py)) reuses Stage
5.4's `check_memory_creation_completeness()`/`check_attack_injection_completeness()`
verbatim across every memory/injection an assembled trace names. Clean on a real,
correctly-instrumented pipeline (tested). These checks were already proven, across
Stages 5.4–5.8, to correctly detect real orphaned-event scenarios (an
`UnknownRunError` raised mid-sequence leaving a durable, membership-less event) — Stage
5.9 does not re-derive that proof, it composes the existing, already-validated checks
into one entry point.

### Consistency / Ordering
`validate_ordering_and_linkage()` checks that every cross-reference a trace's own events
make (an `agent_action`'s `decision_id`, a `context_assembled`'s `context_memory_ids`)
resolves within the same trace, and that timestamps along the funnel
(`created` ≤ `retrieved` ≤ `selected`) are never inverted. Proven to actually catch a
violation, not just pass vacuously: a deliberately dangling `decision_id` reference is
correctly flagged (test: `test_validate_ordering_detects_a_dangling_action_reference`).

### Provenance integrity
`validate_provenance_isolation()` checks that no `context_assembled` event's
`rendered_messages` contain this run's own `injection_id` verbatim. **A real finding
during this stage's own development**: an earlier version of this check also tested
`attack_id`/`artifact_id`, and immediately produced a false positive against a real
pipeline — FARMA's own `SEED_CAMPING` fixture uses `artifact_id="farma_seed_camping"`,
which (under the `DIRECT_ASSIGNMENT` scheme Stage 5.5 documents) **is** the canonical
`memory_id`, and `memory_id` is legitimately agent-visible by frozen Phase 3 design
(`render_messages()`'s own `"[{memory_id}] {content}"` citation format). The check was
corrected to test only `injection_id` (a purely internal, content-derived hash with zero
legitimate reason to appear in real content) — documented in the module as a genuine,
disclosed limitation of naive text-based leak detection, not silently patched over. Both
the corrected check's clean result on the real pipeline AND its continued ability to
detect a genuine injection_id leak are tested.

### Determinism
Proven repeatedly across every prior stage (event-id minting, `assemble_trace()`,
`build_propagation_graph()`, `derive_memory_behavior_dataset()` — all tested for
identical output across repeated calls **and** across a full ledger reload from disk).
Stage 5.9 adds no new determinism claim; it relies on this already-established property.

### Non-interference (the master prompt's own comparison table)
`test_non_interference_full_pipeline_baseline_vs_instrumented()` — the definitive test:
the **identical real computation** (FARMA injection, hybrid retrieval/selection,
generation) run twice: once via raw Phase 3/4 primitives with zero Phase 5 involvement,
once entirely through Phase 5's wiring. Every observable the master prompt names is
diffed and found identical:

| Observable | Result |
|---|---|
| Attack state (admission_status) | Identical |
| Memory contents | Identical |
| Retrieved memories | Identical |
| Ranking (blended scores) | Identical |
| Selected top-K | Identical |
| Rendered agent-visible prompt | Identical |
| Generated output | Identical |

This is the closest thing to a formal proof this framework's own testing conventions
support: Phase 5's wiring functions call the real, frozen primitives (`select_by_hybrid_score()`,
`generate_with_retries()`, `FARMAInjector.inject()`) exactly once each, exactly as the
baseline does, and add only side-channel recording around them — never altering an
argument, a return value, or a call count.

## Freeze declaration

As of this stage, the following are **FROZEN**. Frozen means: future changes must be
additive (new optional fields with safe defaults, new event types added through the same
review discipline used throughout Phase 5, new derivation functions) — never a silent
modification of existing, already-validated field semantics or validation rules. This is
the same discipline Phase 3/4 already hold themselves to, now extended to Phase 5's own
schema.

**Frozen: the Instrumentation Contract** (`PHASE5_5_1_INSTRUMENTATION_CONTRACT.md`) —
OR-1 through OR-15, each still cited by name in every later stage's own documentation.

**Frozen: the Canonical Event Schema** (`PHASE5_5_2_CANONICAL_EVENT_SCHEMA.md`,
[schema/event.py](schema/event.py)) —

- The 9 reused, unmodified `CanonicalEvent` types (`created`, `retrieved`, `selected`,
  `used`, `derived`, `superseded`, `retired`, `rejected`, `relationship_detected`,
  `counterfactually_influential`).
- The 6 `Phase5Event` types and their full, final field sets (as extended across Stages
  5.5–5.7's review fixes): `retrieval_candidate_scored` (including `canonical_status`),
  `context_assembled` (including `rendered_messages`/`rendered_context_fingerprint`),
  `agent_decision`, `agent_action`, `attack_injection`, `attack_ground_truth_transition`.
- The full 9-state ground-truth vocabulary (`GROUND_TRUTH_STATES`).
- The identifier hierarchy (`experiment_id`/`run_id`/`episode_id`/`task_id`/`memory_id`/
  `event_id`/`injection_id`/`decision_id`/`action_id`) and every ledger built to serve it
  (`ExperimentRunLedger`, `EventRunMembershipLedger`, `Phase5EventLedger`).
- The closed relationship vocabulary and evidence-kind discipline in
  [wiring/lineage.py](wiring/lineage.py) (`DERIVED_FROM`, `PRODUCED`, `SUPERSEDES`,
  `RETRIEVED_WITH`, `SELECTED_WITH`, `USED_BY`, `INFLUENCED`, `PROPAGATED_TO`,
  `REFERENCES`; `OBSERVED_EVENT`, `EXPOSURE_ONLY`, `COUNTERFACTUAL_EVIDENCE`,
  `LINEAGE_REACHABILITY`).

**Explicitly NOT frozen / carried forward as open, disclosed limitations** (freezing the
schema does not mean pretending these are resolved):

- The A-MEM/real-vendor retrieval-identity compatibility gate (`PHASE5_CHECKLIST.md`) —
  confirmed `FOUNDATION_UNAVAILABLE` in this environment; genuinely unverified against a
  real backend. Still open; this freeze does not close it, it just no longer blocks any
  further Phase 5 stage progression (there is no further stage — Phase 5 is complete).
- Attribution is intentionally out of scope for all of Phase 5 (confirmed by explicit
  instruction during Stage 5.8) — Phase 5 preserves the evidence a later attribution
  mechanism would need; it makes no attribution claim itself. **Update (2026-09-13):**
  Attribution has since been implemented as a separate, top-level `attribution/` layer,
  consuming this evidence substrate read-only; it remains outside Phase 5 semantics.
- `finish_reason`'s two-value granularity (Stage 5.6), `tainted_memory_evidence()`'s
  single-shortest-path citation (Stage 5.7), and `build_propagation_graph()`'s
  whole-ledger-scan cost (Stage 5.8) — all previously disclosed, none silently resolved
  by this freeze.

**Historical note (chronology preserved, not rewritten)**: this section originally also
listed "`REFERENCES` (named in the relationship vocabulary) has no derivation function —
no citation/reference-extraction mechanism exists in Phase 5" as an open, disclosed
limitation at the time Stage 5.9 first froze. That has since been resolved: Stage 5.7 was
reopened on 2026-09-13 (explicit authorization) and gained `derive_references_edges()` —
a structural, deterministic content-citation signal, never the behavioral-reference
inference this project has always rejected — and Stage 5.8 was reconciled the same day to
compose it into `build_propagation_graph()`. See `PHASE5_5_7_PROVENANCE_LINEAGE_INSTRUMENTATION.md`'s
"Reopening" section and `PHASE5_5_8_TRACE_ASSEMBLY_PROPAGATION_GRAPH.md`'s
"Reconciliation" section for the full record. This entry is removed from the
"not frozen" list above (not silently deleted — recorded here as resolved) because
`REFERENCES` is now a real, frozen relationship type like every other Stage 5.7
relationship.

## Evidence

- [phase5/wiring/validation.py](wiring/validation.py)
- [phase5/tests/test_phase5_9_validation.py](../tests/test_phase5_9_validation.py) — 6
  tests: clean-pipeline validation, a proven-to-detect provenance leak, a proven
  false-positive regression test (the `injection_id`-only fix), a proven-to-detect
  dangling-reference ordering violation, completeness agreement with Stage 5.4's own
  checks, and the definitive baseline-vs-instrumented non-interference comparison.
- Full Phase 5 suite: `python -m pytest phase5/tests/ -q` → 160 passed, 2 skipped (by
  design — the Stage 5.7 future-vendor tests).
- Frozen Phase 3/4 regression: recorded below once complete.

## Final Phase 5 completion statement

MAMBench can now execute a complete controlled agent-memory experiment (a real Phase 4
attack injection, through real Phase 3 memory/retrieval/generation mechanics) and
reconstruct, from instrumentation alone — never from re-running the experiment — the
full lifecycle and lineage of the memories involved, the retrieval/selection funnel with
per-candidate scores, the agent's decision and action, the provenance relationships
between memories, and the propagation graph connecting an attack's origin to its
descendants, all addressed by stable experiment/run/episode/event identifiers, without
materially altering the baseline system's behavior. This satisfies the master prompt's
own Section 20 final pass criterion.

---

## Reconciliation (2026-09-13) — validation re-verified against the final 5.7/5.8/5.8A state

Re-checked every dimension this stage validates against the repository state AFTER the
`REFERENCES` reopening (Stage 5.7) and reconciliation (Stage 5.8/5.8A), not assumed
unaffected:

- **Completeness (OR-1..15)**: `validate_completeness()` reads only `ExperimentTrace`
  (memory creation/injection completeness) — it never reads `PropagationGraph`, so
  `REFERENCES` cannot affect it. All 15 requirements remain DIRECT per the Post-Phase-5
  hardening pass's own coverage matrix; OR-15 ("derivable propagation graph") is, if
  anything, MORE completely satisfied now that the graph composes 9/9 relationship types
  instead of 8/9. **15/15 DIRECT, confirmed unchanged.**
- **Ordering**: `validate_ordering_and_linkage()` reads only `ExperimentTrace` fields
  (injections, memory events, decisions, actions) — no `MemoryInteractionEdge` of any
  type is inspected. Unaffected, confirmed by re-running `test_phase5_9_validation.py`
  unmodified after the reconciliation (still passing).
- **Run/episode consistency**: `EventRunMembershipLedger` scoping is exercised
  identically by `REFERENCES` edges as by every other edge type (see
  `_edge_belongs_to_run()` — no special-casing was added for `REFERENCES`, and the new
  Stage 5.8 tests include a dedicated run-isolation check for it).
- **Provenance isolation**: `validate_provenance_isolation()` reads only
  `context_assembled.rendered_messages` vs. `injection_id` — unrelated to
  `MemoryInteractionEdge`s of any kind. Unaffected.
- **Non-interference**: `derive_references_edges()` is read-only over
  `CanonicalMemoryLedger`/`CanonicalEventLedger` and mutates neither — the definitive
  baseline-vs-instrumented comparison test's own observable table is unaffected (it
  never included a graph edge as one of its compared observables in the first place).
- **Determinism / fresh reload**: both directly re-verified for `REFERENCES` specifically
  by two of Stage 5.8's new tests (`test_build_propagation_graph_references_deterministic_across_repeated_calls`,
  `test_build_propagation_graph_references_survive_fresh_ledger_reload`), not merely
  assumed to inherit the property.
- **Attribution readiness**: Attribution consumes `derive_references_edges()` directly
  (`attribution/wiring/references.py::attribute_references()`), the same "call verbatim,
  never reimplement" pattern every other attribution function already uses. Attribution
  remains a read-only consumer of this evidence substrate, not a modification of it.
- **`REFERENCES` survives 5.7 → 5.8 → 5.8A**: verified end-to-end by a dedicated chain of
  tests — Stage 5.7 (`test_lineage.py`, 6 tests, the raw `derive_references_edges()`
  behavior), Stage 5.8 (`test_trace_assembly.py`, 8 tests, composition into
  `build_propagation_graph()` with run-scoping and determinism), Stage 5.8A
  (`test_memory_behavior_dataset.py`, 1 test, flow-through into the existing
  `memory_relationship` dataset category) — no semantics change at any hop; the same
  `MemoryInteractionEdge` object, with the same `evidence_kind=OBSERVED_EVENT` and the
  same real citation, is what each later stage consumes.

**Regression after reconciliation**: `python -m pytest phase5/tests/ -q` → **203 passed,
2 skipped** (by design). Frozen Phase 3/4 regression re-run fresh — see
`PHASE5_CHECKLIST.md` for the exact final counts.

**STAGE 5.9 STATUS (after reconciliation): PASS.**

---

**STAGE 5.9 STATUS: PASS.**
**PHASE 5 (Instrumentation & Monitoring) STATUS: COMPLETE — OFFICIALLY FROZEN.** See
`PHASE5_CHECKLIST.md`'s "Official Freeze Statement" for the canonical freeze declaration
and final regression counts.
