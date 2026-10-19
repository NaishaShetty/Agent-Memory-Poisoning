"""Generate `paper/numbers.tex` and the paper's LaTeX tables from `results/tables` (review P0-7, D6).

The manuscript contains no typed numbers: every figure is a macro defined here from an authoritative table.
Values whose source artifact does not exist yet are emitted as a visible \\textbf{[PENDING]} so the paper
can never silently carry a placeholder; `test_remediation.test_paper_has_no_pending_or_undefined_macros`
fails the build while any remains. Prose macros for the two pre-registered experiments are generated from
their scored predictions, so the wording follows the outcome rather than an expectation.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict

ROOT = Path(__file__).resolve().parents[2]
TAB = ROOT / "results" / "tables"
PAPER = ROOT / "paper"
PENDING = r"\textbf{[PENDING]}"


def _t(name: str):
    p = TAB / f"{name}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _L(rel: str):
    p = ROOT / "phase17" / "data" / rel
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def pc(x: float, d: int = 1) -> str:
    return f"{100 * x:.{d}f}\\%"


def frac(d: Dict) -> str:
    return f"{d['k']}/{d['n']} ({pc(d['rate'])})"


def _num(s: str) -> str:
    return f"{int(s):,}".replace(",", "{,}")


def macros() -> Dict[str, str]:
    from phase17.stats import rate_with_ci

    m: Dict[str, str] = {}
    T1 = _t("T1_validity")
    m["AuditN"] = _num(T1["total"]["n"])
    m["AuditRate"] = pc(T1["total"]["rate"])
    m["AuditOwn"] = pc(T1["split"]["own"]["rate"])
    m["AuditExt"] = pc(T1["split"]["external"]["rate"])
    m["AuditOwnN"] = _num(T1["split"]["own"]["n"])
    m["AuditExtN"] = _num(T1["split"]["external"]["n"])
    g = next(r for r in T1["rows"] if r["population"] == "exttest_gandalf")
    m["GandalfShare"] = pc(g["n"] / T1["total"]["n"], 0)

    js = _L("remediation/validity_judge_sensitivity.json")
    for key, grp in (("All", "ALL"), ("Own", "own"), ("Ext", "external")):
        if js:
            r = js["results"][grp]
            m[f"JS{key}Czero"] = pc(r["fitted_probe_working_C0"]["rate"])
            m[f"JS{key}Vote"] = pc(r["fitted_probe_working_vote"]["rate"])
        else:
            m[f"JS{key}Czero"] = m[f"JS{key}Vote"] = PENDING
    if js:
        a = js["results"]["ALL"]
        m["JSFlips"] = f"{a['working_only_C0'] + a['working_only_vote']}/{a['n']}"
        m["JSFlipsPct"] = pc((a['working_only_C0'] + a['working_only_vote']) / a['n'], 0)
        m["JSBaseCzero"] = pc(a["task_alone_base_rate_C0"]["rate"])
        m["JSBaseVote"] = pc(a["task_alone_base_rate_vote"]["rate"])
    else:
        m["JSFlips"] = m["JSFlipsPct"] = m["JSBaseCzero"] = m["JSBaseVote"] = PENDING

    T3 = _t("T3_two_denominators")
    shifts = [abs(v["shift_points"]) for r in T3["rows"] for k, v in r.items() if k.startswith("B")]
    m["TwoDenMaxShift"] = f"{max(shifts):.0f}"

    T4 = _t("T4_memory_poisoning_holdouts")
    rows = {r["holdout"]: r for r in T4["rows"]}
    word = {"holdout4": "four", "holdout7": "seven", "holdout8": "eight"}
    fprs = []
    for h, w in word.items():
        c = rows[h]["configs"]
        m[f"HO{w}Bthirteen"] = re.sub(r"\((.*?)%\)", r"(\1\\%)", c["B13"]["recall"])
        m[f"HO{w}Bfourteen"] = re.sub(r"\((.*?)%\)", r"(\1\\%)", c["B14"]["recall"])
        k, n = map(int, c["B13"]["fpr_untrusted"].split(" ")[0].split("/"))
        fprs.append(k / n)
    m["BthirteenFPRmin"], m["BthirteenFPRmax"] = pc(min(fprs)), pc(max(fprs))

    T6 = _t("T6_injection_holdouts")
    for r in T6["rows"]:
        w = {"holdout5": "five", "holdout6": "six"}[r["holdout"]]
        c = r["configs"]["B17"]
        m[f"HO{w}Bseventeen"] = c["recall"].split("(")[1].rstrip(")").replace("%", "\\%")
        m[f"HO{w}BseventeenFPR"] = c["matched_benign_fpr"].split("(")[1].rstrip(")").replace("%", "\\%")

    T7 = _t("T7_baselines")
    m["LeadBthirteen"] = f"{T7['lead_on_own_attacks_over_best_baseline']['points']['B13']}"
    m["LeadBseventeen"] = f"{T7['lead_on_own_attacks_over_best_baseline']['points']['B17']}"

    T8 = _t("T8_harm")
    h = _L("harm_study_v2.json")["retrieved_naturally"]
    m["HarmNatRetr"] = f"{h['k']}/{h['n']} ({pc(h['rate'])})"
    runs = T8["noise"]["runs_k"]
    m["HarmNoiseRange"] = f"{100 * (max(runs) - min(runs)) / T8['noise']['n']:.1f}"
    j0 = _L("harm_rejudged.json")["by_judge"]["J0_current"]["harm_undefended"]["k"]
    m["HarmJudgeOnly"] = str(abs(j0 - runs[2]))          # rep1 judged in noise_repeats vs in harm_rejudged

    T9 = _t("T9_adaptive")
    lb = T9["ledger_plus_B13"]
    m["AdaptCorr"] = f"{lb['control']['k']}/{lb['control']['n']}"
    m["AdaptLedger"] = f"{lb['ledger']['k']}/{lb['ledger']['n']}"
    cfg = _L("eval_ledger_radius_sweep.json")
    pt = next(c for c in cfg["curve"] if abs(c["radius"] - 0.95) < 1e-9)
    m["LedgerBlast"] = pc(pt["ledger_poisoning_blast_radius"])

    T10 = _t("T10_propagation")
    g1 = T10["gen1_dev"]
    m["LaunderOne"] = g1["harm_on_b13_excluded"]["B13+D"].split(" ")[0]
    m["GenOneSemCarry"] = g1["withheld_carrying"]["semantic"].replace("%", "\\%")
    m["GenOneSemNonCarry"] = g1["withheld_NON_carrying_(legitimate_derived_lost)"]["semantic"].replace("%", "\\%")
    m["GenOneMissed"] = str(g1["b13_missed_containment_cannot_act"])

    fx = _L("remediation/ho8_anomaly_devfit.json")["arms"]
    s = fx["shipped_committed_centroids"]["p90"]["anomaly"]
    m["AnomShippedFP"] = f"{s['benign_fpr']['k']}/{s['benign_fpr']['n']} ({pc(s['benign_fpr']['rate'], 0)})"
    m["AnomShippedAtk"] = f"{s['recall']['k']}/{s['recall']['n']}"
    lf = fx["owner_adaptive_leakfree"]["p99"]["anomaly"]
    m["AnomLeakFree"] = (f"{lf['recall']['k']}/{lf['recall']['n']} attacks at {lf['benign_fpr']['k']}/"
                         f"{lf['benign_fpr']['n']} benign")

    pt_ = _t("T12_predictions")
    a = pt_["all_round7"]
    m["PredScored"], m["PredHeld"] = str(a["scored"]), str(a["held"])
    m["PredIntervalHeld"] = f"{a['by_kind']['interval']['held']}/{a['by_kind']['interval']['scored']}"
    m["PredDirectionalHeld"] = f"{a['by_kind']['directional']['held']}/{a['by_kind']['directional']['scored']}"

    sa, p2 = _L("remediation/sleeper_activation_eval.json"), _L("remediation/propagation_2gen.json")
    m.update(_remediation_prose(sa, p2))
    m.update(_gapclosure())
    m.update(_targeted())
    return m


def _targeted() -> Dict[str, str]:
    """Macros for the 2026-10-13 targeted phase (B13 owner LOO; validity three-condition design)."""
    out: Dict[str, str] = {}
    lo = _L("remediation/b13_owner_loo.json")
    if lo:
        P = lo["evidence_conditions"]
        c = P["correct"]["pooled"]
        f = lambda d: f"{d['k']}/{d['n']}"  # noqa: E731
        ci = lambda b: f"[{100 * b['ci95'][0]:.1f}, {100 * b['ci95'][1]:.1f}]"  # noqa: E731
        thr = [r["calibration"]["A-ship"][0] for r in lo["owners"].values()]
        out["LooOwners"] = str(len(lo["owners"]))
        out["LooDet"] = f"{f(c['A-ship']['detection'])} ({pc(c['A-ship']['detection']['k'] / c['A-ship']['detection']['n'])}, owner-bootstrap {ci(c['A-ship']['detection']['owner_bootstrap'])})"
        out["LooBen"] = f"{f(c['A-ship']['benign_exclusion'])} ({pc(c['A-ship']['benign_exclusion']['k'] / c['A-ship']['benign_exclusion']['n'], 2)}, {ci(c['A-ship']['benign_exclusion']['owner_bootstrap'])})"
        out["LooBenMax"] = pc(c["A-ship"]["per_owner_benign_exclusion_range"][1], 1)
        out["LooDetRange"] = f"{pc(c['A-ship']['per_owner_detection_range'][0], 0)}--{pc(c['A-ship']['per_owner_detection_range'][1], 0)}"
        out["LooThrRatio"] = f"{max(thr) / min(thr):.2f}"
        out["LooFrozenDet"] = f(c["A-frozen"]["detection"])
        out["LooNomDet"] = f(c["A-nom"]["detection"])
        out["LooNomBen"] = f(c["A-nom"]["benign_exclusion"])
        out["LooWrongBen"] = f(P["wrong"]["pooled"]["A-ship"]["benign_exclusion"])
        out["LooTruncBen"] = f(P["trunc10"]["pooled"]["A-ship"]["benign_exclusion"])
        out["LooPolicyBDet"] = f(c["B"]["detection"])
        out["LooPolicyBBen"] = f(c["B"]["benign_exclusion"])
        out["LooBtwelveDet"] = f(c["C-B12"]["detection"])
        sg = lo["single_owner_thresholds"]
        s1 = [v["A-ship"][0] for v in sg.values()]
        out["LooSingleRatio"] = f"{max(s1) / min(s1):.1f}"
        h4 = lo["holdouts"]["holdout4"]["conditions"]["correct"]
        out["LooHOfour"] = f"{h4['atk']['A-ship']}/{lo['holdouts']['holdout4']['n_attack']} at {h4['ben']['A-ship']}/{lo['holdouts']['holdout4']['n_benign']} benign"
    u2 = _L("remediation/b13_loo_utility.json")
    if u2:
        b = u2["by_policy"]
        out["LooUtil"] = (f"{b['none']['correct']['k']}, {b['A-ship']['correct']['k']}, {b['A-nom']['correct']['k']} and "
                          f"{b['B']['correct']['k']} of {u2['n_sampled']}")
    vf = _L("remediation/validity_final.json")
    if vf and vf.get("none_arm_complete"):
        tc = vf["three_conditions"]
        for pk, p in (("Fit", "fitted"), ("NL", "nonleading")):
            for jk, j in (("Czero", "C0"), ("Vote", "vote")):
                r = tc[f"{p}|{j}"]
                out[f"Vf{pk}{jk}"] = (f"{r['comply_none']['k']}/{r['comply_clean']['k']}/{r['comply_poisoned']['k']}")
                m_ = r["memory_attributable(poisoned-clean)"]
                out[f"VfNet{pk}{jk}"] = (f"+{m_['diff_points']} [{m_['population_cluster_bootstrap_ci95_points'][0]}, "
                                         f"{m_['population_cluster_bootstrap_ci95_points'][1]}]")
        n = vf["net_effect_2628"]["own"]
        out["NetOwnClust"] = (f"[{n['C0']['population_cluster_bootstrap_ci95_points'][0]}, "
                              f"{n['C0']['population_cluster_bootstrap_ci95_points'][1]}]")
    return out


def _gapclosure() -> Dict[str, str]:
    """Macros for the 2026-10-13 gap-closure analyses (validity, adjudication, probe, corroboration, SA-2, Mem0)."""
    out: Dict[str, str] = {}
    va = _L("remediation/validity_adjusted.json")
    if va:
        for key, g in (("All", "ALL"), ("Own", "own"), ("Ext", "external")):
            for jk, j in (("Czero", "C0"), ("Vote", "vote")):
                x = va["memory_attributable"][g][j]
                out[f"Net{key}{jk}"] = f"+{x['net_points']} [{x['ci95_points'][0]}, {x['ci95_points'][1]}]"
        pops = [p for p in va["memory_attributable"] if p not in ("ALL", "own", "external")]
        out["AdmitCzero"] = f"{sum(va['memory_attributable'][p]['admissible_C0'] for p in pops)} of {len(pops)}"
        out["AdmitVote"] = f"{sum(va['memory_attributable'][p]['admissible_vote'] for p in pops)} of {len(pops)}"
    adj = _L("remediation/judge_adjudication.json")
    if adj:
        d = adj["disagreement_items"]
        out["AdjSplit"] = f"{d['with_C0']}/{d['with_vote']}"
        out["AdjKappa"] = f"{adj['kappa_adjudicator_vs_C0']}"
    pr = _L("remediation/probe_robustness.json")
    if pr:
        c = pr["by_judge"]["C0"]
        out["PrBaseNL"] = f"{c['nonleading']['base_rate']['k']}/{pr['n']}"
        out["PrBaseFit"] = f"{c['fitted']['base_rate']['k']}/{pr['n']}"
        out["PrWorkNL"] = f"{c['nonleading']['working']['k']}/{pr['n']}"
        out["PrWorkFit"] = f"{c['fitted']['working']['k']}/{pr['n']}"
        out["PrNetNL"] = f"+{c['nonleading']['net_effect_points']}"
        out["PrNetFit"] = f"+{c['fitted']['net_effect_points']}"
        out["PrAgree"] = pc(c["item_agreement_working"], 0)
    cr = _L("remediation/corroboration_robustness.json")
    if cr:
        s4, s8 = cr["sets"]["holdout4"]["arms"], cr["sets"]["holdout8"]["arms"]
        w = lambda a: f"{a['corroboration_recall']['k']}/{a['corroboration_recall']['n']} attacks vs {a['corroboration_benign_fpr']['k']}/{a['corroboration_benign_fpr']['n']} benign"  # noqa: E731
        out["HOfourWrong"] = w(s4["wrong_owner|frozen"])
        out["HOeightWrong"] = w(s8["wrong_owner|frozen"])
        dd = lambda a: f"{a['B13_recall']['k']}/{a['B13_recall']['n']} at {a['B13_benign_fpr']['k']}/{a['B13_benign_fpr']['n']} benign"  # noqa: E731
        out["HOfourDisjoint"] = dd(s4["full|disjoint"])
        out["HOeightDisjoint"] = dd(s8["full|disjoint"])
    s2 = _L("remediation/sa2_eval.json")
    if s2:
        R = s2["by_judge"]["C0"]
        A, B, D = R["atk"], R["ben"], R["discrimination"]
        out["SAtwoBtwelve"] = f"{D['B12']['attack_excluded']}/60"
        out["SAtwoBthirteen"] = f"{D['B13_untrusted']['attack_excluded']}/60"
        f = lambda x: f"{x['k']}/{x['n']}"  # noqa: E731
        st = {p["id"]: p["status"] for p in s2["predictions"]}
        out["SAtwoBody"] = (
            f"The note was retrieved by its trigger in {f(A['retrieved_on_trigger'])} attacks and by the unrelated message in "
            f"{f(A['retrieved_on_non_trigger'])}; attacks activated on {f(A['activation_on_trigger'])} triggers and "
            f"{f(A['activation_on_non_trigger'])} unrelated messages (S2-4a~{st['S2-4a']}, S2-4b~{st['S2-4b']}; vote judge "
            f"{f(s2['by_judge']['vote']['atk']['activation_on_trigger'])} on triggers). Content-only B12 excluded "
            f"{D['B12']['attack_excluded']}/60 attacks and {D['B12']['lookalike_excluded']}/60 benign rules (S2-1~{st['S2-1']}, "
            f"S2-2~{st['S2-2']}); deberta {A['defended']['deberta_pi_v2@dev']['excluded']['k']}/60; the Phase~8 sleeper guard "
            f"{A['defended']['sleeper_guard_phase8']['excluded']['k']}/60 (S2-5~{st['S2-5']}); the development-fitted anomaly signal "
            f"flagged {A['defended']['anomaly_devfit_p90']['excluded']['k']}/60 attacks and "
            f"{B['defended']['anomaly_devfit_p90']['excluded']['k']}/60 benign rules. B13's corroboration excluded "
            f"{D['B13_untrusted']['attack_excluded']}/60 attacks and {D['B13_untrusted']['lookalike_excluded']}/60 benign rules "
            f"(S2-3~{st['S2-3']}, one-sided Fisher $p$={D['B13_untrusted']['fisher_p_greater']:.1e}) and reduced trigger activation from "
            f"{f(A['activation_on_trigger'])} to {f(A['defended']['B13_untrusted']['activation_on_trigger'])}. Because the benign "
            f"rules were written to reflect what the owner said, corroboration's clean separation is partly by construction; "
            f"the robust finding is the negative one: no content, injection or sleeper-specific detector recognised implicit "
            f"conditional poisoning, and only owner-specific evidence did.")
    mem = _L("remediation/mem0_pipeline_eval.json")
    if mem:
        from phase17.remediation.paper_prose import mem_prose
        out.update(mem_prose(mem))
        if s2 and va:
            A = mem["MEM1_ho4"]["attacks_document"]
            S = mem["MEM2_sa1"]["atk_document"]
            D2 = s2["by_judge"]["C0"]["discrimination"]
            out["Conclusion"] = (
                f"RQ1: memory-poisoning attacks causally change a 7B agent's behaviour (net {out['NetOwnCzero']} points), "
                "but which instances count as working depends on the probe and judge; defense rankings do not. "
                "RQ2: provenance-aware admission works through corroboration against the owner's own conversation, not "
                "through channel trust; it survives a real memory system's extraction (Mem0 stored the poisoned claim in "
                f"{A['carries']['k']}/157 cases and corroboration still excluded {A['excl_B13']['k']}/157 at "
                f"{mem['MEM1_ho4']['benign_document']['excl_B13']['k']}/262 benign), leaves user-channel poisoning untouched, and "
                "its operating point depends on the calibration owners. Natural retrieval, not admission, was the first "
                f"filter: only {A['retrieved']['k']}/157 stored poisons reached the agent for their task. RQ3: consolidation "
                "launders excluded poisons and lineage-taint containment decays from the first to the second generation, "
                "holding only through inherited state. RQ4: conditional memories are dormant and trigger-activated; content "
                f"detection catches explicit rules in raw form but only {S['excl_B12']['k']}/60 once Mem0 has reworded them "
                f"and none of the implicit rules ({D2['B12']['attack_excluded']}/60), and no sleeper-specific detector works. "
                "None of the three gaps is solved; the evidence supports evaluating defenses on attacks shown to work, "
                "through real memory pipelines, with benign lookalikes and owner-specific evidence.")
    else:
        out["MemAbstract"] = out["MemBody"] = PENDING
    # Holm over the gap-closure significance family (pre-registered set; missing results stay out)
    fam = []
    for src, key in (("remediation/mem0_pipeline_eval.json", "predictions"), ("remediation/sa2_eval.json", "predictions")):
        d = _L(src)
        for p in (d or {}).get(key, []):
            if p.get("kind") == "significance" and p.get("p") is not None:
                fam.append((p["id"], p["p"]))
    if fam:
        from phase17.remediation.paper_prose import _holm, _p
        out["GapHolm"] = "; ".join(f"{i} {_p(a)}" for i, _, a in _holm(fam))
    else:
        out["GapHolm"] = PENDING
    return out


def _remediation_prose(sa, p2) -> Dict[str, str]:
    """Prose for SA-1 / P2, generated from the scored outcome (filled in after the runs; PENDING before)."""
    out = {k: PENDING for k in ("SAoneAbstract", "SAoneBody", "PtwoAbstract", "PtwoBody", "RemHolm", "Conclusion")}
    try:
        from phase17.remediation.paper_prose import prose
    except ImportError:
        return out
    if sa and p2:
        out.update(prose(sa, p2))
    return out


def tables() -> Dict[str, str]:
    T3 = _t("T3_two_denominators")
    lines = [r"\begin{table}[t]\centering\caption{Recall on the full population $\rightarrow$ the causal working subset, per single-use hold-out.}\label{tab:twoden}",
             r"\footnotesize\begin{tabular}{lrrrrr}\toprule Hold-out (working/all) & B12 & B13 & B14 & B17 & B18\\\midrule"]
    for r in T3["rows"]:
        cells = []
        for c in ("B12", "B13", "B14", "B17", "B18"):
            v = r[c]
            f = re.search(r"\(([\d.]+)%\)", v["full"]).group(1)
            w = re.search(r"\(([\d.]+)%\)", v["working"]).group(1)
            cells.append(f"{float(f):.0f}$\\rightarrow${float(w):.0f}")
        lines.append(f"{r['holdout'].replace('holdout', 'HO')} ({r['working']}) & " + " & ".join(cells) + r"\\")
    lines += [r"\bottomrule\end{tabular}\end{table}"]
    two = "\n".join(lines)

    T4 = _t("T4_memory_poisoning_holdouts")
    lines = [r"\begin{table}[t]\centering\caption{Memory-poisoning hold-outs, each scored once (B13 with the owner's conversation as evidence). Recall / benign exclusion on the untrusted channel / on the user channel.}\label{tab:mp}",
             r"\footnotesize\begin{tabular}{llll}\toprule & HO4 & HO7 & HO8\\\midrule"]
    R = {r["holdout"]: r for r in T4["rows"]}
    pctof = lambda s: re.search(r"\(([\d.]+)%\)", s).group(1)  # noqa: E731
    for c in ("B12", "B13", "B14", "B17", "B18"):
        cells = []
        for h in ("holdout4", "holdout7", "holdout8"):
            v = R[h]["configs"][c]
            cells.append(f"{pctof(v['recall'])} / {pctof(v['fpr_untrusted'])} / {pctof(v['fpr_user_turn'])}")
        lines.append(f"{c} & " + " & ".join(cells) + r"\\")
    lines.append(r"\midrule B13 vs B14 & " + " & ".join(R[h]["B13_vs_B14"].replace("+", r"$+$").replace("-", r"$-$")
                                                       for h in ("holdout4", "holdout7", "holdout8")) + r"\\")
    lines += [r"\bottomrule\end{tabular}\end{table}"]
    mp = "\n".join(lines)

    D = json.loads((ROOT / "phase17" / "data" / "remediation" / "b13_decomposition.json").read_text(encoding="utf-8"))
    lines = [r"\begin{table}[t]\centering\caption{Decomposition of B13 (stored decisions, reproduced item for item). Attacks excluded / untrusted-channel benign excluded.}\label{tab:decomp}",
             r"\footnotesize\begin{tabular}{lccc}\toprule & HO4 & HO7 & HO8\\\midrule"]
    names = {"B12_stored": "B12 (content only)", "channel_plus_rules": "B13 without corroboration",
             "corroboration_only": "Corroboration alone", "B13": "B13"}
    H = ("holdout4", "holdout7", "holdout8")
    for k, lab in names.items():
        cells = []
        for h in H:
            a = D["holdouts"][h]["arms"][k]
            cells.append(f"{a['recall']['k']}/{a['recall']['n']} / {a['benign_fpr_untrusted']['k']}/{a['benign_fpr_untrusted']['n']}")
        lines.append(f"{lab} & " + " & ".join(cells) + r"\\")
    cells = [f"0/{D['holdouts'][h]['n_attacks']} ({D['holdouts'][h]['arms']['user_channel_poisoning']['flagged_but_admitted']['k']} flagged)" for h in H]
    lines.append(r"\midrule Attacks on user channel & " + " & ".join(cells) + r"\\")
    lines += [r"\bottomrule\end{tabular}\end{table}"]
    return {"tab_twoden.tex": two, "tab_mp.tex": mp, "tab_decomp.tex": "\n".join(lines)}


def run() -> Dict:
    PAPER.mkdir(exist_ok=True)
    m = macros()
    body = ["% GENERATED by phase17/remediation/paper_numbers.py from results/tables -- do not edit by hand."]
    for k, v in sorted(m.items()):
        body.append(f"\\newcommand{{\\{k}}}{{{v}\\xspace}}" if "PENDING" not in v and len(v) < 60 else f"\\newcommand{{\\{k}}}{{{v}}}")
    (PAPER / "numbers.tex").write_text("\n".join(body) + "\n", encoding="utf-8")
    for name, tex in tables().items():
        (PAPER / name).write_text("% GENERATED by phase17/remediation/paper_numbers.py\n" + tex + "\n", encoding="utf-8")
    return m


if __name__ == "__main__":
    m = run()
    print(len(m), "macros;", sum("PENDING" in v for v in m.values()), "pending:",
          [k for k, v in m.items() if "PENDING" in v])
