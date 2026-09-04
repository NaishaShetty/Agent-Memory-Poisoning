# Phase 3.3-H.3 — Immutable Memory Versioning, Supersession & Retirement — Implementation Report

Status: **COMPLETE**.

## 1. Design summary

The mission's own illustrative model (multiple content-versions sharing one logical memory
identity) was found to directly contradict the FROZEN `memory_schema.md`/
`memory_schema.json` (memory identity "never reassigned, reused, or mutated," supersession
is explicitly "A —superseded_by→ B," a relationship between TWO DISTINCT memory identities,
never a content update to one). H.3 therefore implements the evidence-based alternative: a
"version" is an immutable snapshot of `(lifecycle_state, superseded_by)` for one PERMANENT
`memory_id` — content never changes across a memory's own versions. Full reasoning:
`PHASE3_3_H3_MEMORY_VERSIONING.md` section 4.

## 2. Version identity

`version_id = f"{memory_id}::v{version_number}"` — benchmark-owned, deterministic by
construction (no fingerprinting needed, since versions are computed, never independently
authored — see design doc section 6), collision-free by construction (memory_id embedded
verbatim).

## 3. Version record

`CanonicalMemoryVersion` (frozen dataclass): `version_id`, `memory_id`, `version_number`,
`lifecycle_state`, `superseded_by`, `established_by_event_id` (a REFERENCE to the causing
`CanonicalEvent`, never a duplicate of its content), `recorded_at`. No content/source/
parent_ids/memory_type field — those remain H.1's, permanently.

## 4. Version lineage

Strictly linear per `memory_id` (append order of `created`/`derived`/`superseded`/`retired`
events). Cycle rejection: a `RETIRED` memory can never be used as a superseder (implemented
as an explicit precondition check in `supersede_memory()`, added after initial
implementation when a test — `test_14_cycles_rejected` — proved the gap existed; see section
9 for the fix).

## 5. Current version semantics

`get_current_version()` = last entry of `reconstruct_version_history()`. Never inferred from
`CanonicalMemoryRecord.lifecycle_state` (frozen at its at-creation value forever, by design —
an important, explicitly documented "gotcha" in the design doc).

## 6. Supersession semantics

`supersede_memory()`: validates both memories exist, superseded memory not already retired/
superseded, superseding memory not itself retired (cycle guard) → appends `superseded` event
→ appends `SupersessionRecord` → appends `retired` event. At most one successor per memory
(relationship_schema.md: one-to-one), enforced at two layers (ledger collision + precondition
check).

## 7. Retirement / tombstone semantics

