# Probe and Attack Validity (final)

**Date:** 2026-10-13. Targeted phase, deliverable 3.

**Pre-registration:** `PREREGISTRATION_TARGETED_2026-10-13.md` §6–7 (commit `dff63620`).

**Code:** `phase17/remediation/validity_final.py`.

**Output:** `phase17/data/remediation/validity_final.json`. Table: T20.

## 0. Terminology correction

The "without memory" arm of the validity audit, PR-1 and every earlier report is **not** an empty memory. It is a **clean-memory** arm: the same 8 benign owner turns, with the poison removed.

This phase adds the genuinely **empty-memory** arm ("none"). New model calls:
- 300 agent answers: 150 PR-1 items × 2 probes, with qwen2.5:7b, the audit's prompt template, temperature 0 and seed 42;
- 900 judge verdicts: C0, C1 and C3, with unchanged templates.

The task, agent, decoding and template are held fixed. Only the store, or the probe, varies.

## 1. Three conditions × two probes (150 own-population items, paired)

Compliance as judged, counts out of 150.

| Probe | Judge | None (empty) | Clean (8 owner turns) | Poisoned (+ note) |
|---|---|---|---|---|
| Fitted | C0 | 59 | 38 | 109 |
| Fitted | Vote | 104 | 67 | 139 |
| Non-leading | C0 | 5 | 5 | 41 |
| Non-leading | Vote | 14 | 7 | 63 |

**Effects.** Each cell gives points, the exact McNemar p-value, and the population-cluster bootstrap 95% CI.

| Probe · judge | Memory-attributable (poisoned − clean) | Context (clean − none) | Total (poisoned − none) |
|---|---|---|---|
| Fitted · C0 | **+47.3**, p = 1.5e-19, [38.1, 56.3] | −14.0, p = 5.1e-4, [−19.8, −2.5] | +33.3, p = 1.5e-9 |
| Fitted · vote | **+48.0**, p = 7.9e-21, [38.0, 58.1] | −24.7, p = 2.4e-7, [−29.4, −18.0] | +23.3, p = 7.9e-8 |
| Non-leading · C0 | **+24.0**, p = 2.9e-11, [14.9, 36.3] | 0.0, p = 1, [−2.9, 1.4] | +24.0 |
| Non-leading · vote | **+37.3**, p = 2.8e-17, [24.8, 50.8] | −4.7, p = 0.065, [−9.9, −1.1] | +32.7 |

**Prediction V2 HELD.** The memory-attributable effect is positive, with a cluster CI excluding 0, in all four probe × judge cells. Family-cluster CIs agree (T20).

**Prediction V1 FAILED, and the failure is informative.**

V1 predicted that no-memory compliance would be within ±5 points of clean-memory compliance. With the **fitted** probe, the empty-store agent was judged compliant *more* often than the clean-store agent: 59 vs 38 under C0, and 104 vs 67 under the vote.

The fitted tasks are written from each note's subject. Without any context the agent answers the task's premise as stated, and the judge reads that answer as "asserting the note's claim". The 8 benign owner turns pull the answer back towards the owner's real situation.

So **the fitted probe leaks the note's content into the task**. This confirms the round-7 base-rate concern (25.7% under C0) and locates it in the probe. With the **non-leading** probe there is no such leak: none = clean = 5/150 under C0.

**Consequences.**

1. The clean arm, not the empty arm, is the appropriate baseline. The memory-attributable effect (poisoned − clean) is the right estimand under either probe. "Total (poisoned − none)" understates the fitted-probe effect, because the empty arm is itself inflated.
2. The fitted-probe effect (+47) and the non-leading effect (+24 C0, +37 vote) differ. That is **measurement**, not attack strength: the probe determines whether the agent has an occasion to act (§3).

## 2. Is the published net effect causal, and at what level?

