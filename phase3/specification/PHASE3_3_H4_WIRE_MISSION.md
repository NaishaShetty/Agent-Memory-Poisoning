# Phase 3.3-H.4-WIRE — Live Canonical Event Emission for Condition B (Mem0) — Mission Brief

Status: **NOT STARTED**. Mission brief for an implementation pass, following
[PHASE3_3_H4_READINESS_ASSESSMENT.md](../experiments/PHASE3_3_H4_READINESS_ASSESSMENT.md)
§6 item 1. On completion, produce `PHASE3_3_H4_WIRE_IMPLEMENTATION_REPORT.md` under
`phase3/experiments/`.

**This mission carries materially higher stakes than any prior H.4-* mission.** Every
earlier mission (B, C, D, E, F, G, A) built and tested a standalone capability without
touching the code path that actually produced the frozen baseline campaign results. This
mission is the first to modify `campaign_formal_runner.py` itself — the module that ran
the real, hours-long, GPU-bound Mem0/A-MEM campaigns whose metrics this entire
strengthening effort exists to make trustworthy. A mistake here risks corrupting or
silently altering results from a real, expensive run, not just failing a unit test.
**Every requirement in §7 (validation-before-scale) is load-bearing, not optional
diligence.**

## 1. Problem, and what direct inspection found

The readiness assessment states plainly: no real campaign has ever emitted any of the new
instrumentation (`rejected`, `relationship_detected`, `config_fingerprint`-bearing
`retrieved`/`selected`, `counterfactually_influential`), because `campaign_formal_runner.py`
has **no reference anywhere** to `CanonicalMemoryLedger`, `CanonicalEventLedger`, or
`RunConfigLedger` — confirmed directly, not assumed (`grep` across the file found none).
Memories are ingested via a raw `foundation.add_memory(memory_id=source_id, content=...,
metadata=...)` call (line ~127); `run_agent_task()` is called directly (already returning
`AgentRunOutcome.retrieved_memory_ids`/`selected_memory_ids`, but nothing ever logs them to
a canonical event ledger); results are recorded via the pre-existing, separate
`evaluate_and_trace_with_identity()` trace/metrics layer, which this mission must not
touch or alter.

**A second, harder problem was found by reading `agent_runtime/identity.py`:** Condition B
(Mem0) uses `STRATEGY_METADATA_LOOKUP` — Mem0 does **not** reliably honor a caller-supplied
memory id, so the id `run_agent_task()`'s `AgentRunOutcome.retrieved_memory_ids`/
`selected_memory_ids` actually contains is Mem0's own **vendor-native** id, not the
original dataset source id. Resolving vendor-native ids back to canonical/source ids
requires exactly the machinery `resolve_source_identity()`/`resolve_source_identities()`
already provide (one real `inspect_memory()` call per id, reading a `source_memory_id`
metadata key) — and that resolution can legitimately fail (`STATUS_NOT_RESOLVABLE`,
`STATUS_INSPECT_UNAVAILABLE`), which this mission must handle explicitly, never silently.

**This mission is scoped to Condition B (Mem0) only.** Condition C (A-MEM) uses the
simpler `STRATEGY_DIRECT_ASSIGNMENT` (no lookup round-trip needed) and is a natural,
smaller follow-up once this mission's pattern is proven — attempting both conditions in one
mission would double the risk surface for a first attempt at something this consequential.

## 2. Relationship to frozen/existing files

- H.1/H.2/H.3(+R+R2) canonical files — **call only.** No modification.
- `canonical_write.py::write_canonical_memory()` (H.1) — call only; this is the existing,
  documented ingestion bridge and must be used in place of a hand-rolled second write path.
- `agent_runtime/identity.py` — call only (`resolve_source_identities`,
  `STRATEGY_METADATA_LOOKUP`, `IdentityResolution`, `STATUS_RESOLVED`/
  `STATUS_NOT_RESOLVABLE`/`STATUS_INSPECT_UNAVAILABLE`). Do not build a second identity-
  resolution mechanism — this module already solves exactly the problem this mission needs
  solved.
