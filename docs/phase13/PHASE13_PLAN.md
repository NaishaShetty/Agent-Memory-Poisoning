# Phase 13 Plan — Systematic Evaluation: Attribution Metrics

Status: DRAFT, written before the implementation it governs, per this project's own standing
discipline (`attribution/ATTRIBUTION_METHODOLOGY.md`, `docs/phase9/PHASE9_PLAN.md`,
`docs/phase12/PHASE12_PLAN.md`'s own opening lines). Finalized once the implementation and its
real test results validate against it.

## 1. Research Question

*"This project's real, five-type attribution layer (`attribution/`) has been validated case-by-case
(11 hand-authored scenarios, A–K) since Phase 9 — but has anyone ever measured its OWN accuracy,
confidence calibration, and cost systematically, across the real attack/dataset space Phase 12 just
finished building and fixing? And now that Phase 12 made detection real (100% on real content, not
0%), does attribution confidence track that same real signal, or is it still calibrated against the
old, broken detection landscape?"*

This is a measurement phase, like Phase 12. It introduces no new attribution logic — it runs the
real, existing `attribution/` layer against real data it has never been run against at this scale,
and reports the real answer.

## 2. Why This Is Not Already Covered

| Existing capability | Where | Real limit |
|---|---|---|
| 5 real attribution types (ORIGIN, LINEAGE, PROPAGATION, INFLUENCE, forensics), real evidence, real uncertainty statuses | `attribution/wiring/*.py` | Validated against 11 hand-authored scenarios (A–K) — never run against Phase 12's real 15-poison / 4-dataset corpus. |
| Real attribution accuracy/calibration metric functions (`origin_attribution_accuracy`, `lineage_reconstruction_accuracy`, `source_precision_recall`, `ambiguity_rate`, `false_attribution_rate`, `influence_attribution_accuracy`) | `attribution/metrics.py` | **Confirmed via direct grep**: every one of these functions is called ONLY from `attribution/tests/test_attribution.py` — never from any real corpus sweep. This is the exact same "built but never run at scale" gap Phase 12 found and closed for PAR/SDR/AMR. |
| Real Phase 4/5 event-ledger instrumentation (`record_attack_injection`, `record_memory_creation`, `record_memory_derivation`) | `phase5/wiring/memory_lifecycle.py` | Phase 12's own B0–B8/PR/Consolidation-Guard work used lightweight `MemoryScenario` objects and, for PR specifically, real but throwaway (`tempfile.TemporaryDirectory()`) ledgers — never persisted, never available for a later attribution pass to query. |
| Phase 12's own real, persisted derivation events | `phase12/propagation/propagation_rate.py::_record_real_derivation_events()` | Currently written to a temporary directory and discarded after `compute_pr()` returns. These are real `derived` events with real, known ground truth (which poison scenario each one came from) — exactly the kind of case Phase 13's path-fidelity metric needs, and they already exist, they just aren't kept. |

**The real, named gap**: Phase 9 built a real attribution capability and validated it correctly
case-by-case; Phase 12 built a real, large, systematically-swept detection corpus. Nobody has yet
pointed the first at the second.

## 3. Proposed Scope (confirm before implementation)

| # | Metric | Definition | Real basis |
|---|---|---|---|
| 1 | **Source accuracy** | Fraction of real ORIGIN attributions (`attribute_origin()`) that correctly name the real injecting attack, run across all 15 real poison scenarios in `real_poison_scenarios()` | Real ground truth already exists (`attack_family_ground_truth`, and the real Phase 4/5 injection event each scenario's own injector call produces) |
| 2 | **Path fidelity** | Fraction of real LINEAGE/PROPAGATION full-chain attributions whose returned path matches the real, known derivation chain exactly, per-hop | Reuses Phase 12's own real derivation events (Section 2) — persisted for the first time instead of discarded |
| 3 | **Uncertainty calibration** | Real false-attribution and ambiguity rates, specifically comparing: (a) real corpus content admission now correctly detects (Phase 12's fixed signals) vs. (b) content it still misses (MINJA's one remaining architectural case, if any) — does attribution confidence track detection confidence, or is it decoupled? | `false_attribution_rate()`/`ambiguity_rate()`, already real, never run at this scale |
| 4 | **Time-to-attribute** | Real wall-clock cost of one `attribute_*()` call, measured directly | New instrumentation, a timer around existing unmodified calls |

## 4. A Real Prerequisite This Phase Must Do First (not optional)

**STATUS: BUILT (2026-09-22)**, ahead of the rest of Phase 13's implementation, per the user's explicit
request. `phase13/ledger_setup.py` now exists:
1. `build_persistent_real_ledgers(ledger_dir)` runs the real, unmodified `compute_pr()` pipeline with its
   own real ledger-writing code pointed at a real, persistent directory instead of the
   `tempfile.TemporaryDirectory()` it previously discarded results into — every one of the 15 real
   `real_poison_scenarios()` gets a real `CanonicalMemoryRecord` (`record_memory_creation()`), and every
   scenario PR measures as propagating gets a real derived-memory record plus a real `derived` event
   (`record_memory_derivation()`), with the poison's own scenario_id as `source_memory_ids` — real, known
   ground truth for path-fidelity.
2. `assert_ledger_disjoint_from_held_out_pools(ledger_dir)` verifies the real, on-disk ledger's memory ids
   never intersect `held_out_pools()`/`corpus.all_pools()`, mirroring `phase12/eval_corpus.py`'s own
   guardrail.
3. `phase13/tests/test_ledger_setup.py` — a real, slow (one full real `compute_pr()` run) end-to-end test
   verifying every real scenario is persisted, at least one real derivation event exists, and
   disjointness holds.

No new attack, defense, or attribution logic was introduced — this is pure plumbing pointing existing,
real code at a persistent path instead of a discarded one.

## 5. Non-Negotiable Rules (carried forward, unchanged)

1. No new attribution logic is introduced — this measures what `attribution/` already does.
2. Real ground truth (`attack_family_ground_truth`, real injection/derivation event ids) is the ONLY
   source of correctness — no manually-assigned "should have attributed to X" label.
3. `held_out_pools()` remains read-only.
4. A negative or mixed result (attribution that is confidently wrong, or appropriately uncertain in
   the wrong direction) is a complete, expected finding, reported as such — exactly Phase 12's own
   discipline, carried forward.
5. Given Phase 12's own real, hard-won lesson this session (three separate real methodology biases
   found and fixed in PR alone): **any metric showing an unconditionally suspicious pattern — 0%,
   100%, or identical across every real case — gets root-caused before being reported**, not accepted
   at face value.

## 6. Open Questions Requiring Confirmation Before Implementation

1. Does "source accuracy" mean exact attack-family match only, or does partial credit apply for a
   correct mechanism-family classification (e.g., correctly identifying "forged reasoning" without
   pinning FARMA specifically)?
2. Should Phase 13 also attribute the Consolidation Guard's OWN real decisions (Phase 12's newest
   component) — i.e., when the guard quarantines a derived memory, does attribution correctly trace
   that decision back to the real poisoned source? This wasn't in Phase 12's original scope but now
   exists as real, attributable data.
3. Time-to-attribute: measured on this same small local machine (no dedicated benchmarking
   environment) — real numbers will reflect this hardware, disclosed as such, not treated as a
   general performance claim.

## 7. Deliverables

1. `phase13/` — new, additive module tree, no existing `attribution/`, `phase4/`–`phase12/` file
   modified except the ledger-persistence change in Section 4 (disclosed, minimal, additive).
2. A real, executed sweep of all 4 metrics against the real 15-scenario corpus.
3. `docs/phase13/PHASE13_ATTRIBUTION_METRICS_REPORT.md` — real, measured results.
4. Regression suite extended, not replaced.

## 8. What Phase 13 Does Not Do

- Utility metrics (Phase 14, per the original Phase 12 plan's own division).
- Full cross-cutting sweep (Phase 15) or synthesis report (Phase 16).
- Recalibrating Phase 12's own PR/Consolidation-Guard thresholds (a real, disclosed Phase 12 loose
  end — see the final Phase 12 report — but out of THIS phase's scope unless attribution's own
  findings make it directly necessary).
