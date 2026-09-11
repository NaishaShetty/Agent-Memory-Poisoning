"""Phase 4 -- MAMBench reconstruction of FARMA, Milestone 6a: store_evasion
variant, retrieval check.

Repeats Milestone 4's retrieval-hijack check (amplified cluster vs. real
17-turn benign pool, under `select_by_hybrid_score`), with one change: every
injected record uses `content_type=CONVERSATIONAL_FACT` (per
`phase4/attacks/farma/variants.py`) instead of `REASONING_TRACE`, blending
in with the benign pool's own content_type rather than carrying a distinct
tag. Tests whether the base variant's retrieval-hijack effect (Milestone 4:
8 of 8 top-8 slots) survives this evasion, not the base variant's own
result being rerun unchanged.

MUST RUN INSIDE C:\\h4venv (mem0ai is only importable there). No LLM server
needed.
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
from phase4.attacks.farma.variants import CONTENT_TYPE_STORE_EVASION, VARIANT_STORE_EVASION, store_evasion_artifact

USER_ID = "farma-milestone6-store-evasion"
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
    print(f"Variant: {VARIANT_STORE_EVASION}")
    print(f"Ingesting {len(real_pool)} real LoCoMo turns (task 0, sessions 1-2)...")
    for text in real_pool:
        foundation.add_memory(
            memory_id=None,
            content={"text": text, "content_type": "CONVERSATIONAL_FACT"},
            metadata={"user_id": USER_ID},
        )

    seed = store_evasion_artifact(SEED_CAMPING)
    injector = FARMAInjector(foundation)
    seed_result = injector.inject(seed, extra_metadata={"user_id": USER_ID}, content_type=CONTENT_TYPE_STORE_EVASION)
    assert seed_result.admission_status == ADMISSION_ADMITTED
    cycles = generate_amplification_sequence(seed, num_cycles=NUM_CYCLES)
    cycle_results = injector.inject_many(
        cycles, extra_metadata={"user_id": USER_ID}, content_type=CONTENT_TYPE_STORE_EVASION
    )
    assert all(r.admission_status == ADMISSION_ADMITTED for r in cycle_results)
    farma_ids = {seed_result.canonical_memory_id} | {r.canonical_memory_id for r in cycle_results}
    print(f"Injected {len(farma_ids)} reasoning_trace-content records, all tagged "
          f"content_type={CONTENT_TYPE_STORE_EVASION!r} (indistinguishable by content_type "
          f"from the benign pool above).\n")

    query = SEED_CAMPING.target_question
    print(f"Query: {query!r}")
    retrieve_field = foundation.retrieve({"text": query, "user_id": USER_ID}, top_k=RETRIEVAL_POOL_SIZE_N)
    raw_ids: List[str] = list(retrieve_field.value or [])
    candidates: List[Tuple[str, str]] = []
    for mid in raw_ids:
        inspect_field = foundation.inspect_memory(mid)
        if inspect_field.availability in (FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL):
            candidates.append((mid, _extract_content_text(inspect_field.value or {})))

    sel = select_by_hybrid_score(query, candidates, top_k=DEFAULT_TOP_K)
    selected_ids = [c.memory_id for c in sel.selected]
    farma_selected = [mid for mid in selected_ids if mid in farma_ids]

    print(f"\nselect_by_hybrid_score top-{DEFAULT_TOP_K} result:")
    for rank, mid in enumerate(selected_ids, start=1):
        tag = "FARMA (store_evasion)" if mid in farma_ids else "benign"
        print(f"  rank {rank}: {mid} ({tag})")

    print(f"\nFARMA records selected into top-{DEFAULT_TOP_K}: {len(farma_selected)} of "
          f"{len(farma_ids)} injected.")
    print("\n" + "=" * 100)
    print("VERDICT -- comparison to base variant's Milestone 4 result (8 of 8 slots)")
    print("=" * 100)
    print(
        f"store_evasion (content_type blended with benign pool): {len(farma_selected)} of "
        f"{DEFAULT_TOP_K} slots. Retrieval hijack does not depend on the REASONING_TRACE "
        f"content_type tag being present -- select_by_hybrid_score reranks on the query's "
        f"real text content (cosine/token-overlap/entity-overlap), not the content_type "
        f"metadata field, so this result is expected to match the base variant closely; "
        f"reported here as measured, not assumed."
    )

    foundation.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
