# Phase 3.3-H.4-BC — Rejected & Relationship-Detection Events — Mission Brief

Status: **NOT STARTED**. Mission brief for an implementation pass. This document is the
input to that pass, in the same role the (unretained-in-repo) mission briefs played for
H.1/H.2/H.3 — see their own frequent references to "the mission's own STOP conditions,"
"mission section N," etc. in
[PHASE3_3_H3_MEMORY_VERSIONING.md](PHASE3_3_H3_MEMORY_VERSIONING.md). Whoever implements
this stage should produce, on completion, a `PHASE3_3_H4_BC_IMPLEMENTATION_REPORT.md`
under `phase3/experiments/`, matching the format of
`phase3/experiments/PHASE3_3_H2_IMPLEMENTATION_REPORT.md` /
`PHASE3_3_H3_IMPLEMENTATION_REPORT.md`.

This mission covers **Initiatives B and C only**, as sequenced in
[MEMORY_FOUNDATION_STRENGTHENING_PLAN_REVISED.md §10](MEMORY_FOUNDATION_STRENGTHENING_PLAN_REVISED.md).
Initiatives A, D, E, F, G are explicitly out of scope for this stage (see §7).

## 1. Problem

[TRACEABILITY_CONTRACT.md §5](../contracts/TRACEABILITY_CONTRACT.md) requires traceability
"for both accepted and rejected candidates where the rejection itself is diagnostically
relevant" — but [relationship_schema.md §3](../schemas/relationship_schema.md)'s frozen
event-type table has no `rejected` type. A candidate that is retrieved by candidate
discovery but not selected for the reasoning context currently disappears from the ledger
with no recorded reason.

Separately, `equivalent_to`/`conflicts_with`/`superseded_by` are edges in
[relationship_schema.md §2](../schemas/relationship_schema.md), but nothing records *when*
or *by what mechanism* an edge was established. A `superseded_by` edge's own linkage is
recorded by H.3's `SupersessionRecord`, but the *detection* that preceded the decision to
call `supersede_memory()` (why did the system decide A and B were the same fact, or that B
should supersede A?) has no corresponding event at all, for any of the three relationship
types.

Both gaps were identified during architectural review of
[MEMORY_FOUNDATION_STRENGTHENING_PLAN_REVISED.md](MEMORY_FOUNDATION_STRENGTHENING_PLAN_REVISED.md)
(Initiatives B and C) and are sequenced first because they are pure additive event-logging
extensions with no dependency on any other initiative in that plan.

## 2. Relationship to frozen H.1 (must remain untouched)

Zero lines of `canonical.py`, `ledger.py`, or `canonical_write.py` may be changed.
`CanonicalMemoryRecord` and `CanonicalMemoryLedger` are consumed read-only (`exists()`,
`get()`), exactly as H.2 and H.3 already do. This stage introduces no new memory-identity
concept — it only adds two new *event* types.

## 3. Relationship to frozen H.2/H.2-R/H.2-R2 (must remain untouched)

Zero lines of `canonical_event.py` or `event_ledger.py` may be changed.
`CanonicalEventLedger.append()` is driven, unmodified, with two new `event_type` values.
This mission does **not** relax H.2-R2's single-occurrence-per-type enforcement, nor its
`len(memory_ids)==1` constraints, except where explicitly noted in §4/§5 below (a
`relationship_detected` event concerns a *pair* of memories, which needs the same
`memory_ids`-tuple-of-two shape H.2 already supports for other multi-memory event types —
confirm against `canonical_event.py`'s actual `memory_ids` cardinality rules before
implementing; do not assume single-memory shape applies here).

## 4. Relationship to frozen H.3 (must remain untouched)

Zero lines of `memory_versioning.py` may be changed. `relationship_detected` is
complementary to, not a replacement for, H.3's `SupersessionRecord` — see §6.2. This stage
does not alter version reconstruction, current-version semantics, or supersession/
retirement mechanics in any way.

## 5. Deliverable 1 — the `rejected` event type

**Schema addition to `relationship_schema.md` §3's event-type table:**

| Event | Meaning |
|---|---|
| `rejected` | Memory was retrieved as a candidate but not selected for the reasoning context |

**Required fields** (beyond the base fields every event already carries — `event_id`,
`event_type`, `memory_id`, `task_id`, `timestamp`, `actor`, `reason`,
`previous_state`/`new_state` where applicable, per §3 of the frozen schema):

