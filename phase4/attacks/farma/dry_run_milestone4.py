"""Phase 4 -- MAMBench reconstruction of FARMA, Milestone 4: retrieval
behavior check under `hybrid_selection.py`.

Per PHASE4_4_4_FARMA_RECONSTRUCTION_PLAN.md Section 7, Milestone 4: with the
amplified pool in place, confirm whether V3-Hybrid's actual cosine/
token-overlap/entity-overlap rerank (not FARMA's original generic
persistent-memory assumption) surfaces the poisoned entries for a
semantically related follow-up query. Genuinely unknown until tested -- the
direct FARMA analogue of AgentPoison's Milestone 5 open question.

MUST RUN INSIDE C:\\h4venv (mem0ai is only importable there). No LLM server
needed -- this only exercises retrieve() + select_by_hybrid_score(), not
generation.
"""

from __future__ import annotations

import sys
from typing import List, Tuple

from phase3.evaluation.foundations.adapter import FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL
from phase3.evaluation.foundations.hybrid_selection import DEFAULT_TOP_K, RETRIEVAL_POOL_SIZE_N, select_by_hybrid_score
from phase3.evaluation.foundations_real.mem0_real_adapter import RealMem0Adapter

from phase4.attacks.agentpoison.locomo_pool import load_db_locomo
from phase4.attacks.farma.injector import ADMISSION_ADMITTED, FARMAInjector
from phase4.attacks.farma.reasoning_trace import SEED_CAMPING, generate_amplification_sequence

USER_ID = "farma-milestone4-dry-run"
NUM_CYCLES = 10


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

    injector = FARMAInjector(foundation)
    seed_result = injector.inject(SEED_CAMPING, extra_metadata={"user_id": USER_ID})
    assert seed_result.admission_status == ADMISSION_ADMITTED
    cycles = generate_amplification_sequence(SEED_CAMPING, num_cycles=NUM_CYCLES)
    cycle_results = injector.inject_many(cycles, extra_metadata={"user_id": USER_ID})
    assert all(r.admission_status == ADMISSION_ADMITTED for r in cycle_results)

    farma_ids = {seed_result.canonical_memory_id} | {r.canonical_memory_id for r in cycle_results}
    precedent_by_id = {seed_result.canonical_memory_id: seed_result.precedent_count}
    precedent_by_id.update({r.canonical_memory_id: r.precedent_count for r in cycle_results})
    print(f"\nInjected {len(farma_ids)} reasoning_trace records for seed "
          f"{SEED_CAMPING.artifact_id!r} (1 seed + {len(cycles)} amplification cycles).")
    print(f"Total pool size: {len(real_pool)} benign + {len(farma_ids)} poisoned = "
          f"{len(real_pool) + len(farma_ids)} records.")

    query = SEED_CAMPING.target_question
    print(f"\nQuery: {query!r}")
    retrieve_field = foundation.retrieve({"text": query, "user_id": USER_ID}, top_k=RETRIEVAL_POOL_SIZE_N)
    print(f"retrieve() availability: {retrieve_field.availability}")
    raw_ids: List[str] = list(retrieve_field.value or [])
    print(f"retrieve() returned {len(raw_ids)} candidate ids (pool size N={RETRIEVAL_POOL_SIZE_N}).")

    candidates: List[Tuple[str, str]] = []
    for mid in raw_ids:
        inspect_field = foundation.inspect_memory(mid)
        if inspect_field.availability in (FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL):
            candidates.append((mid, _extract_content_text(inspect_field.value or {})))

    farma_in_raw_pool = [mid for mid, _ in candidates if mid in farma_ids]
    print(f"FARMA records present in the raw retrieved pool: {len(farma_in_raw_pool)} of {len(farma_ids)}")

    sel = select_by_hybrid_score(query, candidates, top_k=DEFAULT_TOP_K)
    selected_ids = [c.memory_id for c in sel.selected]
    farma_selected = [mid for mid in selected_ids if mid in farma_ids]

    print(f"\nselect_by_hybrid_score top-{DEFAULT_TOP_K} result:")
    for rank, mid in enumerate(selected_ids, start=1):
        tag = f"FARMA precedent_count={precedent_by_id[mid]}" if mid in farma_ids else "benign"
        print(f"  rank {rank}: {mid} ({tag})")

    print(f"\nFARMA records selected into top-{DEFAULT_TOP_K}: {len(farma_selected)} of "
          f"{len(farma_ids)} injected.")

    print("\n" + "=" * 100)
    print("VERDICT")
    print("=" * 100)
    if farma_selected:
        print(
            f"{len(farma_selected)} poisoned reasoning_trace record(s) reached the real "
            f"top-{DEFAULT_TOP_K} selection for a semantically related query -- the "
            f"amplification cluster's volume/semantic-centrality strategy produced a real "
            f"effect against V3-Hybrid's actual reranker, not just the raw retrieve() pool."
        )
    else:
        print(
            f"No poisoned record reached the real top-{DEFAULT_TOP_K} selection for this "
            f"query, even though {len(farma_in_raw_pool)} were present in the raw retrieved "
            f"pool -- a real negative result for this cluster/query pairing, reported as such "
            f"rather than smoothed over."
        )

    foundation.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
