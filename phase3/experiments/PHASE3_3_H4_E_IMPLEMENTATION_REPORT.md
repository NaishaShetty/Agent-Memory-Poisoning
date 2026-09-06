# Phase 3.3-H.4-E — Content-Level Leakage Gate — Implementation Report

Status: **COMPLETE**.

## 1. Scope correction, confirmed

Direct inspection confirmed the mission's own corrected premise: `boundary.py` (Phase
3.2-B) and `security/leakage.py` (Phase 3.2-F) already provide a strong, live, wired
structural/key-based leakage gate. `leakage.py`'s own docstring explicitly disclaims content
-level detection ("cannot catch semantic leakage smuggled entirely inside a string
value... that is NOT this module's job"). This stage builds exactly that one disclaimed
gap, additively, alongside the existing gates — it does not rebuild them.

## 2. Deliverable 1 — `content_leakage.py`

New module: `scan_for_gold_content(assembled_payload, evaluator_reference, *, min_length,
fields)` → `ContentLeakageResult`. Exact substring matching, **case-sensitive** (§4.2's
recommended conservative default), minimum match length **8 characters** (§4.1's
recommended threshold) — a gold value shorter than this is recorded as
`FINDING_SKIPPED_TOO_SHORT`, never silently treated as clean. Two text surfaces are built
and checked per gold value: a `raw_form` (every string leaf value in the structure, joined
by newlines — the literal, unescaped text) and a `serialized_form`
(`json.dumps(..., ensure_ascii=True)` of the whole structure) — plus the JSON-escaped form
of the gold value itself checked against both, so a leak that only matches after JSON
escaping (e.g. a literal `\uXXXX` sequence already present in stored text) is still caught
(mission section 8, item 3). No semantic/paraphrase detection is attempted or claimed
(§4.2, documented explicitly in the module docstring).

Accepts either a `Mapping` (a pre-render `AgentVisibleContext`-shaped dict), a rendered
message list (`[{"role":..., "content":...}, ...]`), or a plain `str` — see section 3 for
which shape is actually used at the live wiring point.

## 3. Wiring — which call site, and why not the other one

**Wired**: `integration/pipeline.py::evaluate_case()`, immediately alongside the two
existing structural checks, fail-closed (raises `ContentLeakageDetectedError` immediately
on detection — the case's execution does not proceed).

**Not wired**: `agent_runtime/runner.py::run_agent_task()` — verified during
implementation, per the mission's own anticipated caveat: `AgentTaskInput`/
`run_agent_task()` structurally carry no `evaluator_reference` parameter at all (by
design, per that module's own "the evaluator must remain outside the agent" docstring), so
there is no point inside it where a gold value is legitimately in scope to check against.
`pipeline.py` itself never calls `render_messages()` either (its synthetic-agent path hands
`case.agent_visible_context` directly to `agent.outcomes.run_synthetic_agent()`) — so the
payload actually scanned at the one real wiring point is the **pre-render
`agent_visible_context` dict**, not a rendered message list, contrary to the mission's own
stated recommendation (which assumed a rendered-message call site would be reachable; it is
not, in this codebase's actual structure). `scan_for_gold_content()` itself still supports a
rendered-message-list input (tested directly:
`test_rendered_message_list_input_shape_is_supported`) for a future call site, but none
exists today.

## 4. Discovered false-positive problem, and the resulting scope decision (read before use)

Wiring an unscoped `scan_for_gold_content(case.agent_visible_context,
case.evaluator_reference)` broke **11 pre-existing, legitimate tests**
(`test_evaluation_integration.py` and others). Root cause, confirmed directly against the
failing fixtures: `GOLD_EVIDENCE`/`RETRIEVED_MEMORY`-condition test fixtures throughout this
codebase deliberately give the agent a memory whose `content` text **literally states** the
fact the gold answer restates (e.g. memory content `"Caroline attended the LGBTQ support
group on May 8, 2023."`, `gold_answer = "May 8, 2023"`) — this is not leakage, it is the
intended shape of correctly-exposed evidence. A second, analogous case was found for gold
evidence IDs: a correctly retrieved/selected memory's own `memory_id` field legitimately
**equals** a `gold_evidence_ids` entry whenever retrieval/selection worked correctly — that
equality is what "the right evidence was exposed" means.

Resulting, documented design decision (`content_leakage.py`'s own "WHY `gold_answer` IS
SCOPED DIFFERENTLY" docstring section; `pipeline.py`'s wiring comment): the wiring makes
**two separate scans over two different, narrower payload views**, not one scan over the
whole context:

1. `gold_answer` — scanned against `case.agent_visible_context` with the entire
   `memory_content` key removed (`task` and any other top-level keys only). Catches a gold
   answer leaking somewhere OTHER than the legitimately-exposed evidence content.
2. `gold_evidence_ids` — scanned against `case.agent_visible_context` with each
   `memory_content` entry's own `memory_id` key removed (its `content` text and any other
   entry keys are kept). Catches an evidence id string appearing inside a memory's
   free-text content (which has no legitimate explanation) while excluding the memory's own
   `memory_id` field (which legitimately equals a gold evidence id for correctly-exposed
   evidence).

`scan_for_gold_content()` itself remains general-purpose and unscoped by default (its
`fields` parameter, new in this stage, lets a caller restrict which gold field to check) —
this narrowing is a wiring-site decision alone; every invariant/adversarial-case test in
`test_content_leakage.py` exercises the general function directly, unscoped, and two
dedicated end-to-end tests (`test_pipeline_wiring_does_not_raise_when_answer_only_in_
legitimate_evidence`, `test_pipeline_wiring_raises_when_gold_evidence_id_leaks_into_memory_
content`) prove the wiring-level scoping decision itself is correct in both directions.

## 5. Deliverable 2 — fail-closed enforcement

Confirmed, before wiring: the two PRE-EXISTING structural checks at this call site
(`validate_agent_visible_context_shape()`, `sec_leakage.validate_against_boundary()`) only
ever **collect** their results into `warnings`/`leakage_result` — neither currently raises
on a detected violation at this call site. This is a pre-existing, separate observation
(not this mission's remit to fix, per mission section 5's own explicit deferral) and is
recorded here, not silently fixed alongside this mission's own change. This stage's new
check is fail-closed as specified: `ContentLeakageDetectedError` is raised immediately,
stopping the case, the moment either of the two scoped scans returns
`CONTENT_LEAKAGE_DETECTED`.

## 6. Deliverable 3 — extended self-check convention

`test_content_leakage.py` extends (does not replace) `test_leakage.py`'s established
source-text-scan pattern: `content_leakage.py` is checked for forbidden imports, direct
dataset loading, and real dataset path tokens, exactly mirroring `_SECURITY_MODULES`'s
existing parametrization. A new, symmetric check
(`test_agent_side_modules_never_import_content_leakage`) proves `agent/conditions.py`,
`agent_runtime/messages.py`, and `agent_runtime/runner.py`'s own source never imports
`content_leakage` — the direct generalization of the existing "no `EvaluatorReference`
param" property to this stage's new module — plus a structural signature check that
`render_messages()`/`run_agent_task()` accept no `evaluator_reference`-shaped parameter.

## 7. Explicit non-scope / deferred (mission section 9)

- `boundary.py`/`leakage.py` — untouched, reused only.
- Semantic/paraphrase/embedding-based detection — explicitly out of scope (§4.2).
- Re-auditing/fixing the two pre-existing structural checks' own non-fail-closed posture at
  this call site — flagged (section 5 above), not fixed.
- **The historical baseline campaign (LoCoMo/LongMemEval × Mem0/A-MEM) was NOT
  retroactively re-scanned through this new check.** This is a valuable, separate follow-up
  execution step (would require re-loading each historical case's `agent_visible_context`
  and `evaluator_reference` and running them through `scan_for_gold_content()`), not part of
  building the checker itself, and was not performed as part of this stage.
- Initiatives A, D, G — unrelated.

## 8. Files touched

- `phase3/evaluation/security/content_leakage.py` — new module.
- `phase3/evaluation/integration/pipeline.py` — additive: one new import, the two-scan
  fail-closed check block inside `evaluate_case()`, immediately after the two existing
  structural checks. No existing line was removed or altered in behavior.
- `phase3/evaluation/tests/test_content_leakage.py` — new, 33 tests covering mission
  sections 7 and 8, plus end-to-end wiring tests.

**Untouched, as required:** `contracts/boundary.py`, `security/leakage.py`,
`agent/conditions.py`, `agent_runtime/messages.py`, `agent_runtime/runner.py`, H.1/H.2/H.3
canonical files.

## 9. Tests

**Before H.4-E (this session's own baseline, carried over from the H.4-D report):**
`python -m pytest phase3/evaluation/tests/ -q` → **1485 passed, 1 failed, 17 skipped**
(342.30s). The one failure is the same pre-existing, unrelated dataset-fingerprint drift
reported in every prior H.4 report this session.

**After H.4-E:** **1518 passed, 1 failed (the same pre-existing failure), 17 skipped**
(294.22s) — exactly `1485 + 33` new tests, zero regressions, identical failure and skip
counts. (The interim discovery-and-fix cycle — 11 tests broken by an initially unscoped
wiring, then fixed by the scoping decision in section 4 — is captured here as the
before/after delta across the whole session, not as a reported regression: the final
committed state introduces zero regressions relative to the H.4-D baseline.)

**New H.4-E tests only:**
`python -m pytest phase3/evaluation/tests/test_content_leakage.py -q` →
**33 passed** (0.17s).

## 10. Definition of done — checklist

- [x] `content_leakage.py` — `scan_for_gold_content()`, `ContentLeakageResult`, minimum-
      length guard (8 chars), case-sensitive exact matching, both documented explicitly.
- [x] Wired into `integration/pipeline.py`, fail-closed, at the one call site where both
      `agent_visible_context` and `evaluator_reference` are legitimately in scope together
      — documented why `runner.py` was confirmed not to be a second viable wiring point.
- [x] Self-checks extending `test_leakage.py`'s convention, in `test_content_leakage.py`.
- [x] All invariants (section 7) and adversarial cases (section 8) tested.
- [x] Full regression suite shows zero regressions (1485→1518 passed, same 1 pre-existing
      unrelated failure, same 17 skipped).
- [x] This report states: wired only at `pipeline.py::evaluate_case()` (not `runner.py`);
      threshold=8 chars, case-sensitive; historical baseline campaign was NOT re-scanned.
- [x] No modification to `boundary.py`, `leakage.py`, or any agent-side module beyond the
      new self-check proving they do not import `content_leakage`.

This closes the one gap `security/leakage.py` itself explicitly disclaims, completing
Initiative E per `MEMORY_FOUNDATION_STRENGTHENING_PLAN_REVISED.md` §5.
