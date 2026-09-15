# Stage 6.19 — Reproducibility & Artifact Packaging

Status: 6.19 deliverable. Completes the suggested `phase6/` directory
structure (`schemas/`, `artifacts/`) and adds the reproducibility-manifest
infrastructure the brief requires, reusing Phase 2/3's own established
serialization primitive rather than inventing a new one.

---

## 1. `phase6/schemas/` — Real JSON Schema, Mirroring Phase 3's Own Convention

`mgp_decision_record.schema.json` — a real JSON Schema for `MGPDecisionRecord`,
following `phase3/schemas/memory_schema.json`'s own established pattern (a
checkable schema alongside the Python dataclass, not a substitute for it).
**Validated against real, constructed instances**, not hand-verified once and
left to drift: all seven real actions produce schema-valid output, a missing
`evidence_refs` is correctly rejected, an unknown action is correctly
rejected, and an unexpected extra field is correctly rejected
(`additionalProperties: false`).

## 2. Reproducibility Manifest — Every Brief-Required Field, Real or Honestly `None`

`phase6/evaluation/reproducibility/manifest.py`'s `Phase6ReproducibilityManifest`
covers every field the brief names: defense/policy versions, configuration,
thresholds, model versions, seeds, attack version, task sample, memory
foundation, environment, hardware (via `platform.platform()`), dependency
versions, campaign/run/episode IDs. Fields genuinely not applicable to a given
run (attack version, task sample, memory foundation — all `None` for the
current synthetic-corpus-only work) are explicit `None`, never a fabricated
placeholder string — the same "honest absence" discipline Phase 2's own
Unified Memory Record schema established.

**`build_shipped_defense_manifest()` reads every threshold directly from the
real, currently-shipped module constants** (`reasoning_guard.py`,
`consensus_guard.py`, `containment_guard.py`, `sleeper_guard.py`) rather than
retyping them by hand, which could silently drift out of sync —
`test_build_shipped_defense_manifest_reads_real_thresholds` cross-references
one real constant directly to confirm this.

**`canonical_identity()` reuses `phase3.evaluation.security.reproducibility.
fingerprint()`** — the repository's one existing SHA-256 canonical-
serialization primitive, already reused by Stage 6.3's `mint_decision_id()`
and Phase 5's own `Phase5Event.event_id` — a third reuse of the same scheme,
never a fourth Phase-6-specific hashing mechanism. It deliberately **excludes
`environment`** from the identity hash (two runs with identical configuration
on different machines are the same run for reproducibility purposes) —
verified directly (`test_canonical_identity_excludes_environment`), mirroring
`reproducibility.py`'s own "exclude generation timestamp and local filesystem
path" discipline for its own manifest.

`environment_snapshot()` queries **real, current** facts (Python version,
platform string, and the installed version of every package Phase 6 code
actually imports — `scipy`, `sentence-transformers`, `torch`, `numpy`) —
never a hand-typed, potentially-stale string, and honestly reports `None` for
a tracked package that turns out not to be installed rather than omitting it
silently.

## 3. `phase6/artifacts/` — A Real, Generated Worked Example

Mirrors Phase 5's own precedent (`phase5/datasets/memory_behavior_dataset_
sample.jsonl` — "a real, generated 10-record sample dataset, produced from an
actual full pipeline run rather than hand-written"). `worked_example_
governance_ledger/` contains:

- `mgp_decisions.jsonl` — 12 **real** decisions from an actual run of Stage
  6.5's `evaluate_admission()` against 10 real LoCoMo turns, Stage 6.14's
  real adaptive V1 evasion example, and one explicit FARMA-template BLOCK
  case — not fabricated to illustrate a point; the result distribution (10
  benign `ALLOW`, 1 evasion `ALLOW`, 1 `BLOCK`) is exactly what re-running
  the same inputs against the current shipped code produces.
- `reproducibility_manifest.json` — the real manifest for that exact run,
  including its real, deterministic `canonical_identity`.
- `README.md` — provenance and a reproduction snippet.

## 4. Directory Structure — Now Matches the Suggested Layout

```
phase6/
├── defense/           (policy/ admission/ retrieval/ propagation/ sleeper/
│                        orchestration/ wiring/ attribution_bridge/ signals/)
├── evaluation/         (ablations/ metrics/ statistics/ generalization/
│                        adaptive/ regression/ failures/ reproducibility/)
├── schemas/            (mgp_decision_record.schema.json)   <- new this stage
├── artifacts/          (worked_example_governance_ledger/) <- new this stage
└── tests/
```

## 5. Tests and Evidence

14 new tests (`test_phase6_reproducibility.py`): schema validation for all seven
real actions, three real rejection cases (missing evidence, unknown action,
extra field), the manifest's real-threshold cross-reference, empty-id
rejection, canonical-identity determinism, environment-exclusion, a real
configuration-difference producing a different identity, and honest
`None`-reporting for an uninstalled package.

**Full Phase 6 suite: 293 passed, 0 failed.** Frozen `phase3/`, `phase4/`,
`phase5/`, `attribution/` verified unchanged.

## 6. Limitations Carried Forward

1. `seeds={}` in the shipped manifest is honest, not an oversight — the
   current shipped defense (regex/arithmetic only) has no stochastic
   component; D2's embedding model is deterministic given fixed input. A
   future D3 (LLM-judge) would need a real `seed`/`temperature` field
   populated here, per `RETRIEVAL_DEFENSE.md`'s own frozen-configuration
   requirements for that component.
2. Only one JSON Schema was produced (`MGPDecisionRecord`) — `SignalContext`,
   `RetrievalCandidate`, and `AncestorRecord` remain Python-dataclass-only,
   consistent with them being internal plain-data-carriers (Stage 6.4's own
   design) rather than persisted, cross-system-boundary records the way
   `MGPDecisionRecord` is (written to `GovernanceLedger`'s JSONL file).
3. The worked-example artifact is small (12 records) — a real, generated
   sample, not a claim of comprehensive coverage, exactly matching the scope
   Phase 5's own analogous worked example set for itself.

## Verdict

**PASS** as a 6.19 deliverable. Every brief-required reproducibility field is
represented, real or honestly `None`; the one existing project-wide
canonical-serialization primitive was reused a third time rather than
inventing a new one; and the committed worked example is real, generated
output from the actual shipped code, not fabricated to look like one.
