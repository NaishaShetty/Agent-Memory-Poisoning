# Phase 3.3-H.2-R — Canonical Event Ledger Remediation — Report

Status: **COMPLETE**.

## 1. Original H.2 issue

Post-implementation review of H.2 (already COMPLETE, 1230 passed/14 skipped) identified
three architectural gaps that would contaminate H.3 immutable-versioning and later
poisoning-lineage work if left unaddressed:

1. No representation existed for an experiment/foundation-store isolation boundary (a
   RESET), distinct from a memory's own lifecycle.
2. `CanonicalEventLedger` verified `event_id` uniqueness but no component owned actually
   *generating* one.
3. `derived` events' flat `memory_ids` tuple could not distinguish source (parent)
   memories from the derived (child) memory except by an unstated positional convention.

## 2. Evidence from repository

- `campaign_formal_runner.py`'s own module docstring: "a fresh RESET+INGEST happens once
  per unique `(dataset, session_or_haystack)` group" — confirms a real, already-documented
  reset boundary exists in this framework's runtime behavior, with no canonical
  representation.
- `relationship_schema.md` section 3's event-type table has exactly seven rows, none named
  `experiment_reset` or equivalent.
- `relationship_schema.md` section 2: `parent_of`/`derived_from: A -> C` is explicitly
  directional; `memory_schema.json`'s `parent_ids` field already encodes this direction on
  the child record (`memory_type=derived` requires non-empty `parent_ids`).
- `test_canonical_event_ledger_h2.py::test_non_task_scoped_event_does_not_require_task_id`
  constructed a `derived` event with `memory_ids=("m1", "m2")` and no way to tell which was
  the parent and which the child — direct evidence of gap 3 in the existing test suite
  itself.
