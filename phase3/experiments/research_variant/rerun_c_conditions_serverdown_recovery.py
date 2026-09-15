"""Recovery rerun for Conditions C-Mem0 (500 tasks) and C-A-MEM (120 tasks)
after discovering their entire generation stage silently failed
(`LLMProviderConnectionError` on every task -- the llama-server went down
during Condition B and stayed down for the rest of the original campaign;
memory ingestion/retrieval succeeded throughout since those don't need the
server, masking the failure in the progress log).

Uses a FRESH campaign_id (not the original) -- the broken run already wrote
real canonical-ledger entries for every pool under the original campaign_id;
re-ingesting the same pools under that id would hit the documented
CanonicalCollisionError class. The broken checkpoints are preserved (moved
to broken_backup_2026-09-15/), never deleted.

Same task lists as the original mixed-N campaign: the full 500-task sample
for C-Mem0, the first 120 of that same sample (a true subset) for C-A-MEM.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from phase3.evaluation.agent_runtime.campaign_sampling import build_formal_sample
from phase3.evaluation.agent_runtime.campaign_v3_hybrid_runner import (
    V3_HYBRID_STORE, run_condition_c_v3_amem, run_condition_c_v3_mem0,
)
from phase3.evaluation.llm.provider import LlamaServerEndpoint, LlamaServerProvider, clean_baseline_generation_config

CAMPAIGN_ID = "3.3-V3-HYBRID-FULL-R6-MIXEDN-CRETRY"
N_FULL = 500
N_AMEM = 120
CHECKPOINT_DIR = V3_HYBRID_STORE / "checkpoints_mixed_n"


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def main():
    log(f"=== Sampling: {N_FULL} real LoCoMo tasks (formal sample, seed 33005) ===")
    sample = build_formal_sample(n_per_dataset=N_FULL)
    loco_tasks_full = sample["locomo"]
    loco_tasks_amem = loco_tasks_full[:N_AMEM]
    log(f"Sampled {len(loco_tasks_full)} tasks; C-A-MEM uses the first {len(loco_tasks_amem)}.")

    endpoint = LlamaServerEndpoint()
    llm_provider = LlamaServerProvider(endpoint)
    identity = llm_provider.verify_server_identity()
    log(f"Server identity verified: {identity}")
    v3_gen_config = clean_baseline_generation_config(n_ctx=4096, max_tokens=64)

    c_mem0_path = CHECKPOINT_DIR / "results_c_mem0.json"
    log("=== Condition C, Mem0 recovery rerun: starting/resuming ===")
    t0 = time.time()
    results_c_mem0 = run_condition_c_v3_mem0(loco_tasks_full, llm_provider, v3_gen_config, CAMPAIGN_ID, checkpoint_path=str(c_mem0_path))
    n_ok = sum(1 for r in results_c_mem0 if (r.get("trace") or {}).get("agent_output") is not None)
    log(f"Condition C (Mem0) recovery done: {n_ok}/{len(loco_tasks_full)} have a real generated answer, {time.time()-t0:.1f}s")

    c_amem_path = CHECKPOINT_DIR / "results_c_amem.json"
    log("=== Condition C, A-MEM recovery rerun: starting/resuming (long stage) ===")
    t0 = time.time()
    results_c_amem = run_condition_c_v3_amem(loco_tasks_amem, llm_provider, v3_gen_config, CAMPAIGN_ID, checkpoint_path=str(c_amem_path))
    n_ok = sum(1 for r in results_c_amem if (r.get("trace") or {}).get("agent_output") is not None)
    log(f"Condition C (A-MEM) recovery done: {n_ok}/{len(loco_tasks_amem)} have a real generated answer, {time.time()-t0:.1f}s")

    log("=== C-condition recovery rerun complete. Reassemble the dataset next. ===")


if __name__ == "__main__":
    main()
