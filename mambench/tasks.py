"""Task executors. One `run_<executor>(params, workdir)` per registry entry.

Each executor calls an existing, frozen project function and converts its output into
metrics with explicit denominators. Nothing here re-implements attack or defence logic.
Executors write only inside `workdir`; the runner fails any task that modifies a tracked
file. They return `(metrics, details)` or raise:

* `NotEvaluable` -- the evidence a metric needs is absent (never coerced to zero);
* `IntegrityViolation` -- an integrity-critical check found a problem (the task FAILS).
"""
from __future__ import annotations

import hashlib
import importlib
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Mapping, Tuple

from mambench.schema import count, proportion, value

Metrics = List[Dict]
Out = Tuple[Metrics, Dict]
ROOT = Path(__file__).resolve().parents[1]


class NotEvaluable(Exception):
    pass


class IntegrityViolation(Exception):
    pass


def _exact_count(rate: float, n: int, name: str) -> int:
    """Recover the integer numerator behind a published rate; refuse if it is not exact."""
    k = round(rate * n)
    if abs(k / n - rate) > 1e-9:
        raise ValueError(f"{name}: rate {rate} is not k/{n} for an integer k")
    return k


# --- attack validity ------------------------------------------------------------------

def run_attack_register_coverage(params: Mapping, workdir: Path) -> Out:
    import phase17.attack_register as ar

    original = ar.OUT
    ar.OUT = workdir / "attack_register.json"  # build() writes its output; keep the committed copy untouched
    try:
        reg = ar.build()
    finally:
        ar.OUT = original
    built = [p for p in reg["populations"] if p["n"] > 0]
    if not built:
        raise NotEvaluable("no attack population has instances in this checkout")
    metrics = [
        proportion("proportion_mechanism_validated", sum(bool(p["mechanism_validated_at_generation"]) for p in built), len(built)),
        proportion("proportion_harm_measured", sum(p["harm_measured_instances"] > 0 for p in built), len(built)),
        count("attack_instances", reg["total_attack_instances"]),
        count("populations_not_built", len(reg["populations"]) - len(built)),
    ]
    return metrics, {"populations": reg["populations"], "gaps": reg["gaps"]}


def run_poison_admission_rate(params: Mapping, workdir: Path) -> Out:
    from phase12.security_metrics import compute_par

    r = compute_par()
    if r.n_attempts == 0:
        raise NotEvaluable("no injection attempts were produced")
    metrics = [proportion("poison_admission_rate", r.n_admitted, r.n_attempts)]
    for fam, n in sorted(r.per_family_n.items()):
        metrics.append(proportion("poison_admission_rate", _exact_count(r.per_family_par[fam], n, fam), n, group=fam))
    return metrics, {}


# --- defence detection ----------------------------------------------------------------

def run_frozen75_ablation(params: Mapping, workdir: Path) -> Out:
    from phase6.defense.orchestration.pipeline import (
        ALLOW, B0_TO_B7, B8_ALL_FOUR, SLEEPER_ONLY, IllegalTransitionError, evaluate_pool,
    )
    from phase6.evaluation.ablations.corpus import all_pools

    pools = all_pools()
    metrics: Metrics = []
    excluded: Dict[str, List[str]] = {}
    for config in B0_TO_B7 + (SLEEPER_ONLY, B8_ALL_FOUR):
        outcomes = []
        for pool in pools:
            try:
                outcomes.extend(evaluate_pool(pool, config, run_id=f"mambench-{config.name}"))
            except IllegalTransitionError:
                excluded.setdefault(config.name, []).append(pool.pool_id)
        poison = [o for o in outcomes if o.is_poison_ground_truth]
        benign = [o for o in outcomes if not o.is_poison_ground_truth]
        if not poison or not benign:
            raise NotEvaluable(f"{config.name}: no poison or no benign outcomes to score")
        metrics += [
            proportion("poison_detection_rate", sum(o.combined_action != ALLOW for o in poison), len(poison), group=config.name),
            proportion("benign_false_positive_rate", sum(o.combined_action != ALLOW for o in benign), len(benign), group=config.name),
            count("excluded_pools", len(excluded.get(config.name, ())), group=config.name),
        ]
    return metrics, {"excluded_pools": excluded, "n_pools": len(pools)}


def _sha_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "absent"


def run_split_eval(params: Mapping, workdir: Path) -> Out:
    from mambench.registry import JUDGE_CACHES, _ollama_reachable
    from phase17.bench_runner import run

    res = run(params["split"], params["defense"], workdir / f"{params['split']}_{params['defense']}.json")
    s = res["summary"]
    if s["n"] == 0:
        raise NotEvaluable(f"split {params['split']} has no records in this checkout")
    details = {"split": params["split"], "defense": params["defense"], "bench_manifest": res["manifest"],
               # B11/B12 call an LLM judge; with no server reachable every decision came from the committed cache
               "judge_source": "live_or_cache" if _ollama_reachable() else "cache_only",
               "judge_cache_sha256": {p: _sha_file(ROOT / p) for p in JUDGE_CACHES}}
    return [proportion("flag_rate", s["flagged"], s["n"]), proportion("exclusion_rate", s["excluded"], s["n"])], details


