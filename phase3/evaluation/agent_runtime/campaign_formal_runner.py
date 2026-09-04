"""Phase 3.3-G -- formal campaign execution: Conditions A (no-memory) and B (Mem0) at
full N=120-per-dataset, with per-unique-pool (session/haystack) ingestion sharing.

Condition C (A-MEM) is NOT executed at full scale by this module -- see
`campaign_formal_amem_probe.py` for the small, explicitly-labeled real cost measurement
run instead, and the 3.3-G final report for the STOP/revision-request this triggered
(projected ~28 hours for LongMemEval, ~1.9-3 hours for LoCoMo at the measured real
per-item rate -- see report for the exact real numbers).

Reuses `agent_runtime.runner.run_agent_task`, `agent_runtime.trace.evaluate_and_trace`/
`evaluate_and_trace_with_identity`, `campaign_runner._ingest_pool` (unmodified) --
zero new evaluator/metric logic.

ISOLATION: a fresh RESET+INGEST happens once per unique (dataset, session_or_haystack)
group; every task within that group gets its own independent RETRIEVE->GENERATE->
EVALUATE pass (read-only w.r.t. the shared store, verified by inspecting
`runner.py::_retrieve_and_select`, unchanged since 3.3-B: only `retrieve()`/
`inspect_memory()` are ever called during evaluation, never `add_memory()`). No task's
generated answer or evaluation result is ever written back into the foundation.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Mapping

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from phase3.evaluation.agent.conditions import CONDITION_NO_MEMORY, CONDITION_RETRIEVED_MEMORY
from phase3.evaluation.agent_runtime.campaign_runner import _ingest_pool
from phase3.evaluation.agent_runtime.campaign_sampling import build_formal_sample
from phase3.evaluation.agent_runtime.runner import AgentTaskInput, RunConfiguration, run_agent_task
from phase3.evaluation.agent_runtime.trace import evaluate_and_trace, evaluate_and_trace_with_identity
from phase3.evaluation.foundations.adapter import FOUNDATION_AVAILABLE
from phase3.evaluation.llm.provider import (
    LlamaServerEndpoint,
    LlamaServerProvider,
    clean_baseline_generation_config,
)

DATASET_REVISION = "phase3.2-frozen"
OUTPUT_DIR = _REPO_ROOT / "phase3" / "experiments" / "results"


def _gpu_vram_mib():
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"], text=True
        )
        return int(out.strip().splitlines()[0])
    except Exception as exc:  # pragma: no cover
        return f"UNAVAILABLE: {exc}"


def _group_by_pool(tasks):
    groups: dict = {}
    for t in tasks:
        key = (t.dataset, t.ingest_key_value)
        groups.setdefault(key, []).append(t)
    return groups


def run_condition_a(all_tasks, llm_provider, generation_config, campaign_id):
    results = []
    for task in all_tasks:
        t0 = time.time()
        try:
            outcome = run_agent_task(
                AgentTaskInput(task_id=task.task_id, prompt=task.question, condition=CONDITION_NO_MEMORY),
                foundation=None,
                config=RunConfiguration(llm_provider=llm_provider, generation_config=generation_config),
            )
            latency = time.time() - t0
            trace = evaluate_and_trace(
                outcome, experiment_id=f"{campaign_id}-{task.dataset}-{task.task_id}-A",
                dataset=task.dataset, dataset_revision=DATASET_REVISION, record_id=task.task_id,
                expected_answer=task.answer, gold_evidence_ids=task.evidence_memory_ids,
            )
            results.append({
                "task_id": task.task_id, "dataset": task.dataset, "status": "SUCCESSFUL_EVALUATION",
                "trace": trace, "latency_sec": latency, "vram_mib": _gpu_vram_mib(),
            })
        except Exception as exc:
            results.append({
                "task_id": task.task_id, "dataset": task.dataset, "status": "EXECUTION_FAILURE",
                "error": repr(exc), "latency_sec": time.time() - t0,
            })
    return results


def run_condition_b_mem0(all_tasks, llm_provider, generation_config, campaign_id):
    from phase3.evaluation.foundations_real.mem0_real_adapter import RealMem0Adapter
    import hashlib

    groups = _group_by_pool(all_tasks)
    results = []
    for (dataset, pool_key), tasks_in_pool in sorted(groups.items()):
        foundation = RealMem0Adapter()
        collection_name = "g_" + hashlib.sha256(f"{dataset}:{pool_key}".encode()).hexdigest()[:16]
        init_field = foundation.initialize(
            {"embedding_model": "sentence-transformers/all-MiniLM-L6-v2", "collection_name": collection_name}
        )
        if init_field.availability != FOUNDATION_AVAILABLE:
            for task in tasks_in_pool:
                results.append({"task_id": task.task_id, "dataset": dataset, "status": "ENVIRONMENT_FAILURE",
                                 "error": f"initialize() -> {init_field.availability}"})
            continue
        reset_t0 = time.time()
        reset_field = foundation.reset()
        reset_latency = time.time() - reset_t0
        if reset_field.availability != FOUNDATION_AVAILABLE:
            for task in tasks_in_pool:
                results.append({"task_id": task.task_id, "dataset": dataset, "status": "ENVIRONMENT_FAILURE",
                                 "error": "reset() not AVAILABLE"})
            continue

        t_ingest0 = time.time()
        ingested_ids = []
        for row in _ingest_pool(dataset, tasks_in_pool[0].ingest_key_field, pool_key):
            source_id = row["memory_id"]
            add_field = foundation.add_memory(
                memory_id=source_id,
                content={"text": f"{row['source_role']}: {row['content']}"},
                metadata={"user_id": f"g-{dataset}-{pool_key}", "source_memory_id": source_id},
            )
            if add_field.availability == FOUNDATION_AVAILABLE:
                ingested_ids.append(source_id)
        ingest_latency = time.time() - t_ingest0

        for task in tasks_in_pool:
            t0 = time.time()
            try:
                outcome = run_agent_task(
                    AgentTaskInput(
                        task_id=task.task_id, prompt=task.question, condition=CONDITION_RETRIEVED_MEMORY,
                        retrieval_query={"text": task.question, "user_id": f"g-{dataset}-{pool_key}"}, top_k=5,
                    ),
                    foundation=foundation,
                    config=RunConfiguration(llm_provider=llm_provider, generation_config=generation_config),
                )
                run_latency = time.time() - t0
                trace = evaluate_and_trace_with_identity(
                    outcome, foundation, experiment_id=f"{campaign_id}-{dataset}-{task.task_id}-B",
                    dataset=dataset, dataset_revision=DATASET_REVISION, record_id=task.task_id,
                    expected_answer=task.answer, gold_evidence_ids=task.evidence_memory_ids,
                    ingested_source_memory_ids=ingested_ids,
                )
                results.append({
                    "task_id": task.task_id, "dataset": dataset, "status": "SUCCESSFUL_EVALUATION",
                    "trace": trace, "reset_latency_sec": reset_latency, "ingest_latency_sec": ingest_latency,
                    "run_latency_sec": run_latency, "pool_key": pool_key, "ingested_count": len(ingested_ids),
                    "vram_mib": _gpu_vram_mib(),
                })
            except Exception as exc:
                results.append({"task_id": task.task_id, "dataset": dataset, "status": "EXECUTION_FAILURE",
                                 "error": repr(exc), "pool_key": pool_key})
        foundation.shutdown()
    return results


def run_condition_c_amem(all_tasks, llm_provider, generation_config, campaign_id, checkpoint_path=None, pool_filter=None):
    """Condition C (A-MEM), same per-unique-pool sharing pattern as Condition B, using
    the DIRECT_ASSIGNMENT identity strategy (verified in 3.3-D/E/F.1: A-mem-sys honors
    a caller-supplied id directly, so no METADATA_LOOKUP round-trip is needed and
    retrieved/selected ids from `evaluate_and_trace()` are ALREADY source-space).

    CHECKPOINTING (added after a real, observed failure mode: this run was externally
    terminated -- process AND llama-server both killed, no Python traceback -- partway
    through its first attempt at this ~3.9h run, losing all progress since nothing had
    been persisted incrementally). If `checkpoint_path` is given: (1) any already-
    completed pool (all its tasks present with a real status) is loaded from the
    checkpoint file and SKIPPED, not re-ingested or re-generated -- this does not
    change what is measured, only avoids repeating already-obtained real results; (2)
    the checkpoint file is rewritten after EVERY pool completes, so a kill loses at
    most one in-progress pool's worth of work (~5-35 min at this campaign's measured
    per-pool cost), not the whole run.
    """
    from phase3.evaluation.agent_runtime.citation import classify_citation_based_usage
    from phase3.evaluation.agent_runtime.identity import resolve_via_direct_assignment, verify_collision_safety
    from phase3.evaluation.foundations_real.amem_real_adapter import RealAMemAdapter

    groups = _group_by_pool(all_tasks)

    results = []
    completed_task_ids = set()
    if checkpoint_path and Path(checkpoint_path).exists():
        with open(checkpoint_path, "r", encoding="utf-8") as f:
            results = json.load(f)
        completed_task_ids = {r["task_id"] for r in results}
        print(f"  Resuming from checkpoint: {len(completed_task_ids)} tasks already done.")

    def _save_checkpoint():
        if checkpoint_path:
            with open(checkpoint_path, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False, default=str)

    for (dataset, pool_key), tasks_in_pool in sorted(groups.items()):
        if pool_filter is not None and pool_key not in pool_filter:
            continue  # not this worker's partition -- a parallel sibling process owns it
        if all(t.task_id in completed_task_ids for t in tasks_in_pool):
            continue  # entire pool already completed in a prior run -- skip re-ingestion
        foundation = RealAMemAdapter()
        init_field = foundation.initialize({"embedding_model": "all-MiniLM-L6-v2"})
        if init_field.availability != FOUNDATION_AVAILABLE:
            for task in tasks_in_pool:
                results.append({"task_id": task.task_id, "dataset": dataset, "status": "ENVIRONMENT_FAILURE",
                                 "error": f"initialize() -> {init_field.availability}"})
            continue
        reset_t0 = time.time()
        reset_field = foundation.reset()
        reset_latency = time.time() - reset_t0
        if reset_field.availability != FOUNDATION_AVAILABLE:
            for task in tasks_in_pool:
                results.append({"task_id": task.task_id, "dataset": dataset, "status": "ENVIRONMENT_FAILURE",
                                 "error": "reset() not AVAILABLE"})
            continue

        t_ingest0 = time.time()
        resolutions = {}
        for row in _ingest_pool(dataset, tasks_in_pool[0].ingest_key_field, pool_key):
            source_id = row["memory_id"]
            add_field = foundation.add_memory(
                memory_id=source_id,
                content={"text": f"{row['source_role']}: {row['content']}"},
                metadata={"tags": ["g_formal", dataset], "keywords": [dataset], "context": pool_key},
            )
            if add_field.availability == FOUNDATION_AVAILABLE:
                resolution = resolve_via_direct_assignment(source_id, add_field.value)
                resolutions[resolution.foundation_memory_id] = resolution
        ingest_latency = time.time() - t_ingest0
        collision_report = verify_collision_safety(resolutions)

        for task in tasks_in_pool:
            if task.task_id in completed_task_ids:
                # Mid-pool resume: this specific task was already recorded before an
                # interruption, even though the pool as a whole wasn't fully done (the
                # pool-level `all(...)` check above only skips a pool when EVERY task
                # in it is already complete). Re-ingesting the pool above is harmless
                # (a fresh RESET+INGEST, idempotent), but re-evaluating an
                # already-recorded task here would create a duplicate task-condition
                # record -- skipped explicitly, never silently duplicated.
                continue
            t0 = time.time()
            try:
                outcome = run_agent_task(
                    AgentTaskInput(
                        task_id=task.task_id, prompt=task.question, condition=CONDITION_RETRIEVED_MEMORY,
                        retrieval_query={"text": task.question}, top_k=5,
                    ),
                    foundation=foundation,
                    config=RunConfiguration(llm_provider=llm_provider, generation_config=generation_config),
                )
                run_latency = time.time() - t0
                trace = evaluate_and_trace(
                    outcome, experiment_id=f"{campaign_id}-{dataset}-{task.task_id}-C",
                    dataset=dataset, dataset_revision=DATASET_REVISION, record_id=task.task_id,
                    expected_answer=task.answer, gold_evidence_ids=task.evidence_memory_ids,
                    store_memory_ids=list(resolutions.keys()),
                )
                citation = classify_citation_based_usage(outcome.execution_result.answer, outcome.exposed_memory_ids)
                results.append({
                    "task_id": task.task_id, "dataset": dataset, "status": "SUCCESSFUL_EVALUATION",
                    "trace": trace, "reset_latency_sec": reset_latency, "ingest_latency_sec": ingest_latency,
                    "run_latency_sec": run_latency, "pool_key": pool_key, "ingested_count": len(resolutions),
                    "identity_collision_free": collision_report.collision_free,
                    "citation_diagnostic": {"status": citation.status},
                    "vram_mib": _gpu_vram_mib(),
                })
            except Exception as exc:
                results.append({"task_id": task.task_id, "dataset": dataset, "status": "EXECUTION_FAILURE",
                                 "error": repr(exc), "pool_key": pool_key})
        foundation.shutdown()
        _save_checkpoint()
        print(f"  [checkpoint] pool {pool_key} done ({len(results)}/{len(all_tasks)} tasks total)", flush=True)
    return results


def run_formal_c_locomo(campaign_id: str = "3.3-G-formal-2026-09-01") -> Mapping[str, Any]:
    """Condition C (A-MEM), LoCoMo ONLY, at full N=120 -- per the explicit revision
    decision recorded in PHASE3_3_G_FORMAL_CAMPAIGN_REPORT.md section 22 ("Option 1"):
    run A-MEM x LoCoMo at full N now; LongMemEval x A-MEM remains formally deferred
    (projected ~57h, not attempted)."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    sample = build_formal_sample(120)
    loco_tasks = sample["locomo"]

    llm_provider = LlamaServerProvider(LlamaServerEndpoint(base_url="http://127.0.0.1:8811"))
    print("Verifying llama-server reachability and identity...")
    if not llm_provider.health_check(timeout_sec=5.0):
        raise RuntimeError("llama-server not reachable -- start it first.")
    identity_check = llm_provider.verify_server_identity()
    print(f"  Server identity verified: {identity_check['system_fingerprint']}")
    generation_config = clean_baseline_generation_config(n_ctx=4096, max_tokens=64)

    checkpoint_path = OUTPUT_DIR / "campaign_3_3g_formal_c_locomo_CHECKPOINT.json"
    print(f"\n=== CONDITION C: A-MEM, LoCoMo only ({len(loco_tasks)} tasks) ===")
    print(f"  Checkpointing to {checkpoint_path} after every pool.")
    t0 = time.time()
    results_c = run_condition_c_amem(
        loco_tasks, llm_provider, generation_config, campaign_id, checkpoint_path=checkpoint_path
    )
    elapsed = time.time() - t0
    print(f"  Condition C (LoCoMo) complete in {elapsed:.1f}s: "
          f"{sum(1 for r in results_c if r['status']=='SUCCESSFUL_EVALUATION')}/{len(results_c)} successful")

    output = {
        "campaign_id": campaign_id, "server_identity": identity_check,
        "n_tasks": len(loco_tasks), "elapsed_sec": elapsed, "results_c_locomo": results_c,
    }
    path = OUTPUT_DIR / "campaign_3_3g_formal_c_locomo_result.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nWritten to {path}")
    return output


