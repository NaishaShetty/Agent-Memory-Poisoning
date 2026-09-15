"""Targeted rerun of the 268 real Condition B tasks that showed
AGENT_EXECUTION_FAILURE (draft_answer=null after exhausted generation
retries, top-level campaign status still SUCCESSFUL_EVALUATION -- a real,
distinct failure category, not a scoring bug) in the mixed-N 500-task
campaign. Investigating whether this was transient server instability
during that window: this script reruns exactly those 268 task_ids against
the now-confirmed-healthy server and merges successful results back into
the checkpoint, never fabricating an answer for one that still fails.
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
    V3_HYBRID_STORE, run_condition_b_hybrid,
)
from phase3.evaluation.llm.provider import LlamaServerEndpoint, LlamaServerProvider, clean_baseline_generation_config

# A fresh campaign_id namespace, not a reuse of the original -- these 268
# tasks' memory content was already ingested into canonical stores under the
# original campaign_id even though generation failed; re-ingesting under the
# same id risks the documented CanonicalCollisionError class (see
# run_v3_hybrid_full_campaign.py's own comment on this exact failure mode).
CAMPAIGN_ID = "3.3-V3-HYBRID-FULL-R6-MIXEDN-BRETRY"
CHECKPOINT_DIR = V3_HYBRID_STORE / "checkpoints_mixed_n"
FAILED_IDS_PATH = Path(r"C:\Users\naish\AppData\Local\Temp\claude\C--Agent-Memory-Poisoning\4cc60a6c-8883-4a6a-a0ef-1fdb7d3109a1\scratchpad\failed_b_task_ids.json")


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def main():
    failed_ids = set(json.load(FAILED_IDS_PATH.open(encoding="utf-8")))
    log(f"Loaded {len(failed_ids)} previously-failed task ids.")

    sample = build_formal_sample(n_per_dataset=500)
    loco_tasks_full = sample["locomo"]
    retry_tasks = [t for t in loco_tasks_full if t.task_id in failed_ids]
    log(f"Matched {len(retry_tasks)} of {len(failed_ids)} failed ids in the sample.")

    endpoint = LlamaServerEndpoint()
    llm_provider = LlamaServerProvider(endpoint)
    identity = llm_provider.verify_server_identity()
    log(f"Server identity verified: {identity}")
    v5_gen_config = clean_baseline_generation_config(n_ctx=4096, max_tokens=256)

    log("=== Rerunning the 268 previously-failed tasks ===")
    t0 = time.time()
    new_results = run_condition_b_hybrid(retry_tasks, llm_provider, v5_gen_config, CAMPAIGN_ID)
    still_failed = [r for r in new_results if r["status"] != "SUCCESSFUL_EVALUATION" or r["trace"].get("failure_stage") == "AGENT_EXECUTION_FAILURE"]
    now_succeeded = len(new_results) - len(still_failed)
    log(f"Rerun done: {now_succeeded}/{len(new_results)} now genuinely succeeded, {len(still_failed)} still failed, {time.time()-t0:.1f}s")

    # Merge: replace the old failed entries with the new results (success or
    # still-failed, honestly, not silently dropped either way).
    b_path = CHECKPOINT_DIR / "results_b.json"
    old_results = json.load(b_path.open(encoding="utf-8"))
    new_by_id = {r["task_id"]: r for r in new_results}
    merged = [new_by_id.get(r["task_id"], r) for r in old_results]
    json.dump(merged, b_path.open("w", encoding="utf-8"), indent=2, ensure_ascii=False, default=str)
    log(f"Merged into {b_path}. Still-failed task ids: {[r['task_id'] for r in still_failed]}")


if __name__ == "__main__":
    main()
