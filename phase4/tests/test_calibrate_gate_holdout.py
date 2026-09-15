"""Phase 4 P1 regression tests -- MemoryGraft calibration hold-out split
(`phase4/attacks/memorygraft/calibrate_gate.py`), the fix for the audit
finding that the gate's prompt (persistence_gate.py, "REVISION 2") was
rewritten specifically because it failed CALIBRATION_CASES' own Tier 3, then
re-tested on those same cases plus two more added in the same revision --
with no case held out from that authoring process. Uses the same scripted
mock HTTP transport as `test_persistence_gate.py` -- no real server needed
to test that the CODE correctly separates the two case sets.
"""

from __future__ import annotations

import json

from phase3.evaluation.llm.provider import GenerationConfig, LlamaServerEndpoint, LlamaServerProvider, _RawHttpResponse

from phase4.attacks.memorygraft.calibrate_gate import (
    CALIBRATION_CASES,
    HOLD_OUT_CASES,
    run_calibration,
    run_holdout_validation,
)
from phase4.attacks.memorygraft.persistence_gate import DECISION_DISCARD, DECISION_KEEP


def _scripted_provider(decision_for_artifact_id) -> LlamaServerProvider:
    """`decision_for_artifact_id`: callable(artifact_id) -> "KEEP"|"DISCARD".
    Lets a test script the gate's reply per-artifact, deterministically,
    mirroring `test_persistence_gate.py`'s own established mock-transport
    pattern -- no real server anywhere in this file."""

    def post_json(url: str, body: bytes, timeout: float) -> _RawHttpResponse:
        # artifact_id is never rendered into the real gate prompt (only
        # req/resp are -- see persistence_gate.py's _build_messages), so
        # identify which case is being judged by its (unique) req text,
        # exactly the information the real gate itself has access to.
        request = json.loads(body)
        prompt_text = " ".join(m.get("content", "") for m in request.get("messages", []))
        artifact_id = None
        for case in tuple(CALIBRATION_CASES) + tuple(HOLD_OUT_CASES):
            if case.artifact.req in prompt_text:
                artifact_id = case.artifact.artifact_id
                break
        decision = decision_for_artifact_id(artifact_id)
        payload = {
            "choices": [{"message": {"content": f"DECISION: {decision}\nRATIONALE: scripted for test."}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            "system_fingerprint": "b10717-a32af33de",
        }
        return _RawHttpResponse(status=200, body=json.dumps(payload).encode("utf-8"))

    return LlamaServerProvider(endpoint=LlamaServerEndpoint(), post_json=post_json)


def _config() -> GenerationConfig:
    return GenerationConfig(temperature=0.0, seed=42, max_tokens=64, enable_thinking=False, n_ctx=1024)


# ---------------------------------------------------------------------------
# Structural: the two case sets must never overlap.
# ---------------------------------------------------------------------------


def test_hold_out_cases_share_no_artifact_id_with_calibration_cases():
    calibration_ids = {c.artifact.artifact_id for c in CALIBRATION_CASES}
    holdout_ids = {c.artifact.artifact_id for c in HOLD_OUT_CASES}
    assert calibration_ids.isdisjoint(holdout_ids)


def test_hold_out_cases_share_no_response_text_with_calibration_cases():
    """Not just distinct ids -- distinct CONTENT, so a hold-out case cannot
    be a relabeled duplicate of an existing calibration case."""
    calibration_resp = {c.artifact.resp for c in CALIBRATION_CASES}
    holdout_resp = {c.artifact.resp for c in HOLD_OUT_CASES}
    assert calibration_resp.isdisjoint(holdout_resp)


def test_hold_out_cases_cover_both_decision_directions():
    """A hold-out set that only ever expects one decision would not be a
    real discrimination test."""
    expected = {c.expected_decision for c in HOLD_OUT_CASES}
    assert expected == {DECISION_KEEP, DECISION_DISCARD}


# ---------------------------------------------------------------------------
# Behavioral: run_calibration() and run_holdout_validation() are genuinely
# separate -- a hold-out failure must not flip run_calibration()'s own
# result, and vice versa.
# ---------------------------------------------------------------------------


def _always_matching_provider():
    expected_by_id = {
        c.artifact.artifact_id: c.expected_decision for c in tuple(CALIBRATION_CASES) + tuple(HOLD_OUT_CASES)
    }
    return _scripted_provider(lambda aid: expected_by_id.get(aid, DECISION_KEEP))


def test_run_calibration_passes_independently_of_holdout_outcome():
    """Script the provider to match CALIBRATION_CASES perfectly but FAIL
    every HOLD_OUT_CASE (always answer the opposite of what's expected) --
    run_calibration()'s own return value must be True regardless, since it
    must never read HOLD_OUT_CASES at all."""
    holdout_ids = {c.artifact.artifact_id for c in HOLD_OUT_CASES}
    calibration_expected = {c.artifact.artifact_id: c.expected_decision for c in CALIBRATION_CASES}

    def decision_for(aid):
        if aid in holdout_ids:
            return DECISION_DISCARD if False else DECISION_KEEP  # deliberately wrong either way below
        return calibration_expected.get(aid, DECISION_KEEP)

    # Force every hold-out case to receive the WRONG decision explicitly.
    wrong_for_holdout = {
        c.artifact.artifact_id: (DECISION_DISCARD if c.expected_decision == DECISION_KEEP else DECISION_KEEP)
        for c in HOLD_OUT_CASES
    }

    def decision_fn(aid):
        if aid in wrong_for_holdout:
            return wrong_for_holdout[aid]
        return calibration_expected.get(aid, DECISION_KEEP)

    provider = _scripted_provider(decision_fn)
    assert run_calibration(provider, _config()) is True


def test_run_holdout_validation_does_not_affect_calibration_cases():
    """Symmetric check: script every CALIBRATION_CASE to fail, every
    HOLD_OUT_CASE to pass -- run_holdout_validation() must report True,
    proving it only ever reads HOLD_OUT_CASES."""
    wrong_for_calibration = {
        c.artifact.artifact_id: (DECISION_DISCARD if c.expected_decision == DECISION_KEEP else DECISION_KEEP)
        for c in CALIBRATION_CASES
    }
    holdout_expected = {c.artifact.artifact_id: c.expected_decision for c in HOLD_OUT_CASES}

    def decision_fn(aid):
        if aid in wrong_for_calibration:
            return wrong_for_calibration[aid]
        return holdout_expected.get(aid, DECISION_KEEP)

    provider = _scripted_provider(decision_fn)
    assert run_calibration(provider, _config()) is False
    assert run_holdout_validation(provider, _config()) is True


def test_both_pass_when_provider_matches_every_case():
    provider = _always_matching_provider()
    assert run_calibration(provider, _config()) is True
    assert run_holdout_validation(provider, _config()) is True


def test_holdout_failure_is_detected_not_silently_swallowed():
    holdout_expected = {c.artifact.artifact_id: c.expected_decision for c in HOLD_OUT_CASES}
    calibration_expected = {c.artifact.artifact_id: c.expected_decision for c in CALIBRATION_CASES}
    first_holdout_id = HOLD_OUT_CASES[0].artifact.artifact_id
    wrong_first = DECISION_DISCARD if HOLD_OUT_CASES[0].expected_decision == DECISION_KEEP else DECISION_KEEP

    def decision_fn(aid):
        if aid == first_holdout_id:
            return wrong_first
        return {**calibration_expected, **holdout_expected}.get(aid, DECISION_KEEP)

    provider = _scripted_provider(decision_fn)
    assert run_calibration(provider, _config()) is True  # unaffected
    assert run_holdout_validation(provider, _config()) is False
