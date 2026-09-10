"""V3-hybrid full campaign driver: 120 real LoCoMo tasks x {Mem0, A-MEM} x
{A, B, C}, run through `campaign_v3_hybrid_runner.py` -- V3's unchanged Condition A
and Condition C, plus V5's bounded verification pipeline (`V5_VERIFIED`) for
Condition B, per this session's own head-to-head evidence that this specific
combination beats plain V3 on B while losing nothing on A or C. Checkpointed at
every stage/pool, same discipline as `run_v3_full_campaign.py`/
`run_v5_full_campaign.py`.

Produces `V3_HYBRID_STORE / "clean_agent_dataset_v3_hybrid_locomo_120x2.json"` --
a SEPARATE artifact from every other candidate's frozen store; none of them are
ever opened for writing by this script.

Condition C (Mem0/A-MEM) requires the isolated `C:\\h4venv` interpreter, same as
every other Condition-C script in this project.
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

# NOTE: this campaign was interrupted mid-pool once (a killed-and-resumed run) and
# hit a real CanonicalCollisionError on resume -- the task-level checkpoint
# (results_c_mem0.json) correctly tracks per-task completion, but a pool killed
# mid-ingestion leaves PARTIAL canonical-ledger entries under the old campaign_id
# that collide when that same pool is re-ingested on resume. Fixed by bumping the
# campaign_id to a fresh canonical-ledger namespace for the resume -- task-level
# checkpoint progress (already-completed tasks) is preserved regardless, since it
# lives in results_c_mem0.json, not in the canonical ledger.
CAMPAIGN_ID = "3.3-V3-HYBRID-FULL-R5"
CHECKPOINT_DIR = V3_HYBRID_STORE / "checkpoints"
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

    log("=== Sampling: 120 real LoCoMo tasks (formal sample, seed 33005 -- SAME frozen sample V1-V5 use) ===")
    sample = build_formal_sample(n_per_dataset=120)
    loco_tasks = sample["locomo"]
    log(f"Sampled {len(loco_tasks)} real LoCoMo tasks.")

    endpoint = LlamaServerEndpoint()
    llm_provider = LlamaServerProvider(endpoint)
    identity = llm_provider.verify_server_identity()
    log(f"Server identity verified: {identity}")

    # Condition A/C: V3's own generation config (max_tokens=64), reused verbatim --
    # this campaign changes nothing about how V3's own conditions were run.
    v3_gen_config = clean_baseline_generation_config(n_ctx=4096, max_tokens=64)
    # Condition B: V5_VERIFIED's validated config (max_tokens=256 -- shown necessary
    # for the verify/revise stage to have room to actually restate an answer).
    v5_gen_config = clean_baseline_generation_config(n_ctx=4096, max_tokens=256)

    a_path = CHECKPOINT_DIR / "results_a.json"
    results_a = _load_json_if_exists(a_path)
    if results_a is None:
        log("=== Condition A (V3, unchanged): starting ===")
        t0 = time.time()
        results_a = run_condition_a(loco_tasks, llm_provider, v3_gen_config, CAMPAIGN_ID)
        _save_json(a_path, results_a)
        log(f"Condition A done: {sum(1 for r in results_a if r['status']=='SUCCESSFUL_EVALUATION')}/{len(loco_tasks)} succeeded, {time.time()-t0:.1f}s")
    else:
        log(f"Condition A: resumed from checkpoint ({len(results_a)} results).")

    b_path = CHECKPOINT_DIR / "results_b.json"
    results_b = _load_json_if_exists(b_path)
    if results_b is None:
        log("=== Condition B (V5_VERIFIED: V3 evidence + bounded verify/revise): starting ===")
        t0 = time.time()
        results_b = run_condition_b_hybrid(loco_tasks, llm_provider, v5_gen_config, CAMPAIGN_ID)
        _save_json(b_path, results_b)
        log(f"Condition B done: {sum(1 for r in results_b if r['status']=='SUCCESSFUL_EVALUATION')}/{len(loco_tasks)} succeeded, {time.time()-t0:.1f}s")
    else:
        log(f"Condition B: resumed from checkpoint ({len(results_b)} results).")

    c_mem0_path = CHECKPOINT_DIR / "results_c_mem0.json"
    log("=== Condition C, Mem0 (V3, unchanged): starting/resuming ===")
    t0 = time.time()
    results_c_mem0 = run_condition_c_v3_mem0(loco_tasks, llm_provider, v3_gen_config, CAMPAIGN_ID, checkpoint_path=str(c_mem0_path))
    log(f"Condition C (Mem0) done: {sum(1 for r in results_c_mem0 if r['status']=='SUCCESSFUL_EVALUATION')}/{len(loco_tasks)} succeeded, {time.time()-t0:.1f}s")

    c_amem_path = CHECKPOINT_DIR / "results_c_amem.json"
    log("=== Condition C, A-MEM (V3, unchanged): starting/resuming (long stage) ===")
    t0 = time.time()
    results_c_amem = run_condition_c_v3_amem(loco_tasks, llm_provider, v3_gen_config, CAMPAIGN_ID, checkpoint_path=str(c_amem_path))
    log(f"Condition C (A-MEM) done: {sum(1 for r in results_c_amem if r['status']=='SUCCESSFUL_EVALUATION')}/{len(loco_tasks)} succeeded, {time.time()-t0:.1f}s")

    log("=== Assembling final V3-hybrid dataset records (reusing the shared, unmodified dataset_record_assembler.py) ===")
    records = assemble_dataset_records(
        campaign_id=CAMPAIGN_ID, dataset="locomo", environment_record_id=None,
        results_a=results_a, results_gold_evidence=results_b,
        results_b_mem0=results_c_mem0, results_c_amem=results_c_amem,
    )
    out_dir = V3_HYBRID_STORE / "dataset_full"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "clean_agent_dataset_v3_hybrid_locomo_120x2.json"
    _save_json(out_path, records)
    log(f"Wrote {len(records)} V3-hybrid dataset records to {out_path}")

    total_elapsed = time.time() - t_campaign_start
    log(f"=== FULL V3-HYBRID CAMPAIGN COMPLETE. Total elapsed: {total_elapsed/60:.1f} min ({total_elapsed/3600:.2f} hr) ===")


if __name__ == "__main__":
    main()
