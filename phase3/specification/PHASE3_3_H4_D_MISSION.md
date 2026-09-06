# Phase 3.3-H.4-D — Foundation Qualification Gate — Mission Brief

Status: **NOT STARTED**. Mission brief for an implementation pass, in the same role
[PHASE3_3_H4_BC_MISSION.md](PHASE3_3_H4_BC_MISSION.md) and
[PHASE3_3_H4_F_MISSION.md](PHASE3_3_H4_F_MISSION.md) played for the completed H.4-BC/H.4-F
stages. Covers **Initiative D only**, per
[MEMORY_FOUNDATION_STRENGTHENING_PLAN_REVISED.md §4](MEMORY_FOUNDATION_STRENGTHENING_PLAN_REVISED.md)
and §10 (sequenced after F, which this stage now depends on for `config_fingerprint`). On
completion, produce `PHASE3_3_H4_D_IMPLEMENTATION_REPORT.md` under `phase3/experiments/`.

**Naming disambiguation, checked before writing this brief:** an unrelated, already-complete
stage exists at `phase3/evaluation/tests/test_foundation_conformance_h4.py` /
`phase3/evaluation/foundations_real/conformance_record.py`, headed **"Phase 3.2-H.4"** — a
different phase number. That stage proves real adapters' basic CRUD operations
(`INITIALIZE`/`ADD_MEMORY`/`RETRIEVE`/etc.) actually execute against the real installed
libraries (`mem0ai`, `graphiti-core`, `sentence-transformers`, `letta-client`) under a
separate interpreter (`C:\h4venv`), tagging each result `REAL_FOUNDATION_CONFORMANCE` /
`MODEL_DEPENDENT` / `ENVIRONMENT_LIMITATION` / `DEFERRED` / `NOT_ATTEMPTED`. This mission
(**Phase 3.3-H.4-D**) is a different, higher-level question: given a foundation that CRUD-
conforms, does the **canonical ledger** correctly reconstruct relationship/lineage
semantics (equivalence, conflict, supersession, derivation) after round-tripping through
that foundation? Do not confuse the two. §2 states the dependency between them explicitly.

## 1. Problem — corrected understanding from repo inspection

The original strengthening plan assumed the H.3 fixtures
(`phase3/evaluation/fixtures/{conflicting_memory,equivalent_memory,derived_memory,lineage}/`)
already establish "structural conformance" per foundation and only needed to be "promoted"
into a regression gate. **Direct inspection during this mission's preparation found this is
not accurate**, and the mission scope is corrected accordingly:

- `grep`-ing every consumer of these fixture directories found exactly four: `metrics/
  equivalence.py`, `tests/test_evaluation_contracts.py`, `tests/test_evidence_equivalence.py`,
  `tests/test_provenance_lineage.py`.
- All four load the fixtures as **plain JSON dicts** and feed them directly to pure
  functions in `metrics/provenance.py` / `metrics/equivalence.py` (Phase 3.2-D). None of
  them constructs a `CanonicalMemoryRecord`, writes through
  `canonical_write.write_canonical_memory()`, calls any real or mock foundation adapter, or
  reads back through `CanonicalEventLedger`/`memory_versioning.py`.
- **There is currently no harness that replays a fixture through an actual foundation
  adapter and the canonical ledger, then checks the reconstructed relationship graph
  against the fixture's own expectations.** That harness does not exist yet — this mission
  is where it gets built, not merely "wired into a gate."

This corrects the plan's phrasing ("promote... into... a standing regression gate") into
its accurate scope: **build the missing round-trip qualification harness, define what it
means to pass, freeze the fixture set version, then gate future experiment runs on it.**

## 2. Dependency on Phase 3.2-H.4 (structural CRUD conformance)

A foundation cannot be meaningfully qualified by this stage if its basic `ADD_MEMORY`/
`RETRIEVE` operations don't actually run for real — that would qualify a foundation that
never executed. Before running this stage's harness against a foundation:

- Consult that foundation's existing `RealConformanceRecord` results (Phase 3.2-H.4). If
  `ADD_MEMORY`/`RETRIEVE` are tagged `REAL_FOUNDATION_CONFORMANCE`, proceed with a real
  qualification attempt.
