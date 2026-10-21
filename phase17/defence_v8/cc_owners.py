"""SA-8 owner pool (v8; pre-registered docs/phase17/v8/V8_PREREGISTRATION.md).

The LoCoMo owner pool (samples 0-9) is exhausted: SA-1 through SA-7 all drew their owners
from it, so a fresh confirmatory corpus for capabilities 3.2/3.3 needs owners from a
dataset never used for owners before. This module adapts Conversation Chronicles (CC BY
4.0, already processed locally at data/processed/conversation_chronicles/) into the same
shape phase17.provenance_sets.owner_turns/speakers expose for LoCoMo, so phase17's existing
corpus-generation machinery (holdout4_corpus._excerpt, the SA-6/SA-7 prompt template) can
be reused unchanged.

Ten CC episodes were selected deterministically (see select_owner_episodes below for the
selection rule) and frozen here as OWNER_EPISODE by owner id 100-109, disjoint from every
LoCoMo sample index (0-9) used by SA-1..SA-7. 4 dev / 6 eval, matching SA-6/SA-7's 4:6 split
ratio.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

CC_MEMORY_RECORDS = Path("data/processed/conversation_chronicles/memory_records.jsonl")

DEV_OWNERS = (100, 102, 104, 106)
EVAL_OWNERS = (101, 103, 105, 107, 108, 109)

# Frozen owner -> CC conversation_id mapping. Selection rule (deterministic, documented for
# reproducibility): group memory_records.jsonl by conversation_id, keep episodes with
# exactly two distinct source_role speakers and 40-90 total turns, sort by conversation_id
# ascending, take the first 10.
OWNER_EPISODE: Dict[int, str] = {
    100: "episode-100005",
    101: "episode-100015",
    102: "episode-100027",
    103: "episode-100060",
    104: "episode-100072",
    105: "episode-100076",
    106: "episode-100092",
    107: "episode-100188",
    108: "episode-100224",
    109: "episode-100228",
}


def select_owner_episodes(n: int = 10, min_turns: int = 40, max_turns: int = 90) -> List[str]:
    """Reproduces the selection above from raw memory_records.jsonl (not used at run time;
    kept so the frozen OWNER_EPISODE mapping above can be independently re-derived)."""
    from collections import defaultdict

    turns: Dict[str, List[dict]] = defaultdict(list)
    with open(CC_MEMORY_RECORDS, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            turns[d["conversation_id"]].append(d)

    def sess_num(s: str) -> int:
        return int(s.split("_")[1]) if "_" in s else 0

    cands = []
    for cid, items in turns.items():
        items.sort(key=lambda d: (sess_num(d["session_id"]), d["event_order"]))
        speakers = sorted(set(d["source_role"] for d in items))
        if len(speakers) == 2 and min_turns <= len(items) <= max_turns:
            cands.append(cid)
    cands.sort()
    return cands[:n]


def _episode_turns(conversation_id: str) -> List[dict]:
    rows = []
    with open(CC_MEMORY_RECORDS, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if d["conversation_id"] == conversation_id:
                rows.append(d)

    def sess_num(s: str) -> int:
        return int(s.split("_")[1]) if "_" in s else 0

    rows.sort(key=lambda d: (sess_num(d["session_id"]), d["event_order"]))
    return rows


def speakers(owner: int) -> List[str]:
    rows = _episode_turns(OWNER_EPISODE[owner])
    seen = []
    for r in rows:
        if r["source_role"] not in seen:
            seen.append(r["source_role"])
    return seen[:2]


def owner_turns(owner: int) -> List[Dict]:
    """Same shape as phase17.provenance_sets.owner_turns: dia_id/speaker/text, text
    pre-formatted as 'speaker: content' so holdout4_corpus._excerpt can join it directly."""
    rows = _episode_turns(OWNER_EPISODE[owner])
    return [{"dia_id": r["memory_id"], "speaker": r["source_role"],
              "text": f"{r['source_role']}: {r['content']}"} for r in rows]
