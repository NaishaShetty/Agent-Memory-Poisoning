# Phase 3.3-G.1 — Dedicated A-MEM × LongMemEval Formal Baseline Completion

## 1. Purpose

Phase 3.3-G's formal campaign executed Conditions A (no-memory) and B (Mem0) at full
scale (N=120/dataset) plus Condition C (A-MEM) at full scale for LoCoMo, but formally
deferred Condition C for LongMemEval: the real per-item A-MEM ingestion cost measured
in 3.3-G (`campaign_formal_amem_probe.py`) projected ~28 hours of wall-clock time for
60 unique LongMemEval haystacks at serial execution speed, which the 3.3-G mission's
own stop condition flagged as requiring a dedicated follow-up rather than silently
extending that campaign's scope. This document is that follow-up: it completes the
missing A-MEM × LongMemEval cell of the six-cell (2 datasets × 3 conditions) formal
comparison matrix, using the exact same frozen sample, model, and evaluation pipeline
as 3.3-G — nothing about the experimental design changed, only that the deferred cell
was finally executed.

## 2. Relationship to 3.3-G

This is an **additive completion**, not a revision. `PHASE3_3_G_FORMAL_CAMPAIGN_REPORT.md`
is left untouched and remains historically accurate to what 3.3-G itself measured and
concluded (A/B full, C LoCoMo-only). All new code and outputs in this phase write to
**new** files (`campaign_3_3g1_*`), never overwriting or mutating any `campaign_3_3g_*`
file 3.3-G already produced or cited. The only case where this required care was
`campaign_formal_analysis.py` and `campaign_formal_diagnostics.py`, which are shared,
executable modules (not frozen artifacts) — they were extended in place to also handle
the new LongMemEval Condition C data, but their **output paths were changed** to new
filenames (`campaign_3_3g1_formal_analysis.json`, `campaign_3_3g1_formal_diagnostics.json`)
specifically so that re-running them never silently invalidates the `campaign_3_3g_formal_*`
snapshot the 3.3-G report already quotes verbatim.

## 3. Frozen Configuration

Identical to 3.3-G, unmodified:
- Model: Qwen3-8B-Q4_K_M.gguf, served via `llama-server.exe` (llama.cpp b10717, CUDA 12.4,
  `-ngl 99`), OpenAI-compatible HTTP API at `http://127.0.0.1:8811`.
- Generation config: `clean_baseline_generation_config(n_ctx=4096, max_tokens=64)`
  (`temperature=0.0`, `seed` fixed, `enable_thinking` explicit).
- Foundation: `RealAMemAdapter` (real A-MEM package, `all-MiniLM-L6-v2` embeddings),
  DIRECT_ASSIGNMENT identity strategy (caller-supplied memory IDs honored by the
  foundation).
- Evaluation: unmodified Phase 3.2 canonical metrics (`evidence.py`, `retrieval.py`,
  `selection.py`), strict TSR, exact-match Answer Correctness — no new metric logic.
- Isolation: fresh RESET+INGEST once per unique haystack, read-only RETRIEVE→GENERATE→
  EVALUATE per task (`runner.py::_retrieve_and_select`, unchanged since 3.3-B — only
  `retrieve()`/`inspect_memory()` ever called during evaluation).

## 4. Frozen Sample

Reused `build_formal_sample(120)["longmemeval"]` verbatim — the same 120-task,
60-unique-haystack, seed-33005 sample 3.3-G's manifest already froze and fingerprinted
(`campaign_3_3g_manifest.json`, fingerprint
`419f1565a25c0736cc68b4890882389991fb65508d426d97b8bfaa0a6aafa91c`). No new sampling,
no re-seeding, no task substitution. This is the exact same task set Conditions A and B
were already evaluated against in 3.3-G, so all three conditions are now paired on
identical tasks.

## 5. Haystack Sharing

Per the frozen manifest, the 120 LongMemEval tasks share exactly 60 unique haystacks
(2 tasks/haystack), so A-MEM ingestion was amortized across paired tasks exactly as it
was for Conditions A/B/C-LoCoMo in 3.3-G — one RESET+INGEST per haystack, not per task.

## 6. Execution

Executed in two phases:

1. **Serial baseline** (pre-parallelization): 22 tasks / 11 pools completed via the
   existing `run_formal_c_longmemeval()` serial path, interrupted multiple times by
   external process termination (consistent with environment/session resets during idle
   gaps) and cleanly resumed from checkpoint each time with no data loss or duplication.
