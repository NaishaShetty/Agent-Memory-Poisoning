"""Figures for Defence v7 (2026-10-15/17), drawn from the v7 artifacts at build time. Used by both document builders.
A figure whose source artifact does not exist yet is skipped (None).

  W1  Gap 1: explicit-attack exclusion vs legitimate-rule exclusion per arm (SA-7 eval), with GP's framed share
  W2  Gap 2: HO10 instruction-payload containment across generations for the main arms
  W3  Gap 3: implicit detection vs ungrounded legitimate-rule false positives per condition (SA-7 eval), with the limits
  W4  Operational closure per gap: v5, v6 and v7 (frozen rubric)
"""
from __future__ import annotations

import json
from pathlib import Path

from phase17.figures_v6 import COL, _plt, _r

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "phase17" / "data" / "defence_v7"
OUT = ROOT / "docs" / "figures" / "v7"
COL = dict(COL, **{"GP": "#d62728", "ND|RAR-S": "#d62728", "RAR-S": "#9467bd"})


def L(name):
    p = DATA / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _save(fig, name):
    p = OUT / name
    fig.savefig(p, dpi=170)
    import matplotlib.pyplot as plt
    plt.close(fig)
    return p


def w1_gap1():
    g = L("g1_eval_sa7.json")
    if not g:
        return None
    s = g["single_notes"]
    plt = _plt()
    fig, ax = plt.subplots(figsize=(6.4, 3.2))
    arms = ("B13s", "PAB13", "PCL", "GP_excl")
    lab = {"B13s": "B13 on stored", "PAB13": "PAB13", "PCL": "PCL (v6)", "GP_excl": "GP (v7)"}
    x = range(len(arms))
    ax.bar([i - 0.2 for i in x], [_r(s["atk_explicit"][a]) for a in arms], 0.4, label="explicit attacks excluded",
           color="#1f77b4")
    ax.bar([i + 0.2 for i in x], [_r(s["pooled_ungrounded"][a]) for a in arms], 0.4,
           label="ungrounded legitimate rules excluded", color="#ff7f0e")
    ax.bar([3.2], [_r(s["pooled_ungrounded"]["GP_frame"])], 0.4, bottom=[_r(s["pooled_ungrounded"]["GP_excl"])],
           color="#ffbb78", label="GP: legitimate rules framed (delayed)")
    ax.axhline(10, color="black", ls="--", lw=0.8)
    ax.text(-0.45, 11, "10% benign limit", fontsize=7)
    ax.set_xticks(list(x), [lab[a] for a in arms])
    ax.set_ylabel("% of items (SA-7 eval)")
    ax.legend(fontsize=7, loc="upper left")
    fig.tight_layout()
    return _save(fig, "W1_gap1.png")


def w2_containment():
    g = L("g2_eval_ho10.json")
    if not g:
        return None
    ins = g["by_payload"]["instruction"]
    plt = _plt()
    fig, ax = plt.subplots(figsize=(6.4, 3.2))
    for a in ("FG", "ND", "PRC", "RAR-S", "ND|RAR-S"):
        ax.plot([1, 2, 3, 4], [_r(ins[a]["withheld_carrying"][k]) for k in range(4)], marker="o", label=a,
                color=COL.get(a, "#333333"), lw=2.2 if a == "ND|RAR-S" else 1.2)
    ax.axhline(60, color="black", ls="--", lw=0.8)
    ax.text(1.02, 61.5, "60% bar (generation 4)", fontsize=7)
    ax.set_xticks([1, 2, 3, 4])
    ax.set_xlabel("consolidation generation")
    ax.set_ylabel("payload-carrying descendants withheld (%)")
    ax.set_ylim(0, 100)
    ax.legend(fontsize=7, ncol=3)
    fig.tight_layout()
    return _save(fig, "W2_containment.png")


def w3_gap3():
    g = L("g3_eval_sa7.json")
    if not g:
        return None
    C = g["conditions"]
    show = {"B_transformed(baseline)": "B", "C&K_metadata+stored": "C∧K", "D_original_record(v6 frozen)": "D",
            "E_validated_lineage(PRIMARY)": "E (primary)", "A_original_text": "A", "N1_alone(raw)": "N1", "BF_R_alone(raw)": "BF-R"}
    plt = _plt()
    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    ax.axvspan(0, 10, color="#e5f5e0", zorder=0)
    ax.axhline(50, color="black", ls=":", lw=0.8)
    for k, lab in show.items():
        v = C[k]
        xx, yy = _r(v["ungrounded_pooled"]), _r(v["atk_implicit"])
        ax.scatter(xx, yy, s=40, color="#d62728" if lab.startswith("E") else "#1f77b4", zorder=3)
        off = {"C∧K": (-24, 5), "B": (5, 4), "E (primary)": (-10, -13), "D": (-4, 7), "A": (5, 4)}.get(lab, (5, 3))
        ax.annotate(lab, (xx, yy), textcoords="offset points", xytext=off, fontsize=7)
    ax.set_xlabel("ungrounded legitimate rules flagged (%)  [green: within the 10% limit]")
    ax.set_ylabel("implicit sleepers detected (%)")
    ax.set_xlim(0, max(35, max(_r(C[k]["ungrounded_pooled"]) for k in show) + 5))
    ax.set_ylim(0, 105)
    fig.tight_layout()
    return _save(fig, "W3_gap3.png")


