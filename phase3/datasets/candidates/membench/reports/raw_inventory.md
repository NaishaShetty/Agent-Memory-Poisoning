# MemBench Raw Inventory

Scope: this inventory covers a **full scan of the actual bundled corpus** obtained from the
GitHub repository (commit `f66d8d1028d3f68627d00f77a967b93fbb8694b6`), i.e. every record in
every `MemData/{FirstAgent,ThirdAgent}/*.json` file was walked and counted directly (not
estimated, not sampled) — these are exact counts. It does NOT cover the Google Drive/Baidu
mirrors independently (see `source/source_audit.md` and the top-level README for why that
was not necessary here).

## Total record count

**26,637** QA-annotated conversation records across both variants and all 19 category files.

## Per (variant, category, scenario) breakdown

| variant | category | scenario | records | missing_answer | missing_ground_truth | missing_evidence (target_step_id) | duplicate tid | duplicate qid (within scenario) | malformed |
|---|---|---|---|---|---|---|---|---|---|
| FirstAgent | RecMultiSession | multi_agent | 500 | 0 | 0 | 0 | 0 | 499 | 0 |
| FirstAgent | aggregative | events | 500 | 0 | 0 | 0 | 0 | 499 | 0 |
| FirstAgent | aggregative | roles | 500 | 0 | 0 | 0 | 0 | 499 | 0 |
| FirstAgent | comparative | events | 500 | 0 | 0 | 0 | 0 | 499 | 0 |
| FirstAgent | comparative | roles | 500 | 0 | 0 | 0 | 0 | 499 | 0 |
| FirstAgent | conditional | events | 500 | 0 | 0 | 0 | 0 | 499 | 0 |
| FirstAgent | conditional | roles | 500 | 0 | 0 | 0 | 0 | 499 | 0 |
| FirstAgent | highlevel | book | 500 | 0 | 0 | 0 | 0 | 499 | 0 |
| FirstAgent | highlevel | food | 500 | 0 | 0 | 0 | 0 | 499 | 0 |
| FirstAgent | highlevel | movie | 500 | 0 | 0 | 0 | 0 | 499 | 0 |
| FirstAgent | highlevel_rec | book | 500 | 0 | 0 | 0 | 0 | 499 | 0 |
| FirstAgent | highlevel_rec | food | 500 | 0 | 0 | 0 | 0 | 499 | 0 |
| FirstAgent | highlevel_rec | movie | 500 | 0 | 0 | **4** | 0 | 499 | 0 |
| FirstAgent | knowledge_update | events | 500 | 0 | 0 | 0 | 0 | 499 | 0 |
| FirstAgent | knowledge_update | roles | 500 | 0 | 0 | 0 | 0 | 499 | 0 |
| FirstAgent | lowlevel_rec | book | 500 | 0 | 0 | 0 | 0 | 499 | 0 |
| FirstAgent | lowlevel_rec | food | 500 | 0 | 0 | 0 | 0 | 499 | 0 |
| FirstAgent | lowlevel_rec | movie | 500 | 0 | 0 | 0 | 0 | 499 | 0 |
| FirstAgent | noisy | events | 500 | 0 | 0 | 0 | 0 | 499 | 0 |
| FirstAgent | noisy | roles | 500 | 0 | 0 | 0 | 0 | 499 | 0 |
| FirstAgent | post_processing | events | 500 | 0 | 0 | 0 | 0 | 499 | 0 |
| FirstAgent | post_processing | roles | 500 | 0 | 0 | 0 | 0 | 499 | 0 |
| FirstAgent | simple | events | 500 | 0 | 0 | 0 | 0 | 499 | 0 |
| FirstAgent | simple | roles | 500 | 0 | 0 | 0 | 0 | 499 | 0 |
| ThirdAgent | aggregative | events | 456 | 0 | 0 | 0 | 0 | 455 | 0 |
| ThirdAgent | aggregative | hybrid | 431 | 0 | 0 | 0 | 0 | 430 | 0 |
| ThirdAgent | aggregative | roles | 279 | 0 | 0 | 0 | 0 | 278 | 0 |
| ThirdAgent | comparative | events | 500 | 0 | 0 | 0 | 0 | 499 | 0 |
| ThirdAgent | comparative | hybrid | 500 | 0 | 0 | 0 | 0 | 499 | 0 |
| ThirdAgent | comparative | roles | 500 | 0 | 0 | 0 | 0 | 499 | 0 |
| ThirdAgent | conditional | events | 500 | 0 | 0 | 0 | 0 | 499 | 0 |
| ThirdAgent | conditional | hybrid | 500 | 0 | 0 | 0 | 0 | 499 | 0 |
| ThirdAgent | conditional | items | 500 | 0 | 0 | 0 | 0 | 499 | 0 |
| ThirdAgent | conditional | places | 500 | 0 | 0 | 0 | 0 | 499 | 0 |
| ThirdAgent | conditional | roles | 500 | 0 | 0 | 0 | 0 | 499 | 0 |
| ThirdAgent | highlevel | book | 500 | 0 | 0 | 0 | 0 | 499 | 0 |
| ThirdAgent | highlevel | food | 500 | 0 | 0 | 0 | 0 | 499 | 0 |
| ThirdAgent | highlevel | movie | 500 | 0 | 0 | 0 | 0 | 499 | 0 |
| ThirdAgent | knowledge_update | events | 499 | 0 | 0 | 0 | 0 | 498 | 0 |
| ThirdAgent | knowledge_update | roles | 500 | 0 | 0 | 0 | 0 | 499 | 0 |
| ThirdAgent | noisy | events | 500 | 0 | 0 | 0 | 0 | 499 | 0 |
| ThirdAgent | noisy | hybrid | 500 | 0 | 0 | 0 | 0 | 499 | 0 |
| ThirdAgent | noisy | items | 500 | 0 | 0 | 0 | 0 | 499 | 0 |
| ThirdAgent | noisy | places | 500 | 0 | 0 | 0 | 0 | 499 | 0 |
| ThirdAgent | noisy | roles | 500 | 0 | 0 | 0 | 0 | 499 | 0 |
| ThirdAgent | post_processing | events | 500 | 0 | 0 | 0 | 0 | 499 | 0 |
| ThirdAgent | post_processing | hybrid | 500 | 0 | 0 | 0 | 0 | 499 | 0 |
| ThirdAgent | post_processing | items | 236 | 0 | 0 | 0 | 0 | 235 | 0 |
| ThirdAgent | post_processing | places | 236 | 0 | 0 | 0 | 0 | 235 | 0 |
| ThirdAgent | post_processing | roles | 500 | 0 | 0 | 0 | 0 | 499 | 0 |
| ThirdAgent | simple | events | 500 | 0 | 0 | 0 | 0 | 499 | 0 |
| ThirdAgent | simple | hybrid | 500 | 0 | 0 | 0 | 0 | 499 | 0 |
| ThirdAgent | simple | items | 500 | 0 | 0 | 0 | 0 | 499 | 0 |
| ThirdAgent | simple | places | 500 | 0 | 0 | 0 | 0 | 499 | 0 |
| ThirdAgent | simple | roles | 500 | 0 | 0 | 0 | 0 | 499 | 0 |