- If tagged `ENVIRONMENT_LIMITATION`/`MODEL_DEPENDENT`/`DEFERRED`/`NOT_ATTEMPTED` (e.g.
  Letta, with no server available in this environment), this stage's qualification result
  for that foundation must be tagged consistently — **never** `REAL_FOUNDATION_CONFORMANCE`
  for a foundation whose underlying CRUD never ran for real. Reuse
  `foundations_real.conformance_record.CONFORMANCE_TAGS` as the vocabulary for this
  consistency check (import it read-only; do not modify `conformance_record.py` — see §3).

## 3. Relationship to frozen/existing files (must remain untouched)

- `canonical.py`, `ledger.py`, `canonical_write.py` (H.1) — **call only**
  (`write_canonical_memory()` is the existing, documented ingestion bridge: constructs/
  validates a `CanonicalMemoryRecord`, writes it to `CanonicalMemoryLedger`, calls the
  foundation adapter's existing unmodified `add_memory(memory_id, content, metadata)`,
  records the vendor alias — this is exactly the mechanism this stage's harness needs and
  must reuse, not reinvent).
- `canonical_event.py`, `event_ledger.py` (H.2, extended by H.4-BC/H.4-F) — call only. This
  stage may need one more additive field if qualification records need to reference
  specific events, but default to **not** modifying these files; the qualification record
  (§5) is a new, separate type, following H.3's own precedent (§5.1 of
  `PHASE3_3_H4_F_MISSION.md`'s reasoning applies identically here: a frozen type's shape
  that can't express a new fact gets a new, additive side-record, not a modification).
- `memory_versioning.py` (H.3) — call only (`reconstruct_version_history()`,
  `get_current_version()`, `supersede_memory()`/`retire_memory()` as needed to replay
  supersession fixtures).
- `run_config.py` (H.4-F) — call/reuse. Qualification records reference a
  `config_fingerprint` from this exact module (§6) — do not build a second, parallel
  configuration-record type.
- `metrics/provenance.py`, `metrics/equivalence.py` (Phase 3.2-D) — call only. These
  already compute "expected" relationship/lineage facts from a fixture's raw JSON; this
  stage's harness uses their output as the **ground truth** to compare the
  canonical-ledger-reconstructed result against, rather than re-deriving expected values by
  a second, independent method.
- `foundations_real/conformance_record.py` (Phase 3.2-H.4) — reuse the tag vocabulary
  (§2) read-only. Do not modify.
- Every existing fixture-consuming test (`test_provenance_lineage.py`,
  `test_evidence_equivalence.py`, `test_evaluation_contracts.py`) — untouched; this stage
  adds a new, additional way of exercising the same fixtures, it does not replace or modify
  their existing JSON-only exercise of them.

## 4. Deliverable 1 — freeze the fixture set version

Introduce `fixture_set_version = "qualification_fixtures_v1"` identifying, by content hash
or explicit manifest listing (implementer's choice, document whichever is used), the exact
current contents of `phase3/evaluation/fixtures/{conflicting_memory,equivalent_memory,
derived_memory,lineage}/` (20 files total: 3+3+3+12 lineage sub-fixtures at time of writing
— verify count and exact filenames against the directory in §1 before freezing, do not
transcribe stale figures). Any future addition or modification to these fixtures requires
a new version identifier (`qualification_fixtures_v2`, etc.) — never a silent edit under
the same version string. Store this freeze declaration in a small manifest file (e.g.
`phase3/evaluation/fixtures/QUALIFICATION_FIXTURE_MANIFEST.json` or equivalent) listing
every included file and, ideally, a content hash per file (reuse whatever fingerprinting
utility H.4-F already established — `security.reproducibility.fingerprint()` — rather than
inventing a second hashing scheme).

## 5. Deliverable 2 — the qualification round-trip harness

New module (e.g. `phase3/evaluation/foundations_real/qualification_harness.py`). For a
given `(foundation_adapter, fixture)` pair:

1. Load the fixture's memory records and events (raw JSON, as the existing consumers
   already do).
2. Replay each memory through `canonical_write.write_canonical_memory()` against the given
   foundation adapter, in the fixture's own declared order (never re-sorted).
3. Replay each fixture event (`created`/`derived`/`superseded`/`retired`, and, where the
   fixture concerns an `equivalent_to`/`conflicts_with`/`superseded_by` pair, a
   `relationship_detected` event per H.4-BC) through `CanonicalEventLedger.append()`,
   tagging each `retrieved`/`selected` event (if the fixture contains any) with a
   `config_fingerprint` resolvable against a `RunConfigLedger` entry for this
   qualification run (H.4-F).
