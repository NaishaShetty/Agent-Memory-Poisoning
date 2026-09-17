"""Phase 7.23 -- tests for real_retrieval_pipeline_study.py: closes Report
Limitation 5.5 (the retrieval-pool-narrowing gap) using RealMem0Adapter's
real embedding-based retrieve() instead of MockMem0Adapter's hand-picked
candidate lists. Requires C:\\h4venv; self-skips elsewhere (mirroring
phase5/tests/test_real_vendor_compatibility_gate.py's own convention).

Real, measured results (see module docstring for the full analysis):
- Sleeper: FULLY closes 5.5 -- the real pipeline reproduces the exact
  historical dormant/active discrimination (selected for exact/paraphrased/
  near/partial, NOT for distant).
- AgentPoison: PARTIALLY closes 5.5 -- the real retrieval-pool-narrowing
  mechanism itself is proven to fire exactly as history recorded (the
  trigger condition's retrieved pool narrows to exactly the poison memory,
  1 item), but full benign/trigger discrimination is not reproduced in this
  run (the poison is also selected under the benign query). Reported
  honestly as a partial result, not forced to a false "closed."
"""

from __future__ import annotations

import pytest

from phase7.propagation.real_retrieval_pipeline_study import (
    is_real_mem0_available,
    run_agentpoison_real_retrieval_study,
    run_sleeper_real_retrieval_study,
)


def _skip_if_unavailable():
    if not is_real_mem0_available():
        pytest.skip(
            "RealMem0Adapter unavailable in this environment -- this test is written in full for a "
            "real-Mem0-stack session (C:\\h4venv's interpreter); NOT VALIDATED here."
        )


def test_agentpoison_real_pipeline_narrows_trigger_pool_to_exactly_the_poison(tmp_path):
    _skip_if_unavailable()
    result = run_agentpoison_real_retrieval_study()
    # The real, historically-matching finding: the real embedding-based
    # retrieve() stage narrows the trigger-condition pool down to exactly
    # the poisoned memory -- proving the retrieval-pool-narrowing mechanism
    # this harness previously could not exercise now genuinely fires.
    assert result.trigger_retrieved_ids == (result.poison_memory_id,)
    assert result.selected_in_trigger_condition is True


def test_agentpoison_real_pipeline_benign_condition_also_retrieves_the_poison(tmp_path):
    _skip_if_unavailable()
    result = run_agentpoison_real_retrieval_study()
    # Honest, disclosed partial result: unlike the historical campaign, this
    # run's benign condition also selects the poison -- full discrimination
    # is not reproduced here, only the narrowing mechanism itself.
    assert result.poison_memory_id in result.benign_retrieved_ids
    assert result.selected_in_benign_condition is True
    assert result.discriminates is False


def test_sleeper_real_pipeline_fully_discriminates_dormant_vs_active(tmp_path):
    _skip_if_unavailable()
    result = run_sleeper_real_retrieval_study()
    # Full closure for Sleeper: the real pipeline reproduces the exact
    # historical discrimination.
    assert result.selected_by_condition["exact"] is True
    assert result.selected_by_condition["paraphrased"] is True
    assert result.selected_by_condition["near"] is True
    assert result.selected_by_condition["partial"] is True
    assert result.selected_by_condition["distant"] is False
    assert result.discriminates is True
