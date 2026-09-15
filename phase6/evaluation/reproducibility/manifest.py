"""Phase 6.19 -- the Phase 6 Reproducibility Manifest.

REUSES PHASE 2/3's OWN CANONICAL SERIALIZATION PRIMITIVE, NEVER A NEW ONE
--------------------------------------------------------------------------------
`phase3.evaluation.security.reproducibility.fingerprint()` is the repository's
one existing SHA-256 canonical-serialization primitive (already reused
verbatim by Stage 6.3's `mint_decision_id()` and Stage 5.2's `Phase5Event.
event_id`). This module reuses it a third time for the same reason: one
hashing scheme across the whole project, not a fourth Phase-6-specific one.

WHAT THIS MANIFEST RECORDS, AND WHY EACH FIELD IS REAL, NOT A PLACEHOLDER
--------------------------------------------------------------------------------
Every field the Stage 6.19 brief names (defense version, policy version,
configuration, thresholds, model versions, seeds, attack version, task
sample, memory foundation, environment, hardware, dependency versions,
campaign ID, run ID, episode ID) is represented below. Fields that are
genuinely not applicable to a given run (e.g. `attack_version` for a pure
benign-regression run) are explicit `None`, never a fabricated string --
the same "honest absence, never a placeholder" discipline Phase 2's own
Unified Memory Record schema established (field_status vocabulary,
Methodology Section 6.2).

`environment_snapshot()` queries REAL, CURRENT facts about the machine this
manifest is built on (Python version, platform string, and the installed
version of every package Phase 6 code actually imports) -- never a
hand-typed, potentially-stale string.
"""

from __future__ import annotations

import platform
import sys
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError, version
from typing import Any, Mapping, Optional, Tuple

from phase3.evaluation.security.reproducibility import fingerprint

MANIFEST_SCHEMA_VERSION = "phase6-reproducibility-manifest-1.0.0"

# Every package a Phase 6 module actually imports (grep-verified against
# phase6/defense/ and phase6/evaluation/'s real import statements) -- not a
# speculative list of "things that might matter."
_TRACKED_PACKAGES: Tuple[str, ...] = ("scipy", "sentence-transformers", "torch", "numpy")


def environment_snapshot() -> Mapping[str, Any]:
    """Real, current facts about the machine this manifest is built on."""
    dependency_versions = {}
    for pkg in _TRACKED_PACKAGES:
        try:
            dependency_versions[pkg] = version(pkg)
        except PackageNotFoundError:
            dependency_versions[pkg] = None  # honestly absent, not fabricated
    return {
        "python_version": sys.version,
        "platform": platform.platform(),
        "dependency_versions": dependency_versions,
    }


@dataclass(frozen=True)
class Phase6ReproducibilityManifest:
    manifest_schema_version: str
    campaign_id: str
    run_id: str
    episode_id: Optional[str]

    defense_component_versions: Mapping[str, str]  # e.g. {"admission.reasoning_guard": "reasoning-guard-1.0.0", ...}
    policy_version: str  # phase6.defense.policy.records.CURRENT_POLICY_VERSION
    configuration: Mapping[str, Any]  # thresholds/weights actually in effect for this run

    model_versions: Mapping[str, str]  # e.g. {"D2_embedding_model": "sentence-transformers/all-MiniLM-L6-v2"}
    seeds: Mapping[str, int]

    attack_version: Optional[str]  # e.g. "Common Attack Contract Revision 3" -- None if no attack involved
    task_sample_description: Optional[str]  # e.g. "LoCoMo formal n=120 sample" -- None if not applicable
    memory_foundation: Optional[str]  # "Mem0" | "A-MEM" | None (synthetic/no live foundation)

    environment: Mapping[str, Any] = field(default_factory=environment_snapshot)

    def __post_init__(self) -> None:
        if not self.campaign_id or not self.run_id:
            raise ValueError("campaign_id and run_id must both be non-empty.")
        if not self.policy_version:
            raise ValueError("policy_version must be non-empty.")

    def canonical_identity(self) -> str:
        """A deterministic fingerprint over every field EXCEPT `environment`
        (machine-local facts like the exact Python patch version or platform
        string should not change what two runs with identical configuration
        and seeds are considered -- the same 'exclude generation timestamp
        and local filesystem path' discipline `reproducibility.py`'s own
        module docstring already establishes for its own manifest)."""
        return fingerprint(
            {
                "manifest_schema_version": self.manifest_schema_version,
                "campaign_id": self.campaign_id,
                "run_id": self.run_id,
                "episode_id": self.episode_id,
                "defense_component_versions": dict(self.defense_component_versions),
                "policy_version": self.policy_version,
                "configuration": dict(self.configuration),
                "model_versions": dict(self.model_versions),
                "seeds": dict(self.seeds),
                "attack_version": self.attack_version,
                "task_sample_description": self.task_sample_description,
                "memory_foundation": self.memory_foundation,
            }
        )

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "manifest_schema_version": self.manifest_schema_version,
            "campaign_id": self.campaign_id,
            "run_id": self.run_id,
            "episode_id": self.episode_id,
            "defense_component_versions": dict(self.defense_component_versions),
            "policy_version": self.policy_version,
            "configuration": dict(self.configuration),
            "model_versions": dict(self.model_versions),
            "seeds": dict(self.seeds),
            "attack_version": self.attack_version,
            "task_sample_description": self.task_sample_description,
            "memory_foundation": self.memory_foundation,
            "environment": dict(self.environment),
            "canonical_identity": self.canonical_identity(),
        }


