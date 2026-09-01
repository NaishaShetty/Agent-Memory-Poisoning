"""Phase 3.3-B REAL PILOT: Qwen3-8B + Mem0 + a real LoCoMo record.

Not a pytest test -- a standalone script producing a PILOT_RESULT (per the mission's
explicit UNIT_TEST / INTEGRATION_TEST / REAL_RUNTIME_TEST / PILOT_RESULT distinction).
Exercises the complete path Part 3.3-B is required to establish before any real
benchmark campaign begins:

    Real LoCoMo dataset record (data/processed/locomo/, conv-26/session_1)
        -> Agent (phase3.evaluation.agent_runtime.runner)
        -> Qwen3-8B (real llama-server.exe, verified identity)
        -> Mem0 (RealMem0Adapter -- real local Qdrant + real local HuggingFace embedder)
        -> Answer
        -> Existing Phase 3.2 evaluator (agent.outcomes / agent.diagnostics, unmodified)
        -> Metrics (answer correctness, failure stage)
        -> Trace (agent_runtime.trace, Part 18 of PHASE3_3_EXPERIMENTAL_SPEC.md)

WHY THIS MUST RUN UNDER C:\\h4venv, NOT THE REPO'S OWN INTERPRETER
--------------------------------------------------------------------------------
`mem0ai` is only importable inside the isolated `C:\\h4venv` created in Phase 3.2-H.4
(`phase3/evaluation/foundations_real/environment.py` documents this and it was
independently reconfirmed in Phase 3.3-B: `ModuleNotFoundError` in the repo's own
interpreter, both before and after this stage). Running this script under the repo's
own `python -m pytest` interpreter would make `RealMem0Adapter.initialize()` report
`FOUNDATION_UNAVAILABLE` (`ENVIRONMENT_LIMITATION`, honestly) rather than genuinely
exercising Mem0 -- that is a legitimate, non-fabricated outcome (the adapter is
explicitly built to report this rather than pretend), but it is NOT what this pilot is
for. To get a REAL pilot result, run:

    C:\\h4venv\\Scripts\\python.exe phase3\\evaluation\\agent_runtime\\pilot_mem0_locomo.py

with a real `llama-server.exe` already running and reachable at
`http://127.0.0.1:8811` (see PHASE3_3_B0_LLM_FEASIBILITY.md for how to start one). This
script adds the repo root to `sys.path` itself (below) so `phase3.*` imports resolve
even though `C:\\h4venv` has no knowledge of this repository as an installed package.

DATASET RECORD USED (real, not fabricated)
--------------------------------------------------------------------------------
`data/processed/locomo/task_records.jsonl`, task_id `ecf5a096af5598393ce49c80`:
"When did Caroline go to the LGBTQ support group?", answer "7 May 2023", gold evidence
memory_id `0a2bbeb23bfc6abe6a886f09` -- a real LoCoMo turn from `conv-26`/`session_1`.
The full 18-turn `session_1` of `conv-26` (all real `memory_records.jsonl` rows for that
session, no synthetic content) is ingested into Mem0 as the memory substrate, per the
mission's "small, deterministic subset of real approved dataset records" requirement.

RESET / INGEST / RUN / EVALUATE (Part 20 of PHASE3_3_EXPERIMENTAL_SPEC.md)
--------------------------------------------------------------------------------
Each invocation of this script calls `RealMem0Adapter.reset()` before ingesting -- a
REAL Qdrant collection drop/recreate (`Memory.reset()`), not a simulated reset -- so two
runs of this script do not silently share contaminated state. If `reset()` reports
anything other than genuine success, this script aborts rather than proceeding and
silently treating the run as isolated when it was not (per the mission's "do not call
the runs independent" instruction).
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
from phase3.evaluation.agent_runtime.trace import evaluate_and_trace, paired_memory_contribution
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

DATASET_REVISION = "phase3.2-frozen"  # data/processed/locomo/ is Phase 2/3.2-frozen, per
# PHASE3_RESTART_BOUNDARY.md -- this pilot reads it read-only and records this literal
# label rather than a git commit hash, since the file itself carries no revision field.


def _gpu_vram_mib():
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            text=True,
        )
        return int(out.strip().splitlines()[0])
    except Exception as exc:  # pragma: no cover -- environment-dependent
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
        raise RuntimeError(
            f"No memory records found for {PILOT_CONVERSATION_ID}/{PILOT_SESSION_ID} in {LOCOMO_MEMORY_RECORDS}"
        )
    return memory_rows, task_row


def run_pilot() -> dict:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    memory_rows, task_row = _load_pilot_records()

    endpoint = LlamaServerEndpoint(base_url="http://127.0.0.1:8811")
    llm_provider = LlamaServerProvider(endpoint)

    print("Verifying llama-server reachability and identity...")
    if not llm_provider.health_check(timeout_sec=5.0):
        raise RuntimeError(
            "llama-server is not reachable at http://127.0.0.1:8811 -- start it before "
            "running this pilot. See PHASE3_3_B0_LLM_FEASIBILITY.md for the command."
        )
    identity_check = llm_provider.verify_server_identity()
    print(f"  Server identity verified: {identity_check['system_fingerprint']}")

    generation_config = clean_baseline_generation_config(n_ctx=4096, max_tokens=64)
    vram_before_any = _gpu_vram_mib()
    print(f"VRAM before pilot (Qwen only, idle): {vram_before_any} MiB")

    # -------------------------------------------------------------------
    # CONDITION A -- no-memory control
    # -------------------------------------------------------------------
    print("\n=== CONDITION A: NO_MEMORY ===")
    task_a = AgentTaskInput(
        task_id=task_row["task_id"], prompt=task_row["question"], condition=CONDITION_NO_MEMORY
    )
    outcome_a = run_agent_task(
        task_a,
        foundation=None,
        config=RunConfiguration(llm_provider=llm_provider, generation_config=generation_config),
    )
    trace_a = evaluate_and_trace(
        outcome_a,
        experiment_id="3.3-b-pilot-mem0-locomo-A",
        dataset="locomo",
        dataset_revision=DATASET_REVISION,
        record_id=task_row["task_id"],
        expected_answer=str(task_row["answer"]) if task_row["answer"] is not None else None,
        gold_evidence_ids=task_row["evidence_memory_ids"],
    )
    print(f"  answer={outcome_a.execution_result.answer!r}")
    print(f"  failure_stage={trace_a['failure_stage']}")

    # -------------------------------------------------------------------
    # RESET / INGEST -- real Mem0
    # -------------------------------------------------------------------
    print("\n=== RESET / INGEST: real Mem0 (RealMem0Adapter) ===")
    from phase3.evaluation.foundations_real.mem0_real_adapter import RealMem0Adapter

    foundation = RealMem0Adapter()
    init_field = foundation.initialize(
        {"embedding_model": "sentence-transformers/all-MiniLM-L6-v2", "collection_name": "pilot_3_3b_locomo"}
    )
    if init_field.availability != FOUNDATION_AVAILABLE:
        raise RuntimeError(
            f"RealMem0Adapter.initialize() reported {init_field.availability}, not "
            f"AVAILABLE (note: {init_field.note!r}). This means mem0ai is not importable "
            "in the interpreter running this script -- rerun under C:\\h4venv\\Scripts\\"
            "python.exe, per this module's docstring."
        )
    print("  Mem0 initialized: local on-disk Qdrant + local HuggingFace embedder "
          "(sentence-transformers/all-MiniLM-L6-v2, 384-dim, CPU device -- h4venv's torch "
          "is a CPU build, torch.cuda.is_available()==False, so this embedder runs "
          "entirely on CPU: genuinely ZERO GPU/VRAM contention with the Qwen server).")

    reset_field = foundation.reset()
    if reset_field.availability != FOUNDATION_AVAILABLE:
        raise RuntimeError(
            f"RealMem0Adapter.reset() reported {reset_field.availability}, not AVAILABLE "
            "-- aborting rather than proceeding on unverified isolation, per Part 20 of "
            "PHASE3_3_EXPERIMENTAL_SPEC.md."
        )
    print("  RESET confirmed (real Qdrant collection drop/recreate).")

    vram_before_ingest = _gpu_vram_mib()
    t_ingest0 = time.time()
    added_ids = []
    for row in memory_rows:
        add_field = foundation.add_memory(
            memory_id=row["memory_id"],  # ignored by real Mem0's add() -- see adapter docstring
            content={"text": f"{row['source_role']}: {row['content']}"},
            metadata={"user_id": "pilot-3-3b-conv-26", "source_memory_id": row["memory_id"]},
        )
        if add_field.availability == FOUNDATION_AVAILABLE:
            added_ids.append(add_field.value["memory_id"])
    ingest_latency = time.time() - t_ingest0
    vram_after_ingest = _gpu_vram_mib()
    print(
        f"  Ingested {len(added_ids)}/{len(memory_rows)} real LoCoMo turns "
        f"(conv-26/session_1) in {ingest_latency:.2f}s. "
        f"VRAM before={vram_before_ingest} MiB, after={vram_after_ingest} MiB "
        f"(delta={vram_after_ingest - vram_before_ingest if isinstance(vram_after_ingest, int) and isinstance(vram_before_ingest, int) else 'n/a'} MiB)."
    )

    # -------------------------------------------------------------------
    # CONDITION B -- RETRIEVED_MEMORY via real Mem0
    # -------------------------------------------------------------------
    print("\n=== CONDITION B: RETRIEVED_MEMORY (real Mem0) ===")
    task_b = AgentTaskInput(
        task_id=task_row["task_id"],
        prompt=task_row["question"],
        condition=CONDITION_RETRIEVED_MEMORY,
        retrieval_query={"text": task_row["question"], "user_id": "pilot-3-3b-conv-26"},
        top_k=5,
    )
    vram_before_run_b = _gpu_vram_mib()
    outcome_b = run_agent_task(
        task_b,
        foundation=foundation,
        config=RunConfiguration(llm_provider=llm_provider, generation_config=generation_config),
    )
    vram_after_run_b = _gpu_vram_mib()
    trace_b = evaluate_and_trace(
        outcome_b,
        experiment_id="3.3-b-pilot-mem0-locomo-B",
        dataset="locomo",
        dataset_revision=DATASET_REVISION,
        record_id=task_row["task_id"],
        expected_answer=str(task_row["answer"]) if task_row["answer"] is not None else None,
        gold_evidence_ids=task_row["evidence_memory_ids"],
        store_memory_ids=added_ids,
    )
    print(f"  retrieved={outcome_b.retrieved_memory_ids}")
    print(f"  selected={outcome_b.selected_memory_ids}")
    print(f"  answer={outcome_b.execution_result.answer!r}")
    print(f"  failure_stage={trace_b['failure_stage']}")
    print(
        f"  VRAM before condition B run={vram_before_run_b} MiB, after={vram_after_run_b} MiB "
        "(combined Qwen+Mem0-retrieval peak)."
    )

    contribution = paired_memory_contribution(
        trace_a, trace_b, expected_answer=str(task_row["answer"]) if task_row["answer"] is not None else None
    )
    print(f"\n  Paired memory contribution: {contribution['status']}")

    shutdown_field = foundation.shutdown()

    result = {
        "pilot": "3.3-B mem0+locomo",
        "task": {"task_id": task_row["task_id"], "question": task_row["question"], "gold_answer": task_row["answer"]},
        "server_identity": identity_check,
        "vram_mib": {
            "idle_before_pilot": vram_before_any,
            "before_ingest": vram_before_ingest,
            "after_ingest": vram_after_ingest,
            "before_condition_b_run": vram_before_run_b,
            "after_condition_b_run": vram_after_run_b,
        },
        "ingest_latency_sec": ingest_latency,
        "ingested_count": len(added_ids),
        "condition_a_no_memory": trace_a,
        "condition_b_retrieved_memory": trace_b,
        "paired_memory_contribution": contribution,
        "foundation_shutdown_availability": shutdown_field.availability,
    }

    output_path = OUTPUT_DIR / "pilot_3_3b_mem0_locomo_result.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nPilot result written to {output_path}")
    return result


if __name__ == "__main__":
    run_pilot()
