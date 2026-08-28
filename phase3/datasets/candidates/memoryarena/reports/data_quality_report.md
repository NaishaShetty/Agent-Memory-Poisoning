# Data Quality Report — MemoryArena

Full scan (all 701 task-chain records, all 4850 subtasks), no sampling. See
`reports/raw_inventory.md` and `reports/field_semantics.md` for the underlying detail this
report summarizes.

## Before / after counts

| Stage | Task-chain records | Subtask records |
|---|---|---|
| Raw (source JSONL, all 5 configs) | 701 | 4850 |
| Normalized (`normalized/task_chains.jsonl`, `normalized/subtasks.jsonl`) | 701 | 4850 |
| Excluded | 0 | 0 |

**No data loss occurred at any stage.** Every source record and every source subtask has
exactly one corresponding normalized record.

## Exclusions and reasons

None. See `manifests/exclusion_manifest.json` — zero records met the exclusion criteria
(genuinely malformed: unparseable JSON, missing required field, length mismatch). This is
recorded explicitly as a finding, not an omission.

## Missing answers

Zero. Every one of the 4850 subtasks across all 701 records has a non-null,
non-empty-string `answers[i]` entry (full scan). This is a materially different
availability profile from LoCoMo, whose sampled task records had a 65/300 null-answer rate
(all `question_type=5`, adversarial/unanswerable questions) — MemoryArena's five configs
have no analogous "intentionally unanswerable" category observed anywhere in this scan.

## Missing evidence

100% missing, by design of the source (not a defect). MemoryArena provides no separate
`evidence_memory_ids`-style pointer at all — see `reports/field_semantics.md`. The
`backgrounds` field (formal_reasoning_math/phys only) and `base_person` field
(group_travel_planner only) are the closest analogues to "evidence context," but neither
is an ID pointing at a separately identified memory unit; both are recorded as
`AGENT-VISIBLE context`, not `evidence`, in the field semantics report. This is reported
as `NOT_PROVIDED_BY_SOURCE` for evidence availability, not as a data-quality defect to be
patched over.

## Missing IDs

None. `id` is present and required in 701/701 records (full scan); no null/missing `id`
observed in any config.

## Duplicates

None. 0 duplicate `id` values found in any of the 5 configs (full scan; see
`raw_inventory.md`'s per-config duplicate-ID counts). No duplicate subtask content was
checked for (content-similarity deduplication was explicitly out of scope, per the task
brief's instruction not to infer relationships from textual similarity).

## Relationship / interdependency availability

- **Chain grouping (which subtasks belong to the same interdependent task):** AVAILABLE —
  every subtask carries its parent chain's `source_record_id`/`source_task_id` plus its
  own `subtask_index` and `chain_length`.
- **Explicit machine-readable interdependency edges (e.g. "subtask 3 depends on subtask
  1's answer"):** NOT_PROVIDED_BY_SOURCE — the source conveys interdependency only through
  list position and (for formal_reasoning_*) shared `paper_name`, never an explicit edge
  field. See `raw_inventory.md`'s "Task interdependency structure" section for a
  per-config account of how the interdependency actually manifests.
- **Cross-record relationships (e.g. two different `id`s sharing a paper or scenario):**
  PARTIAL for `formal_reasoning_math`/`formal_reasoning_phys` only, via the `paper_name`
  field (some `paper_name` values carry a `_part_N` suffix indicating a shared source
  paper split across multiple `id`s) — NOT_PROVIDED_BY_SOURCE for the other three configs.
- **Memory-level relationships (`parent_ids`/`equivalent_to`/`conflicts_with`/
  `superseded_by`):** NOT_PROVIDED_BY_SOURCE across all 701 records (full scan, not a
  grep sample) — consistent with this dataset having no separate memory-unit layer at all.

## Ambiguous fields

- `group_travel_planner.base_person.daily_plans`: could function as agent-visible
  background context OR as an evaluator-side gold reference for judging joiner-plan
  consistency — flagged in `field_semantics.md` as requiring an explicit policy decision,
  not resolved here.
- `progressive_search`/`bundled_shopping` README-illustrated answer shapes do not match
  the actually-downloaded data's answer shapes (they are swapped between the two
  configs) — flagged as an observed discrepancy in `field_semantics.md`, not silently
  corrected in the normalized output (the normalized output preserves the file's actual
  content, not the README's description of it).
- Whether `id` values are stable across future HuggingFace dataset revisions is UNKNOWN
  (only one snapshot inspected).

## Summary

This is an unusually clean source: full-scan inspection of all 701 records and 4850
subtasks found zero malformed records, zero missing answers, zero missing IDs, and zero
duplicates. The main data-quality caveat is structural rather than a defect: MemoryArena
provides no memory-unit layer, no evidence-ID pointers, and no explicit interdependency
edges — all of which are core primitives the existing MAMBench metric suite (Recall@K,
Strict-TSR, evidence precision/recall, lineage/equivalence diagnostics) was built to
consume. See `profile/mambench_compatibility.json` for the resulting per-metric
SUPPORTED/UNDEFINED/NOT_ATTEMPTABLE assessment.
