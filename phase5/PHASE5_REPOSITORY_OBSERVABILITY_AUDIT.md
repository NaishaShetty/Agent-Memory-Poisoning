# Phase 5 — Repository Observability Audit

Status: evidence-gathering only. No Phase 5 code written. This document precedes and
gates Stage 5.1 (Observability Requirements & Instrumentation Contract) per the Phase 5
master prompt's Section 25 requirement to inspect the actual repository before designing
anything.

Scope inspected: `phase3/`, `phase3_reference/`, `phase4/`, `preprocessing/`, `tests/`,
and root-level docs. Vendored third-party candidate repos under
`phase3/datasets/candidates/*/raw/` (mem0, letta, cognee, hipporag, etc.) are excluded —
they are downloaded benchmark candidates, not MAMBench project code.

---

## 0. Existing Phase 5 planning material

- `PHASE5_HANDOFF_REPORT.md` (repo root, written 2026-09-11 at Phase 4's freeze) exists
  and is substantive, but it argues for a **defense-evaluation** Phase 5 — that
  recommendation is superseded by the current master prompt, which is explicit that
  Phase 5 is instrumentation/observability, not defense. Its Section 5 open question is
  still true and relevant: *"provenance metadata exists and is tracked, but nothing in
  V3-Hybrid currently acts on it."*
- No `phase5/` directory, instrumentation-contract doc, or observability spec existed
  before this file. No dedicated event-schema doc for a "Phase 5" concept exists anywhere.

---

## 1. Existing instrumentation — two regimes that never talk to each other

**(A) Real, tested, ledger/event infrastructure** — `phase3/evaluation/foundations/`:
`CanonicalMemoryLedger`, `CanonicalEventLedger`, `RunConfigLedger`,
`ExperimentBoundaryLedger`, `SupersessionLedger`, `ProvenanceGraph`,
`taint_propagation.py`. Append-only, JSONL-backed, schema-validated, exercised by a real
test suite (`phase3/evaluation/tests/test_canonical_*`, `test_provenance_*`,
`test_taint_propagation.py`, `test_h2_*`, `test_h3_versioning.py`,
`test_campaign_formal_runner_h4_wire*.py`).

**(B) Ad hoc `print()` → manually captured `.txt` files** — this is how every real
Phase 4 attack campaign records evidence today (e.g.
`phase4/attacks/farma/milestone5_campaign.py`, `phase4/shared/dormancy_report.py`'s
`print_dormancy_report()`). Confirmed: zero uses of Python's `logging` module anywhere
under `phase3/evaluation/` or `phase4/` (the only real `logging.getLogger` usage in the
repo is `preprocessing/logging_utils.py`, an unrelated Phase 2 data-prep module never
imported by phase3/phase4).

**Correction to an initial finding**: ledger (A) is **not** universally unadopted. It
*is* wired into real Phase 3 campaign runs — `phase3/evaluation/agent_runtime/
canonical_wiring.py` (Condition B / Mem0 only) is called from
`campaign_formal_runner.py::run_condition_b_mem0()` and from
`campaign_selection_policy_runner.py`, `campaign_v2_runner.py`, `campaign_v3_runner.py`,
`campaign_v5_runner.py`. So the frozen Phase 3 clean-agent campaigns (Mem0 condition)
**do** write real `CanonicalMemoryRecord`s and `retrieved`/`selected`/`rejected`
`CanonicalEvent`s through the ledger. What is confirmed **not** wired anywhere is:
Phase 4 attack campaigns (zero call sites of `CanonicalEventLedger.append`,
`build_canonical_event`, or `write_canonical_memory` under `phase4/`), and Condition C
(A-MEM) is explicitly out of scope in `canonical_wiring.py`'s own module docstring.

A third, legacy regime — `phase3_reference/diagnostics/derived_memory/results/**/events/
*.events.jsonl` — used an incompatible, earlier event schema and predates/was superseded
by (A). Not authoritative; Phase 5 should not build on it.

---

## 2. Canonical event/record schemas that already exist

All under `phase3/evaluation/foundations/`, plain frozen dataclasses backed by real JSON
Schema contracts (`phase3/schemas/*.json`, `phase3/evaluation/contracts/*.schema.json`):

- `CanonicalMemoryRecord` (`canonical.py`) — memory_id, memory_type, content, source,
  parent_ids, creation_event, creation_timestamp, lifecycle_state, equivalent_to,
  conflicts_with, superseded_by.
- `CanonicalEvent` (`canonical_event.py`) — event_id, event_type (10 values: created,
  retrieved, selected, used, derived, superseded, retired, rejected,
  relationship_detected, counterfactually_influential), memory_ids, timestamp, actor,
  reason, task_id, previous_state, new_state, foundation_name, foundation_memory_id,
  source_memory_ids, target_memory_id, relationship_type, mechanism, score, threshold,
  config_fingerprint, counterfactual_answer_hash, baseline_answer_hash, diff_criterion,
  masking_method. Cross-field validation is per-event-type in `__post_init__`.
- `RunConfigRecord` (`run_config.py`) — content-derived `CFG-<sha256>` fingerprint over
  embedding/reranker/retrieval/selection configuration.
- `ExperimentBoundaryRecord` (`experiment_boundary.py`) — `BND-<fingerprint>`,
  boundary_type=RESET, scope, timestamp, actor, reason.
- `evaluate_and_trace()`'s trace dict (`agent_runtime/trace.py`) — experiment_id,
  dataset, record_id, model/foundation identity, configuration, task, retrieved/
  selected/exposed/used/contributed memories, per-memory lifecycle, agent_output,
  evaluation_result, failure_stage, latency, fingerprints. `used_memories`/
  `contributed_memories` are honestly marked `NOT_OBSERVABLE` — the runtime does not
  implement usage attribution beyond retrieval/selection/exposure.
- `GraphNode`/`GraphEdge`/`ProvenanceGraph` (`provenance_graph.py`) — node types
  {memory, task, memory_version, experiment_boundary}; edge types {derived_from,
  retrieved, selected, rejected, used, counterfactually_influential, superseded_by,
  equivalent_to, conflicts_with, has_version, within_boundary}, every edge grounded by an
  `established_by_event_id` — "no edge is ever invented."
- Phase 4's own per-attack result dataclasses (`FARMAInjectionResult`,
  `ControlledCampaignRecord`, `AttackCollectResult`, `DormancyState`,
  `JointCounterfactualRunOutcome`) — plain dataclasses, never persisted, only printed or
  returned in-memory.

