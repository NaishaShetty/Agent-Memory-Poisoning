"""Phase 3.2-J.3 -- bridges PerLTQA's (zh) J.1-normalized records into the flat shape
`phase3.evaluation.integration.dataset_adapter.build_evaluator_reference` expects
(`record["answer"]`, `record["evidence_memory_ids"]`), and builds a `memory_id ->
{"content": ...}` lookup table, WITHOUT modifying `normalize.py` (frozen J.1 output) or
`integration/dataset_adapter.py` (frozen H stage contract).

This is the "dataset-native representation -> common evaluation representation"
translation Part 9 requires -- it reuses `PerLTQAAdapter` (extensions/adapters/
perltqa_adapter.py) for every field access, never re-deriving field lookups itself.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Tuple

from phase3.evaluation.extensions.adapters.perltqa_adapter import (
    PerLTQAAdapter,
    load_memory_records,
    load_task_records,
)

_ADAPTER = PerLTQAAdapter()

DATASET_ID = "perltqa"


def build_memory_lookup(memory_records: List[Mapping[str, Any]]) -> Dict[str, Mapping[str, Any]]:
    """`memory_id -> {"content": <str>, "structured_content": <dict>}` for every PerLTQA
    memory unit, keyed by the `NATIVE_MEMORY_ID` (character-scope-resolved)
    `PerLTQAAdapter.memory_identity` produces.

    `structured_content` is `PerLTQAAdapter.native_memory()`'s value verbatim -- the
    source-native dict, never flattened, per this stage's explicit "do not collapse
    source-native structure" instruction. `content` is a DETERMINISTIC, LOSSLESS,
    REVERSIBLE `json.dumps(..., sort_keys=True)` serialization of that same dict -- this
    exists ONLY because `agent_visible_context.schema.json` (a frozen Phase 3.2-B
    contract) requires `memory_content[].content` to be a plain string; it is a
    canonical re-encoding of the exact same structure (recoverable via `json.loads`),
    not a paraphrase, summary, or lossy flattening. Chinese characters are preserved
    verbatim (`ensure_ascii=False`)."""
    lookup: Dict[str, Mapping[str, Any]] = {}
    for rec in memory_records:
        identity = _ADAPTER.memory_identity(rec)
        if identity.availability != "AVAILABLE":
            continue
        content_field = _ADAPTER.native_memory(rec)
        structured = content_field.value
        serialized = json.dumps(structured, ensure_ascii=False, sort_keys=True)
        lookup[identity.value] = {"content": serialized, "structured_content": structured}
    return lookup


def to_evaluation_record(task_record: Mapping[str, Any]) -> Dict[str, Any]:
    """Flatten one PerLTQA task record into the shape
    `dataset_adapter.build_evaluator_reference` reads (`answer`, `evidence_memory_ids`).
    Evidence IDs are the `NATIVE_MEMORY_ID` (character-scope-resolved) encoding, not the
    bare source ID (which is not globally unique) -- see `identity.py`."""
    answer_field = _ADAPTER.answer(task_record)
    evidence_ids = _ADAPTER.encoded_evidence_ids(task_record)
    return {
        "answer": answer_field.value,
        "evidence_memory_ids": evidence_ids,
    }


def scoped_memories_for_task(
    task_record: Mapping[str, Any], memory_lookup: Dict[str, Mapping[str, Any]]
) -> Dict[str, Mapping[str, Any]]:
    """Return only the memory-lookup entries belonging to this task's own `character` --
    realistic per-case scoping (a real case only has the memories relevant to one
    character's story, not the whole 141-character corpus). See
    `phase3.datasets.candidates.convomem.evaluation_bridge.scoped_memories_for_task`'s
    docstring for why per-case scoping matters for `provenance_completeness_report`'s
    real, discovered O(n^2) behavior at large scale -- the same discipline applies here
    even though PerLTQA's corpus (7,521 memory units) is much smaller."""
    character = task_record.get("character")
    if not character:
        return {}
    prefix = f"PERLTQA<{character}>::"
    return {mid: content for mid, content in memory_lookup.items() if mid.startswith(prefix)}


def load_evaluation_universe(task_limit: int = None, memory_limit: int = None) -> Tuple[
    List[Mapping[str, Any]], Dict[str, Mapping[str, Any]]
]:
    """Load (task_records, memory_lookup) ready for `dataset_adapter.build_evaluation_case`
    calls -- one call per task record, e.g.:

        tasks, memories = load_evaluation_universe()
        for i, t in enumerate(tasks):
            case = dataset_adapter.build_evaluation_case(
                dataset_id=DATASET_ID, profile=PROFILE, task_id=f"perltqa-{i}",
                prompt=t["agent_visible"]["question"], condition=CONDITION_GOLD_EVIDENCE,
                record=to_evaluation_record(t), memories=memories,
                selected_memory_ids=to_evaluation_record(t)["evidence_memory_ids"],
            )
    """
    task_records = load_task_records(limit=task_limit)
    memory_records = load_memory_records(limit=memory_limit)
    return task_records, build_memory_lookup(memory_records)


_PROFILE_PATH = Path(__file__).resolve().parent / "profile" / "perltqa_evaluation_profile.json"


def load_evaluation_profile() -> Mapping[str, Any]:
    """The pipeline-consumable evaluation profile (distinct from
    `profile/perltqa_profile.json`, which is J.1's capability-audit-shaped document --
    this one mirrors `phase3/evaluation/datasets/profiles/locomo.json`'s shape so
    `integration.validation`/`integration.pipeline` can consume it directly)."""
    with open(_PROFILE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)
