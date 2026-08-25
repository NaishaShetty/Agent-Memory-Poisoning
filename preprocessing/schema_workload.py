"""Common (loose) representation for task/domain workload resources
(API-Bank, ToolBench, StrategyQA, WebShop, SWE-bench Verified, tau-bench,
tau2-bench, EHRAgent -- research-plan section B).

These resources are NOT forced into the memory-substrate schema
(preprocessing.schema.MemoryRecord) -- their native structure (a tool
call, a GitHub issue/patch pair, a yes/no question, a task config) is
fundamentally different from a conversational turn. Instead each resource
keeps its native fields inside `payload`, and only the cross-cutting
concerns (identity, provenance, resource-type tagging) are normalized.
"""
from __future__ import annotations

import dataclasses
from typing import Any


@dataclasses.dataclass
class WorkloadRecord:
    record_id: str                # DERIVED: deterministic hash of provenance chain
    resource_id: str              # SOURCE-PROVIDED-adjacent: registry resource ID (e.g. "strategyqa")
    resource_category: str        # DERIVED: "task_workload"
    record_type: str              # DERIVED: what native structure this is, e.g. "qa_instance",
                                   # "tool_call_dialogue", "issue_patch_pair", "domain_task"
    source_file: str              # SOURCE-PROVIDED
    source_record_id: str         # SOURCE-PROVIDED
    payload: dict                 # SOURCE-PROVIDED, native fields verbatim (not remapped)
    provenance: dict              # DERIVED

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)
