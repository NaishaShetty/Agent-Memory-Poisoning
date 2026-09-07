"""The MAMBench reference clean agent -- the single, explicitly-named entry point the
Phase 3 completion audit found missing (checklist §8: "there is no file literally named
'reference_agent.py' or similar; the de facto implementation is `runner.py::
run_agent_task()`").

THIS IS A THIN, DELIBERATE RE-EXPORT -- NEVER A SECOND IMPLEMENTATION
--------------------------------------------------------------------------------
`runner.py::run_agent_task()` remains the actual implementation, unchanged, untouched.
This module adds no logic of its own -- it exists purely so "the reference agent" has one
discoverable, stably-named place to look, without risking two implementations silently
drifting apart (exactly the failure mode `provenance_graph.py`'s own "projection, not a
second store" design already guards against elsewhere in this codebase). If
`run_agent_task()`'s own behavior ever changes, this module's behavior changes with it,
automatically, by construction -- there is no logic here to keep in sync.

WHAT MAKES THIS "THE" REFERENCE AGENT (per the audit's own checklist, restated here as a
single point of reference rather than left implicit across several documents)
--------------------------------------------------------------------------------
- Performs real retrieval (`foundation.retrieve()`), never simulated.
- Receives selected memory/context via the same boundary-checked, leakage-audited
  `agent_visible_context` construction every other real pipeline in this codebase uses.
- Generates a real response via the configured `LLMProvider`.
- Produces fully observable execution outcomes (`AgentRunOutcome`) and observable memory
  interactions (`retrieved_memory_ids`/`selected_memory_ids`/`exposed_memory_ids`) -- with
  the one honestly-disclosed exception that `used_memory_ids` remains `None` (no
  attribution mechanism exists for it in this runtime; see
  `PHASE3_FINAL_STATUS_DONE_NOT_DONE.md`).
- Never imports `EvaluatorReference` or any gold/hidden-evaluation data -- structurally
  impossible by construction, verified directly (no such import exists anywhere in
  `agent_runtime/`, confirmed by repo-wide grep during the completion audit).
- Suitable as Phase 4's control/clean-path agent per
  `PHASE4_INTERFACE_REQUIREMENTS.md §2`'s own framing (layer separation exists
  specifically so Phase 4 can hold this agent's configuration fixed while manipulating only
  the memory layer).
"""

from __future__ import annotations

from phase3.evaluation.agent_runtime.runner import (
    AgentRunOutcome,
    AgentRuntimeLeakageError,
    AgentTaskInput,
    GenerationAttempt,
    RunConfiguration,
    run_agent_task,
)

# The reference agent's own entry point -- identical function, re-exported under a name
# that says what it is for a reader who doesn't already know `runner.py`'s own history.
run_reference_agent = run_agent_task

__all__ = [
    "AgentRunOutcome",
    "AgentRuntimeLeakageError",
    "AgentTaskInput",
    "GenerationAttempt",
    "RunConfiguration",
    "run_agent_task",
    "run_reference_agent",
]
