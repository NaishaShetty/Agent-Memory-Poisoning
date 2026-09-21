# Phase 11 — GNN Leave-One-Attack-Family-Out Generalization Report

Written after every real number below was actually computed, per this
project's own "never write the conclusion first" discipline. Every command
below can be re-run directly (`python -m phase11.gnn.lofo`). The audit this
report follows from is `docs/phase11/PHASE11_LOFO_AUDIT.md`, written and
internally reviewed before any fold was trained.

## A. Research question

*"Does the Phase 11 GNN generalize to an attack family that was completely
excluded from its training data?"*

## B. Protocol

For each of the 4 families the GNN's own real corpus actually contains
(`FARMA`, `MemoryGraft-style-volume`, `Sleeper`, `propagated` — see Audit §1
for why this is not the 7-attack Phase 4 taxonomy):

1. Remove every poison scenario belonging to that family from
   `split.all_dev_pools()` (benign scenarios and other-family poison
   scenarios untouched).
2. Train a fresh `MinimalGNN` (frozen architecture, frozen hyperparameters —
   `hidden_dim=8`, `num_layers=2`, `WEIGHT_DECAY=0.0`, `EPOCHS=300`,
   unchanged from `phase11/gnn/train.py`) on the filtered pools, once per
   seed in `range(11, 21)` — the same 10-seed protocol the original
   stability study used.
3. Select the decision threshold fold-locally, in-sample, on that SAME
   filtered training set (`_threshold_for_target_fpr`, target FPR 10% —
   unmodified from the original implementation).
4. Evaluate on the real, unmodified `held_out_pools()` (never filtered),
   restricting the reported poison side to the excluded family's own
   held-out examples, and the benign side to the full shared 44-node
   reference.

Architecture, feature contract, threshold-selection function, and
`held_out_pools()` itself are all reused byte-for-byte from the existing,
frozen Phase 11.2 implementation — nothing about them was changed to run
this experiment.

## C. Leakage audit summary

Full detail in `PHASE11_LOFO_AUDIT.md`. Headline finding: **this
architecture has no fitted normalization, no PCA, no early stopping, and no
family-identity input at all** — the only leakage path that exists is
"does the excluded family's data appear in the `pools` object passed into
`build_dataset()`." A single filter at that point, applied before every
downstream stage, is sufficient — confirmed by tracing every stage
(features, threshold, model init, graph construction), not assumed.
Verified directly by 16 new tests (`test_gnn_lofo.py`), including a
structural check that no excluded-family scenario id ever appears in a
fold's `train_ds.node_ids`.

## D. Dataset composition

| Held-out family | Train poison families (n excluded / n remaining) | Held-out n | Unique poison-bearing pools (train / held-out) | Power classification |
|---|---|---|---|---|
| FARMA | 6 excluded / 9 remaining | 7 | 1 / 2 | Interpretable |
| MemoryGraft-style-volume | 6 excluded / 9 remaining | 20 | 2 / 2 | Interpretable |
| Sleeper | 1 excluded / 14 remaining | 5 | 1 / 2 | Low-power (training-exclusion side: only 1 example is ever removed) |
| propagated | 2 excluded / 13 remaining | 2 | 1 / 1 | Low-power / descriptive-only |

Benign reference (shared, unaffected by family choice): 44 held-out nodes
(41 real scenarios + 3 synthetic ancestor nodes, matching
`test_gnn_held_out_split_is_the_real_corpus_size`'s locked-in 78 = 34 + 44).

## E. Per-family results (10 seeds, 11–20, full distribution)

| Held-out family | n | AUROC mean [min, max] | Detection mean | FPR mean | Interpretation |
|---|---|---|---|---|---|
| FARMA | 7 | **0.451** [0.169, 0.854] | 32.9% | 44.8% | Collapses to chance (Baseline B mean 0.495) — no reliable margin above chance across any part of the seed range's lower half |
| MemoryGraft-style-volume | 20 | **0.760** [0.689, 0.909] | 89.5% | 41.4% | Well above chance (Baseline B mean 0.499) on every seed — the one family with a real, seed-stable margin |
| Sleeper | 5 | **0.614** [0.295, 0.932] | 60.0% | 38.4% | Overlaps chance's own range at this n (Baseline B mean 0.495, range [0.182, 0.823]) — mean is above chance but the seed range is not cleanly separated from it |
| propagated | 2 | **0.925** [0.500, 1.000] | 100.0% | 69.5% | High mean, but n=2 and chance's own range at this n reaches [0.045, 0.977] — not distinguishable from a lucky draw at this sample size |

Full per-seed AUROC/detection/FPR values are in the reproducible script
output (`python -m phase11.gnn.lofo`), not hand-transcribed here beyond the
summary above.

## F. Pooled out-of-fold result (SEED=11, one consistent set of 4 fold
models — see Audit §8 for why pooling is not done blindly across seeds)

