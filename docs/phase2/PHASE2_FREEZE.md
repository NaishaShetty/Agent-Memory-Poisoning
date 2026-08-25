# Phase 2 Freeze — Canonical Baseline

## 1. What Phase 2 established

Phase 2 took the four raw-but-honestly-acquired memory datasets Phase 1
produced and turned them into a single, internally consistent, provenance-
preserving, reproducible benchmark substrate — without ever fabricating a
fact the source data didn't provide. Phases 2.2 through 2.6 each added one
layer; Phase 2.7 is the acceptance and freeze gate that confirms all six
layers still agree, and records the whole-Phase-2 canonical state a later
phase can rely on without re-deriving it.

## 2. Phase 2.2 — Unified Memory Record (UMR)

Mapped all four core datasets' independently-shaped Phase 1 output into
one shared schema (`preprocessing/unified_schema.py`, version `1.1.0`),
with an explicit `field_status` provenance model on every field
(`SOURCE_PROVIDED` / `BENCHMARK_GENERATED` / `INFERRED` / absence reasons)
so no reader ever has to guess whether a value came from the source
dataset or from MAMBench itself.

## 3. Phase 2.3 — Temporal normalization

Gave every UMR record a `normalized_timestamp`, `temporal_provenance`, and
(where applicable) a deterministic `benchmark_timestamp`, policy version
`2.3.0` (`preprocessing/temporal.py`). Never invents a source-absolute
timestamp for a dataset that never provided one — LoCoMo and LongMemEval
carry real calendar timestamps; MSC and Conversation Chronicles never do,
and are never mislabeled as if they did.

## 4. Phase 2.4 — Resource organization

Classified all 28 tracked project resources (not just the four memory
datasets) into exactly one of five roles — `memory` (4), `workload` (9),
`attack` (6), `sleeper` (2), `evaluation` (7) — and made the memory-
foundation boundary a hard, enforced invariant: only LoCoMo, LongMemEval,
MSC, and Conversation Chronicles may ever be `memory`-role, in either
direction (`preprocessing/benchmark_organization.py`, organization
version `1.0.0`).

## 5. Phase 2.5 — Reproducibility metadata

Gave every resource a `canonical_identity` (source version/snapshot,
MAMBench preparation version, schema version, temporal policy version,
configuration id, seed) and a deterministic `canonical_identity_hash`,
plus — for the four resources an actual preparation pipeline has run
against — an `artifact_identity`. Canonical identity is machine- and
timestamp-independent by construction: it excludes `generated_at` and any
local filesystem path (`preprocessing/reproducibility.py`, manifest
version `1.0.0`).

## 6. Phase 2.6 — Substrate validation

The first cross-phase layer: re-ran Phase 2.2's, 2.3's, and 2.4's real
validators fresh and added checks no single earlier validator could
express — cross-manifest resource-identity/role/status agreement, version
consistency across every layer that states one, record-count agreement
backed by a freshly re-scanned corpus, and an explicit
experimental-activation-boundary check
(`preprocessing/benchmark_substrate_validation.py`, 29 checks, all PASS).

## 7. Phase 2.7 — Acceptance & freeze

This phase. Re-confirms the entire Phase 2 substrate by calling Phase
2.6's validator fresh exactly once, computes one deterministic identity
for the *whole* Phase 2 state (not per-resource — see Section 12), and
writes the single canonical freeze manifest,
`data/metadata/phase2_freeze_manifest.json`
(`preprocessing/phase2_freeze_validation.py`, freeze version `2.7.0`).

## 8. Canonical memory foundation

```
LoCoMo                    5,882
LongMemEval             210,365
MSC                      227,185
Conversation Chronicles  822,762
------------------------------
Total                  1,266,194
```

No additional dataset is silently included; none of the four is missing.

## 9. Canonical resource organization

```
memory       4
workload     9
attack       6
sleeper      2
evaluation   7
------------
total       28
```

## 10. Canonical versions

| Layer | Version |
|---|---|
| Unified Memory Record schema | 1.1.0 |
| Temporal normalization policy | 2.3.0 |
| Benchmark organization | 1.0.0 |
| Reproducibility manifest | 1.0.0 |
| Substrate validation | 1.0.0 |
| Phase 2 freeze | 2.7.0 |

## 11. Canonical manifests

| Manifest | Path | Role |
|---|---|---|
| Resource registry | `data/metadata/resource_registry.json` | resource IDENTITY |
| Phase 2 input manifest | `data/metadata/phase2_input_manifest.json` | Phase 2 input APPROVAL |
| Benchmark organization | `data/metadata/benchmark_resources.json` | benchmark ROLE |
| Reproducibility manifest | `data/metadata/reproducibility_manifest.json` | REPRODUCIBILITY IDENTITY |
| **Phase 2 freeze manifest** | `data/metadata/phase2_freeze_manifest.json` | **whole-phase canonical pointer** |

The freeze manifest does not duplicate any of the first four — it
references them by path and states the whole-Phase-2 canonical identity
and freeze status on top.

## 12. Canonical Phase 2 identity

A single SHA-256 hash over exactly:

