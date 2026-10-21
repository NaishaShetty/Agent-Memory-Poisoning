"""SA-9 owner pool (v8 addendum W1b; docs/phase17/v8/V8_PREREG_ADDENDUM_W1b.md Sec 3.0).

LongMemEval (MIT), never used for owners before (SA-1..SA-8 exhausted LoCoMo and
Conversation Chronicles). Same adapter shape as phase17.defence_v8.cc_owners, so the
existing corpus-generation machinery works unchanged. Owner ids 200-209, disjoint from
every id any prior SA corpus used.

LongMemEval's two roles are generically "user"/"assistant" (a human-AI transcript, not two
humans); callers that need a sensible rule SUBJECT must use "user" (speakers()[0]), never
"assistant" -- see sa9_corpus.py, which always sets who = "User" (D-V8-4).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

LME_MEMORY_RECORDS = Path("data/processed/longmemeval/memory_records.jsonl")

DEV_OWNERS = (200, 202, 204, 206)
EVAL_OWNERS = (201, 203, 205, 207, 208, 209)

# Frozen owner -> LongMemEval conversation_id mapping. Selection rule (deterministic):
# group memory_records.jsonl by conversation_id, keep episodes with exactly two distinct
# source_role values and 40-120 total turns (event_order alone orders turns correctly --
# every conversation_id maps to exactly one session_id in this corpus), sort by
# conversation_id ascending, take the first 10 of the 19 candidates.
OWNER_EPISODE: Dict[int, str] = {
    200: "answer_b10dce5e",
    201: "answer_cebb7159",
    202: "answer_d586e9cd",
    203: "answer_sharegpt_GYqnAhC_190",
    204: "answer_sharegpt_d6JJiqH_76",
    205: "answer_sharegpt_i9adwQn_0",
    206: "answer_sharegpt_m2xJfjo_0",
    207: "sharegpt_11WxPMZ_0",
    208: "sharegpt_5m6qXKr_0",
    209: "sharegpt_8qFtl50_53",
}


def select_owner_episodes(n: int = 10, min_turns: int = 40, max_turns: int = 120) -> List[str]:
    """Reproduces OWNER_EPISODE from raw memory_records.jsonl (kept for independent
    re-derivation; not used at run time)."""
    from collections import defaultdict

    turns: Dict[str, List[dict]] = defaultdict(list)
    with open(LME_MEMORY_RECORDS, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            turns[d["conversation_id"]].append(d)

    cands = []
    for cid, items in turns.items():
        items.sort(key=lambda d: d["event_order"])
        speakers = sorted(set(d["source_role"] for d in items))
        if len(speakers) == 2 and min_turns <= len(items) <= max_turns:
            cands.append(cid)
    cands.sort()
    return cands[:n]


def _episode_turns(conversation_id: str) -> List[dict]:
    rows = []
    with open(LME_MEMORY_RECORDS, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if d["conversation_id"] == conversation_id:
                rows.append(d)
    rows.sort(key=lambda d: d["event_order"])
    return rows


def speakers(owner: int) -> List[str]:
    rows = _episode_turns(OWNER_EPISODE[owner])
    seen = []
    for r in rows:
        if r["source_role"] not in seen:
            seen.append(r["source_role"])
    # "user" first, always, regardless of which role appears first in the transcript --
    # callers that pick speakers(owner)[0] as the rule subject must get the human, not the
    # assistant role.
    seen.sort(key=lambda s: s != "user")
    return seen[:2]


def owner_turns(owner: int) -> List[Dict]:
    rows = _episode_turns(OWNER_EPISODE[owner])
    return [{"dia_id": r["memory_id"], "speaker": r["source_role"],
              "text": f"{r['source_role']}: {r['content']}"} for r in rows]