- `agent_runtime/trace.py::evaluate_and_trace_with_identity()` — **must not be modified,
  and its own call and return value in `run_condition_b_mem0()` must be left completely
  unchanged.** This mission's new canonical-ledger calls run *alongside* it, never replacing
  or altering any of its inputs/outputs. The existing trace/metrics output for any campaign
  run after this mission must be byte-for-byte identical to what it would have been before
  this mission, for the same inputs (§7 requires proving this).
- `agent_runtime/runner.py::run_agent_task()`/`AgentTaskInput`/`AgentRunOutcome` — call
  only, already returns everything needed (`retrieved_memory_ids`, `selected_memory_ids`).
- `run_config.py`, `canonical_event.py`, `event_ledger.py` — call only, reuse the existing
  `RunConfigRecord`/`RunConfigLedger`/`CanonicalEvent`/`CanonicalEventLedger` APIs exactly
  as H.4-F/H.4-BC built them.
- `campaign_formal_runner.py` — **the one file this mission modifies**, and only
  `run_condition_b_mem0()` within it (plus, if needed, a small new helper module for the
  canonical-ledger wiring logic itself, to keep the diff to `campaign_formal_runner.py`
  additive and easy to review). Do not touch `run_condition_a`, `run_condition_c_amem`,
  `run_formal_c_locomo`, `run_formal_c_longmemeval`, or any worker/checkpoint logic.

## 3. Deliverable 1 — canonical ledger construction, once per pool

Alongside the existing `foundation = RealMem0Adapter()` / `foundation.initialize(...)` /
`foundation.reset()` sequence (lines ~104-121), construct:

- A `CanonicalMemoryLedger` + `CanonicalEventLedger` + `RunConfigLedger`, storage location
  scoped per campaign+pool (e.g. under a new, explicit directory —
  `phase3/experiments/canonical_store/<campaign_id>/<dataset>-<pool_key>/` or equivalent;
  exact path scheme is an implementation decision, but must be documented and must not
  collide with any existing storage convention).
- One `RunConfigRecord` for this pool's retrieval/selection configuration:
  `embedding_model="sentence-transformers/all-MiniLM-L6-v2"` (the existing literal at line
  107), `retrieval_k=5` (the existing literal), `retrieval_mechanism`/`selection_mechanism`
  descriptive strings (e.g. `"mem0_dense_retrieve"` / `"select_from_retrieved_top_k"` —
  document the actual mechanism honestly, including that the current provisional selection
  policy is a no-op slice, per §6), `adapter_revision` from
  `foundation.foundation_identity().adapter_version` (already computed elsewhere in this
  codebase — reuse the same accessor `agent_runtime/runner.py` itself uses). Append it once
  to `RunConfigLedger`, obtain its `config_fingerprint`, reuse that same fingerprint for
  every `retrieved`/`selected` event this pool produces (all tasks in one pool share one
  retrieval configuration by construction, since embedding model/k/mechanism don't change
  per task).

## 4. Deliverable 2 — canonical memory writes at ingestion

Replace the ingestion loop's raw call:

```python
add_field = foundation.add_memory(
    memory_id=source_id,
    content={"text": f"{row['source_role']}: {row['content']}"},
    metadata={"user_id": f"g-{dataset}-{pool_key}", "source_memory_id": source_id},
)
```

