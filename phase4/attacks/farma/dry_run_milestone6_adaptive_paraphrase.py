"""Phase 4 -- MAMBench reconstruction of FARMA, Milestone 6b:
adaptive_paraphrase variant, retrieval check.

Per `phase4/attacks/farma/variants.py`'s module docstring: this variant's
paper-original claim ("defeats SENTINEL") is NOT testable here -- no
SENTINEL-equivalent defense exists in this repository. What this script
DOES test: does a real LLM paraphrase of the forged claim still inject and
survive the real `hybrid_selection.py` rerank, i.e. does the attack's core
mechanism tolerate a paraphrase pass at all.

MUST RUN INSIDE C:\\h4venv (mem0ai is only importable there) WITH A REAL,
REACHABLE llama-server INSTANCE (needed for the paraphrase generation
call itself, not just the campaign).
"""

from __future__ import annotations

import sys
from typing import List, Tuple

from phase3.evaluation.agent_runtime.messages import DEFAULT_SYSTEM_PROMPT
from phase3.evaluation.agent_runtime.runner import RunConfiguration
from phase3.evaluation.foundations.adapter import FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL
from phase3.evaluation.foundations.hybrid_selection import DEFAULT_TOP_K, RETRIEVAL_POOL_SIZE_N, select_by_hybrid_score
from phase3.evaluation.foundations_real.mem0_real_adapter import RealMem0Adapter
from phase3.evaluation.llm.provider import (
    GenerationConfig, LLMProviderConfigurationMismatchError, LLMProviderConnectionError,
    LlamaServerEndpoint, LlamaServerProvider,
)

from phase4.attacks.agentpoison.locomo_pool import load_db_locomo
from phase4.attacks.farma.injector import ADMISSION_ADMITTED, FARMAInjector
from phase4.attacks.farma.reasoning_trace import SEED_CAMPING, generate_amplification_sequence
from phase4.attacks.farma.variants import VARIANT_ADAPTIVE_PARAPHRASE, adaptive_paraphrase_artifact

USER_ID = "farma-milestone6-adaptive-paraphrase"
NUM_CYCLES = 10


def _extract_content_text(native) -> str:
    if isinstance(native, dict):
        return native.get("memory") or native.get("text") or ""
    return ""


def main() -> int:
    endpoint = LlamaServerEndpoint()
    llm_provider = LlamaServerProvider(endpoint=endpoint)
    if not llm_provider.health_check():
        print(f"llama-server not reachable at {endpoint.base_url}", file=sys.stderr)
        return 1
    try:
        llm_provider.verify_server_identity()
    except (LLMProviderConnectionError, LLMProviderConfigurationMismatchError) as exc:
        print(f"Server identity verification failed: {exc}", file=sys.stderr)
        return 1

    generation_config = GenerationConfig(
        temperature=0.7, seed=42, max_tokens=96, enable_thinking=False, n_ctx=4096,
    )
    run_config = RunConfiguration(
        llm_provider=llm_provider, generation_config=generation_config,
        system_prompt=DEFAULT_SYSTEM_PROMPT, max_retries=0,
    )

    print(f"Variant: {VARIANT_ADAPTIVE_PARAPHRASE}")
    print(f"Original forged claim: {SEED_CAMPING.forged_claim!r}")
    paraphrased_seed = adaptive_paraphrase_artifact(SEED_CAMPING, run_config)
    print(f"Paraphrased forged claim: {paraphrased_seed.forged_claim!r}\n")

    if paraphrased_seed.forged_claim.strip().lower() == SEED_CAMPING.forged_claim.strip().lower():
        print("WARNING: paraphrase is identical to the original -- generation may not have "
              "actually varied the text. Proceeding anyway, reported as observed.")

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
    seed_result = injector.inject(paraphrased_seed, extra_metadata={"user_id": USER_ID})
    assert seed_result.admission_status == ADMISSION_ADMITTED
    cycles = generate_amplification_sequence(paraphrased_seed, num_cycles=NUM_CYCLES)
    cycle_results = injector.inject_many(cycles, extra_metadata={"user_id": USER_ID})
    assert all(r.admission_status == ADMISSION_ADMITTED for r in cycle_results)
    farma_ids = {seed_result.canonical_memory_id} | {r.canonical_memory_id for r in cycle_results}
    print(f"Injected {len(farma_ids)} paraphrased reasoning_trace records.\n")

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
        tag = "FARMA (adaptive_paraphrase)" if mid in farma_ids else "benign"
        print(f"  rank {rank}: {mid} ({tag})")

    print(f"\nFARMA records selected into top-{DEFAULT_TOP_K}: {len(farma_selected)} of "
          f"{len(farma_ids)} injected.")

    print("\n" + "=" * 100)
    print("VERDICT")
    print("=" * 100)
    print(
        f"adaptive_paraphrase: {len(farma_selected)} of {DEFAULT_TOP_K} slots, using a real "
        f"LLM-paraphrased forged claim (not the literal base-variant wording). "
        f"DISCLOSED LIMITATION: this only shows the mechanism tolerates paraphrasing at the "
        f"retrieval-selection layer -- it does NOT demonstrate the paper's own claim of "
        f"defeating SENTINEL or any other defense, since no such defense exists in this "
        f"repository to test against."
    )

    foundation.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