4. Reconstruct the resulting relationship graph purely from the canonical ledgers
   (`CanonicalMemoryLedger`, `CanonicalEventLedger`, `SupersessionLedger` via
   `memory_versioning.py`) — never by re-reading the original fixture JSON at this step.
5. Compute the fixture's **expected** relationship graph using the existing, unmodified
   `metrics/provenance.py`/`metrics/equivalence.py` functions (the same ones
   `test_provenance_lineage.py` already calls) against the same fixture JSON.
6. Compare reconstructed (step 4) against expected (step 5). A fixture **passes** iff the
   two agree on every relationship/lineage fact the fixture is designed to exercise
   (ancestry, descendant sets, cycle presence/absence, equivalence pairing, conflict
   pairing, current supersession state) — exact comparison semantics (e.g. set equality of
   ancestor sets) are an implementation decision, but must be explicit and asserted, not
   approximate.

**This is the harness's entire job.** It does not decide pass/fail policy for an entire
foundation (that's §6) — it produces one pass/fail-with-detail result per
`(foundation, fixture)` pair.

## 6. Deliverable 3 — `FoundationQualificationRecord` and its ledger

New module (e.g. `qualification_record.py`), following the same frozen-dataclass +
append-only-ledger discipline as every prior stage:

`FoundationQualificationRecord` fields:

| Field | Meaning |
|---|---|
| `foundation_id` | e.g. `"MEM0"`, `"AMEM"`, `"GRAPHITI"`, `"LETTA"` |
| `adapter_revision` | the adapter module's own version/commit identifier |
| `fixture_set_version` | e.g. `"qualification_fixtures_v1"` (§4) |
| `config_fingerprint` | the `RunConfigRecord` fingerprint (H.4-F) active during this qualification run |
| `per_fixture_results` | mapping of fixture name → pass/fail + detail (§5 step 6's output) |
| `conformance_tag` | one of Phase 3.2-H.4's `CONFORMANCE_TAGS` (§2), reflecting the underlying CRUD conformance this qualification attempt actually achieved |
| `overall_verdict` | `QUALIFIED` only if every fixture passed AND `conformance_tag == REAL_FOUNDATION_CONFORMANCE`; otherwise `NOT_QUALIFIED`, with `per_fixture_results` and `conformance_tag` explaining why |
| `qualified_at` | ISO-8601 UTC timestamp |

`QualificationLedger` — append-only (`qualifications.jsonl`), no update/delete, same
discipline as `RunConfigLedger`/`CanonicalEventLedger`. `get_latest(foundation_id)`,
`all_for_foundation(foundation_id)`, `exists(...)`.

## 7. Deliverable 4 — the gate itself

An experiment manifest (or equivalent run-declaration artifact) must record which
`FoundationQualificationRecord` (by `foundation_id` + `adapter_revision` +
`fixture_set_version`) it was run under. A checker function (e.g.
`check_qualification_currency(manifest, qualification_ledger)`) flags — does not silently
pass — a manifest whose declared `adapter_revision` no longer matches the foundation
adapter's actual current revision, or whose referenced qualification record has
`overall_verdict == NOT_QUALIFIED`. This is a documentation/tooling deliverable, not
necessarily a hard runtime block on `campaign_formal_runner.py` at this stage — wiring it
as an enforced pre-flight check on that runner is allowed but not required; if deferred,
say so explicitly in the implementation report (matching H.4-BC/H.4-F's own precedent for
deferred live-wiring).

## 8. Invariants to implement and test

1. `fixture_set_version` is stable and content-addressable — re-running the freeze process
   against unchanged fixture files reproduces the identical version identifier/hash.
2. The harness (§5) is deterministic: replaying the same fixture through the same
   foundation adapter with the same `config_fingerprint` twice produces identical
   pass/fail results.
3. `FoundationQualificationRecord.overall_verdict == QUALIFIED` is structurally impossible
   unless `conformance_tag == REAL_FOUNDATION_CONFORMANCE` **and** every fixture in
   `per_fixture_results` passed — enforced in `__post_init__`, mirroring
   `RealConformanceRecord`'s own `REAL_FOUNDATION_CONFORMANCE` requires
   `library_import_succeeded` invariant (conformance_record.py lines 124-129).
4. `QualificationLedger` is append-only — no update/delete (structural test).
5. A qualification record's `config_fingerprint` resolves against a real
   `RunConfigLedger` entry (reuse H.4-F's resolvability discipline — do not invent a
   second one).
6. Vendor/foundation-native IDs never appear in a qualification record's persisted fields
   — only canonical `memory_id`s and the foundation's own `foundation_id` string label,
   consistent with the "vendor IDs are aliases" principle throughout this framework.

## 9. Adversarial cases to test

- A foundation that passes every fixture structurally but has `conformance_tag ==
  ENVIRONMENT_LIMITATION` (e.g. Letta with no server) — must still be `NOT_QUALIFIED`
  overall, since passing fixtures against a foundation whose CRUD never really ran is not
  meaningful evidence (§2's dependency, enforced as a hard invariant per §8 item 3).
- A fixture whose expected graph (computed via `metrics/provenance.py`) and reconstructed
  graph (via the canonical ledger) disagree on exactly one edge (e.g. a `conflicts_with`
  pair the foundation's own internal store silently dropped during round-tripping) — must
  be reported as a per-fixture failure with the specific disagreeing edge named, not a bare
  boolean.
- Two qualification runs for the same foundation with different `adapter_revision` values
  — both must be retained in `QualificationLedger` (it is a history, not a single current-
  state slot); `get_latest()` must return the most recently `qualified_at` one.
- A qualification attempt against a fixture set version that doesn't match any frozen
  manifest (§4) — must be rejected/flagged before the harness runs, not silently qualified
  against an undeclared, driftable fixture set.

## 10. Explicit non-scope for this stage

- Running the actual qualification campaign against Mem0/A-MEM/Graphiti/Letta and
  recording real results — this mission defines and builds the harness/gate machinery;
  actually invoking it (which requires the real libraries, per Phase 3.2-H.4's own
  `C:\h4venv` environment-isolation precedent) is a follow-up execution step, not part of
  building the mechanism. State clearly in the implementation report whether any real
  qualification run was actually performed or only the harness/gate code was built and
  unit-tested against mocks.
- Wiring `check_qualification_currency()` as a hard pre-flight block inside
  `campaign_formal_runner.py` — allowed but not required (§7).
- Running Graphiti's first baseline campaign — a separate, later action this gate exists to
  precede, not part of this mission.
- Initiatives A, E, G — untouched, unrelated.
- Re-litigating or modifying anything in Phase 3.2-H.4's own conformance results or tag
  definitions.

## 11. Deliverables checklist

- [ ] `QUALIFICATION_FIXTURE_MANIFEST.json` (or equivalent) freezing `fixture_set_version =
      "qualification_fixtures_v1"` over the exact current fixture files.
- [ ] `qualification_harness.py` (§5), tested against at least the mock adapters
      (`foundations/mocks/mock_*.py`) for correctness of the replay/compare logic itself,
      independent of whether a real qualification run was performed.
- [ ] `qualification_record.py` — `FoundationQualificationRecord` + `QualificationLedger`
      (§6).
- [ ] `check_qualification_currency()` (§7).
- [ ] New test file covering §8/§9.
- [ ] Full existing regression suite re-run with zero regressions.
- [ ] `PHASE3_3_H4_D_IMPLEMENTATION_REPORT.md` under `phase3/experiments/`, explicitly
      stating whether a real (non-mock) qualification run was performed and against which
      foundations.
- [ ] No modification to any file listed as frozen/existing-untouched in §3.

## 12. Definition of done

Complete when: the fixture set is frozen and versioned; the harness can replay a fixture
through an adapter (mock, minimum; real, if environment allows) and compare
canonical-ledger-reconstructed graphs against `metrics/provenance.py`/`equivalence.py`'s
own computed expectations; `FoundationQualificationRecord`/`QualificationLedger` exist and
enforce the CRUD-conformance-dependency invariant (§8 item 3); the currency checker exists;
all invariants and adversarial cases pass; regression suite shows zero regressions; the
report states real-vs-mock execution status honestly. Completion makes Graphiti's first
baseline campaign gate-able under this mechanism, per
[MEMORY_FOUNDATION_STRENGTHENING_PLAN_REVISED.md §9](MEMORY_FOUNDATION_STRENGTHENING_PLAN_REVISED.md).
