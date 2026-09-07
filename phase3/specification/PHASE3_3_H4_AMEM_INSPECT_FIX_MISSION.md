# Phase 3.3-H4-AMEM-INSPECT-FIX — `RealAMemAdapter.inspect_memory()` Missing Content Field — Mission Brief

Status: **NOT STARTED**. Mission brief for an implementation pass. On completion, produce
`PHASE3_3_H4_AMEM_INSPECT_FIX_IMPLEMENTATION_REPORT.md` under `phase3/experiments/`.

**Origin:** discovered while running a real, sampled LoCoMo/A-MEM counterfactual
experiment (not while writing or reviewing code) — see
[PHASE3_3_H4_A_LOCOMO_AMEM_RUN_REPORT.md](../experiments/PHASE3_3_H4_A_LOCOMO_AMEM_RUN_REPORT.md)
for the full discovery trace. This is a real, pre-existing bug (not introduced by any
Phase 3.3-H.4-* work), invisible to every prior conformance check because
`inspect_memory()` genuinely executes and returns *something* real — conformance tagging
has no concept of "returned the wrong shape." It was only found by running a full
retrieval→generation cycle against real content and noticing the model's answers made no
sense (it answered "none of the provided memories mention X" for every task in that run).

## 1. Root cause — confirmed by direct comparison, not inference

`foundations_real/amem_real_adapter.py::RealAMemAdapter.inspect_memory()` (lines
~304-323):

```python
note = self._mem.memories.get(memory_id)
...
return FoundationField(
    value={"id": note.id, "links": list(note.links), "tags": list(note.tags), "context": note.context},
    ...
)
```

**`note.content` — the actual memory text — is never included.** Confirmed two ways:

1. A real, standalone probe (`add_memory()` real text, then `inspect_memory()` it) under
   `C:\h4venv` returned `{'id': 'x1', 'links': [], 'tags': ['locomo'], 'context':
   'conv-26'}` — no content anywhere.
2. `export_state()`, two methods below in the same file, **does** include
   `"content": n.content` for the identical underlying `MemoryNote` objects (`memory_id`,
   `content`, `links`, `tags` — confirmed by reading that method directly). The data is
   always available on the object; `inspect_memory()` specifically drops it.
3. `agentic_memory/memory_system.py::MemoryNote.__init__` (the cloned real library, pinned
   commit per `AMEM_SYS_SOURCE`) confirms `self.content = content` is a plain string
   attribute — nothing exotic, no reason it couldn't be included.

**Downstream consequence, traced through the actual call chain:**
`agent_runtime/runner.py::_extract_content_text()` checks, in order,
`native.get("memory")`, `native.get("text")`, `native.get("content")` — finds none present
in A-MEM's current `inspect_memory()` shape, and falls back to `str(native)`, i.e. the
stringified `{id, links, tags, context}` dict becomes the agent-visible "memory content"
for every A-MEM memory, in every condition-C task, ever. This is not scoped to the
counterfactual experiment that found it — it affects **any** real A-MEM run that has ever
gone through `runner.py::run_agent_task()`'s retrieval path, including whatever the
original G.1-adjacent A-MEM probe/campaign work produced.

## 2. The fix

Add `note.content` to `inspect_memory()`'s returned dict, in both the diagnostic
`_record(native_result=...)` call and the actual `FoundationField.value` returned to the
caller:

```python
self._record(
    "INSPECT_MEMORY",
    conformance_tag=REAL_FOUNDATION_CONFORMANCE,
    code_path_executed=True,
    native_result=None if note is None else {
        "id": note.id, "content": note.content, "links": list(note.links), "tags": list(note.tags),
    },
)
if note is None:
    return FoundationField(value=None, availability=FOUNDATION_UNAVAILABLE, operation="inspect_memory")
return FoundationField(
    value={"id": note.id, "content": note.content, "links": list(note.links), "tags": list(note.tags), "context": note.context},
    availability=FOUNDATION_AVAILABLE,
    operation="inspect_memory",
    note="Native note-linking structure preserved (links/tags/context) AND content included "
    "(Phase 3.3-H4-AMEM-INSPECT-FIX: content was previously, incorrectly, omitted).",
)
```

**Why this is the correct, minimal fix:** it adds exactly the one missing field, in the
exact key name (`"content"`) `_extract_content_text()` already checks for (third priority,
after `"memory"`/`"text"`) — no change needed to `runner.py` at all. It does not remove or
rename `id`/`links`/`tags`/`context` — every existing consumer of those fields is
unaffected. It matches `export_state()`'s own field-naming precedent exactly
(`"content": n.content`), so the adapter is now internally consistent between its two
methods that both expose note data.

