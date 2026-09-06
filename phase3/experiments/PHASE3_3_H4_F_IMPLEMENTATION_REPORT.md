# Phase 3.3-H.4-F — Configuration Fingerprinting for Retrieval/Selection Events — Implementation Report

Status: **COMPLETE** (record/ledger, event wiring, both eager and deferred resolvability
paths, tests). Live emission wiring into `campaign_formal_runner.py` is **explicitly
deferred** — see section 7.

## 1. Design summary

`MEMORY_FOUNDATION_STRENGTHENING_PLAN_REVISED.md` §6 requires `retrieved`/`selected` events
to be traceable to the exact deterministic configuration that produced them, using a
two-tier design: an immutable configuration record identified by a deterministic
`config_fingerprint`, referenced — never duplicated — by each event. This stage builds both
tiers: `run_config.py` (new module: `RunConfigRecord` + `RunConfigLedger`) is the record
side; `canonical_event.py`'s new `config_fingerprint` field is the reference side.

## 2. `RunConfigRecord` / `RunConfigLedger`

`RunConfigRecord` (`phase3/evaluation/foundations/run_config.py`) is a frozen dataclass
holding exactly the fields needed to reproduce a retrieval/selection operation:
`embedding_model`, `embedding_model_revision`, `retrieval_k`, `retrieval_mechanism`,
`selection_mechanism`, `adapter_revision` (all required), `reranker_model`/
`reranker_model_revision` (optional, paired — mirrors `canonical_event.py`'s existing
`foundation_memory_id` requires `foundation_name` rule), `sampling_seed` (optional), and
`created_at` (required, validated via `canonical_event.py`'s existing, reused
`_validate_timestamp()` — no second timestamp validator was written).

`RunConfigLedger` is append-only (`run_configs.jsonl`), identical persistence discipline to
every other ledger in this framework: open-append, one JSON line per `append()`, `flush()` +
`os.fsync()`, malformed lines raise loudly on reload. No `update()`/`delete()` method exists
anywhere in its public API — tested as a structural invariant, matching H.2 §5's own
"deliberately absent" test style.

## 3. Fingerprint derivation

