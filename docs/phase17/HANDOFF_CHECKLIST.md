# Handoff checklist — every item of HANDOFF_PROMPT.md, with its evidence

Status as of 2026-10-08. "Guard" means a test that `scripts/run_registry.py` (the mutation
registry) has proven: it fails when the error is reintroduced and passes once restored
(`phase17/data/error_registry.json`). R7-n are entries in `docs/phase17/ROUND7_LOG.md`.

## Ground rules

| Rule | How it is kept |
|---|---|
| One GPU job at a time | `run_round7.py` serialises stages and kills orphans; audit refuses while a stage runs (guard `gpu_contention`) |
| Stopped shell ≠ stopped child | `kill_orphan_phase17.ps1` before every relaunch; string `-ExcludePid` list (guards `orphan_killer_kills_caller`, `orphan_killer_pid_list`); registry runs via `scripts/run_registry.py` so the killer cannot hit it mid-mutation |
| Dev, then one frozen hold-out | Hold-out 3 RETIRED by the owner after 7 uses (guard `holdout3_reuse`); hold-outs 4–7 frozen (SHA-256) and scored exactly once under pre-registrations committed first; the default pipeline cannot score a hold-out (guard `pipeline_rescores_holdout`) |
| FPR + both denominators | Every hold-out table; computed check in `phase17/publishability.py` criterion 2; HO7's working subset declared not reportable by the 20% rule fixed beforehand |
| Hold-out-informed labelled | B17/B18 labelled throughout; the hold-out 3 "dev" set exposed as the hold-out (R7-1, guard `dev_holdout_overlap`); #5's attribution labelled hold-out-informed |
| Negatives in place | Every prediction reported (guard `prediction_omitted`); round 7 failures in Table 16 |
| Noise floor | Measured, not argued: SD 0.8–1.7 points over three repeats; verdict criterion 6 checks headline claims against it |
| Checkpointing; never mutate phase17/data | guards `missing_checkpoint`, `frozen_corpus_edited`, `test_writes_data_artifact`; session-wide read-only data guard in `phase17/tests/conftest.py`; adaptive stages now checkpoint per seed |

## Unfavourable outcomes 1–15

| # | Item | Status | Evidence |
|---|---|---|---|
| 1 | Matched-benign FPR very high (HO3) | **Characterised; largely corpus-specific** | HO5 B17 10.2%, HO6 B17 2.2% (matched benign, scored once). Neutralisation composed with detection: dominated on dev, primary FAILED on HO5 (underpowered), HELD on HO6 (246 → 227 of 500, p=0.023) |
| 2 | 3 of 5 predictions failed (historical) | **Stated + guarded** | Table 9A lists all five; guard `prediction_omitted`. Round 7 re-pre-registered: 29/35 held, CALIBRATED |
| 3 | Recall ranking inverts once FPR counted | **Addressed** | Recommendation conditioned on budget; on clean hold-outs B17 runs at 10.2% / 2.2%; B18 dropped (16.3% FPR on HO6) |
| 4 | Labelling-artifact hypothesis mostly wrong (historical) | **Stated + guarded** | Results paper after Table 9: 54.9% → 49.0% from artifacts; guard `fpr_labelling_artifact_claim` |
| 5 | Content detector, not corroboration, is the FPR source (historical) | **Stated + guarded; labelled hold-out-informed** | Results paper after Table 9 (86/200 vs +2); guard `fpr_blamed_on_corroboration_claim` |
| 6 | "B13 is the recommendation" was wrong unqualified | **Resolved by clean data** | HO4: B13 50.3% vs B14 20.4% on memory poisoning (p=1.4e-14); recommendation split by threat |
| 7 | B14's hold-out gap | **Characterised, not closed** | deberta ablation (feature load-bearing); B14 77–90% on HO5/HO6 injection corpora, 20.4% on HO4 memory poisoning |
| 8 | Union FPR floor | **Tried; failed on dev; floor shown corpus-specific** | B20/B21 (no content detector): −8 points recall, no FPR saving; corroboration v2 (abstain, contradiction): failed; HO5/HO6 floors 10.2% / 2.2% |
| 9 | Underpowered first adaptive test (historical) | **Stated + guarded** | guard `underpowered_preregistration`; `require_power` refused today's adaptive design until fixed (R7-24) |
| 10 | Exfiltration authoring | **Improved, still weak** | few-shot authoring 11/40 (qwen), 7/40 (Gemini) vs 1/40 spec-only; B-6 HELD (27.5%) |
| 11 | Own process errors (historical) | **Stated + guarded** | Results paper §10; guards for each, incl. new `b12_omitted_from_table` (which found Table 8 still missing B12 — fixed) |
| 12 | Founding families weak content-only | **Re-measured with evidence** | Table 5E: FARMA 87%, AgentPoison 65%; MemoryGraft 34%, DSRM 30% remain weak — stated |
| 13 | Memory-shape gate failed | **Negative retained** | B19 reported as failed; reused as a router (round 6) |
| 14 | deberta attribution imprecise (historical) | **Stated + guarded** | guard `superseded_claim_summary` (claim `deberta_inherited`) |
| 15 | Harmful v1 frame (historical) | **Stated + guarded** | guard `harmful_neutralisation_frame` |

