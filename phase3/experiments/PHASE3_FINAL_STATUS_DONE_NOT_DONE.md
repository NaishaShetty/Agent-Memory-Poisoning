# Phase 3 — Final Status: Done / Not Done

Status: **STATUS DOCUMENT**, not a freeze decision. Consolidates the completion audit,
every fix made in response to it, and this document's own honest re-assessment of the
provenance graph against a fuller design specification supplied after the graph was
already built. Supersedes no other document's technical content — cross-references
[PHASE3_3_7_FREEZE_CERTIFICATION.md](PHASE3_3_7_FREEZE_CERTIFICATION.md) for the formal
certification and corrects one thing it understated (§7 below).

**SUPERSEDED BY FINAL CLOSURE**: see
[PHASE3_FINAL_FREEZE_AND_CERTIFICATION_REPORT.md](PHASE3_FINAL_FREEZE_AND_CERTIFICATION_REPORT.md)
for the terminal, certified Phase 3 closure state. This document's own content
below remains accurate as the running history that led there.

**Latest update**: an unfiltered self-assessment of real strengths/weaknesses (not
just checklist completion) surfaced five honest concerns — selection realness
(already resolved), the relationship layer's real thinness, a misleading frozen
correctness metric, the reference agent's minimalism, and an unexamined A-MEM
timing confound. All five received real, bounded follow-up work; see
[PHASE3_3_FOUNDATION_STRENGTHENING_FIVE_CONCERNS_REPORT.md](PHASE3_3_FOUNDATION_STRENGTHENING_FIVE_CONCERNS_REPORT.md)
for the full report. Headline results: a new, additive correctness metric reveals
the real accuracy picture (3.3%/43.3%/39.6% across A/B/C, vs. the frozen grader's
near-0% everywhere); a bounded V2 reference-agent candidate was built, piloted, and
formally qualified against V1 — **NO-GO for promotion** (no measurable accuracy
improvement at n=20) — so **V1 remains the canonical reference agent**, V2 preserved
as a real, tested, documented candidate.

## What is genuinely DONE

- **Canonical Memory Ledger (H.1)** — authoritative, frozen, vendor IDs as aliases,
  partial-failure-safe, idempotent.
- **Canonical Event Ledger (H.2/H.2-R/H.2-R2)** — append-only, 10 event types, experiment
  boundaries genuinely separate from memory lifecycle events, worker-merge tested.
- **Memory versioning/supersession (H.3)** — two real, previously-undiscovered bugs found
  and fixed this session (H.3-R, H.3-R2), now provably correct for every derived memory,
  including multi-hop chains.
- **Initiatives B, C, D, F, G** — schema-complete, tested. D (qualification) is real for
  both active foundations: Mem0 and A-MEM both `QUALIFIED`, 15/15 fixtures, zero
  divergence.
- **Initiative E (leakage)** — structural checks live via `run_agent_task()`; content-
  level scan now live in the actual real campaign path (`campaign_formal_runner.py`), not
  only a separate harness.
- **Initiative A (counterfactual influence)** — real, valid, comparable measurements for
  both Mem0 (17/13/0) and A-MEM (18/12/0, post-bugfix) on the identical 6 real LoCoMo
  tasks.
- **Live wiring (H.4-WIRE, H.4-WIRE-C)** — both Mem0 and A-MEM canonical event emission
  live in the real campaign path, each with a proven zero-interference dry-run/regression
  guarantee.
- **Reproducibility** — `config_fingerprint` (H.4-F) plus, as of this session, a real
  `EnvironmentRecord`/artifact-hash mechanism closing the previously-unmet
  `REPRODUCIBILITY_CONTRACT.md §3` requirement.
- **Two real, previously-undiscovered bugs found and fixed via real execution, not code
  review**: the H.3 derived-memory versioning gap, and `RealAMemAdapter.inspect_memory()`
  silently dropping memory content.
- **Scope/naming documentation** — Mem0+A-MEM-only scope and the `clean_agent_memory_v1`
  ambiguity are both now written down, not left to conversation.
