# Pre-registration 2: is my model of this system any good? (2026-10-06)

Written **before** B17 or B18 was scored on hold-out 2 (Mosscap). Predictions below are
recorded first; the measurement follows; the calibration is then scored whether or not it
flatters me.

## Why this exists

Three of the five predictions in `PREREGISTRATION_HOLDOUT3.md` failed, and one failed
backwards. That row sits in the unfavourable column as "my predictions were wrong", and it
cannot be un-failed — the honest question is not whether those predictions were right but
whether the *model that produced them* has improved now that the system is better understood.
That is testable, and the only way to test it is to predict again, in advance, on something not
yet measured, and score the result.

**B17 and B18 have never been scored on hold-out 2.** `eval_round6` ran B12–B15 there and
stopped; both union configurations postdate it. So Mosscap is an unmeasured target about which I
have a detailed mechanistic model, which makes it the right calibration test.

## What is already known (the basis for the predictions, not the predictions)

| Config on Mosscap (1,200 attacks) | Recall |
|---|---|
| B12 | 15.0% |
| B13 | 17.6% |
| B14 | **54.2%** |
| B15 | 43.2% |
| deberta_pi_v2@dev (same corpus) | 67.2% |

And the mechanism established in §32.27: on external corpora B14's decisions agree with deberta
90.1% of the time, and B17 = B13 OR B14 while B18 = B17 OR deberta@oracle.

## Predictions, recorded before measurement

Each is a point estimate with a stated tolerance. A prediction counts as HELD only if the
measured value falls inside its interval — "roughly right" after the fact does not count.

| # | Prediction | Interval | Reasoning |
|---|---|---|---|
| **C1** | **B17 recall on Mosscap = 56%** | 52–60% | B17 is B13 OR B14. B14 alone is 54.2%; B13 adds only 17.6% and its catches should overlap B14's heavily on injection-shaped text, where B13's provenance signals barely engage. So B17 should sit just above B14, not near the sum. |
| **C2** | **B18 recall on Mosscap = 74%** | 69–79% | B18 adds deberta@oracle, which scores 64.3% on this corpus alone. The B17∪deberta union measured 72.2% on hold-out 3's distribution; Mosscap is deberta's stronger corpus, so slightly higher. |
| **C3** | **B18 > B14 by at least 15 points here** | — | Directional. The whole justification for B18 is that B14's fusion discards deberta's independent signal out of distribution; Mosscap is where that was first observed. If this fails, B18's rationale fails on the corpus that motivated it. |
| **C4** | **B17 and B18 ordinary-benign FPR ≤ 3/1054** | 0–3 | B13 and B14 are 0/1054 and 1/1054 without evidence; unions add no new false positive in every measurement so far. |
| **C5** | **B17 adds ≤ 5 points over B14** | 0–5 | The sharp form of C1: on injection-shaped text B13 contributes almost nothing B14 does not already catch. This is the prediction most likely to fail, because it asserts near-total overlap. |

## How this is scored

- **5/5 or 4/5 held** → the model is calibrated; the earlier failures reflected a system I did
  not yet understand rather than a habit of overclaiming.
- **3/5** → partially calibrated; report as such.
- **≤ 2/5 held** → the model is *not* calibrated, the earlier failures were not a one-off, and
  every forward-looking statement in this project should be read with that attached. This
  outcome is reported as prominently as the favourable one.

## Commitments

- No prediction is edited after the run. This file is committed before the measurement.
- The measurement uses the frozen Mosscap corpus with its digest verified, scored without
  evidence (it has no owner conversation), exactly as B12–B15 were scored there.
- Mosscap has now been used for B12–B15 (round 6) and for this analysis. It was frozen before
  B15 existed, so it is clean for B15 and earlier; B17/B18 postdate the hold-out results that
  informed their design, so their Mosscap numbers are **not** a clean generalisation estimate
  and are not reported as one. The calibration test does not depend on that: it asks whether I
  can predict a number, not whether the number is independent.