## Open items

| # | Item | Status |
|---|---|---|
| 1 | B17/B18 lack a clean estimate | **Done**: HO4, HO5, HO6, HO7 each scored once. B18 then failed: 16.3% FPR on HO6, excludes 4.9% of user_turn on HO7 |
| 2 | No memory-poisoning hold-out | **Done**: HO4 (mistral author, LoCoMo owner 7) and HO7 (base-model author, owner 8). Conditional backdoors remain untested on a clean hold-out (3/40 valid) — reported as untested |
| 3 | LICENSE | **Deferred by the owner — not added** |
| 4 | Second human annotator | **Done** (2026-10-09): independent, blind; 95% / kappa 0.834 with annotator 1; harm and mechanism labels at ceiling; original harm judge misses the same 16 harms (R7-30) |
| 5 | Compliance judge vs people (kappa 0.596) | **Improved, not proven**: majority vote of three judges, kappa 0.736 (human-to-human 0.731), selected by a rule committed before scoring; 5 fixed / 2 broken on 35 items (p=0.45). Dev frame effect -20.8 -> -34.2 pts under it (R7-32, R7-34) |
| 6 | B13 false positives on untrusted notes | **Dev result**: epistemic quarantine (frame v1) 79/1054 -> 0 excluded; corroboration-only attacks asserted 14/109 framed vs 2 excluded vs 40 raw (R7-31). Tested once on hold-out 8 |
| 7 | Conditional backdoors on a clean hold-out | **Scheduled 2026-10-10**: hold-out 8 (Gemini author) |

## Phase A leads

