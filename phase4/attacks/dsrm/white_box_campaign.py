"""Phase 4 gap-closing -- DSRM's white-box variant, carried into a real
injection + campaign + counterfactual check (was previously left at
Milestone 5's real optimization result only -- see
PHASE4_4_4_DSRM_RECONSTRUCTION_PLAN.md Section 6, Milestone 5's own text:
"Not carried further into an actual injection+campaign run in this pass").

Reuses the real optimize_retrieval_text() output directly (not
re-optimized here) as the `retrieval_text` of an `AdversarialDecisionArtifact`
whose forged claim / CSRM justification are otherwise identical to the
black-box campaign's own (SEED_POTTERY) -- isolating the ONE real
variable this milestone is actually about: does a gradient-optimized
retrieval string out-hijack retrieval relative to black-box's simple
Q-plus-claim concatenation, against the exact same target content.

MUST RUN INSIDE C:\\h4venv (mem0ai only importable there) WITH A REAL,
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
from phase4.attacks.dsrm.csrm import generate_csrm_justification
from phase4.attacks.dsrm.decision import AdversarialDecisionArtifact
from phase4.attacks.dsrm.injector import ADMISSION_ADMITTED, DSRMInjector
from phase4.attacks.dsrm.seeds import SEED_POTTERY
from phase4.attacks.dsrm.white_box import optimize_retrieval_text
from phase4.shared.campaign_runner import retrieve_select_generate
from phase4.shared.dormancy_report import print_dormancy_report

USER_ID = "dsrm-white-box-campaign"


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

    print("Running real white-box retrieval-text optimization (reuses Milestone 5's "
          "optimize_retrieval_text(), not re-implemented)...")
    negative_queries = ["When did Melanie go to the museum?", "When did Caroline have a picnic?"]
    wb_result = optimize_retrieval_text(
        positive_query=SEED_POTTERY.target_question,
        negative_queries=negative_queries,
        num_adv_tokens=6, num_iter=15, num_cand=40,
    )
    print(f"Optimized retrieval text: {wb_result.retrieval_text!r}")
    print(f"InfoNCE loss: {wb_result.loss_initial:.4f} -> {wb_result.loss_final:.4f}\n")

    gate_generation_config = GenerationConfig(
        temperature=0.7, seed=42, max_tokens=320, enable_thinking=False, n_ctx=4096,
    )
    gate_run_config = RunConfiguration(
        llm_provider=llm_provider, generation_config=gate_generation_config,
        system_prompt=DEFAULT_SYSTEM_PROMPT, max_retries=0,
    )
    print("Generating a real CSRM justification for the white-box artifact...")
    justification = generate_csrm_justification(SEED_POTTERY.target_question, SEED_POTTERY.forged_claim, gate_run_config)
    print(f"CSRM: {justification.render()!r}\n")

    white_box_artifact = AdversarialDecisionArtifact(
        artifact_id="dsrm_white_box_pottery",
        task_id=SEED_POTTERY.task_id,
        target_question=SEED_POTTERY.target_question,
        gold_answer=SEED_POTTERY.gold_answer,
        forged_claim=SEED_POTTERY.forged_claim,
        planning_text=SEED_POTTERY.initial_planning_text,  # not SRM-refined here -- white-box's real
        initial_planning_text=SEED_POTTERY.initial_planning_text,  # variable is the retrieval text, not planning text
        csrm_justification=justification,
        srm_iterations_used=0,
        srm_converged=False,
        srm_final_similarity=0.0,
        variant="white_box",
        retrieval_text=wb_result.retrieval_text,
    )

    campaign_generation_config = GenerationConfig(
        temperature=0.0, seed=42, max_tokens=64, enable_thinking=False, n_ctx=4096,
    )
    campaign_run_config = RunConfiguration(
        llm_provider=llm_provider, generation_config=campaign_generation_config,
        system_prompt=DEFAULT_SYSTEM_PROMPT, max_retries=0,
    )

    foundation = RealMem0Adapter()
    if foundation.initialize({}).availability != FOUNDATION_AVAILABLE:
        print("RealMem0Adapter failed to initialize", file=sys.stderr)
        return 1
    foundation.reset()

    real_pool = load_db_locomo(max_turns=17)
    for text in real_pool:
        foundation.add_memory(
            memory_id=None, content={"text": text, "content_type": "CONVERSATIONAL_FACT"},
            metadata={"user_id": USER_ID},
        )

    injector = DSRMInjector(foundation)
    inject_result = injector.inject(white_box_artifact, extra_metadata={"user_id": USER_ID})
    print(f"Injection admission_status: {inject_result.admission_status}")
    assert inject_result.admission_status == ADMISSION_ADMITTED
    print(f"Injected white-box decision as memory_id={inject_result.canonical_memory_id!r}\n")

    query = SEED_POTTERY.target_question
    print(f"Victim query: {query!r}")
    print(f"Real gold answer: {SEED_POTTERY.gold_answer!r}")
    baseline = retrieve_select_generate(
        foundation, query, campaign_run_config, user_id=USER_ID, task_id="dsrm-white-box",
    )
    print(f"Selected (top-8): {baseline.selected_memory_ids}")
    print_dormancy_report("dsrm-white-box", baseline, [inject_result.canonical_memory_id])
    selected = inject_result.canonical_memory_id in baseline.selected_memory_ids
    print(f"White-box decision in selected set: {selected}")
    print(f"Baseline (poisoned) answer: {baseline.execution_result.answer!r}")

    if not selected:
        print("\nNot selected -- no counterfactual check to run. Real negative result, "
              "reported as observed (compare to black-box's real positive result, "
              "PHASE4_4_4_DSRM_RECONSTRUCTION_PLAN.md Milestone 4).")
        foundation.shutdown()
        return 0

    masked = run_counterfactual_mask(baseline, inject_result.canonical_memory_id, campaign_run_config)
    print(f"\nMasked-run answer: {masked.masked_answer!r}")
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