def run_formal_c_longmemeval(campaign_id: str = "3.3-G-formal-2026-09-01") -> Mapping[str, Any]:
    """Phase 3.3-G.1 -- Condition C (A-MEM), LongMemEval, at full N=120. Completes the
    ONE cell Phase 3.3-G formally deferred (projected ~57h at a conservative rate;
    real measured rate, per the campaign_3_3g_formal_c_locomo run, was ~3.9-8s/item --
    still substantial across 60 haystacks averaging 431 items each). Uses the EXACT
    same frozen sample (`build_formal_sample(120)["longmemeval"]`, seed 33005,
    identical to what Conditions A and B already evaluated), the same
    `run_condition_c_amem` haystack-sharing/checkpointing machinery already validated
    on LoCoMo, and the same clean_baseline_generation_config. No configuration
    parameter differs from the frozen 3.3-G manifest."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    sample = build_formal_sample(120)
    lme_tasks = sample["longmemeval"]

    llm_provider = LlamaServerProvider(LlamaServerEndpoint(base_url="http://127.0.0.1:8811"))
    print("Verifying llama-server reachability and identity...")
    if not llm_provider.health_check(timeout_sec=5.0):
        raise RuntimeError("llama-server not reachable -- start it first.")
    identity_check = llm_provider.verify_server_identity()
    print(f"  Server identity verified: {identity_check['system_fingerprint']}")
    generation_config = clean_baseline_generation_config(n_ctx=4096, max_tokens=64)

    checkpoint_path = OUTPUT_DIR / "campaign_3_3g1_formal_c_longmemeval_CHECKPOINT.json"
    print(f"\n=== CONDITION C: A-MEM, LongMemEval only ({len(lme_tasks)} tasks, "
          f"{len(set(t.ingest_key_value for t in lme_tasks))} unique haystacks) ===")
    print(f"  Checkpointing to {checkpoint_path} after every pool.")
    t0 = time.time()
    results_c = run_condition_c_amem(
        lme_tasks, llm_provider, generation_config, campaign_id, checkpoint_path=checkpoint_path
    )
    elapsed = time.time() - t0
    print(f"  Condition C (LongMemEval) complete in {elapsed:.1f}s: "
          f"{sum(1 for r in results_c if r['status']=='SUCCESSFUL_EVALUATION')}/{len(results_c)} successful")

    output = {
        "campaign_id": campaign_id, "server_identity": identity_check,
        "n_tasks": len(lme_tasks), "elapsed_sec": elapsed, "results_c_longmemeval": results_c,
    }
    path = OUTPUT_DIR / "campaign_3_3g1_formal_c_longmemeval_result.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nWritten to {path}")
    return output


# ---------------------------------------------------------------------------
# Phase 3.3-G.1 -- parallel execution across multiple worker processes.
#
# WHY THIS IS A VALID, NON-METHODOLOGY-CHANGING SPEEDUP: A-MEM ingestion is CPU/
# embedding-bound, not GPU-bound (VRAM stays flat throughout every ingestion measured
# in 3.3-D/E/F.1/G/G.1), and every unique haystack already gets its own independent
# `RealAMemAdapter` instance with its own RESET -- there is no shared mutable state
# between haystacks in the existing (serial) implementation either. Running N worker
# processes, each owning a DISJOINT subset of the remaining haystacks, changes only the
# WALL-CLOCK SCHEDULE (parallel vs. serial), never the model, A-MEM configuration,
# retrieval, generation, or evaluation of any individual task -- the exact same
# per-task real work happens, just concurrently instead of sequentially. This is
# explicitly NOT "optimizing A-MEM after seeing its results" (the mission's prohibited
# case): no A-MEM behavior, timeout, or configuration changes; only which OS process
# runs a given haystack's already-identical work.
#
# ISOLATION: each worker writes to its OWN checkpoint file (never the shared main one)
# to avoid any concurrent-write race condition -- merged only after all workers finish
# a batch, by `merge_longmemeval_worker_checkpoints()`.
# ---------------------------------------------------------------------------


def _worker_checkpoint_path(worker_id: int) -> Path:
    return OUTPUT_DIR / f"campaign_3_3g1_formal_c_longmemeval_CHECKPOINT_worker{worker_id}.json"


def run_formal_c_longmemeval_worker(
    worker_id: int, num_workers: int, campaign_id: str = "3.3-G-formal-2026-09-01"
) -> Mapping[str, Any]:
    """One parallel worker's share of the remaining LongMemEval A-MEM haystacks.
    Deterministic partition: remaining (not-yet-done, per the MAIN checkpoint) pool
    keys, sorted, then round-robin-assigned via `sorted_pools[worker_id::num_workers]`
    -- reproducible from `worker_id`/`num_workers` alone, no randomness.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    sample = build_formal_sample(120)
    lme_tasks = sample["longmemeval"]
    all_pool_keys = sorted(set(t.ingest_key_value for t in lme_tasks))

    main_checkpoint = OUTPUT_DIR / "campaign_3_3g1_formal_c_longmemeval_CHECKPOINT.json"
    already_done_task_ids = set()
    if main_checkpoint.exists():
        with open(main_checkpoint, "r", encoding="utf-8") as f:
            already_done_task_ids = {r["task_id"] for r in json.load(f)}
    tasks_by_pool: dict = {}
    for t in lme_tasks:
        tasks_by_pool.setdefault(t.ingest_key_value, []).append(t)
    remaining_pools = [
        p for p in all_pool_keys
        if not all(t.task_id in already_done_task_ids for t in tasks_by_pool[p])
    ]
    my_pools = set(remaining_pools[worker_id::num_workers])

    print(f"Worker {worker_id}/{num_workers}: {len(remaining_pools)} pools remain overall, "
          f"{len(my_pools)} assigned to this worker: {sorted(my_pools)}")

    llm_provider = LlamaServerProvider(LlamaServerEndpoint(base_url="http://127.0.0.1:8811"))
    if not llm_provider.health_check(timeout_sec=5.0):
        raise RuntimeError("llama-server not reachable -- start it first.")
    identity_check = llm_provider.verify_server_identity()
    generation_config = clean_baseline_generation_config(n_ctx=4096, max_tokens=64)

    checkpoint_path = _worker_checkpoint_path(worker_id)
    t0 = time.time()
    results_c = run_condition_c_amem(
        lme_tasks, llm_provider, generation_config, campaign_id,
        checkpoint_path=checkpoint_path, pool_filter=my_pools,
    )
    elapsed = time.time() - t0
    print(f"Worker {worker_id} complete in {elapsed:.1f}s: "
          f"{sum(1 for r in results_c if r['status']=='SUCCESSFUL_EVALUATION')}/{len(results_c)} successful")
    return {"worker_id": worker_id, "elapsed_sec": elapsed, "results": results_c}


