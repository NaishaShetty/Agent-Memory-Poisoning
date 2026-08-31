# Phase 3 Freeze Gate

Status: **FROZEN DECISION** — this is the checklist and decision procedure. It is not itself
an evaluation of readiness (the clean agent does not exist yet at 3.1).

## 1. Purpose

Defines the conditions under which a future, implemented clean agent may be declared frozen
and ready for Phase 4 to build against. This document is written now, before implementation,
so that "done" is defined independently of whatever the implementation later turns out to
look like.

## 2. Freeze conditions

The clean agent may only be frozen when **all** of the following hold:

1. Phase 2 integrity is verified (no drift from the frozen substrate).
2. The memory schema (per [../schemas/memory_schema.md](../schemas/memory_schema.md)) is
   stable — no further structural changes anticipated.
3. Foundation/derived semantics are explicit and implemented as specified.
4. The memory-creation policy is stable and justified by experimentation (per
   [EXPERIMENT_GOVERNANCE.md](EXPERIMENT_GOVERNANCE.md)).
5. The retrieval architecture is stable and its behavior characterized (not merely
   implemented — measured).
6. Candidate-generation recall is characterized across all four datasets, given the
   historical finding that candidate generation was the dominant failure mode
   (~72.4% of failures).
7. Selection behavior is characterized (selection-capacity failures measured and
   understood).
8. Provenance is reconstructable for a representative sample of memories, foundation and
   derived.
9. Lifecycle transitions pass validation (no invalid transitions, no orphans) per
   [../schemas/relationship_schema.md](../schemas/relationship_schema.md).
10. Reproducibility is characterized per
    [../contracts/REPRODUCIBILITY_CONTRACT.md](../contracts/REPRODUCIBILITY_CONTRACT.md),
    including measured Qwen3-8B variance.
11. No ground-truth leakage exists, per the audit required by
    [../contracts/LEAKAGE_AND_VISIBILITY_CONTRACT.md](../contracts/LEAKAGE_AND_VISIBILITY_CONTRACT.md).
12. Memory-level metrics (per
    [../contracts/EVALUATION_CONTRACT.md](../contracts/EVALUATION_CONTRACT.md)) are available
    for all four datasets.
13. Agent-level metrics are available for LoCoMo and LongMemEval (the two datasets with task
    layers).
14. No-memory / gold-evidence / retrieved-memory controls (A/B/C, per the evaluation
    contract) are complete and comparable (same model/prompt/decoding/task set).
15. Composition has been tested for every mechanism accepted into the design (per
    [EXPERIMENT_GOVERNANCE.md](EXPERIMENT_GOVERNANCE.md) section 3).
16. Known limitations are documented (a limitations ledger exists and is current).
17. No unexplained catastrophic interaction remains between accepted mechanisms.
18. `phase3_reference/` Clean Agent V1 remains untouched (verified, not assumed).
19. Phase 4 can manipulate memory content/provenance without requiring any change to the
    reasoning-layer configuration (verified by a smoke test that swaps memory content and
    confirms reasoning-layer config is untouched).
20. Full traces (per
    [../contracts/TRACEABILITY_CONTRACT.md](../contracts/TRACEABILITY_CONTRACT.md)) explain
    memory creation, retrieval, selection, reuse, derivation, and retirement for a
    representative sample of tasks and memories.

## 3. Freeze decision vocabulary (frozen)

The freeze-gate review concludes with exactly one of:

- `FREEZE` — all 20 conditions pass; the clean agent is frozen as the Phase 4 foundation.
- `ONE TARGETED FIX THEN FREEZE` — exactly one specific, named blocker remains; it is fixed
  and the gate is re-checked, without reopening broad experimentation.
- `DO NOT FREEZE` — one or more conditions fail without a single targeted fix available.

## 4. After `DO NOT FREEZE`

A `DO NOT FREEZE` decision names the specific failing condition(s) and the next concrete step.
It does **not** automatically authorize a new broad experiment program — any follow-up work
must itself be specified under [EXPERIMENT_GOVERNANCE.md](EXPERIMENT_GOVERNANCE.md).

## 5. What this document does not decide

Numeric thresholds for "characterized," "stable," or "complete" in the conditions above are
set by the reviewer(s) applying [EXPERIMENT_GOVERNANCE.md](EXPERIMENT_GOVERNANCE.md) and
[../contracts/EVALUATION_CONTRACT.md](../contracts/EVALUATION_CONTRACT.md) at review time, not
fixed in advance here.
