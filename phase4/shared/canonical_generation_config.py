"""Phase 4 fix (2026-09-15) -- the canonical, shared answer-generation
config every real attack campaign's victim-answer generation stage uses.

WHAT THIS CLOSES
--------------------------------------------------------------------------------
The audit finding: "the shared pipeline's determinism guarantee actually
varies by which config object a given attack script chose to build,"
illustrated by real config differences across the seven attacks. On direct
re-inspection of the actual real campaign scripts (not assumption), those
differences are ALL in attack-INTERNAL steps -- gate/judge generation
(`gate_generation_config`, n_ctx=2048 for MemoryGraft/Sleeper vs 4096
elsewhere) and DSRM's own SRM/CSRM forged-content generation
(`srm_csrm_generation_config`, temperature=0.7) -- never in the actual
victim-answer generation stage whose output is what gets compared for
"did the attack succeed." That stage's config
(`generation_config`/`campaign_generation_config` in each script) was
ALREADY identical -- `temperature=0.0, seed=42, max_tokens=64,
enable_thinking=False, n_ctx=4096` -- across all seven real milestone
campaigns (agentpoison, farma, minja, both mpbench campaigns, both dsrm
campaigns, memorygraft, sleeper).

This module makes that already-true fact a STRUCTURAL, checkable invariant
instead of a coincidence nobody had verified holds: `CANONICAL_ANSWER_GENERATION_CONFIG`
is the single source of truth, and `test_canonical_generation_config.py`
parses every real campaign script's own source (AST, not string matching) to
confirm its answer-generation-stage `GenerationConfig(...)` call matches this
config exactly. Attack-internal steps (gates, SRM/CSRM) remain free to use a
different config -- explicitly documented as such here, closing the "not
documented as such" half of the original finding -- this module does not
force them to match and does not touch any already-published campaign
script's actual behavior (every value already matched; nothing changed).
"""

from __future__ import annotations

from phase3.evaluation.llm.provider import GenerationConfig

CANONICAL_ANSWER_GENERATION_TEMPERATURE = 0.0
CANONICAL_ANSWER_GENERATION_SEED = 42
CANONICAL_ANSWER_GENERATION_MAX_TOKENS = 64
CANONICAL_ANSWER_GENERATION_ENABLE_THINKING = False
CANONICAL_ANSWER_GENERATION_N_CTX = 4096


def canonical_answer_generation_config() -> GenerationConfig:
    """The exact config every real attack campaign's victim-answer
    generation stage already uses. New campaign scripts should call this
    rather than re-declaring the same five literals independently."""
    return GenerationConfig(
        temperature=CANONICAL_ANSWER_GENERATION_TEMPERATURE,
        seed=CANONICAL_ANSWER_GENERATION_SEED,
        max_tokens=CANONICAL_ANSWER_GENERATION_MAX_TOKENS,
        enable_thinking=CANONICAL_ANSWER_GENERATION_ENABLE_THINKING,
        n_ctx=CANONICAL_ANSWER_GENERATION_N_CTX,
    )


# Attack-internal steps that are INTENTIONALLY, disclosedly different from the
# canonical answer-generation config above -- never compared across attacks,
# so a different config here does not confound the cross-attack comparison
# the audit finding was concerned about. Listed explicitly so this remains a
# checked, disclosed fact rather than something a future reader has to
# re-derive from seven separate files.
DISCLOSED_ATTACK_INTERNAL_CONFIG_VARIANCE = {
    "memorygraft.gate_generation_config": "n_ctx=2048 (judge role, not compared across attacks)",
    "sleeper_memory_poisoning.gate_generation_config": "n_ctx=2048 (judge role, not compared across attacks)",
    "dsrm.srm_csrm_generation_config": "temperature=0.7 (attack-content generation, not the compared answer)",
    "dsrm.white_box_campaign.gate_generation_config": "temperature=0.7, n_ctx=4096, max_tokens=320 (white-box CSRM judgment step, not the compared answer)",
}

__all__ = [
    "CANONICAL_ANSWER_GENERATION_TEMPERATURE",
    "CANONICAL_ANSWER_GENERATION_SEED",
    "CANONICAL_ANSWER_GENERATION_MAX_TOKENS",
    "CANONICAL_ANSWER_GENERATION_ENABLE_THINKING",
    "CANONICAL_ANSWER_GENERATION_N_CTX",
    "canonical_answer_generation_config",
    "DISCLOSED_ATTACK_INTERNAL_CONFIG_VARIANCE",
]
