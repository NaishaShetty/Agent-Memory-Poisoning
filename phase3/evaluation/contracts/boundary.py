"""Phase 3.2-B boundary enforcement: agent-visible vs. evaluator-only separation.

This module is defense-in-depth *beyond* the JSON Schema `additionalProperties: false`
guarantee already present in agent_visible_context.schema.json. Two independent layers
guard the same invariant on purpose: a schema can be bypassed if someone hand-constructs
a dict and skips validation; a runtime check that inspects the payload for forbidden keys
catches that case too.

Design/scope note: this module performs no schema validation itself (that is
`jsonschema`'s job, exercised in phase3/evaluation/tests/test_evaluation_contracts.py).
It only enforces the narrower, absolute rule from LEAKAGE_AND_VISIBILITY_CONTRACT.md and
CLEAN_AGENT_INTERFACES.md section 2.4: a payload destined for agent visibility must never
carry any evaluator-only/gold/hidden-benchmark key, at any nesting depth.

Load-bearing property for Phase 4 readiness: `validate_agent_visible()` takes ONLY the
agent-visible payload. Its signature does not accept, require, or reference an
EvaluatorReference object anywhere -- this operationalizes the requirement that the agent
execution path must not import or depend on EvaluatorReference. See
test_evaluation_contracts.py::test_validate_agent_visible_signature_has_no_evaluator_reference_param
for the automated check that this stays true.
"""

from __future__ import annotations

from typing import Any


class AgentVisibilityViolation(ValueError):
    """Raised when a payload intended for agent visibility carries a forbidden key."""


# Keys that must never appear anywhere in an agent-visible payload, at any nesting depth.
# This list mirrors LEAKAGE_AND_VISIBILITY_CONTRACT.md section 1 ("agent-hidden") and
# CLEAN_AGENT_INTERFACES.md section 2.4 ("MUST NOT receive"). It is intentionally broader
# than the exact field names used in evaluator_reference.schema.json, so that a renamed or
# nested evaluator-only field is still caught (e.g. "gold_evidence_id" singular, or a key
# nested inside a "permitted_provenance" blob).
FORBIDDEN_KEYS: frozenset[str] = frozenset(
    {
        "gold_answer",
        "gold_answers",
        "gold_evidence_ids",
        "gold_evidence_id",
        "evidence_equivalence_refs",
        "task_labels",
        "benchmark_annotations",
        "evaluation_metadata",
        "expected_evidence",
        "evaluator_reference",
        "evaluation_labels",
        "evaluation_label",
        "evaluation_score",
        "evaluation_scores",
        "retrieval_ground_truth",
        "internal_retrieval_score",
        "internal_retrieval_scores",
        "internal_rank",
        "internal_ranks",
        "attack_label",
        "attack_labels",
        "hidden_benchmark_metadata",
    }
)


def _find_forbidden_keys(payload: Any, path: str = "$") -> list[str]:
    """Recursively walk payload, returning dotted paths of any forbidden key found."""
    hits: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_str = str(key)
            child_path = f"{path}.{key_str}"
            if key_str.lower() in FORBIDDEN_KEYS:
                hits.append(child_path)
            hits.extend(_find_forbidden_keys(value, child_path))
    elif isinstance(payload, list):
        for index, item in enumerate(payload):
            hits.extend(_find_forbidden_keys(item, f"{path}[{index}]"))
    return hits


def validate_agent_visible(agent_visible_payload: dict) -> dict:
    """Validate that a payload destined for agent visibility carries no forbidden key.

    Parameters
    ----------
    agent_visible_payload:
        A candidate AgentVisibleContext document (already loaded as a Python dict, e.g.
        from agent_visible_context.json). This is the ONLY parameter -- there is
        deliberately no `evaluator_reference` parameter, so the agent-visible path can
        never be wired to accept, need, or reference evaluator-only data by construction.

    Returns
    -------
    The same payload, unchanged, if it passes.

    Raises
    ------
    AgentVisibilityViolation
        If any forbidden key is found anywhere in the payload (at any nesting depth).
    """
    if not isinstance(agent_visible_payload, dict):
        raise AgentVisibilityViolation(
            f"agent_visible_payload must be a dict, got {type(agent_visible_payload).__name__}"
        )

    hits = _find_forbidden_keys(agent_visible_payload)
    if hits:
        raise AgentVisibilityViolation(
            "Forbidden evaluator-only key(s) found in agent-visible payload: "
            + ", ".join(sorted(hits))
        )
    return agent_visible_payload
