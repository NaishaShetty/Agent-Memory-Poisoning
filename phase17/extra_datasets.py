"""Phase 17 -- additional real benign populations for security false-positive
testing (`PHASE17_PLAN.md` B4).

INCLUDED: ConvoMem (`phase3/datasets/candidates/convomem`) -- real English
multi-turn conversations. One pool per real conversation (up to
`MAX_MESSAGES` messages), first `N_POOLS` conversations in file order.

EXCLUDED, deliberately: PerLTQA's memory records are Chinese profile text;
this project's admission signals are English patterns, so they cannot fire on
it and a "0% FPR" would be vacuous, not evidence. Reported as excluded, not
silently dropped.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple

from phase17.engine import Truth
from phase6.defense.orchestration.pipeline import MemoryScenario, ScenarioPool

CONVOMEM = Path("phase3/datasets/candidates/convomem/normalized/memory_records.jsonl")
N_POOLS = 60
MAX_MESSAGES = 12


def convomem_pools(n_pools: int = N_POOLS) -> Tuple[List[ScenarioPool], Dict[str, Truth]]:
    pools, truth = [], {}
    with CONVOMEM.open(encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            for conv in rec["agent_visible_context"].get("conversations", []):
                msgs = [m["text"] for m in conv.get("messages", []) if m.get("text", "").strip()][:MAX_MESSAGES]
                if len(msgs) < 3:
                    continue
                pid = f"CONVOMEM-{len(pools)}"
                mems = []
                for k, t in enumerate(msgs):
                    mid = f"{pid}:{k}"
                    mems.append(MemoryScenario(mid, t))
                    truth[mid] = Truth(False, None, "benign_convomem")
                pools.append(ScenarioPool(pid, tuple(mems)))
                if len(pools) >= n_pools:
                    return pools, truth
    return pools, truth


__all__ = ["convomem_pools", "N_POOLS"]
