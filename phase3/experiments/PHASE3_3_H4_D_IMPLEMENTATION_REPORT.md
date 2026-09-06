# Phase 3.3-H.4-D — Foundation Qualification Gate — Implementation Report

Status: **COMPLETE** (fixture freeze, round-trip harness, qualification record/ledger,
currency checker, tests). **No real (non-mock) qualification run was performed against
Mem0/A-MEM/Graphiti/Letta** — every test in this stage runs against `foundations/mocks/
mock_mem0.py` and `foundations/mocks/mock_amem.py`. See section 7.

## 1. Scope correction, confirmed

Direct inspection (mission section 1) found the fixture-consuming test set is exactly four
files (`metrics/equivalence.py`, `test_evaluation_contracts.py`,
`test_evidence_equivalence.py`, `test_provenance_lineage.py`), none of which constructs a
`CanonicalMemoryRecord`, writes through `canonical_write.write_canonical_memory()`, or reads
back through `CanonicalEventLedger`/`memory_versioning.py`. No round-trip harness existed
before this stage — this report documents building it, not "promoting" a pre-existing gate.

## 2. Fixture set — verified count, frozen

Verified 22 files, not the mission brief's own flagged-as-possibly-stale "20": 3
(`conflicting_memory/`) + 3 (`equivalent_memory/`) + 4 (`derived_memory/` — one more file
than the other two pair-fixtures, since it has three memories not two) + 12 (`lineage/`).
`fixture_set_version = "qualification_fixtures_v1"` frozen in
[`phase3/evaluation/fixtures/QUALIFICATION_FIXTURE_MANIFEST.json`](../evaluation/fixtures/QUALIFICATION_FIXTURE_MANIFEST.json)
— per-file SHA-256 (`security.reproducibility.digest_bytes()`, the same authority H.4-F
already established) plus one set-level `fixture_set_hash` (`fingerprint()` of the sorted
per-file digest mapping). `qualification_fixtures.py`'s `verify_fixture_manifest()` performs
a LIVE directory walk (not just a re-check of the frozen manifest's own file list) so a
genuinely added file is detectable, not only a modified or removed one.

## 3. The harness — design decisions, all explicit

`qualification_harness.py`'s module docstring records four decisions made necessary by
direct experimentation against the real fixtures and the real (frozen) ledger code, not
assumed in advance:

1. **Relationship facts are never copied onto the written `CanonicalMemoryRecord`.** The
   fixture JSON already carries each scenario's intended FINAL answer
   (`equivalent_to`/`conflicts_with`/`superseded_by`/`lifecycle_state`) — copying those onto
   the record the harness writes would make "reconstruction" a tautology. Every written
   record always has `lifecycle_state=CREATED` and no relationship fields; every
   relationship fact is instead established by replaying an event and reconstructed by
   reading the event ledger back.
2. **`created`/`derived` events are synthesized from each memory's own record fields**
   (`creation_event`, `creation_timestamp`, `parent_ids`), not replayed verbatim from
   `events.json` — `conflicting_memory/events.json`'s and `equivalent_memory/events.json`'s
   own docstrings already flag themselves as illustrative, not machine-replayable, and
   `lineage/*.json` fixtures have no `events.json` at all. One code path handles every
   fixture shape.
3. **Two latent gaps were found in frozen H.2/H.3 code during implementation** (both
   discovered by running the harness against the real fixtures, not by inspection alone):
   - `event_ledger.py`'s H.2-R2 single-occurrence check (frozen, extended-not-altered by
     H.4-BC/H.4-F) treats ANY appearance of a `memory_id` in a `derived` event's
     `memory_ids` tuple — which legitimately includes every SOURCE, not just the target —
     as "this memory already has a creation slot." Appending a child's `derived` event
     before its parent's own `created`/`derived` event raises
     `SingleOccurrenceViolationError` when the parent's own event is appended afterward.
     Worked around by replaying events in topological order (`_event_replay_order()`,
     Kahn's algorithm over `parent_ids`) for every acyclic fixture.
   - `memory_versioning.reconstruct_version_history()` (frozen, H.3) filters lifecycle
     events via `events_for_memory()`, which has the identical "matches on any appearance
     in `memory_ids`" property — so a memory that is merely a PARENT of some derived memory
     also picks up that `derived` event (`new_state=None`) into its own version history,
     which `CanonicalMemoryVersion.__post_init__` then rejects. H.3's own test suite never
     exercises this (it only ever seeds via `created`). Worked around by never invoking
     `memory_versioning` for any id that is derivation-touched at all (`_derivation_touched_
     ids()`) — none of the 22 frozen fixtures need supersession/retirement checked on such
     an id anyway.
   Neither frozen file (`event_ledger.py` beyond H.4-BC/H.4-F's own prior, separate
   additions; `memory_versioning.py`) was modified to work around these — both are
   documented, honest limitations of this stage's harness, exactly matching this
   framework's own established convention (e.g. H.4-F's temporal-ordering gap) rather than
   patching a frozen module.
