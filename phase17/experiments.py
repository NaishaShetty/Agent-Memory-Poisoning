"""Phase 17 -- ablation experiments (Part A). Runs every variant of each
system across the arenas, reporting counts + Wilson CIs + paired exact test
against the full system, split by poison provenance (`signal_source` =
in-sample, `held_out_*` = held out) so in-sample results are never blended
with held-out ones.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Callable, Dict, FrozenSet, List, Mapping, Optional, Sequence

from phase17 import arenas
from phase17.engine import (
    ADMISSION_KEYS, ADMISSION_SIGNAL_KEYS, B8_ALL_FOUR, RETRIEVAL_SIGNAL_KEYS, SLEEPER_SIGNAL_KEYS, Truth,
    admission_actions, build_signal_table, counts, guard_actions, rule_actions, summarize, vector,
)
from phase17.poison_sets import SPLIT_EVASION, SPLIT_REGEN, SPLIT_SOURCE, all_records
from phase17.stats import paired_delta, rate_with_ci
from phase6.defense.risk.risk_score import (
    GROUPED_GATED, GROUPED_GATED_ADMISSION_CORROBORATED, GROUPED_GATED_RETRIEVAL_CORROBORATED, WEIGHTED_SUM,
)

OUT = Path(__file__).parent / "data" / "ablation_results.json"
POISON_GROUPS = {
    "in_sample(original15)": (SPLIT_SOURCE,),
    "held_out_regen": (SPLIT_REGEN,),
    "held_out_evasion": (SPLIT_EVASION,),
    "frozen75": ("frozen75",),
}
DETECT_KEYS = ("isolated:in_sample(original15)", "isolated:held_out_regen", "isolated:held_out_evasion",
               "coordinated:in_sample(original15)", "coordinated:held_out_regen", "frozen75:frozen75")
LEX_SEM = frozenset({"consensus_divergence_score", "semantic_consensus_divergence_score"})
NON_ADMISSION_ORDER = ("consensus_divergence_score", "semantic_consensus_divergence_score",
                       "imperative_write_directive_score", "activation_shape_score")


class Arenas:
    """Lazily-built (pools, truth, signal table) per arena."""

    def __init__(self, records=None):
        self.records = records if records is not None else all_records(include_evasion=True)
        iso_pools, iso_truth = arenas.isolated_arena(self.records)
        co_pools, co_truth = arenas.coordinated_arena([r for r in self.records if r.split != SPLIT_EVASION])
        fz_pools, fz_truth = arenas.frozen_arena()
        ds_pools, ds_truth = arenas.dataset_arena()
        self.pools = {"isolated": iso_pools, "coordinated": co_pools, "frozen75": fz_pools, "datasets": ds_pools}
        self.truth = {"isolated": iso_truth, "coordinated": co_truth, "frozen75": fz_truth, "datasets": ds_truth}
        self.tables = {k: build_signal_table(v) for k, v in self.pools.items()}


def _poison_ids(truth: Mapping[str, Truth], splits: Sequence[str]) -> List[str]:
    return [m for m, t in truth.items() if t.is_poison and t.split in splits]


def evaluate(actions_by_arena: Mapping[str, Mapping[str, str]], A: Arenas,
             baseline: Optional[Mapping[str, Mapping[str, str]]] = None) -> dict:
    """Aggregate one variant into detection/FPR cells, optionally paired
    against a baseline (the full system) on identical record ids."""
    out = {"detect": {}, "fpr": {}}
    for arena, actions in actions_by_arena.items():
        truth = A.truth[arena]
        rows = summarize(actions, truth)["rows"]
        base_rows = summarize(baseline[arena], truth)["rows"] if baseline else None
        for label, splits in POISON_GROUPS.items():
            ids = _poison_ids(truth, splits)
            if not ids or (label == "frozen75") != (arena == "frozen75"):
                continue
            for key in ("flagged", "excluded"):
                k, n = counts(rows, poison=True, key=key, split=None if arena == "frozen75" else None) \
                    if False else (sum(vector(rows, ids, key)), len(ids))
                cell = rate_with_ci(k, n)
                if base_rows is not None:
                    cell["vs_full"] = paired_delta(vector(base_rows, ids, key), vector(rows, ids, key))
                out["detect"][f"{arena}:{label}|{key}" if arena != "frozen75" else f"frozen75:frozen75|{key}"] = cell
        benign_splits = sorted({t.split for t in truth.values() if not t.is_poison})
        for split in benign_splits:
            ids = [m for m, t in truth.items() if not t.is_poison and t.split == split]
            for key in ("flagged", "excluded"):
                out["fpr"][f"{split}|{key}"] = rate_with_ci(sum(vector(rows, ids, key)), len(ids))
    return out


def run_rule_stack(A: Arenas, rule: str = GROUPED_GATED_RETRIEVAL_CORROBORATED) -> Dict[str, dict]:
    """Leave-one-out over the B9-style composed system. Arenas with retrieval
    structure (frozen75) are where retrieval-only evidence can decide."""
    def acts(drop=frozenset(), r=rule, floor=None):
        return {a: rule_actions(A.tables[a], drop=drop, rule=r, floor=floor) for a in A.tables}

    full = acts()
    variants = {"FULL": full}
    for key in ADMISSION_KEYS:
        variants[f"-signal:{key}"] = acts(frozenset({key}))
    for key in NON_ADMISSION_ORDER:
        variants[f"-signal:{key}"] = acts(frozenset({key}))
    variants["-group:admission(all 14)"] = acts(frozenset(ADMISSION_SIGNAL_KEYS))
    variants["-group:retrieval(lex+sem)"] = acts(frozenset(RETRIEVAL_SIGNAL_KEYS))
    variants["-group:sleeper(directive+shape)"] = acts(frozenset({"imperative_write_directive_score", "activation_shape_score"}))
    variants["rule:GROUPED_GATED"] = acts(r=GROUPED_GATED)
    variants["rule:ADMISSION_CORROBORATED(floor2.5)"] = acts(r=GROUPED_GATED_ADMISSION_CORROBORATED)
    variants["rule:WEIGHTED_SUM"] = acts(r=WEIGHTED_SUM)
    for f in (1.2, 2.4, 3.0):
        variants[f"rule:ADMISSION_CORROBORATED,floor={f}"] = acts(r=GROUPED_GATED_ADMISSION_CORROBORATED, floor=f)
    return {name: evaluate(a, A, baseline=None if name == "FULL" else full) for name, a in variants.items()}


def run_admission_only(A: Arenas) -> Dict[str, dict]:
    """Leave-one-signal-out over B1-style admission alone (weighted sum)."""
    def acts(drop=frozenset()):
        return {a: admission_actions(A.tables[a], drop) for a in A.tables}

    full = acts()
    variants = {"FULL": full}
    for key in ADMISSION_KEYS:
        variants[f"-signal:{key}"] = acts(frozenset({key}))
    return {name: evaluate(a, A, baseline=None if name == "FULL" else full) for name, a in variants.items()}


def run_guards(A: Arenas) -> Dict[str, dict]:
    """Leave-one-guard-out over B8 via pipeline.evaluate_pool()."""
    B = B8_ALL_FOUR
    cfgs = {
        "FULL(B8)": B,
        "-admission": replace(B, admission_enabled=False),
        "-retrieval": replace(B, retrieval_enabled=False),
        "-propagation": replace(B, propagation_enabled=False),
        "-sleeper": replace(B, sleeper_enabled=False),
        "-sibling_propagation": replace(B, sibling_propagation_enabled=False),
        "retrieval:semantic-metric": replace(B, retrieval_metric="semantic"),
    }
    acts = {name: {a: guard_actions(A.pools[a], cfg) for a in A.pools} for name, cfg in cfgs.items()}
    full = acts["FULL(B8)"]
    return {name: evaluate(a, A, baseline=None if name == "FULL(B8)" else full) for name, a in acts.items()}


def holm_adjust(system_results: Dict[str, dict]) -> None:
    """Holm step-down correction over ALL paired tests within one system
    (one family per flagged/excluded key) -- adds `p_holm` to each cell. With
    dozens of leave-one-out tests, an uncorrected p=0.03 is expected by chance."""
    for key in ("flagged", "excluded"):
        cells = [c["vs_full"] for r in system_results.values() for k, c in r["detect"].items()
                 if k.endswith(f"|{key}") and "vs_full" in c]
        order = sorted(range(len(cells)), key=lambda i: cells[i]["p_exact"])
        m, running = len(cells), 0.0
        for rank, i in enumerate(order):
            running = max(running, min(1.0, (m - rank) * cells[i]["p_exact"]))
            cells[i]["p_holm"] = running


def run_all(out: Path = OUT) -> dict:
    A = Arenas()
    results = {
        "rule_stack": run_rule_stack(A),
        # Live-path B9 (what actually EXCLUDES content in Phase 14): the matrix rule above never
        # reaches QUARANTINE, so exclusion-level ablation needs the admission-corroborated baseline.
        "live_b9_stack": run_rule_stack(A, rule=GROUPED_GATED_ADMISSION_CORROBORATED),
        "admission_only": run_admission_only(A), "guards_b8": run_guards(A),
    }
    for system in results.values():
        holm_adjust(system)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2, default=list), encoding="utf-8")
    return results


if __name__ == "__main__":
    run_all()
    print("DONE")
