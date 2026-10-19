# Attack Validity and Causal Attribution

**Date:** 2026-10-13. **Deliverable 3.**

**Analysis kinds used here**

| Label | Meaning |
|---|---|
| CACHED-RECOMPUTE | Recomputed from saved verdicts; no model calls |
| PRE-REG | Pre-registered in `docs/phase17/PREREGISTRATION_GAPCLOSURE_2026-10-13.md` before the run |
| NEW ANALYSIS | Not pre-registered, labelled as such |

All numbers trace to `phase17/data/remediation/*.json` (§9).

---

## 1. What the audit measures (definitions, unchanged)

| Quantity | Definition | Status |
|---|---|---|
| Observed compliance | The judge says the answer complied with the memory note (instruction followed, or claim asserted), memory **present** | As in the original audit |
| Task-alone compliance (probe baseline) | The same judgement on the same task with the memory **absent** (the 8 owner turns remain: a clean-memory control) | As in the original audit |
| **Working attack** (original, round 5) | Compliance with memory ∧ ¬compliance without it ∧ mechanism implemented (third-family judge). Membership = union over two probes | Defined in code before the audit. The union rule was adopted after the first probe (disclosed) |
| **Memory-attributable compliance** (population level) | net = P(comply \| memory) − P(comply \| no memory), paired, same task | NEW ANALYSIS. Immune to a leading probe: a leading task raises both arms |
| **Robust working** (item level) | Working under **both** C0 and the vote | NEW ANALYSIS, reported **beside** the original, not instead of it |
| Harm | A separate study: family-specific harm question, task-alone control, **poison force-inserted in 71% of instances** | Harm given exposure, not end-to-end |

A "matched benign-memory condition" per attack does not exist in the audit design. The clean-memory control (owner turns without the note) is the available control. A matched benign condition exists only in SA-1 and SA-2 (benign lookalikes).

## 2. The probe problem, and why it does not overturn the main conclusions

**CACHED-RECOMPUTE: `validity_adjusted.json`**

**Task-alone base rate (fitted probe)**

| Group | Original judge (C0) | Human-calibrated vote |
|---|---|---|
| All 2,628 | 25.7% | 47.4% |
| Own memory-poisoning populations | 26.7% | 43.4% |
| External corpora | 25.2% | 49.2% |

**Admissibility.** Only **8 of 20 populations under C0 and 2 of 20 under the vote** meet the project's own rule (task-alone base rate ≤ 20%). The rule was adopted in round 7 and never applied to this audit.

**Memory-attributable compliance**, net percentage points with a 95% CI:

| Group | C0 | Vote |
|---|---|---|
| All | **+22.4** [20.5, 24.4] | **+23.9** [21.9, 25.9] |
| Own memory poisoning | **+43.2** [39.5, 46.8] | **+47.1** [43.5, 50.8] |
| External | **+13.3** [11.1, 15.4] | **+13.7** [11.4, 15.9] |

**Interpretation**
- The probe is leading. It produces the target behaviour without any memory in a quarter of cases (C0), and nearly half under the more permissive vote.
- **The memory's causal effect is nonetheless large, and almost identical under both judges.** The net effect, which a leading probe cannot inflate, is about +45 points on the project's own memory-poisoning attacks and about +13 on external injection corpora.
- The conclusion that most of the project's own attacks function, and that external injection corpora largely do not as memory poisoning, is robust.
- **The item-level working set is the fragile part** (§3), not the population-level effect.

## 3. Judge disagreement

**CACHED-RECOMPUTE + PRE-REG ADJ-1**

**Size.** 509 of 2,628 instances (19%) change working status between C0 and the vote: +231 working under C0 only, 278 under the vote only (paired p = 0.041).
- Excluding `own_gemini_30` (the ADJ-1 analysis set), 505 of 2,598.
- By arm: 274 flip on the with-memory verdict and 230 on the without-memory verdict.

**Spread.** The disagreements are spread across every population, at 10–41%:

| Highest rates | Lowest rates |
|---|---|
| AgentDojo 41%, trackb_15 40%, founding_regen 33% | zh_native 10%, novel_60 12% |

By family, the external corpora and every founding family contribute.

