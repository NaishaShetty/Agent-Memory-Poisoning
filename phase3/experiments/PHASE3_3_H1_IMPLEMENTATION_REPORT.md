# Phase 3.3-H.1 — Canonical Memory Ledger — Implementation Report

Status: **COMPLETE**. Architectural remediation stage only — no evaluation campaign was run
or modified.

## 1. Files changed

All additions. **No existing file was modified.**

| File | Purpose |
|---|---|
| `phase3/evaluation/foundations/canonical.py` | `CanonicalMemoryRecord` — strict runtime object for `memory_schema.json` |
| `phase3/evaluation/foundations/ledger.py` | `CanonicalMemoryLedger` — benchmark-owned, foundation-independent store + alias table |
| `phase3/evaluation/foundations/canonical_write.py` | `write_canonical_memory()` — authoritative write orchestration; the documented transitional compatibility wrapper |
| `phase3/evaluation/tests/test_canonical_memory_ledger_h1.py` | 29 contract tests covering the mission's 20 test items + 8 invariants |
| `phase3/specification/PHASE3_3_H1_CANONICAL_MEMORY_LEDGER.md` | Architecture/design document |
| `phase3/experiments/PHASE3_3_H1_IMPLEMENTATION_REPORT.md` | This report |

## 2. Interfaces changed

