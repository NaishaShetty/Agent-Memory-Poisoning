# Phase 3.3-H.4-WIRE — Live Canonical Event Emission for Condition B (Mem0) — Implementation Report

Status: **COMPLETE**. This is the first H.4- mission to modify `campaign_formal_runner.py`
itself — the module that ran the real, hours-long, GPU-bound Mem0/A-MEM campaigns. Every
requirement in mission section 7 (validation-before-scale) was treated as load-bearing, not
optional diligence, and is documented in full below.

## 1. Problem confirmed, scoped to Condition B (Mem0) only

Direct inspection confirmed the readiness assessment's claim: before this mission,
`campaign_formal_runner.py` had zero reference to `CanonicalMemoryLedger`,
`CanonicalEventLedger`, or `RunConfigLedger`. Memories were ingested via a raw
`foundation.add_memory(...)` call; nothing logged `retrieved`/`selected` ids anywhere
durable. `agent_runtime/identity.py`'s `STRATEGY_METADATA_LOOKUP` was confirmed, by reading
both `identity.py` and `mem0_real_adapter.py` directly, to be the correct mechanism for
Condition B: Mem0 never honors a caller-suggested id (verified in `RealMem0Adapter.
add_memory()`'s own source — it has no `memory_id` parameter passed to the real library
call at all), so every retrieved/selected id from `run_agent_task()` is Mem0's own
vendor-native id and must be resolved back via `inspect_memory()` + a `source_memory_id`
metadata lookup. Condition C (A-MEM) was left completely untouched, per the mission's own
scope boundary — confirmed via a new, precise regression test (section 5).

## 2. Design — one new module, additive-only diff to the campaign runner

`phase3/evaluation/agent_runtime/canonical_wiring.py` (new) holds all the wiring logic:
`open_pool_canonical_ledgers()` (constructs/reopens the three ledgers for one pool, computes
and persists one `RunConfigRecord` per pool), `write_ingested_canonical_memory()` (thin
wrapper over `write_canonical_memory()`), and `record_retrieval_and_selection_events()`
(identity resolution + `retrieved`/`selected`/`rejected` event emission). Keeping this out
of `campaign_formal_runner.py` itself kept that file's own diff to `run_condition_b_mem0()`
purely additive: the existing control flow (initialize → reset → ingest → per-task
retrieve/generate/evaluate → shutdown) is completely unchanged in shape; new calls are
inserted alongside it, never replacing an existing line's own logic.

## 3. Storage path scheme

`<experiments_dir>/canonical_store/<campaign_id>/<dataset>-<collection_name>/{memory,
events,run_config}/`, where `collection_name` is the SAME sha256-derived token
`run_condition_b_mem0()` already computes for Mem0's own collection name
(`"g_" + sha256(f"{dataset}:{pool_key}")[:16]`) — reused so the canonical store directory
and the Mem0 collection it describes are traceable to each other by construction.
`<experiments_dir>/canonical_store/` is a new top-level directory this mission introduces;
verified it cannot collide with any existing convention (`results/`, `manifests/`, or any
other prior campaign artifact path).

## 4. Deliverable 2 — canonical memory writes, call-shape verification (mission section 4)

