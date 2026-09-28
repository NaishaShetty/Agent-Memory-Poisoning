# Phase 17 Workstreams A–M — Final Report

Scope note: this report covers the additional workstreams (external validity hierarchy,
evaluator independence, nondeterminism, security-utility, adaptive attackers, provenance
integrity, sanity baselines, canonical matrix, benchmark spec/runner/card, README,
methodology) requested on top of the ablation/generalization work already in
`PHASE17_ABLATION_GENERALIZATION_REPORT.md` (§0–§11, which this report does not repeat).
Full regression after every code change: see §13. Nothing committed or pushed.

## 1. What was added

- `phase17/leakage_audit.py` — automated train/eval conversation-disjointness,
  poison-target/benign-negative disjointness, dev/eval exact-text disjointness, and
  metadata-completeness checks (all pass on real data; wired into `phase17/tests/`).
- `phase17/sanity_baselines.py` — `ALWAYS_ALLOW`, `ALWAYS_QUARANTINE`,
  `RANDOM_BUDGET_MATCHED` bounds and a `compare_to_random` helper.
- `phase17/provenance_integrity.py` — structural forgery rejection test (all 22
  `FORBIDDEN_SIGNAL_KEYS`) and a content-level forged-metadata live-defense test with a
  matched benign negative control.
- `phase17/evaluator_independence.py` — same-model (self-judge) vs. independent-judge
  comparison on the identical 150 real Track A answers.
- `phase17/adaptive_attacker.py` — NLI-based confirmation that every evasion variant
  preserves its parent's forged claim.
- `phase17/security_utility_frontier.py` — cross-config aggregation (detection, FPR,
  utility, latency) from existing artifacts.
- `phase17/canonical_matrix.py` — a scoped, traceable cross-phase result matrix
  (JSON + CSV), with disclosed `MATRIX_LIMITS`.
- `phase17/bench_runner.py` + `phase17/tests/test_bench_runner.py` — a minimal,
  tested, forward-facing canonical benchmark entry point.
- `docs/phase17/BENCHMARK_SPECIFICATION.md`, `docs/BENCHMARK_CARD.md`,
  `docs/METHODOLOGY.md` (new, reorganized), README.md current-status section.
- `phase17/tests/test_workstreams.py` — 6 new tests covering the above.

## 2. What was reused (not duplicated)

