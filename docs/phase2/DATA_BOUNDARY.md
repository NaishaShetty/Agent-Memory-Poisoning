# Phase 2.1 Data Boundary

This document defines the layering between raw source data, Phase 1
derived artifacts, officially approved Phase 2 inputs, and future
benchmark-generated data (attacks, sleeper payloads, poisoned memories,
GNN/GLN training data). It is the enforcement point Task 6 of Phase 2.1
asks for: a boundary that makes it structurally hard to mix these
categories by accident.

No files were moved or duplicated to build this boundary. The existing
Phase 1 directory layout already respects it; this document makes the
layering explicit and adds the one new artifact (the Phase 2 input
manifest) that formally marks which Phase 1 outputs are approved to cross
into Phase 2.

## The four layers

```
LAYER 1 — RAW SOURCE DATA                        data/raw/<resource_id>/
    Immutable. Never written to by any pipeline code after acquisition
    (verified in the Phase 1 audit: every open(...,"w") call site in
    preprocessing/ targets interim/processed/metadata/reports/logs, never
    raw_dir; MSC's tarball extraction is a manual, documented step for
    exactly this reason). Integrity is checked, not assumed: every core
    dataset's raw files are sha256-hashed in data/metadata/dataset_manifest.json,
    and tests/test_phase2_boundary.py::test_raw_files_unchanged_since_dataset_manifest_was_generated
    re-hashes them on every test run and fails if a single byte has changed.

        ↓ (read-only)

LAYER 2 — PHASE 1 DERIVED ARTIFACTS               data/interim/, data/processed/,
                                                    data/metadata/dataset_manifest.json,
                                                    data/metadata/resource_registry.json,
                                                    data/reports/, data/logs/
    Everything the Phase 1 pipeline produced: cleaned/normalized/quality-
    classified memory records, quarantine and removal logs, inspection and
    statistics reports, the two Phase 1 metadata files. This layer is
    FROZEN as of Phase 1 completion (status: PASS WITH ISSUES) and must be
    treated as read-only going forward — Phase 2.1 does not regenerate it,
    only reads and cross-checks it (see PROVENANCE_TRACE.md,
    REPRODUCIBILITY_REPORT.md).

        ↓ (selective, explicit approval)

LAYER 3 — OFFICIAL PHASE 2 INPUTS                 data/metadata/phase2_input_manifest.json
    The one new artifact Phase 2.1 adds. Every one of the 28 tracked
    resources gets an entry with an explicit phase2_status (one of
    PHASE2_INPUT_APPROVED / PREPARED / INSPECTED / CONDITIONALLY_AVAILABLE /
    UNAVAILABLE / UNVERIFIED / NOT_GENERATED) and a boolean
    phase2_input_approved. Only the four core memory datasets — LoCoMo,
    LongMemEval, MSC, Conversation Chronicles — are phase2_input_approved:
    true. This is a deliberate, narrow scope decision (see "Why only four
    resources are approved" below), not an oversight.

    Any later phase that wants to consume a resource from data/processed/
    or data/raw/ MUST first check this manifest. Consuming an unapproved
    resource without updating this manifest (and the reasoning behind the
    update) violates the freeze boundary.

        ↓ (nothing crosses this line yet)

LAYER 4 — FUTURE BENCHMARK-GENERATED DATA          data/generated/ (reserved,
                                                    does not exist yet)
    Attack-generated memories, sleeper/backdoor payloads, poisoned-memory
    variants, propagation-monitoring outputs, and GNN/GLN training data
    all belong here in later phases (4, 6-9) — never inside data/raw/ or
    data/processed/, and never flagged as if they were source-provided.
    Phase 2.1 does not create this directory or anything under it (Task 11:
    no attack/sleeper generation in Phase 2.1). When a later phase does
    create it, each subtree must be tagged with its generation method
    (e.g. attack_family, generator_version, seed) distinguishing:
      - source-provided   (from data/raw, unchanged in meaning)
      - benchmark-generated (constructed by this project's own code)
      - inferred            (derived by a heuristic/model over other data)
      - model-predicted     (an LLM/GNN/GLN output)
    matching the vocabulary already used by preprocessing/schema.py's
    Provenance fields for Layer 2.
```

## Why only four resources are approved as Phase 2 inputs

The Phase 2.1 objective statement is specific: freeze and register "the
Phase 1 data foundation" — described elsewhere in the same objective as
"the clean memory foundation" — before any new benchmark generation
occurs. That foundation is the four PROCESSED core memory datasets.

The other 24 registry entries (9 task_workload, 2 sleeper, 6 attack, 7
security_benchmark) are real, useful, and accurately recorded — but
approving them as "Phase 2 inputs" here would blur two different
questions: "does this resource exist and what state is it in" (answered
for all 28 by both `resource_registry.json` and
`phase2_input_manifest.json`) versus "is this resource cleared for use
inside the specific artifact this phase is chartered to produce" (answered
`true` only for the four core datasets). Marking, say, `swebench_verified`
(PREPARED, has real local data) as `phase2_input_approved: true` here
would create a plausible-looking green light for a resource that Phase
2.1 was never asked to freeze, and whose eventual approval (as a Phase 4
workload source, say) is a decision for whoever actually designs that
usage — not something Phase 2.1 should decide by default.

This is enforced, not just documented: `tests/test_phase2_boundary.py`
asserts that `phase2_input_approved_resource_ids` is exactly the four core
IDs, and that every `attack`/`sleeper` category resource is unapproved
regardless of its underlying Phase 1 status.

## What would violate this boundary

- Writing anything to `data/raw/*` after acquisition (would break Layer 1
  immutability; caught by the checksum re-verification test).
- Reprocessing a core dataset and overwriting `data/processed/*` without a
  version bump and a new Phase 1 completion record (would silently change
  Layer 2 out from under anything built on top of it).
- A Phase 4+ script reading `data/raw/agentpoison` (doesn't exist — no
  local copy was made, by design) or treating `agentpoison`'s
  `phase2_status: "INSPECTED"` as if it meant "ready to use".
- Writing attack- or sleeper-generated records into `data/processed/` or
  any core dataset's directory, rather than a new, clearly-labeled
  `data/generated/` subtree.
- Hand-editing `phase2_input_manifest.json` to approve a resource instead
  of updating the underlying Phase 1 record and regenerating it via
  `python -m preprocessing.phase2_manifest`.
