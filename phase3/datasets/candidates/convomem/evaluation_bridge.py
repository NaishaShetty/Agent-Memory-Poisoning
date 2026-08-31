"""Phase 3.2-J.3 -- bridges ConvoMem's J.2-normalized records into the flat shape
`phase3.evaluation.integration.dataset_adapter.build_evaluator_reference` expects
(`record["answer"]`, `record["evidence_memory_ids"]`), and builds a per-MESSAGE
`memory_id -> {"content": ...}` lookup table (finer-grained than the per-evidence_item
memory_records.jsonl rows), WITHOUT modifying `normalize.py` (J.2 output, only the
additive location-population fix) or `integration/dataset_adapter.py` (frozen H contract).

ConvoMem's `evidence_memory_ids` (per `ConvoMemAdapter.encoded_evidence_ids`) reference
individual MESSAGES within a conversation, not whole evidence_items -- this module
flattens each memory_records.jsonl row's bundled `conversations` into one lookup entry
per message, keyed by the SAME `ADAPTER_DERIVED_IDENTITY` encoding
(`identity.encode_convomem_memory_identity`) the evidence IDs use, so a
`selected_memory_ids` lookup and a `gold_evidence_ids` lookup share one consistent
namespace.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Tuple

from phase3.evaluation.extensions.adapters.convomem_adapter import (
    ConvoMemAdapter,
    load_memory_records,
    load_task_records,
)
from phase3.evaluation.extensions.identity import encode_convomem_memory_identity

_ADAPTER = ConvoMemAdapter()

DATASET_ID = "convomem"


def build_memory_lookup(memory_records: List[Mapping[str, Any]]) -> Dict[str, Mapping[str, Any]]:
    """`memory_id -> {"content": ...}` for every individual MESSAGE across every
    evidence_item's bundled conversations, keyed by
    `identity.encode_convomem_memory_identity(conversation_id, message_index)` -- the same
    encoding `ConvoMemAdapter.encoded_evidence_ids` produces for resolved evidence spans."""
    lookup: Dict[str, Mapping[str, Any]] = {}
    for rec in memory_records:
        conversations = rec.get("agent_visible_context", {}).get("conversations") or []
        for ci, conv in enumerate(conversations):
            cid = conv.get("id")
            if not cid:
                continue
            for mi, m in enumerate(conv.get("messages", []) or []):
                if "text" not in m:
                    continue
                memory_id = encode_convomem_memory_identity(cid, mi)
                lookup[memory_id] = {"content": m["text"], "speaker": m.get("speaker")}
    return lookup


def to_evaluation_record(task_record: Mapping[str, Any]) -> Dict[str, Any]:
    """Flatten one ConvoMem task record into the shape
    `dataset_adapter.build_evaluator_reference` reads. `evidence_memory_ids` includes
    ONLY spans the J.2 waterfall resolved (EXACT_RAW/EXACT_NORMALIZED/TRUNCATED_UNIQUE/
    MULTIMESSAGE_UNIQUE) -- UNRESOLVED/TOO_SHORT/*_AMBIGUOUS spans contribute nothing,
    never a fabricated id (see `ConvoMemAdapter.encoded_evidence_ids`)."""
    answer_field = _ADAPTER.answer(task_record)
    evidence_ids = _ADAPTER.encoded_evidence_ids(task_record)
    return {
        "answer": answer_field.value,
        "evidence_memory_ids": evidence_ids,
    }


def scoped_memories_for_task(
    task_record: Mapping[str, Any], memory_lookup: Mapping[str, Mapping[str, Any]]
) -> Dict[str, Mapping[str, Any]]:
    """Return only the memory-lookup entries belonging to this task's OWN evidence_item
    (its `source_record_id` prefix), not the entire corpus lookup.

    REAL FINDING (Phase 3.2-J.3): `phase3.evaluation.metrics.provenance
    .provenance_completeness_report` (a frozen 3.2-D canonical metric, never modified
    here) is O(n^2) in the size of its `memories` argument -- calling it with this
    bridge's full ~76,587-entry per-message lookup for a single case took minutes and
    was killed rather than left to complete. This had never been exercised at real
    multi-tens-of-thousands-of-records scale before (existing integration tests use
    small, hand-built synthetic memory dicts). Passing the FULL corpus as one case's
    `memories` was never the metric's intended usage pattern -- a real case only ever
    has the small number of memories actually relevant to it. This function restores
    that realistic scoping; it does not patch, wrap, or alter the metric function
    itself."""
    prefix = task_record.get("memory_ref")
    if not prefix:
        return {}
    conv_prefix = f"CONVOMEM<"
    # memory ids for this evidence_item's own conversations only
    resolution = task_record.get("evaluator_only", {}).get("evidence_resolution")
    conv_ids = set()
    if isinstance(resolution, list):
        for r in resolution:
            for loc in r.get("locations", []) or []:
                cid = loc.get("conversation_id")
                if cid:
                    conv_ids.add(cid)
    if not conv_ids:
        return {}
    return {
        mid: content
        for mid, content in memory_lookup.items()
        if any(mid.startswith(f"{conv_prefix}{cid}>") for cid in conv_ids)
    }


def load_evaluation_universe(task_limit: int = None, memory_limit: int = None) -> Tuple[
    List[Mapping[str, Any]], Dict[str, Mapping[str, Any]]
]:
    """Load (task_records, memory_lookup) ready for `dataset_adapter.build_evaluation_case`
    calls. Operates on the committed 18-file `raw/` sample's normalized output -- the same
    scope every ConvoMem test in this repository operates on (the full 75,336-item corpus
    is REACQUISITION_REPRODUCIBLE, not locally present, per J.2's disclosed size limit)."""
    task_records = load_task_records(limit=task_limit)
    memory_records = load_memory_records(limit=memory_limit)
    return task_records, build_memory_lookup(memory_records)


_PROFILE_PATH = Path(__file__).resolve().parent / "profile" / "convomem_evaluation_profile.json"


def load_evaluation_profile() -> Mapping[str, Any]:
    """The pipeline-consumable evaluation profile (distinct from
    `profile/convomem_profile.json`, J.1/J.2's capability-audit-shaped document -- this one
    mirrors `phase3/evaluation/datasets/profiles/locomo.json`'s shape)."""
    with open(_PROFILE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)
