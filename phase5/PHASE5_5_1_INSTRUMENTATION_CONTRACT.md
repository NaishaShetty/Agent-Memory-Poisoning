# Phase 5.1 — Observability Requirements & Instrumentation Contract

Status: FROZEN (Stage 5.9 validation sign-off complete — see
`PHASE5_5_9_VALIDATION_NONINTERFERENCE_FREEZE.md`; §7 below).
Depends on: `PHASE5_REPOSITORY_OBSERVABILITY_AUDIT.md` (all claims below are grounded in
that audit's evidence, not in the master prompt's illustrative sketches).

This contract is the thing every later Phase 5 event/field decision must trace back to.
Per the master prompt's PASS condition for this stage: **every instrumentation event
introduced in Stages 5.2–5.8 must cite a requirement ID from §2 below.** A field or event
type that cannot be traced to a requirement here does not get added "because it seems
useful" — that is exactly the schema-sprawl this contract exists to prevent.

---

## 1. Where each requirement comes from

Requirements are derived from six concrete sources, each cited by the audit:

- **R3-LIFE** — Phase 3's actual memory lifecycle, as implemented (not as prose):
  `CanonicalMemoryRecord.lifecycle_state ∈ {CREATED, ACTIVE, RETIRED}`,
  `CanonicalEvent.event_type ∈ {created, retrieved, selected, used, derived, superseded,
  retired, rejected, relationship_detected, counterfactually_influential}`
  (`canonical.py`, `canonical_event.py`).
- **R3-RET** — Phase 3's actual retrieval/selection pipeline:
  `hybrid_selection.select_by_hybrid_score()` → `HybridScoredCandidate` (cosine,
  token-overlap, entity-overlap, blended score) over a 20-candidate pool, top-K=8
  (`hybrid_selection.py`).
- **R3-AGT** — Phase 3's actual agent runtime trace:
  `evaluate_and_trace()`'s documented, honestly-partial output (retrieved/selected/
  exposed observable; used/contributed marked `NOT_OBSERVABLE`) (`agent_runtime/
  trace.py`).
- **R4-ATK** — Phase 4's attack contract as actually implemented: per-attack
  `*InjectionResult` dataclasses, `attacker_originated`/`attack_id` metadata written via
  `add_memory()`, and the shared `AttackAdapter`/`campaign_runner`/`dormancy_report`/
  `controlled_campaign`/`counterfactual_joint_mask` modules (`phase4/shared/*.py`,
  `phase4/attacks/farma/injector.py`).
