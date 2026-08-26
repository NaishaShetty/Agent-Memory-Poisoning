# Phase 3.2-A — Existing Evaluation Infrastructure Audit

Status: **AUDIT ONLY**. This document contains no implementation, no new evaluators, no new
schemas, and no new runners. It is a survey of what already exists, graded for scientific
trustworthiness, against the frozen Phase 3.1 contracts in `phase3/specification/`,
`phase3/schemas/`, and `phase3/contracts/`. See section 14 for the explicit no-implementation
statement.

---

## 1. Executive summary

Phase 3.1 defines a two-layer evaluation contract (memory success vs. agent success), a
strict-TSR-as-diagnostic-only rule, a new evidence-equivalent success metric, a full
memory-level metric set (Recall@{1,5,10,20,50,100,200}, MRR, evidence precision/recall/
coverage, failure-mode counters, provenance/lineage/lifecycle metrics), an A/B/C agent-level
control methodology, an absolute leakage/visibility boundary, and a determinism/traceability
recording requirement. **None of this exists as live, active code anywhere in the repository
today.** `phase3/` (the only active Phase 3 surface) contains specification/schema/contract
documents only — no implementation. All Phase 3 evaluation code that has ever been written
lives in `phase3_reference/`, which is explicitly historical-only per
`phase3/specification/PHASE3_RESTART_BOUNDARY.md`.

The good news: `phase3_reference/` is not a blank slate. It contains a substantial, partially
tested body of work that is directly relevant precedent — a lifecycle state machine and
provenance-graph validator that are close to reusable as-is, a Recall@k/MRR/evidence-precision-
recall implementation, a three-way candidate-generation/selection-capacity/identity-artifact
failure taxonomy that reproduces the exact ~72.4%/14.8%/12.8% split the new spec cites, a paired
counterfactual causal-replay method, and a four-condition (collapsible to the new three-
condition A/B/C) agent-level evaluation harness with real answer grading and a five-way failure
attribution taxonomy. None of it is validated to the standard the new contracts require, none of
it has adequate test coverage for the metric-computation code specifically, and several
mechanisms it encodes are explicitly rejected by the new governance/schema documents (score-gap
selection, foundation-preference/lineage-family selection, semantic-only retrieval, blanket and
relation-aware temporal retrieval, selective memory creation). Nothing outside
`phase3_reference/` and `phase3/` is evaluation-relevant except pure Phase 1/2 dataset/schema/
quality/reproducibility code, which is frozen and out of scope.

The central finding for Phase 3.2 planning: **Phase 3.2 must design and implement a new,
tested evaluation layer from scratch**, informed by — but not built by importing — the
historical code. The historical code is best treated as a design precedent and citation source,
with a handful of specific modules (the lifecycle state machine, the provenance graph validator,
the Recall@k/MRR module, the failure-taxonomy classifier, the extended-rank rescan methodology)
worth re-deriving with adaptation rather than reinventing from zero.

---

## 2. Repository evaluation inventory

Scope of this inventory: every file or module anywhere in the repository whose purpose touches
evaluation, metrics, scoring, provenance/lifecycle validation, leakage, or determinism/
reproducibility recording for the memory/agent layer (Phase 3 concerns). Pure Phase 1/2 dataset
ingestion/schema/quality code is listed only to confirm it is out of scope, not inventoried in
depth.

| Area | Location | In scope? |
|---|---|---|
| Phase 3.1 specification/schema/contract docs | `phase3/specification/`, `phase3/schemas/`, `phase3/contracts/` | Yes — the audit target |
| Historical Clean Agent V1 | `phase3_reference/clean_agent_v1/src/`, `/tests/` | Yes — historical precedent |
| Historical V2/V2b/V2c candidate-selection thread | `phase3_reference/v2c/src/`, `/tests/`, `/results/` | Yes — historical precedent |
| Historical diagnostics | `phase3_reference/diagnostics/derived_memory/`, `/retrieval/` | Yes — historical precedent |
| Historical experiments A–I, idf_retrieval | `phase3_reference/experiments/*` | Yes — historical precedent, several rejected mechanisms |
| Historical Qwen reasoning-layer pilot | `phase3_reference/qwen_experiments/reasoning_layer_v1/` | Yes — closest precedent to new A/B/C contract |
| Historical ad-hoc scripts | `phase3_reference/scripts/` | Yes — throwaway, no reusable logic |
| Historical spec docs | `phase3_reference/specifications/*.md` | Yes — citation source, not methodology |
| Phase 1/2 dataset loaders | `preprocessing/datasets/{locomo,longmemeval,msc,conversation_chronicles}.py` | Frozen substrate — read-only; produces task/evidence records consumed by evaluation but is not itself evaluation code |
| Phase 1/2 schema/quality/reproducibility | `preprocessing/unified_schema.py`, `schema.py`, `quality.py`, `reproducibility*.py`, `temporal.py` | Frozen — out of scope, structurally informative only for the new reproducibility contract |
| Phase 1/2 tests | `tests/*` (root) | Frozen — zero TSR/recall/MRR/lifecycle-as-agent-state content; pure dataset/schema validation |
| Phase 1/2 docs | `docs/phase2/*` | Frozen — dataset-to-UMR provenance only, not agent-memory provenance |
| Phase 1/2 reports/metadata | `data/reports/*`, `data/metadata/*` | Frozen — dataset-quality/manifest content only; confirmed to hold no gold-answer/eval-label content today |
| `tests/fixtures/{locomo,longmemeval}/` | root | Confirmed **empty** — no gold-evidence fixtures exist at these paths despite being named in the task brief |
| `tests/fixtures/msc/` | root | Contains conversation-content fixtures only (msc has no task/evidence layer) |

No evaluation-relevant code was found anywhere outside `phase3_reference/` and `phase3/`.
`preprocessing/` at repo root currently contains **only** Phase 1/2 dataset/schema code — no
`substrate.py`, `reference_agent.py`, `lifecycle.py`, or any TSR/recall/MRR code lives there
today; all such code exists only inside the archived `phase3_reference/clean_agent_v1/src/` and
`phase3_reference/v2c/src/` trees.

---

## 3. Existing metric inventory

