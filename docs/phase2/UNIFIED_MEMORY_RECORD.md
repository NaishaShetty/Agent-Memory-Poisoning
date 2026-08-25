# Unified Memory Record Specification (Phase 2.2)

`schema_version: "1.1.0"` (bumped from `"1.0.0"` by Phase 2.3's additive
temporal fields — see [`TEMPORAL_NORMALIZATION.md`](TEMPORAL_NORMALIZATION.md)).
Defined in [`preprocessing/unified_schema.py`](../../preprocessing/unified_schema.py);
mappers in [`preprocessing/unified_memory.py`](../../preprocessing/unified_memory.py);
cross-dataset validator in [`preprocessing/unified_validation.py`](../../preprocessing/unified_memory.py).

## What a Unified Memory Record (UMR) means

One UMR is one conversational turn from one of the four core memory
datasets (LoCoMo, LongMemEval, MSC, Conversation Chronicles), normalized
into a single common schema so downstream MAMBench components never need
to know which of the four source datasets a record came from in order to
read it. It answers **what a memory is**, not how it behaves over time —
see "Scope boundary" below.

A UMR is built entirely from **Phase 1's already-processed, already-frozen
`data/processed/<dataset>/memory_records.jsonl`** — never from raw source
files, and it never modifies that Phase 1 output. This is a strict
add-on layer: `data/processed/unified_memory/<dataset>/memory_records.jsonl`
sits alongside, not instead of, the existing Phase 1 output.

## Existing mechanisms reused, not reimplemented

Before writing any Phase 2.2 code, the following were inspected and
reused rather than duplicated:

- **`memory_id`** — Phase 1's `deterministic_id()`-based ID
  (`preprocessing/io_utils.py`) is reused verbatim. It is already
  deterministic, collision-resistant (sha256 over the ordered provenance
  tuple), reproducible, order-independent, and traceable to provenance —
  every property Phase 2.2 needs. Phase 1's own validation
  (`unique_memory_ids`, `no_cross_dataset_id_collision`) already proved
  this over the full 1,266,194-record corpus; Phase 2.2's own
  cross-dataset validator re-confirms it did not break anything.
- **`quality_status` / `data_quality`** — Phase 1's four-state
  classification (`preprocessing/quality.py`) is carried through
  unchanged; Phase 2.2 does not reclassify.
- **Trusted clean-memory exclusion** — Phase 2.1-R's
  `preprocessing/trusted_baseline.py:is_trusted_clean_memory()` is called
  directly, not reimplemented, for the `trusted_clean_memory` field.
- **Provenance-exception registry** — `data/metadata/longmemeval_provenance_exceptions.json`
  (Phase 2.1-R) is the input to the `admission_status` rule (see below);
  it was not duplicated or hardcoded into the mapper.

## Field-status model

Every UMR field that could plausibly be absent, uncertain, or
not-yet-computed carries an entry in the record's `field_status` map,
keyed by field name. A field has exactly one status, chosen from two
combined vocabularies:

**Positive origins** (the project's canonical terminology, Methodology.pdf
§2.4): `SOURCE_PROVIDED`, `BENCHMARK_GENERATED`, `INFERRED`, `MODEL_PREDICTED`
(never actually assigned in Phase 2.2 output — no runtime component has
run yet).

