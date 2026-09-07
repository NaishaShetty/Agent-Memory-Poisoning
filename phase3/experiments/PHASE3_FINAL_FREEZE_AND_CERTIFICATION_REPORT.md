# Phase 3 Final Freeze and Certification Report

Status: **PHASE 3 FROZEN**, as of this report, on the evidence below. This is the
terminal Phase 3 document — it does not introduce new work, it consolidates and
certifies what real work already exists, with every claim traceable to a specific
real artifact.

## A. What Phase 3 IS

A real, largely-tested, mostly-real-infrastructure-validated **memory foundation and
clean-agent benchmark** for two active foundations (Mem0, A-MEM), comprising: an
append-only canonical memory/event ledger architecture (H.1/H.2/H.3, with two real
bugs found and fixed via a reviewed process — H.3-R/H.3-R2); a deterministic
provenance-graph projection over those ledgers (single- and multi-boundary); a
real, calibrated counterfactual-influence measurement mechanism; a frozen, primary
120×2 clean-agent behavioral dataset (LoCoMo × {Mem0, A-MEM}, all four
`EVALUATION_CONTRACT.md` conditions); a real, calibrated but non-canonical
threshold-based selection-policy variant; a real, demonstrated `superseded_by`
creation-policy detector; and an honest, evidence-heavy research record of what was
tried and did not work (`equivalent_to`/`conflicts_with` automatic detection, a V2
reference agent, an A-MEM backend fix) — each closed with real data, not assumption.

## B. What Phase 3 IS NOT

- Not a system with working automatic `equivalent_to`/`conflicts_with` detection —
  both are explicitly deferred, NO-GO, real-evidence-backed.
- Not a system where selection is canonically real — the FROZEN primary dataset
  still uses the provisional (identity-slice) selection policy; the real,
  calibrated threshold policy exists only as a separately-documented variant.
- Not a system with a more capable V2 reference agent — V2 was built, piloted, and
  formally NO-GO'd for promotion; V1 remains canonical.
- Not a system with full counterfactual coverage — 40/240 records, not 240/240.
- Not a system that has qualified Graphiti or Letta — both remain explicitly out of
  scope/deferred, untouched, unrevived.
- Not a system whose exact-match accuracy numbers should be read at face value —
  the frozen grader is real but deliberately strict; a second, additive metric
  exists specifically because the first one alone is misleading.
- Not dependent on `phase3_reference/` anywhere in its active execution path
  (verified directly — zero real Python imports).

## C. Canonical architecture

`phase3/evaluation/foundations/` (H.1 `ledger.py`/`canonical.py`, H.2
`canonical_event.py`/`event_ledger.py`, H.3 `memory_versioning.py`), `provenance_graph.py`,
`environment_record.py`, `run_config.py`, `selection_policy.py` (calibrated,
non-canonical-path), `creation_policy.py` (`superseded_by` half, real),
`similarity.py`, `relationship_candidates.py` (suggestion-only layer, both relationship
types). `phase3/evaluation/agent_runtime/` (`runner.py` = V1 canonical agent,
`gold_evidence_runner.py`, `campaign_formal_runner.py` = canonical campaign path,
`canonical_wiring.py`, `dataset_record_assembler.py`, `selection_policy_runner.py`/
`campaign_selection_policy_runner.py` = variant-only path, `reference_agent_v2.py` =
non-canonical candidate).

## D. Canonical reference agent

**V1** (`agent_runtime/runner.py::run_agent_task()`). Real, tested, used to produce
every canonical real artifact this project has (the frozen G-formal baseline and the
primary 120×2 dataset). V2 (`reference_agent_v2.py::run_agent_task_v2()`) is a real,
tested, formally-qualified CANDIDATE — NO-GO for promotion (identical normalized
correctness, 2/20, at real n=20 qualification) — preserved, not canonical.

## E. Canonical clean baseline

**Correction to this closure's own initial framing, stated plainly**: the literal
artifact named `clean_agent_memory_v1` lives inside `phase3_reference/clean_agent_v1/baselines/clean_agent_memory_v1/`
— i.e. it is part of the LEGACY reference tree, not a separate active-Phase-3
artifact. This was already established earlier this session
(`PHASE3_ACTIVE_CLEAN_BASELINE_CLARIFICATION.md`) and is reconfirmed here directly
(verified: it exists ONLY under `phase3_reference/`, nowhere in the active `phase3/`
tree). Per that document's own, already-correct resolution: it is **NOT** re-certified
as "canonical/immutable Phase 3 clean baseline" here, because doing so would
misrepresent a legacy artifact as an active one.

