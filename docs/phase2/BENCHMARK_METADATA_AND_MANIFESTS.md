# Phase 2.5 — Benchmark Metadata & Manifests

## 1. Why Phase 2.5 exists

Phase 2.4 (`preprocessing/benchmark_organization.py`) answers *"what job
does this resource do in the benchmark"* — its **role** (memory / workload
/ attack / sleeper / evaluation). It does not answer a different, equally
important question: *"exactly which version, snapshot, preparation
pipeline, schema, policy, configuration, and seed produced this artifact,
and can someone else reproduce it?"*

Phase 2.5 answers that second question, for every one of the 28 tracked
resources, without touching, re-deriving, or duplicating anything Phase
2.4 already established.

The test this module exists to pass, six months from now: *if an
experiment produces an interesting result, can MAMBench say exactly which
resource, source version, snapshot, MAMBench preparation, schema, policy,
configuration, and seed produced it?*

## 2. Resource identity vs. role vs. status vs. artifact identity vs.
   experiment configuration

These five concepts are kept as five distinct things, never merged into
one flat record:

| Concept | Question it answers | Where it lives |
|---|---|---|
| Resource identity | "What is this thing, and where did it come from?" | `preprocessing/registry.py` → `resource_registry.json` |
| Resource role | "What job does it do in the benchmark?" | `preprocessing/benchmark_organization.py` → `benchmark_resources.json` |
| Resource state | "How available/processed/implemented is it?" | `phase1_status` / `acquisition_status` / `implementation_status` (registry + organization) |
| **Reproducibility (artifact) identity** | "Exactly which version/config/policy/seed produced the prepared artifact from this resource?" | **`preprocessing/reproducibility.py` (this phase) → `reproducibility_manifest.json`** |
| Experiment configuration | "How did a specific experiment use these artifacts?" | Not built yet — reserved for a later phase (Section 16 below); Phase 2.5 deliberately does not build an experiment runner |

A resource can be correctly *registered* (identity), correctly *organized*
(role), and still have **no prepared artifact** (e.g. `dsrm`, `agentpoison`
— specification-only, no local implementation). Phase 2.5's
`artifact_identity` block makes that distinction explicit per resource
(`status: "not_applicable_no_prepared_artifact"` vs `"prepared"`) — see
Section 17 of the implementation prompt this phase was built from.

## 3. The single authoritative chain

```
registry.py                 -- resource IDENTITY + Phase 1 status
        |
        v
phase2_manifest.py           -- Phase 2 input APPROVAL status
        |
        v
benchmark_organization.py    -- benchmark ROLE
        |
        v
reproducibility.py (Phase 2.5) -- REPRODUCIBILITY IDENTITY
        |
        +-- resource_identity      (human-readable, read-through)
        +-- canonical_identity      (machine/timestamp-independent, hashed)
        +-- artifact_identity       (derived from canonical_identity)
```

Each link reads every upstream link and never writes to one. Phase 2.5
adds no second resource registry: every identity/role/status field it
reports is read straight through from `benchmark_resources.json` (which
itself reads through `resource_registry.json` and
`phase2_input_manifest.json`). Only genuinely new facts — canonical
identity, artifact identity, code state, configuration identity, seed
semantics — are introduced here.

## 4. Versioning policy

Every version/policy value in the manifest is **read from its existing
single source of truth**, never re-typed as an independent literal:

| Field | Source of truth |
|---|---|
| `preprocessing_pipeline_version` | `preprocessing/__init__.py: PIPELINE_VERSION` |
| `unified_memory_record_schema_version` | `preprocessing/unified_schema.py: SCHEMA_VERSION` |
| `temporal_normalization_policy_version` | `preprocessing/temporal.py: NORMALIZATION_POLICY_VERSION` |
| `phase2_input_manifest_version` | `preprocessing/phase2_manifest.py: PHASE2_MANIFEST_VERSION` |
| `benchmark_organization_version` | `preprocessing/benchmark_organization.py: ORGANIZATION_VERSION` |
| `reproducibility_manifest_version` | `preprocessing/reproducibility.py: REPRODUCIBILITY_MANIFEST_VERSION` |

`preprocessing/schema_workload.py` (`WorkloadRecord`) has **no** independent
version constant today. Rather than inventing one, the manifest records
`workload_record_schema_version: "unknown"` with an explanatory note. This
is a documented pre-existing gap (already flagged in
`docs/phase2/REPRODUCIBILITY_REPORT.md`), not something Phase 2.5 silently
papers over.

## 5. Snapshot policy

