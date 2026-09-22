"""Phase 13 -- real `attack_injection` event persistence (2026-09-22,
explicitly authorized, found necessary while building the first real
attribution check).

WHY THIS EXISTS, AND WHAT WAS WRONG WITHOUT IT
--------------------------------------------------------------------------------
`attribution/wiring/origin.py::attribute_origin()` answers "which attack
produced this memory" by looking for a real `attack_injection` `Phase5Event`
that names the memory as its product (`derive_produced_edges()`). The
original `phase13/ledger_setup.py` persisted real `created` events
(`record_memory_creation()`) for all 15 `real_poison_scenarios()`, but never
called `record_attack_injection()` -- there was no `Phase5EventLedger`
entry at all. Every one of the 15 real scenarios would have attributed as
`NO_ATTACK_ORIGIN`, not because attribution failed, but because it was
never given the data it needs. This module closes that gap for real,
before any attribution metric is computed against it.

WHY A NEW MODULE, NOT A PATCH INSIDE `real_corpus.py`
--------------------------------------------------------------------------------
`real_corpus.py`'s own `_dsrm_scenarios()` etc. call each real Phase 4
injector and immediately discard the raw result object, keeping only the
extracted text -- `attribute_origin()` needs the RAW result (to normalize
via `phase5.wiring.attack_integration.NORMALIZERS`, the project's own real,
already-built per-attack field-mapping layer). Re-running each real
injector here, with the SAME real seeds/artifacts `real_corpus.py` itself
uses, keeps the raw result available for real ledger instrumentation
without touching `real_corpus.py` (a protected, already-verified module).

THE ONE DELIBERATE ID SUBSTITUTION, DISCLOSED
--------------------------------------------------------------------------------
Each attack's own injector result carries its OWN internal
`canonical_memory_id` (assigned by its own mock foundation). `real_corpus.py`
discards that and re-labels every scenario "REAL-<FAMILY>-<i>" for its own
real, project-wide naming convention -- the SAME convention
`phase12/propagation/propagation_rate.py`'s own real ledger-writing code
already uses. To keep Phase 13's attribution ledger queryable by the SAME
scenario ids the rest of Phase 12/13 uses (so a derivation event's
`source_memory_ids` and an origin attribution's `target_id` refer to the
same real memory), this module overrides ONLY the `memory_id` field on the
already-real, already-normalized injection result before recording it --
`attack_id`, `artifact_id`, `admission_status`, and `stored_text` are all
the real, unmodified values the real injector actually produced.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple

from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger
from phase4.attacks.agentpoison.injector import AgentPoisonInjector
from phase4.attacks.agentpoison.trigger_run import AgentPoisonArtifact
from phase4.attacks.dsrm.decision import AdversarialDecisionArtifact, CSRMJustification
from phase4.attacks.dsrm.injector import DSRMInjector
from phase4.attacks.dsrm.seeds import DSRM_SEEDS
from phase4.attacks.farma.injector import FARMAInjector
from phase4.attacks.farma.reasoning_trace import SEED_TRACES
from phase4.attacks.memorygraft.adapter import MemoryGraftInjector
from phase4.attacks.memorygraft.locomo_seed import SEED_RESEARCH_TOPIC
from phase4.attacks.minja.injector import MINJAInjector
from phase4.attacks.minja.milestone4_campaign import CANDIDATE_1 as MINJA_CANDIDATE_1
from phase4.attacks.mpbench.injector import MPBenchPCFIInjector
from phase4.attacks.mpbench.scenario import PCFI_SCENARIOS
from phase4.attacks.sleeper_memory_poisoning.artifact import SEED_DESTRESS
from phase4.attacks.sleeper_memory_poisoning.injector import SleeperInjector
from phase5.identity.run_identity import EventRunMembershipLedger, ExperimentRunLedger, ExperimentRunRecord
from phase5.schema.event_ledger import Phase5EventLedger
from phase5.wiring.attack_integration import (
    NORMALIZERS,
    build_attack_canonical_memory_record,
    generate_injection_id,
)
from phase5.wiring.live_attack_runs import _generation_config, _new_mock_foundation, _scripted_llm_provider
from phase5.wiring.memory_lifecycle import record_attack_injection, record_memory_creation

TS = "2026-09-22T00:00:00+00:00"


def _override_memory_id(normalized, memory_id: str):
    from dataclasses import replace

    return replace(normalized, memory_id=memory_id)


def _record_one_injection(
    attack_id: str, raw_result, scenario_id: str, *, memory_ledger, event_ledger, phase5_event_ledger,
    membership_ledger, run_id: str, stored_text_override=None,
) -> str:
    """Returns the real, deterministically-minted `injection_id` this
    scenario was recorded under -- real ground truth for
    `attribution.metrics.origin_attribution_accuracy()`, not a value
    invented after the fact (it is the SAME value `record_attack_injection()`
    itself persists, recomputed here via the identical, pure
    `generate_injection_id()` function)."""
    normalized = NORMALIZERS[attack_id](raw_result)
    normalized = _override_memory_id(normalized, scenario_id)
    injection_id = generate_injection_id(normalized.attack_id, normalized.artifact_id, TS)

    stored_text = stored_text_override if stored_text_override is not None else normalized.stored_text
    if stored_text is None:
        raise ValueError(f"No resolvable stored_text for real {attack_id} scenario {scenario_id!r}.")

    record = build_attack_canonical_memory_record(normalized, stored_text=stored_text, creation_timestamp=TS)
    record_memory_creation(
        memory_ledger=memory_ledger, event_ledger=event_ledger, membership_ledger=membership_ledger,
        run_id=run_id, record=record, actor="phase13-attribution-setup",
        reason=f"real {attack_id} attack injection, admitted", timestamp=TS,
        attack_context={
            "attack_id": normalized.attack_id, "injection_id": injection_id,
            "artifact_id": normalized.artifact_id, "admission_status": normalized.admission_status,
        },
        phase5_event_ledger=phase5_event_ledger,
    )
    return injection_id


def build_real_attack_injection_ledger(ledger_dir: Path) -> Dict[str, str]:
    """Re-runs every real Phase 4 injector this project's own
    `real_poison_scenarios()` uses (the SAME real seeds/artifacts), and
    persists a real `attack_injection` `Phase5Event` PLUS a real `created`
    `CanonicalEvent` for each of the 15 real poison scenarios, under the
    SAME "REAL-<FAMILY>-<i>" scenario ids the rest of Phase 12/13 uses.
    Returns a real `{scenario_id: injection_id}` ground-truth map, for
    `attribution.metrics.origin_attribution_accuracy()`.

    UPDATE (2026-09-22, explicitly authorized): this returned map is now ALSO
    persisted verbatim to `ledger_dir/real_injection_ground_truth.json` by
    `phase13/ledger_setup.py` immediately after this call returns -- BEFORE
    any ledger round-trip (serialization to the on-disk event/memory ledgers,
    then later re-reading them back). `attribution_metrics.py` compares
    `attribute_origin()`'s output (read back from the persisted ledger) against
    THIS captured-at-injection-time map as independent ground truth, rather
    than reconstructing ground truth FROM the same persisted ledger record
    `attribute_origin()` itself reads (which is circular -- it can only ever
    confirm the ledger agrees with itself, never catch a real serialization/
    field-mapping bug). See `attribution_metrics.py`'s own module docstring
    for the full disclosure of what this change does and does not newly test."""
    ledger_dir.mkdir(parents=True, exist_ok=True)
    memory_ledger = CanonicalMemoryLedger(ledger_dir / "memory")
    event_ledger = CanonicalEventLedger(ledger_dir / "events", memory_ledger)
    phase5_event_ledger = Phase5EventLedger(ledger_dir / "phase5_events")
    run_ledger = ExperimentRunLedger(ledger_dir / "runs")
    membership_ledger = EventRunMembershipLedger(ledger_dir / "membership", run_ledger)

    run = ExperimentRunRecord(
        experiment_id="phase13-attribution-setup", run_id="RUN-phase13-attack-injections",
        dataset="real_corpus", scope={}, started_at=TS, actor="phase13-attribution-setup",
        reason="real attack_injection ledger for Phase 13 attribution",
    )
    run_ledger.register(run)

    injection_ids: Dict[str, str] = {}

    def record(attack_id, raw_result, scenario_id, stored_text_override=None):
        injection_ids[scenario_id] = _record_one_injection(
            attack_id, raw_result, scenario_id, memory_ledger=memory_ledger, event_ledger=event_ledger,
            phase5_event_ledger=phase5_event_ledger, membership_ledger=membership_ledger,
            run_id=run.run_id, stored_text_override=stored_text_override,
        )

    # DSRM -- 3 real seeds.
    foundation = _new_mock_foundation()
    injector = DSRMInjector(foundation)
    for i, seed in enumerate(DSRM_SEEDS):
        artifact = AdversarialDecisionArtifact(
            artifact_id=seed.seed_id, task_id=seed.task_id,
            target_question=seed.target_question, gold_answer=seed.gold_answer,
            forged_claim=seed.forged_claim, planning_text=seed.initial_planning_text,
            initial_planning_text=seed.initial_planning_text,
            csrm_justification=CSRMJustification("N/A", "N/A", "N/A"),
            srm_iterations_used=0, srm_converged=False, srm_final_similarity=0.0,
            variant="black_box", retrieval_text=f"{seed.target_question} {seed.forged_claim}",
        )
        result = injector.inject(artifact)
        record("dsrm", result, f"REAL-DSRM-{i}")

    # FARMA -- 3 real seeds.
    foundation = _new_mock_foundation()
    injector = FARMAInjector(foundation)
    for i, seed in enumerate(SEED_TRACES):
        result = injector.inject(seed)
        record("farma", result, f"REAL-FARMA-{i}")

    # MPBench-PCFI -- 3 real scenarios.
    foundation = _new_mock_foundation()
    injector = MPBenchPCFIInjector(foundation)
    for i, scenario in enumerate(PCFI_SCENARIOS):
        result = injector.inject(scenario)
        record("mpbench", result, f"REAL-MPBENCH-{i}")

    # MINJA -- real 3-step sequence.
    foundation = _new_mock_foundation()
    injector = MINJAInjector(foundation)
    results = injector.inject(MINJA_CANDIDATE_1)
    for i, result in enumerate(results):
        record("minja", result, f"REAL-MINJA-{i}")

    # AgentPoison -- 1 real, GCG-optimized artifact.
    from phase11.data.real_corpus import _load_agentpoison_artifact

    foundation = _new_mock_foundation()
    injector = AgentPoisonInjector(foundation)
    artifact = AgentPoisonArtifact(**_load_agentpoison_artifact())
    result = injector.inject(artifact)
    record("agentpoison", result, "REAL-AGENTPOISON-0")

    # MemoryGraft -- 1 real seed (stored_text has no field on the result object itself).
    foundation = _new_mock_foundation()
    injector = MemoryGraftInjector(
        foundation_adapter=foundation, foundation_label="mem0",
        llm_provider=_scripted_llm_provider(["DECISION: KEEP\nRATIONALE: Looks like a valid shortcut."]),
        generation_config=_generation_config(),
    )
    result = injector.inject(SEED_RESEARCH_TOPIC)
    record("memorygraft", result, "REAL-MEMORYGRAFT-0", stored_text_override=SEED_RESEARCH_TOPIC.resp)

    # Sleeper -- 1 real seed.
    from phase3.evaluation.agent_runtime.messages import DEFAULT_SYSTEM_PROMPT
    from phase3.evaluation.agent_runtime.runner import RunConfiguration

    foundation = _new_mock_foundation()
    injector = SleeperInjector(foundation)
    run_config = RunConfiguration(
        llm_provider=_scripted_llm_provider(["DECISION: KEEP\nRATIONALE: Reasonable."]),
        generation_config=_generation_config(), system_prompt=DEFAULT_SYSTEM_PROMPT, max_retries=0,
    )
    result = injector.inject(SEED_DESTRESS, run_config)
    record("sleeper_memory_poisoning", result, "REAL-SLEEPER-0")

    return injection_ids
