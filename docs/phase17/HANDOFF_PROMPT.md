# Handoff prompt — MAMBench Phase 17, external review rounds 3–6

Paste everything below the line into the new session.

---

You are continuing work on **MAMBench**, a research benchmark for memory-poisoning attacks on
LLM agents with persistent memory. The repo is `C:\Agent Memory Poisoning`. It is a Windows
machine with a 6GB RTX 4050 and local Ollama models (`qwen2.5:7b`, `llama3.1:8b`, `mistral:7b`,
`phi3:mini`, `llama-guard3:8b`, `llama2`). A Gemini provider exists and reads `GEMINI_API_KEY`
from the environment. The work is destined for a published paper, so measurement integrity
matters more than favourable numbers.

## Read these first

- `docs/phase17/PHASE17_FINAL_RESULTS.md` — the one-table summary and the findings
- `Methodology Draft.docx` — §32.0 is a reader's guide; §32.19–32.48 cover rounds 3–6
- `MAMBench Results Analysis.docx` — standalone results paper, 14 sections
- `docs/phase17/ROUND6_UNFAVOURABLE_RESOLUTION.md` — the 20-item resolution record
- `phase17/data/final_inventory.json` — every result, classified, generated from artifacts
- `phase17/RUNNING_THE_PIPELINE.md` and `phase17/RESUME_AFTER_SHUTDOWN.md` — how to run things

## Non-negotiable ground rules (violating these invalidates the paper)

1. **One GPU job at a time.** Two jobs on this card stall each other: VRAM hit 5,716 of 6,141MB
   once and a run made no progress for 13 minutes. `phase17/run_all.py` serialises stages,
   kills orphans between them, and refuses to start while another phase17 process lives. The
   cross-phase audit script refuses too. Use them.
2. **Stopping a backgrounded shell does not stop its python child.** Always run
   `scripts/kill_orphan_phase17.ps1` before relaunching (pass `-ExcludePid <pid>` if the caller
   is itself a phase17 process).
3. **Develop on dev data, evaluate once on a frozen hold-out.** Three hold-outs exist, each
   digest-verified: `external_test_corpus` (1,258), `holdout2_corpus` (1,200 Mosscap),
   `holdout3_corpus` (1,000 in-the-wild jailbreaks + 995 matched benign). **Hold-out 3 has
   already been scored five times and only the first was pre-registered.** Treat further use as
   costly and say so in anything you report.
4. **Every attack-detection rate carries its false-positive cost, and both denominators.**
   Full population AND working-attack subset (`phase17/working_set.py`).
5. **Nothing is fitted on a hold-out.** If you select anything after seeing hold-out results,
   label it hold-out-informed at every point of use.
6. **Report negatives in place.** This project's credibility rests on the failures being
   visible. Do not quietly drop a result that stops being favourable.
7. **Noise floor:** ~5 points on n=120. Despite temperature 0 and fixed seeds, an identical
   prompt set scored 66, 64 and 61 of 120 across three runs — Ollama's concurrent batching is
   not bit-reproducible. Do not claim differences smaller than that.
8. **Long stages must checkpoint** (worst-case loss <3 min) and `error_registry.py` must never
   mutate anything under `phase17/data/` — it corrupted a frozen digest record once.

## What the defence configurations are