A resource's **snapshot id** is its local acquisition timestamp
(`dataset_manifest.json`'s `acquisition_date`), when one was recorded at
acquisition time. When it was not (a resource never run through Phase 1's
acquisition step), `snapshot_id` is the literal string `"unknown"` — never
a guessed or invented date.

## 6. Preparation version policy

`preparation_version` in `canonical_identity` is `PIPELINE_VERSION` for
any resource whose Phase 1 status is `PROCESSED` or `PREPARED` (i.e. an
actual MAMBench pipeline ran against it), and the literal
`"not_applicable"` otherwise (e.g. `INSPECTED`-only resources like
`toolbench`, `webshop`, `agentpoison`). This distinguishes "the pipeline
processed this" from "this resource is merely documented."

## 7. Schema version policy

`unified_memory_record_schema_version` is populated (from
`unified_schema.SCHEMA_VERSION`) **only** for the four core memory-
foundation datasets (LoCoMo, LongMemEval, MSC, Conversation Chronicles) —
the only resources actually mapped into UMR. Every other resource
explicitly reads `"not_applicable"`. Validation Check 8
(`preprocessing/reproducibility_validation.py`) enforces this scoping is
never violated in either direction.

## 8. Temporal policy version

`temporal_normalization_policy_version` (from
`temporal.NORMALIZATION_POLICY_VERSION`) follows the identical scoping
rule as the schema version above — core datasets only, `"not_applicable"`
elsewhere, enforced by Check 9.

## 9. Quality policy

Phase 2.5 does not recompute or override any record's `quality_status`.
It references the existing, authoritative vocabulary
(`preprocessing.unified_schema.VALID_QUALITY_STATUSES` — `valid`,
`repaired`, `valid_flagged`, `irrecoverably_invalid`) in
`schema_and_policy_versions.quality_policy`, so a manifest reader knows
which classification scheme produced the corpus's quality labels, without
this document re-deriving or duplicating them.

## 10. Provenance policy

Similarly, `schema_and_policy_versions.provenance_policy` references the
UMR `field_status` vocabulary (`preprocessing.unified_schema`'s four
origins — `SOURCE_PROVIDED`, `BENCHMARK_GENERATED`, `INFERRED`,
`MODEL_PREDICTED` — and four absence reasons) rather than asserting a
bare `provenance: true`.

## 11. Seed policy

The project has exactly **one** master seed
(`config/pipeline_config.yaml: seed: 20260101`), and it is consumed by
exactly **one** pipeline step: Conversation Chronicles' deterministic
reservoir sample. Every resource's `canonical_identity.seed` block is
structured, not a single blanket value:

```json
{"seed_applicable": false, "seed_value": null, "seed_status": "seed_not_applicable"}
```

only `conversation_chronicles` reads `seed_applicable: true` with the live
`master_seed` value. A resource is never assigned a seed value merely
because the manifest schema has a seed field (Section 12 of the
implementation prompt) — Check 10 enforces this per-resource, and the
pipeline-level `master_seed` is recorded once, separately, in
`pipeline_identity`.

## 12. Configuration identity

`configuration_id` is a **content hash** (SHA-256) of
`config/pipeline_config.yaml`'s raw bytes — not its filename, not its
absolute path. Two checkouts of the same commit on two different machines,
in two different directories, produce the identical `configuration_id`.
The config file's *relative* repo path is recorded separately, as
convenience metadata only (`config_relative_path`), and never participates
in any hash.

## 13. Canonical identity / hash policy

`canonical_identity` is the **minimal** field set needed to answer "which
exact version/config/policy/seed produced this," and nothing else:

```
resource_id
source_dataset_version_or_revision   (or "unknown")
snapshot_id                          (or "unknown")
preparation_version                  (or "not_applicable")
unified_memory_record_schema_version (or "not_applicable")
temporal_normalization_policy_version (or "not_applicable")
configuration_id                     (content hash of pipeline_config.yaml)
seed                                 ({seed_applicable, seed_value, seed_status})
```

`canonical_identity_hash` is `sha256(json.dumps(canonical_identity,
sort_keys=True))`. Explicitly **excluded**: `generated_at`, `local_path`,
any absolute filesystem path, and machine identity — none of these
participate in the hash, and none live inside the `canonical_identity`
block at all (they live in the separate `source_identity` convenience
block, or in `pipeline_identity`, which itself only feeds `configuration_id`
— a content hash — into any resource's canonical set).

`artifact_identity.artifact_id` is derived deterministically from the
canonical fields via `preprocessing.io_utils.deterministic_id` (the same
SHA-256-truncated-hex convention already used for `memory_id`/`task_id`),
so an artifact's identity changes exactly when a canonical input changes —
never on a manifest reformat, path change, or re-run at a different time.

## 14. Path portability

Canonical identity and artifact identity never contain an absolute
filesystem path (`C:\Users\...`, `/home/...`, `/mnt/...`). Convenience
fields (`source_identity.local_path`, `pipeline_identity.configuration_identity.config_relative_path`)
may contain a *repo-relative* path, which is portable across checkouts.
`preprocessing/reproducibility_validation.py`'s Check 13 scans every
canonical field for an absolute-path pattern and fails the report if one
leaks in.

## 15. Unknown-version handling

Every field that could be missing carries an explicit sentinel —
`"unknown"` (the fact genuinely isn't known) or `"not_applicable"` (the
concept doesn't apply to this resource) — rather than a plausible-looking
invented value (`"1.0"`, `"latest"`). Check 6 specifically verifies that
any registry entry whose `version_or_revision` says `"unavailable"` maps
to the literal `"unknown"` in `canonical_identity`, never to a fabricated
version string.

## 16. Manifest hierarchy

```
MAMBench
   |
   +-- Resource Registry            (resource_registry.json)
   |
   +-- Phase 2 Input Manifest       (phase2_input_manifest.json)
   |
   +-- Benchmark Organization        (benchmark_resources.json)
   |       |
   |       +-- memory / workload / attack / sleeper / evaluation
   |
   +-- Reproducibility Manifest      (reproducibility_manifest.json) -- Phase 2.5
           |
           +-- pipeline_identity      (code state, master seed, config identity)
           +-- schema_and_policy_versions
           +-- per-resource:
                 +-- source_identity      (human-readable)
                 +-- canonical_identity     (hashed)
                 +-- canonical_identity_hash
                 +-- artifact_identity      (derived)
```

Experiment-level configuration (Section 16 of the implementation prompt —
"how did a specific experiment use these artifacts") is **not** built in
Phase 2.5. It is a reserved future layer that would reference
`artifact_id`s produced here, once an experiment runner exists (a later
phase, out of scope now).

## 17. Reproducibility workflow

To reproduce any experiment input this manifest describes:

1. `git checkout <pipeline_identity.code_state.commit_hash>` (check
   `is_dirty` — if `true`, the manifest-generating run had uncommitted
   changes and the commit hash alone does not fully identify the code).
2. Use `config/pipeline_config.yaml` whose content hashes to
   `pipeline_identity.configuration_identity.configuration_id`.
3. Place each resource's raw file(s) at the paths its
   `source_identity.local_artifact_checksums` sha256 values were computed
   from.
4. Run `python -m preprocessing.run_all`, then
   `python -m preprocessing.unified_memory`, then
   `python -m preprocessing.temporal_validation` — using
   `pipeline_identity.master_seed`.
5. The resulting artifact's `artifact_id` (recomputed from the same
   canonical inputs) should match `artifact_identity.artifact_id` exactly.

## 18. Limitations

- Dependency pinning remains weak: `requirements.txt` uses `>=` ranges, no
  lockfile exists. Recorded in `unresolved_identity_gaps`, not fixed here
  (pinning is a general project-hygiene item, not a Phase 2.5 objective).
- `WorkloadRecord`'s schema has no independent version constant (Section
  4 above) — a genuine repository gap, documented rather than invented
  around.
- Several resources' `source_dataset_version_or_revision` is genuinely
  `"unknown"` because the upstream source itself never published a
  version tag (LoCoMo, LongMemEval, Conversation Chronicles) — this is a
  property of the source, not a Phase 2.5 shortcoming, and is listed per-
  resource in `unresolved_identity_gaps`.
- `artifact_id` identifies *what canonical inputs produced an artifact*;
  it is not a content hash of the artifact's actual bytes on disk (the
  four core datasets' UMR output is ~1.27M records — hashing the full
  corpus routinely was judged unnecessary overhead per Section 14 of the
  implementation prompt, given `dataset_manifest.json`'s existing raw-file
  SHA-256 checksums and Phase 2.2/2.3's own validated record counts
  already establish artifact integrity).

## 19. What Phase 2.5 does not implement

Per the implementation prompt's Section 31, Phase 2.5 implements
**nothing** beyond reproducible benchmark identity and metadata. It does
not implement: attack reconstruction (DSRM, AgentPoison, MINJA,
MemoryGraft, FARMA, MPBench), poisoned-memory generation, attack
execution, propagation, lifecycle graphs, sleeper generation/detection,
defenses, mitigation, containment, attack-origin attribution, GNN/GLN
analysis, agent execution, or model benchmarking. Every occurrence of
words like "attack" or "sleeper" in this phase's code is a **role name**
or **resource-metadata field** read through from Phase 1/2.4 — never
implemented later-phase functionality.