| Lead | Status |
|---|---|
| Compose neutralisation with detection | Done (see #1) |
| Confidence-gated B13 to remove the floor | Done as B20/B21 and corroboration v2 — failed on dev, reported |
| Exfiltration with another author / few-shot | Done (see #10) |
| B18 + evidence per founding family | Done (Table 5E) |
| Fourth frozen hold-out | Done — four (HO4–HO7) |
| Memory-poisoning hold-out from a new author family | Done (HO4, HO7) |

## Phase B leads

| Lead | Status |
|---|---|
| Ledger composed with B18 | **NOT measured.** ~40 s per B18 decision on novel text → an estimated 4–9 GPU hours; B18 is no longer recommended. Measured instead: ledger + B13-with-evidence (the actual memory-poisoning recommendation), pre-registration addendum 4 |
| Ledger radius sweep vs denial-of-service | Done: 0.95 recommended (5/130 evasion, 6.4% blast radius) |
| Neutralisation on own attacks | Done: harm 28.8% → 24.6% (p=0.098, n.s.); with B13 9.1% → 6.5%. Re-tested with more data (addendum 8, P8-2): pooled 123 → 104 of 424, p=0.037 (HELD at its alpha; not after Holm; new 175 alone p=0.15) |
| Neutralisation on a stronger agent | Done: Gemini 44.2% → 11.7% vs qwen 50.8% → 30.0% (n=120, p=2e-10) |

## Found and measured beyond the handoff (round 7)

- Harm levels were under-estimated by about half: 58.3% vs 32.0% undefended under a judge selected
  against held-back human labels (p=6e-18). PARTIAL: 163 Gemini verdicts outstanding (daily quota); scheduled for 2026-10-10.
- Corroboration is brittle to an adaptive attacker: 22/48 evasions (Fisher p=0.0096 vs stateless).
- On hold-out 6, the attacks that work are ~9 points harder to detect than the population.
- The frame costs no significant utility on benign memories (largest −5.0 points, p=0.08); re-tested on 600
  new notes (P8-1): −3.8 points, p=0.056 — a small consistent cost of ~4 points, not proven.
- Compliance levels judged by the original judge are under-estimates (as harm levels were); the frame's
  reduction holds under both judges (R7-34).
- Predictions: 39/47 held; after Holm across 15 significance predictions, H6-4, R-1, R6-1 and P8-2 hold
  at their own alpha only.

## Phase C

The verdict is computed by `phase17/publishability.py` against the two-sided standard and rendered
as Section 14 of the results paper. **Held at PENDING by the owner's decision until the harm
re-measurement completes** (the Gemini quota did not reset on 2026-10-09; next reset ~05:30 on 2026-10-10; see R7-29 in
ROUND7_LOG.md). Criterion 7 enforces it.

## Phase-by-phase check against the project specification (2026-10-09)

| Phase | Specified | Implemented in | Status |
|---|---|---|---|
| 3 | Clean agent-memory environment | `phase3/` (Methodology §12) | ✓ frozen; 1,776 tests |
| 4 | Six named attacks + sleeper behind a common interface; reconstructions labelled | `phase4/attacks/`, AttackAdapter (§17) | ✓ disclosed: AgentPoison weaker than the original; MPBench 2 of 6 classes |
| 5 | Instrument insertion, retrieval, updates, decisions, provenance, interactions | `phase5/` (§18-19) | ✓ all six |
| 6 | Provenance/governance admission; flag, restrict, quarantine | `phase6/defense/` (§21) | ✓ |
| 7 | Propagation monitoring, self-reinforcing patterns | `phase7/`, `phase12/propagation/` (§22) | ✓ evaluated on all seven attacks; disclosed: never fires in Phase 14's live pilot (no ancestor memories) |
| 8 | Sleeper detection by content, temporal, retrieval, activation signals | `phase8/detection/` (§23) | ✓ four signals |
| 9 | Backward chain action -> memory -> origin, with uncertainty | `attribution/wiring/forensics.py` (§24) | ✓ disclosed: ambiguity unreachable by design |
| 10 | Risk estimates influencing retrieval, monitoring, verification, quarantine | `phase6/defense/risk/` (§25) | verification + quarantine LIVE (Phase 14 B9); **retrieval ranking first evaluated 2026-10-09** (addendum 5: 88 -> 82 of 309, p=0.031, not Holm-robust; the fixed gate itself barely acts); **monitoring built and tested, not evaluated** (no measurable outcome) |
| 11 | GNN + GLN, combined into a hybrid | `phase11/gnn`, `phase11/gln` (online), `phase11/hybrid.py` (§26) | ✓ |
| 12-16 | PAR, PR, SDR, AMR, DGS; source accuracy, path fidelity, uncertainty, time-to-attribute; task success, utility retention, latency, memory overhead | `phase12/`-`phase15/`, `docs/phase16/` (§27-31) | ✓ every named metric computed |
| 17 | Ablation and generalisation | `phase17/` (§32) | ✓ |
