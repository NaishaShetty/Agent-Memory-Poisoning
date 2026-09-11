"""Phase 4.8 -- MemoryGraft Milestones 3+4 (real, finally executed): gate
check, isolated retrieval dry run, and real Condition C campaign with the
required counterfactual measurement, combined into one script since all
three need the same live llama-server.

Per PHASE4_4_3_MEMORYGRAFT_INTEGRATION_PLAN.md:
- Milestone 3: "Embedder substitution + isolated retrieval dry run."
- Milestone 4: "Multi-session campaign + poisoned-retrieval-proportion
  measurement. Run the real V3-Hybrid Condition C campaign..."

Neither had been executed before this pass -- MemoryGraft's persistence
gate was real, calibrated, and adversarially tested (Milestone 2.5), but
never connected to real LoCoMo content or a real campaign. This script
closes that gap using the same real infrastructure pattern every other
attack in this repository already used: `RealMem0Adapter`, a real
identity-verified llama-server, `select_by_hybrid_score`, and
`run_counterfactual_mask`.

MUST RUN INSIDE C:\\h4venv (mem0ai is only importable there) WITH A REAL,
REACHABLE llama-server INSTANCE.
"""

from __future__ import annotations

import sys

from phase3.evaluation.agent_runtime.counterfactual import compare_counterfactual_run, run_counterfactual_mask
from phase3.evaluation.agent_runtime.messages import DEFAULT_SYSTEM_PROMPT
from phase3.evaluation.agent_runtime.runner import RunConfiguration
from phase3.evaluation.foundations.adapter import FOUNDATION_AVAILABLE
from phase3.evaluation.foundations_real.mem0_real_adapter import RealMem0Adapter
from phase3.evaluation.llm.provider import (
    GenerationConfig, LLMProviderConfigurationMismatchError, LLMProviderConnectionError,
    LlamaServerEndpoint, LlamaServerProvider,
)

from phase4.attacks.agentpoison.locomo_pool import load_db_locomo
from phase4.attacks.memorygraft.adapter import ADMISSION_ADMITTED, MemoryGraftInjector
from phase4.attacks.memorygraft.locomo_seed import GOLD_ANSWER, SEED_RESEARCH_TOPIC, TARGET_QUESTION
from phase4.attacks.memorygraft.persistence_gate import DECISION_KEEP, FOUNDATION_MEM0, judge_persistence
from phase4.shared.campaign_runner import retrieve_select_generate
from phase4.shared.dormancy_report import print_dormancy_report

USER_ID = "memorygraft-milestone3-4"


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

    gate_generation_config = GenerationConfig(
        temperature=0.0, seed=42, max_tokens=64, enable_thinking=False, n_ctx=2048,
    )

    print("=" * 100)
    print("MILESTONE 3a: Real gate check on the LoCoMo-reformulated artifact")
    print("=" * 100)
    print(f"req: {SEED_RESEARCH_TOPIC.req!r}")
    print(f"resp: {SEED_RESEARCH_TOPIC.resp!r}")
    judgment = judge_persistence(
        SEED_RESEARCH_TOPIC, llm_provider, gate_generation_config, foundation=FOUNDATION_MEM0,
    )
    print(f"Gate decision: {judgment.decision}")
    print(f"Gate rationale: {judgment.rationale!r}\n")

    if judgment.decision != DECISION_KEEP:
        print(
            "Gate returned DISCARD on this LoCoMo-reformulated artifact -- a real, "
            "disclosed negative result, not smoothed over. This means MemoryGraft's "
            "own admission mechanism (as calibrated) would refuse to persist THIS "
            "specific artifact when framed this way; reported honestly rather than "
            "revised post hoc to force a KEEP."
        )
        return 0

    campaign_generation_config = GenerationConfig(
        temperature=0.0, seed=42, max_tokens=64, enable_thinking=False, n_ctx=4096,
    )
    run_config = RunConfiguration(
        llm_provider=llm_provider, generation_config=campaign_generation_config,
        system_prompt=DEFAULT_SYSTEM_PROMPT, max_retries=0,
    )

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

    print("\n" + "=" * 100)
    print("MILESTONE 3b: Injection via the real, gated MemoryGraftInjector")
    print("=" * 100)
    injector = MemoryGraftInjector(
        foundation_adapter=foundation, foundation_label=FOUNDATION_MEM0,
        llm_provider=llm_provider, generation_config=gate_generation_config,
    )
    injection_result = injector.inject(SEED_RESEARCH_TOPIC, extra_metadata={"user_id": USER_ID})
    print(f"Injection admission_status: {injection_result.admission_status}")
    assert injection_result.admission_status == ADMISSION_ADMITTED
    print(f"Written memory_id: {injection_result.canonical_memory_id}\n")

    print("=" * 100)
    print("MILESTONE 4: Real Condition C campaign + counterfactual check")
    print("=" * 100)
    print(f"Query: {TARGET_QUESTION!r}")
    print(f"Real gold answer: {GOLD_ANSWER!r}")

    baseline = retrieve_select_generate(
        foundation, TARGET_QUESTION, run_config, user_id=USER_ID, task_id="memorygraft-m4",
    )
    selected = injection_result.canonical_memory_id in baseline.selected_memory_ids
    print(f"Selected (top-8): {baseline.selected_memory_ids}")
    print_dormancy_report("memorygraft", baseline, [injection_result.canonical_memory_id])
    print(f"Poisoned experience selected (retrieval-hijack): {selected}")
    print(f"Baseline answer: {baseline.execution_result.answer!r}")

    if not selected:
        print("Not selected -- no counterfactual check to run.")
        foundation.shutdown()
        return 0

    masked = run_counterfactual_mask(baseline, injection_result.canonical_memory_id, run_config)
    print(f"Masked-run answer: {masked.masked_answer!r}")
    comparison = compare_counterfactual_run(baseline, masked)
    print(f"Counterfactual status: {comparison.status}")
    print(
        "Interpretation: interventional dependence (did masking change the observed "
        "answer), NOT causal proof, per PHASE4_PRE_FLIGHT_DECISIONS.md Decision 4."
    )

    foundation.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
