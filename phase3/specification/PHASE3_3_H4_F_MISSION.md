# Phase 3.3-H.4-F — Configuration Fingerprinting for Retrieval/Selection Events — Mission Brief

Status: **NOT STARTED**. Mission brief for an implementation pass, in the same role
[PHASE3_3_H4_BC_MISSION.md](PHASE3_3_H4_BC_MISSION.md) played for the just-completed H.4-BC
stage (see `phase3/experiments/PHASE3_3_H4_BC_IMPLEMENTATION_REPORT.md` for what that stage
actually built: `canonical_event.py` gained `EVENT_REJECTED`/`EVENT_RELATIONSHIP_DETECTED`,
closed enums, and validation, purely additively; `event_ledger.py` gained collision
enforcement, `events_for_relationship()`, and `check_retrieval_resolution()`; H.1/H.3 files
were untouched). This mission covers **Initiative F only**, as sequenced in
[MEMORY_FOUNDATION_STRENGTHENING_PLAN_REVISED.md §10](MEMORY_FOUNDATION_STRENGTHENING_PLAN_REVISED.md)
(item 2 — next after B/C, and a prerequisite for D and A). On completion, produce
`PHASE3_3_H4_F_IMPLEMENTATION_REPORT.md` under `phase3/experiments/`, matching the format
of the H.2/H.3/H.4-BC reports.

## 1. Problem

[MEMORY_FOUNDATION_STRENGTHENING_PLAN_REVISED.md §6](MEMORY_FOUNDATION_STRENGTHENING_PLAN_REVISED.md)
requires that `retrieved`/`selected` events be traceable to the exact deterministic
configuration that produced them (embedding model, embedding model revision, reranker
model/revision, retrieval `k`, sampling seed, retrieval/selection mechanism, adapter
revision), so that a clean run and a later manipulated run (Phase 4) can be proven
identical except for the injected manipulation. The revision explicitly rejected embedding
this configuration inline in every event (redundant, risk of two events silently
disagreeing, unnecessary coupling) in favor of a two-tier design: an immutable
configuration record, identified by a deterministic `config_fingerprint`, referenced —
never duplicated — by each event.

## 2. Relationship to frozen H.1 (must remain untouched)

Zero lines of `canonical.py`, `ledger.py`, `canonical_write.py` may be changed. This stage
introduces no new memory-identity concept.

## 3. Relationship to H.2 and H.4-BC's `canonical_event.py`/`event_ledger.py`

**These two files are not frozen in the same sense as H.1/H.3** — H.4-BC already
extended both of them additively (new event types, new enums, new validation branches, a
new `events_for_relationship()` query, a new `check_retrieval_resolution()` reconstruction
check), and this stage follows the exact same precedent: **additive fields and additive
validation branches only.** Concretely:

- Every field, constant, and validation branch H.2 originally defined, and every one
  H.4-BC added, must remain exactly as-is — same names, same semantics, same required/
  forbidden rules for the nine existing event types.
- This stage adds exactly one new field to `CanonicalEvent`: `config_fingerprint:
  Optional[str] = None`, following the identical pattern H.4-BC used for
  `relationship_type`/`mechanism`/`score`/`threshold` (§`__post_init__`'s existing
  if/else structure — required-and-validated for specific event types, `_require`d to be
  `None` for every other event type).
- `identity_fields()`, `to_dict()`, `from_dict()` each already enumerate every field
  explicitly (see `canonical_event.py` lines 420-443, 377-418) — this stage must add
  `config_fingerprint` to all three in the same enumerated style, not via a generic
  `**kwargs`/reflection shortcut (matches this module's own established convention of
  never doing anything implicitly it can do explicitly).

## 4. Relationship to frozen H.3

Zero lines of `memory_versioning.py` may be changed. This stage does not touch
supersession/versioning mechanics. (Initiative D — not this stage — is where qualification
records will later reference a `config_fingerprint`; that is out of scope here, see §9.)

## 5. Deliverable 1 — the immutable configuration record and its ledger

