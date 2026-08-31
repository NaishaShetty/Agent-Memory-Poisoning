# Evaluation Contract

Status: **FROZEN DECISION** for the two-layer evaluation structure and the control-condition
methodology; **NOT FROZEN** for exact metric thresholds or pass/fail bars (those are set by
[../specification/PHASE3_FREEZE_GATE.md](../specification/PHASE3_FREEZE_GATE.md) at freeze
time, informed by experimentation under
[../specification/EXPERIMENT_GOVERNANCE.md](../specification/EXPERIMENT_GOVERNANCE.md)).

## 1. Two evaluation layers (frozen)

Phase 3 evaluation is explicitly split into **memory success** (did the memory subsystem do
its job?) and **agent success** (did the full agent, including reasoning, do its job?).
Historical Phase 3 conflated these — strict TSR (whether the selected memory set contained the
literal gold evidence memory ID) was implicitly treated as a proxy for overall agent
correctness. This contract makes the distinction explicit and permanent:

```
TSR ≠ QA accuracy
TSR ≠ reasoning accuracy
TSR ≠ complete agent success
```

## 2. Memory-level metrics (frozen set; not frozen thresholds)

- Recall@1, Recall@5, Recall@10, Recall@20, Recall@50, Recall@100, Recall@200 (where feasible
  given corpus size).
- MRR.
- Evidence precision, evidence recall, evidence coverage.
- Selected-memory count, irrelevant-memory count, redundancy.
- Candidate-generation capacity failures (candidate discovery never surfaced the needed
  memory) vs. selection-capacity failures (surfaced but not selected) — kept as separate
  counters, per the historical root-cause finding that ~72.4% of failures were
  candidate-generation failures vs. ~14.8% selection-capacity failures and ~12.8%
  identity/evaluation artifacts. This split must be preserved so future work does not
  re-conflate these failure modes.
- Creation rate, rejection rate, duplicate rate, semantic-equivalence rate, reuse rate.
- Foundation-vs-derived usage rate, derivation depth.
- Provenance completeness, lineage correctness.
- Lifecycle validity, orphan rate, invalid-transition rate.

## 3. Strict TSR (retained, reclassified)

Strict TSR — whether the selected memory set contains the literal benchmark-designated gold
evidence memory ID — is **retained** for comparability with historical Phase 3 results, but is
explicitly classified as a **diagnostic/comparability metric**, not a definition of agent
success. No future document may re-promote strict TSR to "the" success metric without
explicitly overriding this contract.

## 4. Evidence-equivalent success (new)

A separate diagnostic metric assessing whether the selected memory set contains evidence that
is *semantically or evidentially equivalent* to the gold evidence, even if it does not match
the literal gold memory ID. This exists because strict TSR undercounts cases where the agent
found a correct-but-differently-identified piece of evidence (e.g. a duplicate or an
equivalent memory, per [../schemas/memory_schema.md](../schemas/memory_schema.md)). This
metric does not silently replace strict TSR — both are reported.

## 5. Agent-level metrics: three controlled conditions (frozen methodology)

All three conditions below must use the **same** model, prompt, decoding configuration, task
set, and evaluation methodology — only the memory input differs:

**A — No-memory control**
```
Task → Qwen → Answer
```

**B — Gold-evidence control**
```
Task → Gold evidence → Qwen → Answer
```

**C — Retrieved-memory (the actual clean agent)**
```
Task → Memory foundation → Retrieval → Selection → Qwen → Answer
```

Derived contribution metrics:

```
memory contribution      = accuracy(C) - accuracy(A)
gold memory contribution = accuracy(B) - accuracy(A)
```

Retrieved-memory performance (C) must always be characterized **relative to** gold-evidence
performance (B), not in isolation — a retrieved-memory accuracy that looks acceptable in
isolation but is far below gold-evidence accuracy indicates retrieval/selection is the
bottleneck, not reasoning.

## 6. What this contract forbids

- Treating strict TSR as a complete measure of agent success.
- Reporting condition C without also reporting conditions A and B from the same run
  (same model/prompt/decoding/task set).
- Silently replacing strict TSR with evidence-equivalent success rather than reporting both.
- Accepting a mechanism into the clean agent based on a single metric's improvement without
  the composition testing required by
  [../specification/EXPERIMENT_GOVERNANCE.md](../specification/EXPERIMENT_GOVERNANCE.md).

## 7. What this contract does not decide

Exact numeric pass/fail thresholds for any of the above metrics are not set here — they are
set at freeze-gate time (see
[../specification/PHASE3_FREEZE_GATE.md](../specification/PHASE3_FREEZE_GATE.md)), informed by
actual measurement, not assumed in advance.
