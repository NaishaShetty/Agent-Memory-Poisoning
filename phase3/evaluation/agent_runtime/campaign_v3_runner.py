"""Phase 3.3-V3 -- the real, production-pipeline campaign runner for the V3
candidate (V2 + deterministic relative-time resolution, validated in
PHASE3_V3_ROUND2/3_*.md at n=24 on both conditions with hand-verified real gains and
zero real regressions). Produces a SEPARATE dataset artifact from both V1's and V2's
frozen canonical stores -- neither is read for writing, neither is modified.

V3 = V2 EXACTLY, PLUS ONE ADDITIVE CHANGE
--------------------------------------------------------------------------------
- Condition A: unchanged from V2 (== unchanged from V1). Reuses
  `campaign_formal_runner.run_condition_a()` verbatim.
- Condition B: V2's timestamp-prefixed evidence content, PLUS
  `temporal_resolution.render_content_with_temporal_annotations()` applied on top.
- Condition C (both foundations): V2's validated hybrid selection (pool=20, top-8,
  fixed weights 0.5/0.3/0.2) -- UNCHANGED -- but each SELECTED item's content has
  `render_content_with_temporal_annotations()` applied using that item's real
  `source_timestamp` (looked up via the same `source_memory_id` metadata resolution
  V2 already performs, not a new identity mechanism) before rendering.

Canonical ledger wiring reuses `canonical_wiring.py` exactly as `campaign_v2_runner.py`
already does, with its own accurate reason-label constants (an additive parameter
already added to `canonical_wiring.py` for V2, reused here unmodified).
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Mapping, Tuple

from phase3.evaluation.agent.conditions import CONDITION_GOLD_EVIDENCE, CONDITION_RETRIEVED_MEMORY, build_agent_visible_context
from phase3.evaluation.agent_runtime.campaign_formal_runner import (
    DATASET_REVISION, OUTPUT_DIR, _gpu_vram_mib, _group_by_pool, run_condition_a,
)
from phase3.evaluation.agent_runtime.campaign_runner import _ingest_pool
from phase3.evaluation.agent_runtime.gold_evidence_runner import GoldEvidenceTaskInput, run_gold_evidence_task
from phase3.evaluation.agent_runtime.messages import DEFAULT_SYSTEM_PROMPT, render_messages
from phase3.evaluation.agent_runtime.runner import (
    AgentTaskInput, RunConfiguration, _extract_content_text, _extract_memory_id, generate_with_retries,
)
from phase3.evaluation.agent.outcomes import EXECUTION_STATUS_ERROR, EXECUTION_STATUS_SUCCESS, AgentExecutionResult
from phase3.evaluation.agent_runtime.trace import evaluate_and_trace, evaluate_and_trace_with_identity
from phase3.evaluation.foundations.adapter import FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL
from phase3.evaluation.foundations.hybrid_selection import DEFAULT_TOP_K, RETRIEVAL_POOL_SIZE_N, select_by_hybrid_score
from phase3.evaluation.foundations.temporal_resolution import render_content_with_temporal_annotations
from phase3.evaluation.llm.provider import clean_baseline_generation_config
from phase3.evaluation.security import content_leakage as sec_content_leakage

V3_STORE = OUTPUT_DIR / "canonical_store" / "v3_candidate"

REASON_RETRIEVED_V3 = (
    "retrieved via foundation.retrieve() during Condition C V3 campaign execution "
    "(pool_size=20, hybrid_selection.select_by_hybrid_score(), plus per-item "
    "deterministic relative-time resolution on selected content)."
)
REASON_SELECTED_V3 = (
    "selected via foundations.hybrid_selection.select_by_hybrid_score() (identical "
    "mechanism/weights to V2), content additionally annotated by "
    "foundations.temporal_resolution.render_content_with_temporal_annotations() where "
    "a relative-time pattern matched. Validated in PHASE3_V3_ROUND2/3 at n=24 on both "
    "conditions, hand-verified real gains, zero real regressions, before this scale-up."
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


def run_condition_b_v3(all_tasks, llm_provider, generation_config, campaign_id):
    """V3 Condition B: V2's timestamp-prefixed evidence content, PLUS deterministic
    relative-time resolution applied on top. Foundation-independent -- run once."""
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
                base_content = f"{row['source_role']}: {row['content']}"
                if row.get("source_timestamp"):
                    v2_content = f"[{row['source_timestamp']}] {base_content}"
                    annotated = render_content_with_temporal_annotations(base_content, row["source_timestamp"])
                    if annotated != base_content:
                        resolved_suffix = annotated[len(base_content):]
                        content_text = f"{v2_content}{resolved_suffix}"
                    else:
                        content_text = v2_content
                else:
                    content_text = base_content
                evidence_items.append({"gold_evidence_id": eid, "content": content_text})

            outcome = run_gold_evidence_task(
                GoldEvidenceTaskInput(task_id=task.task_id, prompt=task.question, evidence_items=evidence_items),
                config=RunConfiguration(llm_provider=llm_provider, generation_config=generation_config),
            )
            latency = time.time() - t0
            _content_leakage_scan(outcome, task, "V3-B-GoldEvidence-TemporalResolved")

            trace = evaluate_and_trace(
                outcome, experiment_id=f"{campaign_id}-{task.dataset}-{task.task_id}-V3-B",
                dataset=task.dataset, dataset_revision=DATASET_REVISION, record_id=task.task_id,
                expected_answer=task.answer, gold_evidence_ids=task.evidence_memory_ids,
            )
            results.append({
                "task_id": task.task_id, "dataset": task.dataset, "status": "SUCCESSFUL_EVALUATION",
                "trace": trace, "latency_sec": latency, "vram_mib": _gpu_vram_mib(),
            })
        except Exception as exc:
            results.append({"task_id": task.task_id, "dataset": task.dataset, "status": "EXECUTION_FAILURE", "error": repr(exc), "latency_sec": time.time() - t0})
    return results


def _run_condition_c_v3(all_tasks, llm_provider, generation_config, campaign_id, checkpoint_path, foundation_kind):
    """Shared implementation for both Mem0 and A-MEM V3 Condition C -- differs only
    in which real adapter/canonical-wiring identity-resolution strategy is used,
    mirroring campaign_v2_runner.py's own Mem0/A-MEM split exactly."""
    if foundation_kind == "MEM0":
        from phase3.evaluation.foundations_real.mem0_real_adapter import RealMem0Adapter
        from phase3.evaluation.agent_runtime.canonical_wiring import (
            open_pool_canonical_ledgers, record_retrieval_and_selection_events, write_ingested_canonical_memory,
        )
        from phase3.evaluation.foundations.canonical_write import STATUS_CANONICAL_AND_FOUNDATION
    else:
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
        print(f"  Resuming V3 {foundation_kind}: {len(completed_task_ids)} tasks already done.", flush=True)

    def _save():
        if checkpoint_path:
            with open(checkpoint_path, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False, default=str)

    for (dataset, pool_key), tasks_in_pool in sorted(groups.items()):
        if all(t.task_id in completed_task_ids for t in tasks_in_pool):
            continue

        pool_rows_by_id = {}
        for row in _ingest_pool(dataset, tasks_in_pool[0].ingest_key_field, pool_key):
            pool_rows_by_id[row["memory_id"]] = row

        if foundation_kind == "MEM0":
            foundation = RealMem0Adapter()
            collection_name = "v3_" + hashlib.sha256(f"{dataset}:{pool_key}".encode()).hexdigest()[:16]
            init_field = foundation.initialize({"embedding_model": "sentence-transformers/all-MiniLM-L6-v2", "collection_name": collection_name})
        else:
            foundation = RealAMemAdapter()
            init_field = foundation.initialize({"embedding_model": "all-MiniLM-L6-v2"})

        if init_field.availability != FOUNDATION_AVAILABLE:
            for task in tasks_in_pool:
                results.append({"task_id": task.task_id, "dataset": dataset, "status": "ENVIRONMENT_FAILURE", "error": "initialize() failed"})
            continue
        if foundation.reset().availability != FOUNDATION_AVAILABLE:
            for task in tasks_in_pool:
                results.append({"task_id": task.task_id, "dataset": dataset, "status": "ENVIRONMENT_FAILURE", "error": "reset() failed"})
            continue

        if foundation_kind == "MEM0":
            pool_ledgers = open_pool_canonical_ledgers(
                OUTPUT_DIR, campaign_id, dataset, collection_name,
                adapter_revision=foundation.foundation_identity().adapter_version,
                retrieval_k=RETRIEVAL_POOL_SIZE_N, embedding_model="sentence-transformers/all-MiniLM-L6-v2",
            )
            ingested_ids = []
            for row in pool_rows_by_id.values():
                wr = write_ingested_canonical_memory(
                    pool_ledgers.memory_ledger, foundation, source_id=row["memory_id"],
                    content={"text": f"{row['source_role']}: {row['content']}"},
                    metadata_extra={"user_id": f"v3-{dataset}-{pool_key}", "source_memory_id": row["memory_id"]},
                    ingestion_label=f"v3-ingest-{campaign_id}-{dataset}-{pool_key}",
                )
                if wr.status == STATUS_CANONICAL_AND_FOUNDATION:
                    ingested_ids.append(row["memory_id"])
        else:
            collection_token = "v3_a_" + hashlib.sha256(f"{dataset}:{pool_key}".encode()).hexdigest()[:16]
            pool_ledgers = open_pool_canonical_ledgers(
                OUTPUT_DIR, campaign_id, dataset, collection_token,
                adapter_revision=foundation.foundation_identity().adapter_version,
                retrieval_k=RETRIEVAL_POOL_SIZE_N, embedding_model="all-MiniLM-L6-v2",
                retrieval_mechanism=RETRIEVAL_MECHANISM_AMEM_DENSE,
            )
            resolutions = {}
            for row in pool_rows_by_id.values():
                add_field = foundation.add_memory(
                    memory_id=row["memory_id"], content={"text": f"{row['source_role']}: {row['content']}"},
                    metadata={"tags": ["v3", dataset], "keywords": [dataset], "context": pool_key},
                )
                if add_field.availability == FOUNDATION_AVAILABLE:
                    resolution = resolve_via_direct_assignment(row["memory_id"], add_field.value)
                    resolutions[resolution.foundation_memory_id] = resolution
                    try:
                        write_canonical_record_and_alias_direct_assignment(
                            pool_ledgers.memory_ledger, source_id=row["memory_id"],
                            content={"text": f"{row['source_role']}: {row['content']}"},
                            ingestion_label=f"v3-ingest-{campaign_id}-{dataset}-{pool_key}",
                            foundation_memory_id=(resolution.foundation_memory_id if resolution.status == STATUS_RESOLVED else None),
                        )
                    except Exception:
                        pass

        for task in tasks_in_pool:
            if task.task_id in completed_task_ids:
                continue
            t0 = time.time()
            try:
                retrieval_query = {"text": task.question, "user_id": f"v3-{dataset}-{pool_key}"} if foundation_kind == "MEM0" else {"text": task.question}
                retrieve_field = foundation.retrieve(retrieval_query, top_k=RETRIEVAL_POOL_SIZE_N)
                memory_items: List[Mapping[str, Any]] = []
                retrieved_ids: Tuple[str, ...] = ()
                selected_ids: Tuple[str, ...] = ()
                if retrieve_field.availability in (FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL):
                    raw_items = retrieve_field.value or []
                    retrieved_ids = tuple(mid for mid in (_extract_memory_id(i) for i in raw_items) if mid is not None)
                    candidates: List[Tuple[str, str]] = []
                    source_id_by_foundation_id: Mapping[str, str] = {}
                    for mid in retrieved_ids:
                        inspect_field = foundation.inspect_memory(mid)
                        if inspect_field.availability in (FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL):
                            native = inspect_field.value or {}
                            candidates.append((mid, _extract_content_text(native)))
                            if foundation_kind == "MEM0":
                                metadata = native.get("metadata") if isinstance(native, Mapping) else None
                                source_id = metadata.get("source_memory_id") if isinstance(metadata, Mapping) else None
                                if source_id is not None:
                                    source_id_by_foundation_id[mid] = str(source_id)
                            else:
                                source_id_by_foundation_id[mid] = mid  # direct-assignment: foundation id == canonical id

                    sel = select_by_hybrid_score(task.question, candidates, top_k=DEFAULT_TOP_K)
                    selected_ids = tuple(c.memory_id for c in sel.selected)
                    content_by_id = dict(candidates)
                    for c in sel.selected:
                        content = content_by_id[c.memory_id]
                        source_id = source_id_by_foundation_id.get(c.memory_id)
                        source_ts = pool_rows_by_id.get(source_id, {}).get("source_timestamp") if source_id else None
                        annotated = render_content_with_temporal_annotations(content, source_ts) if source_ts else content
                        memory_items.append({"memory_id": c.memory_id, "content": annotated})

                context = build_agent_visible_context(condition=CONDITION_RETRIEVED_MEMORY, task_id=task.task_id, prompt=task.question, memory_items=memory_items)
                messages = render_messages(context, DEFAULT_SYSTEM_PROMPT)
                answer, attempts = generate_with_retries(messages, RunConfiguration(llm_provider=llm_provider, generation_config=generation_config))
                run_latency = time.time() - t0

                exec_result = AgentExecutionResult(
                    task_id=task.task_id, condition=CONDITION_RETRIEVED_MEMORY, answer=answer,
                    execution_status=EXECUTION_STATUS_SUCCESS if answer is not None else EXECUTION_STATUS_ERROR,
                    selected_memory_ids=selected_ids, used_memory_ids=None, execution_metadata={"attempts": len(attempts)},
                )
                from phase3.evaluation.agent_runtime.runner import AgentRunOutcome
                outcome = AgentRunOutcome(
                    task_id=task.task_id, condition=CONDITION_RETRIEVED_MEMORY, memory_available=True,
                    retrieved_memory_ids=retrieved_ids, selected_memory_ids=selected_ids,
                    exposed_memory_ids=tuple(item["memory_id"] for item in memory_items),
                    agent_visible_context=context, execution_result=exec_result, attempts=tuple(attempts),
                    generation_config_fingerprint=llm_provider.configuration_fingerprint(generation_config),
                    model_metadata=llm_provider.model_metadata(), total_latency_sec=run_latency,
                    foundation_identity={"foundation_id": foundation.foundation_identity().foundation_id,
                                          "foundation_name": foundation.foundation_identity().foundation_name,
                                          "adapter_version": foundation.foundation_identity().adapter_version,
                                          "status": foundation.foundation_identity().status},
                )
                _content_leakage_scan(outcome, task, f"V3-C-{foundation_kind}-TemporalResolved")

                if foundation_kind == "MEM0":
                    trace = evaluate_and_trace_with_identity(
                        outcome, foundation, experiment_id=f"{campaign_id}-{dataset}-{task.task_id}-V3-C-{foundation_kind}",
                        dataset=dataset, dataset_revision=DATASET_REVISION, record_id=task.task_id,
                        expected_answer=task.answer, gold_evidence_ids=task.evidence_memory_ids,
                        ingested_source_memory_ids=ingested_ids,
                    )
                    try:
                        canonical_event_report = dataclasses.asdict(record_retrieval_and_selection_events(
                            pool_ledgers.event_ledger, pool_ledgers.memory_ledger, foundation,
                            task_id=task.task_id, config_fingerprint=pool_ledgers.config_fingerprint,
                            timestamp=datetime.now(timezone.utc).isoformat(),
                            retrieved_foundation_ids=retrieved_ids, selected_foundation_ids=selected_ids,
                            retrieved_reason=REASON_RETRIEVED_V3, selected_reason=REASON_SELECTED_V3,
                        ))
                    except Exception as canonical_exc:
                        canonical_event_report = {"CANONICAL_EVENT_WIRING_ERROR": repr(canonical_exc)}
                else:
                    trace = evaluate_and_trace(
                        outcome, experiment_id=f"{campaign_id}-{dataset}-{task.task_id}-V3-C-{foundation_kind}",
                        dataset=dataset, dataset_revision=DATASET_REVISION, record_id=task.task_id,
                        expected_answer=task.answer, gold_evidence_ids=task.evidence_memory_ids,
                        store_memory_ids=list(resolutions.keys()),
                    )
                    try:
                        canonical_event_report = dataclasses.asdict(record_retrieval_and_selection_events_direct_assignment(
                            pool_ledgers.event_ledger, pool_ledgers.memory_ledger,
                            task_id=task.task_id, config_fingerprint=pool_ledgers.config_fingerprint,
                            timestamp=datetime.now(timezone.utc).isoformat(),
                            retrieved_canonical_ids=retrieved_ids, selected_canonical_ids=selected_ids,
                            retrieved_reason=REASON_RETRIEVED_V3, selected_reason=REASON_SELECTED_V3,
                        ))
                    except Exception as canonical_exc:
                        canonical_event_report = {"CANONICAL_EVENT_WIRING_ERROR": repr(canonical_exc)}

                results.append({
                    "task_id": task.task_id, "dataset": dataset, "status": "SUCCESSFUL_EVALUATION",
                    "trace": trace, "run_latency_sec": run_latency, "pool_key": pool_key,
                    "vram_mib": _gpu_vram_mib(), "canonical_event_report": canonical_event_report,
                })
            except Exception as exc:
                results.append({"task_id": task.task_id, "dataset": dataset, "status": "EXECUTION_FAILURE", "error": repr(exc), "pool_key": pool_key})
        foundation.shutdown()
        _save()
        print(f"  [v3-checkpoint {foundation_kind.lower()}] pool {pool_key} done ({len(results)}/{len(all_tasks)} tasks total)", flush=True)
    return results


def run_condition_c_v3_mem0(all_tasks, llm_provider, generation_config, campaign_id, checkpoint_path=None):
    return _run_condition_c_v3(all_tasks, llm_provider, generation_config, campaign_id, checkpoint_path, "MEM0")


def run_condition_c_v3_amem(all_tasks, llm_provider, generation_config, campaign_id, checkpoint_path=None):
    return _run_condition_c_v3(all_tasks, llm_provider, generation_config, campaign_id, checkpoint_path, "AMEM")


__all__ = ["V3_STORE", "run_condition_a", "run_condition_b_v3", "run_condition_c_v3_mem0", "run_condition_c_v3_amem"]
