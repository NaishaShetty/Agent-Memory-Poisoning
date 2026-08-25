# Phase 2.1 Reproducibility Report (Tasks 7 & 8)

> **Update, Phase 2.1-R (Part 4):** the code-state-identity gap described
> below is now closed. A local git repository was initialized and the
> verified Phase 1 + Phase 2.1 state was committed as baseline
> `4792a3a458500435f3913f1b600aeacfc02a92a3` ("Baseline: Phase 1 (PASS
> WITH ISSUES) + Phase 2.1 freeze/registration"). The Phase 2.1-R
> remediation work (this document included) is committed on top of that
> baseline — see `git log` for the current `HEAD` commit hash, which is
> the code-state identifier for everything this report describes as of
> Phase 2.1-R. The table row below is kept for historical accuracy (this
> is what Phase 2.1 actually had) and marked resolved rather than
> rewritten. See `docs/phase2/DATA_VERSIONING_POLICY.md` for what Git
> tracks vs. excludes, and the "Phase 2.1-R — Remediation" section of
> `MAMBench Process Documentation.docx` for the full remediation record.

## What is captured today

| Identity element | Captured? | Where | Mechanism |
|---|---|---|---|
| Raw file integrity | Yes | `data/metadata/dataset_manifest.json` (`files[].sha256`) | Recomputed from disk at manifest-build time, not copied from an external source |
| Source version/revision | Partial | `dataset_manifest.json` (`version_or_revision`) | Publisher-stated where one exists (e.g. MSC `v0.1`); explicitly `"unavailable"` where the upstream source has no version tag or commit pin (LoCoMo, LongMemEval, Conversation Chronicles) — stated as a gap, not guessed |
| Master seed | Yes | `config/pipeline_config.yaml` (`seed: 20260101`) | Used for Conversation Chronicles' deterministic reservoir sample; the only randomness in the pipeline |
| Deterministic record IDs | Yes | `preprocessing/io_utils.py: deterministic_id()` | sha256 over the ordered provenance-chain tuple; same source record always yields the same ID across runs (confirmed by the `unique_memory_ids` / `no_cross_dataset_id_collision` PASS checks in `phase1_validation_report.json`) |
| Preprocessing pipeline version | Yes | `preprocessing/__init__.py: PIPELINE_VERSION = "1.0.0"` | Stamped into every record's `provenance.extraction_pipeline_version` and every removal/quarantine event |
| Manifest/registry schema version | Yes | `manifest_version` / `registry_version` = `"1.0.0"` | Hardcoded string literals, independent of `PIPELINE_VERSION` |
| Configuration used | Yes | `data/logs/run_all_<ts>.log` header | Logs the exact config path and seed for the run |
| Schema version (record shape) | Implicit | `preprocessing/schema.py`, `schema_workload.py` | Not independently versioned from `PIPELINE_VERSION`; a schema change and a logic-only change would bump the same string |
| Dependency/environment pinning | Weak | `requirements.txt` | `>=` ranges (`PyYAML>=6.0`, `pytest>=7.0`, `pyarrow>=14.0`), no lockfile, no captured `pip freeze` |
| Code-state identity | **Yes (as of Phase 2.1-R)** | local git repository, `git log` | Was: no git repository existed (Phase 1 / Phase 2.1). Resolved in Phase 2.1-R Part 4: local git initialized, baseline commit `4792a3a4...` recorded, `.gitignore` scoped per `DATA_VERSIONING_POLICY.md`. A dependency-lock hash (`requirements.txt` still uses `>=` ranges) remains unresolved — see below. |
| Phase 2 manifest generation | Yes | `preprocessing/phase2_manifest.py`, `data/metadata/phase2_input_manifest.json` | New in Phase 2.1: deterministic given fixed inputs, verified by `tests/test_phase2_boundary.py::test_manifest_generation_is_deterministic_given_fixed_timestamp` |

## What "reproducible" means for this project today

Re-running `python -m preprocessing.run_all` against the *same* raw files
and the *same* code would deterministically reproduce:
- identical `memory_id`/`task_id` values (content-derived hashing, not
  random), and
- identical Conversation Chronicles sampling (seeded reservoir sample).

This was not re-verified by an actual second full pipeline run in Phase
2.1 (Task 8 explicitly says not to perform expensive full reprocessing
unless necessary) — it is verified **by code inspection and by the
`deterministic_id` unit tests in `tests/test_io_utils.py`**, which is a
weaker form of evidence than an actual repeated run. This distinction
(inspected vs. tested vs. actually re-run) is recorded here rather than
blurred.

## The reproducibility gap: no code-state identity (Phase 1 / Phase 2.1 — RESOLVED in Phase 2.1-R)

**As of Phase 1/2.1, nothing in this repository tied "this exact
processed output" to "this exact preprocessing code + dependency
state."** `PIPELINE_VERSION` is a manually-maintained string, not derived
from anything. Concretely: someone could have edited
`preprocessing/datasets/locomo.py`, re-run the pipeline, and produced
different `data/processed/locomo/*` output while `PIPELINE_VERSION`
still read `"1.0.0"` — nothing would have flagged the mismatch.

**Root cause:** no VCS was in use for this project. **Resolved in Phase
2.1-R, Part 4:** a local git repository is now initialized, with the
verified Phase 1 + Phase 2.1 state committed as baseline
`4792a3a458500435f3913f1b600aeacfc02a92a3`, and every subsequent
remediation change committed on top of it. Anyone can now answer "which
exact code produced this data?" by checking out the commit that matches
a given `data/metadata/*.json`'s content, or, going forward, by
recording the commit hash a given experiment run was performed under.

This closes the code-state half of the gap. Two related items remain
open, deliberately not addressed by this remediation (kept in scope):

1. **No automatic stamping.** The commit hash is not yet automatically
   written into `PIPELINE_VERSION` or any generated report — a future
   `run_all.py` invocation would need to record `git rev-parse HEAD` (and
   a "dirty" flag for uncommitted changes) itself for this to be
   fully automatic rather than something a human checks manually via
   `git log`. This is a natural Phase 2.2+ enhancement, not required for
   the Phase 2.1-R freeze boundary itself.
2. **Dependency-lock hash.** `requirements.txt` still uses `>=` ranges;
   no lockfile or captured `pip freeze` exists. See below.

**No GitHub or other remote was created.** This is a local-only git
repository, per explicit instruction; publication remains a separate,
future decision.

## Minor cosmetic finding (not a data-integrity issue)

`run_all_2026-08-12T165458Z.log`'s own `asctime` lines use local system
time (`22:24:58`–`22:26:44`), while every emitted record/log entry's
`run_timestamp` field is UTC (`2026-08-12T16:54:58Z`, matching the log
filename). The value actually persisted in data is the UTC one; only the
human-readable log line uses local time. Documented here so a future
reader isn't confused by the two-timestamp appearance, but this does not
affect reproducibility or provenance.

## Recommendation for later phases (not implemented in 2.1-R — out of scope)

Version control now exists (Phase 2.1-R). Two items remain for later
phases: (1) have `run_all.py` stamp the current commit hash (and a
"dirty" flag) into `PIPELINE_VERSION` or a sibling field automatically,
and (2) pin `requirements.txt` exactly or add a lockfile. Both are
natural Phase 2.2+ or general project-hygiene items, not Phase 2.1-R
freeze-boundary items — recorded here as known limitations rather than
silently fixed.
