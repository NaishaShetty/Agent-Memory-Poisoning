"""Regenerates ONLY Condition B of the 3.3-V3-HYBRID-FULL-R5 campaign, using the
now-fixed `run_condition_b_hybrid()` (P2 fix 2026-09-14: explicit
`unresolved_evidence_ids` tracking + `failure_kind` tagging on the
except-Exception path -- see git diff on
phase3/evaluation/agent_runtime/campaign_v3_hybrid_runner.py).

Conditions A, C-mem0, C-amem are NOT re-run: `run_condition_a`,
`run_condition_c_v3_mem0`, and `run_condition_c_v3_amem` were not touched by the
P0/P2 remediation (verified via `git diff` before writing this script -- the
diff for campaign_v3_hybrid_runner.py only modifies `run_condition_b_hybrid`),
so their existing checkpoints (`results_a.json`, `results_c_mem0.json`,
`results_c_amem.json`) remain valid inputs to the final assembly step. This
follows the resource-reconciliation task's own Part J rule: "not regenerated"
must be justified by dependency analysis, not convenience -- the justification
here is a diff, not an assumption.

Same sample (build_formal_sample, seed 33005, same as V1-V5), same
v5_gen_config as the original script, same CAMPAIGN_ID. Writes to a NEW
checkpoint file (results_b_P2FIX.json), never overwrites the original
results_b.json (already separately backed up to
checkpoints/pre_p2_fix_backup_2026-09-15/results_b_OLD.json).
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

# A fresh campaign_id namespace, not a reuse of "3.3-V3-HYBRID-FULL-R5": the
# original script's own comment documents a real CanonicalCollisionError when a
# campaign_id's canonical-ledger entries already exist and are re-ingested under
# the same id. Condition B's memory/event records for the R5 campaign_id already
# exist on disk from the original run, so re-running run_condition_b_hybrid under
# the identical id would hit that same collision, not a clean regeneration.
CAMPAIGN_ID = "3.3-V3-HYBRID-FULL-R5-P2FIX"
CHECKPOINT_DIR = V3_HYBRID_STORE / "checkpoints"


def _save_json(path: Path, data) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)


def main():
    def log(msg):
        print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

    log("=== Sampling: 120 real LoCoMo tasks (formal sample, seed 33005 -- identical to the original run) ===")
    sample = build_formal_sample(n_per_dataset=120)
    loco_tasks = sample["locomo"]
    log(f"Sampled {len(loco_tasks)} real LoCoMo tasks.")

    endpoint = LlamaServerEndpoint()
    llm_provider = LlamaServerProvider(endpoint)
    identity = llm_provider.verify_server_identity()
    log(f"Server identity verified: {identity}")

    v5_gen_config = clean_baseline_generation_config(n_ctx=4096, max_tokens=256)

    log("=== Condition B (P2-fix regeneration): starting ===")
    t0 = time.time()
    results_b_new = run_condition_b_hybrid(loco_tasks, llm_provider, v5_gen_config, CAMPAIGN_ID)
    out_path = CHECKPOINT_DIR / "results_b_P2FIX.json"
    _save_json(out_path, results_b_new)
    succeeded = sum(1 for r in results_b_new if r["status"] == "SUCCESSFUL_EVALUATION")
    log(f"Condition B (P2-fix) done: {succeeded}/{len(loco_tasks)} succeeded, {time.time()-t0:.1f}s")
    log(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
