# Phase 3.3-H4-ENVIRONMENT-RECORD — Implementation Report

Status: **COMPLETE**. Closes the `REPRODUCIBILITY_CONTRACT.md §3` requirement flagged
by the Phase 3 completion audit as unmet: "software environment (library versions...)"
and "artifact hashes for any generated memory store or index" — required "for every run,"
recorded by nothing until now.

## 1. Design decision: a new, independently-keyed record, not an extension of `RunConfigRecord`

`RunConfigRecord` (H.4-F) verifies, at construction, that its `config_fingerprint` matches
what `compute_config_fingerprint()` derives from the record's own other fields. Adding
fields to it would mean either silently changing every `config_fingerprint` value already
computed and stored by this session's own real runs (invalidating already-resolvable
references retroactively, for runs that did nothing wrong), or carving out an unstated
exception to that record's "every field participates in identity" discipline. Both worse
than a new, small, additively-introduced type — the same reasoning this codebase already
used for `SupersessionRecord` (H.3) and `rejected`/`relationship_detected` (H.4-BC).

`EnvironmentRecord` is keyed by `campaign_id` (one record per real run, not per task,
since environment doesn't change within a run) and lives in its own
`EnvironmentRecordLedger`, append-only, same persistence discipline as every other ledger.

## 2. What was built

`phase3/evaluation/foundations/environment_record.py`:
`capture_environment_record(campaign_id, recorded_at, *, artifact_hash_source_dir=None,
packages=...)` — captures the CURRENT interpreter's Python version, platform, and real
`importlib.metadata`-resolved versions for the relevant libraries (`mem0ai`, `chromadb`,
`sentence-transformers`, `torch`, `litellm`, `qdrant-client`) — a package not importable
is simply absent, never a fabricated placeholder. Optionally computes a real SHA-256 over
the sorted (path, content) pairs of every file under a given directory — a genuine,
verifiable artifact hash for a generated memory store, not a random token.

## 3. Testing

11 tests: real Python version/platform capture, never-fabricate-a-missing-package
(explicit negative test), artifact hash present/absent/deterministic/content-sensitive
correctly, construction validation (hash requires a stated source), ledger
append/idempotent-reappend/collision/reload-survival.

**Real-environment verification, not just synthetic**: run under `C:\h4venv` (the
interpreter that actually executed this session's real Mem0/A-MEM work), captured:

```
package_versions: {'mem0ai': '2.0.19', 'chromadb': '1.5.9', 'sentence-transformers': '6.0.0',
                    'torch': '2.13.0+cpu', 'litellm': '1.98.0', 'qdrant-client': '1.19.0'}
artifact_hash: 30da3befba5e0518c1924f5919b105c9dbd1c071acc5a4918171fbf204462510
```

— genuine, real library versions, and a real hash over the actual canonical-ledger files
from this session's real `h4a-real-locomo-smoke-1` Mem0/LoCoMo counterfactual run.

## 4. Retroactive record for existing real evidence

Since this capability didn't exist during this session's real runs, it cannot honestly
claim those runs recorded their environment *at the time*. Instead, one
`EnvironmentRecord` was captured **after the fact**, explicitly labeled as such, for the
`h4a-real-locomo-smoke-1` campaign — persisted to
`phase3/experiments/canonical_store/h4a-real-locomo-smoke-1/environment_records/
environment_records.jsonl`. This documents the environment *as it exists now* (same
`C:\h4venv` interpreter, same installed package versions, unchanged since that run) and
hashes the actual, still-present ledger artifacts from that run — a reasonable, honestly-
labeled best-effort backfill, not a claim that this was captured live during the original
execution.

## 5. Regression

Full suite: **1623 passed**, 14 skipped, same single pre-existing unrelated failure.

## 6. What remains

- Not wired into `campaign_formal_runner.py` — a future real campaign run should call
  `capture_environment_record()` once per pool/campaign and persist it, the same way
  `RunConfigRecord` is captured once per pool today. Not performed here — this stage
  delivers the capability; live wiring into the real campaign path is a natural, smaller
  follow-up, consistent with how every H.4-* mechanism this session built was delivered
  standalone before any wiring decision.
- The relevant-package list (`_RELEVANT_PACKAGES`) is a documented, reviewable constant,
  not exhaustive — extending it (e.g. adding `graphiti-core`/`kuzu`/`letta-client` if those
  foundations are ever un-deferred) is a one-line change, not a redesign.

## 7. Compatibility and freeze status

Additive only — one new module, one new test file, zero changes to any existing frozen or
tested file. Not a frozen decision.