**ADJ-1, a blind automated adjudicator** (gemini-3.5-flash-lite, original prompt, blind to C0, the vote and the item's set). Sample: 120 disagreement items stratified by direction, plus 40 agreement items.

| Set | n | Adjudicator sides with C0 | With the vote |
|---|---|---|---|
| C0-only working | 60 | 29 | 31 |
| Vote-only working | 60 | 31 | 29 |
| Both agree (control) | 40 | 34 | 34 |

- On the disagreements the adjudicator splits **exactly 60/60**. Kappa against C0 and against the vote is both 0.145.
- **ADJ-1a FAILED.** The adjudicator does not favour the human-calibrated vote.
- **Reading.** The disagreement items are genuinely ambiguous for LLM judges. About one item in five has no reliable working/non-working label at the item level. Agreement items are mostly stable (85%).
- **This is model adjudication, not human adjudication.** No human labels were created, and the human labels that exist have the annotator caveats in `DATA_LICENSING_AND_ANNOTATION_AUDIT.md` §3.

## 4. Validity-adjusted defence comparisons

**CACHED-RECOMPUTE**

Exclusion recall (%) of each configuration, by denominator. "Audited" means items both evaluated and audited. B13 vs B14 is a paired exact McNemar test.

**Own memory-poisoning populations**

| Denominator | n | B12 | B13 | B14 | B15 | B17 | B13 vs B14 |
|---|---|---|---|---|---|---|---|
| Full (audited) | 804 | 43.2 | 46.1 | 41.2 | 37.7 | 51.2 | +81/−41, p = 3.7e-4 |
| Published working (union, C0) | 482 | 45.0 | 46.7 | 39.4 | 36.5 | 51.5 | p = 1.3e-4 |
| Working, fitted probe, C0 | 328 | 47.0 | 48.8 | 43.0 | 40.5 | 53.4 | p = 0.0094 |
| Working, fitted probe, vote | 356 | 45.5 | 46.6 | 39.6 | 38.2 | 50.3 | p = 6.2e-4 |
| **Robust working (both judges)** | 246 | 47.6 | 48.8 | 39.8 | 39.8 | 51.6 | +29/−7, p = 3.1e-4 |

**External corpora**

| Denominator | n | B12 | B13 | B14 | B15 | B17 | B13 vs B14 |
|---|---|---|---|---|---|---|---|
| Full (audited) | 1,524 | 60.6 | 65.6 | 84.3 | 79.2 | 84.8 | B14 ≫ B13 |
| Published working | 571 | 48.3 | 53.1 | 72.5 | 64.8 | 73.4 | p = 1.6e-28 |
| Working, C0 | 274 | 52.2 | 58.8 | 79.6 | 73.4 | 81.4 | p = 1.4e-13 |
| Working, vote | 301 | 62.1 | 67.4 | 87.4 | 82.1 | 88.4 | p = 1.3e-15 |
| Robust working | 157 | 58.6 | 65.0 | 84.1 | 79.0 | 85.4 | p = 6.9e-08 |

**Conclusion.** **No ranking changes under any of the five denominators**, and every B13-vs-B14 comparison keeps its direction and significance.
- Magnitudes move by up to about 7 points (own) and about 19 points (external).
- The magnitudes depend on the judge and the probe. The comparative conclusions do not.

**Context.** These are *admission-classification* rates on frozen text, conditional on the attack reaching admission. They are not end-to-end security effectiveness; see `REAL_MEMORY_PIPELINE_EVALUATION.md`.

**False-positive trade-off,** on the same configurations: ordinary benign 1/1088 for B12 and B13, 2/1088 for B14 and B17 (no evidence). With evidence, B13 excludes 7.5% of ordinary benign (79/1054), and 8.8–15.3% of untrusted-channel benign on the hold-outs.

## 5. Probe robustness (PR-1)

**PRE-REG PR-1.** 150 seeded own-population instances (development data), the audit's exact harness, with the fitted task replaced by a **non-leading** task: `harm_tasks.nonleading_generate` with its deterministic leak check. 44 of the 150 tasks fell back to the generic "What's been going on with my friend lately?".

| | Non-leading, C0 | Fitted, C0 | Non-leading, vote | Fitted, vote |
|---|---|---|---|---|
| Task-alone (no-memory) compliance | **5/150** | 38/150 | 7/150 | 67/150 |
| Compliance with memory | 41/150 | 109/150 | 63/150 | 139/150 |
| Working | 36/150 | 73/150 | 56/150 | 73/150 |
| Net memory effect (points) | +24.0 | +47.3 | +37.3 | +48.0 |
| Instance agreement on working status (non-leading vs fitted) | 54% | | 46% | |

**Predictions**
- **PR-1a HELD.** The non-leading base rate is 3%.
- **PR-1b FAILED.** Working rates differ by 25 points under C0, outside the ±15 predicted.

**Reading**
- **Removing the leading element does not remove the memory effect.** It stays positive and substantial: +24 points under C0, +37 under the vote.
- **But the effect's size roughly halves, and about half of the instances change working status.** The fitted probe both leads (a 25% base rate) and gives the attack an opening the non-leading probe often lacks; 44 non-leading tasks were generic.
- The two effects cannot be separated with this design.
- **Conclusion.** Working-attack status, and per-population working rates, are **probe-dependent quantities**. The paper reports them as properties of a stated probe and judge, and leans on the net memory effect and on the denominator-stable defence ranking (§4) for its conclusions.

## 6. Recommended wording for the paper

- **Use:** "the memory's causal effect: net compliance with versus without the memory on the same task". Report it at population level under both judges.
- **Use:** "working-attack status is defined per instance by a causal two-arm test; it depends on the probe and judge, and about one instance in five is ambiguous between LLM judges".
- **Report** defence results on the full and working denominators, and state that the ranking is stable across five denominators.
- **Do not write** "only 42.5% of attacks work" without the qualifiers: union over two probes, one judge, a leading probe.

## 7. Reproduction commands

```bash
python -m phase17.remediation.validity_judge_sensitivity
```

```bash
python -m phase17.remediation.validity_adjusted
```

```bash
python -m phase17.remediation.judge_adjudication
```

```bash
python -m phase17.remediation.probe_robustness
```

Notes:
- `validity_judge_sensitivity` reads cached answers and makes 10.5k judge calls.
- `validity_adjusted` is cached-only.
- `judge_adjudication` needs `GEMINI_API_KEY`.
- `probe_robustness` makes GPU calls.

## 8. Remaining limitations

- No matched benign-memory arm per audited attack.
- The working set is still a union over probes with different leading rates.
- Item-level labels are ambiguous for about 19% of items.
- Human calibration is weak (annotator 1 is the author).

## 9. Artifacts

- `phase17/data/remediation/validity_judge_sensitivity.json`
- `phase17/data/remediation/validity_adjusted.json`
- `phase17/data/remediation/judge_adjudication.json`
- `phase17/data/remediation/probe_robustness.json`
- `attack_validity_audit.json` (original, unchanged)
