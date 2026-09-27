"""Phase 17 -- generalization experiments (Part B) and B10 ablation (A4).

B1 LEAVE-ONE-FAMILY-OUT (signal removal): for each attack family F, remove
exactly the signals that were WRITTEN FROM family F's own real content
(provenance recorded inline in `phase6/defense/admission/signals.py`) and
re-measure detection of F's records (all splits: original, regenerated,
evasion). The drop in F's detection is what F's own tailored signals were
contributing; what remains is what the rest of the stack generalizes to F.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, FrozenSet, List

from phase17.b10_ablation import VARIANTS, calibrate_ungated, decisions
from phase17.engine import admission_actions, rule_actions
from phase17.experiments import Arenas, POISON_GROUPS
from phase17.stats import paired_delta, rate_with_ci
from phase15.b10_live import live_threshold
from phase6.defense.risk.risk_score import GROUPED_GATED_RETRIEVAL_CORROBORATED

# family -> signals written FROM that family's real content (signals.py provenance comments).
SIGNALS_FROM_FAMILY: Dict[str, FrozenSet[str]] = {
    "dsrm": frozenset({"template_anomaly_score", "interrogative_restatement_score", "synthetic_repetition_padding_score"}),
    "farma": frozenset({"self_reference_score", "stale_precedent_dismissal_score", "unverifiable_closure_score"}),
    "mpbench": frozenset({"third_person_report_score", "preference_decision_update_score"}),
    "minja": frozenset({"entity_link_directive_score"}),
    "agentpoison": frozenset({"forged_provenance_confirmation_score"}),
    "memorygraft": frozenset({"decision_log_vocabulary_score"}),
    "sleeper_memory_poisoning": frozenset({"imperative_write_directive_score", "activation_shape_score"}),
}
OUT_LOFO = Path(__file__).parent / "data" / "lofo_results.json"
OUT_B10 = Path(__file__).parent / "data" / "b10_ablation_results.json"


def _family_ids(A: Arenas, family: str) -> List[str]:
    return [m for m, t in A.truth["isolated"].items() if t.is_poison and t.family == family]


def leave_one_family_out(A: Arenas) -> dict:
    out = {}
    systems = {
        "admission_only(B1)": lambda drop: admission_actions(A.tables["isolated"], drop),
        "rule_stack(B9-matrix)": lambda drop: rule_actions(A.tables["isolated"], drop=drop,
                                                          rule=GROUPED_GATED_RETRIEVAL_CORROBORATED),
    }
    for family, sigs in SIGNALS_FROM_FAMILY.items():
        ids = _family_ids(A, family)
        by_split = {}
        for sname, fn in systems.items():
            full, ablated = fn(frozenset()), fn(sigs)
            row = {"n": len(ids), "removed": sorted(sigs)}
            for key, fset in (("flagged", lambda a: a != "ALLOW"), ("excluded", lambda a: a in ("QUARANTINE", "BLOCK"))):
                f_vec = [fset(full[i]) for i in ids]
                a_vec = [fset(ablated[i]) for i in ids]
                row[key] = {"full": rate_with_ci(sum(f_vec), len(ids)), "family_signals_removed": rate_with_ci(sum(a_vec), len(ids)),
                            "paired": paired_delta(f_vec, a_vec)}
            by_split[sname] = row
        out[family] = by_split
    return out


def b10_ablation(A: Arenas) -> dict:
    """{variant: {arena: {split: cell}, fpr: ...}}; shipped = gated blend."""
    ds_pools = A.pools["datasets"]
    results = {}
    shipped = {}
    for arena in ("isolated", "coordinated", "frozen75"):
        shipped[arena] = decisions(A.pools[arena], 0.25, True, float("-inf"))
    for gate in (True, False):
        for vname, w in VARIANTS.items():
            name = f"{'gated' if gate else 'UNGATED'}:{vname}"
            cell = {"detect": {}, "fpr": {}}
            if gate:
                thr_poison, fpr_folds = float("-inf"), None
                d_ds = decisions(ds_pools, w, True, float("-inf"))
                fpr = rate_with_ci(sum(d_ds.values()), len(d_ds))
            else:
                scores, thrs, fold = calibrate_ungated(ds_pools, w)
                thr_poison = sum(thrs) / 2
                # thrs[f] was fit ONLY on nodes with fold != f; it is applied only to nodes with fold == f (held out)
                flagged = sum(1 for n, s in scores.items() if s >= thrs[fold[n]])
                fpr = rate_with_ci(flagged, len(scores))
            cell["fpr"]["datasets(502,held-out)"] = fpr
            for arena in ("isolated", "coordinated", "frozen75"):
                d = decisions(A.pools[arena], w, gate, thr_poison)
                for label, splits in POISON_GROUPS.items():
                    ids = [m for m, t in A.truth[arena].items() if t.is_poison and t.split in splits]
                    if not ids or (label == "frozen75") != (arena == "frozen75"):
                        continue
                    key = f"{arena}:{label}" if arena != "frozen75" else "frozen75:frozen75"
                    v = [d[i] for i in ids]
                    c = rate_with_ci(sum(v), len(ids))
                    c["vs_shipped"] = paired_delta([shipped[arena][i] for i in ids], v)
                    cell["detect"][key] = c
            results[name] = cell
    return results


def run_all() -> dict:
    A = Arenas()
    lofo = leave_one_family_out(A)
    OUT_LOFO.write_text(json.dumps(lofo, indent=2), encoding="utf-8")
    b10 = b10_ablation(A)
    OUT_B10.write_text(json.dumps(b10, indent=2), encoding="utf-8")
    return {"lofo": lofo, "b10": b10}


if __name__ == "__main__":
    run_all()
    print("DONE")
