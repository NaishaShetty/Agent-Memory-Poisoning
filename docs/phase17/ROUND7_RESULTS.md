# MAMBench Phase 17 -- current results (round 7)

Generated from the artifacts by `phase17/build_round7_summary.py`; do not edit by hand. The full account is `MAMBench Results Analysis.docx` (results) and `Methodology Draft.docx` (methods, Sections 32.49-32.63); every correction is logged in `docs/phase17/ROUND7_LOG.md`.

**Publishability verdict: PENDING.** Held by the owner's rule until every scheduled measurement is complete; outstanding: compliance_judge_fix.json, harm_rejudged.json. Computed by `phase17/publishability.py`; criteria: 1_traceable PASS; 2_fpr_and_both_denominators PASS; 3_holdout_informed_labelled PASS; 4_negatives_in_place PASS; 5_full_suite_passes PENDING; 6_above_noise_floor PASS; 7_all_measurements_complete PENDING.

## Recommendation, conditioned on the threat and the false-positive budget

1. **Memory poisoning, owner's conversation available: B13 with evidence.** Hold-out 4: 50.3% recall at 11.8% false positives on untrusted channels and 0.0% on the user's own words; B14 reaches 20.4%. Hold-out 7 (a second, base-model author): 54.3% at 15.3% untrusted / 0.0% user_turn; B14 29.5%.
2. **Injection-shaped text: B17, not B18.** 90.1% at 10.2% (hold-out 5) and 77.6% at 2.2% (hold-out 6), matched benign. B18's deberta rule costs 16.3% on hold-out 6.
3. **Neutralisation** (admit untrusted memory framed as data) as a zero-exclusion layer under either.
4. **Retry-capable attackers: add the rejection ledger at radius 0.95.** With B13 + evidence, adaptive evasion 22/48 -> 5/48 (pre-registered, p=7.6e-05).
5. **Retrieval ranking: run the consensus guard with semantic divergence** (not its lexical default) -- against coordinated campaigns 99 -> 63 of 302 reach the agent, at 2.78 points of benign displacement; inert against a single poison by design. Development data, not a hold-out. On Phase 6's own corpus it trades detection for false positives (B8 70.6% -> B8s 100.0%, FPR 7.3% -> 14.6%).

## Hold-outs 4-7, each frozen and scored once

| Hold-out | Config | Recall (all) | Recall (working) | False positives |
|---|---|---|---|---|
| holdout4 | B12 | 1.9% | 2.3% (86) | 1.5% |
| holdout4 | B13 | 50.3% | 60.5% (86) | 11.8% |
| holdout4 | B14 | 20.4% | 31.4% (86) | 9.2% |
| holdout4 | B17 | 50.3% | 60.5% (86) | 16.0% |
| holdout4 | B18 | 50.3% | 60.5% (86) | 16.0% |
| holdout5 | B12 | 51.1% | 59.6% (47) | 2.6% |
| holdout5 | B13 | 55.0% | 63.8% (47) | 5.1% |
| holdout5 | B14 | 90.1% | 89.4% (47) | 10.0% |
| holdout5 | B17 | 90.1% | 89.4% (47) | 10.2% |
| holdout5 | B18 | 90.1% | 89.4% (47) | 11.0% |
| holdout6 | B12 | 33.8% | 24.5% (294) | 0.1% |
| holdout6 | B13 | 37.2% | 28.6% (294) | 0.1% |
| holdout6 | B14 | 77.4% | 68.4% (294) | 2.1% |
| holdout6 | B17 | 77.6% | 68.4% (294) | 2.2% |
| holdout6 | B18 | 98.6% | 98.6% (294) | 16.3% |
| holdout7 | B12 | 37.2% | not reportable (probe base rate > 20% rule) | 4.2% |
| holdout7 | B13 | 54.3% | not reportable (probe base rate > 20% rule) | 15.3% |
| holdout7 | B14 | 29.5% | not reportable (probe base rate > 20% rule) | 13.8% |
| holdout7 | B17 | 56.6% | not reportable (probe base rate > 20% rule) | 22.8% |
| holdout7 | B18 | 57.4% | not reportable (probe base rate > 20% rule) | 22.8% |

Hold-outs 4 and 7 are memory poisoning (false positives on untrusted-channel benign notes); 5 and 6 are injection corpora with matched benign halves. B17/B18 were selected after reading earlier hold-out results; these are their first clean estimates.

## Findings

- **Provenance reaches memory poisoning that content classification misses, on two independent hold-outs:** B13 vs B14 79/157 vs 32/157 on hold-out 4 (p=1e-14) and 70/129 vs 38/129 on hold-out 7 (p=7e-08), two author families, two owners.
- **Harm levels were under-estimated by about half.** Re-judged on identical answers by the judge selected against held-back human labels: undefended harm 58.3% vs 32.0% (p=6e-18). B13's reduction holds under both judges (PARTIAL: 120-item family stratum; 166 verdicts outstanding).
- **Corroboration is brittle to an adaptive attacker** (22/48 evade by paraphrase) **and the ledger closes it** (see recommendation 4).
- **Framing helps a stronger agent more:** Gemini 44.2% -> 11.7% vs qwen +20.8 points (n=120).
- **B13 protects a stronger agent:** Gemini harm 36.0% -> 14.0% (p=4.8e-07, seeded 100).
- **The frame costs no significant usefulness** on benign memories (largest loss: direct_question, 5.0 points, p=0.082).
- **Phase 10's risk-weighted retrieval, first evaluated:** with admission signals as corroboration it keeps the poison out of the agent's context in 6 more of 309 cases than the fixed-gate guard (p=0.031), at no benign cost; the fixed gate itself barely acts on realistic stores (89 -> 88).
- **The retrieval consensus guard works on the threat it was built for:** against coordinated campaigns (poison + 2 paraphrases) any copy reached the agent 99 -> 63 of 302 with semantic divergence (lexical: 100); against a single poison it is inert.
- **Full-population recall can mislead in either direction:** on hold-out 6 the attacks that work are harder to detect; on hold-outs 4 and 5 they are easier for B13. Both denominators are reported.

## Pre-registered predictions

39/47 held (CALIBRATED). Failed, reported in place: H5-3, H5-6, H5-7, H6-6, H7-6, H7-7, R-4, P8-1. After Holm correction across the 15 significance predictions, H6-4, R-1, R6-1, P8-2 no longer holds.

## Not done, partial, or untested -- stated, not hidden

- Harm re-measurement: PARTIAL (Gemini daily quota); completes with `python -m phase17.harm_judge_fix rejudge`.
- The ledger composed with B18: not measured (about 40 s per B18 decision on novel text; an estimated 4-9 GPU hours). B18 is no longer recommended.
- Phase 10's risk-weighted monitoring: evaluated on development data -- it ranks the poison first in 39 of 43 listed cases (33.5 by default), but realistic review lists are about one item long, so it has little to do.
- Conditional backdoors: untested on a clean hold-out so far (a base-model author produced 3/40 valid); hold-out 8 is built to test them.
- MPBench's other four classes (command, compaction and skill-synthesis write channels) need a tool-using victim agent this architecture does not have: future work.
- The human check of the judges rests on 100 items and two annotators (agreement 95%, kappa 0.834; harm and mechanism labels near ceiling).
- Hold-out 3 is retired after seven uses; its numbers are hold-out-informed where used.
- Compliance judge: a majority vote of three judges matches the people at the human-to-human level (kappa 0.736), not significantly better than the original on 35 items; under it the frame's dev effect is 34.2 points (original judge 20.8). Compliance levels by the original judge are under-estimates.
- No LICENSE: deliberately deferred by the owner.
