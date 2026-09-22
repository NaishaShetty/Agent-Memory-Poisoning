"""Generates Figure 16 (Phase 12 — Security Metrics real results) and
Figure 17 (Phase 13 — Attribution Metrics real results) for the MAMBench
methodology draft, from the real, already-measured numbers in
docs/phase12/PHASE12_SECURITY_METRICS_REPORT.md and
docs/phase13/PHASE13_ATTRIBUTION_METRICS_REPORT.md. No numbers here are
invented -- every value below is copied from those reports' own real,
computed results.
"""

import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

os.makedirs("docs/figures", exist_ok=True)

# ---------------------------------------------------------------------------
# Figure 16 -- Phase 12: real PR (Propagation Rate) across 2 real local models
# x 3 real distractor sets (6 independent real trials), plus the Consolidation
# Guard's real catch rate in each of those same 6 trials.
# ---------------------------------------------------------------------------

distractor_sets = ["Set 1\n(Gina/Jon)", "Set 2\n(Jolene/Deborah)", "Set 3\n(Calvin/Dave)"]
llama2_pr = [91.7, 83.3, 73.3]
qwen_pr = [95.0, 81.7, 91.7]
grand_mean = 86.1
guard_catch_rate = [100.0, 100.0, 100.0]  # 100% catch rate in all 6 real trials (both models)

fig, axes = plt.subplots(1, 2, figsize=(13, 5))

ax = axes[0]
x = np.arange(len(distractor_sets))
width = 0.35
ax.bar(x - width / 2, llama2_pr, width, label="llama2:7b", color="#4C72B0")
ax.bar(x + width / 2, qwen_pr, width, label="qwen2.5:7b", color="#DD8452")
ax.axhline(grand_mean, color="#555555", linestyle="--", linewidth=1.5, label=f"Grand mean = {grand_mean}%")
ax.set_ylim(0, 105)
ax.set_ylabel("Propagation Rate (PR), %")
ax.set_xticks(x)
ax.set_xticklabels(distractor_sets)
ax.set_title("(a) Real PR across 2 models x 3 distractor sets\n(6 independent real trials)")
ax.legend(loc="lower right", fontsize=9)
for i, v in enumerate(llama2_pr):
    ax.text(i - width / 2, v + 1.5, f"{v}", ha="center", fontsize=9)
for i, v in enumerate(qwen_pr):
    ax.text(i + width / 2, v + 1.5, f"{v}", ha="center", fontsize=9)

ax = axes[1]
ax.bar(distractor_sets, guard_catch_rate, color="#55A868")
ax.set_ylim(0, 110)
ax.set_ylabel("Consolidation Guard catch rate, %")
ax.set_title("(b) Real Consolidation Guard catch rate of\nreal (unguarded) PR propagation events")
for i, v in enumerate(guard_catch_rate):
    ax.text(i, v + 2, f"{v}%", ha="center", fontsize=9)

fig.suptitle("Figure 16 — Phase 12 Real Results: Propagation Rate and the Consolidation Guard", fontsize=13, fontweight="bold")
fig.tight_layout(rect=[0, 0, 1, 0.93])
fig.savefig("docs/figures/figure16_phase12_results.png", dpi=150)
plt.close(fig)

# ---------------------------------------------------------------------------
# Figure 17 -- Phase 13: real attribution accuracy metrics (all 100%), the
# real lineage ambiguity rate, and the real, weak confidence-correlation
# result at two resolutions.
# ---------------------------------------------------------------------------

fig, axes = plt.subplots(1, 2, figsize=(13, 5))

ax = axes[0]
metrics = [
    "Source\naccuracy\n(15/15)", "Path fidelity\n(19/19)", "Influence\naccuracy\n(6/6)",
    "Propagation\nreconstruction\n(19/19)", "Guard trace\nQUARANTINE\n(14/14)", "Guard trace\nALLOW\n(4/4)",
]
values = [100.0, 100.0, 100.0, 100.0, 100.0, 100.0]
bars = ax.bar(metrics, values, color="#4C72B0")
ax.set_ylim(0, 115)
ax.set_ylabel("Accuracy, %")
ax.set_title("(a) Real attribution accuracy across all measured checks")
for b, v in zip(bars, values):
    ax.text(b.get_x() + b.get_width() / 2, v + 2, f"{v:.0f}%", ha="center", fontsize=9)
ax.tick_params(axis="x", labelsize=8)

ax = axes[1]
ax2 = ax.twinx()
amb_labels = ["Lineage\nambiguity rate"]
amb_values = [21.1]
ax.bar(amb_labels, amb_values, color="#C44E52", width=0.5)
ax.set_ylim(0, 100)
ax.set_ylabel("Lineage ambiguity rate, %", color="#C44E52")
ax.tick_params(axis="y", labelcolor="#C44E52")
for i, v in enumerate(amb_values):
    ax.text(i, v + 3, f"{v}%\n(4/19 real\nmulti-source)", ha="center", fontsize=9)

corr_labels = ["r (banded)", "r (raw signals)"]
corr_values = [-0.113, -0.106]
xpos = np.arange(len(corr_labels)) + 1.0
ax2.bar(xpos, corr_values, color="#8172B2", width=0.5)
ax2.set_ylim(-0.3, 0.3)
ax2.axhline(0, color="#555555", linewidth=1)
ax2.set_ylabel("Pearson r (confidence correlation)", color="#8172B2")
ax2.tick_params(axis="y", labelcolor="#8172B2")
for i, v in enumerate(corr_values):
    ax2.text(xpos[i], v - 0.04, f"{v}", ha="center", fontsize=9, color="#8172B2")

all_xpos = list(range(len(amb_labels))) + list(xpos)
all_labels = amb_labels + corr_labels
ax.set_xticks(all_xpos)
ax.set_xticklabels(all_labels, fontsize=9)
ax.set_title("(b) Real ambiguity rate and confidence-correlation results\n(both weak/negative, root-caused — see Section 28.5)")

fig.suptitle("Figure 17 — Phase 13 Real Results: Attribution Accuracy, Ambiguity, and Confidence Correlation", fontsize=13, fontweight="bold")
fig.tight_layout(rect=[0, 0, 1, 0.93])
fig.savefig("docs/figures/figure17_phase13_results.png", dpi=150)
plt.close(fig)

print("Saved docs/figures/figure16_phase12_results.png and figure17_phase13_results.png")
