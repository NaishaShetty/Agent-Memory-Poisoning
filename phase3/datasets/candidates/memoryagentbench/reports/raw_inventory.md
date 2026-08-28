# MemoryAgentBench -- Raw Inventory Report

Scope: full-dataset scan (NOT a sample). Every one of the 4 HF parquet split files was read
in its entirety with `pandas.read_parquet` / `pyarrow`, and every row and every
question/answer pair inside every row was iterated. This is an exhaustive scan, not a
prefix/sample scan, because the entire dataset is small (146 context rows, 3671 QA pairs,
~75MB compressed / ~126MB uncompressed) -- well within a full-scan budget.

Source: `raw/hf_dataset/data/*.parquet`, HF dataset revision `7ea066982b140a19337e17e60d45d4076e042faf`.

## Top-level shape

Each parquet split has exactly 4 columns: `context` (string), `questions` (list[string]),
`answers` (list[list[string]] -- one list of acceptable answer-alias strings per question),
`metadata` (struct with fields: `demo`, `haystack_sessions`, `keypoints`, `previous_events`,
`qa_pair_ids`, `question_dates`, `question_ids`, `question_types`, `source`).

## Per-competency (split) counts

| Split (competency) | Context rows | Total QA pairs | Distinct `source_task_name` values |
|---|---:|---:|---|
| Accurate_Retrieval | 22 | 2000 | ruler_qa1_197K (1), ruler_qa2_421K (1), eventqa_full (5), eventqa_65536 (5), eventqa_131072 (5), longmemeval_s* (5) |
| Test_Time_Learning | 6 | 700 | recsys_redial_full, icl_banking77_5900shot_balance, icl_clinic150_7050shot_balance, icl_nlu_8296shot_balance, icl_trec_coarse_6600shot_balance, icl_trec_fine_6400shot_balance (1 row each) |
| Long_Range_Understanding | 110 | 171 | infbench_sum_eng_shots2 (100 rows, 1 question each), detective_qa (10 rows, 6-10 questions each) |
| Conflict_Resolution | 8 | 800 | factconsolidation_{mh,sh}_{6k,32k,64k,262k} (1 row each, 100 QA pairs each) |
| **Total** | **146** | **3671** | 22 distinct source_task_name values |

Session/context counts: there is no separate "session" concept distinct from the
context-row concept in this dataset -- each row's `context` string IS the full
injectable corpus for that row (already possibly containing multiple embedded
"Document N:" / "Dialogue N:" sub-units as plain text, not as separate structured
fields). `haystack_sessions` (LongMemEval rows only, 5 rows) is the one exception: it
is a nested list-of-lists-of-turns structure (session -> turn -> {content, role,
has_answer}) preserved verbatim.

## Null / empty / missing-field counts (full scan, all 146 rows / 3671 QA pairs)

- Null `context`: 0
- Empty-string `context`: 0
- Null `questions` or `answers` arrays: 0
- `questions`/`answers` length mismatch (structurally malformed): 0
- Null question strings: 0
- Empty-string question strings: 0
- Null answer-alias-lists (an entire `answers[i]` being null): 0
- Empty answer-alias-lists (`answers[i] == []`): 0
- Null or empty-string individual answer-alias strings: 0
- Missing `qa_pair_ids` (metadata field entirely null for a row): 0 (present in all 146 rows)
- `question_dates` / `question_ids` / `question_types`: populated ONLY on the 5
  `longmemeval_s*` rows (all other 141 rows have these three fields null at the
  metadata level) -- this is a genuine per-task-type field, not a missing-data defect.
- `demo` / `keypoints`: populated ONLY on the 110 Long_Range_Understanding rows
  (both `infbench_sum_eng_shots2` and `detective_qa` sub-datasets) -- null elsewhere.
- `previous_events`: populated ONLY on the 17 `eventqa_*` rows (Accurate_Retrieval
  split) -- null elsewhere.
- `haystack_sessions`: populated ONLY on the 5 `longmemeval_s*` rows -- null elsewhere.

**No malformed records were found anywhere in the dataset.** The exclusion manifest
(`manifests/exclusion_manifest.json`) is consequently empty (0 exclusions) -- this is
stated explicitly rather than left implicit, per the mission's requirement that "nothing
excluded" be an explicit, reconciled claim, not silence.

