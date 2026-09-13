"""Phase 5.6 -- Agent Decision & Action Instrumentation.

WHAT EXISTS ALREADY
--------------------------------------------------------------------------------
- `agent_runtime/trace.py::evaluate_and_trace()` -- a real, tested, rich per-task trace,
  but confirmed (Stage 5.1's audit) to be an EVALUATION-TIME trace: it requires
  evaluator-only inputs (`expected_answer`, `gold_evidence_ids`) supplied by a caller
  outside the live agent runtime, and its own `used_memories`/`contributed_memories`
  fields are honestly marked `NOT_OBSERVABLE`. `runner.py` never calls it -- it is not
  part of the live decision path any Phase 4 attack campaign actually executes.
- `agent_runtime/runner.py::generate_with_retries()` -- the real, frozen retry loop every
  Phase 4 attack's `campaign_runner.retrieve_select_generate()` already calls. Confirmed
  by direct read: it returns `(generation_text, attempts)` -- the underlying
  `GenerationResult.finish_reason` the LLM provider actually returned is read internally
  but NEVER propagated out; only `.text` survives into the returned tuple.
- `llm.provider.LLMProvider.model_metadata()`/`.configuration_fingerprint()` -- real,
  deterministic, already used by `campaign_runner.py` itself
  (`run_config.llm_provider.configuration_fingerprint(run_config.generation_config)`) --
  reused verbatim here, not recomputed a second way.
- `agent.outcomes.AgentExecutionResult` -- confirmed by direct read: this framework has
  no concept of an "action" distinct from the generated answer for LoCoMo-style QA tasks;
  `execution_status` (SUCCESS/ERROR/SKIPPED/TIMEOUT) is the closest existing concept to an
  action's *result*.

THE GAP THIS MODULE CLOSES
--------------------------------------------------------------------------------
No live decision/action telemetry exists at all for a Phase 4 attack campaign run
(contract OR-8/OR-9/OR-10) -- `evaluate_and_trace()` is evaluation-time-only and never
called from the live path.

WHY `finish_reason` IS A DERIVED VALUE, NOT THE LITERAL PROVIDER STRING (disclosed, not silently guessed)
--------------------------------------------------------------------------------
Since `generate_with_retries()` (frozen) discards the real `GenerationResult.finish_reason`
before returning, and this module does not call the LLM provider a second time just to
recover it (that would be a real, undesirable extra generation call, and could legitimately
return a DIFFERENT result if the provider is not perfectly deterministic) -- `finish_reason`
on the `agent_decision` event here is DERIVED from `generate_with_retries()`'s own returned
outcome shape (`GENERATED` if `generation_text is not None`, `FAILED_ALL_ATTEMPTS`
otherwise), never the literal `"stop"`/`"length"`/etc. string the provider itself returned.
This is recorded honestly under those two distinct constant names -- never spelled to look
like a real provider finish_reason -- so a reader is never misled into thinking this module
observed something it did not.

WHY `used_memories_observability` IS ALWAYS `NOT_OBSERVABLE` IN THE LIVE PIPELINE (OR-10)
--------------------------------------------------------------------------------
Confirmed by the Stage 5.1 audit: this framework's own `evaluate_and_trace()` marks
`used_memories` `NOT_OBSERVABLE` because nothing in the runtime implements citation-based
usage attribution beyond a separate heuristic in `citation.py` that this live pipeline
does not invoke. `instrument_agent_decision()` therefore always records
`used_memories_observability=NOT_OBSERVABLE` -- never fabricating an "OBSERVED" claim the
runtime cannot back up. A caller with a genuinely observed usage signal (e.g. a citation
heuristic run separately) may still call `record_agent_decision()` directly with
`used_memories_observability=OBSERVED`.

`ACTION` FOR A QA TASK: SUBMITTING THE ANSWER (OR-9)
--------------------------------------------------------------------------------
LoCoMo-style QA tasks have no action distinct from generation, but the framework's own
`AgentExecutionResult.execution_status` already models submitting an answer as having a
real outcome (SUCCESS/ERROR). `instrument_agent_decision()` therefore also records one
`agent_action` event per decision -- `action="submit_answer"`, `result=execution_status`
-- rather than leaving OR-9 wired but never exercised by the one task shape this
framework's frozen attack campaigns actually run today. A future action-shaped task
(tool use, an environment step) would call `record_agent_action()` directly with its own
real action/result, not through this QA-specific convenience wrapper.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import List, Mapping, Optional, Sequence, Tuple

from phase3.evaluation.agent.outcomes import EXECUTION_STATUS_ERROR, EXECUTION_STATUS_SUCCESS
from phase3.evaluation.agent_runtime.runner import GenerationAttempt, RunConfiguration, generate_with_retries

from phase5.identity.run_identity import EVENT_SCHEMA_PHASE5_EVENT, EventRunMembership, EventRunMembershipLedger
from phase5.schema.event import AGENT_ACTION, AGENT_DECISION, Phase5Event, generate_phase5_event_id
from phase5.schema.event_ledger import Phase5EventLedger

FINISH_REASON_GENERATED = "GENERATED"
FINISH_REASON_FAILED_ALL_ATTEMPTS = "FAILED_ALL_ATTEMPTS"

USED_MEMORIES_NOT_OBSERVABLE = "NOT_OBSERVABLE"
USED_MEMORIES_OBSERVED = "OBSERVED"

ACTION_SUBMIT_ANSWER = "submit_answer"


def record_agent_decision(
    *,
    phase5_event_ledger: Phase5EventLedger,
    membership_ledger: EventRunMembershipLedger,
    run_id: str,
    task_id: str,
    decision_id: str,
    exposed_memory_ids: Tuple[str, ...],
    output: str,
    finish_reason: str,
    model_identity: str,
    config_fingerprint: str,
    used_memories_observability: str,
    actor: str,
    reason: str,
    timestamp: str,
    episode_id: Optional[str] = None,
) -> Phase5Event:
    """Instruments one agent decision (contract OR-8, OR-10). Thin: builds and appends
    one `agent_decision` `Phase5Event` and registers its membership -- no inference, no
    derivation performed here (that is `instrument_agent_decision()`'s job below); a
    caller with its own real decision data may call this directly.
    """
    kwargs = dict(
        event_type=AGENT_DECISION, timestamp=timestamp, actor=actor, reason=reason,
        task_id=task_id, config_fingerprint=config_fingerprint, decision_id=decision_id,
        exposed_memory_ids=tuple(exposed_memory_ids), output=output, finish_reason=finish_reason,
        model_identity=model_identity, used_memories_observability=used_memories_observability,
    )
    event_id = generate_phase5_event_id(**kwargs)
    event = Phase5Event(event_id=event_id, **kwargs)
    phase5_event_ledger.append(event)
    membership_ledger.append(
        EventRunMembership(
            event_id=event.event_id, event_schema=EVENT_SCHEMA_PHASE5_EVENT,
            run_id=run_id, episode_id=episode_id, recorded_at=timestamp,
        )
    )
    return event


def record_agent_action(
    *,
    phase5_event_ledger: Phase5EventLedger,
    membership_ledger: EventRunMembershipLedger,
    run_id: str,
    task_id: str,
    decision_id: str,
    action_id: str,
    action: str,
    result: str,
    actor: str,
    reason: str,
    timestamp: str,
    episode_id: Optional[str] = None,
) -> Phase5Event:
    """Instruments one agent action (contract OR-9), linked back to the decision that
    produced it via `decision_id`. Generic -- not QA/LoCoMo-specific."""
    kwargs = dict(
        event_type=AGENT_ACTION, timestamp=timestamp, actor=actor, reason=reason,
        task_id=task_id, decision_id=decision_id, action_id=action_id, action=action, result=result,
    )
    event_id = generate_phase5_event_id(**kwargs)
    event = Phase5Event(event_id=event_id, **kwargs)
    phase5_event_ledger.append(event)
    membership_ledger.append(
        EventRunMembership(
            event_id=event.event_id, event_schema=EVENT_SCHEMA_PHASE5_EVENT,
            run_id=run_id, episode_id=episode_id, recorded_at=timestamp,
        )
    )
    return event


@dataclass(frozen=True)
class InstrumentedGenerationResult:
    """Result of `instrument_agent_decision()` -- carries the real, unmodified
    `generate_with_retries()` output alongside the two events this stage recorded, so a
    caller building `AgentExecutionResult`/`AgentRunOutcome` (as `campaign_runner.py`
    itself does) has everything it needs without re-deriving it."""

    generation_text: Optional[str]
    attempts: Tuple[GenerationAttempt, ...]
    decision_event: Phase5Event
    action_event: Phase5Event


def instrument_agent_decision(
    *,
    phase5_event_ledger: Phase5EventLedger,
    membership_ledger: EventRunMembershipLedger,
    run_id: str,
    task_id: str,
    decision_id: str,
    action_id: str,
    exposed_memory_ids: Tuple[str, ...],
    messages: List[Mapping[str, str]],
    run_config: RunConfiguration,
    actor: str,
    timestamp: str,
    episode_id: Optional[str] = None,
) -> InstrumentedGenerationResult:
    """Calls the real, frozen `generate_with_retries()` exactly once (never
    reimplemented, never called twice), then instruments the resulting decision (OR-8,
    with `used_memories_observability` always `NOT_OBSERVABLE` -- OR-10) and, for the
    current QA-task shape, one `submit_answer` action (OR-9) recording whether that
    generation succeeded.
    """
    generation_text, attempts = generate_with_retries(messages, run_config)

    finish_reason = FINISH_REASON_GENERATED if generation_text is not None else FINISH_REASON_FAILED_ALL_ATTEMPTS
    config_fingerprint = run_config.llm_provider.configuration_fingerprint(run_config.generation_config)
    model_identity = json.dumps(dict(run_config.llm_provider.model_metadata()), sort_keys=True)

    decision_event = record_agent_decision(
        phase5_event_ledger=phase5_event_ledger, membership_ledger=membership_ledger, run_id=run_id,
        task_id=task_id, decision_id=decision_id, exposed_memory_ids=tuple(exposed_memory_ids),
        output=generation_text if generation_text is not None else "",
        finish_reason=finish_reason, model_identity=model_identity, config_fingerprint=config_fingerprint,
        used_memories_observability=USED_MEMORIES_NOT_OBSERVABLE,
        actor=actor, reason="generation completed via generate_with_retries().", timestamp=timestamp,
        episode_id=episode_id,
    )

    execution_status = EXECUTION_STATUS_SUCCESS if generation_text is not None else EXECUTION_STATUS_ERROR
    action_event = record_agent_action(
        phase5_event_ledger=phase5_event_ledger, membership_ledger=membership_ledger, run_id=run_id,
        task_id=task_id, decision_id=decision_id, action_id=action_id, action=ACTION_SUBMIT_ANSWER,
        result=execution_status, actor=actor,
        reason="answer submitted as this QA task's terminal action.", timestamp=timestamp, episode_id=episode_id,
    )

    return InstrumentedGenerationResult(
        generation_text=generation_text, attempts=attempts, decision_event=decision_event, action_event=action_event,
    )


__all__ = [
    "FINISH_REASON_GENERATED",
    "FINISH_REASON_FAILED_ALL_ATTEMPTS",
    "USED_MEMORIES_NOT_OBSERVABLE",
    "USED_MEMORIES_OBSERVED",
    "ACTION_SUBMIT_ANSWER",
    "record_agent_decision",
    "record_agent_action",
    "InstrumentedGenerationResult",
    "instrument_agent_decision",
]
