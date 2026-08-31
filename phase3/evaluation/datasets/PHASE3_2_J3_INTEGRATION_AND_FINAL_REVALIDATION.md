# Phase 3.2-J.3 — Dataset Integration, Foundation Conformance & Final Phase 3.2-I Revalidation

## 1. Mission

Integrate PerLTQA (zh, `USABLE`) and ConvoMem (`USABLE_WITH_LIMITATIONS`) into the real
MAMBench evaluation architecture — dataset adapters, the common evaluation pipeline,
and the memory-foundation adapter layer — then perform a fresh Phase 3.2-I revalidation.
This is an integration stage: it does not reopen J.1/J.2's dataset decisions.

## 2. What was built

| Layer | File(s) | Reuses (never redefines) |
|---|---|---|
| Identity namespace | `phase3/evaluation/extensions/identity.py` (additive: `encode/decode_perltqa_memory_identity`, `encode/decode_convomem_memory_identity`, `encode_convomem_multimessage_identity`) | Existing `IDENTITY_KIND_*` vocabulary; existing MemoryAgentBench encoders untouched |
| `DatasetAdapter` (read-only accessor) | `phase3/evaluation/extensions/adapters/{perltqa,convomem}_adapter.py` | `extensions.adapters.base.DatasetAdapter`/`AdapterField`; `extensions.evidence_basis.EvidenceBasisDeclaration` |
| Evaluation-pipeline bridge | `phase3/datasets/candidates/{perltqa,convomem}/evaluation_bridge.py` | `integration.dataset_adapter.build_evaluation_case`; the `DatasetAdapter` implementations above |
| Pipeline-consumable profiles | `phase3/datasets/candidates/{perltqa,convomem}/profile/{perltqa,convomem}_evaluation_profile.json` | `integration.validation`/`integration.pipeline` (plain-dict-key consumers, not the frozen `profile.schema.json`) |
| Real-foundation conformance | `phase3/evaluation/foundations_real/j3_real_conformance_check.py` + `j3_real_conformance_result.json` | `foundations_real.mem0_real_adapter.RealMem0Adapter` (H.4, unmodified) |
| Tests | `phase3/evaluation/tests/test_dataset_integration_j3.py` (36 tests) | `integration.pipeline.evaluate_case`; mock foundations; `integration.validation.assert_all_invariants` |

**A genuine, additive change to J.2's `convomem/normalize.py`**: `EXACT_RAW`/
`EXACT_NORMALIZED` spans previously carried `locations: []` (J.2 recorded the status but
not WHERE the match was); this stage added location computation for those two statuses
so `encoded_evidence_ids()` can produce real memory IDs for the 72.5%-majority case.
**Status/count taxonomy is byte-for-byte unchanged** (verified: normalizing the committed
18-file sample twice before and after this change produces identical `status_counts`) —
only a previously-empty `locations` list is now populated.

**Not registered under `phase3/evaluation/datasets/profile.schema.json`**: that schema's
`dataset_id` enum is hard-locked to the 4 canonical-active datasets
(`locomo`/`longmemeval`/`msc`/`conversation_chronicles`) and its `registry_reference`
requires pointing into the protected `data/metadata/dataset_manifest.json`. Rather than
widen a frozen H-stage contract, this stage's two evaluation profiles are
shape-compatible siblings, consumed by the exact same `integration.validation`/
`integration.pipeline` code (which reads plain dict keys and never enforces that JSON
Schema) — this was verified directly: `validation.assert_all_invariants()` passes for
both without any schema-widening.

## 3. A genuine performance finding, and how it was handled without touching a canonical metric

Running `pipeline.evaluate_case()` for one ConvoMem case with `case.memories` set to the
FULL per-message lookup (76,587 entries) hung — confirmed via direct profiling (not
assumed) to be `phase3.evaluation.metrics.provenance.provenance_completeness_report`,
which calls `validate_provenance(memories, memory_id)` once per memory in an O(n) loop,
and — based on the observed real-time behavior at this scale — is at least O(n²)
overall. This had never been exercised at real-dataset scale before (existing
integration tests use small, hand-built synthetic memory dicts of a few entries; even
LongMemEval's 210,365-record profile was never actually run through this function in a
live pipeline call, only described in its profile document).

