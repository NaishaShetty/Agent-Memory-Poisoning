# MemoryAgentBench -- Data Quality Report

## Before / after counts (full reconciliation, no silent data loss)

| Stage | Context rows | QA pairs |
|---|---:|---:|
| Input (raw HF parquet, all 4 splits) | 146 | 3671 |
| Excluded (malformed) | 0 | 0 |
| Output (`normalized/memory_records.jsonl` + `normalized/task_records.jsonl`) | 146 | 3671 |

**Zero records excluded.** See `manifests/exclusion_manifest.json` for the explicit
empty-exclusions confirmation with the same reconciliation numbers. Every input row
produced exactly one `memory_records.jsonl` entry; every input QA pair produced exactly
one `task_records.jsonl` entry. Counts verified programmatically in
`normalize.py`'s `counters` dict, printed at generation time and reproduced in
`manifests/preprocessing_manifest.json`.

## Missing answers

0 / 3671 QA pairs have a missing (null or empty-list) `answers[i]`. 0 / 3671 have a
null or empty-string member inside a non-empty `answers[i]` list. This is a
substantially cleaner answer-completeness profile than, e.g., LoCoMo's documented ~22%
null-answer rate for its adversarial question category (see
`phase3/evaluation/datasets/profiles/locomo.json`) -- MemoryAgentBench's QA pairs are
uniformly answerable in the sampled/scanned data; every row across all 4 splits
carries an answer for every question.

## Missing evidence

100% of QA pairs lack a source-native, memory-ID-level gold evidence pointer (no
`evidence_memory_ids`-equivalent field exists anywhere in the schema -- confirmed via
whole-dataset field-name scan, see `reports/field_semantics.md`). The dataset's design
does not need such a pointer for its own evaluation protocol (whole-context injection,
not retrieval-and-cite), so this is a structural property of the benchmark, not a
data-quality defect within it. The one partial exception is the 5 LongMemEval-sourced
rows, where `metadata.haystack_sessions` carries a per-turn `has_answer` boolean --
turn-level evidence-location signal exists there, but not as a resolvable memory ID
(no turn-level ID field exists to reference). This is documented, not silently
dropped: the raw `haystack_sessions` structure is fully preserved in
`normalized/memory_records.jsonl`'s `evaluator_only.haystack_sessions` field.

## Missing IDs

- Context/document-level: 100% of the 146 rows lack a source-native ID (no such field
  exists in the schema at all). Represented as `NOT_PROVIDED_BY_SOURCE` in
  `normalized/memory_records.jsonl.source_record_id`, with a `positional_reference`
  (split + row_index) supplied instead, explicitly labeled as derived/non-native.
- Question-level: 0% missing -- every QA pair has a `qa_pair_ids` value (100%
  populated across the full scan).

## Duplicate IDs

`qa_pair_ids` are duplicated **across rows** (not within a row): 360 of 2231 distinct
ID strings recur across multiple context-length/task-hop variant rows (up to 5x each;
see `reports/raw_inventory.md` for the full breakdown and cause). This is classified,
not silently deleted: every duplicate-ID occurrence is retained as its own distinct
`task_records.jsonl` entry, disambiguated by `memory_ref` (split + row_index) plus
`question_index_in_row`. No record was dropped because its ID collided with another
row's ID.

## Relationship availability

`parent_ids`, `equivalent_to`, `conflicts_with`, `superseded_by`: **0% availability**
-- confirmed absent via whole-dataset field-name scan (not inferred from silence).
Represented as `NOT_PROVIDED_BY_SOURCE` (never fabricated) in every normalized record.
This means MemoryAgentBench's `Conflict_Resolution` split -- despite being explicitly
designed to test conflict/update handling at the AGENT'S reasoning level (facts stated,
then later contradicted, within the same injected `context`) -- provides **no explicit
structural link** between an original fact statement and its contradicting update. The
conflict must be discovered by the agent (and, for evaluation purposes, by a human/LLM
judge) by reading the `context` text itself; it is not pre-annotated as a
`conflicts_with` relationship in the data. This is an important and non-obvious
limitation for anyone assuming `Conflict_Resolution` ships gold conflict-pair
annotations -- it does not.

## Ambiguous fields

- `metadata.source` values encode both task-family AND context-length/hop-difficulty
  variant in one string (e.g. `factconsolidation_mh_262k` = multi-hop, 262K-token
  variant) -- no separate structured fields for hop-difficulty or context-length exist;
  a consumer must parse the string if it wants those as independent facets. Documented
  here rather than split apart speculatively (no separator convention is guaranteed
  stable across all 22 source names, e.g. `longmemeval_s*` doesn't follow the same
  `_<length>` suffix convention as `eventqa_*`/`factconsolidation_*`).
- `question_dates`' agent-visible-vs-evaluator-only classification is a judgment call
  (see `reports/field_semantics.md`) -- flagged, not silently assumed either way.
- The `Long_Range_Understanding` row-5/row-44 exact-content duplicate's cause is
  `UNKNOWN` (not independently confirmed from any changelog or source documentation).

## Summary

This is, in the full scan performed, an unusually clean dataset by MAMBench's existing
standards: zero malformed records, zero missing answers, zero null/empty questions.
Its principal audit-worthy properties are not "dirty data" but **structural absences by
design** (no context-level ID, no evidence-memory-ID field, no lineage/relationship
fields anywhere) and **one documented instability axis** (the HF dataset card's own
changelog: `qa_pair_ids` renamed from `uuid` and bug-fixed across 2025 revisions,
`keypoints` added mid-stream) -- both are called out explicitly rather than smoothed
over.