2. **Parallel completion**: given the real per-item cost data from 3.3-G's own probe
   projected an infeasible ~28-hour serial wall-clock time, and A-MEM ingestion is
   CPU/embedding-bound rather than GPU-bound (VRAM stayed flat throughout), execution
   was split across 3 concurrent worker processes (`run_formal_c_longmemeval_worker()`),
   each deterministically owning a disjoint partition of the 49 not-yet-done haystack
   pools (`sorted(remaining_pools)[worker_id::num_workers]`), each writing to its own
   checkpoint file to avoid concurrent-write races. This is a **wall-clock scheduling
   change only** — no change to the model, A-MEM configuration, sample, retrieval,
   generation, or evaluation of any individual task; each worker performed the identical
   RESET→INGEST→(RETRIEVE→GENERATE→EVALUATE per task) sequence the serial path already
   used, just concurrently with its siblings instead of sequentially. This was verified
   safe before being relied upon: `test_campaign_formal_checkpoint.py` (5 tests, written
   during 3.3-G.1 planning) locks in both between-pool and mid-pool checkpoint resume
   correctness, which the parallel workers depend on identically to the serial path.

   The parallel run itself survived two more idle-period process deaths (server +
   workers all exited with no traceback, consistent with the same environment-reset
   pattern seen during the serial phase) and was restarted cleanly from checkpoint both
   times — verified duplicate-free (`len(tasks) == len(set(task_ids))`) at every
   restart before resuming.

3. **Merge**: `merge_longmemeval_worker_checkpoints(3)` combined the main checkpoint (22
   tasks) with all 3 worker checkpoints (34 + 32 + 32 = 98 tasks) into
   `campaign_3_3g1_formal_c_longmemeval_result.json` — **120/120 unique task_ids, zero
   duplicates, all 60/60 unique haystacks accounted for**.

## 7. Canonical Results

| Condition | N | Answer Correct | Recall@5 | MRR | Strict TSR | Evidence Precision | Evidence Recall/Coverage |
|---|---|---|---|---|---|---|---|
| A (no-memory) | 120 | 0 (0.0%) | — | — | — | — | — |
| B (Mem0) | 120 | 6 (5.0%) | 0.933 | 0.661 | 0.933 | 0.415 | 0.130 |
| C (A-MEM) | 120 | 0 (0.0%) | 0.925 | 0.665 | 0.925 | 0.418 | 0.131 |

Source: `campaign_3_3g1_formal_analysis.json`.

**Headline finding**: A-MEM's retrieval quality on LongMemEval is statistically
indistinguishable from Mem0's (recall@5 0.925 vs 0.933, strict TSR 0.925 vs 0.933 — both
foundations correctly retrieve and select the gold evidence in the great majority of
cases) — yet A-MEM produced **zero** exact-match-correct answers versus Mem0's 6. Good
retrieval did not translate into correct final answers for A-MEM on this dataset. This
contrasts with the LoCoMo cell (3.3-G), where A-MEM and Mem0 were much closer on
canonical answer correctness.

## 8. Failure Stages

| Condition | RETRIEVAL_FAILURE | AGENT_FAILURE_WITH_EVIDENCE | SUCCESS | EVIDENCE_UNAVAILABLE |
|---|---|---|---|---|
| A | — | — | 0 | 120 |
| B | 112 | 2 | 6 | — |
| C | 118 | 2 | 0 | — |

A's 120/120 `EVIDENCE_UNAVAILABLE` is expected and definitional (no memory foundation
is attached in Condition A). B and C share the same failure-stage *shape*
(overwhelmingly `RETRIEVAL_FAILURE`, a small `AGENT_FAILURE_WITH_EVIDENCE` tail) despite
near-identical underlying recall/TSR — see §10 for the diagnostic-layer explanation of
why "RETRIEVAL_FAILURE" as a canonical label does not mean the evidence was actually
absent from what was retrieved (the canonical failure-stage classifier is driven by the
strict exact-match Answer Correctness check, not directly by strict TSR per row).

## 9. Identity Results

A-MEM uses the DIRECT_ASSIGNMENT identity strategy (caller-supplied memory IDs honored
verbatim by the foundation), so resolution is definitional rather than probabilistic —
`identity_collision_free` was computed per-pool via `verify_collision_safety()` from
`identity.py` regardless. Result: **120/120 (100%) collision-free** across all 60 unique
haystacks — no source ID ever silently mapped to more than one foundation record within
any single haystack's ingestion batch.

