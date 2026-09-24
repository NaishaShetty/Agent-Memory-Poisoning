"""Phase 14 follow-on (2026-09-23, explicitly authorized) -- the real, second
calibration pass for `risk_score.py`'s `ADMISSION_MULTI_SIGNAL_CORROBORATION_FLOOR`
(used only by the separate `GROUPED_GATED_ADMISSION_CORROBORATED` rule).

WHY THIS EXISTS
--------------------------------------------------------------------------------
The floor (2.5) was originally justified by a single arithmetic argument
(`GROUP_WEIGHT=0.25` means a group score >= 2.4 is needed to reach the `HIGH`
band, so 2.5 gives margin) plus a pass/fail check against `dev_corpus.py`'s
9-item `dev_admission_pool()`. Direct investigation found that pool alone
cannot discriminate a SAFE floor from an UNSAFE one: none of its 3 real
benign records ever accumulate 2+ admission signals, so every floor from 2.4
upward looks identically "safe" on that pool by construction, not because a
real sweep confirmed a genuine boundary. This module is the real, larger-scale
second pass this gap named: it sweeps real candidate floor values (via
`compute_memory_risk_score()`'s own public `admission_corroboration_floor`
parameter, added for exactly this purpose -- see that function's docstring)
against the full, real 502-record benign corpus (`phase12/eval_corpus.py`'s
`per_dataset_eval_corpora()`, the same one `test_admission_multi_signal_
corroboration_floor.py` already uses for its own single-value check) plus
every real poison scenario known to have 2+ corroborating admission signals
(`dev_corpus.py`'s 4 dev poison scenarios AND all 9 real DSRM/FARMA/MPBench
Track B scenarios), and reports the real minimum floor that reaches
`QUARANTINE` for every one of them, and the real false-positive rate at every
candidate floor -- not just the one value (2.5) that shipped.
"""

from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

from phase6.defense.admission.reasoning_guard import compute_signals as admission_signals
from phase6.defense.retrieval.embedding_signals import pool_consensus_divergence_signals_semantic
from phase6.defense.retrieval.signals import pool_consensus_divergence_signals
from phase6.defense.risk.risk_action import action_for_risk_estimate
from phase6.defense.risk.risk_score import GROUPED_GATED_ADMISSION_CORROBORATED, compute_memory_risk_score
from phase6.defense.policy.states import QUARANTINE, UNASSESSED
from phase6.defense.sleeper.signals import imperative_write_directive_signal
from phase6.defense.signals.contract import build_signal_context
from phase6.evaluation.ablations.dev_corpus import dev_admission_pool
from phase11.data.real_corpus import real_poison_scenarios
from phase12.eval_corpus import per_dataset_eval_corpora

TS = "2026-01-01T00:00:00Z"


def _ctx(memory_id: str, text: str):
    return build_signal_context(
        memory_id=memory_id, content_text=text, content_type="CONVERSATIONAL_FACT",
        memory_type="foundation", parent_ids=(), lifecycle_state="ACTIVE", creation_timestamp=TS,
    )


def _dev_poison_with_two_plus_signals() -> List[Tuple[str, Dict[str, float]]]:
    """The 4 real dev_corpus.py poison scenarios already confirmed (by direct
    computation) to have 2+ real admission signals firing."""
    eligible_ids = {"DEV-ADMISSION-POISON-HIGH", "DEV-ADMISSION-POISON-MED-A", "DEV-ADMISSION-POISON-MED-B", "DEV-ADMISSION-POISON-LOW-C"}
    out = []
    for m in dev_admission_pool().memories:
        if m.scenario_id in eligible_ids:
            out.append((m.scenario_id, admission_signals(_ctx(m.scenario_id, m.content_text))))
    return out


