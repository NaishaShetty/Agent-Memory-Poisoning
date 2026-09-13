# MAMBench — Attribution Methodology

STATUS: DRAFT, written before the implementation it governs (per explicit instruction:
"Before creating the final implementation, write a short Attribution Methodology
document"). Finalized once the implementation and its 11 test scenarios (A-K) validate
against it; any change forced by implementation reality is reconciled here explicitly,
not silently.

## 0. What this layer is, and is not

Attribution is a **new, read-only analytical layer**, consuming frozen Phase 5 evidence.
It is:
- NOT a Phase 5 modification (no Phase 5 file under `phase5/` is edited by this work).
- NOT a defense mechanism (it does not block, filter, or mitigate anything).
- NOT a detection mechanism (it does not decide whether an attack succeeded).
- NOT an attack implementation.
- NOT a second source of truth: every `AttributionResult` this layer produces must be
  reconstructible, byte-for-byte, from the same persisted Phase 3/4/5 ledgers, at any
  later time, by re-running the same deterministic function. Nothing here is a store
  attribution writes only its own results to (see §8) — it is never a store attribution
  *reads from* as if it were independent evidence.

Central standard (verbatim, load-bearing for every design choice below): **"MAMBench
must never claim to know more than its evidence establishes."**

## 1. Attribution target

The **target** of an attribution question is always one of:

| target_type | meaning |
|---|---|
| `MEMORY` | a canonical memory (identified by `memory_id`) — used for ORIGIN, LINEAGE, PROPAGATION, and (as the object being asked "was this memory used/influential") EXPOSURE and INFLUENCE |
| `DECISION` | one `agent_decision` Phase5Event (`decision_id`) — used for EXPOSURE ("what memories were exposed to this decision") |
| `ACTION` | one `agent_action` Phase5Event (`action_id`) — `attribute_action()` (`attribution/wiring/action.py`) resolves `action_id -> decision_id` via the real ledger and delegates the actual attribution question to `attribute_exposure()`, then re-wraps the result with `target_type=ACTION`. This is a thin resolution layer, not a duplicate mechanism: no new evidence exists at the ACTION level beyond what its DECISION already carries. |

A single `memory_id` (or `decision_id`) can be, and often is, the target of more than one
`AttributionResult` — one per `attribution_type` (see §2) — never collapsed into one
combined answer, per the explicit instruction against conflating the five questions.

## 2. Attribution types — five distinct questions, never collapsed

| attribution_type | question it answers | reuses (verbatim, never reimplemented) |
|---|---|---|
| `ORIGIN` | Which attack (if any) produced this memory directly? | `phase5.wiring.lineage.derive_produced_edges()` |
| `LINEAGE` | What is this memory's real ancestor chain, hop by hop? | `phase5.wiring.lineage.derive_derived_from_edges()`, `tainted_memory_evidence()` |

`attribute_lineage(memory_id, ..., full_chain=False)`: default is one-hop (immediate real
parentage). `full_chain=True` walks the entire real ancestor graph (cycle-safe BFS over
repeated `derive_derived_from_edges()` results) and answers the complete-chain question:
`UNIQUE` with the full `lineage_path` when the ancestor graph is a single linear chain;
`MULTIPLE_POSSIBLE_SOURCES` naming EVERY distinct ancestor found (not just the deepest
roots, which could under-report a branch that reconverges deeper — a diamond-shaped
derivation history) when any real ancestor has more than one parent. This remains a
different question from PROPAGATION, which is scoped to a caller-given set of confirmed
attack origins rather than the memory's complete, attack-agnostic ancestry.
| `PROPAGATION` | Which attack-tainted memories (if any) is this memory reachable from, and by what grounded path? | `phase5.wiring.lineage.tainted_memory_evidence()` / `derive_propagated_to_edges()` |
| `EXPOSURE` | Was this memory exposed to a given decision (retrieved/selected/exposed), as distinct from *used*? | `phase5.wiring.lineage.derive_exposed_to_decision_edges()`, `query_co_retrieved_memory_ids()`/`query_co_selected_memory_ids()` |
| `INFLUENCE` | Is there a real counterfactual finding that this memory influenced a task outcome? | `phase5.wiring.lineage.derive_influenced_edges()` (the ONLY source — a real `EVENT_COUNTERFACTUALLY_INFLUENTIAL` `CanonicalEvent`) |
| `REFERENCES` | Does this memory's own content literally cite one or more other real memories? | `phase5.wiring.lineage.derive_references_edges()` (added 2026-09-13 via an explicitly-authorized reopening of frozen Stage 5.7 — see §13) |

## 3. Attribution source

| source_type | meaning |
|---|---|
| `ATTACK` | the attribution resolves to an attack/injection origin (ORIGIN only) |
| `MEMORY` | the attribution resolves to another memory (LINEAGE, PROPAGATION) |
| `NONE` | no source was established (a legitimate, informative negative finding — e.g. a foundation memory with `NO_ATTACK_ORIGIN`, or a memory with `NO_LINEAGE_ANCESTOR`) |

## 4. The central structural finding: ORIGIN is never genuinely ambiguous for one memory

`Phase5EventLedger.append()`'s `DuplicateMemoryClaimError` invariant (added during the
Stage 5.7 review, `phase5/schema/event_ledger.py`) already, structurally, prevents two
different `attack_injection` events from ever claiming the same `memory_id`. Consequence:
**`attribute_origin()` for a single `memory_id` is always exactly one of `UNIQUE` or
`NO_ATTACK_ORIGIN` — `MULTIPLE_POSSIBLE_SOURCES` is not a reachable status for ORIGIN
under this framework's own write-time invariant**, and the implementation must not
pretend otherwise by inventing a scenario for it. (`MULTIPLE_POSSIBLE_SOURCES` remains a
real, reachable status for **LINEAGE** — a memory legitimately can have more than one
real parent via `derived`'s own `source_memory_ids` tuple — and is exercised there,
Scenario D.)

