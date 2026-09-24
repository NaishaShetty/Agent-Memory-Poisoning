"""Phase 14 -- the real, executed pilot campaign (2026-09-23, explicitly
authorized): Track A (benign real cost) and Track B (real protection),
each x the real defense configurations in `UTILITY_PILOT_CONFIGS` (B0/B1/B9
originally; B2/B4 added as a Phase 15 follow-on, explicitly authorized --
see that constant's own module-level comment for why B3/B5/B6/B7 are
deliberately not run separately), computing real Utility Retention Score
(URS), real false-positive task cost, and real protection outcomes. See
`docs/phase14/PHASE14_PLAN.md` Section 6 for the originally-confirmed scope
and `docs/phase15/PHASE15_PLAN.md` for the follow-on scope.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Tuple

from phase6.evaluation.metrics.utility_metrics import utility_retention_score
from phase14.defended_retrieval import (
    CONFIG_B0_NO_DEFENSE,
    CONFIG_B1_ADMISSION_ONLY,
    CONFIG_B2_RETRIEVAL_ONLY,
    CONFIG_B3_PROPAGATION_ONLY,
    CONFIG_B4_ADMISSION_RETRIEVAL,
    CONFIG_B5_RETRIEVAL_PROPAGATION,
    CONFIG_B6_ADMISSION_PROPAGATION,
    CONFIG_B7_ALL_THREE,
    CONFIG_B8_ALL_FOUR,
    CONFIG_B9_RISK_COMPOSED,
    CONFIG_B10_LEARNED_HYBRID,
)
from phase14.track_a_benign import build_track_a_cases, run_track_a_case
from phase14.track_a_longmemeval import build_track_a_longmemeval_cases, run_track_a_longmemeval_case
from phase14.track_b_consolidation_stage import run_all_consolidation_stage_cases
from phase14.track_b_poison import build_track_b_cases, run_track_b_case

# UPDATE (2026-09-23, Phase 14 follow-on, explicitly authorized): these were
# 40/40 (the FIRST pilot's real scale). The reported n=60/60 numbers in
# `docs/phase14/PHASE14_UTILITY_METRICS_REPORT.md` were produced by an
# earlier explicit `pilot_size=60` override at the call site, never reflected
# back into these module defaults -- a real, disclosed staleness this update
# also fixes. Now 150/150 (the real, further scale-up this pass adds; see
# the report's own Section on real dataset ceilings: LoCoMo has 1,388 real
# QA pairs and LongMemEval has 479 real usable items, uncapped, so 150 each
# is real, available data, not a ceiling).
PILOT_SIZE_TRACK_A = 150
PILOT_SIZE_TRACK_A_LONGMEMEVAL = 150
# `flat_counterfactual_pool()`'s own default per-task cap (15) only allows
# 135 real LoCoMo QA pairs total across the real 9-task range -- below the
# new 150 pilot size. This raises it just enough (17/task x 9 tasks = 153)
# to unlock enough of the already-real, uncapped 1,388-pair pool.
TRACK_A_LOCOMO_PER_TASK_CAP = 17

# Real, disclosed dataset scope (2026-09-23, explicitly authorized follow-on):
# only LoCoMo and LongMemEval have a real, native question/answer task layer.
# This project's own frozen Phase 3.2-G dataset audit already found, and
# directly verified, that MSC and Conversation Chronicles ship a real,
# confirmed 0-byte `task_records.jsonl` -- no real task/QA layer exists for
# either, and their own registered role explicitly excludes them from the
# task-QA framework "unless and until a legitimate task/workload layer
# exists." Building a real Track A measurement for them would require
# inventing gold answers this project's real data does not provide -- this
# project does not do that anywhere else, and does not start here.
DATASETS_WITH_NO_REAL_TASK_LAYER: Tuple[str, ...] = ("msc", "conversation_chronicles")

# 2026-09-23 (Phase 15 follow-on, explicitly authorized): which real configs
# this campaign's Track A/B live pilot actually RUNS -- deliberately NOT the
# same as `defended_retrieval.REAL_CONFIGS` (the full set `apply_defense()`
# supports). B3/B5/B6/B7 are excluded here on a real, direct, confirmed
# basis, not an assumption: none of Phase 14's live task memories (LoCoMo/
# LongMemEval QA pairs, poison scenarios) ever carry real `ancestors`, so
# `evaluate_propagation_containment()` never fires for them
# (`defended_retrieval.py::_pipeline_actions()`'s own docstring;
# `pipeline.py`'s `evaluate_pool()` only calls it when `m.ancestors` is
# truthy). This means, PROVEN directly by
# `test_defended_retrieval_b0_to_b7.py` (byte-identical `combined_action`
# outputs on real Phase 14 pool data, not merely argued from reading the
# source): B3 always degenerates to B0, B5 to B2, B6 to B1, and B7 to B4 in
# THIS live setting. Running a separate real, expensive LLM campaign for
# each of these four would burn real compute for a result already knowable
# from the config it degenerates to -- so this campaign runs only the
# genuinely distinct real configs, and `docs/phase15/
# PHASE15_CROSS_CUTTING_REPORT.md` reports the other four by proven
# equivalence instead.
UTILITY_PILOT_CONFIGS: Tuple[str, ...] = (
    CONFIG_B0_NO_DEFENSE, CONFIG_B1_ADMISSION_ONLY, CONFIG_B2_RETRIEVAL_ONLY, CONFIG_B4_ADMISSION_RETRIEVAL,
    CONFIG_B8_ALL_FOUR, CONFIG_B9_RISK_COMPOSED, CONFIG_B10_LEARNED_HYBRID,
)
# B10 (2026-09-23): live per-task learned-hybrid decision (`phase15/b10_live.py`).
# B8 is NOT degenerate the way B3/B5/B6/B7 are: it adds real Sleeper
# detection (`evaluate_sleeper_admission()`) and real sibling-propagation
# (`semantic_sibling_propagation_actions()`) on top of B7's own
# (degenerate-to-B4) admission+retrieval stack -- neither of those two
# components existed in any already-tested config, so B8 gets its own real
# live campaign rather than being reported by equivalence.
# The real, proven degeneracy map (config -> the config it is byte-identical
# to in Phase 14's live path) -- used by the report, never by any decision
# logic itself.
UTILITY_DEGENERATE_CONFIGS: Dict[str, str] = {
    CONFIG_B3_PROPAGATION_ONLY: CONFIG_B0_NO_DEFENSE,
    CONFIG_B5_RETRIEVAL_PROPAGATION: CONFIG_B2_RETRIEVAL_ONLY,
    CONFIG_B6_ADMISSION_PROPAGATION: CONFIG_B1_ADMISSION_ONLY,
    CONFIG_B7_ALL_THREE: CONFIG_B4_ADMISSION_RETRIEVAL,
}


@dataclass(frozen=True)
class TrackASummary:
    config: str
    n_tasks: int
    n_success: int
    task_success_rate: float
    n_false_positive_exclusions: int  # target (benign) memory excluded by the defense
    n_false_positive_task_failures: int  # of those, how many also failed the task
    n_reused_baseline: int  # real cases where the defended context was identical to B0 -- B0's own real result was reused, not re-generated (see run_track_a_case()'s own docstring for why)


@dataclass(frozen=True)
class TrackBSummary:
    config: str
    n_tasks: int
    n_matches_gold: int
    n_matches_forged: int
    n_poison_excluded: int
    gold_rate: float
    forged_rate: float
    exclusion_rate: float


def _run_track_a_generic(cases, run_case_fn) -> Dict[str, TrackASummary]:
    """Real fix (2026-09-23, explicitly authorized): B0 is always run first,
    per real case; B1/B9 REUSE that same real B0 result whenever their real
    defended context is byte-identical to it (see `run_track_a_case()`'s own
    docstring for the real, direct evidence this was necessary -- re-running
    an unchanged context measured this local model's own sampling noise, not
    any real defense cost). A config's task success rate now reflects ONLY
    real cases where the defense genuinely changed something, or a fresh real
    generation over a genuinely different real context -- never noise from
    redundantly re-asking an identical question. Generalized (2026-09-23,
    same-day follow-on) to accept any real Track-A-shaped case/runner pair,
    so LoCoMo and LongMemEval share one real implementation."""
    if not cases:
        raise ValueError("cases is empty -- Track A summary is undefined over zero real tasks.")
    baseline_results = {case.task_id: run_case_fn(case, CONFIG_B0_NO_DEFENSE) for case in cases}

    summaries: Dict[str, TrackASummary] = {}
    for config in UTILITY_PILOT_CONFIGS:
        n_success = 0
        n_fp_exclusions = 0
        n_fp_task_failures = 0
        n_reused = 0
        for case in cases:
            baseline_result = baseline_results[case.task_id]
            if config == CONFIG_B0_NO_DEFENSE:
                result = baseline_result
            else:
                result = run_case_fn(case, config, reuse_if_context_unchanged=baseline_result)
                if result.get("reused_baseline"):
                    n_reused += 1
            if result["success"]:
                n_success += 1
            if result["target_excluded"]:
                n_fp_exclusions += 1
                if not result["success"]:
                    n_fp_task_failures += 1
        summaries[config] = TrackASummary(
            config=config, n_tasks=len(cases), n_success=n_success,
            task_success_rate=n_success / len(cases),
            n_false_positive_exclusions=n_fp_exclusions,
            n_false_positive_task_failures=n_fp_task_failures,
            n_reused_baseline=n_reused,
        )
    return summaries


def run_track_a(pilot_size: int = PILOT_SIZE_TRACK_A) -> Dict[str, TrackASummary]:
    """Real LoCoMo Track A."""
    per_task_cap = TRACK_A_LOCOMO_PER_TASK_CAP if pilot_size > 135 else None
    cases = build_track_a_cases(pilot_size, per_task_cap=per_task_cap)
    return _run_track_a_generic(cases, run_track_a_case)


def run_track_a_longmemeval(pilot_size: int = PILOT_SIZE_TRACK_A_LONGMEMEVAL) -> Dict[str, TrackASummary]:
    """Real LongMemEval Track A (2026-09-23, explicitly authorized follow-on)
    -- the one other real dataset among this project's original four with a
    real, native task/QA layer. See `phase14/track_a_longmemeval.py`'s own
    module docstring for why MSC and Conversation Chronicles are NOT
    included."""
    cases = build_track_a_longmemeval_cases(pilot_size)
    return _run_track_a_generic(cases, run_track_a_longmemeval_case)


def combine_track_a_summaries(*summaries_by_dataset: Dict[str, TrackASummary]) -> Dict[str, TrackASummary]:
    """Real, pooled Track A summary across every real dataset tested --
    combines real n_tasks/n_success counts directly (never averages rates,
    which would misweight a smaller real dataset equally against a larger
    one)."""
    combined: Dict[str, TrackASummary] = {}
    for config in UTILITY_PILOT_CONFIGS:
        n_tasks = sum(s[config].n_tasks for s in summaries_by_dataset)
        n_success = sum(s[config].n_success for s in summaries_by_dataset)
        n_fp_exclusions = sum(s[config].n_false_positive_exclusions for s in summaries_by_dataset)
        n_fp_task_failures = sum(s[config].n_false_positive_task_failures for s in summaries_by_dataset)
        n_reused = sum(s[config].n_reused_baseline for s in summaries_by_dataset)
        combined[config] = TrackASummary(
            config=config, n_tasks=n_tasks, n_success=n_success,
            task_success_rate=n_success / n_tasks if n_tasks else 0.0,
            n_false_positive_exclusions=n_fp_exclusions,
            n_false_positive_task_failures=n_fp_task_failures,
            n_reused_baseline=n_reused,
        )
    return combined


def run_track_b() -> Dict[str, TrackBSummary]:
    cases = build_track_b_cases()
    summaries: Dict[str, TrackBSummary] = {}
    for config in UTILITY_PILOT_CONFIGS:
        n_gold = 0
        n_forged = 0
        n_excluded = 0
        for case in cases:
            result = run_track_b_case(case, config)
            if result["matches_gold"]:
                n_gold += 1
            if result["matches_forged"]:
                n_forged += 1
            if result["poison_excluded"]:
                n_excluded += 1
        summaries[config] = TrackBSummary(
            config=config, n_tasks=len(cases), n_matches_gold=n_gold, n_matches_forged=n_forged,
            n_poison_excluded=n_excluded, gold_rate=n_gold / len(cases), forged_rate=n_forged / len(cases),
            exclusion_rate=n_excluded / len(cases),
        )
    return summaries


@dataclass(frozen=True)
class ConsolidationStageSummary:
    n_tasks: int
    n_protected: int
    protection_rate: float


def run_track_b_consolidation_stage() -> ConsolidationStageSummary:
    """Real Stage-2 check (2026-09-23, explicitly authorized): does the
    ALREADY-BUILT Consolidation Guard (Phase 12's fifth defense component,
    unmodified here) protect Track B's real cases once their real content
    reaches a real consolidation step -- tested separately from B1/B9
    because it is a structurally distinct real pipeline stage, not another
    admission/retrieval configuration. See `phase14/track_b_consolidation_
    stage.py`'s own module docstring for why this was worth testing."""
    results = run_all_consolidation_stage_cases()
    n_protected = sum(1 for r in results if r.protected)
    return ConsolidationStageSummary(
        n_tasks=len(results), n_protected=n_protected, protection_rate=n_protected / len(results),
    )