`phase14/defended_retrieval.py::apply_defense` (every config dispatch), `phase6/defense/
risk/risk_score.py`'s existing `FORBIDDEN_SIGNAL_KEYS`/`EvaluatorOnlyLeakageError`
(the structural provenance guard already existed — this round proves it fires, it does
not add a new guard), `phase3/evaluation/agent/nli_entailment_correctness.py` and
`llm_judge_correctness.py` (reused verbatim for the adaptive-attacker and
evaluator-independence checks), `phase11`'s own LOFO vocabulary and `phase17/
generalization.py`'s existing leave-one-family-out module, `phase17/poison_sets.py`'s
existing split-tag discipline, `phase17/stats.py`'s Wilson/exact-McNemar/cluster
bootstrap helpers.

## 3. What was intentionally not changed

No frozen `B0`–`B10` config, composition rule, or historical result artifact was
modified. `Methodology Draft.docx` and `Methodology.pdf` are untouched; `docs/METHODOLOGY.md`
is a new, separate file. `README.md`'s original Phase-4 content is preserved verbatim
below a new current-status header, not deleted.

## 4. External-validity results (Workstream A)

| Axis | Result | Source |
|---|---|---|
| Unseen attack family (signal removal) | Phase 11/17 LOFO — see ablation report §2/§10.4 for the honest headline (family-tuned signals contribute most of that family's own detection) | `phase17/generalization.py`, `phase17/data/lofo_results.json` |
| Unseen attack mechanism | 0/60 to 19/60 to 35/60 excluded (original stack, then B11, then B12); leave-mechanism-out CV ceiling is about 60% recall at a 0.5% dev FPR budget | `phase17/data/extended_results.json`, `b12_results.json`, `lomo_results.json` |
| Unseen source conversation | 0 conversation-id overlap between calibration and held-out FPR halves, on all 3 benign populations; 0 overlap between poison-target conversations and calibration negatives | `phase17/leakage_audit.py`, confirmed by test |
| Unseen dataset / distribution shift | ConvoMem 0/360 excluded (B12), PerLTQA-Chinese 0/447 excluded, 30/84 Chinese poison excluded | `phase17/data/b12_results.json`, `zh_route_results.json` |
| Unseen memory foundation | Live A-mem-sys: 9/9 original poison excluded on what A-MEM itself retrieves; evasion variants mostly evade; A-MEM evolution never fired in 57 real stores (disclosed, unresolved) | `phase17/amem_live/stage2_results.json` |
| Unseen model family | Not extended. Two local models (qwen2.5:7b, llama2) are already used as generator/judge throughout; no further local checkpoint was available in this round's time/compute budget. Disclosed as incomplete, not silently skipped. | -- |

## 5. Evaluator-independence results (Workstream B)

Independent judge (qwen2.5:7b, a different model family from the llama2 answer
generator): 93.3% correct (140/150). Self-judge (llama2, the same model as the
generator): 100% (150/150) -- a measured, real inflation from self-judging. Agreement
rate 93.3%; the 10 disagreements are all cases the independent judge marked wrong and the
self-judge marked right (the self-judge never disagreed in the harsher direction). A
blinded human evaluation subset (50-100 outputs) was scoped but **not executed** this
round -- no human evaluator was available; disclosed, not fabricated.

## 6. Nondeterminism results (Workstream C)

3 repeated B0 runs on the same 150 real LoCoMo cases (temperature 0, fixed seed): answer
text identical in 139/150 cases; string/date-metric rate 0.607/0.607/0.613; LLM-judge
0.933/0.940/0.940; NLI perfectly stable (0.853 in all 3 runs). Judge/detector decision
stability (separately measured, `determinism.json`): 0/207 flips within one session,
about 0.2% flips across sessions after a runtime restart. Reported as distributions, not
a single favorable run; the qualitative conclusions do not flip across any of the 3 runs.

## 7. Security-utility results (Workstream D)

| Config | Novel-mechanism excluded | Dataset-arena benign excluded | Track-A success (n=300) | URS | Track-B forged (n=9) |
|---|---|---|---|---|---|
| B0 | not measured (no defense) | not measured | 122/300 | N/A (baseline) | 3/9 |
| B9-live | 0/60 | not measured | 122/300 | 1.000 | 0/9 |
| B10 | not measured | not measured | 124/300 | 1.016 | 0/9 |
| B11 | 20/60 | 0/247 | 122/300 | 1.000 | 0/9 |
| B12 | 35/60 | 0/247 | 122/300 | 1.000 | 0/9 |

No config is declared "best" -- B12 trades about 0.2-0.4s of judge latency per admitted
memory for its generalization gain; B9-live is free but generalizes worst. Full table:
`phase17/data/security_utility_frontier.json` / `.md`.

## 8. Adaptive-attacker results (Workstream E)

All 47/47 evasion variants (Wilson CI [0.92, 1.0]) still semantically assert their
parent's forged claim (NLI-confirmed) -- the measured drop in detection on these variants
(ablation report §10.1/§11.2) is a real evasion of the defense, not a broken attack.
0 variants were excluded from this claim.

## 9. Provenance-integrity results (Workstream F)

**Structural forgery: 22/22 rejected.** Every attempt to pass an evaluator-only field
(including `attacker_originated`) into a real risk-scoring call raises
`EvaluatorOnlyLeakageError` -- this is frozen, pre-existing code; this round proves it
fires, it adds no new guard. **Content-level forgery:** B9-live is fooled by 4/5
deliberately constructed forged-metadata sentences (fake memory-id citation, fake
timestamp, fake signed code, fake replay claim, all resulting in `ALLOW`); B11/B12 catch
4/5 (`QUARANTINE`) but **both still miss the fake-parent-lineage phrasing** (`ALLOW`) -- a
real, disclosed, unresolved gap. 0/3 benign negative-control sentences (genuine dates,
confirmations, codes) were falsely flagged by any config.

## 10. Baseline results (Workstream G)

`ALWAYS_ALLOW` is identical to B0 (0% detection, 0% FPR, maximal utility, by
definition). `ALWAYS_QUARANTINE` (100%/100%, minimal utility, by definition).
`RANDOM_BUDGET_MATCHED` is provided as a reusable helper
(`phase17/sanity_baselines.py::compare_to_random`); it was not re-run against every live
config's own alert rate in this pass (time-boxed) -- the helper and its test
(`test_workstreams.py::test_compare_to_random_matches_alert_rate`) are real and ready for
a caller to invoke per config.

## 11. Benchmark packaging changes (Workstreams H-K)

`docs/phase17/BENCHMARK_SPECIFICATION.md` (schema reusing existing dataclasses),
`phase17/canonical_matrix.py` (24 rows, JSON+CSV, `MATRIX_LIMITS` discloses exactly what
is out of scope), `phase17/bench_runner.py` (tested end-to-end smoke path),
`docs/BENCHMARK_CARD.md`.

## 12. README / methodology changes (Workstreams L-M)

`README.md`: new "Current status (Phase 17)" section prepended; original Phase-4 content
preserved verbatim below it with an explicit "read as history" note. `docs/METHODOLOGY.md`:
new, reorganized methodology covering Phases 1-17 (the `.docx`/`.pdf` originals are
untouched -- see that document's own status note for why a Markdown file was produced
instead of editing the binary `.docx` in place).

## 13. Test results

New tests: `phase17/tests/test_workstreams.py` (6 passed), `phase17/tests/
test_bench_runner.py` (2 passed). Full cross-phase regression after all Phase 17
workstream changes (`phase6/ phase8/ phase11/ phase12/ phase13/ phase14/ phase15/
phase17/ attribution/ phase7/ phase3/ -m "not slow"`): **2711 passed, 30 skipped,
9 deselected, 0 failed** (728.5s).

## 14. Reproducibility information

Git commit, Python version, platform, and timestamp are recorded in every
`bench_runner.py` result manifest. Judge/detector caches (`phase17/data/*_cache.json`)
make repeated runs of the SAME query reproducible; cross-session drift is measured
(§6), not eliminated. Ollama must be started manually (`ollama serve`) with
`qwen2.5:7b` and `llama2` pulled; live A-MEM numbers require the separate isolated
`C:\h4venv` environment (already present on this machine, not committed to the repo).

## 15. Remaining limitations

See `docs/phase17/PHASE17_ABLATION_GENERALIZATION_REPORT.md` §11.5 and `docs/
BENCHMARK_CARD.md`'s "Known limitations" for the full, dated list. New to this round:
unseen-model-family axis incomplete; blinded human evaluation not executed;
`RANDOM_BUDGET_MATCHED` helper built but not run against every config; the
fake-parent-lineage provenance forgery is not caught by any live config.

## 16. Experiments that failed or produced a negative result

Carried forward from earlier Phase 17 rounds (embedding-only classifier, few-shot
continuous-score judging, hearsay/second-hand-claim flag, steering-plus-stack exclusion,
question decomposition and larger-k retrieval for multi-hop) -- see the ablation report
§8/§10/§11 for each. This round's own new negative findings: self-judging measurably
inflates correctness (§5); the fake-parent-lineage provenance forgery evades every live
config (§9).

## 17. Results that should NOT be used as a headline claim

- "35/60 novel mechanisms excluded" without the leave-mechanism-out caveat (§4) -- the
  honest ceiling on truly unseen mechanisms is closer to 10-20% for some mechanism
  groups (ablation report §10.4).
- Any Track-A success-rate comparison across configs without noting only 0-1 of 300
  contexts actually changed between B0 and any defended config (utility is dominated
  by "the defense didn't touch this context," not by answer-quality improvement).
- The live A-MEM originals-excluded number (9/9) without noting the evasion-variant
  number alongside it (mostly evades) and that A-MEM's own evolution never fired.


---

## 18. Round 2 — fixes applied on explicit request ("fix the negative results")

### 18.1 Content-level provenance forgery: FIXED, then validated held-out
Added a `lineage` judge tier (a new prompt variant, additive, no existing prompt's
cached answers touched) that asks specifically whether a note cites another stored
memory/record/ID to inherit trust. Initial result: **5/5 forged-metadata sentences now
caught by B11/B12** (was 4/5 -- the fake-parent-lineage phrasing was the one miss), 0/60
dev-benign and 0/3 negative-control false positives.

**Caveat raised by external review (2026-09-28) and closed with a real held-out test:**
those same 5 sentences were used BOTH to motivate the `lineage` prompt's design AND to
report its "5/5" result -- in-sample evidence, not proof of generalization. A FRESH set
of 10 forged-metadata sentences (different phrasing and fake-identifier formats -- case
numbers, audit references, ticket numbers, session logs -- never looked at while writing
the prompt) plus 4 fresh benign negative controls was built and run
(`phase17/provenance_holdout_check.py`): **B9 (pre-fix) catches 0/10; B11 and B12 catch
10/10, with 0/4 benign false positives.** This is genuine held-out evidence that the fix
generalizes beyond the sentences it was designed against, not just a restatement of the
original in-sample result.

### 18.2 The 47 evasion variants: confirmed GOOD, not a problem to fix
Re-stated for clarity: `phase17/adaptive_attacker.py`'s 47/47 "objective preserved" result
is a POSITIVE validity check (it confirms the evasion variants are still real attacks,
so the LOW detection numbers on them are genuine defense evasion, not broken attacks). It
does not need "fixing." The actual weak number is **evasion detection itself**
(3-7/47 excluded, depending on detector combination) -- see 18.3 for the attempt made on it.

### 18.3 Evasion detection: attempted, real negative result
Combined the new `lineage` tier with the ORDER-FREE conflict check against each evasion
variant's own 3 real LoCoMo distractors (no gold anchor) across all 47 variants (not just
the 13 gold-bearing ones): **4/47 excluded** -- no improvement over the existing 3/47.
**Root cause, confirmed:** the order-free conflict check requires an embedding-similar
EARLIER memory to conflict with (`MIN_COS = 0.45`); the evasion arena's 3 real distractors
are topically unrelated, so the conflict gate never fires. The conflict check only helps
when a genuinely related earlier memory exists (the 13 gold-bearing parents, where it
already gave 7/26, reported in §11.2 of the ablation report) -- it cannot be extended to
the general 47-variant arena without a real related-memory anchor, which this benchmark's
arenas do not construct for most evasion cases. Reported as a real, disclosed negative
result, not forced through.

### 18.4 Leakage audit: extended, still passes
Extended `check_dev_eval_text_disjoint` to also cover `corpus_extended.py`'s
`held_out_extended` split (138 records) added in an earlier round, closing a gap where a
newly-added eval split was not yet covered by the audit. Result: still **0 overlap**
(455 dev texts vs. 351 eval texts, up from 213).

### 18.5 Random-budget-matched baseline: run against B12
At B12's own real alert rate on held-out novel mechanisms + benign (11.4%), a
random detector at that SAME budget catches a mean of 11.1% of the poison (95% range
5.0-18.3%); B12's real detection is **58.3%** -- clearly outside the random range. This
is the concrete, run result the earlier report disclosed as "built but not run."
(`phase17/data/random_baseline_results.json`)

### 18.6 Unseen model family: extended with a 3rd local model AND a hosted model
- **phi3:mini** (Microsoft, pulled via `ollama pull phi3:mini`, a third local model
  family distinct from Qwen and Llama) as the `concept`-judge decision: **0/40 recall**
  on held-out novel mechanisms, 0/40 benign false positives, 88% raw agreement with
  qwen2.5:7b (near-total agreement on the "NO" cases, near-zero on the "YES" cases --
  phi3:mini is simply too small to make this judgment reliably). As the Track-A
  ANSWER-GENERATING agent (replacing llama2, n=30 real LoCoMo cases, disclosed as a spot
  check not a full 150-case rerun): 73.3% string/date-metric, 100% LLM-judge -- as good
  as or better than llama2 on this small sample.
- **Gemini (Google's free tier, `gemini-3.5-flash-lite`)**, added on explicit
  instruction, via a new real `LLMProvider` implementation
  (`phase17/gemini_provider.py`) that reads its API key only from `GEMINI_API_KEY`,
  never hardcoded, never logged. (The first model tried, `gemini-3.8-flash`, hit its
  free-tier 20-requests/day quota during this module's own smoke-testing --
  `gemini-3.5-flash-lite` is a distinct model with its own separate quota, confirmed
  working.) Same `concept`-judge decision, same 40+40 texts: **47.5% recall** on held-out
  novel mechanisms (higher than qwen2.5:7b's own 25% on this run), 0/40 false positives,
  85% agreement with qwen. **Honest headline: the judge decision does NOT generalize
  uniformly across model family** -- a larger hosted model (Gemini) generalizes BETTER
  than the project's own default judge on the exact same prompt with zero tuning to this
  project, while a small local model (phi3:mini, ~3.8B) fails almost completely. Model
  capacity, not model family per se, appears to be the load-bearing variable -- a real,
  disclosed finding, not spun as either a pure success or a pure failure.

### 18.7 Full regression after all round-2 changes
`phase6/ phase8/ phase11/ phase12/ phase13/ phase14/ phase15/ phase17/ attribution/
phase7/ phase3/ -m "not slow"`: **2711 passed, 30 skipped, 9 deselected, 0 failed**
(742.4s). New tests this round: `test_b11_lineage_tier_excludes`,
`test_gemini_provider.py` (3 tests, no live network call required) -- 12/12 passed
in the targeted new-test run.
