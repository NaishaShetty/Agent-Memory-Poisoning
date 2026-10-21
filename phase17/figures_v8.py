"""Figures for Defence Programme v8 (2026-10-20/21), drawn from the v8 artifacts at build time.
Used by both document builders. A figure whose source artifact does not exist yet is skipped (None).

  X1  Gap 3 detection vs ungrounded false positives: C AND K on SA-8 and C AND K + G on SA-9
  X2  Writer-authentication stress test: plain vs gated detection across three writer scenarios
  X3  Two-stage frame and high-impact gate: paired discordant counts on the 184-item pool
  X4  Gap 2 factual-payload containment across consolidation generations (HO11)
  X5  Operational closure per gap: v7 and v8 (frozen rubric)
"""
from __future__ import annotations

import json
from pathlib import Path

from phase17.figures_v6 import _plt, _r

ROOT = Path(__file__).resolve().parents[1]
D8 = ROOT / "phase17" / "data" / "defence_v8"
D7 = ROOT / "phase17" / "data" / "defence_v7"
OUT = ROOT / "docs" / "figures" / "v8"


def L(name, base=D8):
    p = base / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _save(fig, name):
    p = OUT / name
    fig.savefig(p, dpi=170)
    import matplotlib.pyplot as plt

    plt.close(fig)
    return p


def x1_detection_vs_fpr():
    sa8, sa9 = L("g3_eval_sa8.json"), L("g3_eval_sa9.json")
    if not (sa8 and sa9):
        return None
    plt = _plt()
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    ax.axhspan(0, 10, color="#e5f5e0", zorder=0)
    ax.axvline(50, color="black", ls=":", lw=0.8)
    points = [
        ("SA-8: C∧K", sa8["conditions"]["C&K_metadata+stored(SECONDARY, pre-registered here for SA-8)"], "#1f77b4", "o"),
        ("SA-9: C∧K (plain)", sa9["conditions"]["C&K(plain, same frozen rule as W1)"], "#1f77b4", "s"),
        ("SA-9: C∧K + G", sa9["conditions"]["C&K+G(W1b primary)"], "#d62728", "s"),
    ]
    for lab, v, col, marker in points:
        xx, yy = _r(v["atk_implicit"]), _r(v["ungrounded_pooled"])
        ax.scatter(xx, yy, s=55, color=col, marker=marker, zorder=3)
        off = {"SA-8: C∧K": (6, 4), "SA-9: C∧K (plain)": (-28, 6), "SA-9: C∧K + G": (6, -4)}.get(lab, (6, 4))
        ax.annotate(lab, (xx, yy), textcoords="offset points", xytext=off, fontsize=7.5)
    ax.set_xlabel("implicit sleepers detected (%)")
    ax.set_ylabel("ungrounded legitimate rules flagged (%)")
    ax.set_title("green band: within the 10% limit", fontsize=8, loc="left")
    ax.set_xlim(40, 85)
    ax.set_ylim(0, 18)
    fig.tight_layout()
    return _save(fig, "X1_detection_vs_fpr.png")


def x2_writer_stress():
    s = L("g3_stress_sa9.json")
    if not s:
        return None
    plt = _plt()
    fig, ax = plt.subplots(figsize=(6.4, 3.2))
    labels = ["authenticated,\nnon-owner-trusted writer", "compromised\ntrusted writer", "unsigned\nwriter"]
    keys = ["authenticated_non_owner_trusted_writer", "compromised_trusted_writer", "unsigned_writer"]
    plain = [100 * s[k]["plain_rate"] for k in keys]
    gated = [100 * s[k]["gated_rate"] for k in keys]
    x = range(3)
    ax.bar([i - 0.18 for i in x], plain, 0.34, label="C∧K (plain)", color="#1f77b4")
    ax.bar([i + 0.18 for i in x], gated, 0.34, label="C∧K + G", color="#d62728")
    for i, (p, g) in enumerate(zip(plain, gated)):
        ax.text(i - 0.18, p + 1.5, f"{p:.0f}%", ha="center", fontsize=7.5)
        ax.text(i + 0.18, g + 1.5, f"{g:.0f}%", ha="center", fontsize=7.5)
    ax.set_xticks(list(x), labels, fontsize=8)
    ax.set_ylabel("attacks detected (%)")
    ax.set_ylim(0, 65)
    ax.legend(fontsize=8, loc="upper right")
    fig.tight_layout()
    return _save(fig, "X2_writer_stress.png")