| Metric / mechanism | Implementation | Location | Formula / logic (as read) |
|---|---|---|---|
| Strict TSR | Yes | `phase3_reference/clean_agent_v1/src/reference_agent.py` | `set(used_memory_ids) & set(evidence_memory_ids)` non-empty ⇒ success; empty evidence ⇒ `NO_EVIDENCE_STRUCTURE` outcome (not scored as failure) |
| Recall@k (k ∈ {1,5,10,20,50}) | Yes | `phase3_reference/v2c/src/run_diagnostic_cycle2_retrieval_metrics.py` | First-hit-rank of any gold evidence ID in the retrieved-order list; `recall_at[k] += 1` if `first_hit_rank <= k`, divided by evaluable-task count |
| MRR | Yes | same file | `rr_sum += 1.0/first_hit_rank if first_hit_rank else 0.0`, averaged over evaluable tasks |
| Evidence precision / recall | Yes | same file, `evidence_metrics()` | `|used ∩ evidence| / |used|` (precision), `|used ∩ evidence| / |evidence|` (recall), both averaged |
| Selected-memory count | Yes | same file | mean of `len(used_memory_ids)` |
| Evidence coverage | Not found | — | No historical implementation located anywhere |
| Redundancy | Not found | — | No historical implementation located anywhere |
| Candidate-generation-failure vs selection-capacity-failure vs identity-artifact counters | Yes | `phase3_reference/v2c/src/diagnostic_v2_root_cause.py`, `run_diagnostic_v2_root_cause.py` | Three-way per-task classification (see section 4) |
| Creation/rejection/duplicate/equivalence/reuse rates | Partial | `clean_agent_v1/src/clean_baseline.py`, `agent_memory_interface.py` | Creation and reuse are recorded via events; no duplicate-detection or semantic-equivalence rate is computed anywhere (Experiment I documents that v1's `create_memory` always byte-copies content, making any literal-content novelty/duplicate check vacuous) |
| Foundation-vs-derived usage rate, derivation depth | Yes | `clean_agent_v1/src/clean_baseline.py` (`foundation_proportion`, `agent_derived_proportion`, `_lineage_depth()`), `v2c/src/diagnostic_v2_root_cause.py` (`derivation_depth()`) | Recursive/memoized parent-edge walk, consistent with the new spec's "explicit edges only, no giant families" rule |
| Provenance completeness, lineage correctness | Yes | `clean_agent_v1/src/lifecycle_graph.py` (`ProvenanceGraphBuilder.validate_graph()`) | Named PASS/FAIL checks: memory-node validity, task-node validity, no dangling edges, behavioral-edge evidence resolves to real events, lifecycle-annotation agreement, UMR-provenance agreement, approved-dataset-only, no dangling identifier refs |
| Lifecycle validity, orphan rate, invalid-transition rate | Yes | `clean_agent_v1/src/lifecycle.py` (`VALID_MEMORY_TRANSITIONS`, `build_histories()`, `validate_trace()`) | Explicit state machine (`AVAILABLE→RETRIEVED→USED`); errors recorded as `invalid_state_transition`, `missing_prerequisite_event`, `broken_parent_reference`, `unknown_memory_reference`, `duplicate_memory_creation` — never silently repaired |
| Answer correctness (exact match / F1) | Yes | `phase3_reference/qwen_experiments/reasoning_layer_v1/src/grading.py` | `exact_match` (normalized string equality), `token_f1` (SQuAD-style, threshold 0.5 for `graded_correct`), `is_abstention` (fixed-phrase match), `unsupported_claim_heuristic` (lexical-overlap hallucination proxy, explicitly documented as unproven) |
| Agent-level A/B/C(/D) conditions | Yes, as four conditions | `qwen_experiments/reasoning_layer_v1/src/conditions.py` | `A_gold_evidence_oracle`, `B_current_clean_memory`, `C_no_memory_baseline`, `D_retrieval_candidate_context` (uncurated top-N, cap 20) — maps to new-spec A/B/C with the roles of A and C swapped in name only, plus one extra condition (D) with no new-spec equivalent |
| Memory contribution / gold memory contribution deltas | Not found | — | No historical code computes `accuracy(C)-accuracy(A)` style deltas directly, though `aggregate_report.py` computes all the per-condition accuracies needed to derive them |
| Paired counterfactual causal replay | Yes | `phase3_reference/diagnostics/derived_memory/src/diagnostic_v2_derived_memory_causal.py` | Strips derived memories from an already-recorded candidate list (fixed order, no re-scoring), replays selection, computes `paired_causal_effect_pct_points` |
| Extended-rank rescan (enables Recall@100/200) | Yes | `phase3_reference/diagnostics/retrieval/experiment_retrieval_diagnostic_rescan.py` | Re-runs frozen `retrieve()` at `top_k=50` (max historical depth anywhere) to record rank/score of first evidence hit |
| Leakage detection/audit tooling | Not found | — | No leakage-detection code exists anywhere in the repository, historical or active |
| Determinism/reproducibility recording (agent/memory layer) | Partial | `qwen_experiments/reasoning_layer_v1/scripts/determinism_study.py` | Measured only on Condition B, on a fixed stratified sample, not a full sweep — explicit scoping limitation, not a general-purpose reproducibility harness |
| Trace validation | Yes (structural) | `clean_agent_v1/src/lifecycle_graph.py`, `lifecycle.py` | Validates event-derived graph/lifecycle structure; does not implement the full task-execution trace chain (candidate set → reranking → selection → reasoning context → response → evaluation) required by `TRACEABILITY_CONTRACT.md` |

---

## 4. TSR audit

**How TSR is currently calculated.** In `phase3_reference/clean_agent_v1/src/reference_agent.py`,
TSR is computed as a literal set-intersection between the memories the agent's deterministic
top-N usage strategy marked `used` and the task's benchmark-designated `evidence_memory_ids`:

```
if resolved_evidence:
    task_outcome = SUCCESS if set(used_ids) & set(resolved_evidence) else FAILURE
else:
    task_outcome = NO_EVIDENCE_STRUCTURE
```

This is exactly the definition the new `EVALUATION_CONTRACT.md` calls "strict TSR" — literal
gold-evidence-ID membership. It consumes only `used_memory_ids` (post-selection) and
`evidence_memory_ids` (benchmark gold), nothing else; no answer text, no reasoning-layer output
is involved anywhere in the historical v1/v2c pipeline — there is no reasoning layer in that
code at all (see section 9). It is fully literal-ID-based: an agent that selects a derived
memory that is a verbatim content copy of the gold evidence, or a memory the new spec would call
`equivalent_to` the gold evidence, still scores as a TSR failure, because only the exact
`memory_id` is checked.

**Does it match the new spec's strict-TSR definition?** Yes, exactly — the historical
implementation *is* the definition the new spec formalized and reclassified. The new contract's
contribution is not a different formula; it is the classification change: strict TSR is
retained verbatim as one diagnostic/comparability metric, but is explicitly forbidden from being
treated as "the" measure of agent success, and must always be reported alongside a new
evidence-equivalent success metric and the full agent-level A/B/C accuracy comparison.

**Reusability.** The historical TSR calculation itself (`set(used) & set(evidence)`) is trivial,
correct, and directly reusable verbatim (classification: B — reuse with adapter, only because it
needs to be wired into the new two-metric reporting requirement rather than reported alone). The
real work is elsewhere: (a) an evidence-equivalent success metric must be built new — no
historical code computes semantic/evidential equivalence between a selected memory and gold
evidence at the memory-ID level (the closest analog, `qwen_experiments/.../grading.py`'s
`token_f1`, operates on answer text, not evidence identity, and is a different layer entirely);
(b) the historical corpus already independently discovered and documented the strict-TSR
insufficiency problem — `phase3_reference/specifications/PHASE3_6_V2_ROOT_CAUSE_INVESTIGATION.md`
states verbatim that "the honest description of 'TSR' here is 'evidence-retrieval-and-selection
hit rate,' not 'task success rate,'" and that "100% of the current TSR gap is upstream of any
hypothetical reasoning [layer]" — this is a direct historical ancestor of, and justification for,
the new spec's two-layer evaluation requirement, and is worth citing directly in any Phase 3.2
design rationale rather than re-deriving.

**Known historical TSR figures** (from `phase3_reference/v2c/results/phase3_6_v2_candidate_diagnostic/aggregate_findings.json`,
verified by the research pass): LoCoMo TSR 29.79%, LongMemEval TSR 34.40%, with failure
decomposition LoCoMo 70.24% candidate-generation / 15.71% selection / 14.05% identity-artifact,
LongMemEval 76.98% / 12.80% / 10.21%. The new spec's cited "~72.4%/14.8%/12.8%" is a
pooled/rounded blend of exactly these two rows — the historical finding the new spec's section 3
cites is directly traceable to this file and is reproducible from
`phase3_reference/v2c/src/run_diagnostic_v2_root_cause.py` + `run_diagnostic_v2_aggregate.py`.
This confirms the historical number is not fabricated or approximate folklore — it has a
concrete, inspectable source — but it is still a **historical, unvalidated-by-new-standards**
number: it was produced against the old (pre-3.1) memory schema, the old lifecycle model, and a
naive top-N usage strategy that the new spec's own architecture (candidate discovery / reranking
/ selection as separated layers) does not yet have an implementation of. It should not be
imported as a current baseline number without re-running under the new architecture.

