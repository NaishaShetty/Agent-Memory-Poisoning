# Phase 3.3-H.4-E — Content-Level Leakage Gate — Mission Brief

Status: **NOT STARTED**. Mission brief for an implementation pass, in the same role
[PHASE3_3_H4_BC_MISSION.md](PHASE3_3_H4_BC_MISSION.md),
[PHASE3_3_H4_F_MISSION.md](PHASE3_3_H4_F_MISSION.md), and
[PHASE3_3_H4_D_MISSION.md](PHASE3_3_H4_D_MISSION.md) played for the completed H.4-BC/F/D
stages. Covers **Initiative E only**, per
[MEMORY_FOUNDATION_STRENGTHENING_PLAN_REVISED.md §5](MEMORY_FOUNDATION_STRENGTHENING_PLAN_REVISED.md).
On completion, produce `PHASE3_3_H4_E_IMPLEMENTATION_REPORT.md` under
`phase3/experiments/`.

## 1. Problem — corrected understanding from repo inspection

The strengthening plan's Initiative E assumed the leakage audit is "currently a manual/
procedural checklist" and proposed building two enforcement layers (static import-graph,
runtime substring-scan) from scratch. **Direct inspection during this mission's
preparation found this premise is substantially wrong**, and the mission scope is
corrected accordingly:

- `phase3/evaluation/contracts/boundary.py` (Phase 3.2-B) already provides
  `validate_agent_visible()`: a recursive, key-name-based forbidden-field scanner
  (`FORBIDDEN_KEYS`) over any agent-visible payload.
- `phase3/evaluation/security/leakage.py` (Phase 3.2-F) already extends this with a wider
  protected-field set, dataclass/tuple descent (catching `MetricResult`/
  `AgentExecutionResult` instances embedded as leaf values, not just dict keys), a
  `MetricResult`-*shape* detector (structural, not name-based), a JSON serialization
  round-trip check, and a condition-aware wrapper (`validate_no_leakage`).
- **Both are already wired as live, automated gates in the actual execution path**, not
  merely unit-tested in isolation:
  - `agent/conditions.py::build_agent_visible_context()` calls `validate_agent_visible()`
    before returning (construction-time gate).
  - `agent_runtime/runner.py` calls `validate_no_leakage()` at its own call site (line 277
    at time of writing).
  - `integration/pipeline.py` calls `sec_leakage.validate_against_boundary()` at its own
    call site (line 423 at time of writing), where `case.evaluator_reference` (containing
    `gold_answer`/`gold_evidence_ids`) is already in scope for the same task `case`.
- `security/leakage.py`'s own docstring is explicit about what it deliberately does **not**
  do: *"STRUCTURAL, KEY-BASED DETECTION ONLY — NOT A GENERAL SOLUTION... does not perform
  any content/semantic/steganography analysis... cannot catch semantic leakage smuggled
  entirely inside a string value (e.g. an agent-visible observation whose free text
  happens to literally restate a gold answer) — that is NOT this module's job and is
  explicitly out of scope."*
- `test_leakage.py`/`test_reproducibility.py` already include a self-check pattern this
  mission should extend rather than replace: a source-text scan of a module's own code for
  forbidden import statements and forbidden path tokens (`"data/raw"`, `"data/processed"`,
  `"data/metadata"`, `"data/reports"`) — this is functionally the "static layer" the
  original plan asked for, already established as a convention, just not yet applied to
  every module this mission needs it applied to.

**Corrected scope:** this mission does not rebuild the structural/key-based leakage audit
— it exists, is strong, and is already live. This mission builds and wires the **one
specific, explicitly-disclaimed gap**: a per-task, content-level check that the exact
assembled reasoning-context payload for task `T` does not contain `T`'s own gold-answer
text or gold-evidence-ID value(s) as a literal substring, anywhere the existing key-based
checks structurally cannot see (inside a legitimately-named string field).

## 2. Relationship to existing/frozen files (must remain untouched)

