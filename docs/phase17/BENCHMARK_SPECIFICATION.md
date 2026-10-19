# MAMBench Canonical Benchmark Specification (Phase 17, Workstream I)

This specification names the fields a MAMBench scenario and result carry. It **reuses
existing project schemas verbatim** wherever one already covers a field — it does not
introduce a second, competing schema. Where this document names a field that does not
literally exist as a dataclass attribute, it names the existing accessor that supplies it.

## 1. Scenario identity

| Spec field | Existing implementation |
|---|---|
| `scenario_id` | `PoisonRecord.scenario_id` (`phase17/poison_sets.py`) / `MemoryScenario.scenario_id` (`phase6/defense/orchestration/pipeline.py`) |
| `dataset_id` | The corpus a record was drawn from — `"locomo"`, `"longmemeval"`, `"convomem"`, `"perltqa"` (`phase17/{extra_datasets,perltqa}.py`, `phase14/track_a_longmemeval.py`) |
| `conversation_id` / `episode_id` | LoCoMo task id embedded in `scenario_id` (`LOCOMO-T<n>-...`) or a `ScenarioPool.pool_id` (one pool = one real conversation/dialogue/event-group by construction, per `convomem_pools`/`perltqa_pools`'s own docstrings) |
| `attack_id` | `PoisonRecord.family` (`dsrm`, `farma`, `mpbench`, `minja`, `agentpoison`, `memorygraft`, `sleeper_memory_poisoning`) or `NovelAttack.mechanism` (`phase17/novel_attacks.py`) for an unseen mechanism |
| `attacker capability` | Documented per-family in `README.md`'s "Seven attacks" section (white-box/black-box/query-only/gated) |
| `injection surface` | The Common Attack Contract's `PoisonArtifact`/`InjectionEvent` (`phase4/shared/`) |
| `target stage` | One of `injection → admission → storage → retrieval → selection → exposure/use → propagation → influence → detection → attribution` (README's own lifecycle diagram) |
| `poison artifact ID` | `PoisonArtifact.artifact_id` (Common Attack Contract, `phase4/shared/`) |
| `trigger condition` | `Sleeper`-family only: `SleeperArtifact`'s trigger fields (`phase6/defense/sleeper/`); `N/A` otherwise |
| `split` | `PoisonRecord.split` — one of `signal_source`, `held_out_regen`, `held_out_evasion`, `held_out_novel`, `held_out_zh`, `held_out_extended`, `benign_<dataset>`, `frozen75` |
| `variant` | `PoisonRecord.variant` (evasion strategy: `plain`/`embedded`) or `None` |
| `parent_id` | `PoisonRecord.parent_id` — links a regenerated/evasion/translated record to its `signal_source` parent |

## 2. Environment / model identity

| Spec field | Existing implementation |
|---|---|
| `memory_foundation` | `MemoryFoundationAdapter.foundation_identity` (`phase3/evaluation/foundations/adapter.py`); `"clean agent"` (MockMem0Adapter) or `"A-mem-sys (live, C:\h4venv)"` (`phase3/evaluation/foundations_real/amem_real_adapter.py`) |
| `model_id` / `model_version` | Ollama model tag, e.g. `qwen2.5:7b`, `llama2` (`phase12/propagation/ollama_provider.py`) |
| `quantization` | Whatever Ollama's own pulled tag encodes (`Q4_K_M` default for these tags — not independently re-verified per run) |
| `inference_configuration` | `GenerationConfig` (`phase3/evaluation/llm/provider.py`): `temperature`, `seed`, `max_tokens`, `n_ctx`, `request_timeout_sec` |
| `reasoning/thinking mode` | `GenerationConfig.enable_thinking` (always `False` in this project) |

## 3. Defense identity

| Spec field | Existing implementation |
|---|---|
| `defense_configuration` | One of `phase14.defended_retrieval.REAL_CONFIGS` (`B0`..`B12`) |
| `composition_rule` | `phase6.defense.risk.risk_score.COMPOSITION_RULES` entry, where applicable |
| `threshold(s)` | Recorded in the config's own module docstring/constants (e.g. `StackedDetector.thr`, `CONSOLIDATION_REFLECTS_FLAGGED_SOURCE_THRESHOLD`) |

## 4. Result schema

Produced by `phase17.bench_runner.run()` (Workstream J) as one JSON artifact:

```json
{
  "manifest": {
    "scenario_id": "bench-<split>-<defense>",
    "split": "...", "defense": "...", "n_records": 0,
    "git_commit": "<sha or disclosed fallback>",
    "python_version": "...", "platform": "...",
    "timestamp_utc": "...", "seed_note": "..."
  },
  "summary": {"flagged": 0, "excluded": 0, "n": 0},
  "rows": [{"scenario_id": "...", "family": "...", "action": "ALLOW|...", "excluded": false, "flagged": false}]
}
```

Ground truth (`is_poison_ground_truth`, `attack_family_ground_truth`) is **evaluator-only**
per `phase6/defense/orchestration/pipeline.py`'s own module contract and is never passed
into a defense decision function — enforced structurally by `FORBIDDEN_SIGNAL_KEYS` /
`EvaluatorOnlyLeakageError` (`phase6/defense/policy/records.py`), verified in
`phase17/provenance_integrity.py::structural_forgery_is_rejected()`.

## 5. Evidence vocabulary

Every reported number carries (implicitly, by which module produced it) one of:
`OBSERVED` (a real defense decision or a real LLM/embedding output), `INFERRED`
(a calibrated probability, e.g. `phase17/prob_attribution.py`), `COUNTERFACTUAL`
(Phase 11's z-score/LOFO ablations), `EXPOSURE_ONLY` / `LINEAGE_REACHABILITY`
(`attribution/schema.py`'s own vocabulary). This specification does not introduce a new
tag; it points every new Phase 17 result at whichever of these labels already applies.

## 6. What this specification deliberately does NOT cover

Propagation/Sleeper/attribution's own richer per-metric schemas (`PAR`, `PR`, `SDR`,
`AMR`, `DGS`) are NOT re-derived under this schema — they remain reported in their own
Phase 7/8/9/10/12/13 report formats. `phase17/canonical_matrix.py`'s own `MATRIX_LIMITS`
disclose exactly which cells this specification's runner can and cannot currently fill.

## 7. Unified benchmark runner (added 2026-10-18)

`python -m mambench` is now the canonical entry point. It does not replace §4: the
`defence.held_out_*` tasks call `phase17.bench_runner.run()` and keep its JSON artifact; the
runner adds a registry of every task, one status vocabulary, and provenance on every result.

| Item | Where |
|---|---|
| Tracks, tasks, metrics (numerator and denominator for every proportion), split roles, requirements | `mambench/registry.json` (version 1.0.0: 7 tracks, 19 tasks, 28 metrics) |
| Result schema, statuses, aggregation | `mambench/schema.py` |
| Executors (one per task, wrapping frozen components) | `mambench/tasks.py` |
| Registry validation, requirement probes | `mambench/registry.py` |
| CLI and execution rules | `mambench/runner.py` |
| Tests (registry, schema, every failure path, a real smoke run) | `mambench/tests/` |

**Statuses.** COMPLETED; FAILED (exception, integrity violation, or a tracked file modified
during the task); BLOCKED (a declared requirement such as licensed data, Ollama or the
isolated Mem0 interpreter is unavailable; the task is not run); NOT_EVALUABLE (the evidence a
metric needs is absent; never reported as zero); UNSUPPORTED (registered as out of scope, e.g.
the 4 inapplicable MPBench classes; never run); SKIPPED (not selected; still listed).

**Result record.** `task_id`, `task_version`, `track`, `status`, `reason`, `split_role`,
`prior_runs_of_this_split` (from `holdout_ledger.jsonl`, for `published_eval` and
`frozen_holdout` tasks), `metrics` (each `{metric, group, kind, numerator, denominator,
value}`), `details`, and `provenance` (`registry_version`, `schema_version`, `config_hash`,
`implementation_digest` over the task's source files, `git_commit`, `git_dirty`, `seed`,
`python_version`, `platform`, start and finish times). `aggregate()` refuses results from
different registry versions or commits and reports no overall score.

**Adding a task.** Add an entry to `registry.json` (declare any new metric with its
numerator and denominator), add `run_<executor>(params, workdir)` to `mambench/tasks.py`
returning `(metrics, details)` or raising `NotEvaluable` / `IntegrityViolation`, and run
`python -m mambench validate` and `python -m pytest mambench/tests`. An executor writes only
inside `workdir`.
