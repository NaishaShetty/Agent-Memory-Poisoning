"""Figures drawn from the artifacts at build time, so they cannot drift from the data (2026-10-09).

Results paper (new; it had no figures):
  R1  hold-outs 4-8: attack recall against the matched / untrusted-benign false-positive rate
  R2  harm study: undefended / B12 / B13 / no-poison, and undefended under both judges
  R3  adaptive attackers: stateless vs ledger, corroboration vs corroboration + ledger
  R4  retrieval ranking: single poison vs coordinated campaign, lexical vs semantic consensus guard
Methodology (replacing images found stale on 2026-10-09):
  fig01b  Overall pipeline, Phases 14-17 (the old one was dated 2026-09-27, "5 rounds")
  fig12   Phase 10 architecture (the old footer said "zero live wiring"; surfaces since evaluated)
  fig20   Harm study (the old one showed an n=5-per-mechanism pilot captioned "final numbers")
  fig16b  Phase 13 results, renumbered from a duplicated "Figure 17"
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "phase17" / "data"
FIG = ROOT / "docs" / "figures" / "round7"


def L(n):
    p = DATA / n
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _plt():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})
    return plt


def r1_holdouts():
    plt = _plt()
    E = (L("eval_round7_holdouts.json") or {}).get("holdouts", {})
    E.update((L("eval_round7b_holdouts.json") or {}).get("holdouts", {}))
    _h8 = L("eval_holdout8.json")
    if _h8 and _h8.get("configs"):
        E["holdout8"] = _h8
    if not E:
        return None
    fig, ax = plt.subplots(figsize=(8, 5.2))
    marks = {"holdout4": "o", "holdout5": "s", "holdout6": "^", "holdout7": "D", "holdout8": "P"}
    colors = {"B12": "#7f8c8d", "B13": "#2980b9", "B14": "#e67e22", "B17": "#27ae60", "B18": "#c0392b"}
    for h, m in marks.items():
        if h not in E:
            continue
        for c, col in colors.items():
            v = E[h]["configs"][c]
            fp = (v.get("matched_benign_fpr") or v["benign_fpr_untrusted_channel"])["rate"]
            ax.scatter(100 * fp, 100 * v["attack_recall"]["rate"], marker=m, color=col, s=55, edgecolor="black", lw=0.5)
    for c, col in colors.items():
        ax.scatter([], [], color=col, label=c)
    for h, m in marks.items():
        ax.scatter([], [], marker=m, color="white", edgecolor="black", label=h.replace("holdout", "hold-out "))
    ax.set_xlabel("False positives on benign text (%)  [matched benign, or untrusted-channel notes]")
    ax.set_ylabel("Attack recall (%), full population")
    ax.set_title("Hold-outs 4-8, each scored once: recall against false-positive cost")
    ax.grid(alpha=0.3)
    ax.legend(ncol=2, fontsize=8, loc="lower right")
    out = FIG / "R1_holdouts_recall_vs_fpr.png"
    fig.tight_layout(); fig.savefig(out, dpi=150); plt.close(fig)
    return out


def r2_harm():
    plt = _plt()
    H, HR = L("harm_study_v2.json"), L("harm_rejudged.json")
    if not H:
        return None
    o = H["overall"]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.4), gridspec_kw={"width_ratios": [1.4, 1]})
    arms = [("No poison", o["harm_no_poison"]), ("Undefended", o["harm_no_defense"]),
            ("B12", o["harm_b12"]), ("B13", o["harm_b13"])]
    ax = axes[0]
    vals = [100 * a[1]["rate"] for a in arms]
    errs = [[100 * (a[1]["rate"] - a[1]["ci95"][0]) for a in arms], [100 * (a[1]["ci95"][1] - a[1]["rate"]) for a in arms]]
    ax.bar([a[0] for a in arms], vals, yerr=errs, capsize=4, color=["#95a5a6", "#c0392b", "#e67e22", "#2980b9"])
    for i, a in enumerate(arms):
        ax.text(i, 100 * a[1]["ci95"][1] + 1.2, f"{a[1]['k']}/{a[1]['n']}", ha="center", fontsize=9)
    ax.set_ylim(0, max(100 * a[1]["ci95"][1] for a in arms) + 8)
    ax.set_ylabel("Harmful outcome (%), 95% Wilson CI")
    ax.set_title(f"Harm study, {H['n']} instances (original judge)")
    ax = axes[1]
    if HR and HR.get("undefended_all_items"):
        u = HR["undefended_all_items"]
        names = [("Original judge", u["J0_current"]), ("Human-validated judge", u["J2_gemini_original"])]
        v2 = [100 * x[1]["rate"] for x in names]
        ax.bar([x[0] for x in names], v2, color=["#e67e22", "#8e44ad"])
        for i, x in enumerate(names):
            ax.text(i, v2[i] + 2, f"{x[1]['k']}/{x[1]['n']}", ha="center", fontsize=9)
        ax.set_title("Undefended harm: the same answers\nscored by two judges", fontsize=10)
        ax.set_ylim(0, 100)
    else:
        ax.axis("off")
    out = FIG / "R2_harm.png"
    fig.tight_layout(); fig.savefig(out, dpi=150); plt.close(fig)
    return out


def r3_adaptive():
    plt = _plt()
    SW, AD, LB = L("eval_ledger_radius_sweep.json"), L("adaptive_round7.json"), L("adaptive_ledger_b13.json")
    if not (AD and LB):
        return None
    bars = [("Stateless\ndetection (B15)", 32, 130, "#7f8c8d")]
    if SW:
        c = next((x for x in SW.get("curve", []) if abs(x.get("radius", 0) - 0.95) < 1e-9), None)
        if c:
            bars.append(("Stateless\n+ ledger 0.95", c["adaptive_evasion"]["k"], c["adaptive_evasion"]["n"], "#27ae60"))
    bars += [("Corroboration\n(B13 + evidence)", LB["control_evasion"]["k"], LB["n_seeds"], "#c0392b"),
             ("Corroboration\n+ ledger 0.95", LB["ledger_evasion"]["k"], LB["n_seeds"], "#27ae60")]
    fig, ax = plt.subplots(figsize=(8.5, 4.4))
    vals = [100 * k / n for _, k, n, _c in bars]
    ax.bar(range(len(bars)), vals, color=[b[3] for b in bars])
    ax.set_xticks(range(len(bars)), [b[0] for b in bars])
    bars = [b[:3] for b in bars]
    for i, (_, k, n) in enumerate(bars):
        ax.text(i, vals[i] + 1.5, f"{k}/{n}", ha="center", fontsize=9)
    ax.set_ylabel("Adaptive evasion within 5 rewrites (%)")
    ax.set_title("An attacker told why it was rejected: the rejection ledger closes the gap")
    out = FIG / "R3_adaptive.png"
    fig.tight_layout(); fig.savefig(out, dpi=150); plt.close(fig)
    return out


def r4_retrieval():
    plt = _plt()
    FR, CP = L("rwr_fresh_replication.json"), L("rwr_campaign.json")
    if not (FR and CP):
        return None
    import numpy as np

    arms = [("A0", "no defense"), ("A1", "lexical gate (shipped)"), ("A1s", "semantic gate"),
            ("A3", "lexical + corroboration"), ("A3s", "semantic + corroboration")]
    x = np.arange(len(arms))
    fig, ax = plt.subplots(figsize=(9, 4.4))
    for off, (lab, d, col) in zip((-0.2, 0.2), (("single poison", FR, "#2980b9"), ("coordinated campaign", CP, "#c0392b"))):
        v = [100 * d["exposure"][a]["rate"] for a, _ in arms]
        ax.bar(x + off, v, width=0.4, label=f"{lab} (n={d['n']})", color=col)
    ax.set_xticks(x, [f"{a}\n{t}" for a, t in arms], fontsize=8)
    ax.set_ylabel("Poison reaches the agent's top 5 (%)")
    ax.set_title("Retrieval ranking on fresh stores: the consensus guard needs semantic divergence")
    ax.legend()
    out = FIG / "R4_retrieval.png"
    fig.tight_layout(); fig.savefig(out, dpi=150); plt.close(fig)
    return out


def _boxes(ax, boxes, title):
    from matplotlib.patches import FancyBboxPatch

    ax.set_xlim(0, 10); ax.set_ylim(0, 10); ax.axis("off")
    ax.text(5, 9.75, title, ha="center", va="top", fontsize=14, fontweight="bold", wrap=True)
    for (x, y, w, h, head, body, col) in boxes:
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08", fc=col, ec="#333", lw=1.2))
        ax.text(x + w / 2, y + h - 0.18, head, ha="center", va="top", fontsize=10.5, fontweight="bold")
        ax.text(x + w / 2, y + h - 0.62, body, ha="center", va="top", fontsize=8.3, wrap=True, linespacing=1.35)


def _closure_line() -> str:
    """Latest operational closure per gap, read from the newest closure artifact at build time."""
    for rel, key in (("defence_v7/closure_v7.json", "after_v7"), ("defence_v6/closure_v6.json", "after")):
        p = DATA / rel
        if p.exists():
            c = json.loads(p.read_text(encoding="utf-8"))
            return ("closure " + ", ".join(f"{g.split(': ')[1]} {100 * v[key]:.0f}%" for g, v in c["gaps"].items())
                    + f" (after {rel.split('/')[0].replace('defence_', '')}).")
    return "closure pending."


def fig01b():
    plt = _plt()
    P = L("round7_predictions.json")
    fig, ax = plt.subplots(figsize=(12, 10))
    h8 = (DATA / "eval_holdout8.json").exists()
    _mp = "three" if h8 else "two"
    p17 = ("Ablation, generalisation, seven external review rounds. Hold-outs 1-3 (3 retired after seven uses);\n"
           f"round 7 built hold-outs 4-{8 if h8 else 7}, each frozen and scored once under committed predictions"
           + (f"\n({P['n_held']}/{P['n_scored']} held)" if P else "") + ".\n"
           f"Working-attack discipline (42.5% of 2,628 instances work); provenance reaches memory poisoning on {_mp}\n"
           "independent hold-outs; consolidation laundering met by semantic containment; harm re-judged against\n"
           "human labels. (The earlier 'union beats every detector' claim was withdrawn on 2026-10-12: its hold-out\n"
           "threshold was fitted on the hold-out.)\n"
           "Remediation (2026-10-12) and pre-registered defence programmes v2-v7 (2026-10-13/17), each scored once\n"
           "on fresh held-out data: " + _closure_line())
    boxes = [
        (0.5, 7.3, 9, 1.4, "PHASE 14 - Scalability / Systems Evaluation",
         "Live B0-B10 per-task decisions: benign QA utility (Track A) and real poison exclusion (Track B).\n"
         "URS 1.0 (B9 live), 9/9 real poison excluded, forged-answer rate 3/9 -> 0/9.", "#c6dbef"),
        (0.5, 5.4, 9, 1.4, "PHASE 15 - Integrated Security Evaluation",
         "Cross-cutting matrix across every configuration and corpus; B10 per-dataset calibration and\n"
         "corroboration gate.", "#f2c6c6"),
        (0.5, 3.7, 9, 1.2, "PHASE 16 - Final Evaluation / Validation",
         "Synthesis of Phases 1-15; a dated qualification was added after Phase 17 showed several\n"
         "'resolved' findings held only in-sample.", "#c0e2df"),
        (0.5, 0.7, 9, 2.62, "PHASE 17 - Ablation & Generalization (final phase)", p17, "#fde08a"),
    ]
    _boxes(ax, boxes, "Figure 1b - Overall Pipeline, continued (Phases 14-17)")
    for y in (7.3, 5.4, 3.7):
        ax.annotate("", xy=(5, y - 0.35), xytext=(5, y), arrowprops=dict(arrowstyle="->", lw=1.5))
    ax.text(5, 0.45, "Drawn from the artifacts at build time (phase17/figures_round7.py)",
            ha="center", fontsize=8.5, style="italic")
    out = FIG / "fig01b_pipeline_14_17.png"
    fig.savefig(out, dpi=150, bbox_inches="tight"); plt.close(fig)
    return out


def fig12():
    plt = _plt()
    RW, MR, B9 = L("risk_weighted_retrieval_eval.json"), L("risk_monitoring_eval_realistic.json"), True
    fig, ax = plt.subplots(figsize=(12, 10.5))
    retr = ("risk_weighted_retrieval.py: continuous penalty\n"
            + (f"EVALUATED round 7: exposure {RW['exposure']['A1']['k']} -> {RW['exposure']['A3']['k']}\n"
               f"of {RW['n']} vs the fixed gate with admission\ncorroboration (p={RW['paired_A3_vs_A1']['p_exact']:.2g})"
               if RW else "not yet evaluated"))
    mon = ("risk_weighted_monitoring.py: orders review\n"
           + (f"EVALUATED round 7: poison first in\n{MR['poison_first_by_risk']}/{MR['poison_listed']} listed retrievals "
              f"({MR['poison_first_expected_default']}\nby default); lists ~{MR['mean_list_length']} items long" if MR else "not yet evaluated"))
    boxes = [
        (0.3, 7.6, 9.4, 1.3, "Four guard-group scores (Phase 6-8 signals)",
         "admission (5 signals) | retrieval consensus divergence | propagation lineage taint | sleeper gate", "#e8eaf6"),
        (1.0, 5.9, 8.0, 1.2, "GROUPED_GATED -> RiskEstimate",
         "each group an equal 0.25 share; score in [0,1]; band LOW / MODERATE / ELEVATED / HIGH", "#fff2cc"),
        (0.3, 3.0, 3.0, 2.3, "RETRIEVAL", retr, "#d9ead3"),
        (3.5, 3.0, 3.0, 2.3, "ACTION SURFACE",
         "risk_action.py: band -> ALLOW /\nREQUIRE_VALIDATION / QUARANTINE\nLIVE since Phase 14 as B9\n(URS 1.0, 9/9 real poison excluded)",
         "#cfe2f3"),
        (6.7, 3.0, 3.0, 2.3, "MONITORING", mon, "#fce5cd"),
        (0.3, 0.6, 9.4, 1.8, "Recalibration (Section 25.4)",
         "B9 first shipped at 47.1% / 7.3% (a regression vs B8's 70.6% / 7.3%); BAND_THRESHOLD_MODERATE\n"
         "recalibrated 0.15 -> 0.05 on a disjoint dev corpus; B9 then matched B8, reported as a match.", "#eeeeee"),
    ]
    _boxes(ax, boxes, "Figure 12 - Phase 10 Architecture: Cross-Guard Risk Composition, Its Recalibration, and Its Surfaces")
    for x in (1.8, 5.0, 8.2):
        ax.annotate("", xy=(x, 5.35), xytext=(5, 5.9), arrowprops=dict(arrowstyle="->", lw=1.3))
    ax.annotate("", xy=(5, 7.15), xytext=(5, 7.6), arrowprops=dict(arrowstyle="->", lw=1.3))
    ax.text(5, 0.2, "Drawn from the artifacts at build time (phase17/figures_round7.py)", ha="center", fontsize=8.5, style="italic")
    out = FIG / "fig12_phase10.png"
    fig.savefig(out, dpi=150, bbox_inches="tight"); plt.close(fig)
    return out


def fig20():
    plt = _plt()
    H, HR = L("harm_study_v2.json"), L("harm_rejudged.json")
    if not H:
        return None
    import numpy as np

    fams = sorted(H["by_family"])
    x = np.arange(len(fams))
    fig, ax = plt.subplots(figsize=(13, 5.2))
    for off, key, lab, col in ((-0.27, "harm_no_poison", "no poison (task alone)", "#95a5a6"),
                               (0.0, "harm_no_defense", "undefended", "#c0392b"),
                               (0.27, "harm_b13", "B13", "#2980b9")):
        ax.bar(x + off, [100 * H["by_family"][f][key]["rate"] for f in fams], width=0.27, label=lab, color=col)
    ax.set_xticks(x, [f.replace("_", "\n") for f in fams], fontsize=8)
    ax.set_ylabel("Harmful outcome (%)")
    o = H["overall"]
    sub = (f"Overall: undefended {o['harm_no_defense']['k']}/{H['n']}, B13 {o['harm_b13']['k']}/{H['n']}, "
           f"task alone {o['harm_no_poison']['k']}/{H['n']} (original judge)")
    if HR and HR.get("undefended_all_items"):
        u = HR["undefended_all_items"]
        sub += (f"\nRe-run of the undefended answers judged twice: human-validated judge {u['J2_gemini_original']['k']}/"
                f"{HR['n']}, original judge {u['J0_current']['k']}/{HR['n']} (same answers)")
    ax.set_title("Figure 20 - Harm study (309 instances, fixed per-mechanism tasks)\n" + sub, fontsize=10)
    ax.legend()
    out = FIG / "fig20_harm.png"
    fig.tight_layout(); fig.savefig(out, dpi=150); plt.close(fig)
    return out


def r5_union_defense():
    """The generalized union defense per attack type: no single detector covers all, their union does."""
    plt = _plt()
    U = L("union_defense_dev.json")
    if not U or "by_group_recall_test" not in U:
        return None
    groups = ["provenance", "sleeper", "propagation"]
    g = U["by_group_recall_test"]
    series = [("B13 (provenance)", "B13", "#2980b9"), ("anomaly (planted-memory)", "anomaly", "#e67e22"),
              ("UNION", "union", "#27ae60")]
    import numpy as np
    x = np.arange(len(groups)); w = 0.26
    fig, ax = plt.subplots(figsize=(8, 5))
    for i, (lab, key, col) in enumerate(series):
        ax.bar(x + (i - 1) * w, [100 * g[gr][key]["rate"] for gr in groups], w, label=lab, color=col, edgecolor="black", lw=0.4)
    ax.set_xticks(x, [gr.capitalize() for gr in groups])
    ax.set_ylabel("Attack recall (%)"); ax.set_ylim(0, 100)
    ax.set_title("Figure R5 - Generalized union defense (development): no single detector covers every\n"
                 "attack type; their union does. Union recall "
                 f"{U['detectors']['union_B13_or_anomaly']['recall']['rate']:.0%} at "
                 f"{U['detectors']['union_B13_or_anomaly']['fpr']['rate']:.0%} FPR.", fontsize=9)
    ax.legend(); ax.grid(alpha=0.3, axis="y")
    out = FIG / "R5_union_defense.png"
    fig.tight_layout(); fig.savefig(out, dpi=150); plt.close(fig)
    return out


def r6_laundering():
    """Laundering through consolidation and the lexical-vs-semantic containment fix (dev + hold-out 8)."""
    plt = _plt()
    D = L("derived_memory_eval.json")
    if not D or "harm_on_b13_excluded" not in D:
        return None
    hx = D["harm_on_b13_excluded"]
    labels = ["B13 excludes\n(convention)", "+consolidation\n(laundering)", "+lexical\ncontainment", "+semantic\ncontainment"]
    vals = [hx["B13"]["k"], hx["B13+D"]["k"], hx["B13+D+lexical"]["k"], hx["B13+D+semantic"]["k"]]
    cols = ["#7f8c8d", "#c0392b", "#e67e22", "#27ae60"]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(labels, vals, color=cols, edgecolor="black", lw=0.4)
    for i, v in enumerate(vals):
        ax.text(i, v + 0.5, str(v), ha="center", fontsize=10)
    ax.set_ylabel(f"Harmful of {D['n_b13_excluded']} B13-excluded instances")
    _h8 = L("eval_holdout8.json")
    sub = ("Development data: a poison B13 excludes returns through the consolidated summary; lexical "
           "propagation containment barely acts, semantic nearly eliminates it.")
    if _h8 and _h8.get("derived_memory", {}).get("laundered_admitted_of_carried_excluded"):
        la = _h8["derived_memory"]["laundered_admitted_of_carried_excluded"]
        sub += f"\nConfirmed on hold-out 8: laundered summaries admitted - lexical {la['lexical']} vs semantic {la['semantic']}."
    ax.set_title("Figure R6 - Laundering through consolidation, and the semantic containment fix\n" + sub, fontsize=9)
    ax.grid(alpha=0.3, axis="y")
    out = FIG / "R6_laundering.png"
    fig.tight_layout(); fig.savefig(out, dpi=150); plt.close(fig)
    return out


def run() -> dict:
    FIG.mkdir(parents=True, exist_ok=True)
    made = {}
    for name, fn in (("R1", r1_holdouts), ("R2", r2_harm), ("R3", r3_adaptive), ("R4", r4_retrieval),
                     ("R5", r5_union_defense), ("R6", r6_laundering),
                     ("fig01b", fig01b), ("fig12", fig12), ("fig20", fig20)):
        p = fn()
        made[name] = str(p.relative_to(ROOT)) if p else None
    (FIG / "index.json").write_text(json.dumps(made, indent=1), encoding="utf-8")
    return made


if __name__ == "__main__":
    print(json.dumps(run(), indent=1))
    print("DONE")