**Why not fix this by changing `_extract_content_text()` instead:** the bug is that A-MEM
never sends content at all — no reordering or new fallback key in the generic extraction
helper would help, since the key genuinely isn't present in the payload today. Fixing the
adapter (the actual data source) is the only fix that addresses the root cause rather than
adding a second workaround on top of a still-broken adapter.

## 3. What must be re-verified before this is considered safe

1. **`test_foundation_conformance_h4.py`'s existing A-MEM tests must still pass
   unchanged.** Direct inspection during this mission's preparation found the one existing
   call (`adapter.inspect_memory("note-1")`, line ~342) does not assert on the returned
   shape at all — a smoke check only — so adding a field should not break it. Confirm this
   by running the file, not by assuming it from this reading alone.
2. **No other caller anywhere in the codebase reads `inspect_memory()`'s A-MEM return
   value and asserts an exact, closed key set** (as opposed to checking for the presence
   of specific keys it expects) — grep for `inspect_memory` across the repo and check each
   call site before declaring this safe, not just the ones already found during this
   mission's own preparation (`runner.py`, `test_foundation_conformance_h4.py`).
3. **`RealConformanceRecord`'s own tag for `INSPECT_MEMORY` remains
   `REAL_FOUNDATION_CONFORMANCE`** — this fix does not change whether the operation is
   real, only what it returns; Phase 3.2-H.4's own conformance claims for A-MEM are
   unaffected by construction, but confirm by re-running that file's A-MEM tests under
   `C:\h4venv` (not just the mock-based main-environment suite), since that is the
   authoritative environment those claims were originally made against.
4. **A minimal, direct re-run of the standalone probe** from
   [PHASE3_3_H4_A_LOCOMO_AMEM_RUN_REPORT.md](../experiments/PHASE3_3_H4_A_LOCOMO_AMEM_RUN_REPORT.md)
   §2 item 2 (add the same real text, `inspect_memory()` it, confirm `content` is now
   present and correct) — proof the fix actually works, not just that it compiles.

## 4. Explicit non-scope for this stage

- Re-running the full A-MEM/LoCoMo counterfactual sample against the fix — a separate,
  follow-up action once this fix is verified in isolation (§3), not part of this mission's
  own definition of done. State clearly in the implementation report whether it was
  additionally performed.
- Any change to `export_state()`, `add_memory()`, `retrieve()`, `update_memory()`,
  `delete_memory()`, `reset()`, `shutdown()`, or `foundation_identity()` — this mission
  touches `inspect_memory()` only.
- Any change to `runner.py::_extract_content_text()` — per §2's own reasoning, none is
  needed.
- Re-litigating whether A-MEM's real qualification result
  ([PHASE3_3_H4_D_A_RUN_REPORT.md](../experiments/PHASE3_3_H4_D_A_RUN_REPORT.md)) is
  affected — it is not: the qualification harness never calls `inspect_memory()` (it
  compares canonical-ledger-reconstructed relationship graphs, built from `write_
  canonical_memory()`/event data, never from a foundation's own `inspect_memory()`
  return value). Confirm this by grep, not assumption, but do not spend mission time
  re-running qualification unless that grep turns up something unexpected.

## 5. Deliverables checklist

- [ ] The field addition in `inspect_memory()` (§2), and nowhere else in that file.
- [ ] `test_foundation_conformance_h4.py`'s A-MEM tests re-run and confirmed passing,
      under both the main environment and `C:\h4venv` (§3 items 1, 3).
- [ ] Full repository-wide grep for `inspect_memory` call sites, each one checked for
      shape assumptions (§3 item 2), documented in the report even if none were found
      broken.
- [ ] The standalone re-probe (§3 item 4), with its output included in the report.
- [ ] Full existing regression suite re-run, before/after counts.
- [ ] `PHASE3_3_H4_AMEM_INSPECT_FIX_IMPLEMENTATION_REPORT.md`: root cause restated, the
      fix, all three re-verification results, and an explicit statement of whether the
      A-MEM/LoCoMo counterfactual sample was re-run against the fix (§4).
- [ ] No modification to any file other than `foundations_real/amem_real_adapter.py`.

## 6. Definition of done

Complete when: `inspect_memory()` returns `content` alongside its existing fields; the
standalone probe confirms real, correct content comes back; all existing A-MEM-touching
tests pass under both environments; a full-repo grep for other `inspect_memory()`
consumers turns up nothing broken (or, if something is found, it is fixed or explicitly
flagged, not silently left inconsistent); the regression suite shows zero unexpected
regressions. This unblocks a valid re-run of the A-MEM/LoCoMo counterfactual comparison
against Mem0 — the actual, original goal the bug was found while pursuing.
