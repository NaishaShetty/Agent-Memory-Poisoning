# Phase 3.2-G — Dataset Evaluation Profiles

Status: **DESCRIPTIVE CAPABILITY LAYER ONLY.** This stage maps, for each of the four
FROZEN datasets, exactly what the real Phase 1/2 data files support for Phase 3
evaluation. It implements no dataset adapter, no real agent execution, no retrieval/
reranking/selection, no memory creation/storage code, and no Qwen/LLM/embeddings
integration. Every non-trivial claim in a profile is grounded in an actual file/field
inspected during this stage (see each profile's `evidence_notes`) — nothing here is
inferred or fabricated.

## Purpose

Phase 3.1 froze the dataset set and each dataset's role
(`phase3/specification/DATASET_CAPABILITY_MATRIX.md`). Phase 3.2-B through 3.2-F built
the evaluation data contracts, core memory metrics, agent-level diagnostics, security/
leakage/determinism/reproducibility tooling, and equivalence/provenance metrics — all of
it dataset-agnostic. Nothing in Phase 3.2 so far records, per dataset, which of those
metrics/conditions actually has real data behind it. This stage (3.2-G) is that mapping:
a thin, honest capability layer that says, per dataset, "this field exists / does not
exist / exists but only partially," and derives from that "this metric is
supported / unsupported / needs an adapter" for every metric and every condition.

## Explicit distinction from the Phase 1/2 registry

This package is **not** a competing dataset registry. `data/metadata/dataset_manifest.json`
remains the single authoritative source of dataset identity (acquisition date, file
list, license, source URL). Every profile's `registry_reference` field points into that
manifest by `dataset_key` — it never restates or duplicates the manifest's content, and
`validation.py`'s `check_registry_reference_resolves` cross-checks that the pointer
actually resolves against the real manifest file, not merely a self-consistent claim
inside the profile. Record counts are likewise not restated as canonical here; each
profile's `registry_reference.record_count_reference` points to
`data/metadata/phase2_freeze_manifest.json`, and the profile only reports the line count
this stage itself observed in the corresponding processed file (which happened to match
in every case checked).

## The frozen-dataset rule

Exactly four datasets, per `DATASET_CAPABILITY_MATRIX.md` section 1 — no dataset may be
added, removed, or have its role changed by this stage:

1. **LoCoMo** (`locomo`) — primary task-level memory and reasoning evaluation.
2. **LongMemEval** (`longmemeval`) — primary large-scale long-term memory and reasoning
   evaluation.
3. **MSC** (`msc`) — lifecycle, provenance, multi-session memory, reuse, and
   longitudinal behavior; **not** forced into the strict-TSR / task-QA framework.
4. **Conversation Chronicles** (`conversation_chronicles`) — longitudinal memory,
   lifecycle, provenance, and reuse validation; same constraint as MSC.

`phase3/evaluation/datasets/capability.py`'s `DATASET_IDS` is the single source of truth
for these four string identifiers, matching `data/metadata/dataset_manifest.json`'s
`datasets` map keys exactly.

## Capability vocabulary

Two distinct, controlled vocabularies are used, at two different levels of granularity:

### 1. Capability states (field-level granularity)

Used for memory/workload/evidence/answer/provenance/lineage/equivalence-availability
judgments:

- **`AVAILABLE`** — directly observed, populated, in the actual file(s) inspected.
- **`PARTIAL`** — observed to be populated for most, but not all, of the sampled/
  inspected records (e.g. LoCoMo: 65/300 sampled tasks have `answer: null`, all
  `question_type: "5"`).
- **`UNAVAILABLE`** — the field's absence was not itself directly confirmed by
  inspecting a specific file (distinguish from `NOT_PROVIDED_BY_SOURCE` below); used
  sparingly in this package's profiles, mostly for derived judgments (e.g. "separate
  from memory" doesn't apply when there's no task layer at all).
- **`UNKNOWN`** — genuinely undetermined one way or the other from what was inspected.
  **`UNKNOWN` is never silently treated as `UNAVAILABLE` or `False` anywhere in
  `validation.py`** — see `is_unknown_status()` and the explicit test
  `test_unknown_never_silently_coerced_in_controlled_vocabulary_check` in
  `phase3/evaluation/tests/test_dataset_profiles.py`.
- **`NOT_PROVIDED_BY_SOURCE`** — used specifically when this stage **positively
  confirmed**, via actual inspection (a whole-file grep, or a confirmed 0-byte file),
  that a field/layer does not exist in the source data. This is the status used for
  MSC/Conversation Chronicles' task/workload layer (`task_records.jsonl` is a literal
  0-byte file on disk, not merely "not sampled"), and for `parent_ids`/`equivalent_to`/
  `conflicts_with`/`superseded_by` across **all four** datasets (whole-file grep, zero
  matches in every one of the four `memory_records.jsonl` files).