---

## 3. Identifier schemes

| Identifier | Phase 3 | Phase 4 |
|---|---|---|
| `event_id` | `EVT-<sha256 content fingerprint>` via `event_identity.generate_event_id()`, deterministic, never `uuid4()` | Not minted — no `CanonicalEvent` ever appended from a phase4 attack path |
| `boundary_id` | `BND-<fingerprint>` | unused |
| `config_fingerprint` | `CFG-<fingerprint>`, wrapped in `RunConfigRecord`/`RunConfigLedger` | `RunConfiguration.configuration_fingerprint()` exists and is computed/printed (`campaign_runner.py`), but never wrapped into a `RunConfigRecord` or appended to a ledger in any real Phase 4 run |
| `run_id` / `task_id` / `experiment_id` | Plain caller-supplied strings, `task_id` used consistently via `EvaluationRun` schema | `task_id` is an ad hoc literal per attack script (e.g. `"farma-m5"`); no `run_id`/`experiment_id` object exists for attack campaigns at all |
| `attack_id` | n/a | Plain string constant per attack (`"farma"`, `"agentpoison"`, …), consistent by convention only, no shared enum |
| poison/artifact id | n/a | Field name varies per attack (`poison_id`, `step_id`, `artifact_id`, `scenario_id`) — disclosed as non-uniform in `PHASE4_4_6_POISON_ARTIFACT_AND_INJECTION_MODEL.md` |
| `injection_id` / `InjectionEvent` | n/a | Named in the abstract common attack contract doc; **no concrete class/dataclass by this name exists anywhere in `phase4/`** |

