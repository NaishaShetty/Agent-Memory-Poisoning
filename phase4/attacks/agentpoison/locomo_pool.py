"""Phase 4 -- AgentPoison Milestone 3: `load_db_locomo`, a reusable LoCoMo pool
loader matching the interface role of the reference implementation's
`load_db_ad`/`load_db_qa`/`load_db_ehr` (per PHASE4_4_1_AGENTPOISON_DOSSIER.md
Section 9 item 1) -- supplies a real, LoCoMo-derived candidate pool to the
domain-agnostic optimization core (core.py) without importing agentdriver/ReAct/
EhrAgent's own loaders.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence

LOCOMO_PATH = Path("data/raw/locomo/locomo10.json")


@dataclass(frozen=True)
class DomainTranslationRecord:
    """Per PHASE4_4_2_COMMON_ATTACK_CONTRACT.md Section 3 -- makes the
    LoCoMo-reformulation an explicit, reviewable artifact rather than
    something an adapter invents silently."""

    attack_id: str
    original_domain: str
    mambench_domain: str
    mechanism_preserved: Sequence[str]
    mechanism_reinterpreted: Sequence[str]
    rationale: str
    validation_status: str  # UNVALIDATED | PILOT_VALIDATED | VALIDATED


AGENTPOISON_LOCOMO_TRANSLATION = DomainTranslationRecord(
    attack_id="agentpoison",
    original_domain=(
        "Agent-Driver motion-planning documents (agentdriver/data/memory), "
        "StrategyQA paragraphs (ReAct/database), EHR clinical records (EhrAgent) "
        "-- three separate, domain-specific document/knowledge-base formats."
    ),
    mambench_domain="LoCoMo conversational memory turns (one flat text-per-turn format).",
    mechanism_preserved=(
        "Gaussian-kernel MMD + cluster-distance fitness (core.py, verbatim port)",
        "GradientStorage backward-hook gradient capture (core.py, verbatim port)",
        "HotFlip discrete token search (core.py, verbatim port)",
        "The core mechanism: optimize a trigger token sequence to push a "
        "trigger-augmented query's embedding away from the benign candidate "
        "pool's cluster centers, into a distinctive region",
    ),
    mechanism_reinterpreted=(
        "db_embeddings source: real LoCoMo conversation turns (a flat "
        "candidate pool) instead of a domain-specific structured document "
        "store -- same role (defines the 'normal' embedding distribution "
        "the trigger pushes away from), different content shape.",
        "Query construction: a real LoCoMo question, not "
        "AgentDriver's '{ego} {perception} NOTICE:' template or "
        "StrategyQA/EHR's own query framing.",
        "Embedding function: minilm_mean_pool_emb (Milestone 1 fix) replaces "
        "bert_get_emb's pooler_output convention -- necessary for the "
        "optimization to target Mem0's actual embedding space at all.",
    ),
    rationale=(
        "LoCoMo has no analogue to a driving-planning document or a "
        "structured clinical record -- conversational turns are the only "
        "content V3-Hybrid's Condition C actually retrieves over, so they "
        "are the natural (and only available) MAMBench-native candidate "
        "pool content."
    ),
    validation_status="PILOT_VALIDATED",  # per Milestone 2's real smoke-test run
)


def load_db_locomo(task_index: int = 0, max_turns: int = 17, sessions: Sequence[str] = ("session_1", "session_2")) -> List[str]:
    """Real LoCoMo turns from `data/raw/locomo/locomo10.json`, as plain
    "Speaker: text" strings -- the MAMBench-native `db_embeddings` source,
    replacing `load_db_ad`/`load_db_qa`/`load_db_ehr`."""
    with open(LOCOMO_PATH, encoding="utf-8") as f:
        data = json.load(f)
    conv = data[task_index]["conversation"]
    turns: List[str] = []
    for session_key in sessions:
        for turn in conv.get(session_key, []):
            turns.append(f"{turn['speaker']}: {turn['text']}")
            if len(turns) >= max_turns:
                return turns
    return turns


def load_locomo_questions(task_index: int = 0, max_questions: int = 20) -> List[str]:
    """Real LoCoMo QA questions from the same task -- the MAMBench-native
    query stream replacing AgentDriverDataset/StrategyQADataset/EHRAgent's
    own dataset classes."""
    with open(LOCOMO_PATH, encoding="utf-8") as f:
        data = json.load(f)
    qa = data[task_index].get("qa", [])
    return [item["question"] for item in qa[:max_questions]]


__all__ = [
    "DomainTranslationRecord",
    "AGENTPOISON_LOCOMO_TRANSLATION",
    "load_db_locomo",
    "load_locomo_questions",
]