- **`PROVISIONAL`** — reserved for a capability whose presence depends on a mechanism
  this stage does not itself build or assume (used sparingly; most such cases in this
  package are expressed at the support-state level instead, see below).

### 2. Support states (metric/condition support — a judgment derived FROM capability states)

Used specifically for `metric_support` and `condition_support`:

- **`SUPPORTED`** — the metric/condition's required inputs are directly available today
  (per the capability-state facts cited in the same entry's `reason`).
- **`SUPPORTED_WITH_ADAPTER`** — the required inputs exist in principle, but a
  not-yet-built transformation (e.g. a real candidate-discovery/reranking/selection
  pipeline) would be needed to actually produce them. This profile package **describes**
  such an adapter requirement (see each profile's `adapter_requirements`); it never
  implements one.
- **`UNAVAILABLE`** — a required input is confirmed absent and no adapter could
  reasonably manufacture it (e.g. Strict TSR for MSC: there is no gold evidence ID
  anywhere in the source, so no adapter fixes this — it is a source-data fact, not a
  missing-pipeline fact).
- **`UNDEFINED`** — the very question doesn't parse for this dataset (e.g. `NO_MEMORY`
  condition for MSC: the condition is defined relative to a task, and no task concept
  exists at all for MSC, so the question "is memory withheld from the task" has no task
  to be withheld from — a stronger claim than "unbuilt" or "absent").
- **`PROVISIONAL`** — the metric is mechanically computable from non-gold inputs alone,
  but doing so today would require synthesizing an execution context this stage has no
  legitimate way to produce (e.g. `RETRIEVAL_UTILIZATION` for MSC/Conversation
  Chronicles).

A support-state judgment is not asserted freestanding — `validation.py`'s
`check_strict_tsr_implies_evidence_ids` is an explicit, checked invariant (not prose)
tying `STRICT_TSR` support back to `evidence_availability` and `RETRIEVED_MEMORY`
condition support, and is exercised by both a passing case and a deliberately-broken
in-test case in `test_dataset_profiles.py`.

## The Strict-TSR evidence-ID requirement (the single biggest scientific constraint)

Per `phase3/contracts/EVALUATION_CONTRACT.md` section 3, Strict TSR is a literal
gold-evidence-memory-ID-membership check. A profile may only claim
`metric_support.STRICT_TSR` as `SUPPORTED` or `SUPPORTED_WITH_ADAPTER` if
`evidence_availability.status` is `AVAILABLE` or `PARTIAL` — never
`UNAVAILABLE`/`NOT_PROVIDED_BY_SOURCE`/`UNKNOWN`. This is enforced as code, not
convention, by `validation.py::check_strict_tsr_implies_evidence_ids`, and both LoCoMo
and LongMemEval's profiles satisfy it because their `task_records.jsonl` files were
directly observed (sample-based) to carry literal `evidence_memory_ids` lists of real
`memory_id` values. MSC and Conversation Chronicles correctly mark `STRICT_TSR`
`UNAVAILABLE` because their `task_records.jsonl` files are confirmed 0-byte — there is no
gold evidence ID to check membership against, for any record, by construction.

## Provenance/equivalence must be explicit, never inferred

Per `PHASE3_CLEAN_AGENT_FOUNDATION_SPEC.md` sections 8/9/12, lineage is computed by
walking **explicit** `parent_ids` edges, and equivalence is an **explicit**
`equivalent_to` relationship — never inferred from textual/content similarity. This
stage honored that rule literally: every profile's `lineage_availability` and
`equivalence_availability` judgments come from a whole-file grep for the literal field
names `parent_ids`/`equivalent_to` (plus `conflicts_with`/`superseded_by`) across all
four `memory_records.jsonl` files, which found **zero matches in every file** — no
dataset's current substrate has any derived memories or declared equivalence/conflict
edges yet, since Phase 1/2 only ever produces foundation memories (memories with a
`source`/`provenance` pointer and no parents, per `memory_schema.md` section 3.1). This
package explicitly flags, in the MSC and Conversation Chronicles profiles' notes, that
this is a **discrepancy worth surfacing**, not silently resolving: the capability matrix
frames MSC/ConvChron's provenance/lifecycle role as their "primary use case," but at the
raw-field level every dataset's current lineage/equivalence richness is identically zero
— the matrix's framing is about which datasets have session/repeated-interaction
structure well-suited for this machinery *in the future*, once a memory-creation policy
produces derived memories, not a claim that the data already exists today.

## What "adapter required" means

`SUPPORTED_WITH_ADAPTER` and each profile's `adapter_requirements` list **describe** a
future transformation (e.g. "a candidate-discovery + reranking + selection pipeline over
`memory_records.jsonl`") — they never implement, stub, or partially build one. Nothing
in `phase3/evaluation/datasets/*.py` performs retrieval, reranking, selection, or memory
creation of any kind.

## No data movement/modification, no LLM involvement

This package never writes to `data/raw/`, `data/processed/`, `data/metadata/`, or
`data/reports/` — every file under those paths was read strictly in read-only mode
during this stage's inspection, and `validation.py`'s functions open the profile/schema/
manifest files they consume in read-only mode only (`test_dataset_profiles.py` checks
this both statically, via source inspection, and at runtime, via a before/after file
hash comparison). No LLM, embeddings, or network call of any kind appears anywhere in
this package (checked by `test_datasets_modules_never_import_forbidden_libraries` and
`test_datasets_modules_make_no_network_calls`).

## Per-dataset summary

| Dataset | Task/workload layer | Gold evidence IDs | Gold answers | Provenance (source pointer) | Lineage/equivalence (explicit edges) | Strict TSR |
|---|---|---|---|---|---|---|
| LoCoMo | AVAILABLE (`task_records.jsonl`, 1986 tasks) | PARTIAL (3/300 sampled empty) | PARTIAL (65/300 sampled null, all `question_type="5"`) | AVAILABLE | NOT_PROVIDED_BY_SOURCE | SUPPORTED |
| LongMemEval | AVAILABLE (`task_records.jsonl`, 1000 tasks) | AVAILABLE (0/300 sampled empty) | AVAILABLE (0/300 sampled null) | AVAILABLE | NOT_PROVIDED_BY_SOURCE | SUPPORTED |
| MSC | NOT_PROVIDED_BY_SOURCE (`task_records.jsonl` is 0 bytes) | NOT_PROVIDED_BY_SOURCE | NOT_PROVIDED_BY_SOURCE | AVAILABLE | NOT_PROVIDED_BY_SOURCE | UNAVAILABLE |
| Conversation Chronicles | NOT_PROVIDED_BY_SOURCE (`task_records.jsonl` is 0 bytes) | NOT_PROVIDED_BY_SOURCE | NOT_PROVIDED_BY_SOURCE | AVAILABLE | NOT_PROVIDED_BY_SOURCE | UNAVAILABLE |

## Files in this package

- `README.md` — this file.
- `profile.schema.json` — the single common JSON Schema (draft 2020-12) all four
  profiles validate against.
- `profiles/{locomo,longmemeval,msc,conversation_chronicles}.json` — the four dataset
  profiles.
- `capability.py` — controlled vocabulary constants (`CAPABILITY_STATES`,
  `SUPPORT_STATES`, `METRIC_NAMES` (19), `CONDITION_NAMES` (6), `DATASET_IDS` (4)) and
  read-only profile-loading/lookup helpers.
- `validation.py` — schema validation plus every cross-field consistency invariant
  (pure functions; read-only where it touches the filesystem at all).

## `schema_version` convention

`"3.2-g.1"`, following the `"<phase>-<stage>.<revision>"` convention already established
by `phase3/evaluation/contracts/*.schema.json` (e.g. `"3.2-b.1"`) — matched here for
consistency rather than inventing a new scheme.

## `profile_status` convention

`DRAFT` / `REVIEWED` — all four shipped profiles are `REVIEWED` (they reflect this
stage's completed file-inspection pass, not a placeholder). A future revision to a
profile (e.g. after a real adapter is built and a metric moves from
`SUPPORTED_WITH_ADAPTER` to `SUPPORTED`) should be recorded by editing the relevant
profile and, if the change is substantive, updating `profile_status` back to `DRAFT`
until re-reviewed.

## Running the tests

```
pytest phase3/evaluation/tests/test_dataset_profiles.py -v
```

or, as part of the full suite:

```
pytest phase3/evaluation/tests/ -q
```

## What this stage does not decide

Whether/how a future workload/task layer is ever added for MSC or Conversation
Chronicles remains explicitly out of scope (deferred to a future capability-gap
analysis, per `DATASET_CAPABILITY_MATRIX.md` section 4) — this package documents the
current absence, it does not propose or schedule a fix. The exact retrieval/reranking/
selection implementation needed to move any `SUPPORTED_WITH_ADAPTER` metric/condition to
`SUPPORTED` is likewise not decided or built here.
