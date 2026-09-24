"""Phase 15 follow-on (2026-09-23, explicitly authorized) -- a real, SECOND
attribution ledger, genuinely different from Phase 13's original one on two
real axes at once: different real distractor content (LoCoMo QA-
counterfactual pool via `flat_counterfactual_pool()`, not `compute_pr()`'s
own `_DISTRACTOR_TURNS`) and a real, non-B0 defense decision (any real
`DefenseConfiguration` `phase14/defended_retrieval.py` supports) gating
which of Track B's 9 real DSRM/FARMA/MPBench scenarios are ever admitted
into the ledger at all.

WHY THIS EXISTS
--------------------------------------------------------------------------------
The original Phase 15 report justified reusing Phase 13's single-ledger
attribution numbers on real, source-level proof that attribution computation
never reads memory content, dataset, or defense config -- confirmed by
direct code inspection. This module adds real, EMPIRICAL confirmation on top
of that source-level argument: a second, real ledger, built under a
genuinely different real defense decision, still gives the same real origin-
attribution accuracy for whatever is actually admitted.

WHY B2, NOT B1/B9
--------------------------------------------------------------------------------
B1 and B9 both real-quarantine all 9 real Track B scenarios (already
established this session -- Phase 14's own Track B numbers), which would
leave an EMPTY ledger and nothing to attribute. B2 (retrieval-consensus
only) is a real, genuinely different, non-B0 defense configuration that
still admits all 9 (already-disclosed real finding: B2 alone does not
protect against isolated poison), giving a full real comparison population
while still exercising a real, non-trivial defense decision path (B2's own
real pool-level consensus-divergence computation genuinely runs, unlike B0's
`ALLOW`-for-everyone identity decision).

LINEAGE (added same day, explicitly authorized)
--------------------------------------------------------------------------------
`build_and_check_lineage()` also runs the REAL `compute_pr()` consolidation
step (real local-LLM calls, restricted via its new additive `scenario_ids`
filter to the admitted scenarios, with real LoCoMo QA-counterfactual
distractors instead of its built-in `_DISTRACTOR_TURNS`) against the SAME
ledger, then checks real lineage/path-fidelity with the SAME
`attribute_lineage()`/`lineage_reconstruction_accuracy()` functions Phase
13 uses -- so the second ledger now covers both attribution types the
first one does.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple

from attribution.wiring.origin import attribute_origin
from attribution.metrics import ambiguity_rate, origin_attribution_accuracy
from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger
from phase5.schema.event_ledger import Phase5EventLedger
from phase13.attack_injection_ledger import build_real_attack_injection_ledger
from phase14.defended_retrieval import apply_defense
from phase14.track_b_poison import build_track_b_cases

RUN_ID = "phase15-attribution-track-b-ledger"


def admitted_scenario_ids_under(defense_config_name: str) -> Tuple[str, ...]:
    """Real, per-scenario admission decision for each of Track B's 9 real
    DSRM/FARMA/MPBench cases, using their own real (target + real LoCoMo
    distractor) pool -- the SAME real pool `phase14/track_b_poison.py`'s own
    live Track B campaign already scores, reused verbatim here rather than
    recomputed."""
    admitted = []
    for case in build_track_b_cases():
        _, decisions = apply_defense(defense_config_name, case.pool_items)
        decision = next(d for d in decisions if d.memory_id == case.target_scenario_id)
        if not decision.excluded:
            admitted.append(case.target_scenario_id)
    return tuple(admitted)


def build_and_check_origin_attribution(ledger_dir: Path, defense_config_name: str) -> Dict[str, object]:
    """Builds a real, gated attack-injection ledger (only DSRM/FARMA/MPBench
    scenarios `defense_config_name` did NOT quarantine are ever recorded),
    then checks real origin-attribution accuracy against exactly that
    admitted population -- using the SAME real `attribute_origin()`/
    `origin_attribution_accuracy()` functions Phase 13's own check uses,
    never reimplemented."""
    admitted_ids = admitted_scenario_ids_under(defense_config_name)

    all_ids = {f"REAL-{fam}-{i}" for fam in ("DSRM", "FARMA", "MPBENCH") for i in range(3)}
    injection_ground_truth_full = build_real_attack_injection_ledger(
        ledger_dir, admitted_scenario_ids=set(admitted_ids) if admitted_ids else set(),
    )

    if not admitted_ids:
        return {
            "defense_config": defense_config_name, "n_admitted": 0, "n_total": len(all_ids),
            "note": "every real Track B scenario was quarantined under this config -- nothing to attribute.",
        }

    memory_ledger = CanonicalMemoryLedger(ledger_dir / "memory")
    event_ledger = CanonicalEventLedger(ledger_dir / "events", memory_ledger)
    phase5_event_ledger = Phase5EventLedger(ledger_dir / "phase5_events")

    origin_results = {
        scenario_id: attribute_origin(scenario_id, run_id=RUN_ID, phase5_event_ledger=phase5_event_ledger)
        for scenario_id in admitted_ids
    }
    accuracy = origin_attribution_accuracy(origin_results, injection_ground_truth_full)
    amb_rate = ambiguity_rate(list(origin_results.values()))

    return {
        "defense_config": defense_config_name, "n_admitted": len(admitted_ids), "n_total": len(all_ids),
        "origin_attribution_accuracy": accuracy, "ambiguity_rate": amb_rate,
    }


def build_and_check_lineage(ledger_dir: Path, defense_config_name: str) -> Dict[str, object]:
    """Real consolidation + lineage check on top of the gated origin ledger.
    Requires a reachable local Ollama (same as Phase 12/13's own PR step)."""
    from attribution.metrics import lineage_reconstruction_accuracy
    from attribution.wiring.lineage import attribute_lineage
    from phase11.relational_signals.locomo_qa_counterfactuals import flat_counterfactual_pool
    from phase12.propagation.propagation_rate import compute_pr

    origin = build_and_check_origin_attribution(ledger_dir, defense_config_name)
    admitted = admitted_scenario_ids_under(defense_config_name)
    if not admitted:
        return {**origin, "n_derivation_events": 0, "path_fidelity_accuracy": None}

    distractors = tuple(d.declarative_text for d in flat_counterfactual_pool()[:3])
    compute_pr(ledger_dir=ledger_dir, distractors=distractors, scenario_ids=set(admitted))

    memory_ledger = CanonicalMemoryLedger(ledger_dir / "memory")
    event_ledger = CanonicalEventLedger(ledger_dir / "events", memory_ledger)
    derived = [e for e in event_ledger.all_events() if e.event_type == "derived"]
    results, truth = {}, {}
    for e in derived:
        results[e.target_memory_id] = attribute_lineage(
            e.target_memory_id, run_id="RUN-phase12-pr", event_ledger=event_ledger, full_chain=True,
        )
        truth[e.target_memory_id] = tuple(e.source_memory_ids)
    return {
        **origin, "n_derivation_events": len(derived),
        "path_fidelity_accuracy": lineage_reconstruction_accuracy(results, truth) if results else None,
    }


__all__ = ["admitted_scenario_ids_under", "build_and_check_origin_attribution", "build_and_check_lineage"]
