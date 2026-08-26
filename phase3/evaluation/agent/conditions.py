"""Agent evaluation conditions and `AgentVisibleContext` assembly.

Phase 3.2-E scope note: `phase3/evaluation/contracts/evaluation_run.schema.json`'s
`condition` field is a `const`-pinned enum containing exactly three values:
``NO_MEMORY``, ``GOLD_EVIDENCE``, ``RETRIEVED_MEMORY`` (Conditions A/B/C per
`EVALUATION_CONTRACT.md` section 5). This module does **not** modify that schema to add
new canonical values -- per the 3.2-E task brief, a schema extension must be strictly
backward-compatible, unavoidable, and justified, and this module has no such need: the
schema's three conditions remain exactly as frozen in 3.2-B.

Instead, this module defines three ADDITIONAL, clearly-labeled PROVISIONAL conditions
(``SELECTED_MEMORY_AVAILABLE``, ``DERIVED_MEMORY_AVAILABLE``, ``CONFLICTING_MEMORY_AVAILABLE``)
for this stage's synthetic diagnostic testing only. These are deliberately named with an
``_AVAILABLE`` suffix -- a naming convention distinct from the three schema-canonical
values (which have no such suffix) -- so a reader can immediately tell, from the name
alone, which conditions are schema-canonical and which are 3.2-E provisional extensions,
without needing to cross-reference a table. `CANONICAL_CONDITIONS` and
`PROVISIONAL_CONDITIONS` below make this machine-checkable as well as visually obvious.

Why provisional conditions are needed at all: the 3.2-E task brief requires exercising
memory-contribution and failure-stage diagnostics against scenarios the three canonical
conditions alone cannot cleanly represent for SYNTHETIC testing purposes -- e.g. a
"selected memory available but not necessarily gold" condition (distinct from
`RETRIEVED_MEMORY`, which per `EVALUATION_CONTRACT.md` already implies the full
retrieval+selection pipeline), a "derived memory available" condition, and a "conflicting
memory available" condition (to synthetically exercise `NEGATIVE_MEMORY_EFFECT`, see
`paired.py`). None of these three is claimed as a new frozen Phase 3.1/3.2-B agent-level
condition -- they exist ONLY inside this diagnostic package, for this stage's synthetic
fixtures and tests, and must never be written into an `EvaluationRun.condition` field
(which remains schema-validated against the frozen three-value enum).

This module also provides `build_agent_visible_context()`, a thin assembly helper that
shapes a payload consistent with `agent_visible_context.schema.json`'s structure (task,
condition, memory_content, legitimate_observations) and runs it through
`phase3/evaluation/contracts/boundary.py`'s `validate_agent_visible()` before returning --
reusing the existing, stronger boundary check rather than inventing a parallel, weaker one.
Note that `validate_agent_visible()` performs no schema/enum validation (it only scans for
forbidden keys), so it accepts payloads carrying a provisional condition value with no
special-casing required; JSON-Schema-level validation against
`agent_visible_context.schema.json`'s `condition` enum is intentionally not attempted for
the three provisional conditions (that enum is schema-canonical and out of scope to
extend), and no test in this stage claims a provisional-condition payload validates
against that schema.

Pure functions/data only: no filesystem/network/LLM/embeddings access, no randomness, no
global state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence, Tuple

from phase3.evaluation.contracts.boundary import validate_agent_visible

# ---------------------------------------------------------------------------
# Condition vocabulary
# ---------------------------------------------------------------------------

# CANONICAL -- exact string values from evaluation_run.schema.json's `condition` enum.
# Never redefine or rename these; they must always match the schema literally.
CONDITION_NO_MEMORY = "NO_MEMORY"
CONDITION_GOLD_EVIDENCE = "GOLD_EVIDENCE"
CONDITION_RETRIEVED_MEMORY = "RETRIEVED_MEMORY"

CANONICAL_CONDITIONS: Tuple[str, ...] = (
    CONDITION_NO_MEMORY,
    CONDITION_GOLD_EVIDENCE,
    CONDITION_RETRIEVED_MEMORY,
)

# PROVISIONAL -- 3.2-E diagnostic-only extensions. Never written to a schema-validated
# EvaluationRun.condition field. See module docstring for rationale.
CONDITION_SELECTED_MEMORY_AVAILABLE = "SELECTED_MEMORY_AVAILABLE"
CONDITION_DERIVED_MEMORY_AVAILABLE = "DERIVED_MEMORY_AVAILABLE"
CONDITION_CONFLICTING_MEMORY_AVAILABLE = "CONFLICTING_MEMORY_AVAILABLE"

PROVISIONAL_CONDITIONS: Tuple[str, ...] = (
    CONDITION_SELECTED_MEMORY_AVAILABLE,
    CONDITION_DERIVED_MEMORY_AVAILABLE,
    CONDITION_CONFLICTING_MEMORY_AVAILABLE,
)

ALL_CONDITIONS: Tuple[str, ...] = CANONICAL_CONDITIONS + PROVISIONAL_CONDITIONS

# Conditions under which SOME memory content is legitimately available to the agent
# (used by the paired memory-contribution diagnostic in `paired.py` to select the
# "WITH_MEMORY" side of a comparison against NO_MEMORY). Deliberately excludes
# NO_MEMORY.
WITH_MEMORY_CONDITIONS: Tuple[str, ...] = (
    CONDITION_GOLD_EVIDENCE,
    CONDITION_RETRIEVED_MEMORY,
    CONDITION_SELECTED_MEMORY_AVAILABLE,
    CONDITION_DERIVED_MEMORY_AVAILABLE,
    CONDITION_CONFLICTING_MEMORY_AVAILABLE,
)


@dataclass(frozen=True)
class ConditionDefinition:
    """Documentation-carrying record for one evaluation condition.

    Attributes
    ----------
    name:
        The condition's string identifier (one of the CONDITION_* constants above).
    canonical:
        True iff `name` is one of the three schema-frozen values in
        `evaluation_run.schema.json`. False for the 3.2-E provisional extensions.
    description:
        Human-readable summary of what agent-visible content this condition implies.
    """

    name: str
    canonical: bool
    description: str


CONDITION_DEFINITIONS: Mapping[str, ConditionDefinition] = {
    CONDITION_NO_MEMORY: ConditionDefinition(
        CONDITION_NO_MEMORY,
        canonical=True,
        description=(
            "Condition A per EVALUATION_CONTRACT.md section 5. Agent-visible context "
            "contains the task only -- no memory content, no legitimate observations "
            "beyond what the task itself supplies."
        ),
    ),
    CONDITION_GOLD_EVIDENCE: ConditionDefinition(
        CONDITION_GOLD_EVIDENCE,
        canonical=True,
        description=(
            "Condition B per EVALUATION_CONTRACT.md section 5. Agent-visible context "
            "contains the task plus the gold evidence CONTENT (never the literal gold "
            "evidence ID, per LEAKAGE_AND_VISIBILITY_CONTRACT.md section 1)."
        ),
    ),
    CONDITION_RETRIEVED_MEMORY: ConditionDefinition(
        CONDITION_RETRIEVED_MEMORY,
        canonical=True,
        description=(
            "Condition C per EVALUATION_CONTRACT.md section 5 -- the actual clean agent: "
            "task plus retrieved-and-selected memory content, the output of the full "
            "candidate discovery -> reranking -> selection pipeline."
        ),
    ),
    CONDITION_SELECTED_MEMORY_AVAILABLE: ConditionDefinition(
        CONDITION_SELECTED_MEMORY_AVAILABLE,
        canonical=False,
        description=(
            "PROVISIONAL, 3.2-E synthetic-testing only. Agent-visible context contains "
            "task plus some selected memory content, without asserting the full "
            "retrieval+selection pipeline semantics RETRIEVED_MEMORY implies -- used to "
            "synthetically exercise retrieval-utilization diagnostics."
        ),
    ),
    CONDITION_DERIVED_MEMORY_AVAILABLE: ConditionDefinition(
        CONDITION_DERIVED_MEMORY_AVAILABLE,
        canonical=False,
        description=(
            "PROVISIONAL, 3.2-E synthetic-testing only. Agent-visible context contains "
            "task plus derived-memory content (per memory_schema.md section 3.2), for "
            "synthetically exercising memory-contribution diagnostics against derived "
            "(not foundation) memory."
        ),
    ),
    CONDITION_CONFLICTING_MEMORY_AVAILABLE: ConditionDefinition(
        CONDITION_CONFLICTING_MEMORY_AVAILABLE,
        canonical=False,
        description=(
            "PROVISIONAL, 3.2-E synthetic-testing only. Agent-visible context contains "
            "task plus two or more mutually conflicting memory contents (per "
            "memory_schema.md section 6's `conflicts_with` relationship), for "
            "synthetically exercising the NEGATIVE_MEMORY_EFFECT memory-contribution case."
        ),
    ),
}


# ---------------------------------------------------------------------------
# AgentVisibleContext assembly (reuses boundary.py's stronger check)
# ---------------------------------------------------------------------------


def build_agent_visible_context(
    condition: str,
    task_id: str,
    prompt: str,
    memory_items: Optional[Sequence[Mapping[str, Any]]] = None,
    legitimate_observations: Optional[Sequence[Mapping[str, Any]]] = None,
) -> Mapping[str, Any]:
    """Assemble a payload shaped like `agent_visible_context.schema.json` and validate it
    through `phase3/evaluation/contracts/boundary.py::validate_agent_visible()` before
    returning it.

    Parameters
    ----------
    condition:
        One of `ALL_CONDITIONS` (canonical or provisional). Not itself schema-validated
        against `agent_visible_context.schema.json`'s `condition` enum here -- that enum
        is schema-canonical (three values only) and this function must also support the
        3.2-E provisional conditions, which are, by design, never written into a
        schema-validated artifact.
    task_id, prompt:
        The task as legitimately presented to the agent.
    memory_items:
        Sequence of ``{"memory_id": ..., "content": ...}`` mappings (optionally with a
        ``permitted_provenance`` key) -- the CONTENT-only memory payload, never a
        gold/evaluator field. Empty/omitted for NO_MEMORY.
    legitimate_observations:
        Sequence of ``{"observation_id": ..., "content": ...}`` mappings.

    Returns
    -------
    The assembled payload (a plain dict), unchanged, after
    `validate_agent_visible()` confirms it carries no forbidden evaluator-only key at any
    nesting depth.

    Raises
    ------
    phase3.evaluation.contracts.boundary.AgentVisibilityViolation
        If any forbidden key (gold_answer, gold_evidence_ids, evaluation_metadata, etc.)
        is found anywhere in the assembled payload -- e.g. if a caller mistakenly stuffed
        a forbidden key into `memory_items`' `permitted_provenance` blob.

    DECISION (3.2-E, non-obvious choice): NO_MEMORY is enforced, by this function, to
    carry an EMPTY `memory_content` list regardless of what `memory_items` is passed --
    this operationalizes "NO_MEMORY has no memory context" as a structural guarantee of
    the assembly helper itself, not merely a convention callers must remember to follow.
    A caller who passes `memory_items` alongside `condition=CONDITION_NO_MEMORY` gets an
    empty `memory_content` in the returned payload, not a payload reflecting what was
    passed in -- this is deliberate, defensive behavior, not a silent bug.
    """
    payload: dict = {
        "schema_version": "3.2-b.1",
        "task": {"task_id": task_id, "prompt": prompt},
        "condition": condition,
    }

    if condition == CONDITION_NO_MEMORY:
        payload["memory_content"] = []
    else:
        payload["memory_content"] = [dict(item) for item in (memory_items or [])]

    if legitimate_observations:
        payload["legitimate_observations"] = [dict(o) for o in legitimate_observations]

    return validate_agent_visible(payload)