## Duplicate-ID counts

- `qa_pair_ids` are **NOT globally unique across the whole dataset**: of 3671 total
  `qa_pair_ids`, only 2231 are unique strings; 360 distinct ID strings each appear
  multiple times (up to 5x). This is because several source task families
  (`eventqa_full` / `eventqa_65536` / `eventqa_131072`; the 8
  `factconsolidation_{mh,sh}_*` variants) reuse the same question-index naming
  scheme (e.g. `eventqa_full_no0`) across multiple *separate context-length variant
  rows* that share the same underlying question set applied to different
  context-length cuts of the same source material. **Global uniqueness therefore
  requires the composite key (`split`, `row_index`, `qa_pair_id`)**, not
  `qa_pair_id` alone. This candidate's `normalized/task_records.jsonl` disambiguates
  every record via its `memory_ref` (split + row_index) plus `question_index_in_row`,
  so no two normalized task records collide even though `source_record_id` (`=
  qa_pair_id`) values repeat.
- Within any single `(split, row_index)` pair, all `qa_pair_ids` are unique (0
  duplicates observed in the full scan).
- No duplicate context-row IDs exist to check, because the source provides no
  context-row-level ID at all (see `reports/field_semantics.md`).

## Duplicate-content counts (exact string match only, no semantic similarity)

- `Conflict_Resolution`: rows 0-3 (`factconsolidation_mh_{6k,32k,64k,262k}`) and rows
  4-7 (`factconsolidation_sh_{6k,32k,64k,262k}`) have byte-identical `context` strings
  pairwise at matching lengths (row 0 == row 4, length 26157; row 1 == row 5, length
  136565; row 2 == row 6, length 273473; row 3 == row 7, length 1118123) -- i.e. the
  same underlying fact corpus is reused verbatim for both the multi-hop (`mh`) and
  single-hop (`sh`) question variants at each context-length tier. This is a
  deliberate upstream design choice (same facts, different reasoning-hop
  difficulty questions over them), not a data-quality defect. 4 duplicate-content
  pairs total.
- `Long_Range_Understanding`: row 5 and row 44 (both `infbench_sum_eng_shots2`) have
  byte-identical `context` strings (length 632149). Verified via direct string
  equality, not just length matching. Cause not independently confirmed from source
  documentation; flagged as `UNKNOWN` -- most likely the same book/document was
  sampled into two separate benchmark instances with different downstream summary
  targets. 1 duplicate-content pair.
- `Accurate_Retrieval` and `Test_Time_Learning`: 0 duplicate-content pairs found.
- Total: 5 duplicate-content pairs across the whole dataset (out of 146 rows). None
  were excluded -- duplication of upstream content is not, by the mission's rules, a
  valid exclusion reason.

## Task-type / temporal / role / tool fields found

- Task-type distribution: 4 competency splits, 22 distinct `source_task_name` values
  (listed in the per-competency table above), directly readable from `metadata.source`.
- Temporal fields: `question_dates` (LongMemEval rows only -- ISO-like date strings
  tied to individual questions). No dataset-wide timestamp field exists on the
  `context` documents themselves (e.g. no per-turn/per-document timestamp outside the
  LongMemEval `haystack_sessions` substructure, which itself carries no explicit
  timestamp field either -- only `content`, `role`, `has_answer` per turn).
- Role fields: `haystack_sessions` turns carry a `role` field (values observed:
  "user"/"assistant"-style conversational roles, consistent with LongMemEval's
  session-transcript format) -- this is the only place a conversational role field
  appears in this dataset; the `Test_Time_Learning` `recsys`/`icl_*` contexts embed
  "System:"/"User:" role markers as plain text inside the `context` string itself,
  not as a structured field.
- Tool fields: none found anywhere in the dataset (MemoryAgentBench is a
  read/QA/classification/summarization benchmark; it contains no tool-call or
  tool-result records).

## Sampling disclosure

This report is based on a full scan of all 146 context rows and all 3671 QA pairs
across all 4 parquet files -- not a sample. The only place a "sample" is invoked
anywhere in this candidate package is the field-shape description in
`reports/field_semantics.md`, which is grounded in inspecting representative rows from
each of the 22 distinct `source_task_name` values (at least one row per source, more
where only one existed), plus the aggregate full-scan statistics above.
