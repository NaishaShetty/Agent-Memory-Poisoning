# Phase 3.3-H.4-D — First Real Qualification Run (Mem0) — Execution Report

Status: **COMPLETE**. This is an *execution* report, not an implementation report — no
code was written or modified. It records the first real (non-mock) run of the H.4-D
qualification harness (built and tested against mocks only), resolving hard blocker #7 of
[PHASE3_3_H4_READINESS_ASSESSMENT.md](PHASE3_3_H4_READINESS_ASSESSMENT.md) for Mem0
specifically, per that report's own punch-list item 2.

## 1. What was run, and how

`phase3/evaluation/foundations_real/qualification_record.py::run_foundation_qualification()`
— the existing, unmodified, mock-tested orchestrator — was invoked for real against
`RealMem0Adapter` under the `C:\h4venv` interpreter (the dedicated real-library
environment this project has used throughout, per Phase 3.2-H.4's own established
isolation convention), with `PYTHONPATH` pointed at the repo root.

No source file was changed to make this run possible — the mechanism built by H.4-D was
already complete and callable; this was purely an execution + observation task.

## 2. Steps and results

**Step 0 — fixture manifest verification.** `verify_fixture_manifest()` confirmed the
on-disk fixture set exactly matches the frozen
`QUALIFICATION_FIXTURE_MANIFEST.json` (`fixture_set_version = "qualification_fixtures_v1"`,
identical SHA-256 hash before and after). No drift.

