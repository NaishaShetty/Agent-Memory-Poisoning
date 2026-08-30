# Phase 3.2-I — Final Phase 3.2 Validation Gate

**Stage type: audit only (with narrowly-scoped fix authority; none exercised).** This is the
capstone review of the entire Phase 3.2 evaluation foundation (stages A through H.5) before
Phase 3.3 (real LLM/agent integration) begins. No new features were implemented, no dataset
was activated/demoted, no real model or agent was integrated, and no fix was required or made.

## 1. Executive verdict

**PASS_WITH_DOCUMENTED_LIMITATIONS.**

No blocking defect was discovered anywhere in Phase 3.2's contracts, metrics, agent/evaluator
separation, leakage protection, determinism, reproducibility, dataset integrity, or foundation
architecture. Every claim audited in this gate was verified by direct source inspection (not
by trusting prior-stage prose), and every claim held up. The qualifier is present only because
Phase 3.2 carries a set of **known, already-honestly-documented, non-blocking limitations**
(enumerated in section 30) that are inherent to its scope (synthetic data, no real LLM, no
production agent) or to the external environment (real-library tests only runnable in the
isolated `C:\h4venv`) — none of these represent a defect, an inconsistency, or a scientific
overreach; they are exactly what a foundation-only stage should still be missing before 3.3.

## 2. Phase 3.2 scope recap

Phase 3.2 built: contract schemas + boundary enforcement (B), core memory metrics (C), agent
conditions/outcomes/paired comparison (D/E), leakage detection (F, alongside reproducibility),
dataset capability/validation vocabulary and profiles (G), the single integration pipeline
(H), memory-foundation adapter architecture + real-foundation conformance testing (H.3/H.4),
and candidate-dataset accommodation review (H.5). All of it operates on synthetic fixtures and
already-processed Phase 1/2 data — no real LLM, no production agent, no Phase 4 attack was ever
in scope.

## 3. Stage history verified against actual code

Every stage's headline claim was checked against source, not just against its own report:

| Stage | Claim | Verified against |
|---|---|---|
| B | Agent/evaluator boundary enforced structurally | `contracts/boundary.py` `FORBIDDEN_KEYS` + recursive walker |
| C | Metrics never silently collapse undefined to 0 | `metrics/types.py` `MetricResult`/`STATUS_*`, `metrics/selection.py` |
| F | Leakage detection + reproducible fingerprinting | `security/leakage.py`, `security/reproducibility.py` |
| G | Dataset profiles are evidence-grounded, sample-honest | `datasets/profiles/locomo.json` (read in full) |
| H | Single orchestration path, no reimplementation | `integration/pipeline.py` (read in full) |
| H.3 | 7-stage memory lifecycle, MEMORY_CAUSED never implemented | `foundations/lifecycle.py`, `foundations/adapter.py` |
| H.4 | Timestamp fix is real and narrowly scoped | `pipeline.py` `_semantic_view`/metadata-only field sets; `test_foundation_conformance_h4.py` |
| H.5 | KEEP_CANDIDATE_ONLY unchanged, evidence-based | `PHASE3_2_H5_CANDIDATE_ACCOMMODATION.md` (read in full) |

## 4. Baseline and final test results

- **Baseline (re-verified at the start of this gate, before any inspection):**
  `python -m pytest phase3/evaluation/tests/ -q` → **907 passed, 3 skipped**, 11.13s.
- **Run 2 (plain, mid-gate):** 907 passed, 3 skipped, 18.05s.
- **Run 3 (`-W error`):** 907 passed, 3 skipped, 16.41s — no warning was promoted to an
  error, i.e. no test relies on a suppressed warning.
- **No fix was made in this stage**, so no further regression run was needed beyond these
  three; all three are identical in pass/skip counts.
- The 3 skips are the same as documented at session start: real Mem0/Graphiti/A-MEM library
  tests that only run inside the isolated `C:\h4venv`, not the main interpreter. Confirmed
  honest (not a hidden failure) — `test_foundation_conformance_h4.py` gates these with an
  environment-availability check, not a blanket `xfail`.

## 5. Contract audit (Part 2)

