"""Phase 3.3-E -- deterministic pilot task sampling.

Documents and implements the sampling procedure for the 3.3-E controlled pilot campaign.
Reads ONLY the existing, frozen Phase 3.2 processed files
(`data/processed/<dataset>/{memory_records,task_records}.jsonl`) -- never modifies them,
never fabricates a record.

WHY ONLY LOCOMO AND LONGMEMEVAL
--------------------------------------------------------------------------------
Directly verified in this stage: `data/processed/msc/task_records.jsonl` and
`data/processed/conversation_chronicles/task_records.jsonl` are both EMPTY (0 lines).
This matches `DATASET_CAPABILITY_MATRIX.md`'s existing, Phase-3.2-established
characterization of MSC and Conversation Chronicles as "lifecycle/provenance/reuse/
longitudinal validation only -- not forced into strict-TSR/QA framework without a future
task layer" -- there is no gold-answer/gold-evidence QA task structure to run the
Condition A/B/C answer-correctness comparison against for these two datasets at all. This
is not a new gap this stage introduces or a bug to fix; building a new task layer for
these datasets is out of scope for a pilot stage and is not attempted here. The 3.3-E
pilot therefore covers LoCoMo and LongMemEval only, honestly, rather than fabricating a
task layer or silently dropping the two datasets without explanation.

LONGMEMEVAL HAYSTACK SIZE
--------------------------------------------------------------------------------
Directly measured: every LongMemEval task's real ingestion "haystack" (all memory
records sharing its `source_record_id`) is large -- the SMALLEST haystack across all
1000 LongMemEval tasks with a non-null answer and non-empty evidence is 216 records (this
is a long-context stress-test dataset by design). Combined with A-MEM's measured
per-item ingestion cost (~3.9s/item at pilot scale, per 3.3-D's 69.93s/18-item finding,
dominated by its real per-item evolution-decision attempt against an unreachable Ollama
server), ingesting even the smallest LongMemEval haystack into A-MEM would cost roughly
216 * 3.9s =~ 14 minutes for that ONE task alone. This is not "computationally
manageable" for a pilot stage (per the mission's explicit instruction), so LongMemEval is
scoped to Conditions A/B (no-memory, Mem0) only in this pilot -- Condition C (A-MEM) is
explicitly marked SCOPE_EXCLUDED_RESOURCE_COST for LongMemEval, not silently skipped
without explanation, and not run in a way that would misleadingly suggest A-MEM "failed"
on it.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import List, Mapping, Optional, Sequence

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DATA_ROOT = _REPO_ROOT / "data" / "processed"

SAMPLING_SEED = 33005  # fixed, documented -- "3.3-E" read as digits, arbitrary but fixed
# and disclosed so the sample is independently reproducible from this file alone.

CONDITION_EXCLUDED_RESOURCE_COST = "SCOPE_EXCLUDED_RESOURCE_COST"


@dataclass(frozen=True)
class PilotTask:
    dataset: str
    task_id: str
    question: str
    answer: Optional[str]
    evidence_memory_ids: Sequence[str]
    ingest_key_field: str  # which memory-record field selects this task's ingestion pool
    ingest_key_value: str
    pool_size: int
    conditions_to_run: Sequence[str]  # e.g. ("A", "B", "C") or ("A", "B")


def _load_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


def _locomo_pool_sizes() -> Mapping[str, int]:
    sizes: dict = {}
    for row in _load_jsonl(_DATA_ROOT / "locomo" / "memory_records.jsonl"):
        key = (row["conversation_id"], row["session_id"])
        sizes[key] = sizes.get(key, 0) + 1
    return sizes


def sample_locomo_tasks(n: int = 3) -> List[PilotTask]:
    """Deterministic sample: eligible = non-null answer, non-empty evidence_memory_ids,
    ALL evidence ids resolvable within a single (conversation_id, session_id) pool of
    size <= 25 (keeps ingestion tractable for both foundations; LoCoMo sessions range
    10-47 records, median 20, per this stage's own direct measurement). The FIRST
    eligible task (by task_id sort order) is always included for continuity with the
    3.3-B/C/D LoCoMo pilot record (conv-26/session_1/ecf5a096af5598393ce49c80); the
    remaining `n - 1` are chosen via `random.Random(SAMPLING_SEED).sample()` over the
    rest of the eligible pool -- not hand-picked for favorable results.
    """
    pool_sizes = _locomo_pool_sizes()
    memory_by_id = {}
    memory_session = {}
    for row in _load_jsonl(_DATA_ROOT / "locomo" / "memory_records.jsonl"):
        memory_by_id[row["memory_id"]] = row
        memory_session[row["memory_id"]] = (row["conversation_id"], row["session_id"])

    eligible = []
    for t in _load_jsonl(_DATA_ROOT / "locomo" / "task_records.jsonl"):
        if t.get("answer") is None or not t.get("evidence_memory_ids"):
            continue
        sessions = {memory_session.get(eid) for eid in t["evidence_memory_ids"]}
        if len(sessions) != 1 or None in sessions:
            continue  # evidence spans multiple sessions or an unresolvable id -- skip
        (conv_id, session_id) = next(iter(sessions))
        size = pool_sizes.get((conv_id, session_id), 0)
        if size == 0 or size > 25:
            continue
        eligible.append((t, conv_id, session_id, size))

    eligible.sort(key=lambda row: row[0]["task_id"])
    if not eligible:
        return []

    continuity_task = next(
        (row for row in eligible if row[0]["task_id"] == "ecf5a096af5598393ce49c80"), eligible[0]
    )
    remaining_pool = [row for row in eligible if row is not continuity_task]
    rng = random.Random(SAMPLING_SEED)
    extra = rng.sample(remaining_pool, k=min(n - 1, len(remaining_pool))) if n > 1 else []

    chosen = [continuity_task] + extra
    tasks = []
    for t, conv_id, session_id, size in chosen:
        tasks.append(
            PilotTask(
                dataset="locomo",
                task_id=t["task_id"],
                question=t["question"],
                answer=str(t["answer"]),
                evidence_memory_ids=tuple(t["evidence_memory_ids"]),
                ingest_key_field="session",
                ingest_key_value=f"{conv_id}/{session_id}",
                pool_size=size,
                conditions_to_run=("A", "B", "C"),
            )
        )
    return tasks


def sample_longmemeval_tasks(n: int = 2) -> List[PilotTask]:
    """Deterministic sample: eligible = non-null answer, non-empty evidence_memory_ids.
    Ranked by ASCENDING haystack pool size (smallest ingestion cost first -- a
    resource-aware, not outcome-aware, ordering criterion) and the first `n` distinct
    haystacks taken. Tie-breaking within equal pool size is by task_id sort order
    (deterministic, not random -- there is no meaningful randomness to add once the
    resource-based primary sort is applied)."""
    pool_sizes: dict = {}
    for row in _load_jsonl(_DATA_ROOT / "longmemeval" / "memory_records.jsonl"):
        pool_sizes[row["source_record_id"]] = pool_sizes.get(row["source_record_id"], 0) + 1

    eligible = []
    for t in _load_jsonl(_DATA_ROOT / "longmemeval" / "task_records.jsonl"):
        if t.get("answer") is None or not t.get("evidence_memory_ids"):
            continue
        haystack = t["source_record_id"]
        size = pool_sizes.get(haystack, 0)
        if size == 0:
            continue
        eligible.append((size, t["task_id"], t, haystack))

    eligible.sort()
    seen_haystacks = set()
    tasks = []
    for size, task_id, t, haystack in eligible:
        if haystack in seen_haystacks:
            continue
        seen_haystacks.add(haystack)
        tasks.append(
            PilotTask(
                dataset="longmemeval",
                task_id=t["task_id"],
                question=t["question"],
                answer=str(t["answer"]),
                evidence_memory_ids=tuple(t["evidence_memory_ids"]),
                ingest_key_field="source_record_id",
                ingest_key_value=haystack,
                pool_size=size,
                conditions_to_run=("A", "B"),  # C (A-MEM) SCOPE_EXCLUDED_RESOURCE_COST
            )
        )
        if len(tasks) >= n:
            break
    return tasks


def build_pilot_sample() -> List[PilotTask]:
    return sample_locomo_tasks(3) + sample_longmemeval_tasks(2)


# ---------------------------------------------------------------------------
# Phase 3.3-F -- final campaign sampling protocol extensions
# ---------------------------------------------------------------------------
#
# HAYSTACK-SHARING (Issue 2, Option D from the 3.3-F mission): when multiple eligible
# LongMemEval tasks share the same `source_record_id` haystack, a single RESET+INGEST of
# that haystack can validly serve ALL of them, because retrieval/generation/evaluation
# are READ-ONLY foundation operations (verified by inspecting `runner.py`'s
# `_retrieve_and_select`: it calls only `foundation.retrieve()`/`inspect_memory()`, never
# `add_memory()`) -- no task's RETRIEVE/GENERATE/EVALUATE step can mutate the shared
# store, so task independence is preserved even though ingestion cost is amortized across
# every task sharing that haystack. This does NOT apply across DIFFERENT haystacks (each
# still gets its own fresh RESET) and does NOT apply to LoCoMo's smaller per-session pools
# (not needed there -- ingestion is already cheap).


def eligible_longmemeval_tasks_grouped_by_haystack() -> Mapping[str, List[Mapping[str, object]]]:
    """Group EVERY eligible LongMemEval task_record (non-null answer, non-empty
    evidence_memory_ids) by its `source_record_id` haystack -- unlike
    `sample_longmemeval_tasks()` (which deliberately keeps only one task per haystack
    for pilot-scale cost control), this returns ALL tasks per haystack, so a formal
    campaign can amortize one ingestion across every task that shares it. Read-only over
    the real, unmodified `data/processed/longmemeval/` files.
    """
    pool_sizes: dict = {}
    for row in _load_jsonl(_DATA_ROOT / "longmemeval" / "memory_records.jsonl"):
        pool_sizes[row["source_record_id"]] = pool_sizes.get(row["source_record_id"], 0) + 1

    groups: dict = {}
    for t in _load_jsonl(_DATA_ROOT / "longmemeval" / "task_records.jsonl"):
        if t.get("answer") is None or not t.get("evidence_memory_ids"):
            continue
        haystack = t["source_record_id"]
        if pool_sizes.get(haystack, 0) == 0:
            continue
        groups.setdefault(haystack, []).append(
            {"task_id": t["task_id"], "question": t["question"], "answer": str(t["answer"]),
             "evidence_memory_ids": tuple(t["evidence_memory_ids"]), "pool_size": pool_sizes[haystack]}
        )
    return groups


# ---------------------------------------------------------------------------
# Phase 3.3-G -- formal N=120-per-dataset campaign sampling
# ---------------------------------------------------------------------------
#
# Reuses the SAME eligibility rules and SAME sampling seed (33005) established in
# 3.3-E/3.3-F -- this is a scale-up of the existing, already-frozen methodology, not a
# new one invented for this stage. Nothing here was chosen after observing any result.

FORMAL_N_PER_DATASET = 120


def sample_locomo_tasks_formal(n: int = FORMAL_N_PER_DATASET) -> List[PilotTask]:
    """Formal-campaign LoCoMo sample: identical eligibility rule and seed as
    `sample_locomo_tasks()` (single-session evidence, pool size <= 25, continuity task
    always included, remainder via `random.Random(SAMPLING_SEED).sample()`), simply
    requested at n=120 instead of the pilot's n=3. The population check
    (`sample_locomo_tasks(200)` returning exactly 200 during this stage's own freeze
    verification) confirms >=120 eligible tasks exist without loosening the pool-size
    bound.
    """
    return sample_locomo_tasks(n)


def sample_longmemeval_tasks_formal(
    n_tasks: int = FORMAL_N_PER_DATASET,
) -> List[PilotTask]:
    """Formal-campaign LongMemEval sample: HAYSTACK-level sampling (n_tasks // 2
    haystacks, both of that haystack's exactly-2 eligible tasks each) rather than
    3.3-E's one-task-per-haystack pilot sampling -- this maximizes the A-MEM
    haystack-sharing benefit the mission's own Issue-2 resolution (3.3-F) and this
    stage's explicit instructions call for: "may use ONE A-MEM INGESTION PER HAYSTACK
    when both sampled tasks belonging to that haystack are evaluated." Verified
    directly (3.3-F, re-confirmed this stage): every one of LongMemEval's 500 eligible
    haystacks has EXACTLY 2 eligible tasks, so `n_tasks // 2` haystacks yields exactly
    `n_tasks` tasks with the theoretical MINIMUM possible unique-haystack count
    (n_tasks // 2) -- not a coincidence, a deliberate resource-aware sampling choice
    made BEFORE any result was observed. Same disclosed seed (`SAMPLING_SEED`) as every
    other sampling function in this module.

    Raises ValueError if `n_tasks` is odd (every haystack contributes exactly 2 tasks;
    an odd n_tasks would require taking a partial haystack, breaking the
    both-tasks-per-haystack sharing guarantee) or if `n_tasks // 2` exceeds the number
    of eligible haystacks (500).
    """
    if n_tasks % 2 != 0:
        raise ValueError(
            f"n_tasks={n_tasks} must be even -- every LongMemEval haystack contributes "
            "exactly 2 eligible tasks; an odd n_tasks would break the "
            "both-tasks-per-haystack sharing guarantee."
        )
    groups = eligible_longmemeval_tasks_grouped_by_haystack()
    n_haystacks_needed = n_tasks // 2
    if n_haystacks_needed > len(groups):
        raise ValueError(
            f"Requested {n_haystacks_needed} haystacks but only {len(groups)} eligible "
            "haystacks exist."
        )

    haystack_ids = sorted(groups.keys())  # deterministic base order before seeded draw
    rng = random.Random(SAMPLING_SEED)
    chosen_haystacks = rng.sample(haystack_ids, k=n_haystacks_needed)

    tasks: List[PilotTask] = []
    for haystack in sorted(chosen_haystacks):  # deterministic emission order
        for t in sorted(groups[haystack], key=lambda row: row["task_id"]):
            tasks.append(
                PilotTask(
                    dataset="longmemeval",
                    task_id=t["task_id"],
                    question=t["question"],
                    answer=t["answer"],
                    evidence_memory_ids=t["evidence_memory_ids"],
                    ingest_key_field="source_record_id",
                    ingest_key_value=haystack,
                    pool_size=t["pool_size"],
                    conditions_to_run=("A", "B", "C"),  # formal campaign: all three,
                    # unlike the pilot's A/B-only LongMemEval scope -- haystack sharing
                    # is exactly what makes C tractable enough to attempt here.
                )
            )
    return tasks


def build_formal_sample(n_per_dataset: int = FORMAL_N_PER_DATASET) -> Mapping[str, List[PilotTask]]:
    """The complete frozen formal-campaign sample: {dataset: [PilotTask, ...]}. Must be
    generated and recorded BEFORE any formal execution begins, per the mission's
    explicit freeze-before-execution requirement -- this function itself performs no
    execution, no LLM calls, no foundation calls; it is pure, deterministic, read-only
    sampling.
    """
    return {
        "locomo": sample_locomo_tasks_formal(n_per_dataset),
        "longmemeval": sample_longmemeval_tasks_formal(n_per_dataset),
    }


if __name__ == "__main__":
    for task in build_pilot_sample():
        print(task)