- `reason` — **not free text.** Must be one value from a closed enum. Minimum required
  enum members for this stage (extendable later, but not silently — any addition after
  this stage's freeze is itself a schema change requiring the same review discipline):
  - `below_rerank_threshold`
  - `capacity_cut`
  - `deduplicated_against_selected_equivalent`
  - `retired_lifecycle_state`
- `task_id` — required (mirrors the existing `retrieved`/`selected`/`used` requirement;
  a `rejected` event is always task-scoped, since rejection only has meaning relative to a
  specific candidate-selection decision).
- `memory_id` — the rejected candidate.

**Emission point:** the evidence-selection stage, once per retrieved candidate that does
not appear in that task's selected set. Every `retrieved` event for a task must eventually
be paired with exactly one of: a `selected` event, or a `rejected` event, for that same
`(memory_id, task_id)` pair — no candidate may be left with neither. (This is a **new
invariant** this stage introduces — see §8, item 5.)

## 6. Deliverable 2 — the `relationship_detected` event type

**Schema addition to `relationship_schema.md` §3's event-type table:**

| Event | Meaning |
|---|---|
| `relationship_detected` | An `equivalent_to`/`conflicts_with`/`superseded_by` edge was established between two memories |

**Required fields:**

- `relationship_type` — one of `equivalent_to`, `conflicts_with`, `superseded_by`.
- `memory_ids` — the pair of memory identities involved (order matters for
  `superseded_by`: superseded first, superseding second; `equivalent_to`/`conflicts_with`
  are symmetric per relationship_schema.md §2, but the event should still record both IDs
  in a stable, documented order — e.g. lexicographic by `memory_id` — for reproducible
  event fingerprinting, not an arbitrary call-order-dependent order).
- `mechanism` — how the relationship was detected, e.g. `embedding_similarity_threshold`,
  `llm_judge`, `manual_annotation`. Not a closed enum at this stage (the creation policy
  that would populate this is not yet frozen — see §6.1) but the field must exist so a
  future policy has somewhere to write to.
- `score` — the mechanism's own confidence/similarity score, if the mechanism produces one.
  Optional (some mechanisms, e.g. `manual_annotation`, may not have one).
- `threshold` — the decision threshold applied, if applicable. Optional, same reasoning.

### 6.1 Explicit STOP condition — do not invent the creation policy

This event type can and should be **defined and frozen** in this stage. It **cannot be
populated in production** until the memory-creation policy
([memory_schema.md §8](../schemas/memory_schema.md)) is itself frozen — that policy is
what decides *whether* two memories are equivalent/conflicting, or whether B should
supersede A, in the first place. If no creation policy exists yet, this stage's tests
must exercise `relationship_detected` by constructing it directly with test-authored
mechanism/score values (the same way H.2's tests construct `CanonicalEvent`s directly
without needing a real candidate-discovery pipeline) — **do not build a creation policy
as a side effect of this mission.** That is out of scope; if you find yourself writing
similarity-threshold logic to make a test pass, stop and flag it rather than proceeding.

### 6.2 Relationship to H.3's `SupersessionRecord` — complementary, not redundant

`SupersessionRecord` (H.3 §5.1) records the accepted *linkage* (A is superseded by B) once
a supersession decision has already been made. `relationship_detected` records the
*evidence that led to* that decision (what mechanism, what score, against what threshold).
For a `superseded_by` relationship specifically, the expected sequence is:
`relationship_detected` (this stage) → `supersede_memory()`'s existing four-step write
order (H.3 §9: `superseded` event → `SupersessionRecord` → `retired` event). This stage
does **not** modify `supersede_memory()`'s call signature or write order — it only adds
a preceding, independent event that a caller may choose to emit before invoking it. Do not
make `supersede_memory()` require a preceding `relationship_detected` event to succeed;
that would be a breaking change to a frozen H.3 API.

## 7. Explicit non-scope for this stage

- Initiative A (`counterfactually_influential`) — not started here; depends on Initiative F.
- Initiative D (qualification gate, including the `config_fingerprint` requirement added
  by the architectural review) — not started here.
- Initiative E (executable leakage audit) — not started here.
- Initiative F (`config_fingerprint` mechanism) — not started here. Note: `rejected` and
  `relationship_detected` do **not** require a `config_fingerprint` field — only
  `retrieved`/`selected` do, per the revised Initiative F. Do not add one to either event
  type defined in this mission.
- Initiative G (`tainted_by` traversal query) — not started here.
- No call site in `campaign_formal_runner.py` or elsewhere is required to *actually emit*
  these events as part of a live evaluation run during this stage, unless doing so is
  trivial and risk-free given existing call sites for `retrieved`/`selected`/`superseded`.
  If wiring live emission is nontrivial (e.g. requires touching evidence-selection logic
  that isn't purely additive), defer it to a follow-up integration stage and say so
  explicitly in the implementation report — matching H.3 §18's own precedent of listing
  "deferred runtime integration" as an explicit, named non-goal rather than a silent gap.

## 8. Invariants to implement and test

1. `rejected` and `relationship_detected` are valid `CanonicalEvent.event_type` values,
   accepted by the existing, unmodified `CanonicalEventLedger.append()`.
2. A `rejected` event's `reason` is always one of the closed enum values in §5 — malformed/
   unknown reasons are rejected at construction or append time, not silently accepted.
3. A `relationship_detected` event's `relationship_type` is always one of `equivalent_to`,
   `conflicts_with`, `superseded_by` — no other value is accepted.
4. Both new event types remain append-only — no update/delete path exists for either,
   matching every other event type's own invariant (H.2 §6, "no `update_event()`/
   `delete_event()` — deliberately absent, not merely unused").
5. **New cross-event invariant:** for any `(memory_id, task_id)` pair with a `retrieved`
   event, there is eventually exactly one of a `selected` event or a `rejected` event for
   that same pair — never both, never neither. (This invariant is checkable only over a
   *complete* task's event history — it is not a per-append constraint the ledger itself
   can enforce eagerly, since `retrieved` necessarily precedes the eventual selection
   decision. Implement it as a reconstruction-time consistency check, not an `append()`-
   time rejection.)
6. `relationship_detected` events are reconstructable per relationship pair via a query
   analogous to `events_for_memory`/`events_for_task` (H.2 §5) — e.g.
   `events_for_relationship(memory_id_a, memory_id_b)` or equivalent; exact naming is an
   implementation decision, not frozen here.
7. Vendor/foundation IDs never appear in either new event type's required fields — only
   canonical `memory_id`s, consistent with the existing "vendor IDs are aliases" principle
   this entire framework maintains.

## 9. Adversarial cases to test

- A `rejected` event submitted with a `reason` value outside the closed enum — must be
  rejected, not silently coerced or logged with a placeholder.
- A `relationship_detected` event for a `superseded_by` pair, followed by a caller that
  never actually calls `supersede_memory()` — must be a valid, permanently-recorded state
  (a detected-but-not-acted-on relationship is a legitimate, diagnostically interesting
  fact, not an error).
- A `relationship_detected` event for a pair where one or both `memory_id`s do not exist
  in the `CanonicalMemoryLedger` — must be rejected the same way `CanonicalEventLedger`
  already rejects any event referencing an unknown memory id (H.2's
  `UnknownCanonicalMemoryError`), reusing that existing mechanism rather than inventing a
  parallel validation path.
- Two `rejected` events submitted for the same `(memory_id, task_id)` pair with different
  `reason` values — decide and document whether this is a collision (H.2-R2-style,
  differing-payload same-identity rejection) or a legitimate re-evaluation; do not leave
  this ambiguous. Default recommendation: treat it as a collision, consistent with every
  other event type's existing collision discipline, unless a concrete call site requires
  otherwise.
- A `relationship_detected` event where `memory_ids` contains the same `memory_id` twice
  (a memory "detected as equivalent to itself") — must be rejected as malformed.

## 10. Deliverables checklist

- [ ] `relationship_schema.md` updated (additive only) with the two new event types and
      their required fields, in the same table format as the existing seven.
- [ ] New/updated test file (e.g. `test_canonical_event_ledger_h4_bc.py`) covering every
      item in §8 and §9.
- [ ] Full existing regression suite re-run with zero regressions (matching the "before/
      after passed count" table format H.2's and H.3's implementation reports use).
- [ ] `PHASE3_3_H4_BC_IMPLEMENTATION_REPORT.md` under `phase3/experiments/`, documenting
      exactly what was built, what remains deferred (per §7), and the before/after test
      counts.
- [ ] No modification to any file listed as frozen in §2–§4.

## 11. Definition of done

This stage is complete when: both event types are defined in `relationship_schema.md`,
both are constructible and appendable through the existing, unmodified
`CanonicalEventLedger`, all invariants in §8 and adversarial cases in §9 are tested and
passing, the full regression suite shows zero regressions, and the implementation report
explicitly states whether live emission (candidate-discovery/evidence-selection wiring)
was completed or deferred. Completion of this stage unblocks Initiative F
(`config_fingerprint`) as the next sequenced step per
[MEMORY_FOUNDATION_STRENGTHENING_PLAN_REVISED.md §10](MEMORY_FOUNDATION_STRENGTHENING_PLAN_REVISED.md).