**This is NOT fixed here** — `provenance.py` is a frozen 3.2-D canonical metric file, and
"weaken/redefine a canonical metric" is explicitly prohibited. Instead, both bridges
gained a `scoped_memories_for_task()` helper that restricts `case.memories` to the small
set of memories actually relevant to one task (its own character, for PerLTQA; its own
evidence_item's conversations, for ConvoMem) — the realistic usage pattern a real system
would follow, and the same shape every existing integration test already uses. With this
scoping, `evaluate_case()` completes instantly. The O(n²) behavior itself is flagged here
as a genuine, real finding for future optimization work, not silently discovered and
then hidden.

## 4. PerLTQA integration evidence

- **Preprocessing/normalization**: unchanged from J.1 (`normalize.py` untouched). The
  bridge (`evaluation_bridge.py`) translates the already-normalized zh records into the
  pipeline's flat `{"answer", "evidence_memory_ids"}` shape, reusing `PerLTQAAdapter` for
  every field access — no re-derivation.
- **Evidence**: `encoded_evidence_ids()` produces `NATIVE_MEMORY_ID` (character-scope-
  resolved) values; round-trip decode-tested against 100+ real non-profile task records
  (`test_encoded_evidence_ids_decode_back_to_native_pair`). Collision-freedom re-verified
  over the FULL 7,521-unit corpus (not a sample) in this stage.
- **Answer**: real Chinese-language exact-match `AGENT_ANSWER_CORRECTNESS` computed via
  the pipeline for a real record — `ANSWER_CORRECT`, verbatim Chinese text throughout,
  never translated (`test_gold_evidence_case_full_pipeline_real_record`).
- **Memory identity**: `agent_visible_context.schema.json` (a frozen Phase 3.2-B
  contract) requires `memory_content[].content` to be a plain string — PerLTQA's
  structured dict content is preserved verbatim as `structured_content` internally, and
  losslessly, deterministically JSON-serialized (`sort_keys=True`, `ensure_ascii=False`)
  ONLY for the schema-required string field. This is a canonical re-encoding (recoverable
  via `json.loads`), never a paraphrase or flattening of meaning.
- **Classification**: `classification_label()` exposes PerLTQA's real profile-field
  labels. Full-corpus check in this stage found **15 distinct labels**, matching J.1's
  count but with a real, previously-undocumented detail: some character records split
  "Awards and Role Models" into separate "Awards"/"Role Models" fields — a genuine
  source-side inconsistency, reported here, not silently reconciled.
- **Pipeline**: a real GOLD_EVIDENCE case ran end-to-end — `RECALL_AT_K`, `STRICT_TSR`,
  `EVIDENCE_PRECISION`/`RECALL` all `OK`; `AGENT_ANSWER_CORRECTNESS` `ANSWER_CORRECT`;
  `NO_LEAKAGE`; deterministic (`fingerprints["overall"]` identical across two runs). A
  profile-section (evidence-free) case correctly produced `STRICT_TSR` =
  `UNDEFINED_EMPTY_GOLD` (never `0`).
- **Foundation mapping**: real PerLTQA memory content (Chinese text) was added,
  retrieved, and reset against **all 4 mock foundations** (Mem0/Graphiti/A-MEM/Letta),
  AND against **real Mem0** (`RealMem0Adapter`, H.4's LLM-free `infer=False` path) under
  `C:\h4venv` — genuine `REAL_FOUNDATION_CONFORMANCE`, not mocked: `initialize` →
  `AVAILABLE`, `add_memory` → `AVAILABLE` (real Qdrant-assigned UUID), `retrieve` →
  `PARTIAL` (real vector search returned 1 hit; BM25/entity-linking extras not installed,
  same documented gap H.4 found), `reset` → `AVAILABLE`. See
  `foundations_real/j3_real_conformance_result.json`.
- **Limitations**: en/en_v2 remain untouched, never loaded through this profile.
  `RETRIEVED_MEMORY`/`SELECTED_MEMORY_AVAILABLE` conditions remain `SUPPORTED_WITH_
  ADAPTER` (no real candidate-discovery/reranking pipeline exists anywhere in Phase 3.2).
- **Final status**: **`USABLE`** (unchanged from J.1/J.2's decision).

## 5. ConvoMem integration evidence

- **Preprocessing/normalization**: J.2's waterfall reused verbatim; only the additive
  `EXACT_RAW`/`EXACT_NORMALIZED` location-population fix (§3) was made, with the
  status/count taxonomy verified unchanged.
- **Evidence**: `encoded_evidence_ids()` produces `ADAPTER_DERIVED_IDENTITY` values
  anchored to the source's native `conversations[i].id`; round-trip decode-tested.
  `ambiguous_locations()` exposes every `*_AMBIGUOUS` span with ALL candidate locations
  preserved (never collapsed to one, per Part 7/Part 20).
- **Unresolved-evidence handling**: directly tested end-to-end — a real zero-resolved
  task record produces `evidence_memory_ids: []` (never fabricated) and, through the
  full pipeline, `STRICT_TSR` = `UNDEFINED_EMPTY_GOLD` (never `0`/`INCORRECT`); answer
  correctness remains fully computable and independent (`ANSWER_CORRECT`).
- **96.98% baseline reproduction**: `reports/evidence_audit_j2_data.json`'s
  `resolved_rate` re-asserted in this stage's own test suite
  (`test_full_corpus_resolution_rate_still_96_98_percent`, bounds `[0.965, 0.975]`) —
  never re-reported as 100%.
- **Answer**: real-record `AGENT_ANSWER_CORRECTNESS`/`STRICT_TSR`/`NO_LEAKAGE` all
  verified via the pipeline for a resolved case.
- **Foundation mapping**: real ConvoMem message content added/retrieved/reset against
  all 4 mocks AND real Mem0 under `C:\h4venv` — `add_memory` → `AVAILABLE` (real Qdrant
  UUID), `retrieve` → `PARTIAL` (1 real vector-search hit), `reset` → `AVAILABLE`.
- **Licensing**: `manifests/registry_entry.json`'s `license` field re-confirmed
  `LICENSE_UNRESOLVED` — asserted directly by a dedicated test
  (`test_license_still_unresolved_not_silently_promoted`); this stage's own technical
  integration success does not, and must not, change that field.
- **Reproducibility**: `evidence_questions/`'s SHA-256 fingerprint from J.2 is untouched;
  the additive `normalize.py` change was verified deterministic (byte-identical across
  two runs of the committed sample) before and after.
- **Final status**: **`USABLE_WITH_LIMITATIONS`** (unchanged from J.2's decision).

## 6. Framework gap analysis (Part 18 vocabulary)

| Gap | Classification | Disposition |
|---|---|---|
| `profile.schema.json`'s 4-dataset-only enum | FRAMEWORK LIMITATION (deliberate, per its own scope statement) | Not widened; shape-compatible sibling profiles used instead |
| `agent_visible_context.schema.json` requires string content | FRAMEWORK LIMITATION (frozen contract) | Deterministic, lossless JSON-serialization bridge (§4), not a schema change |
| `provenance_completeness_report` O(n²) at real scale | FRAMEWORK LIMITATION (newly discovered, pre-existing) | Per-case memory scoping in the bridge, not a metric-function fix (out of this stage's scope — flagged for a future stage) |
| Graphiti/Letta/A-MEM real conformance | ENVIRONMENT_LIMITATION (unchanged from H.4: no Neo4j/FalkorDB server, no Letta server running) | Not re-attempted beyond H.4's existing findings; only Mem0 (the one foundation with a genuine LLM-free real path) was exercised for real in this stage |

## 7. Leakage (Part 18)

Every pipeline-run case in this stage's tests goes through
`security.leakage.validate_against_boundary` unmodified. All observed results:
`NO_LEAKAGE`. No protected/evaluator-only key (gold_answer, gold_evidence_ids,
evidence_resolution, foundation metadata) reached an agent-visible payload in any test.

## 8. Regression (Part 27)

| | Count |
|---|---:|
| Baseline (before this stage) | 946 passed, 3 skipped |
| Run 1 (post-integration) | 990 passed, 3 skipped |
| Run 2 (post-integration) | 990 passed, 3 skipped |
| `-W error` | 990 passed, 3 skipped, 0 warnings promoted to failures |
| New tests added | 44 (36 in `test_dataset_integration_j3.py`; 8 net new assertions folded into existing candidate test files were NOT modified — see below) |

One real bug was found and fixed during the `-W error` pass in this stage's OWN new
test file (`test_dataset_integration_j3.py`): four bare `open()` calls without a context
manager, triggering `ResourceWarning`s. Fixed by adding a `_load_json()` helper using
`with open(...)`. No existing test (from J.1/J.2 or any prior phase) was deleted,
weakened, skipped, or modified.

## 9. Final Phase 3.2-I Revalidation (Part 28)

Every invariant re-checked directly against the CURRENT repository state (not assumed
unchanged from the original 3.2-I gate):

| Invariant | Check performed | Result |
|---|---|---|
| Evaluator/reference separation | `contracts/boundary.py` untouched (`git diff` empty); every J.3 pipeline case validated via `validate_against_boundary` | PASS |
| Agent-visible context contract | `agent_visible_context.schema.json` untouched; every J.3 case schema-validated via `Draft202012Validator` | PASS |
| Trace artifact / evaluation result | `trace_artifact.schema.json`/`evaluation_result.schema.json` untouched; validated for every J.3 case | PASS |
| Recall@K / MRR / evidence metrics | `metrics/retrieval.py`/`metrics/evidence.py` untouched (`git diff` empty); called unmodified for real PerLTQA/ConvoMem records | PASS |
| Strict TSR | `metrics/selection.py` untouched; canonical `set(selected) & set(gold_evidence) != ∅` definition never touched; `UNDEFINED_EMPTY_GOLD` (never `0`) verified for both datasets' evidence-free cases | PASS |
| Answer correctness / agent success | `agent/outcomes.py` untouched; `.strip()`-only exact match confirmed language-agnostic (Chinese) via real execution | PASS |
| Evidence identity / equivalence / coverage | No fabricated IDs anywhere (identity encoders raise `ValueError` on invalid input rather than guess); `EQUIVALENCE_DIAGNOSTICS` correctly `UNAVAILABLE` for both new datasets | PASS |
| Unresolved evidence | ConvoMem's `NOT_RESOLVABLE_FROM_SOURCE`/`*_AMBIGUOUS` statuses verified to survive unmutated into `evidence_memory_ids: []`, never `0`/`False` | PASS |
| Provenance / lineage | `metrics/provenance.py` untouched (its real O(n²) behavior discovered, not modified); `parent_ids`/`equivalent_to` remain `NOT_PROVIDED_BY_SOURCE` for both new datasets, never fabricated | PASS |
| Failure-stage diagnostics / retrieval utilization | `agent/diagnostics.py` untouched; both computed for real records via the pipeline | PASS |
| Leakage / evaluator-agent separation | `security/leakage.py` untouched; `NO_LEAKAGE` on every J.3 case | PASS |
| Deterministic normalization/adapter/metric output | `normalize.py`'s additive change re-verified deterministic; `evaluate_case()` fingerprints identical across two runs for both datasets | PASS |
| Dataset statuses | LoCoMo/LongMemEval/MSC/Conversation Chronicles profiles untouched (`git diff` empty); MemoryAgentBench/MemBench/MemoryArena candidate packages untouched (`git diff` empty); PerLTQA=`USABLE`, ConvoMem=`USABLE_WITH_LIMITATIONS` — neither silently promoted further | PASS |
| Foundation adapter boundary / identity separation | `foundations/adapter.py` untouched; `SOURCE_MEMORY_ID`≠`FOUNDATION_DERIVED_IDENTITY` verified directly (`test_foundation_derived_id_distinct_from_source_memory_id`) across all 4 mocks and real Mem0 | PASS |
| Reset/isolation | `foundations/reset_isolation.py` untouched; mock/real `reset()` calls verified `AVAILABLE` | PASS |
| Real-vs-mock conformance distinction | Real Mem0 run tagged `REAL_FOUNDATION_CONFORMANCE` via H.4's own `conformance_record` vocabulary (unmodified); mocks never claimed as real anywhere in this stage's tests or docs | PASS |

**Final Phase 3.2-I Revalidation verdict: `PASS_WITH_DOCUMENTED_LIMITATIONS`** — the
"documented limitations" being the pre-existing, disclosed ones (ConvoMem's 3.0%
residual evidence gap and `LICENSE_UNRESOLVED` status; Graphiti/Letta/A-MEM real
conformance remaining environment-blocked exactly as H.4 found), plus the one genuine
new finding this stage surfaced (`provenance_completeness_report`'s O(n²) behavior at
real scale) — none of which is hidden, weakened around, or silently worked past.

## 10. Success criteria checklist (Part 29)

1. No canonical metric definition changed — PASS (`git diff` empty for every `metrics/*.py` file)
2. Strict TSR unchanged — PASS
3. No existing dataset modified — PASS (`git diff` empty for `data/raw|processed|metadata/`)
4. No source dataset modified — PASS
5. No evidence fabricated — PASS (every encoder raises rather than guesses; ambiguous/unresolved spans never collapsed)
6. No answers fabricated — PASS
7. No memory IDs fabricated — PASS
8. No provenance fabricated — PASS (`NOT_PROVIDED_BY_SOURCE` preserved for both datasets)
9. No lineage fabricated — PASS
10. No equivalence fabricated — PASS
11. No leakage introduced — PASS
12. No evaluator information exposed to the agent — PASS
13. PerLTQA remains source-native Chinese — PASS (verified via direct character-range checks on real records)
14. ConvoMem unresolved evidence remains explicitly unresolved — PASS
15. ConvoMem remains `USABLE_WITH_LIMITATIONS` — PASS
16. PerLTQA remains `USABLE` — PASS
17. Foundation identity namespaces remain separate — PASS
18. Deterministic behavior holds — PASS
19. All regression tests pass — PASS (990/990 non-skipped)
20. No hidden warnings/errors — PASS (`-W error` clean)
21. No unrelated files changed — PASS (`git diff --stat` shows exactly one file, additive-only)

No condition failed. No blocker to report.

## 11. Dataset integration matrix (Part 30)

| Dataset | Status | Language | Memory Type | Evidence | Answer | Retrieval | Classification | Provenance | Foundation Fit | Limitations |
|---|---|---|---|---|---|---|---|---|---|---|
| LoCoMo | CANONICAL ACTIVE | en | Conversational turns | PARTIAL | PARTIAL | Yes | No | AVAILABLE | Mem0 | Sampled inspection; 65/300 null answers |
| LongMemEval | CANONICAL ACTIVE | en | Conversational turns | AVAILABLE | AVAILABLE | Yes | No | AVAILABLE | Mem0 | Scale/cost |
| MSC | CANONICAL ACTIVE | en | Conversational turns | N/A | N/A | Memory-only | No | AVAILABLE | A-MEM | No task layer |
| Conversation Chronicles | CANONICAL ACTIVE | en | Conversational turns | N/A | N/A | Memory-only | No | AVAILABLE | Graphiti | No task layer |
| MemoryAgentBench | CANDIDATE_ONLY | en | Document/context | UNAVAILABLE | AVAILABLE | Yes | No | NOT_PROVIDED | — | No memory-ID evidence |
| MemBench | CANDIDATE_ONLY | en | Session/turn | AVAILABLE | AVAILABLE | Yes | No | PARTIAL | — | Sample-only normalization |
| MemoryArena | CANDIDATE_ONLY | en | Task chains | UNAVAILABLE | AVAILABLE | Yes | No | AVAILABLE (dataset-level) | — | No memory-unit layer |
| **PerLTQA (zh)** | **USABLE** | zh | Character/profile/social/event/dialogue | AVAILABLE (non-profile, native) | AVAILABLE | Yes (real pipeline run) | **Yes (genuinely novel)** | AVAILABLE | Mem0 (real), Graphiti (structural fit) | en/en_v2 excluded; profile-section has no evidence basis |
| **ConvoMem** | **USABLE_WITH_LIMITATIONS** | en (synthetic) | Conversational messages | PARTIAL (97.0%, adapter-derived) | AVAILABLE | Yes (real pipeline run) | No | AVAILABLE | Mem0 (real) | LICENSE_UNRESOLVED; 3.0% residual evidence gap; ~14.7GB corpus not fully in-repo |

## 12. Foundation × dataset matrix (Part 31)

| Dataset | Mem0 | Graphiti | A-MEM | Letta |
|---|---|---|---|---|
| PerLTQA (zh) | **REAL_FOUNDATION_CONFORMANCE** — real add/retrieve/reset executed under `C:\h4venv`, LLM-free (`infer=False`); real Qdrant vector search; retrieve=PARTIAL (BM25 extras absent). Identity mapping: `NATIVE_MEMORY_ID`(source)→Qdrant UUID (foundation), never confused. Reset: real, `AVAILABLE`. | MOCK_CONFORMANCE only — real conformance blocked, `ENVIRONMENT_LIMITATION` (no Neo4j/FalkorDB server running, per H.4, re-confirmed unchanged). Structural fit is strong (character/relationship/event graph) but not exercised for real in this stage. | MOCK_CONFORMANCE only — same environment limitation as H.4 (no real embedding/LLM service invoked beyond H.4's own scope; not re-attempted here). | MOCK_CONFORMANCE only — `ENVIRONMENT_LIMITATION`/`DEFERRED` in every environment (no Letta server, per H.4, unchanged). |
| ConvoMem | **REAL_FOUNDATION_CONFORMANCE** — same real add/retrieve/reset path exercised for a real ConvoMem message, same LLM-free discipline. | MOCK_CONFORMANCE only — same `ENVIRONMENT_LIMITATION`. | MOCK_CONFORMANCE only — same. | MOCK_CONFORMANCE only — same. |

Only Mem0 was re-exercised for real conformance in this stage — the only one of the four
with a genuine, previously-established LLM-free real path (H.4's `infer=False` finding).
Graphiti/A-MEM/Letta's real-conformance status is unchanged from H.4 (not re-attempted;
their blockers are environment-level, not dataset-level, so re-testing them against
PerLTQA/ConvoMem specifically would not have produced new information).

## 13. Data integrity (Part 32)

```
git status --short   -> one modified file (extensions/identity.py, additive-only, +84/-0),
                         plus new untracked files under phase3/datasets/candidates/
                         {perltqa,convomem}/, phase3/evaluation/extensions/adapters/,
                         phase3/evaluation/foundations_real/, phase3/evaluation/tests/,
                         phase3/evaluation/datasets/*.md
git diff --stat       -> phase3/evaluation/extensions/identity.py | 84 ++++++++++
git diff --cached     -> empty (nothing staged)
```

No Phase 1 file touched. No Phase 2 file touched. No active dataset (`data/raw|processed|
metadata/`) touched. No existing H.1 candidate package (MemoryAgentBench/MemBench/
MemoryArena) touched. No metric, contract, or foundation-architecture file touched
except the purely-additive `identity.py` change. No secrets, credentials, or generated
caches were committed (`__pycache__` cleaned before each check).

## 14. Repository cleanup recommendation (NOT performed in this stage)

- **KEEP**: everything listed in §2's file table; `PHASE3_2_J1`/`J2`/`J3` documents;
  `j3_real_conformance_result.json` (genuine real-conformance evidence, worth preserving).
- **ARCHIVE**: none identified.
- **REMOVE**: none — no scratch/temporary artifact was left in the tracked tree (all
  external scratch state — `C:\Users\naish\cmdl2`, `j2tmp/`, `j3tmp` — was cleaned before
  this document was written and never committed).

Repository cleanup (the dedicated hygiene stage) may proceed after this document is
reviewed — not performed here, per this stage's explicit stop condition.
