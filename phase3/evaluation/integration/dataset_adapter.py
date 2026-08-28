"""Phase 3.2-H — read-only dataset adapters.

Turns a dataset_id + a raw record (shaped like an actual `memory_records.jsonl`/
`task_records.jsonl` line, or a synthetic equivalent for testing) + the corresponding
`phase3/evaluation/datasets/profiles/<id>.json` profile into:

(a) an `EvaluatorReference`-shaped dict -- populated only from what the profile says is
    available; a field the profile marks PARTIAL/UNAVAILABLE for this dataset is carried
    through FAITHFULLY from the record (including `None`/empty), never invented.
(b) an `AgentVisibleContext`-shaped dict -- task/observations/memory content only,
    assembled via `phase3.evaluation.agent.conditions.build_agent_visible_context`
    (reused verbatim, not reimplemented), which itself runs the payload through
    `phase3.evaluation.contracts.boundary.validate_agent_visible()` before returning.

Nothing here invents ground truth, retrieves real dataset files, or performs any I/O
beyond what the caller already loaded into memory. `phase3.evaluation.datasets.capability
.load_profile` is the caller's job (or the test fixture's), not this module's.

RESOLVED CONTRACT GAP (3.2-H remediation -- see README.md "Contract inconsistency
resolved"): `evaluator_reference.schema.json`'s `gold_answer` field previously required
`type: "string"` with no `null` option, which could not represent LoCoMo's real
question_type "5" records (`answer_availability: PARTIAL`, null answer). The schema now
declares `gold_answer` as `type: ["string", "null"]` -- the REQUIRED KEY is unchanged
(omitting it entirely is still a schema violation), only its VALUE may legitimately be
`null`. This module's `EvaluatorReference`-shaped dict carries `gold_answer: None`
verbatim for such a record, and `pipeline.py` now schema-validates the resulting
EvaluatorReference-shaped subset (excluding this module's own bookkeeping keys
`applicable`/`dataset_id`, which are not part of the frozen schema) alongside
`AgentVisibleContext`, `trace_artifact`, and `evaluation_result`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence, Tuple

from phase3.evaluation.agent.conditions import (
    ALL_CONDITIONS,
    CONDITION_GOLD_EVIDENCE,
    CONDITION_NO_MEMORY,
    CONDITION_RETRIEVED_MEMORY,
    build_agent_visible_context,
)
from phase3.evaluation.datasets import capability as cap

from . import validation as val

# ---------------------------------------------------------------------------
# EvaluatorReference-shaped construction
# ---------------------------------------------------------------------------


def build_evaluator_reference(
    dataset_id: str,
    record: Mapping[str, Any],
    profile: Mapping[str, Any],
    task_id: str,
) -> dict:
    """Build an `EvaluatorReference`-shaped dict for one task record.

    If the profile says this dataset has no task layer at all
    (`workload_availability.explicit_task_records` not AVAILABLE/PARTIAL), returns an
    explicit `{"applicable": False, "reason": ...}` marker -- this function REFUSES to
    construct a task-evaluation case for such a dataset, per the 3.2-H task brief's
    instruction that MSC/Conversation Chronicles must never get a null-filled fake case.

    Otherwise returns `{"applicable": True, "task_id", "gold_answer", "gold_evidence_ids",
    ...}`, where `gold_answer`/`gold_evidence_ids` are read VERBATIM from `record` --
    `record.get("answer")` may legitimately be `None` (faithfully propagated, never
    coerced to a placeholder string) and `record.get("evidence_memory_ids")` may
    legitimately be `[]` (also faithfully propagated).
    """
    task_ok, reason = val.task_layer_gate(profile)
    if not task_ok:
        return {"applicable": False, "reason": reason, "task_id": task_id, "dataset_id": dataset_id}

    gold_answer = record.get("answer")
    gold_evidence_ids = record.get("evidence_memory_ids")
    if gold_evidence_ids is None:
        gold_evidence_ids = []

    return {
        "applicable": True,
        "schema_version": "3.2-b.1",
        "dataset_id": dataset_id,
        "task_id": task_id,
        "gold_answer": gold_answer,
        "gold_evidence_ids": list(gold_evidence_ids),
    }


# ---------------------------------------------------------------------------
# AgentVisibleContext-shaped construction
# ---------------------------------------------------------------------------


def build_agent_visible_context_for_case(
    task_id: str,
    prompt: str,
    condition: str,
    memory_records: Mapping[str, Mapping[str, Any]],
    selected_memory_ids: Sequence[str] = (),
    gold_evidence_ids: Sequence[str] = (),
) -> Mapping[str, Any]:
    """Assemble an `AgentVisibleContext`-shaped payload for one case, reusing
    `agent.conditions.build_agent_visible_context()` verbatim (which itself runs
    `boundary.validate_agent_visible()`).

    Parameters
    ----------
    memory_records:
        `memory_id -> {"content": ..., ...}` mapping -- the full known memory set for this
        case (used to look up content by id; never itself put into the payload wholesale).
    selected_memory_ids:
        Used for `CONDITION_RETRIEVED_MEMORY` (and the provisional
        `SELECTED_MEMORY_AVAILABLE`/`DERIVED_MEMORY_AVAILABLE`/
        `CONFLICTING_MEMORY_AVAILABLE` conditions): the agent's own opaque handle on the ids
        it was handed is not a leakage risk (per agent_visible_context.schema.json's
        `memory_content[].memory_id` description) -- what must never leak is the
        benchmark's GOLD labelling, not the agent's own id.
    gold_evidence_ids:
        Used ONLY for `CONDITION_GOLD_EVIDENCE`: content is looked up by these ids, but
        each item is re-keyed under an OPAQUE per-slot id (`"evidence-slot-{n}"`), never the
        literal benchmark gold_evidence_id string -- mirrors the 3.2-B `gold_evidence/`
        fixture's explicit design choice (see phase3/evaluation/README.md).

    Raises
    ------
    ValueError
        If `condition` is not one of `ALL_CONDITIONS`.
    """
    if condition not in ALL_CONDITIONS:
        raise ValueError(f"condition {condition!r} is not one of {ALL_CONDITIONS!r}")

    memory_items = []
    if condition == CONDITION_GOLD_EVIDENCE:
        for idx, gid in enumerate(gold_evidence_ids):
            content = memory_records.get(gid, {}).get("content")
            if content is not None:
                memory_items.append({"memory_id": f"evidence-slot-{idx + 1}", "content": content})
    elif condition != CONDITION_NO_MEMORY:
        for mid in selected_memory_ids:
            content = memory_records.get(mid, {}).get("content")
            if content is not None:
                memory_items.append({"memory_id": mid, "content": content})

    return build_agent_visible_context(
        condition=condition,
        task_id=task_id,
        prompt=prompt,
        memory_items=memory_items,
    )


# ---------------------------------------------------------------------------
# Evaluation case assembly (dataset+record -> everything pipeline.py needs)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EvaluationCase:
    """Everything `pipeline.py::evaluate_case()` needs for one integrated evaluation.

    `task_applicable=False` means the profile ruled out a task/gold basis entirely for
    this dataset (MSC/Conversation Chronicles) -- `evaluator_reference["applicable"]` will
    also be False in that case, and `agent_visible_context`/`gold_evidence_ids`/
    `expected_answer` are not meaningful. Memory-only metrics (SELECTION_COUNT, REDUNDANCY,
    PROVENANCE_VALIDATION, LINEAGE_DIAGNOSTICS, EQUIVALENCE_DIAGNOSTICS) remain attemptable
    via `memories`/`selected_memory_ids` regardless.
    """

    dataset_id: str
    case_id: str
    condition: str
    task_applicable: bool
    task_not_applicable_reason: str
    agent_visible_context: Optional[Mapping[str, Any]]
    evaluator_reference: Mapping[str, Any]
    memories: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    retrieved_memory_ids: Tuple[str, ...] = ()
    selected_memory_ids: Tuple[str, ...] = ()
    used_memory_ids: Optional[Tuple[str, ...]] = None


def build_evaluation_case(
    dataset_id: str,
    profile: Mapping[str, Any],
    task_id: str,
    prompt: str,
    condition: str,
    record: Mapping[str, Any],
    memories: Mapping[str, Mapping[str, Any]] = None,
    retrieved_memory_ids: Sequence[str] = (),
    selected_memory_ids: Sequence[str] = (),
    used_memory_ids: Optional[Sequence[str]] = None,
) -> EvaluationCase:
    """Assemble one `EvaluationCase` from a dataset_id + profile + a task record + a
    synthetic memory/retrieval/selection picture.

    If the profile rules out a task layer for this dataset entirely (MSC/Conversation
    Chronicles), `agent_visible_context` is left `None` and `task_applicable=False` --
    this function does NOT attempt to build a NO_MEMORY/GOLD_EVIDENCE/RETRIEVED_MEMORY
    context for a task that does not exist, per the 3.2-H task brief.
    """
    memories = dict(memories or {})
    evaluator_reference = build_evaluator_reference(dataset_id, record, profile, task_id)
    task_applicable = evaluator_reference["applicable"]
    reason = "" if task_applicable else evaluator_reference["reason"]

    agent_visible_context = None
    if task_applicable:
        agent_visible_context = build_agent_visible_context_for_case(
            task_id=task_id,
            prompt=prompt,
            condition=condition,
            memory_records=memories,
            selected_memory_ids=selected_memory_ids,
            gold_evidence_ids=evaluator_reference.get("gold_evidence_ids", []),
        )

    return EvaluationCase(
        dataset_id=dataset_id,
        case_id=task_id,
        condition=condition,
        task_applicable=task_applicable,
        task_not_applicable_reason=reason,
        agent_visible_context=agent_visible_context,
        evaluator_reference=evaluator_reference,
        memories=memories,
        retrieved_memory_ids=tuple(retrieved_memory_ids),
        selected_memory_ids=tuple(selected_memory_ids),
        used_memory_ids=tuple(used_memory_ids) if used_memory_ids is not None else None,
    )
