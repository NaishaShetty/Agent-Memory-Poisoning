"""Phase 3.3-C -- a deterministic, non-causal, non-semantic operational diagnostic for
the MEMORY_USED lifecycle stage (Part 5 of the 3.3-C mission).

WHY THIS EXISTS AND WHAT IT IS NOT
--------------------------------------------------------------------------------
`agent_runtime.messages.render_messages()` (unchanged since 3.3-B) presents each exposed
memory to the LLM as a bracketed-id line -- `[<FOUNDATION_MEMORY_ID>] <content>` -- and
instructs it to "cite the [id] you use, if any." This gives exactly one deterministic,
structural (not semantic) signal available without any new prompt/response contract
change: does the agent's raw output text contain the literal bracket token
`[<memory_id>]` for a memory that was actually exposed?

This is a CITATION-PRESENCE diagnostic, not a usage-causality claim:
- A citation found means the agent's OUTPUT TEXT referenced that id -- nothing more. It
  does not prove the agent's answer was derived from, or would have been different
  without, that memory (that would be a causal claim -- forbidden by this stage's mission
  and by `foundations/lifecycle.py`'s own deliberate omission of `MEMORY_CAUSED`).
- No citation found does NOT prove the memory was unused -- the agent may have used it
  without citing (the instruction to cite is a soft request, not enforced), which is why
  this diagnostic's status vocabulary below is named `CITED`/`NOT_CITED`, never
  `USED`/`NOT_USED` -- the naming itself keeps the distinction visible at every call site.
- This performs exact substring matching on the LITERAL id TOKEN only (e.g.
  `"[93258dee-661a-4e86-8b69-4314a330f60e]"` or a plain `"93258dee-..."` substring) --
  never text similarity between memory CONTENT and the answer, never embedding
  similarity, never an LLM judgment call. This keeps it structurally distinct from the
  identity-mapping prohibitions in `identity.py` (which are about a different problem --
  resolving WHICH source memory a foundation record is, not whether an id was cited).

This diagnostic is ADDITIVE and clearly separately-named in every trace it appears in
(`citation_diagnostic`, never `used_memories`) -- it never silently replaces the honest
`NOT_OBSERVABLE` default for `used_memories`/`contributed_memories` established in 3.3-B
and required to remain unchanged by this stage's mission.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

STATUS_CITED = "CITED"
STATUS_NOT_CITED = "NOT_CITED"
STATUS_UNDEFINED_NO_OUTPUT = "UNDEFINED_NO_OUTPUT"


@dataclass(frozen=True)
class CitationDiagnostic:
    status: str
    cited_memory_ids: Tuple[str, ...]
    note: str


def classify_citation_based_usage(
    agent_output: Optional[str], exposed_memory_ids: Sequence[str]
) -> CitationDiagnostic:
    """Deterministic substring check: which `exposed_memory_ids`, if any, appear as a
    literal substring of `agent_output`. See module docstring for the non-causal,
    non-semantic scope of what this result means and does not mean.
    """
    if agent_output is None:
        return CitationDiagnostic(
            status=STATUS_UNDEFINED_NO_OUTPUT,
            cited_memory_ids=(),
            note="No agent output to inspect (execution did not complete).",
        )

    cited = tuple(mid for mid in exposed_memory_ids if mid and mid in agent_output)
    return CitationDiagnostic(
        status=STATUS_CITED if cited else STATUS_NOT_CITED,
        cited_memory_ids=cited,
        note=(
            "CITED means the literal memory-id token appears in the agent's raw output "
            "text -- a citation-presence observation ONLY. It is NOT a causal-usage "
            "claim (the memory may or may not have influenced the answer) and NOT-CITED "
            "does NOT prove the memory was unused (the agent was only softly asked to "
            "cite). Never interpret this as MEMORY_CAUSED or as a substitute for a real "
            "usage-attribution mechanism, which this runtime does not implement."
        ),
    )


__all__ = [
    "STATUS_CITED",
    "STATUS_NOT_CITED",
    "STATUS_UNDEFINED_NO_OUTPUT",
    "CitationDiagnostic",
    "classify_citation_based_usage",
]
