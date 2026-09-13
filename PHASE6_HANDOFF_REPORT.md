# MAMBench — Phase 6 Handoff Report

Status: handoff document, not a Phase 6 implementation plan. Written 2026-09-13, at the
point of Phase 5's official freeze and the Attribution layer's PASS verdict, for whoever
(human or agent) picks up Phase 6 next. This document summarizes what Phases 1–5 and the
post-Phase-5 Attribution layer actually established — brief, not a reproduction of every
underlying document — so Phase 6 starts from evidence, not from re-deriving it. It does
not decide or invent Phase 6's scope.

For full detail, follow the citations in each section rather than treating this document
as self-sufficient.

---

## Phase 1 — Dataset and Benchmark Foundations

- **What it did**: identified, registered, acquired, and cleaned four core
  conversational-memory datasets (LoCoMo, LongMemEval, MSC, Conversation Chronicles) plus
  supporting workload/attack/sleeper/evaluation resources (28 tracked resources total,
  classified into exactly one of 5 roles in Phase 2.4).
- **Provenance**: every resource's real acquisition path, license, and integrity status
  is recorded in `data/metadata/resource_registry.json` / `dataset_manifest.json`, never
  fabricated when a source dataset didn't provide a fact.
- **Validation**: 10-check validation, 9 pass / 1 fail (an encoding issue), disclosed not
  hidden.
- **Remaining limitations**: MSC's license is unpublished (used under a documented,
  disclosed assumption); LongMemEval/Conversation Chronicles are multi-hundred-MB to
  multi-GB and never committed (see `.gitignore`'s `data/raw/`, `data/interim/`,
  `data/processed/` policy) — identity/checksum/acquisition instructions live in the
  tracked manifests instead.
