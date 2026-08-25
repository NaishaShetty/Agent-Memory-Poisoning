# Phase 2.1 Validation Report (Task 9 results)

Full suite: `python -m pytest -q` → **65 passed, 0 failed, 0 skipped**
(53 pre-existing Phase 1 tests + 12 new Phase 2.1 freeze-boundary tests in
`tests/test_phase2_boundary.py`). All tests run read-only against the
real `data/` directory or `tmp_path`-rooted synthetic fixtures; none
mutate `data/raw`.

## New tests and the invariant each one checks

| Test | Invariant (Task 9 requirement) | Verification method |
|---|---|---|
| `test_core_datasets_all_registered` | 1. Core dataset registration is complete | automated test |
| `test_every_manifest_entry_has_required_fields` | 2. Required metadata exists | automated test |
| `test_phase2_statuses_are_from_known_vocabulary` | 3. Resource statuses are valid | automated test |
| `test_unavailable_and_inspected_resources_are_not_approved` | 4. Unavailable resources cannot be accidentally treated as available | automated test |
| `test_raw_files_unchanged_since_dataset_manifest_was_generated` | 5. Raw source artifacts are not overwritten | automated test (re-hashes real files on disk) |
| `test_processed_memory_records_carry_provenance` | 6. Phase 1 provenance links exist for representative records | automated test (reads real processed output) |
| `test_quality_status_distributions_cover_known_vocabulary` | 7. Quality classifications are preserved | automated test |
| `test_quarantine_log_entries_are_traceable_to_source` | 8. Quarantined records remain traceable | automated test (reads real quarantine log) |
| `test_manifest_top_level_schema` | 9. Manifest schema is valid | automated test |
| `test_core_datasets_have_snapshot_and_checksum_identifiers` | 10. Dataset/version identifiers are present where available | automated test |
| `test_manifest_generation_is_deterministic_given_fixed_timestamp` | 11. Phase 2 input selection is deterministic | automated test (byte-for-byte equality of two independent builds) |
| `test_no_attack_or_sleeper_resource_is_approved` | 12. No attack/poisoned data is included in the clean Phase 2.1 foundation | automated test |

Every Task 9 invariant maps to exactly one real test; none were padded or
duplicated to inflate the count.

## Verification-method key used throughout Phase 2.1 documentation

Per the task's final research-integrity requirement, every claim in
`PROVENANCE_TRACE.md`, `ISSUES_REPORT.md`, and this document is tagged
(explicitly or by section) as one of:

- **verified by artifact inspection** — a human/agent directly opened and
  read the actual file (raw data, processed record, log entry, report)
  during the Phase 2.1 audit.
- **verified by automated test** — a pytest assertion in
  `tests/test_phase2_boundary.py` (or a pre-existing Phase 1 test) checks
  it on every run.
- **inferred** — derived from code inspection without a corresponding
  test or direct data read (used sparingly; flagged where it occurs, e.g.
  the deterministic-reproduction claim in `REPRODUCIBILITY_REPORT.md`
  under "What 'reproducible' means for this project today").
- **unavailable / unresolved** — explicitly could not be verified (e.g.
  DSRM's identity, MSC's dataset-specific license, whether the named
  "Methodology"/"PROCESS DOCUMENTATION" files exist anywhere).

No claim in the Phase 2.1 deliverables asserts completeness beyond what
its tag supports.
