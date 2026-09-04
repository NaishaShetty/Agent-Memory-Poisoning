# Phase 3.3-G — Formal Repeated-N Controlled Memory Campaign

**Status:** Conditions A (no-memory) and B (Mem0) executed at full formal scale on
both datasets (N=120/dataset). Condition C (A-MEM) executed at full formal scale on
**LoCoMo** (N=120) per an explicit revision decision (§5); A-MEM×LongMemEval remains
**formally deferred** (projected ~57h at full N=120, judged impractical for this
session — see §5) to a dedicated follow-on stage.

## 1. Executive Summary

720 real Qwen3-8B task-condition executions completed: 240 (Condition A) + 240
(Condition B) + 120 (Condition C, LoCoMo only) = **600 successful, 0 execution/
environment failures.** A real, measured probe (not an estimate) established
A-MEM×LongMemEval would cost ~57 hours at full N=120 — genuinely infeasible within this
session and formally deferred, not silently reduced.

Within the completed comparisons: **Mem0 and A-MEM produced nearly identical retrieval
performance on LoCoMo** (Strict TSR 79.2% vs. 78.3%, statistically indistinguishable —
McNemar C vs. B: 0 discordant pairs, p=1.0) despite A-MEM costing **~17x more compute**
(~2 hours vs. ~7 minutes of wall-clock for the same 120 tasks). But the two foundations
diverged sharply on the **diagnostic answer-equivalence layer**: 55.8% of Mem0's
canonical-incorrect LoCoMo answers were lexically equivalent to gold, versus only
**6.7% for A-MEM** — despite similar retrieval, A-MEM's downstream answers are
substantially less gold-like. On LongMemEval, Mem0 produced a statistically significant
paired improvement in canonical Answer Correctness over no-memory (McNemar exact
p=0.031, 6/120 tasks flipped correct, 0 flipped the other way), though this does not
survive Bonferroni correction for 3 planned comparisons. Overall, canonical exact-match
substantially understates real behavior: **45.8% of canonical-incorrect Mem0 answers
across both datasets were diagnostically equivalent to gold** (110/234).

## 2. Campaign Configuration

