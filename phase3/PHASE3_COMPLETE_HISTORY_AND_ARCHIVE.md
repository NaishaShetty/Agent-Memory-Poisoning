# Phase 3 Complete History and Archive

**Status: FINAL CLOSURE DOCUMENT.** This is the authoritative narrative record of Phase 3 of the MAMBench project, written at the point of formal Phase 3 closure and Phase 4 handoff. Where a fact could not be established from repository evidence available at closure time, this document says so explicitly rather than guessing.

---

## 1. Phase 3 Objective

Build and evaluate a memory-augmented question-answering agent against real, frozen conversational benchmarks (LoCoMo, LongMemEval), using real third-party memory foundations (Mem0, A-MEM) rather than mocks, with a canonical, auditable, provenance-preserving memory ledger underneath — and determine, through a disciplined sequence of validated iterations, the strongest agent architecture that can be scientifically justified on this hardware and this evidence.

## 2. Original Phase 3 Architecture

Per `phase3/README.md`'s own status line at the time of this closure, Phase 3's early stage tracking (stages A–J.4, labeled "3.2 complete") preceded the LLM+agent integration work ("3.3 — Real LLM + Agent Integration") that produced everything described from Section 4 onward. The foundational architecture established in that early stage: a canonical memory/event ledger substrate, a `MemoryFoundationAdapter` interface each real foundation (Mem0, A-MEM) implements, and a strict boundary contract (`phase3/evaluation/contracts/boundary.py`) preventing evaluator-only data (gold answers, gold evidence IDs) from leaking into what the agent sees.

## 3. Original Clean Agent / Memory Foundation

The `phase3_reference/clean_agent_v1/` directory holds the original reference implementation predating the `phase3/evaluation/` production track. It is explicitly historical/legacy (see Section 5 below) and is not depended on by any active Phase 3 code — confirmed by direct grep audit during this closure (Section 21).

## 4. Initial Memory Foundation Audit

Not established from available evidence beyond what Sections 6–10 document — no single "initial audit" report distinct from the H.1/H.2/H.3 mission sequence was identified as a separate artifact during this closure's repository search.

## 5. Audit Findings

Superseded by the specific H.1/H.2/H.3/H.4 findings below; no separate consolidated "findings" document was identified as distinct from those mission reports.

## 6. H.1 — Canonical Memory Ledger

