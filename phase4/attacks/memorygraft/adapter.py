"""Phase 4 -- MemoryGraft `inject()` wiring: the gate from `persistence_gate.py`,
placed as a real precondition in front of the real, unmodified
`MemoryFoundationAdapter.add_memory()` write path.

WHY THIS FILE DOES NOT IMPORT `RealMem0Adapter`/`RealAMemAdapter` DIRECTLY
--------------------------------------------------------------------------------
Per `phase3/evaluation/foundations_real/environment.py`, `mem0ai`/`amem` are only
importable inside the isolated `C:\\h4venv` interpreter, not the main repo
environment this module is written and unit-tested in. `MemoryGraftInjector` below
therefore takes an already-constructed `MemoryFoundationAdapter` instance via
dependency injection (the same pattern `phase3/evaluation/foundations/adapter.py`
already establishes) -- a caller running inside `C:\\h4venv` passes a real
`RealMem0Adapter`/`RealAMemAdapter`; a unit test passes a fake. This file itself
places no constraint on which interpreter it runs in, exactly like
`phase3.evaluation.llm.provider` (see that module's own docstring on this point).

WHAT THIS IS NOT
--------------------------------------------------------------------------------
This is NOT the full Phase 4.2 `AttackAdapter` interface (validate/prepare/
generate/inject/execute/collect) described in
`PHASE4_4_2_COMMON_ATTACK_CONTRACT.md` -- that full contract, and a
`MemoryGraftAdapter` implementing all six of its stages, do not exist as code
anywhere in this repository yet; only the `inject()` stage specifically was
requested and is built here. `MemoryGraftInjectionResult` below deliberately
mirrors the contract's `InjectionEvent` field names (`admission_status`,
`attacker_originated`, `canonical_memory_id`) so it slots into that larger
structure later without renaming, but it is a standalone result type today, not
the contract's actual `InjectionEvent` dataclass.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

from phase3.evaluation.foundations.adapter import MemoryFoundationAdapter
from phase3.evaluation.llm.provider import GenerationConfig, LLMProvider

from phase4.attacks.memorygraft.persistence_gate import (
    DECISION_KEEP,
    PersistenceJudgment,
    PoisonedExperienceArtifact,
    judge_persistence,
)

# Content-type tag per PHASE4_4_2_COMMON_ATTACK_CONTRACT.md Revision 3, Section 5:
# carried INSIDE CanonicalMemoryRecord.content (confirmed open by direct code read
# of phase3/evaluation/foundations/canonical.py), never as a new top-level field.
CONTENT_TYPE_EXPERIENCE_PRECEDENT = "EXPERIENCE_PRECEDENT"

ADMISSION_NOT_ADMITTED = "NOT_ADMITTED"
ADMISSION_ADMITTED = "ADMITTED"
ADMISSION_REJECTED = "REJECTED"


@dataclass(frozen=True)
class MemoryGraftInjectionResult:
    """One artifact's outcome through the gated inject() step."""

    artifact_id: str
    judgment: PersistenceJudgment
    admission_status: str  # ADMISSION_NOT_ADMITTED | ADMISSION_ADMITTED | ADMISSION_REJECTED
    attacker_originated: bool  # per G-003 -- always True for this adapter's writes,
    # since MemoryGraftInjector is always the writer (a DIRECT_WRITE injection_method,
    # per PHASE4_4_2_COMMON_ATTACK_CONTRACT.md Section 9's MemoryGraft row) --
    # never left implicit.
    canonical_memory_id: Optional[str]
    foundation_field_note: Optional[str]