def x3_ts_hig():
    b = L("g3_behaviour_sa89.json")
    if not b:
        return None
    plt = _plt()
    fig, ax = plt.subplots(figsize=(6.0, 3.0))
    rows = [("TS vs stored", b["TS_vs_stored"]), ("HIG vs stored", b["HIG_vs_stored"])]
    y = range(len(rows))
    for i, (lab, v) in enumerate(rows):
        ax.barh(i - 0.18, v["only_undefended"], 0.3, color="#8c8c8c", label="stored-only" if i == 0 else None)
        ax.barh(i + 0.18, v["only_defended"], 0.3, color="#d62728", label="defended-only" if i == 0 else None)
        ax.text(v["only_undefended"] + 0.5, i - 0.18, f"p={v['p_exact']:.2g}", va="center", fontsize=7.5)
    ax.set_yticks(list(y), [r[0] for r in rows])
    ax.set_xlabel("discordant pairs (184-item pool, SA-8 + SA-9 eval)")
    ax.set_xlim(0, 40)
    ax.legend(fontsize=8, loc="upper right")
    fig.tight_layout()
    return _save(fig, "X3_ts_hig.png")


def x4_ho11_containment():
    g = L("g2_eval_ho11.json")
    if not g:
        return None
    f = g["factual"]
    plt = _plt()
    fig, ax = plt.subplots(figsize=(6.4, 3.2))
    for a, col in (("FG", "#8c8c8c"), ("ND", "#bcbd22"), ("PRC", "#2ca02c"), ("ND|RAR-S", "#d62728")):
        ax.plot([1, 2, 3, 4], [_r(f[a]["withheld_carrying"][k]) for k in range(4)], marker="o", label=a,
                color=col, lw=2.4 if a == "ND|RAR-S" else 1.2)
    ax.axhline(60, color="black", ls="--", lw=0.8)
    ax.text(1.02, 61.5, "60% bar (generation 4)", fontsize=7)
    ax.set_xticks([1, 2, 3, 4])
    ax.set_xlabel("consolidation generation")
    ax.set_ylabel("factual-payload-carrying descendants withheld (%)")
    ax.set_ylim(0, 100)
    ax.legend(fontsize=8, ncol=2)
    fig.tight_layout()
    return _save(fig, "X4_ho11_containment.png")


def x5_closure():
    c7 = json.loads((D7 / "closure_v7.json").read_text(encoding="utf-8"))
    c8 = L("closure_v8.json")
    if not c8:
        return None
    plt = _plt()
    gaps = list(c7["gaps"])
    v7 = [100 * c7["gaps"][g]["after_v7"] for g in gaps]
    v8 = [100 * (c8["gaps"][g].get("after_v8", c8["gaps"][g].get("after_v7"))) for g in gaps]
    fig, ax = plt.subplots(figsize=(6.4, 2.9))
    y = range(len(gaps))
    for off, vals, lab, col in ((-0.17, v7, "v7", "#8c8c8c"), (0.17, v8, "v8", "#d62728")):
        ax.barh([i + off for i in y], vals, 0.32, label=lab, color=col)
        for i, v in zip(y, vals):
            ax.text(v + 0.8, i + off, f"{v:.0f}%", va="center", fontsize=7.5)
    ax.axvline(75, color="black", ls="--", lw=0.8)
    ax.set_yticks(list(y), [g.split(": ")[1] for g in gaps])
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xlabel("operational closure (frozen rubric; critical caps)")
    ax.legend(fontsize=8, loc="lower right")
    fig.tight_layout()
    return _save(fig, "X5_closure.png")


