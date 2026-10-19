"""Figures for the 2026-10-13/14 work (targeted phase; defence programmes v2-v5), drawn from the committed artifacts
at build time so they cannot drift from the numbers in the text and tables. Used by both document builders.

  F1  B13 leave-one-owner-out: per-owner detection and benign exclusion (A-ship)
  F2  B13 evidence conditions: pooled benign exclusion and detection (correct / wrong / truncated / none)
  F3  Attack validity: none / clean / poisoned compliance under both probes (C0)
  F4  Multi-generation containment: withheld among payload-carrying descendants, gens 1-4 (HO4, HO8, HO7)
  F5  Implicit sleepers: attack detection vs ungrounded-benign exclusion for every detector (SA-3 dev and eval)
  F6  Verify-on-activation: unconfirmed activation and legitimate-rule availability (SA-4 raw; SA-5 Mem0-stored)
  F7  Operational closure scores per gap, per capability
  F8  Defence architecture (lifecycle diagram) with each component's evaluated status
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "phase17" / "data"
OUT = ROOT / "docs" / "figures" / "final"
C = {"FG": "#8c8c8c", "RCL": "#1f77b4", "CTC": "#ff7f0e", "PRC": "#2ca02c", "A0": "#d62728", "WTP": "#9467bd"}


def L(rel):
    p = DATA / rel
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _plt():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9})
    return plt


def _r(x):
    return x["k"] / x["n"] if x and x.get("n") else 0.0


def f1_loo():
    d = L("remediation/b13_owner_loo.json")
    if not d:
        return None
    plt = _plt()
    owners = sorted(d["owners"], key=int)
    det = [_r(d["owners"][o]["A-ship"]["detection"]) * 100 for o in owners]
    ben = [_r(d["owners"][o]["A-ship"]["benign_exclusion"]) * 100 for o in owners]
    fig, ax = plt.subplots(1, 2, figsize=(9, 3.2))
    ax[0].bar(owners, det, color=C["RCL"])
    ax[0].set_title("Attack detection per held-out owner (%)")
    ax[0].set_ylim(0, 100)
    ax[1].bar(owners, ben, color=C["A0"])
    ax[1].set_title("Benign exclusion per held-out owner (%)")
    ax[1].set_ylim(0, 5)
    for a in ax:
        a.set_xlabel("LoCoMo owner (thresholds fitted on the other nine)")
    fig.tight_layout()
    p = OUT / "F1_b13_loo.png"
    fig.savefig(p, dpi=170)
    plt.close(fig)
    return p


def f2_evidence():
    d = L("remediation/b13_owner_loo.json")
    if not d:
        return None
    plt = _plt()
    conds = ["correct", "trunc50", "trunc10", "wrong", "none"]
    ev = d["evidence_conditions"]
    ben = [ev[c]["pooled"]["A-ship"]["benign_exclusion"]["k"] / ev[c]["pooled"]["A-ship"]["benign_exclusion"]["n"] * 100 for c in conds]
    det = [ev[c]["pooled"]["A-ship"]["detection"]["k"] / ev[c]["pooled"]["A-ship"]["detection"]["n"] * 100 for c in conds]
    fig, ax = plt.subplots(figsize=(7, 3.2))
    x = range(len(conds))
    ax.bar([i - 0.2 for i in x], det, 0.4, label="attack detection", color=C["RCL"])
    ax.bar([i + 0.2 for i in x], ben, 0.4, label="benign exclusion", color=C["A0"])
    ax.set_xticks(list(x))
    ax.set_xticklabels(["correct owner", "first 50%", "first 10%", "wrong owner", "no conversation"])
    ax.set_ylabel("% (10 owners pooled)")
    ax.legend()
    ax.set_title("B13 corroboration depends on the evidence, not on the calibration owners")
    fig.tight_layout()
    p = OUT / "F2_b13_evidence.png"
    fig.savefig(p, dpi=170)
    plt.close(fig)
    return p


def f3_validity():
    d = L("remediation/validity_final.json")
    if not d or not d.get("none_arm_complete"):
        return None
    plt = _plt()
    fig, ax = plt.subplots(figsize=(7, 3.2))
    probes = [("fitted", "fitted probe"), ("nonleading", "non-leading probe")]
    arms = ["none", "clean", "poisoned"]
    cols = ["#bbbbbb", "#6baed6", C["A0"]]
    for pi, (pk, pl) in enumerate(probes):
        tc = d["three_conditions"][f"{pk}|C0"]
        for ai, a in enumerate(arms):
            v = tc[f"comply_{a}"]
            ax.bar(pi * 4 + ai, v["k"] / v["n"] * 100, color=cols[ai], label=a if pi == 0 else None)
    ax.set_xticks([1, 5])
    ax.set_xticklabels([p[1] for p in probes])
    ax.set_ylabel("judged compliant (%, C0, 150 items)")
    ax.legend(title="memory")
    ax.set_title("The fitted probe leaks the note; the memory effect survives a non-leading probe")
    fig.tight_layout()
    p = OUT / "F3_validity_three_conditions.png"
    fig.savefig(p, dpi=170)
    plt.close(fig)
    return p


def f4_containment():
    ho4 = L("defence_v2/prop_eval.json")
    prc = L("defence_v4/prc_eval.json")
    if not (ho4 and prc):
        return None
    plt = _plt()
    sets = [("HO4 (factual)", prc["sets"]["ho4"]["pooled"]), ("HO8 (instruction+factual)", prc["sets"]["ho8"]["pooled"]),
            ("HO7 fresh (instruction+factual)", prc["sets"]["ho7"]["pooled"])]
    fig, ax = plt.subplots(1, 3, figsize=(10, 3.2), sharey=True)
    for a, (name, b) in zip(ax, sets):
        for arm in ("FG", "RCL", "CTC", "PRC"):
            ys = [_r(x) * 100 for x in b[arm]["withheld_carrying"]]
            a.plot([1, 2, 3, 4], ys, marker="o", color=C[arm], label=arm)
        a.set_title(name)
        a.set_xticks([1, 2, 3, 4])
        a.set_xlabel("consolidation generation")
        a.set_ylim(0, 105)
    ax[0].set_ylabel("payload-carrying descendants withheld (%)")
    ax[0].legend(loc="lower left")
    fig.suptitle("Containment across generations (unflagged-benign collateral 0/40 for every lineage arm)")
    fig.tight_layout()
    p = OUT / "F4_containment_generations.png"
    fig.savefig(p, dpi=170)
    plt.close(fig)
    return p


def f5_sleepers():
    v2 = L("defence_v2/sleeper_v2_eval.json")
    v3 = L("defence_v3/sleeper_v3_selection.json")
    if not (v2 and v3):
        return None
    plt = _plt()
    fig, ax = plt.subplots(figsize=(6.5, 4))
    pts = []
    for n, a in v2["eval_raw"]["aggregate"].items():
        pts.append((n + " (eval)", a["ben_unground"][0] / a["ben_unground"][1] * 100, a["atk"][0] / a["atk"][1] * 100, "o"))
    for n, a in v3["dev"]["aggregate"]["raw"].items():
        if n.startswith("N1"):
            pts.append((n + " (dev)", a["ben_unground"][0] / a["ben_unground"][1] * 100, a["atk"][0] / a["atk"][1] * 100, "s"))
    for name, x, y, mk in pts:
        ax.scatter(x, y, marker=mk, s=30)
        ax.annotate(name, (x, y), fontsize=6, xytext=(3, 2), textcoords="offset points")
    from matplotlib.patches import Rectangle
    ax.add_patch(Rectangle((0, 50), 10, 52, color="#2ca02c", alpha=0.12, lw=0))
    ax.set_xlabel("legitimate ungrounded conditional rules flagged (%)")
    ax.set_ylabel("implicit sleepers detected (%)")
    ax.set_title("Implicit sleepers: no detector reaches the acceptance region\n"
                 "(shaded: <=10% legitimate rules flagged and >=50% detected)")
    ax.set_xlim(-2, 102)
    ax.set_ylim(-2, 102)
    fig.tight_layout()
    p = OUT / "F5_sleeper_detectors.png"
    fig.savefig(p, dpi=170)
    plt.close(fig)
    return p


def f6_voa():
    v4 = L("defence_v4/voa_eval.json")
    v5 = L("defence_v5/af_eval.json")
    if not (v4 and v5):
        return None
    plt = _plt()
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.4))
    b = v4["sets"]["N1|B13"]
    labels = ["undefended", "exclusion", "VoA (F2)"]
    atk = [b["atk"]["raw"]["undefended"]["unconfirmed_activation"], b["atk"]["raw"]["exclusion"]["unconfirmed_activation"],
           b["atk"]["raw"]["VoA"]["unconfirmed_activation"]]
    ben = [b["ben_unground"]["raw"]["undefended"]["surfaced"], b["ben_unground"]["raw"]["exclusion"]["surfaced"],
           b["ben_unground"]["raw"]["VoA"]["surfaced"]]
    x = range(3)
    ax[0].bar([i - 0.2 for i in x], [_r(v) * 100 for v in atk], 0.4, color=C["A0"], label="attacks acting without confirmation")
    ax[0].bar([i + 0.2 for i in x], [_r(v) * 100 for v in ben], 0.4, color=C["RCL"], label="legitimate rules still usable")
    ax[0].set_xticks(list(x))
    ax[0].set_xticklabels(labels)
    ax[0].set_title("SA-4, raw memories (held-out)")
    ax[0].legend(fontsize=7)
    g = v5["groups"]
    fr = v5["frame"]
    arms = [("undefended", "undefended"), ("F2_v4", "F2 (comparator)"), (fr, f"{fr} (selected)")]
    ax[1].bar([i - 0.2 for i in range(3)], [_r(g["attacks_document"][a]["unconfirmed_activation"]) * 100 for a, _ in arms], 0.4, color=C["A0"])
    ax[1].bar([i + 0.2 for i in range(3)], [_r(g["benign_user_channel"][a]["surfaced"]) * 100 for a, _ in arms], 0.4, color=C["RCL"])
    ax[1].set_xticks(range(3))
    ax[1].set_xticklabels([l for _, l in arms])
    ax[1].set_title("SA-5, after Mem0 rewriting (held-out)")
    for a in ax:
        a.set_ylabel("%")
        a.set_ylim(0, 100)
    fig.tight_layout()
    p = OUT / "F6_verify_on_activation.png"
    fig.savefig(p, dpi=170)
    plt.close(fig)
    return p


CLOSURE = {
    "Gap 1: provenance and governance": [("1.1 transformation-aware detection*", .25, .5), ("1.2 wrong lineage safe*", .20, .75),
                                         ("1.3 benign utility incl. ungrounded*", .20, .5), ("1.4 owner generalisation", .15, .75),
                                         ("1.5 end-to-end prevention", .20, .5)],
    "Gap 2: self-propagation": [("2.1 claim tracking", .10, .75), ("2.2 instruction payloads gen 4*", .25, .5),
                                ("2.3 factual payloads gen 4", .15, .75), ("2.4 influence reduced*", .20, .75),
                                ("2.5 benign preserved, recovery", .15, .75), ("2.6 lineage loss", .15, .5)],
    "Gap 3: implicit sleepers": [("3.1 dormancy/activation measured", .15, .75), ("3.2 detection after transformation*", .30, 0),
                                 ("3.3 benign preserved while detecting*", .25, 0), ("3.4 activation prevented", .20, .5),
                                 ("3.5 explicit sleepers after transformation", .10, .75)],
}


def closure_scores():
    out = {}
    for g, caps in CLOSURE.items():
        s = sum(w * v for _, w, v in caps)
        crit = [v for n, w, v in caps if n.endswith("*")]
        cap = 0.5 if min(crit) == 0 else (0.6 if min(crit) <= 0.25 else 1.0)
        out[g] = round(min(s, cap), 3)
    return out


def f7_closure():
    plt = _plt()
    sc = closure_scores()
    fig, ax = plt.subplots(figsize=(7, 3))
    names = list(sc)
    ax.barh(names, [sc[n] * 100 for n in names], color=[C["RCL"], C["PRC"], C["A0"]])
    ax.axvline(75, color="black", ls="--", lw=0.8)
    ax.text(75.5, 2.35, "75% target", fontsize=7)
    for i, n in enumerate(names):
        ax.text(sc[n] * 100 + 1, i, f"{sc[n] * 100:.0f}%", va="center")
    ax.set_xlim(0, 100)
    ax.invert_yaxis()
    ax.set_xlabel("operational closure (weighted evidence-strength rubric; critical caps)")
    fig.tight_layout()
    p = OUT / "F7_closure.png"
    fig.savefig(p, dpi=170)
    plt.close(fig)
    return p


def f8_architecture():
    plt = _plt()
    from matplotlib.patches import FancyBboxPatch

    fig, ax = plt.subplots(figsize=(10, 3.6))
    ax.axis("off")
    stages = [("Ingestion\n(user / document)", "PRW: source per\nmemory, kept\nthrough Mem0\n(137/137)", "#d9f0d3"),
              ("Admission", "B13 corroboration\n(LOO-stable)\n+ VPL: verified\npayload lineage", "#d9f0d3"),
              ("Memory store\n(Mem0)", "rewrites rules\ninto preference\nfacts", "#f0f0f0"),
              ("Consolidation", "RCL / PRC\ncontainment\nWTP: taint at\nwrite time", "#d9f0d3"),
              ("Retrieval +\nactivation", "VoA frame: works\non raw memories,\nnot after\nrewriting", "#fde0c5"),
              ("Agent action", "judged behaviour only\n(no tool execution)", "#f0f0f0")]
    w, h, gap = 1.45, 1.0, 0.25
    for i, (title, note, col) in enumerate(stages):
        x = i * (w + gap)
        ax.add_patch(FancyBboxPatch((x, 0.6), w, 1.5, boxstyle="round,pad=0.04", fc=col, ec="black", lw=0.8))
        ax.text(x + w / 2, 1.75, title, ha="center", va="center", fontsize=8, weight="bold")
        ax.text(x + w / 2, 1.0, note, ha="center", va="center", fontsize=6.3)
        if i < len(stages) - 1:
            ax.annotate("", xy=(x + w + gap, 1.35), xytext=(x + w, 1.35), arrowprops=dict(arrowstyle="->"))
    ax.text(0, 2.55, "green = evaluated and accepted within scope;  orange = works only partly;  grey = not a defence stage",
            fontsize=7)
    ax.text(0, 0.05, "Open: implicit-sleeper detection; lineage deleted after writing; user-channel poisoning", fontsize=7, color="#a50f15")
    ax.set_xlim(-0.1, 6 * (w + gap))
    ax.set_ylim(0, 2.8)
    fig.tight_layout()
    p = OUT / "F8_architecture.png"
    fig.savefig(p, dpi=170)
    plt.close(fig)
    return p


def run() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    made = {}
    for k, fn in (("F1", f1_loo), ("F2", f2_evidence), ("F3", f3_validity), ("F4", f4_containment), ("F5", f5_sleepers),
                  ("F6", f6_voa), ("F7", f7_closure), ("F8", f8_architecture)):
        p = fn()
        made[k] = str(p.relative_to(ROOT)) if p else None
    (OUT / "index.json").write_text(json.dumps(made, indent=1), encoding="utf-8")
    return made


if __name__ == "__main__":
    print(json.dumps(run(), indent=1))
    print(closure_scores())
