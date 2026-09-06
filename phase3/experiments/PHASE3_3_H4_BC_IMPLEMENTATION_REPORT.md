# Phase 3.3-H.4-BC — Rejected & Relationship-Detection Events — Implementation Report

Status: **COMPLETE** (event-type definitions, validation, ledger integration, tests). Live
runtime emission (candidate-discovery/evidence-selection call-site wiring) is **explicitly
deferred** — see section 7.

## 1. Design summary

`relationship_schema.md` section 3 was missing two event types the traceability contract
requires: `rejected` (why a retrieved candidate never entered the reasoning context) and
`relationship_detected` (what evidence led to an `equivalent_to`/`conflicts_with`/
`superseded_by` edge, independent of whether any accepted-linkage action — e.g. H.3's
`supersede_memory()` — was ever taken on it). Both are additive extensions to the existing,
frozen `CanonicalEvent`/`CanonicalEventLedger` machinery from H.2 — no new memory-identity
concept, no new ledger file, no new storage model.

## 2. `rejected` event

Required fields beyond the base set: `task_id` (required — a rejection only has meaning
relative to one task's candidate-selection decision) and a `reason` constrained to a closed
enum (`below_rerank_threshold`, `capacity_cut`, `deduplicated_against_selected_equivalent`,
`retired_lifecycle_state`). `memory_ids` is constrained to exactly one id — a rejection
concerns exactly one candidate.

Two `rejected` events for the same `(memory_id, task_id)` pair with different `reason`
values are a collision (mission section 9's default recommendation): enforced in
`CanonicalEventLedger._check_single_occurrence()`, the same mechanism H.2-R2 already uses
for `created`/`derived`/`superseded`/`retired`'s own singular-fact enforcement — no new
enforcement mechanism was invented.

## 3. `relationship_detected` event

Required fields beyond the base set: `relationship_type` (one of `equivalent_to`,
`conflicts_with`, `superseded_by`), `mechanism` (required, non-empty — no closed enum yet,
per section 6.1), and optional `score`/`threshold`. `memory_ids` is constrained to exactly
two, distinct ids.

**Ordering decision** (relationship_schema.md section 3.2, made explicit in this stage):
`superseded_by`'s pair order is semantic (`(superseded, superseding)`) and is never
reordered. `equivalent_to`/`conflicts_with` are symmetric, so their pair is recorded in
lexicographic order by `memory_id` — enforced at construction (a caller supplying the pair
out of order gets a validation error naming the required order), so the same real-world
pair always fingerprints identically regardless of which memory a caller happened to
discover first.

**Section 6.1 STOP condition honored**: no memory-creation/similarity policy was built.
Every `relationship_detected` event in the new test file is constructed directly with
test-authored `mechanism`/`score`/`threshold` values, exactly as H.2's own tests construct
`CanonicalEvent`s without a real candidate-discovery pipeline.

## 4. Cross-event invariant (`retrieved` → `selected` XOR `rejected`)

Implemented as `CanonicalEventLedger.check_retrieval_resolution(task_id)` — a
reconstruction-time query over a task's complete event history, **not** an `append()`-time
check (mission section 8, item 5: a `retrieved` event necessarily precedes the eventual
selection decision, so the invariant cannot be enforced eagerly). Raises
`RetrievalResolutionViolation` naming every candidate left with neither a `selected` nor a
`rejected` event, or with both.

## 5. Query surface

`CanonicalEventLedger.events_for_relationship(memory_id_a, memory_id_b)` — every
`relationship_detected` event for the unordered pair, in append order, regardless of which
order the caller passes the two ids in (matched by set membership, not position — position
still carries the semantic `superseded_by` meaning inside the returned events themselves).

## 6. Adversarial cases (mission section 9) — all tested

| # | Case | Outcome |
|---|---|---|
| 1 | `rejected.reason` outside the closed enum | `CanonicalEventValidationError` at construction |
| 2 | `relationship_detected` for `superseded_by` with no following `supersede_memory()` call | Valid, permanently recorded — not an error |
| 3 | `relationship_detected`/`rejected` referencing an unknown `memory_id` | `UnknownCanonicalMemoryError` (H.2's existing mechanism, reused verbatim) |
| 4 | Two `rejected` events, same `(memory_id, task_id)`, different `reason` | `SingleOccurrenceViolationError` (collision, per section 2 above) |
| 5 | `relationship_detected` with the same `memory_id` twice | `CanonicalEventValidationError` at construction |

## 7. Explicit non-scope / deferred (mission section 7)

- Initiatives A, D, E, F, G — not started, unchanged from the mission brief's own scoping.
- **Live emission deferred.** No call site in `campaign_formal_runner.py` or elsewhere emits
  `rejected` or `relationship_detected` events as part of a live evaluation run. Wiring
  `rejected` into evidence-selection is not "trivial and risk-free" against the existing
  call sites (it requires the evidence-selection stage to know, per task, the full
  retrieved-but-not-selected set — a change to that stage's own logic, not purely additive
  event-logging) — deferred to a follow-up integration stage, matching H.3 section 18's own
  "deferred runtime integration" precedent.
- No `config_fingerprint` field was added to either new event type (Initiative F is not yet
  started; the revised plan scopes that field to `retrieved`/`selected` only).

## 8. Files touched

- `phase3/schemas/relationship_schema.md` — additive: two new event-type table rows plus
  sections 3.1/3.2 documenting their required fields, ordering rule, and collision policy.
- `phase3/evaluation/foundations/canonical_event.py` — additive: `EVENT_REJECTED`,
  `EVENT_RELATIONSHIP_DETECTED`, the `REJECTED_REASONS`/`RELATIONSHIP_TYPES` closed enums,
  four new optional dataclass fields (`relationship_type`, `mechanism`, `score`,
  `threshold`), and their validation in `__post_init__`. No existing field, event type, or
  validation rule was changed.
- `phase3/evaluation/foundations/event_ledger.py` — additive: `rejected`-specific
  single-occurrence enforcement in `_check_single_occurrence()`, `events_for_relationship()`,
  and `check_retrieval_resolution()`. `append()`'s existing signature, collision policy, and
  linkage check are unchanged and unmodified.
- `phase3/evaluation/tests/test_canonical_event_ledger_h4_bc.py` — new, 34 tests covering
  every item in mission sections 8 and 9.

**Frozen files — verified untouched:** `canonical.py`, `ledger.py`, `canonical_write.py`
(H.1); `memory_versioning.py` (H.3). No line of any of these four files was changed.

## 9. Tests

**Before H.4-BC (this session's own baseline):**
`python -m pytest phase3/evaluation/tests/ -q` → **1346 passed, 1 failed, 17 skipped**
(295.38s). The one failure, `test_candidate_memoryarena.py::
test_raw_fingerprint_file_count_matches_actual_raw_directory`, is a pre-existing dataset
fingerprint drift (211 vs. 215 files in a vendored raw dataset directory) with no
relationship to this stage's files — confirmed present before any H.4-BC file was touched
(captured against a `git stash` of every H.4-BC change).

**After H.4-BC:** **1380 passed, 1 failed (the same pre-existing failure), 17 skipped**
(355.85s) — exactly `1346 + 34` new tests, zero regressions, identical failure and skip
counts.

**New H.4-BC tests only:**
`python -m pytest phase3/evaluation/tests/test_canonical_event_ledger_h4_bc.py -q` →
**34 passed** (0.25s).

## 10. Definition of done — checklist

- [x] Both event types defined in `relationship_schema.md` (additive only).
- [x] Both constructible and appendable through the existing, unmodified
      `CanonicalEventLedger`.
- [x] All invariants in mission section 8 and adversarial cases in section 9 tested and
      passing.
- [x] Full regression suite shows zero regressions (1346→1380 passed, same 1 pre-existing
      unrelated failure, same 17 skipped).
- [x] This report states live emission was deferred (section 7).
- [x] No modification to any file listed as frozen in mission sections 2–4.

Completion of this stage unblocks Initiative F (`config_fingerprint`) as the next sequenced
step per `MEMORY_FOUNDATION_STRENGTHENING_PLAN_REVISED.md` §10.