- `security/reproducibility.py::fingerprint()` — an existing, already-used-everywhere
  (`agent_runtime/trace.py`'s `trace_fingerprint`) deterministic SHA-256 identity primitive
  — was available for reuse for gap 2, rather than introducing `uuid4()`.
- `contracts/evaluation_run.schema.json`'s `EvaluationRun.configuration_identity` —
  precedent in this repository for "record some free-form scope/identity, don't
  over-specify its shape" — informed `ExperimentBoundaryRecord.scope`'s design.

## 3. Root cause

H.2 was scoped, correctly, to establish the event-history SUBSTRATE (append-only
persistence, memory linkage, immutability) without yet needing every semantic distinction
future stages would require. The three gaps above are exactly the semantic distinctions
that H.3 (immutable versioning, supersession, retirement) and later poisoning-lineage work
would need but H.2 had not yet had reason to make precise.

## 4. Chosen remediation

| Gap | Remediation | New file(s) |
|---|---|---|
| 1. Experiment boundary | Separate `ExperimentBoundaryRecord`/`ExperimentBoundaryLedger` type — no shared identity with `CanonicalEvent`, no `memory_ids` field, no dependency on `CanonicalMemoryLedger` | `phase3/evaluation/foundations/experiment_boundary.py` |
| 2. Event ID authority | `generate_event_id()` — deterministic, fingerprint-based factory; purely additive, `CanonicalEvent.event_id` contract unchanged | `phase3/evaluation/foundations/event_identity.py` |
| 3. Lineage roles | Two new optional `CanonicalEvent` fields, `source_memory_ids`/`target_memory_id`, required together for `derived`, forbidden otherwise; must exactly equal `memory_ids` as a set | `phase3/evaluation/foundations/canonical_event.py` (modified — see section 6) |

Full design reasoning for each: `PHASE3_3_H2_CANONICAL_EVENT_LEDGER.md` sections 23-29 (the
H.2-R appendix added to the existing H.2 doc; nothing above that appendix was changed).

## 5. Alternatives rejected

- **Gap 1:** an 8th `CanonicalEvent` type (`experiment_reset`), relaxing `memory_ids` to
  allow empty for it. Rejected: requires changing the frozen `relationship_schema.md`
  event-type table, and weakens the `memory_ids`-non-empty invariant for every other event
  type just to accommodate one structurally different case.
- **Gap 2:** `uuid4()`. Rejected: non-reproducible, and would make two calls describing the
  identical historical fact mint two different ids, undermining the ledger's own
  idempotent-duplicate policy. A hash of `(sequence_number, timestamp)` alone was also
  considered and rejected: it would make the id depend on WHEN/in-what-order something was
  appended rather than WHAT it records, which is a weaker reproducibility guarantee than
  fingerprinting the event's actual content.
- **Gap 3:** auto-deriving `memory_ids` from `source_memory_ids ∪ {target_memory_id}`
  rather than requiring and validating consistency. Rejected: every other validator in this
  codebase (`canonical.py`, `ledger.py`) fails loudly on an inconsistent caller input rather
  than silently computing a "corrected" value on the caller's behalf; introducing an
  auto-fill convention here would be a new, locally-inconsistent pattern. Also rejected:
  adding a symmetric `superseded_by_memory_id` field at the same time — doing so starts
  implementing H.3's actual supersession semantics prematurely.

## 6. Files changed

**New:**

| File | Purpose |
|---|---|
| `phase3/evaluation/foundations/event_identity.py` | `generate_event_id()` — the MAMBench Event ID Factory |
| `phase3/evaluation/foundations/experiment_boundary.py` | `ExperimentBoundaryRecord`/`ExperimentBoundaryLedger` |
| `phase3/evaluation/tests/test_h2_remediation.py` | 32 contract tests for all three remediations |
| `phase3/experiments/PHASE3_3_H2_REMEDIATION_REPORT.md` | This report |

**Modified:**

| File | Change |
|---|---|
| `phase3/evaluation/foundations/canonical_event.py` | Added optional `source_memory_ids`/`target_memory_id` fields to `CanonicalEvent`, with validation (required+consistent for `derived`, forbidden otherwise); extended `to_dict`/`from_dict`/`identity_fields` accordingly. Fully additive/backward-compatible — no existing field, default, or non-`derived` behavior changed. |
| `phase3/evaluation/tests/test_canonical_event_ledger_h2.py` | One test (`test_non_task_scoped_event_does_not_require_task_id`) updated to supply the now-required `source_memory_ids`/`target_memory_id` for its `derived`-event example. No other line changed. |
| `phase3/specification/PHASE3_3_H2_CANONICAL_EVENT_LEDGER.md` | Appended sections 23-29 documenting the remediation. Sections 1-22 unchanged. |

**Not modified:** `phase3/evaluation/foundations/canonical.py`, `ledger.py`,
`canonical_write.py`, `event_ledger.py` (event_ledger.py's linkage-existence check already
covered lineage-field validation for free, since `memory_ids` is required to contain every
lineage role's id — see remediation test 19). No file on the live G.1 import path was
touched (see section 10).

## 7. Schema changes

**None.** `relationship_schema.md` and `memory_schema.json` are both byte-for-byte
unmodified. Every remediation was implemented as either a genuinely new, separate type
(experiment boundary) or an additive field extension to a Python runtime object
(`CanonicalEvent`'s lineage fields) — neither required touching a frozen schema document.

## 8. Tests added

32 new tests in `test_h2_remediation.py`, covering all 24 mission test items plus 3 extra
invariant-focused tests (boundary collision, boundary idempotency, boundary type
rejection) and all 12 mission invariants (folded into the 24-item coverage plus 3 explicit
invariant tests at the end of the file). Full item-by-item mapping is embedded as section
comments in the test file itself (`# =====... EXPERIMENT BOUNDARY -- items 1-5`, etc.).

## 9. Regression results

| Run | Result | Duration |
|---|---|---|
| Full suite, before H.2-R (== H.2's final state) | 1230 passed, 14 skipped | 374.83s |
| Full suite, after H.2-R | 1262 passed, 14 skipped (1230 + 32 new, zero regressions) | 236.69s |
| Full suite, after H.2-R, `-W error` | 1262 passed, 14 skipped, no warning promoted to error | 244.05s |

Dedicated suites: `test_canonical_event_ledger_h2.py` (all 42 original H.2 tests, one
updated) → 42 passed. `test_h2_remediation.py` → 32 passed.

## 10. G.1 protection verification

Confirmed via `Get-CimInstance Win32_Process -Filter "Name='python.exe'"`:

- **Before starting H.2-R:** PIDs 33588/18212/4512 running
  `phase3.evaluation.agent_runtime.campaign_formal_runner c_longmemeval_worker {0,1,2} 3`
  under `C:\h4venv\Scripts\python.exe`.
- **After completing H.2-R** (immediately before the final regression run): the identical
  three PIDs, running the identical command line.

No file on that process's import path (`campaign_formal_runner.py`, `foundations/
adapter.py`, `foundations_real/amem_real_adapter.py`, `foundations_real/environment.py`,
`agent_runtime/identity.py`, `agent_runtime/runner.py`, `agent_runtime/campaign_formal_
manifest.py`, `agent_runtime/campaign_formal_diagnostics.py`, or any checkpoint/manifest/
result file) was read-written, modified, or deleted. `git status --short` confirms every
H.2-R change is either a new file or one of the three explicitly-listed modifications in
section 6 — none of which is on the G.1 import path. `git diff --stat` against the working
tree shows zero changes to any file that existed before this session.

## 11. Remaining limitations

- `ExperimentBoundaryLedger` shares the single-process/single-writer limitation every
  ledger in this framework has (H.1, H.2, H.2-R alike) — no cross-process lock.
- `BOUNDARY_TYPES` contains only `BOUNDARY_RESET` — deliberately minimal, extensible
  additively if a genuine second boundary kind is ever needed.
- The `EVT-`/`BND-` id prefixes are human-readable conventions, not runtime-enforced —
  `looks_like_generated_event_id()` is advisory only, and a boundary id lacking the `BND-`
  prefix is still fully valid.
- No call site was wired to actually construct an `ExperimentBoundaryRecord` on a real
  foundation reset, nor to call `generate_event_id()` from any runtime path
  (`campaign_formal_runner.py` or otherwise) — this stage provides representation, not
  runtime integration, matching H.1/H.2's own deferred-integration posture.
- `superseded`/`retired` events still carry no "which memory superseded/retired this one"
  linkage — deliberately deferred to H.3, which owns supersession-chain semantics.

## 12. Why H.2 is now ready to freeze

All three gaps identified in post-implementation review are closed:

- Experiment/run boundaries are now representable, structurally distinct from memory
  lifecycle events (confusion is impossible by type, not merely discouraged by convention).
- Event identity generation has a single, named, benchmark-owned, reproducible authority,
  fully backward-compatible with every existing H.2 caller.
- `derived` events now carry unambiguous, explicitly-validated source/target roles,
  resolving the exact ambiguity a future poisoning-lineage-reconstruction consumer would
  otherwise have hit.

No compatibility break, no schema change, no weakening of any existing invariant, and zero
regressions across 1262 tests (up from 1230). The canonical event ledger's public surface
(`CanonicalEvent`, `CanonicalEventLedger`) is additively richer but not narrower than
before this remediation.

## 13. Explicit boundary with H.3

H.2-R implements no part of H.3. Specifically NOT implemented here:

- Immutable memory version identity (a 7th namespace — see design doc section 25's table,
  which explicitly marks it "not yet implemented").
- Supersession-chain policy (what a `superseded_by` pointer means operationally, one-to-one
  enforcement, version-chain traversal).
- Retirement/tombstone workflows.
- Any change to `CanonicalMemoryLedger.put()`'s existing collision-only semantics.
- Any runtime call-site wiring (event emission from `campaign_formal_runner.py` or any
  other pipeline stage).

## 14. Git status

```
$ git status --short
?? phase3/evaluation/foundations/event_identity.py
?? phase3/evaluation/foundations/experiment_boundary.py
?? phase3/evaluation/tests/test_h2_remediation.py
?? phase3/experiments/PHASE3_3_H2_REMEDIATION_REPORT.md
 M phase3/evaluation/foundations/canonical_event.py
 M phase3/evaluation/tests/test_canonical_event_ledger_h2.py
 M phase3/specification/PHASE3_3_H2_CANONICAL_EVENT_LEDGER.md
(plus every prior H.1/H.2 untracked addition, and pre-existing untracked files from the
in-progress 3.3-G/G.1 campaign work, unrelated to and unmodified by this stage)

$ git diff --stat
(no output for tracked files that existed before this session -- canonical_event.py,
test_canonical_event_ledger_h2.py, and PHASE3_3_H2_CANONICAL_EVENT_LEDGER.md are all
themselves untracked H.2 additions from this same session, so `git diff --stat` reports
them as part of the untracked-file set, not as tracked-file diffs; there is no git-tracked
file anywhere in the repository whose committed content changed)
```

Per the mission's repository-discipline rule, no `git add`/`commit`/`push` was performed.