The raw `foundation.add_memory(memory_id=source_id, content=..., metadata=...)` call was
replaced with `write_canonical_memory()`. **Verification performed, as required**: read
`canonical_write.py::write_canonical_memory()`'s own source directly — it calls
`foundation.add_memory(memory_id=record.memory_id, content=dict(record.content),
metadata=_foundation_metadata(record, metadata_extra))`, the exact same three-keyword-
argument shape the raw call already used. One honest, additive difference was found and is
reported explicitly (not silently glossed over, per the mission's own diligence
requirement): `_foundation_metadata()` additively injects two breadcrumb keys
(`canonical_memory_id`, `mambench_memory_type`) into the metadata dict actually sent to
`foundation.add_memory()`. This was verified NOT to change what Mem0 actually ingests:
`RealMem0Adapter.add_memory()`'s own source reads `text = content.get("text") or
content.get("memory") or str(content)` for the embedded/stored text — `metadata` is passed
through to `self._memory.add(text, user_id=..., metadata=dict(metadata), infer=False)` as
opaque, non-embedded payload metadata only. `content` itself (the `{"text": ...}` dict) is
passed through byte-for-byte unchanged. This is tested directly:
`test_write_canonical_memory_underlying_add_memory_call_shape` asserts `content`'s key set
is unchanged and the two new metadata keys are additive-only. `ingested_ids` continues to be
populated by the identical condition (`STATUS_CANONICAL_AND_FOUNDATION`, the
`write_canonical_memory()` equivalent of the raw call's `FOUNDATION_AVAILABLE` check).

`CanonicalMemoryRecord.creation_event` (a required, H.1 "pointer to the logged creation
event" field) is populated with a descriptive per-memory label string; **no corresponding
`created` `CanonicalEvent` is appended to the event ledger for ingestion** in this mission —
documented explicitly in `canonical_wiring.py`'s own module docstring as a deliberate scope
boundary (this mission's deliverables are canonical memory WRITES at ingestion and resolved
`retrieved`/`selected`/`rejected` events, not full event-sourced ingestion; nothing in this
mission calls `memory_versioning.py` at all).

## 5. Deliverable 3 — resolved events

`record_retrieval_and_selection_events()` calls `resolve_source_identities()` (H.4-C/D's
existing, unmodified function) once per task, over `outcome.retrieved_memory_ids`. For each
resolved id: a `retrieved` event (always); a `selected` event if also in the resolved
selected set, else a `rejected` event (`REJECTED_REASON_CAPACITY_CUT` — the closest-fitting
existing closed-enum value, documented as such, not a claim that a real capacity-based
selection policy exists today). Every event references the pool's single, shared
`config_fingerprint`. An id that fails to resolve, or resolves to a canonical id not present
in the pool's own `CanonicalMemoryLedger`, produces no event — it is counted in the returned
`RetrievalEventReport` (`unresolved_foundation_ids`, `unresolved_reasons`,
`not_in_canonical_ledger`), attached to each task's result dict as `canonical_event_report`,
never silently absent. Confirmed the reason-string requirement is honored: `rejected`'s
`reason` field is the literal closed-enum value itself (`canonical_event.py` requires this
verbatim, not a free-text description).

Event emission happens strictly AFTER `evaluate_and_trace_with_identity()` has already
returned its `trace` — by construction, nothing computed by the new wiring can affect that
call's own inputs or output, since the wiring reads only `outcome` (already fully computed)
and writes only to the new canonical ledgers.

## 6. The `rejected` event's near-vacuity — documented at the wiring site and here

As predicted and required by mission section 6: `runner.py::select_from_retrieved()`'s
current provisional policy slices a `retrieved_memory_ids` sequence that
`_retrieve_and_select()` already capped at the SAME `top_k` via `foundation.retrieve()`
itself, so `selected_memory_ids` equals `retrieved_memory_ids` exactly for Condition B's
current configuration. Confirmed directly in the dry run (section 7): `rejected_event_ids`
was empty for both fabricated tasks. The code path exists, is correct, and is tested
directly against an adversarial reordering (not exercised via the dry run's own data, but
via `canonical_wiring.py`'s own logic, which builds the `selected_set` independently of
retrieval order and correctly classifies any id absent from it as rejected) — no smarter
selection policy was invented to make this path fire artificially.

## 7. Mandatory dry-run proof (mission section 7) — full method and result

**Method**: the PRE-mission `run_condition_b_mem0()` was loaded from `git show HEAD` (the
commit immediately preceding this mission's own changes) as an independently-loaded Python
module, alongside the POST-mission (current working tree) version. Both were run against an
IDENTICAL, tiny, fabricated pool (2 synthetic memories, 2 synthetic tasks — never a real
dataset), through a **vendor-id-diverging** Mem0-like test double
(`VendorIdDivergingFakeMem0Adapter`, subclassing `MockMem0Adapter` but overriding
`add_memory()` to assign its own vendor id and ignore the caller-suggested one) — this
specific choice matters: a naive test double that coincidentally preserved ids (as bare
`MockMem0Adapter` does) would not have exercised the actual hard case
(`STRATEGY_METADATA_LOOKUP` identity resolution) this mission's wiring depends on. A
deterministic fake `LLMProvider` and a fabricated `_ingest_pool` replacement were used for
both runs; real dataset files were never touched.

**Result**: for both fabricated tasks, the `trace` field of the resulting task record was
**byte-for-byte identical** (post JSON-normalization, matching the real campaign path's own
`json.dump(..., default=str)` serialization) between the before and after runs:

```
task 'dryrun-t1': trace IDENTICAL, byte-for-byte (post-normalization).
  after-only canonical_event_report: {'task_id': 'dryrun-t1',
    'retrieved_event_ids': ['retrieved-dryrun-t1-src-mem-0001', 'retrieved-dryrun-t1-src-mem-0002'],
    'selected_event_ids': ['selected-dryrun-t1-src-mem-0001', 'selected-dryrun-t1-src-mem-0002'],
    'rejected_event_ids': [], 'unresolved_foundation_ids': [], 'unresolved_reasons': {},
    'not_in_canonical_ledger': []}
