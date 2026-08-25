# Benchmark-Level Dataset Organization (Phase 2.4)

`preprocessing.benchmark_organization.ORGANIZATION_VERSION = "1.0.0"`.
Organization logic: [`preprocessing/benchmark_organization.py`](../../preprocessing/benchmark_organization.py).
Validation: [`preprocessing/benchmark_validation.py`](../../preprocessing/benchmark_validation.py).
Manifest: `data/metadata/benchmark_resources.json`. Report:
`data/reports/phase2_4_benchmark_organization_validation_report.json`.

## Why benchmark-level organization is necessary

By the end of Phase 2.3, MAMBench has 28 tracked resources
(`data/metadata/resource_registry.json`) spanning five genuinely
different jobs — the clean memory substrate, task workloads, attack
specifications, sleeper/dormant-poisoning resources, and
evaluation/defense-comparison resources — but nothing in the project yet
answers, in one place: *which resources constitute memory, which are
workloads, which are attacks, which are sleeper resources, and which are
evaluation resources, along with whether each is actually available or
merely identified.* Later benchmark construction (Phase 4+) needs that
separation to be explicit and enforced, not implicit in prose — in
particular, it must never be possible for an attack or sleeper resource
to be accidentally treated as clean memory data.

## What Phase 2.4 is (and is not)

Phase 2.4 is a **join and classification layer**, not a new data source:

- **Identity, provenance, and category** for every resource already
  exist in Phase 1's `preprocessing/registry.py`
  (`data/metadata/resource_registry.json`) — untouched by Phase 2.4.
- **Honest availability/processing/approval status** already exists in
  Phase 2.1's `preprocessing/phase2_manifest.py`
  (`data/metadata/phase2_input_manifest.json`) — untouched by Phase 2.4.
- Phase 2.4 (`preprocessing/benchmark_organization.py`) reads both,
  classifies each resource's existing `category` into exactly one
  **benchmark role**, and writes the join as
  `data/metadata/benchmark_resources.json`. It writes to no other file
  and mutates neither of the two files it reads.

No dataset is regenerated, no memory record is rescored, and the Phase
2.2 UMR schema (`1.1.0`) and Phase 2.3 temporal normalization policy
(`2.3.0`) are unchanged — Phase 2.4 only *re-verifies* they are unchanged
(see "UMR integrity" below), it does not touch the code or data that
produced them.

## The five benchmark roles

| Role | Registry `category` | Resources (current registry) |
|---|---|---|
| `memory` | `memory_data` | LoCoMo, LongMemEval, MSC, Conversation Chronicles |
| `workload` | `task_workload` | API-Bank, ToolBench, StrategyQA, WebShop, SWE-bench Verified, tau-bench, tau2-bench, EHRAgent, MIMIC-III/eICU |
| `attack` | `attack` | AgentPoison, MINJA, DSRM, MemoryGraft, FARMA, MPBench |
| `sleeper` | `sleeper` | Hidden in Memory, Sleeper Dataset Generator |
| `evaluation` | `security_benchmark` | MemSecBench, MEMSAD, MemAudit, A-MemGuard, ASB, AgentDojo, InjecAgent |

The mapping (`preprocessing.benchmark_organization._CATEGORY_TO_ROLE`) is
total (every category the registry currently emits has exactly one role)
and fixed at 1:1 — no resource currently documents a genuine second role,
so `secondary_roles` is `[]` for all 28 entries today; the field exists
(not fabricated data, an empty-but-present list) so a future resource
that legitimately serves two roles has somewhere to say so without a
schema change.

`classify_role()` raises rather than silently defaulting on an
unrecognized category — a category the registry doesn't currently emit
must be classified deliberately if it ever appears, not swallowed into
an arbitrary role.

## The memory-foundation boundary (enforced, not just documented)

`APPROVED_MEMORY_FOUNDATION` is the same four-identifier tuple Phase
2.2/2.3 already build the real corpus from
(`preprocessing.unified_schema.CORE_DATASETS`) — not a second,
independently typed constant that could silently drift from it.
`build_benchmark_organization()` raises `RoleClassificationError` (refuses
to produce a manifest at all) if either direction of the invariant is
violated:

- a resource in `APPROVED_MEMORY_FOUNDATION` is not classified `memory`, or
- a resource classified `memory` is not in `APPROVED_MEMORY_FOUNDATION`
  (i.e. a hypothetical fifth `memory_data`-category resource cannot
  silently expand the foundation just by being added to the registry).

`tests/test_benchmark_organization.py::test_build_raises_if_a_memory_foundation_id_is_misclassified`
proves this is actually enforced (by synthetically corrupting the
role-mapping table, not just asserting today's data happens to be
consistent).

## Role vs. status — kept as separate fields, never collapsed

A resource's **role** (what job it does) and its **status** (whether it
is actually implemented/acquired/approved) are independent axes. Every
organized resource carries both, verbatim from the two source documents
plus one small derived field:

