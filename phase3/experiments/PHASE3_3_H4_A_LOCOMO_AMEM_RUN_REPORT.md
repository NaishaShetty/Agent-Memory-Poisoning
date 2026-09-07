# Phase 3.3-H.4-A — Real, Sampled LoCoMo/A-MEM Counterfactual Run — Execution Report

Status: **COMPLETE, BUT INVALID AS A CROSS-FOUNDATION COMPARISON — a real, previously-
undiscovered bug was found and is reported prominently, not buried.** Execution report; no
code was modified as part of running this experiment (a separate bug-discovery
investigation, described in §2, did modify nothing either — read-only diagnosis).

## 1. Method

Identical to [PHASE3_3_H4_A_LOCOMO_SAMPLE_RUN_REPORT.md](PHASE3_3_H4_A_LOCOMO_SAMPLE_RUN_REPORT.md)
(Mem0), same `sample_locomo_tasks_formal(n=6)` call (same seed → same 6 real tasks, same 5
pools), swapped to `RealAMemAdapter` and the newly-wired Condition C canonical functions
(`write_canonical_record_and_alias_direct_assignment`,
`record_retrieval_and_selection_events_direct_assignment`) — the first real exercise of
that wiring against actual dataset content.

## 2. Result, and the bug that explains it

**Raw numbers: 30 comparisons, 6 `COUNTERFACTUALLY_INFLUENTIAL`, 24
`NOT_COUNTERFACTUALLY_INFLUENTIAL`, 0 inconclusive.** All 6 baseline tasks produced a
"None of the provided memories mention X" (or equivalent) response — the agent reported
being unable to answer for every single task, despite retrieving 5 memories each time.

**Root cause, traced and confirmed, not assumed:** `RealAMemAdapter.inspect_memory()`
(`foundations_real/amem_real_adapter.py`, lines ~304-323) constructs its return value as
`{"id": note.id, "links": ..., "tags": ..., "context": ...}` — it never includes
`note.content`, the actual memory text. Confirmed directly:

1. The canonical ledger's own stored record for one retrieved memory contains the correct,
   directly relevant text: `"Caroline: I went to a LGBTQ support group yesterday and it
   was so powerful."`
2. A standalone real probe — `add_memory()` that exact text, then `inspect_memory()` it —
   returned `{'id': 'x1', 'links': [], 'tags': ['locomo'], 'context': 'conv-26'}`. No
   content field anywhere in the response.
3. `runner.py::_extract_content_text()` checks `native.get("memory")`,
   `native.get("text")`, `native.get("content")` in order, finds none present, and falls
   back to `str(native)` — so the agent-visible memory content for every A-MEM memory in
   this run was literally the stringified metadata dict, never the real text.
4. `export_state()`, two methods below `inspect_memory()` in the same file, **does**
   include `"content": n.content` for the same underlying data — proving the content was
   always available to the adapter; `inspect_memory()` specifically omits it.

