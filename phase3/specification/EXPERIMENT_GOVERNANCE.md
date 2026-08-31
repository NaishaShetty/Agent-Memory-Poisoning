# Experiment Governance

Status: **FROZEN DECISION** — this is the process every future Phase 3 experiment must follow.
It does not itself run or predetermine any experiment.

## 1. Why this exists

Historical Phase 3 accepted mechanisms (e.g. specific retrieval or selection variants) based
on isolated improvement in one metric, without composition testing, and without consistently
preserving negative results. This document exists to prevent repeating that failure mode
during the restart.

## 2. Required experiment specification

Every future Phase 3 experiment — retrieval, reranking, selection, memory-creation policy, or
otherwise — must be specified, before it is run, with:

- **Hypothesis** — the specific claim being tested.
- **Baseline** — the exact configuration being compared against.
- **Independent variable** — what is being changed.
- **Dependent variables** — which metrics from
  [../contracts/EVALUATION_CONTRACT.md](../contracts/EVALUATION_CONTRACT.md) will be measured.
- **Dataset/subset** — which of the four datasets (per
  [DATASET_CAPABILITY_MATRIX.md](DATASET_CAPABILITY_MATRIX.md)) and which subset, with
  justification for that choice.
- **Expected result** — stated in advance, not fitted after seeing results.
- **Failure criterion** — what result would falsify the hypothesis, stated in advance.
- **Composition test** — see section 3.
- **Decision** — see section 4.

## 3. Isolation + composition is mandatory

A mechanism that improves an isolated experiment must **never** automatically become part of
the clean agent. Every important mechanism must eventually be validated:

```
in isolation
+
under composition (with the other mechanisms it will actually run alongside)
```

Historical evidence (derived-memory competition, the V2c candidate-selection thread) showed
that isolated gains can reverse or interact unpredictably once composed with other active
mechanisms. Composition testing is not optional polish — it is a precondition for acceptance.

## 4. Decision vocabulary (frozen)

Every experiment concludes with exactly one of:

- `ACCEPT` — the mechanism is adopted into the clean agent design, with isolation and
  composition evidence both supporting it.
- `REJECT` — the mechanism is not adopted. The experiment and its data are preserved as
  negative-result evidence (see section 5), not deleted.
- `DIAGNOSTIC ONLY` — the experiment provided useful understanding but is not itself a
  candidate for adoption (e.g. a root-cause analysis).
- `REQUIRES FOLLOW-UP` — inconclusive; a specific follow-up experiment is named as the next
  step. This must not be used as a way to indefinitely defer a decision without a concrete
  follow-up plan.

No other outcome label is permitted. In particular, "probably fine" or accepting a mechanism
by default because no one objected is not a valid decision.

## 5. Negative results are preserved, not hidden

Do not accept a mechanism merely because one metric increased. Do not delete or omit an
experiment's results because the outcome was `REJECT`. This applies in particular to the
categories of rejected/regressed mechanisms already known from
`phase3_reference/`: score-gap selection, foundation-preference intervention, semantic-only
retrieval, blanket temporal proximity, relation-aware temporal retrieval, selective memory
creation, derived-memory competition, and lineage-family abstraction. Any future experiment
revisiting one of these must reference the prior historical result rather than re-discovering
it from scratch.

## 6. Scope discipline

Do not start broad, uncontrolled experimentation. Every experiment must trace to a specific
open question raised by the master specification's "candidate hypotheses requiring
experimentation" ledger (see
[PHASE3_CLEAN_AGENT_FOUNDATION_SPEC.md](PHASE3_CLEAN_AGENT_FOUNDATION_SPEC.md) section 4) or a
`REQUIRES FOLLOW-UP` decision from a prior experiment.

## 7. What this document does not decide

It does not name specific experiments to run — that begins in a later Phase 3 stage, once the
architecture defined here (3.1) is in place.
