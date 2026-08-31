# Phase 3 Restart Boundary & Phase Contract

Status: **FROZEN DECISION** (this document defines a boundary, not an experiment)

## 1. Purpose

This document draws an explicit, auditable line between what Phase 3 may read, what Phase 3
may never touch, and what is genuinely new. It exists so that every later Phase 3 artifact —
code, data, or documentation — can be checked against a single boundary statement instead of
tribal knowledge.

## 2. Frozen inputs (read-only for Phase 3)

Phase 3 **consumes** the following, and **never modifies, regenerates, renames, moves, or
deletes** any of it:

- All Phase 1 code, data, and reports.
- All Phase 2 code, data, and reports, including but not limited to:
  - `data/metadata/` — Phase 2 registries and manifests (`dataset_manifest.json`,
    `phase2_input_manifest.json`, `resource_registry.json`, `benchmark_resources.json`,
    `phase2_freeze_manifest.json`, `reproducibility_manifest.json`,
    `longmemeval_provenance_exceptions.json`).
  - `data/reports/phase1_*`, `data/reports/phase2_*` — Phase 1/2 validation and inspection
    reports.
  - The Unified Memory Record (UMR) artifacts and schema produced by
    `preprocessing/unified_memory.py` / `preprocessing/unified_schema.py`.
  - `docs/phase2/*` — Phase 2 documentation, including `PHASE2_FREEZE.md`.
  - `config/pipeline_config.yaml`.
- The four memory-foundation datasets as processed by Phase 1–2 (LoCoMo, LongMemEval, MSC,
  Conversation Chronicles) — see [DATASET_CAPABILITY_MATRIX.md](DATASET_CAPABILITY_MATRIX.md).

If it is unclear whether a file belongs to Phase 1/2, it is treated as frozen and left
untouched until a human resolves the ambiguity.

## 3. Historical-only (reference, never active)

`phase3_reference/` contains the previous Phase 3 attempt in its entirety: Clean Agent V1,
the V2/V2b/V2c candidate-selection thread, Experiments A–I, retrieval and derived-memory
diagnostics, the incomplete Qwen3-8B pilot, and all associated reports, logs, scripts, and
results.

- `phase3_reference/` is **read-only reference material**. Its results are historical
  evidence, not validated design.
- No file under `phase3_reference/` may be imported, executed, or copied into the active
  implementation without being re-derived and re-justified in the new specification.
- `phase3_reference/` is excluded from the public GitHub repository (see repo `.gitignore`)
  but remains part of the local working tree for consultation during the restart.

## 4. New active design surface

`phase3/` is the **only** location for the new, active Phase 3 work. At the current stage
(3.1) it contains specification, schema, and contract documents only — **no implementation
code**. Future stages will add implementation packages under `phase3/` (or a sibling
directory named at that time); this boundary document will be updated when that happens.

## 5. Repository surfaces Phase 3 may read

| Surface | Access | Notes |
|---|---|---|
| `data/metadata/*` | read-only | Phase 2 manifests/registries |
| `data/reports/phase1_*`, `data/reports/phase2_*` | read-only | validation history, for context only |
| `data/raw/`, `data/processed/` (Phase 2 UMR outputs) | read-only | the frozen memory substrate |
| `preprocessing/unified_memory.py`, `unified_schema.py` | read-only (import, do not edit) | UMR schema/loader |
| `docs/phase2/*` | read-only | Phase 2 documentation |
| `phase3_reference/*` | read-only, reference | historical evidence only |
| `config/pipeline_config.yaml` | read-only | Phase 1 pipeline config |
| `phase3/*` | read-write | the new active design/implementation surface |

Phase 3 must not write to any path outside `phase3/` (and, once implementation begins,
its own designated output directories under `phase3/`, `data/experiments/`, `data/reports/`,
and `data/events/` using clearly Phase-3-scoped filenames — never overwriting a Phase 1/2
filename).

## 6. Statement of non-modification

> Phase 3 consumes the frozen Phase 2 substrate but does not modify it. Phase 3 does not
> rebuild, regenerate, or re-derive any Phase 1 or Phase 2 artifact. Any apparent need to
> change a Phase 1/2 artifact is a signal to stop and escalate, not a task to perform.

## 7. Relationship to other Phase 3.1 documents

This boundary is a precondition for everything else in `phase3/specification/`,
`phase3/schemas/`, and `phase3/contracts/`. Where those documents describe reading Phase 2
data (e.g. the memory ontology's "foundation memory" definition), they refer back to this
document rather than restating the boundary.
