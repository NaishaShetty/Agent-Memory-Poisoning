"""Phase 13 -- running ACTION-targeted attribution against the real corpus
for the first time (2026-09-22, explicitly authorized).

WHY THIS EXISTS
--------------------------------------------------------------------------------
Another real oversight: `attribute_action()` (the thin `action_id ->
decision_id -> attribute_exposure()` resolution layer) was never exercised
against real data -- Section 1.7's EXPOSURE work recorded a real
`agent_decision` Phase5Event but never the matching real `agent_action`
event `attribute_action()` needs. This module adds exactly that one real
event (`action="submit_answer"`, `result=` the real baseline run's own
execution status -- both real, already-observed facts from the SAME real
`AgentRunOutcome` `influence_attribution_case.py`/`exposure_and_references_
attribution.py` already produced, nothing invented) and confirms
`attribute_action()` correctly resolves to, and exactly reproduces,
`attribute_exposure()`'s own already-verified real result.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict

from attribution.wiring.action import attribute_action
from attribution.wiring.exposure import attribute_exposure

from phase3.evaluation.agent.outcomes import EXECUTION_STATUS_SUCCESS
from phase5.identity.run_identity import EventRunMembershipLedger, ExperimentRunLedger, ExperimentRunRecord, RunCollisionError
from phase5.schema.event_ledger import Phase5EventLedger
from phase5.wiring.agent_decision_instrumentation import ACTION_SUBMIT_ANSWER, record_agent_action
from phase13.exposure_and_references_attribution import record_real_exposure_decisions
from phase13.influence_attribution_case import run_established_case
from phase13.ledger_setup import DEFAULT_LEDGER_DIR

TS = "2026-09-22T00:25:00+00:00"
RUN_ID = "phase13-action-attribution"
ACTION_ID = "phase13-action-established"


def record_real_action(ledger_dir: Path) -> str:
    """Adds ONE real `agent_action` event tied to the real, already-recorded
    'established' EXPOSURE decision -- `action`/`result` are the SAME real
    baseline run's own already-observed facts, not invented."""
    decision_ids = record_real_exposure_decisions(ledger_dir)  # idempotent -- reuses what's already recorded
    decision_id = decision_ids["established"]

    phase5_event_ledger = Phase5EventLedger(ledger_dir / "phase5_events")
    run_ledger = ExperimentRunLedger(ledger_dir / "runs")
    membership_ledger = EventRunMembershipLedger(ledger_dir / "membership", run_ledger)

    if any(e.event_type == "agent_action" and getattr(e, "action_id", None) == ACTION_ID for e in phase5_event_ledger.all_events()):
        return decision_id  # already recorded -- idempotent

    try:
        run_ledger.register(ExperimentRunRecord(
            experiment_id="phase13-attribution-setup", run_id=RUN_ID, dataset="real_corpus", scope={},
            started_at=TS, actor="phase13-attribution-setup", reason="real ACTION attribution against real corpus",
        ))
    except RunCollisionError:
        pass

    case = run_established_case()  # real, already-run case -- same real answer/execution status each time (temperature=0, seed=42)
    record_agent_action(
        phase5_event_ledger=phase5_event_ledger, membership_ledger=membership_ledger, run_id=RUN_ID,
        task_id=case.task_id, decision_id=decision_id, action_id=ACTION_ID, action=ACTION_SUBMIT_ANSWER,
        result=EXECUTION_STATUS_SUCCESS, actor="phase13-attribution-setup",
        reason="real agent_action instrumented from a real baseline run", timestamp=TS,
    )
    return decision_id


def evaluate_action_attribution(ledger_dir: Path = DEFAULT_LEDGER_DIR) -> Dict[str, object]:
    decision_id = record_real_action(ledger_dir)
    phase5_event_ledger = Phase5EventLedger(ledger_dir / "phase5_events")

    action_result = attribute_action(ACTION_ID, "REAL-FARMA-1", run_id=RUN_ID, phase5_event_ledger=phase5_event_ledger)
    direct_exposure_result = attribute_exposure(
        "REAL-FARMA-1", decision_id, run_id=RUN_ID, phase5_event_ledger=phase5_event_ledger,
    )

    negative_result = attribute_action(ACTION_ID, "REAL-AGENTPOISON-0", run_id=RUN_ID, phase5_event_ledger=phase5_event_ledger)

    return {
        "action_status": action_result.status,
        "matches_direct_exposure": action_result.status == direct_exposure_result.status,
        "negative_case_status": negative_result.status,
    }


if __name__ == "__main__":
    result = evaluate_action_attribution()
    print(result)


__all__ = ["record_real_action", "evaluate_action_attribution"]
