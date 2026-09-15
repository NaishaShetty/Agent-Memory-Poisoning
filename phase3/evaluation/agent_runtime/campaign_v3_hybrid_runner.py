"""Phase 3.3-V3-HYBRID -- FINAL, CANONICAL Phase 3 memory foundation.

V3-HYBRID IS THE ONLY CANONICAL PHASE 3 FOUNDATION. V1, V2, V3, V4, and V5 are
historical/experimental variants, retained for evidence and reproducibility but not
depended on by this file or by Phase 4.

COMPOSITION, NOT REDESIGN
--------------------------------------------------------------------------------
V3-Hybrid combines two independently-validated pieces, per the real head-to-head
evidence gathered during Phase 3 closure work:

- Condition A (no memory): V3's exact, unchanged `run_condition_a` -- imported from
  `campaign_formal_runner.py`, shared stable infrastructure every version reuses.
- Condition B (gold evidence): V3's exact evidence construction (temporal-resolved
  gold evidence, identical to `campaign_v3_runner.py::run_condition_b_v3`), PLUS a
  bounded draft->verify->[revise] reasoning step
  (`canonical_verified_reasoning.generate_verified_answer`) -- the ONE piece
  originally developed during V5 experimentation with a real, reproduced win on
  this condition specifically (confirmed at n=120 with a corrected, V3-matching
  system prompt: normalized/content-recall/date-normalized/number-word/llm-judge
  all improved or held vs. plain V3's own B). See
  `canonical_verified_reasoning.py`'s docstring for full provenance.
- Condition C (retrieved memory, Mem0 and A-MEM): V3's exact, unchanged
  `run_condition_c_v3_mem0`/`run_condition_c_v3_amem` -- the same bounded
  verification step was tested here too and found to NOT reliably help (flat on
  A-MEM, a real regression on Mem0), so it is deliberately NOT applied to Condition
  C. V3-Hybrid makes no claim of universal verification benefit.

ISOLATION -- WHY THIS FILE HAS ZERO V5 IMPORTS
--------------------------------------------------------------------------------
An earlier version of this file imported `V5_VERIFIED`/`run_condition_b_v5`
directly from `campaign_v5_runner.py` -- a real coupling violation found during
final Phase 3 closure audit (Phase 4 must not need to import V5). Fixed by
promoting the underlying reasoning mechanism to a canonical, version-neutral module
(`canonical_verified_reasoning.py`, a byte-for-byte logical duplicate of the
originally-validated V5 logic, not a redesign) and reimplementing Condition B here
directly against shared, non-versioned primitives -- exactly mirroring
`campaign_v3_runner.py::run_condition_b_v3`'s own evidence construction, since
V3-Hybrid's B condition IS V3's B condition plus one additional reasoning step.
V5's own files (`v5_reasoning_pipeline.py`, `campaign_v5_runner.py`,
`v5_structured_memory.py`) are left completely untouched as historical artifacts --
never modified, never deleted, never imported from here.

Produces its OWN separate canonical-store namespace (`V3_HYBRID_STORE`), never
writing into `v3_candidate`, `v5_candidate`, or any other existing store.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from phase3.evaluation.agent.conditions import CONDITION_GOLD_EVIDENCE, build_agent_visible_context
from phase3.evaluation.agent.outcomes import EXECUTION_STATUS_ERROR, EXECUTION_STATUS_SUCCESS, AgentExecutionResult
from phase3.evaluation.agent_runtime.campaign_formal_runner import OUTPUT_DIR, DATASET_REVISION, _gpu_vram_mib, run_condition_a
from phase3.evaluation.agent_runtime.campaign_v3_runner import run_condition_c_v3_amem, run_condition_c_v3_mem0
from phase3.evaluation.agent_runtime.canonical_verified_reasoning import generate_verified_answer
from phase3.evaluation.agent_runtime.dataset_record_assembler import assemble_dataset_records
from phase3.evaluation.agent_runtime.runner import AgentRunOutcome
from phase3.evaluation.agent_runtime.trace import evaluate_and_trace
from phase3.evaluation.contracts.boundary import AgentVisibilityViolation
from phase3.evaluation.foundations.temporal_resolution import render_content_with_temporal_annotations
from phase3.evaluation.llm.provider import LLMProviderError
from phase3.evaluation.security import content_leakage as sec_content_leakage
from phase3.evaluation.security.content_leakage import ContentLeakageDetectedError

V3_HYBRID_STORE = OUTPUT_DIR / "canonical_store" / "v3_hybrid_candidate"

# P2 fix (2026-09-14): exception types this loop genuinely expects to see from a
# real campaign run (an LLM connection drop, a genuine boundary/leakage rejection
# this module itself raises as RuntimeError below) -- NOT a signal that every
# other exception type is impossible, but a way to distinguish "ordinary
# experimental failure" from "this task silently triggered a bug in the
# assembler." See EXPECTED_RUNTIME_EXCEPTION_TYPES's use in the except block below.
EXPECTED_RUNTIME_EXCEPTION_TYPES = (LLMProviderError, ContentLeakageDetectedError, RuntimeError)


def _load_jsonl(path: Path):
    import json
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


_DATA_ROOT = Path(__file__).resolve().parents[3] / "data" / "processed"


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


def run_condition_b_hybrid(all_tasks, llm_provider, generation_config, campaign_id):
    """V3-Hybrid Condition B: V3's exact evidence construction (temporal-resolved
    gold evidence -- identical to `campaign_v3_runner.py::run_condition_b_v3`),
    plus the canonical bounded verify/revise reasoning step. No V5 import."""
    memory_rows_by_id = {row["memory_id"]: row for row in _load_jsonl(_DATA_ROOT / "locomo" / "memory_records.jsonl")}
    results = []
    for task in all_tasks:
        t0 = time.time()
        try:
            evidence_items = []
            unresolved_evidence_ids = []  # P2 fix (2026-09-14) -- see below
            for eid in task.evidence_memory_ids:
                row = memory_rows_by_id.get(eid)
                if row is None:
                    # P2 fix (2026-09-14): a gold evidence id that fails to resolve
                    # against memory_records.jsonl (stale id, dataset-revision
                    # mismatch, path typo) used to be silently dropped here -- the
                    # model could then receive partial or EMPTY gold evidence with
                    # nothing in the trace distinguishing "the LLM was given full
                    # gold evidence" from "a data-pipeline bug silently starved it,"
                    # on Condition B specifically -- the condition V3-Hybrid's
                    # headline improvement is measured on (module docstring). Now
                    # recorded explicitly, always (not just when non-empty), so
                    # downstream analysis can filter/aggregate without guessing.
                    unresolved_evidence_ids.append(eid)
                    continue
                base_content = f"{row['source_role']}: {row['content']}"
                content_text = base_content
                if row.get("source_timestamp"):
                    prefixed = f"[{row['source_timestamp']}] {base_content}"
                    annotated = render_content_with_temporal_annotations(base_content, row["source_timestamp"])
                    content_text = prefixed + (annotated[len(base_content):] if annotated != base_content else "")
                evidence_items.append({"memory_id": eid, "content": content_text})

            memory_items = [{"memory_id": f"evidence-slot-{idx + 1}", "content": item["content"]} for idx, item in enumerate(evidence_items)]
            try:
                agent_visible_context = build_agent_visible_context(
                    condition=CONDITION_GOLD_EVIDENCE, task_id=task.task_id, prompt=task.question, memory_items=memory_items,
                )
            except AgentVisibilityViolation as exc:
                raise RuntimeError(f"Boundary check rejected V3-Hybrid-B context for {task.task_id!r}: {exc}") from exc

            evidence_text = "\n".join(item["content"] for item in evidence_items)
            answer_result = generate_verified_answer(
                question=task.question, evidence_text=evidence_text, llm_provider=llm_provider,
                generation_config=generation_config, enable_verification=True,
            )
            run_latency = time.time() - t0

            exec_result = AgentExecutionResult(
                task_id=task.task_id, condition=CONDITION_GOLD_EVIDENCE, answer=answer_result.final_answer,
                execution_status=EXECUTION_STATUS_SUCCESS if answer_result.final_answer is not None else EXECUTION_STATUS_ERROR,
                selected_memory_ids=(), used_memory_ids=None,
                execution_metadata={"v3_hybrid": True, "stage_call_count": len(answer_result.stage_calls)},
            )
            outcome = AgentRunOutcome(
                task_id=task.task_id, condition=CONDITION_GOLD_EVIDENCE, memory_available=True,
                retrieved_memory_ids=(), selected_memory_ids=(), exposed_memory_ids=tuple(item["memory_id"] for item in memory_items),
                agent_visible_context=agent_visible_context, execution_result=exec_result, attempts=(),
                generation_config_fingerprint=llm_provider.configuration_fingerprint(generation_config),
                model_metadata=llm_provider.model_metadata(), total_latency_sec=run_latency, foundation_identity=None,
            )
            _content_leakage_scan(outcome, task, "V3-Hybrid-B")

            trace = evaluate_and_trace(
                outcome, experiment_id=f"{campaign_id}-{task.dataset}-{task.task_id}-V3HYBRID-B",
                dataset=task.dataset, dataset_revision=DATASET_REVISION, record_id=task.task_id,
                expected_answer=task.answer, gold_evidence_ids=task.evidence_memory_ids,
            )
            trace_dict = dict(trace)
            trace_dict["unresolved_evidence_ids"] = tuple(unresolved_evidence_ids)
            trace_dict["v3_hybrid_reasoning"] = {
                "draft_answer": answer_result.draft_answer,
                "was_revised": answer_result.was_revised,
                "verification": answer_result.verification,
                "verification_parse_error": answer_result.verification_parse_error,
                "stages": [
                    {"stage": sc.stage, "latency_sec": sc.latency_sec, "finish_reason": sc.finish_reason, "attempts": sc.attempts}
                    for sc in answer_result.stage_calls
                ],
            }

            results.append({
                "task_id": task.task_id, "dataset": task.dataset, "status": "SUCCESSFUL_EVALUATION",
                "trace": trace_dict, "latency_sec": run_latency, "vram_mib": _gpu_vram_mib(),
            })
        except Exception as exc:
            # P2 fix (2026-09-14): still catches broadly (so one task's real infra
            # failure doesn't abort an entire long campaign run over many tasks --
            # that continue-on-failure behavior is preserved deliberately), but no
            # longer treats every exception type identically. An exception type this
            # loop does NOT expect (AttributeError/KeyError/TypeError from a genuine
            # programming bug, not a runtime condition) is tagged and printed loudly
            # here, rather than silently recorded as an ordinary EXECUTION_FAILURE
            # indistinguishable from a real LLM connection drop -- previously, a
            # systematic bug affecting many tasks would only ever show up as an
            # elevated EXECUTION_FAILURE rate, never as a loud, investigable signal.
            is_expected = isinstance(exc, EXPECTED_RUNTIME_EXCEPTION_TYPES)
            if not is_expected:
                print(
                    f"[campaign_v3_hybrid_runner] UNEXPECTED exception type "
                    f"{type(exc).__name__} for task {task.task_id!r} (Condition B) -- "
                    "not one of EXPECTED_RUNTIME_EXCEPTION_TYPES; this may be a real "
                    "code bug rather than an ordinary experimental failure.",
                    file=sys.stderr,
                )
            results.append({
                "task_id": task.task_id, "dataset": task.dataset, "status": "EXECUTION_FAILURE",
                "error": repr(exc), "latency_sec": time.time() - t0,
                "failure_kind": "EXPECTED_RUNTIME_FAILURE" if is_expected else "UNEXPECTED_EXCEPTION",
            })
    return results


__all__ = [
    "V3_HYBRID_STORE",
    "EXPECTED_RUNTIME_EXCEPTION_TYPES",
    "run_condition_a",
    "run_condition_b_hybrid",
    "run_condition_c_v3_mem0",
    "run_condition_c_v3_amem",
    "assemble_dataset_records",
]
