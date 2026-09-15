"""Mixed-N V3-hybrid full-scale campaign (2026-09-15) -- Conditions A, B,
C-Mem0 at n=500; Condition C-A-MEM at n=120 (a strict SUBSET of the same
500-task sample, not a separately-drawn 120, so every C-A-MEM task_id is
also present in the other three conditions and cross-condition comparison
stays valid for those 120).

Why the split: Condition C-A-MEM costs ~14 min/task (documented,
PHASE4_PRE_FLIGHT_DECISIONS.md's own A-MEM ingestion estimate) -- 500 tasks
would be ~117 hours (~4.9 days). The other three conditions are cheap
(Condition A: 500 tasks in 604s measured this session; Condition B: ~31 min
projected from the 120-task rate; C-Mem0 historically the faster memory-
foundation condition) and scaling them to 500 costs nothing meaningful. This
was the user's own explicit choice after being shown the real per-condition
cost breakdown -- not a default silently applied.

`assemble_dataset_records()`'s own documented behavior (verified by reading
it before writing this script, not assumed) handles a task missing from one
condition correctly: that condition's block reports NOT_RUN / the real
status, never silently dropped from the record -- so the 380 tasks (500-120)
that never ran under C-A-MEM will correctly show that condition as not
evaluated, not as a fabricated result.

Checkpointed per condition (same discipline as the original 120-task
script), safe to interrupt and resume -- and C-Mem0/C-A-MEM ALSO checkpoint
per LoCoMo conversation-pool internally (verified by reading
campaign_v3_runner.py's `_run_condition_c_v3` before relying on this), so a
crash mid-condition loses at most one in-flight pool, not the whole
condition.
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
    V3_HYBRID_STORE, assemble_dataset_records, run_condition_a, run_condition_b_hybrid,
    run_condition_c_v3_amem, run_condition_c_v3_mem0,
)
from phase3.evaluation.llm.provider import LlamaServerEndpoint, LlamaServerProvider, clean_baseline_generation_config

CAMPAIGN_ID = "3.3-V3-HYBRID-FULL-R6-MIXEDN"
N_FULL = 500  # Conditions A, B, C-Mem0
N_AMEM = 120  # Condition C-A-MEM -- a strict subset of the first N_AMEM of the N_FULL sample
CHECKPOINT_DIR = V3_HYBRID_STORE / "checkpoints_mixed_n"
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

    log(f"=== Sampling: {N_FULL} real LoCoMo tasks (formal sample, seed 33005) ===")
    sample = build_formal_sample(n_per_dataset=N_FULL)
    loco_tasks_full = sample["locomo"]
    loco_tasks_amem = loco_tasks_full[:N_AMEM]  # strict subset, by construction
    log(f"Sampled {len(loco_tasks_full)} tasks; C-A-MEM will use the first {len(loco_tasks_amem)} of them.")

    endpoint = LlamaServerEndpoint()
    llm_provider = LlamaServerProvider(endpoint)
    identity = llm_provider.verify_server_identity()
    log(f"Server identity verified: {identity}")

    v3_gen_config = clean_baseline_generation_config(n_ctx=4096, max_tokens=64)
    v5_gen_config = clean_baseline_generation_config(n_ctx=4096, max_tokens=256)

    a_path = CHECKPOINT_DIR / "results_a.json"
    results_a = _load_json_if_exists(a_path)
    if results_a is None:
        log(f"=== Condition A ({N_FULL} tasks): starting ===")
        t0 = time.time()
        results_a = run_condition_a(loco_tasks_full, llm_provider, v3_gen_config, CAMPAIGN_ID)
        _save_json(a_path, results_a)
        log(f"Condition A done: {sum(1 for r in results_a if r['status']=='SUCCESSFUL_EVALUATION')}/{len(loco_tasks_full)} succeeded, {time.time()-t0:.1f}s")
    else:
        log(f"Condition A: resumed from checkpoint ({len(results_a)} results).")

    # Checkpointing fix (2026-09-15, user request): `run_condition_b_hybrid()`
    # itself has no incremental checkpoint (it returns only after ALL tasks in
    # the list it's given finish) -- confirmed by reading
    # campaign_v3_hybrid_runner.py before relying on this, not assumed. Batched
    # here at the CALLING script level instead of modifying that shared,
    # frozen-adjacent function: process B_BATCH_SIZE tasks at a time, save a
    # checkpoint after every batch, and skip already-completed task_ids on
    # resume. A crash now loses at most one batch (a few minutes), not the
    # whole condition.
    B_BATCH_SIZE = 25
    b_path = CHECKPOINT_DIR / "results_b.json"
    results_b = _load_json_if_exists(b_path) or []
    done_ids_b = {r["task_id"] for r in results_b}
    remaining_b = [t for t in loco_tasks_full if t.task_id not in done_ids_b]
    if remaining_b:
        log(f"=== Condition B: {len(done_ids_b)}/{len(loco_tasks_full)} already done, "
            f"{len(remaining_b)} remaining, batch size {B_BATCH_SIZE} ===")
        t0 = time.time()
        for i in range(0, len(remaining_b), B_BATCH_SIZE):
            batch = remaining_b[i:i + B_BATCH_SIZE]
            batch_results = run_condition_b_hybrid(batch, llm_provider, v5_gen_config, CAMPAIGN_ID)
            results_b.extend(batch_results)
            _save_json(b_path, results_b)
            log(f"  Condition B checkpoint: {len(results_b)}/{len(loco_tasks_full)} done "
                f"({time.time()-t0:.1f}s elapsed this run)")
        log(f"Condition B done: {sum(1 for r in results_b if r['status']=='SUCCESSFUL_EVALUATION')}/{len(loco_tasks_full)} succeeded, {time.time()-t0:.1f}s")
    else:
        log(f"Condition B: resumed from checkpoint, already complete ({len(results_b)} results).")

    c_mem0_path = CHECKPOINT_DIR / "results_c_mem0.json"
    log(f"=== Condition C, Mem0 ({N_FULL} tasks): starting/resuming ===")
    t0 = time.time()
    results_c_mem0 = run_condition_c_v3_mem0(loco_tasks_full, llm_provider, v3_gen_config, CAMPAIGN_ID, checkpoint_path=str(c_mem0_path))
    log(f"Condition C (Mem0) done: {sum(1 for r in results_c_mem0 if r['status']=='SUCCESSFUL_EVALUATION')}/{len(loco_tasks_full)} succeeded, {time.time()-t0:.1f}s")

    c_amem_path = CHECKPOINT_DIR / "results_c_amem.json"
    log(f"=== Condition C, A-MEM ({N_AMEM} tasks -- bounded, subset of the {N_FULL}-task sample): starting/resuming ===")
    t0 = time.time()
    results_c_amem = run_condition_c_v3_amem(loco_tasks_amem, llm_provider, v3_gen_config, CAMPAIGN_ID, checkpoint_path=str(c_amem_path))
    log(f"Condition C (A-MEM) done: {sum(1 for r in results_c_amem if r['status']=='SUCCESSFUL_EVALUATION')}/{len(loco_tasks_amem)} succeeded, {time.time()-t0:.1f}s")

    log("=== Assembling final V3-hybrid dataset records (NOT_RUN expected for C-A-MEM on tasks beyond the first 120) ===")
    records = assemble_dataset_records(
        campaign_id=CAMPAIGN_ID, dataset="locomo", environment_record_id=None,
        results_a=results_a, results_gold_evidence=results_b,
        results_b_mem0=results_c_mem0, results_c_amem=results_c_amem,
    )
    out_dir = V3_HYBRID_STORE / "dataset_full"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"clean_agent_dataset_v3_hybrid_locomo_mixed_n_{N_FULL}_{N_AMEM}.json"
    _save_json(out_path, records)
    log(f"Wrote {len(records)} V3-hybrid dataset records to {out_path}")

    total_elapsed = time.time() - t_campaign_start
    log(f"=== MIXED-N CAMPAIGN COMPLETE (A/B/C-Mem0 @ {N_FULL}, C-A-MEM @ {N_AMEM}). Total elapsed: {total_elapsed/60:.1f} min ({total_elapsed/3600:.2f} hr) ===")


if __name__ == "__main__":
    main()
