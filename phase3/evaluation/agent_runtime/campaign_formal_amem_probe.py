"""Phase 3.3-G -- SMALL, EXPLICITLY-LABELED real A-MEM cost measurement probe.

NOT part of the formal statistical campaign. This runs REAL A-MEM ingestion against
ONE real LoCoMo session and ONE real LongMemEval haystack, both drawn from the ACTUAL
frozen N=120 sample (not synthetic data), purely to obtain a precise, real per-item
ingestion rate for THIS campaign's real content -- refining the projection already
computed from 3.3-D/E/F measurements before deciding how to handle Condition C at
formal scale. Results here are NOT counted as formal campaign task evaluations.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from phase3.evaluation.agent_runtime.campaign_runner import _ingest_pool
from phase3.evaluation.agent_runtime.campaign_sampling import build_formal_sample
from phase3.evaluation.foundations.adapter import FOUNDATION_AVAILABLE

OUTPUT_PATH = _REPO_ROOT / "phase3" / "experiments" / "results" / "campaign_3_3g_amem_probe_result.json"


def probe_one_pool(dataset: str, ingest_key_field: str, ingest_key_value: str, label: str) -> dict:
    from phase3.evaluation.foundations_real.amem_real_adapter import RealAMemAdapter

    foundation = RealAMemAdapter()
    init_field = foundation.initialize({"embedding_model": "all-MiniLM-L6-v2"})
    if init_field.availability != FOUNDATION_AVAILABLE:
        return {"label": label, "error": f"initialize() -> {init_field.availability}"}
    foundation.reset()

    rows = list(_ingest_pool(dataset, ingest_key_field, ingest_key_value))
    t0 = time.time()
    ingested = 0
    for row in rows:
        add_field = foundation.add_memory(
            memory_id=row["memory_id"],
            content={"text": f"{row['source_role']}: {row['content']}"},
            metadata={"tags": ["g_probe", dataset], "keywords": [], "context": "probe"},
        )
        if add_field.availability == FOUNDATION_AVAILABLE:
            ingested += 1
    elapsed = time.time() - t0
    foundation.shutdown()

    return {
        "label": label, "dataset": dataset, "pool_key": ingest_key_value,
        "pool_size": len(rows), "ingested": ingested, "elapsed_sec": elapsed,
        "sec_per_item": elapsed / len(rows) if rows else None,
    }


def run_probe() -> dict:
    sample = build_formal_sample(120)
    loco = sample["locomo"]
    lme = sample["longmemeval"]

    # Smallest real LoCoMo session in the ACTUAL frozen sample.
    loco_pools = sorted(set((t.ingest_key_value, t.pool_size) for t in loco), key=lambda p: p[1])
    smallest_loco = loco_pools[0]

    # Smallest real LongMemEval haystack in the ACTUAL frozen sample.
    lme_pools = sorted(set((t.ingest_key_value, t.pool_size) for t in lme), key=lambda p: p[1])
    smallest_lme = lme_pools[0]

    print(f"Probing LoCoMo session {smallest_loco[0]} (pool_size={smallest_loco[1]})...")
    result_loco = probe_one_pool("locomo", "session", smallest_loco[0], "locomo_smallest_real_session")
    print(f"  {result_loco}")

    print(f"Probing LongMemEval haystack {smallest_lme[0]} (pool_size={smallest_lme[1]})...")
    result_lme = probe_one_pool("longmemeval", "source_record_id", smallest_lme[0], "longmemeval_smallest_real_haystack")
    print(f"  {result_lme}")

    output = {
        "note": "SMALL PROBE ONLY -- not part of the formal statistical campaign. Real "
        "A-MEM ingestion measured against real pools from the actual frozen N=120 "
        "sample, used only to refine the Condition-C runtime projection.",
        "locomo_probe": result_loco,
        "longmemeval_probe": result_lme,
    }
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False, default=str)
    print(f"Written to {OUTPUT_PATH}")
    return output


if __name__ == "__main__":
    run_probe()
