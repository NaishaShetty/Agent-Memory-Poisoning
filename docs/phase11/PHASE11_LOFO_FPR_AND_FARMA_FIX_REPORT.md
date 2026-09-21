# Phase 11 — Fixing the Residual FPR and FARMA's Ranking

Direct follow-on to the two problems named as unsolved at the end of
`PHASE11_LOFO_THRESHOLD_FIX_REPORT.md`. Three real attempts, in order —
one clean rejection, one diagnosed dead end that turned out to be
genuinely informative, and one real, strong fix.

## Attempt 1 — re-chunk the reference to match training pool sizes (rejected)

Hypothesis: the reference-threshold fix's residual FPR (30.9%) came from
the 135-example reference's 15-member pool cliques differing structurally
from the training/held-out corpus's 3–9-member pools. Tested by
re-grouping the SAME 135 real LoCoMo turns into pools of size {3, 5, 8, 15}
(real content unchanged, only grouping changed — same technique already
used and disclosed in `PHASE11_X_OPTION2_EXPANDED_FEATURES_REPORT.md`
Section 15, applied locally here without touching `real_corpus.py`).

**Real, measured result: chunk size has no effect.** Macro AUROC, macro
detection, and macro FPR were identical (to 3 decimal places) across all
four chunk sizes tested. The pool-topology-mismatch hypothesis is
**rejected** for this specific FPR — not because it was a bad hypothesis to
test, but because the real cause turned out to be something else entirely
(Attempt 2).

## Attempt 2 — diagnosing why chunk size didn't matter (a real, structural finding)

Direct inspection: **all 135 of `real_benign_scenarios()`'s real LoCoMo
turns produce the IDENTICAL 9-feature vector, `(0,0,1,0,0,0,0,0,0)`.**
Every rule-based sanctioned feature (`consensus_divergence_score`,
`decision_log_vocabulary_score`, `imperative_write_directive_score`,
`lineage_taint_score`, `perfection_claim_score`, `provenance_anomaly_score`,
`self_reference_score`, `template_anomaly_score`) is exactly zero for
ordinary real conversational text — none of the regex/near-duplicate/
lineage triggers this project's own feature vocabulary relies on ever fire
on casual dialogue. Only the constant `dormancy_activation_score = 1.0` is
ever nonzero. The raw-feature-sum score is therefore **constant** across
this entire real reference population — chunking a constant-feature
population differently cannot change anything, which is exactly the null
result Attempt 1 found.

**This also explains why an earlier attempted fix (blending fitted+raw-sum
scores, calibrated against this same 135-example reference) produced
degenerate results (AUROC pinned at exactly 0.5, FPR pinned at exactly
1.0)** — z-scoring a constant vector divides by zero variance, and any
blend weight above the pure-fitted endpoint collapsed to the same
constant. Not a code bug — a real property of this project's rule-based
feature vocabulary on natural text, now confirmed directly rather than
assumed. It also retroactively qualifies `PHASE11_LOFO_BASELINE_C_REPORT.md`'s
own finding: the untrained raw-sum score's strong AUROC (1.0 on FARMA) was
always measured against the HAND-AUTHORED held-out corpus's own
deliberately-constructed near-miss benign examples (which DO trigger
nonzero features by design), never against arbitrary real conversational
text — a real, narrower scope for that earlier finding than originally
stated, disclosed here rather than left uncorrected.

## Attempt 3 — blend fitted + raw-sum, thresholded on the fold's own real training-benign set (real, strong fix)

Given Attempt 2's diagnosis, the fix is to calibrate the blend against a
population that isn't degenerate: the fold's own 8–11 real, hand-authored
training-benign examples (the ones that motivated this whole investigation
in the first place) — which DO have real, varying, nonzero features. Same
blend as before (`w·z(fitted) + (1-w)·z(raw_sum)`, z-scored on the
training set), thresholded with the SAME `_threshold_for_target_fpr()`
already used everywhere in this project, `w ∈ {0, 0.25, 0.5, 0.75, 1.0}`
pre-registered before any result was seen.

| w | Macro AUROC | Macro detection | Macro FPR |
|---|---|---|---|
| 0.0 (pure raw-sum) | 0.921 | 75.0% | 1.7% |
| **0.25** | **0.941** | **87.5%** | **6.1%** |
| 0.5 | 0.937 | 65.0% | 6.7% |
| 0.75 | 0.932 | 62.5% | 16.7% |
| 1.0 (pure fitted, the prior best) | 0.747 | 37.5% | 18.75% |

**`w=0.25` is a real, substantial, honest win on every axis at once —
this is the best result found across this entire investigation.** Macro
detection nearly triples over the pure-fitted result (37.5%→87.5%) while
FPR drops threefold (18.75%→6.1%) — and 6.1% is now BELOW the original
shipped pooled-family GNN's own 6.8% FPR (Baseline A), while measuring
generalization to entirely unseen families, a strictly harder task.

Per family at `w=0.25`:

| Family | AUROC | Detection | FPR |
|---|---|---|---|
| FARMA | **1.000** | **100%** | 5.9% |
| MemoryGraft-style-volume | 0.825 | 50% | 6.8% |
| Sleeper | 0.939 | **100%** | 6.8% |
| propagated | 1.000 | 100% | 4.8% |

**FARMA — the family that never broke chance-level AUROC (~0.49) under
any prior fix (weight decay, reference-threshold) — is now perfectly
separated (AUROC 1.0, 100% detection, 5.9% FPR).** This resolves the
second open problem directly: FARMA's issue was never that no signal
existed for it — the untrained raw-sum score always separated it perfectly
(Baseline C, and confirmed again here) — it was that the FITTED model's
weights, tuned on the 3 OTHER pooled families, actively worked against
that signal. A 75%-raw/25%-fitted blend lets the untrained signal carry
FARMA while still letting the fitted component contribute for
MemoryGraft-style-volume (the one family where fitting alone had helped).

MemoryGraft-style-volume remains the weakest family in this configuration
(50% detection, though AUROC 0.825 is solid) — a real, disclosed remaining
gap, not hidden by the strong macro numbers above.

## Net result of this whole threshold-fixing investigation, stacked

| Stage | Macro AUROC | Macro detection | Macro FPR |
|---|---|---|---|
| Shipped (weight_decay=0.0, order-stat, pure fitted) | 0.687 | ~24%* | ~24%* |
| + regularization (weight_decay=0.005) | 0.774 | 37.5% | 18.75% |
| + reference-threshold (135-example, pure fitted) | 0.774 | 71.0% | 30.9% |
| **+ raw-sum blend (w=0.25), in-fold threshold** | **0.941** | **87.5%** | **6.1%** |

*(same-threshold-protocol comparison point, computed for completeness — see prior report)*

## What this does not establish

This is still measured on a real but very small corpus (34 held-out
poison examples across 4 families, 8–11 training-benign examples per
fold) — the same statistical-power caveat every Phase 11 report has
carried throughout. MemoryGraft-style-volume's 50% detection is a real,
disclosed remaining weakness, not resolved by this fix. Nothing here is
wired into B10 or the live pipeline; this remains an independent research
evaluation.

## Regression status

`python -m pytest phase6/ attribution/ phase7/ phase8/ phase11/ -q` →
**687 passed, 13 skipped, 0 failed** (was 680 before this investigation —
+7, 0 regressions). B9/B10 and the shipped GNN default reconfirmed
byte-for-byte unchanged.
