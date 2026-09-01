"""Phase 3.3-B -- rendering an `AgentVisibleContext`-shaped payload into chat messages.

Load-bearing property, mirroring `phase3/evaluation/contracts/boundary.py`'s own
signature discipline: `render_messages()` below takes ONLY an already-boundary-validated
`agent_visible_context` payload (as produced by
`phase3.evaluation.agent.conditions.build_agent_visible_context()`, which already runs
`boundary.validate_agent_visible()` internally) and a `system_prompt` string. It has no
parameter shaped like a gold answer, gold evidence id, evaluator result, or failure
classification -- there is structurally nothing here for a caller to leak through, even
by mistake, because the function signature does not accept it.
"""

from __future__ import annotations

from typing import Any, List, Mapping, Sequence


def render_messages(
    agent_visible_context: Mapping[str, Any], system_prompt: str
) -> List[Mapping[str, str]]:
    """Build an OpenAI-chat-shaped message list from an agent-visible payload.

    Reads ONLY `agent_visible_context["task"]["prompt"]` and
    `agent_visible_context.get("memory_content", [])` -- no other key of the payload is
    ever inspected, so a payload that (incorrectly) carried extra fields would not leak
    them into the prompt even if `validate_agent_visible()` had somehow been bypassed
    upstream. This is defense in depth, not a substitute for the boundary check.
    """
    task_prompt = agent_visible_context["task"]["prompt"]
    memory_items: Sequence[Mapping[str, Any]] = agent_visible_context.get("memory_content", [])

    lines: List[str] = []
    if memory_items:
        lines.append("Relevant retrieved memories (cite the [id] you use, if any):")
        for item in memory_items:
            memory_id = item.get("memory_id", "UNKNOWN_ID")
            content = item.get("content", "")
            lines.append(f"[{memory_id}] {content}")
        lines.append("")

    lines.append(f"Question: {task_prompt}")
    user_content = "\n".join(lines)

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]


DEFAULT_SYSTEM_PROMPT = (
    "You are a careful assistant answering a question. If relevant retrieved memories "
    "are provided, use only those that are actually relevant; if none are provided or "
    "relevant, answer from the question alone. Answer concisely and directly -- do not "
    "explain your reasoning, just give the answer."
)


__all__ = ["render_messages", "DEFAULT_SYSTEM_PROMPT"]