**Step 1 — real conformance probe.** A fresh `RealMem0Adapter` was initialized, reset, and
exercised through `add_memory()`/`retrieve()` directly (not inferred, not assumed — the
mission's own requirement was to source `conformance_tag` from actual `RealConformanceRecord`
results, never invent one). Observed tags: `INITIALIZE`/`RESET`/`ADD_MEMORY`/`RETRIEVE` all
`REAL_FOUNDATION_CONFORMANCE`. One honest nuance worth recording: `retrieve()`'s
`FoundationField.availability` came back `PARTIAL`, not `AVAILABLE` — yet its underlying
conformance tag was still `REAL_FOUNDATION_CONFORMANCE`, which this framework's own
established vocabulary (Phase 3.2-H.4) treats as a legitimate, distinct signal: the real
library genuinely executed the operation; `PARTIAL` describes the result's own
completeness, not whether real code ran. `conformance_tag =
REAL_FOUNDATION_CONFORMANCE` was used, correctly, since `FoundationQualificationRecord
.__post_init__` requires exactly this value for any possibility of `overall_verdict ==
QUALIFIED` (H.4-D's own structural invariant).

**Step 2 — configuration record.** One `RunConfigRecord` was constructed and appended to a
real `RunConfigLedger` (`embedding_model="sentence-transformers/all-MiniLM-L6-v2"`,
`retrieval_k=5`, `adapter_revision="h4-real-v1"` from `foundation_identity()
.adapter_version`), giving `config_fingerprint =
CFG-eca65bd4e2ab06c28e18de522a712689f6bfe3dfc7c3eb363729b9bdf330a0e4`, resolvable and
referenced by the resulting qualification record (H.4-F's own invariant, exercised here for
the first time against a real run rather than a test).

**Step 3 — per-fixture replay, fresh foundation per fixture.** All **15 fixture bundles**
(`load_all_fixture_bundles()` groups the 22 frozen fixture *files* into 15 self-contained
*scenarios* — `conflicting_memory`/`derived_memory`/`equivalent_memory` each bundle 3 files,
`lineage/*` contributes its 12 files as 12 separate bundles: 3×3 + 12 = 21... — precise
grouping confirmed directly by the run's own printed count, "15 fixtures loaded"; treat that
as authoritative over any earlier informal file-count estimate). Each fixture was replayed
against a **freshly constructed** `RealMem0Adapter` with its own uniquely-named Mem0
collection, specifically to rule out one risk identified during preparation and not merely
assumed safe: several fixtures deliberately reuse the same `memory_id` for unrelated
scenario content (documented in `qualification_record.py`'s own docstring, for the
*canonical*-ledger side only) — a shared real Mem0 collection across fixtures could in
principle let one fixture's vendor-side state leak into another's, which canonical-ledger
isolation alone would not protect against. **Result: 15/15 fixtures passed**, zero
mismatches, zero unexplained replay errors.

**Step 4 — the official run, via the unmodified orchestrator.**
`run_foundation_qualification()` was also run exactly as built — a **single**
`RealMem0Adapter` instance shared across all 15 fixtures internally, per its own current
implementation (this was not altered to force fresh-per-fixture behavior, since that would
have meant testing something other than what actually ships). **Result: `overall_verdict =
QUALIFIED`, 15/15 fixtures passed.**

**Comparison.** The fresh-foundation-per-fixture run (Step 3) and the official
shared-foundation run (Step 4) were diffed fixture-by-fixture. **Zero divergences.** The
theoretical vendor-state-leakage risk identified during mission preparation did not
manifest in practice, for this fixture set, against Mem0 — empirically confirmed, not
assumed. This is recorded as a positive finding, not evidence the risk doesn't exist in
general (a fixture set exercising *more* memory-id reuse across scenarios could still
surface it) — worth keeping in mind if the fixture set is ever extended.

**Step 5 — persisted.** The official `FoundationQualificationRecord` was appended to a real
`QualificationLedger` at
`phase3/experiments/results/canonical_store/qualification/mem0/qualification_ledger/` —
append status `CREATED`. This is now an on-disk, real, first-of-its-kind qualification
record.

## 3. Result

```json
{
  "fixture_set_version": "qualification_fixtures_v1",
  "conformance_tag": "REAL_FOUNDATION_CONFORMANCE",
  "config_fingerprint": "CFG-eca65bd4e2ab06c28e18de522a712689f6bfe3dfc7c3eb363729b9bdf330a0e4",
  "adapter_revision": "h4-real-v1",
  "official_overall_verdict": "QUALIFIED",
  "official_per_fixture_pass_count": "15/15",
  "divergences": []
}
```

**Mem0 is now `QUALIFIED` under Initiative D's real gate — the first real qualification
record this framework has ever produced.**

## 4. Artifacts

All under `phase3/experiments/results/canonical_store/qualification/mem0/` (currently
untracked — a decision on whether to commit these as evidence, same open question as the
H.4-WIRE dry-run artifacts, is left to the user):

- `qualification_ledger/qualifications.jsonl` — the real, appended
  `FoundationQualificationRecord`.
- `run_config/run_configs.jsonl` — the real `RunConfigRecord`.
- `fixtures/<name>/{memory,events,supersessions}/` — 15 independent canonical-ledger
  triples, one per fixture, from the fresh-per-fixture comparison run.
- `official_run/<name>/{memory,events,supersessions}/` — 15 independent canonical-ledger
  triples from the official orchestrator run (the one whose record was actually persisted).
- `run_summary.json` — the machine-readable summary reproduced in §3.

## 5. What this does and does not change

This resolves hard blocker #7 (Foundation qualification integrity) **for Mem0 only** —
Graphiti, A-MEM, and Letta remain unqualified; each would need its own real run, and A-MEM/
Graphiti/Letta's own conformance tags (per Phase 3.2-H.4) are not all
`REAL_FOUNDATION_CONFORMANCE` for the operations that matter here, so they may not even be
eligible for a `QUALIFIED` verdict without further environment work (running services this
project has documented as deliberately not stood up — Neo4j/FalkorDB, Ollama, a Letta
server).

This does **not** by itself make any foundation/dataset pairing poisoning-eligible — per
the readiness assessment's own rule (§11.4 of the strengthening plan), eligibility for a
specific claim requires *every* capability that claim depends on to be qualified. Hard
blocker #5 (Initiative A, real counterfactual execution) is still unresolved for every
pairing, including Mem0 — that is the readiness assessment's punch-list item 3, not yet
attempted.

## 6. Freeze status

Not a frozen decision — a dated execution record. Re-run and re-verify if the fixture set,
the Mem0 adapter, or the qualification harness itself ever changes.