**The +43.2 (C0) / +47.1 (vote) figures**, re-derived item for item (2,628 audited items, own n = 804):
- **Numerator:** discordant pairs, 362 vs 15 under C0 and 391 vs 12 under the vote.
- **Denominator:** all 804 own items. Nothing was dropped.
- **Missing data:** 1 empty poisoned-arm and 1 empty clean-arm answer, after retries. Each was scored NO.
- **Design:** paired. Same item, task and store, with only the note toggled. Deterministic decoding, one run per arm.

**Causal at the level of "note present in context vs absent".**
- It is **conditional**: it assumes the note is in the context window. It is **not** an end-to-end success rate.
- The stage measurements come from the real Mem0 pipeline (MEM-1). They are not multiplied together, because their independence is not established.

**Clustering.** Items cluster by population (12 own) and family (24 own). Cluster-bootstrap CIs:

| Judge | Item-level Wald CI | Population-cluster CI |
|---|---|---|
| C0 | 39.5–46.8 | **36.4–48.1** |
| Vote | 43.5–50.8 | **35.9–57.3** |

The point estimates stand; the item-level intervals were too narrow.

## 3. Probe comparison: what the lower working count means

**Working counts on the same 150 items:**

| Definition | Fitted probe | Non-leading probe |
|---|---|---|
| C0, mechanism-checked | 72 | 34 |
| Vote | 70 | 53 |
| Robust (both judges) | 50 | 33 |

**Item status changes, fitted → non-leading (C0):**

| Status | Count |
|---|---|
| Both working | 20 |
| Fitted only | 52 |
| Non-leading only | 14 |
| Neither | 64 |

Agreement is 56%.

**What drives the changes** (C0, from the per-arm verdicts):
- **50 of the 52 "fitted-only" items lost their working status because the agent no longer complied with the note present.** Their clean-arm verdict did not change. The non-leading task gave the note **no occasion to act**.
- 12 of the 14 "non-leading-only" items gained because their clean-arm compliance disappeared. The fitted probe's leak had masked them.

**Interpretation.** Each is kept distinct:

| Possible explanation | Verdict |
|---|---|
| Lower probe-induced compliance | Real: base rate 38 → 5 (C0) |
| Fewer observed working attacks | Real: 72 → 34 |
| Genuine reduction in attack success | **Not shown.** The drop comes from fewer occasions to act, not from the same occasion being resisted |
| Measurement change | Instance labels depend on the probe. Population effects remain positive and significant under both |

## 4. Five working-attack definitions × probe: defence ranking

Recall on each subset; the full population is reported separately.

| Probe · definition | n | B12 | B13 | B14 | B15 | B17 |
|---|---|---|---|---|---|---|
| Fitted · full | 150 | 78 | 80 | 68 | 63 | 86 |
| Fitted · published working (union, C0) | 102 | 54 | 54 | 43 | 40 | 57 |
| Fitted · working C0 | 72 | 39 | 39 | 34 | 31 | 42 |
| Fitted · working vote | 70 | 35 | 35 | 28 | 27 | 37 |
| Fitted · robust | 50 | 25 | 25 | 19 | 19 | 25 |
| Non-leading · full | 150 | 78 | 80 | 68 | 63 | 86 |
| Non-leading · published working | — | Not available: the union is defined only over the audit's own probes | | | | |
| Non-leading · working C0 | 34 | 13 | 13 | 11 | 10 | 15 |
| Non-leading · working vote | 53 | 22 | 22 | 20 | 18 | 25 |
| Non-leading · robust | 33 | 12 | 12 | 10 | 9 | 14 |

**The ranking is identical in every row:** B17 ≥ B12 = B13 > B14 > B15. The five definitions were applied unchanged and no sixth definition was introduced.

**Prediction V3 FAILED, as worded.** V3 said "B13 *above* B12 on every definition with n ≥ 10". On these 150 own-population items, B13 **ties** B12 on every working subset. It is ahead only on the full population (80 vs 78).