**None.** `MemoryFoundationAdapter` (`phase3/evaluation/foundations/adapter.py`) is
byte-for-byte unmodified. `write_canonical_memory()` is a new, additive function that
consumes a `CanonicalMemoryRecord` and drives the existing, unmodified
`add_memory(memory_id, content, metadata)` interface underneath — see
`PHASE3_3_H1_CANONICAL_MEMORY_LEDGER.md` section 9 ("WHY NO ADAPTER INTERFACE CHANGE") for
the full reasoning: the currently-running 3.3-G.1 A-MEM × LongMemEval campaign made a
breaking interface change (which would require editing `amem_real_adapter.py`, on that
process's live execution path) a hard STOP per the mission's own STOP conditions.

## 3. Adapters migrated / not migrated

| Adapter | File touched | Reason |
|---|---|---|
| `RealMem0Adapter` | No | Compatible via wrapper; no change needed |
| `RealAMemAdapter` | **No** | **Deliberately untouched — live 3.3-G.1 execution path** |
| `RealGraphitiAdapter` | No | Compatible via wrapper; no change needed |
| `RealLettaAdapter` | No | Compatible via wrapper; all methods already `_deferred` |
| `MockMem0Adapter` | No | Compatible via wrapper; exercised directly in new tests |
| `MockAMemAdapter` | No | Compatible via wrapper; exercised directly in new tests |
| `MockGraphitiAdapter` | No | Compatible via wrapper; exercised directly in new tests |
| `MockLettaAdapter` | No | Compatible via wrapper (not directly exercised — Letta has no live behavior to test against) |

No foundation was marked `UNQUALIFIED_FOR_H1` — the transitional-wrapper approach means
every existing adapter, real or mock, already satisfies the canonical write contract with
zero modification.

## 4. Tests

**Before this stage:** `python -m pytest phase3/evaluation/tests/ -q` → **1159 passed, 14
skipped** (342.77s).

**After this stage:** `python -m pytest phase3/evaluation/tests/ -q` → **1188 passed, 14
skipped** (365.20s) — exactly `1159 + 29` new tests, zero regressions, identical skip count.

**`-W error` pass:** `python -m pytest phase3/evaluation/tests/ -q -W error` → **1188
passed, 14 skipped** (309.19s) — identical result to the plain run; no warning was promoted
to an error anywhere in the suite, including the new H.1 tests.

**New H.1 tests only:** `python -m pytest phase3/evaluation/tests/test_canonical_memory_ledger_h1.py -q`
→ **29 passed** in 0.21s.

Coverage against the mission's 20-item test list and 8 invariants:

| # | Item | Test(s) |
|---|---|---|
| 1 | canonical record creation | `test_canonical_record_creation_valid` |
| 2 | schema validation | `test_schema_validation_rejects_malformed_records`, `test_derived_record_requires_parent_ids`, `test_invalid_timestamp_rejected` |
| 3 | canonical ID uniqueness | `test_canonical_id_uniqueness_and_idempotent_rewrite` |
| 4 | canonical ID collision | `test_canonical_id_collision_fails_loudly`, `test_collision_is_never_swallowed_by_write_canonical_memory` |
| 5 | provenance preservation | `test_provenance_and_content_preserved_exactly` |
| 6 | exact content preservation | `test_provenance_and_content_preserved_exactly`, `test_to_dict_from_dict_round_trip` |
| 7 | canonical ledger persistence | `test_records_and_aliases_are_valid_jsonl` |
| 8 | canonical ledger reload | `test_ledger_persists_and_reloads_from_disk` |
| 9 | canonical memory reconstruction | `test_ledger_persists_and_reloads_from_disk`, `test_reconstruction_independent_of_vendor_inspection[*]` |
| 10 | canonical -> vendor alias mapping | `test_alias_mapping_both_directions` |
| 11 | vendor -> canonical alias resolution | `test_alias_mapping_both_directions` |
| 12 | multiple foundations sharing one canonical identity | `test_multiple_foundations_share_one_canonical_identity` |
| 13 | vendor-generated ID cannot replace canonical ID | `test_vendor_generated_id_cannot_replace_canonical_id` |
| 14 | canonical record survives vendor failure | `test_canonical_record_survives_vendor_failure` |
| 15 | vendor failure is explicitly observable | `test_vendor_failure_is_explicitly_observable` |
| 16 | A-MEM inspection not required for reconstruction | `test_reconstruction_independent_of_vendor_inspection[MockAMemAdapter-a-mem]` |
| 17 | Mem0 inspection not required for reconstruction | `test_reconstruction_independent_of_vendor_inspection[MockMem0Adapter-mem0]` |
| 18 | Graphiti inspection not required for reconstruction | `test_reconstruction_independent_of_vendor_inspection[MockGraphitiAdapter-graphiti]` |
| 19 | no evaluator/gold data can enter canonical record | `test_no_evaluator_gold_data_can_enter_canonical_record` |
| 20 | leakage checks continue to pass | `test_clean_canonical_record_passes_leakage_checks` + zero regressions in the full suite (which includes the existing `security/leakage` test coverage) |

| Invariant | Test(s) |
|---|---|
| 1: one canonical identity per memory | `test_canonical_id_uniqueness_and_idempotent_rewrite` |
| 2: canonical identity foundation-independent | `test_canonical_only_write_when_no_foundation_supplied` |
| 3: canonical content foundation-independent | `test_reconstruction_independent_of_vendor_inspection[*]` |
| 4: vendor IDs are aliases, never canonical identities | `test_vendor_generated_id_cannot_replace_canonical_id` |
| 5: reconstruction needs no vendor service | `test_reconstruction_independent_of_vendor_inspection[*]` |
| 6: vendor deletion/update cannot erase the canonical record | `test_canonical_record_survives_vendor_failure`, `test_reconstruction_independent_of_vendor_inspection[*]` (post-`reset()`) |
| 7: a collision cannot silently overwrite history | `test_canonical_id_collision_fails_loudly` |
| 8: provenance not reconstructable solely from vendor metadata | `test_provenance_and_content_preserved_exactly` (provenance is asserted straight from the ledger, never derived from any adapter call) |

## 5. Compatibility issues encountered

None requiring a design change. One test-authoring bug was found and fixed during
self-verification: an initial `pytest.raises(Exception)` block in
`test_reconstruction_independent_of_vendor_inspection` wrapped an assertion that could
never raise, silently passing for the wrong reason; corrected to assert the mock's actual
post-`reset()` `inspect_memory()` return shape (`value is None`) instead.

## 6. Unresolved issues / exact remaining limitations

See `PHASE3_3_H1_CANONICAL_MEMORY_LEDGER.md` section 15 for the full list. Summary:

- `CanonicalMemoryLedger` is single-process/single-writer (no cross-process file lock) —
  acceptable because no caller adopts it yet.
- Validation is hand-written per-field Python, not a generic `jsonschema.validate()` call
  against `memory_schema.json` — deliberate (the mission asks for dataclass-enforced
  validation), documented as a possible belt-and-suspenders follow-up.
- No existing call site (`campaign_formal_runner.py`, `campaign_runner.py`, pilot scripts)
  was migrated to `write_canonical_memory()` — deliberately deferred, see design doc
  section 13.
- Vendor-id extraction depends on the `value["memory_id"]` convention observed across all
  eight existing adapters; a hypothetical future adapter violating this convention would
  degrade to `ALIAS_PERSISTENCE_FAILED` (observable, not a crash) rather than resolve
  correctly.

## 7. G.1 impact

**The running 3.3-G.1 A-MEM × LongMemEval N=120 campaign was not disturbed.**

Verified before writing any code: `Get-CimInstance Win32_Process -Filter "Name='python.exe'"`
showed three live worker processes running
`phase3.evaluation.agent_runtime.campaign_formal_runner c_longmemeval_worker {0,1,2} 3`
under `C:\h4venv\Scripts\python.exe`.

Verified again after implementation, before finalizing this report: the same three worker
processes (PIDs unchanged: 33588/18212/4512 under `h4venv`, plus their subprocess
counterparts) were still running the identical command line.

No file on that process's import path
(`campaign_formal_runner.py`, `foundations/adapter.py`, `foundations_real/amem_real_adapter.py`,
`foundations_real/environment.py`, `agent_runtime/identity.py`, `agent_runtime/runner.py`,
`agent_runtime/campaign_formal_manifest.py`, `agent_runtime/campaign_formal_diagnostics.py`,
or any of its checkpoint/manifest/result files under `phase3/experiments/`) was modified,
read-written, or deleted by this stage. `git status --short` confirms every change this
stage made is a newly-added file; `git diff --stat` against the working tree shows zero
modified tracked files.

## 8. Git status

```
$ git status --short
?? phase3/evaluation/foundations/canonical.py
?? phase3/evaluation/foundations/canonical_write.py
?? phase3/evaluation/foundations/ledger.py
?? phase3/evaluation/tests/test_canonical_memory_ledger_h1.py
?? phase3/specification/PHASE3_3_H1_CANONICAL_MEMORY_LEDGER.md
?? phase3/experiments/PHASE3_3_H1_IMPLEMENTATION_REPORT.md
(plus pre-existing untracked files from the in-progress 3.3-G/G.1 campaign work, unrelated
to and unmodified by this stage)

$ git diff --stat
(empty -- no tracked file was modified)
```

Per the mission's GIT RULE, no `git add`/`commit`/`push` was performed. The user will
review and stage these changes manually.
