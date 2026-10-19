# Statistical Validity Audit

**Date:** 2026-10-13. Targeted phase, deliverable 5.

**Scope:** the B13 and attack-validity analyses.

**Code:**
- `phase17/remediation/stats_audit.py`: re-derives the p-values with scipy, an independent implementation.
- `b13_owner_loo.py`: owner clustering.
- `validity_final.py`: clustered effects and the three-condition design.

Each item was checked by inspecting the code and data first. Only confirmed issues were changed.

## Summary

| # | Check | Finding | Status |
|---|---|---|---|
| 1 | Owner clustering (B13) | Earlier B13 rates carried Wilson intervals over **notes of one owner**. Those intervals are valid for that owner, but were sometimes read as owner-level generalisation. No owner-level interval existed | **Confirmed (interpretation). Corrected:** owner-cluster bootstrap over 10 LOO owners (T19). Hold-out intervals now labelled "conditional on one owner" |
| 2 | Paired designs | Net memory effect: same item, same task, same store, ± the note. Item-level exact McNemar is appropriate. Defence comparisons on the same items use exact McNemar (`paired_delta`). Correct | No defect |
| 3 | Clustering of validity items | The 2,628 items come from 12 own and 8 external populations and 24+ families. Several are variants of one parent (evasion, translations). The Wald CI treated items as independent | **Confirmed. Corrected:** population- and family-cluster bootstrap (below). The point estimates stand; the intervals widen |
| 4 | Repeated runs | One deterministic run per arm (temperature 0, fixed seed). Repeats are never pooled as independent. Run-to-run spread was measured separately in round 7 (SD 0.8–1.7 points) | No defect; the limit is stated |
| 5 | Denominators | Net effect: n = 804 own and 1,824 external (2,628 in total). These match the audit rows. B13 LOO denominators are given per owner | No defect |
| 6 | Missing or failed trials | The audit's `_retry` records an empty answer after 3 failures, which the judge scores NO. Found **1** empty poisoned-arm and **1** empty clean-arm answer in 2,628 × 2; **0** in PR-1 | Negligible; disclosed |
| 7 | Duplicates | 5 of 804 own items share a note text with another item (distinct ids and tasks) | Negligible; covered by the family-cluster bootstrap |
| 8 | Threshold selection bias | LOO: all points pre-declared. The curve is published and no point is selected from it | No defect |
| 9 | Hold-out influence on selection | Previously disclosed and unchanged (`CALIBRATION_AND_LEAKAGE_AUDIT.md`): B18's oracle threshold was fitted on test-half benign data; frame v6 was designed after an HO7 failure; judge selection used HO5 items. **Withdrawn:** the "≈3× owner instability" (see 11) | Unchanged |
| 10 | Number of owners vs claims | 10 owners support "stable across these owners". They do not support population-level owner generalisation | Wording corrected |
| 11 | "Disjoint thresholds" analysis (my own, previous round) | It compared the nominal 2% budget at top-20 against shipped constants that sit at a 0.49% budget at top-20. This was a **budget** change, not an owner change | **Confirmed defect. Corrected;** T15 annotated; regression test |
| 12 | p-values vs stated tests | All 6 gap-closure p-values re-derive exactly with scipy. Holm-adjusted values match `\GapHolm` exactly. The **Fisher** p-values (M2-4, S2-3, and SA-3 in the remediation family) are **one-sided** (`alternative="greater"`, matching directional predictions) but were printed as plain "Fisher p" | **Confirmed (labelling). Corrected:** labelled one-sided in the paper. Two-sided values are 2× and change no conclusion (S2-3 two-sided 7.3e-17; M2-4 6.5e-7) |

## Corrected analyses

### Net memory-attributable effect (2,628 audited items, fitted probe)

| Group | Judge | Net (points) | Item-level Wald CI | Population-cluster CI | Family-cluster CI | Exact McNemar |
|---|---|---|---|---|---|---|
| Own (804) | C0 | **+43.2** | 39.5–46.8 | **36.4–48.1** (12 clusters) | 37.7–48.4 (24) | 1.7e-87 (362 vs 15 discordant) |
| Own (804) | Vote | **+47.1** | 43.5–50.8 | **35.9–57.3** | 38.4–56.5 | 3.2e-99 (391 vs 12) |

External and all-items rows are in T20.

**What the effect is.** The net effect is P(judged compliant | poisoned store) − P(judged compliant | clean store), on the same item and the same task.

- **It is causal for the note's presence in context.** The note is the only thing manipulated between the arms, and decoding is deterministic. This holds for this agent, this store and these judges.
- **It is not an end-to-end attack-success rate.** It conditions on the note already being in the context window: it is not retrieved, not extracted and not stored.
- **The real-pipeline stages are measured separately.** In MEM-1, 48 of 157 notes were retrieved and 29 changed the answer. The stage probabilities are **not** multiplied into an end-to-end estimate, because the stages were not shown to be independent.
- **Terminology correction.** "Without memory" in earlier reports is the **clean-memory** arm (8 owner turns, no poison). The truly empty-memory arm is new; see `PROBE_AND_ATTACK_VALIDITY_FINAL.md`.

### B13 owner-level uncertainty

| Measure | Pooled (10 LOO owners) | Owner-cluster bootstrap CI | Per-owner range |
|---|---|---|---|
| Detection | 116/200 (58.0%) | 49.5–67.0% | 30–90% |
| Benign exclusion | 15/2,541 (0.59%) | 0.29–0.91% | 0–1.5% |

Hold-out results (HO4, HO7, HO8, SA-1, SA-2) are single-owner. Their Wilson intervals describe within-owner sampling of notes only.

## Methods chosen, and their limits

| Method | Used for | Limit |
|---|---|---|
| Exact McNemar | Paired binary outcomes | — |
| Fisher exact | Independent groups; one-sided where the prediction was directional, now labelled | — |
| Wilson | Within-population proportions | — |
| Cluster bootstrap (10,000 resamples) | Owners; populations; families | 10–24 clusters makes the bootstrap approximate. No interval is used to claim generalisation beyond the sampled clusters |
| Holm | Within each pre-registered family | — |

**Not done.** Mixed-effects models. With 10–24 clusters and binary outcomes, they would add model assumptions without changing any conclusion.