# --- propagation ----------------------------------------------------------------------

def _signal_values(obj, group: str) -> Metrics:
    out: Metrics = []
    for name in ("fan_out_rate", "re_entry_rate", "cycle_reinforcement_depth", "cross_task_bleed"):
        v = getattr(obj, name, None)
        v = getattr(v, "mean", v)  # a SignalDistribution carries its mean
        v = getattr(v, "value", v)  # a footprint trial carries a SignalResult
        if v is None or v != v:  # absent or NaN: not computable, so not reported as a number
            continue
        out.append(value(name, v, group=group))
    return out


def run_seven_attack_footprint(params: Mapping, workdir: Path) -> Out:
    from phase7.propagation.attack_study import run_seven_attack_footprint_study

    trials = run_seven_attack_footprint_study(storage_dir=workdir / "footprint")
    if not trials:
        raise NotEvaluable("no attack trials were produced")
    metrics = [proportion("attacks_admitted", sum(bool(t.admitted) for t in trials.values()), len(trials))]
    for aid, t in sorted(trials.items()):
        metrics += _signal_values(t, aid)
    return metrics, {aid: t.note for aid, t in trials.items()}


def run_benign_baseline(params: Mapping, workdir: Path) -> Out:
    from phase7.propagation.benign_baseline_study import run_benign_baseline_study

    r = run_benign_baseline_study(storage_dir=workdir / "benign")
    metrics = _signal_values(r.baseline, "benign")
    if not metrics:
        raise NotEvaluable("no baseline signal could be computed")
    return metrics, {"num_roots": r.num_roots, "n_by_signal": {k: getattr(r.baseline, k).n for k in
                     ("fan_out_rate", "re_entry_rate", "cycle_reinforcement_depth", "cross_task_bleed")}}


def run_propagation_rate_live(params: Mapping, workdir: Path) -> Out:
    from phase12.propagation.propagation_rate import compute_pr

    r = compute_pr(ledger_dir=workdir / "pr_ledger")
    if r.n_admitted == 0:
        raise NotEvaluable("no admitted scenarios to measure propagation on")
    metrics = [value("propagation_rate", r.overall_pr)]
    if r.overall_guard_catch_rate is not None:
        metrics.append(value("guard_catch_rate", r.overall_guard_catch_rate))
    return metrics, {"n_admitted": r.n_admitted, "n_propagated": r.n_propagated, "per_family_pr": r.per_family_pr}


# --- sleeper --------------------------------------------------------------------------

def run_directive_evasion(params: Mapping, workdir: Path) -> Out:
    from phase8.detection.sleeper_directive_evasion_study import run_directive_evasion_study

    cases = run_directive_evasion_study().case_results
    if not cases:
        raise NotEvaluable("the study produced no cases")
    return [proportion("directive_hit_rate", sum(bool(c.hit) for c in cases), len(cases))], \
        {c.label: c.hit for c in cases}


_SHAPE_SCRIPT = (
    "import json; from phase8.detection.sleeper_activation_shape_study import run_sleeper_activation_shape_study as f; "
    "r = f(); print(json.dumps({k: {'match': getattr(r, k).matches_dormant_pattern, "
    "'selected': getattr(r, k).selected_by_condition} for k in ('poison', 'benign')}))"
)


def run_activation_shape_live(params: Mapping, workdir: Path) -> Out:
    import os

    exe = Path(os.environ.get("MAMBENCH_H4VENV", r"C:\h4venv")) / "Scripts" / "python.exe"
    p = subprocess.run([str(exe), "-c", _SHAPE_SCRIPT], cwd=str(ROOT), capture_output=True, text=True, timeout=3600)
    if p.returncode != 0:
        raise RuntimeError(f"activation-shape study failed in the isolated environment: {p.stderr.strip()[-500:]}")
    r = json.loads(p.stdout.strip().splitlines()[-1])
    return [proportion("activation_shape_poison_match", int(bool(r["poison"]["match"])), 1)], r


# --- attribution ----------------------------------------------------------------------

def run_attribution_metrics(params: Mapping, workdir: Path) -> Out:
    from phase13.attribution_metrics import compute_attribution_metrics

    r = compute_attribution_metrics()
    if r.n_poison_scenarios == 0 or r.n_derivation_events == 0:
        raise NotEvaluable("the persisted Phase 13 ledger has no scenarios or no derivation events")
    n, d = r.n_poison_scenarios, r.n_derivation_events
    metrics = [
        proportion("origin_family_match", _exact_count(r.origin_family_match_accuracy, n, "origin"), n),
        proportion("path_fidelity", _exact_count(r.path_fidelity_accuracy, d, "path"), d),
        proportion("lineage_ambiguity", _exact_count(r.lineage_ambiguity_rate, d, "ambiguity"), d),
    ]
    if r.origin_false_attribution_rate is None:
        raise NotEvaluable("independent injection-time ground truth is missing, so false attribution cannot be checked")
    metrics.append(proportion("origin_false_attribution", _exact_count(r.origin_false_attribution_rate, n, "false"), n))
    return metrics, {"mean_time_to_attribute_origin_ms": r.mean_time_to_attribute_origin_ms}


