"""Tests for the FINAL, CANONICAL V3-Hybrid runner: confirms it's pure composition
(imports V3's A/C unchanged, no reimplementation of retrieval/selection), that
Condition B routes through the canonical bounded-verification reasoning pipeline,
and -- critically, per the Phase 3 closure audit that found and fixed a real V5
coupling violation -- that this module and its dependencies contain ZERO import of
anything under a v5-named file."""

from __future__ import annotations

import ast
from pathlib import Path

from phase3.evaluation.agent_runtime import campaign_v3_hybrid_runner as hybrid
from phase3.evaluation.agent_runtime.campaign_formal_runner import run_condition_a as v3_run_condition_a
from phase3.evaluation.agent_runtime.campaign_v3_runner import run_condition_c_v3_amem as v3_run_c_amem
from phase3.evaluation.agent_runtime.campaign_v3_runner import run_condition_c_v3_mem0 as v3_run_c_mem0


def test_condition_a_is_v3s_unchanged_function_object():
    """Identity check, not just equal behavior -- confirms this is the SAME
    function object, i.e. genuinely reused, not a reimplementation that happens to
    match."""
    assert hybrid.run_condition_a is v3_run_condition_a


def test_condition_c_mem0_is_v3s_unchanged_function_object():
    assert hybrid.run_condition_c_v3_mem0 is v3_run_c_mem0


def test_condition_c_amem_is_v3s_unchanged_function_object():
    assert hybrid.run_condition_c_v3_amem is v3_run_c_amem


def test_hybrid_store_is_its_own_isolated_namespace():
    """Never writes into v3_candidate, v5_candidate, or any other existing store."""
    parts = hybrid.V3_HYBRID_STORE.parts
    assert "v3_hybrid_candidate" in parts
    assert "v3_candidate" not in parts
    assert "v5_candidate" not in parts


def _module_source_path(module) -> Path:
    return Path(module.__file__)


def _imported_module_names(py_file: Path) -> set:
    tree = ast.parse(py_file.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
    return names


def test_hybrid_runner_has_zero_v5_imports():
    """Regression test for a real coupling violation found during Phase 3 closure
    audit: this file previously imported V5_VERIFIED/run_condition_b_v5 directly
    from campaign_v5_runner.py. Fixed by promoting the reasoning mechanism to
    canonical_verified_reasoning.py. This test parses the actual import statements
    (not just a manual read) so any future regression is caught automatically."""
    imports = _imported_module_names(_module_source_path(hybrid))
    v5_imports = {name for name in imports if "v5" in name.lower() or "V5" in name}
    assert not v5_imports, f"campaign_v3_hybrid_runner.py must have zero V5 imports, found: {v5_imports}"


def test_canonical_verified_reasoning_has_zero_v5_imports():
    """The promoted reasoning module itself must also be V5-free -- it's a
    relocated duplicate, not a wrapper around the original V5 file."""
    from phase3.evaluation.agent_runtime import canonical_verified_reasoning

    imports = _imported_module_names(_module_source_path(canonical_verified_reasoning))
    v5_imports = {name for name in imports if "v5" in name.lower() or "V5" in name}
    assert not v5_imports, f"canonical_verified_reasoning.py must have zero V5 imports, found: {v5_imports}"


def test_run_condition_b_hybrid_makes_at_most_three_llm_calls_per_task():
    """Bounded-by-construction check using a scripted fake provider, same
    discipline as the original v5_reasoning_pipeline tests -- confirms the
    promotion preserved the exact call-count bound, not just the function names."""
    import json

    from phase3.evaluation.llm.provider import GenerationResult

    class _ScriptedProvider:
        def __init__(self, script):
            self._script = list(script)
            self.calls = 0

        def generate(self, messages, config):
            self.calls += 1
            text, finish_reason = self._script[self.calls - 1]
            return GenerationResult(
                text=text, finish_reason=finish_reason, prompt_tokens=None,
                completion_tokens=None, latency_sec=0.0, server_fingerprint=None, raw_response={},
            )

        def configuration_fingerprint(self, config):
            return "fp"

        def model_metadata(self):
            return {}

    class _TaskShim:
        def __init__(self, task_id, dataset, question, answer, evidence_memory_ids):
            self.task_id = task_id
            self.dataset = dataset
            self.question = question
            self.answer = answer
            self.evidence_memory_ids = evidence_memory_ids

    revise_json = json.dumps({"commits_to_answer": False, "grounded": True, "verdict": "REVISE", "instruction": "Be direct."})
    provider = _ScriptedProvider([
        ("The memory does not specify.", "stop"),
        (revise_json, "stop"),
        ("A few months.", "stop"),
    ])
    task = _TaskShim("t1", "locomo", "How long?", "A few months", [])

    results = hybrid.run_condition_b_hybrid([task], provider, generation_config=None, campaign_id="test")
    assert provider.calls == 3
    assert results[0]["status"] == "SUCCESSFUL_EVALUATION"
    assert results[0]["trace"]["v3_hybrid_reasoning"]["was_revised"] is True
