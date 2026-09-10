"""Phase 3.3-V5 -- the V5 experimental campaign runner. NEW FILE, additive only.

DOES NOT IMPORT, MODIFY, OR CALL INTO CAMPAIGN_V2_RUNNER.PY OR CAMPAIGN_V3_RUNNER.PY
--------------------------------------------------------------------------------
V5 reuses V1's `run_condition_a` (foundation-independent, structurally unaffected by
anything V5 adds) and the same lower-level primitives V2/V3 already reuse
(`hybrid_selection.select_by_hybrid_score`, `temporal_resolution.render_content_with_
temporal_annotations`, `canonical_wiring.*`, `identity.*`, the real Mem0/A-MEM
adapters) -- but V5's OWN Condition B/C logic lives entirely in this file, so V2's
and V3's runner files are never touched and never even imported by name. Produces a
SEPARATE dataset artifact (`V5_STORE`) from V1/V2/V3's frozen canonical stores;
none of those are read for writing, and none are modified.

WHAT'S NEW VS. V3, AND WHY -- SEE PHASE3_V5_ARCHITECTURE.MD FOR THE FULL RATIONALE
--------------------------------------------------------------------------------
- Retrieval/selection: UNCHANGED from V3 (pool=20, hybrid top-8, weights 0.5/0.3/0.2)
  -- the V4 diagnosis found retrieval was never the bottleneck (~99% gold-in-pool
  already), so V5 does not touch it.
- Temporal resolution: UNCHANGED from V3, reused verbatim, ablatable via
  `V5Config.enable_temporal_normalization`.
- NEW: a structured-memory layer (`v5_structured_memory.py`) that extracts (entity,
  attribute, value) facts from the SAME selected evidence, via one bounded LLM call,
  and presents them ALONGSIDE (never instead of) the raw evidence text -- ablatable
  via three independent flags.
- NEW: a bounded draft->verify->[revise] reasoning pipeline (`v5_reasoning_
  pipeline.py`) replacing V1-V4's single-pass generate-and-stop, directly targeting
  the "quote-then-hedge" pattern this session found twice. Ablatable via
  `V5Config.enable_bounded_verification`; when disabled, behavior is IDENTICAL to
  V1-V4's single generate_with_retries() call.
- Model config: same Qwen3-8B-Q4_K_M artifact as V1-V4 (the only model file on this
  hardware; see PHASE3_V5_DESIGN_RATIONALE.md's Model Selection section for the
  measured VRAM/disk evidence). `enable_thinking` and `max_tokens` are passed in via
  the caller's `GenerationConfig`, exactly as V1-V4 already support -- V5 does not
  hardcode a specific generation config, so both "V5 non-thinking" and "V5 thinking"
  variants can be run with zero code branching.

Condition A is reused verbatim, unchanged, from `campaign_formal_runner.py` -- see
`run_condition_a` re-exported below. No V5-specific Condition A exists because there
is nothing for the new components to act on with no memory present.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Mapping, Optional, Tuple

from phase3.evaluation.agent.conditions import CONDITION_GOLD_EVIDENCE, CONDITION_RETRIEVED_MEMORY, build_agent_visible_context
from phase3.evaluation.agent.outcomes import EXECUTION_STATUS_ERROR, EXECUTION_STATUS_SUCCESS, AgentExecutionResult
from phase3.evaluation.agent_runtime.campaign_formal_runner import (
    DATASET_REVISION, OUTPUT_DIR, _gpu_vram_mib, _group_by_pool, run_condition_a,
)
from phase3.evaluation.agent_runtime.campaign_runner import _ingest_pool
from phase3.evaluation.agent_runtime.messages import DEFAULT_SYSTEM_PROMPT, render_messages
from phase3.evaluation.agent_runtime.runner import AgentRunOutcome, _extract_content_text, _extract_memory_id
from phase3.evaluation.agent_runtime.trace import evaluate_and_trace, evaluate_and_trace_with_identity
from phase3.evaluation.agent_runtime.v5_reasoning_pipeline import generate_verified_answer
from phase3.evaluation.agent_runtime.v5_structured_memory import run_structured_memory_pipeline
from phase3.evaluation.contracts.boundary import AgentVisibilityViolation
from phase3.evaluation.foundations.adapter import FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL
from phase3.evaluation.foundations.hybrid_selection import DEFAULT_TOP_K, RETRIEVAL_POOL_SIZE_N, select_by_hybrid_score
from phase3.evaluation.foundations.temporal_resolution import render_content_with_temporal_annotations
from phase3.evaluation.security import content_leakage as sec_content_leakage

V5_STORE = OUTPUT_DIR / "canonical_store" / "v5_candidate"

REASON_RETRIEVED_V5 = (
    "retrieved via foundation.retrieve() during Condition C V5 campaign execution "
    "(pool_size=20, hybrid_selection.select_by_hybrid_score(), unchanged from V3; "
    "plus optional structured-fact extraction/consolidation over the selected set, "
    "per this run's V5Config)."
)
REASON_SELECTED_V5 = (
    "selected via foundations.hybrid_selection.select_by_hybrid_score() (identical "
    "mechanism/weights to V2/V3, unmodified). Content additionally annotated by "
    "temporal_resolution.render_content_with_temporal_annotations() where enabled, "
    "and supplemented (never replaced) by a structured-facts block where enabled -- "
    "see this record's v5_trace for exactly which V5 stages ran."
)


@dataclasses.dataclass(frozen=True)
class V5Config:
    """Every V5-specific behavior is gated by one of these flags, independently --
    per the V5 spec's explicit ablatability requirement. `label` is a short,
    human-readable name recorded into every trace this config produces, so a result
    can always be traced back to exactly which configuration produced it."""

    label: str
    enable_temporal_normalization: bool = True
    enable_structured_memory: bool = False
    enable_entity_resolution: bool = False
    enable_consolidation: bool = False
    enable_bounded_verification: bool = False


V5_BASE = V5Config(label="V5-base")  # == V3's evidence construction, single-pass generation -- the floor
V5_STRUCTURED = V5Config(label="V5+structured", enable_structured_memory=True, enable_entity_resolution=True, enable_consolidation=True)
V5_VERIFIED = V5Config(label="V5+verified", enable_bounded_verification=True)
V5_FULL = V5Config(
    label="V5-full", enable_structured_memory=True, enable_entity_resolution=True,
    enable_consolidation=True, enable_bounded_verification=True,
)
V5_NO_TEMPORAL = V5Config(label="V5-no_temporal", enable_temporal_normalization=False)


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


def _v5_trace_block(structured_result, answer_result) -> Mapping[str, Any]:
    """Every V5-specific observability field required by the spec: structured facts,
    entity links (via canonical_entity), consolidation decisions, reasoning stages,
    verification result, per-stage latency, finish_reason. Nothing here is
    fabricated -- a field absent from either pipeline result (e.g. no verification
    ran) is recorded as `None`/empty, never guessed."""
    return {
        "structured_memory": {
            "stages_run": list(structured_result.stages_run),
            "fact_count": len(structured_result.facts),
            "consolidated_fact_count": len(structured_result.consolidated),
            "facts": [
                {"entity": f.entity, "canonical_entity": f.canonical_entity, "attribute": f.attribute,
                 "value": f.value, "source_memory_ids": list(f.source_memory_ids), "confidence": f.confidence}
                for f in structured_result.facts
            ],
            "consolidated_facts": [
                {"canonical_entity": cf.canonical_entity, "attribute": cf.attribute, "values": list(cf.values),
                 "all_source_memory_ids": list(cf.all_source_memory_ids), "contributing_fact_count": cf.contributing_fact_count}
                for cf in structured_result.consolidated
            ],
            "extraction_parse_error": structured_result.extraction.parse_error if structured_result.extraction else None,
            "extraction_finish_reason": structured_result.extraction.finish_reason if structured_result.extraction else None,
        },
        "reasoning": {
            "draft_answer": answer_result.draft_answer,
            "was_revised": answer_result.was_revised,
            "verification": answer_result.verification,
            "verification_parse_error": answer_result.verification_parse_error,
            "stages": [
                {"stage": sc.stage, "latency_sec": sc.latency_sec, "finish_reason": sc.finish_reason, "attempts": sc.attempts}
                for sc in answer_result.stage_calls
            ],
            "total_reasoning_latency_sec": answer_result.total_latency_sec,
        },
    }


def run_condition_b_v5(all_tasks, llm_provider, generation_config, campaign_id, v5_config: V5Config):
    """V5 Condition B: gold evidence content, with V5's evidence construction and
    bounded reasoning pipeline applied on top -- structurally the same evidence
    SOURCE as V3 (no foundation, no retrieval), everything new is in how that
    evidence is presented to and reasoned over by the model."""
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
                content_text = base_content
                if v5_config.enable_temporal_normalization and row.get("source_timestamp"):
                    prefixed = f"[{row['source_timestamp']}] {base_content}"
                    annotated = render_content_with_temporal_annotations(base_content, row["source_timestamp"])
                    content_text = prefixed + (annotated[len(base_content):] if annotated != base_content else "")
                elif row.get("source_timestamp"):
                    content_text = f"[{row['source_timestamp']}] {base_content}"
                evidence_items.append({"memory_id": eid, "content": content_text})

            structured_result = run_structured_memory_pipeline(
                evidence_items, llm_provider, generation_config,
                enable_structured_memory=v5_config.enable_structured_memory,
                enable_entity_resolution=v5_config.enable_entity_resolution,
                enable_consolidation=v5_config.enable_consolidation,
            )

            memory_items = [{"memory_id": f"evidence-slot-{idx + 1}", "content": item["content"]} for idx, item in enumerate(evidence_items)]
            try:
                agent_visible_context = build_agent_visible_context(
                    condition=CONDITION_GOLD_EVIDENCE, task_id=task.task_id, prompt=task.question, memory_items=memory_items,
                )
            except AgentVisibilityViolation as exc:
                raise RuntimeError(f"Boundary check rejected V5-B context for {task.task_id!r}: {exc}") from exc

            raw_evidence_text = "\n".join(item["content"] for item in evidence_items)
            full_evidence_text = raw_evidence_text + (f"\n\n{structured_result.rendered_block}" if structured_result.rendered_block else "")

            answer_result = generate_verified_answer(
                question=task.question, evidence_text=full_evidence_text, llm_provider=llm_provider,
                generation_config=generation_config, enable_verification=v5_config.enable_bounded_verification,
            )
            run_latency = time.time() - t0

            exec_result = AgentExecutionResult(
                task_id=task.task_id, condition=CONDITION_GOLD_EVIDENCE, answer=answer_result.final_answer,
                execution_status=EXECUTION_STATUS_SUCCESS if answer_result.final_answer is not None else EXECUTION_STATUS_ERROR,
                selected_memory_ids=(), used_memory_ids=None,
                execution_metadata={"v5_config": v5_config.label, "stage_call_count": len(answer_result.stage_calls)},
            )
            outcome = AgentRunOutcome(
                task_id=task.task_id, condition=CONDITION_GOLD_EVIDENCE, memory_available=True,
                retrieved_memory_ids=(), selected_memory_ids=(), exposed_memory_ids=tuple(item["memory_id"] for item in memory_items),
                agent_visible_context=agent_visible_context, execution_result=exec_result, attempts=(),
                generation_config_fingerprint=llm_provider.configuration_fingerprint(generation_config),
                model_metadata=llm_provider.model_metadata(), total_latency_sec=run_latency, foundation_identity=None,
            )
            _content_leakage_scan(outcome, task, f"V5-B-{v5_config.label}")

            trace = evaluate_and_trace(
                outcome, experiment_id=f"{campaign_id}-{task.dataset}-{task.task_id}-V5-B",
                dataset=task.dataset, dataset_revision=DATASET_REVISION, record_id=task.task_id,
                expected_answer=task.answer, gold_evidence_ids=task.evidence_memory_ids,
            )
            trace_dict = dataclasses.asdict(trace) if dataclasses.is_dataclass(trace) else dict(trace)
            trace_dict["v5"] = _v5_trace_block(structured_result, answer_result)
            trace_dict["v5_config"] = v5_config.label

            results.append({
                "task_id": task.task_id, "dataset": task.dataset, "status": "SUCCESSFUL_EVALUATION",
                "trace": trace_dict, "latency_sec": run_latency, "vram_mib": _gpu_vram_mib(),
            })
        except Exception as exc:
            results.append({"task_id": task.task_id, "dataset": task.dataset, "status": "EXECUTION_FAILURE", "error": repr(exc), "latency_sec": time.time() - t0})
    return results


def _run_condition_c_v5(all_tasks, llm_provider, generation_config, campaign_id, checkpoint_path, foundation_kind, v5_config: V5Config):
    """Shared V5 Condition C implementation for Mem0/A-MEM. Retrieval, selection,
    canonical-ledger wiring, and identity resolution are IDENTICAL to
    campaign_v3_runner.py's own Condition C (same functions, same parameters,
    imported independently here rather than calling into that module) -- only the
    evidence-construction and answer-generation steps differ, per V5Config."""
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
        print(f"  Resuming V5 {foundation_kind} ({v5_config.label}): {len(completed_task_ids)} tasks already done.", flush=True)

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
            collection_name = "v5_" + hashlib.sha256(f"{dataset}:{pool_key}".encode()).hexdigest()[:16]
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
                    metadata_extra={"user_id": f"v5-{dataset}-{pool_key}", "source_memory_id": row["memory_id"]},
                    ingestion_label=f"v5-ingest-{campaign_id}-{dataset}-{pool_key}",
                )
                if wr.status == STATUS_CANONICAL_AND_FOUNDATION:
                    ingested_ids.append(row["memory_id"])
        else:
            collection_token = "v5_a_" + hashlib.sha256(f"{dataset}:{pool_key}".encode()).hexdigest()[:16]
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
                    metadata={"tags": ["v5", dataset], "keywords": [dataset], "context": pool_key},
                )
                if add_field.availability == FOUNDATION_AVAILABLE:
                    resolution = resolve_via_direct_assignment(row["memory_id"], add_field.value)
                    resolutions[resolution.foundation_memory_id] = resolution
                    try:
                        write_canonical_record_and_alias_direct_assignment(
                            pool_ledgers.memory_ledger, source_id=row["memory_id"],
                            content={"text": f"{row['source_role']}: {row['content']}"},
                            ingestion_label=f"v5-ingest-{campaign_id}-{dataset}-{pool_key}",
                            foundation_memory_id=(resolution.foundation_memory_id if resolution.status == STATUS_RESOLVED else None),
                        )
                    except Exception:
                        pass

        for task in tasks_in_pool:
            if task.task_id in completed_task_ids:
                continue
            t0 = time.time()
            try:
                retrieval_query = {"text": task.question, "user_id": f"v5-{dataset}-{pool_key}"} if foundation_kind == "MEM0" else {"text": task.question}
                retrieve_field = foundation.retrieve(retrieval_query, top_k=RETRIEVAL_POOL_SIZE_N)
                memory_items: List[Mapping[str, Any]] = []
                evidence_items_for_structured: List[Mapping[str, Any]] = []
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
                                source_id_by_foundation_id[mid] = mid

                    sel = select_by_hybrid_score(task.question, candidates, top_k=DEFAULT_TOP_K)
                    selected_ids = tuple(c.memory_id for c in sel.selected)
                    content_by_id = dict(candidates)
                    for c in sel.selected:
                        content = content_by_id[c.memory_id]
                        source_id = source_id_by_foundation_id.get(c.memory_id)
                        source_ts = pool_rows_by_id.get(source_id, {}).get("source_timestamp") if source_id else None
                        annotated = (
                            render_content_with_temporal_annotations(content, source_ts)
                            if (v5_config.enable_temporal_normalization and source_ts) else content
                        )
                        memory_items.append({"memory_id": c.memory_id, "content": annotated})
                        evidence_items_for_structured.append({"memory_id": c.memory_id, "content": annotated})

                structured_result = run_structured_memory_pipeline(
                    evidence_items_for_structured, llm_provider, generation_config,
                    enable_structured_memory=v5_config.enable_structured_memory,
                    enable_entity_resolution=v5_config.enable_entity_resolution,
                    enable_consolidation=v5_config.enable_consolidation,
                )

                context = build_agent_visible_context(condition=CONDITION_RETRIEVED_MEMORY, task_id=task.task_id, prompt=task.question, memory_items=memory_items)
                raw_evidence_text = "\n".join(item["content"] for item in memory_items)
                full_evidence_text = raw_evidence_text + (f"\n\n{structured_result.rendered_block}" if structured_result.rendered_block else "")

                answer_result = generate_verified_answer(
                    question=task.question, evidence_text=full_evidence_text, llm_provider=llm_provider,
                    generation_config=generation_config, enable_verification=v5_config.enable_bounded_verification,
                )
                run_latency = time.time() - t0

                exec_result = AgentExecutionResult(
                    task_id=task.task_id, condition=CONDITION_RETRIEVED_MEMORY, answer=answer_result.final_answer,
                    execution_status=EXECUTION_STATUS_SUCCESS if answer_result.final_answer is not None else EXECUTION_STATUS_ERROR,
                    selected_memory_ids=selected_ids, used_memory_ids=None,
                    execution_metadata={"v5_config": v5_config.label, "stage_call_count": len(answer_result.stage_calls)},
                )
                outcome = AgentRunOutcome(
                    task_id=task.task_id, condition=CONDITION_RETRIEVED_MEMORY, memory_available=True,
                    retrieved_memory_ids=retrieved_ids, selected_memory_ids=selected_ids,
                    exposed_memory_ids=tuple(item["memory_id"] for item in memory_items),
                    agent_visible_context=context, execution_result=exec_result, attempts=(),
                    generation_config_fingerprint=llm_provider.configuration_fingerprint(generation_config),
                    model_metadata=llm_provider.model_metadata(), total_latency_sec=run_latency,
                    foundation_identity={"foundation_id": foundation.foundation_identity().foundation_id,
                                          "foundation_name": foundation.foundation_identity().foundation_name,
                                          "adapter_version": foundation.foundation_identity().adapter_version,
                                          "status": foundation.foundation_identity().status},
                )
                _content_leakage_scan(outcome, task, f"V5-C-{foundation_kind}-{v5_config.label}")

                if foundation_kind == "MEM0":
                    trace = evaluate_and_trace_with_identity(
                        outcome, foundation, experiment_id=f"{campaign_id}-{dataset}-{task.task_id}-V5-C-{foundation_kind}",
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
                            retrieved_reason=REASON_RETRIEVED_V5, selected_reason=REASON_SELECTED_V5,
                        ))
                    except Exception as canonical_exc:
                        canonical_event_report = {"CANONICAL_EVENT_WIRING_ERROR": repr(canonical_exc)}
                else:
                    trace = evaluate_and_trace(
                        outcome, experiment_id=f"{campaign_id}-{dataset}-{task.task_id}-V5-C-{foundation_kind}",
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
                            retrieved_reason=REASON_RETRIEVED_V5, selected_reason=REASON_SELECTED_V5,
                        ))
                    except Exception as canonical_exc:
                        canonical_event_report = {"CANONICAL_EVENT_WIRING_ERROR": repr(canonical_exc)}

                trace_dict = dataclasses.asdict(trace) if dataclasses.is_dataclass(trace) else dict(trace)
                trace_dict["v5"] = _v5_trace_block(structured_result, answer_result)
                trace_dict["v5_config"] = v5_config.label

                results.append({
                    "task_id": task.task_id, "dataset": dataset, "status": "SUCCESSFUL_EVALUATION",
                    "trace": trace_dict, "run_latency_sec": run_latency, "pool_key": pool_key,
                    "vram_mib": _gpu_vram_mib(), "canonical_event_report": canonical_event_report,
                })
            except Exception as exc:
                results.append({"task_id": task.task_id, "dataset": dataset, "status": "EXECUTION_FAILURE", "error": repr(exc), "pool_key": pool_key})
        foundation.shutdown()
        _save()
        print(f"  [v5-checkpoint {foundation_kind.lower()} {v5_config.label}] pool {pool_key} done ({len(results)}/{len(all_tasks)} tasks total)", flush=True)
    return results


def run_condition_c_v5_mem0(all_tasks, llm_provider, generation_config, campaign_id, v5_config: V5Config, checkpoint_path=None):
    return _run_condition_c_v5(all_tasks, llm_provider, generation_config, campaign_id, checkpoint_path, "MEM0", v5_config)


def run_condition_c_v5_amem(all_tasks, llm_provider, generation_config, campaign_id, v5_config: V5Config, checkpoint_path=None):
    return _run_condition_c_v5(all_tasks, llm_provider, generation_config, campaign_id, checkpoint_path, "AMEM", v5_config)


__all__ = [
    "V5_STORE", "V5Config", "V5_BASE", "V5_STRUCTURED", "V5_VERIFIED", "V5_FULL", "V5_NO_TEMPORAL",
    "run_condition_a", "run_condition_b_v5", "run_condition_c_v5_mem0", "run_condition_c_v5_amem",
]
