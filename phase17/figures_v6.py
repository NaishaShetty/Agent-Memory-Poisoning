"""Figures for Defence v6 (2026-10-14/15), drawn from the committed v6 artifacts at build time so they cannot drift from
the text. Used by both document builders. A figure whose source artifact does not exist yet is skipped (None).

  V1  Provenance through Mem0: native metadata vs the PL ledger (ADD; forced UPDATE; native history writer fields)
  V2  Claim fingerprints on FPB eval: recall vs false matches for each matcher
  V3  HO9 instruction-payload containment across generations (powered held-out set)
  V4  Lineage recovery conditions A / B / C1 / C2 / C3: recovery and false association
  V5  Gap 1: claim-level provenance (PCL) vs B13 on explicit attacks, and the benign cost
  V6  Gap 3 information boundary: implicit detection vs legitimate-rule false positives per information condition
  V7  Gap 3 two-stage defence: unconfirmed activation and legitimate-rule use
  V8  Operational closure after v6 (frozen rubric)
  V9  v6 defence architecture with each component's evaluated status
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "phase17" / "data" / "defence_v6"
OUT = ROOT / "docs" / "figures" / "v6"
COL = {"FG": "#8c8c8c", "ND": "#bcbd22", "RCL": "#1f77b4", "CTC": "#ff7f0e", "PRC": "#2ca02c", "RAR": "#e377c2",
       "RAR-B": "#9467bd", "B13s": "#8c8c8c", "PAB13": "#17becf", "PCL": "#2ca02c", "ITEM": "#ff7f0e"}


def L(name):
    p = DATA / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _plt():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9})
    return plt


def _r(x):
    return 100 * x["k"] / x["n"] if x and x.get("n") else 0.0


def _save(fig, name):
    p = OUT / name
    fig.savefig(p, dpi=170)
    import matplotlib.pyplot as plt
    plt.close(fig)
    return p


def v1_provenance():
    d = L("g1_eval.json")
    st = L("sa6_mem0_stage.json")
    if not d or not st:
        return None
    plt = _plt()
    forced = [x for v in st["items"].values() for x in v.get("forced_update") or []]
    n = len(forced)
    native_ok = sum(x["native_src_after"] != "user" for x in forced)
    ledger_ok = sum(x["ledger_untrusted_after"] for x in forced)
    hist = sum(any(h.get("role") or h.get("actor_id") for h in x["native_history"]) for x in forced)
    pv = d["provenance"]
    labels = ["Channel correct\nafter ADD (eval)", "Document source kept\nafter forced UPDATE", "Writer in native\nhistory rows"]
    nat = [100 * pv["native_src_correct"] / pv["derived_memories"], 100 * native_ok / n, 100 * hist / n]
    led = [100 * pv["ledger_channel_correct"] / pv["derived_memories"], 100 * ledger_ok / n, 100.0]
    fig, ax = plt.subplots(figsize=(7.2, 3.5))
    x = range(3)
    ax.bar([i - 0.18 for i in x], nat, 0.36, label="Mem0 native", color="#d62728")
    ax.bar([i + 0.18 for i in x], led, 0.36, label="PL ledger (application-level)", color="#2ca02c")
    for i, (a, b) in enumerate(zip(nat, led)):
        ax.text(i - 0.18, a + 2, f"{a:.0f}%", ha="center", fontsize=8)
        ax.text(i + 0.18, b + 2, f"{b:.0f}%", ha="center", fontsize=8)
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels)
    ax.set_ylim(0, 115)
    ax.set_ylabel("% of memories")
    ax.set_title(f"Provenance through Mem0 2.0.19 ({pv['derived_memories']} eval memories; forced UPDATE on {n}; "
                 f"natural UPDATEs: {pv['natural_update_events']})", fontsize=8.5)
    ax.legend(fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=2)
    fig.tight_layout()
    return _save(fig, "V1_provenance_mem0.png")


def v2_fingerprints():
    d = L("fpb_eval.json")
    if not d:
        return None
    plt = _plt()
    arms = ["digest_only", "sem_only(0.5)", "nli_only(0.00474)", "HFP", "HFP-B"]
    lab = ["Digest", "Similarity", "NLI only", "HFP (pre-reg.,\nfailing)", "HFP-B\n(addendum A)"]
    m = [("carry_recall", "Recall (payload-carrying)", "#2ca02c"), ("benign_overlap", "False match: benign same-subject", "#d62728"),
         ("neg_action_match", "Match: negation / action change", "#ff7f0e")]
    fig, ax = plt.subplots(figsize=(8, 3.8))
    for j, (k, name, c) in enumerate(m):
        vals = [100 * d["arms"][a]["all"][k]["rate"] for a in arms]
        ax.bar([i + (j - 1) * 0.26 for i in range(len(arms))], vals, 0.26, label=name, color=c)
    ax.set_xticks(range(len(arms)))
    ax.set_xticklabels(lab, fontsize=8)
    ax.set_ylabel("%")
    ax.set_ylim(0, 105)
    ax.set_title(f"Claim fingerprints on held-out FPB ({d['n_eval_roots']} HO9 roots x 8 transformations)", fontsize=9)
    ax.legend(fontsize=7.5, loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=3)
    fig.tight_layout()
    return _save(fig, "V2_fingerprints.png")


def v3_containment():
    d = L("g2_eval.json")
    if not d:
        return None
    plt = _plt()
    b = d["by_payload"]["instruction"]
    fig, ax = plt.subplots(figsize=(7.4, 3.8))
    for a in ("FG", "ND", "RCL", "CTC", "PRC", "RAR", "RAR-B"):
        ys = [_r(x) for x in b[a]["withheld_carrying"]]
        ax.plot([1, 2, 3, 4], ys, marker="o", label=a, color=COL[a], lw=2.2 if a in ("PRC", "FG") else 1.2)
    ax.axhline(60, ls="--", color="black", lw=0.8)
    ax.text(3.35, 64, "pre-registered bar (60%)", fontsize=7)
    ax.set_xticks([1, 2, 3, 4])
    ax.set_xlabel("Consolidation generation")
    ax.set_ylabel("% payload-carrying descendants withheld")
    ax.set_ylim(0, 100)
    ax.set_title(f"HO9 instruction payloads ({b['n_flagged_roots']} flagged roots; gen-4 carrying n = "
                 f"{b['carry'][3]['k']}); PRC vs FG at gen 4: p = {d['holm_C2_instruction']['PRC']:.1e} (Holm)", fontsize=8.5)
    ax.legend(fontsize=7.5, ncol=7, loc="upper center", bbox_to_anchor=(0.5, -0.17))
    fig.tight_layout()
    return _save(fig, "V3_containment_ho9.png")


def v4_recovery():
    d = L("g2_eval.json")
    w = L("g2_wtp_check.json")
    if not d or not w:
        return None
    plt = _plt()
    r = d["recovery_HFP-B"]
    conds = ["A: present", "B: never persisted", "C1: deleted,\nlog intact", "C2: deleted +\nrewritten (sim.)", "C3: total loss\n(reference)"]
    keyc = ["A_lineage_present", None, "C1_deleted_log_intact", "C2_deleted_then_rewritten_SIMULATION", "C3_total_loss_reference"]
    wh = []
    for k in keyc:
        if k is None:
            wh.append(_r(w["withheld_carrying_g4"]))
        else:
            v = [x for kk, x in r[k].items() if kk.startswith("withheld_carrying_g4")][0]
            wh.append(_r(v))
    rec = [0, 0, _r(r["C1_deleted_log_intact"]["recovery_correct_g4"]),
           _r(r["C2_deleted_then_rewritten_SIMULATION"]["recovery_correct_g4"]), _r(r["C3_total_loss_reference"]["recovery_correct_g4"])]
    fa = [0, 0, _r(r["C1_deleted_log_intact"]["false_association_owner_store"]),     # A/B: nothing to recover
          _r(r["C2_deleted_then_rewritten_SIMULATION"]["false_association_owner_store"]),
          _r(r["C3_total_loss_reference"]["collateral_owner_store"])]
    fig, ax = plt.subplots(figsize=(8.4, 3.9))
    x = range(5)
    ax.bar([i - 0.27 for i in x][2:], rec[2:], 0.27, label="Correct root recovered", color="#2ca02c")
    ax.bar(list(x)[2:], fa[2:], 0.27, label="Owner memories falsely associated (C3: owner memories withheld)", color="#d62728")
    for i in (0, 1):
        ax.text(i - 0.27, 40, "recovery\nn/a\n(lineage\navailable)", fontsize=6.5, ha="center")
    ax.bar([i + 0.27 for i in x], wh, 0.27, label="Gen-4 carrying withheld (HFP-B decision)", color="#9467bd")
    ax.axhline(5, ls="--", color="black", lw=0.7)
    ax.set_xticks(list(x))
    ax.set_xticklabels(conds, fontsize=7.5)
    ax.set_ylim(0, 110)
    ax.set_ylabel("%")
    ax.set_title("Lineage recovery on HO9 (296 flagged attack chains; conditions never pooled)", fontsize=9)
    ax.legend(fontsize=7, loc="upper center", bbox_to_anchor=(0.5, -0.24), ncol=3)
    fig.tight_layout()
    return _save(fig, "V4_lineage_recovery.png")


def v5_gap1():
    d = L("g1_eval.json")
    if not d:
        return None
    plt = _plt()
    s, m = d["single_notes"], d["msd"]
    fig, ax = plt.subplots(1, 2, figsize=(9, 3.2))
    sets = [("Explicit, single\nnotes (48)", s["atk_explicit"]), ("Explicit, mixed-\nsource docs (48)", m["explicit"]),
            ("Implicit, single\nnotes (48)", s["atk_implicit"])]
    for j, a in enumerate(("B13s", "ITEM", "PCL")):
        ax[0].bar([i + (j - 1) * 0.26 for i in range(3)], [_r(v[a]) for _, v in sets], 0.26, label=a, color=COL[a])
    ax[0].set_xticks(range(3))
    ax[0].set_xticklabels([n for n, _ in sets], fontsize=7.5)
    ax[0].set_title("Attacks excluded (%)")
    ax[0].set_ylim(0, 100)
    ax[0].legend(fontsize=7)
    groups = [("Ungrounded legit\n(144, pooled)", s["pooled_ungrounded"]), ("Grounded legit (48)", s["pooled_grounded"]),
              ("Benign memories in\nmixed docs (250)", m["benign_derived_memories"])]
    for j, a in enumerate(("B13s", "PAB13", "PCL")):
        ax[1].bar([i + (j - 1) * 0.26 for i in range(3)], [_r(v[a]) for _, v in groups], 0.26, label=a, color=COL[a])
    ax[1].axhline(10, ls="--", color="black", lw=0.7)
    ax[1].set_xticks(range(3))
    ax[1].set_xticklabels([n for n, _ in groups], fontsize=7.5)
    ax[1].set_title("Legitimate memories excluded (%)")
    ax[1].set_ylim(0, 60)
    ax[1].legend(fontsize=7)
    fig.tight_layout()
    return _save(fig, "V5_gap1_claim_level.png")


def v6_boundary():
    d = L("g3_eval.json")
    if not d:
        return None
    plt = _plt()
    order = ["A_original_text", "B_transformed", "C_metadata", "C&K_metadata+stored", "D_original_record",
             "E_validated_lineage", "F_provenance+counterfactual_activation", "S_SIMULATION_authenticated_principal"]
    lab = ["A original\ntext", "B trans-\nformed", "C meta-\ndata", "C + K\nstored", "D original\nrecord", "E validated\nlineage",
           "F prov. +\nactivation", "S authent.\n(simulation)"]
    c = d["conditions"]
    det = [_r(c[k]["implicit"]) for k in order]
    fp = [_r(c[k]["ungrounded_pooled"]) for k in order]
    gp = [_r(c[k]["grounded_pooled"]) for k in order]
    fig, ax = plt.subplots(figsize=(9, 3.4))
    x = range(len(order))
    ax.bar([i - 0.27 for i in x], det, 0.27, label="Implicit sleepers detected", color="#2ca02c")
    ax.bar(list(x), fp, 0.27, label="Ungrounded legit flagged", color="#d62728")
    ax.bar([i + 0.27 for i in x], gp, 0.27, label="Grounded legit flagged", color="#ff7f0e")
    ax.axhline(10, ls="--", color="black", lw=0.7)
    ax.axhline(50, ls=":", color="black", lw=0.7)
    ax.set_xticks(list(x))
    ax.set_xticklabels(lab, fontsize=7)
    ax.set_ylim(0, 105)
    ax.set_ylabel("%")
    ax.set_title(f"Information boundary on SA-6 eval (K = {d['K']}; operating point {d['operating_point']})", fontsize=9)
    ax.legend(fontsize=7, loc="upper left")
    fig.tight_layout()
    return _save(fig, "V6_information_boundary.png")


def v7_two_stage():
    d = L("g3_eval.json")
    if not d:
        return None
    plt = _plt()
    b = d["behaviour"]
    arms = ["stored", "F2s", "TS", "TSX"]
    lab = ["Undefended\n(stored)", "Frame on\nstored text", "Two-stage\n(restore + frame)", "Withhold\n(TS-X)"]
    imp = [_r(b["atk_implicit"][a]["unconfirmed_activation"]) for a in arms]
    exp = [_r(b["atk_explicit"][a]["unconfirmed_activation"]) for a in arms]
    leg = [_r(b["legit_untrusted_surfaced"][a]) for a in arms]
    fig, ax = plt.subplots(figsize=(8, 3.3))
    x = range(4)
    ax.bar([i - 0.27 for i in x], imp, 0.27, label="Implicit: unconfirmed activation", color="#d62728")
    ax.bar(list(x), exp, 0.27, label="Explicit: unconfirmed activation", color="#ff7f0e")
    ax.bar([i + 0.27 for i in x], leg, 0.27, label="Legit (document/missing channel): used or offered", color="#2ca02c")
    ax.set_xticks(list(x))
    ax.set_xticklabels(lab, fontsize=8)
    ax.set_ylabel("%")
    ax.set_ylim(0, 100)
    ax.set_title("Two-stage sleeper defence on Mem0-stored SA-6 eval memories (trigger message)", fontsize=9)
    ax.legend(fontsize=7, loc="upper right")
    fig.tight_layout()
    return _save(fig, "V7_two_stage.png")


def v8_closure():
    d = L("closure_v6.json")
    if not d:
        return None
    plt = _plt()
    gaps = list(d["gaps"])
    before = [100 * d["gaps"][g]["before"] for g in gaps]
    after = [100 * d["gaps"][g]["after"] for g in gaps]
    fig, ax = plt.subplots(figsize=(7, 3))
    x = range(len(gaps))
    ax.bar([i - 0.18 for i in x], before, 0.36, label="Before v6", color="#8c8c8c")
    ax.bar([i + 0.18 for i in x], after, 0.36, label="After v6", color="#2ca02c")
    for i, (a, b) in enumerate(zip(before, after)):
        ax.text(i - 0.18, a + 1.5, f"{a:.0f}%", ha="center", fontsize=8)
        ax.text(i + 0.18, b + 1.5, f"{b:.0f}%", ha="center", fontsize=8)
    ax.axhline(75, ls="--", color="black", lw=0.8)
    ax.text(-0.45, 76.5, "aspirational 75%", fontsize=7)
    ax.set_xticks(list(x))
    ax.set_xticklabels([g.split(": ")[1] if ": " in g else g for g in gaps], fontsize=8)
    ax.set_ylim(0, 100)
    ax.set_ylabel("Operational closure (%)")
    ax.set_title("Evidence-based closure under the frozen rubric (no combined score)", fontsize=9)
    ax.legend(fontsize=8)
    fig.tight_layout()
    return _save(fig, "V8_closure_v6.png")


def v9_architecture():
    plt = _plt()
    from matplotlib.patches import FancyBboxPatch

    g3 = L("g3_eval.json")
    ts_ok = bool(g3 and g3["behaviour"]["P1_acceptance"]["accepted"])
    stages = [
        ("Write: PL ledger", "source event per add\nchannel, digest, original\n(union; not authenticated)", "#c7e9c0"),
        ("Mem0 extraction", "ADD-only in infer mode\nmetadata last-writer-wins\non API update()", "#eeeeee"),
        ("Admission: PCL", "FLV-validated links\nclaim-level B12 inheritance\nPAB13 (corroboration)", "#fdd0a2"),
        ("Propagation: PRC", "powered: beats FG (p=5e-4)\n58.9% < 60% bar\nlog recovery C1 exact", "#fdd0a2"),
        ("Retrieval: TS", "restore original rule\n+ unverified frame\n(user channel untouched)", "#c7e9c0" if ts_ok else "#fdd0a2"),
        ("Agent", "answers; asks before\nacting on unverified\nrules", "#eeeeee")]
    fig, ax = plt.subplots(figsize=(10, 2.7))
    ax.axis("off")
    w, gap = 1.45, 0.25
    for i, (t, n, c) in enumerate(stages):
        x = i * (w + gap)
        ax.add_patch(FancyBboxPatch((x, 0.6), w, 1.5, boxstyle="round,pad=0.04", fc=c, ec="black", lw=0.8))
        ax.text(x + w / 2, 1.8, t, ha="center", va="center", fontsize=8, weight="bold")
        ax.text(x + w / 2, 1.05, n, ha="center", va="center", fontsize=6.2)
        if i < len(stages) - 1:
            ax.annotate("", xy=(x + w + gap, 1.35), xytext=(x + w, 1.35), arrowprops=dict(arrowstyle="->"))
    ax.text(0, 2.55, "green = accepted within scope;  orange = partial (some pre-registered criteria missed);  grey = not a "
                     "defence stage", fontsize=7)
    ax.text(0, 0.05, "Open: authenticated writer identity; recovery after post-deletion rewrite; legitimate rules arriving "
                     "through untrusted channels", fontsize=7, color="#a50f15")
    ax.set_xlim(-0.1, 6 * (w + gap))
    ax.set_ylim(0, 2.8)
    fig.tight_layout()
    return _save(fig, "V9_architecture_v6.png")


def run() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    made = {}
    for k, fn in (("V1", v1_provenance), ("V2", v2_fingerprints), ("V3", v3_containment), ("V4", v4_recovery),
                  ("V5", v5_gap1), ("V6", v6_boundary), ("V7", v7_two_stage), ("V8", v8_closure), ("V9", v9_architecture)):
        p = fn()
        made[k] = str(p.relative_to(ROOT)) if p else None
    (OUT / "index.json").write_text(json.dumps(made, indent=1), encoding="utf-8")
    return made


if __name__ == "__main__":
    print(json.dumps(run(), indent=1))