`retire_memory()`: validates not already retired → appends `retired` event. No separate
tombstone structure — `lifecycle_state=RETIRED` on the latest version IS the tombstone marker
(memory_schema.json's own vocabulary), avoiding a redundant second structure.

## 8. Event integration

One version per lifecycle-relevant event (`created`/`derived`/`superseded`/`retired`), in
event-ledger append order — the most literal reading of the mission's own suggested mapping.

## 9. Reset distinction

Zero import coupling to `experiment_boundary`/`ExperimentBoundaryRecord` or any
`MemoryFoundationAdapter`/foundation adapter anywhere in `memory_versioning.py` — verified
directly via `hasattr` checks on the actual imported module (not string-matching prose, which
legitimately discusses the distinction).

## 10. Persistence / failure semantics

One new file, `supersessions.jsonl` (same append/flush/fsync/loud-malformed-failure
discipline as every prior ledger). No `versions.jsonl` — versions are computed, not
persisted (mission: "use references, don't duplicate"). `supersede_memory()`'s four-step
write order is explicitly not claimed atomic; each step's durability is independent, and a
mid-sequence failure leaves an honest, explicitly-reconstructable partial state (tested:
`test_38_linkage_write_failure_reported_explicitly_not_silently_repaired`,
`test_39_reload_after_partial_failure_shows_honest_state`).

## 11. Reconstruction

`reconstruct_version_history()`/`get_current_version()`/`get_version()` — pure functions over
`CanonicalEventLedger` + `CanonicalMemoryLedger` + `SupersessionLedger`. Zero vendor/
`MemoryFoundationAdapter` dependency anywhere; no vendor object is ever constructed in the
entire H.3 test module.

## 12. Schema changes

**None.** `memory_schema.json` and `relationship_schema.md` are both byte-for-byte
unmodified. `canonical.py`, `ledger.py`, `canonical_write.py`, `canonical_event.py`, and
`event_ledger.py` are all byte-for-byte unmodified. `SupersessionRecord` is a genuinely new,
additive type (mirrors H.2-R's `ExperimentBoundaryRecord` precedent) introduced specifically
because H.2's frozen `CanonicalEvent` shape cannot express an A→B linkage without modifying
a frozen file.

## 13. Tests

**Before H.3 (this session's own baseline — see note below):**
`python -m pytest phase3/evaluation/tests/ -q` → **1295 passed, 17 skipped** (291.21s).

**After H.3:** **1347 passed, 17 skipped** (295.38s) — exactly `1295 + 52` new tests, zero
regressions, identical skip count.

**`-W error`:** 1347 passed, 17 skipped, clean (316.38s) — no warning promoted to an error.

**New H.3 tests only:** `python -m pytest phase3/evaluation/tests/test_h3_versioning.py -q`
→ **52 passed** (0.43-0.56s across runs).

**Note on the baseline count vs. H.2-R2's reported 1298/14:** this session's own
pre-H.3 baseline run showed 1295 passed/17 skipped, not 1298/14. Investigated directly (not
assumed): the extra 3 skips are `REAL_RUNTIME_TEST`-guarded tests for `mem0ai`/
`graphiti-core`/`A-mem-sys`/a local llama-server, all reporting "not importable in this
interpreter" / "no llama-server reachable at http://127.0.0.1:8811" — an environmental
difference in which Python interpreter/services this session's `python` resolves to,
compared to whatever process ran H.2-R2's regression pass, and NOT caused by any H.3 code
change (verified: these skips are present in this session's baseline run, captured BEFORE
any H.3 file was written). H.3's own before/after comparison (1295→1347, 17→17) is the
apples-to-apples regression check that matters, and it shows zero regressions.

**Failure-injection tests:** items 36-40 (`test_36`-`test_40`) directly simulate write
failures between the four supersession steps (missing linkage, missing retirement event,
malformed on-disk record) and assert the resulting state is honest and non-corrupting —
see design doc section 14 for the full failure-mode table.

## 14. H.1/H.2 compatibility

Spot-checked directly (`test_41`-`test_44`): H.1's frozen-at-creation `lifecycle_state`,
H.2-R2's single-occurrence enforcement (`SingleOccurrenceViolationError` still raised for a
duplicate `created` event), H.2-R's `ExperimentBoundaryRecord`/`build_reset_boundary()`, and
H.2-R2's `generate_event_id()` determinism all still behave exactly as their own defining
test suites prove — run unmodified alongside the new H.3 suite in this same regression pass.

## 15. G.1 protection verification

**Important environmental observation, not caused by this session:** the 3.3-G.1 A-MEM ×
LongMemEval campaign's worker processes (PIDs 33588/18212/4512, confirmed running throughout
H.1/H.2/H.2-R/H.2-R2) were **no longer running** when this H.3 stage began — checked via
`Get-CimInstance Win32_Process`/`Get-Process python` before any H.3 code was written, and the
campaign's own checkpoint files' last-modified timestamps (`~2026-09-04 00:58-01:16`) predate
this stage's start by several hours, consistent with the campaign having completed on its
own. This session did not terminate, restart, or otherwise act on that process at any point
in this or any prior stage. No `campaign_formal_runner.py`/checkpoint/manifest/result file
was read-written or modified by any H.3 change (verified: `campaign_formal_runner.py`
contains zero reference to `memory_versioning` anywhere in its source —
`test_invariant_no_runtime_wiring_into_g1`).

**A second, independent environmental event occurred mid-stage:** a git commit
(`4c059df "Phase G/G.1"`, authored by the repository's own user account, NOT by this
session) landed during H.3's implementation, capturing a snapshot of the working tree
(including this stage's in-progress `memory_versioning.py` and every prior H.1/H.2/H.2-R/
H.2-R2 file). This session performed no `git add`/`commit`/`push` at any point, per the
mission's repository-discipline rule — this commit was an external action. Its effect on
this report: `git status`/`git diff --stat` below shows this stage's remaining DELTA
relative to that commit, rather than every file as freshly untracked.

## 16. Files changed

**New (untracked relative to the `4c059df` commit):**

| File | Purpose |
|---|---|
| `phase3/evaluation/tests/test_h3_versioning.py` | 52 tests covering all 44 mission test items + 16 invariants + adversarial cases |
| `phase3/specification/PHASE3_3_H3_MEMORY_VERSIONING.md` | Design document |
| `phase3/experiments/PHASE3_3_H3_IMPLEMENTATION_REPORT.md` | This report |

**Modified relative to `4c059df` (this session's own edit, made after that commit landed):**

| File | Change |
|---|---|
| `phase3/evaluation/foundations/memory_versioning.py` | Added the cycle-rejection precondition check in `supersede_memory()` (+16 lines) — the module's initial version (as captured by `4c059df`) lacked this check; a test written immediately afterward (`test_14_cycles_rejected`) proved the gap, and the fix was added before finalizing this stage. |

**Present in the repository but NOT created or modified by this session:**
`phase3/experiments/results/regression_pass_after_fix.log` shows as modified in `git diff`
purely because an unrelated, already-running process (not part of this session) finished
writing to that pre-existing file after the `4c059df` commit's snapshot was taken. This
session never opened, read, or wrote that file at any point — verified: no tool call in this
session's transcript references that path.

**Not modified:** every H.1/H.2/H.2-R/H.2-R2 file (`canonical.py`, `ledger.py`,
`canonical_write.py`, `canonical_event.py`, `event_ledger.py`, `event_identity.py`,
`experiment_boundary.py`), `memory_schema.json`, `relationship_schema.md`.

## 17. Remaining limitations

See design doc section 20 for the full list. Summary: single-writer `SupersessionLedger`; no
multi-worker merge utility (none needed by any current caller); `equivalent_to`/
`conflicts_with` versioning remains an open, unanswered question; the cycle-rejection check
is proven directly for the 2-cycle case and reasoned (not formally proven) to generalize; a
caller that bypasses `supersede_memory()`/`retire_memory()` and calls
`event_ledger.append()` directly could still construct an event sequence H.3's own
orchestration would have rejected (H.2's `append()` has no concept of H.3 semantics, by
design, since H.2 is frozen).

## 18. Explicit H.4 boundary

Not implemented: memory-version-aware retrieval/selection (excluding `RETIRED` memories from
candidate discovery or similar), memory-use attribution, causal contribution, foundation
requalification, poisoning attacks, or any change to canonical evaluation metrics. H.3
provides only the mechanism for recording and reconstructing lifecycle transitions; no
runtime call site was wired to use it.

## 19. Git status

```
$ git status --short
 M phase3/evaluation/foundations/memory_versioning.py
 M phase3/experiments/results/regression_pass_after_fix.log   (see section 15/16 -- not this session's edit)
?? phase3/evaluation/tests/test_h3_versioning.py
?? phase3/specification/PHASE3_3_H3_MEMORY_VERSIONING.md
?? phase3/experiments/PHASE3_3_H3_IMPLEMENTATION_REPORT.md

$ git diff --stat
 phase3/evaluation/foundations/memory_versioning.py       | 16 ++++++++++++++++
 phase3/experiments/results/regression_pass_after_fix.log |  6 +++++-
 2 files changed, 21 insertions(+), 1 deletion(-)
```

Per the mission's repository-discipline rule, no `git add`/`commit`/`push` was performed by
this session at any point in H.1, H.2, H.2-R, H.2-R2, or H.3.
