"""V2 full production campaign driver: 120 real LoCoMo tasks x {Mem0, A-MEM} x
{A, B, C}, run through the actual production pipeline (`campaign_v2_runner.py`).
Every stage is checkpointed to disk so an interruption never costs more than the
in-flight pool's worth of work (the same lesson learned earlier this session when an
uncheckpointed research script lost 73 completed tasks to a killed process).

Produces `V2_STORE / "clean_agent_dataset_v2_locomo_120x2.json"` -- a SEPARATE artifact
from V1's frozen `canonical_store/dataset_full/clean_agent_dataset_locomo_120x2.json`,
which this script never opens for writing.
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
from phase3.evaluation.agent_runtime.campaign_v2_runner import (
    V2_STORE, run_condition_a, run_condition_b_v2_timestamped, run_condition_c_v2_amem, run_condition_c_v2_mem0,
)
from phase3.evaluation.agent_runtime.dataset_record_assembler import assemble_dataset_records
from phase3.evaluation.llm.provider import LlamaServerEndpoint, LlamaServerProvider, clean_baseline_generation_config

CAMPAIGN_ID = "3.3-V2-FULL-2026-09-08"
CHECKPOINT_DIR = V2_STORE / "checkpoints"
CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)


def _save_json(path: Path, data) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)


def _load_json_if_exists(path: Path):
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    return None


def main():
    def log(msg):
        print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

    t_campaign_start = time.time()

    log("=== Sampling: 120 real LoCoMo tasks (formal sample, seed 33005) ===")
    sample = build_formal_sample(n_per_dataset=120)
    loco_tasks = sample["locomo"]
    log(f"Sampled {len(loco_tasks)} real LoCoMo tasks.")

    endpoint = LlamaServerEndpoint()
    llm_provider = LlamaServerProvider(endpoint)
    identity = llm_provider.verify_server_identity()
    log(f"Server identity verified: {identity}")
    gen_config = clean_baseline_generation_config(n_ctx=4096, max_tokens=64)

    # --- Condition A ---
    a_path = CHECKPOINT_DIR / "results_a.json"
    results_a = _load_json_if_exists(a_path)
    if results_a is None:
        log("=== Condition A (no-memory): starting ===")
        t0 = time.time()
        results_a = run_condition_a(loco_tasks, llm_provider, gen_config, CAMPAIGN_ID)
        _save_json(a_path, results_a)
        log(f"Condition A done: {sum(1 for r in results_a if r['status']=='SUCCESSFUL_EVALUATION')}/{len(loco_tasks)} succeeded, {time.time()-t0:.1f}s")
    else:
        log(f"Condition A: resumed from checkpoint ({len(results_a)} results).")

    # --- Condition B ---
    b_path = CHECKPOINT_DIR / "results_b.json"
    results_b = _load_json_if_exists(b_path)
    if results_b is None:
        log("=== Condition B (gold evidence, timestamped): starting ===")
        t0 = time.time()
        results_b = run_condition_b_v2_timestamped(loco_tasks, llm_provider, gen_config, CAMPAIGN_ID)
        _save_json(b_path, results_b)
        log(f"Condition B done: {sum(1 for r in results_b if r['status']=='SUCCESSFUL_EVALUATION')}/{len(loco_tasks)} succeeded, {time.time()-t0:.1f}s")
    else:
        log(f"Condition B: resumed from checkpoint ({len(results_b)} results).")

    # --- Condition C, Mem0 (internally checkpointed per-pool) ---
    c_mem0_path = CHECKPOINT_DIR / "results_c_mem0.json"
    log("=== Condition C, Mem0 (hybrid selection, no timestamp): starting/resuming ===")
    t0 = time.time()
    results_c_mem0 = run_condition_c_v2_mem0(loco_tasks, llm_provider, gen_config, CAMPAIGN_ID, checkpoint_path=str(c_mem0_path))
    log(f"Condition C (Mem0) done: {sum(1 for r in results_c_mem0 if r['status']=='SUCCESSFUL_EVALUATION')}/{len(loco_tasks)} succeeded, {time.time()-t0:.1f}s")

    # --- Condition C, A-MEM (internally checkpointed per-pool -- the long stage) ---
    c_amem_path = CHECKPOINT_DIR / "results_c_amem.json"
    log("=== Condition C, A-MEM (hybrid selection, no timestamp): starting/resuming (this is the long stage) ===")
    t0 = time.time()
    results_c_amem = run_condition_c_v2_amem(loco_tasks, llm_provider, gen_config, CAMPAIGN_ID, checkpoint_path=str(c_amem_path))
    log(f"Condition C (A-MEM) done: {sum(1 for r in results_c_amem if r['status']=='SUCCESSFUL_EVALUATION')}/{len(loco_tasks)} succeeded, {time.time()-t0:.1f}s")

    # --- Assemble final V2 dataset ---
    log("=== Assembling final V2 dataset records ===")
    records = assemble_dataset_records(
        campaign_id=CAMPAIGN_ID, dataset="locomo", environment_record_id=None,
        results_a=results_a, results_gold_evidence=results_b,
        results_b_mem0=results_c_mem0, results_c_amem=results_c_amem,
    )
    out_dir = V2_STORE / "dataset_full"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "clean_agent_dataset_v2_locomo_120x2.json"
    _save_json(out_path, records)
    log(f"Wrote {len(records)} V2 dataset records to {out_path}")

    total_elapsed = time.time() - t_campaign_start
    log(f"=== FULL V2 CAMPAIGN COMPLETE. Total elapsed: {total_elapsed/60:.1f} min ({total_elapsed/3600:.2f} hr) ===")


if __name__ == "__main__":
    main()