**New module** (name at implementer's discretion, e.g. `run_config.py`), containing:

`RunConfigRecord` — a frozen dataclass, mirroring `CanonicalMemoryRecord`'s own
immutability discipline (H.1) and `CanonicalMemoryVersion`'s "no content, pure snapshot"
discipline (H.3 §5). Fields — **only those necessary to establish reproducibility of the
retrieval/selection operation, not every possible runtime setting** (explicit non-goal, per
the revised plan's own wording):

| Field | Required? | Notes |
|---|---|---|
| `config_fingerprint` | required | the deterministic identity of this record — see §5.1 |
| `embedding_model` | required | |
| `embedding_model_revision` | required | |
| `retrieval_k` | required | |
| `retrieval_mechanism` | required | e.g. `"dense_knn"`, `"bm25"`, `"hybrid"` — not a closed enum at this stage unless an existing one already governs retrieval mechanism naming elsewhere in the codebase; check before inventing one |
| `selection_mechanism` | required | e.g. `"rerank_topk"`, `"threshold_filter"` — same caveat |
| `adapter_revision` | required | the foundation adapter's own version/commit identifier, since adapter behavior is itself part of what must be reproducible |
| `reranker_model` | optional | `None` when selection uses no separate reranker model |
| `reranker_model_revision` | optional | required (non-`None`) whenever `reranker_model` is set; forbidden (`None`) otherwise — mirrors `canonical_event.py`'s existing `foundation_memory_id` requires `foundation_name` pattern (line 295-299) |
| `sampling_seed` | optional | `None` when the mechanism is fully deterministic without one; if present, must be recorded exactly, never re-rolled |
| `created_at` | required | ISO-8601 UTC, the record's own creation timestamp — reuse `canonical_event.py`'s existing `_validate_timestamp()` validation logic rather than writing a second timestamp validator |

`RunConfigLedger` — append-only store (`run_configs.jsonl`), identical persistence
discipline to every other ledger in this framework (open-append, one JSON line per
`append()`, `flush()`, `os.fsync()`; malformed lines raise loudly on reload, never
silently skipped — matching H.1 §13/H.3 §13's own stated discipline). API:
`append(record) -> APPEND_CREATED | APPEND_IDEMPOTENT` (raises a new
`RunConfigCollisionError` for a differing-payload fingerprint re-use, mirroring
`CanonicalEventCollisionError`'s exact semantics), `get(config_fingerprint)`, `exists
(config_fingerprint)`, `all_records()`. **No `update()`/`delete()`** — deliberately absent,
tested as a structural invariant, exactly as H.2 §5 states for `CanonicalEventLedger`.

### 5.1 Fingerprint derivation

`config_fingerprint` must be **deterministic**: identical field values (excluding
`config_fingerprint` and `created_at` themselves) always produce the identical fingerprint,
and differing field values (in any field) always produce a different one. Recommended
approach: a stable content hash (e.g. SHA-256) over a canonical serialization (sorted-key
JSON) of every other field — check first whether `canonical.py`/`canonical_event.py`
already expose a reusable content-hashing/fingerprint utility (H.3 §6 references H.2's own
"content-derived (`fingerprint()`-based) event-identity design" as prior art) and reuse it
rather than writing a second, parallel hashing scheme if one already exists. If none
exists, this stage may introduce one, but it must be used consistently by both this
record type and documented as reusable prior art for Initiative D's qualification records
(§9), not duplicated a third time later.

**Explicit non-goal:** this stage does not need to invent a human-readable
"CFG-..."-style identifier — the plan's own text ("the exact identifier syntax does not
need to be frozen unless the existing architecture requires it") leaves this open. A raw
content hash is an acceptable, sufficient `config_fingerprint` value.

## 6. Deliverable 2 — wire `config_fingerprint` into `CanonicalEvent`

Add to `CanonicalEvent` (canonical_event.py): `config_fingerprint: Optional[str] = None`.

**Validation, added to `__post_init__` following the exact existing if/else pattern (see
lines 335-373 for the `relationship_detected`-specific block this mirrors):**

- Required (non-`None`, non-empty string) for `event_type in (EVENT_RETRIEVED,
  EVENT_SELECTED)`.
- Forbidden (`None`) for every other event type — including the two H.4-BC just added
  (`rejected`, `relationship_detected`), per the revised plan's explicit statement that
  neither of those needs a `config_fingerprint`.

**Resolvability — the invariant that gives this initiative its actual value:**

> Every `retrieved`/`selected` event must reference exactly one immutable configuration
> fingerprint. The referenced configuration must be resolvable. If it cannot be resolved,
> the event is not considered reproducibly interpretable.

Following the same pattern H.4-BC used for cross-ledger invariants that can't be enforced
eagerly at construction time (`check_retrieval_resolution()`, H.4-BC §8 item 5 — a
reconstruction-time check, not a per-append rejection, because of ordering
dependencies) versus invariants that *can* be enforced eagerly (H.2's own
`UnknownCanonicalMemoryError` for an event referencing an unknown `memory_id`, checked
inside `append()` itself because the referenced memory must already exist before an event
about it is appended):

A `config_fingerprint` is analogous to the *memory_id* case, not the *retrieval-resolution*
case — a configuration record must exist (the run must have started) before any
`retrieved`/`selected` event referencing it can legitimately be appended. Therefore:

1. `CanonicalEventLedger`'s constructor gains a new **optional** parameter,
   `config_ledger: Optional[RunConfigLedger] = None`, alongside its existing required
   `memory_ledger` parameter (event_ledger.py). This is additive and backward-compatible —
   every existing call site constructing `CanonicalEventLedger(storage_dir, memory_ledger)`
   continues to work unmodified, exactly as adding `config_ledger.py` didn't break H.1
   callers when H.2 added it, per this codebase's stated non-negotiable "no breaking
   change without explicit justification" precedent.
2. When `config_ledger` is provided, `append()` validates any `retrieved`/`selected`
   event's `config_fingerprint` resolves via `config_ledger.exists(...)`, raising a new
   `UnknownConfigFingerprintError` (mirroring `UnknownCanonicalMemoryError`'s exact role)
   if it does not.
3. When `config_ledger` is not provided (e.g. an existing call site not yet updated to
   pass one), this eager check is skipped — but the event still carries the
   `config_fingerprint` value for later, reconstruction-time verification. Provide a
   `check_config_resolution(event_ledger, config_ledger) -> list[violation]` function
   (module-level, analogous to `check_retrieval_resolution()`) that a caller can run after
   the fact to find any `retrieved`/`selected` event whose `config_fingerprint` does not
   resolve against a given `RunConfigLedger` — this is how "the event is not considered
   reproducibly interpretable" gets surfaced when eager validation wasn't wired in at
   append time.

## 7. Immutability of configuration records mid-experiment

**New invariant, not previously stated anywhere in this framework because nothing
previously modeled "the configuration active during a run" as a first-class object:** a
`RunConfigRecord` must be immutable once any event references its `config_fingerprint`.
`RunConfigLedger`'s lack of `update()`/`delete()` (§5) already makes this true by
construction for anything going through the ledger's own API — this section exists only to
state the invariant explicitly and require it be tested (§8), not to add a second
enforcement mechanism.

## 8. Invariants to implement and test

1. `config_fingerprint` derivation is deterministic: two `RunConfigRecord`s constructed
   with identical field values (excluding `config_fingerprint`/`created_at`) produce the
   identical fingerprint; changing any one field changes the fingerprint.
2. `RunConfigRecord` is an immutable (frozen) dataclass — no field can be reassigned after
   construction.
3. `RunConfigLedger` is append-only: no `update()`/`delete()` method exists anywhere in its
   public API (structural test, matching H.2 §5's own "deliberately absent" test style).
4. A `retrieved` or `selected` `CanonicalEvent` constructed with `config_fingerprint=None`
   or an empty string is rejected at construction (`CanonicalEventValidationError`).
5. A `created`/`used`/`derived`/`superseded`/`retired`/`rejected`/`relationship_detected`
   event constructed with a non-`None` `config_fingerprint` is rejected at construction —
   the field is scoped exclusively to `retrieved`/`selected`.
6. When `config_ledger` is supplied to `CanonicalEventLedger`, appending a `retrieved`/
   `selected` event whose `config_fingerprint` does not `exist()` in that ledger raises
   `UnknownConfigFingerprintError` and the event is not persisted.
7. When `config_ledger` is **not** supplied, the same malformed event append succeeds (no
   eager check performed), but `check_config_resolution()` run afterward reports it as an
   unresolvable-fingerprint violation.
8. `identity_fields()`, `to_dict()`, `from_dict()` round-trip `config_fingerprint`
   correctly for `retrieved`/`selected` events and correctly omit/null it for every other
   event type.
9. Two different `retrieved` events referencing the same `config_fingerprint` resolve, via
   `config_ledger.get(...)`, to bit-identical configuration field values — proving the
   reference mechanism actually eliminates the duplication/disagreement risk the revised
   plan identified as the original design's flaw.

## 9. Adversarial cases to test

- A `RunConfigRecord` with `reranker_model` set but `reranker_model_revision` left `None`
  — must be rejected (mirrors the existing `foundation_memory_id`/`foundation_name`
  pairing rule already established in `canonical_event.py` lines 295-299 — reuse that
  reasoning, don't invent a new one).
- Constructing two `RunConfigRecord`s with every field identical except `sampling_seed`
  (one `None`, one set) — must produce different fingerprints (seed materially affects
  reproducibility and must not be silently ignored by the hashing scheme).
- Appending a `RunConfigRecord` with a `config_fingerprint` that collides with an
  already-appended, differently-valued record — must raise `RunConfigCollisionError`
  (mirrors `CanonicalEventCollisionError`/`CanonicalEventCollisionError`'s exact
  idempotent-vs-collision distinction already established in this framework).
- Re-appending the exact same `RunConfigRecord` (identical fingerprint, identical every
  other field) twice — must be idempotent (`APPEND_IDEMPOTENT`), not an error, matching
  every other ledger's own idempotency discipline.
- A caller attempting to construct a `retrieved` event whose `config_fingerprint`
  references a record that technically exists in the ledger but was appended *after* the
  event's own `timestamp` — decide and document whether this is checked (temporal
  ordering) or left unchecked (the fingerprint-existence check is atemporal). Default
  recommendation: leave unchecked at this stage — enforcing event/config temporal
  ordering is a stronger property than "resolvable," and adding it silently would exceed
  this mission's stated scope; document it as a known limitation instead (matching this
  framework's own convention of naming gaps rather than silently leaving them ambiguous).

## 10. Explicit non-scope for this stage

- Initiative A (`counterfactually_influential`) — not started here. This stage only makes
  A *possible* by giving its future counterfactual/baseline event pairs something
  resolvable to prove they share configuration.
- Initiative D's qualification-record extension (requiring qualification results to
  reference a `config_fingerprint` alongside `fixture_set_version` and adapter revision,
  per [MEMORY_FOUNDATION_STRENGTHENING_PLAN_REVISED.md §4](MEMORY_FOUNDATION_STRENGTHENING_PLAN_REVISED.md))
  — not started here, but this stage's `RunConfigRecord`/`RunConfigLedger` are exactly
  what that future work will reuse; do not build a second, parallel configuration-record
  type for qualification when this one already exists.
- Initiative E, G — untouched, unrelated.
- No call site in `campaign_formal_runner.py` is required to actually construct/append a
  `RunConfigRecord` or populate `config_fingerprint` on live `retrieved`/`selected` events
  as part of this stage, unless trivial given existing call sites. If nontrivial, defer and
  document explicitly in the implementation report — same stance H.4-BC took on live
  emission wiring.
- This stage does not decide whether `retrieval_mechanism`/`selection_mechanism` should
  become closed enums — left as free-form strings unless an existing closed vocabulary is
  found elsewhere in the codebase during implementation.

## 11. Deliverables checklist

- [ ] New module (`run_config.py` or equivalent) with `RunConfigRecord`, deterministic
      fingerprinting, and `RunConfigLedger` (append-only, `run_configs.jsonl`).
- [ ] `canonical_event.py` updated (additive only) with `config_fingerprint` field,
      validation branches, and `identity_fields()`/`to_dict()`/`from_dict()` updates.
- [ ] `event_ledger.py` updated (additive only) with optional `config_ledger` constructor
      parameter, `UnknownConfigFingerprintError`, and `check_config_resolution()`.
- [ ] New test file covering every item in §8 and §9.
- [ ] Full existing regression suite re-run with zero regressions (before/after counts
      table, matching H.2/H.3/H.4-BC report format).
- [ ] `relationship_schema.md` updated to document the `config_fingerprint` field on
      `retrieved`/`selected` (additive documentation change, consistent with how H.4-BC
      added §3.1/§3.2).
- [ ] `PHASE3_3_H4_F_IMPLEMENTATION_REPORT.md` under `phase3/experiments/`.
- [ ] No modification to any file listed as frozen in §2/§4.

## 12. Definition of done

Complete when: `RunConfigRecord`/`RunConfigLedger` exist and are tested;
`CanonicalEvent.config_fingerprint` is wired with correct required/forbidden validation
per event type; both eager (`config_ledger` supplied) and deferred
(`check_config_resolution()`) resolvability paths are implemented and tested; all
invariants (§8) and adversarial cases (§9) pass; the full regression suite shows zero
regressions; the implementation report states whether live emission wiring was completed
or deferred. Completion unblocks Initiative D's `config_fingerprint` extension and
Initiative A's counterfactual-comparison mechanism, per
[MEMORY_FOUNDATION_STRENGTHENING_PLAN_REVISED.md §10](MEMORY_FOUNDATION_STRENGTHENING_PLAN_REVISED.md).