Raw machine-readable form: `manifests/full_corpus_inventory_scan.json`.

## Interpretation notes

- **Record identity:** `tid` is unique within every (variant, category, scenario) file --
  zero duplicates observed anywhere. `qid` (the QA's own id) is **not** a reliable unique key
  on its own -- it duplicates across nearly every record in nearly every scenario (e.g. 499
  duplicate qids among 500 records is the norm, meaning qid resets to a small value, most
  commonly 0, per record rather than incrementing globally). Normalized `source_record_id`
  therefore keys off `tid` (verified unique) plus `scenario`/`category`/`variant`, with `qid`
  carried along for completeness but not relied on for uniqueness.
- **Answer / ground-truth coverage:** 100% (26,637 / 26,637) of records have both a free-text
  `answer` and a multiple-choice `ground_truth` letter. Never missing anywhere in the corpus.
- **Evidence coverage:** 26,633 / 26,637 records (99.985%) carry a non-empty
  `target_step_id` gold-evidence pointer (list of `[session_index, turn_index]` pairs into the
  transcript). The 4 exceptions are all in `FirstAgent/highlevel_rec/movie`. These are NOT
  malformed records (every other required field is present and well-typed) -- they are
  legitimately QA items whose source data provides no evidence localization, most plausibly
  because the high-level recommendation questions in that scenario intentionally require
  synthesis across the whole conversation rather than a pinpoint-able turn. Documented here,
  not in the exclusion manifest (nothing was excluded).
- **Malformed records:** 0 across the entire corpus (no record missing `tid`, `message_list`,
  or `QA`, and no non-dict top-level record).
- **Task-type / category distribution** matches the taxonomy documented in the README and
  confirmed by the generation source (`DialogueGeneration/`, `DialogueGenerationCouple/`):
  simple, noisy, knowledge_update, aggregative, comparative, conditional, highlevel,
  highlevel_rec (high-level + recommendation), lowlevel_rec, post_processing, and the
  multi-session `RecMultiSession` category.
- **Turn-shape variability (see `reports/field_semantics.md` for full detail):** three distinct
  turn shapes are used across categories:
  1. FirstAgent dialogue turns (`sid`/`user_message`/`assistant_message`), nested per session.
  2. FirstAgent recommendation/multi-session turns (`mid`/`user`/`assistant`), nested per
     session.
  3. ThirdAgent observation turns (`mid`/`message`, no dialogue split), flat (no session
     nesting provided by the source).
  All three are normalized into one common turn shape in `normalized/` (see
  `reports/field_semantics.md`), with unused slots marked `NOT_PROVIDED_BY_SOURCE`.
- **This report's counts are exact, full-corpus counts**, not sample-based estimates --
  distinct from the *normalized/* directory, which (see below) normalizes only a small
  deterministic sample for size-management reasons.
