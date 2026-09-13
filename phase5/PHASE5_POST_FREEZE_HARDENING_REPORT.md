# MAMBench — Post-Phase-5 Gap Closure & Pre-Phase-6 Hardening Report

Phase 5 remains FROZEN. This pass made no change to Phase 5's semantics, Phase 3, or
Phase 4 — every remediation below is additive: new modules, new tests, extended
docstrings. No existing validated behavior was altered.

## 1. Baseline verification (mandatory first action)

Run fresh at the start of this pass, not assumed from a prior background result:

- `python -m pytest phase5/tests/ -q` → **160 passed, 2 skipped** (pre-existing,
  by-design skips — the Stage 5.7 future-vendor compatibility tests).
- `python -m pytest phase3/evaluation/tests phase4/tests -q` → **1845 passed, 17
  skipped (pre-existing), 0 failures.**

No STOP condition triggered. Remediation proceeded.

## 2. Full Phase 5 documentation gap inventory

A systematic grep across all `PHASE5_5_*.md` files for the requested keyword set
(limitation, open, unverified, not implemented, proxy, unresolved,
FOUNDATION_UNAVAILABLE, UNKNOWN_VERSIONING_GAP, NOT_OBSERVABLE, performance, coverage,
etc.) surfaced the following distinct issues, each independently classified below (not
silently accepted just because it was previously documented):

| # | Issue | Origin | Classification |
|---|---|---|---|
| 1 | A-MEM/real-vendor identity resolution unverified | 5.5–5.7 | COMPATIBILITY — environment limitation |
| 2 | Attribution not implemented | 5.8 | INTENTIONAL DESIGN at the time (confirmed by explicit instruction); **since implemented 2026-09-13** as the separate `attribution/` layer, outside Phase 5 — see `PHASE5_CHECKLIST.md`'s "Attribution layer" section |
| 3 | `REFERENCES` relationship has no producer | 5.7 | **CLOSED 2026-09-13** — `derive_references_edges()` added (structural content-citation, not behavioral inference; see §10 amendment) |
| 4 | `finish_reason` two-state granularity | 5.6 | INTENTIONAL DESIGN — frozen `generate_with_retries()` boundary |
| 5 | `tainted_memory_evidence()` returns one path, not all | 5.7 | OPTIONAL — not materially needed yet |
| 6 | Trace/graph/dataset are per-run, not per-task | 5.8/5.8A | CLOSED this pass — `assemble_task_trace()` added |
| 7 | `build_propagation_graph()` scans whole ledger | 5.8 | OPTIONAL OPTIMIZATION — assessed, deferred (Section 9 below) |
| 8 | Non-interference tested for FARMA only | 5.9 | CLOSED this pass — all 7 attacks now verified |
| 9 | 7-attack end-to-end coverage never run together | 5.4–5.9 | CLOSED this pass — coverage matrix added |
| 10 | Ordering validation non-exhaustive | 5.9 | STRENGTHENED this pass — 2 more invariants added |
| 11 | OR-1..OR-15 coverage never tabulated | 5.1/5.9 | CLOSED this pass — matrix below; **1 real gap found and closed** (OR-12) |
| 12 | Provenance-isolation check scope | 5.9 | VALIDATED — already correctly scoped after its own review fix; re-audited this pass |
| 13 | `UNKNOWN_VERSIONING_GAP` (H.3/H.4-D) | Phase 3 / 5.7 | KNOWN LIMITATION — frozen Phase 3 behavior, not touched |
| 14 | Completeness check NOT_APPLICABLE distinction | 5.9 | VALIDATED — already correct by construction; now documented explicitly |
| 15 | Memory Behavior Dataset sample mislabeled as representative | 5.8A | NOT A REAL GAP — already correctly labeled "worked example" |
| 16 | **OR-12 (ground-truth transitions) has schema but no producer** | 5.2–5.9 | **FIX NOW — genuinely new finding, closed this pass** |

## 3. OR-1 through OR-15 contract coverage matrix

