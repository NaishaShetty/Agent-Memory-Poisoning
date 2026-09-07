"""Confirms reference_agent.py is a genuine re-export, never a second implementation."""

from __future__ import annotations

import phase3.evaluation.agent_runtime.reference_agent as ref
import phase3.evaluation.agent_runtime.runner as runner_mod


def test_run_reference_agent_is_identically_run_agent_task():
    assert ref.run_reference_agent is runner_mod.run_agent_task
    assert ref.run_agent_task is runner_mod.run_agent_task


def test_reexported_types_are_identical_objects_not_copies():
    assert ref.AgentTaskInput is runner_mod.AgentTaskInput
    assert ref.AgentRunOutcome is runner_mod.AgentRunOutcome
    assert ref.RunConfiguration is runner_mod.RunConfiguration