## 5. Evidence discipline — reused vocabulary, never invented

`evidence_kind` on every positive `AttributionResult` is one of Stage 5.7's own four
(`phase5.wiring.lineage.EVIDENCE_KINDS`): `OBSERVED_EVENT`, `EXPOSURE_ONLY`,
`COUNTERFACTUAL_EVIDENCE`, `LINEAGE_REACHABILITY`. No fifth kind was found necessary.

The mapping from attribution_type to the evidence_kind(s) it may legitimately carry:

| attribution_type | possible evidence_kind |
|---|---|
| ORIGIN | `OBSERVED_EVENT` only (a real `attack_injection` event) |
| LINEAGE | `OBSERVED_EVENT` only (real `derived` events) |
| PROPAGATION | `LINEAGE_REACHABILITY` only (never upgraded to a stronger claim) |
| EXPOSURE | `EXPOSURE_ONLY` (retrieved/selected/exposed are all still exposure, never usage) |
| INFLUENCE | `COUNTERFACTUAL_EVIDENCE` only — the ONLY grounds for `INFLUENCE_ESTABLISHED` |
| REFERENCES | `OBSERVED_EVENT` only (a literal content-citation fact, exactly as strong/weak an evidentiary claim as LINEAGE — never usage or influence) |

**Never conflated, by construction**: RETRIEVED ≠ SELECTED ≠ EXPOSED ≠ USED ≠ INFLUENCED.
`attribute_exposure()` reports retrieved/selected/exposed as three independent booleans
(in `details`) plus its own `status`; it never sets `status=INFLUENCE_ESTABLISHED` and
`attribute_influence()` never derives an answer from exposure, selection, or retrieval —
only from a real `counterfactually_influential` event. Likewise, LINEAGE_REACHABILITY
(structural, derivation-graph reachability) is never treated as evidence for INFLUENCE
(causal). A memory can be `PROPAGATION`-reachable from an attack and simultaneously
`INFLUENCE_NOT_ESTABLISHED` — this is the expected, correct outcome for "exposure without
influence" (Scenario E) and is not treated as a contradiction to reconcile.

## 6. No numeric confidence score (decision, per instruction §16)

Rejected. See `attribution/schema.py` module docstring for the full reasoning: every
question here reduces to a discrete evidence fact, and a status/evidence_kind pair
communicates that fact more precisely, and less misleadingly, than a synthetic score
would. `AttributionResult` has no confidence/score field.

## 7. Ambiguity handling — closed status vocabulary

`attribution/schema.py::ATTRIBUTION_STATUSES` (`UNIQUE`, `MULTIPLE_POSSIBLE_SOURCES`,
`INSUFFICIENT_EVIDENCE`, `NO_ATTACK_ORIGIN`, `NO_LINEAGE_ANCESTOR`,
`INFLUENCE_ESTABLISHED`, `INFLUENCE_NOT_ESTABLISHED`). `NO_LINEAGE_ANCESTOR` is the one
addition beyond the prompt's own named list, justified because it is a real, distinct
fact ("this memory is a root/foundation memory — not derived from anything") that neither
`NO_ATTACK_ORIGIN` (an attack-specific question) nor `INSUFFICIENT_EVIDENCE` (a gap in
observability) correctly describes; collapsing it into either would misrepresent a
perfectly well-evidenced negative as an attack-negative or an observability gap.

Ambiguity is never forced to one answer: `MULTIPLE_POSSIBLE_SOURCES` results carry
`candidate_source_ids` (all of them) and `source_id=None` — no arbitrary pick.

## 8. Multi-attack, cross-run, and version/supersession handling

- **Multi-attack isolation**: every attribution function takes explicit ledgers scoped
  to one run's storage directory (the same "one storage_dir per run/campaign" discipline
  every Phase 3/4/5 ledger already assumes — see `event_ledger.py`'s own "Concurrency"
  section). No function ever merges evidence across two different attacks' injected
  memories unless a real `derived`/lineage edge connects them — cross-attribution is
  never inferred from co-occurrence alone (Scenario C).