4. **`conflicts_with` has no existing `metrics/*.py` function.** `metrics/equivalence.py`
   computes `equivalent_to` components; nothing computes anything for `conflicts_with`
   (confirmed absent by grep). `_symmetric_edges()` is one small, local, purely mechanical
   extraction (declared-on-both-sides pairs, generalized from `equivalence.py`'s own
   `extract_equivalence_edges()` pattern) — never a semantic/content-based conflict
   inference.
5. **A real graph cycle among `derived` memories (`10_cycle.json`) cannot be fully
   represented via the event ledger's single-occurrence model** — every node in a cycle is
   both a source and a target across different events, which is exactly the ambiguity item
   3 describes, and no replay order resolves it (no topological order exists for a cycle).
   The harness catches and records the resulting `SingleOccurrenceViolationError` rather
   than crashing; critically, ancestor/descendant/cycle RECONSTRUCTION never depends on
   these events anyway (it reads `parent_ids` straight off `CanonicalMemoryLedger`, which
   Step 1 always writes successfully regardless of Step 2's event-replay outcome) — so the
   qualification check for this fixture is unaffected.

## 4. Comparison

`compare_graphs()` does an explicit, per-key diff (ancestors, descendants, cycles,
equivalence components, conflict pairs, orphan children, supersession state, and — for
fixtures 11/12 — the independence-diagnostic pairwise classification) between
`compute_expected_graph()` (raw fixture JSON, via unmodified `metrics/provenance.py`/
`metrics/equivalence.py`) and `reconstruct_graph()` (purely from `CanonicalMemoryLedger` +
`CanonicalEventLedger` + `SupersessionLedger` — never the fixture JSON again). Every
mismatch names the specific disagreeing key (tested directly:
`test_disagreeing_graphs_report_the_specific_edge_not_a_bare_boolean`,
`test_fixture_result_reports_mismatch_when_reconstruction_is_tampered` — the latter
monkeypatches `reconstruct_graph` to simulate a foundation silently dropping a
`conflicts_with` edge, and confirms it is reported failed with the edge named, never
silently passed).

## 5. `FoundationQualificationRecord` / `QualificationLedger`

`qualification_record.py`. `overall_verdict == QUALIFIED` is structurally impossible unless
`conformance_tag == REAL_FOUNDATION_CONFORMANCE` (Phase 3.2-H.4's own, imported read-only,
never-redefined `conformance_record.CONFORMANCE_TAGS` vocabulary) AND every fixture in
`per_fixture_results` passed — enforced in `__post_init__`, mirroring
`RealConformanceRecord`'s own analogous invariant. `QualificationLedger` is append-only
(`qualifications.jsonl`), no `update()`/`delete()`. `run_foundation_qualification()` ties
`qualification_fixtures.py` + `qualification_harness.py` + `conformance_record.py` +
`run_config.py` together: it verifies the fixture manifest BEFORE running anything (raising
`FixtureManifestError` on drift), validates `config_fingerprint` against a supplied
`RunConfigLedger` if one is given, and gives each fixture its OWN, freshly-constructed
ledger triple under its own subdirectory — several fixtures deliberately reuse the same
`memory_id` for unrelated scenario content (e.g. `lineage/01_independent.json` and
`lineage/02_direct_derivation.json` both declare `mem-lin-A`), so a single shared ledger
across all 22 fixtures would raise a genuine `CanonicalCollisionError` on the second reuse —
correctly, since a real shared ledger should never merge unrelated scenario content, which
is exactly why this function does not use one.

## 6. `check_qualification_currency()`

Flags, never silently passes: no qualification record for the foundation; the record's
`fixture_set_version` differs from what the manifest declares; the record's
`adapter_revision` no longer matches the foundation adapter's current one (if supplied); or
the record's own `overall_verdict` is `NOT_QUALIFIED`. Pure documentation/tooling — see
section 7.

## 7. Explicit non-scope / deferred (mission section 10)

- **No real (non-mock) qualification run was performed.** Every test in
  `test_qualification_h4_d.py` runs against `MockMem0Adapter`/`MockAMemAdapter`. All 22
  fixtures pass against both mocks — proof of the harness's own replay/compare correctness
  (mission section 11's explicit minimum bar), not proof any real foundation is qualified.
  Actually invoking this against real Mem0/A-MEM/Graphiti/Letta libraries (which would
  require Phase 3.2-H.4's own `C:\h4venv` environment-isolation precedent) is a follow-up
  execution step, not part of building the mechanism.
- `check_qualification_currency()` is not wired as a hard pre-flight block inside
  `campaign_formal_runner.py` — allowed but not required per mission section 7; deferred,
  matching H.4-BC's/H.4-F's own precedent for deferred live-wiring.
- Running Graphiti's first baseline campaign — unaffected, a separate later action.
- Initiatives A, E, G — untouched, unrelated.
- Phase 3.2-H.4's own conformance results/tag definitions — not modified; `CONFORMANCE_TAGS`
  is imported read-only from `conformance_record.py`.

## 8. Files touched

- `phase3/evaluation/fixtures/QUALIFICATION_FIXTURE_MANIFEST.json` — new, frozen manifest.
- `phase3/evaluation/foundations_real/qualification_fixtures.py` — new: manifest
  computation/freezing/verification, fixture loading.
- `phase3/evaluation/foundations_real/qualification_harness.py` — new: replay, expected/
  reconstructed graph computation, comparison, per-fixture result.
- `phase3/evaluation/foundations_real/qualification_record.py` — new:
  `FoundationQualificationRecord`, `QualificationLedger`, `check_qualification_currency()`,
  `run_foundation_qualification()` orchestration.
- `phase3/evaluation/tests/test_qualification_h4_d.py` — new, 74 tests covering mission
  sections 8 and 9.

**Frozen/existing-untouched files — verified unmodified (empty diff) since the H.4-F
report:** `canonical.py`, `ledger.py`, `canonical_write.py` (H.1); `memory_versioning.py`
(H.3); `metrics/provenance.py`, `metrics/equivalence.py` (Phase 3.2-D);
`foundations_real/conformance_record.py` (Phase 3.2-H.4); `test_provenance_lineage.py`,
`test_evidence_equivalence.py`, `test_evaluation_contracts.py`. `canonical_event.py`/
`event_ledger.py` (H.2, already additively extended by H.4-BC/H.4-F) were NOT touched again
in this stage — this stage calls them only.

## 9. Tests

**Before H.4-D (this session's own baseline, carried over from the H.4-F report):**
`python -m pytest phase3/evaluation/tests/ -q` → **1411 passed, 1 failed, 17 skipped**
(319.21s). The one failure is the same pre-existing, unrelated dataset-fingerprint drift
reported in the H.4-BC and H.4-F reports.

**After H.4-D:** **1485 passed, 1 failed (the same pre-existing failure), 17 skipped**
(342.30s) — exactly `1411 + 74` new tests, zero regressions, identical failure and skip
counts.

**New H.4-D tests only:**
`python -m pytest phase3/evaluation/tests/test_qualification_h4_d.py -q` →
**74 passed** (1.24s).

## 10. Definition of done — checklist

- [x] Fixture set frozen and versioned (`qualification_fixtures_v1`, 22 files, content
      hash), reproducible re-freeze verified.
- [x] Harness replays every fixture through a mock adapter and compares canonical-ledger-
      reconstructed graphs against `metrics/provenance.py`/`equivalence.py`'s own computed
      expectations — no real-foundation run performed (stated honestly above).
- [x] `FoundationQualificationRecord`/`QualificationLedger` exist and enforce the
      CRUD-conformance-dependency invariant (tested:
      `test_environment_limitation_conformance_is_never_qualified_even_if_fixtures_pass`).
- [x] `check_qualification_currency()` exists and flags every drift shape mission section 7
      names.
- [x] All invariants (section 8) and adversarial cases (section 9) pass.
- [x] Regression suite shows zero regressions (1411→1485 passed, same 1 pre-existing
      unrelated failure, same 17 skipped).
- [x] This report states real-vs-mock execution status honestly (mock only).
- [x] No modification to any file listed as frozen/existing-untouched in mission section 3.

Completion makes Graphiti's first baseline campaign gate-able under this mechanism, per
`MEMORY_FOUNDATION_STRENGTHENING_PLAN_REVISED.md` §9 — pending an actual real qualification
run, which this stage's harness/gate machinery now makes possible but does not itself
perform.