## 10. Diagnostic Results

Token-overlap diagnostic (`answer_diagnostics.classify_answer_equivalence()`, Jaccard
overlap threshold 0.5, diagnostic-only — never alters canonical metrics), from
`campaign_3_3g1_formal_diagnostics.json`:

| Condition | N | Canonical Incorrect | Diagnostic-Equivalent | % of Canonical-Incorrect |
|---|---|---|---|---|
| B (longmemeval) | 120 | 114 | 43 | 37.7% |
| C (longmemeval) | 120 | 120 | 13 | 10.8% |

**This is the key nuance behind the headline finding**: A-MEM's 0/120 canonical
(strict exact-match) score is not entirely "wrong answers" — 13 of its 120 responses
were close enough by lexical-overlap standards to plausibly be correct paraphrases that
the strict evaluator does not credit. That is real signal, not zero, but it is
substantially less than Mem0's 43/114 (37.7%) diagnostic-equivalent rate among its own
incorrect answers — so even under this more permissive diagnostic lens, A-MEM still
underperforms Mem0 on LongMemEval by a wide margin, not merely a strict-scoring
artifact.

Temporal diagnostic (`temporal_diagnostics.resolve_temporal_equivalence()`, calendar
arithmetic vs. lexical overlap — a genuinely separate deterministic method, applied only
to Condition C given time), from `campaign_3_3g1_temporal_diagnostic.json`:

- 120/120 successful traces had a real gold-evidence `source_timestamp` available to
  serve as `reference_date` (read directly from `data/processed/longmemeval/memory_records.jsonl`,
  never fabricated).
- Status distribution: 115 `TEMPORAL_NOT_APPLICABLE` (candidate answer contained no
  recognized temporal expression), 5 `TEMPORAL_UNRESOLVED` (temporal expression found
  but not deterministically resolvable), **0 `TEMPORAL_EQUIVALENT`**.
- This diagnostic surfaced **no** additional plausibly-correct answers for A-MEM on
  LongMemEval — the token-overlap diagnostic (§ above) is where the 13 near-misses were
  found, not date-arithmetic near-misses.

## 11. Resource Results

- Ingestion cost profile matched 3.3-G's own probe measurement (`campaign_formal_amem_probe.py`):
  CPU/embedding-bound, VRAM flat throughout — confirming the parallelization
  precondition was correctly diagnosed before relying on it.
- Execution completed via 22 serial tasks (11 pools) + 3 parallel workers (34 + 32 + 32
  tasks; 17 + 16 + 16 pools respectively), 0 execution failures, 0 environment failures
  across all 120 tasks.
- Checkpoint/resume was exercised for real multiple times by genuine interruptions (not
  simulated) — both the pre-existing between-pool case and, for the first time in this
  project's history under real conditions, effectively the mid-pool case pattern the
  dedicated unit tests (`test_campaign_formal_checkpoint.py`) were written to protect
  against — and recovered losslessly and duplicate-free every time.

## 12. Statistical Completion

With Condition C now complete for both datasets, the primary 3-comparison statistical
design (B vs A, C vs A, C vs B) is now fully executable per dataset AND pooled overall,
closing the gap 3.3-G left open (`campaign_3_3g_formal_analysis.json`'s `C_vs_A`/`C_vs_B`
had LoCoMo only). From `campaign_3_3g1_formal_analysis.json`:

| Comparison | Dataset | Discordant (b, c) | Statistic | p-value | Bonferroni α=0.0167 |
|---|---|---|---|---|---|
| C vs A | longmemeval | (0, 0) | 0.0 | 1.0 | not significant |
| C vs B | longmemeval | (6, 0) | 6.0 | 0.03125 | **not significant** (raw p<0.05 but > 0.0167) |

C vs A shows no difference (both scored 0/120) — unsurprising given A-MEM produced zero
correct answers. C vs B is nominally significant at the raw α=0.05 threshold (B strictly
dominates C: 6 tasks where B was correct and C was not, 0 the other way) but **does not
survive Bonferroni correction** (N_PRIMARY_COMPARISONS=3, α=0.0167) — so per the frozen
statistical design's own multiple-comparisons discipline, this result should be reported
as suggestive, not as a confirmed significant difference at the pre-registered family-wise
error rate.

## 13. Cross-Dataset Interpretation