**The genuinely active, canonical clean-agent baseline** is: `runner.py::run_agent_task()`
(V1, §D) + the frozen 3.3-G-formal campaign evidence + the primary 120×2 dataset
(§F). This is what is actually certified below.

**`clean_agent_memory_v1` itself, as a legacy artifact**: inspected at the directory
level only (per the standing "do not modify phase3_reference" instruction, no deep
content audit or modification was performed). It is untracked by git (0 files),
contains its own manifest/hashes/events/reports from an earlier, disavowed Phase 3
attempt, and the active codebase has zero real import dependency on it (verified).
**Certification: LEGACY / HISTORICAL REFERENCE ONLY — not certified as the active
canonical clean baseline, and not modified.**

## F. Canonical dataset(s)

**Primary (canonical)**:
`phase3/experiments/results/canonical_store/dataset_full/clean_agent_dataset_locomo_120x2.json`
— 240 records (120 tasks × {MEM0, AMEM}), 0 schema errors, 0 duplicate
(task_id, foundation) pairs, identical task_id sets across foundations, single
consistent `generation_config_fingerprint` across all 240 records, all four
`EVALUATION_CONTRACT.md` conditions present per record, 40/240 real counterfactual
coverage (§J). **Untouched by the selection-policy variant or any research-track
work** — verified: the variant lives in a fully separate file/directory, the
counterfactual attach was the only post-hoc modification, and it was additive
(pre-attach backup preserved, byte-diff confirms only `counterfactual_influence`/
`observability_coverage.counterfactual_measured` fields changed).

**Selection-policy variant (real, experimental, NOT canonical)**:
`phase3/experiments/results/canonical_store/selection_policy_variant/` — a real,
full 120×2 run under the calibrated threshold selection policy. Per explicit
instruction, NOT treated as replacing the primary dataset — kept as a
separately-documented real experimental artifact (`PHASE3_3_SELECTION_POLICY_VARIANT_120x2_COMPLETION_REPORT.md`,
`PHASE3_SELECTION_FINAL_DIAGNOSTIC.md`).

## G. Selection-policy status

Real, calibrated (`CALIBRATED_THRESHOLD_LOCOMO=0.2633`, 125 real LoCoMo pairs, 95%
gold-evidence coverage target), run at full real scale as a variant (2,937 real
`rejected` events, 71-92/120 real answers changed vs. primary). **Not canonical.**
The primary dataset's Condition C still uses the provisional identity-slice policy.
`PHASE3_SELECTION_FINAL_DIAGNOSTIC.md` documents that the retrieval-pool-size effect
and the selection-mechanism effect could not be cleanly isolated from existing data
(both changed simultaneously in the variant) — stated as an honest limitation, not
resolved further.

## H. Counterfactual status

**40/240 records carry real counterfactual evidence** (20 LoCoMo tasks × Mem0, 20 ×
A-MEM, matched exactly by `(task_id, foundation)` against the real n=20 measurement
runs). **200/240 records carry none.** The earlier n=6 measurements are a verified
strict subset of n=20 for both foundations and added no new coverage. **No claim of
full 240-record coverage is made anywhere in canonical documentation** — verified by
grep across this session's own reports; every mention states 40/240 explicitly.

## I. Foundation qualification

**Mem0**: QUALIFIED, 15/15 real fixtures, zero divergence
(`PHASE3_3_H4_D_RUN_REPORT.md`). Real write/inspect/retrieve/select(provisional)/
exposure(citation-diagnostic)/reset tested; update/supersession/retire tested via
the canonical H.3 mechanism against real Mem0-sourced canonical records; identity
mapping (`STRATEGY_METADATA_LOOKUP`) real and tested (`test_identity_bridge.py`,
real-runtime, verified passing under `h4venv` this session: 105/105 real-infra
tests green).

