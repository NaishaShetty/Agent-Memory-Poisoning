"""Phase 4 -- MAMBench scenario inspired by MPBench's taxonomy, Milestone 4:
isolated injection + retrieval dry run (no campaign, no LLM generation).

Mirrors the pattern of every other 4.3/4.4 plan's Milestone 4: write the
three PCFI scenarios into a real, isolated Mem0 test pool alongside the
real 17-turn LoCoMo benign pool, and check whether V3-Hybrid's actual
`select_by_hybrid_score` rerank surfaces each scenario's fact for its own
target query -- MPBench's write-phase/ASR analogue in isolation, before
generation.

MUST RUN INSIDE C:\\h4venv (mem0ai is only importable there). No LLM
server needed.
"""

from __future__ import annotations

import sys
from typing import List, Tuple

from phase3.evaluation.foundations.adapter import FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL
from phase3.evaluation.foundations.hybrid_selection import DEFAULT_TOP_K, RETRIEVAL_POOL_SIZE_N, select_by_hybrid_score
from phase3.evaluation.foundations_real.mem0_real_adapter import RealMem0Adapter

from phase4.attacks.agentpoison.locomo_pool import load_db_locomo
from phase4.attacks.mpbench.injector import ADMISSION_ADMITTED, MPBenchPCFIInjector
from phase4.attacks.mpbench.scenario import PCFI_SCENARIOS

USER_ID = "mpbench-pcfi-milestone4"


def _extract_content_text(native) -> str:
    if isinstance(native, dict):
        return native.get("memory") or native.get("text") or ""
    return ""


def main() -> int:
    foundation = RealMem0Adapter()
    init_field = foundation.initialize({})
    if init_field.availability != FOUNDATION_AVAILABLE:
        print(f"RealMem0Adapter failed to initialize: {init_field.note}", file=sys.stderr)
        return 1
    foundation.reset()

    real_pool = load_db_locomo(max_turns=17)
    print(f"Ingesting {len(real_pool)} real LoCoMo turns (task 0, sessions 1-2)...")
    for text in real_pool:
        foundation.add_memory(
            memory_id=None,
            content={"text": text, "content_type": "CONVERSATIONAL_FACT"},
            metadata={"user_id": USER_ID},
        )

    injector = MPBenchPCFIInjector(foundation)
    results = injector.inject_many(PCFI_SCENARIOS, extra_metadata={"user_id": USER_ID})
    assert all(r.admission_status == ADMISSION_ADMITTED for r in results)
    id_by_scenario = {s.scenario_id: r.canonical_memory_id for s, r in zip(PCFI_SCENARIOS, results)}
    print(f"Injected {len(results)} PCFI scenarios.\n")

    for scenario in PCFI_SCENARIOS:
        print("=" * 100)
        print(f"SCENARIO: {scenario.scenario_id}")
        print(f"Query: {scenario.retrieval_query!r}")
        print(f"Injected fact: {scenario.context!r}")
        print("=" * 100)

        retrieve_field = foundation.retrieve({"text": scenario.retrieval_query, "user_id": USER_ID}, top_k=RETRIEVAL_POOL_SIZE_N)
        raw_ids: List[str] = list(retrieve_field.value or [])
        candidates: List[Tuple[str, str]] = []
        for mid in raw_ids:
            inspect_field = foundation.inspect_memory(mid)
            if inspect_field.availability in (FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL):
                candidates.append((mid, _extract_content_text(inspect_field.value or {})))

        sel = select_by_hybrid_score(scenario.retrieval_query, candidates, top_k=DEFAULT_TOP_K)
        selected_ids = [c.memory_id for c in sel.selected]
        this_scenario_mid = id_by_scenario[scenario.scenario_id]
        selected = this_scenario_mid in selected_ids

        print(f"Selected (top-8): {selected_ids}")
        print(f"This scenario's fact selected (write-phase/ASR analogue): {selected}\n")

    foundation.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
