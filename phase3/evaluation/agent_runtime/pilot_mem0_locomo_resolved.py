"""Phase 3.3-C REAL PILOT RERUN: the identical 3.3-B pilot (Qwen3-8B + real Mem0 + the
same real LoCoMo record, conv-26/session_1, task ecf5a096af5598393ce49c80), now evaluated
through `evaluate_and_trace_with_identity()` -- the SOURCE_MEMORY_ID identity bridge from
`identity.py`. Paired against the original 3.3-B result
(`phase3/experiments/pilots/pilot_3_3b_mem0_locomo_result.json`), which this script does
NOT modify -- it is preserved as the historical, unresolved-identity baseline.

Same run requirements as 3.3-B's `pilot_mem0_locomo.py`: must run under
`C:\\h4venv\\Scripts\\python.exe` (mem0ai is only importable there -- see that script's
module docstring for the full explanation, unchanged in this stage) with a real
`llama-server.exe` reachable at `http://127.0.0.1:8811`.

Per the mission's Part 16 instruction, this script runs Condition B TWICE (same RESET ->
INGEST once, two independent RETRIEVE -> SELECT -> EXPOSE -> GENERATE -> EVALUATE passes)
to check determinism, without claiming global LLM determinism from two samples.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from phase3.evaluation.agent.conditions import CONDITION_NO_MEMORY, CONDITION_RETRIEVED_MEMORY
from phase3.evaluation.agent_runtime.runner import AgentTaskInput, RunConfiguration, run_agent_task
from phase3.evaluation.agent_runtime.trace import evaluate_and_trace, evaluate_and_trace_with_identity
from phase3.evaluation.foundations.adapter import FOUNDATION_AVAILABLE
from phase3.evaluation.llm.provider import (
    LlamaServerEndpoint,
    LlamaServerProvider,
    clean_baseline_generation_config,
)

LOCOMO_MEMORY_RECORDS = _REPO_ROOT / "data" / "processed" / "locomo" / "memory_records.jsonl"
LOCOMO_TASK_RECORDS = _REPO_ROOT / "data" / "processed" / "locomo" / "task_records.jsonl"

PILOT_CONVERSATION_ID = "conv-26"
PILOT_SESSION_ID = "session_1"
PILOT_TASK_ID = "ecf5a096af5598393ce49c80"

OUTPUT_DIR = _REPO_ROOT / "phase3" / "experiments" / "pilots"
DATASET_REVISION = "phase3.2-frozen"


def _gpu_vram_mib():
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"], text=True
        )
        return int(out.strip().splitlines()[0])
    except Exception as exc:  # pragma: no cover -- environment-dependent
        return f"UNAVAILABLE: {exc}"


def _sys_ram_mib():
    try:
        import psutil

        return psutil.virtual_memory().used / (1024 * 1024)
    except Exception as exc:  # pragma: no cover
        return f"UNAVAILABLE: {exc}"


def _load_pilot_records():
    memory_rows = []
    with LOCOMO_MEMORY_RECORDS.open("r", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            if row["conversation_id"] == PILOT_CONVERSATION_ID and row["session_id"] == PILOT_SESSION_ID:
                memory_rows.append(row)
    task_row = None
    with LOCOMO_TASK_RECORDS.open("r", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            if row["task_id"] == PILOT_TASK_ID:
                task_row = row
                break
    if task_row is None:
        raise RuntimeError(f"Pilot task_id {PILOT_TASK_ID!r} not found in {LOCOMO_TASK_RECORDS}")
    if not memory_rows:
        raise RuntimeError(f"No memory records for {PILOT_CONVERSATION_ID}/{PILOT_SESSION_ID}")
    return memory_rows, task_row


def run_pilot() -> dict:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    memory_rows, task_row = _load_pilot_records()
    expected_answer = str(task_row["answer"]) if task_row["answer"] is not None else None
    gold_evidence_ids = task_row["evidence_memory_ids"]

    endpoint = LlamaServerEndpoint(base_url="http://127.0.0.1:8811")
    llm_provider = LlamaServerProvider(endpoint)

    print("Verifying llama-server reachability and identity...")
    if not llm_provider.health_check(timeout_sec=5.0):
        raise RuntimeError("llama-server not reachable at http://127.0.0.1:8811 -- start it first.")
    identity_check = llm_provider.verify_server_identity()
    print(f"  Server identity verified: {identity_check['system_fingerprint']}")

    generation_config = clean_baseline_generation_config(n_ctx=4096, max_tokens=64)
    ram_idle = _sys_ram_mib()
    vram_idle = _gpu_vram_mib()
    print(f"Idle: VRAM={vram_idle} MiB, RAM={ram_idle} MiB")

    # -------------------------------------------------------------------
    # CONDITION A -- no-memory control (same task, same config, same evaluator)
    # -------------------------------------------------------------------
    print("\n=== CONDITION A: NO_MEMORY ===")
    t_a0 = time.time()
    outcome_a = run_agent_task(
        AgentTaskInput(task_id=task_row["task_id"], prompt=task_row["question"], condition=CONDITION_NO_MEMORY),
        foundation=None,
        config=RunConfiguration(llm_provider=llm_provider, generation_config=generation_config),
    )
    latency_a = time.time() - t_a0
    trace_a = evaluate_and_trace(
        outcome_a, experiment_id="3.3-c-pilot-resolved-A", dataset="locomo",
        dataset_revision=DATASET_REVISION, record_id=task_row["task_id"],
        expected_answer=expected_answer, gold_evidence_ids=gold_evidence_ids,
    )
    print(f"  answer={outcome_a.execution_result.answer!r} failure_stage={trace_a['failure_stage']} latency={latency_a:.2f}s")

    # -------------------------------------------------------------------
    # RESET / INGEST -- real Mem0, WITH source_memory_id metadata (unchanged from 3.3-B's
    # ingestion call shape -- 3.3-B already stored this; 3.3-C is the first stage to
    # actually USE it for evaluation).
    # -------------------------------------------------------------------
    print("\n=== RESET / INGEST: real Mem0 ===")
    from phase3.evaluation.foundations_real.mem0_real_adapter import RealMem0Adapter

    foundation = RealMem0Adapter()
    init_field = foundation.initialize(
        {"embedding_model": "sentence-transformers/all-MiniLM-L6-v2", "collection_name": "pilot_3_3c_locomo_resolved"}
    )
    if init_field.availability != FOUNDATION_AVAILABLE:
        raise RuntimeError(
            f"RealMem0Adapter.initialize() reported {init_field.availability} -- rerun under "
            "C:\\h4venv\\Scripts\\python.exe."
        )
    reset_field = foundation.reset()
    if reset_field.availability != FOUNDATION_AVAILABLE:
        raise RuntimeError("RealMem0Adapter.reset() did not report AVAILABLE -- aborting rather than proceeding on unverified isolation.")
    print("  RESET confirmed.")

    vram_before_ingest = _gpu_vram_mib()
    t_ingest0 = time.time()
    added_ids = []
    for row in memory_rows:
        add_field = foundation.add_memory(
            memory_id=row["memory_id"],
            content={"text": f"{row['source_role']}: {row['content']}"},
            metadata={
                "user_id": "pilot-3-3c-conv-26",
                "source_memory_id": row["memory_id"],
                "session_id": row["session_id"],
                "conversation_id": row["conversation_id"],
            },
        )
        if add_field.availability == FOUNDATION_AVAILABLE:
            added_ids.append(add_field.value["memory_id"])
    ingest_latency = time.time() - t_ingest0
    vram_after_ingest = _gpu_vram_mib()
    print(f"  Ingested {len(added_ids)}/{len(memory_rows)} real turns in {ingest_latency:.2f}s. "
          f"VRAM before={vram_before_ingest} after={vram_after_ingest}")

    # -------------------------------------------------------------------
    # CONDITION B -- run TWICE for a basic determinism check (Part 16), same RESET/INGEST.
    # -------------------------------------------------------------------
    condition_b_runs = []
    for run_index in (1, 2):
        print(f"\n=== CONDITION B: RETRIEVED_MEMORY (real Mem0), run {run_index} ===")
        task_b = AgentTaskInput(
            task_id=task_row["task_id"], prompt=task_row["question"], condition=CONDITION_RETRIEVED_MEMORY,
            retrieval_query={"text": task_row["question"], "user_id": "pilot-3-3c-conv-26"}, top_k=5,
        )
        vram_before_run = _gpu_vram_mib()
        t_b0 = time.time()
        outcome_b = run_agent_task(
            task_b, foundation=foundation,
            config=RunConfiguration(llm_provider=llm_provider, generation_config=generation_config),
        )
        latency_b = time.time() - t_b0
        vram_after_run = _gpu_vram_mib()

        trace_b = evaluate_and_trace_with_identity(
            outcome_b, foundation,
            experiment_id=f"3.3-c-pilot-resolved-B-run{run_index}", dataset="locomo",
            dataset_revision=DATASET_REVISION, record_id=task_row["task_id"],
            expected_answer=expected_answer, gold_evidence_ids=gold_evidence_ids,
            ingested_source_memory_ids=[row["memory_id"] for row in memory_rows],
        )
        print(f"  retrieved(foundation)={trace_b['retrieved_memories']}")
        print(f"  retrieved(source, resolved)={trace_b['identity']['retrieved_memories_source_space']}")
        print(f"  answer={outcome_b.execution_result.answer!r}")
        print(f"  base failure_stage={trace_b['failure_stage']}  resolved failure_stage={trace_b['resolved_evaluation']['failure_stage']}")
        print(f"  resolved strict_tsr={trace_b['resolved_evaluation']['strict_tsr']}")
        print(f"  collision_free={trace_b['identity']['collision_report']['collision_free']}")
        print(f"  citation_diagnostic={trace_b['citation_diagnostic']['status']}")
        print(f"  latency={latency_b:.2f}s  VRAM before={vram_before_run} after={vram_after_run}")

        condition_b_runs.append(
            {
                "run_index": run_index,
                "trace": trace_b,
                "latency_sec": latency_b,
                "vram_before_mib": vram_before_run,
                "vram_after_mib": vram_after_run,
            }
        )

    shutdown_field = foundation.shutdown()

    determinism_note = (
        "identical answer text and resolved_evaluation.failure_stage across both runs"
        if condition_b_runs[0]["trace"]["agent_output"] == condition_b_runs[1]["trace"]["agent_output"]
        and condition_b_runs[0]["trace"]["resolved_evaluation"]["failure_stage"]
        == condition_b_runs[1]["trace"]["resolved_evaluation"]["failure_stage"]
        else "DIVERGED between run 1 and run 2 -- see individual traces"
    )

    result = {
        "pilot": "3.3-C mem0+locomo (identity-resolved rerun)",
        "task": {"task_id": task_row["task_id"], "question": task_row["question"], "gold_answer": task_row["answer"]},
        "server_identity": identity_check,
        "resource_measurements": {
            "idle_vram_mib": vram_idle,
            "idle_ram_mib": ram_idle,
            "vram_before_ingest_mib": vram_before_ingest,
            "vram_after_ingest_mib": vram_after_ingest,
            "ingest_latency_sec": ingest_latency,
        },
        "ingested_count": len(added_ids),
        "condition_a_no_memory": {"trace": trace_a, "latency_sec": latency_a, "vram_mib": vram_idle},
        "condition_b_retrieved_memory_runs": condition_b_runs,
        "determinism_check": determinism_note,
        "foundation_shutdown_availability": shutdown_field.availability,
    }

    output_path = OUTPUT_DIR / "pilot_3_3c_mem0_locomo_resolved_result.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nPilot result written to {output_path}")
    return result


if __name__ == "__main__":
    run_pilot()