with `write_canonical_memory()` (H.1), constructing the `CanonicalMemoryRecord` with
`memory_id=source_id` (the dataset's own stable Phase 2 UMR identifier — already unique,
already what the raw call passes as the vendor-requested id today) and the same
`content`/`metadata`. **Verify during implementation that `write_canonical_memory()`'s
underlying call to the foundation adapter is the exact same `add_memory(memory_id, content,
metadata)` shape this loop already uses** (per H.1's own design doc, it should be) — if it
is not, STOP and report the discrepancy rather than silently adapting around it, since a
different call shape could change what actually gets ingested into Mem0, which is exactly
the kind of change this mission must not make.

`ingested_ids` (already tracked for the trace layer) continues to be populated exactly as
today — this mission only adds the canonical-ledger side effect alongside the existing one,
never changes what `ingested_ids` contains or how it's used downstream.

## 5. Deliverable 3 — resolved `retrieved`/`selected`/`rejected` events, once per task

After `run_agent_task()` returns `outcome` (line ~146), and *before or after*
`evaluate_and_trace_with_identity()`'s own call — order must not affect that call's own
inputs — resolve identity and append events:

1. `resolutions = resolve_source_identities(foundation, outcome.retrieved_memory_ids)` —
   reuse `agent_runtime.identity`'s existing function directly.
2. For each `foundation_memory_id` in `outcome.retrieved_memory_ids`:
   - If `resolutions[fid].status == STATUS_RESOLVED`: use `resolutions[fid]
     .source_memory_id` as the canonical `memory_id` for this event.
   - If not resolved (`STATUS_NOT_RESOLVABLE`/`STATUS_INSPECT_UNAVAILABLE`): **do not
     construct a `retrieved` event for this id at all** — record it in a per-task
     unresolved-id count/list that the implementation report must surface honestly (§8),
     never silently dropped without a trace, and never fabricate a canonical id for it.
3. For each resolved id: append a `retrieved` `CanonicalEvent`
   (`task_id=outcome.task_id`, `config_fingerprint` from §3, `actor="candidate_discovery"`,
   `reason` documenting the retrieval call).
4. For each resolved id that is also in `outcome.selected_memory_ids` (resolved the same
   way): append a `selected` `CanonicalEvent` (same `config_fingerprint`,
   `actor="evidence_selection"`).
5. For each resolved id that is **not** in the resolved selected set: append a `rejected`
   `CanonicalEvent` with `reason` — given the current provisional `select_from_retrieved()`
   policy (`runner.py`) takes the same `top_k` as retrieval itself, this set is expected to
   be **empty in practice today** (§6) — but the code path must still exist and be correct,
   not merely untested, since a future, real selection policy will populate it.
6. Every appended event must reference this pool's own `CanonicalMemoryLedger` linkage —
   i.e., every resolved `memory_id` must already exist in the `CanonicalMemoryLedger` from
   §4's ingestion step. If a resolved id does *not* exist there (e.g. a Mem0-internal
   memory this framework never ingested, which should not happen given Condition B only
   ever ingests through this loop, but must not be assumed) — this is the same "unresolved"
   handling as step 2: record and report, never silently skip without a trace, never invent
   a canonical record on the fly at event-append time.

## 6. Explicit, honest documentation requirement — the `rejected` event's near-vacuity today

State clearly, in both a code comment at the wiring site and the implementation report:
`runner.py::select_from_retrieved()`'s current provisional policy
(`retrieved_memory_ids[:top_k]`) is applied to a `retrieved_memory_ids` sequence that
`_retrieve_and_select()` already capped at the same `top_k` via the `foundation.retrieve()`
call itself — so for Condition B's current configuration, `selected_memory_ids` will
typically equal `retrieved_memory_ids` exactly, and the `rejected` event path built in this
mission will rarely or never fire in practice. **This is not a bug in this mission's
wiring** — it is an accurate reflection of the current, still-provisional selection policy
(`memory_schema.md §8` explicitly defers the real creation/selection policy). Do not
"fix" this by inventing a stricter selection policy as part of this mission — that is a
separate, out-of-scope decision.

## 7. Validation-before-scale — mandatory, not optional

Given this mission touches the real campaign path, before any full-scale or checkpointed
run is attempted with this new wiring:

