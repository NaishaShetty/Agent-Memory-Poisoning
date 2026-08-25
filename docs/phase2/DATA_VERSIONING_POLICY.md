# Data Versioning Policy (Task 4C)

## What Git tracks

- All code (`preprocessing/`, `tests/`, `config/`).
- All small metadata/manifests: `data/metadata/dataset_manifest.json`,
  `data/metadata/resource_registry.json`,
  `data/metadata/phase2_input_manifest.json`.
- All reports: `data/reports/*.json`.
- The two canonical, unique provenance logs:
  `data/logs/quarantine_log.jsonl`, `data/logs/removal_log.jsonl`.
- All documentation (`docs/`), `requirements.txt`, `pytest.ini`,
  `.gitignore` itself.

## What Git deliberately does not track

- `data/raw/` — the original acquired datasets. Excluded because: (a)
  several are large (Conversation Chronicles raw ≈ 1.7GB, LongMemEval raw
  ≈ 293MB, MSC ≈ 51MB), and (b) licensing is restrictive or unpublished
  for some of them (LoCoMo: CC BY-NC 4.0, non-commercial; MSC: license
  "unavailable / not explicitly published for the dataset itself" per
  `dataset_manifest.json`). Committing raw data would both bloat the
  repository and risk redistributing data under terms this project has
  not cleared.
- `data/interim/` and `data/processed/` — derived from raw data via a
  fully deterministic pipeline (`python -m preprocessing.run_all`, seed
  `20260101`); regenerable from `data/raw/` + the tracked code, so
  committing them would only duplicate what the pipeline already
  reproduces, at large size (`data/processed` ≈ 1.6GB).
- Timestamped per-run pipeline logs (`data/logs/run_all_*.log`) — one new
  file every run; ephemeral and regenerable, not a canonical provenance
  record (the canonical events are already captured in
  `quarantine_log.jsonl` / `removal_log.jsonl`, which are tracked).
- `data/generated/` — reserved for Phase 4+ benchmark/attack/sleeper
  output; does not exist yet.

## How excluded datasets remain identifiable and reproducible without being committed

For every raw dataset excluded from Git, `data/metadata/dataset_manifest.json`
(tracked) already records, per file:
- exact relative path,
- size in bytes,
- sha256 checksum (recomputed from disk at manifest-build time — an
  independent, verifiable identity, not a copied claim),

and per dataset:
- source URL,
- paper citation,
- version/revision (or an explicit `"unavailable"` where the upstream
  publisher provides none),
- license,
- acquisition date.

`config/pipeline_config.yaml` (tracked) records the exact list of raw
files each dataset expects and the deterministic seed used for sampling.

Given a fresh checkout of this Git repository, the reproduction procedure
is:
1. Acquire each raw file from the `source` URL recorded in
   `dataset_manifest.json`.
2. Verify its sha256 against the recorded checksum.
3. Run `python -m preprocessing.run_all` to regenerate
   `data/interim/`, `data/processed/`, and the metadata/report files
   (which will then be byte-identical to the tracked versions for any
   field that isn't a fresh timestamp, given deterministic IDs and the
   fixed seed).

This is the intended meaning of "dataset identity is tracked in Git even
though dataset content is not."

## Relationship between dataset snapshots and code commits

A dataset snapshot is identified by the tuple `(source URL, sha256 per
file, acquisition_date)` recorded in `dataset_manifest.json`. A code
state is identified by the Git commit that includes that version of
`dataset_manifest.json` (and the `preprocessing/` code that produced the
rest of the tracked outputs from it). Because `dataset_manifest.json`,
`resource_registry.json`, `phase2_input_manifest.json`, and all
`data/reports/*.json` files are tracked, **the Git commit hash is now the
missing code-state identifier** flagged as a gap in
`REPRODUCIBILITY_REPORT.md` (Phase 2.1) — see that document's update in
this remediation pass for the specific commit this applies to.
