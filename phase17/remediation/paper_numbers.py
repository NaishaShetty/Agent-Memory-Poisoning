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
    return m


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