`compute_config_fingerprint()` reuses `security.reproducibility.fingerprint()` (SHA-256 over
canonical, sorted-key JSON) — the same content-hashing authority `event_identity.
generate_event_id()` already established as this framework's ONE hashing scheme. No second,
parallel hashing scheme was introduced. The fingerprint covers every field except
`config_fingerprint` itself and `created_at` (metadata, not semantic content — the same
reasoning `security/reproducibility.py::MANIFEST_METADATA_ONLY_FIELDS` already applies to a
manifest's own `timestamp`). Prefixed `CFG-`, mirroring `event_identity.EVENT_ID_PREFIX`'s
advisory-only namespace-separation convention. `RunConfigRecord.__post_init__` verifies the
supplied `config_fingerprint` matches what `compute_config_fingerprint()` derives from the
record's own other fields — an inconsistent caller input fails loudly, mirroring
`canonical_event.py`'s existing `derived`-event `memory_ids`-consistency check.

`compute_config_fingerprint()` and `RunConfigRecord`/`RunConfigLedger` are the single,
reusable configuration-record type — Initiative D's future qualification-record extension
should reuse this, not build a second, parallel one (mission §9, item explicit note).

## 4. `CanonicalEvent.config_fingerprint`

Added as one new optional field, `config_fingerprint: Optional[str] = None`, following the
identical pattern H.4-BC used for `relationship_type`/`mechanism`/`score`/`threshold`:
required (non-empty string) for `event_type in (EVENT_RETRIEVED, EVENT_SELECTED)`; forbidden
(`None`) for every other event type, including the two H.4-BC additions (`rejected`,
`relationship_detected`) — the revised plan states neither needs one. `identity_fields()`,
`to_dict()`, `from_dict()` each enumerate `config_fingerprint` explicitly, in the same
enumerated style as every other field (no `**kwargs`/reflection shortcut). Every field,
constant, and validation branch H.2 and H.4-BC previously defined is unchanged.

## 5. Resolvability — eager and deferred paths

A `config_fingerprint` is analogous to a `memory_id` reference (must already exist before
the event about it is appended), not to the `retrieved`/`selected`/`rejected` cross-event
invariant (which is necessarily reconstruction-time, since `retrieved` precedes the eventual
decision):

- **Eager path**: `CanonicalEventLedger.__init__` gained one new optional parameter,
  `config_ledger: Optional[RunConfigLedger] = None`, additive and backward-compatible —
  every existing call site constructing `CanonicalEventLedger(storage_dir, memory_ledger)`
  continues to work unmodified (tested directly:
  `test_event_ledger_backward_compatible_without_config_ledger_param`). When supplied,
  `append()` validates a `retrieved`/`selected` event's `config_fingerprint` against
  `config_ledger.exists(...)`, raising the new `UnknownConfigFingerprintError` if it does
  not resolve — checked before any write, alongside the existing memory-linkage check.
- **Deferred path**: `check_config_resolution(event_ledger, config_ledger)` (module-level
  function, analogous to `check_retrieval_resolution()`) — for a ledger constructed WITHOUT
  a `config_ledger`, finds every `retrieved`/`selected` event whose `config_fingerprint`
  does not resolve against a given `RunConfigLedger`, after the fact. Never raises on its
  own; returns the offending events as data for the caller to act on.

## 6. Immutability mid-experiment

Stated explicitly in `run_config.py`'s module docstring (mission §7): a `RunConfigRecord`
must be immutable once any event references its `config_fingerprint`. `RunConfigLedger`'s
lack of `update()`/`delete()` already makes this true by construction — no second
enforcement mechanism was added.

## 7. Explicit non-scope / deferred (mission §10)

- Initiatives A, D (qualification-record extension), E, G — not started, unchanged from the
  mission's own scoping. This stage's `RunConfigRecord`/`RunConfigLedger` are exactly what
  Initiative D will reuse.
- **Live emission deferred.** No call site in `campaign_formal_runner.py` constructs/appends
  a `RunConfigRecord` or populates `config_fingerprint` on live `retrieved`/`selected`
  events. Not trivial given existing call sites (it requires the retrieval/selection stage
  to know its own embedding/reranker/adapter configuration at the point it emits an event —
  a change to that stage's own logic, not purely additive event-logging) — deferred to a
  follow-up integration stage, matching H.4-BC's and H.3's own "deferred runtime
  integration" precedent.
- `retrieval_mechanism`/`selection_mechanism` remain free-form strings — no existing closed
  vocabulary for either was found elsewhere in the codebase during implementation, and the
  mission does not require inventing one at this stage.
- Event/config **temporal ordering is explicitly left unchecked** (mission §9, item 5's
  documented default): a `retrieved`/`selected` event's own `timestamp` may predate the
  referenced `RunConfigRecord.created_at`, and `append()` does not check this — only
  fingerprint *existence* is validated, not temporal precedence. Tested directly:
  `test_config_fingerprint_resolution_is_atemporal_by_design`. Enforcing temporal ordering
  would be a stronger property than "resolvable" and is named here as a known limitation,
  not silently left ambiguous.

## 8. Files touched

- `phase3/evaluation/foundations/run_config.py` — new module: `RunConfigRecord`,
  `compute_config_fingerprint()`, `RunConfigLedger`, `RunConfigCollisionError`,
  `RunConfigValidationError`.
- `phase3/evaluation/foundations/canonical_event.py` — additive: `config_fingerprint`
  field, `_CONFIG_SCOPED_EVENT_TYPES`, validation branch, and `identity_fields()`/
  `to_dict()`/`from_dict()` updates. No existing field, event type, or validation rule
  changed.
- `phase3/evaluation/foundations/event_ledger.py` — additive: optional `config_ledger`
  constructor parameter, `UnknownConfigFingerprintError`, the eager check inside
  `append()`, and the module-level `check_config_resolution()` function. `append()`'s
  existing signature (for callers not passing `config_ledger`), collision policy, and
  memory-linkage check are unchanged.
- `phase3/schemas/relationship_schema.md` — additive: new §3.3 documenting
  `config_fingerprint` on `retrieved`/`selected`.
- `phase3/evaluation/tests/test_canonical_event_ledger_h4_f.py` — new, 31 tests covering
  every item in mission §8 and §9.
- **Existing test fixtures updated** (not a scope change, a required consequence of making
  `config_fingerprint` required on `retrieved`/`selected` — every pre-existing test that
  constructs a `retrieved`/`selected` event now supplies one):
  `test_canonical_event_ledger_h2.py` (8 constructions), `test_canonical_event_ledger_h4_bc.py`
  (2 shared helper functions), `test_h2_r2_hardening.py` (2 constructions). No assertion
  in any of these files was weakened or removed — only a required field was added to
  existing fixtures so they remain valid under the new, spec-mandated constraint.

**Frozen files — verified untouched:** `canonical.py`, `ledger.py`, `canonical_write.py`
(H.1); `memory_versioning.py` (H.3).

## 9. Tests

**Before H.4-F (this session's own baseline, carried over from the H.4-BC report):**
`python -m pytest phase3/evaluation/tests/ -q` → **1380 passed, 1 failed, 17 skipped**
(355.85s). The one failure, `test_candidate_memoryarena.py::
test_raw_fingerprint_file_count_matches_actual_raw_directory`, is the same pre-existing
dataset fingerprint drift (211 vs. 215 files in a vendored raw dataset directory) reported
in the H.4-BC report, unrelated to this stage's files.

**After H.4-F:** **1411 passed, 1 failed (the same pre-existing failure), 17 skipped**
(319.21s) — exactly `1380 + 31` new tests, zero regressions, identical failure and skip
counts.

**New H.4-F tests only:**
`python -m pytest phase3/evaluation/tests/test_canonical_event_ledger_h4_f.py -q` →
**31 passed** (0.13s).

## 10. Definition of done — checklist

- [x] `RunConfigRecord`/`RunConfigLedger` exist and are tested (deterministic fingerprint,
      frozen dataclass, append-only, reranker pairing, collision/idempotency).
- [x] `CanonicalEvent.config_fingerprint` wired with correct required/forbidden validation
      per event type.
- [x] Eager (`config_ledger` supplied) and deferred (`check_config_resolution()`)
      resolvability paths implemented and tested.
- [x] All invariants (§8) and adversarial cases (§9) pass.
- [x] Full regression suite shows zero regressions (1380→1411 passed, same 1 pre-existing
      unrelated failure, same 17 skipped).
- [x] This report states live emission wiring was deferred (section 7).
- [x] No modification to any file listed as frozen in mission §2/§4.

Completion unblocks Initiative D's `config_fingerprint` extension and Initiative A's
counterfactual-comparison mechanism, per `MEMORY_FOUNDATION_STRENGTHENING_PLAN_REVISED.md`
§10.