| Config | What it is |
|---|---|
| B12 | content-only stacked detector (embedding + judge logit) |
| B13 | + provenance: source-aware trust, NLI corroboration of personal claims against the owner's own conversation, write-guard against self-replicating directives |
| B14 | 11-feature fused classifier including three published detectors |
| B15 | lean refit of B14 (deberta backbone + this project's own signals) |
| B16 | B15 + **rejection memory**: a per-scope ledger of what was already hard-mitigated, refusing semantic neighbours. `rejection_memory.with_rejection_memory()` wraps *any* config |
| B17 | B13 **OR** B14 (parameter-free union) |
| B18 | B17 **OR** deberta at its FPR-matched oracle threshold |
| B19 | memory-shape gate + B13 — **FAILED, retained only as a documented negative** |
| — | **Neutralisation**: admit verbatim but frame as data, not instruction (`phase17/neutralise.py`) |

## FAVOURABLE OUTCOMES (23) — what currently works

**Defence results**
1. Unconditional harm 28.2% → **10.4%** (B13), task-alone base rate 1/309. *Not comparable to the older 42.3%→12.5% — the population changed.*
2. Provenance reaches classes content-only provably cannot, pre-registered: additive fabrication **0/72 → 37/72** (p=1e-11), fabricated preferences 0/48 → 27/48, legitimate-instruction false flags 14/40 → 2/40.
3. B13 costs **0.10s** per admitted memory vs B12's 0.15s — cheaper than what it replaces.
4. On own memory-poisoning attacks B13 **46.1%** vs deberta's 14.1%; every published baseline is 3–15% on note-shaped poisoning.
5. Our ordinary-benign FPR is far below the baselines': B13/B15 **1/1088** vs deberta 8/1088, Llama Guard 23/1088.
6. **Corroboration lifts every founding family**: sleeper 0%→37%, MPBench 11%→46%, MINJA 13%→33%, DSRM 17%→30%, FARMA 74%→87%; aggregate own-attack 46.1%→59.7%, discrimination +46.1→+52.2. *Costs 7.5% ordinary-benign FPR, all on untrusted channels.*
7. Corroboration costs **nothing** on user-authored content: 0/40, 0/6, 0/20 in the `user_turn` channel.
8. **B18 + evidence is the best configuration on this benchmark's own threat**: own attacks **64.6%** at 7.7% FPR, discrimination +56.9 (B13 +52.2, B12 +43.2).
9. **Adaptive evasion resolved**: 32/130 (24.6%) → 1/130 (0.8%) with the ledger, paired +0/−31, **p=9.3e-10**, across 20 families. *Radius was pre-registered but the seed rule was revised after the first test failed; the 0.90 radius carries a 29.7% ledger-poisoning blast radius vs 0.7% at 0.97 — the finding is the trade.*
10. **Neutralisation resolves the regime detection could not**: hold-out 3 compliance 34.0% → **14.7%**, p=2.4e-06, no significant utility loss, and **zero false positives by construction** since nothing is excluded. Active ingredient is *recency* (constraint after the content).
11. New best on hold-out 2: **B18 72.7%** vs B14's 54.2%, at 2/1054 FPR.
12. Matched operating points shrink the baseline's apparent lead from 17 points to **2.8**.

**Methodological results**
13. **Working-set discipline**: only **1,117/2,628 = 42.5%** of instances both subvert an undefended agent and implement their label. Per-population CI floors break the build on drift. This is the round's main contribution.
14. AgentPoison published records: **0/6 → 3/6** working once probed with their own trigger (four prior readings were measurement error).
15. memory_worm regeneration: 33% → **90.0%** mechanism-correct (out-of-loop judge); undefended harm 83.3% → 3.3% with B13.
16. Exfiltration is now a **tested** mechanism (structural gates; 87.5% out-of-loop) — the result is a negative *about the attack class* against 7–8B assistants, not a benchmark defect.
17. **Multi-hop is not a reasoning ceiling** — it's NLI-scorer strictness. Every agent is 80–87% correct under the LLM judge; Gemini scores 60.0%, *below* phi3:mini's 65.0%. This corrects a claim the project had published.
18. Three frozen, digest-verified hold-outs; hold-out 3 adds the project's first **matched** benign half.
19. **Prediction calibration demonstrated**: 5/5 pre-registered predictions held on an unmeasured target.
20. **Every past error's guard proven by mutation testing**: 8/8 fail when the error is reintroduced, pass when restored.
21. Recommendation conditioned on the false-positive budget rather than naming one config.
22. Union configs beat both components at no extra FPR (hold-out-informed, descriptive).
23. **Every phase verified**: 3,466 tests passed, 32 skipped, 0 failed across phases 3–17 + attribution + cross-cutting. Phase 3 and Phase 5 datasets intact, no regeneration needed.

## UNFAVOURABLE OUTCOMES (15) — fix these

1. **Matched-benign FPR is very high**: B18 54.9%, B14 54.5%, B13 33.5% — against 0.09% on ordinary memory. Detection cannot fix it (B19 failed); neutralisation addresses the regime on a different axis, but the detection numbers stand.
2. **Three of five first-round pre-registered predictions failed**: P2 (B18 beats B14 by 5 pts) at +0.4; P4 (baselines degrade most) failed *backwards*; P5 (nothing above 85%) failed for four configs.
3. **The recall ranking inverts once FPR is counted**: B14/B17/B18 reach 92.7–93.1% recall by flagging >half of benign; their discrimination is the *worst* measured.
4. **A labelling-artifact hypothesis was mostly wrong**: 82.7% of hold-out 3's benign half *is* benign-as-a-memory; filtering moves B18 only 54.9% → 49.0% (≈6 of 55 points).
5. **The content detector is the FPR source, not provenance**: content-only 43.0% on dev in-the-wild benign; corroboration adds 2 of 200. An earlier reading blamed corroboration and was wrong.
6. **"B13 is the recommendation" was wrong unqualified**: on working attacks B14 *strictly dominates* B13 on the clean hold-out (40/64 vs 8/64, +32/−0, p=5e-10). B13's 12.5% there had gone unreported.
7. **B14's hold-out gap**: 36.6 points, narrowing to 20.6 on working attacks (p=0.0001) — half composition, half something else.
8. **Union configs cannot reach a low-FPR regime**: B17's hold-out-3 FPR cannot go below 33.5% and B18's below 35.0% at *any* threshold, because both exclude whenever B13 excludes. They also leave 6.2 and 9.2 points of discrimination unused at shipped thresholds.
9. **The first pre-registered adaptive test was underpowered**: 1/38 vs 0/38 at p=1.0 — one control event caps the p-value regardless of the true effect. Superseded by a powered re-run, but the original rule did fail and the design was mine.
10. **Exfiltration regeneration only half worked**: 38% → 68.8% out-of-loop, but generator acceptance 38.1% equals the unguided rate, so the spec did not improve *authoring*.
11. **A list of my own process errors**: AgentPoison trigger error a *fifth* time; a dev fit that measured the wrong distribution; an orphan-kill script that killed the pipeline runner; a guard test that matched its own docstring; corroboration left inert in every published table; a computed arm never reported; B12 omitted from the table testing it; a thread-unsafe cache that corrupted a run; GPU contention I caused.
12. **Five of seven founding families are weakly detected content-only**: DSRM, MPBench, MINJA, MemoryGraft 11–32%; sleeper 0% before corroboration. *(These are floors — see `evidence_round6.json`.)*
13. **The memory-shape gate failed**: B19 gives discrimination +21.1 vs B13's +45.8; a structural-rules-only variant gives +45.3 (no gain). On an in-the-wild prompt corpus the benign and malicious halves are structurally indistinguishable, so no shape pre-filter can separate them.
14. **An "instability inherited from deberta" attribution was imprecise**: removing the feature *widens* the gap (+32.9 → +46.6) and collapses hold-out 2 (59.8% → 40.7%). The feature is load-bearing; the gap is a property of the fused weights.
15. **The neutralisation frame originally built is actively harmful**: `v1_prefix` raises compliance 6.7 points and costs 10 points of utility. An earlier "partial, 49/150 → 38/150" reading came from a hold-out sample that flattered it.

## OPEN ITEMS (3)

1. **B17/B18 have no clean hold-out estimate.** Both were selected after reading hold-out
   results. Hold-out 3 tested them once, and their shipped calibration is poor there.
2. **All three hold-outs are injection/jailbreak corpora.** A good score on them is evidence
   about detecting overt injected instructions arriving in memory — it says nothing about
   additive fabrication or preference hijack, for which this project's own mechanism
   populations remain the only test.
3. **No LICENSE is attached.** This is the owner's deliberate deferral; do not add one without
   asking.

## YOUR TASK

**Phase A — fix the unfavourable outcomes and the open items.**

Work through items 1–15 and the 3 open items. Some are historical facts that cannot be
un-made (#2, #4, #5, #9, #11, #14, #15) — for those, the fix is *structural*: ensure each is
(a) stated plainly where a reader will meet the relevant number, and (b) prevented from
recurring by a test that **mutation testing proves actually detects it**
(`python -m phase17.error_registry`). Do not merely assert a guard exists.

For the rest, think past the obvious repair. Worked examples from this round:
- the shape gate failed as a *detector* but was then reused productively as a *router*
- the FPR regime was unfixable by detection, so a different axis (neutralisation) was tried
- "predictions failed" was answered by pre-registering again and scoring calibration
- "not fixable" diagnoses were turned into ablations, two of which refuted the diagnosis

Highest-value concrete leads:
- **#1/#3/#8**: compose neutralisation with detection. Neutralisation has zero FPR by
  construction; a config that neutralises instead of excluding on the injection distribution
  may dominate everything measured. Not yet tried.
- **#8**: B17/B18's FPR floor is B13's rule component. A confidence-gated B13 contribution
  would remove the floor. Fit on dev only.
- **#10**: the generator cannot author exfiltration attacks. Try a different author model
  (Gemini is available) or few-shot from the 16 gate-valid instances.
- **#12**: re-measure the founding families with B18 + evidence per family — never done.
- **Open #1**: build a fourth frozen hold-out, pre-register, and give B17/B18 one clean test.
- **Open #2**: the benchmark needs a memory-poisoning hold-out, not another injection corpus.
  Consider a frozen set authored by a model family never used for attack authoring here.

**Phase B — then improve the favourable outcomes too.** Do not stop at fixing. Push each
favourable result toward its best honest version. Leads: compose the ledger with B18 (never
measured); B18 + evidence per founding family; sweep the ledger radius against its
denial-of-service surface to find the best trade; test whether neutralisation helps on *own*
attacks, not just injection corpora; check whether the ~19-point neutralisation effect is
larger on a stronger agent.

**Phase C — then state publishability.** Say plainly whether it is publishable, and list the
conditions. Apply this standard:

- **Publishable** if: every claim is traceable to an artifact; every rate carries its
  false-positive cost and both denominators; every hold-out-informed number is labelled; every
  negative result and every correction is reported in place; the full suite passes; and no
  claim rests on a number smaller than the noise floor.
- **Not publishable** if: any headline claim depends on a hold-out that was scored repeatedly
  without being labelled; any attack family is reported as measured when it is untested; or any
  guard is claimed without mutation-test proof.

Report honestly. If something cannot be fixed, say so and say why — a well-characterised
negative result is publishable and a concealed one is not. Regenerate both documents
(`python phase17/build_results_analysis_docx.py`, and the `update_methodology_*.py` scripts)
and `phase17/final_inventory.py` as you go, and commit after each substantive result.
