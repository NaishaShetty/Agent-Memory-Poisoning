"""V5 full production campaign driver (Stage 4, per PHASE3_V5_EXPERIMENT_PLAN.md,
run only after explicit user approval): 120 real LoCoMo tasks x {Mem0, A-MEM} x
{A, B, C}, run through `campaign_v5_runner.py` using the `V5_VERIFIED` config --
the one candidate the Stage 2 pilots (n=15, then a scaled n=50/n=20x2-foundation
rerun) found to hold a real, hand-verified, zero-hallucination-regression gain over
V5_BASE. `V5_FULL`/`V5_STRUCTURED` are NOT run here -- the structured-memory layer
showed a real, disclosed regression in piloting and is not promoted.

Checkpointed at every stage/pool, same discipline as `run_v3_full_campaign.py`.
Produces `V5_STORE / "clean_agent_dataset_v5_verified_locomo_120x2.json"` -- a
SEPARATE artifact from V1/V2/V3's frozen canonical stores, none of which this
script ever opens for writing.

MUST BE RUN UNDER THE ISOLATED C:\\h4venv INTERPRETER -- Mem0/A-MEM are only
importable there (confirmed directly this session; the main repo interpreter
reports both foundations UNAVAILABLE).
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
from phase3.evaluation.agent_runtime.campaign_v5_runner import (
    V5_STORE, V5_VERIFIED, run_condition_a, run_condition_b_v5, run_condition_c_v5_amem, run_condition_c_v5_mem0,
)
from phase3.evaluation.agent_runtime.dataset_record_assembler import assemble_dataset_records
from phase3.evaluation.llm.provider import LlamaServerEndpoint, LlamaServerProvider, clean_baseline_generation_config

CAMPAIGN_ID = "3.3-V5-VERIFIED-FULL-2026-09-09"
CHECKPOINT_DIR = V5_STORE / "checkpoints"
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

    log("=== Sampling: 120 real LoCoMo tasks (formal sample, seed 33005 -- SAME frozen sample V1-V4 use) ===")
    sample = build_formal_sample(n_per_dataset=120)
    loco_tasks = sample["locomo"]
    log(f"Sampled {len(loco_tasks)} real LoCoMo tasks.")

    endpoint = LlamaServerEndpoint()
    llm_provider = LlamaServerProvider(endpoint)
    identity = llm_provider.verify_server_identity()
    log(f"Server identity verified: {identity}")
    # max_tokens=256 (not V1-V4's 64) -- same generation config used throughout the
    # V5 Stage 2 pilots, chosen to reduce truncation-driven premature hedging (see
    # PHASE3_V5_DESIGN_RATIONALE.md); enable_thinking stays False, unchanged from V1-V4.
    gen_config = clean_baseline_generation_config(n_ctx=4096, max_tokens=256)

    a_path = CHECKPOINT_DIR / "results_a.json"
    results_a = _load_json_if_exists(a_path)
    if results_a is None:
        log("=== Condition A: starting ===")
        t0 = time.time()
        results_a = run_condition_a(loco_tasks, llm_provider, gen_config, CAMPAIGN_ID)
        _save_json(a_path, results_a)
        log(f"Condition A done: {sum(1 for r in results_a if r['status']=='SUCCESSFUL_EVALUATION')}/{len(loco_tasks)} succeeded, {time.time()-t0:.1f}s")
    else:
        log(f"Condition A: resumed from checkpoint ({len(results_a)} results).")

    b_path = CHECKPOINT_DIR / "results_b.json"
    results_b = _load_json_if_exists(b_path)
    if results_b is None:
        log("=== Condition B (V5_VERIFIED: V3 evidence construction + bounded verify/revise): starting ===")
        t0 = time.time()
        results_b = run_condition_b_v5(loco_tasks, llm_provider, gen_config, CAMPAIGN_ID, v5_config=V5_VERIFIED)
        _save_json(b_path, results_b)
        log(f"Condition B done: {sum(1 for r in results_b if r['status']=='SUCCESSFUL_EVALUATION')}/{len(loco_tasks)} succeeded, {time.time()-t0:.1f}s")
    else:
        log(f"Condition B: resumed from checkpoint ({len(results_b)} results).")

    c_mem0_path = CHECKPOINT_DIR / "results_c_mem0.json"
    log("=== Condition C, Mem0 (V5_VERIFIED): starting/resuming ===")
    t0 = time.time()
    results_c_mem0 = run_condition_c_v5_mem0(loco_tasks, llm_provider, gen_config, CAMPAIGN_ID, v5_config=V5_VERIFIED, checkpoint_path=str(c_mem0_path))
    log(f"Condition C (Mem0) done: {sum(1 for r in results_c_mem0 if r['status']=='SUCCESSFUL_EVALUATION')}/{len(loco_tasks)} succeeded, {time.time()-t0:.1f}s")

    c_amem_path = CHECKPOINT_DIR / "results_c_amem.json"
    log("=== Condition C, A-MEM (V5_VERIFIED): starting/resuming (long stage -- ~2+ hours expected) ===")
    t0 = time.time()
    results_c_amem = run_condition_c_v5_amem(loco_tasks, llm_provider, gen_config, CAMPAIGN_ID, v5_config=V5_VERIFIED, checkpoint_path=str(c_amem_path))
    log(f"Condition C (A-MEM) done: {sum(1 for r in results_c_amem if r['status']=='SUCCESSFUL_EVALUATION')}/{len(loco_tasks)} succeeded, {time.time()-t0:.1f}s")

    log("=== Assembling final V5 dataset records (reusing the shared, unmodified dataset_record_assembler.py) ===")
    records = assemble_dataset_records(
        campaign_id=CAMPAIGN_ID, dataset="locomo", environment_record_id=None,
        results_a=results_a, results_gold_evidence=results_b,
        results_b_mem0=results_c_mem0, results_c_amem=results_c_amem,
    )
    out_dir = V5_STORE / "dataset_full"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "clean_agent_dataset_v5_verified_locomo_120x2.json"
    _save_json(out_path, records)
    log(f"Wrote {len(records)} V5 dataset records to {out_path}")

    total_elapsed = time.time() - t_campaign_start
    log(f"=== FULL V5 (V5_VERIFIED) CAMPAIGN COMPLETE. Total elapsed: {total_elapsed/60:.1f} min ({total_elapsed/3600:.2f} hr) ===")


if __name__ == "__main__":
    main()