Phase 3's foundations layer has a real, disciplined, content-derived, collision-checked
identity scheme. Phase 4 does not use it and has no equivalent of its own beyond ad hoc
string literals.

---

## 4. Retrieval & selection telemetry

Real per-candidate data is computed by `hybrid_selection.select_by_hybrid_score()`
(the actual selection mechanism used by both Phase 3 and Phase 4 campaign paths):
`HybridSelectionResult(selected, rejected, top_k, weights)`, where every
`HybridScoredCandidate` carries `memory_id, content, cosine_score,
token_overlap_score, entity_overlap_score, blended_score` — computed for the **entire**
candidate pool (`RETRIEVAL_POOL_SIZE_N = 20`), not just the selected top-K
(`DEFAULT_TOP_K = 8`).

**Gap**: in `phase4/shared/campaign_runner.py::retrieve_select_generate()`, this is
immediately reduced to bare `(memory_id, content)` pairs. `sel.rejected` is discarded
entirely; `AgentRunOutcome` only carries `retrieved_memory_ids`/`selected_memory_ids` —
id tuples with no scores, no ranks. The exact data Stage 5.5 needs already exists inside
one function call and is thrown away before leaving it.

---

## 5. Agent decision/action telemetry

`phase3/evaluation/agent_runtime/trace.py::evaluate_and_trace()` produces a rich,
fingerprinted per-task trace (see §2) — real and tested, but it is an
**evaluation-time** trace requiring evaluator-only inputs (`expected_answer`,
`gold_evidence_ids`) supplied by a caller outside the live agent runtime; `runner.py`
itself never calls it.

**Gap**: zero call sites of `evaluate_and_trace()` anywhere under `phase4/`. Every real
Phase 4 campaign gets agent-decision data only from `AgentRunOutcome`'s raw fields and
prints them directly — no trace object, no fingerprint, no lifecycle classification for
any real attack run.

---

## 6. Provenance

Real and multi-layered in Phase 3: `CanonicalMemoryRecord.source`/`.parent_ids`,
`CanonicalEvent.source_memory_ids`/`.target_memory_id` for `derived` events, the
foundation-name/foundation-memory-id alias table on `CanonicalMemoryLedger`, and
`ProvenanceGraph`/`taint_propagation.tainted_memories()` built on top.

Phase 4's attack-origin provenance is real but shallow: every injector writes
`attacker_originated: True, attack_id: "<name>"` plus attack-specific fields directly
into the foundation's `metadata` via `add_memory()` — never into a
`CanonicalMemoryRecord.source`, never as a `CanonicalEvent`. It is queryable only by
calling `foundation.inspect_memory()` on the live vendor store, not through any
benchmark-owned ledger.

**Known, disclosed limitation to inherit, not silently paper over**:
`taint_propagation.py`'s own docstring states a real, open H.3/H.4-D versioning-gap bug:
under current frozen H.3 behavior, `lifecycle_status` realistically reports
`UNKNOWN_VERSIONING_GAP` for every genuinely-tainted id. `tainted_memories()` also
explicitly documents that lineage-reachability taint is **not** counterfactual
influence (a tainted memory may never have been retrieved/selected/used, and a
counterfactually-influential memory need not be lineage-tainted) — this distinction must
carry into Phase 5's event/relationship design (Section 15 of the master prompt already
anticipates it).

---

## 7. Attack telemetry (Phase 4 side)

- `phase4/shared/adapter.py::AttackAdapter` — real shared interface;
  `execute()`/`collect()` delegate to `campaign_runner.retrieve_select_generate()` and
  `phase3.evaluation.agent_runtime.counterfactual.run_counterfactual_mask`/
  `compare_counterfactual_run`, returning an in-memory `AttackCollectResult`.
- `phase4/shared/campaign_runner.py::retrieve_select_generate()` — the shared
  retrieve→select→render→generate pipeline every attack uses; emits nothing itself.
- `phase4/shared/counterfactual_joint_mask.py` — joint masking for cases where multiple
  redundant poisoned artifacts are selected simultaneously; in-memory only.