Read: all 6 `contracts/*.schema.json` + `boundary.py`. `evaluator_reference.schema.json`
accepts `gold_answer: null` as a legal value (verified: the key stays in `required`, only its
value's type union permits `null`); `pipeline.py::validate_evaluator_reference_shape` schema-
validates this directly, and `_AGENT_RESULT_REQUIRED_METRIC_FAMILIES`/`compute_metric` route a
`None` `gold_answer` into `EVALUATION_UNDEFINED`-classified outcomes (`agent.outcomes.
classify_agent_success`) rather than crashing or defaulting to a false answer. `gold_answer`
itself is in `boundary.FORBIDDEN_KEYS`, so a `null` gold answer is exactly as unreachable from
agent-visible context as a real one — null-handling did not create a new leakage path. Schemas
were not loosened to make tests pass; `additionalProperties: false` remains in force on every
schema inspected.

## 6. Metric semantics audit (Part 4)

Read `metrics/selection.py` and `metrics/types.py` in full; spot-checked `metrics/retrieval.py`
and `metrics/evidence.py` via the integration pipeline's dispatch table (`compute_metric`).
Every metric returns a `MetricResult` with an explicit `status`; no metric function coerces an
undefined precondition into a numeric 0 silently (`selection_count_aggregate` on an empty
run-list returns `value=None`/`STATUS_UNDEFINED_EMPTY_SEQUENCE`, not `0.0`). No duplicated
metric logic was found: `pipeline.py`'s `compute_metric` calls exactly one canonical function
per family and its own docstring states "No metric ... is reimplemented anywhere in this
module" — confirmed true by inspection of every branch in `compute_metric`.

## 7. Strict TSR final audit (Part 3) — direct source verification

`phase3/evaluation/metrics/selection.py::strict_tsr()`:

```
intersection = set(selected_or_used_ids) & set(gold_evidence_ids)
hit = len(intersection) > 0
value = 1.0 if hit else 0.0
```

This is exactly `selected ∩ gold_evidence ≠ ∅`, unchanged from the frozen formula. No later
stage redefines it: a codebase-wide search for `strict_tsr`/`STRICT_TSR` (29 files) found
every non-test, non-doc usage to be either (a) a call into this exact function, or (b) the
integration layer's `_compute_strict_tsr()` case-level guard in `pipeline.py`, which does
**not** alter `strict_tsr()`'s own OK/0.0 semantics for an empty-gold input — it only
substitutes a different `MetricResult.status` (`STATUS_UNDEFINED_EMPTY_GOLD`, imported
verbatim from `metrics.types`, the same status `recall_at_k`/`evidence_recall` already use for
the identical precondition) at the integration layer, for a specific case whose gold is empty,
while the underlying function is called unmodified for every other case. No answer-correctness
signal, no LLM judgment, and no case-level filtering of "hard" tasks was found anywhere near
Strict TSR. **Strict TSR remains canonical and unchanged.**

## 8. Agent/evaluator separation (Part 5)

`contracts/boundary.py::validate_agent_visible()` takes only the agent-visible payload — no
`EvaluatorReference` parameter exists in its signature (this is itself asserted by an automated
test named in the module's own docstring). `security/leakage.py` layers a wider, recursive,
dataclass/tuple-aware check on top (never bypassing or weakening `boundary.py`), including a
**MetricResult-shape detector** that flags a `{metric_name, value, status, detail}`-shaped
value even if none of its individual keys matches a forbidden name — this catches a whole class
of leakage a pure key-name list would miss. The module's own docstring is explicit and accurate
about scope: "STRUCTURAL, KEY-BASED DETECTION ONLY — NOT A GENERAL SOLUTION" — a value like
`{"note": "the user bought gold-colored shoes"}` is correctly NOT flagged (word inside a string
value, not a key), and this limitation is stated, not hidden. No semantic/steganographic
leakage claim is made anywhere in the module or its README — confirmed accurate.

## 9. Leakage audit (Part 5, continued)

`validate_against_boundary()` runs `boundary.validate_agent_visible()` first, then the wider
recursive walk — never the reverse order, never skipping the authoritative check.
`check_serialization_round_trip()` confirms a clean payload stays clean and a leaking payload
stays caught across a JSON `dumps`/`loads` boundary. `PROTECTED_FIELD_NAMES` is documented as a
strict superset addition over `boundary.FORBIDDEN_KEYS` (never a removal). No false-positive
risk was found for ordinary natural-language agent-visible text in the cases inspected.

## 10. Determinism audit (Part 6)

- `security/reproducibility.py::_normalize()`: dict keys sorted (`sort_keys=True` in
  `canonical_serialize`), lists/tuples preserved in caller order, sets/frozensets sorted only
  because they have no order to begin with (documented explicitly as "recovering a canonical
  form, not discarding meaningful order — there was none to discard").
- `fingerprint()` uses `hashlib.sha256`, never `hash()`. A codebase-wide search for `hash(`
  found matches only in `test_reproducibility.py` (testing this exact property) and in
  `reproducibility.py`'s own docstring explaining why `hash()` must never be used. No other
  file in `phase3/evaluation` calls Python's built-in `hash()`.
- `foundations/lifecycle.py::classify_memory_retrieval`/`classify_memory_selection` preserve
  caller-supplied list order verbatim and record `rank` explicitly, never re-sorting a ranked
  list.
- Order-sensitivity for Recall@K/MRR vs. order-independence for evidence precision/recall and
  Strict TSR follows directly from their set-based (`set() & set()`) vs. positional
  implementations, confirmed by direct read of `selection.py`.

## 11. H.4 timestamp fix final audit (Part 7) — re-verified with an actual test

`pipeline.py`'s `_TRACE_METADATA_ONLY_FIELDS = {"created_at"}` and
`_EVALUATION_RESULT_METADATA_ONLY_FIELDS = {"evaluation_timestamp"}`, combined with
`_semantic_view()`, are used to build `trace_semantic`/`evaluation_result_semantic` dicts that
are what actually gets fingerprinted (`fingerprints["trace"]`, `fingerprints["evaluation_
result"]`, `fingerprints["overall"]`) — the **returned** `trace`/`evaluation_result` dicts
handed back to the caller still carry the real wall-clock `created_at`/`evaluation_timestamp`
values, confirmed by reading `_build_trace`/`_build_evaluation_result` directly: nothing was
stripped from what a consumer sees, only from what gets fingerprinted.

Ran the regression test directly in this stage:
```
python -m pytest phase3/evaluation/tests/test_foundation_conformance_h4.py -q -k "timestamp or fingerprint"
→ 3 passed, 41 deselected
```
Confirmed both halves of the fix are exercised, not just the positive case:
- `test_two_runs_differing_only_in_wall_clock_time_produce_identical_case_fingerprints`
  (monkeypatches `datetime.now` to 2020 vs. 2030): asserts `evaluation_timestamp` values differ
  but `fingerprints["trace"]`/`["evaluation_result"]`/`["overall"]` are identical.
- `test_a_genuinely_different_semantic_result_still_produces_a_different_fingerprint`: guards
  against an over-broad fix that would make fingerprints ignore too much — a genuinely
  different semantic evaluation still produces a different fingerprint.

Both hold. The TRACE-METADATA-vs-SEMANTIC-FINGERPRINT-CONTENT distinction is explicit in code
comments and preserved in behavior.

## 12. Reproducibility audit (Part 8)

`canonical_serialize`/`fingerprint`/`build_manifest`/`validate_manifest_completeness`/
`verify_reproducibility`/`reconstruct_and_verify` read in full (`security/reproducibility.py`).
`REQUIRED_MANIFEST_FIELDS` includes `seed`, which defaults to the honest sentinel
`"NOT_APPLICABLE"` rather than being silently omitted or defaulted to `None`.
`MANIFEST_METADATA_ONLY_FIELDS = {"timestamp"}` is the exact pattern `pipeline.py`'s H.4 fix
mirrors. `verify_reproducibility`'s five-way status precedence (`INCOMPLETE_MANIFEST` →
`ARTIFACT_MISMATCH` → `CONFIGURATION_MISMATCH` → `INPUT_MISMATCH` → `REPRODUCIBLE_MATCH`) is
checked in a fixed, documented order, one status ever returned. The module's own limitation
statement — that none of this guarantees reproducibility of a future *stochastic* LLM's output
— is accurate and was not overstated anywhere it was referenced.

## 13. Dataset integrity audit (Part 9)

`git status --short` (see section 33) shows the only tracked-file change anywhere in the repo
is the single documented `raw_fingerprint.json` correction described in the task briefing —
already verified, already tested, explicitly out of scope to revisit further. No file under
`data/raw/`, `data/processed/`, `data/metadata/`, `phase3_reference/`, or any candidate's
`raw/` directory was touched by this gate (this gate made **zero** file edits of any kind).

## 14. Active dataset profile audit (Part 10)

Read `datasets/profiles/locomo.json` in full as the representative sample (all four active
profiles share the same schema and were spot-checked structurally against
`datasets/profile.schema.json`). Findings:
- Status vocabulary (`AVAILABLE`/`PARTIAL`/`UNAVAILABLE`/`NOT_PROVIDED_BY_SOURCE`) is used
  consistently and never collapsed — e.g. `gold_answer_field` and `evidence_availability` are
  both explicitly `PARTIAL` (65/300 null answers, all `question_type: "5"`; 3/300 empty
  `evidence_memory_ids`), not silently rounded up to `AVAILABLE` nor down to `UNAVAILABLE`.
- Every claim in the profile carries a `grounding` pointer to a specific file/field, and the
  `inspection_method` block is explicit about which claims are sample-based (500/5882,
  300/1986) vs. full-file (the four relationship-field greps, 5882/5882 lines) — this is
  honest, falsifiable methodology, not narrative.
- `metric_support` correctly ties `STRICT_TSR`/evidence metrics to the same PARTIAL gold-ID
  caveat rather than claiming a cleaner story than the data supports.

## 15. Candidate dataset final audit (Part 11) and H.5 findings (Part 15)

Read `PHASE3_2_H5_CANDIDATE_ACCOMMODATION.md` in full. Confirms:
- **MemoryAgentBench: `KEEP_CANDIDATE_ONLY` (unchanged).** Fundamental blocker (no chunk/turn
  granularity gold evidence — confirmed by full 3671/3671-record scan, not sample) stands. A
  genuinely new, narrower accommodation (`document_level_evidence_basis()`) was added
  *additively*, without touching the existing `evidence_basis()` method or its protected test
  assertions — two metric families move from `NOT_ATTEMPTABLE` to `PARTIALLY_ATTEMPTABLE` under
  an explicit coarse-granularity caveat; this does not change the promotion verdict.
- **MemBench: `KEEP_CANDIDATE_ONLY` (unchanged).** H.5 found and fixed a genuine **adapter**
  bug (not one of H.2's named blockers): 140/275 sample records use a flat-int evidence shape
  that crashed the H.3 encoder (`TypeError`), reproduced before the fix, fixed via
  `normalize_membench_evidence_positions()` which normalizes only when `session_count == 1`
  (refuses otherwise, never guesses). Neither of H.2's actual blockers (275/26,637 sample size;
  unconfirmed license — re-verified via a fresh GitHub API call in H.5, independently
  corroborating the manual finding) was removed.
- A **mid-stage self-correction is documented in H.5's own text**: an initial attempt to widen
  `EVIDENCE_BASIS_KINDS` to 6 broke three protected `test_framework_extensions_h3.py`
  assertions; H.5 reverted that change and used a separate, non-enum-validated type instead.
  This is exactly the kind of forthright reporting this gate was told to look for, and it
  reads as genuine (a fix that "worked around" its own test failure by reverting, not by
  weakening the test).
- **No contradictory evidence was found in this gate that would reopen H.5.** Both
  `KEEP_CANDIDATE_ONLY` verdicts stand, and this gate did not touch either candidate's `raw/`
  directory or promote/demote anything.

## 16. Memory foundation architecture audit (Part 12)

Read `foundations/adapter.py` and `foundations/lifecycle.py` in full. Confirmed:
- `MemoryFoundationAdapter` is an abstract interface only (no concrete production
  implementation in Phase 3.2) with every method returning a `FoundationField` carrying an
  explicit `availability` status — `FOUNDATION_NOT_SUPPORTED_BY_ARCHITECTURE` is a real, one-
  new-value addition, documented as distinct from a genuine empty/no-op `AVAILABLE` result.
- The 7-stage lifecycle vocabulary (`MEMORY_AVAILABLE → MEMORY_RETRIEVED → MEMORY_SELECTED →
  MEMORY_EXPOSED → MEMORY_USED → MEMORY_CONTRIBUTED → MEMORY_CAUSED`) is exactly as specified.
  `MEMORY_CAUSED` is a named constant kept **deliberately outside** `LIFECYCLE_STAGES` (the
  tuple of achievable stages) — no function in `lifecycle.py` can return it, and the module
  states this is enforced by a dedicated grep-based test in `test_foundation_architecture_h3.py`.
  `build_lifecycle_trace()` enforces stage ordering structurally (cannot reach `MEMORY_SELECTED`
  without first reaching `MEMORY_RETRIEVED`, etc.), not merely by trusting caller input.
- `MEMORY_USED`/`MEMORY_CONTRIBUTED` are literal re-exports (`classify_memory_usage =
  classify_retrieval_utilization`; `classify_memory_foundation_contribution =
  classify_memory_contribution`) — no duplicated or foundation-specific reimplementation of
  either, confirmed by reading the assignment lines directly.
- Foundation-native structure preservation (Graphiti graph-native, A-MEM evolution-native) is
  asserted in `normalize_trace()`'s docstring as a hard requirement ("without discarding
  foundation-native structure ... never flattened into a bare list"); this gate did not find a
  concrete adapter that violates it (the concrete Mem0/Graphiti/A-MEM adapters live under
  `foundations_real/`, exercised by H.4's tests, separately from this abstract interface).

## 17. Real foundation conformance audit (Part 13)

`foundations_real/` contains real adapters for Mem0, Graphiti, A-MEM, and Letta plus
`conformance_record.py`/`environment.py`. H.4's tests (`test_foundation_conformance_h4.py`,
44 tests, 3 skipped when the real libraries are absent from the main interpreter) are
environment-adaptive, not silently mocked when the real library is missing — the skip
mechanism reports honestly rather than substituting a mock result under a real-conformance
label. `PARTIAL_CONFORMANCE` language (LLM-mediated behavior untested) was not found upgraded
to `FULL_CONFORMANCE` anywhere in the code or docs inspected.

## 18. Integration pipeline audit (Part 16)

Read `integration/pipeline.py` in full (515 lines). `evaluate_case()`'s call graph matches its
own documented 8-step sequence exactly: condition validation → schema validation → leakage
validation → agent execution → per-family metric computation (`compute_metric`, one canonical
function call per family, `KeyError` on an unhandled family rather than silently skipping) →
trace/result assembly → schema validation of both → fingerprinting (semantic-view, timestamp-
excluded). No metric, condition, or leakage function is reimplemented in this module — every
branch of `compute_metric` is a direct call into `metrics.*`/`agent.*` modules, confirmed by
reading every branch.

## 19. Error/undefined semantics audit (Part 17)

Confirmed distinct, non-conflated statuses exist and are actually returned along the paths
inspected:
- `STATUS_UNDEFINED_EMPTY_GOLD` vs. `STATUS_OK` with `value=0.0` (Strict TSR's own empty-gold
  case) vs. the integration-layer's case-level override — three genuinely different things,
  never collapsed into one.
- `STATUS_NOT_ATTEMPTED` (dataset-level gate) vs. a case-level `not_attempted(..., scope=
  "CASE")` (e.g. `LINEAGE_DIAGNOSTICS` with no selected ids) — distinguished by an explicit
  `scope` argument.
- `RETRIEVAL_UTILIZATION`'s `STATUS_UNDEFINED_USAGE_NOT_OBSERVABLE` (used_memory_ids is `None`)
  vs. `NO_SELECTED_EVIDENCE` (selected is empty but usage IS observable) — explicitly not
  conflated, per `diagnostics.py`'s own docstring: "we don't know" vs. "we know it wasn't used"
  are different findings.
- `AGENT_EXECUTION_FAILURE` vs. `STAGE_UNDEFINED` vs. `SUCCESS` vs. the four evidence-handling
  failure stages in `classify_observed_failure_stage` — six-way precedence, one status ever
  returned, confirmed by reading the full function body.

## 20. Provisional decision inventory (Part 18)

Enumerated PROVISIONAL items found during this audit (none frozen prematurely, none silently
promoted to canonical):
- `security/leakage.py`'s `_ADDITIONAL_PROTECTED_FIELD_NAMES` — explicitly labeled PROVISIONAL
  in its own README (no contract document enumerates this exact list).
- `EVIDENCE_COVERAGE` metric — labeled PROVISIONAL per `metrics/README.md` (confirmed
  referenced as such in `locomo.json`'s own `metric_support` entry).
- `agent.conditions`'s three provisional conditions (`SELECTED_MEMORY_AVAILABLE`,
  `DERIVED_MEMORY_AVAILABLE`, `CONFLICTING_MEMORY_AVAILABLE`) — schema validation is skipped
  for these by design, both in `agent.conditions` and mirrored in `pipeline.py`'s
  `validate_agent_visible_context_shape`.
- H.5's `DocumentEvidenceBasisDeclaration`/`document_level_evidence_basis()` — explicitly kept
  outside the frozen 5-way `EVIDENCE_BASIS_KINDS` vocabulary, a deliberate non-canonical
  addition.
- `MemBench` reproducibility classification `REPRODUCIBLE_WITH_SOURCE_REACQUISITION` (not
  `FULLY_REPRODUCIBLE`, since the full corpus is not vendored in-repo) — correctly left as-is,
  not force-upgraded.

None of these needed to become canonical or be deferred differently as a result of this gate;
each remains exactly as prior stages classified it.

## 21. Scientific validity assessment (Part 19)

Answering each question directly, based on source inspection (not documentation alone):

| Question | Answer | Basis |
|---|---|---|
| Distinguish retrieval failure from answer failure? | YES | `classify_observed_failure_stage` six-way precedence |
| Memory availability from actual use? | YES | `lifecycle.py` `MEMORY_AVAILABLE` vs. `MEMORY_USED` are structurally distinct classifications with different inputs |
| Use from contribution? | YES | `MEMORY_USED` (`classify_retrieval_utilization`) vs. `MEMORY_CONTRIBUTED` (`classify_memory_contribution`, a paired NO_MEMORY/WITH_MEMORY comparison) are different functions over different inputs |
| Avoid claiming causality? | YES | Every diagnostic module's docstring states "OBSERVED", not "CAUSED"; `MEMORY_CAUSED` is a named-but-unimplemented placeholder, test-enforced |
| Identify evidence grounding where it exists? | YES | Strict TSR + evidence precision/recall/coverage, gated per-dataset by `metric_support` |
| Honestly represent datasets lacking evidence? | YES | `NOT_PROVIDED_BY_SOURCE`/`NOT_ATTEMPTABLE` used consistently, confirmed in `locomo.json` and H.5's MemoryAgentBench table |
| Prevent evaluator leakage? | YES (structural only) | `boundary.py` + `leakage.py`; semantic/steganographic leakage explicitly out of scope, honestly stated |
| Reproduce deterministic infrastructure behavior? | YES | SHA-256 fingerprinting, no `hash()`, list order preserved, H.4 timestamp fix verified |
| Preserve native foundation semantics? | YES (by design; not independently re-verified beyond H.4's own tests in this gate) | `adapter.py`/`lifecycle.py` docstrings + H.4 tests |
| Accommodate heterogeneous datasets? | YES | H.5's additive, non-fabricating accommodations for two structurally different candidate datasets |
| Expose the failure stage responsible for low TSR? | YES | Section 22 below |
| Accept a real LLM without requiring metric redesign? | YES (assessed, not tested) | `AgentExecutionResult`/`compute_metric` take plain IDs/strings; no metric function assumes a specific model |

No BLOCKING "NO" was found for any of these.

## 22. The low-TSR question revisited (Part 20) — critical PASS criterion

Phase 3 was restarted because Strict TSR alone gave no way to tell *why* it was low. Phase 3.2
does **not** claim to have solved low TSR — no accuracy number was improved, no dataset was
made to score higher. What was verified in this gate is that the **diagnostic separation** now
exists structurally, ahead of any real experiment:

- `RETRIEVAL_FAILURE` (gold id never appears in `retrieved_memory_ids`),
- `SELECTION_FAILURE` (gold id retrieved but never in `selected_memory_ids`),
- `EVIDENCE_UNAVAILABLE` (NO_MEMORY condition — no memory layer was ever engaged),
- `AGENT_FAILURE_WITH_EVIDENCE` (gold evidence was fully retrieved+selected, or handed directly
  under GOLD_EVIDENCE condition, yet the answer was still wrong — implicates reasoning, not
  memory),
- `AGENT_EXECUTION_FAILURE` (the run itself did not complete),
- `SUCCESS`, and `UNDEFINED_EVALUATION` (no basis to classify at all)

are seven mutually exclusive, precedence-ordered, causally-non-committal classifications, all
reachable from a single function (`classify_observed_failure_stage`) whose full body was read
in this gate. This is precisely the diagnostic separation the original Phase 3 restart lacked.
**Verdict: Phase 3.2 makes low TSR scientifically diagnosable, once real agent/LLM experiments
begin in Phase 3.3 — it does not, and does not claim to, solve low TSR itself.**

## 23. Phase 3.3 readiness (Part 21)

| Readiness criterion | Status |
|---|---|
| Agent input well-defined | YES — `AgentVisibleContext` schema + `boundary.py` |
| Evaluator input well-defined | YES — `EvaluatorReference` schema (incl. `gold_answer: null`) |
| Gold data hidden from agent | YES — structural leakage protection, verified |
| Agent output contract defined | YES — `AgentExecutionResult`/`agent_execution_result.schema.json` |
| Answer correctness defined | YES — `agent.outcomes.evaluate_answer_correctness`/`classify_agent_success` |
| Failures classifiable | YES — `classify_observed_failure_stage`, `RETRIEVAL_UTILIZATION` |
| Memory foundation adapter boundary exists | YES — `MemoryFoundationAdapter` abstract interface + 4 real adapters |
| Deterministic evaluation infrastructure exists | YES — verified in sections 10-12 |
| Stochastic model behavior isolatable from deterministic metrics | YES (by construction — metrics take plain IDs/strings, never a model handle) — genuinely untested against a REAL stochastic model, since none exists yet in this repo |
| Model configuration fingerprintable without exposing secrets | YES — `foundations/fingerprinting.py::reject_secrets`, reused verbatim by H.4's tests |

**READY for Phase 3.3 to begin**, with the explicit caveat that "stochastic isolation" and
"real foundation LLM-mediated conformance" are architecturally prepared but not yet exercised
against an actual model — that exercise is Phase 3.3's job, not a Phase 3.2 gap.

## 24. Dependency/environment audit (Part 23)

External (non-stdlib) imports found across `phase3/evaluation`: `jsonschema` (contract
validation) and `pytest` (tests only). No LLM SDK, no HTTP client, no database driver is
imported anywhere in non-test, non-`foundations_real` code. `foundations_real/*_real_adapter.py`
files import their respective real libraries (`mem0`, `graphiti_core`, etc.) — these are
optional-foundation-dependencies, gated by `try/except ImportError` and the H.4 skip mechanism,
never a hard import failure in the main environment. No unnecessary dependency was added by
this gate (none was added at all).

## 25. Secrets/security audit (Part 22)

Searched for API-key/secret/password/token/Bearer/AKIA-shaped literals across
`phase3/evaluation`; every match was either the word "secret" inside a function/variable name
(`reject_secrets`, doc comments describing what must never appear) or a documentation
description of the protection mechanism itself — no actual credential-shaped value was found
anywhere in the codebase. `foundations/fingerprinting.py::reject_secrets` (reused verbatim by
`MemoryFoundationAdapter.initialize()`'s documented contract and by H.4's tests) is the concrete
mechanism preventing a configuration fingerprint from embedding a secret field.

## 26. Documentation consistency audit (Part 24)

Cross-checked prose claims against code in every module read in this gate (sections 5-18
above); no FULL/AVAILABLE/DETERMINISTIC/CONFORMANT claim was found overstated relative to what
the code actually does. Two cases worth flagging as *exemplary*, not concerning: the leakage
module's explicit "NOT semantic leakage protection" limitation, and the reproducibility
module's explicit "does not guarantee future stochastic reproducibility" limitation — both
appear in the code's own docstrings, not only in a separate README, meaning a future maintainer
reading the implementation directly gets the same honest caveat a README reader would.

## 27. Test quality audit (Part 25)

- Total test functions across `phase3/evaluation/tests/*.py`: ~660 (many further parametrized
  by pytest, yielding the 907 collected cases).
- Assertion density spot-checked: `test_core_memory_metrics.py` (126 asserts), `test_leakage.py`
  (48 asserts), `test_evaluation_integration.py` (123 asserts) — multiple real assertions per
  test on average, not one trivial assertion per test.
- Searched for tautological patterns (`assert True`, `assert 1`, bare `pass` bodies) across all
  test files — **zero matches**. No smoke-only ("doesn't crash") test pattern was found in the
  files inspected; `test_candidate_accommodation_h5.py`'s own description explicitly commits to
  "exact assertions (never 'doesn't crash')" and this was spot-verified true for the timestamp-
  fingerprint regression test (section 11), which asserts both equality AND inequality, not
  just "ran without an exception."
- No test was weakened, deleted, or added defensively in this gate (no fix was made, so no new
  test was needed either) — H.4's existing regression test for the timestamp fix was judged
  sufficiently meaningful (both a positive and a negative case) without needing a duplicate.

## 28. Final dataset/foundation matrix (Part 28)

| Dataset | Status | Task | Evidence | Identity | Provenance | Lineage | Equivalence | Agentic-memory | Foundation-compat | Metric coverage | Primary limitation | 3.3 relevance |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| LoCoMo | ACTIVE | AVAILABLE | PARTIAL | AVAILABLE | AVAILABLE | NOT_PROVIDED_BY_SOURCE | NOT_PROVIDED_BY_SOURCE | N/A | Full pipeline (needs future retrieval layer) | Broad (Strict TSR, Recall@K, MRR, evidence, answer, agent-success) | Small null-evidence/null-answer minority (adversarial Q-type) | Primary QA benchmark |
| LongMemEval | ACTIVE | AVAILABLE | (profile-specific, not re-read line-by-line this gate; unchanged from H prior stages) | AVAILABLE | AVAILABLE | per-profile | per-profile | N/A | Full pipeline | Broad | per profile | Primary |
| MSC | ACTIVE | AVAILABLE | per-profile | AVAILABLE | AVAILABLE | per-profile | per-profile | N/A | Full pipeline | Broad | per profile | Primary |
| Conversation Chronicles | ACTIVE | AVAILABLE | per-profile | AVAILABLE | AVAILABLE | per-profile | per-profile | N/A | Full pipeline | Broad | per profile | Primary |
| MemoryAgentBench | CANDIDATE_ONLY (unchanged, H.5-confirmed) | AVAILABLE (multi-ref) | NOT_ATTEMPTABLE (chunk/turn) / PARTIALLY_ATTEMPTABLE (document-level, new) | ADAPTER_DERIVED / COMPOSITE_SOURCE (new, never NATIVE) | NOT_PROVIDED_BY_SOURCE | NOT_ATTEMPTABLE | NOT_ATTEMPTABLE | Structural chain data only | Document-granularity conformance now well-defined (unused) | ~2/7 families PARTIALLY_ATTEMPTABLE, rest NOT_ATTEMPTABLE | No chunk/turn evidence exists in source, fundamental | Not promoted; document-level experiment available if wanted |
| MemBench | CANDIDATE_ONLY (unchanged, H.5-confirmed) | AVAILABLE | AVAILABLE (post-fix; was silently/crash-prone pre-fix for 51% of sample) | ADAPTER_DERIVED (session/turn) | NOT_PROVIDED_BY_SOURCE | NOT_PROVIDED_BY_SOURCE | NOT_PROVIDED_BY_SOURCE | Session/turn structural | Not yet run | Most families ATTEMPTABLE | 275/26,637 sample; license CLAIMED_NOT_CONFIRMED | Not promoted; full-corpus normalization is low-risk future work |
| MemoryArena | CANDIDATE_ONLY (unchanged; out of H.5 scope, not re-audited this gate) | per H.2 | per H.2 | per H.2 | per H.2 | per H.2 | per H.2 | Structural chain data (agentic_memory.py) | per H.2 | per H.2 | Unchanged from H.2 (not re-audited this gate, per task brief's explicit scope exclusion) | Not promoted |

Foundations: Mem0/Graphiti tested against real libraries (H.4, PARTIAL_CONFORMANCE — LLM-
mediated behavior untested); A-MEM tested to the extent the environment permits; Letta
deferred (adapter exists, no real-library conformance test run yet); LangMem screen-only;
LlamaIndex/Memary/MemoryBank-SiliconFriend/LongMem rejected (unchanged, not revisited).

## 29. Final Phase 3.2 readiness criteria (Part 29)

All 22 criteria from the task brief hold, based on the evidence in sections 4-27 above: contracts
consistent; metrics stable; Strict TSR canonical; evaluator/agent separation works; leakage
protection works (structurally, honestly scoped); deterministic infrastructure works;
reproducibility works; active profiles honest; candidates honestly classified; foundation
abstraction functional; real structural conformance honestly reported (PARTIAL_CONFORMANCE not
upgraded); integration pipeline works; undefined states preserved; H.4 fix correct; H.5 findings
incorporated (no dataset corrupted or fabricated); no critical secrets found; documentation
matches implementation; framework is ready for stochastic LLM integration (architecturally, not
yet exercised); limitations explicitly identified (this document, section 30); all critical
tests pass deterministically (907 passed / 3 skipped, three consecutive runs, `-W error` clean).

## 30. Discovered issues, fixes made, and unresolved limitations

**Fixes made in this gate: none.** No genuinely blocking defect was found. The one
already-existing uncommitted change (`membench/manifests/raw_fingerprint.json` correction) was
inspected, confirmed to be exactly the documented, pre-verified, pre-tested fix described in
the task briefing, and left untouched as instructed.

**Known, non-blocking, already-honest limitations carried forward (not hidden, not new):**
1. Semantic/steganographic leakage is out of scope for the leakage detector — structural,
   key-name-based detection only. Documented in the module itself.
2. Real foundation conformance is `PARTIAL_CONFORMANCE` — LLM-mediated behavior is untested
   until Phase 3.3 supplies a real model.
3. 3 tests are environment-gated skips (real Mem0/Graphiti/A-MEM libraries only installed in
   the isolated `C:\h4venv`, not the main interpreter) — an environmental, not a code,
   limitation.
4. MemBench's full 26,637-record corpus is not normalized in-repo (275-record deterministic
   sample only); classified `REPRODUCIBLE_WITH_SOURCE_REACQUISITION`, not
   `FULLY_REPRODUCIBLE`. Ordinary future data-preparation work, not a framework defect.
5. MemBench's MIT-license claim remains `CLAIMED_NOT_CONFIRMED` (re-verified via GitHub API in
   H.5; no LICENSE file exists upstream) — cannot be resolved without upstream author
   confirmation.
6. Letta's real-library conformance test has not yet been run (adapter exists; H.4 focused on
   Mem0/Graphiti/A-MEM).
7. Stochastic-model isolation and secret-safe model-configuration fingerprinting are
   architecturally prepared (`reject_secrets`, plain-ID/string metric inputs) but have never
   been exercised against an actual non-deterministic model, since none exists in this repo
   yet — this is expected and appropriate for a foundation stage, not a gap in Phase 3.2 itself.

None of these are classified BLOCKING; all are DATASET-INHERENT, FOUNDATION-INHERENT,
ENVIRONMENTAL, or explicitly 3.3-DEPENDENT per the task brief's own taxonomy (Part 27).

## 31. Phase 3.3 boundary (Part 30)

This gate did **not**: integrate Qwen/OpenAI/Gemini/Anthropic or any other real LLM; run a
production agent; run any Phase 4 poisoning/attack; modify any benchmark dataset; activate,
promote, or demote any dataset or memory foundation; or redesign any metric based on
hypothetical future LLM behavior. Phase 3.2-I ends here, immediately before real model/agent
integration.

## 32. Final decision

**PASS_WITH_DOCUMENTED_LIMITATIONS.** Phase 3.2 is scientifically coherent, internally
consistent, deterministic, reproducible, leakage-safe (structurally), data-integrity-preserving,
metric-semantics-preserving, compatible with the prepared candidate datasets, compatible with
the selected memory-foundation architecture, and ready for Phase 3.3 real LLM/agent
integration to begin. The documented limitations in section 30 are honest, pre-existing,
non-blocking, and explicitly the kind of thing Phase 3.3 exists to resolve — not a reason to
withhold PASS, and not something this gate should paper over by omitting them.

## 33. Pre-commit verification (performed in this gate)

```
git status --short
 M phase3/datasets/candidates/membench/manifests/raw_fingerprint.json
?? phase3/README.md
?? phase3/contracts/
?? phase3/schemas/
?? phase3/specification/

git diff --stat
 phase3/datasets/candidates/membench/manifests/raw_fingerprint.json | 7 +++++--
 1 file changed, 5 insertions(+), 2 deletions(-)

git diff --cached --stat
(empty — nothing staged)
```

Confirmed: exactly one modified tracked file (the pre-existing, pre-verified H.1 fingerprint
correction described in the task briefing) and exactly the four pre-existing Phase 3.1
untracked paths (`phase3/README.md`, `phase3/contracts/`, `phase3/schemas/`,
`phase3/specification/`) — nothing else. No secrets, no generated garbage, no duplicate
directories, no stale background-agent artifacts, no Phase 1/2 changes, no `phase3_reference/`
changes. This gate itself added exactly one new file:
`phase3/evaluation/PHASE3_2_FINAL_VALIDATION.md` (this document), which will appear as a new
untracked file until committed.

## 34. Exact manual commit commands (for the user to run; not executed by this gate)

```
git add phase3/datasets/candidates/membench/manifests/raw_fingerprint.json
git add phase3/evaluation/PHASE3_2_FINAL_VALIDATION.md
git commit -m "Add Phase 3.2-I final validation gate report; confirm H.1 fingerprint correction"
```

Do **not** run `git add phase3/` or `git add -A` — that would also stage the four pre-existing
Phase 3.1 untracked paths (`phase3/README.md`, `phase3/contracts/`, `phase3/schemas/`,
`phase3/specification/`), which are outside this gate's and this session's scope and must stay
excluded from this commit.
