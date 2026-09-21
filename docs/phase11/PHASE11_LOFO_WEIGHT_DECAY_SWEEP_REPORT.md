# Phase 11 — Weight Decay, Re-Swept Against the LOFO Objective

Direct answer to "I want the GNN to work properly": the original
weight-decay sweep (`train.py`'s own docstring) tested regularization only
against the pooled-family held-out metric and found it made things worse.
That is a different question than "does regularization fix
family-generalization" — this report tests the latter, for the first time,
using the exact same leakage-safe LOFO harness already audited and built.
Every number below is real, computed via
`python -m phase11.gnn.lofo_weight_decay_sweep` (single, additive,
backward-compatible `weight_decay` parameter threaded through
`train_model()`/`run_lofo_fold()`; every pre-existing call site and test
confirmed byte-for-byte unchanged).

## Macro AUROC (unweighted mean across the 4 families) by weight_decay

| weight_decay | Macro AUROC |
|---|---|
| 0.0 (shipped default) | 0.687 |
| 0.001 | 0.757 |
| **0.005** | **0.774 (peak)** |
| 0.01 | 0.769 |
| 0.02 | 0.751 |
| 0.05 | 0.638 |

**Real, measured finding: moderate regularization (0.001–0.02) genuinely
improves cross-family generalization** over the shipped `weight_decay=0.0`
default — the opposite conclusion from the original, differently-scoped
sweep. Peak at 0.005 (+0.087 macro AUROC over shipped). Too much (0.05)
overcorrects and gets worse than the default.

## Per-family detail (weight_decay = 0.0 vs. 0.005, the peak)

| Family | AUROC mean [range] @ 0.0 | AUROC mean [range] @ 0.005 | Detection mean @ 0.0 | Detection mean @ 0.005 |
|---|---|---|---|---|
| FARMA | 0.451 [0.169, 0.854] | 0.488 [0.409, 0.571] | 32.9% | **0.0%** |
| MemoryGraft-style-volume | 0.760 [0.689, 0.909] | **0.819** [0.751, 0.922] | 89.5% | 50.0% |
| Sleeper | 0.614 [0.295, 0.932] | **0.789** [0.705, 0.864] | 60.0% | **0.0%** |
| propagated | 0.925 [0.500, 1.000] | **1.000 [1.000, 1.000]** | 100.0% | 100.0% |

Two real effects, both genuine, pulling in different directions:

1. **Seed variance collapses dramatically.** FARMA's range shrinks from
   0.69-wide to 0.16-wide; Sleeper's from 0.64-wide to 0.16-wide;
   propagated locks to exactly 1.0 on every one of the 10 seeds (was
   [0.5, 1.0]). This directly attacks the seed-instability problem
   `PHASE11_REPORT.md` §2 already disclosed for the pooled-family model —
   regularization stabilizes the LOFO result the same way.
2. **AUROC (ranking quality) improves for 3 of 4 families** —
   MemoryGraft-style-volume, Sleeper, and propagated all rank better with
   moderate weight decay than without it.

**But detection rate at the existing in-sample threshold gets WORSE for
FARMA and Sleeper — both drop to 0%, despite better AUROC.** This is the
same threshold-selection fragility `PHASE11_LOFO_BASELINE_C_REPORT.md`
already disclosed for `RAW_SUM`/Sleeper: regularizing the model pulls its
score distribution narrower, and the in-sample threshold — fit from an
8-to-11-example training-benign set at a fixed 10%-target FPR — ends up
sitting above nearly every held-out poison score even when the underlying
ranking (AUROC) is good. **Regularization fixes the model's ranking; it
does not fix the threshold-selection protocol, and at this data scale the
second problem is now the binding constraint on detection rate.**

FARMA remains the one family that does not meaningfully improve on any
axis at any weight_decay tested (AUROC stays in the 0.44–0.50 band
throughout the sweep) — a real, disclosed limit of this lever specifically
for this family, not resolved by regularization at any strength tried.

## What this establishes, and what it does not

**Establishes**: weight decay was prematurely ruled out for the wrong
reason — it does help family-generalization specifically, for 3 of 4
families, once tested against the right objective. This is a real,
positive, actionable finding.

**Does not establish**: that the GNN is now "fixed." Two real, separate
problems remain even at the best weight_decay found: (1) FARMA does not
generalize under any setting tried, and (2) the in-sample threshold
protocol itself becomes the bottleneck once ranking improves — a
regularized model with good AUROC but a threshold that misses every
positive is not yet a working detector. Fixing (2) (e.g. a less
training-set-fragile threshold rule) is the next concrete, scoped
follow-on this report identifies but does not attempt.

## Regression status

`python -m pytest phase6/ attribution/ phase7/ phase8/ phase11/ -q` →
**672 passed, 13 skipped, 0 failed** (was 665 before this sweep — +7, 0
regressions). `run_gnn_feasibility_study()` (shipped `weight_decay=0.0`
default) and B9/B10 reconfirmed byte-for-byte unchanged.
