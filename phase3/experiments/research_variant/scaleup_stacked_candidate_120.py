"""Phase 3.3-RESEARCH Round 7 -- SCALE-UP: the stacked-three candidate (pool=20
retrieval + hybrid top-8 selection + timestamp injection, still no prompt/model/budget
change) run across the FULL real 120-task LoCoMo x Mem0 sample, per the explicit,
pre-agreed condition: Round 6's n=15 stacked result held exactly (matched the best
pairwise result, did not regress) -- the agreed trigger for scaling up.

V1's baseline is NOT re-run here. The frozen 240-record dataset
(`canonical_store/dataset_full/clean_agent_dataset_locomo_120x2.json`) already contains
real, recorded V1 answers for all 120 of these exact LoCoMo x Mem0 tasks -- this script
only executes the NEW stacked-three candidate and a separate analysis pass compares
against those existing frozen numbers. Frozen dataset is read-only throughout, never
modified.

Reuses every function from `pilot_stacked_three_candidate.py` unmodified (imported, not
copy-pasted) -- only N_TASKS changes (15 -> all 120 real MEM0 task_ids).
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pilot_stacked_three_candidate as base  # noqa: E402

from phase3.evaluation.llm.provider import LlamaServerEndpoint, LlamaServerProvider  # noqa: E402

_OUT_DIR = Path(__file__).resolve().parent / "results"
_OUT_DIR.mkdir(parents=True, exist_ok=True)


def _select_all_mem0_task_ids():
    with base.FROZEN_DATASET_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return sorted({r["task_id"] for r in data if r["foundation"] == "MEM0"})


def main():
    def log(msg):
        print(msg, flush=True)

    task_ids = _select_all_mem0_task_ids()
    tasks = base._build_task_records(task_ids)
    log(f"Selected ALL {len(tasks)} real MEM0 task_ids from the frozen 120x2 dataset (scale-up, not a resample).")

    endpoint = LlamaServerEndpoint()
    llm_provider = LlamaServerProvider(endpoint)
    identity_check = llm_provider.verify_server_identity()
    log(f"Server identity verified: {identity_check}")

    out_path = _OUT_DIR / "scaleup_stacked_candidate_n120_mem0.json"

    # Resume support: if a partial checkpoint from an earlier (e.g. killed) run exists,
    # load it and skip tasks already completed -- avoids losing work to an interrupted
    # session a second time, and avoids silently re-running (and re-ingesting) tasks
    # whose real result is already on disk.
    results = {}
    if out_path.exists():
        with out_path.open("r", encoding="utf-8") as f:
            prior = json.load(f)
        results = prior.get("results_C_stacked", {})
        log(f"Resuming from existing checkpoint: {len(results)}/{len(tasks)} tasks already completed.")

    def _checkpoint():
        with out_path.open("w", encoding="utf-8") as f:
            json.dump({"task_ids": task_ids, "tasks": tasks, "results_C_stacked": results}, f, indent=2, ensure_ascii=False)

    t_start = time.time()
    for i, task in enumerate(tasks):
        if task["task_id"] in results:
            continue  # already completed in a prior (interrupted) run
        log(f"\n=== Task {i+1}/{len(tasks)}: {task['task_id']} — {task['question']!r} (gold={task['answer']!r}) ===")
        base._run_stacked_c(task, llm_provider, results, log)
        _checkpoint()  # write after EVERY task -- cheap (single JSON file), makes the
                        # run resumable from any point, never loses more than one task's
                        # worth of work to an interruption.
        if len(results) % 10 == 0:
            elapsed = time.time() - t_start
            log(f"--- progress: {len(results)}/{len(tasks)} total completed, elapsed this run={elapsed/60:.1f}min ---")

    log(f"\nFinal write complete: {out_path}")

    n_norm = sum(1 for t in results.values() if t.get("normalized_status") == "ANSWER_CORRECT")
    n_exact = sum(1 for t in results.values() if t.get("exact_status") == "ANSWER_CORRECT")
    n_gold_pool = sum(1 for t in results.values() if t.get("gold_in_pool"))
    n_gold_sel = sum(1 for t in results.values() if t.get("gold_selected"))
    n = len(results)
    log(f"\n=== SUMMARY: SCALE-UP STACKED CANDIDATE (n={n}), Condition C ===")
    log(f"  normalized={n_norm}/{n} exact={n_exact}/{n} gold_in_pool={n_gold_pool}/{n} gold_selected={n_gold_sel}/{n}")


if __name__ == "__main__":
    main()
