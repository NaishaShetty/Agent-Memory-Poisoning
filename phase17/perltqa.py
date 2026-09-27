"""Phase 17 -- PerLTQA (Chinese) as a real benign population, INCLUDED (the
earlier plan excluded it because English-pattern signals cannot fire on
Chinese, which would make a bare "0% FPR" vacuous). It is now paired with a
recorded Chinese translation of the poison sets (`translation.py`) so the
language axis is a real test with a real non-zero-possible outcome: benign
Chinese FPR AND Chinese poison detection are both measured.

Pools: one per real DIALOGUE record (first session's utterances, <=12) and one
per group of 10 real EVENT records. Content is used exactly as stored.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple

from phase17.engine import Truth
from phase6.defense.orchestration.pipeline import MemoryScenario, ScenarioPool

PERLTQA = Path("phase3/datasets/candidates/perltqa/normalized/memory_records.jsonl")
N_DIALOGUE_POOLS = 80
N_EVENT_POOLS = 30
EVENTS_PER_POOL = 10
MAX_UTTERANCES = 12


def perltqa_pools() -> Tuple[List[ScenarioPool], Dict[str, Truth]]:
    pools, truth = [], {}
    events: List[str] = []
    with PERLTQA.open(encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            kind, ctx = r["memory_kind"], r["agent_visible_context"]
            if kind == "DIALOGUES" and sum(1 for p in pools if p.pool_id.startswith("PERLTQA-D")) < N_DIALOGUE_POOLS:
                sessions = ctx.get("contents", {})
                if not sessions:
                    continue
                utts = [u for u in next(iter(sessions.values())) if u.strip()][:MAX_UTTERANCES]
                if len(utts) < 3:
                    continue
                pid = f"PERLTQA-D{len(pools)}"
                mems = []
                for k, u in enumerate(utts):
                    mid = f"{pid}:{k}"
                    mems.append(MemoryScenario(mid, u))
                    truth[mid] = Truth(False, None, "benign_perltqa")
                pools.append(ScenarioPool(pid, tuple(mems)))
            elif kind == "EVENTS" and len(events) < N_EVENT_POOLS * EVENTS_PER_POOL and ctx.get("content", "").strip():
                events.append(ctx["content"])
    for g in range(N_EVENT_POOLS):
        chunk = events[g * EVENTS_PER_POOL:(g + 1) * EVENTS_PER_POOL]
        if len(chunk) < 3:
            break
        pid = f"PERLTQA-E{g}"
        mems = []
        for k, t in enumerate(chunk):
            mid = f"{pid}:{k}"
            mems.append(MemoryScenario(mid, t))
            truth[mid] = Truth(False, None, "benign_perltqa")
        pools.append(ScenarioPool(pid, tuple(mems)))
    return pools, truth


__all__ = ["perltqa_pools"]