**A-MEM**: QUALIFIED, 15/15 real fixtures, zero divergence
(`PHASE3_3_H4_D_A_RUN_REPORT.md`). Same coverage as Mem0, identity mapping
(`STRATEGY_DIRECT_ASSIGNMENT`) real and tested. **Known, documented limitation**:
every real A-MEM ingestion incurs the Ollama-unreachable confound (§ below) — a
real, measured performance cost, not a correctness defect (never fabricates a fake
evolution result, always falls back honestly).

**Graphiti**: OUT OF SCOPE / DEFERRED. Not revived, not touched, no qualification
claimed anywhere.

**Letta**: OUT OF SCOPE / DEFERRED. Same as above.

## J. Lifecycle/provenance status

`CanonicalMemoryLedger`/`CanonicalEventLedger`/`SupersessionLedger` real, tested,
append-only (H.2's own single-occurrence + append-only guarantees, worker-merge
tested). Canonical memory identity is authoritative; vendor ids are aliases only
(verified structurally in both Mem0's `METADATA_LOOKUP` and A-MEM's
`DIRECT_ASSIGNMENT` identity strategies). Experiment boundaries genuinely isolate —
`build_multi_boundary_provenance_graph()`'s zero-cross-boundary-edge invariant is
both unit-tested and verified against real composed data (42 nodes, 80 edges, 0
cross-boundary, `PHASE3_3_H4_MULTI_BOUNDARY_REAL_DEMONSTRATION_REPORT.md`).
Lifecycle/supersession reconstruction is correct, including for the real
`superseded_by` demonstrations this closure re-verified (§K). The provenance graph
is a deterministic projection — never a second persisted store (verified by
inspection: no `load_provenance_graph_from_json()` exists, only reconstruction from
live ledgers). Selection/rejection events are real and reconstructable (verified
directly against a real selection-policy-variant pool's event ledger:
`{'retrieved': 47, 'selected': 15, 'rejected': 32}`).