def _real_dsrm_farma_mpbench_with_full_signals() -> List[Tuple[str, Dict[str, float]]]:
    """All 9 real Track B scenarios, with the SAME full real signal set
    (admission + retrieval + sleeper) `defended_retrieval.py`'s live B9 path
    computes -- not just admission signals in isolation."""
    pool = {m.scenario_id: m.content_text for m in real_poison_scenarios().memories}
    scenario_ids = [f"REAL-{fam}-{i}" for fam in ("DSRM", "FARMA", "MPBENCH") for i in range(3)]
    out = []
    for sid in scenario_ids:
        contents = [pool[sid], "Jon lost his job as a banker on January 19, 2023.", "Gina lost her job at Door Dash in January 2023."]
        div = pool_consensus_divergence_signals(contents)
        sem, _cost = pool_consensus_divergence_signals_semantic(contents)
        ctx = _ctx(sid, pool[sid])
        signals = {
            **admission_signals(ctx), **div[0], "semantic_consensus_divergence_score": sem[0]["consensus_divergence_score"],
            **imperative_write_directive_signal(ctx), "dormancy_activation_score": 1.0,
        }
        out.append((sid, signals))
    return out


def sweep_corroboration_floor(floors: Sequence[float]) -> List[dict]:
    """For each candidate floor value: real QUARANTINE rate across (a) 13 real
    poison scenarios known to have 2+ corroborating admission signals (4 dev +
    9 real DSRM/FARMA/MPBench), and (b) the real false-positive rate across
    the FULL 502-record real benign corpus, checked at the full, real,
    end-to-end decision level (admission + retrieval + sleeper signals
    together, exactly as `defended_retrieval.py`'s live B9 path computes
    them), not just per-signal in isolation."""
    poison_cases = _dev_poison_with_two_plus_signals() + _real_dsrm_farma_mpbench_with_full_signals()

    benign_cases: List[Tuple[str, Dict[str, float]]] = []
    corpora = per_dataset_eval_corpora()
    for corpus in corpora.values():
        for pool in corpus.benign_pools:
            contents = [m.content_text for m in pool.memories]
            if not contents:
                continue
            div = pool_consensus_divergence_signals(contents)
            sem, _cost = pool_consensus_divergence_signals_semantic(contents)
            for m, d, s in zip(pool.memories, div, sem):
                ctx = _ctx(m.scenario_id, m.content_text)
                signals = {
                    **admission_signals(ctx), **d,
                    "semantic_consensus_divergence_score": s["consensus_divergence_score"],
                    **imperative_write_directive_signal(ctx), "dormancy_activation_score": 1.0,
                }
                benign_cases.append((m.scenario_id, signals))

    results = []
    for floor in floors:
        n_poison_quarantined = 0
        for scenario_id, signals in poison_cases:
            estimate = compute_memory_risk_score(
                scenario_id, signals, rule=GROUPED_GATED_ADMISSION_CORROBORATED, admission_corroboration_floor=floor,
            )
            action = action_for_risk_estimate(estimate, current_security_state=UNASSESSED)
            n_poison_quarantined += int(action == QUARANTINE)

        n_benign_quarantined = 0
        for scenario_id, signals in benign_cases:
            estimate = compute_memory_risk_score(
                scenario_id, signals, rule=GROUPED_GATED_ADMISSION_CORROBORATED, admission_corroboration_floor=floor,
            )
            action = action_for_risk_estimate(estimate, current_security_state=UNASSESSED)
            n_benign_quarantined += int(action == QUARANTINE)

        results.append({
            "floor": floor,
            "n_poison": len(poison_cases), "n_poison_quarantined": n_poison_quarantined,
            "poison_quarantine_rate": n_poison_quarantined / len(poison_cases),
            "n_benign": len(benign_cases), "n_benign_quarantined": n_benign_quarantined,
            "benign_false_quarantine_rate": n_benign_quarantined / len(benign_cases),
        })
    return results


if __name__ == "__main__":
    print("=== Real corroboration-floor sweep (13 real 2+-signal poison cases, 502 real benign records) ===")
    for r in sweep_corroboration_floor([0.5, 1.0, 1.5, 2.0, 2.2, 2.3, 2.4, 2.5, 2.6, 3.0, 4.0]):
        print(
            f"  floor={r['floor']:.2f}  poison_quarantine={r['n_poison_quarantined']}/{r['n_poison']}  "
            f"benign_false_quarantine={r['n_benign_quarantined']}/{r['n_benign']}"
        )


__all__ = ["sweep_corroboration_floor"]