---

## 5. Gold/leakage audit

**No leakage-detection or leakage-audit tooling exists anywhere in the repository, historical or
active.** The new `LEAKAGE_AND_VISIBILITY_CONTRACT.md` requires a standing audit that
`data/metadata/` and `data/reports/` never enter reasoning-context assembly, re-verified whenever
context-assembly code changes — no such audit, static or runtime, was found.

**Agent-visible vs. evaluator-only data, per component:**

- `preprocessing/datasets/{locomo,longmemeval}.py` produce `TaskRecord`s that bundle
  `question`, `answer` (gold), `evidence_memory_ids` (gold) together in one record. This is
  correct and expected at the dataset-ingestion layer (Phase 1/2, frozen) — the gold fields must
  exist somewhere to build the benchmark at all. The leakage risk is entirely downstream, in
  whatever component reads a `TaskRecord` and assembles the reasoning-layer prompt.
- `phase3_reference/clean_agent_v1/src/reference_agent.py`'s `TaskRunner.run_task` reads
  `evidence_memory_ids` directly to compute `MEMORY_USED`/TSR — this is **evaluator-side** use
  and is explicitly documented in the module's own docstring as "NOT how the agent decides
  usage." The risk is only realized if this evaluator-side code path and the agent's actual
  decision path are not kept structurally separate. `clean_agent_v1/tests/` does contain source-
  inspection tests asserting the agent "never touches raw store/logger" directly (`assert
  "open(" not in src`), which is a positive signal that the historical authors were alert to this
  class of risk, but there is no test asserting the *agent's* code path never reads
  `evidence_memory_ids` or `answer` fields — the tests check I/O-boundary discipline, not
  gold-field discipline specifically.