- **Full regression**: 1623 passed, 14 skipped (all environment-dependent, documented), 1
  pre-existing unrelated failure, reproducible across every run this session.

## What was PARTIALLY done — now further closed in this pass

- **Reference clean agent had no dedicated file** — **closed**:
  `agent_runtime/reference_agent.py`, a deliberate, tested, thin re-export of
  `run_agent_task()` (literal object identity, never a second implementation).
- **`C:\h4venv` had one genuinely hardcoded, functionally load-bearing path literal**
  (`amem_real_adapter.py`) — **closed**: now derives from `environment.VENV_PATH` (kept
  as the frozen historical record it correctly is) with a `MAMBENCH_H4VENV_PATH`
  environment-variable override, verified both directions (unmodified default behavior,
  and the override genuinely taking effect).
- **Counterfactual measurements were small-n (6 tasks per foundation)** — **enlarged**:
  n=20 real tasks per foundation now (18 pools each), 100 comparisons per foundation, 200
  total, zero inconclusive — Mem0 59% influential, A-MEM 62%, closely comparable. See
  `PHASE3_3_H4_A_LOCOMO_N20_RUN_REPORT.md`. Still real, still not full 120-task
  research-campaign scale — an honest, not a research-final, sample size.
- **Provenance graph coverage gaps (version nodes, boundary nodes, persistence schema,
  named query catalog)** — **all closed**, per the design review, then implemented, then
  the one open architectural question (multi-boundary graphs) explicitly decided by the
  user and verified against real data (two genuine real experiment runs composed into one
  graph, zero cross-boundary edges) — see
  `PHASE3_3_H4_PROVENANCE_GRAPH_EXTENSION_IMPLEMENTATION_REPORT.md` and
  `PHASE3_3_H4_MULTI_BOUNDARY_REAL_DEMONSTRATION_REPORT.md`.

## Clean-agent behavioral dataset — DONE

The full 120×2 (LoCoMo × {Mem0, A-MEM}) clean-agent behavioral dataset is complete:
480 real executions (Conditions A/GOLD_EVIDENCE/B/C, all four per task), zero
failures, zero content-leakage detections, 240 assembled records, all 240
schema-valid. See
[PHASE3_3_DATASET_FULL_120x2_COMPLETION_REPORT.md](../experiments/PHASE3_3_DATASET_FULL_120x2_COMPLETION_REPORT.md)
for the full report, including an important, investigated-not-assumed finding: the
near-zero `ANSWER_CORRECT` rate reflects the frozen Phase 3.2-E exact-match grading
design interacting with free-form generation, not an agent or measurement defect.
This also closes the `EVALUATION_CONTRACT.md §5-6` gap this session discovered
(Condition C had never been run alongside Conditions A/B by any prior real campaign,
including the frozen G-formal baseline) — `gold_evidence_runner.py`, new this
session, is the real Condition B (GOLD_EVIDENCE) execution path that closes it.

## What remains PARTIALLY done — genuinely deferred, evaluated but not implemented

These two received a full research/qualification pass this session (design review,
then real empirical calibration at meaningful scale, then a NO-GO decision recorded
with evidence) — deferred on evidence, not merely on the original "novel decision"
reasoning alone:

- **Selection policy — now wired and run at full real scale.** The existing default
  campaign path (`campaign_formal_runner.py`, used by the frozen 120×2 dataset)
  still uses the provisional top-5-of-5 policy, unmodified. But the real,
  threshold-based policy (`foundations/selection_policy.py`, calibrated: 125 real
  LoCoMo pairs, threshold=0.263 at 95% gold-evidence coverage) was wired into a real
  N=20-retrieval path (`selection_policy_runner.py`/`campaign_selection_policy_runner.py`)
  and run at full 120×2 scale: 240/240 real successes, **2,937 real `rejected`
  events** (the first non-vacuous rejection this project has produced), and a real,
  measured effect on agent behavior (71-92/120 real answers changed vs. the original
  run). Produced as a separate dataset variant, not merged into the frozen dataset —
  see `PHASE3_3_SELECTION_POLICY_VARIANT_120x2_COMPLETION_REPORT.md`.
