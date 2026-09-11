"""Phase 4.7 -- shared retrieve/select/render/generate pipeline.

Extracted from five near-identical, independently-written copies of the
same function (`retrieve_select_generate`), found during Phase 4.6/4.7's
consolidation pass in `phase4/attacks/{agentpoison,minja,farma,dsrm,mpbench}/
milestone*_campaign.py` -- each attack's author (this session, across
separate implementation passes) independently arrived at the exact same
sequence of real Phase 3 calls, differing only in the `task_id` label
string passed to `build_agent_visible_context`. This is real convergent
evidence that the sequence below IS "the" real Condition C retrieve/select/
generate pipeline for a single task, not an attack-specific convenience --
see PHASE4_4_6_POISON_ARTIFACT_AND_INJECTION_MODEL.md Section 2 and
PHASE4_4_7_ATTACK_PHASE3_INTEGRATION.md for the extraction evidence.

BEHAVIOR-PRESERVING EXTRACTION, NOT A REDESIGN: every call inside is the
same real, unmodified Phase 3 function each campaign script already called
directly (`foundation.retrieve()`, `select_by_hybrid_score()`,
`build_agent_visible_context()`, `render_messages()`,
`generate_with_retries()`) -- nothing here reimplements or wraps Phase 3
logic, it only removes five-way duplication of the SAME calling code. Does
not go through `run_condition_c_v3_mem0` itself (checkpointing/ledger/
orchestration) -- same scoping disclosure every prior campaign script
already carried individually.
"""

from __future__ import annotations

from typing import Any, List, Mapping, Tuple

from phase3.evaluation.agent.conditions import CONDITION_RETRIEVED_MEMORY, build_agent_visible_context
from phase3.evaluation.agent.outcomes import EXECUTION_STATUS_ERROR, EXECUTION_STATUS_SUCCESS, AgentExecutionResult
from phase3.evaluation.agent_runtime.messages import render_messages
from phase3.evaluation.agent_runtime.runner import (
    AgentRunOutcome, RunConfiguration, _extract_content_text, _extract_memory_id, generate_with_retries,
)
from phase3.evaluation.foundations.adapter import FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL, MemoryFoundationAdapter
from phase3.evaluation.foundations.hybrid_selection import DEFAULT_TOP_K, RETRIEVAL_POOL_SIZE_N, select_by_hybrid_score


def retrieve_select_generate(
    foundation: MemoryFoundationAdapter,
    query: str,
    run_config: RunConfiguration,
    *,
    user_id: str,
    task_id: str,
) -> AgentRunOutcome:
    """The real Condition C retrieve -> select -> render -> generate
    sequence for one task, against a real (or mock) `MemoryFoundationAdapter`."""
    retrieve_field = foundation.retrieve({"text": query, "user_id": user_id}, top_k=RETRIEVAL_POOL_SIZE_N)
    retrieved_ids: Tuple[str, ...] = ()
    selected_ids: Tuple[str, ...] = ()
    memory_items: List[Mapping[str, Any]] = []
    if retrieve_field.availability in (FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL):
        raw_items = retrieve_field.value or []
        retrieved_ids = tuple(mid for mid in (_extract_memory_id(i) for i in raw_items) if mid is not None)
        candidates: List[Tuple[str, str]] = []
        for mid in retrieved_ids:
            inspect_field = foundation.inspect_memory(mid)
            if inspect_field.availability in (FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL):
                candidates.append((mid, _extract_content_text(inspect_field.value or {})))
        sel = select_by_hybrid_score(query, candidates, top_k=DEFAULT_TOP_K)
        selected_ids = tuple(c.memory_id for c in sel.selected)
        content_by_id = dict(candidates)
        for c in sel.selected:
            memory_items.append({"memory_id": c.memory_id, "content": content_by_id[c.memory_id]})

    context = build_agent_visible_context(
        condition=CONDITION_RETRIEVED_MEMORY, task_id=task_id, prompt=query, memory_items=memory_items,
    )
    messages = render_messages(context, run_config.system_prompt)
    answer, attempts = generate_with_retries(messages, run_config)

    exec_result = AgentExecutionResult(
        task_id=task_id, condition=CONDITION_RETRIEVED_MEMORY, answer=answer,
        execution_status=EXECUTION_STATUS_SUCCESS if answer is not None else EXECUTION_STATUS_ERROR,
        selected_memory_ids=selected_ids, used_memory_ids=None, execution_metadata={"attempts": len(attempts)},
    )
    return AgentRunOutcome(
        task_id=task_id, condition=CONDITION_RETRIEVED_MEMORY, memory_available=True,
        retrieved_memory_ids=retrieved_ids, selected_memory_ids=selected_ids,
        exposed_memory_ids=tuple(item["memory_id"] for item in memory_items),
        agent_visible_context=context, execution_result=exec_result, attempts=tuple(attempts),
        generation_config_fingerprint=run_config.llm_provider.configuration_fingerprint(run_config.generation_config),
        model_metadata=run_config.llm_provider.model_metadata(), total_latency_sec=0.0,
        foundation_identity={"foundation_id": "mem0"},
    )


__all__ = ["retrieve_select_generate"]