def build_shipped_defense_manifest(
    *, campaign_id: str, run_id: str, episode_id: Optional[str] = None
) -> Phase6ReproducibilityManifest:
    """Convenience constructor: assembles a manifest for the SHIPPED (never
    per-attack-tuned, never Stage-6.9-recalibrated) defense configuration --
    the actual, real thresholds every component uses today, read directly
    from each module's own constants rather than retyped by hand (which
    could silently drift out of sync with the real code)."""
    from phase6.defense.admission.reasoning_guard import (
        GUARD_VERSION as ADMISSION_GUARD_VERSION,
        SIGNAL_WEIGHTS,
        THRESHOLD_ALLOW_WITH_RESTRICTION as ADM_T1,
        THRESHOLD_BLOCK as ADM_T3,
        THRESHOLD_QUARANTINE as ADM_T2,
    )
    from phase6.defense.propagation.containment_guard import (
        GUARD_VERSION as PROPAGATION_GUARD_VERSION,
        THRESHOLD_ALLOW_WITH_RESTRICTION as PROP_T1,
        THRESHOLD_QUARANTINE as PROP_T3,
        THRESHOLD_REQUIRE_VALIDATION as PROP_T2,
    )
    from phase6.defense.retrieval.consensus_guard import (
        GUARD_VERSION as RETRIEVAL_GUARD_VERSION,
        MIN_TOTAL_FLAGS_FOR_ESCALATION,
        THRESHOLD_DOWNRANK,
        THRESHOLD_ESCALATE_TO_QUARANTINE,
    )
    from phase6.defense.retrieval.embedding_signals import EMBEDDING_MODEL_NAME
    from phase6.defense.retrieval.signals import DEDUP_DAMPENING_EXPONENT, NEAR_DUPLICATE_THRESHOLD
    from phase6.defense.sleeper.sleeper_guard import (
        ADMISSION_THRESHOLD_QUARANTINE as SLEEPER_T1,
        GUARD_VERSION as SLEEPER_GUARD_VERSION,
        RETRIEVAL_THRESHOLD_ALLOW_WITH_RESTRICTION as SLEEPER_T2,
        RETRIEVAL_THRESHOLD_QUARANTINE as SLEEPER_T3,
    )
    from phase6.defense.policy.records import CURRENT_POLICY_VERSION

    return Phase6ReproducibilityManifest(
        manifest_schema_version=MANIFEST_SCHEMA_VERSION,
        campaign_id=campaign_id,
        run_id=run_id,
        episode_id=episode_id,
        defense_component_versions={
            "admission.reasoning_guard": ADMISSION_GUARD_VERSION,
            "retrieval.consensus_guard": RETRIEVAL_GUARD_VERSION,
            "propagation.containment_guard": PROPAGATION_GUARD_VERSION,
            "sleeper.sleeper_guard": SLEEPER_GUARD_VERSION,
        },
        policy_version=CURRENT_POLICY_VERSION,
        configuration={
            "admission": {
                "signal_weights": dict(SIGNAL_WEIGHTS),
                "threshold_allow_with_restriction": ADM_T1,
                "threshold_quarantine": ADM_T2,
                "threshold_block": ADM_T3,
            },
            "retrieval": {
                "near_duplicate_threshold": NEAR_DUPLICATE_THRESHOLD,
                "dedup_dampening_exponent": DEDUP_DAMPENING_EXPONENT,
                "threshold_downrank": THRESHOLD_DOWNRANK,
                "threshold_escalate_to_quarantine": THRESHOLD_ESCALATE_TO_QUARANTINE,
                "min_total_flags_for_escalation": MIN_TOTAL_FLAGS_FOR_ESCALATION,
            },
            "propagation": {
                "threshold_allow_with_restriction": PROP_T1,
                "threshold_require_validation": PROP_T2,
                "threshold_quarantine": PROP_T3,
            },
            "sleeper": {
                "admission_threshold_quarantine": SLEEPER_T1,
                "retrieval_threshold_allow_with_restriction": SLEEPER_T2,
                "retrieval_threshold_quarantine": SLEEPER_T3,
            },
        },
        model_versions={"D2_embedding_model": EMBEDDING_MODEL_NAME},
        seeds={},  # no stochastic component in the current shipped defense (pure regex/arithmetic)
        attack_version=None,
        task_sample_description=None,
        memory_foundation=None,
    )
