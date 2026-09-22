"""Phase 13 -- real attribution metrics, computed for the first time at
scale against the real 15-scenario `real_poison_scenarios()` corpus and its
real, persisted ledger (`phase13/ledger_setup.py`).

Reuses `attribution/metrics.py`'s own real, already-built metric functions
(`origin_attribution_accuracy`, `lineage_reconstruction_accuracy`,
`ambiguity_rate`, `false_attribution_rate`) verbatim -- confirmed via direct
grep before this module was written that they had only ever been exercised
by their own unit tests, never run against real corpus data. No new
attribution logic is introduced here.

STANDING RULE (added this session, per the real lesson learned building
Phase 12's PR measurement): any result showing an unconditionally
suspicious pattern -- 0%, 100%, identical everywhere -- is investigated to
a concrete root cause before being reported, never accepted at face value.

UPDATE (2026-09-22, explicitly authorized): `origin_false_attribution_rate`
was previously computed against ground truth RECONSTRUCTED from the same
persisted ledger record `attribute_origin()` itself reads
(`_reconstruct_injection_ground_truth()`, still present below, kept as
`origin_false_attribution_rate_circular` for comparison) -- a real, disclosed
gap: this can only ever confirm the ledger agrees with itself, and could
never surface a real bug (e.g. a serialization/field-mapping error) between
what an injector actually produced and what the ledger persisted. Fixed via
`phase13/ledger_setup.py`, which now captures `build_real_attack_injection_
ledger()`'s own returned `{scenario_id: injection_id}` map -- computed at
injection time, BEFORE any ledger round-trip -- and persists it verbatim to
`real_injection_ground_truth.json`. `origin_false_attribution_rate` below now
compares `attribute_origin()`'s output (read back AFTER a full persist/
re-load round-trip) against THAT independently-captured map. This does not
make ambiguity reachable (the `DuplicateMemoryClaimError` invariant is a
real, intentional data-integrity guarantee this project will not bypass just
to manufacture a test case -- see docs/phase13/PHASE13_ATTRIBUTION_METRICS_
REPORT.md Section 3 for the full disclosure of why that specific gap stays
open) -- but it does convert false-attribution-rate from tautological to a
real regression check: a bug in the injection/ledger-write/ledger-read path
would now show up here as a nonzero rate, where it could not have before.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from attribution.metrics import (
    ambiguity_rate,
    false_attribution_rate,
    lineage_reconstruction_accuracy,
    origin_attribution_accuracy,
)
from attribution.schema import AttributionResult
from attribution.wiring.lineage import attribute_lineage
from attribution.wiring.origin import attribute_origin
from phase11.data.real_corpus import real_poison_scenarios
from phase13.ledger_setup import DEFAULT_LEDGER_DIR
from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger
from phase5.schema.event_ledger import Phase5EventLedger

RUN_ID = "phase13-attribution-metrics"


@dataclass(frozen=True)
class AttributionMetricsResult:
    n_poison_scenarios: int
    origin_family_match_accuracy: float  # simple, interpretable: does attack_id match the real family
    origin_injection_id_accuracy: float  # attribution/metrics.py's own strict metric
    origin_ambiguity_rate: float
    origin_false_attribution_rate: Optional[float]  # against the real, independent (pre-round-trip) ground truth
    origin_false_attribution_rate_circular: Optional[float]  # against ledger-reconstructed ground truth -- kept for comparison, see module docstring
    n_derivation_events: int
    path_fidelity_accuracy: Optional[float]
    lineage_ambiguity_rate: Optional[float]
    mean_time_to_attribute_origin_ms: float
    mean_time_to_attribute_lineage_ms: Optional[float]
    per_scenario_origin: Dict[str, str]  # scenario_id -> attack_id attributed


def _reconstruct_injection_ground_truth(memory_ledger: CanonicalMemoryLedger) -> Dict[str, str]:
    """Real ground truth, reconstructed from the real, already-persisted
    ledger's own `source.artifact_id`/`source.attack_id` fields (written by
    `phase13/attack_injection_ledger.py` at build time) via the SAME pure,
    deterministic `generate_injection_id()` function -- not a second,
    independent guess."""
    from phase5.wiring.attack_integration import generate_injection_id

    ground_truth = {}
    for m in real_poison_scenarios().memories:
        record = memory_ledger.get(m.scenario_id)
        if record is None:
            continue
        attack_id = record.source.get("attack_id")
        artifact_id = record.source.get("artifact_id")
        if attack_id is None or artifact_id is None:
            continue
        ground_truth[m.scenario_id] = generate_injection_id(attack_id, artifact_id, record.creation_timestamp)
    return ground_truth


def _load_independent_injection_ground_truth(ledger_dir: Path) -> Optional[Dict[str, str]]:
    """Real ground truth captured at injection time, BEFORE any ledger
    round-trip -- see module docstring's 2026-09-22 update. Returns `None`
    (not `{}`) if `ledger_setup.py` has not yet been re-run against this
    `ledger_dir` since the fix was added (an older ledger directory would
    simply lack the file) -- callers must not silently treat that as "zero
    real ground truth."""
    from phase13.ledger_setup import INDEPENDENT_GROUND_TRUTH_FILENAME

    path = ledger_dir / INDEPENDENT_GROUND_TRUTH_FILENAME
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def compute_attribution_metrics(ledger_dir: Path = DEFAULT_LEDGER_DIR) -> AttributionMetricsResult:
    memory_ledger = CanonicalMemoryLedger(ledger_dir / "memory")
    event_ledger = CanonicalEventLedger(ledger_dir / "events", memory_ledger)
    phase5_event_ledger = Phase5EventLedger(ledger_dir / "phase5_events")

    pool = real_poison_scenarios()

    # --- Source accuracy (ORIGIN) ---
    origin_results: Dict[str, AttributionResult] = {}
    origin_timings_ms: List[float] = []
    for m in pool.memories:
        start = time.perf_counter()
        result = attribute_origin(m.scenario_id, run_id=RUN_ID, phase5_event_ledger=phase5_event_ledger)
        origin_timings_ms.append((time.perf_counter() - start) * 1000)
        origin_results[m.scenario_id] = result

    family_matches = sum(
        1 for m in pool.memories if origin_results[m.scenario_id].attack_id == m.attack_family_ground_truth
    )
    origin_family_match_accuracy = family_matches / len(pool.memories)

    injection_ground_truth = _reconstruct_injection_ground_truth(memory_ledger)
    origin_injection_id_accuracy = origin_attribution_accuracy(
        {sid: r for sid, r in origin_results.items() if sid in injection_ground_truth}, injection_ground_truth,
    )

    origin_amb_rate = ambiguity_rate(list(origin_results.values()))
    try:
        origin_fa_rate_circular = false_attribution_rate(origin_results, injection_ground_truth)
    except ValueError:
        origin_fa_rate_circular = None  # no UNIQUE-status results to score -- disclosed, not silently 0.0

    independent_ground_truth = _load_independent_injection_ground_truth(ledger_dir)
    if independent_ground_truth is not None:
        try:
            origin_fa_rate = false_attribution_rate(
                {sid: r for sid, r in origin_results.items() if sid in independent_ground_truth},
                independent_ground_truth,
            )
        except ValueError:
            origin_fa_rate = None
    else:
        # No independent ground-truth file for this ledger_dir (built before the
        # 2026-09-22 fix) -- fall back to the circular check rather than silently
        # reporting a stronger guarantee than this ledger actually supports.
        origin_fa_rate = origin_fa_rate_circular

    # --- Path fidelity (LINEAGE, full chain) ---
    derived_events = [e for e in event_ledger.all_events() if e.event_type == "derived"]
    lineage_results: Dict[str, AttributionResult] = {}
    lineage_ground_truth: Dict[str, Tuple[str, ...]] = {}
    lineage_timings_ms: List[float] = []
    for event in derived_events:
        derived_memory_id = event.target_memory_id
        start = time.perf_counter()
        result = attribute_lineage(derived_memory_id, run_id=RUN_ID, event_ledger=event_ledger, full_chain=True)
        lineage_timings_ms.append((time.perf_counter() - start) * 1000)
        lineage_results[derived_memory_id] = result
        lineage_ground_truth[derived_memory_id] = tuple(event.source_memory_ids)

    if lineage_results:
        path_fidelity_accuracy = lineage_reconstruction_accuracy(lineage_results, lineage_ground_truth)
        lineage_amb_rate = ambiguity_rate(list(lineage_results.values()))
        mean_lineage_ms = sum(lineage_timings_ms) / len(lineage_timings_ms)
    else:
        path_fidelity_accuracy = None
        lineage_amb_rate = None
        mean_lineage_ms = None

    return AttributionMetricsResult(
        n_poison_scenarios=len(pool.memories),
        origin_family_match_accuracy=origin_family_match_accuracy,
        origin_injection_id_accuracy=origin_injection_id_accuracy,
        origin_ambiguity_rate=origin_amb_rate,
        origin_false_attribution_rate=origin_fa_rate,
        origin_false_attribution_rate_circular=origin_fa_rate_circular,
        n_derivation_events=len(derived_events),
        path_fidelity_accuracy=path_fidelity_accuracy,
        lineage_ambiguity_rate=lineage_amb_rate,
        mean_time_to_attribute_origin_ms=sum(origin_timings_ms) / len(origin_timings_ms),
        mean_time_to_attribute_lineage_ms=mean_lineage_ms,
        per_scenario_origin={sid: r.attack_id for sid, r in origin_results.items()},
    )


if __name__ == "__main__":
    import json
    from dataclasses import asdict

    result = compute_attribution_metrics()
    print(json.dumps(asdict(result), indent=2))
