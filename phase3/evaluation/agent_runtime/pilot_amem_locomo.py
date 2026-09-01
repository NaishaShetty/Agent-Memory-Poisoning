"""Phase 3.3-D REAL PILOT: Qwen3-8B + real A-MEM (A-mem-sys) + the SAME real LoCoMo
record used in 3.3-B/3.3-C's Mem0 pilots (conv-26/session_1, task
ecf5a096af5598393ce49c80) -- for cross-foundation comparability, per the mission's
explicit "prefer the same small LoCoMo records" instruction.

Unlike Graphiti (whose `retrieve()` is direct-uuid-lookup only -- real semantic search is
MODEL_DEPENDENT, no local embedder in graphiti-core), A-mem-sys's `retrieve()` performs
REAL ChromaDB cosine-similarity search over REAL local sentence-transformers embeddings
(verified in this stage's identity investigation) -- so a genuine, real, LLM-in-the-loop
agent pilot is meaningful for A-MEM in a way it is not (yet) for Graphiti. This script
uses the DIRECT_ASSIGNMENT identity strategy (`identity.resolve_via_direct_assignment`)
throughout, since A-mem-sys honors a caller-supplied id directly -- no metadata lookup is
needed, and none is attempted.

Must run under `C:\\h4venv\\Scripts\\python.exe` (A-mem-sys is only importable there, per
`foundations_real/environment.py::AMEM_SYS_SOURCE`) with a real `llama-server.exe`
reachable at `http://127.0.0.1:8811`.
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
from phase3.evaluation.agent_runtime.citation import classify_citation_based_usage
from phase3.evaluation.agent_runtime.identity import resolve_via_direct_assignment, verify_collision_safety
from phase3.evaluation.agent_runtime.runner import AgentTaskInput, RunConfiguration, run_agent_task
from phase3.evaluation.agent_runtime.trace import evaluate_and_trace
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
    return memory_rows, task_row


def run_pilot() -> dict:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    memory_rows, task_row = _load_pilot_records()
    expected_answer = str(task_row["answer"]) if task_row["answer"] is not None else None
    gold_evidence_ids = task_row["evidence_memory_ids"]

    llm_provider = LlamaServerProvider(LlamaServerEndpoint(base_url="http://127.0.0.1:8811"))
    print("Verifying llama-server reachability and identity...")
    if not llm_provider.health_check(timeout_sec=5.0):
        raise RuntimeError("llama-server not reachable at http://127.0.0.1:8811 -- start it first.")
    identity_check = llm_provider.verify_server_identity()
    print(f"  Server identity verified: {identity_check['system_fingerprint']}")

    generation_config = clean_baseline_generation_config(n_ctx=4096, max_tokens=64)
    vram_idle = _gpu_vram_mib()

    print("\n=== CONDITION A: NO_MEMORY ===")
    outcome_a = run_agent_task(
        AgentTaskInput(task_id=task_row["task_id"], prompt=task_row["question"], condition=CONDITION_NO_MEMORY),
        foundation=None,
        config=RunConfiguration(llm_provider=llm_provider, generation_config=generation_config),
    )
    trace_a = evaluate_and_trace(
        outcome_a, experiment_id="3.3-d-pilot-amem-A", dataset="locomo",
        dataset_revision=DATASET_REVISION, record_id=task_row["task_id"],
        expected_answer=expected_answer, gold_evidence_ids=gold_evidence_ids,
    )
    print(f"  answer={outcome_a.execution_result.answer!r} failure_stage={trace_a['failure_stage']}")

    print("\n=== RESET / INGEST: real A-MEM (A-mem-sys) ===")
    from phase3.evaluation.foundations_real.amem_real_adapter import RealAMemAdapter

    foundation = RealAMemAdapter()
    init_field = foundation.initialize({"embedding_model": "all-MiniLM-L6-v2"})
    if init_field.availability != FOUNDATION_AVAILABLE:
        raise RuntimeError(
            f"RealAMemAdapter.initialize() reported {init_field.availability} -- rerun under "
            "C:\\h4venv\\Scripts\\python.exe."
        )
    reset_field = foundation.reset()
    if reset_field.availability != FOUNDATION_AVAILABLE:
        raise RuntimeError("RealAMemAdapter.reset() did not report AVAILABLE -- aborting.")
    print("  RESET confirmed.")

    vram_before_ingest = _gpu_vram_mib()
    t_ingest0 = time.time()
    resolutions = {}
    for row in memory_rows:
        source_id = row["memory_id"]
        add_field = foundation.add_memory(
            memory_id=source_id,  # A-mem-sys honors this directly -- DIRECT_ASSIGNMENT strategy
            content={"text": f"{row['source_role']}: {row['content']}"},
            metadata={"tags": ["locomo", row["session_id"]], "keywords": [row["source_role"]], "context": row["conversation_id"]},
        )
        if add_field.availability == FOUNDATION_AVAILABLE:
            resolution = resolve_via_direct_assignment(source_id, add_field.value)
            resolutions[resolution.foundation_memory_id] = resolution
    ingest_latency = time.time() - t_ingest0
    vram_after_ingest = _gpu_vram_mib()
    collision_report = verify_collision_safety(resolutions)
    print(f"  Ingested {len(resolutions)}/{len(memory_rows)} real turns in {ingest_latency:.2f}s "
          f"(DIRECT_ASSIGNMENT: FOUNDATION_MEMORY_ID == SOURCE_MEMORY_ID for all, resolved_count="
          f"{collision_report.resolved_count}, collision_free={collision_report.collision_free}). "
          f"VRAM before={vram_before_ingest} after={vram_after_ingest}")

    print("\n=== CONDITION B: RETRIEVED_MEMORY (real A-MEM, real ChromaDB text search) ===")
    task_b = AgentTaskInput(
        task_id=task_row["task_id"], prompt=task_row["question"], condition=CONDITION_RETRIEVED_MEMORY,
        retrieval_query={"text": task_row["question"]}, top_k=5,
    )
    vram_before_run = _gpu_vram_mib()
    t_b0 = time.time()
    outcome_b = run_agent_task(
        task_b, foundation=foundation,
        config=RunConfiguration(llm_provider=llm_provider, generation_config=generation_config),
    )
    latency_b = time.time() - t_b0
    vram_after_run = _gpu_vram_mib()

    # Since every ingested item's FOUNDATION_MEMORY_ID literally IS its SOURCE_MEMORY_ID
    # (DIRECT_ASSIGNMENT, verified above), the retrieved/selected ids ARE ALREADY in
    # source-id space -- no translation step is needed the way it was for Mem0's
    # METADATA_LOOKUP strategy. This is itself a real, useful architectural finding.
    trace_b = evaluate_and_trace(
        outcome_b, experiment_id="3.3-d-pilot-amem-B", dataset="locomo",
        dataset_revision=DATASET_REVISION, record_id=task_row["task_id"],
        expected_answer=expected_answer, gold_evidence_ids=gold_evidence_ids,
        store_memory_ids=[row["memory_id"] for row in memory_rows],
    )
    citation = classify_citation_based_usage(outcome_b.execution_result.answer, outcome_b.exposed_memory_ids)

    print(f"  retrieved (== source ids, DIRECT_ASSIGNMENT)={trace_b['retrieved_memories']}")
    print(f"  answer={outcome_b.execution_result.answer!r}")
    print(f"  failure_stage={trace_b['failure_stage']}")  # NOTE: no separate "resolved_evaluation"
    # needed here -- base trace IS already in source-id space for this foundation.
    print(f"  citation_diagnostic={citation.status}")
    print(f"  latency={latency_b:.2f}s VRAM before={vram_before_run} after={vram_after_run}")

    shutdown_field = foundation.shutdown()

    result = {
        "pilot": "3.3-D real A-MEM + locomo (DIRECT_ASSIGNMENT identity strategy)",
        "task": {"task_id": task_row["task_id"], "question": task_row["question"], "gold_answer": task_row["answer"]},
        "server_identity": identity_check,
        "vram_mib": {
            "idle": vram_idle, "before_ingest": vram_before_ingest, "after_ingest": vram_after_ingest,
            "before_condition_b_run": vram_before_run, "after_condition_b_run": vram_after_run,
        },
        "ingest_latency_sec": ingest_latency,
        "identity": {
            "strategy": "DIRECT_ASSIGNMENT",
            "resolved_count": collision_report.resolved_count,
            "collision_free": collision_report.collision_free,
            "duplicate_source_ids": dict(collision_report.duplicate_source_ids),
        },
        "condition_a_no_memory": trace_a,
        "condition_b_retrieved_memory": trace_b,
        "condition_b_latency_sec": latency_b,
        "citation_diagnostic": {"status": citation.status, "cited_memory_ids": list(citation.cited_memory_ids)},
        "foundation_shutdown_availability": shutdown_field.availability,
    }
    output_path = OUTPUT_DIR / "pilot_3_3d_amem_locomo_result.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nPilot result written to {output_path}")
    return result


if __name__ == "__main__":
    run_pilot()
