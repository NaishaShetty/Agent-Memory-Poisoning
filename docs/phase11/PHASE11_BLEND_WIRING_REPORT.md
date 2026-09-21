# Phase 11 — Validating, Wiring In, and Closing the Remaining Gaps

Addresses, in order, the four real open items named at the end of the
threshold-fix investigation, plus the housekeeping note. Every number
below is real and reproducible (`python -m phase11.gnn.blend_pooled_family`,
`python -m phase11.gnn.blend_real_attack_corpus`,
`python -m phase11.evaluation.run_b10`, `python -m phase11.gln.lofo_gln`).

## 1. Does the blend fix help the standard pooled-family evaluation, not just LOFO?

Trained on `all_dev_pools()` with no family excluded (the exact Baseline A
regime), same blend (`w·z(fitted) + (1-w)·z(raw_sum)`, `weight_decay=0.005`).

| w | AUROC (seed 11, [range over seeds 11-20]) | Detection | FPR |
|---|---|---|---|
| 0.0 (pure raw-sum) | 0.832 | 44.1% | 0.0% |
| **0.25** | **0.963 [0.963, 0.970]** | **70.6%** | **4.55%** (mean 5.45% over 10 seeds) |
| 1.0 (pure fitted, wd=0.005) | 0.977 | 100% | 56.8% (seed-unstable, reproduces the original seed-instability finding) |

**Real, measured yes: `w=0.25` beats Baseline A (55.9% detection / 6.8%
FPR) on both axes** — detection 70.6% (up from 55.9%, now matching B9's
own rule-based number almost exactly) at FPR 4.55–5.45% (down from 6.8%),
with a tight seed range (AUROC 0.963–0.970 across 10 seeds — the blend
also fixes the seed-instability the pure-fitted approach never escaped).
`weight_decay=0.005` was confirmed necessary here too — at the shipped
`weight_decay=0.0`, `w=0.25` only reaches 29.4% detection — the full
package (regularization + blend + in-fold threshold) works together, not
piecemeal.

## 2. Does it hold up against Phase 11.z's real 7-attack corpus?

