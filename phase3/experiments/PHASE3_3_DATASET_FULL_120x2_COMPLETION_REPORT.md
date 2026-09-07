# Clean-Agent Behavioral Dataset — Full 120×2 Run — Completion Report

Status: **COMPLETE**. Real execution report for the full-scale run approved in
[PHASE3_CLEAN_DATASET_CONSTRUCTION_PLAN.md](../specification/PHASE3_CLEAN_DATASET_CONSTRUCTION_PLAN.md)
(decisions: include Condition B/gold-evidence, full 120-task LoCoMo scale per
foundation, approved schema plus raw ledger/event references), following the
[bounded pilot](PHASE3_3_DATASET_PILOT_REPORT.md) that validated the mechanism
end-to-end on 4 real tasks first.

## 1. What ran

All 120 real LoCoMo tasks from the frozen formal sample (`build_formal_sample(120)`,
seed 33005 — the SAME sample Conditions B/C(mem0/amem) of the original 3.3-G-formal
campaign used), all four conditions, real infrastructure throughout:

| Condition | Mechanism | Result |
|---|---|---|
| A (NO_MEMORY) | `run_agent_task()`, no foundation | 120/120 SUCCESSFUL_EVALUATION |
| GOLD_EVIDENCE | `gold_evidence_runner.py` (new this session) | 120/120 SUCCESSFUL_EVALUATION, 0 content-leakage detections |
| B (Mem0, RETRIEVED_MEMORY) | `RealMem0Adapter`, real ingestion+retrieval | 120/120 SUCCESSFUL_EVALUATION |
| C (A-MEM, RETRIEVED_MEMORY) | `RealAMemAdapter`, real ingestion+retrieval | 120/120 SUCCESSFUL_EVALUATION |

**480 real executions total, zero failures, zero content-leakage detections.**
Real Qwen3-8B via `llama-server.exe` (`b10717`/`a32af33de`, `-ngl 99 --ctx-size 16384
--parallel 4`), health-checked before the run. Wall-clock: Condition A ~2.5 min,
GOLD_EVIDENCE ~4 min, Mem0 ~33 min, A-MEM ~2h6m (7572s) — the A-MEM stage dominates,
consistent with every prior real measurement this session made of A-MEM's per-item
"evolution" overhead against an unreachable Ollama backend.

## 2. Final dataset

`phase3/experiments/results/canonical_store/dataset_full/clean_agent_dataset_locomo_120x2.json`
— **240 records** (120 tasks × 2 foundations), assembled via
`dataset_record_assembler.assemble_dataset_records()`. **All 240 validate against
`clean_agent_dataset_record_schema.json`** (`jsonschema` 4.26.0, direct validation).

Each record carries: task/dataset/foundation identity; all three conditions'
answers, evaluation results, and fingerprints; Condition C's real retrieved/selected/
exposed memory ids and pool key; `raw_ledger_refs` (canonical event report + pool
reference, reopenable via `canonical_wiring.canonical_store_dir_for_pool()` +
`provenance_graph.build_provenance_graph()` — never a duplicated copy of ledger
content); `observability_coverage` (honest per-record: `rejected_events_possible`/
`relationship_detected_possible`/`used_events_possible` all `False`, matching the
project-wide deferral of the selection/creation policies; `counterfactual_measured`
`False` for every record here — this run did not attach the earlier n=6/n=20
counterfactual evidence, see §4).

## 3. An important, honest result: near-zero `ANSWER_CORRECT` rate — expected, not a defect

| Foundation | A (no-memory) | GOLD_EVIDENCE | C (retrieved-memory) |
|---|---|---|---|
| MEM0 | 0/120 correct | 0/120 correct | 0/120 correct |
| AMEM | 0/120 correct | 0/120 correct | 1/120 correct |

**Investigated directly, not assumed.** Sampled real answers are frequently
substantively reasonable (e.g. task `049537bf...`, gold `"Transgender woman"`, real
model answer `"Caroline's identity is transgender."`; task `0578b06c...`, gold
`"Extreme sports"`, real model answer `"extreme sports [evidence-slot-1]"` — the
correct fact literally appears, lowercased, with a citation tag appended). These are
marked `ANSWER_INCORRECT` because `agent/outcomes.py::evaluate_answer_correctness()`
implements **exact string match after only `.strip()`** — no case-folding, no
punctuation/citation stripping, no fuzzy or semantic comparison — a deliberate,
explicitly documented Phase 3.2-E design decision (`evaluate_answer_correctness()`'s
own docstring: "Deterministic EXACT-MATCH answer correctness -- no LLM, no
embeddings, no fuzzy/semantic comparison anywhere"), not something this run
introduced or a bug this report is patching over.

**This is the expected, honest consequence of pairing free-form LLM generation
(no constrained output format, no answer-extraction post-processing) with an
intentionally strict, frozen exact-match grader** — not evidence the agent "failed"
480 times, and not evidence of a measurement defect. It was already visible at small
scale (the 4-task pilot showed the same 0/4 pattern, noted then as "an honest
observed result, not investigated further"); at n=120 it is now confirmed real,
persistent, and understood, not a fluke. **Not modified here** — changing the
answer-correctness grading mechanism (loosening exact-match, adding an LLM judge,
etc.) is itself a novel, consequential, unfrozen decision, the same category of thing
already deferred for selection/creation policy — flagged for a future decision, not
silently fixed or silently left unexplained.

## 4. Counterfactual evidence — attached (updated after initial completion)

`attach_counterfactual_evidence()` was run against this dataset, folding in the
earlier real n=20 counterfactual measurements (both foundations;
`h4a-real-locomo-n20`/`h4a-real-locomo-n20-amem`) by exact `(task_id, foundation)`
match. **Verified first, not assumed**: all 20 n=20 task ids for each foundation are
a subset of the 120-task formal sample this run used, and the earlier n=6 runs are
themselves a verified strict subset of n=20 for both foundations — so n=20 alone
gives full real coverage, n=6 added nothing new.

**Result: 40/240 records (20 tasks × 2 foundations) now carry real
`counterfactual_influence` evidence — 200 total real masked-memory comparisons (100
per foundation), matching the n=20 runs exactly.** No fresh counterfactual pairs were
computed for the other 200 records — this is real evidence being folded in, not new
evidence being generated (a fresh, full 240-record counterfactual sweep would ~5x the
LLM call count and was not requested). The original pre-attach file is preserved at
`clean_agent_dataset_locomo_120x2.PRE_COUNTERFACTUAL_ATTACH.json.bak` for reference.
All 240 records re-validated against `clean_agent_dataset_record_schema.json` after
the attach — 0 errors.
- Selection policy, creation policy (`equivalent_to`/`conflicts_with`,
  `superseded_by`-detection) — all deferred per the standing decisions this session
  recorded; `superseded_by`-detection is implemented (`creation_policy.py`) but not
  wired into this campaign path.
- `clean_agent_memory_v1` / any `phase3_reference/` artifact — untouched.

## 5. Regression / integrity

No existing test, schema, or frozen artifact was modified to produce this run. The
schema validation in §2 is a direct, automated check, not a manual spot-check.

## 6. Freeze status

Not a frozen decision — a dated, real execution record. The dataset file itself is a
real, usable artifact for whatever comes next (Phase 4, or further Phase 3 analysis),
with the exact-match scoring caveat in §3 as required reading before anyone
interprets its `evaluation_result` fields as an accuracy measurement.