- `phase1_status` / `preprocessing_status` — Phase 1's own status, unchanged.
- `phase2_status` / `phase2_input_approved` — Phase 2.1's own honest
  approval status, unchanged (only the four memory-foundation datasets
  are ever `phase2_input_approved: true`).
- `implementation_status` — new in Phase 2.4, computed by a single
  deterministic rule
  (`preprocessing.benchmark_organization._implementation_status()`) from
  each resource's own existing `local_path`/`acquisition_status` text —
  never a per-resource hardcoded judgment:
  - `local_copy_present` — data/code was actually acquired locally.
  - `public_code_available_not_locally_implemented` — a runnable public
    repository exists, but nothing was cloned or executed by this project.
  - `specification_only_no_public_implementation_found` — only a paper
    was verified; no code release was located anywhere.
  - `unresolved` — none of the above evidence patterns matched (does not
    currently occur in the real registry).

**Worked example — DSRM**: `primary_role: "attack"`,
`implementation_status: "specification_only_no_public_implementation_found"`,
`local_path: null`, `phase2_input_approved: false`. The role says "this is
an attack resource"; the status says "no implementation exists to run,
reconstruction-dependent" — exactly the Section 6 example from the Phase
2.4 brief, produced by the general rule above, not a DSRM-specific special
case.

**Worked example — Hidden in Memory**: `primary_role: "sleeper"`,
`implementation_status: "specification_only_no_public_implementation_found"`
(paper-only, no public repo). **Sleeper Dataset Generator**:
`primary_role: "sleeper"`, `local_path` present (templates were acquired
in Phase 1), `implementation_status: "local_copy_present"` — the
generator's *templates* are locally present, which is a different claim
from "a sleeper dataset has been generated" (it has not — Phase 2.4 does
not generate one, same as Phase 1).

## Availability is never inflated by organization

`phase2_input_approved` is `true` for exactly the four memory-foundation
datasets — re-verified by
`preprocessing/benchmark_validation.py`'s
`only_memory_foundation_is_phase2_input_approved`-equivalent check
(`availability_is_represented_honestly`) — and no resource with zero
on-disk artifact evidence (`artifact_presence_on_disk` all false/empty)
is ever marked approved. `AVAILABLE ≠ ACQUIRED ≠ PROCESSED ≠ APPROVED FOR
MEMORY FOUNDATION ≠ ATTACK IMPLEMENTED` (Phase 2.4 brief §9) is visible
directly in the manifest: e.g. AgentPoison/MINJA/ASB/AgentDojo/InjecAgent
all have `acquisition_status` containing "CODE AVAILABLE" (a public repo
was verified to exist and its license checked) but
`implementation_status: "public_code_available_not_locally_implemented"`
and `local_path: null` — "the code is out there" is not conflated with
"we have it" or "we ran it."

## Provenance preservation

Every organized entry carries a `provenance` object distinguishing:

```json
"provenance": {
  "source": "external -- see source_reference; not authored by MAMBench",
  "mambench_created": "this manifest entry's role classification and status join only; no new dataset content, label, or file was generated by Phase 2.4"
}
```

This is identical across all 28 resources by design — it is a structural
statement about what Phase 2.4 does (join + classify), not a per-resource
fact, so it does not vary per resource. The resource's actual origin
remains in `source_reference` (verbatim from the registry), never
overwritten or paraphrased into something that could be mistaken for the
original source document.

## The organizational manifest (`data/metadata/benchmark_resources.json`)

Top-level shape:

```
organization_version, generated_at, generated_from {resource_registry, phase2_input_manifest}
role_vocabulary: [attack, evaluation, memory, sleeper, workload]
memory_foundation: {approved_dataset_ids, note}
resources_by_role: {role: [sorted resource_id, ...]}
resource_count_by_role: {role: int}
total_resources: 28
umr_integrity: {umr_schema_version, temporal_normalization_policy_version,
                approved_dataset_ids, umr_validation_overall_status,
                umr_per_dataset_record_counts, umr_total_records,
                temporal_validation_overall_status}
resources: [ {resource_id, name, primary_role, secondary_roles,
              source_category, research_purpose, source_reference,
              version_or_revision, access_and_license, local_path,
              phase1_status, preprocessing_status, acquisition_status,
              implementation_status, phase2_status, phase2_input_approved,
              artifact_presence_on_disk, known_issues, reproducibility,
              limitations, intended_later_phase, provenance}, ... ]
```

`umr_integrity` is populated by reading Phase 2.2/2.3's own
already-written validation reports
(`data/reports/phase2_2_unified_memory_validation_report.json`,
`data/reports/phase2_3_temporal_validation_report.json`) — Phase 2.4
never rescans the 1.27M-record corpus itself to build this manifest,
keeping manifest generation cheap regardless of corpus size.

## Deterministic organization