This is a genuine, pre-existing defect (not introduced this session, not touched by
H.4-WIRE-C's own wiring), invisible to every prior conformance check because
`inspect_memory()` still reports `REAL_FOUNDATION_CONFORMANCE` (the operation genuinely
executes and returns *something* real) — conformance tagging has no concept of "returned
the wrong shape." It was only surfaced by actually running a full retrieval→generation
cycle against real content and noticing the model's answers didn't make sense.

## 3. What this means for the numbers above

**The 6/30 `COUNTERFACTUALLY_INFLUENTIAL` count and the qualitative "A-MEM answers worse
than Mem0" impression are both artifacts of this bug, not a real signal about A-MEM's
memory quality, retrieval relevance, or counterfactual sensitivity.** With the model
never seeing real memory content, "masking one memory changed nothing" is exactly the
expected behavior of a model reasoning over five near-identical metadata stubs — there is
nothing to have an "influence" one way or the other. **This run cannot be used as the
"compare the two foundations under the same intervention protocol" result the user asked
for** — the protocol was not actually the same in substance, only in code path; A-MEM's
half of the comparison never received real evidence.

## 4. Explicit non-scope — the bug is reported, not fixed

Fixing `inspect_memory()` (adding `content` to its returned dict, presumably alongside
the existing `id`/`links`/`tags`/`context` fields, mirroring `export_state()`'s own shape)
is a real, adapter-behavior-changing edit that deserves its own reviewed pass — checking
whether anything else currently depends on `inspect_memory()`'s current (incomplete) shape,
whether `_extract_content_text()` needs a corresponding update once `content` is present,
and re-verifying Phase 3.2-H.4's own conformance claims are unaffected — not something to
bundle silently into an experiment-execution report. **Not performed here.**

## 5. Artifacts

`phase3/experiments/canonical_store/h4a-real-locomo-smoke-1-amem/` (note: this is the
actual location `open_pool_canonical_ledgers()` wrote to — `<experiments_dir>/
canonical_store/...`, not `<experiments_dir>/results/canonical_store/...`; the companion
Mem0 report's artifact path line should be read with the same correction) — 5 pools'
`memory`/`events`/`run_config`. `run_summary.json` (this run's own output location,
`phase3/experiments/results/canonical_store/h4a-real-locomo-smoke-1-amem/run_summary.json`)
has the full detail. Both kept as evidence.

## 6. What's actually needed for a valid comparison

1. Fix `inspect_memory()`'s missing `content` field (its own reviewed mission).
2. Re-run this exact same script (same 6 tasks, same seed) against the fixed adapter.
3. Only then compare against the Mem0 result — this run's numbers should be treated as
   void for comparison purposes, not as "A-MEM performed worse."

## 7. Addendum — corrected re-run against the fix (real, valid comparison)

Following [PHASE3_3_H4_AMEM_INSPECT_FIX_IMPLEMENTATION_REPORT.md](PHASE3_3_H4_AMEM_INSPECT_FIX_IMPLEMENTATION_REPORT.md),
the exact same script (identical `sample_locomo_tasks_formal(n=6)` seed, same 6 tasks, same
5 pools) was re-run against the fixed `RealAMemAdapter`, under a distinct campaign id
(`h4a-real-locomo-smoke-1-amem-fixed`) so the original void run's artifacts remain
untouched as a documented before/after pair, not overwritten.

**Result: 30 comparisons, 18 `COUNTERFACTUALLY_INFLUENTIAL`, 12 `NOT_COUNTERFACTUALLY_INFLUENTIAL`,
0 inconclusive** — now directly comparable to the Mem0 result (17/13/0).

| Task | A-MEM answer (post-fix) | Mem0 answer (same task) | Gold |
|---|---|---|---|
| `ecf5a096...` | "Caroline went to the LGBTQ support group yesterday." | Identical | "7 May 2023" |
| `9f278780...` | "Melanie painted the lake sunrise last year. [31b0e6cf...]" | Same substance, different citation id | "2022" |
| `6b06956f...` | "Last Wednesday. [f8d7bf45...]" | Same substance | "Wednesday before 9 Feb 2023" |
| `e24aa329...` | "None of the provided memories mention Sam's activities..." | Also failed to find it | "Attending a Weight Watchers meeting" |
| `afef9ecc...` | "Nate made vegan ice cream and shared it with his vegan diet group." | Same substance | "vegan ice cream" |
| `e9d52c07...` | "Calvin mentions being excited to explore streets similar to those in the photo Dave shared [56452a4f...]" | Same substance | "Shinjuku" |

**This is a real, meaningful cross-foundation comparison, not an artifact of the bug.**
Every A-MEM answer is now substantively equivalent to Mem0's own answer for the same task
(same content, occasionally with different citation-tag ids or bracket placement) — including
the one task (`e24aa329...`, the Weight Watchers task) where *both* foundations genuinely
failed to surface the gold answer, which is itself informative: that failure is now
attributable to retrieval/generation quality on a hard task, not to A-MEM's content being
invisible to the model. The overall influential rate (18/30 = 60% vs. Mem0's 17/30 = 57%)
is now close enough that neither foundation shows a dramatically different counterfactual
sensitivity on this small sample — a real, if preliminary, finding rather than the void
6/30 the bug produced.

**Artifacts**: `phase3/experiments/canonical_store/h4a-real-locomo-smoke-1-amem-fixed/`
(5 pools) and `phase3/experiments/results/canonical_store/h4a-real-locomo-smoke-1-amem-fixed/run_summary.json`.
The original void run's artifacts (`...-amem/`, without `-fixed`) are kept, untouched, as
the documented "before" state.

## 8. Freeze status

Not a frozen decision — a dated execution and bug-discovery record.
