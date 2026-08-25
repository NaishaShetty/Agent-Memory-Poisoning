# Temporal Normalization Specification (Phase 2.3)

`preprocessing.temporal.NORMALIZATION_POLICY_VERSION = "2.3.0"`. Policy
and parsing logic: [`preprocessing/temporal.py`](../../preprocessing/temporal.py).
Wired into the mapper: [`preprocessing/unified_memory.py`](../../preprocessing/unified_memory.py)
(`map_memory_record()`). Consistency checks:
[`preprocessing/temporal_validation.py`](../../preprocessing/temporal_validation.py).
UMR schema bumped to `SCHEMA_VERSION = "1.1.0"` in
[`preprocessing/unified_schema.py`](../../preprocessing/unified_schema.py).

## Why temporal normalization is necessary

The four core datasets represent "when" in four different, mutually
incompatible ways (see the mapping table below): two give a real
absolute timestamp per session in a free-text, non-ISO-8601 format; two
give only a natural-language relative gap between sessions, or nothing
at all for the first session. Later MAMBench work explicitly named in
the Phase 2.3 brief — propagation analysis, sleeper-poison dwell time,
attack-origin reconstruction, chronological event analysis, memory
lifecycle analysis — all need to reason about "when" consistently across
these four representations. Phase 2.2 deliberately deferred this
("`benchmark_timestamp` always null in 2.2... Phase 2.3's job, never
fabricated here" — see `UNIFIED_MEMORY_RECORD.md`); this document and
the code it describes fulfil that deferral.

## What was extended, not redesigned

Phase 2.2's Unified Memory Record already reserved exactly the right
slot for this (`benchmark_timestamp`, `timestamp_type`, `source_timestamp`)
and already had the field-status/provenance vocabulary Phase 2.3 needs
(`SOURCE_PROVIDED` / `BENCHMARK_GENERATED` / `INFERRED`, and the four
absence reasons). Phase 2.3 does **not** introduce a new vocabulary or a
parallel record type. It:

1. Populates the previously-always-null `benchmark_timestamp` under a
   documented, deterministic policy (never before Phase 2.3).
2. Adds two new UMR fields: `normalized_timestamp` (a real, source-parsed
   absolute time, or `null`) and `temporal_provenance` (one of four
   values — see below).
3. Bumps `SCHEMA_VERSION` from `"1.0.0"` to `"1.1.0"` to reflect this
   additive change (no 1.0.0 field was removed, renamed, or
   reinterpreted).

## The distinction that must never be collapsed

Two different questions are involved, and this project answers each with
its own field rather than forcing one flat tag to carry both:

1. **"What is the best real-world temporal claim this record supports?"**
   — the record-level `temporal_provenance` field, one of
   `VALID_TEMPORAL_PROVENANCE`.
2. **"Where did each individual temporal value on this record come
   from?"** — the existing, more granular `field_status["normalized_timestamp"]`
   and `field_status["benchmark_timestamp"]` entries, using
   `unified_schema.py`'s existing origin vocabulary
   (`SOURCE_PROVIDED`/`BENCHMARK_GENERATED`/`INFERRED`/absence reasons).

| `temporal_provenance` | Meaning | `normalized_timestamp` | `benchmark_timestamp` |
|---|---|---|---|
| `source_absolute` | The source dataset gave a real, deterministically-parsed absolute timestamp | real ISO-8601 value (`field_status: INFERRED`) | `null` (`field_status: NOT_APPLICABLE` — not assigned, unnecessary once a real value exists) |
| `source_relative` | The source gives ordering only (a relative gap description, or just session/turn position) — no calendar date is ever derived from it | `null` (`field_status: NOT_AVAILABLE`, or `UNRESOLVED` if an absolute claim existed but failed to parse) | assigned from the deterministic policy below (`field_status: BENCHMARK_GENERATED`), so later phases have *a* common coordinate — this does **not** promote the record to `source_absolute` |
| `unknown` | Reserved, unused by the four core datasets | `null` | `null` or assigned, same rule as above |

`benchmark_assigned` is declared in `VALID_TEMPORAL_PROVENANCE` (and is
the value `field_status["benchmark_timestamp"]` effectively documents at
the per-field level, as `BENCHMARK_GENERATED`) but is not additionally
used as the record-level `temporal_provenance` tag: a record whose only
source signal is relative ordering stays classified `source_relative`
at the record level even after a `benchmark_timestamp` is layered on top
— the layering is visible in `field_status`, not by silently upgrading
(or renaming) the record's provenance classification. Both
`benchmark_assigned` and `unknown` are reserved-but-currently-unused at
the record-level-tag position, for the same reason
`ABSENCE_UNRESOLVED` is reserved-but-unused in `unified_schema.py`: a
future dataset or a genuinely inexplicable gap should have somewhere to
go without inventing a new enum value under time pressure.

**`event_order` / `turn_id` / `session_id` are not re-derived here.**
They are Phase 1/2.2 fields and already constitute reliable
source-relative ordering (matching this project's own "turn_index /
message_index / event_order" definition of source-relative ordering) —
Phase 2.3 reuses them as the ordering key for `benchmark_timestamp`
rather than reinventing an ordering mechanism.

## Dataset-specific temporal mapping table

| Dataset | Source temporal signal | Type | Resolution | Normalization | Provenance (typical) |
|---|---|---|---|---|---|
| LoCoMo | `conversation.session_{n}_date_time` (per-session) | absolute | minute | Deterministically reparsed from `'1:56 pm on 8 May, 2023'` into ISO-8601 `normalized_timestamp` | `source_absolute` |
| LongMemEval | `haystack_dates[i]` aligned by index to `haystack_session_ids[i]` (per-session) | absolute | minute | Deterministically reparsed from `'2023/07/07 (Fri) 14:05'` into ISO-8601 `normalized_timestamp` (weekday not cross-checked) | `source_absolute` |
| MSC | `previous_dialogs[-1].{time_num,time_unit,time_back}` (inter-session gap; absent for session 1) | relative (session ≥ 2) / unavailable (session 1) | none (no absolute resolution) | Never converted to a calendar date; `benchmark_timestamp` assigned from `(session_ordinal, event_order)` | `source_relative` |
| Conversation Chronicles | `time_interval[session_index]` (per-session free text, `'Start'` for session 1) | relative | none | Never converted to a calendar date; `benchmark_timestamp` assigned from `(session_ordinal, event_order)` | `source_relative` |

The full, machine-readable version of this table (including
trustworthiness, duplicate/missing/invalid/conflict handling per
dataset) is `preprocessing.temporal.TEMPORAL_POLICY` and is also written
into every dataset's `dataset_context.json` companion file under
`temporal_policy`, exactly as Phase 2.2 already did for
`conversation_id_origin` and `dataset_scope`.

## When `benchmark_timestamp` is (and is not) assigned

`benchmark_timestamp` is assigned **only** when no real absolute time is
available for that record — i.e. `temporal_provenance != source_absolute`.
When a record already has a real, successfully-parsed absolute
`normalized_timestamp`, `benchmark_timestamp` stays `null`
(`field_status: NOT_APPLICABLE`) — assigning a synthetic coordinate on
top of a trustworthy real one would be benchmark-assignment performed
when it is not genuinely necessary, which the Phase 2.3 brief explicitly
warns against.

When it is assigned, the formula is:

```
offset_seconds = session_ordinal * 100_000 + event_order
benchmark_timestamp = 1970-01-01T00:00:00 + offset_seconds seconds
```

- `session_ordinal` is the integer `N` in a `session_N`-shaped
  `session_id` (LoCoMo, MSC, Conversation Chronicles), or `0` when the
  id doesn't follow that shape (LongMemEval — safe because
  `conversation_id == session_id` there, so no cross-session ordering is
  ever needed).
- The stride (100,000) exceeds the largest `event_order` observed in the
  acquired corpus (688, in LoCoMo) with a wide safety margin, so
  within-session ordering (`event_order`) can never spill into the next
  session's bucket.
- `(session_ordinal, event_order)` rather than `event_order` alone is
  used because `event_order`'s scope is **not** uniform across datasets:
  it is conversation-wide in LoCoMo/Conversation Chronicles but resets
  to `0` at the start of every session in MSC
  (`preprocessing/datasets/msc.py:make_turn_records`). Using
  `event_order` alone would silently collide MSC's sessions.
- The anchor (`1970-01-01`, the Unix epoch) is a deliberate, universally
  recognizable "this is not a real date" sentinel: every real timestamp
  in all four datasets is dated 2022 or later (see
  `data/reports/*_inspection.json` → `temporal_information.sample_values`).
  The 1970 anchor is a human-legibility safeguard; the authoritative
  machine-readable signal that a value is synthetic is always the
  `temporal_provenance` field (see the note below the table).

> **Benchmark-assigned timestamps are analytical constructs created by
> MAMBench and must not be interpreted as source-observed timestamps.**
> Always check `temporal_provenance` (and, for the value's field-level
> origin, `field_status["benchmark_timestamp"] == "BENCHMARK_GENERATED"`)
> before using `benchmark_timestamp` for anything — never infer realism
> from the value's format alone.

Note on the table above: because a record with a real absolute time
never gets a `benchmark_timestamp`, and every `benchmark_timestamp`
value is paired with `temporal_provenance` in `{source_relative,
unknown}` (never `source_absolute`), a consumer that only reads
`temporal_provenance` already has the authoritative signal — the 1970
anchor is a secondary, human-legibility safeguard, not the sole guard.

## Missing, invalid, and conflicting temporal information

- **Missing** (`timestamp_type == "unavailable"`, e.g. MSC session 1):
  `normalized_timestamp` stays `null`
  (`field_status: NOT_AVAILABLE`) — nothing is invented. A
  `benchmark_timestamp` is still assigned (see policy above), because
  `event_order`/`session_id` ordering is genuinely available even when
  no relative-gap *description* is.
- **Invalid** (a dataset whose `timestamp_type` is `"absolute"` but whose
  `source_timestamp` string does not match that dataset's documented
  format): detected via a strict, fully-anchored regex per dataset
  (`preprocessing/temporal.py:_LOCOMO_RE` / `_LONGMEMEVAL_RE`), flagged
  in the record's own `data_quality` list as
  `invalid_source_timestamp_format`, and `normalized_timestamp` is left
  `null` with `field_status: UNRESOLVED` (a genuine, tracked gap — not
  explained by `NOT_AVAILABLE`/`NOT_APPLICABLE`, matching
  `unified_schema.py`'s own definition of `UNRESOLVED`). Never
  silently repaired or accepted. **Not observed in the acquired
  corpus** — all 5,882 LoCoMo and 210,365 LongMemEval `source_timestamp`
  values parse cleanly (verified by
  `preprocessing/temporal_validation.py`'s real-corpus run) — but the
  code path is exercised by
  `tests/test_temporal_normalization.py::test_malformed_absolute_timestamp_is_detected_and_flagged`
  against a synthetic fixture.
- **Conflicting signals**: none of the four core datasets provide two
  disagreeing temporal signals for the same record (each record has at
  most one temporal field: LoCoMo/LongMemEval have exactly one absolute
  timestamp source; MSC/Conversation Chronicles have exactly one
  relative-gap source). `TEMPORAL_POLICY[<dataset>]["conflicting_signals_observed"]`
  is `False` for all four, verified against the real corpus. The
  conflict-detection concept (documented, currently unexercised, exactly
  like `ABSENCE_UNRESOLVED` in Phase 2.2) is reserved for a future
  dataset that might provide two disagreeing signals.

## Duplicate timestamps

LoCoMo and LongMemEval assign one timestamp **per session**, shared by
every turn in that session — duplicates are the expected, common case
(verified counts: 5,611 duplicate `source_timestamp` occurrences in
LoCoMo, 194,424 in LongMemEval, from
`data/reports/phase2_3_temporal_validation_report.json`). Phase 2.3
never perturbs a timestamp to make it artificially unique;
`event_order` (already a required, always-present UMR field) is the
documented secondary ordering key for records that share a
`normalized_timestamp`.

## Determinism

Every function in `preprocessing/temporal.py` is a pure function of its
record-level inputs (`source_dataset`, `timestamp_type`,
`source_timestamp`, `session_id`, `event_order`) and the fixed module
constants (`_SYNTHETIC_EPOCH`, `_SESSION_ORDINAL_STRIDE_SECONDS`,
`_MONTH_NAMES`, the two format regexes) — no wall-clock read, no
`random`, no dict/set iteration whose order could vary, no
machine-dependent behavior. `NORMALIZATION_POLICY_VERSION = "2.3.0"` is
recorded in every dataset's `dataset_context.json` and in
`phase2_3_temporal_validation_report.json`, so a future policy change is
always distinguishable from this one.
`tests/test_temporal_normalization.py::test_compute_temporal_fields_is_deterministic`
and `::test_full_mapping_is_deterministic` verify this at the unit level;
`preprocessing/temporal_validation.py`'s
`determinism_recompute_matches_stored_and_is_stable` check re-verifies it
against a 200-record-per-dataset sample of the real corpus (recomputing
from each stored record's own inputs and confirming the result matches
what is on disk) — **PASS**.

## Validation methodology

`preprocessing/temporal_validation.py` streams each dataset's
`data/processed/unified_memory/<dataset>/memory_records.jsonl` (Phase
2.2/2.3's output, not Phase 1's) and checks, in the project's existing
check-list report style:

1. `temporal_provenance` values are from the known vocabulary.
2. No accidental fabrication: `source_absolute` implies a real
   `normalized_timestamp` and no `benchmark_timestamp`; conversely
   `normalized_timestamp` is never set without `source_absolute`
   provenance, and `benchmark_timestamp` is never assigned alongside a
   real absolute value.
3. Ordering consistency: `event_order` never regresses within
   `(source_file, conversation_id, session_ordinal)` as the file is
   streamed in source order, and session ordinals never regress within
   `(source_file, conversation_id)`. (`source_file` is part of the key
   because LongMemEval's `session_id` can legitimately repeat across its
   two raw files — see the mapping table above and
   `preprocessing/datasets/longmemeval.py` — which is a distinct
   occurrence, not a regression.)
4. Determinism, as above.
5. Missing temporal information is never silently invented
   (`timestamp_type == "unavailable"` implies `normalized_timestamp is
   None`).
6. Identical `source_timestamp` strings never parse to two different
   `normalized_timestamp` values.
7. All four core datasets produce well-formed temporal fields for every
   record.

Run against the real, full corpus (1,266,194 records across all four
datasets): **PASS on every check** — see
`data/reports/phase2_3_temporal_validation_report.json`. The existing
Phase 2.2 cross-dataset validator (`preprocessing/unified_validation.py`)
was re-run against the same regenerated corpus and also **PASS**es
(`data/reports/phase2_2_unified_memory_validation_report.json`), which
in particular reconfirms `field_status` values are all still from the
existing known vocabulary — Phase 2.3 introduced no new field_status
values, only new *usages* of the existing ones.

## Limitations

- The `invalid_source_timestamp_format` / `ABSENCE_UNRESOLVED` path is
  implemented and unit-tested but has zero real occurrences in the
  acquired corpus — it cannot be demonstrated end-to-end against real
  data until a source file with a malformed timestamp is encountered.
- `benchmark_timestamp`'s ordering guarantee is scoped to within one
  `(source_file, conversation_id)` — there is no claim, and none is
  needed by the stated Phase 2.3 use cases, that benchmark-assigned
  coordinates are comparable *across* different conversations or
  datasets in any meaningful chronological sense (two different
  conversations' "session 1" both start at the same synthetic instant
  by construction).
- LongMemEval's weekday abbreviation (the `(Fri)` in `'2023/07/07 (Fri)
  14:05'`) is not cross-validated against the parsed date; a
  hypothetical source record with an internally inconsistent weekday
  would still parse successfully from its numeric fields. This mirrors
  Phase 1's own stance of preserving `source_timestamp` verbatim rather
  than re-deriving/correcting parts of it.
- No timezone is assumed or attached to any parsed absolute timestamp
  (`normalized_timestamp` is a naive ISO-8601 string, no `Z`/offset) —
  neither LoCoMo nor LongMemEval states one, and adding `Z` would
  fabricate a UTC claim the source does not make.

## Scope boundary

Phase 2.3 builds a temporal *substrate* — nothing more. It does not
implement (and this document does not describe) poisoning attacks,
attack generation/reconstruction, propagation analysis or graphs,
memory lifecycle graphs, sleeper detection, defenses, mitigation, or
containment. Those are later phases and would consume this substrate,
not extend it.