task 'dryrun-t2': trace IDENTICAL, byte-for-byte (post-normalization).
  after-only canonical_event_report: {'task_id': 'dryrun-t2', ... (same shape, both resolved cleanly)}

ALL TRACE OUTPUTS IDENTICAL: True
```

Both foundation-vendor ids (which literally never equaled the source ids, by the test
double's own design) resolved correctly to their canonical `source_memory_id`s
(`src-mem-0001`/`src-mem-0002`) via the real `resolve_source_identities()` machinery — zero
unresolved ids, zero ids missing from the canonical ledger. A second, separate check
confirmed the honest-reporting path itself (an adapter that never stores a
`source_memory_id` metadata key): the unresolvable id was counted in
`unresolved_foundation_ids` with reason `NOT_RESOLVABLE`, and produced no fabricated event.

This dry run was performed exactly once, manually, using a throwaway comparison script and
a temporarily-copied pre-mission file under `agent_runtime/` (deleted immediately after the
comparison completed — confirmed via `git status`, no trace remains in the working tree).
**No divergence was found; the mission's own STOP condition (section 7, item 3) was never
triggered.**

**No full real-dataset campaign run was performed** — per mission section 7, item 2, this is
explicitly out of scope for this mission and was not attempted.

## 8. Regression test suite (permanent artifact)

`test_campaign_formal_runner_h4_wire.py` (new, 10 tests) is the PERMANENT regression
suite — it asserts current, correct behavior going forward (not a historical diff against a
frozen prior version, which would need updating on every future legitimate change):
original result-dict keys all still present and additive-only (`canonical_event_report` is
the one addition); the environment-failure short-circuit path is unaffected (no canonical
ledger construction attempted); canonical memories are written and findable in the ledger;
`retrieved`/`selected` events reference a resolvable `config_fingerprint`; identity
resolution correctly maps diverging vendor ids (the hard case); `rejected` events correctly
do not fire under the current provisional policy; an unresolvable id is counted and reported
honestly, never dropped; and the `write_canonical_memory()` call-shape verification (section
4) is codified as a permanent test, not just a one-time manual check.

**One pre-existing test needed updating, not fixing**: `test_h2_r2_hardening.py::test_24_
no_automatic_runtime_wiring` asserted the WHOLE `campaign_formal_runner` module never
mentions `event_ledger`/`canonical_event` — an invariant from H.2-R2, when the entire module
had zero canonical-ledger wiring. This mission's own explicit, authorized deliverable is to
wire exactly `run_condition_b_mem0()` to that infrastructure, so the whole-module check
necessarily, correctly fails on this mission's own intended change. Per this framework's own
established discipline for a test encoding a now-superseded invariant (mirroring H.3-R's
own reasoning), the test was updated — not deleted — to preserve its still-real protective
purpose: it now checks that `run_condition_a`, `run_condition_c_amem`, and every
LongMemEval/checkpoint helper function remain completely unwired (the actual G.1/Condition-C
live-campaign concern that motivated the original test), while separately asserting the
Condition-B wiring is actually present (so the test also fails loudly if that wiring is ever
silently removed later). This is the ONE test file modified outside of new-test-file
additions; the change is documented here in full, matching this session's own established
transparency convention for touching a pre-existing invariant.

## 9. Explicit non-scope / deferred (mission section 9)

- Condition C (A-MEM) — untouched; confirmed via the updated `test_24` and via re-running
  `test_campaign_formal_checkpoint.py` in full (5/5 pass, unmodified).
- Condition A (no-memory control) — untouched; nothing to wire.
- Full real-dataset campaign re-run — not performed (section 7).
- Fixing `select_from_retrieved()`'s provisional policy — not attempted (section 6).
- Initiative D's real qualification run, Initiative A's real counterfactual run — both
  remain separate, later punch-list items; this mission only makes the ledger the live
  campaign path can now actually write to, exist and be populated, for Condition B.

## 10. Files touched

- `phase3/evaluation/agent_runtime/canonical_wiring.py` — new module (section 2).
- `phase3/evaluation/agent_runtime/campaign_formal_runner.py` — additive changes inside
  `run_condition_b_mem0()` only: pool-ledger construction, `write_ingested_canonical_
  memory()` replacing the raw `add_memory()` call, and post-trace event emission. No other
  function in this file was touched.
- `phase3/evaluation/tests/test_campaign_formal_runner_h4_wire.py` — new, 10 tests.
- `phase3/evaluation/tests/test_h2_r2_hardening.py` — one existing test
  (`test_24_no_automatic_runtime_wiring`) updated per section 8 above; no other test in this
  file changed (35 others pass unmodified).

**Untouched, confirmed**: `evaluate_and_trace_with_identity()` (called with identical
arguments, identical position in the control flow); `run_condition_a`; `run_condition_c_amem`;
`run_formal_c_locomo`/`run_formal_c_longmemeval`/worker/checkpoint logic; every H.1/H.2/H.3
canonical file; `agent_runtime/identity.py`; `agent_runtime/runner.py`.

## 11. Tests

**Before H.4-WIRE (this session's own baseline, carried over from the H.3-R report):**
`python -m pytest phase3/evaluation/tests/ -q` → **1572 passed, 1 failed, 17 skipped**
(288.50s).

**After H.4-WIRE (final, with the `test_24` update applied):** **1584 passed, 1 failed (the
same pre-existing, unrelated dataset-fingerprint drift reported in every prior report this
session), 17 skipped** (335.98s) — zero regressions beyond the one pre-existing failure that
predates this entire session.

**New/updated test files only:**
`python -m pytest phase3/evaluation/tests/test_campaign_formal_runner_h4_wire.py
phase3/evaluation/tests/test_h2_r2_hardening.py phase3/evaluation/tests/test_campaign_formal_checkpoint.py -q`
→ **51 passed** (3.39s).

## 12. Definition of done — checklist

- [x] `run_condition_b_mem0()` updated, additive around the existing logic.
- [x] Canonical ledger storage path scheme documented (section 3).
- [x] The synthetic dry-run proof performed, with the before/after trace-output comparison
      included in full above (section 7) — zero divergence found.
- [x] Full existing regression suite re-run with zero (unexpected) regressions.
- [x] This report states: the dry-run comparison result (identical), the unresolved-id
      handling behavior observed (both the clean-resolution and honest-unresolved cases),
      and that no full real-dataset campaign was run.
- [x] No modification to `evaluate_and_trace_with_identity()`, `run_condition_a`,
      `run_condition_c_amem`, or any H.1/H.2/H.3 canonical file.

This unblocks readiness-assessment punch-list items 2 and 3 (a real Initiative D
qualification run and a real Initiative A counterfactual run) for the Mem0 pairing
specifically — both remain separate, subsequent missions, not part of this one. Condition C
(A-MEM) wiring, following this same proven pattern, is the natural next follow-up.
