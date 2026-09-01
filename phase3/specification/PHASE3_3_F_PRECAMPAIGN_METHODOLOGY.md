# Phase 3.3-F — Pre-Campaign Methodology & Statistical Readiness

**Status:** Methodology refinement gate. No formal campaign executed in this stage.
**Precondition:** Phase 3.3-A through 3.3-E complete (real LLM/agent/foundation
execution path validated; identity bridge established for Mem0 and A-MEM; controlled
5-task pilot run with real results).

## 1. Verdict

**PASS_WITH_DOCUMENTED_LIMITATIONS**

## 2. Phase 3.3-E Findings

The 3.3-E pilot (5 real tasks: 3 LoCoMo, 2 LongMemEval; conditions A/no-memory, B/Mem0,
C/A-MEM) produced, verified directly against `phase3/experiments/results/campaign_3_3e_result.json`:

- **0/13 real runs scored `ANSWER_CORRECT`** under the frozen exact-match metric, despite
  several answers being substantively useful (e.g. a near-verbatim gold-answer quote).
- **Correct retrieval, wrong answer**: LoCoMo task `ecf5a096af5598393ce49c80` — gold
  evidence found by both Mem0 and A-MEM, both classified `AGENT_FAILURE_WITH_EVIDENCE`,
  answer format mismatch (relative vs. absolute date) drove the exact-match miss.
- **ID mismatch despite near-verbatim content**: LongMemEval task
  `2de941fd020d78c41343a9b4` — Mem0's answer text overlaps the gold answer at a measured
  **0.89 token-overlap ratio** (see §3), yet the literal retrieved/selected ids did not
  include the dataset's tagged `evidence_memory_ids`, so this scored `RETRIEVAL_FAILURE`.
- **A-MEM ingestion cost**: measured at **65.4–70.0s for 17–18-item LoCoMo sessions**
  (~3.9s/item), confirming 3.3-D's projection at pilot scale.
- **N=3 repeated run**: identical answer text and identical resolved `failure_stage`
  across all 3 runs (task `ecf5a096af5598393ce49c80`, condition B) — direct evidence that
  repeated generation under this fixed configuration adds no new information.
- **n=5 is far too small** for any statistical claim — 3.3-E explicitly said so and did
  not attempt one.

## 3. Answer Diagnostic Decision

**A diagnostic-only, deterministic answer-equivalence layer was needed and is now
implemented** — [phase3/evaluation/agent_runtime/answer_diagnostics.py](../evaluation/agent_runtime/answer_diagnostics.py).

