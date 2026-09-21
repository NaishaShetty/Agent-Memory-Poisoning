# Phase 12 Plan — Systematic Evaluation (Security, Attribution, Utility)

Status: DRAFT, written before the implementation it governs, per this project's own
standing discipline (`attribution/ATTRIBUTION_METHODOLOGY.md`, `docs/phase9/PHASE9_PLAN.md`,
`docs/phase10/PHASE10_PLAN.md`'s own opening lines). Finalized once the implementation and
its real test scenarios validate against it; any change forced by implementation reality
is reconciled here explicitly, not silently.

Scope note: the user described this as "Phases 12–16 — Evaluation," one continuous arc
covering security, attribution, and utility measurement across attacks, datasets, and
workloads. This document plans **Phase 12 specifically** — the evaluation *framework*
and its first real metric family (security) — and proposes, but does not commit to
without confirmation, how 13–16 divide the remaining work (Section 2).

## 1. Research Question

*"Across MAMBench's real attacks, real datasets, and real defense configurations already
built (Phases 4–11), do the defenses actually work — not just on the one 75-scenario
held-out corpus B0–B10 already report against, but across the fuller space of real
attack/dataset/workload combinations this project has built and never systematically
swept — and at what real cost to attribution confidence and agent utility?"*

This is a **measurement** phase, not a new-defense or new-detector phase. Phase 12 invents
no new attack, defense, or learned component. It asks whether the real capabilities this
project already has, built across eleven phases, have been evaluated as thoroughly as they
could be, and reports the real answer, positive or negative, exactly as every prior phase
in this project has.

## 2. Proposed division of the 12–16 arc (confirm before implementation)

| Phase | Proposed scope | Why this split |
|---|---|---|
| **12** (this plan) | Evaluation framework + **Security** metrics (PAR, PR, SDR, AMR, DGS) | Security metrics reuse the most already-built infrastructure (Phase 4 attacks, Phase 5 ledgers, Phase 6–11 defenses, B0–B10) — the natural first slice, and the one that validates the framework itself before extending it. |
| 13 | **Attribution** metrics (source accuracy, path fidelity, uncertainty, time-to-attribute) | Reuses Phase 9's `attribution/` layer directly; depends on Phase 12's evaluation-run scaffolding existing first. |
| 14 | **Utility** metrics (task success, utility retention, latency, memory overhead) | Reuses Phase 3's agent-runtime/campaign infrastructure; independent of 12/13's findings, but sequenced after so the same evaluation-run scaffolding is reused rather than rebuilt a third time. |
| 15 | **Cross-cutting sweep** — the full attack × dataset × workload × defense-configuration matrix, all three metric families together | Cannot start until 12–14 each have a working single-metric-family pipeline to compose. |
| 16 | **Synthesis report** — the one document presenting security/attribution/utility together, with the security-vs-utility trade-off curve explicit | The actual deliverable stakeholders read; depends on everything above being real and complete. |

**This split is a proposal, not a decision** — confirm or adjust before Phase 13 begins.
Nothing below commits Phase 13–16 to a fixed design; each gets planned the same way (a
`PHASE1X_PLAN.md`, written before its implementation) when its turn comes.

## 3. Why this is not already covered

| Existing capability | Where | What it is, and its real limit |
|---|---|---|
| Per-attack, per-defense-configuration detection/FPR (`B0`–`B10`) | `phase6/evaluation/ablations/`, `phase11/evaluation/run_b10.py` | Real, and the single most-reused number in this project — but computed on ONE fixed 75-scenario held-out corpus, ONE point in the attack/dataset/workload space, never swept. |
| Seven real, frozen attacks, each independently validated | `phase4/attacks/*` | Real attack mechanisms exist, but no report yet asks "how does defense X perform against attack Y run against dataset Z under workload W" as a full matrix — only single-corpus snapshots. |
| Four real datasets, 1.26M real records (Phase 1/2), only a small fraction ever used by any downstream phase (Phase 11.x Dataset Audit, `docs/phase11/PHASE11_X_DATASET_AUDIT_REPORT.md`) | `data/processed/unified_memory/*` | Real volume exists across LoCoMo/LongMemEval/MSC/ConversationChronicles; no systematic per-dataset defense evaluation has ever been run — Phase 11's own work used at most a few hundred records from 3 of the 4. |
| Real LOFO / real-corpus-generalization harnesses (Phase 11's own final work) | `phase11/gnn/lofo_combined_untrained.py`, `phase11/gnn/real_attack_corpus_detector.py` | The closest existing precedent for "how well does this generalize beyond the one corpus it was built on" — directly informs what Phase 12's **DGS** metric (Section 4) should measure, reusing this exact pattern rather than inventing a new one. |
| A complete, real attribution layer (five attribution types, real evidence, real uncertainty statuses) | `attribution/`, `attribution/ATTRIBUTION_METHODOLOGY.md` | Real and tested against 11 real scenarios (A–K) — but no report yet measures attribution's OWN accuracy/confidence/cost systematically across the attack space; it has been validated case-by-case, not benchmarked. |
| Real Phase 3 agent-evaluation campaigns with real task success/failure outcomes | `phase3/experiments/results/`, e.g. `clean_agent_dataset_locomo_120x2.json` | Real agent answers, real per-task success scoring already exist for the CLEAN (no-defense) condition — but no campaign yet measures the SAME real tasks with defenses ACTIVE, so utility cost of running the real Phase 6–11 pipeline has never been measured. |

**The real, named gap Phase 12 exists to close**: every attack, every defense, and every
dataset this project has built computes something real, and has been validated in
isolation or on one fixed corpus — but nothing yet asks the same real questions ("does it
detect, does it attribute correctly, does it cost the agent anything") *systematically*,
across the real combinations this project has never actually run together, and reports
one governing number set stakeholders can act on.

## 4. Metric definitions — PROPOSED, must be confirmed before implementation

The user's prompt named five security-metric acronyms without expanding them. Guessing
wrong here would misdirect the entire phase, so each is defined below as a **precise,
falsifiable proposal**, grounded in infrastructure this project already has, explicitly
flagged as needing your confirmation (or correction) before any code is written.

| Acronym | Proposed name | Proposed definition | Real, already-existing basis |
|---|---|---|---|
| **PAR** | Poison Admission Rate | Fraction of injected poison artifacts that Phase 6's admission guard actually admits (`ADMISSION_ADMITTED`) into the memory store, before any downstream defense runs | Every attack's `Injector.inject()` already returns a real `admission_status` (Phase 4) — this is a direct aggregation of an already-computed real field, no new instrumentation needed |
| **PR** | Propagation Rate | Of admitted poison, the fraction that produces at least one real downstream `DERIVED_FROM`/taint-propagation edge (i.e., actually spreads) before any guard intervenes | Reuses Phase 7's `build_propagation_graph()`/`campaign_signals.py` and Phase 9's PROPAGATION attribution type directly |
| **SDR** | Sleeper Detection Rate | Detection rate specifically for the Sleeper Memory Poisoning attack family (dormant-then-activated), reported separately from the pooled `poison_detection_rate` B0–B10 already compute | This is the SAME `per_attack_family_detection` field `ConfigurationMetrics` already returns (`phase6/defense/orchestration/pipeline.py`), filtered to one family — no new computation, a reporting choice |
| **AMR** | Attack Mitigation Rate | Of the poison that IS detected, the fraction where the resulting action (`QUARANTINE`/`BLOCK`) actually prevents the poisoned content from being retrieved/used afterward — i.e., detection that produces a real downstream effect, not just a logged flag | New: requires checking a post-action retrieval/EXPOSURE query against the real store, confirming the quarantined/blocked memory is genuinely excluded — buildable directly on `phase6/defense/orchestration/pipeline.py`'s existing action semantics |
| **DGS** | Defense Generalization Score | How much a defense's real detection/FPR degrades when evaluated on data it was not tuned against — the SAME real quantity Phase 11's LOFO (`lofo_combined_untrained.py`) and real-corpus-detector (`real_attack_corpus_detector.py`) work already measures for the GNN specifically, generalized here to EVERY defense configuration (B0–B10, not just the learned ones) | Direct reuse of Phase 11's own, already-validated methodology (train/tune on the hand-authored corpus, evaluate on the real 7-attack corpus and/or LOFO-excluded families), extended beyond the GNN to the rule-based guards too |

Attribution metrics (as named in your prompt, mapped onto the existing five-type
framework, `attribution/ATTRIBUTION_METHODOLOGY.md` §2):

| Metric | Definition | Basis |
|---|---|---|
| Source accuracy | Fraction of real `ORIGIN` attributions matching the real, known injecting attack (ground truth already exists — every injected memory's true origin is known from Phase 4/5's own real event ledger) | `attribute_origin()`, already real and tested |
| Path fidelity | Fraction of real `LINEAGE`/`PROPAGATION` full-chain results whose returned path matches the real, known derivation chain exactly (per-hop, not just endpoint-correct) | `attribute_lineage(full_chain=True)`, `attribute_propagation()` |
| Uncertainty | Calibration of the real `NO_ATTACK_ORIGIN`/`MULTIPLE_POSSIBLE_SOURCES` statuses — do they fire exactly when the real ground truth is genuinely ambiguous, never when it is not (a false confidence or false uncertainty rate) | New aggregation over already-real per-case statuses |
| Time-to-attribute | Real wall-clock/operation cost of running one attribution query, measured directly, not estimated | New instrumentation (a timer around existing, unmodified `attribute_*()` calls) |

Utility metrics (as named in your prompt, mapped onto existing Phase 3 infrastructure):

| Metric | Definition | Basis |
|---|---|---|
| Task success | Real agent answer correctness (`success_status`/`success_value`), defenses ACTIVE vs. the already-real clean-condition baseline | Phase 3's own real evaluation scoring, already used for the no-defense condition; needs a new real campaign run WITH Phase 6–11 wired into the retrieval path |
| Utility retention | Task success WITH defenses active ÷ task success with NO defenses active, on the SAME real tasks | Direct ratio of two real, comparable campaign runs |
| Latency | Real wall-clock added per retrieval/decision by running Phase 6–11's guards, measured directly | New instrumentation around the existing, unmodified guard call path |
| Memory overhead | Real additional storage/state Phase 5–11's own ledgers/signals/models require, measured directly (not estimated) | New instrumentation (real object/file size measurement) |

## 5. Non-negotiable rules (carried forward from every prior phase's own discipline)

1. No new attack, defense, or learned component is introduced by Phase 12 — it measures
   what exists.
2. `held_out_pools()` and the real, reported B0–B10 corpus are read-only inputs to
   measurement, never modified to produce a better-looking evaluation number.
3. Every real attack's ground truth (real `is_poison_ground_truth`,
   `attack_family_ground_truth`, real injecting event) is the ONLY source of truth for
   scoring correctness — no manually-assigned "should have been detected" label is ever
   introduced.
4. DGS reuses Phase 11's own real train/eval separation discipline exactly (never
   evaluates a defense on data it was tuned against) — extending that discipline to
   rule-based guards, not relaxing it for them.
5. A negative or mixed result (a defense that does not generalize, an attack that evades
   detection under some real workload, a utility cost that is real and not small) is a
   complete, acceptable, and expected finding — reported exactly as such, per this
   project's entire standing practice throughout Phases 1–11.
6. No fabricated ground truth for utility/attribution scoring — task success is scored
   the same real way Phase 3 already scores it (real LLM answer vs. real gold answer),
   never a manually-assigned pass/fail.

## 6. Existing infrastructure this phase reuses, unmodified

- `phase4/attacks/*` — all 7 real, frozen attacks, called exactly as already validated.
- `phase5/wiring/live_attack_runs.py`, `phase5/wiring/lineage.py` — the real
  instrumentation/event-ledger machinery.
- `phase6/defense/orchestration/pipeline.py::ConfigurationMetrics`/`compute_metrics()` —
  the real metrics object every ablation already returns; Phase 12 extends its
  *reporting* (per-metric-family breakdowns), not its computation.
- `phase6/evaluation/ablations/{corpus.py, dev_corpus.py}` and `phase11/data/{real_corpus.py, clean_expansion.py, poison_regeneration.py}` —
  every real corpus this project has already built, reused as the real
  attack/dataset/workload matrix's actual cells (Section 7).
- `attribution/*` — the real, tested five-type attribution layer.
- `phase3/evaluation/agent_runtime/*` — the real agent campaign runner and its real
  success scoring.

## 7. The evaluation matrix (Phase 12's own scope: security only)

| Dimension | Real values already available |
|---|---|
| Attacks | DSRM, FARMA, MPBench-PCFI, MINJA, AgentPoison, MemoryGraft, Sleeper (7, all real, frozen) |
| Datasets | LoCoMo (fully wired), LongMemEval/MSC/ConversationChronicles (real, available via `phase11/data/clean_expansion.py`, currently only lightly sampled — Phase 12 would need to decide a real, controlled, documented sample size per the same discipline `clean_expansion.py` already established, not a full 1.26M-record sweep) |
| Defense configurations | B0–B10 (11 real configurations already defined) |
| Workloads | Not yet defined in this project — **open question, Section 8** |

## 8. Open questions requiring your confirmation before implementation

1. **Do the 5 security-metric definitions in Section 4 match your intent?** These are
   principled proposals grounded in real, existing infrastructure, not the only possible
   reading of the acronyms.
2. **What does "workload" mean for this evaluation?** Candidates: (a) query volume/rate
   against the memory store, (b) different real task types (QA vs. summarization vs.
   multi-hop reasoning, if MAMBench's datasets support distinguishing these), (c) real
   concurrent multi-user/multi-session load. Phase 12 cannot proceed to the workload axis
   of the matrix without this defined.
3. **Sample size for the 3 newly-included real datasets** (LongMemEval/MSC/ConversationChronicles):
   a full 1.26M-record sweep is explicitly out of scope per every prior phase's own
   "controlled, not full-corpus" discipline — what real, bounded sample size should Phase
   12 use, and should it match `clean_expansion.py`'s existing controlled sample or be
   independently sized for statistical power across 7 attacks × 11 defense configs?
4. **Does Phase 12 evaluate against the existing `held_out_pools()` corpus only, or does
   it authorize building a NEW, separate, larger real evaluation corpus** (since B0–B10's
   75-scenario corpus was sized for the ablation comparisons it was built for, not
   necessarily for a full 7×11×N-dataset sweep with adequate statistical power per cell)?
5. **Utility metrics require a NEW real Phase 3 campaign run with Phase 6–11 wired into
   the live retrieval path** — this is real compute cost (LLM calls) and real
   engineering work (Phase 6–11 has never been called from inside the Phase 3 agent
   runtime's own decision loop). Confirm this is in scope for Phase 12/14, since it is
   the single largest new-implementation item in this whole plan.

## 9. Deliverables (Phase 12 specifically)

1. `phase12/` — new, additive module tree (`security_metrics.py`, `evaluation_matrix.py`,
   `dgs.py`, tests) — no existing Phase 4–11 file modified.
2. A real, executed sweep of the security-metric matrix (Section 7, minus the workload
   axis until Section 8.2 is answered), with honest per-cell results — including cells
   where a defense fails, an attack evades, or generalization (DGS) is poor.
3. `docs/phase12/PHASE12_SECURITY_METRICS_REPORT.md` — the real, measured results,
   following this project's own "never write the conclusion first" discipline.
4. A regression suite extending, never replacing, the existing 722-test baseline.
5. A recommendation for Phase 13's own scope, informed by what Phase 12 actually finds
   (e.g., if DGS reveals a defense-specific generalization gap, Phase 13's attribution
   work may want to check whether attribution confidence correlates with it).

## 10. What Phase 12 does not do

- Does not modify any Phase 4–11 attack, defense, or learned-component file.
- Does not touch `held_out_pools()`'s content, only reads it.
- Does not implement attribution or utility metrics (Phases 13/14, per Section 2's
  proposed split).
- Does not run the full cross-cutting matrix (Phase 15) or write the synthesis report
  (Phase 16) — those depend on 12–14 each existing first.
- Does not begin implementation before Section 8's open questions are answered.
