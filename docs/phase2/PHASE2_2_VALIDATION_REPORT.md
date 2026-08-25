# Phase 2.2 Validation Report

## Cross-dataset validation (real corpus, full run)

`python -m preprocessing.unified_validation` — streamed all four
datasets' real `data/processed/unified_memory/*/memory_records.jsonl`
output (~54s runtime, ~1.6GB total input). Result persisted at
`data/reports/phase2_2_unified_memory_validation_report.json`:

```
overall_status: PASS
total_records: 1,266,194
```

| Check | Status |
|---|---|
| schema_conformance | PASS |
| unique_memory_ids_within_dataset_and_across_datasets | PASS |
| no_cross_dataset_id_collision | PASS |
| source_dataset_field_matches_containing_file | PASS |
| admission_status_values_are_from_known_vocabulary | PASS |
| quarantined_records_never_trusted_clean | PASS |
| field_status_values_are_from_known_vocabulary | PASS |
| record_counts_match_phase1_processed_output | PASS |

Per-dataset record counts (matching Phase 1's processed output exactly,
verified by the last check above): `locomo: 5,882`, `longmemeval:
210,365`, `msc: 227,185`, `conversation_chronicles: 822,762`.

## Test suite

```
python -m pytest -q
```

**125 tests passing** (92 carried forward from Phase 2.1/2.1-R + 33 new
for Phase 2.2: 18 synthetic mapper-logic tests, 10 bounded real-data
tests, 5 synthetic cross-dataset-validator-logic tests, 2 persisted
real-validation-report tests — see file-by-file breakdown below). No
existing test was weakened or deleted.

| Test file | Count | What it protects |
|---|---|---|
| `test_unified_memory_mapping.py` | 18 | Core mapper correctness against synthetic fixtures: schema conformance, memory_id reuse, origin classification correctness (incl. the turn_id-follows-data_quality-flag property), missing-value semantics, no fabricated timestamps/derivation/propagation, admission-status rule genericity, determinism, schema-validator failure paths |
| `test_unified_memory_real_data.py` | 10 | Real-corpus spot checks: LongMemEval quarantine preserved, LoCoMo QA fields never embedded in memory records, QA reconciliation invariant still holds, MSC license passthrough, Conversation Chronicles sample identity, record counts match Phase 1, raw files unmodified, Phase 1 output unmodified, mapper determinism on real data, schema conformance on real data |
| `test_unified_memory_cross_dataset_logic.py` | 5 | Cross-dataset validator logic itself: catches an injected ID collision, passes on consistent synthetic data, catches an injected quarantine/trust inconsistency |
| `test_unified_memory_validation_report.py` | 2 | The persisted real-run report is actually PASS and covers the full real record count |

## Acceptance-criteria walkthrough

Every checkbox in the Phase 2.2 task brief is backed by either a
passing automated test, the real cross-dataset validation run above, or
a specific documented design decision (never a bare assertion):

- Canonical schema exists, versioned (`SCHEMA_VERSION = "1.0.0"`,
  `preprocessing/unified_schema.py`) — file exists, `test_normal_record_validates_against_schema`.
- Four datasets deterministically mapped — real run above,
  `test_mapping_is_deterministic` + `test_umr_records_are_deterministic_when_remapped_from_real_phase1_data`.
- Source content/identity preserved — `content`/`source_*` fields
  copied verbatim; `test_no_raw_source_file_was_modified_by_phase_2_2`,
  `test_no_phase1_processed_file_was_modified_by_phase_2_2`.
- Provenance traceable — `provenance` dict carries the full Phase 1
  chain; `test_source_provided_content_is_not_marked_benchmark_generated`.
- Field origins explicit, four canonical terms not conflated —
  `field_status` map + `test_source_provided_fields_are_not_incorrectly_marked_benchmark_generated`-equivalent
  assertions throughout `test_unified_memory_mapping.py`.
- Memory IDs deterministic + collision-free across datasets — reused
  Phase 1 ID; `no_cross_dataset_id_collision` PASS over 1,266,194 real
  records.
- Phase 1 quality survives mapping — `test_quality_status_and_flags_survive_mapping_unchanged`.
- LongMemEval's two records remain quarantined + excluded from trusted
  baseline — `test_longmemeval_quarantined_records_remain_quarantined_in_umr`
  (real data), `quarantined_records_never_trusted_clean` (real, full
  corpus).
- LoCoMo `adversarial_answer` never becomes `canonical_answer` —
  re-verified unchanged from Phase 2.1-R by
  `test_locomo_qa_reconciliation_file_still_has_no_invented_canonical_answers`;
  QA eligibility kept structurally separate from memory validity by
  `test_locomo_umr_records_do_not_embed_qa_answer_fields`.
- Conversation Chronicles sample identity preserved —
  `test_conversation_chronicles_sample_identity_is_preserved`.
- No synthetic timestamps — `test_no_synthetic_timestamp_is_generated`;
  `benchmark_timestamp` is `null`/`NOT_AVAILABLE` on every real record
  (verified structurally — `content_type`/`benchmark_timestamp` schema
  entries force this).
- No fabricated propagation/derivation/attack labels — schema forces
  `derivation_parents`/`retrieval_history`/`propagation_history` to `[]`
  and `poison_status` to `null` in Phase 2.2 (`UMR_JSON_SCHEMA`'s
  `const_value`/type constraints, checked by `validate_record` on every
  real record).
- Schema validation passes — every real record validated in the full
  cross-dataset run (`schema_conformance: PASS`) plus bounded
  spot-checks in the fast test suite.
- Raw Phase 1 artifacts unchanged — sha256 re-verification against
  `dataset_manifest.json`, real data, in `test_unified_memory_real_data.py`.