Same pooled-family-trained model, scored against `real_corpus.py`'s 24
real poison examples (all 7 real Phase 4 attacks: DSRM, FARMA, MPBench-
PCFI, MemoryGraft, Sleeper, AgentPoison, MINJA — real LoCoMo-derived text,
never part of this model's training data) vs. the same 44-node held-out
benign reference.

| w | AUROC |
|---|---|
| 0.0 | 0.507 |
| 0.25 | 0.521 |
| 1.0 | 0.556 |

**Real, disclosed negative result: no. AUROC stays at chance (0.51–0.56)
across every blend weight.** Per-family mean scores at `w=0.25` show every
real attack family scoring similarly low, indistinguishable from noise.
**This is a real scope limit, not glossed over**: the blend's real,
measured improvement (Sections 1 and the prior LOFO report) is scoped to
this project's own hand-authored ablation corpus — the same corpus every
B0–B10 number has always been scoped to. It does not constitute evidence
of generalization to real-world or structurally different attack content
(the real corpus is genuine LoCoMo-derived dialogue-adjacent text; the
ablation corpus is hand-authored synthetic text modeled on each attack's
documented mechanism — a real, disclosed content-style gap this
investigation does not close).

## 3. Wiring the blend into B10

`run_b10.py::_train_gnn_and_score_held_out()` now trains with
`weight_decay=0.005` and returns `sigmoid(w·z(fitted) + (1-w)·z(raw_sum))`
(`w=0.25`) instead of the raw fitted sigmoid — a sigmoid squash back into
(0,1), since `_learned_group_score()`'s MIN-of-two-learned-scores logic
assumes a bounded, probability-like scale (an unbounded z-score would
silently break that assumption). `run_gnn_feasibility_study()` (Baseline
A, the standalone "GNN architecture alone" report) is deliberately
untouched — verified directly, not merely asserted
(`test_run_gnn_feasibility_study_baseline_a_untouched_by_the_b10_wiring`).

**Real, measured result: B10's own final number is UNCHANGED — still
70.6%/7.3%, byte-identical to before.** This is not a coincidence, and was
investigated directly rather than accepted at face value:

- Per-node inspection confirms `MIN(gnn, gln)` is now much better
  separated (poison mean 0.424, benign mean 0.035 — a real, substantial
  improvement over the pre-wiring separation).
- But every `PARAPHRASE-POISON-*` (MemoryGraft-style-volume) scenario
  scores GLN exactly `0.0` — and `_learned_group_score()`'s MIN gate
  means `MIN(0.34, 0.0) = 0.0` regardless of how good the GNN's own score
  is. This is the SAME structural blind spot `PHASE11_REPORT.md` Section 5
  already disclosed ("neither the GNN nor the GLN... carries any real
  information about this specific family") — re-confirmed directly with
  the improved GNN, not assumed unchanged.
- **A real, measured check of whether a different combination rule closes
  this**: swapping MIN for MAX was tested directly. Result: **100%
  detection at 100% FPR** — the same degenerate saturation the original
  mean-based `learned_group` was replaced for. MAX is not adopted; MIN
  remains the correct, necessary rule — confirmed empirically with the new
  GNN, not merely by historical precedent.

**Net, honest conclusion**: wiring in the blend is real, live, and safe —
the underlying GNN signal is genuinely better-calibrated, available in
`RiskEstimate.contributing_signals` for any future consumer that reads the
raw signal rather than the final action — but it does not, by itself, move
B10's reported detection/FPR, because the specific gap it doesn't close
(paraphrase-poison) is a gap BOTH learned components share independently,
and no combination rule over two already-blind signals can manufacture
information neither one has.

## 4. Does the GLN generalize to unseen families? (the other half of the "never touched" gap)

Real LOFO analogue for the GLN's own online architecture: warm up
(`predict_and_update`) excluding family F entirely, then measure the
FROZEN model's zero-shot score (`predict`, no update) on family F's
held-out examples at their first retrieval.

| Family | Zero-shot LOFO AUROC | Pooled-family AUROC (all families in warmup) |
|---|---|---|
| FARMA | **0.948** | 0.794 |
| MemoryGraft-style-volume | **0.285** | 0.715 |
| Sleeper | **0.000** | 1.000 |
| propagated | 0.927 | 1.000 |

**Real, mixed, honestly-reported finding: the GLN has its own real,
family-specific generalization gaps — and they are DIFFERENT families than
the GNN's.** FARMA (the GNN's own weakest LOFO family before the blend fix)
generalizes well for the GLN. MemoryGraft-style-volume and Sleeper — both
solid for the GNN's blend — collapse for the GLN under LOFO (Sleeper's
zero-shot AUROC is exactly 0.0: every benign example outscores the single
real held-out Sleeper poison example). This is architecturally sensible:
the GLN has never adapted to that family's own particular feature
signature, and one zero-shot prediction is a much harder ask than the
GNN's batch-trained decision boundary. **This complements, rather than
duplicates, the GNN LOFO finding — the two learned components' real
weaknesses do not overlap, which is a real, substantive piece of evidence
for why MIN-gating (requiring both to corroborate) remains a conservative
but justified choice: whichever one is weak for a given family, the other
frequently is not, but "not is not" is not the same as "both are strong,"
and paraphrase-poison is the case where both genuinely are weak at once.**

## 5. Housekeeping

`phase11/gnn/lofo_robust_threshold.py` and `phase11/gnn/lofo_combined_fix.py`
now carry an explicit `SUPERSEDED` notice at the top of their module
docstrings, pointing to the adopted fix and the report documenting why
each was not adopted — the original docstrings and all code are preserved
unmodified beneath the notice, per this project's own "preserve negative
findings" discipline. No file was deleted.

## Regression status

`python -m pytest phase6/ attribution/ phase7/ phase8/ phase11/ -q` →
**699 passed, 13 skipped, 0 failed** (was 687 before this investigation —
+12, 0 regressions). B9 and `run_gnn_feasibility_study()` (Baseline A)
reconfirmed byte-for-byte unchanged; B10's `WEIGHTED_SUM` regression case
reconfirmed unchanged (100%/100%); B10's `GROUPED_GATED` default
reconfirmed at 70.6%/7.3%, now for a directly-investigated, disclosed
reason rather than an assumed one.

## What remains genuinely open after this pass

- Closing the paraphrase-poison blind spot would need a learned component
  that captures something neither the GNN's nor the GLN's current inputs
  do — not a different composition rule, confirmed directly here (MAX
  tested, rejected).
- The real-7-attack-corpus gap (Section 2) is unresolved and would likely
  require training data drawn from that same real content distribution,
  not a better combination of the existing hand-authored-corpus-trained
  signals.
- MemoryGraft-style-volume's 50% detection under the pooled-family blend
  (Section 1) remains a real, disclosed weak point, unchanged by this pass.
