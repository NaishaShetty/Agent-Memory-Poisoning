"""Phase 4 -- MAMBench reconstruction of DSRM, Milestones 2+3: real SRM
convergence dry run and real CSRM justification dry run, combined into one
script since both need the same live llama-server and this milestone pair
does no memory write (isolated from Milestone 4's real injection).

Milestone 2: for each of the 3 Milestone-1 seeds, run the real Self-Refine
loop (real LLM + real MiniLM/BERT embedder matching Mem0's own convention)
and report whether/how it converges to tau=0.6 -- reported as observed, not
assumed to succeed.

Milestone 3: for each seed, run the real CSRM justification generation and
print the parsed 3-step result for manual plausibility inspection.

No memory store involved -- MUST still run inside C:\\h4venv is NOT required
here (no mem0ai import), but DOES require a real, reachable llama-server for
both SRM's refinement calls and CSRM's justification call.
"""

from __future__ import annotations

import sys

from phase3.evaluation.agent_runtime.messages import DEFAULT_SYSTEM_PROMPT
from phase3.evaluation.agent_runtime.runner import RunConfiguration
from phase3.evaluation.llm.provider import (
    GenerationConfig, LLMProviderConfigurationMismatchError, LLMProviderConnectionError,
    LlamaServerEndpoint, LlamaServerProvider,
)

from phase4.attacks.dsrm.csrm import generate_csrm_justification
from phase4.attacks.dsrm.seeds import DSRM_SEEDS
from phase4.attacks.dsrm.srm import _Embedder, run_self_refine


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

    print("Loading real MiniLM/BERT embedder (matches Mem0's own convention, per AgentPoison Milestone 1)...")
    embedder = _Embedder()

    for seed in DSRM_SEEDS:
        print("=" * 100)
        print(f"SEED: {seed.seed_id}")
        print(f"Target question: {seed.target_question!r}")
        print(f"Gold answer: {seed.gold_answer!r}")
        print(f"Forged claim: {seed.forged_claim!r}")
        print("=" * 100)

        print("\n--- Milestone 2: SRM ---")
        srm_result = run_self_refine(
            target_query=seed.target_question,
            initial_planning_text=seed.initial_planning_text,
            run_config=run_config,
            embedder=embedder,
            tau=0.6,
            max_iterations=5,
        )
        for h in srm_result.history:
            print(f"  iteration {h.iteration}: similarity={h.similarity:.4f}  text={h.planning_text!r}")
        print(f"Converged: {srm_result.converged} (tau=0.6, {srm_result.iterations_used} refinement "
              f"iterations, final similarity={srm_result.final_similarity:.4f})")

        print("\n--- Milestone 3: CSRM ---")
        justification = generate_csrm_justification(seed.target_question, seed.forged_claim, run_config)
        print(f"  why_applies:     {justification.why_applies!r}")
        print(f"  why_effective:   {justification.why_effective!r}")
        print(f"  expected_impact: {justification.expected_impact!r}")
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
