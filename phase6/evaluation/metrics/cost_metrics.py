"""Phase 6.12 -- Cost Metrics: latency and overhead accounting per defense
component, using REAL measurements where they exist, and explicit `None`
(never a fabricated placeholder) where they don't.

REAL, ALREADY-MEASURED NUMBERS THIS MODULE CITES RATHER THAN RE-DERIVES
--------------------------------------------------------------------------------
Stage 6.6's own work measured D2's real embedding cost on this environment's
hardware (`RETRIEVAL_DEFENSE.md`): model load ~11s one-time (amortized across
a process, via `embedding_signals._get_model()`'s module-level cache),
per-pool `encode()` cost ~0.31s cold / ~0.017s warm for a 4-sentence pool.
This module's `ComponentCostProfile` for D2 cites those numbers directly
rather than re-measuring them, to avoid two divergent "real" measurements of
the same thing existing in the project.

EVERY OTHER PHASE 6 COMPONENT'S TOKEN/MODEL-CALL COST IS GENUINELY ZERO,
NOT UNMEASURED
--------------------------------------------------------------------------------
Stage 6.5's Reasoning Guard, Stage 6.6's D1 (lexical), Stage 6.7's
propagation containment, and Stage 6.8's Sleeper Guard are ALL pure
regex/string/dict operations -- no LLM call, no embedding call, confirmed by
direct inspection of their imports (none imports `sentence_transformers`,
`torch`, or any LLM client). Their `token_overhead`/`model_call_overhead`
fields below are `0`, a real, positive, disclosed fact about this design
(consistent with the "establish interpretable baselines before a black-box
detector" instruction), not an unmeasured gap.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ComponentCostProfile:
    component_name: str
    model_call_overhead: int  # number of external model calls per invocation
    token_overhead: int  # 0 for every non-LLM component; N/A (None) for unimplemented D3
    measured_latency_seconds: Optional[float]  # None = not measured / not applicable
    latency_measurement_note: str


ADMISSION_REASONING_GUARD = ComponentCostProfile(
    component_name="admission.reasoning_guard (Stage 6.5)",
    model_call_overhead=0,
    token_overhead=0,
    measured_latency_seconds=None,
    latency_measurement_note="Pure regex/string operations -- not separately timed; expected sub-millisecond, consistent with SENTINEL's own reported <1ms/write for the analogous mechanism (DEFENSE_LITERATURE_AUDIT.md Track B.4).",
)

RETRIEVAL_LEXICAL_D1 = ComponentCostProfile(
    component_name="retrieval.signals (D1, lexical, Stage 6.6)",
    model_call_overhead=0,
    token_overhead=0,
    measured_latency_seconds=None,
    latency_measurement_note="Pure token-set/Jaccard operations -- not separately timed; expected sub-millisecond for realistic pool sizes (n<=20).",
)

RETRIEVAL_SEMANTIC_D2 = ComponentCostProfile(
    component_name="retrieval.embedding_signals (D2, semantic, Stage 6.6)",
    model_call_overhead=1,  # one encode() call per pool
    token_overhead=0,  # embeddings, not a token-generating LLM call
    measured_latency_seconds=0.017,
    latency_measurement_note=(
        "REAL measurement (RETRIEVAL_DEFENSE.md): model load ~11s one-time "
        "(amortized via module-level cache), per-pool encode() ~0.31s cold / "
        "~0.017s warm for a 4-sentence pool on this environment's CPU. The "
        "warm figure is cited here as the steady-state cost; the one-time "
        "load cost must be added for a cold-start accounting."
    ),
)

PROPAGATION_CONTAINMENT = ComponentCostProfile(
    component_name="propagation.containment_guard (Stage 6.7)",
    model_call_overhead=0,
    token_overhead=0,
    measured_latency_seconds=None,
    latency_measurement_note="Pure token-set/severity-arithmetic operations -- not separately timed; expected sub-millisecond per ancestor.",
)

SLEEPER_GUARD = ComponentCostProfile(
    component_name="sleeper.sleeper_guard (Stage 6.8)",
    model_call_overhead=0,
    token_overhead=0,
    measured_latency_seconds=None,
    latency_measurement_note="Pure regex operations -- not separately timed; expected sub-millisecond.",
)

LLM_JUDGE_D3 = ComponentCostProfile(
    component_name="retrieval consensus, D3 (LLM-judge) -- UNIMPLEMENTED",
    model_call_overhead=0,
    token_overhead=0,
    measured_latency_seconds=None,
    latency_measurement_note=(
        "D3 is not implemented (RETRIEVAL_DEFENSE.md: no frozen, reproducible "
        "LLM server available in this environment). Fields here are "
        "placeholders for a component that does not exist yet, not a "
        "measurement of 0 cost -- do not read `model_call_overhead=0` here as "
        "'D3 is free'; it means 'D3 was never run.'"
    ),
)

CONSOLIDATION_GUARD = ComponentCostProfile(
    component_name="consolidation.consolidation_guard (Phase 12's fifth defense component)",
    model_call_overhead=0,
    token_overhead=0,
    # Real measurement (2026-09-23, Phase 14, explicitly authorized): this
    # component did not exist when this module was last touched, so it had
    # no profile at all -- not even a disclosed `None`. `phase14.
    # latency_measurement.measure_consolidation_guard_latency()` measured it
    # directly on this same real local machine, 20 real trials: mean 19.0ms,
    # min 6.6ms, max 161.6ms (stdev 32.8ms -- the real spread traced to the
    # semantic-embedding model's own lazy-loaded, amortized-per-process cost,
    # the SAME real cause RETRIEVAL_SEMANTIC_D2's own docstring already
    # discloses for the identical reason).
    measured_latency_seconds=0.019,
    latency_measurement_note=(
        "Real, measured 2026-09-23 (Phase 14): calls evaluate_admission() + "
        "evaluate_sleeper_admission() + semantic_sibling_propagation_actions() "
        "per real source, plus clause-level embedding similarity -- mean "
        "19.0ms over 20 real trials on this project's own local machine; see "
        "phase14/latency_measurement.py and docs/phase14/"
        "PHASE14_UTILITY_METRICS_REPORT.md for the full real measurement."
    ),
)

ALL_COMPONENT_PROFILES = (
    ADMISSION_REASONING_GUARD,
    RETRIEVAL_LEXICAL_D1,
    RETRIEVAL_SEMANTIC_D2,
    PROPAGATION_CONTAINMENT,
    SLEEPER_GUARD,
    LLM_JUDGE_D3,
    CONSOLIDATION_GUARD,
)


def total_query_latency_seconds(*component_latencies: Optional[float]) -> Optional[float]:
    """Sums the latencies of whichever components a given configuration
    enables. Returns `None` (never 0) if ANY supplied component has no real
    measurement -- an incomplete cost accounting must not silently present
    itself as a complete, low number."""
    if any(latency is None for latency in component_latencies):
        return None
    return sum(component_latencies)