- `phase3_reference/qwen_experiments/reasoning_layer_v1/src/conditions.py`'s `CONDITION_A =
  "A_gold_evidence_oracle"` **deliberately and explicitly** feeds `evidence_memory_ids` content
  to the reasoning layer — this is correct and intentional (it is the historical analog of the
  new spec's Condition B, gold-evidence control) but it means this is exactly the kind of
  component that must be clearly walled off, by construction, from the "real" retrieved-memory
  condition in Phase 3.2's implementation, since the new leakage contract's rules apply to
  Condition C (retrieved-memory) but Condition B is defined precisely to violate them on purpose
  for comparison. **This is not a flaw** — the new evaluation contract itself defines Condition B
  this way — but it is a concrete place where a future implementation could accidentally leak if
  the code for assembling Condition B and Condition C context shares a code path without an
  explicit switch.
- No component anywhere in the historical corpus was found injecting internal retrieval
  scores/ranks into a reasoning-layer prompt, because no historical component has a working
  reasoning-layer integration wired to the memory/selection pipeline at all — the
  `qwen_experiments` pilot's conditions are constructed directly from stored task records, not
  from a live retrieval-selection pipeline output (see section 9). This means the specific
  leakage risk named in the new contract ("selection scores/ranks... serialized into the
  reasoning context") has never actually been exercised by any historical code — it is an
  entirely open, untested risk surface for whatever Phase 3.2/3.3 builds next.
- `data/metadata/` and `data/reports/` at repo root (top-level, Phase 1/2 scope) were confirmed
  by direct inspection to contain only dataset-quality/manifest/registry content
  (`phase2_freeze_manifest.json`, `dataset_manifest.json`, `phase1_validation_report.json`, etc.)
  — no gold-answer or per-task evidence-label content lives there today. All per-task gold-bearing
  artifacts (`task_results.jsonl` files carrying `evidence_memory_ids`) live under
  `phase3_reference/*/reports/` and `/results/`, which is itself excluded from the active design
  surface. **This is a currently-clean state, not a validated-safe architecture** — the risk is
  prospective: whatever Phase 3.2 builds must ensure any new `data/reports/`- or
  `data/metadata/`-adjacent output path it creates continues to keep gold content out, since nothing
  currently enforces this beyond the frozen boundary document's naming convention.

**Flagged mixing risk.** The single clearest historical instance of agent-visible and
evaluator-only planes touching the same code path is `reference_agent.py`'s `TaskRunner`, which
computes both the "real" agent trajectory and the TSR judgment inside one function, reading
`evidence_memory_ids` in the same call that produces `used_memory_ids`. The docstring's own
disclaimer that this is diagnostic, not agent behavior, is the right instinct, but a Phase 3.2
implementation should physically separate "run the agent" from "score the agent" into different
modules/processes so this can never be conflated by construction, rather than relying on a
comment.

---

## 6. Dataset evaluation support

| Dataset | Loader | Evidence/gold representation | Existing metrics exercised against it | Provenance/lifecycle support | Known Phase 3.1-contract incompatibilities |
|---|---|---|---|---|---|
| LoCoMo | `preprocessing/datasets/locomo.py` | `evidence_memory_ids` resolved from native `dia_id` references via a `dia_id_to_memory_id` map; unresolvable refs silently dropped and counted (`qa_instances_missing_evidence`), never fabricated. Loader comment: "QA answers/evidence are dataset-annotated (LLM/human), not verified ground truth." | Full historical suite: strict TSR (29.79%), Recall@{1,5,10,20,50}, MRR, evidence precision/recall, all nine experiments A–I use it or LongMemEval | Exercised across `clean_agent_v1` and `v2c` lifecycle/provenance-graph code | New spec requires Recall@{100,200} — historical max depth is 50 everywhere (the rescan tool caps at 50 too); no historical component computes evidence-equivalent success; `tests/fixtures/locomo/` confirmed empty (no committed gold-evidence fixture) |
| LongMemEval | `preprocessing/datasets/longmemeval.py` | `evidence_memory_ids` resolved from `answer_session_ids` → `session_id_to_memory_ids` (one session may map to multiple UMR records since a session is chunked) | Same suite as LoCoMo; also the dataset for the largest single historical improvement lever (IDF retrieval, TSR 4.9%→40.4% at depth 50) | Same as LoCoMo | Same Recall@{100,200} gap; `tests/fixtures/longmemeval/` confirmed empty |
| MSC | `preprocessing/datasets/msc.py` | **No** evidence/question/answer/task_id handling at all — confirmed zero task-record production | Consistent with new spec: MSC is "not forced into strict-TSR/task-QA framework." `qwen_experiments` pilot explicitly records `tsr_or_answer_accuracy_computed: False` for MSC, substituting a "lightweight_compatibility_check" (memory-record readability only) | Memory lifecycle/provenance components (`clean_agent_v1`) were designed against `APPROVED_MEMORY_DATASETS` generically and should apply to MSC's memory records, but were not specifically exercised/reported against MSC in the historical results reviewed | No task/workload layer exists or is planned in 3.1 (explicitly deferred); nothing here contradicts the new spec, since the new spec itself defers this |
| Conversation Chronicles | `preprocessing/datasets/conversation_chronicles.py` | Same as MSC — no evidence/task handling, confirmed zero hits | Same MSC-style exclusion in the historical Qwen pilot | Same as MSC | Same as MSC |

`tests/fixtures/{locomo,longmemeval}/` were directly confirmed empty during the research pass —
this is a gap regardless of Phase 3.2 scope: any new evaluation test suite will need to construct
gold-evidence fixtures itself (inline or newly authored), since no committed fixture currently
exists for either dataset at that path.

---

## 7. Historical dependency audit

| Component | Depends on | Classification |
|---|---|---|
| `clean_agent_v1/src/substrate.py` (MemoryStore, lexical retrieve) | Old (pre-3.1) memory record loading straight from Phase 2 UMR JSONL; no old lineage-family abstraction | REQUIRES ADAPTER — interface shape (deterministic, source-inspectable, tokenizer-based scoring) is sound, but must be re-derived against the new `memory_schema.json` fields (`memory_type`, `parent_ids`, `lifecycle_state`, etc.) which did not exist in this old form |
| `clean_agent_v1/src/reference_agent.py` (strict TSR, DeterministicTopNUsageStrategy) | Old flat "used_memory_ids" concept, no candidate-discovery/reranking/selection layer separation | REQUIRES ADAPTER for TSR definition (formula is fine, framing needs updating); REIMPLEMENT for selection (the new spec requires three separated layers — candidate discovery, reranking, evidence selection — the old code collapses all three into one top-N cut) |
| `clean_agent_v1/src/lifecycle.py` (state machine) | Old three-state model (`AVAILABLE→RETRIEVED→USED`) | REQUIRES ADAPTER — the new spec's canonical states are `CREATED→ACTIVE→RETIRED` with reuse as an event, not a state; conceptually compatible (both treat reuse/retrieval as loggable events) but the state names and exact transition table must be re-derived against `relationship_schema.md` section 3, not copied verbatim |
| `clean_agent_v1/src/lifecycle_graph.py` (ProvenanceGraphBuilder) | Old event schema, old lifecycle states above | REQUIRES ADAPTER — the validation-check *methodology* (named PASS/FAIL structural checks against real events) is directly reusable and does not depend on any rejected old abstraction; the specific state/edge vocabulary needs updating to the new schema |
| `v2c/src/run_diagnostic_cycle2_retrieval_metrics.py` (Recall@k, MRR, evidence precision/recall) | Old `retrieved_memory_ids`/`used_memory_ids`/`evidence_memory_ids` flat record format; no old lineage-family dependency | SAFE TO REUSE (with the k-list extended to include 100 and 200) — this module has no dependency on any of the explicitly-rejected old mechanisms |
| `v2c/src/diagnostic_v2_root_cause.py`, `run_diagnostic_v2_root_cause.py` (3-way failure taxonomy) | `instrumented_selection()`, which is a replay of Experiment H's `provenance_lineage_aware_selection` — an explicitly-rejected mechanism | REQUIRES ADAPTER — the **taxonomy** (candidate-generation-failure / selection-failure / identity-artifact) is sound and dataset-format-only; the specific selection replay it currently instruments is the rejected lineage-family-preference selection and must be swapped for whatever selection mechanism Phase 3.2/3.3 actually adopts |
| `diagnostics/derived_memory/src/diagnostic_v2_derived_memory_causal.py` (paired counterfactual) | Same instrumented-selection dependency as above | REQUIRES ADAPTER — causal-replay method itself is mechanism-agnostic and safe; the specific selection function it replays needs swapping |
| `diagnostics/retrieval/experiment_retrieval_diagnostic_rescan.py` (extended-rank rescan) | Old `retrieve()` from `substrate.py` (lexical only, top_k=50) | REQUIRES ADAPTER — rescan methodology is sound; needs the new retrieval implementation and needs its depth extended past 50 to actually support Recall@100/200 |
| Experiments C, E, F, H, I (temporal-blanket, semantic-only, relation-aware-temporal, lineage-family selection, selective creation) | Each encodes one of the explicitly-named-rejected mechanisms in `EXPERIMENT_GOVERNANCE.md` section 5 | HISTORICAL ONLY — must not be re-adopted without a new governed experiment explicitly referencing the prior negative/rejected result, per governance section 5 |
| Experiments A/idf_retrieval, B, G, D | Old flat record format only; not on the rejected list, though D (score-gap selection) is separately named rejected by scope decision, not by negative result | A/idf_retrieval and B: REQUIRES ADAPTER (good building blocks). D: HISTORICAL ONLY per governance despite outperforming empirically — flagged as unresolved tension, not silently dropped. G (RRF fusion): REIMPLEMENT if fusion is wanted, no dependency issues |
| `qwen_experiments/reasoning_layer_v1/src/conditions.py`, `grading.py`, `failure_attribution.py`, `aggregate_report.py` | Old V2c `used_memory_ids` as the source of "Condition B" context; no rejected-mechanism dependency in the grading/taxonomy/reporting logic itself | REQUIRES ADAPTER — remap four conditions (A/B/C/D) to the new three (A/B/C), and re-source "current retrieved-memory context" from whatever Phase 3.2/3.3 pipeline replaces V2c, not from the old candidate-selection thread |
| `phase3_reference/scripts/*.py` | Ad-hoc one-off print/debug scripts against specific old result files | HISTORICAL ONLY — no reusable logic |
| `phase3_reference/specifications/*.md` | Narrate the old (rejected) architecture and old TSR framing throughout | HISTORICAL ONLY — valuable as citations for design rationale, not as current methodology |

---

## 8. Reuse/adaptation/reimplementation matrix

Full per-component detail with all fourteen inventory-entry fields (Component, Path, Type,
Current purpose, Phase origin, Used by, Inputs, Outputs, Dataset dependencies, Memory-schema
dependencies, Gold/evaluation dependencies, Deterministic?, Reusable?, Why/why not,
Historical-only?, Recommendation) was compiled for every component named in sections 2–7 above;
the condensed classification is presented here to keep this document navigable. Where a
component appears in more than one classification (e.g. "sound taxonomy, rejected mechanism it
currently instruments"), both are listed.

**A. REUSE**
- `clean_agent_v1/src/lifecycle_graph.py` — `ProvenanceGraphBuilder.validate_graph()` structural-check methodology.
- `clean_agent_v1/src/lifecycle.py` — state-machine validation pattern (`build_histories`, `validate_trace`).
- `clean_agent_v1/src/substrate.py` — `EventLogger`/`EVENT_TYPES` append-only event schema.
- `diagnostics/retrieval/experiment_retrieval_diagnostic_rescan.py` — extended-rank rescan methodology.
- `v2c/src/run_diagnostic_v2_aggregate.py` — aggregate failure/ceiling/provenance/creation-effect report structure.

**B. REUSE WITH ADAPTER**
- `v2c/src/run_diagnostic_cycle2_retrieval_metrics.py` — Recall@k/MRR/evidence precision-recall (extend k-list to {1,5,10,20,50,100,200}).
- `clean_agent_v1/src/reference_agent.py` — strict TSR formula (retain; re-wire into two-metric reporting requirement).
- `clean_agent_v1/src/agent_memory_interface.py` — `AgentMemoryInterface`/`MemoryProvenance` seam and field shape.
- `v2c/src/diagnostic_v2_root_cause.py` + `run_diagnostic_v2_root_cause.py` — candidate-generation/selection/identity-artifact 3-way taxonomy.
- `diagnostics/derived_memory/src/diagnostic_v2_derived_memory_causal.py` — paired counterfactual causal-replay method.
- `experiments/idf_retrieval/`, `experiments/experiment_a` — IDF scoring building block.
- `qwen_experiments/reasoning_layer_v1/src/conditions.py`, `grading.py`, `failure_attribution.py`, `aggregate_report.py` — condition remapping, answer grading, failure taxonomy, report template.
- `clean_agent_v1/src/clean_baseline.py` — aggregate statistical-reporting template.

**C. REIMPLEMENT**
- `clean_agent_v1/src/substrate.py`'s `retrieve()` (lexical-only, no layer separation) — must become three separated layers per `CLEAN_AGENT_INTERFACES.md`.
- `clean_agent_v1/src/reference_agent.py`'s `DeterministicTopNUsageStrategy` — too naive a selection mechanism for the new layer separation.
- `experiments/experiment_b` (stemmer) and `experiments/experiment_g` (RRF fusion) — reasonable building blocks, not dependent on rejected mechanisms, but not currently packaged as reusable library code.

**D. HISTORICAL REFERENCE ONLY**
- All of `phase3_reference/specifications/*.md`.
- `experiments/experiment_i`'s duplicate-detection finding (naive content-identity checks are vacuous).
- `diagnostics/derived_memory/reports/*.json` (superseded by the V2 root-cause investigation numbers).
- Historical numeric results generally (TSR 29.79%/34.40%, Recall@k figures) — valid as citations, not as current baselines.

**E. PHASE 1/2 FROZEN — DO NOT TOUCH**
- `preprocessing/datasets/*.py`, `unified_schema.py`, `schema.py`, `quality.py`, `temporal.py`, `reproducibility*.py`.
- `docs/phase2/*`.
- `data/metadata/*`, `data/reports/phase1_*`, `data/reports/phase2_*`.
- All of `tests/` (root) — pure Phase 1/2 dataset/schema validation, zero Phase 3 metric content.

**F. REMOVE FROM ACTIVE DESIGN ONLY (do not delete from `phase3_reference/`)**
- `experiments/experiment_c` (blanket temporal proximity).
- `experiments/experiment_e` (semantic-only retrieval).
- `experiments/experiment_f` (relation-aware temporal retrieval).
- `experiments/experiment_h`'s selection mechanism specifically (lineage-family/foundation-preference selection) — its diagnostic replay tooling is separately classified B.
- `experiments/experiment_i`'s selective-creation mechanism specifically — its duplicate-detection finding is separately classified D.
- `experiments/experiment_d`'s score-gap selection — rejected by governance/scope decision, not by negative result; flagged in section 4/9 as an unresolved empirical tension worth a human decision, not silently dropped.
- `phase3_reference/scripts/*.py` — throwaway debug scripts.
- `clean_agent_v1/src/reference_agent.py`'s `TaskRunner.run_task` as an agent-behavior model (its evaluator-side TSR computation is reusable per B above, but its conflation of agent-run and scoring in one function should not be carried into active design).

---

## 9. Scientific trust assessment

Trust ratings below reflect **existing code's readiness to be trusted as validated
infrastructure**, not code quality in isolation. "Existing" is never treated as equivalent to
"validated."

| Component | Trust | Justification |
|---|---|---|
| Lifecycle state machine + validation (`lifecycle.py`) | **MEDIUM** | Explicit, well-specified transition table; `clean_agent_v1/tests/` include dedicated invalid-transition tests. Medium rather than high because it targets an old three-state model that must be re-derived against the new `CREATED→ACTIVE→RETIRED` model — passing tests validate the old model, not the new one. |
| Provenance graph builder/validator (`lifecycle_graph.py`) | **MEDIUM** | Strong structural-check design (explicit named PASS/FAIL checks, cross-validated against real events), with dedicated tests (`test_operations_produce_reconstructable_graph_relationships`). Capped at MEDIUM, not HIGH, because it was only ever exercised against the old event/lifecycle vocabulary and the old lineage model, and has not been re-validated against the new pairwise-edge-only, no-giant-family relationship schema it must now conform to. |
| Recall@k / MRR / evidence precision-recall (`run_diagnostic_cycle2_retrieval_metrics.py`) | **MEDIUM** | Formula is straightforward and matches standard IR definitions; correctly avoids leakage by computing post-hoc from logged IDs rather than at decision time. Capped at MEDIUM because this module has **zero dedicated unit tests** anywhere in the corpus (confirmed: `v2c/tests/` contains only `test_v2_harness_isolation.py`) — it was run once as an analysis script against frozen artifacts, never built or verified as tested library code. |
| Strict TSR calculation | **HIGH** for the formula itself, **LOW** as a stand-alone success claim | The set-intersection formula is trivially correct and exercised across the entire historical corpus (hundreds of task-level computations, cross-checked via multiple independent aggregation scripts landing on consistent figures). But the new contract is explicit that strict TSR must never be reported alone — using it as "the" success metric, which historical documents show it effectively was treated as, is precisely the failure mode the new contract exists to prevent. |
| Candidate-generation/selection/identity-artifact taxonomy | **MEDIUM** | Internally consistent (LoCoMo and LongMemEval numbers sum to 100% correctly, cross-validated against `aggregate_findings.json`), and the taxonomy design is sound. Capped at MEDIUM: no dedicated unit tests, and it currently instruments a rejected selection mechanism (lineage-family/foundation-preference selection) rather than whatever mechanism Phase 3.2 will actually ship, so the specific *numbers* are not transferable, only the *method*. |
| Paired counterfactual causal replay | **MEDIUM** | Methodologically rigorous (paired design, holds retrieval/ranking fixed, avoids naive correlation), but has the same "instruments a rejected mechanism" and "no dedicated tests" caveats as the taxonomy above. |
| Answer grading (EM/F1/abstention) (`grading.py`) | **LOW-MEDIUM** | Standard, well-understood formulas (SQuAD-style F1), but the module's own documentation flags `unsupported_claim_heuristic` as "not a proven claim" — a self-acknowledged weak heuristic. No external LLM-judge cross-validation was ever performed (documented as an offline limitation). Reasonable as a starting point, not as validated ground truth for "answer correctness." |
| Agent-level four-condition harness (`conditions.py`, `aggregate_report.py`) | **LOW-MEDIUM** | Directionally the right shape (closest historical precedent to the new A/B/C methodology) but was run as a pilot, not a validated production harness; determinism was checked only for one condition on a stratified sample, explicitly scoped down for cost reasons — variance across the other conditions is unmeasured. |
| Historical numeric results generally (TSR%, Recall@k%) | **LOW** as current baselines, **MEDIUM-HIGH** as historical evidence | Internally consistent and traceable to source files (high confidence they are not fabricated), but produced against an architecture (old lifecycle states, old flat selection, rejected selection mechanisms in composition) that the new spec does not preserve — reusing the *numbers* as a current baseline would be a category error; reusing them as *cited historical evidence motivating design decisions* (which the new spec already does) is appropriate. |
| Leakage-detection tooling | **UNTRUSTED — does not exist** | No implementation found anywhere; cannot be assessed for trust because there is nothing to assess. |
| Determinism/reproducibility harness (general-purpose) | **UNTRUSTED — does not exist as general infrastructure** | The one determinism study found is scoped to a single condition and a stratified sample, not a general reproducibility harness meeting the new contract's "record for every run" requirement. |

---

## 10. Phase 3.1 capability gap matrix

| Capability | Status | Evidence |
|---|---|---|
| Recall@{1,5,10,20,50} | PARTIAL | Implemented historically (`v2c/src/run_diagnostic_cycle2_retrieval_metrics.py`), untested, tied to old record format |
| Recall@{100,200} | MISSING | No historical component ever computed depth beyond 50; extended-rank rescan tool itself caps at top_k=50 |
| MRR | PARTIAL | Same module as Recall@k above; same caveats |
| Evidence precision / recall | PARTIAL | Implemented, untested, same module |
| Evidence coverage | MISSING | No implementation found anywhere |
| Selected-/irrelevant-memory counts | PARTIAL | Selected-memory count exists (`clean_baseline.py`, evidence_metrics); irrelevant-memory count not separately computed anywhere |
| Redundancy | MISSING | No implementation found anywhere |
| Candidate-generation vs. selection-capacity failure counters (separate) | HISTORICAL-UNSAFE | Implemented and internally consistent (`v2c/src/diagnostic_v2_root_cause.py`), but instruments an explicitly-rejected selection mechanism (lineage-family/foundation-preference selection) — numbers not transferable, method is |
| Creation/rejection/duplicate/equivalence/reuse rates | PARTIAL | Creation/reuse events recorded; duplicate/equivalence rate computation not found (and Experiment I documents the historical duplicate-check as vacuous by construction) |
| Foundation-vs-derived usage rate, derivation depth | PARTIAL | Implemented (`clean_baseline.py`, `diagnostic_v2_root_cause.py`), tied to old lineage model, no dedicated tests |
| Provenance completeness | PARTIAL | Implemented as a structural validator (`lifecycle_graph.py`), tied to old event/relationship vocabulary |
| Lineage correctness | PARTIAL | Same as above; also depends on re-deriving against the new explicit-pairwise-edges-only rule (no giant families), which the old code was not designed against |
| Lifecycle validity (transitions, orphans) | PARTIAL | Implemented (`lifecycle.py`), tied to an old three-state model, not the new `CREATED→ACTIVE→RETIRED` model |
| No-memory condition (A) | HISTORICAL-UNSAFE | Exists as historical `CONDITION_C` (`conditions.py`); usable in spirit, requires remapping and re-running against a real Phase 3.2 pipeline, not the old V2c thread |
| Gold-evidence condition (B) | HISTORICAL-UNSAFE | Exists as historical `CONDITION_A`; same caveat |
| Retrieved-memory condition (C) | HISTORICAL-UNSAFE | Exists as historical `CONDITION_B`, sourced from the old (rejected-mechanism-composed) V2c selection output — not a valid source for a Phase 3.2 baseline |
| Answer correctness | PARTIAL | EM/F1 grading exists (`grading.py`), self-documented as not cross-validated against an external judge |
| Task success (agent-level, non-TSR) | MISSING | No historical component defines or computes a full agent-level task-success metric distinct from strict TSR and from raw answer EM/F1 |
| Memory contribution / gold memory contribution deltas | MISSING | Per-condition accuracies exist in the historical pilot; the delta computation itself (`accuracy(C)-accuracy(A)`) was never implemented |
| Gold-memory ceiling, retrieval utilization | MISSING | No historical component computes these explicitly, though `aggregate_report.py`'s per-condition metrics contain the raw ingredients |
| Leakage detection | MISSING | No implementation found anywhere, historical or active |
| Deterministic replay | PARTIAL | Deterministic lexical retrieval and event logging exist (`substrate.py`); no end-to-end deterministic-replay harness covering the full pipeline was found |
| Reproducibility manifests (agent/memory layer) | MISSING | No general-purpose reproducibility-manifest mechanism for the memory/agent layer exists; Phase 1/2 has its own reproducibility manifest (`reproducibility.py`, frozen, structurally informative only) |
| Trace validation (full task-execution chain) | PARTIAL | Structural lifecycle/provenance-graph validation exists; the full chain required by `TRACEABILITY_CONTRACT.md` (candidate set → reranking → selected → reasoning context → response → evaluation) has never been implemented, because no historical component ever wired a live reasoning layer to a live retrieval/selection pipeline in one run (the Qwen pilot consumed pre-recorded task records, not a live pipeline output) |
| Evaluation-run artifacts (general) | PARTIAL | Every historical experiment writes its own ad-hoc JSON report format under its own `reports/`/`results/` directory; no shared, standardized evaluation-run artifact schema exists across the corpus |

---

## 11. Recommended Phase 3.2 architecture (proposal only — not implemented)

The following is a proposed shape for a Phase 3.2 evaluation layer, showing which historical
components would be reused as-is, wrapped with an adapter, rewritten, left purely historical, or
built new. **Nothing below has been implemented as part of this audit.**

```mermaid
flowchart TB
    subgraph Frozen["Phase 1/2 frozen substrate (read-only)"]
        UMR[Unified Memory Record\npreprocessing/*.py]
        TaskRec[TaskRecord loaders\nlocomo.py / longmemeval.py]
    end

    subgraph New["New Phase 3.2+ implementation (to be built)"]
        MemLayer["Memory layer\n(new: memory_schema.json-conformant store)"]
        CandDisc["Candidate discovery\n(REWRITE: substrate.py's lexical retrieve()\nas one of possibly several channels)"]
        Rerank["Reranking\n(NEW - not present in any historical code\nas a separated layer)"]
        Select["Evidence selection\n(REWRITE: old DeterministicTopNUsageStrategy\ntoo naive for new layer separation)"]
        Ctx["Reasoning context assembly\n(NEW, leakage-gated per\nLEAKAGE_AND_VISIBILITY_CONTRACT.md)"]
        Reason["Reasoning layer (Qwen3-8B)\n(NEW wiring; historical Qwen pilot\nnever connected to a live pipeline)"]
    end

    subgraph EvalLayer["New Phase 3.2 evaluation layer"]
        MemMetrics["Memory-level metrics\nADAPT: v2c Recall@k/MRR/evidence P-R\n(extend k to 100/200, add coverage/redundancy - NEW)"]
        FailTax["Failure taxonomy\nADAPT: v2c 3-way candidate-gen/selection/\nidentity-artifact classifier (re-source from\nnew selection, not rejected lineage mechanism)"]
        Prov["Provenance/lineage/lifecycle validation\nADAPT: lifecycle.py + lifecycle_graph.py\n(re-derive against CREATED/ACTIVE/RETIRED\nand pairwise-edge-only model)"]
        TSRMetric["Strict TSR\nREUSE: reference_agent.py formula,\nre-wired into two-metric reporting"]
        EquivMetric["Evidence-equivalent success\n(NEW - no historical precedent)"]
        ABC["A/B/C agent-level harness\nADAPT: qwen conditions.py/grading.py/\nfailure_attribution.py/aggregate_report.py\n(remap 4 conditions to 3, wire to live pipeline)"]
        Leakage["Leakage audit\n(NEW - no historical precedent at all)"]
        Repro["Determinism/reproducibility recording\n(NEW general harness; historical\ndeterminism_study.py too narrowly scoped)"]
        Trace["Full task-execution + memory-history trace\n(NEW; historical trace coverage is\nstructural/lifecycle only, not full chain)"]
    end

    UMR --> MemLayer
    TaskRec --> CandDisc
    MemLayer --> CandDisc --> Rerank --> Select --> Ctx --> Reason

    CandDisc -.diagnostic input.-> MemMetrics
    Select -.diagnostic input.-> MemMetrics
    Select -.diagnostic input.-> FailTax
    MemLayer -.diagnostic input.-> Prov
    Select -.diagnostic input.-> TSRMetric
    Select -.diagnostic input.-> EquivMetric
    Ctx -.leakage-gated audit.-> Leakage
    Reason --> ABC
    MemLayer --> Prov
    CandDisc --> Trace
    Rerank --> Trace
    Select --> Trace
    Ctx --> Trace
    Reason --> Trace

    Historical["phase3_reference/ (read-only citation\nsource; never imported/executed)"]
    Historical -.. design precedent only ..-> EvalLayer
```

**What's reused:** the lifecycle-validation methodology, the provenance-graph structural-check
methodology, the Recall@k/MRR/evidence-P/R formulas, the strict-TSR formula, the paired-
counterfactual causal-replay method, the extended-rank rescan methodology, the four-condition
answer-grading/failure-attribution/report-template shape (collapsed to three conditions).

**What's wrapped (adapter):** everything above must be re-derived against the new memory
schema (`memory_type`, `parent_ids`, `lifecycle_state`), the new lifecycle states
(`CREATED→ACTIVE→RETIRED`), the new relationship model (pairwise edges only, no lineage
families), and a real (not yet built) candidate-discovery/reranking/selection layer separation —
none of the historical code was built against these.

**What's rewritten:** candidate discovery/retrieval itself (must support the new layer
separation and multiple channels per the master spec's retrieval architecture), evidence
selection (old top-N cut is too naive), and the reasoning-context assembly step (must be built
leakage-gated from the ground up).

**What remains purely historical:** the explicitly-rejected mechanisms (blanket temporal
proximity, relation-aware temporal retrieval, semantic-only retrieval, lineage-family/
foundation-preference selection, selective memory creation, score-gap selection), all ad-hoc
debug scripts, and all historical spec documents (valuable as citations, not methodology).

**What's missing entirely and must be built new:** evidence coverage, redundancy, evidence-
equivalent success, memory/gold-memory contribution deltas, gold-memory ceiling, retrieval
utilization, leakage-detection tooling of any kind, a general-purpose reproducibility/
determinism harness, and the full task-execution trace chain (candidate set → reranking →
selection → reasoning context → response → evaluation) connecting a live pipeline end to end —
no historical component has ever run a live retrieval/selection pipeline wired to a live
reasoning layer in one execution.

---

## 12. Risks

- **Baseline-number contamination risk.** The historical TSR/Recall figures (29.79%/34.40% TSR,
  Recall@50 ≈50-51%) are frequently cited in `phase3_reference/specifications/` and could be
  mistaken for a current Phase 3.2 baseline if not clearly re-labeled as produced under a
  different (partially rejected) architecture.
- **Rejected-mechanism re-entry risk.** Several rejected mechanisms (especially Experiment D's
  score-gap selection, which measurably outperformed what shipped, and Experiment H's lineage-
  family selection, whose diagnostic tooling is separately marked reusable) present a temptation
  to quietly re-adopt the mechanism while reusing its adjacent tooling. Any reuse of `v2c/src/
  diagnostic_v2_root_cause.py` or `diagnostic_v2_derived_memory_causal.py` must explicitly swap
  out the `instrumented_selection()` call to a non-rejected mechanism, not merely inherit it.
- **Untested-metric risk.** The single most load-bearing quantitative module found
  (`run_diagnostic_cycle2_retrieval_metrics.py`, computing Recall@k/MRR/evidence-P/R) has zero
  dedicated unit tests anywhere in the historical corpus. Treating its formulas as validated
  because they "look standard" would repeat the audit's own stated warning against equating
  "existing" with "validated."
- **Premature-freezing risk for evidence-equivalent success.** This metric has no historical
  precedent and could plausibly be defined at either the answer-text or evidence-ID equivalence
  layer, and involves a not-yet-frozen semantic-equivalence threshold per the master spec's
  section 4 — building it prematurely risks freezing a threshold that should remain
  experimental.
- **Leakage-tooling absence is a genuine blocker.** Because no leakage-detection tooling of any
  kind exists (historical or active), and the freeze gate requires this audit to pass, Phase 3.2
  cannot skip designing this from scratch — there is no shortcut available here.
- **Trace-chain absence is a genuine blocker.** No historical component ever connected a live
  candidate-discovery/reranking/selection pipeline to a live reasoning layer in one execution;
  the full traceability chain required by `TRACEABILITY_CONTRACT.md` has literally never been
  exercised end-to-end by anything in this repository. This is a larger build than the metric-
  adaptation work above and should be scoped and planned as such.
- **Dataset fixture gap.** `tests/fixtures/{locomo,longmemeval}/` are empty; any new evaluation
  test suite has no committed gold-evidence fixture to build against and will need to author its
  own, adding scope not visible from the specification documents alone.

---

## 13. Required decisions before 3.2-B

1. Which historical components are formally approved for adapter-based reuse vs. which must be
   built new from zero — this audit proposes a classification (section 8) but does not have
   authority to finalize it.
2. Whether the historical four-condition Qwen pilot's `CONDITION_D` (raw uncurated retrieved
   context) is retained as a fourth diagnostic condition alongside the frozen A/B/C, or dropped —
   the new evaluation contract defines exactly three conditions and does not mention a fourth.
3. Whether evidence-equivalent success is defined at the memory-identity level (via
   `equivalent_to`/duplicate relationships) or the answer-text level (via something like the
   historical `token_f1` grading) — the new contract requires the metric but does not fix which
   layer it operates on, and the historical corpus has precedent for both without unifying them.
4. Whether Experiment D's score-gap selection (empirically the highest-TSR selection mechanism
   found historically, but excluded by prior project-owner scope decision, not by negative
   result) should be revisited under `EXPERIMENT_GOVERNANCE.md` in a future stage, given the
   tension documented in section 4/9, or left excluded as-is.
5. How many repeated trials and what statistical treatment will be used to characterize Qwen3-
   8B variance (explicitly deferred to freeze-gate time by `REPRODUCIBILITY_CONTRACT.md`) — the
   one historical determinism study found was narrowly scoped for cost reasons and does not by
   itself answer this.
6. Whether Recall@100/200 are computed via a deeper rescan of the same lexical mechanism (simple
   extension of the historical rescan tool) or require a different candidate-discovery mechanism
   entirely once the new layer separation exists — this depends on decision open in the master
   spec's still-experimental retrieval-fusion formula.
7. Physical storage/indexing mechanism for traceability data (explicitly deferred by
   `TRACEABILITY_CONTRACT.md` to a later Phase 3 stage) — no historical precedent settles this
   either; the historical event log is JSONL-file-based, which may or may not be adequate at the
   new spec's traceability scope.

---

## 14. Statement: no implementation was performed

This audit consisted entirely of reading existing files — specification documents under
`phase3/specification/`, `phase3/schemas/`, `phase3/contracts/`; historical source, test, report,
and result files under `phase3_reference/`; Phase 1/2 dataset loader and test files under
`preprocessing/` and `tests/` (for scoping/boundary confirmation only); and repository-wide
keyword searches. **No code, schema, evaluator, dataset adapter, metric implementation, runner,
or test was written, modified, or executed as part of this audit**, other than the creation of
this single file, `phase3/evaluation/AUDIT.md`, and the `phase3/evaluation/` directory that
contains it. No file under `phase3_reference/`, `data/`, `preprocessing/`, `docs/phase2/`, or any
previously-tracked repository file was modified.

---

## Decision table

| Capability | Existing implementation | Status | Recommendation |
|------------|-------------------------|--------|----------------|
| Recall@K | `v2c/src/run_diagnostic_cycle2_retrieval_metrics.py`, k∈{1,5,10,20,50} only, untested | PARTIAL (missing k=100,200; untested) | REUSE WITH ADAPTER — extend k-list, add unit tests, re-derive against new memory schema and a real candidate-discovery layer |
| MRR | Same module, first-hit-rank based | PARTIAL (untested) | REUSE WITH ADAPTER — add unit tests before trusting |
| Strict TSR | `clean_agent_v1/src/reference_agent.py`, literal `used ∩ evidence` set intersection | PRESENT as formula; historically over-promoted to sole success metric | REUSE the formula verbatim; enforce the new contract's rule that it is reported only alongside evidence-equivalent success and A/B/C accuracy, never alone |
| Evidence precision | `v2c/src/run_diagnostic_cycle2_retrieval_metrics.py`'s `evidence_metrics()` | PARTIAL (untested) | REUSE WITH ADAPTER |
| Evidence recall | Same module | PARTIAL (untested) | REUSE WITH ADAPTER |
| Evidence equivalence | No historical implementation at the memory-identity level; `grading.py`'s `token_f1` exists at the answer-text level only | MISSING at the required layer | REIMPLEMENT — new metric, must resolve the memory-ID-vs-answer-text layer question first (see section 13, decision 3) |
| Provenance | `clean_agent_v1/src/lifecycle_graph.py`'s `validate_graph()` structural checks | PARTIAL (methodology sound, tied to old schema) | REUSE WITH ADAPTER — re-derive against `memory_schema.json`/`relationship_schema.md` |
| Lineage | `diagnostic_v2_root_cause.py`'s `derivation_depth()`, `clean_baseline.py`'s `_lineage_depth()` | PARTIAL (correct method, tied to old lineage-family-adjacent code it must be decoupled from) | REUSE WITH ADAPTER — verify pairwise-edges-only traversal, no precomputed families, per new schema |
| Lifecycle | `clean_agent_v1/src/lifecycle.py` state machine, tested against an old 3-state model | PARTIAL (old states, not new `CREATED/ACTIVE/RETIRED`) | REUSE WITH ADAPTER — re-derive transition table against new canonical states |
| Agent evaluation | `qwen_experiments/reasoning_layer_v1/` four-condition pilot, never wired to a live pipeline | HISTORICAL-UNSAFE | REUSE WITH ADAPTER — remap 4 conditions to new A/B/C, rebuild against a real Phase 3.2/3.3 pipeline, not the old V2c thread |
| Memory contribution | Raw per-condition accuracies exist (`aggregate_report.py`); delta computation itself absent | MISSING | REIMPLEMENT — small addition on top of adapted `aggregate_report.py` |
| Leakage detection | None found anywhere, historical or active | MISSING | REIMPLEMENT — no shortcut; must be built new, is a freeze-gate blocker |
| Determinism | `determinism_study.py`, one condition, one stratified sample, explicitly cost-scoped | PARTIAL | REIMPLEMENT as a general-purpose harness; historical study is too narrow to extend |
| Reproducibility | Phase 1/2 has its own manifest pattern (`preprocessing/reproducibility.py`, frozen, structural precedent only); no agent/memory-layer equivalent exists | MISSING (agent/memory layer) | REIMPLEMENT, using the frozen Phase 1/2 manifest pattern as a structural (not code) precedent only |
| Trace validation | Structural lifecycle/provenance-graph validation exists; full task-execution chain (candidate set→reranking→selection→context→response→evaluation) never implemented end-to-end | PARTIAL (structural only) | REIMPLEMENT the full chain; REUSE WITH ADAPTER the structural lifecycle/provenance pieces as components of it |