1. **A small, synthetic dry run** (a tiny, locally-constructed pool — 2-3 fabricated tasks
   over a handful of memories, not a real dataset pool) must be executed end to end,
   confirming: ingestion succeeds via `write_canonical_memory()`, canonical events are
   correctly appended and resolvable, and — critically — the `evaluate_and_trace_with_
   identity()` trace output for each task is **identical** (same fields, same values) to
   what a parallel run of the *unmodified* `run_condition_b_mem0()` (or an equivalent
   before/after diff) would produce for the same synthetic inputs. This is the concrete
   proof that this mission's changes are additive and non-interfering, not an assumption.
2. **No full real-dataset campaign run is required or expected as part of this mission.**
   Actually re-running LoCoMo/Mem0 at scale with this wiring (which the readiness
   assessment's punch list item 3 will eventually want) is a separate, later, explicitly
   authorized action — do not perform it as part of this mission without being told to.
3. If the dry run in item 1 reveals *any* divergence in the existing trace output, STOP —
   do not proceed to report completion — and treat it as this mission having failed its
   own core safety requirement, regardless of how correct the canonical-ledger side of the
   wiring otherwise looks.

## 8. Invariants to implement and test

1. `evaluate_and_trace_with_identity()`'s call signature, inputs, and return value are
   byte-for-byte unchanged from before this mission, for identical upstream inputs
   (verified per §7).
2. Every appended `retrieved`/`selected`/`rejected` event references a `config_fingerprint`
   resolvable in that pool's own `RunConfigLedger` (H.4-F's own invariant, exercised for
   the first time against real, non-test data here).
3. Every appended event's `memory_id` already exists in that pool's `CanonicalMemoryLedger`
   before the event referencing it is appended (never a dangling reference).
4. An unresolvable retrieved/selected id never silently disappears — it is counted and
   reported per task, never merely absent with no trace.
5. `write_canonical_memory()`'s underlying foundation call is provably the same shape the
   pre-existing raw `add_memory()` call used (§4).

## 9. Explicit non-scope for this stage

- Condition C (A-MEM) — a separate, smaller follow-up mission once this pattern is proven.
- Condition A (no-memory control) — nothing to wire; there is no foundation/retrieval to
  instrument.
- Re-running any full real campaign at scale.
- Fixing the `select_from_retrieved()` provisional policy so `rejected` events actually
  fire in practice (§6) — a separate, future policy decision.
- Initiative D's real qualification run, Initiative A's real counterfactual run — both
  remain separate, later punch-list items; this mission only makes the ledger the
  live campaign path actually writes to, exist and be populated for the first time.

## 10. Deliverables checklist

- [ ] `run_condition_b_mem0()` updated (additive around the existing logic, per §3-§5).
- [ ] Canonical ledger storage path scheme documented.
- [ ] The synthetic dry-run proof (§7 item 1), with before/after trace-output comparison
      included or referenced in the implementation report.
- [ ] Full existing regression suite re-run with zero regressions.
- [ ] `PHASE3_3_H4_WIRE_IMPLEMENTATION_REPORT.md`: the dry-run comparison result, the
      unresolved-id handling behavior observed (if any occurred during the dry run), and
      an explicit statement that no full real-dataset campaign was run.
- [ ] No modification to `evaluate_and_trace_with_identity()`, `run_condition_a`,
      `run_condition_c_amem`, or any H.1/H.2/H.3 canonical file.

## 11. Definition of done

Complete when: canonical ledgers are constructed per pool and populated via
`write_canonical_memory()` and resolved `retrieved`/`selected`/`rejected` events for
Condition B (Mem0) only; identity resolution reuses `agent_runtime.identity` without a
second mechanism; the dry-run proof in §7 shows zero divergence in existing trace output;
all invariants (§8) pass; the regression suite shows zero regressions. This unblocks
readiness-assessment punch-list items 2 and 3 (a real Initiative D qualification run and a
real Initiative A counterfactual run) for the Mem0 pairing specifically — both remain
separate, subsequent missions, not part of this one.
