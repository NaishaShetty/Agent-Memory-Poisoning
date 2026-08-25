# Phase 2.6 — Benchmark-Substrate Validation

## 1. Why Phase 2.6 exists

Phases 2.2 through 2.5 each built and validated exactly one layer of the
Phase 2 benchmark substrate:

- 2.2 — the Unified Memory Record (UMR)
- 2.3 — temporal normalization
- 2.4 — resource organization by benchmark role
- 2.5 — reproducibility metadata (canonical/artifact identity)

Each of those validators is, by construction, blind to the other three —
`unified_validation.py` never asks whether the temporal policy version it
reports matches the one `temporal.py` actually used; `reproducibility_validation.py`
never asks whether `benchmark_resources.json` and `reproducibility_manifest.json`
agree on a given resource's `phase2_status`. Phase 2.6 is the layer that
asks those cross-layer questions, and is the final gate before Phase 2 is
declared frozen (Phase 2.7).

## 2. Component validation vs. cross-phase validation

**Component validation** (Phases 2.2–2.5's own validators) asks: *is this
one layer internally correct?* Phase 2.6 does not re-implement or replace
any of that logic — it re-runs each real validator fresh and trusts its
verdict.

**Cross-phase validation** (Phase 2.6) asks a different question: *do the
four layers, once you already trust each is individually correct, agree
with each other, and does the resulting whole meet the substrate-level
invariants that only make sense once all four layers exist* — e.g. "is the
UMR schema version the same string in `unified_schema.py`, in
`benchmark_resources.json`'s `umr_integrity`, and in
`reproducibility_manifest.json`'s `schema_and_policy_versions`?" No single
earlier validator could ask that question, because no single earlier
validator reads all three of those documents at once.

## 3. Validation architecture

`preprocessing/benchmark_substrate_validation.py` exposes
`validate_benchmark_substrate(cfg, generated_at)` → a report with 29 named
checks, each tagged with a `scope`:

- `"full_corpus"` — the check's evidence comes from a validator that
  actually streamed the full 1,266,194-record corpus this run (not from a
  cached report).
- `"targeted_sample"` — the check's evidence is a deliberately bounded
  sample (see Section 16 below), never claimed as full-corpus coverage.
- `"artifact"` — the check compares already-materialized JSON manifests
  (registry, phase2 manifest, benchmark organization, reproducibility
  manifest) with no corpus scan at all.

`write_benchmark_substrate_validation_report()` writes
`data/reports/phase2_6_benchmark_substrate_validation_report.json`.

## 4. Memory foundation validation (Domain 1)

Confirms `LoCoMo` / `LongMemEval` / `MSC` / `Conversation Chronicles` are
exactly the `memory`-role resource set (no extra dataset silently
included, none missing), and that their record counts — 5,882 / 210,365 /
227,185 / 822,762, total 1,266,194 — agree across three independent
sources computed this run: a **fresh** call to Phase 2.2's own validator
(`validate_cross_dataset`, which streams the real corpus), the benchmark-
organization layer's `umr_integrity` block, and the reproducibility
manifest's `record_counts` block. All three must match each other and the
established expected values — not just the metadata's own self-report.

## 5. UMR validation (Domain 2)

Confirms `unified_schema.SCHEMA_VERSION`, `benchmark_resources.json`'s
`umr_integrity.umr_schema_version`, and `reproducibility_manifest.json`'s
`schema_and_policy_versions.unified_memory_record_schema_version` are the
identical string (`"1.1.0"`), and that a fresh re-run of Phase 2.2's
validator (`validate_cross_dataset`) still reports `PASS` — covering
required fields, field types, and field-status semantics, since that
validator already checks all of those.

## 6. Temporal validation (Domain 5/6)

Confirms a fresh re-run of Phase 2.3's validator (`validate_temporal`)
still reports `PASS`, and adds one cross-check that validator has no
reason to make itself: that the **source-absolute vs. source-relative
split observed in the live corpus** matches each dataset's own documented
temporal signal (`preprocessing/temporal.py`'s `TEMPORAL_POLICY`) — LoCoMo
and LongMemEval must show `source_absolute` records (they have real
calendar timestamps), while MSC and Conversation Chronicles must show
**zero** `source_absolute` records (they never claim one). This directly
guards against the fabrication failure mode the temporal-normalization
design exists to prevent.

## 7. Resource organization validation (Domain 7)

Confirms a fresh re-run of Phase 2.4's validator
(`validate_benchmark_organization`) still reports `PASS`, that the role
counts are exactly `{memory: 4, workload: 9, attack: 6, sleeper: 2,
evaluation: 7}`, and that the memory-foundation boundary is enforced in
both directions (no non-memory-role resource is in the foundation set, and
every foundation resource is classified `memory`).

## 8. Reproducibility validation (Domain 10)

Confirms every one of the 28 resources in `reproducibility_manifest.json`
carries a `canonical_identity`, `canonical_identity_hash`, and
`artifact_identity` block, and that a fresh re-run of Phase 2.5's own
validator (`validate_reproducibility_manifest`) still reports `PASS` — which
itself re-runs Phase 2.2, 2.3, and 2.4's validators internally (see
Section 16, Performance).

## 9. Cross-manifest validation (Domain 11)

The single most Phase-2.6-specific check: the same `resource_id` set must
appear in `resource_registry.json`, `phase2_input_manifest.json`,
`benchmark_resources.json`, and `reproducibility_manifest.json` — and for
every resource, `primary_role`, `source_reference`, `phase2_status`, and
`phase2_input_approved` must be identical between the organization layer
and the reproducibility layer (the two layers most likely to drift, since
they're built independently on different runs). Where two manifests
express the same fact, `benchmark_resources.json` (Phase 2.4's output) is
treated as authoritative and every other layer is checked against it — no
new, independent source of truth is introduced.

## 10. Version consistency (Domain 12)

For each of `umr_schema`, `temporal_policy`, and
`benchmark_organization_version`, every layer that states a copy of that
version is read and compared; a single dictionary of `{source_name: value}`
per version is included in the check's `detail` so a mismatch immediately
shows which layer drifted, rather than only reporting pass/fail.

## 11. Record-count consistency (Domain 13)

`benchmark_resources.json`'s `umr_integrity.umr_total_records`,
`reproducibility_manifest.json`'s `record_counts.umr_total_records`, and a
**freshly streamed** `validate_cross_dataset(cfg)["total_records"]` must
all equal 1,266,194. A metadata layer merely repeating a stale number
without a fresh corpus check backing it up is exactly the failure mode
this domain exists to catch.

## 12. Provenance validation (Domain 4)

For the memory foundation, confirms each dataset's `phase2_input_manifest.json`
entry states its provenance dataclass was populated and validated (the
Phase 1/2.2 provenance chain). For all 28 resources, confirms
`benchmark_resources.json`'s per-resource `source_reference` and
`provenance.{source, mambench_created}` fields are non-empty — the same
invariant Phase 2.4's own test suite checks, re-verified here as part of
the substrate-wide gate rather than assumed carried forward.

## 13. Data integrity validation (Domain 14/19)

Two checks, neither a full-corpus rehash:

1. **Targeted raw-file checksums** — every raw file listed in
   `dataset_manifest.json` under 5 MiB (LoCoMo's ~2.8MB JSON, each
   dataset's small README/LICENSE files) is re-hashed and compared
   against its recorded sha256. Files above that threshold (LongMemEval's
   ~277MB, Conversation Chronicles' ~1.3GB) are checked by file size only
   — `dataset_manifest.json`'s own sha256, computed once at acquisition
   time, already covers full-content integrity for those; Phase 2.6 does
   not re-hash hundreds of megabytes on every run. Both outcomes
   (rehashed vs. size-only) are recorded explicitly in the check's
   `detail`, never blurred into one "checked" claim.
2. **Frozen-output mtime stability** — confirms that simply calling every
   Phase 2 builder function again does not touch a representative sample
   of Phase 1/2.2 frozen output files (mtime and size unchanged).

## 14. Experimental activation boundary (Domain 19)

Explicitly re-verifies that no `attack`- or `sleeper`-role resource has
`phase2_input_approved: true` — Phase 2 organizing/registering a resource
is never the same claim as that resource being experimentally activated.
`DSRM` is checked by name (Domain 8): its role must be `attack`, its
implementation status must remain
`specification_only_no_public_implementation_found`, and it must not carry
a local path or approval flag — the canonical example the implementation
prompt names for this boundary.

## 15. Phase boundary (Domain 18)

`_scan_forbidden_definitions()` scans every `.py` file under
`preprocessing/` for a `def`/`class` whose name contains one of:
`poison, attack, sleeper, propagat*, lifecycle, defense/defence, mitigat*,
contain*, attribut*, gnn, gln`. A raw keyword grep over the whole codebase
would flag dozens of legitimate occurrences (role-name constants like
`ROLE_ATTACK`, reserved-null schema fields like `poison_status`, and
registry entries that *describe* external attack papers as data, not
code) — Phase 2.6 instead checks specifically for an actual function or
class *definition* implementing forbidden semantics, which is the signal
that actually distinguishes "documented as a future resource" from
"implemented." Zero such definitions currently exist anywhere in
`preprocessing/`.

## 16. Performance strategy

The real corpus contains 1,266,194 records, and each of Phase 2.2's and
2.3's validators streams it once per invocation. Phase 2.6 calls:

- `validate_cross_dataset(cfg)` — once, directly, for Domain 2/3's
  per-check detail (the actual collision list).
- `validate_temporal(cfg)` — once, directly, for Domain 5/6's per-check
  detail (the per-dataset temporal-provenance distribution).
- `validate_benchmark_organization(cfg, generated_at)` — once, directly,
  for Domain 7/23; this call itself re-runs `validate_cross_dataset` and
  `validate_temporal` internally (Phase 2.4's own existing design, not
  something Phase 2.6 introduces).
- `validate_reproducibility_manifest(cfg, generated_at)` — once, for
  Domain 10/24; this call itself re-runs `validate_benchmark_organization`
  internally (Phase 2.5's own existing design).

The net effect is a small, deliberate amount of duplicate full-corpus
scanning — the same pattern Phase 2.4 and 2.5 already established, not a
new inefficiency Phase 2.6 introduces — in exchange for genuinely fresh,
per-check detail at every layer. Every other Phase 2.6 check reads
already-materialized JSON manifests (registry, phase2 manifest, benchmark
organization, reproducibility manifest), which involve no corpus
iteration at all. The raw-file integrity check is explicitly bounded (see
Section 13) rather than a full re-hash of gigabytes of raw data.

## 17. Limitations

- The same pre-existing gaps Phase 2.5 already documented remain
  unresolved by Phase 2.6 (dependency-lock absence, `WorkloadRecord`'s
  missing schema version constant, several resources' genuinely-unknown
  source versions) — Phase 2.6 does not attempt to fix them, only
  confirms they remain honestly represented (`"unknown"`, not guessed).
- Domain 20 (Phase 2 component completeness) checks for a fixed list of
  expected metadata/report/doc files; a legitimately-renamed artifact
  would show as "missing" even if replaced by an equivalent file under a
  new name — this is a deliberate simplicity trade-off for a checklist
  that changes rarely, not a hidden false-positive risk in practice.
- The targeted raw-file checksum check (Section 13) does not re-verify
  the content of files above 5 MiB; it inherits `dataset_manifest.json`'s
  original sha256 as the authoritative integrity claim for those, verified
  only by file size on each Phase 2.6 run.

## 18. What Phase 2.6 does not implement

Per the implementation prompt: Phase 2.6 creates no new dataset, redesigns
no UMR field, reorganizes no resource, and implements no attack execution,
poisoning, propagation, lifecycle graph, sleeper generation/detection,
defense, mitigation, containment, attack-origin attribution, GNN/GLN
analysis, or agent execution. It is validation only — every finding is
reported in `data/reports/phase2_6_benchmark_substrate_validation_report.json`,
never silently repaired by mutating data, weakening a check, or changing
an expected value.