**Absence reasons** (introduced in Phase 2.2 because "missing" is not one
uniform fact): `NOT_AVAILABLE` (source doesn't provide it),
`NOT_APPLICABLE` (doesn't apply given the current phase),
`UNRESOLVED` (a genuine, tracked gap — reserved; no UMR field in the four
core datasets currently needs it), `NOT_EVALUATED` (a future-phase field
whose evidence doesn't exist yet — distinct from `NOT_APPLICABLE`: the
field *does* apply, it just hasn't run).

**Why a flat `field_status` map instead of `{value, origin}` objects per
field:** the task's own instructions allow this ("Do not require every
field to use a large nested object if that would make the implementation
impractical"). A flat map keeps every record's primary fields readable as
plain JSON values while keeping full origin semantics machine-readable
and queryable (`record["field_status"]["turn_id"]`). Richer detail
(*why* a field has a given origin) lives in this document and in the
mapper's per-dataset constants, not inline per record — inlining a
derivation-basis string on 1.27M records for a fact that only varies at
the per-dataset (not per-record) level would be pure repetition.

## Full field list

| Field | Type | Meaning | Typical origin |
|---|---|---|---|
| `schema_version` | str | `"1.0.0"` | constant |
| `memory_id` | str (24-hex) | reused Phase 1 deterministic ID | `BENCHMARK_GENERATED` |
| `content` | str | the utterance text, verbatim from Phase 1 | `SOURCE_PROVIDED` |
| `content_type` | str | always `"plain_text"` in Phase 2.2 (see below) | constant |
| `source_dataset` | str | `locomo`\|`longmemeval`\|`msc`\|`conversation_chronicles` | `SOURCE_PROVIDED` |
| `source_file`, `source_record_id` | str | source pointers | `SOURCE_PROVIDED` |
| `conversation_id` | str | project-level conversation grouping | `SOURCE_PROVIDED` (LoCoMo/MSC/CC) or `INFERRED` (LongMemEval — see below) |
| `session_id`, `turn_id` | str\|null | source-level grouping/position | `SOURCE_PROVIDED`, `BENCHMARK_GENERATED` if Phase 1 flagged `turn_id_derived_positional`, or `NOT_AVAILABLE` |
| `event_order` | int | 0-based position within `conversation_id` | `BENCHMARK_GENERATED` |
| `source_role` | str\|null | speaker/role label | `SOURCE_PROVIDED` or `NOT_AVAILABLE` |
| `source_timestamp` | str\|null | verbatim source timestamp/relative marker | `SOURCE_PROVIDED` or `NOT_AVAILABLE` |
| `timestamp_type` | `"absolute"`\|`"relative"`\|`"unavailable"` | temporal semantics of `source_timestamp` | `BENCHMARK_GENERATED` (classified by Phase 1) |
| `benchmark_timestamp` | str\|null | **Phase 2.3** (`SCHEMA_VERSION 1.1.0`): deterministic synthetic coordinate, assigned only when no real absolute time exists — see `TEMPORAL_NORMALIZATION.md` | `BENCHMARK_GENERATED` or `NOT_APPLICABLE` |
| `normalized_timestamp` | str\|null | **Phase 2.3**: real absolute time, deterministically reparsed from `source_timestamp` into ISO-8601 — `null` unless `temporal_provenance == "source_absolute"` | `INFERRED`, `NOT_AVAILABLE`, or `UNRESOLVED` |
| `temporal_provenance` | `"source_absolute"`\|`"source_relative"`\|`"benchmark_assigned"`\|`"unknown"` | **Phase 2.3**: which kind of real-world temporal claim this record supports — see `TEMPORAL_NORMALIZATION.md` | `INFERRED` |
| `quality_status`, `data_quality` | str, list | Phase 1 quality classification, unchanged | `INFERRED` |
| `admission_status` | `ADMISSIBLE`\|`FLAGGED`\|`QUARANTINED` | see below | `INFERRED` |
| `trusted_clean_memory` | bool | see below | `INFERRED` |
| `provenance` | dict | Phase 1's provenance dict + mapping timestamp | `BENCHMARK_GENERATED` |
| `derivation_parents` | `[]` in 2.2 | reserved, see below | `NOT_AVAILABLE` |
| `retrieval_history`, `propagation_history` | `[]` in 2.2 | reserved for Phase 3+ | `NOT_AVAILABLE` |
| `trust_score`, `security_state` | `null` in 2.2 | reserved for Phase 3+/5+ | `NOT_EVALUATED` |
| `poison_status` | `null` in 2.2 | reserved for Phase 4+ | `NOT_APPLICABLE` |
| `embedding`, `embedding_metadata` | `null` in 2.2 | reserved, deferred (see below) | `NOT_EVALUATED` |
| `dataset_scope` | `FULL_SOURCE_ACQUIRED`\|`DETERMINISTIC_SAMPLE` | see MSC/CC section | `BENCHMARK_GENERATED` |
| `dataset_version_or_revision` | str\|null | copied from `dataset_manifest.json` | `SOURCE_PROVIDED` or `NOT_AVAILABLE` |
| `field_status` | dict | per-field status map, see above | — |
| `metadata` | dict | Phase 1's dataset-specific extras, verbatim | `SOURCE_PROVIDED` |

`content_type` is always `"plain_text"` in Phase 2.2 because Phase 1
already flattened every source record to plain text (LoCoMo's multimodal
image turns keep their `img_url`/`blip_caption` fields in `metadata`,
not in `content`) — there is no structured-content case to represent yet
in the four core datasets as currently acquired; the field exists so a
future dataset or modality can be added without a schema-breaking change.

## `conversation_id` origin — dataset-specific, not uniform

`conversation_id` is `SOURCE_PROVIDED` for LoCoMo (`sample_id`), MSC
(`initial_data_id`), and Conversation Chronicles (`data_id`/episode id)
— all three map it from a native source identifier. **LongMemEval is
different and documented as such**: LongMemEval has no native
higher-level grouping above session, so Phase 1's own code sets
`conversation_id := session_id` as a documented rule
(`preprocessing/datasets/longmemeval.py`). Phase 2.2 marks this
`INFERRED`, not `SOURCE_PROVIDED` — it is a real, rule-based mapping, not
a fabricated value, but it is also not a verbatim copy of a distinctly
source-named field, so `SOURCE_PROVIDED` would overclaim. This is exactly
the kind of per-dataset distinction the schema is designed to preserve
rather than flatten away.

## `admission_status` — a general rule, not a hardcoded ID filter

```
QUARANTINED  if memory_id appears in data/metadata/longmemeval_provenance_exceptions.json
FLAGGED      elif quality_status == "valid_flagged"
ADMISSIBLE   otherwise
```

This rule is dataset-agnostic and never names LongMemEval's two specific
IDs — it checks membership in the provenance-exceptions registry, which
today happens to contain only those two IDs, but the rule itself would
apply identically if that registry were ever extended. Verified over the
full real corpus: `tests/test_unified_memory_real_data.py` and the
persisted `data/reports/phase2_2_unified_memory_validation_report.json`
both confirm exactly the two known LongMemEval `memory_id`s are
`QUARANTINED` and no others.

## Trusted clean-memory selection

`trusted_clean_memory` is computed by
`preprocessing.trusted_baseline.is_trusted_clean_memory()` (Phase
2.1-R, reused unchanged): `True` only if `quality_status` is
`valid`/`repaired` **and** the record is not in the provenance-exceptions
registry. A `QUARANTINED` record is *never* `trusted_clean_memory: true`
— enforced by `unified_validation.py`'s
`quarantined_records_never_trusted_clean` check (PASS across the full
real corpus) and by `tests/test_unified_memory_cross_dataset_logic.py`,
which synthetically constructs a violating record to confirm the checker
actually catches it.

## Missing-data policy in practice

No UMR field ever holds an empty string to mean "missing." Absence is
always represented as JSON `null` (for scalars) or `[]` (for the
explicitly-reserved list fields), *paired with* a `field_status` entry
explaining which of the four absence reasons applies. `security_state`,
`trust_score`, and `embedding` are `NOT_EVALUATED`, never a false-clean
default — this project does not set `trust_score = 1.0` or
`poison_status = "CLEAN"` merely because Phase 4/5 haven't run yet; both
are represented as their true current state (not evaluated / not
applicable), not as a fabricated positive claim.

## `derivation_parents` — empty is not proof of "root memory"

`derivation_parents` is `[]` for every record in Phase 2.2, with
`field_status: NOT_AVAILABLE` — meaning "no derivation data was captured
at ingestion," not "confirmed to have no parent." None of the four core
datasets natively encode turn-to-turn derivation relationships at this
granularity, so nothing is fabricated here; this is left for Phase 3's
lifecycle work to populate as real derivation events occur.

## Embeddings — explicitly deferred, not generated to fill a field

`embedding` and `embedding_metadata` are `null` (`NOT_EVALUATED`) for
every Phase 2.2 record. No embedding model was run. This is a deliberate
deferral, not an oversight: generating embeddings for 1.27M records
would be a real, non-trivial compute/config decision (model choice,
dimension, versioning) that belongs to whichever later phase actually
consumes them (the GNN's node features, Section 9.2 of Methodology.pdf),
not to the representation-definition phase. When embeddings are
eventually generated, `embedding_metadata` is where the model identity,
dimension, generation version, and provenance belong — the schema has
capacity for this now so that addition won't require a schema-breaking
change later.

## MSC-specific handling

No new licensing claim is made. `dataset_context.json`'s `license` field
(and `license_note`) are copied verbatim from the existing
`data/metadata/dataset_manifest.json` entry — the same
"unavailable / not explicitly published for the dataset itself..." string
Phase 1 already established. Source data is not redistributed; UMR
records contain only the same turn-level text already present in Phase
1's processed output.

## Conversation Chronicles-specific handling

Every Conversation Chronicles UMR record carries `dataset_scope:
"DETERMINISTIC_SAMPLE"`, and the dataset's companion
`dataset_context.json` carries an explicit `sample_disclosure` string
stating the raw/processed/sampled-out record counts and pointing to the
seed and caps in `config/pipeline_config.yaml`. No document anywhere in
Phase 2.2 describes the processed Conversation Chronicles records as the
entire source dataset.

## LoCoMo QA reconciliation — deliberately not embedded

**No UMR record for LoCoMo contains any QA field** (`answer`,
`adversarial_answer`, `canonical_answer`, `question`, etc.) —
`tests/test_unified_memory_real_data.py::test_locomo_umr_records_do_not_embed_qa_answer_fields`
enforces this over the real corpus. This is a deliberate design choice,
not an oversight: the task's own instruction is that "a memory record
may be valid even if an associated QA instance is not eligible for a
particular evaluation metric," and the cleanest way to guarantee that
distinction can never be silently lost is to keep the two layers in
physically separate files, joinable only by `(source_dataset,
conversation_id)`:

- Memory layer: `data/processed/unified_memory/locomo/memory_records.jsonl`
- QA layer: `data/processed/locomo/qa_reconciled.jsonl` (Phase 2.1-R,
  untouched by Phase 2.2 — re-verified by
  `test_locomo_qa_reconciliation_file_still_has_no_invented_canonical_answers`)

A downstream consumer who wants both joins them by `conversation_id ==
sample_id`; nothing in this design requires or encourages merging them
into one record type.

## Cross-dataset consistency

`preprocessing/unified_validation.py` streams all four datasets'
`memory_records.jsonl` (without holding full record content for more
than one dataset in memory at a time) and checks: schema conformance per
record, `memory_id` uniqueness within *and* across datasets,
`source_dataset` matches the file it was found in, `admission_status`/
`field_status` values are from the known vocabulary, no `QUARANTINED`
record is ever `trusted_clean_memory: true`, and total record counts
match Phase 1's processed output exactly. Run against the real corpus:
**PASS on every check, 1,266,194 total records, zero collisions** — see
`data/reports/phase2_2_unified_memory_validation_report.json` and
`docs/phase2/PHASE2_2_VALIDATION_REPORT.md`.

No statistical rebalancing is performed or intended — the four datasets'
natural size/composition differences (5,882 LoCoMo records vs. 822,762
Conversation Chronicles records) are preserved as-is.

## Scope boundary

Phase 2.2 defines **what a memory is**. It does not implement: temporal
normalization (source timestamps/relative ordering were preserved
verbatim in 2.2; `benchmark_timestamp` stayed always-null — see
`TEMPORAL_NORMALIZATION.md` for Phase 2.3, which fills this in under a
documented, deterministic, non-fabricating policy without touching
anything else in this document), Phase 3 lifecycle/graph construction,
Phase 4 attack/poisoned-memory generation
(no `poison_status` value is ever set), Phase 5+ instrumentation or
defenses (`security_state`/`trust_score` stay `NOT_EVALUATED`), or any
GNN/GLN training. `derivation_parents`, `retrieval_history`, and
`propagation_history` exist in the schema with real capacity for later
phases but are never populated with fabricated content here.
