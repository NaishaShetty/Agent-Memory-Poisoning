# Stage 6.5 — Admission Defense

Status: 6.5 deliverable summary (the design rationale itself lives as module
docstrings in `phase6/defense/admission/`; this document is the stage-gate record
per Section 32's required structure: objective, inputs, implementation, tests,
evidence, limitations, verdict).

## Objective

"Can poisoning be prevented from entering persistent memory?" — via an interpretable,
multi-signal content policy at D1 (admission), never a black-box detector, per the
brief's explicit instruction to establish interpretable baselines first.

## What Was Implemented

Five content/structural signals (`phase6/defense/admission/signals.py`), each a
pure function of `SignalContext` fields already vetted safe by Stage 6.4:
self-reference/precedent-count mismatch, decision-log vocabulary density,
implausible-perfection claims, structural-template anomaly, and a single structural
provenance-consistency check (`derived` memory type with zero parent ids). These are
combined by equal weight (mirroring SENTINEL's own reported 0.2-per-signal design —
see `DEFENSE_LITERATURE_AUDIT.md` Track B.4) into a weighted score, mapped to one of
MGP's four persistent admission actions via three disclosed, uncalibrated v1
thresholds (`phase6/defense/admission/reasoning_guard.py`).

## What Was NOT Implemented (disclosed gap, not silently skipped)

The original Stage 6.5 brief named **five** candidate component families:
(A) content-level screening, (B) provenance-aware screening, (C) **consistency
screening — comparing a candidate memory against trusted existing memory**,
(D) novelty/anomaly screening, (E) multi-signal governance combining the above.

This pass implements (A) fully, a narrow structural slice of (B)/(D) (the single
provenance-anomaly check), and (E) (the weighted combination). **(C) — consistency
screening against the existing trusted memory store — is not implemented.** This is
a real, disclosed gap, not an oversight papered over: a genuine consistency check
requires retrieving and comparing against existing trusted memories at admission
time, which overlaps mechanically with D3's retrieval infrastructure (Stage 6.6) and
was deliberately deferred rather than half-built here, to avoid duplicating retrieval
logic between D1 and D3 before D3's own design is settled. Stage 6.6 should
determine whether consistency screening belongs natively at D1 (a dedicated
admission-time lookup) or is better expressed as a D3 concern applied retroactively
via `QUARANTINE` on an already-admitted memory once retrieval starts surfacing
inconsistency with the trusted store. This document flags the decision as open,
not resolved by default.

## Honest Framing Relative to SENTINEL (6.2's strongest candidate)

This is an adaptation, not a reproduction. SENTINEL's own reported 0% ASR / 0% FPR
was measured on FARMA's own EHR/RAP/ReAct-QA content and its full 5-layer pipeline
(including IFC taint-labeling infrastructure MAMBench does not have). Only the
Layer-5-style weighted-heuristic *concept* transfers; the five signals here are newly
authored against MAMBench's own `SignalContext` fields, using synthetic test content
shaped like (not copied from) Methodology Section 17.3's real descriptions of
FARMA/MemoryGraft output. Whether this configuration achieves anything resembling
SENTINEL's reported numbers against MAMBench's actual seven attacks is an **open
empirical question for Stage 6.9/6.10**, not assumed here.

## Tests and Evidence

`phase6/tests/test_admission_defense.py` — 21 tests: all four action bands exercised
end-to-end, each signal function tested individually (fires on synthetic
forged-reasoning-style content, silent on benign content), determinism, evidence-refs
pass-through, reason-grounded-in-fired-signals, no forbidden key ever appears in
`signals_used`, no attack name hardcoded as an executable string-literal comparison
(checked via `ast`, not substring — attack names may appear in explanatory prose),
no import of frozen `phase4` attack code, and full `GovernanceLedger` integration
including a real `TRUSTED → SUSPICIOUS` walk through this component (not just the
abstract state-machine test from Stage 6.3).

**Full Phase 6 suite: 72 passed, 0 failed** (37 from 6.3, 14 from 6.4, 21 from 6.5).
Frozen `phase3/`, `phase4/`, `phase5/`, `attribution/` verified unchanged
(`git status --porcelain` clean on all four).

## Limitations Carried Forward

1. Thresholds/weights are uncalibrated v1 defaults (module docstring in
   `reasoning_guard.py`) — not validated against real MAMBench attack content.
2. Consistency screening (component C) is unimplemented — see above.
3. Signals operate on a single memory's content in isolation; none compares across
   candidates (that is what A-MemGuard's consensus mechanism does, reserved for D3 —
   Stage 6.6).
4. `provenance_anomaly_signal` is deliberately the weakest, least specific of the
   five (a single boolean structural check) — retained for parity with SENTINEL's
   five-signal count, not because it is expected to carry real discriminative weight.
5. No signal here would be expected to catch AgentPoison/DSRM's optimized-trigger
   attacks (they don't manipulate memory *content* in the ways these signals look
   for) or MPBench-PCFI (deliberately unmarked, ordinary-looking fact content) — this
   was predicted by the 6.2 gap analysis and is not contradicted by anything built
   this stage; cross-attack coverage is Stage 6.10's job to actually measure.

## Verdict

**PASS** as a 6.5 deliverable, with the consistency-screening gap explicitly carried
forward rather than silently absorbed into "component (E) covers everything."
