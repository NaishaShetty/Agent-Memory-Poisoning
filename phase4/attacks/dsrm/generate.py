"""Phase 4 -- MAMBench reconstruction of DSRM: assembles one seed (Milestone
1) into a full `AdversarialDecisionArtifact` by running SRM (Milestone 2)
then CSRM (Milestone 3), and setting the black-box retrieval-text prefix
per Algorithm 1.
"""

from __future__ import annotations

from phase3.evaluation.agent_runtime.runner import RunConfiguration

from phase4.attacks.dsrm.csrm import generate_csrm_justification
from phase4.attacks.dsrm.decision import AdversarialDecisionArtifact, MAX_SRM_ITERATIONS_DEFAULT, TAU_DEFAULT
from phase4.attacks.dsrm.seeds import DSRMSeed
from phase4.attacks.dsrm.srm import _Embedder, run_self_refine


def generate_decision_black_box(
    seed: DSRMSeed,
    run_config: RunConfiguration,
    embedder: _Embedder,
    tau: float = TAU_DEFAULT,
    max_srm_iterations: int = MAX_SRM_ITERATIONS_DEFAULT,
) -> AdversarialDecisionArtifact:
    srm_result = run_self_refine(
        target_query=seed.target_question,
        initial_planning_text=seed.initial_planning_text,
        run_config=run_config,
        embedder=embedder,
        tau=tau,
        max_iterations=max_srm_iterations,
    )
    justification = generate_csrm_justification(seed.target_question, seed.forged_claim, run_config)

    # Algorithm 1: R = Q + T_m (T_m here is the forged claim, MAMBench's
    # tool-selection analogue -- see decision.py's render_content_text docstring).
    retrieval_text = f"{seed.target_question} {seed.forged_claim}"

    return AdversarialDecisionArtifact(
        artifact_id=seed.seed_id,
        task_id=seed.task_id,
        target_question=seed.target_question,
        gold_answer=seed.gold_answer,
        forged_claim=seed.forged_claim,
        planning_text=srm_result.final_planning_text,
        initial_planning_text=seed.initial_planning_text,
        csrm_justification=justification,
        srm_iterations_used=srm_result.iterations_used,
        srm_converged=srm_result.converged,
        srm_final_similarity=srm_result.final_similarity,
        variant="black_box",
        retrieval_text=retrieval_text,
    )


__all__ = ["generate_decision_black_box"]