| Req | Instrumented | Persisted | Stable ID | Reconstructable | Direct test | Coverage |
|---|---|---|---|---|---|---|
| OR-1 (memory creation) | `record_memory_creation()` | `CanonicalEvent(created)` | memory_id, event_id | Yes (`assemble_trace().memory_created`) | `test_memory_lifecycle_wiring.py`, `test_seven_attack_coverage.py` (7/7) | DIRECT |
| OR-2 (lifecycle transition) | `record_memory_lifecycle_transition()` | `CanonicalEvent(superseded/retired)` | event_id, SupersessionRecord | Yes | `test_memory_lifecycle_wiring.py`, `test_completeness.py`, `test_attribution_readiness.py` (chain B) | DIRECT |
| OR-3 (raw retrieval) | `instrument_retrieval_and_selection()` | `CanonicalEvent(retrieved)` | memory_id/task_id/config_fingerprint | Yes | `test_retrieval_instrumentation.py` | DIRECT |
| OR-4 (selection/rejection) | same | `CanonicalEvent(selected/rejected)` | same | Yes | `test_retrieval_instrumentation.py`, `test_lineage.py` | DIRECT |
| OR-5 (derivation) | `record_memory_derivation()` | `CanonicalEvent(derived)` | source/target memory_id | Yes | `test_memory_lifecycle_wiring.py`, `test_lineage.py` | DIRECT |
| OR-6 (per-candidate score) | `instrument_retrieval_and_selection()` | `Phase5Event(retrieval_candidate_scored)` | memory_id/task_id + `canonical_status` | Yes | `test_retrieval_instrumentation.py` | DIRECT |
| OR-7 (context exposure) | `record_context_assembly()` | `Phase5Event(context_assembled)` incl. `rendered_messages`/fingerprint | task_id, context_memory_ids | Yes | `test_retrieval_instrumentation.py`, `test_phase5_9_validation.py` | DIRECT |
| OR-8 (agent decision) | `instrument_agent_decision()` | `Phase5Event(agent_decision)` | decision_id | Yes | `test_agent_decision_instrumentation.py` | DIRECT |
| OR-9 (agent action) | `record_agent_action()` | `Phase5Event(agent_action)` | action_id, decision_id | Yes | `test_agent_decision_instrumentation.py`, `test_attribution_readiness.py` (chain D) | DIRECT |
| OR-10 (non-observability) | `used_memories_observability` field | same event | — | Yes | `test_agent_decision_instrumentation.py` | DIRECT |
| OR-11 (attack injection) | `record_attack_injection()` | `Phase5Event(attack_injection)` | injection_id | Yes | `test_memory_lifecycle_wiring.py`, `test_seven_attack_coverage.py` (7/7), `test_seven_attack_non_interference.py` (7/7) | DIRECT |
| OR-12 (ground-truth state) | **`derive_ground_truth_transitions()` — NEW this pass** | `Phase5Event(attack_ground_truth_transition)` | derived_from_event_id (required) | Yes | `test_ground_truth.py` (new) | **DIRECT (was INDIRECT/schema-only before this pass)** |
| OR-13 (counterfactual evidence) | `EVENT_COUNTERFACTUALLY_INFLUENTIAL` (frozen, reused) | `CanonicalEvent` | memory_id, task_id, config_fingerprint | Yes | `test_lineage.py`, `test_attribution_readiness.py` (chain E) | DIRECT |
| OR-14 (identifier hierarchy) | `ExperimentRunLedger`/`EventRunMembershipLedger` | both | experiment_id/run_id/episode_id | Yes | `test_run_identity.py` | DIRECT |
| OR-15 (derivable propagation graph) | `wiring/lineage.py` + `build_propagation_graph()` | `MemoryInteractionEdge` (in-memory projection) | established_by_event_ids | Yes | `test_lineage.py`, `test_trace_assembly.py` | DIRECT |