- **R4-GT** — Phase 4's 9-state ground-truth vocabulary as currently only partially
  implemented (`dormancy_report.py`'s 3-state subset) and otherwise hand-classified
  (`PHASE4_4_9_ATTACK_GROUND_TRUTH.md`).
- **R-FUT** — Forward-looking needs for later phases (detection, propagation analysis,
  attribution) that the audit found no existing code for, but that the ledger/graph
  infrastructure (`ProvenanceGraph`, `taint_propagation.py`) was already built to
  eventually serve.

A requirement that doesn't map to at least one of these six sources is out of scope for
Phase 5.1.

---

## 2. Requirement catalog

Each requirement states: WHAT is observed, WHEN, WHO/WHAT generates it, WHAT identifiers
connect it, WHAT is agent-visible vs evaluator-only, WHAT is immutable. "Immutable" means
the field is fixed at write time and never edited in place — a change produces a new
record linked to the old one (matches `CanonicalMemoryRecord`'s existing supersession
discipline), not a mutation.

### Memory lifecycle (source: R3-LIFE)

| ID | WHAT | WHEN | WHO generates | Identifiers | Visibility | Immutable |
|---|---|---|---|---|---|---|
| OR-1 | A memory is created (foundation-origin or derived) | At `add_memory()` / derivation time | The wiring layer that calls `write_canonical_memory()` | `memory_id`, `creation_event`, `parent_ids` | Agent-visible: memory content only. Evaluator-only: `source`, `parent_ids`, attack-origin metadata | Yes — a create record is never rewritten |
| OR-2 | A memory transitions lifecycle state (ACTIVE→RETIRED, superseded) | At the moment `memory_versioning.supersede_memory()` (or equivalent) runs | Ledger wiring | `memory_id`, `superseded_by`, triggering `event_id` | Evaluator-only | Yes — new event, old event untouched |
| OR-3 | A memory is retrieved as a raw candidate (pre-selection) | Every retrieval call, for every candidate returned by the embedding/candidate-pool step, not just selected ones | Retrieval wiring at the `select_by_hybrid_score()` call boundary | `memory_id`, `task_id`/`query_id`, `config_fingerprint` | Evaluator-only (candidate pool membership is not shown to the agent) | Yes |
| OR-4 | A memory is selected into the agent-visible top-K, or rejected with a reason | Immediately after `select_by_hybrid_score()` returns | Retrieval wiring | `memory_id`, `task_id`, rejection reason (reuse `CanonicalEvent`'s closed enum: `below_rerank_threshold`, `capacity_cut`, `deduplicated_against_selected_equivalent`, `retired_lifecycle_state`) | Selection outcome (selected/not) is evaluator-only; the selected memory's *content* is what becomes agent-visible | Yes |
| OR-5 | A memory is used/derived-from to create a new memory | At derivation time | Whatever component performs the derivation (e.g. agent writing a new memory citing an old one) | `source_memory_ids`, `target_memory_id` | Evaluator-only | Yes |

### Retrieval & selection funnel detail (source: R3-RET)

| ID | WHAT | WHEN | WHO | Identifiers | Visibility | Immutable |
|---|---|---|---|---|---|---|
| OR-6 | Per-candidate score breakdown (`cosine_score`, `token_overlap_score`, `entity_overlap_score`, `blended_score`, `candidate_rank`) for **every** member of the candidate pool, selected or not | At scoring time, before the pool is reduced to bare ids | Retrieval wiring, reading `HybridSelectionResult.selected`/`.rejected` before they are discarded (closes the gap the audit found in `campaign_runner.retrieve_select_generate()`) | `memory_id`, `task_id`/`query_id`, `config_fingerprint` | Evaluator-only | Yes |
| OR-7 | The final agent-visible context assembly (which memory contents actually entered the prompt, in what order) | At context-render time | Agent runtime / campaign_runner's render step | `memory_id` list, `task_id` | This *is* what's agent-visible — recorded so evaluators can diff "selected" vs "actually rendered" | Yes |

### Agent decision & action (source: R3-AGT)

| ID | WHAT | WHEN | WHO | Identifiers | Visibility | Immutable |
|---|---|---|---|---|---|---|
| OR-8 | A decision: task/input, context memory ids, generated output, finish reason, model+config identity | At generation completion | Agent runtime (extending `evaluate_and_trace()`'s existing, honest shape) | `decision_id`, `task_id`, `memory_id` list (exposed), `config_fingerprint` | Output is agent-visible by definition (it's the agent's own answer); the trace record itself is evaluator-only | Yes |
| OR-9 | An action and its environment result, where the benchmark task involves an action beyond text generation | At action execution | Agent runtime / task harness | `action_id`, `decision_id`, result | Evaluator-only | Yes |
| OR-10 | Explicit non-claim: what the runtime cannot observe (`used_memories`/`contributed_memories` beyond citation heuristics) must be recorded as `NOT_OBSERVABLE`, never silently omitted or guessed | Same time as OR-8 | Agent runtime | same as OR-8 | Evaluator-only | Yes |

### Attack lifecycle (source: R4-ATK, R4-GT)

| ID | WHAT | WHEN | WHO | Identifiers | Visibility | Immutable |
|---|---|---|---|---|---|---|
| OR-11 | An injection attempt: attacker-controlled artifact enters the system, with attack_id, artifact identity (whatever field the specific attack already uses — `poison_id`/`step_id`/`artifact_id`/`scenario_id`), and admission outcome | At `*Injector.inject()` time, for all 7 attacks uniformly | The shared wiring layer wrapping each attack's existing injector (not a rewrite of the injector) | `injection_id` (new — the audit found none exists), `attack_id`, `memory_id` (if admitted) | Evaluator-only | Yes |
| OR-12 | A ground-truth state transition along the 9-state vocabulary, computed from other recorded events rather than hand-classified | Whenever a transition is derivable (e.g. OR-4 selecting a poisoned memory → `POISON_SELECTED_TOP_K`) | A derivation function over the event ledger (extends `dormancy_report.describe_dormancy()`'s pattern to the remaining 6 states, where mechanically derivable) | `attack_id`, `memory_id`, state, `derived_from_event_id` | Evaluator-only | Yes — a computed classification, versionable if the derivation logic changes |
| OR-13 | A counterfactual/interventional run result (baseline vs masked answer, dependence verdict) | When `run_counterfactual_mask`/`run_counterfactual_mask_joint` executes | `phase4/shared` counterfactual modules | `counterfactual_run_id`, `memory_id`(s) masked, `decision_id` compared | Evaluator-only | Yes |

### Forward-looking, infrastructure-only (source: R-FUT)

| ID | WHAT | WHEN | WHO | Identifiers | Visibility | Immutable |
|---|---|---|---|---|---|---|
| OR-14 | Every event above must be attachable to a stable `experiment_id`/`run_id`/`episode_id` hierarchy that Phase 4 currently lacks entirely | At run start | A new, minimal run-registration step (analogous to `RunConfigLedger`, not a new mechanism) | `experiment_id`, `run_id`, `episode_id` | Evaluator-only | Yes, per run |
| OR-15 | The propagation/lineage graph must be **derivable, not hand-built** — i.e. every OR-1..OR-13 event must carry enough identifiers that `ProvenanceGraph`-style projection works without any new manual bookkeeping | Structural requirement, not a single event | N/A — a property of OR-1..OR-14, checked at Stage 5.8/5.9 | — | — | — |

---

## 3. What is explicitly agent-visible vs evaluator-only

This distinction matters because leaking evaluator-only provenance into agent-visible
content would itself corrupt the experiment (an agent that can see "this memory is
attacker-originated" is no longer measuring the attack realistically).

- **Agent-visible**: only memory *content* that is selected into context (OR-7), and the
  agent's own generated output (part of OR-8). Nothing else.
- **Evaluator-only**: every identifier, score, rank, rejection reason, attack label,
  ground-truth state, and counterfactual result (OR-1 through OR-6, OR-8's non-output
  fields, OR-9 through OR-15).
- **Enforcement mechanism**: reuse `contracts/boundary.py`'s existing
  `FORBIDDEN_KEYS`/`enforce_foundation_call_boundary` (already proven to fire in a real
  FARMA trial per the audit) rather than inventing a second content/metadata boundary
  checker.

## 4. What is immutable

Per §2's "Immutable" column: every event is append-only. A correction, state change, or
new classification is a **new event referencing the old one**, never an in-place edit.
This is not a new design choice — it is simply extending `CanonicalMemoryRecord`'s
existing supersession discipline and `CanonicalEventLedger`'s existing append-only JSONL
model (both already real and tested) to the new event types in §2, rather than inventing
a different mutability model for attack/decision events.

## 5. Explicit non-goals for this contract

- No requirement here authorizes filtering, blocking, or scoring memories at
  runtime — that is defense work, out of scope per the master prompt §18.
- No requirement here treats temporal ordering as proof of influence. OR-13
  (counterfactual result) is the only requirement permitted to carry an influence claim,
  and it must retain the "interventional dependence, not formal causal proof" framing
  the audit found already present in `taint_propagation.py`'s own docstring.
- No requirement here is attack-specific. OR-11/OR-12/OR-13 are worded to wrap the
  *existing* per-attack artifact shapes uniformly, not to require the 7 attacks to change
  their own dataclasses.

## 6. Coverage self-check

Cross-checking against the master prompt's own final-deliverable question list (§19):
Entry→OR-11, Admission→OR-11, Memory creation→OR-1, Provenance→OR-1/OR-5,
Retrieval→OR-3/OR-6, Ranking→OR-6, Selection→OR-4, Exposure→OR-7, Agent use→OR-8/OR-9,
Memory evolution→OR-2/OR-5, Propagation→OR-15, Influence→OR-13, Attribution→OR-11/OR-12,
Lineage→OR-15, Reproducibility→OR-14. Every question in the master prompt's canonical
deliverable list maps to at least one requirement ID. No requirement was added that
doesn't trace to §1's six sources (checked against §2 row-by-row).

Cross-checking against the audit's §11 gap list: gap 1 (no Phase4↔ledger wiring)→OR-1
through OR-13 collectively; gap 2 (no structured logging)→ the whole contract; gap 3
(discarded scores)→OR-6; gap 4 (no injection_id)→OR-11; gap 5 (no run identity)→OR-14;
gap 6 (9-state vocab not code)→OR-12; gap 8 (versioning-gap bug)→explicitly *not*
silently worked around — OR-12/OR-15's derivations must surface `UNKNOWN_VERSIONING_GAP`
honestly rather than hide it, matching OR-10's "record what can't be observed" discipline.
Gaps 7 (no CI harness) and 9 (no latency instrumentation) are noted as out of scope for
5.1's event contract — they are tooling/observability-breadth concerns for later stages
(5.9 non-interference measurement will need basic latency capture, tracked there, not
invented as a new top-level requirement here).

## 7. Freeze condition

This contract is frozen once Stage 5.9 confirms (a) every event type introduced in
Stages 5.2–5.8 cites an OR-id from §2, and (b) no OR-id in §2 went unimplemented without
an explicit, documented reason. Until then it is a working frozen baseline for 5.2
onward — changes to it require the same additive-not-silent-rewrite discipline the
master prompt requires of Phase 3/4 (§22).

**STAGE 5.1 STATUS: PASS** — requirements enumerated, each grounded in cited repository
evidence (not assumption), agent-visible/evaluator-only/immutable dimensions defined,
coverage checked against both the master prompt's deliverable list and the audit's own
gap list.
