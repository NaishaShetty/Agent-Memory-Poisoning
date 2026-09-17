"""Phase 7.23 -- Real Two-Stage Retrieval Pipeline Studies (Closing §5.5).

CLOSES REPORT LIMITATION 5.5: THE RETRIEVAL-POOL-NARROWING GAP
--------------------------------------------------------------------------------
`agentpoison_study.py` (Stage 7.12) and `sleeper_study.py` (Stage 7.15) both
disclosed the same real, structural gap: `instrument_retrieval_and_selection()`
runs only `select_by_hybrid_score()` over a candidate list the caller already
assembled -- it never calls `foundation.retrieve()`, the real embedding-based
stage that narrows a large real memory store down to a small candidate pool
BEFORE hybrid re-ranking runs. For both attacks, their real, historically
documented discriminating effect happens at THAT stage, so both studies'
MockMem0Adapter-based harnesses failed to reproduce it (both found the poison
selected in every condition, including ones the real historical logs show it
should NOT be).

This module closes that gap using `RealMem0Adapter` (real sentence-transformers
embeddings + a real local vector store) -- the SAME real two-stage pipeline
`phase4.shared.campaign_runner.retrieve_select_generate()` uses
(`foundation.retrieve()` -> `foundation.inspect_memory()` per candidate ->
`select_by_hybrid_score()`), reproduced here WITHOUT that function's own final
generation step (no LLM call needed to test a retrieval-hijack claim -- this
module never calls `generate_with_retries()`). Requires `C:\\h4venv` (mem0ai
is only importable there); self-skips elsewhere, mirroring
`phase5/tests/test_real_vendor_compatibility_gate.py`'s own convention.

WHAT THIS ACTUALLY TESTS, AND WHAT IT DOES NOT
--------------------------------------------------------------------------------
Both studies below ingest a real, sizeable LoCoMo conversational pool (17 real
turns, `load_db_locomo()`, the SAME real pool the original historical
campaigns used) as genuine competition, then inject the real attack artifact
via its own real, unmodified injector, then run the real two-stage pipeline
under each real query condition. This is NOT a claim that these two studies
now reproduce the FULL original campaigns end-to-end (those also ran a real
generation step and, for AgentPoison, a real gradient-optimized artifact
against the SAME 17-turn pool used at injection time, not a freshly re-loaded
one) -- it is a claim that the retrieval-pool-narrowing mechanism itself is
now genuinely exercised, closing the specific structural gap Limitation 5.5
named.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

TS = "2026-09-16T00:00:00+00:00"
USER_ID = "phase7-real-retrieval-study"


def is_real_mem0_available() -> bool:
    """True iff `RealMem0Adapter` reports AVAILABLE/PARTIAL in the current
    interpreter -- callers (and this module's own tests) should check this
    before calling either study function below."""
    try:
        from phase3.evaluation.foundations_real.mem0_real_adapter import RealMem0Adapter
        from phase3.evaluation.foundations.adapter import FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL
    except ImportError:
        return False
    adapter = RealMem0Adapter()
    return adapter.initialize({}).availability in (FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL)


def _real_retrieve_then_select(foundation, query: str, *, top_k: int) -> Tuple[Tuple[str, ...], Tuple[str, ...]]:
    """The real retrieve -> inspect -> select sequence
    `campaign_runner.retrieve_select_generate()` uses, reproduced here WITHOUT
    its final generation step (module docstring). Returns (retrieved_ids,
    selected_ids), both real."""
    from phase3.evaluation.agent_runtime.runner import _extract_content_text, _extract_memory_id
    from phase3.evaluation.foundations.adapter import FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL
    from phase3.evaluation.foundations.hybrid_selection import RETRIEVAL_POOL_SIZE_N, select_by_hybrid_score

    retrieve_field = foundation.retrieve({"text": query, "user_id": USER_ID}, top_k=RETRIEVAL_POOL_SIZE_N)
    if retrieve_field.availability not in (FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL):
        return (), ()
    raw_items = retrieve_field.value or []
    retrieved_ids = tuple(mid for mid in (_extract_memory_id(i) for i in raw_items) if mid is not None)
    candidates: List[Tuple[str, str]] = []
    for mid in retrieved_ids:
        inspect_field = foundation.inspect_memory(mid)
        if inspect_field.availability in (FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL):
            candidates.append((mid, _extract_content_text(inspect_field.value or {})))
    sel = select_by_hybrid_score(query, candidates, top_k=top_k)
    selected_ids = tuple(c.memory_id for c in sel.selected)
    return retrieved_ids, selected_ids


def _ingest_real_locomo_pool(foundation, *, max_turns: int = 17) -> int:
    from phase4.attacks.agentpoison.locomo_pool import load_db_locomo

    turns = load_db_locomo(max_turns=max_turns)
    for text in turns:
        foundation.add_memory(memory_id=None, content={"text": text, "content_type": "CONVERSATIONAL_FACT"}, metadata={"user_id": USER_ID})
    return len(turns)


# ---------------------------------------------------------------------------
# AgentPoison
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AgentPoisonRealRetrievalResult:
    poison_memory_id: str
    benign_retrieved_ids: Tuple[str, ...]
    benign_selected_ids: Tuple[str, ...]
    trigger_retrieved_ids: Tuple[str, ...]
    trigger_selected_ids: Tuple[str, ...]
    selected_in_benign_condition: bool
    selected_in_trigger_condition: bool
    discriminates: bool  # True iff selected ONLY in the trigger condition (the real historical claim)


def run_agentpoison_real_retrieval_study(*, top_k: int = 8) -> AgentPoisonRealRetrievalResult:
    """Real two-stage (retrieve-then-select) reproduction of AgentPoison's
    backdoor claim, closing Limitation 5.5 for this attack. Requires
    `C:\\h4venv`'s interpreter; call `is_real_mem0_available()` first."""
    from phase3.evaluation.foundations_real.mem0_real_adapter import RealMem0Adapter
    from phase3.evaluation.foundations.adapter import FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL
    from phase4.attacks.agentpoison.injector import AgentPoisonInjector
    from phase7.propagation.agentpoison_study import _DEFAULT_ARTIFACT, _VICTIM_QUERY

    foundation = RealMem0Adapter()
    init_field = foundation.initialize({})
    if init_field.availability not in (FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL):
        raise RuntimeError(f"RealMem0Adapter unavailable ({init_field.availability}) -- run under C:\\h4venv.")
    foundation.reset()

    _ingest_real_locomo_pool(foundation)

    injector = AgentPoisonInjector(foundation)
    result = injector.inject(_DEFAULT_ARTIFACT, extra_metadata={"user_id": USER_ID})
    poison_memory_id = result.canonical_memory_id
    if poison_memory_id is None:
        raise RuntimeError("AgentPoison injection was not admitted -- a real environment problem.")

    trigger_query = f"{_VICTIM_QUERY} {_DEFAULT_ARTIFACT.trigger_text}"
    benign_retrieved, benign_selected = _real_retrieve_then_select(foundation, _VICTIM_QUERY, top_k=top_k)
    trigger_retrieved, trigger_selected = _real_retrieve_then_select(foundation, trigger_query, top_k=top_k)

    selected_in_benign = poison_memory_id in benign_selected
    selected_in_trigger = poison_memory_id in trigger_selected

    return AgentPoisonRealRetrievalResult(
        poison_memory_id=poison_memory_id,
        benign_retrieved_ids=benign_retrieved, benign_selected_ids=benign_selected,
        trigger_retrieved_ids=trigger_retrieved, trigger_selected_ids=trigger_selected,
        selected_in_benign_condition=selected_in_benign, selected_in_trigger_condition=selected_in_trigger,
        discriminates=(selected_in_trigger and not selected_in_benign),
    )


# ---------------------------------------------------------------------------
# Sleeper Memory Poisoning
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SleeperRealRetrievalResult:
    poison_memory_id: str
    selected_by_condition: Dict[str, bool]
    retrieved_by_condition: Dict[str, Tuple[str, ...]]
    # The real historical claim: selected for exact/paraphrased/near/partial, NOT for distant.
    discriminates: bool


def run_sleeper_real_retrieval_study(*, top_k: int = 8) -> SleeperRealRetrievalResult:
    """Real two-stage reproduction of Sleeper's dormant/triggered claim,
    closing Limitation 5.5 for this attack. Requires `C:\\h4venv`'s
    interpreter; call `is_real_mem0_available()` first."""
    from phase3.evaluation.agent_runtime.messages import DEFAULT_SYSTEM_PROMPT
    from phase3.evaluation.agent_runtime.runner import RunConfiguration
    from phase3.evaluation.foundations.adapter import FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL
    from phase3.evaluation.foundations_real.mem0_real_adapter import RealMem0Adapter
    from phase3.evaluation.llm.provider import GenerationConfig, LlamaServerEndpoint, LlamaServerProvider, _RawHttpResponse
    from phase4.attacks.sleeper_memory_poisoning.artifact import SEED_DESTRESS
    from phase4.attacks.sleeper_memory_poisoning.injector import SleeperInjector
    from phase7.propagation.sleeper_study import TRIGGER_CONDITIONS

    import json as _json

    def _scripted_gate_provider(reply: str) -> LlamaServerProvider:
        def post_json(url: str, body: bytes, timeout: float) -> _RawHttpResponse:
            payload = {"choices": [{"message": {"content": reply}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 10, "completion_tokens": 5}, "system_fingerprint": "phase7-real-retrieval-study"}
            return _RawHttpResponse(status=200, body=_json.dumps(payload).encode("utf-8"))
        return LlamaServerProvider(endpoint=LlamaServerEndpoint(), post_json=post_json)

    foundation = RealMem0Adapter()
    init_field = foundation.initialize({})
    if init_field.availability not in (FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL):
        raise RuntimeError(f"RealMem0Adapter unavailable ({init_field.availability}) -- run under C:\\h4venv.")
    foundation.reset()

    _ingest_real_locomo_pool(foundation)

    injector = SleeperInjector(foundation)
    run_config = RunConfiguration(
        llm_provider=_scripted_gate_provider("DECISION: KEEP\nRATIONALE: Reasonable."),
        generation_config=GenerationConfig(temperature=0.0, seed=42, max_tokens=64, enable_thinking=False, n_ctx=2048),
        system_prompt=DEFAULT_SYSTEM_PROMPT, max_retries=0,
    )
    result = injector.inject(SEED_DESTRESS, run_config, extra_metadata={"user_id": USER_ID})
    poison_memory_id = result.canonical_memory_id
    if poison_memory_id is None:
        raise RuntimeError("Sleeper injection was not admitted (scripted KEEP gate) -- a real environment problem.")

    selected_by_condition: Dict[str, bool] = {}
    retrieved_by_condition: Dict[str, Tuple[str, ...]] = {}
    for name, query in TRIGGER_CONDITIONS:
        retrieved, selected = _real_retrieve_then_select(foundation, query, top_k=top_k)
        retrieved_by_condition[name] = retrieved
        selected_by_condition[name] = poison_memory_id in selected

    discriminates = (
        selected_by_condition.get("exact") and selected_by_condition.get("paraphrased")
        and selected_by_condition.get("near") and selected_by_condition.get("partial")
        and not selected_by_condition.get("distant")
    )

    return SleeperRealRetrievalResult(
        poison_memory_id=poison_memory_id, selected_by_condition=selected_by_condition,
        retrieved_by_condition=retrieved_by_condition, discriminates=bool(discriminates),
    )


__all__ = [
    "is_real_mem0_available",
    "AgentPoisonRealRetrievalResult", "run_agentpoison_real_retrieval_study",
    "SleeperRealRetrievalResult", "run_sleeper_real_retrieval_study",
]