`phase3/specification/PHASE3_3_H1_CANONICAL_MEMORY_LEDGER.md` — status **COMPLETE** (per the document's own header). Implementation report: `phase3/experiments/PHASE3_3_H1_IMPLEMENTATION_REPORT.md`. Canonical code: `phase3/evaluation/foundations/ledger.py` (`CanonicalMemoryLedger`, `CanonicalCollisionError`, `CanonicalAliasError`) and `phase3/evaluation/foundations/canonical.py` (`CanonicalMemoryRecord`). This ledger's collision-detection behavior was directly exercised (not just tested in isolation) during this session's own V5 and V3-Hybrid campaign work — a real `CanonicalCollisionError` was raised and correctly refused an overwrite when a campaign was resumed under a reused campaign_id after an interrupted run, exactly the behavior H.1 was built to guarantee.

## 7. H.2 — Canonical Event Ledger

`phase3/specification/PHASE3_3_H2_CANONICAL_EVENT_LEDGER.md` — status **COMPLETE AND FROZEN**. Canonical code: `phase3/evaluation/foundations/event_ledger.py` (`CanonicalEventLedger`, `CanonicalEventCollisionError`, `SingleOccurrenceViolationError`, `RetrievalResolutionViolation`) and `phase3/evaluation/foundations/canonical_event.py` (`CanonicalEvent`).

## 8. H.2-R / H.2-R2 — Experiment Boundaries

Remediation passes within the same H.2 specification document (§23–29 for H.2-R, §30–36 for H.2-R2). Implementation reports: `phase3/experiments/PHASE3_3_H2_REMEDIATION_REPORT.md` and `phase3/experiments/PHASE3_3_H2_R2_FINAL_HARDENING_REPORT.md`.

## 9. H.3 — Immutable Memory Versioning and Supersession

`phase3/specification/PHASE3_3_H3_MEMORY_VERSIONING.md` — status **COMPLETE**. Two follow-on fix missions exist: `PHASE3_3_H3_R_MISSION.md` ("Versioning Fix for Multi-Memory `derived` Events") and `PHASE3_3_H3_R2_MISSION.md` ("Versioning Fix for `derived` Events' Implied Lifecycle State"). Both mission briefs read as not-yet-started in their own text, but corresponding implementation reports (`PHASE3_3_H3_IMPLEMENTATION_REPORT.md`, `PHASE3_3_H3_R_IMPLEMENTATION_REPORT.md`, `PHASE3_3_H3_R2_IMPLEMENTATION_REPORT.md`) confirm all three were in fact completed. Canonical code: `phase3/evaluation/foundations/memory_versioning.py` (`SupersessionLedger`, `SupersessionRecord`, `CanonicalMemoryVersion`, `reconstruct_version_history`, `get_current_version`, `retire_memory`, `supersede_memory`).

## 10. Foundation Qualification

Real-adapter qualification harness: `phase3/evaluation/foundations_real/qualification_fixtures.py`, `qualification_harness.py`, `qualification_record.py`. Mission briefs for the H.4 series (A, AMEM_INSPECT_FIX, BC, D, E, F, G, WIRE) cover: counterfactual-influence measurement, an A-MEM `inspect_memory` fix, rejected/relationship-detection events, the foundation qualification gate itself, a content-level leakage gate, configuration fingerprinting, a `tainted_by` attack-propagation query, and live canonical event emission for Mem0. A separate research-track qualification exists: `PHASE3_RESEARCH_TRACK_RELATIONSHIP_DETECTION_QUALIFICATION.md`.

### Mem0

Real adapter: `phase3/evaluation/foundations_real/mem0_real_adapter.py` (`RealMem0Adapter`). Uses local, on-disk Qdrant + a local HuggingFace embedder (`sentence-transformers/all-MiniLM-L6-v2`) + `infer=False` (no LLM call ever made inside Mem0's own `add()` — confirmed directly from the adapter's own documented finding). Only importable inside the isolated `C:\h4venv` interpreter; confirmed functional via a direct smoke test (`initialize → reset → shutdown`, all `AVAILABLE`) during this closure.

### A-MEM

Real adapter: `phase3/evaluation/foundations_real/amem_real_adapter.py` (`RealAMemAdapter`). Also only importable inside `C:\h4venv`; confirmed functional via the same smoke-test pattern during this closure.

### Deferred foundations

Not established from available evidence during this closure pass — no deferred-foundation list was located distinct from the qualification mission briefs themselves.

## 11. Baseline Campaigns

LoCoMo and LongMemEval are both real, wired-in datasets — confirmed directly (not assumed) during this session's own V5 architecture work: LongMemEval has dataset processing (`preprocessing/datasets/longmemeval.py`), raw/processed data, a Phase 3 dataset profile, and campaign integration (`campaign_formal_runner.py::run_formal_c_longmemeval`). All formal campaign work actually executed and reported on in this document (V1 through V3-Hybrid) used the **LoCoMo** dataset specifically, at the frozen 120-task formal sample (seed 33005, via `campaign_sampling.build_formal_sample`). LongMemEval formal execution status beyond dataset wiring is not established from evidence reviewed during this closure. Provenance graph statistics beyond what individual campaign reports already state are not established from available evidence in this consolidated pass.

## 12. V1

V1 is the frozen baseline agent: single-pass generate-and-stop, `run_agent_task()` in `phase3/evaluation/agent_runtime/runner.py`, and Condition A (`run_condition_a`) in `campaign_formal_runner.py`, both reused unchanged by every subsequent version through V3-Hybrid. Frozen dataset: `phase3/experiments/results/canonical_store/dataset_full/clean_agent_dataset_locomo_120x2.json`. Decision: retained as shared, canonical infrastructure for Condition A across all later versions — never modified.

## 13. V2

V2 = V1 + hybrid retrieval/selection (`hybrid_selection.py`: pool=20, top-8, weights cosine 0.5/token-overlap 0.3/entity-overlap 0.2, fixed in advance) + timestamp-prefixed evidence for Condition B. Full campaign results: `phase3/experiments/results/canonical_store/v2_candidate/`. A real, disclosed run-to-run non-determinism was observed and documented across V2/V3 runs (Condition A shifted 3.3%→5.0% between otherwise-identical runs) — this reproducibility anomaly is explicitly preserved as known evidence, not treated as a bug to hide. Decision: superseded by V3's addition of temporal resolution; V2's hybrid retrieval/selection mechanism itself was carried forward unchanged into V3 and V3-Hybrid.

## 14. V3

V3 = V2 + deterministic relative-time-expression resolution (`foundations/temporal_resolution.py`), applied to both Condition B and Condition C evidence. Motivation: reading real V2 `TEMPORAL_REASONING_FAILURE` cases found the agent already had the correct timestamp but never performed the arithmetic a phrase like "last week" requires — this module removes that arithmetic burden by resolving it in code, appending an auditable annotation, never silently rewriting the original text. Validated in `PHASE3_V3_ROUND1/2/3_*.md` at n=24 with hand-verified real gains and zero real regressions before full-scale promotion. Full campaign results: `phase3/experiments/results/canonical_store/v3_candidate/` (`clean_agent_dataset_v3_locomo_120x2.json`). This is the dataset all "V3 baseline" comparisons in this document and in V4/V5 work are measured against.

## 15. V3-Hybrid — FINAL VALIDATED COMPARISON

**V3-Hybrid is the final, canonical Phase 3 memory foundation** (see Section 19). It composes: V3's unchanged Condition A, V3's unchanged Condition C (both foundations), and V3's Condition B evidence construction plus one addition — a bounded draft→verify→[revise] reasoning step, applied to Condition B only.

The following is the authoritative, final, full-scale (n=120) V3-Hybrid result table, produced after a real engineering defect was found and fixed (58/120 Mem0-condition records had silently recorded `AGENT_EXECUTION_FAILURE` — a null answer — under a misleadingly-"successful" evaluation status, traced to server instability during an interrupted, resumed campaign; the affected tasks were identified, cleared from the checkpoint, and regenerated cleanly before this table was produced). This table is not to be overwritten or reinterpreted:

**Condition A (no memory):**
- normalized: 4.2%
- multi-reference: 5.0%
- content recall: 3.3%
- NLI entailment: 14.2%
- LLM judge: 16.7%

**Condition B (gold evidence):**
- normalized: 56.7%
- multi-reference: 59.2%
- content recall: 65.0%
- NLI entailment: 75.8%
- LLM judge: 81.7%

**Condition C — Mem0:**
- normalized: 45.8%
- multi-reference: 46.7%
- content recall: 55.0%
- NLI entailment: 73.3%
- LLM judge: 82.5%

**Condition C — A-MEM:**
- normalized: 48.3%
- multi-reference: 49.2%
- content recall: 57.5%
- NLI entailment: 69.2%
- LLM judge: 85.8%

This is labeled the **FINAL VALIDATED V3-HYBRID COMPARISON**.

Supporting evidence for the verification step's scope: on Condition B specifically, `V5_VERIFIED`'s bounded-verification mechanism (see Section 17) produced a real, reproduced gain over plain V3 at three independent scales (n=15, n=50, n=120), confirmed on a fresh dataset after a system-prompt parity bug was found and fixed. On Condition C, the identical mechanism was tested at full n=120 scale on both foundations and found to **not** reliably help — flat on A-MEM, a measured regression on Mem0 (judge 93→88/120) — which is why V3-Hybrid restricts verification to Condition B only and makes no claim of universal benefit.

## 16. V4 Diagnosis

V4 was never implemented as a runner or agent — it exists entirely as a diagnostic and roadmap document, `PHASE3_V4_DIAGNOSIS_AND_85_90_ROADMAP.md`, plus a small number of exploratory pilot scripts. It investigated why V3 was capped at ~47–56% (normalized) despite retrieval appearing strong, via a full B-vs-C attribution waterfall computed against the real V3 production checkpoint. Key finding, after fixing a real bug (see below): retrieval loss ≈0.8% and selection loss ≈5.0% of the total B-vs-C gap — together under 6% — while shared-reasoning loss (≈21.7%) and representation/generation loss (≈17.5%) dominated. This directly established that retrieval/selection was **not** the Phase 3 bottleneck, a finding subsequent V5 work explicitly built on rather than re-litigating.

**The assembler bug**: `dataset_record_assembler.py::_condition_c_summary()` was propagating a `failure_stage` value computed from raw, foundation-space (unresolved) memory IDs instead of the identity-resolved value already computed elsewhere in the trace — an id-space mismatch that made retrieval look like it was failing almost universally, when it wasn't. Fixed with a minimal, disclosed, backward-compatible change (verified with 5 new unit tests) before the corrected attribution waterfall above was computed. This fix did not touch or regenerate any frozen V1/V2/V3 dataset file.

**Evaluator artifacts newly characterized in V4**: digit zero-padding mismatches ("3" vs "03"), date-range-vs-point-estimate gold phrasing, and paraphrase drift below the content-recall threshold — motivating the additive metric work carried into V5 (Sections 17, 22).

**The unresolved verification-transfer issue**: V4's own roadmap proposed a hedging fix (§15.3) that was later tested twice in this project's history (a prompt instruction, then a demonstrated few-shot example) and confirmed to backfire both times by giving the model one over-usable refusal phrase. This is exactly why V5's later, differently-designed verification mechanism (a separate check-and-revise call, never a refusal phrase handed to the answer model) was built the way it was — and why, even having avoided that specific failure mode, it *still* did not transfer reliably to Condition C. Why it doesn't transfer was never root-caused; this is an explicit, carried-forward unresolved question (Section 22).

**Why V4 was not promoted**: it produced no runnable architecture of its own — its real contributions (the assembler fix, the corrected attribution waterfall, the evaluator-artifact characterization, and the roadmap that led to V5's verification mechanism) were all carried forward into V5 and V3-Hybrid rather than V4 itself being a candidate.

## 17. V5

**Architecture**: V5 explored two independent additions on top of V3's unchanged retrieval/selection: (a) a structured-memory layer (`v5_structured_memory.py` — LLM-extracted entity/attribute/value facts, deterministic entity normalization, consolidation with full provenance back to source memory IDs) targeting multi-hop/aggregation questions, and (b) a bounded draft→verify→[revise] reasoning pipeline (`v5_reasoning_pipeline.py`) targeting a "quote-then-hedge" pattern found twice independently this session (the model states a fact correctly, then still hedges instead of committing to it as the answer).

**Structured memory — rejected**: piloted and found to regress general performance (the structured-facts block distracted the model on directly-answerable questions it otherwise got right) and, on direct targeted testing, failed to fix even its own motivating case (a multi-hop child-counting question) — Condition B's gold evidence for that task turned out to contain only one relevant turn, meaning the hypothesized scattered-evidence problem wasn't even present in the tested condition. Not carried into V3-Hybrid.

**Bounded verification — the one piece retained**: validated with a real, reproduced gain on Condition B (see Section 15). A real regression was found and fixed along the way: `V5_BASE`'s draft system prompt had silently drifted from V1-V4's exact prompt (dropping an explicit anti-verbosity instruction), which fully explained an initially-alarming full-campaign result where `V5_VERIFIED` appeared to underperform V3 on every metric. After the prompt was corrected to match V1-V4 verbatim, the verification mechanism's real, positive effect on Condition B became visible and was confirmed at three scales.

**Why V5-verified was interesting but not superior to V3-Hybrid as a whole**: verification alone (without structured memory) is exactly what V3-Hybrid promotes — V5 as a complete package (with structured memory included) was not superior to the narrower V3-Hybrid composition, because structured memory's regression outweighed any Condition-C-side benefit it might have offered (and no such benefit was ever established).

**Why V5 was not promoted as a whole**: its Condition C performance (with or without verification) did not exceed plain V3's, and its structured-memory component was a net negative. V5's validated, positive contribution (the verification mechanism) was extracted and promoted individually as part of V3-Hybrid; V5 as an integrated architecture was not.

**Full campaign evidence**: `phase3/experiments/results/canonical_store/v5_candidate/` (`clean_agent_dataset_v5_verified_locomo_120x2.json`), plus the corrected-prompt re-validation runs under `v5-c-corrected-*` and `v5-stage2-scaleup*` directories (all retained as real experimental evidence, including the runs superseded by later corrections — see Section 26).

## 18. Rejected Approaches

| Approach | Why rejected |
|---|---|
| Structured memory (V5) | Regressed general Condition-B/C performance; failed its own motivating multi-hop case on direct test |
| No-template hedging fix (prompt instruction) | Confirmed to make the model reach for one over-usable refusal phrase more often, including on cases it previously answered correctly |
| No-template hedging fix (few-shot demonstration) | Same failure mode as above, demonstrated a second time |
| Format-only terseness fix | Measured near-zero effect (0/8 normalized, 1/8 content-recall movement) — the gap it targeted was structural (annotator-paraphrase vs. evidence-wording), not fixable by changing model verbosity |
| Bounded answer-completeness check (V4 §15.2) | A required-in-advance quantification pass found only 2–3 genuinely completeness-fixable cases out of 26 candidates — below the roadmap's own 5-case promotion threshold |
| Bounded verification on Condition C | Flat on A-MEM, a measured regression on Mem0 at full n=120 scale |
| A synonym/paraphrase dictionary (evaluator-side) | Rejected in design discussion before implementation — context-free synonym credit risks crediting genuinely wrong answers that merely share a word |
| A smaller "thinking-capable" model (Qwen3-4B-Thinking) | Piloted and found to produce 7/15 (47%) empty/truncated answers on Condition C under a realistic token budget — a real, measured feasibility failure, not a preference |

## 19. Final Phase 3 Decision

**V3-HYBRID IS THE FINAL CANONICAL PHASE 3 MEMORY FOUNDATION.**

## 20. Final Architecture

- **Model**: Qwen3-8B, Q4_K_M quantization, non-thinking mode, served via a pinned `llama-server.exe` build (b10717, commit a32af33de) over its OpenAI-compatible HTTP API. `enable_thinking=False`, `temperature=0`, `seed=42`, `n_ctx=4096`.
- **Memory foundations**: Mem0 (real adapter, local on-disk Qdrant + local HuggingFace embeddings, `infer=False`) and A-MEM (real adapter), both requiring the isolated `C:\h4venv` interpreter.
- **Retrieval**: hybrid rerank over a pool of 20 candidates down to a top-8 selection; weights cosine 0.5 / token-overlap 0.3 / entity-overlap 0.2, fixed in advance, unchanged since V2.
- **Temporal resolution**: deterministic relative-time-expression resolution applied to selected evidence in both Condition B and Condition C, unchanged since V3.
- **Reasoning**: Condition A and Condition C use V1/V3's original single-pass generate-and-stop behavior, unmodified. Condition B uses the canonical bounded draft→verify→[revise] pipeline (`canonical_verified_reasoning.py`, promoted from validated V5 logic — see Section 17 and the isolation note in Section 25).
- **Canonical entry point**: `phase3/evaluation/agent_runtime/campaign_v3_hybrid_runner.py`.

## 21. Phase 3 Contracts

- **Memory/event/provenance/lifecycle/identity**: `phase3/evaluation/foundations/{ledger,event_ledger,canonical,canonical_event,memory_versioning,provenance_graph}.py`, `phase3/evaluation/agent_runtime/identity.py`. Two identity-resolution strategies exist: `STRATEGY_METADATA_LOOKUP` (Mem0, foundation-space UUIDs resolved via stored metadata) and `STRATEGY_DIRECT_ASSIGNMENT` (A-MEM, foundation id equals canonical id already).
- **Retrieval/selection**: `phase3/evaluation/foundations/hybrid_selection.py`.
- **Execution/agent boundary**: `phase3/evaluation/contracts/boundary.py` (`AgentVisibilityViolation`) — enforced on every condition's constructed context before generation.
- **Evaluation**: `phase3/evaluation/agent/{outcomes,normalized_correctness,content_recall_correctness,date_normalized_correctness,number_word_normalized_correctness,nli_entailment_correctness,multi_reference_correctness,llm_judge_correctness}.py` — eight correctness metrics, always reported side by side, never substituted for one another.
- **Leakage**: `phase3/evaluation/security/content_leakage.py`, invoked on every task/condition via `_content_leakage_scan()` in every campaign runner including the canonical V3-Hybrid one.
- **Reproducibility**: `phase3/evaluation/security/reproducibility.py` (fingerprinting), `phase3/evaluation/foundations_real/environment.py` (pinned package versions).

## 22. Final Limitations

**Model limitations**: Qwen3-8B non-thinking mode has no scratch space to aggregate facts across turns in one pass; premature commitment to a hedge even when the fact is directly stated was observed and only partially mitigated (Condition B only) by verification.

**Reasoning limitations**: shared-reasoning and representation/generation loss (≈21.7% + ≈17.5% of the B-vs-C gap in the V4 attribution) remain the dominant unresolved source of error; not closed by any change made through V3-Hybrid.

**Multi-hop limitations**: unresolved. The structured-memory attempt to fix this failed both generally and on its own motivating case (Section 17).

**Retrieval residuals**: small and already well-characterized — ≈0.8% retrieval loss, ≈5.0% selection loss of the total B-vs-C gap (V4 attribution waterfall). Not a priority for further work.

**Evaluator limitations**: normalized/content-recall have a structural ceiling on catching genuine paraphrases that no further narrow, deterministic fix fully closes — confirmed directly by testing multi-reference gold answers (modest, real, low-single-digit-point gains) and an NLI-entailment classifier (a real, larger recovery — 63% of the normalized-vs-judge gap on held-out data, ~70–76% raw score on the final V3-Hybrid table — but still short of LLM-judge). The gap between string metrics and judge is now well-quantified but not eliminated.

**Dataset/annotation limitations**: LoCoMo gold-evidence links sometimes point to a turn that does not itself contain the stated fact (a different speaker states it in an adjacent turn not included in the evidence set) — directly verified for at least one real case during this project's diagnostic work. This is a benchmark-annotation property, not an agent failure, and must not be reinterpreted as one.

**Reproducibility limitations**: a real, measured, disclosed run-to-run non-determinism exists even at `temperature=0` (Condition A shifted 3.3%→5.0% between otherwise-identical V2/V3 runs). GPU-side floating-point/embedding non-determinism and retrieval tie-breaking can plausibly contribute to answer variation across runs; this was never fully root-caused, and deterministic reproducibility must not be claimed without that caveat.

**Hardware limitations**: a single RTX 4050-class GPU (6GB VRAM), already ~96% utilized by the one running Qwen3-8B instance, with no headroom for a second concurrent model. This is why no stronger/larger model was used, and why a smaller "thinking-capable" model was tested and rejected (Section 18) rather than simply not considered.

**Architectural limitations**: verification's non-transfer to Condition C was measured but never root-caused (a real, disclosed open question, not a solved one).

**Unresolved engineering issues discovered during this closure**: (1) `campaign_v3_hybrid_runner.py` was found, during this closure audit, to import `V5_VERIFIED`/`run_condition_b_v5` directly from `campaign_v5_runner.py` — a real isolation violation, fixed during this same closure pass by promoting the underlying (unmodified) logic to `canonical_verified_reasoning.py` and reimplementing Condition B against shared, non-versioned primitives only; a regression test (`test_hybrid_runner_has_zero_v5_imports`) was added so this cannot silently reoccur. (2) `PROCESS DOCUMENTATION.docx`, a file tracked since the original Phase 1/2 baseline commit, is currently deleted in the working tree; this deletion is not attributable to any action taken during this closure session and was not silently accepted — it is flagged here for the user's own review and decision (restore via `git checkout -- "PROCESS DOCUMENTATION.docx"` if unintentional; this closure did not perform that restoration itself, per the instruction to avoid destructive/ambiguous git operations without explicit authorization).

**Observability limitations**: `used_memory_ids` (causally-observed, as opposed to merely retrieved/selected, memory use) is not populated anywhere in the runtime — disclosed as a known absence in every campaign runner's own trace construction, never fabricated.

**Lifecycle/provenance limitations**: Not established from available evidence during this closure pass whether any residual gap exists between "implemented" and "authoritative at runtime" for the versioning/supersession mechanisms beyond what Sections 6–9's own implementation reports already document; a full independent re-audit of runtime authority was not performed as part of this closure (see Section 28 for what was and was not verified).

## 23. Phase 4 Interface

Phase 4 can depend on, directly and without further verification:
- `phase3/evaluation/agent_runtime/campaign_v3_hybrid_runner.py` — the sole canonical entry point (`run_condition_a`, `run_condition_b_hybrid`, `run_condition_c_v3_mem0`, `run_condition_c_v3_amem`, `V3_HYBRID_STORE`, `assemble_dataset_records`).
- `phase3/evaluation/agent_runtime/canonical_verified_reasoning.py` — the canonical bounded-verification reasoning primitive.
- The shared, non-versioned infrastructure listed in Section 21 (contracts, metrics, ledgers, retrieval, temporal resolution).
- The real Mem0/A-MEM adapters under `phase3/evaluation/foundations_real/` (requires the isolated `C:\h4venv` interpreter for any real foundation call).
- The frozen V3-Hybrid dataset and results under `phase3/experiments/results/canonical_store/v3_hybrid_candidate/`.

## 24. Phase 4 Must NOT Assume

- That retrieval/selection is a solved problem requiring zero further attention if new task distributions are introduced — it was found sufficient for LoCoMo at this scale, not proven universally sufficient.
- That verification (or any V3-Hybrid mechanism) provides a benefit on Condition C — it does not, on the evidence gathered.
- That normalized/content-recall scores reflect true semantic correctness — they systematically under-count it; LLM-judge and NLI-entailment are closer, but neither is asserted as ground truth either.
- That 85–90% correctness under strict string metrics is achievable on this model/hardware — it was explicitly assessed as not realistic under strict normalized matching.
- That answers are deterministic run-to-run — they are not, provably.
- That `used_memory_ids` or any causal-usage signal is available — it is not populated.
- That V1/V2/V4/V5 code paths are safe to import into Phase 4 — none of them are the canonical foundation, and V5 in particular was found to have leaked into what should have been a clean V3-Hybrid dependency chain (now fixed).
- That LoCoMo's gold-evidence annotations are always complete or correctly attributed — they are not, in at least one directly-verified case.

## 25. Full Artifact Map

- **Canonical runner**: `phase3/evaluation/agent_runtime/campaign_v3_hybrid_runner.py`
- **Canonical reasoning primitive**: `phase3/evaluation/agent_runtime/canonical_verified_reasoning.py`
- **Reused shared infra (V1/V3-origin, unmodified)**: `campaign_formal_runner.py` (`run_condition_a`), `campaign_v3_runner.py` (`run_condition_c_v3_mem0`, `run_condition_c_v3_amem`), `dataset_record_assembler.py`, `hybrid_selection.py`, `temporal_resolution.py`, `messages.py`
- **Foundations**: `ledger.py`, `event_ledger.py`, `canonical.py`, `canonical_event.py`, `memory_versioning.py`, `provenance_graph.py`, `identity.py`, `adapter.py`
- **Real adapters**: `foundations_real/mem0_real_adapter.py`, `foundations_real/amem_real_adapter.py`
- **Evaluation metrics (8, additive, side-by-side)**: `outcomes.py` (exact), `normalized_correctness.py`, `content_recall_correctness.py`, `date_normalized_correctness.py`, `number_word_normalized_correctness.py`, `nli_entailment_correctness.py`, `multi_reference_correctness.py`, `llm_judge_correctness.py`, plus `semantic_similarity_correctness.py` (built earlier, embedding-based, disclosed negation-blindness limitation, not part of the primary 8 reported for V3-Hybrid)
- **Frozen datasets**: `results/canonical_store/{dataset_full,v2_candidate,v3_candidate,v5_candidate,v3_hybrid_candidate}/`
- **Historical/experimental (retained, not canonical)**: `campaign_v2_runner.py`, `campaign_v5_runner.py`, `v5_reasoning_pipeline.py`, `v5_structured_memory.py`, `hybrid_selection_runner.py`, everything under `phase3/experiments/research_variant/`
- **Legacy (retained, not canonical, no active dependency)**: `phase3_reference/` (all subdirectories)

## 26. Cleanup / Deletion Manifest

**No files were deleted during this closure.** Per the closure's own governance rules ("if there is ambiguity about a file: KEEP IT"), and given that every candidate examined either (a) contains real experimental evidence (the multiple `v5-c-corrected-*`, `v5-stage2-scaleup*`, and `3.3-V3-HYBRID-FULL-R2` through `-R5` result directories, which document the real engineering incidents — server crashes, a canonical-collision bug, a silent-failure bug — encountered and fixed during this project's own execution) or (b) is a generated cache directory whose deletion has zero scientific or reproducibility value but also zero urgency (`__pycache__/`, `.pytest_cache/`), this closure pass made a conservative decision: document the candidates rather than delete them, so the user can review and authorize deletion explicitly. Candidates identified, not deleted:

| Candidate | Type | Reason not deleted |
|---|---|---|
| `__pycache__/` (multiple, under `phase3/evaluation/*`) | Generated bytecode cache | Zero risk to delete, but zero closure-relevant urgency either; left for the user's own routine cleanup |
| `.pytest_cache/` (repo root) | Generated test cache | Same as above |
| `3.3-V3-HYBRID-FULL-R2` through `-R5` (canonical_store) | Superseded partial/interrupted campaign runs | Real evidence of the actual engineering incidents this closure documents (Section 22); deleting would remove traceability of a real, disclosed defect-and-fix story |
| `v5-c-corrected-*`, `v5-stage2-scaleup*` (canonical_store) | V5 re-validation pilot runs | Real evidence supporting the Section 17 V5 findings; not redundant with any single retained summary |
| Empty `supersessions/`/`events/` subdirectories under qualification/campaign result trees | Possibly-expected empty output (a "no supersessions occurred" run) | Ambiguous whether empty-by-design or a defect; per the explicit rule, ambiguity means keep |

## 27. Retained Historical Evidence

All items in Section 18 (Rejected Approaches), all full campaign datasets for V1 through V5 (Section 25), and every `PHASE3_V*` diagnosis/report document under `phase3/experiments/research_variant/` are retained in full. `phase3_reference/` is retained in full as historical/legacy material per the closure's own explicit instruction not to redesign, conform, or prune it.

## 28. Final Verification

- Full regression suite (`phase3/evaluation/tests/`): see the accompanying closure report's Test Results section for the exact pass/skip/fail counts from the final run performed after the V5-isolation fix.
- Targeted canonical/leakage/provenance/ledger/versioning/identity test subset: 444 passed, 11 skipped, 0 failed (run independently during this closure, isolating exactly the mechanisms Sections 6–9 and 21 describe).
- Mem0 and A-MEM adapter smoke tests (`initialize → reset → shutdown`, isolated `C:\h4venv` interpreter): both `AVAILABLE`, confirmed during this closure.
- A full independent re-audit of every H.1–H.4 mechanism's runtime authority (the "implemented vs. authoritative at runtime" distinction the closure's audit brief calls for) beyond what the passing test suite already exercises was **not** separately re-derived from first principles in this pass — the test suite's passing state is real, direct evidence these mechanisms function as implemented, but a fresh line-by-line re-audit of every historical H.1–H.4 report against current code was outside what this closure pass completed. This is disclosed explicitly rather than implied as done.

