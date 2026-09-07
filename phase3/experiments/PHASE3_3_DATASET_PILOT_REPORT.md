# Clean-Agent Behavioral Dataset — Bounded Pilot — Execution Report

Status: **COMPLETE**. Execution + implementation report for the pilot phase of
[PHASE3_CLEAN_DATASET_CONSTRUCTION_PLAN.md](../specification/PHASE3_CLEAN_DATASET_CONSTRUCTION_PLAN.md),
after the user's decisions: include a real Condition B (gold-evidence) pass, scale to
120 LoCoMo tasks per foundation, use the proposed schema plus raw ledger/event
references, keep selection/creation policies deferred.

## 1. What was built (additive, nothing existing modified)

- [`agent_runtime/gold_evidence_runner.py`](../evaluation/agent_runtime/gold_evidence_runner.py)
  (new) — real execution of `EVALUATION_CONTRACT.md` Condition B (GOLD_EVIDENCE):
  builds `agent_visible_context` directly from gold evidence content (re-keyed under
  opaque `evidence-slot-N` ids, never the literal `gold_evidence_id`), skips
  retrieval/selection entirely, reuses `runner.py`'s own `generate_with_retries`/
  `render_messages`/boundary-and-leakage-check discipline verbatim. `runner.py` itself
  is untouched — its own `AgentTaskInput.__post_init__()` still rejects GOLD_EVIDENCE,
  exactly as designed; this module is the evaluator-side counterpart its own comment
  pointed to.
- [`agent_runtime/campaign_formal_runner.py`](../evaluation/agent_runtime/campaign_formal_runner.py)
  — added `run_condition_gold_evidence()` / `run_formal_gold_evidence_locomo()`,
  deliberately NOT named "Condition B" (this file's own existing convention already
  uses A/B/C for no-memory/Mem0/A-MEM — a different axis from the frozen contract's
  A/B/C). Runs gold evidence ONCE PER TASK, not once per foundation, since evidence
  content is foundation-independent.
- [`agent_runtime/dataset_record_assembler.py`](../evaluation/agent_runtime/dataset_record_assembler.py)
  (new) — assembles one record per (task_id, foundation) from the four raw result
  lists, per the approved schema plus `raw_ledger_refs`/`provenance_graph_ref` (never a
  copy of ledger contents — references only, reopened via
  `canonical_wiring.canonical_store_dir_for_pool()` + `provenance_graph.
  build_provenance_graph()` on demand). `observability_coverage` is honest per record:
  `rejected_events_possible`/`relationship_detected_possible`/`used_events_possible`
  are `False` project-wide (deferred policies), `counterfactual_measured` defaults
  `False` and is only flipped by the separate `attach_counterfactual_evidence()` helper
  where a real prior H.4-A measurement exists for that (task, foundation).
- [`schemas/clean_agent_dataset_record_schema.json`](../schemas/clean_agent_dataset_record_schema.json)
  (new) — export-only JSON Schema for the assembled record, mirroring
  `provenance_graph_schema.json`'s own convention.
- [`tests/test_gold_evidence_runner.py`](../evaluation/tests/test_gold_evidence_runner.py)
  (new, 4 tests) — fake-provider unit tests: success path, literal-gold-evidence-id
  never leaks into `agent_visible_context`, generation-failure reporting, empty-evidence
  edge case.

## 2. Real pilot run

4 real LoCoMo tasks (`build_formal_sample(4)["locomo"]`, 3 unique pools), real
infrastructure throughout: `RealMem0Adapter`, `RealAMemAdapter` (post-`inspect_memory()`
fix), real Qwen3-8B via `llama-server.exe` (`b10717`/`a32af33de`, `-ngl 99 --ctx-size
16384 --parallel 4`, freshly launched this session, health-checked before the run).

| Condition | Result |
|---|---|
| A (NO_MEMORY) | 4/4 SUCCESSFUL_EVALUATION |
| GOLD_EVIDENCE | 4/4 SUCCESSFUL_EVALUATION, 0 missing evidence ids, 0 content-leakage detections |
| B (Mem0, RETRIEVED_MEMORY) | 4/4 SUCCESSFUL_EVALUATION |
| C (A-MEM, RETRIEVED_MEMORY) | 4/4 SUCCESSFUL_EVALUATION |

16/16 real executions succeeded. Assembled into 8 real dataset records (4 tasks × 2
foundations) via `assemble_dataset_records()`; **all 8 validate against
`clean_agent_dataset_record_schema.json`** (`jsonschema` 4.26.0, direct validation, not
a hand-check).

One honest observed result, not a mechanism defect: the gold-evidence ceiling on this
4-task pilot was 0/4 correct (`ANSWER_INCORRECT` for all four, including under
GOLD_EVIDENCE). Per `agent/diagnostics.py`'s own documented framing, this is reported
as an OBSERVED result for this tiny sample under this specific reasoning behavior, never
a theoretical ceiling — not investigated further here since the pilot's purpose is
mechanism validation, not answer-quality analysis. Raw pilot artifacts:
`phase3/experiments/results/canonical_store/dataset_pilot_raw_results.json`,
`dataset_pilot_records.json`.

## 3. Regression

Full suite re-run after these additions: **1640 passed, 14 skipped, 1 pre-existing
unrelated failure** (`test_candidate_memoryarena.py::test_raw_fingerprint_file_count_matches_actual_raw_directory`
— confirmed unrelated in this session before this work began; still unrelated, untouched).
4/4 new `test_gold_evidence_runner.py` tests pass.

## 4. What was NOT attempted here

- Fresh counterfactual-influence measurement for the full 120×2 scale — this pilot/full
  run does not compute new counterfactual pairs. `attach_counterfactual_evidence()`
  exists to fold in this session's already-executed real n=6/n=20 measurements by
  (task_id, foundation) match; tasks outside that overlap get
  `counterfactual_measured=False`, honestly, not fabricated. A full fresh counterfactual
  sweep at 120-task scale would roughly 5x the LLM call count for masked re-runs and
  was not requested — flagged here for a future decision, not silently done or silently
  skipped.
- Selection policy, creation policy — untouched, per the standing deferral.
- `clean_agent_memory_v1` / any `phase3_reference/` artifact — untouched.

## 5. Next step

Full 120-task LoCoMo run (both foundations, all four conditions) launched in the
background immediately after this pilot validated, per the user's explicit
pilot-then-scale instruction. See the follow-up completion report for real results.