def compute_urs(track_a: Dict[str, TrackASummary]) -> Dict[str, float]:
    baseline = track_a[CONFIG_B0_NO_DEFENSE].task_success_rate
    return {
        config: utility_retention_score(track_a[config].task_success_rate, baseline).urs
        for config in UTILITY_PILOT_CONFIGS if config != CONFIG_B0_NO_DEFENSE
    }


def run_full_pilot(
    pilot_size: int = PILOT_SIZE_TRACK_A, pilot_size_longmemeval: int = PILOT_SIZE_TRACK_A_LONGMEMEVAL,
    out_path: Path = None,
) -> Dict[str, object]:
    track_a_locomo = run_track_a(pilot_size)
    track_a_longmemeval = run_track_a_longmemeval(pilot_size_longmemeval)
    track_a_combined = combine_track_a_summaries(track_a_locomo, track_a_longmemeval)
    track_b = run_track_b()
    track_b_consolidation = run_track_b_consolidation_stage()
    urs_locomo = compute_urs(track_a_locomo)
    urs_longmemeval = compute_urs(track_a_longmemeval)
    urs_combined = compute_urs(track_a_combined)

    result = {
        "track_a_locomo": {k: asdict(v) for k, v in track_a_locomo.items()},
        "track_a_longmemeval": {k: asdict(v) for k, v in track_a_longmemeval.items()},
        "track_a_combined": {k: asdict(v) for k, v in track_a_combined.items()},
        "track_a_datasets_with_no_real_task_layer": list(DATASETS_WITH_NO_REAL_TASK_LAYER),
        "track_b": {k: asdict(v) for k, v in track_b.items()},
        "track_b_consolidation_stage": asdict(track_b_consolidation),
        "urs_locomo": urs_locomo,
        "urs_longmemeval": urs_longmemeval,
        "urs_combined": urs_combined,
    }
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    result = run_full_pilot(out_path=Path("phase14/data/pilot_results.json"))
    print(json.dumps(result, indent=2))


__all__ = [
    "TrackASummary", "TrackBSummary", "run_track_a", "run_track_a_longmemeval", "combine_track_a_summaries",
    "run_track_b", "compute_urs", "run_full_pilot",
]