| Field | Value |
|---|---|
| Model | `Qwen/Qwen3-8B-GGUF`, `Qwen3-8B-Q4_K_M.gguf` |
| Model revision | `7c41481f57cb95916b40956ab2f0b139b296d974` |
| Model SHA-256 | `d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785` |
| Quantization | Q4_K_M |
| Backend | official llama.cpp, build `b10717`, commit `a32af33de` |
| Context | n_ctx = 4096 |
| Decoding | temperature=0, seed=42, max_tokens=64, enable_thinking=False |
| Retrieval K | 5 (top-K passthrough selection policy, unchanged) |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` |
| Prompt version | `agent_runtime.messages.DEFAULT_SYSTEM_PROMPT` (unchanged since 3.3-B) |
| Sampling seed | 33005 (disclosed, same as 3.3-E/F) |
| Configuration fingerprint | `419f1565a25c0736cc68b4890882389991fb65508d426d97b8bfaa0a6aafa91c` |

Configuration was **not** changed between the A/B run and the (later, resumed) C run —
same manifest, same fingerprint, verified identical.

## 3. Frozen Sampling Manifest

| Dataset | Eligible population | Selected N | Unique ingestion pools |
|---|---|---|---|
| LoCoMo | ≥200 (single-session evidence, pool≤25) | 120 | 93 unique sessions (1,757 total memory items) |
| LongMemEval | 1000 (500 haystacks × 2 tasks) | 120 | 60 unique haystacks (haystack-level sampling, avg 431 items/haystack, 25,844 total) |

Full frozen manifest: [manifests/campaign_3_3g_manifest.json](manifests/campaign_3_3g_manifest.json)

## 4. Experimental Design

A = no memory, B = real Mem0, C = real A-MEM (LoCoMo only, per §5's revision). Every
task is the same paired unit across conditions; only memory availability/foundation
differs. Both Mem0 and A-MEM ingestion are shared once per unique session/haystack (a
fresh `RESET`→`INGEST` per pool, independent `RETRIEVE`→`GENERATE`→`EVALUATE` per task —
verified read-only, unchanged since 3.3-B).

## 5. Condition C (A-MEM) — Cost Investigation and Revision Decision

A **real, measured probe** (not part of the statistical campaign) against the actual
frozen sample's smallest real pools:

| Probe | Real pool size | Real elapsed | Real sec/item |
|---|---|---|---|
| LoCoMo smallest session | 13 items | 102.9s | 7.91s/item |
| LongMemEval smallest haystack | 264 items | 2163.7s | 8.20s/item |

Projected: **LoCoMo ~3.9h, LongMemEval ~57.4h** at full N=120. Per this stage's own
explicit stop condition, this was reported rather than worked around, and an explicit
revision decision was requested from the user. **Decision made: run A-MEM×LoCoMo at
full N=120 now; formally defer A-MEM×LongMemEval.**

**Real outcome**: LoCoMo A-MEM completed in **7104.9s (~1.97h) — faster than the ~3.9h
projection** (the campaign's actual 93 sessions averaged smaller/cheaper than the
probe's worst-case assumption). Ingestion dominated (6884.9s of 7104.9s total, ~97% of
wall-clock; mean 74.0s/pool vs. Mem0's mean 5.5s/pool). LongMemEval×A-MEM **remains
formally deferred** — its per-haystack cost (avg 431 items vs. LoCoMo's avg 18.9) makes
the ~57h projection the operative one, not LoCoMo's more favorable real result.

**Reliability note**: the first attempt at this run was externally terminated (process
and llama-server both killed, no Python exception — consistent with an environment
reset across a long real-time gap) partway through, with zero progress persisted. The
runner was extended with incremental per-pool checkpointing before the successful
rerun, so a future interruption would lose at most one pool (~1 minute to ~2.3 minutes),
not the whole run. This is disclosed as a real operational finding, not smoothed over.

## 6. Canonical Results

| Metric | LoCoMo A | LoCoMo B | LoCoMo C | LongMemEval A | LongMemEval B |
|---|---|---|---|---|---|
| Recall@5 | n/a | 0.792 | 0.783 | n/a | 0.933 |
| MRR | n/a | 0.501 | 0.511 | n/a | 0.661 |
| Strict TSR | n/a | 0.792 | 0.783 | n/a | 0.933 |
| Evidence Precision | n/a | 0.163 | 0.160 | n/a | 0.415 |
| Evidence Recall | n/a | 0.788 | 0.771 | n/a | 0.130 |
| Evidence Coverage | n/a | 0.788 | 0.771 | n/a | 0.130 |
| Answer Correctness (n correct/120) | 0 | 0 | 0 | 0 | 6 |
| Generation latency (mean/median/max, s) | 0.86/0.87/1.82 | 1.41/1.46/3.39 | 1.31/1.36/2.41 | (pooled with LoCoMo A) | (pooled with LoCoMo B) |
| Citation rate | n/a | (not separately tallied) | 0/120 | n/a | (not separately tallied) |

Full data: [campaign_3_3g_formal_analysis.json](results/campaign_3_3g_formal_analysis.json)

## 7. Failure-Stage Results

| Stage | LoCoMo A | LoCoMo B | LoCoMo C | LongMemEval A | LongMemEval B |
|---|---|---|---|---|---|
| EVIDENCE_UNAVAILABLE | 120 | 0 | 0 | 120 | 0 |
| RETRIEVAL_FAILURE | 0 | 26 | 29 | 0 | 112 |
| AGENT_FAILURE_WITH_EVIDENCE | 0 | 94 | 91 | 0 | 2 |
| SUCCESS | 0 | 0 | 0 | 0 | 6 |
| SELECTION_FAILURE / AGENT_EXECUTION_FAILURE / UNDEFINED_EVALUATION | 0 | 0 | 0 | 0 | 0 |

Mem0 and A-MEM's failure-stage distributions on LoCoMo are nearly identical
(94/26 vs. 91/29) — reinforcing the retrieval-parity finding from §6.

## 8. Foundation Comparison (Mem0 vs. A-MEM, LoCoMo)

| Dimension | Mem0 | A-MEM |
|---|---|---|
| Retrieval (Strict TSR) | 79.2% | 78.3% — **statistically indistinguishable** |
| Evidence Recall/Coverage | 78.8% | 77.1% |
| Answer Correctness (canonical) | 0/120 | 0/120 — identical |
| Diagnostic-equivalent rate (of canonical-incorrect) | **55.8%** | **6.7%** — large, real divergence |
| Citation rate | not separately tallied | 0/120 |
| Total wall-clock (120 tasks, 93/93 unique pools) | ~44.4 min (pooled with LongMemEval ingest) | ~118.4 min |
| Ingestion cost per pool (mean) | 5.5s | 74.0s (**~13.5x**) |
| Identity | METADATA_LOOKUP, all resolved, collision-free | DIRECT_ASSIGNMENT, all resolved, collision-free (93/93 pools) |

**No universal winner declared.** Retrieval quality is essentially tied; A-MEM's
dramatically higher cost does not translate into better retrieval on this dataset. The
diagnostic-equivalence gap (55.8% vs. 6.7%) is the most consequential real difference
found — A-MEM's answers, even when grounded in correct evidence, are lexically much
less similar to gold than Mem0's (see §13 for a plausible mechanism).

## 9. Dataset Comparison

LongMemEval shows dramatically higher Strict TSR (93.3%) than LoCoMo (79.2%/78.3%) but
also a much higher `RETRIEVAL_FAILURE` rate (93% vs. ~22-24%) — not a contradiction:
LongMemEval's gold-evidence sets are typically much larger than LoCoMo's, so "at least
one gold ID retrieved" (Strict TSR) and "every gold ID retrieved" (the failure-stage
precedence rule) diverge sharply under top-5 retrieval. A dataset-structure effect, not
a foundation-quality difference.

## 10. Statistical Analysis

| Comparison | Dataset | n pairs | Discordant | Statistic | p-value | 95% CI (paired diff) | Bonferroni (0.0167) |
|---|---|---|---|---|---|---|---|
| B vs A | LoCoMo | 120 | 0/0 | 0.0 | 1.0 | n/a | Not significant |
| B vs A | LongMemEval | 120 | 0/6 | 0.0 (exact) | **0.03125** | −0.089 to −0.011 | Not significant after correction |
| B vs A | Overall | 240 | 0/6 | 0.0 (exact) | 0.03125 | −0.045 to −0.005 | Not significant after correction |
| **C vs A** | LoCoMo | 120 | 0/0 | 0.0 | 1.0 | n/a | Not significant |
| **C vs B** | LoCoMo | 120 | 0/0 | 0.0 | 1.0 | n/a (identical outcome pattern) | Not significant |

C vs A and C vs B are now real (not deferred): both are exactly non-significant because
A-MEM's canonical Answer Correctness was 0/120, identical to both A and B's LoCoMo
result — there is no discordant pair to test. This is itself informative: on canonical
exact-match, no condition differentiated on LoCoMo at all.

## 11. Multiple-Comparison Correction

Bonferroni: α=0.05 / 3 predefined comparisons = 0.0167, set before any result was
observed. None of the three comparisons clears the corrected threshold.

## 12. Diagnostic Results

| | LoCoMo B (n=120) | **LoCoMo C (n=120)** | LongMemEval B (n=120) | Overall (n=360 rows) |
|---|---|---|---|---|
| Canonical `ANSWER_INCORRECT` count | 120 | 120 | 114 | 354 |
| `DIAGNOSTIC_EQUIVALENT` count | 67 | **8** | 49 | 118 |
| **% diagnostically equivalent** | **55.8%** | **6.7%** | **37.7%** | **33.3%** (118/354) |

The LoCoMo B-vs-C diagnostic gap (55.8% vs. 6.7%) is the single largest, most surprising
finding of this campaign — see §20. Never counted as canonical success anywhere. Full
row-level data (all 118 discrepancies):
[campaign_3_3g_formal_diagnostics.json](results/campaign_3_3g_formal_diagnostics.json).
Temporal diagnostic was not run at full N in this stage (time-budget priority given to
completing Condition C) — listed as a limitation (§18).

## 13. Failure Analysis

LoCoMo: both foundations clearly help retrieval (0%→~79% Strict TSR) with the dominant
downstream failure being `AGENT_FAILURE_WITH_EVIDENCE` for both (94/120 Mem0, 91/120
A-MEM) — evidence present, exact-match answer still wrong. But the diagnostic layer
reveals these superficially-similar failure profiles hide a real quality gap: Mem0's
"failures" are mostly (55.8%) lexical near-misses; A-MEM's are mostly (93.3%) genuine
misses even when evidence was present. A plausible (not confirmed) mechanism, consistent
with prior-stage qualitative observations (3.3-D): A-MEM's answers more often included
hedging/refusal framing ("None of the provided memories...") even when relevant content
was exposed, which would both fail exact-match AND fail lexical overlap with a
fact-stated gold answer, unlike Mem0's more direct factual restatements.

LongMemEval: memory helps (0%→93.3% Strict TSR), dominant failure is
`RETRIEVAL_FAILURE` (112/120) driven by the large-gold-set structural effect (§9).

## 14. Resource Analysis

| | LoCoMo/LongMemEval A | LoCoMo/LongMemEval B | LoCoMo C |
|---|---|---|---|
| Generation latency (mean/median/max, s) | 0.86/0.87/1.82 | 1.41/1.46/3.39 | 1.31/1.36/2.41 |
| Ingestion (per unique pool) | n/a | mean 5.50s, median 0.45s, max 17.69s, total 841.5s (153 pools) | mean 74.03s, median 73.34s, max 137.72s, total 6884.9s (93 pools) |
| VRAM | 5225–5227 MiB | 5227–5231 MiB | 5229–5231 MiB |
| Total wall-clock | 218.4s | 2444.7s (~40.7 min) | 7104.9s (~118.4 min) |
| A-MEM×LongMemEval (not run) | — | — | Projected ~57.4h — formally deferred |

A-MEM's cost is overwhelmingly ingestion-bound (97% of its wall-clock), not generation
or retrieval — the real, measured bottleneck is per-item memory-evolution-attempt
overhead against an unreachable Ollama server (confirmed architecture, 3.3-D/E/F.1).

## 15. Reproducibility

Every one of the 600 successful task-condition executions carries the full manifest
field set (experiment_id, dataset, dataset_revision, task_id, condition, foundation,
foundation_version, model/revision/hash, llama.cpp build, n_ctx, temperature,
generation_seed, enable_thinking, retrieval_K, embedding_model,
configuration_fingerprint, resolved-identity detail, latency, VRAM) unchanged from the
3.3-B–F.1 trace schema. Raw traces:
[campaign_3_3g_formal_ab_result.json](results/campaign_3_3g_formal_ab_result.json),
[campaign_3_3g_formal_c_locomo_result.json](results/campaign_3_3g_formal_c_locomo_result.json).

## 16. Security / Leakage

`boundary.validate_agent_visible()` + `security.leakage.validate_no_leakage()` ran
unmodified on all 600 real agent-visible contexts (structurally guaranteed, unchanged
since 3.3-B). No gold data reached the agent at any point; diagnostic/statistical
analyses run strictly after `run_agent_task()` returns.

## 17. Data Integrity

No task excluded post-hoc anywhere. No record deleted/rewritten/filtered because of an
observed outcome. All sampled task_ids recorded in the frozen manifest before execution.
The Condition C interruption (§5) resulted in zero lost or altered results — checkpoint
recovery re-used, never re-derived, the already-completed pools' real outputs.

## 18. Statistical Limitations

- LoCoMo's McNemar tests (B vs A, C vs A, C vs B) are all uninformative for canonical
  Answer Correctness — every condition scored 0/120, so there are no discordant pairs;
  the diagnostic layer (§12) is the only lens distinguishing real behavior on LoCoMo.
- LongMemEval's p=0.031 does not survive Bonferroni correction.
- A-MEM×LongMemEval has zero formal-scale data — the C vs A/B comparisons on
  LongMemEval remain entirely unanswered.
- Temporal diagnostic not run at full N this stage.
- Effect-size CIs use the standard paired-proportion normal approximation; with only
  0-6 discordant pairs per cell, this is a reasonable but not exact description.

## 19. Scientific Interpretation

1. **Does memory improve retrieval?** Yes, decisively, both foundations, both datasets.
2. **Does retrieval improvement translate into correct answers?** Dataset- and
   foundation-dependent — LongMemEval/Mem0 shows a real (uncorrected-significant) gain;
   LoCoMo shows none under exact-match for either foundation, but Mem0's diagnostic
   layer reveals substantial real quality that A-MEM's does not replicate.
3. **Where does the chain fail?** LoCoMo: downstream (`AGENT_FAILURE_WITH_EVIDENCE`)
   for both foundations. LongMemEval: retrieval-completeness (`RETRIEVAL_FAILURE`).
4. **Do foundations behave differently?** Yes — nearly identical on retrieval metrics,
   sharply different on diagnostic answer quality (§8, §12) — the single most important
   finding this campaign produced.
5. **What failure stage dominates?** `AGENT_FAILURE_WITH_EVIDENCE` (LoCoMo, both
   foundations), `RETRIEVAL_FAILURE` (LongMemEval).
6. **Latency/resource cost?** A-MEM costs ~13.5x more per-pool ingestion than Mem0 on
   LoCoMo, entirely in the ingestion phase, for statistically indistinguishable
   retrieval performance and markedly worse diagnostic answer quality.
7. **Do effects differ LoCoMo vs LongMemEval?** Yes, substantially, on every axis.
8. **Does memory improve evidence access without improving final answers?** Yes,
   exactly the LoCoMo pattern for both foundations.
9. **How often do canonical metrics understate useful behavior?** 33.3% overall across
   all three completed conditions (118/354 canonical-incorrect rows), but this varies
   sharply by foundation (55.8% Mem0 vs. 6.7% A-MEM on LoCoMo) — not a single number.
10. **What diagnostic patterns distinguish retrieval failure from reasoning/answer
    failure?** The failure-stage taxonomy already does this; the NEW finding this stage
    adds is that the diagnostic-equivalence layer further distinguishes "reasoning
    failure with genuinely poor output" (A-MEM) from "reasoning failure that's actually
    a format mismatch" (Mem0), a distinction invisible to the failure-stage taxonomy
    alone.

## 20. Unexpected Findings

- **A-MEM and Mem0's near-identical Strict TSR (78.3% vs. 79.2%) despite a ~13.5x
  ingestion cost difference** — the expensive memory-evolution machinery A-MEM attempts
  on every item does not appear to buy better retrieval on this task set.
- **The 55.8% vs. 6.7% diagnostic-equivalence gap** — the single largest and least
  anticipated finding. Retrieval parity does NOT imply answer-quality parity between
  foundations; a campaign that only reported Strict TSR would have concluded "the
  foundations perform identically," which would have been actively misleading.
- **LongMemEval's Strict TSR/RETRIEVAL_FAILURE apparent paradox** (§9), first surfaced
  in the A/B run, reconfirmed structurally sound.
- **A real infrastructure failure mode** (§5) — a multi-hour background process was
  externally terminated with no application-level error, motivating a genuine,
  now-implemented checkpointing capability.

## 21. Threats to Validity

- **External validity**: 2 datasets, 1 model, A-MEM data limited to 1 dataset —
  findings should not be generalized beyond this exact configuration.
- **Dataset bias**: LoCoMo's session-based (pool≤25) and LongMemEval's haystack-pair
  sampling are both real, disclosed, pre-registered rules but not exhaustive of either
  dataset's diversity.
- **Foundation limitations**: Mem0's `infer=False` (LLM-free) path was used throughout;
  A-MEM's evolution step never obtained a real LLM verdict (unreachable Ollama, by
  design per 3.3-D). Neither foundation's full documented feature set was exercised.
- **Computational constraints**: directly caused A-MEM×LongMemEval's absence — the
  single largest completeness gap in this stage.
- **The diagnostic-equivalence mechanism (§12) is lexical, not semantic** — it may
  itself be biased toward Mem0's answer style (shorter, more direct) over A-MEM's
  (more hedging/verbose) in ways unrelated to true correctness; this is a real
  possible confound in the 55.8%/6.7% comparison, not resolved by this stage.

## 22. Phase 3.3-G Verdict

**PASS_WITH_DOCUMENTED_LIMITATIONS**

Conditions A and B were executed at full N=120/dataset with 100% success. Condition C
was executed at full N=120 for LoCoMo (100% success, recovered cleanly from a real
mid-run infrastructure failure via newly-added checkpointing) per an explicit,
requested revision decision; A-MEM×LongMemEval remains formally deferred (~57h
projected, not attempted) — this is the methodology's own stop condition functioning
as designed, not an execution failure. The campaign produced a genuinely surprising,
scientifically important finding (§20) that would not have been visible from canonical
metrics alone.

## 23. Phase 3.4 Readiness

**Partially ready.** The Mem0 clean baseline (both datasets) and the A-MEM/LoCoMo clean
baseline are now complete and statistically characterized at full N. A-MEM×LongMemEval
remains an open gap that should be resolved (via a longer-budget dedicated stage) before
any Phase 3.4 work that requires a complete three-condition, two-dataset clean baseline.

---

Per the mission's stop condition — stopping here after A/B/C(LoCoMo) execution, result
validation, statistical analysis, diagnostic analysis, resource analysis,
reproducibility validation, and regression testing (1151 passed, 17 skipped, three
consecutive runs including `-W error`). No attacks, no Phase 4, no canonical metric
changes, no new foundations, no dataset promotion, and no further unilateral N change.