def merge_longmemeval_worker_checkpoints(num_workers: int) -> Mapping[str, Any]:
    """Merge the main checkpoint + every worker checkpoint into the unified main
    checkpoint (deduplicated by task_id, never overwriting a real result with nothing).
    If every one of the 120 frozen tasks is now present, also writes the final
    `campaign_3_3g1_formal_c_longmemeval_result.json`, matching the exact same output
    shape the serial `run_formal_c_longmemeval()` path produces.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    main_checkpoint = OUTPUT_DIR / "campaign_3_3g1_formal_c_longmemeval_CHECKPOINT.json"
    merged: dict = {}
    if main_checkpoint.exists():
        with open(main_checkpoint, "r", encoding="utf-8") as f:
            for r in json.load(f):
                merged[r["task_id"]] = r
    for worker_id in range(num_workers):
        wpath = _worker_checkpoint_path(worker_id)
        if wpath.exists():
            with open(wpath, "r", encoding="utf-8") as f:
                for r in json.load(f):
                    merged[r["task_id"]] = r  # last-writer-wins on task_id key,
                    # but no task_id is ever assigned to more than one worker's
                    # partition, so this is never actually a real conflict.

    merged_list = list(merged.values())
    with open(main_checkpoint, "w", encoding="utf-8") as f:
        json.dump(merged_list, f, indent=2, ensure_ascii=False, default=str)
    print(f"Merged checkpoint: {len(merged_list)} total tasks recorded.")

    sample = build_formal_sample(120)
    lme_tasks = sample["longmemeval"]
    expected_task_ids = {t.task_id for t in lme_tasks}
    have_task_ids = set(merged.keys())
    missing = expected_task_ids - have_task_ids
    if missing:
        print(f"Still missing {len(missing)}/{len(expected_task_ids)} tasks -- not yet complete.")
        return {"complete": False, "n_done": len(merged_list), "n_missing": len(missing)}

    output = {
        "campaign_id": "3.3-G-formal-2026-09-01", "n_tasks": len(lme_tasks),
        "results_c_longmemeval": [merged[t.task_id] for t in lme_tasks],
        "note": "Executed via parallel workers (Phase 3.3-G.1 speedup) then merged -- "
        "same per-task work as the serial path, only the wall-clock schedule differs.",
    }
    result_path = OUTPUT_DIR / "campaign_3_3g1_formal_c_longmemeval_result.json"
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False, default=str)
    print(f"All {len(lme_tasks)} tasks complete. Written to {result_path}")
    return {"complete": True, "n_done": len(merged_list)}


def run_formal_ab(campaign_id: str = "3.3-G-formal-2026-09-01") -> Mapping[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    sample = build_formal_sample(120)
    all_tasks = sample["locomo"] + sample["longmemeval"]

    llm_provider = LlamaServerProvider(LlamaServerEndpoint(base_url="http://127.0.0.1:8811"))
    print("Verifying llama-server reachability and identity...")
    if not llm_provider.health_check(timeout_sec=5.0):
        raise RuntimeError("llama-server not reachable -- start it first.")
    identity_check = llm_provider.verify_server_identity()
    print(f"  Server identity verified: {identity_check['system_fingerprint']}")
    generation_config = clean_baseline_generation_config(n_ctx=4096, max_tokens=64)

    print(f"\n=== CONDITION A: NO_MEMORY ({len(all_tasks)} tasks) ===")
    t0 = time.time()
    results_a = run_condition_a(all_tasks, llm_provider, generation_config, campaign_id)
    print(f"  Condition A complete in {time.time()-t0:.1f}s: "
          f"{sum(1 for r in results_a if r['status']=='SUCCESSFUL_EVALUATION')}/{len(results_a)} successful")

    print(f"\n=== CONDITION B: MEM0 ({len(all_tasks)} tasks) ===")
    t0 = time.time()
    results_b = run_condition_b_mem0(all_tasks, llm_provider, generation_config, campaign_id)
    print(f"  Condition B complete in {time.time()-t0:.1f}s: "
          f"{sum(1 for r in results_b if r['status']=='SUCCESSFUL_EVALUATION')}/{len(results_b)} successful")

    output = {
        "campaign_id": campaign_id,
        "server_identity": identity_check,
        "n_tasks": len(all_tasks),
        "results_a": results_a,
        "results_b": results_b,
    }
    path = OUTPUT_DIR / "campaign_3_3g_formal_ab_result.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nWritten to {path}")
    return output


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "c_locomo":
        run_formal_c_locomo()
    elif len(sys.argv) > 1 and sys.argv[1] == "c_longmemeval":
        run_formal_c_longmemeval()
    elif len(sys.argv) > 1 and sys.argv[1] == "c_longmemeval_worker":
        run_formal_c_longmemeval_worker(int(sys.argv[2]), int(sys.argv[3]))
    elif len(sys.argv) > 1 and sys.argv[1] == "c_longmemeval_merge":
        merge_longmemeval_worker_checkpoints(int(sys.argv[2]))
    else:
        run_formal_ab()