class MemoryGraftInjector:
    """Gated inject() step: judge, then (conditionally) write through the real,
    unmodified `MemoryFoundationAdapter.add_memory()`.

    Parameters
    ----------
    foundation_adapter:
        A real, already-initialized `MemoryFoundationAdapter` (RealMem0Adapter or
        RealAMemAdapter in production; a fake/mock in tests). This class never
        constructs or initializes it -- lifecycle ownership stays with the caller,
        exactly as `phase3.evaluation.foundations.adapter.MemoryFoundationAdapter`
        implementations already require.
    foundation_label:
        "mem0" or "amem" -- passed straight through to `judge_persistence()`'s
        `foundation` argument, so Decision 2's A-MEM guard is enforced at the gate,
        not silently bypassed by this layer.
    llm_provider / generation_config:
        The gate's own LLM call target -- typically the same `LlamaServerProvider`
        instance V3-Hybrid's own campaign already uses (per
        `phase3.evaluation.llm.provider`), passed explicitly rather than constructed
        here, so a caller can point the gate at a specific, already-verified server
        instance.
    """

    def __init__(
        self,
        foundation_adapter: MemoryFoundationAdapter,
        foundation_label: str,
        llm_provider: LLMProvider,
        generation_config: GenerationConfig,
        *,
        amem_confound_fix_confirmed: bool = False,
    ) -> None:
        self._foundation_adapter = foundation_adapter
        self._foundation_label = foundation_label
        self._llm_provider = llm_provider
        self._generation_config = generation_config
        self._amem_confound_fix_confirmed = amem_confound_fix_confirmed

    def inject(
        self,
        artifact: PoisonedExperienceArtifact,
        extra_metadata: Optional[Mapping[str, Any]] = None,
    ) -> MemoryGraftInjectionResult:
        """Judge `artifact`, and write it through the real foundation adapter only if
        the gate returns KEEP. Always returns a result -- a DISCARD is not an error,
        it is the gate correctly doing its job."""

        judgment = judge_persistence(
            artifact,
            self._llm_provider,
            self._generation_config,
            foundation=self._foundation_label,
            amem_confound_fix_confirmed=self._amem_confound_fix_confirmed,
        )

        if judgment.decision != DECISION_KEEP:
            return MemoryGraftInjectionResult(
                artifact_id=artifact.artifact_id,
                judgment=judgment,
                admission_status=ADMISSION_NOT_ADMITTED,
                attacker_originated=True,
                canonical_memory_id=None,
                foundation_field_note="gate returned DISCARD; add_memory() was not called",
            )

        content: Mapping[str, Any] = {
            "text": artifact.resp,
            "content_type": CONTENT_TYPE_EXPERIENCE_PRECEDENT,
            "source_request": artifact.req,
        }
        metadata = dict(extra_metadata or {})
        metadata.setdefault("attacker_originated", True)
        metadata.setdefault("attack_id", "memorygraft")
        metadata.setdefault("gate_config_fingerprint", judgment.gate_config_fingerprint)
        metadata.setdefault("semantic_targets", list(artifact.semantic_targets))
        if artifact.tag:
            metadata.setdefault("tag", artifact.tag)

        field_result = self._foundation_adapter.add_memory(
            memory_id=artifact.artifact_id,
            content=content,
            metadata=metadata,
        )

        if field_result.availability not in ("AVAILABLE", "PARTIAL"):
            return MemoryGraftInjectionResult(
                artifact_id=artifact.artifact_id,
                judgment=judgment,
                admission_status=ADMISSION_REJECTED,
                attacker_originated=True,
                canonical_memory_id=None,
                foundation_field_note=field_result.note,
            )

        written_id = artifact.artifact_id
        if isinstance(field_result.value, str):
            written_id = field_result.value
        elif isinstance(field_result.value, Mapping) and "memory_id" in field_result.value:
            # Real MemoryFoundationAdapter implementations (e.g. MockMem0Adapter,
            # per phase3/evaluation/foundations/mocks/mock_mem0.py) return
            # {"memory_id": <id>} as the AVAILABLE value, not a bare string --
            # callers must read the returned id, never assume it echoes the id
            # passed in (per MemoryFoundationAdapter.add_memory's own docstring).
            written_id = str(field_result.value["memory_id"])
        return MemoryGraftInjectionResult(
            artifact_id=artifact.artifact_id,
            judgment=judgment,
            admission_status=ADMISSION_ADMITTED,
            attacker_originated=True,
            canonical_memory_id=written_id,
            foundation_field_note=field_result.note,
        )


__all__ = [
    "CONTENT_TYPE_EXPERIENCE_PRECEDENT",
    "ADMISSION_NOT_ADMITTED",
    "ADMISSION_ADMITTED",
    "ADMISSION_REJECTED",
    "MemoryGraftInjectionResult",
    "MemoryGraftInjector",
]
