"""Phase 14 -- Track B, Stage 2: real Consolidation Guard protection for
content that survives the admission/retrieval stage (2026-09-23, explicitly
authorized).

WHY THIS EXISTS
--------------------------------------------------------------------------------
Track B (`track_b_poison.py`) tests ONLY the admission/retrieval stage
(`B1`/`B9`, per the plan's own Section 3 scope). Investigating why FARMA and
MPBench still are not fully protected there found a real, important fact
about THIS PROJECT'S OWN ALREADY-BUILT architecture: `evaluate_consolidation()`
(Phase 12's fifth defense component) does not require admission-time
QUARANTINE to act -- it quarantines a real derivation whenever a source's own
admission action is anything OTHER than plain `ALLOW` (i.e., `ALLOW_WITH_
RESTRICTION` already qualifies) AND the real derived content is genuinely
similar to that source. MPBench's own real content already reaches
`ALLOW_WITH_RESTRICTION` at admission time (`third_person_report_score`
fires) -- meaning REAL protection for it may already exist at the
consolidation stage, without needing a new, riskier admission-time signal.

This module tests that directly: for each real Track B case, it builds a
real consolidation context (the SAME real poison + real benign distractors
Track B already uses), gets a real summary from the SAME real local Ollama
model used throughout this project, and checks whether `evaluate_
consolidation()` -- reused completely unmodified -- would quarantine it.
This is not a new defense; it is the first real test of an already-built one
against Track B's own real cases.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from phase3.evaluation.llm.provider import GenerationConfig, LLMProvider
from phase6.defense.consolidation.consolidation_guard import evaluate_consolidation
from phase6.defense.policy.states import ALLOW
from phase12.propagation.ollama_provider import OllamaProvider
from phase12.propagation.propagation_rate import _consolidation_messages
from phase14.track_b_poison import TrackBCase, build_track_b_cases

TS = "2026-09-23T00:10:00Z"
RUN_ID = "phase14-track-b-consolidation-stage"


@dataclass(frozen=True)
class ConsolidationStageResult:
    case: TrackBCase
    summary_text: str
    consolidation_action: str
    protected: bool  # action != ALLOW -- the real derivation would be quarantined/restricted


def run_consolidation_stage_case(
    case: TrackBCase, *, provider: Optional[LLMProvider] = None, config: Optional[GenerationConfig] = None,
) -> ConsolidationStageResult:
    provider = provider or OllamaProvider()
    config = config or GenerationConfig(
        temperature=0.0, seed=42, max_tokens=200, enable_thinking=False, n_ctx=2048, request_timeout_sec=120.0,
    )

    poison_text = case.pool_items[0][1]
    distractor_texts = [text for _, text in case.pool_items[1:]]
    context = tuple([poison_text] + distractor_texts)

    result = provider.generate(_consolidation_messages(context), config)
    summary = result.text.strip()

    decision = evaluate_consolidation(
        summary, [poison_text] + distractor_texts, run_id=RUN_ID, episode_id="e1",
        timestamp=TS, evidence_refs=(f"EVT-{case.target_scenario_id}",),
    )
    return ConsolidationStageResult(
        case=case, summary_text=summary, consolidation_action=decision.action,
        protected=decision.action != ALLOW,
    )


def run_all_consolidation_stage_cases(*, provider: Optional[LLMProvider] = None) -> Tuple[ConsolidationStageResult, ...]:
    cases = build_track_b_cases()
    return tuple(run_consolidation_stage_case(c, provider=provider) for c in cases)


if __name__ == "__main__":
    for r in run_all_consolidation_stage_cases():
        print(f"{r.case.target_scenario_id}: action={r.consolidation_action} protected={r.protected}")
        print(f"  summary: {r.summary_text!r}")


__all__ = ["ConsolidationStageResult", "run_consolidation_stage_case", "run_all_consolidation_stage_cases"]