**Known H.3 limitation** (explicitly assessed, per this closure's own instruction):
the raw `CanonicalEventLedger.append()` API does not itself enforce that a
`superseded`/`retired`/`SupersessionRecord` triplet is always internally
consistent — a caller COULD append a malformed sequence directly. **Classification:
B — documented limitation, not an actual blocker.** Verified directly: every real,
non-test call site in the active codebase that calls `event_ledger.append()` sits
INSIDE an orchestrating function (`canonical_wiring.py`'s retrieved/selected/rejected
emitters, `memory_versioning.py`'s own `supersede_memory()`/`retire_memory()`,
`creation_policy.py`'s single-purpose emitter, `qualification_harness.py`'s
controlled test context) — there is no real production path that appends raw,
unorchestrated events. The limitation is real at the API-design level; it is not
exercised anywhere in the canonical frozen execution path.

**Known environment-record gap** (found during this closure's integrity audit, not
previously documented as clearly): every record in the primary 120×2 dataset has
`environment_record_id: null`. The `EnvironmentRecord` mechanism itself is real and
tested (`PHASE3_3_H4_ENVIRONMENT_RECORD_IMPLEMENTATION_REPORT.md`, one real capture
exists from an earlier validation run) but was **never wired into the actual
dataset-producing campaign** (`campaign_formal_runner.py`, `dataset_record_assembler.py`).
This is a real, honest reproducibility gap — the mechanism to capture "what real
package versions/artifact hashes produced this dataset" exists but was not invoked
for the dataset that needs it most. Documented as a known limitation (§M), not
silently patched during this closure (would require a new real capture + dataset
mutation, out of scope for a closure operation).

## K. Relationship status

- **`superseded_by`**: IMPLEMENTED / REAL-DEMONSTRATED. 16 real examples (1 curated
  LoCoMo + 15 deterministically-selected real LongMemEval knowledge-update pairs),
  16/16 successful, real lifecycle reconstruction confirmed. Not wired into any live
  campaign path (no real caller exists in current pipeline code — documented, not
  hidden).
- **`equivalent_to`**: ONTOLOGY SUPPORTED / ADVISORY CANDIDATE ONLY (`relationship_candidates.py`,
  real, demonstrated, never auto-commits) / AUTOMATIC DETECTION NO-GO. Best real
  cascade F1 = 0.533 (254 real pairs); few-shot prompting real-but-modest
  improvement to 0.400 on held-out; fine-tuning attempt real NEGATIVE result
  (0.296→0.250 held-out F1).
- **`conflicts_with`**: ONTOLOGY SUPPORTED / AUTOMATIC CONVERSATIONAL DEPLOYMENT
  NO-GO / FUTURE RESEARCH. Real MemoryAgentBench `Conflict_Resolution` data
  demonstrated strong mechanism capability (LLM judge: 0.976 F1) on a different,
  declarative fact-triple genre — this does NOT establish equivalent performance on
  LoCoMo conversational memory, where zero real positive examples exist at any
  scale attempted (254 real pairs, two rounds).

**Contamination check**: none of these three research tracks modified any canonical
artifact. Verified: `superseded_by`'s real demonstrations live in dedicated,
separate ledger directories (`superseded_by_real_demo/`, `superseded_by_real_demo_longmemeval/`),
never the primary dataset's own canonical stores; `equivalent_to`/`conflicts_with`
research never called `CanonicalEventLedger.append()` at all (verified: their only
ledger-adjacent module, `relationship_candidates.py`, contains zero `.append()`
calls by construction).

## L. Evaluation metrics

**Exact-match** (`agent/outcomes.py::evaluate_answer_correctness()`) — frozen,
Phase 3.2-E, unmodified, still the primary/original metric. Real result on the
primary dataset: 0.0% / 0.0% / 0.4% (A/GOLD_EVIDENCE/C) — near-zero by design
interaction with free-form generation, not a defect (traced directly to real
sample answers).

**Normalized** (`agent/normalized_correctness.py`) — new, additive, NEVER replaces
or modifies the frozen metric or any historical `evaluation_result` field. Real
result on the same 240 records: **3.3% / 43.3% / 39.6%**. Deterministic (lowercase +
punctuation-strip + whitespace-collapse + bidirectional substring), 6 tests, no
pathological behavior found (an empty gold answer never counts as correct, checked
directly). **Both metrics are preserved and documented as complementary, not
competing** — the historical `evaluation_result` fields in the dataset itself are
untouched; the normalized numbers live in a separate summary artifact
(`dataset_full_normalized_correctness_summary.json`).

## M. Known limitations

**Research limitations** (open scientific questions, not implementation debt):
- `equivalent_to`/`conflicts_with` automatic detection quality ceiling on
  conversational-register memory is genuinely unknown past what was measured (best
  real F1 0.533/undetermined).
- Whether the MemoryAgentBench-validated `conflicts_with` mechanism (0.976 F1)
  transfers to conversational register is untested (no real conversational
  positive examples exist to test against).
- Retrieval-pool-size effect vs. selection-mechanism effect cannot be isolated from
  existing selection-policy-variant data (would need an ablation run, not performed).

**Engineering limitations** (real, fixable, not yet done):
- Selection policy real but not wired into the canonical campaign path.
- `superseded_by` detection real but has no real caller in the live pipeline.
- A-MEM's Ollama confound: root cause confirmed, a real fix validated
  end-to-end (point A-mem-sys's OpenAI backend at the already-running llama-server),
  deliberately not wired into the shared adapter pending its own scale pilot.
- `environment_record_id` is `null` for all 240 primary-dataset records — the
  mechanism exists, was never invoked for this dataset.
- V2 reference agent real, tested, NO-GO for promotion at n=20 — not re-tested at
  larger scale.

**Phase 4 claim restrictions** (what must NOT be asserted downstream):
- No claim of full (240/240) counterfactual coverage.
- No claim of automatic `equivalent_to` or conversational `conflicts_with`
  detection.
- No claim of universal/general causal memory influence (counterfactual results are
  interventional-dependence evidence, explicitly not causal proof, per this
  session's own established framing).
- No claim that V2 is superior to V1.
- No claim of Graphiti or Letta qualification.
- No claim that the selection-policy variant is or automatically becomes the
  primary dataset.
- No claim of complete semantic relationship understanding.

## N. Deferred research items

`equivalent_to`/`conflicts_with` automatic detection (register-transfer question,
larger real positive-example sourcing); selection-policy canonical promotion
decision; `superseded_by` real live-pipeline wiring (pending a real caller);
A-MEM OpenAI-backend fix wiring (pending its own scale pilot); V2 agent
re-qualification at larger scale; environment-record wiring into the canonical
campaign path.

## O. Legacy artifacts

`phase3_reference/` — **LEGACY / ORIGINAL PHASE 3 REFERENCE, NOT THE CANONICAL
STRENGTHENED PHASE 3 IMPLEMENTATION.** Contains the original, disavowed
`clean_agent_v1`/`clean_agent_memory_v1` (§E). Untracked by git (0 files;
`.gitignore` line 78). A dedicated, exhaustive segregation audit
(`PHASE3_REFERENCE_SEGREGATION_AUDIT.md`) confirmed: zero live Python imports, zero
config references, zero symlinks — the only fourteen string-level mentions
anywhere in `phase3/` are twelve automated anti-dependency guard tests (both
re-run and confirmed passing) and two explanatory prose citations of deliberately
NOT reusing historical logic. This separation was already correctly designed
before this session began, via `PHASE3_RESTART_BOUNDARY.md`; this closure
reconfirms it holds, not modified, not deleted, not made to conform to the
strengthened architecture.

## P. Repository cleanup

See `PHASE3_REPOSITORY_CLEANUP_REPORT.md` — 33 pure-cache directories removed
(`__pycache__`, `.pytest_cache`, all gitignored), zero scientific evidence removed.

## Q. Regression results

See the final comprehensive response for the exact, freshly-run (not assumed)
numbers.

## R. Reproducibility

Dataset: LoCoMo, `phase3.2-frozen` revision (`DATASET_REVISION` constant,
`campaign_formal_runner.py`). Task sample: `build_formal_sample(120)`, seed 33005,
deterministic. Model: Qwen3-8B-Q4_K_M (`b10717`/`a32af33de`, verified via
`system_fingerprint` on every real run this session). Inference backend:
`llama-server.exe`, OpenAI-compatible HTTP, `-ngl 99 --ctx-size 16384 --parallel 4`.
Embedding model: `sentence-transformers/all-MiniLM-L6-v2` (both foundations, plus
the benchmark-owned `similarity.py`). Selection pool size: N=20
(`RETRIEVAL_POOL_SIZE_N`, variant only). Selection threshold: 0.2633
(`CALIBRATED_THRESHOLD_LOCOMO`, real-calibrated, 125 real pairs). Foundation
versions: real `mem0ai`/`A-mem-sys` installed under `C:\h4venv` (external, real,
pinned-commit A-mem-sys per earlier session verification). Experiment boundaries:
per-pool `(dataset, session)` canonical ledger directories, campaign-id-scoped.
Ledger locations: `phase3/experiments/canonical_store/` (raw ledgers) and
`phase3/experiments/results/canonical_store/` (run summaries + the primary
dataset) — see the naming-collision clarification in the cleanup report.
Canonical dataset: §F. Counterfactual coverage: §H. Evaluation metrics: §L.
Known limitations: §M. Deferred work: §N.

## S. Exact frozen artifacts and paths

- `phase3/experiments/results/canonical_store/dataset_full/clean_agent_dataset_locomo_120x2.json` — **CANONICAL, primary dataset**
- `phase3/evaluation/agent_runtime/runner.py` — **CANONICAL, V1 reference agent**
- `phase3/evaluation/agent_runtime/campaign_formal_runner.py` — **CANONICAL, campaign execution path**
- `phase3/evaluation/foundations/` (H.1/H.2/H.3 modules) — **CANONICAL, ledger architecture**
- `phase3/schemas/clean_agent_dataset_record_schema.json`, `provenance_graph_schema.json` — **CANONICAL, export schemas**

## T. Exact experimental/non-canonical artifacts

- `phase3/experiments/results/canonical_store/selection_policy_variant/` — experimental variant, not canonical
- `phase3/evaluation/agent_runtime/reference_agent_v2.py` — experimental candidate, NO-GO, not canonical
- `phase3/evaluation/foundations/selection_policy.py`, `selection_policy_runner.py`, `campaign_selection_policy_runner.py` — real, calibrated, NOT wired into the canonical path
- `phase3/evaluation/foundations/relationship_candidates.py` — real, suggestion-only, never auto-commits, not canonical detection
- `phase3/evaluation/agent/normalized_correctness.py` — real, additive metric, not a replacement for the canonical grader
- All `eqcf_*`/`cf_*`/`conflicts_with_*`/`agent_v2_*`/`superseded_by_real_demo*` research artifacts under `phase3/experiments/results/canonical_store/` — real evidence, non-canonical (research track)
