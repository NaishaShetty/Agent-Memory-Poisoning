"""V3 campaign smoke test -- small n, both foundations, all conditions, through the
real production pipeline (`campaign_v3_runner.py`). Verifies before the full run:
execution succeeds for both foundations, V1 AND V2 canonical files remain untouched.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from phase3.evaluation.agent_runtime.campaign_sampling import build_formal_sample
from phase3.evaluation.agent_runtime.campaign_v3_runner import (
    run_condition_a, run_condition_b_v3, run_condition_c_v3_amem, run_condition_c_v3_mem0,
)
from phase3.evaluation.llm.provider import LlamaServerEndpoint, LlamaServerProvider, clean_baseline_generation_config

V1_PATH = _REPO_ROOT / "phase3" / "experiments" / "results" / "canonical_store" / "dataset_full" / "clean_agent_dataset_locomo_120x2.json"
V2_PATH = _REPO_ROOT / "phase3" / "experiments" / "results" / "canonical_store" / "v2_candidate" / "dataset_full" / "clean_agent_dataset_v2_locomo_120x2.json"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    def log(msg):
        print(msg, flush=True)

    v1_before, v2_before = _sha256(V1_PATH), _sha256(V2_PATH)
    log(f"V1 hash before: {v1_before}")
    log(f"V2 hash before: {v2_before}")

    sample = build_formal_sample(n_per_dataset=4)
    loco_tasks = sample["locomo"]
    log(f"Sampled {len(loco_tasks)} real tasks: {[t.task_id for t in loco_tasks]}")

    endpoint = LlamaServerEndpoint()
    llm_provider = LlamaServerProvider(endpoint)
    log(f"Server identity: {llm_provider.verify_server_identity()}")
    gen_config = clean_baseline_generation_config(n_ctx=4096, max_tokens=64)
    campaign_id = "SMOKE-V3-CAMPAIGN"

    log("\n=== Condition A ===")
    results_a = run_condition_a(loco_tasks, llm_provider, gen_config, campaign_id)
    log(f"A: {sum(1 for r in results_a if r['status']=='SUCCESSFUL_EVALUATION')}/{len(loco_tasks)}")

    log("\n=== Condition B (V3: timestamp + temporal resolution) ===")
    results_b = run_condition_b_v3(loco_tasks, llm_provider, gen_config, campaign_id)
    log(f"B: {sum(1 for r in results_b if r['status']=='SUCCESSFUL_EVALUATION')}/{len(loco_tasks)}")

    log("\n=== Condition C, Mem0 (V3: hybrid + temporal resolution) ===")
    results_c_mem0 = run_condition_c_v3_mem0(loco_tasks, llm_provider, gen_config, campaign_id)
    log(f"C-Mem0: {sum(1 for r in results_c_mem0 if r['status']=='SUCCESSFUL_EVALUATION')}/{len(loco_tasks)}")

    log("\n=== Condition C, A-MEM (V3: hybrid + temporal resolution) ===")
    results_c_amem = run_condition_c_v3_amem(loco_tasks, llm_provider, gen_config, campaign_id)
    log(f"C-AMEM: {sum(1 for r in results_c_amem if r['status']=='SUCCESSFUL_EVALUATION')}/{len(loco_tasks)}")

    v1_after, v2_after = _sha256(V1_PATH), _sha256(V2_PATH)
    log(f"\nV1 unchanged: {v1_before == v1_after}")
    log(f"V2 unchanged: {v2_before == v2_after}")

    all_ok = (
        len(results_a) == len(loco_tasks) and all(r["status"] == "SUCCESSFUL_EVALUATION" for r in results_a)
        and len(results_b) == len(loco_tasks) and all(r["status"] == "SUCCESSFUL_EVALUATION" for r in results_b)
        and len(results_c_mem0) == len(loco_tasks) and all(r["status"] == "SUCCESSFUL_EVALUATION" for r in results_c_mem0)
        and len(results_c_amem) == len(loco_tasks) and all(r["status"] == "SUCCESSFUL_EVALUATION" for r in results_c_amem)
        and v1_before == v1_after and v2_before == v2_after
    )
    log(f"\nALL CHECKS PASS: {all_ok}")
    if not all_ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