- **Cross-run isolation**: `AttributionResult.run_id` is always the run whose ledgers
  produced the result; a target `memory_id` that happens to be reused (or coincidentally
  fingerprint-identical) across two independent run storage directories is attributed
  independently per run — this layer never reads two runs' ledgers in one call (Scenario H).
- **Version/supersession**: a `SUPERSEDES` edge (`derive_supersedes_edges()`) is a
  distinct memory identity change, not a lineage hop — `attribute_lineage()` does not
  silently collapse a superseded memory and its successor into one attribution subject.
  Each retains its own independent `AttributionResult` (Scenario I).

## 9. Read-only, no second source of truth

Every `attribute_*` function takes ledgers/reader objects as arguments and returns a
freshly-computed `AttributionResult` (or tuple thereof) — no attribution function
persists anything, no attribution function is a required input to any other Phase 5
function, and calling one twice with the same ledger state is required to be
byte-identical (Scenarios J, K — reload and repeated-call determinism).

## 10. A-MEM / real-vendor handling

Identical discipline to every prior stage: no fabrication. If a target's evidence chain
depends on real-vendor (`RealMem0Adapter`/`RealAMemAdapter`) retrieval-identity behavior
that Stage 5.5's own "Pre-5.8 gate" already marked `FOUNDATION_UNAVAILABLE` in this
environment, attribution over that evidence is scoped to what Phase 5 actually recorded
(mock-foundation runs) and does not claim real-vendor validity it cannot support. No new
A-MEM-specific attribution code path is introduced; this layer simply inherits the
limitation already disclosed in `PHASE5_CHECKLIST.md`'s "Pre-5.8 gate" section.

## 11. Metrics (see `attribution/metrics.py` module docstring for full definitions)

Computed only where genuine ground truth exists in the test/validation harness itself
(this framework has no independently-labeled "true" attack-origin dataset beyond what the
seven real attack pipelines themselves establish by construction) — never invented from
attribution's own output circularly. Named metrics: origin/injection attribution
accuracy, lineage reconstruction accuracy, source precision/recall, ambiguity rate, false
attribution rate, and influence attribution accuracy — the last computed ONLY over cases
that have a real counterfactual finding to compare against (never extrapolated to cases
without one).

`attribution/metrics.py::build_origin_ground_truth()` reduces the friction of hand-
assembling this map without changing what ground truth fundamentally requires: it reads
`memory_id -> injection_id` directly off real `AttackMemoryLifecycleResult` objects the
caller already obtained by actually calling `phase5.wiring.live_attack_runs.run_live_*_injection()`
— the same real injection that produced the memory — and accepts a separate,
caller-supplied `known_non_attack_memory_ids` list for real negatives it never guesses at.

## 12. Ground truth definition

For the purposes of this layer's own validation (not a new benchmark ground-truth
mechanism — Phase 5's `derive_ground_truth_transitions()` and the seven attacks' own
injector/artifact fixtures remain authoritative), "ground truth" for a given test
scenario means: the real `attack_injection`/`derived`/`counterfactually_influential`
events the test itself constructs or drives through `phase5/wiring/live_attack_runs.py`
— i.e., the test knows what it caused to happen, and attribution is checked against that
known cause, never against a separately-invented label.

## 13. REFERENCES — closed via an explicitly-authorized reopening of frozen Stage 5.7

The original implementation (§0–12 above) disclosed REFERENCES as unimplemented, per
Stage 5.7's own (still-correct) rejection of a specific idea: inferring that "the model
actually referenced [a memory] in its answer" from word overlap, semantic similarity, or
citation coincidence — an agent-BEHAVIOR claim this framework has no calibrated way to
make. **That rejection is unchanged.**

On 2026-09-13 the user explicitly authorized reopening frozen Stage 5.7 to fix this
specific gap, and a narrower, purely STRUCTURAL question was found and implemented
instead: whether one real memory's own persisted CONTENT literally contains another real
memory's exact `[memory_id]` citation-bracket substring (the identical literal format
`agent_runtime/messages.py::render_messages()` itself uses — reused only as a textual
pattern, never as a claim about model behavior). This is an exact, deterministic
substring match against real, known memory_ids, not a heuristic, and is exactly as
strong an evidentiary claim as `DERIVED_FROM` — `OBSERVED_EVENT`, a structural content
fact, never usage or influence.

`derive_references_edges()` (`phase5/wiring/lineage.py`) was added to the now-refrozen
Stage 5.7; `attribute_references()` (`attribution/wiring/references.py`) wraps it
verbatim, exactly like every other attribution function here wraps its Stage 5.7
counterpart. Two new statuses were added for this type alone
(`REFERENCES_ESTABLISHED`/`REFERENCES_NOT_ESTABLISHED`) rather than reusing
`MULTIPLE_POSSIBLE_SOURCES` for a memory citing more than one other memory — citing
several other memories is a confirmed, unambiguous multiplicity (every citation
independently verified), never the genuine uncertainty that status represents elsewhere.
