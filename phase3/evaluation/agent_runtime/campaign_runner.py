"""Phase 3.3-E -- the controlled pilot campaign runner.

Executes RESET -> INGEST -> RETRIEVE -> SELECT -> EXPOSE -> GENERATE -> EVALUATE for
every (task, condition) pair in `campaign_sampling.build_pilot_sample()`, against a real
running `llama-server.exe` and real Mem0/A-MEM foundations. Must run under
`C:\\h4venv\\Scripts\\python.exe` (mem0ai and A-mem-sys are only importable there).

Reuses, unmodified: `agent_runtime.runner.run_agent_task`,
`agent_runtime.trace.evaluate_and_trace`/`evaluate_and_trace_with_identity`,
`agent_runtime.identity.resolve_via_direct_assignment`,
`agent_runtime.citation.classify_citation_based_usage`, and the real
`RealMem0Adapter`/`RealAMemAdapter` from 3.2-H.4/3.3-D. No new evaluator, no new metric.

CONTAMINATION CONTROL
--------------------------------------------------------------------------------
A fresh `RESET` is called before every single (task, condition) foundation ingestion --
never shared across tasks, never shared between Condition B and Condition C (which use
entirely separate adapter instances in any case). This is verified structurally (a new
`reset()` call precedes every `INGEST` block below) and empirically re-confirmed for both
foundations in 3.3-D (round-1 content is genuinely gone after `reset()`, round-2 is
uncontaminated).
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Optional

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from phase3.evaluation.agent.conditions import CONDITION_NO_MEMORY, CONDITION_RETRIEVED_MEMORY
from phase3.evaluation.agent_runtime.campaign_sampling import PilotTask, build_pilot_sample
from phase3.evaluation.agent_runtime.citation import classify_citation_based_usage
from phase3.evaluation.agent_runtime.identity import resolve_via_direct_assignment, verify_collision_safety
from phase3.evaluation.agent_runtime.runner import AgentTaskInput, RunConfiguration, run_agent_task
from phase3.evaluation.agent_runtime.trace import evaluate_and_trace, evaluate_and_trace_with_identity
from phase3.evaluation.foundations.adapter import FOUNDATION_AVAILABLE
from phase3.evaluation.llm.provider import (
    LlamaServerEndpoint,
    LlamaServerProvider,
    clean_baseline_generation_config,
)

_DATA_ROOT = _REPO_ROOT / "data" / "processed"
OUTPUT_DIR = _REPO_ROOT / "phase3" / "experiments" / "results"
DATASET_REVISION = "phase3.2-frozen"

# The single representative task/condition repeated N=3 for a basic determinism check,
# per the mission's "N=3 for a carefully selected subset where runtime permits."
REPEATED_TASK_ID = "ecf5a096af5598393ce49c80"
REPEATED_CONDITION = "B"
REPEATED_N = 3


def _gpu_vram_mib():
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"], text=True
        )
        return int(out.strip().splitlines()[0])
    except Exception as exc:  # pragma: no cover
        return f"UNAVAILABLE: {exc}"


def _load_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


def _ingest_pool(dataset: str, ingest_key_field: str, ingest_key_value: str):
    """Yield real memory_records.jsonl rows belonging to one task's ingestion pool --
    never fabricated, never rewritten, never filtered for difficulty."""
    if dataset == "locomo":
        conv_id, session_id = ingest_key_value.split("/", 1)
        for row in _load_jsonl(_DATA_ROOT / dataset / "memory_records.jsonl"):
            if row["conversation_id"] == conv_id and row["session_id"] == session_id:
                yield row
    elif dataset == "longmemeval":
        for row in _load_jsonl(_DATA_ROOT / dataset / "memory_records.jsonl"):
            if row["source_record_id"] == ingest_key_value:
                yield row
    else:
        raise ValueError(f"Unsupported dataset for ingestion: {dataset!r}")


def _run_condition_a(task: PilotTask, llm_provider, generation_config, experiment_id: str) -> Mapping[str, Any]:
    t0 = time.time()
    outcome = run_agent_task(
        AgentTaskInput(task_id=task.task_id, prompt=task.question, condition=CONDITION_NO_MEMORY),
        foundation=None,
        config=RunConfiguration(llm_provider=llm_provider, generation_config=generation_config),
    )
    latency = time.time() - t0
    trace = evaluate_and_trace(
        outcome, experiment_id=experiment_id, dataset=task.dataset, dataset_revision=DATASET_REVISION,
        record_id=task.task_id, expected_answer=task.answer, gold_evidence_ids=task.evidence_memory_ids,
    )
    return {"trace": trace, "latency_sec": latency, "vram_mib": _gpu_vram_mib()}


def _run_condition_mem0(task: PilotTask, llm_provider, generation_config, experiment_id: str) -> Mapping[str, Any]:
    from phase3.evaluation.foundations_real.mem0_real_adapter import RealMem0Adapter

    foundation = RealMem0Adapter()
    init_field = foundation.initialize(
        {"embedding_model": "sentence-transformers/all-MiniLM-L6-v2", "collection_name": f"campaign_3_3e_{task.task_id}_mem0"}
    )
    if init_field.availability != FOUNDATION_AVAILABLE:
        return {"error": f"RealMem0Adapter.initialize() -> {init_field.availability}", "note": init_field.note}
    reset_t0 = time.time()
    reset_field = foundation.reset()
    reset_latency = time.time() - reset_t0
    if reset_field.availability != FOUNDATION_AVAILABLE:
        return {"error": "RealMem0Adapter.reset() did not report AVAILABLE -- aborting, not proceeding on unverified isolation."}

    vram_before_ingest = _gpu_vram_mib()
    t_ingest0 = time.time()
    ingested_source_ids = []
    for row in _ingest_pool(task.dataset, task.ingest_key_field, task.ingest_key_value):
        source_id = row["memory_id"]
        add_field = foundation.add_memory(
            memory_id=source_id,
            content={"text": f"{row['source_role']}: {row['content']}"},
            metadata={"user_id": f"campaign-{task.task_id}", "source_memory_id": source_id},
        )
        if add_field.availability == FOUNDATION_AVAILABLE:
            ingested_source_ids.append(source_id)
    ingest_latency = time.time() - t_ingest0
    vram_after_ingest = _gpu_vram_mib()

    t_run0 = time.time()
    outcome = run_agent_task(
        AgentTaskInput(
            task_id=task.task_id, prompt=task.question, condition=CONDITION_RETRIEVED_MEMORY,
            retrieval_query={"text": task.question, "user_id": f"campaign-{task.task_id}"}, top_k=5,
        ),
        foundation=foundation,
        config=RunConfiguration(llm_provider=llm_provider, generation_config=generation_config),
    )
    run_latency = time.time() - t_run0
    vram_after_run = _gpu_vram_mib()

    trace = evaluate_and_trace_with_identity(
        outcome, foundation, experiment_id=experiment_id, dataset=task.dataset, dataset_revision=DATASET_REVISION,
        record_id=task.task_id, expected_answer=task.answer, gold_evidence_ids=task.evidence_memory_ids,
        ingested_source_memory_ids=ingested_source_ids,
    )
    foundation.shutdown()
    return {
        "trace": trace, "reset_latency_sec": reset_latency, "ingest_latency_sec": ingest_latency,
        "run_latency_sec": run_latency, "ingested_count": len(ingested_source_ids),
        "vram_before_ingest_mib": vram_before_ingest, "vram_after_ingest_mib": vram_after_ingest,
        "vram_after_run_mib": vram_after_run,
    }


def _run_condition_amem(task: PilotTask, llm_provider, generation_config, experiment_id: str) -> Mapping[str, Any]:
    from phase3.evaluation.foundations_real.amem_real_adapter import RealAMemAdapter

    foundation = RealAMemAdapter()
    init_field = foundation.initialize({"embedding_model": "all-MiniLM-L6-v2"})
    if init_field.availability != FOUNDATION_AVAILABLE:
        return {"error": f"RealAMemAdapter.initialize() -> {init_field.availability}", "note": init_field.note}
    reset_t0 = time.time()
    reset_field = foundation.reset()
    reset_latency = time.time() - reset_t0
    if reset_field.availability != FOUNDATION_AVAILABLE:
        return {"error": "RealAMemAdapter.reset() did not report AVAILABLE -- aborting, not proceeding on unverified isolation."}

    vram_before_ingest = _gpu_vram_mib()
    t_ingest0 = time.time()
    resolutions = {}
    evolution_note = None
    for row in _ingest_pool(task.dataset, task.ingest_key_field, task.ingest_key_value):
        source_id = row["memory_id"]
        add_field = foundation.add_memory(
            memory_id=source_id,
            content={"text": f"{row['source_role']}: {row['content']}"},
            metadata={"tags": ["campaign", task.dataset], "keywords": [row["source_role"]], "context": task.task_id},
        )
        if add_field.availability == FOUNDATION_AVAILABLE:
            resolution = resolve_via_direct_assignment(source_id, add_field.value)
            resolutions[resolution.foundation_memory_id] = resolution
    ingest_latency = time.time() - t_ingest0
    vram_after_ingest = _gpu_vram_mib()
    collision_report = verify_collision_safety(resolutions)

    t_run0 = time.time()
    outcome = run_agent_task(
        AgentTaskInput(
            task_id=task.task_id, prompt=task.question, condition=CONDITION_RETRIEVED_MEMORY,
            retrieval_query={"text": task.question}, top_k=5,
        ),
        foundation=foundation,
        config=RunConfiguration(llm_provider=llm_provider, generation_config=generation_config),
    )
    run_latency = time.time() - t_run0
    vram_after_run = _gpu_vram_mib()

    # A-MEM's retrieved/selected ids ARE ALREADY source ids (DIRECT_ASSIGNMENT) -- no
    # separate resolved-space translation is needed the way Mem0's METADATA_LOOKUP
    # strategy requires it; evaluate_and_trace() alone is already correct-space here.
    trace = evaluate_and_trace(
        outcome, experiment_id=experiment_id, dataset=task.dataset, dataset_revision=DATASET_REVISION,
        record_id=task.task_id, expected_answer=task.answer, gold_evidence_ids=task.evidence_memory_ids,
        store_memory_ids=list(resolutions.keys()),
    )
    citation = classify_citation_based_usage(outcome.execution_result.answer, outcome.exposed_memory_ids)
    foundation.shutdown()
    return {
        "trace": trace, "reset_latency_sec": reset_latency, "ingest_latency_sec": ingest_latency,
        "run_latency_sec": run_latency, "ingested_count": len(resolutions),
        "identity_collision_free": collision_report.collision_free,
        "citation_diagnostic": {"status": citation.status, "cited_memory_ids": list(citation.cited_memory_ids)},
        "vram_before_ingest_mib": vram_before_ingest, "vram_after_ingest_mib": vram_after_ingest,
        "vram_after_run_mib": vram_after_run,
    }


def run_campaign() -> Mapping[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    sample = build_pilot_sample()

    endpoint = LlamaServerEndpoint(base_url="http://127.0.0.1:8811")
    llm_provider = LlamaServerProvider(endpoint)
    print("Verifying llama-server reachability and identity...")
    if not llm_provider.health_check(timeout_sec=5.0):
        raise RuntimeError("llama-server not reachable at http://127.0.0.1:8811 -- start it first.")
    identity_check = llm_provider.verify_server_identity()
    print(f"  Server identity verified: {identity_check['system_fingerprint']}")
    generation_config = clean_baseline_generation_config(n_ctx=4096, max_tokens=64)

    results = []
    for task in sample:
        print(f"\n########## TASK {task.task_id} ({task.dataset}, pool_size={task.pool_size}) ##########")
        print(f"  Q: {task.question}")
        entry: dict = {
            "task_id": task.task_id, "dataset": task.dataset, "pool_size": task.pool_size,
            "conditions_to_run": list(task.conditions_to_run), "runs": {},
        }

        print("  -- Condition A (no memory) --")
        entry["runs"]["A"] = _run_condition_a(
            task, llm_provider, generation_config, f"3.3-e-{task.task_id}-A-run1"
        )
        print(f"     answer={entry['runs']['A']['trace']['agent_output']!r} "
              f"failure_stage={entry['runs']['A']['trace']['failure_stage']}")

        if "B" in task.conditions_to_run:
            print("  -- Condition B (Mem0) --")
            entry["runs"]["B"] = _run_condition_mem0(
                task, llm_provider, generation_config, f"3.3-e-{task.task_id}-B-run1"
            )
            b_trace = entry["runs"]["B"].get("trace")
            if b_trace:
                print(f"     answer={b_trace['agent_output']!r} base_failure_stage={b_trace['failure_stage']} "
                      f"resolved_failure_stage={b_trace['resolved_evaluation']['failure_stage']} "
                      f"ingest={entry['runs']['B']['ingest_latency_sec']:.2f}s")

        if "C" in task.conditions_to_run:
            print("  -- Condition C (A-MEM) --")
            entry["runs"]["C"] = _run_condition_amem(
                task, llm_provider, generation_config, f"3.3-e-{task.task_id}-C-run1"
            )
            c_trace = entry["runs"]["C"].get("trace")
            if c_trace:
                print(f"     answer={c_trace['agent_output']!r} failure_stage={c_trace['failure_stage']} "
                      f"ingest={entry['runs']['C']['ingest_latency_sec']:.2f}s")
        else:
            entry["runs"]["C"] = {"status": "SCOPE_EXCLUDED_RESOURCE_COST",
                                   "note": "LongMemEval haystack too large for A-MEM's per-item evolution-attempt cost; see campaign_sampling.py docstring."}

        results.append(entry)

    # -------------------------------------------------------------------
    # N=3 repeated-run determinism check on one representative (task, condition)
    # -------------------------------------------------------------------
    print(f"\n########## REPEATED RUNS (N={REPEATED_N}): task={REPEATED_TASK_ID}, condition={REPEATED_CONDITION} ##########")
    repeated_task = next(t for t in sample if t.task_id == REPEATED_TASK_ID)
    repeated_runs = []
    for i in range(1, REPEATED_N + 1):
        r = _run_condition_mem0(repeated_task, llm_provider, generation_config, f"3.3-e-repeat-{REPEATED_TASK_ID}-B-run{i}")
        repeated_runs.append(r)
        if r.get("trace"):
            print(f"  run {i}: answer={r['trace']['agent_output']!r} "
                  f"resolved_failure_stage={r['trace']['resolved_evaluation']['failure_stage']}")

    answers = [r["trace"]["agent_output"] for r in repeated_runs if r.get("trace")]
    stages = [r["trace"]["resolved_evaluation"]["failure_stage"] for r in repeated_runs if r.get("trace")]
    determinism_note = (
        "identical answer text and resolved failure_stage across all N runs"
        if len(set(answers)) <= 1 and len(set(stages)) <= 1
        else "DIVERGED across runs -- see individual traces"
    )

    campaign_result = {
        "campaign": "3.3-E controlled pilot",
        "sampling_seed": 33005,
        "server_identity": identity_check,
        "generation_config": {
            "temperature": generation_config.temperature, "seed": generation_config.seed,
            "max_tokens": generation_config.max_tokens, "enable_thinking": generation_config.enable_thinking,
            "n_ctx": generation_config.n_ctx,
        },
        "tasks": results,
        "repeated_runs": {
            "task_id": REPEATED_TASK_ID, "condition": REPEATED_CONDITION, "n": REPEATED_N,
            "runs": repeated_runs, "determinism_note": determinism_note,
        },
    }

    output_path = OUTPUT_DIR / "campaign_3_3e_result.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(campaign_result, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nCampaign result written to {output_path}")
    return campaign_result


if __name__ == "__main__":
    run_campaign()
