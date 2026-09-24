# Phase 14 Plan — Systematic Evaluation: Utility Metrics

Status: DRAFT, written before the implementation it governs, per this project's own
standing discipline (`attribution/ATTRIBUTION_METHODOLOGY.md`, `docs/phase9/PHASE9_PLAN.md`,
`docs/phase12/PHASE12_PLAN.md`, `docs/phase13/PHASE13_PLAN.md`'s own opening lines).
Finalized once the implementation and its real measurements validate against it; any
change forced by implementation reality is reconciled here explicitly, not silently.

Per `docs/phase12/PHASE12_PLAN.md` Section 2's own proposed division of the 12–16 arc
(never revisited since): Phase 12 = security metrics (done), Phase 13 = attribution
metrics (done), **Phase 14 = utility metrics**, Phase 15 = the full cross-cutting sweep,
Phase 16 = the synthesis report.

## 1. Research Question

*"Across MAMBench's real defenses (Phases 6–12), what do they actually cost — in real
benign task success, real wall-clock latency, and real storage overhead — not assumed
from a false-positive rate in isolation, but measured end-to-end on the same real agent
loop Phase 3 already validated?"*

This is a measurement phase, not a new-defense phase. Phase 14 invents no new defense,
guard, or agent capability. It asks whether running the real Phases 6–12 defense stack
in front of a real agent task costs that agent anything, and reports the real answer,
positive or negative, exactly as every prior phase in this project has.

## 2. Why This Is Not Already Covered

| Existing capability | Where | What it is, and its real limit |
|---|---|---|
| Utility Retention Score (URS) formula | `phase6/evaluation/metrics/utility_metrics.py` | Real, already-built arithmetic (`URS = TSR_defended / TSR_baseline`, reusing Phase 3's own frozen correctness metrics rather than reinventing "success") — but it is pure arithmetic over two caller-supplied floats. It has never been called with a real `task_success_rate_defended` computed from an actual defended agent run; only ever exercised with hand-picked numbers in its own unit tests. |
| Per-component cost profiles | `phase6/evaluation/metrics/cost_metrics.py` | Real, disclosed `ComponentCostProfile` entries for the admission, retrieval (D1/D2), propagation, and sleeper guards — but `measured_latency_seconds` is `None` (explicitly, honestly) for every rule-based component, and D2's own number is a real measurement of `encode()` in isolation, not of a full defended task. **The Consolidation Guard (Phase 12's fifth defense component) has no cost profile entry in this module at all** — it did not exist when this module was last touched. |
| Pareto-frontier utility/security trade-off helper | `phase6/evaluation/metrics/pareto.py` | Real, generic dominance-comparison logic — but has never been fed a real (security, utility) point pair, because neither side of that pair has been measured together for the same real configuration yet. |
| Real Phase 3 agent-runtime and campaign infrastructure | `phase3/evaluation/agent_runtime/{runner,campaign_runner}.py`, real campaign result JSONs (e.g. `clean_agent_dataset_locomo_120x2.json`) | Real, validated, frozen — but every existing real campaign result is for the **undefended** condition only. `run_agent_task()`/`build_agent_visible_context()` (confirmed by direct search) has no code path that calls `evaluate_admission()`, `evaluate_pool()`, or any other Phase 6–12 defense function — defenses have, to date, only ever been evaluated OFFLINE against static `ScenarioPool` corpora, never LIVE inside an actual agent task's real retrieval → selection → generation loop. A genuine "defended" real task-success number does not exist anywhere in this project yet. |
| Real per-scenario ledger/event storage (Phase 3/5/12/13's own canonical + Phase5Event ledgers) | `phase3/evaluation/foundations/*ledger*.py`, `phase5/schema/event_ledger.py` | Real, file-backed, and already measurably larger for a defended/instrumented run than an undefended one (every admission/retrieval/propagation decision, plus Phase 12's Consolidation Guard decisions and Phase 13's attribution ledger, are real persisted records) — but no report has ever measured this real overhead directly (bytes on disk, or record count, per real task). |

**The real, named gap Phase 14 exists to close**: this project has a real utility-cost
*formula*, real (partial) cost *profiles*, and a real, validated agent-evaluation
*harness* — but has never connected them. No real number exists anywhere in this project
today for "how much does turning the real defenses on cost a real agent, on a real task."

## 3. A Real Prerequisite This Phase Must Do First (not optional)

Unlike Phase 12 (whose prerequisite was persisting an already-computed ledger) and Phase 13
(whose prerequisite was recording an already-produced event type), Phase 14's prerequisite
is larger: **a real "defended retrieval" path does not exist and must be built** before any
defended-vs-baseline comparison is possible. Concretely, this means a new, additive function
— analogous to `_retrieve_and_select()` in `phase3/evaluation/agent_runtime/runner.py`, but
NOT modifying that frozen function — that, for a `DefenseConfiguration`-supplied set of
enabled guards, real-time evaluates each retrieved candidate memory (`evaluate_admission()`
at creation time is already a settled question for these memories; what Phase 14 adds is
the RETRIEVAL/PROPAGATION/consolidation-time re-evaluation this project's own guards already
support) and excludes/restricts/quarantines candidates before they reach
`build_agent_visible_context()`, exactly mirroring what a real deployment would do.

This is additive, not a modification of any frozen Phase 3 function: `run_agent_task()`
itself is not touched; a new, parallel entry point (or an optional
`defense_configuration` parameter with a clearly-disclosed default of "no defense,
identical to today's behavior") is how this gets wired, so every existing Phase 3 test and
every existing real campaign result remains byte-identical and valid.

## 4. Proposed Scope (confirm before implementation)

| # | Metric | Definition | Real basis |
|---|---|---|---|
| 1 | **Utility Retention Score (URS)** | `task_success_rate_defended / task_success_rate_baseline`, using ONE of Phase 3's own frozen correctness metrics (Methodology Section 12.13) applied identically to both conditions on the SAME real task set | `phase6/evaluation/metrics/utility_metrics.py::utility_retention_score()`, already real and built — needs a real `task_success_rate_defended` for the first time (Section 3's prerequisite) |
| 2 | **Real false-positive task cost** | Of the real benign memories a defense guard quarantines/restricts/blocks (a real false positive, already measured as an admission/retrieval-time RATE in Phases 6–12), what fraction of those specifically cause a real task the agent would otherwise have answered correctly to fail | New — the first metric connecting a defense's abstract FPR to an actual downstream task outcome, rather than treating "flagged a benign memory" and "the agent failed the task" as the same fact |
| 3 | **Real end-to-end latency overhead** | Wall-clock cost of running the full real defended retrieval path per task, broken out per real component (admission, retrieval D1/D2, propagation, sleeper, Consolidation Guard), against the real undefended baseline | `phase6/evaluation/metrics/cost_metrics.py`, extended with a real `ComponentCostProfile` for the Consolidation Guard (currently missing entirely) and real, measured (not `None`) latencies for every component, on this same real local machine already used throughout Phases 12–13 |
| 4 | **Real storage/memory overhead** | Real bytes-on-disk and real record-count growth of the canonical memory/event ledgers, the Phase5Event ledger, and Phase 12/13's own attribution/risk records, per real task, defended vs undefended | New — direct measurement of already-real, already-persisted ledger files; no new ledger format |

## 5. Non-Negotiable Rules (carried forward, unchanged)

1. No new defense, guard, or agent capability is introduced — this measures what Phases
   3–13 already do, wired together for the first time.
2. Real task success is the ONLY source of "success" — reuses Phase 3's own frozen,
   already-validated correctness metrics verbatim; Phase 14 does not invent a new
   correctness criterion.
3. `held_out_pools()` remains read-only; Phase 14's defended-condition tasks draw from the
   SAME real datasets Phase 3's own baseline campaigns already used, so URS compares like
   against like.
4. A negative or mixed result (URS < 1.0, i.e. a real utility cost) is a complete, expected
   finding, reported as such — exactly Phase 12/13's own carried-forward discipline.
5. Any metric showing an unconditionally suspicious pattern — 0%, 100%, or
   identical-everywhere — gets root-caused before being reported, not accepted at face
   value (the same standing rule Phase 12's own PR investigation established and Phase 13
   carried forward).

## 6. Confirmed Scope Decisions (2026-09-22, explicitly authorized)

The three open questions above are now settled. Implementation begins in a later session
("tomorrow," per the user); this section is the frozen record of what was agreed, so that
session starts from a decided scope rather than re-litigating it.

1. **Dataset/task set: BOTH real tracks, confirmed.**
   - **Track A (benign cost)**: the real, frozen LoCoMo/LongMemEval campaigns Phase 3 already
     scored (real baseline numbers exist to diff against) — measures real false-positive
     cost to genuine utility, with zero real poisoned content by construction.
   - **Track B (real protection)**: a real mixed corpus — the same real benign tasks
     alongside real poisoned scenarios from Phase 4/12 — measures whether the real defenses
     actually protect a task's answer from a real poisoned memory's effect, not just what
     they cost.
   Both tracks reuse the SAME defended-retrieval wiring (Section 3); Track B is not a second
   engineering effort, only a second real task/corpus input to the same pipeline.

2. **Defense configurations: two real points, confirmed — `B1_ADMISSION_ONLY` and the full
   risk-composed configuration (B9/B10, Phases 10/11's own final, real 100.0%/14.6%
   detection/FPR number).** Two points, not one, so Phase 14 reports a real cost-vs-detection
   curve rather than a single, unanchored number — the lightest real defense the project has
   shipped, and the strongest. A middle point (e.g. `B8_ALL_FOUR`) is real, disclosed future
   scope if these two real endpoints turn out not to bound the interesting behavior, not
   committed to now.

3. **Sample size: a real pilot first, confirmed — n=30–50 per condition.** Phase 3's original
   baseline campaigns ran n=120–500; a defended-condition re-run at that scale, times two real
   configurations, times two real tracks, is a real, non-trivial LLM-call cost before any
   result is in hand. A real pilot at n=30–50 validates the new defended-retrieval wiring
   (Section 3) and produces a first real, if noisier, URS/cost number; scaling to Phase 3's
   full n is real, disclosed follow-on work, undertaken only if the pilot's own real result
   and cost justify it — never assumed upfront. This mirrors the same "start small, let real
   evidence justify scaling up" discipline Phase 12's own threshold calibration and Phase 13's
   own multi-source sweep already used.

## 7. Deliverables

1. `phase14/` — new, additive module tree (the real defended-retrieval wiring, a real
   campaign runner reusing Phase 3's own harness, and the real cost/storage measurement
   code), no existing `phase3/`–`phase13/` file modified except an additive,
   backward-compatible extension point in the agent runtime (Section 3) and a new
   `ComponentCostProfile` entry for the Consolidation Guard in `cost_metrics.py`.
2. A real, executed defended-vs-baseline campaign at the confirmed pilot scale (Section 6.3:
   n=30–50, both real tracks, both real configurations), producing a real URS number per
   track/configuration, a real false-positive-task-cost number, real per-component latency
   numbers (including the previously-missing Consolidation Guard), and real ledger storage
   overhead numbers.
3. `docs/phase14/PHASE14_UTILITY_METRICS_REPORT.md` — real, measured results, following the
   same disclosure discipline as the Phase 12/13 reports (root-caused suspicious patterns,
   honestly-reported negative/mixed findings, an explicit "what remains open" section).
4. Regression suite extended, not replaced; every existing Phase 3 test must still pass
   unchanged (the new defended path is additive and opt-in).

## 8. What Phase 14 Does Not Do

- The full cross-cutting attack × dataset × workload × defense-configuration sweep
  (Phase 15, per the original Phase 12 plan's own division) — Phase 14 measures utility
  cost for a small, deliberately-scoped set of real configurations (Section 6.2), not the
  full matrix.
- The synthesis report presenting security, attribution, and utility together with an
  explicit trade-off curve (Phase 16).
- Retraining, recalibrating, or otherwise changing any Phase 6–12 defense threshold to
  improve a real utility number this phase finds — a real, disclosed follow-on for a later
  phase if Phase 14's own findings make it necessary, not something Phase 14 does itself.
