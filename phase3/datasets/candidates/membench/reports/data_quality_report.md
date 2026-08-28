# MemBench Data Quality Report

> **Top-level statement:** The GitHub repository (https://github.com/import-myself/Membench,
> commit `f66d8d1028d3f68627d00f77a967b93fbb8694b6`) was found to bundle the **full** MemBench
> QA corpus directly -- 26,637 records across 19 category files and both the FirstAgent
> (Participation) and ThirdAgent (Observation) variants. This report covers that full,
> GitHub-hosted corpus (scanned in its entirety for the counts below). The Google Drive and
> Baidu mirrors documented in the mission and the README were **not independently re-verified**
> in this session, because they were not needed once the GitHub-bundled corpus was confirmed
> intact and internally consistent. See `source/source_audit.md` for the full acquisition
> narrative.

## Before / after counts

| Stage | Records |
|---|---|
| Full corpus, as scanned (before any processing) | 26,637 |
| Excluded (malformed) | 0 |
| Full corpus, after exclusion pass | 26,637 |
| Normalized into `normalized/membench_normalized.jsonl` (deterministic first-5-per-scenario sample, see preprocessing_manifest.json) | 275 |

No record was ever excluded. The gap between 26,637 (full corpus) and 275 (normalized sample)
is a **scope decision**, not data loss: the normalization step was run over a small
deterministic sample to keep candidate-preparation output size manageable, not because any
record failed validation. This is stated explicitly per the "preprocessing is not deletion"
rule.

## Missing-field summary (full corpus, exact counts)

| Field | Missing count | Missing rate |
|---|---|---|
| `QA.answer` | 0 / 26,637 | 0% |
| `QA.ground_truth` | 0 / 26,637 | 0% |
| `QA.target_step_id` (gold evidence) | 4 / 26,637 | 0.015% (all in `FirstAgent/highlevel_rec/movie`) |
| `QA.question` | 0 / 26,637 | 0% |
| `tid` (record id) | 0 / 26,637 | 0% |

## Duplicates

- **`tid` duplicates:** 0 across every (variant, category, scenario) file -- `tid` is a safe,
  stable, unique key within its scenario.
- **`qid` duplicates:** present in effectively every scenario (typically 499/500 or
  498-499/500 records share a duplicate `qid` value). `qid` is **not** a safe standalone
  identifier; see `reports/field_semantics.md`. Normalized `source_record_id` does not rely on
  `qid` alone.

## Relationship / lineage availability

MemBench's source data provides **no explicit parent/lineage or cross-record equivalence
relationships**. Every normalized record sets `parent_ids` and `equivalent_to` to
`NOT_PROVIDED_BY_SOURCE`. The only cross-referencing structure the source does provide is
`QA.target_step_id`, which is a **within-record** evidence pointer (transcript turn
location), not a cross-record relationship -- it is carried as `gold_evidence_step_ids` under
`evaluator_reference`, not under lineage.

## Ambiguous fields

- `qid`: appears to be a per-record question index (usually a small integer, frequently `0`)
  rather than a globally- or scenario-unique id. Treated as a label, not an id.
- `rel`/`attr`/`value` inline triples: present only on the specific turn(s) that establish the
  fact a question asks about; their exact generation semantics (hand-authored vs.
  template-generated) are `UNKNOWN` beyond what the generation scripts in
  `DialogueGeneration/` suggest (template-driven synthesis, per code inspection).
- `graphs.json` PII-shaped fields (ssn, passport_number, bank_account, driver_license): believed
  synthetic (see `reports/field_semantics.md`), not independently verified as such beyond
  contextual reasoning.

## Structural quality: clean

- 0 malformed records (100% of records have `tid`, `message_list`, and `QA` all present and
  correctly typed).
- 0 truncated/corrupted JSON files (all 19 category files across both variants parsed
  successfully with the standard library `json` module).
- Turn-shape variability (3 shapes across categories/variants) is real and source-driven, not
  a corruption artifact -- see `reports/field_semantics.md`.

## Known content caveat

The "noisy" category, the `MakeNoise/NoiseMeta` distractor pools, and the small
missing-evidence group in `highlevel_rec/movie` were all **preserved as-is** and **not**
"cleaned" -- per the mission's explicit instruction that MemBench's noisy/hard content is
intentional benchmark content, not defects to be removed.
