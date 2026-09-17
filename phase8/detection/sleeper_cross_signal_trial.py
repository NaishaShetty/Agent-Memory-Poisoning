"""Phase 8.6 -- Cross-Signal Real Trial.

`docs/phase8/PHASE8_PLAN.md` Stage 8.6: run all four Phase 8 signals together against
ONE real, full Sleeper lifecycle (the real `RealMem0Adapter`-backed pipeline Stage 8.5
uses), and report what each signal says at each real point in that lifecycle -- before,
during, and after the real activation transition Phase 7 already proved is observable.

REAL TASK ORDER -- REORDERED, NEVER FABRICATED
--------------------------------------------------------------------------------
Stage 8.5's own real, measured result (this session, real embeddings) was: selected under
exact/paraphrased/near/partial, NOT under distant -- the same historical discrimination
`phase7/tests/test_real_retrieval_pipeline_study.py` already validated. This module uses
the SAME real 5 queries (`phase7.propagation.sleeper_study.TRIGGER_CONDITIONS`, imported
unmodified), only reordered into a real chronological narrative that a single real run can
exhibit: `distant` (before -- real, measured non-selection) -> `partial` (during -- the
first real selection in this ordering) -> `near` -> `paraphrased` -> `exact` (after --
continued real selection). No query text, content, or result is invented; only the ORDER
in which the same 5 real queries are issued is a deliberate choice.

WHAT EACH SIGNAL CONTRIBUTES AT EACH REAL POINT
--------------------------------------------------------------------------------
- Signal 1 (`real_prior_retrieval_count`, Stage 8.2) and its feed into
  `evaluate_sleeper_retrieval_risk()` (frozen Phase 6): recomputed after each real task,
  from the real, growing `Phase5EventLedger` this trial itself builds via
  `instrument_retrieval_and_selection()` (frozen Phase 5) over real retrieved/inspected
  candidates -- never hand-typed.
- Content signal (`imperative_write_directive_signal()`, frozen Phase 6): computed ONCE
  against the real, unmodified `SEED_DESTRESS.forged_memory_text` -- Stage 8.3's own real
  finding is that this scores 0.0 (a MISS) regardless of retrieval history, since the real
  campaign artifact's content was never imperative-shaped to begin with. This trial
  reports that real score at every point rather than silently omitting the content term.
- Signal 2 (`real_dormancy_window`, Stage 8.4): recomputed after each real task from
  `derive_ground_truth_transitions()` (frozen post-Phase-5 hardening) run fresh over
  the ledger's CURRENT real state -- so `ever_selected`/`tasks_scored_before_first_
  selection`/`elapsed_seconds` genuinely reflect only what has REALLY happened by that
  point in the trial, never evidence from a later task read backward in time.
- Signal 4 (activation-shape, Stage 8.5): computed ONCE at the end, from the real
  `selected` outcome this trial's own five real tasks already recorded (in the ORIGINAL
  exact/paraphrased/near/partial/distant order, per `ORDERED_CONDITION_NAMES`) -- not a
  second real pipeline run; the same real per-task facts this trial already produced are
  reused, never recomputed from a duplicate call.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from phase3.evaluation.foundations.adapter import FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL
from phase3.evaluation.foundations.hybrid_selection import RETRIEVAL_POOL_SIZE_N

from phase5.wiring.attack_integration import instrument_attack_memory_lifecycle
from phase5.wiring.ground_truth import derive_ground_truth_transitions
from phase5.wiring.retrieval_instrumentation import instrument_retrieval_and_selection

from phase6.defense.policy.states import UNASSESSED
from phase6.defense.signals.contract import build_signal_context
from phase6.defense.sleeper.signals import imperative_write_directive_signal
from phase6.defense.sleeper.sleeper_guard import evaluate_sleeper_retrieval_risk

from phase7.propagation.attack_study import new_study_ledgers
from phase7.propagation.real_retrieval_pipeline_study import USER_ID, is_real_mem0_available
from phase7.propagation.sleeper_study import TRIGGER_CONDITIONS

from phase8.detection.sleeper_activation_shape_study import (
    ORDERED_CONDITION_NAMES,
    _ingest_real_locomo_pool_capturing_ids,
    matches_dormant_activation_pattern,
)
from phase8.detection.sleeper_dormancy_signals import real_prior_retrieval_count
from phase8.detection.sleeper_dormancy_window import real_dormancy_window

CFG = "CFG-phase8-cross-signal-trial"

# Real chronological narrative built from the SAME real 5 conditions, reordered (module
# docstring) -- "before" (distant, real non-selection) -> "during" (partial, the first
# real selection in this order) -> "after" (near, paraphrased, exact -- continued real
# selection).
_TRIAL_TASK_ORDER: Tuple[str, ...] = ("distant", "partial", "near", "paraphrased", "exact")


def _real_retrieve_candidates(foundation, query: str, *, pool_size: int) -> List[Tuple[str, str]]:
    """The real retrieve -> inspect half of the real two-stage pipeline (stops BEFORE
    `select_by_hybrid_score()`, unlike `real_retrieval_pipeline_study._real_retrieve_
    then_select()`, which bundles both) -- this trial needs the raw candidate pool so
    `instrument_retrieval_and_selection()` (frozen Phase 5) can run the real scoring AND
    record real `Phase5Event`s in the same step, rather than scoring twice."""
    from phase3.evaluation.agent_runtime.runner import _extract_content_text, _extract_memory_id

    retrieve_field = foundation.retrieve({"text": query, "user_id": USER_ID}, top_k=pool_size)
    if retrieve_field.availability not in (FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL):
        return []
    raw_items = retrieve_field.value or []
    retrieved_ids = [mid for mid in (_extract_memory_id(i) for i in raw_items) if mid is not None]
    candidates: List[Tuple[str, str]] = []
    for mid in retrieved_ids:
        inspect_field = foundation.inspect_memory(mid)
        if inspect_field.availability in (FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL):
            candidates.append((mid, _extract_content_text(inspect_field.value or {})))
    return candidates


@dataclass(frozen=True)
class CrossSignalTaskReading:
    task_id: str
    condition_name: str
    query: str
    real_selected: bool
    real_prior_retrieval_count: int
    retrieval_risk_action: str
    retrieval_risk_gated_score: float
    dormancy_window_ever_selected: bool
    dormancy_window_tasks_scored_before_first_selection: Optional[int]
    dormancy_window_elapsed_seconds: Optional[float]


@dataclass(frozen=True)
class CrossSignalTrialResult:
    poison_memory_id: str
    content_directive_score: float
    task_readings: Tuple[CrossSignalTaskReading, ...]
    activation_shape_selected_sequence: Tuple[bool, ...]  # exact/paraphrased/near/partial/distant order
    activation_shape_transition_count: int
    activation_shape_matches_dormant_pattern: bool  # the tight criterion -- see sleeper_activation_shape_study.py


def run_cross_signal_real_trial(storage_dir, *, pool_size: int = RETRIEVAL_POOL_SIZE_N, top_k: int = 8) -> CrossSignalTrialResult:
    """Runs one real, full Sleeper lifecycle through the real `RealMem0Adapter` pipeline,
    applying all four Phase 8 signals at each real point. `storage_dir` must be a fresh,
    empty directory (same convention as `sleeper_study.run_sleeper_trigger_sweep_study()`).
    Requires `C:\\h4venv`'s interpreter; call `is_real_mem0_available()` first.
    """
    from phase3.evaluation.agent_runtime.messages import DEFAULT_SYSTEM_PROMPT
    from phase3.evaluation.agent_runtime.runner import RunConfiguration
    from phase3.evaluation.foundations_real.mem0_real_adapter import RealMem0Adapter
    from phase3.evaluation.llm.provider import GenerationConfig, LlamaServerEndpoint, LlamaServerProvider, _RawHttpResponse
    from phase4.attacks.sleeper_memory_poisoning.artifact import SEED_DESTRESS
    from phase4.attacks.sleeper_memory_poisoning.injector import SleeperInjector

    import json as _json

    def _scripted_gate_provider(reply: str) -> LlamaServerProvider:
        def post_json(url: str, body: bytes, timeout: float):
            payload = {
                "choices": [{"message": {"content": reply}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
                "system_fingerprint": "phase8-cross-signal-trial",
            }
            return _RawHttpResponse(status=200, body=_json.dumps(payload).encode("utf-8"))
        return LlamaServerProvider(endpoint=LlamaServerEndpoint(), post_json=post_json)

    foundation = RealMem0Adapter()
    init_field = foundation.initialize({})
    if init_field.availability not in (FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL):
        raise RuntimeError(f"RealMem0Adapter unavailable ({init_field.availability}) -- run under C:\\h4venv.")
    foundation.reset()

    _ingest_real_locomo_pool_capturing_ids(foundation)

    ledgers = new_study_ledgers(storage_dir, "sleeper-cross-signal-trial", reason="Phase 8.6 cross-signal real trial")

    injector = SleeperInjector(foundation)
    run_config = RunConfiguration(
        llm_provider=_scripted_gate_provider("DECISION: KEEP\nRATIONALE: Reasonable."),
        generation_config=GenerationConfig(temperature=0.0, seed=42, max_tokens=64, enable_thinking=False, n_ctx=2048),
        system_prompt=DEFAULT_SYSTEM_PROMPT, max_retries=0,
    )
    admission_ts = "2026-09-16T00:00:00+00:00"
    result = injector.inject(SEED_DESTRESS, run_config, extra_metadata={"user_id": USER_ID})
    lifecycle_result = instrument_attack_memory_lifecycle(
        "sleeper_memory_poisoning", result,
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], actor="phase8_cross_signal_trial", reason="admitted", timestamp=admission_ts,
    )
    poison_memory_id = result.canonical_memory_id
    if poison_memory_id is None:
        raise RuntimeError("Sleeper injection was not admitted (scripted KEEP gate) -- a real environment problem.")

    content_context = build_signal_context(
        memory_id=poison_memory_id, content_text=SEED_DESTRESS.forged_memory_text, content_type="text",
        memory_type="foundation", parent_ids=(), lifecycle_state="ACTIVE", creation_timestamp=admission_ts,
    )
    content_directive_score = imperative_write_directive_signal(content_context)["imperative_write_directive_score"]

    condition_lookup = dict(TRIGGER_CONDITIONS)
    task_readings: List[CrossSignalTaskReading] = []
    selected_by_condition = {}

    for i, condition_name in enumerate(_TRIAL_TASK_ORDER):
        query = condition_lookup[condition_name]
        task_id = f"task-{i}-{condition_name}"
        task_ts = f"2026-09-16T00:{i + 1:02d}:00+00:00"

        candidates = _real_retrieve_candidates(foundation, query, pool_size=pool_size)
        report = instrument_retrieval_and_selection(
            memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
            phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
            run_id=ledgers["run_id"], task_id=task_id, query=query,
            candidates=candidates, config_fingerprint=CFG, actor="phase8_cross_signal_trial",
            timestamp=task_ts, top_k=top_k,
        )
        real_selected = poison_memory_id in {e.memory_id for e in report.candidate_scored_events if e.selected}
        selected_by_condition[condition_name] = real_selected

        prior_count = real_prior_retrieval_count(
            poison_memory_id, phase5_event_ledger=ledgers["phase5_ledger"], as_of_task_id=task_id,
        )
        risk_decision = evaluate_sleeper_retrieval_risk(
            poison_memory_id, content_context, prior_count, UNASSESSED,
            run_id=ledgers["run_id"], episode_id=f"ep-{i}", timestamp=task_ts,
            evidence_refs=("phase8-cross-signal-trial",),
        )

        transitions = derive_ground_truth_transitions(phase5_event_ledger=ledgers["phase5_ledger"], timestamp=task_ts)
        try:
            window = real_dormancy_window(
                poison_memory_id, phase5_event_ledger=ledgers["phase5_ledger"], ground_truth_transitions=transitions,
            )
        except ValueError:
            window = None  # POISON_ADMITTED transition not yet derivable this early -- reported honestly below.

        task_readings.append(
            CrossSignalTaskReading(
                task_id=task_id, condition_name=condition_name, query=query, real_selected=real_selected,
                real_prior_retrieval_count=prior_count,
                retrieval_risk_action=risk_decision.action,
                retrieval_risk_gated_score=risk_decision.signals_used["imperative_write_directive_score"]
                * risk_decision.signals_used["dormancy_activation_score"],
                dormancy_window_ever_selected=(window.ever_selected if window is not None else False),
                dormancy_window_tasks_scored_before_first_selection=(
                    window.tasks_scored_before_first_selection if window is not None else None
                ),
                dormancy_window_elapsed_seconds=(window.elapsed_seconds if window is not None else None),
            )
        )

    activation_sequence = tuple(selected_by_condition[name] for name in ORDERED_CONDITION_NAMES)
    transition_count = sum(1 for i in range(len(activation_sequence) - 1) if activation_sequence[i] != activation_sequence[i + 1])

    return CrossSignalTrialResult(
        poison_memory_id=poison_memory_id,
        content_directive_score=content_directive_score,
        task_readings=tuple(task_readings),
        activation_shape_selected_sequence=activation_sequence,
        activation_shape_transition_count=transition_count,
        activation_shape_matches_dormant_pattern=matches_dormant_activation_pattern(activation_sequence),
    )


__all__ = [
    "CrossSignalTaskReading",
    "CrossSignalTrialResult",
    "run_cross_signal_real_trial",
    "is_real_mem0_available",
]