def w4_closure():
    c7 = L("closure_v7.json")
    c6 = json.loads((ROOT / "phase17" / "data" / "defence_v6" / "closure_v6.json").read_text(encoding="utf-8"))
    if not c7:
        return None
    plt = _plt()
    gaps = list(c7["gaps"])
    v5 = [100 * c6["gaps"][g]["before"] for g in gaps]
    v6 = [100 * c7["gaps"][g]["before_v6"] for g in gaps]
    v7 = [100 * c7["gaps"][g]["after_v7"] for g in gaps]
    fig, ax = plt.subplots(figsize=(6.4, 2.9))
    y = range(len(gaps))
    for off, vals, lab, col in ((-0.27, v5, "v5", "#c7c7c7"), (0, v6, "v6", "#8c8c8c"), (0.27, v7, "v7", "#d62728")):
        ax.barh([i + off for i in y], vals, 0.25, label=lab, color=col)
        for i, v in zip(y, vals):
            ax.text(v + 0.8, i + off, f"{v:.0f}%", va="center", fontsize=7)
    ax.axvline(75, color="black", ls="--", lw=0.8)
    ax.set_yticks(list(y), [g.split(": ")[1] for g in gaps])
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xlabel("operational closure (frozen rubric; critical caps)")
    ax.legend(fontsize=7, loc="lower right")
    fig.tight_layout()
    return _save(fig, "W4_closure.png")


def w5_architecture():
    """v7 defence architecture; every component's colour is read from closure_v7.json / the eval artifacts."""
    c, g3 = L("closure_v7.json"), L("g3_eval_sa7.json")
    if not (c and g3):
        return None
    from matplotlib.patches import FancyBboxPatch

    cap = {x["name"].split(" ")[0]: x["after"] for v in c["gaps"].values() for x in v["capabilities"]}
    ok, part, fail, grey = "#c7e9c0", "#fdd0a2", "#fcbba1", "#eeeeee"
    b = g3["behaviour"]
    ts_ok = all(v is True for v in b["TS_replication"].values())
    hig_ok = b["HIG_acceptance"]["paired_raw"] is True
    e_ok = g3["G3_P2_at_E"]["meets"]
    import math

    g2 = L("g2_eval_ho10.json")
    w4 = g2["by_payload"]["instruction"]["ND|RAR-S"]["withheld_carrying"][3]
    margin = w4["k"] - math.ceil(0.6 * w4["n"])
    c2 = g2["recovery"]["C2_deleted_then_rewritten_SIMULATION"]
    fa = (f"{100 * c2['false_association_owner_store']['rate']:.1f}/"
          f"{100 * c2['false_association_unflagged_benign_desc']['rate']:.1f}%")
    stages = [
        ("Write:\nPL ledger", "source event per add;\nhash-chained (tamper-\nevident; tests only)", grey),
        ("Mem0\nextraction", "ADD-only in infer mode;\nstores nothing for some\nlegitimate rules", grey),
        ("Admission:\nGP", f"exclude on B12 AND intent;\nframe on corroboration;\nGap 1 -> {100 * c['gaps']['Gap 1: provenance and governance']['after_v7']:.0f}%",
         ok if cap["1.1"] >= 0.75 and cap["1.3"] >= 0.75 else part),
        ("Propagation:\nND|RAR-S", f"no-decay guard OR\nsentence fingerprint;\n2.2 margin: {margin} descendants",
         ok if cap["2.2"] >= 0.75 else part),
        ("Recovery:\nlog / DCR-2", f"exact with log;\nafter rewrite: FA {fa}\n(relative criterion)", ok if cap["2.6"] >= 0.75 else part),
        ("Detection:\nE", f"implicit {g3['G3_P2_at_E']['implicit_detection']['k']}/48 but\nlegit flagged "
                         f"{100 * g3['G3_P2_at_E']['ungrounded_pooled']['rate']:.1f}% > 10%", ok if e_ok else fail),
        ("Retrieval/action:\nTS + HIG", f"TS {'replicated' if ts_ok else 'not significant'};\n"
                                       f"HIG {'accepted' if hig_ok else 'under-powered'}", ok if (ts_ok and hig_ok) else part),
        ("Agent", "answers; asks before\nacting on framed\nrules", grey)]
    plt = _plt()
    fig, ax = plt.subplots(figsize=(11.5, 2.9))
    ax.axis("off")
    w, gap = 1.25, 0.2
    for i, (t, n, col) in enumerate(stages):
        x = i * (w + gap)
        ax.add_patch(FancyBboxPatch((x, 0.6), w, 1.55, boxstyle="round,pad=0.04", fc=col, ec="black", lw=0.8))
        ax.text(x + w / 2, 1.85, t, ha="center", va="center", fontsize=7.2, weight="bold")
        ax.text(x + w / 2, 1.05, n, ha="center", va="center", fontsize=5.8)
        if i < len(stages) - 1:
            ax.annotate("", xy=(x + w + gap, 1.35), xytext=(x + w, 1.35), arrowprops=dict(arrowstyle="->"))
    ax.text(0, 2.6, "green = accepted on held-out data within scope;  orange = partial / not significant / under-powered;  "
                    "red = failed;  grey = not a defence stage", fontsize=7)
    ax.text(0, 0.08, "Open: legitimate rules from untrusted or unrecorded sources look like attacks; user-relayed attacks "
                     "pass every provenance defence; behavioural base rates too low on SA-7", fontsize=7, color="#a50f15")
    ax.set_xlim(-0.1, len(stages) * (w + gap))
    ax.set_ylim(0, 2.85)
    fig.tight_layout()
    return _save(fig, "W5_architecture_v7.png")


def run() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    made = {}
    for k, fn in (("W1", w1_gap1), ("W2", w2_containment), ("W3", w3_gap3), ("W4", w4_closure), ("W5", w5_architecture)):
        p = fn()
        made[k] = str(p.relative_to(ROOT)) if p else None
    (OUT / "index.json").write_text(json.dumps(made, indent=1), encoding="utf-8")
    return made


if __name__ == "__main__":
    print(json.dumps(run(), indent=1))