# --- provenance integrity -------------------------------------------------------------

def run_ledger_tamper_evidence(params: Mapping, workdir: Path) -> Out:
    from phase17.defence_v7.ledger_chain import ChainedLedger, verify

    def fresh(name: str) -> Path:
        p = workdir / name / "ledger.jsonl"
        p.parent.mkdir(parents=True)
        led = ChainedLedger(p)
        for i in range(5):
            led.record_event(f"note {i}", "user_turn")
        return p

    def lines(p: Path) -> List[str]:
        return [l for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]

    clean = verify(fresh("clean"))["ok"]

    def edit(ls):
        r = json.loads(ls[2]); r["text"] = "tampered"; ls[2] = json.dumps(r); return ls

    mutations = {
        "edit": edit,
        "delete": lambda ls: ls[:2] + ls[3:],
        "reorder": lambda ls: ls[:1] + [ls[2], ls[1]] + ls[3:],
        "truncate": lambda ls: ls[:-1],
    }
    detected = {}
    for name, mutate in mutations.items():
        p = fresh(name)
        p.write_text("\n".join(mutate(lines(p))) + "\n", encoding="utf-8")
        detected[name] = not verify(p)["ok"]
    metrics = [proportion("tamper_detection", sum(detected.values()), len(detected)),
               proportion("clean_chain_verified", int(clean), 1)]
    if not clean or not all(detected.values()):
        raise IntegrityViolation(f"tamper evidence failed: clean_ok={clean}, detected={detected}")
    return metrics, {"detected": detected}


def run_evaluator_field_rejection(params: Mapping, workdir: Path) -> Out:
    from phase17.provenance_integrity import structural_forgery_is_rejected

    try:
        r = structural_forgery_is_rejected()
    except AssertionError as exc:  # raised by the frozen check when a forged key is accepted
        raise IntegrityViolation(str(exc)) from exc
    tried, rejected = r["forbidden_keys_tried"], r["confirmed_rejected"]
    if not tried:
        raise NotEvaluable("FORBIDDEN_SIGNAL_KEYS is empty")
    if set(rejected) != set(tried):
        raise IntegrityViolation(f"accepted evaluator-only keys: {sorted(set(tried) - set(rejected))}")
    return [proportion("forbidden_key_rejection", len(rejected), len(tried))], {"keys": tried}


# --- data integrity -------------------------------------------------------------------

def run_leakage_audit(params: Mapping, workdir: Path) -> Out:
    from phase17.leakage_audit import LeakageError, audit_all

    try:
        r = audit_all()
    except LeakageError as exc:
        raise IntegrityViolation(f"leakage audit failed: {exc}") from exc
    if not r.checks:
        raise NotEvaluable("the leakage audit ran no checks")
    if set(r.passed) != set(r.checks):
        raise IntegrityViolation(f"leakage checks failed: {sorted(set(r.checks) - set(r.passed))}")
    return [proportion("leakage_checks_passed", len(r.passed), len(r.checks))], {"details": r.details}


def run_leakage_text_and_metadata(params: Mapping, workdir: Path) -> Out:
    """The two leakage-audit checks that need only LoCoMo: dev/eval text disjointness and poison
    record metadata. The same functions audit_all() calls; the other two checks need the processed
    unified-memory corpora and are covered by integrity.leakage_audit."""
    from phase17.leakage_audit import LeakageError, check_dev_eval_text_disjoint, check_poison_record_metadata_complete
    from phase17.novel_attacks import novel_records
    from phase17.poison_sets import all_records
    from phase17.translation import zh_records

    try:
        details = {"dev_eval_text_disjoint": check_dev_eval_text_disjoint(),
                   "poison_record_metadata_complete": check_poison_record_metadata_complete(
                       list(all_records()) + novel_records() + zh_records())}
    except LeakageError as exc:
        raise IntegrityViolation(f"leakage check failed: {exc}") from exc
    if details["dev_eval_text_disjoint"]["n_overlap"] or details["poison_record_metadata_complete"]["n_missing"]:
        raise IntegrityViolation(f"leakage check failed: {details}")
    return [proportion("leakage_checks_passed", 2, 2)], details


def run_holdout_freeze_digests(params: Mapping, workdir: Path) -> Out:
    results = {}
    for m in params["modules"]:
        mod = importlib.import_module(m)
        if not mod.FREEZE.is_file():
            results[m] = "freeze record missing"
            continue
        recorded = json.loads(mod.FREEZE.read_text(encoding="utf-8")).get("sha256")
        try:
            results[m] = "match" if mod._digest() == recorded else "MISMATCH"
        except FileNotFoundError as exc:
            results[m] = f"corpus file missing: {exc.filename}"
    bad = {m: s for m, s in results.items() if s != "match"}
    if bad:
        raise IntegrityViolation(f"frozen hold-out integrity failed: {bad}")
    return [proportion("freeze_digest_match", len(results), len(results))], results