- **Canonical location**: `preprocessing/`, `data/`, `docs/phase2/` (Phase 1's own
  artifacts and Phase 2's freeze/validation documents that certify them together).

## Phase 2 — Unified Benchmark Substrate

- **What it did**: turned Phase 1's four independently-shaped raw datasets into one
  internally consistent, provenance-preserving benchmark substrate, in six additive
  layers (2.2–2.7), documented in `docs/phase2/PHASE2_FREEZE.md`.
  - 2.2 **Unified Memory Record** (schema v1.1.0) with an explicit per-field
    `field_status` (`SOURCE_PROVIDED`/`BENCHMARK_GENERATED`/`INFERRED`/absence reason).
  - 2.3 **Temporal normalization** (policy v2.3.0) — never invents a source-absolute
    timestamp a dataset never provided (MSC/Conversation Chronicles correctly lack one).
  - 2.4 **Resource organization** — the hard, enforced memory-foundation-role boundary
    (only the 4 core datasets may ever be `memory`-role).
  - 2.5 **Reproducibility metadata** — machine-/timestamp-independent canonical identity
    hashing.
  - 2.6 **Cross-phase substrate validation** — 29 checks, all PASS.
  - 2.7 **Acceptance and freeze** — the gate confirming all six layers still agree.
- **Frozen memory schema**: the Unified Memory Record, v1.1.0.
- **Temporal policy**: v2.3.0, deterministic relative-time resolution.
- **Reproducibility**: every resource has a canonical identity hash excluding
  machine-local paths and `generated_at`.
- **Remaining limitations**: none disclosed as currently blocking; historical
  reconciliation work (`docs/phase2/LOCOMO_QA_RECONCILIATION.md`,
  `DSRM_RESOLUTION.md`) documents real, resolved data-quality issues found and fixed
  during this phase, preserved as scientific record.
- **Canonical location**: `docs/phase2/`, `preprocessing/`, `tests/` (top-level).

## Phase 3 — Clean Memory-Augmented Agent (V3-Hybrid)

- **What it is**: the canonical, frozen victim architecture — real hybrid
  retrieval/reranking, real Mem0/A-MEM ingestion, real generation/verify/revise, deployed
  against the Phase 2 substrate under benign conditions only.
- **Canonical memory/event infrastructure**: `CanonicalMemoryLedger`,
  `CanonicalEventLedger`, `CanonicalEvent` (append-only, content-derived identifiers,
  frozen `EVENT_TYPES` vocabulary), `ProvenanceGraph`, `taint_propagation.py`,
  `memory_versioning.py` (supersession/retirement).
- **Provenance**: the agent-visible/evaluator-only content boundary
  (`foundations/contracts/boundary.py`'s `FORBIDDEN_KEYS`) — confirmed to actually fire,
  not merely exist on paper.
- **Known limitations**:
  - `LIFECYCLE_STATUS_UNKNOWN_VERSIONING_GAP` — a latent bug in frozen
    `memory_versioning.reconstruct_version_history()` (a memory that is merely a parent
    of a `derived` memory incorrectly picks up that event into its own version history)
    means every genuinely-tainted memory today reports this status rather than a
    resolved current version; `get_current_version()` is never actually reachable for a
    real taint result under present frozen behavior. Documented, not repaired (frozen
    file), surfaced honestly rather than hidden. See
    `phase3/evaluation/foundations/taint_propagation.py`'s own module docstring.
  - Phase 3's own evaluation is benign-only by design (no adversarial content) — Phase 4
    is the adversarial extension.
- **What is frozen**: all of `phase3/evaluation/` — verified via `git status --porcelain`
  before and after every real Phase 4/5/attribution campaign, never modified since.
- **Historical/reference material**: `phase3_reference/` — an explicitly preserved
  archive of the original Phase 3 attempt (V1 canonical baseline, a never-frozen V2/V2c
  candidate-selection thread, Experiments A–I, diagnostics, an incomplete Qwen
  reasoning-layer pilot). Deliberately kept for scientific record (rejected/negative
  results are evidence, not garbage) — see `phase3_reference/README.md`. Not the active
  implementation; do not treat any result there as validated for the current baseline.

## Phase 4 — Seven-Attack Memory Manipulation Benchmark

- **Seven attack families**, each with at least one real, executed campaign against
  V3-Hybrid: **AgentPoison** (white-box gradient trigger optimization), **MINJA**
  (query-only, agent-mediated progressive insertion), **FARMA** (forged reasoning traces,
  self-referential amplification), **MemoryGraft** (gated, LLM-judged forged
  "successful experience" records), **DSRM** (black-box LLM self-refinement + white-box
  InfoNCE optimization), **MPBench-PCFI** (unmarked fabricated facts; 2 of 6 MPBench
  classes applicable, 4 documented as architectural limitations, never simulated), and
  **Sleeper Memory Poisoning** (dormant, trigger-activated document-embedded write
  instruction).
- **Common attack lifecycle**: 10 stages — injection → admission → storage → retrieval →
  selection → exposure/use → propagation → influence → detection → attribution.
- **Shared infrastructure**: Common Attack Contract (Revision 3, frozen) —
  `PoisonArtifact`/`InjectionEvent`/`InjectionSequence` schema, 9-state ground-truth
  vocabulary; `AttackAdapter` (shared `execute()`/`collect()`, attack-specific
  `validate()`/`prepare()`/`generate()`/`inject()`); `campaign_runner.py`;
  `counterfactual_joint_mask.py`; `dormancy_report.py`.
- **Coverage**: 97/97 automated tests passing (mocked, no external infrastructure); 26
  real entry-point scripts, 25 with persisted, citable evidence.
- **Real campaign status**: 10/10 real query trials where an attack's own trigger
  condition was met resulted in top-8 selection and measurable answer influence
  (confirmed via counterfactual masking), zero exceptions. 3 additional real trials
  (A-MEM, a genuine gate refusal, DSRM white-box-to-campaign) closed specific disclosed
  gaps during Phase 4's own release audit.
- **Known scientific limitations** (carried forward unmodified — see
  `PHASE5_HANDOFF_REPORT.md` §3, §6 at repository root for the full original record):
  - No exhaustive attack coverage claimed.
  - No statistically powered success rate — every real result is n=1 or n=2 per
    condition.
  - No defense/mitigation evaluation exists anywhere in this project.
  - A-MEM coverage is n=1 — real evidence the finding generalizes beyond Mem0, not
    general A-MEM coverage.
  - No genuine post-admission `ATTACK_FAILURE` has been observed (the one real
    `ATTACK_FAILURE` is pre-admission, a gate refusal).
  - No automated CI/re-run harness — every real result was run manually, by choice.
  - Provenance/ground-truth metadata (`attacker_originated`/`attack_id`) has not been
    tested under adversarial conditions where an attacker forges the metadata itself.
- **What is frozen**: Common Attack Contract Revision 3; all seven attack
  implementations, injectors, and gates; every real campaign log/artifact (never
  modified retroactively). See `phase3/experiments/PHASE4_4_12_PHASE4_FREEZE.md`.

## Phase 5 — Instrumentation & Monitoring

- **Architecture**: an additive observability layer over Phases 3–4, never a redesign.
  Reuses Phase 3's 9 frozen `CanonicalEvent` types verbatim; adds a new, parallel
  `Phase5Event` schema for 6 event families the repository audit found no existing
  schema for (retrieval-candidate scoring, context assembly, agent decision, agent
  action, attack injection, ground-truth transition).
- **Event model**: `Phase5Event` (frozen, closed per-type field validation),
  content-derived identifiers throughout (never `uuid4()`), a 9-state ground-truth
  vocabulary made real code for the first time.
- **Run/episode identity**: `ExperimentRunLedger`/`EventRunMembershipLedger` — every
  event, from either schema, registered to a stable `experiment_id`/`run_id`/
  `episode_id`.
- **Lifecycle instrumentation**: common entry points for memory creation, attack
  injection, derivation, and lifecycle transitions, usable by any of the seven attacks
  without attack-specific branching. A `DuplicateMemoryClaimError` invariant makes a
  memory's attack origin structurally unambiguous.
- **Retrieval/selection instrumentation**: every candidate scored and persisted
  (previously computed then discarded); an explicit `canonical_status` field distinct
  from selected/rejected; the exact rendered agent-visible context persisted and
  fingerprint-verified.
- **Agent decision/action instrumentation**: wraps, never duplicates, the real
  generation call; exposure and (unobservable) usage kept as two independent facts,
  never conflated.
- **Lineage**: 9-type closed relationship vocabulary (`DERIVED_FROM`, `PRODUCED`,
  `SUPERSEDES`, `RETRIEVED_WITH`, `SELECTED_WITH`, `USED_BY`, `INFLUENCED`,
  `PROPAGATED_TO`, `REFERENCES`), each edge carrying an explicit evidence-kind
  (`OBSERVED_EVENT`/`EXPOSURE_ONLY`/`COUNTERFACTUAL_EVIDENCE`/`LINEAGE_REACHABILITY`).
  `INFLUENCED` is derivable ONLY from a real `counterfactually_influential` event.
- **Trace/graph**: `assemble_trace()`/`build_propagation_graph()` — pure, run-scoped
  projections over persisted ledger state, never a second store.
- **Memory Behavior Dataset**: a derived, 6-category analytical dataset (Stage 5.8A); a
  real, generated 10-record sample committed as a worked example.
- **Validation/non-interference**: completeness, ordering, provenance isolation, and
  determinism all directly tested; the definitive non-interference result is a
  controlled baseline-vs-instrumented comparison across all 7 attacks, zero observable
  divergence.
- **Final freeze**: Stages 5.1–5.9 (including 5.8A) — **PHASE 5 STATUS: COMPLETE —
  OFFICIALLY FROZEN.** One explicitly authorized reopening (Stage 5.7, `REFERENCES`) and
  its matching Stage 5.8/5.8A reconciliation, both re-verified and refrozen. See
  `phase5/PHASE5_CHECKLIST.md`'s "Official Freeze Statement."
- **Final validation numbers**: Phase 5 suite **203 passed, 2 skipped** (by design).
  Combined Phase 3 + Phase 4 + Phase 5 + Attribution regression: **2,079 passed, 19
  skipped, 0 failures.**

## Post-Phase-5 / Attribution

- **Hardening**: OR-1..OR-15 contract coverage audited — 15/15 DIRECT (1 real gap found,
  OR-12, closed additively); non-interference expanded from 1/7 to 7/7 attacks;
  ordering validation strengthened (+2 invariants); task-level trace projection added;
  `REFERENCES` gap found, reopened under explicit authorization, and closed
  (`derive_references_edges()` — a structural, deterministic content-citation signal,
  never a behavioral-reference inference); Stage 5.8/5.8A reconciled to compose it.
- **Attribution readiness**: audited across 5 evidence chains before implementation, all
  confirmed AVAILABLE where real evidence exists.
- **Actual attribution implementation**: a separate, top-level, read-only `attribution/`
  layer (never a Phase 5 modification) consuming the frozen Phase 5 evidence substrate.
- **Six attribution question types, implemented, never collapsed**: origin, lineage
  (one-hop or full ancestor chain), propagation, exposure, influence, and references.
  `attribute_action()` additionally resolves an action to its decision and delegates to
  exposure attribution.
- **Scientific evidence discipline**: every positive attribution result is structurally
  required (schema-validated) to cite a real, existing event; no numeric confidence
  score anywhere; retrieved ≠ selected ≠ exposed ≠ used ≠ influenced; lineage
  reachability ≠ causal influence; structural references ≠ behavioral reference,
  enforced throughout.
- **Counterfactual influence requirement**: influence attribution is grounded
  exclusively in a real `counterfactually_influential` event — directly tested against a
  temporal-order trap (early, repeated exposure with no counterfactual test still
  correctly reports not established).
- **Validation status**: 11 named scenarios (A–K) plus propagation/references/
  orchestrator/metrics coverage, all passing against the real seven-attack live-injection
  pipeline. **Attribution suite: 31 passed, 0 failures. Final verdict: PASS.**

---

## Phase 6 Handoff — Limitations

| Limitation | Origin | Status | Impact on Phase 6 | Required future action |
|---|---|---|---|---|
| A-MEM / real-vendor identity resolution unverified | Phase 5.5–5.9 | Environment limitation | Any Phase 6 work assuming real-vendor (non-mock) retrieval identity behavior is unverified for A-MEM/Mem0 | If a real-vendor environment (the isolated `h4venv` interpreter) becomes available, run the 2 already-written compatibility tests (`test_real_mem0_retrieval_identity_chain_when_available`, `test_real_mem0_identity_continuity_across_update_when_available`) — no further design work needed |
| `LIFECYCLE_STATUS_UNKNOWN_VERSIONING_GAP` | Phase 3 (frozen) | Research limitation / engineering defect in frozen code, not repaired | Every genuinely-tainted memory reports this status rather than a resolved current version; downstream lineage/attribution work correctly surfaces it rather than hiding it | Fixing requires modifying frozen `memory_versioning.reconstruct_version_history()` — out of scope for any additive phase; would need its own explicitly authorized reopening |
| Provider `finish_reason` two-state granularity | Phase 5.6 | Intentional design boundary | Phase 6 cannot distinguish e.g. `length`-truncated vs. other stop reasons from Phase 5 evidence alone | Would require modifying frozen Phase 3 `generate_with_retries()` — not attempted without separate authorization |
| Taint evidence cites one shortest grounded path, not all paths | Phase 5.7 / Attribution | Optional (not a defect) | A memory with multiple real derivation paths to the same attack origin has only one path cited | Not currently needed; revisit only if a real research question requires exhaustive path enumeration |
| `build_propagation_graph()` / relationship-derivation functions scan the whole ledger per call | Phase 5.8 | Optional optimization | Fine at current campaign scale; would need indexing before a very large multi-run shared ledger | Add membership-ledger-side per-run pre-filtering if/when scale requires it |
| No independently-labeled attribution ground truth beyond controlled validation scenarios | Attribution | Research limitation | Attribution metrics (accuracy, precision/recall, false-attribution rate) can only be computed where a caller supplies real, known ground truth — never a general benchmark-wide accuracy claim | Would require a separately-designed, independently-labeled evaluation set — not attempted |
| No exhaustive attack coverage / no statistically powered success rate | Phase 4 | Research limitation | Every real result remains n=1/n=2 per condition across all of Phase 4's evidence, which Phase 5/Attribution instrument but do not multiply | Any Phase 6 statistical claim needs new, additional real campaigns, not a reinterpretation of existing logs |
| No defense/mitigation evaluation exists | Phase 4 (by charter) | Intentional design boundary | Phase 6 has a complete attack + instrumentation + attribution substrate but zero existing defense baseline to compare against | If Phase 6 pursues defense evaluation, it starts from zero, not from a partial existing attempt |
| No post-admission `ATTACK_FAILURE` observed | Phase 4 | Research limitation | The one real `ATTACK_FAILURE` in this project's evidence is pre-admission; whether V3-Hybrid can ever resist an admitted, selected poison is untested | Would require new real campaigns specifically designed to probe this, not existing-log reanalysis |
| REFERENCES excluded from behavioral-reference inference | Phase 5.7 (by design) | Intentional design boundary, not a defect | Phase 6 cannot use `REFERENCES` (or Attribution's `references` type) to claim a model behaviorally cited a memory in its answer — only that one memory's content structurally contains another's citation substring | Would require a new, separately-justified, calibrated mechanism — explicitly rejected twice already (Post-Phase-5 hardening pass and this reopening); do not silently reintroduce |

No new limitation was invented for this table; every row traces to a real, previously
disclosed item in the cited origin document.

---

## Phase 6 Starting State

```
FROZEN:
- Phase 3 baseline (V3-Hybrid, canonical memory/event infrastructure)
- Phase 4 attack suite (seven attacks, Common Attack Contract Rev. 3)
- Phase 5 instrumentation (Stages 5.1-5.9, including 5.8A)
- Phase 5 evidence schema (Phase5Event, relationship vocabulary, evidence-kind vocabulary)
- Attribution analytical layer (six attribution types, schema, metrics)

AVAILABLE EVIDENCE:
- canonical memory ledger (CanonicalMemoryLedger)
- canonical event ledger (CanonicalEventLedger)
- Phase 5 events (Phase5EventLedger)
- run/episode identity (ExperimentRunLedger, EventRunMembershipLedger)
- retrieval/selection evidence (per-candidate scores, canonical_status, rendered context)
- agent decision/action evidence (exposure, finish_reason, config fingerprint)
- lineage/provenance (9-type MemoryInteractionEdge vocabulary, evidence-kind labeled)
- traces (ExperimentTrace, per-run and per-task)
- propagation graph (PropagationGraph, run-scoped, all 9 relationship types)
- Memory Behavior Dataset (6-category flattened analytical dataset)
- attribution results (AttributionResult, 6 question types, metrics)

KNOWN LIMITATIONS:
- see the consolidated table above; none hidden, none invented for this handoff

DO NOT MODIFY:
- phase3/evaluation/ (CanonicalMemoryLedger, CanonicalEventLedger, CanonicalEvent,
  ProvenanceGraph, memory versioning semantics, taint propagation semantics, V3-Hybrid)
- phase4/ attack implementations and their frozen contracts/campaign evidence
- phase5/ instrumentation semantics (Phase5Event schema, identifiers, lifecycle,
  retrieval/selection, agent decision/action semantics, Stage 5.7 relationship
  vocabulary, Stage 5.8 trace/graph semantics, Stage 5.8A dataset semantics) without an
  explicit, narrowly-scoped, documented, regression-tested reopening — the exact
  precedent set by the 2026-09-13 REFERENCES reopening/reconciliation
- attribution/ (read-only consumer; do not fold into Phase 5 or modify without a real,
  discovered defect)

PHASE 6 CAN NOW:
- build on a real, frozen attack + instrumentation + attribution substrate without
  re-deriving lineage, exposure, or influence evidence from raw logs
- query any run's complete lifecycle (injection through propagation) via
  ExperimentTrace/PropagationGraph/Memory Behavior Dataset without re-running experiments
- ask any of the six attribution questions about a real, historical memory or decision
  without building new evidence-extraction machinery
- extend the evidence substrate additively (new event types, new derivation functions,
  new attribution types) following the exact review/reopen/refreeze discipline this
  project has now demonstrated twice (Stage 5.7's REFERENCES gap, Stage 5.8's matching
  reconciliation)
```

This handoff does not decide what Phase 6 studies (a defense evaluation, a broader attack
survey, a statistically powered follow-up, or something else) — that remains an open
choice for the user, informed by the limitations table above and `PHASE5_HANDOFF_REPORT.md`
§5/§7's own carried-forward open questions (still valid — Phase 5/Attribution instrumented
and analyzed the same seven attacks, without answering those questions).
