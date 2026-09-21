# Phase 11 — Correcting a Stale Claim, and Calibrating the Real-Corpus Finding

**No git commit or push was made for any of this work — all changes are
local, uncommitted file modifications only, per explicit instruction,
same as the prior report.**

## 1. A correction, stated plainly

The previous turn claimed "FARMA's LOFO ranking problem is untouched." **This
was wrong**, and re-checking it directly (not re-deriving from memory)
confirms it: `docs/phase11/PHASE11_LOFO_FPR_AND_FARMA_FIX_REPORT.md`,
written earlier in this same session, already measured FARMA's LOFO result
under the raw-sum blend at **AUROC 1.000, 100% detection, 5.9% FPR** — a
real, complete resolution, not a stale or aspirational number. The claim
appears to have conflated FARMA with **MemoryGraft-style-volume**, which
really was (and still partially is) the genuine remaining weak point in
that same table — 50% detection despite a solid 0.825 AUROC. That
confusion is owned directly here rather than quietly worked around.

## 2. Does the semantic feature help MemoryGraft-style-volume's real weak spot?

MemoryGraft-style-volume is the near-duplicate/paraphrase consensus attack
family — exactly what `semantic_consensus_divergence_score` was added to
detect. Re-ran the same LOFO+blend protocol
(`lofo_blend_infold_threshold_semantic.py`, identical to the original
except for the feature set) to check directly, not assume:

| | Original (9 features) | With semantic feature (10 features) |
|---|---|---|
| MemoryGraft-style-volume AUROC | 0.825 | **0.895–0.901** |
| MemoryGraft-style-volume detection | 50% | 50% (unchanged) |
| Sleeper AUROC | 0.939 | 0.932 (roughly unchanged) |
| Sleeper detection | 100% | **0%** (new regression) |
| FARMA AUROC/detection | 1.0 / 100% | 1.0 / 100% (unaffected, as expected — FARMA is an admission-guard attack, unrelated to consensus divergence) |

**Real, mixed, honestly-reported finding: the semantic feature improves
MemoryGraft-style-volume's underlying ranking quality but does not fix its
detection-rate plateau, and introduces a new detection regression for
Sleeper.** This is not a new, mysterious failure — it is the SAME
threshold-selection fragility this entire investigation already diagnosed
in `PHASE11_LOFO_THRESHOLD_FIX_REPORT.md`: at 8–11 training-benign
examples, any shift in the score distribution (here, from adding a 10th
feature) can move the fitted threshold enough to flip a specific family's
detection outcome even when its ranking (AUROC) stays intact or improves.
**Not chased further** — repeatedly re-tuning the threshold protocol
per feature change would be exactly the "keep tuning until it looks good"
pattern this investigation has consistently avoided. The LOFO track
remains, as established throughout, an independent research evaluation,
never wired into B10.

## 3. Calibrating the real-corpus finding into an actual detector

The prior report's real-corpus result was AUROC only (0.91–0.93) — a
ranking metric, not a detector. A real, fitted threshold was added
(`real_attack_corpus_detector.py`), using the SAME non-degenerate,
already-validated training-benign population `lofo_blend_infold_threshold.py`
already uses (the model's own `all_dev_pools()` training set — the
`real_benign_scenarios()` reference was already confirmed degenerate for
this purpose), and the SAME `w=0.50` already wired into `run_b10.py` (not
re-tuned against this evaluation, which would be circular).

| Metric | Value (seeds 11–20) |
|---|---|
| AUROC | 0.911 mean [0.608, 0.990] |
| Detection rate | **0.333 mean [0.042, 1.000]** |
| FPR | 0.055 mean [0.045, 0.068] |

**Real, honest result: FPR is reasonably controlled (~5.5%, close to the
10% target) even under real cross-corpus distribution shift — but
detection is weak (33% mean) and highly seed-unstable (4%–100% range).**
Per-family detection at seed 11: FARMA 70%, MPBench 57.5%, but MINJA/
AgentPoison/MemoryGraft/Sleeper all sit at 10–15%.

**The honest conclusion, stated directly**: a strong AUROC does not
automatically produce a reliable detector once a real, fitted threshold is
required — this is the clearest demonstration yet in this whole
investigation of that distinction. The ranking signal genuinely
generalizes to the real 7-attack corpus (confirmed, Section 5 of the prior
report); a *reliable, low-variance detection threshold* for that same
corpus has not been achieved by this simple in-fold calibration, and this
report does not claim otherwise. Closing that gap would need either a
larger, non-degenerate calibration population drawn from the SAME
distribution as the real corpus, or a threshold-selection method more
robust to cross-corpus distribution shift than the tiny-sample order
statistic used throughout this project — a real, scoped, concrete next
step, not attempted further here to avoid repeating the same
threshold-tuning cycle Section 2 just described.

## Regression status

`python -m pytest phase6/ attribution/ phase7/ phase8/ phase11/ -q` →
**708 passed, 13 skipped, 0 failed** (was 699 before this investigation —
+9, 0 regressions). Nothing here touches B9, B10, or any previously
reported number — both investigations in this report are additive,
standalone evaluations.

## What remains genuinely open after this pass

- MemoryGraft-style-volume's LOFO detection plateau (50%) is real and
  unresolved — the semantic feature helped its ranking, not its threshold
  crossing.
- Sleeper's new LOFO detection regression (100%→0%) under the 10-feature
  vocabulary is real, disclosed, and not investigated further here.
- The real-corpus detector's high seed variance (4%–100% detection) means
  it should not be treated as a reliable, ready-to-use detector for real
  attack content — the ranking signal is real; the threshold is not yet
  trustworthy.
