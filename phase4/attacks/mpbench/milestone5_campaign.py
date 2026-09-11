"""Phase 4 -- MAMBench scenario inspired by MPBench's taxonomy, Milestone 5:
real Condition C campaign + ASR/RSR-equivalent measurement.

Per PHASE4_4_5_MPBENCH_INTEGRATION_PLAN.md Section 5/7: reuse MPBench's own
two-phase ASR/RSR measurement model directly (dossier Section 3) --
POISON_ADMITTED/write-phase =~ ASR (Milestone 4 already confirmed this: all
3 scenarios' facts were admitted and retrieved), POISON_RETRIEVED_AND_
INFLUENCED =~ RSR (this milestone: does the retrieved fact actually change
the generated answer, confirmed via a real counterfactual mask, not mere
retrieval-behavior correlation, per Decision 4).

Each scenario injects a single fact (no seed+amplification, no
multi-artifact redundancy) -- single-mask counterfactual check per
scenario, same shape as AgentPoison's/DSRM's Milestone 5 campaigns.

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
from phase4.attacks.mpbench.injector import ADMISSION_ADMITTED, MPBenchPCFIInjector
from phase4.attacks.mpbench.scenario import PCFI_SCENARIOS
from phase4.shared.campaign_runner import retrieve_select_generate
from phase4.shared.dormancy_report import print_dormancy_report

USER_ID = "mpbench-pcfi-milestone5"



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
        temperature=0.0, seed=42, max_tokens=64, enable_thinking=False, n_ctx=4096,
    )
    run_config = RunConfiguration(
        llm_provider=llm_provider, generation_config=generation_config,
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

    injector = MPBenchPCFIInjector(foundation)
    results = injector.inject_many(PCFI_SCENARIOS, extra_metadata={"user_id": USER_ID})
    assert all(r.admission_status == ADMISSION_ADMITTED for r in results)
    id_by_scenario = {s.scenario_id: r.canonical_memory_id for s, r in zip(PCFI_SCENARIOS, results)}
    print(f"Injected {len(results)} PCFI scenarios (ASR analogue: 3/3 admitted).\n")

    asr_count = 0  # write-phase: admitted (already known 3/3 from injection)
    rsr_count = 0  # retrieval+influence: selected AND counterfactually influential

    for scenario in PCFI_SCENARIOS:
        print("=" * 100)
        print(f"SCENARIO: {scenario.scenario_id}")
        print(f"Query: {scenario.retrieval_query!r}")
        print(f"Real gold answer: {scenario.gold_answer!r}")
        print(f"Injected fact: {scenario.context!r}")
        print("=" * 100)

        baseline = retrieve_select_generate(
            foundation, scenario.retrieval_query, run_config,
            user_id=USER_ID, task_id=f"mpbench-pcfi-{scenario.scenario_id}",
        )
        this_mid = id_by_scenario[scenario.scenario_id]
        selected = this_mid in baseline.selected_memory_ids
        print(f"Selected (top-8): {baseline.selected_memory_ids}")
        print(f"Fact selected: {selected}")
        print(f"Baseline answer: {baseline.execution_result.answer!r}")
        print_dormancy_report(scenario.scenario_id, baseline, [this_mid])

        if not selected:
            print("Not selected -- no counterfactual check to run for this scenario.\n")
            continue

        masked = run_counterfactual_mask(baseline, this_mid, run_config)
        print(f"Masked-run answer: {masked.masked_answer!r}")
        comparison = compare_counterfactual_run(baseline, masked)
        print(f"Counterfactual status (RSR-conditioned causal check): {comparison.status}")
        if comparison.status == "COUNTERFACTUALLY_INFLUENTIAL":
            rsr_count += 1
        print()

    print("=" * 100)
    print("MPBench ASR/RSR-EQUIVALENT SUMMARY (this run only, n=3, not a claimed general rate)")
    print("=" * 100)
    print(f"ASR analogue (admitted to memory): 3/3")
    print(f"RSR analogue (selected AND counterfactually influential, per Decision 4's "
          f"interventional-dependence standard, not causal proof): {rsr_count}/3")
    print(
        "Per Decision 4 and the dossier's own author-disclosed caveat: these figures describe "
        "THIS run against THIS pool/model, not a general MAMBench PCFI success rate -- no "
        "inheritance of MPBench's own OpenClaw/HERMES/GPT-OSS-120B figures is implied or claimed."
    )

    foundation.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
