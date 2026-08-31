# Dataset Capability Matrix

Status: **FROZEN DECISION** — the dataset set itself and each dataset's assigned role are
frozen for Phase 3.1. No dataset is added, removed, modified, or regenerated during this
stage. Datasets remain exactly as produced by the frozen Phase 1–2 pipeline (see
[PHASE3_RESTART_BOUNDARY.md](PHASE3_RESTART_BOUNDARY.md)).

## 1. Frozen dataset set

The four memory-foundation datasets are unchanged from Phase 1–2:

1. LoCoMo
2. LongMemEval
3. MSC
4. Conversation Chronicles

Additional datasets may only be considered later, after a formal capability-gap analysis —
not during 3.1, and not as an implicit side effect of any experiment.

## 2. Roles

### 2.1 LoCoMo
**Role:** Primary task-level memory and reasoning evaluation.
Provides task-oriented QA over multi-session conversational memory with designated gold
evidence, making it suitable for the full candidate-discovery → reranking → selection →
reasoning pipeline and for strict-TSR / evidence-equivalent comparability with historical
Phase 3 results.

### 2.2 LongMemEval
**Role:** Primary large-scale long-term memory and reasoning evaluation.
Larger-scale long-horizon memory QA; used for the same pipeline as LoCoMo but at greater
memory-store scale, stressing candidate-generation recall at higher corpus sizes.

### 2.3 MSC
**Role:** Lifecycle, provenance, multi-session memory, reuse, and longitudinal behavior.
MSC is **not** forced into the strict-TSR / task-QA framework unless and until a legitimate
task/workload layer exists for it. Its primary Phase 3 use is exercising the memory
lifecycle, provenance, and reuse machinery across sessions — not literal-answer evaluation.

### 2.4 Conversation Chronicles
**Role:** Longitudinal memory, lifecycle, provenance, and reuse validation.
Same constraint as MSC: not forced into the TSR framework without an appropriate
workload/task layer. Used to validate lifecycle transitions, derivation chains, and
provenance completeness over long-running conversational histories.

## 3. Matrix

| Property | LoCoMo | LongMemEval | MSC | Conversation Chronicles |
|---|---|---|---|---|
| Corpus size | Phase 2 UMR count (see `data/metadata/dataset_manifest.json`) | Phase 2 UMR count | Phase 2 UMR count | Phase 2 UMR count |
| Task count | Yes — QA tasks with gold evidence | Yes — QA tasks with gold evidence | No native task layer | No native task layer |
| Evidence availability | Gold evidence IDs present | Gold evidence IDs present | Not applicable (no task layer) | Not applicable (no task layer) |
| Answer availability | Gold answers present | Gold answers present | Not applicable | Not applicable |
| Temporal structure | Multi-session, timestamped | Multi-session, timestamped, long-horizon | Multi-session, timestamped | Multi-session, timestamped, longitudinal |
| Multi-hop structure | Present in subset of tasks | Present in subset of tasks | Not applicable | Not applicable |
| Repeated-interaction structure | Present | Present | Strong (primary strength) | Strong (primary strength) |
| Provenance suitability | Suitable | Suitable | Primary use case | Primary use case |
| Lifecycle suitability | Suitable | Suitable | Primary use case | Primary use case |
| Licensing / access status | Per Phase 2 `dataset_manifest.json` (CC BY-NC-4.0 per Phase 2 records) | Per Phase 2 manifest | Per Phase 2 manifest (license status recorded as unpublished/restricted in Phase 2) | Per Phase 2 manifest |
| Compatible metrics | Full memory-level + agent-level + strict/evidence-equivalent TSR | Full memory-level + agent-level + strict/evidence-equivalent TSR | Memory-level lifecycle/provenance/reuse metrics only, pending task layer | Memory-level lifecycle/provenance/reuse metrics only, pending task layer |
| Intended Phase 3 capability coverage | Primary QA/reasoning validation | Scale/long-horizon QA/reasoning validation | Lifecycle/provenance/derivation validation | Longitudinal lifecycle/provenance/derivation validation |

Exact corpus and task counts are not restated here to avoid drift from the authoritative
Phase 2 source — consult `data/metadata/dataset_manifest.json` and
`data/reports/phase2_*` for current figures; this matrix defines *roles and constraints*,
not a duplicate of Phase 2's own reporting.

## 4. What this document does not decide

Whether or how a future workload/task layer might be added on top of MSC or Conversation
Chronicles is explicitly deferred to a future capability-gap analysis — it is not a Phase 3.1
decision, and no such layer may be added as a side effect of unrelated experimentation.
