"""Phase 3.3-V5 -- Stage 3 targeted failure evaluation (per PHASE3_V5_EXPERIMENT_PLAN.md).
First slice run: the Melanie-children multi-hop/counting case that directly
motivated the structured-memory layer (see PHASE3_V5_DESIGN_RATIONALE.md Sec 3).
V5_BASE vs V5_STRUCTURED vs V5_FULL, Condition B (gold evidence).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from phase3.evaluation.agent_runtime.campaign_v5_runner import V5_BASE, V5_FULL, V5_STRUCTURED, run_condition_b_v5
from phase3.evaluation.llm.provider import LlamaServerEndpoint, LlamaServerProvider, clean_baseline_generation_config

_DATA_ROOT = _REPO_ROOT / "data" / "processed"
_OUT_DIR = Path(__file__).resolve().parent / "results"


class _TaskShim:
    def __init__(self, task_id, dataset, question, answer, evidence_memory_ids):
        self.task_id = task_id
        self.dataset = dataset
        self.question = question
        self.answer = answer
        self.evidence_memory_ids = evidence_memory_ids


TARGET_TASK_ID = "ae713a37de7c095811e54d5a"  # "How many children does Melanie have?" gold=3


def main():
    task_records = {}
    with open(_DATA_ROOT / "locomo" / "task_records.jsonl", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            task_records[r["task_id"]] = r

    t = task_records[TARGET_TASK_ID]
    task = _TaskShim(TARGET_TASK_ID, "locomo", t["question"], str(t["answer"]), t["evidence_memory_ids"])
    print(f"Q: {t['question']!r}  GOLD: {t['answer']!r}")

    endpoint = LlamaServerEndpoint()
    llm_provider = LlamaServerProvider(endpoint)
    llm_provider.verify_server_identity()
    generation_config = clean_baseline_generation_config(max_tokens=256, n_ctx=4096)

    all_results = {}
    for cfg in (V5_BASE, V5_STRUCTURED, V5_FULL):
        results = run_condition_b_v5([task], llm_provider, generation_config, campaign_id="v5-stage3-targeted", v5_config=cfg)
        r = results[0]
        all_results[cfg.label] = r
        if r["status"] == "SUCCESSFUL_EVALUATION":
            answer = r["trace"]["agent_output"]
            facts = r["trace"].get("v5", {}).get("structured_memory", {}).get("facts", [])
            print(f"\n[{cfg.label}] answer: {answer!r}")
            print(f"  structured facts: {facts}")
        else:
            print(f"\n[{cfg.label}] EXECUTION_FAILURE: {r.get('error')}")

    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    with (_OUT_DIR / "pilot_v5_stage3_melanie_children.json").open("w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False, default=str)


if __name__ == "__main__":
    main()
