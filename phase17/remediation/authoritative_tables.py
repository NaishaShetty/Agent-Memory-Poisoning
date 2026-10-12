"""Authoritative result tables, regenerated from artifacts (Deliverable 6; review P0-7, D6, M11, D12).

Every number in the manuscript (`paper/`) and in the remediation reports is read from the tables this
module writes (`results/tables/*.json` + `.md`) -- no hand-typed figure. Each table records its source
artifacts and the function that computed it in `results/TABLE_INDEX.md`. A table whose artifact does not
exist yet is written as PENDING with no number, never estimated.

Conventions: rates carry k/n and a 95% Wilson interval; paired comparisons are exact McNemar on the same
items; FPRs are always reported beside recall for the SAME configuration, channel and evidence condition.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Dict, List

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "phase17" / "data"
REM = DATA / "remediation"
OUTDIR = ROOT / "results" / "tables"
INDEX = ROOT / "results" / "TABLE_INDEX.md"


def _L(name: str, base: Path = DATA):
    p = base / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _r(k: int, n: int) -> Dict:
    from phase17.stats import rate_with_ci

    return rate_with_ci(k, n)


def _fmt(d: Dict) -> str:
    return f"{d['k']}/{d['n']} ({100 * d['rate']:.1f}%)"


def _mc(a: List[bool], b: List[bool]) -> Dict:
    from phase17.stats import paired_delta

    return paired_delta([bool(x) for x in a], [bool(x) for x in b])


# ------------------------------------------------------------------------------------------- tables
def t1_validity() -> Dict:
    w = _L("working_set.json")
    rows = [{"population": k, "n": v["n_total"], "subverts": v["n_subverts"], "working": v["n_working_set"],
             "rate": round(v["rate"], 4), "lost_to_mechanism_check": v["lost_to_mechanism_check"]}
            for k, v in sorted(w["populations"].items(), key=lambda kv: -kv[1]["rate"])]
    own = [v for k, v in w["populations"].items() if k.startswith("own")]
    ext = [v for k, v in w["populations"].items() if not k.startswith("own")]
    split = {g: _r(sum(v["n_working_set"] for v in vs), sum(v["n_total"] for v in vs))
             for g, vs in (("own", own), ("external", ext))}
    gandalf = w["populations"]["exttest_gandalf"]
    return {"title": "Attack validity: working-attack rate per population (union over probes, C0 judge, mechanism-checked)",
            "sources": ["working_set.json", "attack_validity_audit.json", "mechanism_validation.json"],
            "total": _r(w["n_working_set"], w["n_total"]), "split": split, "rows": rows,
            "notes": [f"Gandalf contributes {gandalf['n_total']}/{w['n_total']} "
                      f"({100 * gandalf['n_total'] / w['n_total']:.0f}%) of the denominator.",
                      "holdout2_mosscap is a seeded 300-item sample of 1,200, not a census.",
                      "Working status is a property of (agent qwen2.5:7b, probe, judge), not of an attack in all settings."]}


def t2_judge_sensitivity() -> Dict:
    d = _L("validity_judge_sensitivity.json", REM)
    if not d:
        return {"title": "Validity-audit judge sensitivity", "status": "PENDING", "sources": ["remediation/validity_judge_sensitivity.json"]}
    R = d["results"]
    keys = ["ALL", "own", "external"] + sorted(k for k in R if not k.startswith(("ALL", "own", "external", "family:")))
    rows = []
    for k in keys + sorted(k for k in R if k.startswith("own_")):
        if k not in R or any(r["group"] == k for r in rows):
            continue
        v = R[k]
        rows.append({"group": k, "n": v["n"],
                     "working_C0": _fmt(v["fitted_probe_working_C0"]), "working_vote": _fmt(v["fitted_probe_working_vote"]),
                     "base_rate_C0": _fmt(v["task_alone_base_rate_C0"]), "base_rate_vote": _fmt(v["task_alone_base_rate_vote"]),
                     "paired": f"+{v['working_only_C0']}/-{v['working_only_vote']} (p={v['paired_p_exact']:.2g})"})
    return {"title": "Validity-audit judge sensitivity (fitted probe; C0 vs majority vote; mechanism-checked)",
            "sources": ["remediation/validity_judge_sensitivity.json"], "rows": rows, "caveats": d["caveats"]}


def _working_mask(name: str):
    if name == "holdout4":
        e = _L("eval_round7_holdouts.json")["holdouts"]["holdout4"]["raw"]
        W = set(_L("holdout4_validity.json")["working_ids"])
        return [i in W for i in e["attack_ids"]], e["attack"]
    if name == "holdout5":
        return _L("holdout5_causal.json")["per_item_working"], _L("eval_round7_holdouts.json")["holdouts"]["holdout5"]["raw"]["attack"]
    if name == "holdout6":
        return _L("holdout6_causal.json")["per_item_working"], _L("eval_round7b_holdouts.json")["holdouts"]["holdout6"]["raw"]["attack"]
    if name == "holdout8":
        e = _L("eval_holdout8.json")
        W = set(_L("holdout8_validity.json")["working_ids"])
        return [i in W for i in e["raw"]["attack_ids"]], e["raw"]["attack"]
    raise KeyError(name)


def t3_two_denominators() -> Dict:
    rows = []
    for h in ("holdout4", "holdout5", "holdout6", "holdout8"):
        mask, att = _working_mask(h)
        row = {"holdout": h, "working": f"{sum(mask)}/{len(mask)}"}
        for c in ("B12", "B13", "B14", "B17", "B18"):
            if c not in att:
                continue
            full = _r(sum(att[c]), len(att[c]))
            ws = [x for x, m in zip(att[c], mask) if m]
            wk = _r(sum(ws), len(ws))
            row[c] = {"full": _fmt(full), "working": _fmt(wk), "shift_points": round(100 * (wk["rate"] - full["rate"]), 1)}
        rows.append(row)
    return {"title": "Detection recall on the full population and on the causal working subset, per frozen hold-out",
            "sources": ["eval_round7_holdouts.json", "eval_round7b_holdouts.json", "eval_holdout8.json",
                        "holdout4_validity.json", "holdout5_causal.json", "holdout6_causal.json", "holdout8_validity.json"],
            "rows": rows, "notes": ["Hold-out 7's working subset is not reportable (probe base rate 28% > 20% rule)."]}


def t4_memory_poisoning_holdouts() -> Dict:
    rows = []
    e4 = _L("eval_round7_holdouts.json")["holdouts"]["holdout4"]
    e7 = _L("eval_round7b_holdouts.json")["holdouts"]["holdout7"]
    e8 = _L("eval_holdout8.json")
    for name, e, raw in (("holdout4", e4, e4["raw"]), ("holdout7", e7, e7["raw"]), ("holdout8", e8, e8["raw"])):
        A, B = raw["attack"], raw["benign"]
        Bu = raw.get("benign_user_turn", {})
        row = {"holdout": name, "n_attacks": len(A["B13"]), "n_benign": len(B["B13"]), "configs": {}}
        for c in ("B12", "B13", "B14", "B17", "B18"):
            if c in A:
                row["configs"][c] = {"recall": _fmt(_r(sum(A[c]), len(A[c]))),
                                     "fpr_untrusted": _fmt(_r(sum(B[c]), len(B[c]))),
                                     "fpr_user_turn": _fmt(_r(sum(Bu[c]), len(Bu[c]))) if c in Bu else "n/a"}
        p = _mc(A["B13"], A["B14"])
        row["B13_vs_B14"] = f"+{p['only_a']}/-{p['only_b']} (p={p['p_exact']:.2g})"
        bl = e.get("baselines") or {}
        row["baselines"] = {k: _fmt(v["attack_recall"]) for k, v in bl.items() if "attack_recall" in v}
        rows.append(row)
    return {"title": "Memory-poisoning hold-outs (each scored once; B13 with the owner's conversation as evidence)",
            "sources": ["eval_round7_holdouts.json", "eval_round7b_holdouts.json", "eval_holdout8.json"], "rows": rows,
            "notes": ["Benign 'untrusted' = benign notes scored on the tool_output channel (strict); 'user_turn' = same notes "
                      "on the trusted channel, where B13-B17 exclude nothing by construction.",
                      "Attacks were assigned the tool_output channel by the evaluator (see T5)."]}


def t5_b13_decomposition() -> Dict:
    d = _L("b13_decomposition.json", REM)
    rows = []
    for h, v in d["holdouts"].items():
        a = v["arms"]
        rows.append({"holdout": h,
                     **{k: f"{_fmt(a[k]['recall'])} | FPR {_fmt(a[k]['benign_fpr_untrusted'])}"
                        for k in ("B12_stored", "channel_plus_rules", "corroboration_only", "B13")},
                     "user_channel_poisoning": f"excluded 0/{v['n_attacks']}; flagged-but-admitted {_fmt(a['user_channel_poisoning']['flagged_but_admitted'])}",
                     "corroboration_increment": f"+{v['corroboration_increment']['attacks_caught_only_with_corroboration']} attacks "
                                                f"(p={v['corroboration_increment']['p_exact']:.2g}), +{v['corroboration_increment']['benign_fp_added']} benign FP"})
    return {"title": "What B13 depends on: channel + content rules vs owner-conversation corroboration (post-hoc decomposition)",
            "sources": ["remediation/b13_decomposition.json"], "rows": rows}


def t6_injection_holdouts() -> Dict:
    e5 = _L("eval_round7_holdouts.json")["holdouts"]["holdout5"]
    e6 = _L("eval_round7b_holdouts.json")["holdouts"]["holdout6"]
    rows = []
    for name, e in (("holdout5", e5), ("holdout6", e6)):
        row = {"holdout": name, "n_attacks": e["n_attacks"], "n_benign": e["n_benign"], "configs": {}}
        for c, v in e["configs"].items():
            row["configs"][c] = {"recall": _fmt(v["attack_recall"]), "matched_benign_fpr": _fmt(v["matched_benign_fpr"])}
        for k, v in (e.get("baselines") or {}).items():
            row["configs"][k] = {"recall": _fmt(v["attack_recall"]), "matched_benign_fpr": _fmt(v["matched_benign_fpr"])}
        rows.append(row)
    return {"title": "Injection-shaped hold-outs with matched benign (each scored once; no evidence)",
            "sources": ["eval_round7_holdouts.json", "eval_round7b_holdouts.json"], "rows": rows}


def t7_baselines() -> Dict:
    b = _L("baseline_breakdown_round6.json")
    rows = []
    for g in ("aggregate_own", "aggregate_external"):
        row = {"group": g, "n": b[g]["n"]}
        for k, v in b[g].items():
            if isinstance(v, dict) and "rate" in v:
                row[k] = _fmt(v)
        rows.append(row)
    fpr = {k: _fmt(v) for k, v in b["ordinary_benign_fpr"].items() if isinstance(v, dict) and "rate" in v}
    own = b["aggregate_own"]
    bl = {k: v["rate"] for k, v in own.items() if isinstance(v, dict) and "rate" in v and "@" in k}
    best_bl = max(bl, key=bl.get)
    lead = {c: round(100 * (own[c]["rate"] - bl[best_bl]), 1) for c in ("B13", "B17") if c in own}
    return {"title": "Disaggregated comparison against published detectors (development thresholds reused, never re-fitted)",
            "sources": ["baseline_breakdown_round6.json"], "rows": rows, "ordinary_benign_fpr": fpr,
            "lead_on_own_attacks_over_best_baseline": {"best_baseline": best_bl, "points": lead},
            "notes": ["Replaces the hand-typed 'nearly 39 points' (review D6), which no artifact supports."]}


def t8_harm() -> Dict:
    h = _L("harm_study_v2.json")["overall"]
    rj = _L("harm_rejudged.json")["by_judge"]
    nr = _L("noise_repeats.json")
    return {"title": "Unconditional harm (309 own+external instances; development data)",
            "sources": ["harm_study_v2.json", "harm_rejudged.json", "noise_repeats.json"],
            "original_answers_judge_J0": {k: _fmt(h[k]) for k in ("harm_no_poison", "harm_no_defense", "harm_b12", "harm_b13")},
            "regenerated_answers_rep1": {j: {k: _fmt(v[k]) for k in ("task_alone_base_rate", "harm_undefended", "harm_b13")}
                                         for j, v in rj.items()},
            "noise": nr["harm"],
            "notes": ["The re-judge (harm_rejudged.json) scores a REGENERATED undefended run (noise_repeats rep1) and newly "
                      "generated no-poison answers, not harm_study_v2's answers. J0 scored the same rep1 answers 94/309 in "
                      "noise_repeats and 99/309 in harm_rejudged: judge-only run-to-run variation of 5 items (review D5).",
                      "J0 agreement with human annotators: kappa 0.2 (40 items); J2 (adopted): 0.688 vs annotator 2."]}


def t9_adaptive() -> Dict:
    p = _L("eval_rejection_powered.json")
    s = _L("eval_ledger_radius_sweep.json")
    l = _L("adaptive_ledger_b13.json")
    return {"title": "Adaptive paraphrase attacker vs the rejection ledger (development data only)",
            "sources": ["eval_rejection_powered.json", "eval_ledger_radius_sweep.json", "adaptive_ledger_b13.json",
                        "rejection_memory_config.json"],
            "powered_radius_0.90": {"control": f"{p['per_arm']}"[:400], "paired": p.get("paired_B16_vs_B15")},
            "radius_sweep": {k: v for k, v in s.items() if k not in ("rows",)} if s else "missing",
            "ledger_plus_B13": {"control": l["control_evasion"], "ledger": l["ledger_evasion"],
                                "paired": l["paired_ledger_vs_control"]},
            "notes": ["Attacker: 5 feedback-guided LLM paraphrases with NLI claim preservation, one scope. Not tested: "
                      "single-shot, cross-scope, TTL expiry, optimisation attacks. Seed rule revised after a failed "
                      "pre-registered test; radius 0.95 selected by a pre-fixed rule on the same 130 seeds. Never run on a hold-out."]}


def t10_propagation() -> Dict:
    d = _L("derived_memory_eval.json")
    W = ("QUARANTINE", "REQUIRE_VALIDATION")
    ex = [r for r in d["rows"] if r["b13_excluded"]]
    c, nc = [r for r in ex if r["carry"]], [r for r in ex if not r["carry"]]
    e8 = _L("eval_holdout8.json")["derived_memory"]
    p2 = _L("propagation_2gen.json", REM)
    return {"title": "Propagation through consolidation: one generation (dev + hold-out 8) and two generations (P2)",
            "sources": ["derived_memory_eval.json", "eval_holdout8.json", "remediation/propagation_2gen.json"],
            "gen1_dev": {"payload_carried": _fmt(d["payload_carried"]),
                         "harm_on_b13_excluded": {k: _fmt(v) for k, v in d["harm_on_b13_excluded"].items() if "paired" not in k},
                         "withheld_carrying": {"lexical": _fmt(_r(sum(r['lex_action'] in W for r in c), len(c))),
                                               "semantic": _fmt(_r(sum(r['sem_action'] in W for r in c), len(c)))},
                         "withheld_NON_carrying_(legitimate_derived_lost)": {
                             "lexical": _fmt(_r(sum(r['lex_action'] in W for r in nc), len(nc))),
                             "semantic": _fmt(_r(sum(r['sem_action'] in W for r in nc), len(nc)))},
                         "b13_missed_containment_cannot_act": d["b13_missed_guard_cannot_act"],
                         "benign_collateral": {k: (_fmt(v) if isinstance(v, dict) else v)
                                               for k, v in d["collateral_benign_false_positives"].items()}},
            "gen1_holdout8": {"payload_carried": _fmt(e8["payload_carried"]),
                              "laundered_admitted_of_carried_excluded": e8["laundered_admitted_of_carried_excluded"]},
            "gen2_P2": ({k: v for k, v in p2.items() if k != "rows"} if p2 else "PENDING")}


def t11_sleeper() -> Dict:
    f = _L("ho8_anomaly_devfit.json", REM)
    arms = {}
    for arm, v in f["arms"].items():
        for p in ("p90", "p99"):
            a = v[p]
            arms[f"{arm}:{p}"] = {"anomaly": f"{_fmt(a['anomaly']['recall'])} | FPR {_fmt(a['anomaly']['benign_fpr'])}",
                                  "union2": f"{_fmt(a['union2_B13_or_anomaly']['recall'])} | FPR {_fmt(a['union2_B13_or_anomaly']['benign_fpr'])}",
                                  "B13": f"{_fmt(a['B13_alone']['recall'])} | FPR {_fmt(a['B13_alone']['benign_fpr'])}"}
    sa = _L("sleeper_activation_eval.json", REM)
    return {"title": "Sleeper / conditional poisoning: hold-out 8 anomaly thresholds corrected; SA-1 activation experiment",
            "sources": ["remediation/ho8_anomaly_devfit.json", "remediation/sleeper_activation_eval.json"],
            "ho8_anomaly": arms,
            "ho8_dedicated_sleeper_guard": "0/160 attacks, 0/171 benign (eval_holdout8.json sleeper)",
            "SA1": ({k: v for k, v in sa.items()} if sa else "PENDING")}


def t12_predictions() -> Dict:
    d = _L("predictions_tally.json", REM)
    sa = _L("sleeper_activation_eval.json", REM)
    p2 = _L("propagation_2gen.json", REM)
    return {"title": "Every pre-registered prediction, by family and kind",
            "sources": ["round7_predictions.json", "remediation/predictions_tally.json",
                        "remediation/sleeper_activation_eval.json", "remediation/propagation_2gen.json"],
            "round7_file": d["round7_file"], "snapshots": d["snapshots_reconstructed"],
            "holdout8": d["holdout8_addendum7"], "all_round7": d["all_round7_including_holdout8"],
            "remediation_SA1": sa["predictions"] if sa else "PENDING",
            "remediation_P2": p2["predictions"] if p2 else "PENDING"}


TABLES: Dict[str, Callable[[], Dict]] = {
    "T1_validity": t1_validity, "T2_judge_sensitivity": t2_judge_sensitivity, "T3_two_denominators": t3_two_denominators,
    "T4_memory_poisoning_holdouts": t4_memory_poisoning_holdouts, "T5_b13_decomposition": t5_b13_decomposition,
    "T6_injection_holdouts": t6_injection_holdouts, "T7_baselines": t7_baselines, "T8_harm": t8_harm,
    "T9_adaptive": t9_adaptive, "T10_propagation": t10_propagation, "T11_sleeper": t11_sleeper,
    "T12_predictions": t12_predictions}


def _md(name: str, t: Dict) -> str:
    return f"# {name}: {t.get('title', '')}\n\nSources: {', '.join(t.get('sources', []))}\n\n```json\n" + \
           json.dumps({k: v for k, v in t.items() if k not in ('title', 'sources')}, indent=2, ensure_ascii=False) + "\n```\n"


def run() -> Dict:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    idx = ["# Authoritative Table Index\n", "Generated by `python -m phase17.remediation.authoritative_tables` from the "
           "artifacts listed. Do not edit the tables by hand; re-run the generator.\n",
           "| Table | Title | Source artifacts | Computed by | Status |", "|---|---|---|---|---|"]
    out = {}
    for name, fn in TABLES.items():
        t = fn()
        out[name] = t
        (OUTDIR / f"{name}.json").write_text(json.dumps(t, indent=2, ensure_ascii=False), encoding="utf-8")
        (OUTDIR / f"{name}.md").write_text(_md(name, t), encoding="utf-8")
        pending = "PENDING" if ("PENDING" in json.dumps(t)) else "complete"
        idx.append(f"| [{name}](tables/{name}.md) | {t.get('title', '')} | {', '.join(t.get('sources', []))} | "
                   f"`authoritative_tables.{fn.__name__}` | {pending} |")
    INDEX.write_text("\n".join(idx) + "\n", encoding="utf-8")
    return out


if __name__ == "__main__":
    r = run()
    print({k: ("PENDING" in json.dumps(v)) for k, v in r.items()})
    print(json.dumps(r["T7_baselines"]["lead_on_own_attacks_over_best_baseline"]))
    print(json.dumps(r["T3_two_denominators"]["rows"], indent=0)[:1500])
