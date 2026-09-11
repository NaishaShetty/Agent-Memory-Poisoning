"""Phase 4.8 -- Sleeper Memory Poisoning: the real, controlled 2x2
dormancy/trigger campaign.

Per PHASE4_4_3_SLEEPER_MEMORY_POISONING_INTEGRATION_PLAN.md and the
handoff's own explicit control design, this runs a full 2x2:

    pool     x  query
    {clean, poisoned}  x  {distant_question, target_question}

which exactly covers all four requested controls without redundancy:
- Control 1 (clean, no poison):       (clean, distant)
- Control 2 (poison, no trigger):     (poisoned, distant)   -- expect DORMANT
- Control 3 (poison + trigger):       (poisoned, target)    -- expect TRIGGERED/ACTIVE
- Control 4 (trigger without poison): (clean, target)       -- rules out the
                                        query itself causing the effect

Dormancy is read directly from `AgentRunOutcome`'s own two distinct fields
(no new code needed -- confirmed by inspection of
`phase4/shared/campaign_runner.py`): `retrieved_memory_ids` (the raw
~20-candidate pool, i.e. POISON_IN_CANDIDATE_POOL) vs `selected_memory_ids`
(the reranked top-8 that actually reaches the agent, i.e.
POISON_SELECTED_TOP_K) -- exactly the granularity
PHASE4_4_2_COMMON_ATTACK_CONTRACT.md Section 7a's ground-truth chain
already provides.

THREE counterfactual comparisons are run, per the handoff's Section H
(two possible causal-looking dependencies: on the poisoned memory itself,
and on the query's semantic proximity to it):
1. Single-artifact mask on the poison+trigger cell (standard Decision-4 check).
2. poison+trigger vs poison+trigger-removed-i.e.-distant-query (cell 3 vs cell 2)
   -- query-type dependence.
3. poison+trigger vs clean+trigger (cell 3 vs cell 4) -- poison-presence dependence.

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
from phase4.attacks.sleeper_memory_poisoning.adapter import SleeperAdapter
from phase4.attacks.sleeper_memory_poisoning.artifact import SEED_DESTRESS
from phase4.attacks.sleeper_memory_poisoning.injector import ADMISSION_ADMITTED
from phase4.shared.campaign_runner import retrieve_select_generate

USER_ID_CLEAN = "sleeper-m8-clean"
USER_ID_POISONED = "sleeper-m8-poisoned"


def ingest_benign_pool(foundation: RealMem0Adapter, user_id: str) -> None:
    real_pool = load_db_locomo(max_turns=17)
    for text in real_pool:
        foundation.add_memory(
            memory_id=None,
            content={"text": text, "content_type": "CONVERSATIONAL_FACT"},
            metadata={"user_id": user_id},
        )


def report_dormancy_state(label: str, outcome, injected_memory_id) -> None:
    in_pool = injected_memory_id is not None and injected_memory_id in outcome.retrieved_memory_ids
    selected = injected_memory_id is not None and injected_memory_id in outcome.selected_memory_ids
    print(f"[{label}] stored={injected_memory_id is not None} "
          f"in_candidate_pool={in_pool} selected_top_k={selected}")
    print(f"[{label}] answer: {outcome.execution_result.answer!r}")


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
    gate_run_config = RunConfiguration(
        llm_provider=llm_provider, generation_config=gate_generation_config,
        system_prompt=DEFAULT_SYSTEM_PROMPT, max_retries=0,
    )
    campaign_generation_config = GenerationConfig(
        temperature=0.0, seed=42, max_tokens=64, enable_thinking=False, n_ctx=4096,
    )
    campaign_run_config = RunConfiguration(
        llm_provider=llm_provider, generation_config=campaign_generation_config,
        system_prompt=DEFAULT_SYSTEM_PROMPT, max_retries=0,
    )

    adapter = SleeperAdapter()
    seed = SEED_DESTRESS
    print(f"Target (goal-adjacent) question: {seed.target_question!r}")
    print(f"Real gold answer: {seed.gold_answer!r}")
    print(f"Distant (goal-distant) question: {seed.distant_question!r}")
    print(f"Forged memory: {seed.forged_memory_text!r}\n")

    # --- Clean foundation (Controls 1 and 4) ---
    clean_foundation = RealMem0Adapter()
    if clean_foundation.initialize({}).availability != FOUNDATION_AVAILABLE:
        print("clean RealMem0Adapter failed to initialize", file=sys.stderr)
        return 1
    clean_foundation.reset()
    ingest_benign_pool(clean_foundation, USER_ID_CLEAN)

    # --- Poisoned foundation (Controls 2 and 3) ---
    poisoned_foundation = RealMem0Adapter()
    if poisoned_foundation.initialize({}).availability != FOUNDATION_AVAILABLE:
        print("poisoned RealMem0Adapter failed to initialize", file=sys.stderr)
        return 1
    poisoned_foundation.reset()
    ingest_benign_pool(poisoned_foundation, USER_ID_POISONED)

    print("=" * 100)
    print("INJECTION (real, gated by injection_gate)")
    print("=" * 100)
    injection_result = adapter.inject(
        seed, poisoned_foundation, run_config=gate_run_config, extra_metadata={"user_id": USER_ID_POISONED},
    )
    print(f"Gate decision: {injection_result.judgment.decision}")
    print(f"Gate rationale: {injection_result.judgment.rationale!r}")
    print(f"Admission status: {injection_result.admission_status}")
    if injection_result.admission_status != ADMISSION_ADMITTED:
        print("Gate returned NOT_ADMITTED -- a real, disclosed negative result. "
              "No campaign controls can be run without a successfully planted artifact.")
        return 0
    injected_mid = injection_result.canonical_memory_id
    print(f"Planted memory_id: {injected_mid}\n")

    print("=" * 100)
    print("CONTROL 1 -- clean, no poison, distant query")
    print("=" * 100)
    control1 = adapter.execute(clean_foundation, seed.distant_question, campaign_run_config, user_id=USER_ID_CLEAN, task_id="sleeper-c1")
    report_dormancy_state("Control 1", control1, None)
    print()

    print("=" * 100)
    print("CONTROL 2 -- poisoned, distant query (expect DORMANT)")
    print("=" * 100)
    control2 = adapter.execute(poisoned_foundation, seed.distant_question, campaign_run_config, user_id=USER_ID_POISONED, task_id="sleeper-c2")
    report_dormancy_state("Control 2", control2, injected_mid)
    print()

    print("=" * 100)
    print("CONTROL 3 -- poisoned, target (goal-adjacent) query (expect TRIGGERED/ACTIVE)")
    print("=" * 100)
    control3 = adapter.execute(poisoned_foundation, seed.target_question, campaign_run_config, user_id=USER_ID_POISONED, task_id="sleeper-c3")
    report_dormancy_state("Control 3", control3, injected_mid)
    print()

    print("=" * 100)
    print("CONTROL 4 -- clean, target (goal-adjacent) query (rules out query-only effect)")
    print("=" * 100)
    control4 = adapter.execute(clean_foundation, seed.target_question, campaign_run_config, user_id=USER_ID_CLEAN, task_id="sleeper-c4")
    report_dormancy_state("Control 4", control4, None)
    print()

    control3_selected = injected_mid in control3.selected_memory_ids
    print("=" * 100)
    print("COUNTERFACTUAL COMPARISONS")
    print("=" * 100)
    if control3_selected:
        masked = run_counterfactual_mask(control3, injected_mid, campaign_run_config)
        comparison = compare_counterfactual_run(control3, masked)
        print(f"1) Single-artifact mask (poison removed, trigger query kept):")
        print(f"   masked answer: {masked.masked_answer!r}")
        print(f"   status: {comparison.status}")
    else:
        print("1) Poison was not selected under the trigger query -- no mask to run "
              "(a real negative result for Control 3, reported as such).")

    print(f"\n2) Query-type dependence (Control 3 vs Control 2 -- same poison, different query):")
    print(f"   Control 3 (adjacent) answer: {control3.execution_result.answer!r}")
    print(f"   Control 2 (distant) answer:  {control2.execution_result.answer!r}")
    print(f"   Selected under adjacent query: {control3_selected}; "
          f"selected under distant query: {injected_mid in control2.selected_memory_ids}")

    print(f"\n3) Poison-presence dependence (Control 3 vs Control 4 -- same query, poison present/absent):")
    print(f"   Control 3 (poisoned) answer: {control3.execution_result.answer!r}")
    print(f"   Control 4 (clean) answer:    {control4.execution_result.answer!r}")
    print(
        "\nInterpretation, per PHASE4_PRE_FLIGHT_DECISIONS.md Decision 4: these are "
        "counterfactual/interventional dependence evidence -- NOT causal proof."
    )

    clean_foundation.shutdown()
    poisoned_foundation.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