## 29. Reproducibility Instructions

1. Model: `Qwen/Qwen3-8B-GGUF`, file `Qwen3-8B-Q4_K_M.gguf`, served via the pinned `llama-server.exe` build (b10717, commit a32af33de) — real, sha256-checked identity in `phase3/evaluation/llm/provider.py::QWEN3_8B_Q4_K_M_IDENTITY`. Launch flags: `-ngl 99 --ctx-size 16384 --parallel 4`.
2. Generation config: `temperature=0`, `seed=42`, `enable_thinking=False`, `n_ctx=4096`; `max_tokens=64` for V1–V3's own conditions, `max_tokens=256` for V3-Hybrid's Condition B (required for the verify/revise stage to have room to restate an answer — confirmed necessary by direct A/B test).
3. Foundations: run any Mem0/A-MEM code under the isolated `C:\h4venv` interpreter, never the main repo interpreter (confirmed: `mem0ai`/A-MEM are not importable in the main interpreter).
4. Sample: `campaign_sampling.build_formal_sample(120)`, seed 33005, LoCoMo dataset.
5. Entry point: `phase3/evaluation/agent_runtime/campaign_v3_hybrid_runner.py`, driven by `phase3/experiments/research_variant/run_v3_hybrid_full_campaign.py` (checkpointed per-pool; safe to interrupt and resume, though a genuinely fresh `campaign_id` is required after any interrupted-mid-pool resume, per the real collision incident documented in Section 22).
6. Known non-determinism: expect small run-to-run variation even with the above fixed; do not expect byte-identical reproduction.

## 30. Final Phase 3 → Phase 4 Handoff

Phase 3 closes with V3-Hybrid as the single, unambiguous, canonical memory foundation: a validated composition of V3's unmodified retrieval/selection/temporal-resolution pipeline and a narrowly-scoped, evidence-gated bounded verification step applied only where it was shown to help. Every rejected alternative, every measured limitation, and every real engineering defect found along the way (including one found and fixed during this very closure pass) is preserved as disclosed evidence in this document and its supporting reports, not hidden to present a cleaner story. Phase 4 begins against this foundation with a clean, isolated dependency chain, a passing test suite, and an explicit, non-exhaustive list of what remains genuinely open.
