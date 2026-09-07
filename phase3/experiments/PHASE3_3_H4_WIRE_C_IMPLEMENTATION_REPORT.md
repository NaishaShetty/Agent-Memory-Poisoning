# Phase 3.3-H.4-WIRE-C — Live Canonical Event Emission for Condition C (A-MEM) — Implementation Report

Status: **COMPLETE**. Extends [PHASE3_3_H4_WIRE_IMPLEMENTATION_REPORT.md](PHASE3_3_H4_WIRE_IMPLEMENTATION_REPORT.md)
(Condition B / Mem0) to Condition C (A-MEM), the follow-up that mission's own docstring
explicitly deferred.

## 1. Why this was simpler than Condition B, and one thing that made it not entirely trivial

Condition C uses `STRATEGY_DIRECT_ASSIGNMENT` (A-mem-sys honors a caller-supplied id) —
`run_agent_task()`'s `retrieved_memory_ids`/`selected_memory_ids` are already canonical
source ids, so no `resolve_source_identities()`/`inspect_memory()` round-trip is needed,
unlike Condition B's `STRATEGY_METADATA_LOOKUP`. This meant a genuinely simpler pair of
event-emission functions.

The one complication: `resolve_via_direct_assignment()` needs the RAW
`foundation.add_memory()` return value (`{"memory_id": ..., "requested_id_honored": ...}`),
which `write_canonical_memory()`'s `CanonicalWriteResult` does not expose. Rather than
modify `canonical_write.py` (H.1) to add that, or duplicate the existing, working
`add_memory()`/`resolve_via_direct_assignment()` call sequence, this mission left that
sequence **completely untouched** and instead added a canonical-ledger-only write
afterward, using `write_canonical_memory(..., foundation=None)` — a documented, existing,
first-class mode (`STATUS_CANONICAL_ONLY`) that persists only the canonical record without
calling the foundation a second time. The alias is then set explicitly from the
already-computed resolution. Verified directly: `run_condition_c_amem()`'s existing
`foundation.add_memory()` call is provably unchanged (a source-inspection test asserts
`write_ingested_canonical_memory` — Condition B's foundation-calling helper — never
appears in Condition C's source).

## 2. What was added

- `canonical_wiring.py` (additive): `FOUNDATION_NAME_AMEM`, `RETRIEVAL_MECHANISM_AMEM_DENSE`,
  an optional `retrieval_mechanism` parameter on `open_pool_canonical_ledgers()` (defaults
  to `RETRIEVAL_MECHANISM_MEM0_DENSE` — zero behavior change for Condition B's existing,
  already-live call sites), `write_canonical_record_and_alias_direct_assignment()`, and
  `record_retrieval_and_selection_events_direct_assignment()`.
- `campaign_formal_runner.py::run_condition_c_amem()`: canonical ledgers opened once per
  pool; a canonical-ledger-only write appended after each existing `add_memory()` call;
  resolved `retrieved`/`selected`/`rejected` events appended after
  `evaluate_and_trace()`/`classify_citation_based_usage()` have already returned — same
  ordering guarantee as Condition B (nothing computed before those calls, nothing here
  mutates their inputs). `canonical_event_report` added to the results dict, additive-only.

## 3. Safety verification

Rather than a manual before/after diff script (Condition B's own approach, since no
established fast-test convention existed for it yet), this mission used
`run_condition_c_amem()`'s own pre-existing, monkeypatch-based fast-test convention
(`test_campaign_formal_checkpoint.py`) and extended it: new file
`test_campaign_formal_runner_h4_wire_c.py`, 9 tests, covering the same safety properties
Condition B's suite does (original result keys preserved, `canonical_event_report`
additive-only, trace/citation-diagnostic unaffected, canonical memory written and
findable, resolvable `config_fingerprint`, no resolution round-trip for DIRECT_ASSIGNMENT,
unresolved id counted honestly, add_memory call shape provably unchanged) plus one
Condition-C-specific test: the existing checkpoint/resume mechanism still works unaffected.

**One real bug found and fixed along the way, not merely a new test written:**
`test_campaign_formal_checkpoint.py`'s existing `patch_amem` fixture did not patch
`OUTPUT_DIR` — since `run_condition_c_amem()` previously had no dependency on it, this was
correct at the time it was written. This mission's own wiring introduced that dependency,
which meant, uncaught, every future run of that pre-existing test suite would have
silently written real files into the repo's actual
`phase3/experiments/results/canonical_store/` on disk. Caught by actually running that
test suite (not assumed safe), fixed additively (one new `monkeypatch.setattr(mod,
"OUTPUT_DIR", tmp_path)` line), confirmed clean afterward (`find ... -newer` check showed
no unexpected writes).

**`test_h2_r2_hardening.py::test_24_no_automatic_runtime_wiring`** — the same test H.4-WIRE
(Condition B) previously updated — needed a second, honest update: `run_condition_c_amem`
moved from the "must remain unwired" list to its own positive-presence check (mirroring
Condition B's). This is the expected, intended consequence of this mission's own explicit
scope, not a regression — the test now protects exactly two authorized exceptions instead
of one, and still fails loudly if either wiring is ever silently removed.

## 4. Regression

Full suite before this stage: 1596 passed baseline not yet established (rolling from prior
session state). Full suite after this stage and its two test fixes: **1596 passed**, 14
skipped (llama-server was live during this run, so those 3 tests executed rather than
skipped — unrelated to this mission), same single pre-existing unrelated memoryarena
fingerprint-drift failure.

## 5. What remains

Real (non-mock) execution against `RealAMemAdapter` — this mission wires the mechanism,
consistent with every prior H.4-* mission's separation of "build/wire" from "run for
real." A real Condition C campaign run (even a small sample, mirroring the Mem0/LoCoMo
smoke run) has not yet been attempted.

## 6. Compatibility

`canonical.py`, `ledger.py`, `canonical_write.py`, `canonical_event.py`, `event_ledger.py`,
`memory_versioning.py` — untouched. `run_condition_a`, `run_condition_b_mem0`,
`run_formal_c_locomo`, `run_formal_c_longmemeval`, `run_formal_c_longmemeval_worker`,
`merge_longmemeval_worker_checkpoints` — untouched.

## 7. Freeze status

Not a frozen decision — an implementation report for an additive extension.