**Methods investigated, in the required order:**
1. Exact string match (canonical, unchanged) — insufficient for either 3.3-E case, as
   expected (that's exactly what triggered this investigation).
2. Normalized exact match (casefold/punctuation/whitespace) — tested directly against
   both 3.3-E cases: catches **neither** (wording differs too much even after normalizing).
3. Structured/dataset-native answer representation — **investigated and found
   insufficient**: neither LoCoMo nor LongMemEval exposes a machine-parseable "this is a
   relative-date expression, resolve against timestamp X" field. Building relative-date
   temporal-expression parsing would be new, nontrivial, dataset-specific NLP — **not
   built in this stage**, explicitly deferred (§21).
4. **Deterministic normalized token-overlap (Jaccard, reference-token denominator)** —
   **selected**. Directly validated against the literal real 3.3-E strings
   (`test_answer_diagnostics.py::TestRealCampaignCaseRegressions`):
   - LongMemEval near-verbatim case → `DIAGNOSTIC_EQUIVALENT` (ratio 0.89)
   - LoCoMo relative-date case → `DIAGNOSTIC_NOT_EQUIVALENT` (ratio 0.0, **honestly**, not
     forced equivalent)
   - A genuinely wrong LongMemEval case (`Radialisk` vs. `Fissionator`) → correctly
     `DIAGNOSTIC_NOT_EQUIVALENT`

**Conclusion: deterministic methods are sufficient for the observed lexical-near-match
case class and were not exhausted-and-found-insufficient in a way that would justify
introducing embeddings or an LLM judge.** No semantic/embedding/LLM judge is implemented
in this stage.

**Relationship to canonical Answer Correctness**: `evaluate_answer_correctness()` is
**never called, imported, or modified** by `answer_diagnostics.py` (structurally
guarded, test-enforced). Status vocabulary is disjoint from both the canonical
`ANSWER_CORRECT`/`ANSWER_INCORRECT` values and the seven-value failure-stage enum
(test-enforced): `DIAGNOSTIC_EQUIVALENT` is never `SUCCESS`, never `ANSWER_CORRECT`.

**Limitations**: token-overlap cannot resolve cases requiring numeric/temporal/domain
reasoning (the LoCoMo case remains `DIAGNOSTIC_NOT_EQUIVALENT`, not equivalent, not
unresolved-and-hidden — reported honestly as "lexical methods found no overlap," which
is true, not "the answer is wrong," which the canonical metric already says).

## 4. Evidence Diagnostic Decision

**Investigated the existing Phase 3.2 mechanism first, per instruction**:
`phase3/evaluation/metrics/equivalence.py` implements EXPLICIT, dataset-declared
`equivalent_to` edges only (never inferred from content/embeddings/LLM — verified by
reading its module docstring and code). **Neither LoCoMo nor LongMemEval declares any
`equivalent_to` edges** (LoCoMo's dataset profile already records
`EQUIVALENCE_DIAGNOSTICS: UNAVAILABLE`, re-confirmed here) — this existing mechanism has
nothing to operate on for either dataset and **is not the right tool for the 3.3-E gap**.

**What the 3.3-E gap actually was**: not a missing equivalence *edge*, but retrieved
*content* that lexically overlaps the gold *answer text* without matching the gold
*evidence ID*. This is answer/content-level, not identity-level. `identity.py` (3.3-C/D)
already correctly resolves the *foundation-vs-source-ID* mismatch class (and did so
correctly in 3.3-E — the `RETRIEVAL_FAILURE` verdicts were computed on already
identity-resolved ids, so the remaining gap is genuinely a content-relevance question,
not an unresolved identity question).

**Decision**: reuse the same deterministic token-overlap mechanism, applied to
retrieved-memory content vs. gold answer text —
`answer_diagnostics.classify_evidence_content_relevance()`. This is explicitly a
**diagnostic OBSERVATION**, never a memory-ID inference: it returns no ID, is
structurally guarded (test-enforced: the result type carries no `memory_id`/
`source_memory_id` field) against ever being mistaken for or substituted into Strict
TSR's frozen literal-ID computation.

**No modification to `equivalence.py`, `identity.py`, or Strict TSR was made or needed.**

## 5. LongMemEval × A-MEM Decision

**Investigated all six options the mission listed:**

| Option | Finding |
|---|---|
| A. Full-haystack evaluation | Scientifically required (see LongMemEval rule below) |
| B. Deterministically reduced haystacks | **Rejected** — would remove real distractor content, changing task semantics |
| C. Dataset-provided smaller configuration | **Investigated directly**: `data/raw/longmemeval/longmemeval_s_cleaned.json` exists but is the "S" split — LongMemEval's own **larger**, MORE-distractor-sessions variant (277MB vs. 15MB for `longmemeval_oracle.json`, the file Phase 2 already processed). **`oracle` is already the dataset's smallest legitimate configuration** — no smaller option exists. |
| D. Shared/reused ingestion across tasks with the same haystack | **Adopted** — see below |
| E. Batch/pre-ingestion | Equivalent to D in effect; not separately implemented |
| F. Task-structure permits shared memory state | Directly verified: yes (see below) |

**Adopted strategy: Option D, haystack-grouped shared ingestion + asymmetric N.**
Verified directly (`campaign_sampling.eligible_longmemeval_tasks_grouped_by_haystack()`,
now run for real over all 1000 eligible LongMemEval tasks): **exactly 500 distinct
haystacks, each with exactly 2 tasks** — a clean, real, non-cherry-picked 2:1 ratio. This
is scientifically valid because retrieval/generation/evaluation are read-only foundation
operations (`runner.py`'s `_retrieve_and_select` calls only `retrieve()`/
`inspect_memory()`, never `add_memory()` — verified by inspection) — no task's evaluation
can mutate the shared store, so sharing one `RESET`→`INGEST` across the 2 tasks per
haystack halves ingestion cost with **zero task-independence risk**.

**LongMemEval rule compliance**: no haystack content is reduced, removed, or altered —
full-haystack evaluation is preserved exactly as the rule requires; only the *ingestion
schedule* (not the *task/evidence content*) is shared across co-haystack tasks.

**A-MEM×LongMemEval runtime remains genuinely expensive**: even with 2:1 sharing,
500 distinct-haystack ingestions × ~4s/item × ~230 items/haystack (average of 216–249
measured) ≈ **511 minutes (~8.5 hours)** for full population coverage — not attempted at
full population. The formal campaign (3.3-G) should use a **smaller N specifically for
the A-MEM×LongMemEval cell** (asymmetric N, explicitly justified by this measured cost,
per the mission's explicit permission to do so) rather than either (a) skipping A-MEM on
LongMemEval entirely or (b) silently reducing haystack content to make it fast.

## 6. Dataset Scope

| Dataset | Campaign Status | Foundation Scope | Reason |
|---|---|---|---|
| LoCoMo | **INCLUDED** | Mem0, A-MEM | Real task layer, small sessions, both foundations pilot-validated |
| LongMemEval | **INCLUDED** | Mem0 (full N), A-MEM (reduced N) | Real task layer; oracle haystack already minimal; A-MEM asymmetric-N per §5 |
| MSC | **EXCLUDED** | — | `data/processed/msc/task_records.jsonl` verified empty (0 lines) — no task layer exists. Per §6.1 below, not fabricated here. |
| Conversation Chronicles | **EXCLUDED** | — | Same finding — `task_records.jsonl` verified empty (0 lines) |
| PerLTQA zh | **SECONDARY VALIDATION ONLY**, not formal campaign | Not decided this stage | Usable per Phase 3.2, but not pilot-tested with the real agent/foundation path yet — including it in 3.3-G without that validation would be a first-time integration risk during the formal campaign itself |
| ConvoMem | **SECONDARY VALIDATION ONLY**, not formal campaign | Not decided this stage | `USABLE_WITH_LIMITATIONS` (97% evidence resolution, `LICENSE_UNRESOLVED`) — the limitations themselves argue for a small dedicated validation pass before formal inclusion, not automatic inclusion because it is "usable" |
| MemoryAgentBench | **KEEP_CANDIDATE_ONLY** | — | Unchanged, not promoted |
| MemBench | **KEEP_CANDIDATE_ONLY** | — | Unchanged, not promoted |
| MemoryArena | **KEEP_CANDIDATE_ONLY** | — | Unchanged, not promoted |

### 6.1 MSC / Conversation Chronicles task-layer issue

**Investigated, not fabricated.** Building a legitimate task layer from either dataset's
native evaluation structure (rather than inventing labels) is possible in principle —
both datasets carry structured provenance/session metadata that *could* support a
future, separately-governed data-preparation stage — but doing so is genuine new data
engineering (parsing native task/probe structures, generating question/answer/evidence
triples from source material, validating them), which is explicitly **out of scope for a
methodology-only stage** and is not attempted here. **Decision: exclusion is preserved**,
documented as a pre-campaign data-preparation decision for a future stage, not resolved
in 3.3-F.

## 7. Sampling Protocol

Extends (does not replace) `campaign_sampling.py`'s 3.3-E deterministic procedure:

- **LoCoMo**: eligible = non-null answer, non-empty evidence, all evidence resolvable
  within one `(conversation_id, session_id)` pool ≤25 records. Continuity task always
  included; remaining tasks via `random.Random(SAMPLING_SEED).sample()` — seed disclosed
  (`33005`), never re-rolled to chase a result.
- **LongMemEval**: eligible = non-null answer, non-empty evidence (1000/1000 task records
  qualify). **New for 3.3-F**: `eligible_longmemeval_tasks_grouped_by_haystack()` groups
  ALL eligible tasks (not just one per haystack) by `source_record_id`, enabling the
  haystack-sharing strategy in §5. Final task selection within this grouped population
  for 3.3-G should again use a fixed, disclosed `random.Random(seed)` draw over
  haystacks (not individual tasks, to preserve the 2:1 sharing benefit).
- **No task is ever excluded because of its expected outcome** — verified structurally:
  sampling functions read only `answer`/`evidence_memory_ids`/pool-size fields, never any
  outcome/score field (none exists at sampling time in any case, since no generation has
  happened yet).

## 8. Experimental Unit

**The paired task** (one `task_id`, run once under each applicable condition with
identical configuration) is the unit of independent observation. Repeated *generations*
of the same (task, condition) pair are **not** counted as additional independent
observations — directly justified by 3.3-E's N=3 finding (§2): under
temperature=0/seed=42/fixed context, repeated generation produced literally identical
output, so it carries no additional statistical information for a between-condition
comparison. See `campaign_power.REPEATED_RUN_RATIONALE`.

## 9. Statistical Design

**McNemar's test** (paired binary outcome — e.g. Strict TSR hit/miss, or canonical
Answer Correctness, per task) for each of the three pairwise comparisons (A vs B, A vs C,
B vs C). An independent-samples test would discard the pairing structure the A/B/C
control methodology is built on (per `PHASE3_3_EXPERIMENTAL_SPEC.md` Part 11) and would
be a design error, not merely a suboptimal choice.

**Multiple comparisons**: 3 pairwise tests planned → Bonferroni-corrected target alpha =
0.05/3 ≈ 0.0167. The implemented sample-size table (`campaign_power.py`) only supports
{0.05, 0.01} two-sided (to avoid implementing a general inverse-normal-CDF for a one-off
calculation) — the α=0.01 entry is used as a **conservative upper bound**, not an exact
match, and this approximation is stated explicitly in every `recommend_n_tasks()` output.

## 10. Recommended N

**No single N is asserted from the 5-task pilot** — that would manufacture an effect
size from insufficient data, which the mission explicitly forbids. Instead, a
sensitivity table across 5 plausible discordant-proportion scenarios (never estimated
from 3.3-E's n=5):

| Scenario | p10 | p01 | Effect | N (α=0.05, single comparison) | N (α=0.01, Bonferroni bound) |
|---|---|---|---|---|---|
| Small effect, low discordance | 0.10 | 0.00 | 10pp | 76.1 | 113.9 |
| Small effect, moderate discordance | 0.20 | 0.10 | 10pp | 233.1 | 347.5 |
| Medium effect, moderate discordance | 0.30 | 0.10 | 20pp | 76.1 | 113.9 |
| Medium effect, high discordance | 0.40 | 0.20 | 20pp | 115.3 | 172.3 |
| Large effect, moderate discordance | 0.35 | 0.05 | 30pp | 32.4 | 48.9 |

(power=0.80 throughout; all values from `campaign_power.recommend_n_tasks()`, run for
real, not hand-typed.)

**Recommended target for 3.3-G planning: N ≈ 100–150 paired tasks per condition-pair**
where population and runtime allow — covers the medium-effect scenarios at the
conservative Bonferroni bound. **LoCoMo's real eligible population is ~1900+ tasks**
(well above this); **LongMemEval's is 1000 tasks / 500 haystacks** (also sufficient,
subject to the A-MEM asymmetric-N constraint from §5). If the true effect is small
(≤10pp) and highly discordant, even N≈350 would be underpowered — this is stated as a
genuine limitation (§21), not hidden.

## 11. Repeated-Run Design

**Task replication, not generation replication, is the lever.** Per §8/§2: N repeated
generations of the identical (task, condition) pair are not treated as independent
samples (verified empirically, not assumed) — the frozen `temperature=0, seed=42` does
not eliminate all stochasticity in principle (per `REPRODUCIBILITY_CONTRACT.md`'s
standing position, unchanged), but at the scale this pilot could observe, zero variance
was found. 3.3-G should still record a small budget (e.g. N=2–3) of repeated-generation
spot-checks on a handful of tasks as an ongoing determinism monitor, not as a
statistical-power contributor.

## 12. Runtime Budget

Using **measured 3.3-E rates**, not assumptions:

| Cell | Ingestion rate | Est. cost at N=100 |
|---|---|---|
| LoCoMo × Mem0 | ~0.02s/item, ~18 items/session | ~36s total |
| LoCoMo × A-MEM | ~3.9s/item, ~18 items/session | ~117 min (100 fresh sessions) |
| LongMemEval × Mem0 (500 haystacks, 2:1 shared) | ~0.02s/item, ~230 items/haystack | ~50×N_haystacks sec — trivial |
| LongMemEval × A-MEM (asymmetric N) | ~3.9s/item, ~230 items/haystack | **~15 min/haystack** — full 500-haystack coverage ≈ 8.5 hours, hence asymmetric N recommended |
| Generation (all cells) | 0.35–2.44s/call, measured | negligible vs. ingestion |

VRAM stayed flat (5223→5231 MiB) across all of 3.3-E — no evidence of scaling risk with
N, but not verified at N=100+ in this stage.

## 13. Foundation Scope

**Mem0 and A-MEM: both formal-campaign-ready** (identity bridge, reset isolation,
collision behavior all characterized in 3.3-C/D, re-confirmed working in 3.3-E's real
multi-task pilot). **Graphiti: remains excluded** — its natural-language retrieval path
is `MODEL_DEPENDENT` (no local embedder in `graphiti-core`, confirmed by direct
inspection in 3.3-D, not re-litigated here) and no cloud API is being introduced to
change that. **Letta: not added**, per explicit instruction.

## 14. Canonical Metrics

**Unchanged.** Recall@K, MRR, Strict TSR, Evidence Precision/Recall/Coverage, Answer
Correctness, Agent Success, Memory Utilization, Memory Contribution, and the seven-value
failure-stage enum are all reused verbatim from Phase 3.2/3.3-B code, with zero
modification (`git status`/`git diff --stat` confirm — see §20). No composite score, no
weighting, no tuning.

## 15. Diagnostic Metrics (new, approved, non-canonical)

- `DIAGNOSTIC_EQUIVALENT` / `DIAGNOSTIC_NOT_EQUIVALENT` / `DIAGNOSTIC_UNRESOLVED`
  (`answer_diagnostics.py`) — deterministic token-overlap, for both answer-level and
  evidence-content-level use. Never affects `evaluation_result`, `failure_stage`, or
  Strict TSR.

## 16. Leakage

`boundary.validate_agent_visible()` + `security.leakage.validate_no_leakage()` remain
unmodified and are still the enforcement point for every agent-visible context. The new
diagnostic module is evaluator-side only (like `evaluate_and_trace()`), never imported by
`runner.py`, and structurally cannot leak into agent context — it has no code path that
writes into an `AgentVisibleContext`-shaped payload (verified: it returns only a small
frozen dataclass, never touched by `messages.py`/`runner.py`).

## 17. Reproducibility

Final manifest (superset of 3.3-E's, unchanged fields plus explicit sampling
provenance): `experiment_id`, `task_id`, `dataset`, `dataset_revision`, `sample_seed`,
`condition`, `foundation`, `foundation_version`, `model`, `model_revision`, `model_hash`
(GGUF SHA-256), `llama.cpp build`, generation parameters (temperature/seed/max_tokens/
`enable_thinking`/`n_ctx`), embedding model, foundation configuration, reset
confirmation, `configuration_fingerprint`, timestamps, resource measurements — all
already produced by `agent_runtime/trace.py`'s existing trace shape (unmodified) plus
`campaign_runner.py`'s per-run wrapper (unmodified from 3.3-E).

## 18. Validation Experiments

All performed for real, at small scale, this stage:
1. `answer_diagnostics` validated against the literal real 3.3-E strings (§3) —
   confirmed correct classification on all 3 known cases.
2. `eligible_longmemeval_tasks_grouped_by_haystack()` run for real over the full 1000
   LongMemEval eligible tasks — confirmed the 500-haystack/2-tasks-each structure (§5).
3. `campaign_power.recommend_n_tasks()` run for real, producing the sensitivity table in
   §10 (not hand-typed).
4. `longmemeval_s_cleaned.json` directly inspected (file size + structure) to settle the
   "smaller dataset variant" question (§5) rather than assumed.

No formal campaign, no new LLM calls, no new foundation ingestion runs were performed in
this stage (all validation reused already-collected 3.3-E data plus static file/data
population inspection).

## 19. Tests

- **UNIT_TEST**: 44 new (18 answer-diagnostics incl. real-case regressions, 10
  campaign-power, 4 haystack-grouping, plus existing sampling tests re-verified)
- **Full regression**: `pytest -q` ×2 → **1101 passed, 17 skipped**; `-W error` → same

## 20. Protected Surfaces

Verified untouched (`git status --short` / `git diff --stat` confirm below): canonical
metrics (`phase3/evaluation/metrics/*`), Strict TSR, evaluator semantics
(`phase3/evaluation/agent/*`), `phase3/contracts/*.md`, active/candidate dataset
definitions, historical reports, `PHASE3_3_EXPERIMENTAL_SPEC.md`, all foundation adapters
(`RealMem0Adapter`/`RealGraphitiAdapter`/`RealAMemAdapter`), Qwen model artifact.

## 21. Remaining Limitations

1. Relative-date/temporal-expression resolution remains genuinely unsolved by
   deterministic methods — `DIAGNOSTIC_NOT_EQUIVALENT` is the honest result for such
   cases, not a false positive, but it does mean some genuinely-useful answers will still
   read as "not equivalent" in the diagnostic layer too.
2. Power sensitivity range is wide (33–350 tasks depending on assumed effect/discordance)
   because no reliable prior variance estimate exists — 3.3-G's early real data should be
   used to narrow this before committing to a final N.
3. A-MEM×LongMemEval remains expensive even with haystack-sharing (~15 min/haystack) —
   asymmetric N is a scientifically valid but not fully satisfying resource compromise.
4. PerLTQA/ConvoMem participation is deferred, not decided — they need their own small
   real-path validation pass before formal inclusion.
5. MSC/Conversation Chronicles task-layer construction remains unresolved — a genuine
   future data-preparation project, not attempted here.

## 22. 3.3-G Readiness

**YES — the methodology is now sufficiently specified to execute a formal repeated-N
controlled campaign**, with the following exact configuration:

- **Datasets**: LoCoMo (full eligible population, session-pool-bounded sampling) +
  LongMemEval (haystack-grouped sampling, 2:1 task-sharing)
- **Foundations**: Mem0 (full N) + A-MEM (full N on LoCoMo; reduced/asymmetric N on
  LongMemEval, per §5/§12's measured cost)
- **Conditions**: A (no memory) / B (Mem0) / C (A-MEM)
- **N**: target 100–150 paired tasks per condition-pair where population/runtime allow;
  narrower for A-MEM×LongMemEval specifically, quantified once early 3.3-G data exists
- **Statistics**: McNemar paired test per comparison, Bonferroni-corrected α, power=0.80
  design target
- **Metrics**: fully canonical, unmodified; `DIAGNOSTIC_EQUIVALENT`/`NOT_EQUIVALENT`/
  `UNRESOLVED` reported alongside, never substituted in
- **Model/backend**: unchanged Qwen3-8B Q4_K_M / llama.cpp b10717 / n_ctx=4096 /
  temperature=0 / seed=42 / `enable_thinking=False`

Per the mission's stop condition — stopping here. No formal campaign, no final N, no
canonical-metric change, no dataset promotion, no new foundation was executed or
introduced in this stage.