```
preprocessing_pipeline_version
umr_schema_version
temporal_normalization_policy_version
benchmark_organization_version
reproducibility_manifest_version
substrate_validation_version
phase2_freeze_version
configuration_id                        (content hash of pipeline_config.yaml)
memory_foundation_dataset_ids
memory_record_counts
memory_record_total
resource_role_counts
total_resources
per_resource_canonical_identity_hashes  (all 28, from Phase 2.5)
```

Deliberately **excluded**: `generated_at`, any absolute local filesystem
path, and machine identity — the same policy Phase 2.5 already established
per-resource, applied once at the whole-phase level. Aggregating all 28
resources' own canonical identity hashes means the whole-phase identity
changes if and only if some individual resource's canonical identity
changed, without re-deriving any of those 28 hashes from scratch.

## 13. Freeze policy

**Frozen** (changing any of these silently would change the canonical
Phase 2 identity hash, and is the exact failure mode the freeze exists to
catch):

- UMR semantics and schema
- memory-foundation membership and memory IDs
- temporal semantics and policy
- benchmark resource roles
- reproducibility metadata semantics and canonical identities
- the Phase 2 manifests themselves

**Allowed after freeze** — later phases may:

- read the frozen Phase 2 substrate
- create derived experimental artifacts on top of it
- create attack-specific data *outside* the frozen clean substrate
- create workload traces, experimental results, and analysis artifacts

**Not allowed after freeze** — later phases must not *silently*:

- modify the frozen UMR or memory IDs
- change source timestamps or temporal provenance
- add or remove memory-foundation datasets
- redefine benchmark resource roles
- rewrite Phase 2 provenance
- overwrite the canonical Phase 2 manifests

If a genuine correction to Phase 2 is ever required, it must be an
explicit new revision — a new freeze version, a documented reason, updated
validation, and an updated canonical identity hash — never an invisible
mutation of the recorded one.

**Mechanism**: this is a tripwire, not a filesystem lock. Phase 2.7 does
not chmod any file or otherwise make the repository harder to develop
against; it records a canonical hash that any future accidental or silent
scientific-state change would break, detectable by re-running
`preprocessing.phase2_freeze_validation` and comparing the resulting hash
against the one recorded in `phase2_freeze_manifest.json`.

## 14. Git baseline

As of this freeze, the repository's Phase 2 work (2.3 through 2.7) is
uncommitted in the working tree — see
`docs/phase2/PHASE2_7_COMPLETION_REPORT.md`'s Git Baseline section for the
exact `git status`/`git log` evidence and the proposed (not yet executed)
canonical commit message and tag. Per this project's git safety policy,
Phase 2.7 documents the proposed baseline rather than creating the commit
or tag itself; the actual commit/tag is a separate, explicit action for
the user to authorize.

## 15. Known limitations

Carried forward, unresolved, and not claimed fixed by this freeze:

- No dependency lockfile exists (`requirements.txt` uses `>=` ranges).
- `preprocessing/schema_workload.py` (`WorkloadRecord`) has no independent
  schema version constant.
- Several resources' `source_dataset_version_or_revision` is genuinely
  `"unknown"` because the upstream source itself never published a
  version tag (LoCoMo, LongMemEval, Conversation Chronicles).
- The two corrupted LongMemEval records flagged since Phase 1 remain
  quarantined, not repaired (repairing them would mean guessing at
  destroyed characters, which this project's data-integrity rules
  forbid).
- LoCoMo's QA answers/evidence remain dataset-annotated, not independently
  verified ground truth.

None of these block acceptance; Phase 2's own status has always been
`PASS WITH ISSUES` at the phases where these originate, and Phase 2.7
freezes that honest status rather than silently upgrading it to a clean
`PASS`.

## 16. Phase 3 boundary

Phase 3 ("Clean Agent-Memory Environment") may consume: the frozen four-
dataset memory foundation, the frozen UMR, frozen temporal metadata,
selected workload resources, and frozen reproducibility metadata. Phase 3
must not modify the frozen Phase 2 substrate — it builds a clean
experimental environment on top of it, not a replacement for it.

## 17. Experimental activation boundary

Preserved without exception:

```
acquired  ≠  organized  ≠  prepared  ≠  implemented  ≠  experimentally activated
```

- DSRM: Phase 1 acquired/registered → Phase 2 organized/prepared (role
  `attack`, `implementation_status = specification_only_no_public_implementation_found`)
  → **not** experimentally activated in Phase 2 or Phase 3 → reconstructed/
  activated only in Phase 4.
- Workload resources (API-Bank, StrategyQA, etc.): Phase 2 organized/
  prepared → experimentally activated only in Phase 3.
- Memory foundation: Phase 2 frozen substrate → consumed (read-only) by
  Phase 3's clean agent-memory environment.

## 18. What Phase 2 explicitly does not contain

No attack reconstruction (DSRM, AgentPoison, MINJA, MemoryGraft, FARMA,
MPBench), no poisoned-memory generation, no attack execution, no
propagation or lifecycle graphs, no sleeper generation or detection, no
defenses, mitigation, containment, or attack-origin attribution, no
GNN/GLN analysis, and no agent execution or Phase 3 experiment
orchestration. Phase 2.7's final scope scan
(`_scan_forbidden_definitions`, reused unmodified from Phase 2.6) found
zero function/class definitions implementing any of this anywhere in
`preprocessing/`.