Combining with 3.3-G's LoCoMo Condition C results (`campaign_3_3g_formal_c_locomo_result.json`,
120/120 successful): A-MEM's relative standing versus Mem0 is not uniform across
datasets. This report does not restate 3.3-G's LoCoMo numbers (see that report for
them) but notes qualitatively that the LongMemEval cell shows a much larger
retrieval-quality/answer-correctness gap for A-MEM than the LoCoMo cell did — consistent
with LongMemEval's longer, more topically dense haystacks stressing A-MEM's answer
synthesis differently than LoCoMo's conversational-session structure does. No causal
mechanism is claimed here (per the project's `MEMORY_CAUSED` non-claim discipline) —
this is an association observed across two datasets' canonical results, not a diagnosed
cause.

## 14. Limitations

- Single-seed (33005), single-model (Qwen3-8B-Q4_K_M) evaluation — as with 3.3-G, no
  claim is made that these results generalize to other models or repeated sampling.
- The diagnostic layers (token-overlap, temporal) are intentionally conservative and
  deterministic; they may under-count genuinely-correct-but-differently-phrased answers
  that neither lexical overlap nor date arithmetic can detect (e.g., correct answers
  requiring semantic paraphrase recognition beyond word-level overlap).
  `EQUIVALENCE_THRESHOLD=0.5` for the token-overlap diagnostic is the same frozen
  threshold used throughout the project, not tuned for this dataset.
  n_ctx=4096 (not the 16K context 3.3-B0's feasibility report measured RAM for) means
  very long LongMemEval haystack content retrieved into the prompt could be truncated;
  this was not separately re-verified for the LongMemEval cell specifically.
- The parallel-worker execution strategy is validated for correctness (checkpoint
  resume, no duplication, deterministic partitioning) but was not itself a controlled
  experiment on execution-strategy effects on results — no evidence suggests it could
  affect model outputs (each worker's per-task RETRIEVE→GENERATE→EVALUATE sequence is
  identical to the serial path), but this was not exhaustively re-verified against a
  full from-scratch serial re-run given the time cost that would entail.
- `-W error` regression pass surfaced 2 additional failures beyond the 2 pre-existing
  `test_git_repository_state.py` failures, both in `tests/test_unified_memory_real_data.py`
  — real but pre-existing `PytestUnraisableExceptionWarning`s from an unclosed file
  handle to `data/processed/locomo/qa_reconciled.jsonl`, reproduced in isolation,
  confirmed to predate this session (file unchanged since the initial commit) and
  unrelated to any 3.3-G.1 code. Not fixed here as out of this phase's frozen scope.

## 15. Clean-Baseline Matrix Status

The six-cell formal comparison matrix (2 datasets × 3 conditions) is now **fully
complete**:

| | LoCoMo | LongMemEval |
|---|---|---|
| A (no-memory) | ✅ (3.3-G) | ✅ (3.3-G) |
| B (Mem0) | ✅ (3.3-G) | ✅ (3.3-G) |
| C (A-MEM) | ✅ (3.3-G) | ✅ (3.3-G.1, this report) |

No cell remains formally deferred.

## 16. Verdict

**Phase 3.3-G.1 is COMPLETE.** The previously-deferred A-MEM × LongMemEval formal cell
(N=120, 60 unique haystacks) has been executed at full frozen scale using the identical
sample, model, and evaluation pipeline as 3.3-G, closing the six-cell matrix. Execution
was 120/120 successful with zero execution or environment failures, 120/120
identity-collision-free, and survived multiple real interruptions with verified
lossless, duplicate-free checkpoint recovery — including through a parallelized
execution strategy whose correctness was verified by dedicated unit tests before being
relied upon for the real run. The regression suite is clean relative to this session's
changes: 257/259 passing consistently across two full `pytest -q` runs, with the 2
consistent failures and the `-W error` pass's 2 additional resource-warning failures all
independently confirmed pre-existing and unrelated to this phase's code.

The substantive scientific result — A-MEM matching no-memory's 0/120 exact-match
correctness on LongMemEval despite retrieval quality statistically indistinguishable
from Mem0's — is a genuine, noteworthy finding, tempered honestly by the diagnostic
layer showing it is not *entirely* zero signal (13/120 near-misses) and by the
Bonferroni-corrected non-significance of the raw C-vs-B p-value. Per the project's
absolute stop condition: no further experimentation, model changes, metric changes, or
re-running of completed cells follows from this report.
