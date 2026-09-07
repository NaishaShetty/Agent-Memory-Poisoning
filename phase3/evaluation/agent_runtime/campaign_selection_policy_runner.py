"""Phase 3.3-DATASET (selection-policy variant) -- full real campaign execution
under the calibrated threshold-based selection policy (`selection_policy.py`),
per the user's explicit request to actually wire it in and re-run.

Produces a SEPARATE dataset variant. Reuses every existing piece it can
(`campaign_runner._ingest_pool`, `canonical_wiring`'s existing event-recording
functions -- which ALREADY correctly emit a `rejected` CanonicalEvent for any
retrieved-but-not-selected id, so no new canonical-wiring logic is needed here,
only a caller that finally supplies a `selected_ids` set that can be a genuine
subset of `retrieved_ids`), `evaluate_and_trace(_with_identity)`, and the same
content-leakage-scan discipline every other condition in `campaign_formal_runner.py`
uses. `campaign_formal_runner.py` itself is untouched.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from phase3.evaluation.agent.conditions import CONDITION_RETRIEVED_MEMORY
from phase3.evaluation.agent_runtime.campaign_formal_runner import (
    DATASET_REVISION, OUTPUT_DIR, _gpu_vram_mib, _group_by_pool,
)
from phase3.evaluation.agent_runtime.campaign_runner import _ingest_pool
from phase3.evaluation.agent_runtime.campaign_sampling import build_formal_sample
from phase3.evaluation.agent_runtime.runner import AgentTaskInput, RunConfiguration
from phase3.evaluation.agent_runtime.selection_policy_runner import run_agent_task_with_selection_policy
from phase3.evaluation.agent_runtime.trace import evaluate_and_trace, evaluate_and_trace_with_identity
from phase3.evaluation.foundations.adapter import FOUNDATION_AVAILABLE
from phase3.evaluation.foundations.selection_policy import CALIBRATED_THRESHOLD_LOCOMO, RETRIEVAL_POOL_SIZE_N
from phase3.evaluation.security import content_leakage as sec_content_leakage
from phase3.evaluation.llm.provider import (
    LlamaServerEndpoint, LlamaServerProvider, clean_baseline_generation_config,
)

VARIANT_STORE = OUTPUT_DIR / "canonical_store" / "selection_policy_variant"


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


def run_condition_c_mem0_selection_policy(all_tasks, llm_provider, generation_config, campaign_id, checkpoint_path=None):
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
        print(f"  Resuming Mem0 selection-policy: {len(completed_task_ids)} tasks already done.", flush=True)

    def _save():
        if checkpoint_path:
            with open(checkpoint_path, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False, default=str)

    for (dataset, pool_key), tasks_in_pool in sorted(groups.items()):
        if all(t.task_id in completed_task_ids for t in tasks_in_pool):
            continue
        foundation = RealMem0Adapter()
        collection_name = "sp_" + hashlib.sha256(f"{dataset}:{pool_key}".encode()).hexdigest()[:16]
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
            wr = write_ingested_canonical_memory(
                pool_ledgers.memory_ledger, foundation, source_id=row["memory_id"],
                content={"text": f"{row['source_role']}: {row['content']}"},
                metadata_extra={"user_id": f"sp-{dataset}-{pool_key}", "source_memory_id": row["memory_id"]},
                ingestion_label=f"selection-policy-ingest-{campaign_id}-{dataset}-{pool_key}",
            )
            if wr.status == STATUS_CANONICAL_AND_FOUNDATION:
                ingested_ids.append(row["memory_id"])

        for task in tasks_in_pool:
            if task.task_id in completed_task_ids:
                continue
            t0 = time.time()
            try:
                outcome, rejected_ids, selection_result = run_agent_task_with_selection_policy(
                    AgentTaskInput(
                        task_id=task.task_id, prompt=task.question, condition=CONDITION_RETRIEVED_MEMORY,
                        retrieval_query={"text": task.question, "user_id": f"sp-{dataset}-{pool_key}"},
                    ),
                    foundation=foundation,
                    config=RunConfiguration(llm_provider=llm_provider, generation_config=generation_config),
                    threshold=CALIBRATED_THRESHOLD_LOCOMO,
                )
                run_latency = time.time() - t0
                _content_leakage_scan(outcome, task, "Selection-Policy-Mem0")

                trace = evaluate_and_trace_with_identity(
                    outcome, foundation, experiment_id=f"{campaign_id}-{dataset}-{task.task_id}-SP-MEM0",
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
                    ))
                except Exception as canonical_exc:
                    canonical_event_report = {"CANONICAL_EVENT_WIRING_ERROR": repr(canonical_exc)}

                results.append({
                    "task_id": task.task_id, "dataset": dataset, "status": "SUCCESSFUL_EVALUATION",
                    "trace": trace, "run_latency_sec": run_latency, "pool_key": pool_key,
                    "ingested_count": len(ingested_ids), "rejected_count": len(rejected_ids),
                    "selection_threshold": CALIBRATED_THRESHOLD_LOCOMO,
                    "vram_mib": _gpu_vram_mib(), "canonical_event_report": canonical_event_report,
                })
            except Exception as exc:
                results.append({"task_id": task.task_id, "dataset": dataset, "status": "EXECUTION_FAILURE", "error": repr(exc), "pool_key": pool_key})
        foundation.shutdown()
        _save()
        print(f"  [sp-checkpoint mem0] pool {pool_key} done ({len(results)}/{len(all_tasks)} tasks total)", flush=True)
    return results


def run_condition_c_amem_selection_policy(all_tasks, llm_provider, generation_config, campaign_id, checkpoint_path=None):
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
        print(f"  Resuming A-MEM selection-policy: {len(completed_task_ids)} tasks already done.", flush=True)

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

        collection_token = "sp_a_" + hashlib.sha256(f"{dataset}:{pool_key}".encode()).hexdigest()[:16]
        pool_ledgers = open_pool_canonical_ledgers(
            OUTPUT_DIR, campaign_id, dataset, collection_token,
            adapter_revision=foundation.foundation_identity().adapter_version,
            retrieval_k=RETRIEVAL_POOL_SIZE_N, embedding_model="all-MiniLM-L6-v2",
            retrieval_mechanism=RETRIEVAL_MECHANISM_AMEM_DENSE,
        )

        resolutions = {}
        for row in _ingest_pool(dataset, tasks_in_pool[0].ingest_key_field, pool_key):
            add_field = foundation.add_memory(
                memory_id=row["memory_id"], content={"text": f"{row['source_role']}: {row['content']}"},
                metadata={"tags": ["selection_policy", dataset], "keywords": [dataset], "context": pool_key},
            )
            if add_field.availability == FOUNDATION_AVAILABLE:
                resolution = resolve_via_direct_assignment(row["memory_id"], add_field.value)
                resolutions[resolution.foundation_memory_id] = resolution
                try:
                    write_canonical_record_and_alias_direct_assignment(
                        pool_ledgers.memory_ledger, source_id=row["memory_id"],
                        content={"text": f"{row['source_role']}: {row['content']}"},
                        ingestion_label=f"selection-policy-ingest-{campaign_id}-{dataset}-{pool_key}",
                        foundation_memory_id=(resolution.foundation_memory_id if resolution.status == STATUS_RESOLVED else None),
                    )
                except Exception:
                    pass

        for task in tasks_in_pool:
            if task.task_id in completed_task_ids:
                continue
            t0 = time.time()
            try:
                outcome, rejected_ids, selection_result = run_agent_task_with_selection_policy(
                    AgentTaskInput(
                        task_id=task.task_id, prompt=task.question, condition=CONDITION_RETRIEVED_MEMORY,
                        retrieval_query={"text": task.question},
                    ),
                    foundation=foundation,
                    config=RunConfiguration(llm_provider=llm_provider, generation_config=generation_config),
                    threshold=CALIBRATED_THRESHOLD_LOCOMO,
                )
                run_latency = time.time() - t0
                _content_leakage_scan(outcome, task, "Selection-Policy-AMEM")

                trace = evaluate_and_trace(
                    outcome, experiment_id=f"{campaign_id}-{dataset}-{task.task_id}-SP-AMEM",
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
                    ))
                except Exception as canonical_exc:
                    canonical_event_report = {"CANONICAL_EVENT_WIRING_ERROR": repr(canonical_exc)}

                results.append({
                    "task_id": task.task_id, "dataset": dataset, "status": "SUCCESSFUL_EVALUATION",
                    "trace": trace, "run_latency_sec": run_latency, "pool_key": pool_key,
                    "ingested_count": len(resolutions), "rejected_count": len(rejected_ids),
                    "selection_threshold": CALIBRATED_THRESHOLD_LOCOMO,
                    "vram_mib": _gpu_vram_mib(), "canonical_event_report": canonical_event_report,
                })
            except Exception as exc:
                results.append({"task_id": task.task_id, "dataset": dataset, "status": "EXECUTION_FAILURE", "error": repr(exc), "pool_key": pool_key})
        foundation.shutdown()
        _save()
        print(f"  [sp-checkpoint amem] pool {pool_key} done ({len(results)}/{len(all_tasks)} tasks total)", flush=True)
    return results


__all__ = ["run_condition_c_mem0_selection_policy", "run_condition_c_amem_selection_policy", "VARIANT_STORE"]