- **`relationship_detected` for `equivalent_to`/`conflicts_with` remains NO-GO for
  automatic detection**, confirmed with real, expanded evidence: 254 real LoCoMo
  pairs (two sampling rounds), a synthetic conflicts_with set explicitly labeled and
  kept separate, an evaluated cosine-gate+LLM-judge cascade (best real F1: 0.533,
  still not adequate), and a real light fine-tune attempt that made held-out
  performance WORSE (F1 0.296→0.250 — a genuine negative result, not just untried).
  Two things ARE real and working, deliberately short of full automatic detection:
  (1) the `superseded_by` half of the creation policy (`foundations/creation_policy.py`)
  was proven end-to-end against real content — a genuine real conv-41 job-status
  change across two real sessions, correctly superseded and detected; (2) a
  candidate-flagging layer (`foundations/relationship_candidates.py`) surfaces
  `SUGGESTED_LOW_CONFIDENCE` pairs for review, never auto-committing to the
  canonical event ledger, for BOTH `equivalent_to` and `conflicts_with` — each
  demonstrated for real on real live pools (conflicts_with: 5 real pools, 100 real
  memories, 0 errors, 2 suggested candidates that read as false positives on manual
  inspection, consistent with the rest of the NO-GO evidence). Neither is
  wired into any live campaign path as automatic detection. See
  `PHASE3_RESEARCH_TRACK_RELATIONSHIP_DETECTION_QUALIFICATION.md` for full evidence,
  all follow-up experiments, and the settled within-ingestion-pool
  temporal-scoping constraint (conservative abstention required if any future stage
  compares across sessions/pools).
- **`used` events are never emitted** anywhere in real runtime code — this one is not a
  gap needing a fix; `counterfactually_influential` is the deliberate, honest replacement
  signal, and `used_memory_ids` staying `None` is correct, disclosed behavior, not an
  oversight.

## §7 provenance graph — now genuinely closed, history preserved

The certification originally scored this `[DONE]` prematurely (architecture right, real
coverage gaps present against a fuller 10-point spec supplied after the fact). That
process failure — implementing before a documented design review — is what led to
`PHASE3_PROVENANCE_GRAPH_DESIGN_REVIEW.md` being written *after* the fact rather than
before, unlike every other H.4-* mission this session. All four coverage gaps that review
identified are now closed:

1. **Memory-version nodes** — `include_versions=True` attaches one node per
   `CanonicalMemoryVersion`, in exact append order.
2. **Experiment/run boundary nodes, multi-boundary graphs** — implemented, and the one
   open architectural question (should a clean run and a manipulated run be composable
   into one graph, with strictly no synthesized cross-boundary edges?) was explicitly
   decided by the user and verified against real data — two genuine real experiment runs
   (Mem0, A-MEM) composed into one graph, zero cross-boundary edges.
3. **Formal persistence schema** — `phase3/schemas/provenance_graph_schema.json`,
   export-only, `to_dict()` output validated directly against it.
4. **Named Phase-4-facing query catalog** — `forward_provenance()`,
   `backward_provenance()`, `derivation_propagation()`, `task_exposure_and_use()`, and
   `attack_origin_lineage()` — the last one now genuinely wires `taint_propagation.py`'s
   `tainted_memories()` into the graph, closing the "two disconnected modules" gap
   directly.

See `PHASE3_3_H4_PROVENANCE_GRAPH_EXTENSION_IMPLEMENTATION_REPORT.md` and
`PHASE3_3_H4_MULTI_BOUNDARY_REAL_DEMONSTRATION_REPORT.md` for full detail. The design
review document itself is kept, unrewritten, as the honest historical record that this
started as a process mistake and was corrected properly — not smoothed over.

## Freeze status

Not a frozen decision. `PHASE3_3_7_FREEZE_CERTIFICATION.md` §2's original `[DONE]`
characterization of §7 is now, after this closing pass, accurate again — the correction
this document made to it is itself superseded by the work described above.
