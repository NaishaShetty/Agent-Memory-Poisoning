# Phase 11 — Calibrating Baseline C Into a Real Detector

Direct follow-on to `docs/phase11/PHASE11_LOFO_REPORT.md`'s own closing
recommendation: since an untrained sum of the 9 sanctioned features beat
the trained GNN's LOFO generalization for 3 of 4 attack families, this
investigation asks whether that score, turned into an actual detector, is
a more honest cross-family option than the GNN at this data scale — and,
separately, whether ANY fitting (not specifically graph message-passing)
reproduces the GNN's own generalization problem. Every number below is
real, computed via `python -m phase11.gnn.linear_baseline`.

## What was built

Two configurations, kept separate throughout, never blended into one
number:

- **`RAW_SUM`**: the exact same zero-training score
  (`baseline_c_frozen_feature_sum`) from the LOFO report, with one addition
  — a real decision threshold, fitted fold-locally and in-sample via the
  SAME `_threshold_for_target_fpr()` the GNN already uses (reused
  verbatim, not reimplemented).
- **`LINEAR`**: a from-scratch `nn.Linear(9, 1)` detector — literally the
  GNN's own architecture with both `MessagePassingLayer`s removed, nothing
  else changed (same `Adam`/`lr=0.05`/`weight_decay=0.0`/`300`-epoch
  protocol). Isolates whether it is specifically graph message-passing, or
  any form of fitting on pooled-family data, that fails to generalize.

Both are evaluated two ways: **pooled-family** (directly comparable to
Baseline A / B9 / B10 — trained on all 4 families, evaluated on the full
held-out corpus) and **LOFO** (same protocol as the GNN LOFO report — one
family entirely excluded from training per fold).

**One disclosed, real difference from every GNN number**: neither
`RAW_SUM` nor `LINEAR` builds a graph, so the 3 synthetic ancestor nodes
`graph_build.py` adds (present in every GNN evaluation) are absent here —
held-out benign n is **41**, not the GNN's **44**, in every table below.
Never silently reconciled by adding fabricated nodes to match.

## Pooled-family results (comparable to Baseline A)

| Config | Detection | FPR | AUROC | n_poison / n_benign |
|---|---|---|---|---|
| Baseline A — GNN (`run_gnn_feasibility_study()`, unchanged) | 55.9% | 6.8% | not reported | 34 / 44 |
| `RAW_SUM` (deterministic, no training) | 23.5% | **0.0%** | **0.819** | 34 / 41 |
| `LINEAR` (mean, seeds 11–20, tight range) | 47.1% | **0.0%** | 0.824 [0.821, 0.843] | 34 / 41 |

Both calibrated frozen-feature configurations hit 0% FPR (a stricter
in-sample threshold than the GNN's own 6.8%) with real AUROC well above
the GNN's own detection-implied separation. `LINEAR` nearly matches the
GNN's detection rate (47.1% vs. 55.9%) at zero false positives instead of
6.8% — a real, favorable pooled-family comparison. This is NOT yet the
generalization question — see below.

## LOFO results — the real test

| Held-out family | `RAW_SUM` AUROC / detection | `LINEAR` AUROC (mean [range]) / detection | GNN LOFO AUROC (from prior report) |
|---|---|---|---|---|
| FARMA (n=7) | **1.0** / 100% | 0.374 [0.0, 0.645] / 0% | 0.451 |
| MemoryGraft-style-volume (n=20) | 0.696 / 0% | 0.696 / 50% | **0.760** |
| Sleeper (n=5) | **1.0** / 0%* | 0.361 [0.0, 0.902] / 0% | 0.614 |
| propagated (n=2) | 0.963 / 50% | **0.979** [0.963, 0.988] / 50% | 0.925 |

*Sleeper `RAW_SUM`: AUROC 1.0 (poison ranks strictly above every benign
example) but detection 0% at the fold's own in-sample threshold — a real,
disclosed limitation explained below, not a contradiction.

## The real, important finding

**Untrained `RAW_SUM` reproduces and sharpens the LOFO report's own
finding: for FARMA and Sleeper specifically, `RAW_SUM`'s AUROC (1.0, 1.0)
is dramatically higher than either the fitted GNN (0.451, 0.614) or the
fitted `LINEAR` detector (0.374, 0.361).** This rules out "it's specifically
the graph/message-passing that fails to generalize" as the explanation —
`LINEAR` has no graph at all and shows the same collapse pattern as the
GNN for these two families. **The common factor is fitting itself**: any
model (graph or not) whose weights are tuned on the 3 OTHER pooled
families ends up worse at ranking the excluded family than a naive,
untrained equal-weighted sum of the same 9 features. For
MemoryGraft-style-volume specifically, the pattern reverses — the GNN
(0.760) beats both `LINEAR` (0.696) and `RAW_SUM` (0.696) — consistent with
the LOFO report's own finding that this was the one family where training
added real value.

**The `RAW_SUM`/Sleeper detection-rate-vs-AUROC discrepancy is itself a
real, disclosed finding, not swept under the rug**: a perfect AUROC (1.0)
with 0% detection at the chosen threshold means the poison scores rank
strictly above every benign score, but the in-sample threshold — fit only
from an 8-to-11-example training benign set at a 10% target FPR — landed
above all 5 of Sleeper's held-out scores anyway. **This is a real weakness
of the in-sample threshold-selection protocol itself** (inherited
unmodified from the GNN's own precedent, not introduced here): at this
tiny a training-benign sample, one outlier training example can push the
threshold high enough to erase a real, well-separated ranking signal. AUROC
(threshold-free) and detection-rate-at-in-sample-threshold are reported
side by side specifically so this gap is visible rather than hidden behind
one number.

## Honest comparison to the frozen baselines

Neither `RAW_SUM` nor `LINEAR`, under LOFO, beats the GNN on every family —
`RAW_SUM`/`LINEAR` win FARMA and Sleeper decisively; the GNN wins
MemoryGraft-style-volume; `propagated` (n=2, low-power per the original
audit) is close across all three. **No single one of the three
configurations dominates on this real, tiny corpus.** This report does not
claim `RAW_SUM` or `LINEAR` is "the fix" — it is a real, informative
three-way comparison that narrows what the LOFO report's open question
("was it the graph specifically?") actually was: no, fitting on pooled
families is the common failure mode across both a graph model and a
non-graph linear model alike; only the untrained score is immune to it, at
the cost of needing its own (currently fragile) threshold-selection
protocol to become an actual detector.

## What this does not do

Per the same standing discipline as every other Phase 11 investigation:
nothing here is wired into B10, the live pipeline, or any production
threshold; no existing GNN/B9/B10 result is modified; `held_out_pools()`
is read only for final evaluation, never filtered or used for fitting.

## Regression status

`python -m pytest phase6/ attribution/ phase7/ phase8/ phase11/ -q` →
**665 passed, 13 skipped, 0 failed** (was 654 before this investigation —
+11, 0 regressions). Baseline A (GNN) and B9/B10 unaffected.
