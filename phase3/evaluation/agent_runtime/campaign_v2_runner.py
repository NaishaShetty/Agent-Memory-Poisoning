"""Phase 3.3-V2 -- the real, production-pipeline campaign runner for the V2
clean-agent candidate, wired through the actual canonical ledger infrastructure
(not an isolated research script). Produces a SEPARATE dataset artifact from V1's
frozen `canonical_store/dataset_full/clean_agent_dataset_locomo_120x2.json` -- that
file is never read for writing, never modified, never overwritten.

V2 CONFIGURATION (per the frozen research record -- not redesigned here):
- Condition A (no-memory): UNCHANGED. Reuses `campaign_formal_runner.run_condition_a()`
  verbatim -- zero new code, zero behavior difference from V1.
- Condition B (gold evidence): reuses `gold_evidence_runner.run_gold_evidence_task()`
  verbatim. The ONLY difference from V1 is what CONTENT this module builds and passes
  in as evidence text -- V1 passed `"{role}: {content}"`; V2 prepends the real
  `source_timestamp` when present: `"[{source_timestamp}] {role}: {content}"`. This is
  the validated Round 8 configuration.
- Condition C (retrieved memory), BOTH foundations: reuses
  `hybrid_selection_runner.run_agent_task_with_hybrid_selection()` (pool=20, hybrid
  rerank, top-8, fixed weights 0.5/0.3/0.2) -- the validated Round 7/11 configuration.
  Ingested content does NOT include a timestamp prefix for either foundation (Round 11:
  timestamp injection measured net-negative for Condition C specifically).

Canonical ledger wiring reuses `canonical_wiring.py` exactly as
`campaign_selection_policy_runner.py` already does for a different (threshold-based)
selection mechanism -- only the `retrieved_reason`/`selected_reason` labels are
overridden (an additive, backward-compatible parameter added to `canonical_wiring.py`
for this purpose) so the ledger accurately describes V2's real mechanism instead of
inheriting V1's "provisional top_k slice" description.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from phase3.evaluation.agent.conditions import CONDITION_GOLD_EVIDENCE, CONDITION_RETRIEVED_MEMORY
from phase3.evaluation.agent_runtime.campaign_formal_runner import (
    DATASET_REVISION, OUTPUT_DIR, _gpu_vram_mib, _group_by_pool, run_condition_a,
)
from phase3.evaluation.agent_runtime.campaign_runner import _ingest_pool
from phase3.evaluation.agent_runtime.gold_evidence_runner import GoldEvidenceTaskInput, run_gold_evidence_task
from phase3.evaluation.agent_runtime.hybrid_selection_runner import run_agent_task_with_hybrid_selection
from phase3.evaluation.agent_runtime.runner import AgentTaskInput, RunConfiguration
from phase3.evaluation.agent_runtime.trace import evaluate_and_trace, evaluate_and_trace_with_identity
from phase3.evaluation.foundations.adapter import FOUNDATION_AVAILABLE
from phase3.evaluation.foundations.hybrid_selection import DEFAULT_TOP_K, RETRIEVAL_POOL_SIZE_N
from phase3.evaluation.security import content_leakage as sec_content_leakage

V2_STORE = OUTPUT_DIR / "canonical_store" / "v2_candidate"

REASON_RETRIEVED_V2 = (
    "retrieved via foundation.retrieve() during Condition C V2 campaign execution "
    "(pool_size=20, hybrid_selection.select_by_hybrid_score())."
)
REASON_SELECTED_V2 = (
    "selected via foundations.hybrid_selection.select_by_hybrid_score() -- fixed-weight "
    "blend (cosine=0.5, token_overlap=0.3, entity_overlap=0.2) of pool=20 candidates, "
    "top_k=8, no hard score floor. Validated in phase3/experiments/research_variant/ "
    "Rounds 5/6/7/11; weights fixed before any of those rounds were run."
)


def _content_leakage_scan(outcome, task, condition_label):
    evaluator_reference_for_leakage_scan = {"gold_answer": task.answer, "gold_evidence_ids": list(task.evidence_memory_ids)}
    context_without_memory_content = {k: v for k, v in outcome.agent_visible_context.items() if k != "memory_content"}
    context_for_evidence_id_scan = dict(outcome.agent_visible_context)
    context_for_evidence_id_scan["memory_content"] = [
        {k: v for k, v in item.items() if k != "memory_id"}
        for item in (outcome.agent_visible_context.get("memory_content") or [])
    ]
    for result in (
        sec_content_leakage.scan_for_gold_content(context_without_memory_content, evaluator_reference_for_leakage_scan, fields=("gold_answer",)),
        sec_content_leakage.scan_for_gold_content(context_for_evidence_id_scan, evaluator_reference_for_leakage_scan, fields=("gold_evidence_ids",)),
    ):
        if result.status == sec_content_leakage.STATUS_CONTENT_LEAKAGE_DETECTED:
            raise sec_content_leakage.ContentLeakageDetectedError(f"task {task.task_id!r} ({condition_label}): {result.summary}")


def _load_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


_DATA_ROOT = Path(__file__).resolve().parents[3] / "data" / "processed"


def run_condition_b_v2_timestamped(all_tasks, llm_provider, generation_config, campaign_id):
    """V2 Condition B: gold evidence WITH timestamp injection. Foundation-independent
    (no foundation call at all, per `gold_evidence_runner.py`'s own module docstring)
    -- run exactly once, not once per foundation."""
    memory_rows_by_id = {row["memory_id"]: row for row in _load_jsonl(_DATA_ROOT / "locomo" / "memory_records.jsonl")}
    results = []
    for task in all_tasks:
        t0 = time.time()
        try:
            evidence_items = []
            for eid in task.evidence_memory_ids:
                row = memory_rows_by_id.get(eid)
                if row is None:
                    continue
                content_text = (
                    f"[{row['source_timestamp']}] {row['source_role']}: {row['content']}"
                    if row.get("source_timestamp") else f"{row['source_role']}: {row['content']}"
                )
                evidence_items.append({"gold_evidence_id": eid, "content": content_text})

            outcome = run_gold_evidence_task(
                GoldEvidenceTaskInput(task_id=task.task_id, prompt=task.question, evidence_items=evidence_items),
                config=RunConfiguration(llm_provider=llm_provider, generation_config=generation_config),
            )
            latency = time.time() - t0
            _content_leakage_scan(outcome, task, "V2-B-GoldEvidence-Timestamped")

            trace = evaluate_and_trace(
                outcome, experiment_id=f"{campaign_id}-{task.dataset}-{task.task_id}-V2-B",
                dataset=task.dataset, dataset_revision=DATASET_REVISION, record_id=task.task_id,
                expected_answer=task.answer, gold_evidence_ids=task.evidence_memory_ids,
            )
            results.append({
                "task_id": task.task_id, "dataset": task.dataset, "status": "SUCCESSFUL_EVALUATION",
                "trace": trace, "latency_sec": latency, "vram_mib": _gpu_vram_mib(),
                "timestamp_injected_count": sum(1 for i in evidence_items if i["content"].startswith("[")),
            })
        except Exception as exc:
            results.append({"task_id": task.task_id, "dataset": task.dataset, "status": "EXECUTION_FAILURE", "error": repr(exc), "latency_sec": time.time() - t0})
    return results


def run_condition_c_v2_mem0(all_tasks, llm_provider, generation_config, campaign_id, checkpoint_path=None):
    from phase3.evaluation.foundations_real.mem0_real_adapter import RealMem0Adapter
    from phase3.evaluation.agent_runtime.canonical_wiring import (
        open_pool_canonical_ledgers, record_retrieval_and_selection_events, write_ingested_canonical_memory,
    )
    from phase3.evaluation.foundations.canonical_write import STATUS_CANONICAL_AND_FOUNDATION

    EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
    groups = _group_by_pool(all_tasks)
    results = []
    completed_task_ids = set()
    if checkpoint_path and Path(checkpoint_path).exists():
        with open(checkpoint_path, "r", encoding="utf-8") as f:
            results = json.load(f)
        completed_task_ids = {r["task_id"] for r in results}
        print(f"  Resuming V2 Mem0: {len(completed_task_ids)} tasks already done.", flush=True)

    def _save():
        if checkpoint_path:
            with open(checkpoint_path, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False, default=str)

    for (dataset, pool_key), tasks_in_pool in sorted(groups.items()):
        if all(t.task_id in completed_task_ids for t in tasks_in_pool):
            continue
        foundation = RealMem0Adapter()
        collection_name = "v2_" + hashlib.sha256(f"{dataset}:{pool_key}".encode()).hexdigest()[:16]
        init_field = foundation.initialize({"embedding_model": EMBEDDING_MODEL, "collection_name": collection_name})
        if init_field.availability != FOUNDATION_AVAILABLE:
            for task in tasks_in_pool:
                results.append({"task_id": task.task_id, "dataset": dataset, "status": "ENVIRONMENT_FAILURE", "error": "initialize() failed"})
            continue
        if foundation.reset().availability != FOUNDATION_AVAILABLE:
            for task in tasks_in_pool:
                results.append({"task_id": task.task_id, "dataset": dataset, "status": "ENVIRONMENT_FAILURE", "error": "reset() failed"})
            continue

        pool_ledgers = open_pool_canonical_ledgers(
            OUTPUT_DIR, campaign_id, dataset, collection_name,
            adapter_revision=foundation.foundation_identity().adapter_version,
            retrieval_k=RETRIEVAL_POOL_SIZE_N, embedding_model=EMBEDDING_MODEL,
        )

        ingested_ids = []
        for row in _ingest_pool(dataset, tasks_in_pool[0].ingest_key_field, pool_key):
            # V2 Condition C: NO timestamp prefix (Round 11 finding -- net negative here)
            wr = write_ingested_canonical_memory(
                pool_ledgers.memory_ledger, foundation, source_id=row["memory_id"],
                content={"text": f"{row['source_role']}: {row['content']}"},
                metadata_extra={"user_id": f"v2-{dataset}-{pool_key}", "source_memory_id": row["memory_id"]},
                ingestion_label=f"v2-ingest-{campaign_id}-{dataset}-{pool_key}",
            )
            if wr.status == STATUS_CANONICAL_AND_FOUNDATION:
                ingested_ids.append(row["memory_id"])

        for task in tasks_in_pool:
            if task.task_id in completed_task_ids:
                continue
            t0 = time.time()
            try:
                outcome, rejected_ids, selection_result = run_agent_task_with_hybrid_selection(
                    AgentTaskInput(
                        task_id=task.task_id, prompt=task.question, condition=CONDITION_RETRIEVED_MEMORY,
                        retrieval_query={"text": task.question, "user_id": f"v2-{dataset}-{pool_key}"},
                    ),
                    foundation=foundation,
                    config=RunConfiguration(llm_provider=llm_provider, generation_config=generation_config),
                    top_k=DEFAULT_TOP_K,
                )
                run_latency = time.time() - t0
                _content_leakage_scan(outcome, task, "V2-C-Mem0-Hybrid")

                trace = evaluate_and_trace_with_identity(
                    outcome, foundation, experiment_id=f"{campaign_id}-{dataset}-{task.task_id}-V2-C-MEM0",
                    dataset=dataset, dataset_revision=DATASET_REVISION, record_id=task.task_id,
                    expected_answer=task.answer, gold_evidence_ids=task.evidence_memory_ids,
                    ingested_source_memory_ids=ingested_ids,
                )
                try:
                    canonical_event_report = dataclasses.asdict(record_retrieval_and_selection_events(
                        pool_ledgers.event_ledger, pool_ledgers.memory_ledger, foundation,
                        task_id=task.task_id, config_fingerprint=pool_ledgers.config_fingerprint,
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        retrieved_foundation_ids=outcome.retrieved_memory_ids,
                        selected_foundation_ids=outcome.selected_memory_ids,
                        retrieved_reason=REASON_RETRIEVED_V2, selected_reason=REASON_SELECTED_V2,
                    ))
                except Exception as canonical_exc:
                    canonical_event_report = {"CANONICAL_EVENT_WIRING_ERROR": repr(canonical_exc)}

                results.append({
                    "task_id": task.task_id, "dataset": dataset, "status": "SUCCESSFUL_EVALUATION",
                    "trace": trace, "run_latency_sec": run_latency, "pool_key": pool_key,
                    "ingested_count": len(ingested_ids), "rejected_count": len(rejected_ids),
                    "top_k": DEFAULT_TOP_K, "vram_mib": _gpu_vram_mib(), "canonical_event_report": canonical_event_report,
                })
            except Exception as exc:
                results.append({"task_id": task.task_id, "dataset": dataset, "status": "EXECUTION_FAILURE", "error": repr(exc), "pool_key": pool_key})
        foundation.shutdown()
        _save()
        print(f"  [v2-checkpoint mem0] pool {pool_key} done ({len(results)}/{len(all_tasks)} tasks total)", flush=True)
    return results


def run_condition_c_v2_amem(all_tasks, llm_provider, generation_config, campaign_id, checkpoint_path=None):
    from phase3.evaluation.agent_runtime.identity import resolve_via_direct_assignment, STATUS_RESOLVED
    from phase3.evaluation.foundations_real.amem_real_adapter import RealAMemAdapter
    from phase3.evaluation.agent_runtime.canonical_wiring import (
        open_pool_canonical_ledgers, record_retrieval_and_selection_events_direct_assignment,
        write_canonical_record_and_alias_direct_assignment, RETRIEVAL_MECHANISM_AMEM_DENSE,
    )

    groups = _group_by_pool(all_tasks)
    results = []
    completed_task_ids = set()
    if checkpoint_path and Path(checkpoint_path).exists():
        with open(checkpoint_path, "r", encoding="utf-8") as f:
            results = json.load(f)
        completed_task_ids = {r["task_id"] for r in results}
        print(f"  Resuming V2 A-MEM: {len(completed_task_ids)} tasks already done.", flush=True)

    def _save():
        if checkpoint_path:
            with open(checkpoint_path, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False, default=str)

    for (dataset, pool_key), tasks_in_pool in sorted(groups.items()):
        if all(t.task_id in completed_task_ids for t in tasks_in_pool):
            continue
        foundation = RealAMemAdapter()
        if foundation.initialize({"embedding_model": "all-MiniLM-L6-v2"}).availability != FOUNDATION_AVAILABLE:
            for task in tasks_in_pool:
                results.append({"task_id": task.task_id, "dataset": dataset, "status": "ENVIRONMENT_FAILURE", "error": "initialize() failed"})
            continue
        if foundation.reset().availability != FOUNDATION_AVAILABLE:
            for task in tasks_in_pool:
                results.append({"task_id": task.task_id, "dataset": dataset, "status": "ENVIRONMENT_FAILURE", "error": "reset() failed"})
            continue

        collection_token = "v2_a_" + hashlib.sha256(f"{dataset}:{pool_key}".encode()).hexdigest()[:16]
        pool_ledgers = open_pool_canonical_ledgers(
            OUTPUT_DIR, campaign_id, dataset, collection_token,
            adapter_revision=foundation.foundation_identity().adapter_version,
            retrieval_k=RETRIEVAL_POOL_SIZE_N, embedding_model="all-MiniLM-L6-v2",
            retrieval_mechanism=RETRIEVAL_MECHANISM_AMEM_DENSE,
        )

        resolutions = {}
        for row in _ingest_pool(dataset, tasks_in_pool[0].ingest_key_field, pool_key):
            # V2 Condition C: NO timestamp prefix (same as Mem0 path above)
            add_field = foundation.add_memory(
                memory_id=row["memory_id"], content={"text": f"{row['source_role']}: {row['content']}"},
                metadata={"tags": ["v2", dataset], "keywords": [dataset], "context": pool_key},
            )
            if add_field.availability == FOUNDATION_AVAILABLE:
                resolution = resolve_via_direct_assignment(row["memory_id"], add_field.value)
                resolutions[resolution.foundation_memory_id] = resolution
                try:
                    write_canonical_record_and_alias_direct_assignment(
                        pool_ledgers.memory_ledger, source_id=row["memory_id"],
                        content={"text": f"{row['source_role']}: {row['content']}"},
                        ingestion_label=f"v2-ingest-{campaign_id}-{dataset}-{pool_key}",
                        foundation_memory_id=(resolution.foundation_memory_id if resolution.status == STATUS_RESOLVED else None),
                    )
                except Exception:
                    pass

        for task in tasks_in_pool:
            if task.task_id in completed_task_ids:
                continue
            t0 = time.time()
            try:
                outcome, rejected_ids, selection_result = run_agent_task_with_hybrid_selection(
                    AgentTaskInput(
                        task_id=task.task_id, prompt=task.question, condition=CONDITION_RETRIEVED_MEMORY,
                        retrieval_query={"text": task.question},
                    ),
                    foundation=foundation,
                    config=RunConfiguration(llm_provider=llm_provider, generation_config=generation_config),
                    top_k=DEFAULT_TOP_K,
                )
                run_latency = time.time() - t0
                _content_leakage_scan(outcome, task, "V2-C-AMEM-Hybrid")

                trace = evaluate_and_trace(
                    outcome, experiment_id=f"{campaign_id}-{dataset}-{task.task_id}-V2-C-AMEM",
                    dataset=dataset, dataset_revision=DATASET_REVISION, record_id=task.task_id,
                    expected_answer=task.answer, gold_evidence_ids=task.evidence_memory_ids,
                    store_memory_ids=list(resolutions.keys()),
                )
                try:
                    canonical_event_report = dataclasses.asdict(record_retrieval_and_selection_events_direct_assignment(
                        pool_ledgers.event_ledger, pool_ledgers.memory_ledger,
                        task_id=task.task_id, config_fingerprint=pool_ledgers.config_fingerprint,
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        retrieved_canonical_ids=outcome.retrieved_memory_ids,
                        selected_canonical_ids=outcome.selected_memory_ids,
                        retrieved_reason=REASON_RETRIEVED_V2, selected_reason=REASON_SELECTED_V2,
                    ))
                except Exception as canonical_exc:
                    canonical_event_report = {"CANONICAL_EVENT_WIRING_ERROR": repr(canonical_exc)}

                results.append({
                    "task_id": task.task_id, "dataset": dataset, "status": "SUCCESSFUL_EVALUATION",
                    "trace": trace, "run_latency_sec": run_latency, "pool_key": pool_key,
                    "ingested_count": len(resolutions), "rejected_count": len(rejected_ids),
                    "top_k": DEFAULT_TOP_K, "vram_mib": _gpu_vram_mib(), "canonical_event_report": canonical_event_report,
                })
            except Exception as exc:
                results.append({"task_id": task.task_id, "dataset": dataset, "status": "EXECUTION_FAILURE", "error": repr(exc), "pool_key": pool_key})
        foundation.shutdown()
        _save()
        print(f"  [v2-checkpoint amem] pool {pool_key} done ({len(results)}/{len(all_tasks)} tasks total)", flush=True)
    return results


__all__ = [
    "V2_STORE", "run_condition_a", "run_condition_b_v2_timestamped",
    "run_condition_c_v2_mem0", "run_condition_c_v2_amem",
]