- `phase3/evaluation/contracts/boundary.py` (Phase 3.2-B) — reuse, do not modify.
  `FORBIDDEN_KEYS` and `validate_agent_visible()`'s key-based behavior are correct and
  sufficient for what they claim to do; this mission does not extend their key set to
  attempt content matching — that would conflate two different detection strategies the
  existing module deliberately keeps separate (see its own "STRUCTURAL, KEY-BASED
  DETECTION ONLY" section).
- `phase3/evaluation/security/leakage.py` (Phase 3.2-F) — reuse (`validate_no_leakage`,
  `LeakageResult`, `LeakageFinding`, `STATUS_LEAKAGE_DETECTED`), do not modify. This
  mission's new check produces its own result type (§4) rather than extending
  `LeakageResult` with content-match fields that module's own documented scope excludes.
- `agent/conditions.py`, `agent_runtime/messages.py`, `agent_runtime/runner.py` (agent-side
  path) — **must not import** this mission's new module or anything that carries gold
  content (`EvaluatorReference`/`data/metadata`/`data/reports`), preserving the existing,
  tested, load-bearing property that the agent execution path never imports or depends on
  `EvaluatorReference` (per `boundary.py`'s own docstring and
  `test_validate_agent_visible_signature_has_no_evaluator_reference_param`). This mission's
  check runs strictly on the **evaluator/integration side**, where gold content is already
  legitimately in scope for scoring — never inside agent-side code.
- H.1/H.2/H.3 canonical files — untouched; unrelated to this mission entirely.

## 3. Where the new check is wired

`phase3/evaluation/integration/pipeline.py`, immediately after
`validate_agent_visible_context_shape()`/`sec_leakage.validate_against_boundary()`'s
existing calls (around line 422-423) and before the assembled context is dispatched to the
reasoning layer — this is the exact point in the existing code where `case
.agent_visible_context` (the payload the reasoning layer will actually see) and `case
.evaluator_reference` (containing that same task's `gold_answer`/`gold_evidence_ids`) are
both already legitimately in scope together. No new call site needs to be invented; this
mission adds one more validation call alongside the two that already run there.

If `agent_runtime/runner.py` has an analogous point where both are in scope (verify during
implementation — `runner.py`'s own signature note says it deliberately has no
`evaluator_reference` parameter, per §2, so this may not apply there and the check may only
be wireable at the `pipeline.py`/integration layer, not inside `runner.py` itself).
Document explicitly which call sites the check was actually wired into and why, rather
than assuming both are symmetric.

## 4. Deliverable 1 — the content-level scan function

New module (e.g. `phase3/evaluation/security/content_leakage.py`), pure function, no
filesystem/network access (matching `leakage.py`'s own stated discipline):

```
scan_for_gold_content(assembled_payload, evaluator_reference) -> ContentLeakageResult
```

- `assembled_payload` — whatever the reasoning layer will actually receive: either
  `case.agent_visible_context` (pre-`render_messages()`) or the rendered message list
  (post-`render_messages()`). **Decide and document which** — scanning the rendered
  message list is closer to "what the model actually sees" (catches a leak introduced by
  `render_messages()`'s own formatting, however unlikely); scanning the pre-render payload
  is closer to "what evidence selection handed over." Recommendation: scan the
  post-`render_messages()` output, since that is the literal string surface a "no
  experimental exceptions" contract should care about — the model reads that, not the
  intermediate dict.
- `evaluator_reference` — the same `case.evaluator_reference` mapping already in scope at
  the wiring point (§3); this function reads `gold_answer` (skip if `None` — the schema
  already permits this per pipeline.py's own 3.2-H remediation note) and
  `gold_evidence_ids` (skip empty list).
- Serializes `assembled_payload` to its actual text form (join rendered message
  `content` fields, or `json.dumps` if still a dict) and checks, per gold value: is this
  value (as a string) a substring of the serialized text?
- Returns a `ContentLeakageResult` (mirroring `LeakageResult`'s shape/discipline from
  `leakage.py`): `status` (`NO_CONTENT_LEAKAGE` / `CONTENT_LEAKAGE_DETECTED`),
  `findings` (list of which gold value matched, and where — e.g. character offset or
  containing message index).

### 4.1 Explicit STOP condition — minimum-match-length guard, decided now, not left ambiguous

A naive exact-substring check will false-positive constantly on short/generic gold answers
(e.g. `gold_answer = "yes"` will match almost any context containing the word "yes"
anywhere, unrelated to leakage). `leakage.py`'s own design philosophy (§ "deliberate,
conservative design choice to control false positives") applies here too. **Decision,
made explicitly rather than left for the implementer to guess:** apply a minimum-length
threshold (recommend 8 characters, case-sensitive exact match, no normalization) below
which a gold value is **not** scanned and is instead recorded as `SKIPPED_TOO_SHORT` in
the result — never silently treated as "no leak," always visible in the output. This is a
known, documented limitation (mirrors `leakage.py`'s own "What this is NOT" precedent),
not a silent gap. If a dataset's gold answers are frequently short, this limitation should
be called out per-dataset in the implementation report, not hidden.

### 4.2 Non-goal — no semantic/paraphrase detection

This mission implements exact substring matching only (optionally case-insensitive — decide
and document; recommend case-sensitive as the conservative default, matching §4.1's
philosophy of minimizing false positives over maximizing recall). It does not attempt to
catch a paraphrased or semantically-equivalent restatement of a gold answer — that is a
different, much harder problem (would need embedding similarity or an LLM judge, at which
point the checker itself becomes an unverified, non-deterministic component of a "no
exceptions" contract, which is undesirable). Document this limitation explicitly, the same
way `leakage.py` documents its own key-based-only limitation.

## 5. Deliverable 2 — fail-closed enforcement

At the `pipeline.py` wiring point (§3): if `scan_for_gold_content(...)` returns
`CONTENT_LEAKAGE_DETECTED`, the task's execution must **not proceed** — raise immediately
(a new `ContentLeakageDetectedError` or equivalent), the same fail-closed posture the
revised plan specified ("a match raises immediately... rather than logging a warning").
This mirrors the existing two structural checks' own posture at that call site (verify
during implementation whether they currently raise or only collect `warnings` — if they
currently only warn, document that as a **pre-existing, separate observation**, out of
scope for this mission to fix, since this mission's remit is the new content-level check,
not re-auditing the enforcement strength of the two checks that already exist).

## 6. Deliverable 3 — extend the existing self-check convention, don't invent a parallel one

`test_leakage.py`'s existing pattern (`test_leakage_module_never_reads_real_dataset_paths`,
`test_security_modules_never_import_forbidden_libraries`) is the established "static layer"
convention in this codebase. Extend it, rather than building a separate `ast`-based
import-graph analyzer:

1. Add the new `content_leakage.py` module to whatever `_SECURITY_MODULES` tuple
   `test_leakage.py` parametrizes over (or an equivalent list in the new test file), so it
   automatically inherits the "never imports forbidden libraries," "never does direct
   dataset loading," "never reads real dataset paths" source-text checks.
2. Add a new, symmetric self-check: assert `agent/conditions.py`,
   `agent_runtime/messages.py`, and `agent_runtime/runner.py`'s own source never imports
   `content_leakage` (or `evaluator_reference`, if not already checked) — proving the
   agent-side path cannot depend on gold content even by accident. This is the direct
   generalization of the existing "no EvaluatorReference param" test to this mission's new
   module.

## 7. Invariants to implement and test

1. `scan_for_gold_content()` is pure — no filesystem/network access, deterministic given
   identical inputs (mirrors `leakage.py`'s own stated discipline).
2. A gold value below the minimum-length threshold (§4.1) is never silently treated as
   clean — it appears in the result as `SKIPPED_TOO_SHORT`.
3. A `gold_answer=None` or empty `gold_evidence_ids` produces no findings for that field —
   never a false "detected" on absent gold data.
4. An assembled payload containing a gold value verbatim (above the length threshold) is
   always detected, regardless of nesting depth or which field it's embedded in — since
   this is a plain substring check, this should hold trivially, but must be tested with at
   least one case where the leak is inside a legitimately-named field (e.g.
   `memory_content[0].content`), not just a top-level key, to prove this check catches
   exactly the case `leakage.py`'s own docstring says its structural check cannot.
5. The new module never imports anything on `_FORBIDDEN_IMPORTS`-equivalent list, never
   does direct dataset loading, never contains a real dataset path string in its own
   source (§6 item 1's inherited checks).
6. Agent-side modules (§2) never import this new module (§6 item 2).

## 8. Adversarial cases to test

- A gold answer that is a common English word/short phrase below the length threshold
  (e.g. `"yes"`, `"2024"`) — must be `SKIPPED_TOO_SHORT`, not flagged, and not silently
  omitted from the result either.
- A gold evidence ID that happens to be a substring of an unrelated, legitimate canonical
  `memory_id` in the assembled context (e.g. gold ID `"m1"` inside legitimate
  `"memory_id": "m123"`) — decide and document whether this is an acceptable false
  positive (conservative, fail-closed bias) or needs a word-boundary-aware match. Default
  recommendation: accept the false positive — a "no experimental exceptions" contract
  should err toward over-flagging, not under-flagging; document this explicitly as a
  known, deliberate precision/recall tradeoff.
- The gold answer appears in the assembled context **after** JSON round-tripping (i.e., an
  escaped or re-encoded form, e.g. Unicode-escaped) — decide whether to check both raw and
  serialized forms (recommend yes, reusing `leakage.py`'s own round-trip-check precedent
  from §"serialization-round-trip check" rather than assuming a single string
  representation suffices).
- A task whose `evaluator_reference` is entirely absent at the wiring point (should not
  happen given `pipeline.py`'s existing structure, but verify the function degrades safely
  — e.g. raises a clear error rather than silently skipping — if ever called without one).

## 9. Explicit non-scope for this stage

- Rebuilding, modifying, or re-scoping `boundary.py`/`leakage.py` — both are correct,
  tested, and live; this mission is purely additive alongside them.
- Semantic/paraphrase/embedding-based leakage detection (§4.2).
- Re-auditing whether the two pre-existing structural checks at the `pipeline.py` wiring
  point are themselves fail-closed (§5) — flag as a separate observation if found weak,
  do not fix as part of this mission unless trivial.
- Retroactively re-running the full historical baseline campaign (LoCoMo/LongMemEval ×
  Mem0/A-MEM) through the new check to confirm no leakage already occurred — a valuable
  follow-up action, but a separate execution step from building the checker itself; state
  in the implementation report whether this was done.
- Initiatives A, D, G — unrelated.

## 10. Deliverables checklist

- [ ] `content_leakage.py` — `scan_for_gold_content()`, `ContentLeakageResult`, minimum-
      length guard, documented case-sensitivity decision.
- [ ] Wired into `integration/pipeline.py` at the identified call site (§3), fail-closed
      (§5).
- [ ] Self-checks extending the existing `test_leakage.py` convention (§6), in a new test
      file (e.g. `test_content_leakage.py`).
- [ ] All invariants (§7) and adversarial cases (§8) tested.
- [ ] Full existing regression suite re-run with zero regressions.
- [ ] `PHASE3_3_H4_E_IMPLEMENTATION_REPORT.md`, stating explicitly: which call site(s) the
      check was wired into, the exact minimum-length threshold and case-sensitivity
      decision, and whether the historical baseline campaign was re-scanned (§9).
- [ ] No modification to `boundary.py`, `leakage.py`, or any agent-side module beyond
      adding a self-check that they do *not* import the new module.

## 11. Definition of done

Complete when: the content-level scan function exists, is wired fail-closed at the
identified integration-layer call site, has its own self-check suite proving it inherits
the established "no forbidden imports/paths" convention and that agent-side code cannot
import it, all invariants and adversarial cases pass, and the regression suite shows zero
regressions. This closes the one gap `security/leakage.py` itself explicitly disclaims,
completing Initiative E per
[MEMORY_FOUNDATION_STRENGTHENING_PLAN_REVISED.md §5](MEMORY_FOUNDATION_STRENGTHENING_PLAN_REVISED.md).
