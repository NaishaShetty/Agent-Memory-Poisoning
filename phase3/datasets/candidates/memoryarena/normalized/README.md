# Normalized View — MemoryArena

Produced by `normalize.py` (deterministic, no network/model/randomness). Run:

```
python normalize.py <raw_dir> <out_dir>
```

## Files

- `task_chains.jsonl` — 701 records, one per source task-chain record across all 5
  configs (150 + 40 + 20 + 270 + 221 = 701). Each carries:
  `source_dataset`, `source_config`, `source_record_id` (the source's own `id`, verbatim,
  never a random UUID), `source_task_id` (`"<config>:<id>"`, a normalization-derived
  composite key built ONLY from source-provided values — recorded as derived, not
  presented as a source-native field), `source_session_id` (`NOT_PROVIDED_BY_SOURCE` —
  the source has no session concept), `source_revision` (both the GitHub commit hash and
  the HuggingFace dataset sha), `normalization_version`, `chain_length` (number of
  subtasks), `parent_ids`/`equivalent_to` (`NOT_PROVIDED_BY_SOURCE` — confirmed absent by
  full scan, not merely unchecked), and `chain_fields` (whatever chain-level fields the
  source provides for that config: `category` for bundled_shopping, `paper_name`+
  `backgrounds` for formal_reasoning_*, `base_person` for group_travel_planner, `{}` for
  progressive_search which has no chain-level fields beyond questions/answers).

- `subtasks.jsonl` — 4850 records, one per (chain, subtask-index) pair. Each carries all
  the same provenance fields as its parent chain PLUS `derived_subtask_key`
  (`"<config>:<id>:<index>"`, explicitly documented as normalization-derived since the
  source provides no separate subtask-level ID — this is never presented as a
  `source_record_id`), `subtask_index` and `chain_length` (encoding the positional
  interdependency ordering the source conveys only implicitly via list position),
  `question` and `answer` (verbatim from the source, answer's native type preserved
  per-config — dict for bundled_shopping, str for progressive_search/formal_reasoning_*,
  list for group_travel_planner; see `reports/field_semantics.md`), and
  `evidence_memory_ids`/`timestamp`/`parent_ids`/`equivalent_to`
  (`NOT_PROVIDED_BY_SOURCE` — this dataset has no separate memory-unit layer at all, see
  `reports/raw_inventory.md`).

## What is deliberately NOT collapsed into a flat QA record

Per the task brief's explicit instruction, MemoryArena's chain structure is preserved as
its own first-class concept (`task_chains.jsonl`) rather than being discarded once
`subtasks.jsonl` is built. A consumer that only reads `subtasks.jsonl` still has
`source_task_id`/`chain_length`/`subtask_index` on every row to reconstruct which subtasks
belong to the same interdependent chain and in what order — no information is lost by
having two files instead of one.

## What is NOT invented

- No gold evidence IDs are invented — `evidence_memory_ids` is `NOT_PROVIDED_BY_SOURCE`
  for every subtask, because the source provides none (see `field_semantics.md`).
- No `parent_ids`/`equivalent_to`/lineage edges are invented anywhere.
- No answer is reworded, coerced to a different type, or "cleaned" — the exact JSON value
  from the source is carried through as `answer`.
- Zero records were excluded (see `manifests/exclusion_manifest.json` — empty because the
  full scan found nothing genuinely malformed, not because exclusion was skipped).

## Determinism

Running `normalize.py` twice against the same `raw/` directory produces byte-identical
`task_chains.jsonl` and `subtasks.jsonl` (verified: both runs' SHA-256 digests match
exactly). This determinism is asserted by
`phase3/evaluation/tests/test_candidate_memoryarena.py`.
