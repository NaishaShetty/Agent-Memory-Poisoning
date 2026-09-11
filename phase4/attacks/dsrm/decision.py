"""Phase 4 -- MAMBench reconstruction of DSRM: the assembled adversarial
decision (Milestone 1's design, Milestones 2-3's generation).

Per PHASE4_4_4_DSRM_RECONSTRUCTION_PLAN.md Section 2, DSRM's three-part
adversarial decision is reinterpreted for V3-Hybrid's tool-free
conversational QA setting:

| DSRM component  | Original meaning                | MAMBench reinterpretation |
|------------------|----------------------------------|----------------------------|
| Planning Text    | Task-execution strategy          | A forged summary of "what was established" about the conversation, refined via SRM |
| Tool Selection   | Which attack tool to invoke      | Which specific false claim the agent should treat as the answer |
| Reasoning Text   | Why the tool applies/is effective/impacts the task | Why that claim is well-supported (CoT, via CSRM) |

This is a genuine reformulation, not a relabeling, per the plan's own
explicit requirement -- documented here, not invented silently inside an
adapter. Milestone 1's content design review (3 concrete target questions,
reviewed for plausibility and for genuine distinctness from FARMA's own
reconstructed mechanism) lives in the reconstruction plan's Section 6; the
seed data below is that review's output.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple

# Per PHASE4_4_2_COMMON_ATTACK_CONTRACT.md Section 9 (line 717), DSRM's row
# specifies content_type = GENERAL_FACT ("reinterpreted 'claim,' inside
# content") -- found and fixed during Milestone 6's contract re-validation.
# An earlier version of this module used a self-descriptive
# "ADVERSARIAL_DECISION" tag instead, the same class of mistake AgentPoison's
# own Milestone 6 caught (a content_type that names the attack rather than
# playing a legitimate content role) -- GENERAL_FACT is both the contract's
# specified value AND the stealth-correct choice (a decision framed as an
# established general fact, not flagged as a "decision" object at all).
CONTENT_TYPE_ADVERSARIAL_DECISION = "GENERAL_FACT"

LABEL = "MAMBench reconstruction of DSRM"  # per the plan's Section 7 explicit labeling requirement

TAU_DEFAULT = 0.6  # per the paper's own default similarity threshold
MAX_SRM_ITERATIONS_DEFAULT = 5


@dataclass(frozen=True)
class CSRMJustification:
    """CoT-Strategy Reasoning Module output -- 3 structured steps, per
    dossier Section 4 / Table A.3: why the claim applies, why it's
    effective/trustworthy, and what impact accepting it has."""

    why_applies: str
    why_effective: str
    expected_impact: str

    def render(self) -> str:
        return (
            f"{self.why_applies} {self.why_effective} {self.expected_impact}"
        )


@dataclass(frozen=True)
class AdversarialDecisionArtifact:
    """One assembled DSRM-reconstruction decision record -- Planning Text +
    Tool Selection (the forged claim) + Reasoning Text (CSRM justification),
    plus SRM provenance (how many refinement iterations it took to reach
    the similarity threshold, and whether it actually converged)."""

    artifact_id: str
    task_id: int
    target_question: str
    gold_answer: str
    forged_claim: str  # the "Tool Selection" analogue
    planning_text: str  # the FINAL (post-SRM) planning text
    initial_planning_text: str  # the pre-SRM seed, for provenance
    csrm_justification: CSRMJustification
    srm_iterations_used: int
    srm_converged: bool
    srm_final_similarity: float
    variant: str = "black_box"  # black_box | white_box
    retrieval_text: Optional[str] = None  # set for black_box: Q + forged claim (Algorithm 1)


def render_content_text(artifact: AdversarialDecisionArtifact) -> str:
    """The actual memory content text written to the store.

    Per Algorithm 1 (black-box), the injected record is R ⊕ D_attack: a
    retrieval component R prepended to the decision itself, specifically to
    guarantee retrieval similarity to the target query -- "proven to be the
    most direct and effective method" per the dossier's reading of the
    paper. R = Q ⊕ T_m in the original (query concatenated with the
    tool-set); MAMBench's reformulation has no literal tool-set, so
    `retrieval_text` carries the query-anchored analogue (set by the
    injector at black_box injection time). D_attack is Planning Text + the
    forged claim (Tool Selection) + the CSRM Reasoning Text, assembled into
    one record, mirroring the paper's single injected 'past experience'
    record (dossier Section 4), not the paper's own multi-step JSON
    tool-plan format (LoCoMo QA has no multi-step tool plan to encode).
    white_box artifacts have no `retrieval_text` prefix -- the retrieval
    component there is instead optimized directly (Milestone 5)."""
    prefix = f"{artifact.retrieval_text} " if artifact.retrieval_text else ""
    return (
        f"{prefix}{artifact.planning_text} {artifact.forged_claim} "
        f"{artifact.csrm_justification.render()}"
    )


__all__ = [
    "CONTENT_TYPE_ADVERSARIAL_DECISION",
    "LABEL",
    "TAU_DEFAULT",
    "MAX_SRM_ITERATIONS_DEFAULT",
    "CSRMJustification",
    "AdversarialDecisionArtifact",
    "render_content_text",
]