**Result: 15/15 requirements DIRECT. One genuine gap (OR-12) found and closed this
pass** — previously it would have been marked INDIRECT ("vocabulary exists, no producer
exercises it against real evidence").

## 4. A-MEM / real-vendor compatibility

Re-verified empirically in this pass (not assumed from Stage 5.7's prior result):

```
RealMem0Adapter().initialize({})  -> FOUNDATION_UNAVAILABLE
RealAMemAdapter().initialize({})  -> FOUNDATION_UNAVAILABLE
```

Both adapter classes import and construct without error in this environment; the real
`mem0ai`/`amem` SDKs are not reachable from `.initialize()` here, consistent with
`canonical_write.py`'s own disclosure that they require the isolated `C:\h4venv`
interpreter, unreachable from this session.

**No vendor-ID mapping was fabricated. No vendor behavior was simulated.** Two
fully-written (not stub) compatibility tests already exist from the Stage 5.7 review fix
(`test_real_vendor_compatibility_gate.py`) and remain ready to run, unmodified, in a
future `h4venv`-enabled session: they exercise exactly the chain Section 6 names (caller
memory_id → vendor admission → vendor-returned ID → canonical resolution → retrieval
candidate ID → Phase 5 retrieval event) plus an identity-continuity-across-update check.

**Status: NOT VALIDATED — FOUNDATION_UNAVAILABLE.** PARTIALLY CLOSED (the compatibility
layer and its tests exist and are correct; the empirical validation itself is blocked by
environment access, not by missing engineering).

## 5. Attribution readiness audit

Attribution itself was NOT implemented (per explicit instruction). Five chains audited,
each with a new, real-evidence test (`test_attribution_readiness.py`):

| Chain | Result |
|---|---|
| A. attack_id → injection_id → artifact_id → origin memory_id | **AVAILABLE** — all four fields on one persisted `attack_injection` event |
| B. origin memory → derived memory → supersession | **AVAILABLE** — `DERIVED_FROM`/`SUPERSEDES` edges, both event-grounded |
| C. source memory → retrieval → selection → exposure → downstream | **AVAILABLE** for every real hop; the final "downstream memory/behavior" hop is only as available as real evidence makes it (never asserted absent one) |
| D. memory → context → decision → action | **AVAILABLE** — linked by task_id/decision_id, all real events |
| E. genuine `counterfactually_influential` → run/memory/evidence | **AVAILABLE** when real evidence exists; **correctly MISSING** (not fabricated) when it does not — verified both ways |

No influence was inferred from temporal order, retrieval, selection, or exposure in any
of these tests — `derive_influenced_edges()` returns empty until a real counterfactual
event exists, confirmed directly.

## 6. Ordering / linkage validation — strengthened

Two invariants added to `validate_ordering_and_linkage()` beyond the original three
(dangling decision reference, context→memory existence, selected-vs-retrieved/created
ordering):

- An `attack_injection`'s timestamp must not postdate its own memory's `created` event.
- An `agent_action`'s timestamp must not precede its own linked `agent_decision`.

Both proven to actually detect a deliberately-introduced violation
(`test_validate_ordering_detects_injection_postdating_its_own_creation`,
`test_validate_ordering_detects_action_preceding_its_own_decision`), and to remain clean
on a correctly-instrumented real pipeline. No cross-task ordering constraint was added —
different tasks/decisions have no real causal relationship to each other, and the
validator deliberately never compares across `task_id` boundaries.

## 7. Non-interference — expanded to all 7 attacks

**Previously**: only FARMA was compared (raw vs. instrumented).
**Now**: `test_seven_attack_non_interference.py` runs the identical real computation
(that attack's own real injector against a real `MockMem0Adapter`, plus hybrid
retrieval/selection and generation) twice — once via raw Phase 3/4 primitives, once via
Phase 5's wiring — for **all 7 attacks**, diffing attack state, memory contents,
retrieved memories, ranking, selected top-K, rendered prompt, and generated output.

**Result: 7/7 VERIFIED**, all identical. No attack was skipped or assumed; every one was
actually executed and compared. (AgentPoison, DSRM, MemoryGraft each needed a fixture
correction to use the exact same artifact the instrumented path constructs internally —
a real test-authoring bug caught and fixed during this pass, not a defect in the
instrumentation itself.)

## 8. Agent-visible / evaluator-only boundary audit

Full OR-1..OR-15 re-examination against agent-visible/evaluator-only/`NOT_OBSERVABLE`
labeling:

- **Agent-visible**: only rendered memory content (OR-7's `rendered_messages`) and the
  model's own output (part of OR-8). `memory_id` is ALSO legitimately agent-visible —
  confirmed by reading frozen `render_messages()`'s own `"[{memory_id}] {content}"`
  citation format, which predates Phase 5 and applies to every clean run, not just
  attack runs.
- **Evaluator-only**: every other identifier and field (OR-1..OR-6, OR-9..OR-15).
- The provenance-isolation check (`validate_provenance_isolation()`) checks only
  `injection_id` — a real, disclosed, tested decision (Stage 5.9's own review fix):
  `attack_id`/`artifact_id` were tried first and produced a real false positive (FARMA's
  `artifact_id` legitimately equals the agent-visible `memory_id`), documented in the
  module rather than silently narrowed.
- Both required cases are tested: a clean, legitimate real pipeline (passes with zero
  violations, `test_validate_provenance_isolation_does_not_false_positive_on_legitimate_memory_id`)
  and a deliberate leak (`test_validate_provenance_isolation_detects_a_real_leak`,
  detects it).

**No change made** — this audit confirms the existing Stage 5.9 boundary discipline is
correct and complete for what it claims to check; it does not claim to catch every
conceivable leak vector (e.g. a memory's own `content["text"]` embedding an evaluator-only
string some other way), which remains a disclosed limitation of text-based leak detection
in general, not fixable without a much larger, out-of-scope content-scanning system.

## 9. Completeness — full lifecycle audit

`validate_completeness()` was found to ALREADY correctly distinguish NOT_APPLICABLE from
MISSING, by construction — it only asks "is this real event complete" for events that
actually exist in the trace, never asserting retrieval/selection/decision/action are
required for a memory's existence. This was previously implicit; the module docstring
now states it explicitly, and `test_seven_attack_coverage.py` (Section 11) demonstrates
the distinction concretely across all 7 real attacks, including two cases (Sleeper
DISCARD, MemoryGraft-shaped rejection) where every downstream stage is correctly
NOT_APPLICABLE, never FAILED.

## 10. `REFERENCES` relationship — decision (AMENDED 2026-09-13 — see below)

**Original decision (still valid, not reversed)**: no reliable signal exists for
inferring that "the model actually referenced [a memory] in its answer" — that would
require word overlap, semantic similarity, or mention-coincidence judgment this framework
has no calibrated way to make. **This specific inference remains rejected and
unimplemented.**

**Amendment (2026-09-13, Stage 5.7 reopened by explicit user instruction)**: a narrower,
purely structural question was later found and is now implemented —
`derive_references_edges()` (`phase5/wiring/lineage.py`) detects whether one real
memory's own persisted CONTENT literally contains another real memory's exact
`[memory_id]` citation-bracket substring. This is an exact, deterministic substring match
against real, known memory_ids, not a heuristic, and makes no claim about model behavior
— it does not reintroduce the case rejected above. See
`PHASE5_5_7_PROVENANCE_LINEAGE_INSTRUMENTATION.md`'s "Reopening" section for the full
rationale and evidence. The gap-status table (§13 below) is updated accordingly.

## 11. `finish_reason` telemetry — decision

Assessed whether provider-level `finish_reason` (`"stop"`/`"length"`/etc.) could be
exposed additively. Confirmed by reading `generate_with_retries()` again: it is a frozen
Phase 3 function whose retry loop discards `GenerationResult.finish_reason` internally.
Exposing the real value would require either (a) modifying that frozen function's return
signature (prohibited), or (b) calling the provider a second time (changes generation
behavior/cost, prohibited). **No safe additive path exists. Kept as the existing derived
two-state representation (`GENERATED`/`FAILED_ALL_ATTEMPTS`), disclosed as coarser than
the real provider value.**

## 12. Taint-lineage multiple paths — decision

Assessed whether attribution/propagation analysis materially needs every valid lineage
path rather than one shortest, grounded one. No current consumer (the attribution
readiness audit above, or any Phase 5 stage) requires more than reachability plus one
real, citable path. **Kept as shortest-path evidence.** Documented already in Stage 5.7's
own report: "The representation provides one grounded lineage path, not an exhaustive
enumeration of all possible lineage paths." `LINEAGE_REACHABILITY ≠ INFLUENCE` preserved
throughout; `tainted_memories()` itself untouched.

## 13. Task-level projections — implemented

`assemble_task_trace(run_id, task_id, ...)` added to `wiring/trace_assembly.py` — a pure
filter over `assemble_trace()`'s own output (never a second ledger query). Run-level
facts with no `task_id` of their own (memory creation/derivation/supersession/retirement,
attack injections) pass through unfiltered, since narrowing them to one task would drop
facts other tasks in the same run still depend on for reconstruction. Tested
(`test_assemble_task_trace_filters_task_scoped_fields_but_keeps_run_level_facts`) against
a real two-task pipeline, confirming correct filtering and that every event id in the
task trace is a subset of the full trace's own event ids (no new identifiers invented).

## 14. Whole-ledger scan performance — decision

Investigated whether `EventRunMembershipLedger.events_for_run(run_id)` could pre-scope
`build_propagation_graph()`'s calls into Stage 5.7's `derive_*` functions before they scan
the whole ledger. Concluded: doing so safely would require either (a) modifying the
`derive_*` functions' own signatures to accept a pre-filtered event list (a real API
change to already-frozen Stage 5.7 code, risking behavioral drift), or (b) duplicating
each function's own filtering/grouping logic in a pre-pass (violates "do not duplicate
Stage 5.7 derivation logic"). Neither is a simple, safe, additive change at this scale.
**Deferred — the existing post-hoc scoping filter (`_edge_belongs_to_run()`) remains
correct, just not optimized; acceptable at current (test/campaign) scale, per the
hardening prompt's own instruction not to build a complex indexing subsystem for
theoretical scalability.**

## 15. Seven-attack end-to-end coverage matrix

`test_seven_attack_coverage.py` — every attack's real injector run through
injection → admission → lifecycle → retrieval → selection → agent (context/decision/
action) → lineage → trace → dataset, using existing additive runners only (no attack code
modified):

| Attack | Injection | Admission | Lifecycle | Retrieval | Selection | Agent | Lineage | Trace | Dataset |
|---|---|---|---|---|---|---|---|---|---|
| AgentPoison | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| DSRM | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| FARMA | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| MINJA | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| MPBench-PCFI | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| Sleeper (KEEP) | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| Sleeper (DISCARD) | PASS | N/A | N/A | N/A | N/A | N/A | N/A | PASS | PASS |
| MemoryGraft | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |

A rejected/discarded outcome's downstream N/A cells are a legitimate result (the injection
attempt is still fully tracked), never collapsed into a failure.

## 16. Seven-attack non-interference coverage

See Section 7 above — **7/7 VERIFIED**, not claimed without being run.

## 17. Files added / modified this pass

New:
- `phase5/wiring/ground_truth.py` — OR-12 gap closure.
- `phase5/wiring/validation.py` — extended (2 new ordering invariants, documentation of
  the already-correct NOT_APPLICABLE handling).
- `phase5/wiring/trace_assembly.py` — extended (`assemble_task_trace()`).
- `phase5/tests/test_seven_attack_coverage.py` (new)
- `phase5/tests/test_seven_attack_non_interference.py` (new)
- `phase5/tests/test_attribution_readiness.py` (new)
- `phase5/tests/test_ground_truth.py` (new)
- `phase5/tests/test_phase5_9_validation.py` — extended (2 new ordering tests)
- `phase5/tests/test_trace_assembly.py` — extended (1 new task-trace test)
- `phase5/PHASE5_POST_FREEZE_HARDENING_REPORT.md` (this document)

**No frozen Phase 3 file was modified.** **No frozen Phase 4 attack file was modified.**
**No previously-frozen Phase 5 semantics were changed** — `Phase5Event`'s schema,
`CanonicalEvent`'s reuse, the identifier hierarchy, and every existing `derive_*`
function's signature and behavior are unchanged; `ground_truth.py` and the two new
`trace_assembly.py`/`validation.py` additions are pure new/extended surface, verified by
full regression (Section 18) to leave every existing test passing unchanged.

## 18. Post-remediation testing

- `python -m pytest phase5/tests/ -q` → **188 passed, 2 skipped** (by design).
- `python -m pytest phase3/evaluation/tests phase4/tests -q` → **1845 passed, 17
  skipped (pre-existing), 0 failures** — run fresh after every remediation in this
  document (including the OR-12 closure), not reused from Section 1's earlier baseline
  check.

## 19. Final gap-status table

| Gap | Origin | Type | Action taken | Evidence | Final status |
|---|---|---|---|---|---|
| A-MEM identity resolution | 5.5–5.9 | Compatibility | Re-verified unavailable; tests ready | `test_real_vendor_compatibility_gate.py` | PARTIALLY CLOSED |
| Attribution | 5.8/5.9 | Research/design | Readiness audited; **since implemented** as the separate `attribution/` layer (2026-09-13) | `attribution/ATTRIBUTION_IMPLEMENTATION_REPORT.md` | CLOSED (as a new layer, not a Phase 5 change) |
| REFERENCES | 5.7 | Observability | Behavioral inference assessed and rejected (unchanged); structural content-citation signal added 2026-09-13 | This report §10 (amended), `derive_references_edges()` | CLOSED |
| finish_reason | 5.6 | Telemetry | Assessed, no safe additive path | This report §11 | INTENTIONAL DESIGN |
| Multiple taint paths | 5.7 | Analytical | Assessed, not materially needed | This report §12 | OPTIONAL |
| Task-level projections | 5.8A | Usability | Implemented | `assemble_task_trace()` + test | CLOSED |
| Whole-ledger scans | 5.8 | Performance | Assessed, unsafe to optimize now | This report §14 | OPTIONAL |
| 7-attack non-interference | 5.9 | Validation | Implemented, all 7 run | `test_seven_attack_non_interference.py` | CLOSED |
| 7-attack end-to-end coverage | 5.4–5.9 | Validation | Implemented, all 7 run | `test_seven_attack_coverage.py` | CLOSED |
| Ordering completeness | 5.9 | Validation | 2 invariants added | `test_phase5_9_validation.py` | STRENGTHENED |
| OR-1–OR-15 coverage | 5.1/5.9 | Validation | Matrix built; 1 real gap found+closed | §3 above | CLOSED (15/15 DIRECT) |
| Boundary validation | 5.9 | Safety | Re-audited, confirmed correct | §8 above | VALIDATED |
| UNKNOWN_VERSIONING_GAP | 3/5.7 | Known limitation | Not touched (frozen Phase 3) | `taint_propagation.py` docstring | OPEN (by design, not fixable here) |
| **OR-12 no producer** | **5.2–5.9** | **Correctness defect** | **`derive_ground_truth_transitions()` added** | **`test_ground_truth.py`** | **CLOSED** |

## 20. Newly discovered gaps

One: **OR-12 had schema support but no producer** (Section 2, row 16) — found only by
performing the explicit coverage-matrix audit this pass required, not previously
disclosed in any Stage 5.1–5.9 document. Closed additively this pass.

## 21. Final scientific questions

1. **Can MAMBench reconstruct attack origin and memory lineage from persisted evidence
   without rerunning the experiment?** Yes — confirmed directly for all 5 attribution
   chains (Section 5) and all 7 attacks (Section 15), from fresh ledger reloads.
2. **Can it distinguish retrieved / selected / exposed / used / influenced without
   collapsing these concepts?** Yes — `retrieved`/`selected` (CanonicalEvent),
   `canonical_status` (OR-6), `context_assembled` (exposure), `used_memories_
   observability=NOT_OBSERVABLE` (used — honestly never claimed), `INFLUENCED` (only
   from real counterfactual evidence) are five structurally distinct signals, verified
   never to be conflated.
3. **Can it distinguish lineage propagation from counterfactual influence without
   relying on convention alone?** Yes — structurally enforced via the required
   `evidence_kind` field on every `MemoryInteractionEdge` (`LINEAGE_REACHABILITY` vs.
   `COUNTERFACTUAL_EVIDENCE`), not merely a naming convention.
4. **Can the frozen Phase 3/4 baseline still produce identical observable behavior with
   and without Phase 5 instrumentation?** Yes — 7/7 attacks verified identical on every
   named observable (Section 7).
5. **Are all OR-1 through OR-15 requirements either directly validated or explicitly
   classified?** Yes — 15/15 DIRECT (Section 3), including OR-12 closed this pass.
6. **Can future attribution research operate on the frozen Phase 5 evidence without an
   obvious missing instrumentation field?** Yes, for the five chains actually audited
   (Section 5) — no field was found missing for A–D; E is correctly evidence-gated.
7. **Are the remaining limitations genuine research/environment/scaling limitations
   rather than avoidable engineering defects?** Yes for every item in Section 19 except
   the one that was an avoidable defect (OR-12), which was found and closed rather than
   left standing.

## 22. BLOCKING determination for Phase 6

**Nothing found in this pass is BLOCKING.** The one genuine correctness defect (OR-12)
was closed. The remaining open items (A-MEM empirical validation, whole-ledger scan
optimization) are environment/scale limitations with real, working code and tests
already in place, not missing engineering. Phase 6 may begin on the frozen Phase 3
baseline, frozen Phase 4 attacks, and the now-hardened Phase 5 evidence substrate.