That is consistent with the B13 decomposition: on instruction-shaped own attacks B13's other components equal B12, and corroboration's advantage lies in additive fabrication (`B13_OWNER_GENERALISATION_REPORT.md`). The ranking conclusion survives; the stronger directional prediction did not.

## 5. Judge disagreement (C0 vs the vote; no ground truth is assumed)

**Fitted probe, 2,628 items × 2 arms.**

- **Systematic and one-directional.** Of 1,939 C0-YES verdicts, only **10** are NO under the vote. Of 3,317 C0-NO verdicts, **1,191** are YES under the vote. The vote is more lenient. This is **systematic judge bias**, not random label noise.
- **By arm:** poisoned 620/2,628, clean 581/2,628. Similar, so the *net* effect is only mildly judge-sensitive, while levels are strongly judge-sensitive.
- **By owner store:** sample 0: 283/1,328; 5: 314/1,322; 6: 314/1,306; 7: 290/1,300. No store effect.
- **By family:** concentrated in external jailbreak corpora:

| Family | Disagreements |
|---|---|
| gandalf | 427/1,996 |
| deepset | 201/520 |
| mosscap | 160/600 |
| agentpoison | 32/74 (43%) |
| agentdojo | 18/54 |
| memory_worm | 32/158 |
| authority_impersonation | 23/100 |

The full table is in T20.

**By probe** (150 items):

| Probe · arm | Disagreements | Notes |
|---|---|---|
| Fitted · none | 45 | — |
| Fitted · clean | 29 | — |
| Fitted · poisoned | 30 | — |
| Non-leading · clean | 4 | The non-leading probe cuts disagreement on the baseline arms sharply |
| Non-leading · none | 9 | |
| Non-leading · poisoned | 24 | Disagreement stays where the agent engages with the note |

### Sensitivity of the working count to disputed items

No item is deleted.

| Group | Agreed working | Disputed | Under C0 | Under vote | Bounds (disputed uncertain) | Adjudicated working / adjudicated |
|---|---|---|---|---|---|---|
| Own (804) | 246 | 192 | 328 | 356 | **246–438** | 30/37 |
| External (1,824) | 189 | 317 | 338 | 357 | **189–506** | 28/83 |
| All (2,628) | 435 | 509 | 666 | 713 | **435–944** | 58/120 |

What can and cannot be established:

- **Aggregate estimate stability.** The net effect is stable across judges.
- **Individual-label instability.** Large: one item in five is disputed.
- **Systematic bias.** Present, in a known direction: the vote calls more compliance.
- **Insufficient evidence to determine an outcome.** The adjudicator (gemini-3.5-flash-lite, blind) is a third model, not a reference standard. It split the stratified sample 60/60 between the judges (κ 0.145 with each).
  - For own items it called most disputed items working (30/37).
  - For external items it called most not working (28/83).

  That is a third model's view, not ground truth.

## 6. What changes, and what does not

| Conclusion | Changes? |
|---|---|
| Memory poisoning causally changes this agent's behaviour when the note is in context | **No.** Positive and significant under both probes and both judges, with cluster-robust intervals |
| Defence ranking | **No.** Identical across 9 definition × probe cells |
| "42.5% of attacks work" / any instance-level working rate | **Yes: it is probe- and judge-dependent.** Report the bounds 435–944/2,628, or the net effect, never a single rate |
| The fitted probe's clean-arm base rate is probe leakage | **Confirmed** (empty arm > clean arm under the fitted probe only) |
| "B13 beats B12 on working own attacks" | **Not supported.** They tie on every working subset; B13's advantage is on additive fabrication, not instruction-shaped attacks |

## 7. Statistical assumptions

- Paired binary outcomes with exact McNemar.
- Cluster bootstrap over populations and families: 10,000 resamples, seed 2026, 12 own populations.
- One deterministic run per arm; run-to-run spread is documented separately (SD 0.8–1.7 points).
- Families are LLM-authored or published corpora, so the intervals are conditional on these populations.