- `phase4/shared/dormancy_report.py::describe_dormancy()` — the **one** place a piece of
  the 9-state ground-truth vocabulary is actually computed as code
  (`{NOT_RETRIEVED, POISON_IN_CANDIDATE_POOL, POISON_SELECTED_TOP_K}`); output only ever
  goes to stdout via `print_dormancy_report()`.
- `phase4/shared/controlled_campaign.py::run_controlled_campaign()` — one
  `ControlledCampaignRecord` per single-artifact attack; in-memory only.
- The full 9-state vocabulary (`POISON_NOT_ADMITTED` … `ATTACK_SUCCESS`/
  `ATTACK_FAILURE`) is **not** a real enum/type anywhere in code — it exists only as
  prose in `PHASE4_4_2_COMMON_ATTACK_CONTRACT.md` and as hand-transcribed table cells in
  `PHASE4_4_9_ATTACK_GROUND_TRUTH.md`, built (per that doc's own description) "by
  re-reading each attack's own persisted run logs directly."
- `FARMAInjector.inject()` (read in full) returns `FARMAInjectionResult{artifact_id,
  admission_status, attacker_originated, canonical_memory_id, stored_text,
  precedent_count}` — `admission_status` is a plain string constant, not drawn from any
  shared enum. Its campaign script (`milestone5_campaign.py`) explicitly declines to
  auto-classify `ATTACK_SUCCESS`, "per this session's standing discipline against
  auto-judging without a documented, calibrated rule" — a real, deliberate scientific
  discipline worth preserving in Phase 5's design (evidence over auto-judgment).

---

## 8. Trace/graph/propagation infrastructure

Real and load-bearing: `ProvenanceGraph` is explicitly a **projection**, rebuilt fresh
every call from the ledgers, never a second store. Query functions:
`build_provenance_graph()`, `build_multi_boundary_provenance_graph()`,
`forward_provenance()`, `backward_provenance()`, `derivation_propagation()`,
`task_exposure_and_use()`, `attack_origin_lineage()` (thin pass-through to
`taint_propagation.tainted_memories()`). All tested
(`test_provenance_graph.py`, `test_provenance_graph_extensions.py`,
`test_provenance_lineage.py`, `test_taint_propagation.py`).

**Critical gap**: this machinery consumes `CanonicalMemoryLedger`/`CanonicalEventLedger`
data. Per §1/§3/§7, Phase 4's attack campaigns never populate either ledger, so
`attack_origin_lineage()` has never run against real attack data — it is real, tested,
reusable infrastructure that is currently starved of the one input Phase 5 exists to
provide.

---

## 9. What the test suites treat as load-bearing

`phase3/evaluation/tests/` has dedicated tests for every ledger/graph/versioning piece
named above. `phase4/tests/` (14 files) contains **zero** references to
`CanonicalEventLedger`, `CanonicalMemoryLedger`, `ProvenanceGraph`, or
`tainted_memories` — every Phase 4 test targets the print-and-return regime
(`AgentRunOutcome`, `AttackCollectResult`, `ControlledCampaignRecord`, `DormancyState`).
**No test anywhere in the repo constructs a `CanonicalEventLedger`, injects a Phase 4
attack artifact, and asserts something about the resulting event/provenance graph.**
This is the clearest single piece of evidence for what Phase 5 exists to close.

---

## 10. Reusable as-is

1. `CanonicalMemoryLedger` / `CanonicalEventLedger` / `RunConfigLedger` /
   `ExperimentBoundaryLedger` / `SupersessionLedger` — real, tested, append-only JSONL,
   collision/idempotency-checked. Already proven end-to-end for Phase 3 Condition B.
2. `CanonicalEvent`'s 10-type vocabulary, including a closed `rejected`-reason enum and
   `counterfactually_influential` — already models most of what Phase 5's retrieval/
   selection/influence instrumentation needs.
3. `event_identity.generate_event_id()` / `build_canonical_event()`,
   `experiment_boundary.generate_boundary_id()` — deterministic, content-derived ID
   factories. Any new Phase 5 identifier should be minted through the same discipline
   rather than inventing a new scheme (e.g. `uuid4()`).
4. `ProvenanceGraph` + `attack_origin_lineage()` / `tainted_memories()` — ready to answer
   lineage questions the moment real events flow in.
5. `phase4/shared/{adapter.py, campaign_runner.py, counterfactual_joint_mask.py,
   dormancy_report.py, controlled_campaign.py}` — the shared attack execution/
   measurement pipeline all 7 attacks already use. Phase 5 instrumentation should attach
   to this shared layer, not to each attack individually — this is what "instrumentation
   must be common across all seven attacks" (Section 18) actually requires in practice.
6. `hybrid_selection.HybridScoredCandidate` — already the exact per-candidate shape
   Stage 5.5 needs; it just needs to stop being discarded.
7. `contracts/boundary.py`'s `FORBIDDEN_KEYS` / `enforce_foundation_call_boundary` —
   confirmed to actually fire in a real trial; any new Phase 5 metadata field must
   respect the same content/metadata boundary.

## 11. Genuine observability gaps Phase 5 must add

1. **No wiring between Phase 4 attack campaigns and the Phase 3 ledgers.** This is the
   load-bearing gap — everything reusable above is real but has never received real
   attack-campaign data.
2. **No structured logging anywhere in phase3/evaluation or phase4** — all evidence
   today is `print()` → manually captured `.txt` → manually hand-transcribed markdown
   tables. No machine-queryable record of any single real attack trial exists today.
3. **Per-candidate retrieval scores computed but discarded** before reaching
   `AgentRunOutcome`.
4. **No unified `injection_id` / `InjectionEvent` / `InjectionSequence`** — named in the
   abstract contract doc, never implemented.
5. **No run-level identity (`run_id`/`experiment_id`) for Phase 4** — task_id is a
   hardcoded literal per script.
6. **The 9-state ground-truth vocabulary is not real code** — only
   `dormancy_report.py`'s 3-state subset is computed; the other 6 states are hand
   classified from logs.
7. **No automated re-run/CI harness** — every real result is manually run and captured
   (consistent with the Phase 4 handoff's own disclosure).
8. **The H.3/H.4-D taint-propagation versioning gap** — `lifecycle_status` is
   realistically `UNKNOWN_VERSIONING_GAP` for genuinely tainted memories today; Phase 5
   must not build a metric that silently assumes this field is populated.
9. **No latency/overhead instrumentation beyond LLM generation latency** — no
   retrieval/embedding/reranking/ledger-write latency is captured anywhere.

---

## 12. Implication for the proposed 5.1–5.9 structure

The nine-stage structure in the master prompt survives inspection largely unchanged,
with one adjustment: Phase 5's central engineering act is not "build new instrumentation
from nothing" — it is **extend the existing, tested `canonical_wiring.py` pattern (proven
for Phase 3 Condition B) to a common, attack-agnostic wiring layer that sits at the
`phase4/shared/` boundary** (campaign_runner.retrieve_select_generate /
AttackAdapter.execute/collect), so that all 7 attacks get ledger-backed instrumentation
through one shared integration point rather than seven bespoke ones. This directly
satisfies Section 18's "no attack-specific instrumentation" constraint using
infrastructure that already exists and is already trusted, rather than inventing a
parallel event system.

Recommended sequencing adjustment: Stage 5.2 (Canonical Event Schema) should default to
**reusing `CanonicalEvent` and extending its `event_type` vocabulary** (e.g. adding
`injected`, `attack_state_transition`, `decision`, `action` types) rather than designing
a new schema from scratch — the master prompt's own Section 10 anticipates this
("the schema must emerge from real Phase 3/4 implementation requirements"), and a new,
parallel schema would recreate exactly the two-regimes-that-never-talk-to-each-other
problem documented in §1 and §9 above.

No changes are proposed to frozen Phase 3 or Phase 4 semantics. All of the above are
observations; nothing here modifies `canonical.py`, `canonical_event.py`,
`hybrid_selection.py`, or any Phase 4 attack module.