`build_benchmark_organization()` is a pure function of the registry and
Phase 2.1 manifest contents plus the fixed `generated_at` argument passed
in: no wall-clock read inside the function (the caller supplies
`generated_at`), no random ordering, no reliance on dict-iteration order
for anything that ends up in the output. `resources` is explicitly
sorted by `resource_id`; every `resources_by_role[<role>]` list is
explicitly sorted. `tests/test_benchmark_organization.py::test_organization_is_deterministic`
and `::test_resources_by_role_lists_are_sorted` /
`::test_resources_list_is_sorted_by_resource_id` verify this; the
validator additionally builds the organization twice and compares.

## Logical organization vs. physical storage

Phase 2.4 deliberately does **not** move, copy, or symlink any file on
disk into a `benchmark/memory/`, `benchmark/workloads/`, ... directory
tree. Two reasons:

1. **No unnecessary duplication of the real corpus.** 1,266,194 Unified
   Memory Records already live at
   `data/processed/unified_memory/<dataset>/memory_records.jsonl`;
   copying or symlinking them into a second logical tree would either
   double storage (copy) or introduce a Windows-portability dependency
   this project's environment (Windows 11, no elevated symlink
   privilege assumed) cannot rely on (symlink) — the Phase 2.4 brief
   itself only asks for symlinks "where appropriate and portable," and
   neither condition holds well here.
2. **Provenance-chain safety.** Every existing phase (1, 2.1, 2.1-R, 2.2,
   2.3) already writes to a fixed, well-known path that later code
   depends on (`preprocessing/unified_memory.py`,
   `preprocessing/temporal_validation.py`, this project's own tests).
   Introducing a second physical path for the same data would create two
   sources of truth for one dataset — exactly what the Phase 2.4 brief's
   "no second conflicting resource registry" instruction warns against,
   generalized to files.

Instead, the **logical** organization (`resources_by_role` in the
manifest) and the **physical** location (`local_path` /
`artifact_presence_on_disk` per resource, already the exact paths Phase
1/2.1/2.2/2.3 use) are both present in the same manifest entry, joined by
`resource_id` — a reader gets the logical grouping and the real path in
one place without either being duplicated or moved.

## Validation

`preprocessing/benchmark_validation.py` implements the Phase 2.4 brief's
12 numbered tests as one check-list report
(`data/reports/phase2_4_benchmark_organization_validation_report.json`),
re-running Phase 2.2's `unified_validation.validate_cross_dataset()` and
Phase 2.3's `temporal_validation.validate_temporal()` fresh (not just
reading their last-written reports) so a single Phase 2.4 run can answer
"did this break anything earlier." Run against the real registry/corpus:

| # | Check | Status |
|---|---|---|
| 1 | `all_registry_resources_have_a_primary_role` | PASS |
| 2 | `every_primary_role_is_from_the_approved_vocabulary` | PASS |
| 3 | `memory_foundation_is_exactly_the_four_approved_datasets` | PASS |
| 4 | `no_attack_resource_in_memory_foundation` | PASS |
| 5 | `no_sleeper_resource_in_memory_foundation` | PASS |
| 6 | `no_workload_or_evaluation_resource_in_memory_foundation` | PASS |
| 7 | `every_resource_retains_source_provenance` | PASS |
| 8 | `availability_is_represented_honestly` | PASS |
| 9 | `organization_is_deterministic_across_independent_runs` | PASS |
| 10 | `phase1_processed_data_not_mutated_by_phase2_4` | PASS |
| 11 | `phase2_2_unified_memory_validation_still_passes` / `phase2_3_temporal_validation_still_passes` | PASS / PASS |
| 12 | `umr_schema_temporal_policy_and_record_counts_unchanged` | PASS |

**Overall: PASS**, 28/28 resources organized, all five roles populated
(`memory: 4, workload: 9, attack: 6, sleeper: 2, evaluation: 7`).

## Limitations

- `secondary_roles` is `[]` for every resource today — no currently
  tracked resource's registry entry documents a genuine second role, so
  none is asserted. The field exists for a future resource that does.
- `implementation_status`'s `unresolved` bucket does not currently occur
  (every one of the 28 registry entries matches one of the three positive
  patterns); it exists as an honest fallback rather than forcing a
  guess if a future registry entry's `acquisition_status` text doesn't
  match any known pattern.
- The manifest's per-resource fields are a *join*, not a re-verification,
  of the registry and Phase 2.1 manifest's own claims (e.g. checksums,
  license text) — Phase 2.4 does not independently re-hash raw files or
  re-check licenses; that verification, where it exists, was already
  done by Phase 1/2.1 and is carried through unchanged.

## Scope boundary

Phase 2.4 builds an organizational *view* over existing resources —
nothing more. It does not implement attack reconstruction, DSRM or any
other attack's implementation, poisoned-memory generation, poisoning
labels, attack execution, propagation analysis or graphs, memory
lifecycle graphs, sleeper detection, sleeper dataset generation,
defenses, mitigation, containment, attack-origin attribution,
embeddings, or GNN/GLN infrastructure. Those are later phases and would
consume this organizational layer, not extend it.