| Metric | Value |
|---|---|
| Pooled detection rate (micro-averaged: total detected / total poison) | **35.3%** (12/34) |
| Macro FPR (mean of each fold's own FPR on the shared 44-node benign reference) | **23.9%** |
| Pooled AUROC (benign repeated once per fold — caveat stated, not hidden) | **0.580** |
| Macro AUROC (unweighted mean of the 4 per-family AUROCs) | **0.625** |
| Total family-poison n across folds | 34 (7+20+5+2, matches `held_out_pools()`'s full poison count exactly) |
| Total benign n per fold | 44 |
| Number of folds | 4 |

## G. Comparison

| | Detection | FPR | AUROC |
|---|---|---|---|
| **Baseline A** — original pooled-family GNN (`run_gnn_feasibility_study()`, SEED=11, re-confirmed unchanged by this investigation) | 55.9% | 6.8% | not reported as AUROC in the original study |
| **Pooled LOFO (SEED=11)** | 35.3% | 23.9% (macro) | 0.580 (pooled, benign repeated) / 0.625 (macro) |
| **Baseline B — chance**, per family (200 real random trials, same n as that family's evaluation population) | FARMA 0.495, MemoryGraft-style-volume 0.499, Sleeper 0.495, propagated 0.501 | — | mean AUROC |
| **Baseline C — frozen 9-feature sum, zero training, zero graph** | FARMA 1.0, MemoryGraft-style-volume 0.696, Sleeper 1.0, propagated 0.963 | — | AUROC |

**The single most important comparison in this report**: for 3 of 4
families (FARMA, Sleeper, propagated), the **untrained** Baseline C (a
plain sum of the same 9 raw feature values, no message passing, no
gradient descent, no fitting of any kind) scores a HIGHER AUROC than the
GNN's own LOFO mean for that family. Only for MemoryGraft-style-volume does
the trained GNN's LOFO result (0.760) exceed the frozen-feature baseline
(0.696). This is reported plainly, not softened — see Section I.

## H. Seed sensitivity

Real, shown in full (Section E's bracketed ranges), not hidden behind one
mean:

- FARMA: AUROC ranges from 0.169 to 0.854 across the 10 seeds — a 0.69-wide
  spread, the largest of any family, spanning from clearly-below-chance to
  clearly-above-chance depending on seed alone.
- MemoryGraft-style-volume: the tightest range (0.689–0.909) and the only
  family whose full range stays above the chance baseline's mean on every
  single seed.
- Sleeper: 0.295–0.932, a similarly wide spread to FARMA.
- propagated: 0.500–1.000 — at n=2, a single flipped prediction moves the
  AUROC by 0.5, which is exactly what this range shows (one seed lands
  exactly at chance).

This mirrors the same real seed-instability `PHASE11_REPORT.md` §2 already
disclosed for the pooled-family model — LOFO does not introduce a new kind
of instability, it inherits the existing one, now visible per family.

## I. Failure/success analysis

Performance **varies strongly by family** and does not degrade uniformly:

- **MemoryGraft-style-volume** is the one family where the trained GNN
  shows a real, seed-stable margin above both chance (Baseline B) and the
  untrained frozen-feature baseline (Baseline C) — the only family where
  training appears to have added something beyond raw feature summation.
- **FARMA** collapses to statistically indistinguishable from chance in
  its mean, with a seed range that straddles chance heavily — and is
  clearly beaten by the untrained Baseline C (1.0 vs. 0.451 mean).
- **Sleeper and propagated** are underpowered (n=5 and n=2 respectively);
  their means are above chance, but chance's own range at these tiny n
  overlaps enough that this report does not claim a reliable signal for
  either — both are also beaten or matched by their own untrained
  Baseline C score.

No causal claim is made about *why* — this experiment measures output
generalization, not internal representation (Audit §10). The fact that an
untrained sum of the same 9 features beats the trained model for 3 of 4
families is consistent with (but does not prove) the trained model having
fit family-specific weightings during pooled-family training that do not
transfer, rather than having learned a generically useful combination of
the 9 features.

## J. Interpretation

**Outcome 2 — partial generalization — is the best-supported reading, with
a genuinely negative qualifier Outcome 3 partially shares:** one family
(MemoryGraft-style-volume, the largest held-out n) shows real, seed-stable
generalization above both chance and the untrained baseline. The other
three do not — FARMA specifically collapses to chance and is beaten by the
untrained baseline; Sleeper and propagated are too underpowered to
distinguish generalization from noise, but are also beaten or matched by
their own untrained baseline, which is itself evidence against (not
neutral on) the trained model adding value for those families specifically.

This is not read as Outcome 1 (broad cross-family generalization) — three
of four families show no reliable margin over either reference. It is also
not read as a clean Outcome 3 (broad collapse) — one family's result is
real and stable. **The honest, combined reading: the GNN's apparent
detection ability, measured on the pooled-family evaluation Baseline A
reports, does not reliably transfer to attack families excluded from
training, with one exception (MemoryGraft-style-volume) that this small
corpus cannot fully explain away as noise given its seed-stability and
larger n.** This is consistent with (not proof of) family-specific
fingerprinting for FARMA specifically, and inconclusive for
Sleeper/propagated given their sample sizes.

## Regression status

`python -m pytest phase6/ attribution/ phase7/ phase8/ phase11/ -q` →
**654 passed, 13 skipped, 0 failed** (was 638 passed before this
investigation — +16, 0 regressions). `python -m phase11.evaluation.run_b10`
re-confirms B9/B10 unchanged: **70.6%/7.3%**, identical per-family
breakdown. `run_gnn_feasibility_study()` (Baseline A) re-confirmed
unchanged: 55.9% detection at 6.8% FPR.

## What this report does NOT do

Per the task's explicit instruction: LOFO is not wired into B10, the live
defense pipeline is untouched, no threshold was recalibrated, no fusion
with the GLN was attempted, the existing detector was not replaced, no
deployment-readiness claim is made, and Phase 6–10 and the protected
held-out corpus were not modified. This is an independent research
evaluation only.