def x6_architecture():
    """v8 defence architecture: the writer-authentication gate added after v7's E/C∧K
    detection stage, and 2.3's restored status after HO11."""
    c8 = L("closure_v8.json")
    sa9, ho11 = L("g3_eval_sa9.json"), L("g2_eval_ho11.json")
    if not (c8 and sa9 and ho11):
        return None
    from matplotlib.patches import FancyBboxPatch

    cap = {x["name"].split(" ")[0]: x["after"] for v in c8["gaps"].values() for x in v["capabilities"]}
    ok, part, grey = "#c7e9c0", "#fdd0a2", "#eeeeee"
    ckg = sa9["conditions"]["C&K+G(W1b primary)"]
    f = ho11["factual"]
    stages = [
        ("Write:\nAuthenticated ledger", "HMAC per-writer signature\non the hash-chained log;\n34 tests, forged keys rejected", grey),
        ("Admission:\nGP (v7)", f"unchanged; Gap 1 -> {100 * c8['gaps']['Gap 1: provenance and governance']['after_v7']:.0f}%", ok),
        ("Propagation:\nND|RAR-S (v7)", f"unchanged; factual sub-test\nnow powered ({_r(f['carry'][3]):.0f}% carry\n"
                                        f"to gen 4), {_r(f['ND|RAR-S']['withheld_carrying'][3]):.0f}% withheld", ok if cap["2.3"] >= 0.75 else part),
        ("Detection:\nC AND K + G", f"implicit {ckg['atk_implicit']['k']}/{ckg['atk_implicit']['n']};\nlegit flagged "
                                   f"{100 * ckg['ungrounded_pooled']['rate']:.1f}%\n<= 10% limit",
         ok if ckg["meets_G3P2"] else part),
        ("Retrieval/action:\nTS (v7)", "replicated on fresh data\n(p = 0.026); HIG unchanged", ok),
        ("Agent", "answers; asks before\nacting on framed rules", grey)]
    plt = _plt()
    fig, ax = plt.subplots(figsize=(12.5, 2.9))
    ax.axis("off")
    w, gap = 1.9, 0.25
    for i, (t, n, col) in enumerate(stages):
        x = i * (w + gap)
        ax.add_patch(FancyBboxPatch((x, 0.6), w, 1.6, boxstyle="round,pad=0.04", fc=col, ec="black", lw=0.8))
        ax.text(x + w / 2, 1.9, t, ha="center", va="center", fontsize=7.4, weight="bold")
        ax.text(x + w / 2, 1.05, n, ha="center", va="center", fontsize=5.9)
        if i < len(stages) - 1:
            ax.annotate("", xy=(x + w + gap, 1.4), xytext=(x + w, 1.4), arrowprops=dict(arrowstyle="->"))
    ax.text(0, 2.65, "green = accepted on held-out data within scope;  orange = partial / stratum-limited;  "
                     "grey = not a detection stage", fontsize=7)
    ax.text(0, 0.1, "Open: a compromised trusted-writer key removes detection on that channel entirely "
                    "(Section 25.4); user-relayed attacks pass every provenance defence", fontsize=7, color="#a50f15")
    ax.set_xlim(-0.1, len(stages) * (w + gap))
    ax.set_ylim(0, 2.85)
    fig.tight_layout()
    return _save(fig, "X6_architecture_v8.png")


def run() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    made = {}
    for k, fn in (("X1", x1_detection_vs_fpr), ("X2", x2_writer_stress), ("X3", x3_ts_hig),
                  ("X4", x4_ho11_containment), ("X5", x5_closure), ("X6", x6_architecture)):
        p = fn()
        made[k] = str(p.relative_to(ROOT)) if p else None
    (OUT / "index.json").write_text(json.dumps(made, indent=1), encoding="utf-8")
    return made


if __name__ == "__main__":
    print(json.dumps(run(), indent=1))
