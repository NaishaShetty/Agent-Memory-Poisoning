# Phase 3.2-F — Leakage, Determinism, Reproducibility

Status: **DIAGNOSTIC/DEFENSE-IN-DEPTH IMPLEMENTATION, ALMOST ENTIRELY PROVISIONAL OR
DIAGNOSTIC ONLY.** No contract document (`EVALUATION_CONTRACT.md`,
`TRACEABILITY_CONTRACT.md`, `LEAKAGE_AND_VISIBILITY_CONTRACT.md`,
`REPRODUCIBILITY_CONTRACT.md`) specifies an exact leakage-detector implementation,
fingerprint format, manifest schema, or determinism-harness shape — those documents fix
*what must be true* (the two information planes, what must be recorded, what must be
deterministic) and explicitly leave the *tooling* undecided (see each contract's "What
this contract does not decide" section). This stage builds that tooling and labels almost
every construct PROVISIONAL or DIAGNOSTIC ONLY accordingly — see the classification table
at the end of this document.

This stage implements ONLY: leakage detection/validation, agent-visible/evaluator-only
boundary auditing, determinism checks, seed/configuration capture, evaluation-input
fingerprinting, artifact integrity checks, a reproducibility manifest, run
reconstruction/verification, and tests for all of the above — all against SYNTHETIC data
only. It does **not** implement real dataset integration, Qwen, any LLM integration,
real-agent integration, retrieval/reranking/candidate-generation, memory creation/store,
new memory policies, semantic equivalence, new provenance semantics, or Phase 4 work.

Code: `phase3/evaluation/security/leakage.py`, `determinism.py`, `reproducibility.py`.
Tests: `phase3/evaluation/tests/test_leakage.py`, `test_determinism.py`,
`test_reproducibility.py`.

## 1. The leakage model

### 1.1 Protected field names

`leakage.PROTECTED_FIELD_NAMES` = `phase3/evaluation/contracts/boundary.py`'s
`FORBIDDEN_KEYS` (the 3.2-B authoritative set — gold answers/ids, evaluation
labels/scores, internal ranks, attack labels, hidden benchmark metadata, etc.) **union**
an explicit, additional set named in the 3.2-F task brief and not already covered
verbatim by `boundary.py`: `gold_memory_ids`, `evidence_memory_ids`, `expected_answer`,
`evaluation_result`, `answer_correctness`/`correctness`/`correctness_label`/`correct`,
`task_success`/`success`/`success_label`, `strict_tsr`, `provenance_label`,
`lineage_label`, `equivalence_label`, `failure_stage`, `observed_failure_stage`,
`condition_metadata`/`hidden_condition_metadata`, `selected_gold`/`gold_selected`,
`evaluator_reference_fingerprint`, `result_fingerprint`. This module never removes or
weakens any `boundary.py` entry — it only adds to it
(`test_protected_field_names_is_superset_of_boundary_forbidden_keys`).

### 1.2 Structural-only detection scope, and the false-positive-control rationale

`leakage.py` matches dict **keys** and dataclass **field names**, never string
**content**. This is the single design decision that makes the module usable at all: a
payload like `{"note": "The user bought gold-colored shoes"}` must NOT be flagged, because
nothing about it is structurally suspicious — `"gold"` only ever appears inside a string
*value*. If this module instead scanned string content for substrings like `"gold"`,
`"correct"`, or `"success"`, it would flag enormous amounts of ordinary, perfectly
legitimate agent-visible text and become useless (or would need an ever-growing exclusion
list, which is worse). Matching by key presence is the only detection strategy this stage
adopts, and it is a deliberate, conservative choice, not an oversight.

The *nested/indirect* leakage patterns this module DOES catch —
`{"debug": {"selected_gold": [...]}}`, `{"metadata": {"evaluation": {"correct": true}}}` —
are still key-based: `selected_gold` and `correct` are themselves protected KEY names, just
nested under an unprotected parent key (`debug`, `metadata`). The walker descends to any
depth, so nesting does not help a forbidden key hide.

### 1.3 MetricResult-shape detection

Beyond named keys, `leakage.py` also flags any dict/dataclass whose key/field set is a
**superset** of `{"metric_name", "value", "status", "detail"}` — the exact shape of
`phase3/evaluation/metrics/types.py::MetricResult` — even if none of those four names is
individually in `PROTECTED_FIELD_NAMES`. A `MetricResult` is evaluator-side machinery by
construction; it must never flow into an agent-visible payload regardless of what its
fields happen to be named, so this is a shape check layered on top of the name check.

### 1.4 What this is NOT

```
NOT A GENERAL STEGANOGRAPHY OR SEMANTIC-INFERENCE SOLUTION.

leakage.py performs STRUCTURAL, KEY-BASED detection over the explicitly enumerated
evaluator-only field set (section 1.1) and the MetricResult shape (section 1.3). It
cannot and does not detect semantic leakage smuggled entirely inside a string VALUE
(e.g. an agent-visible observation whose free text happens to restate a gold answer, or
a benign-looking field whose content encodes hidden information). Catching that class of
leakage would require content/semantic analysis this stage explicitly does not build.
Anyone relying on this module for that guarantee is relying on something it does not
provide.
```

### 1.5 Condition coverage

`leakage.py` is exercised against all six evaluation conditions from
`phase3/evaluation/agent/conditions.py`: the three schema-canonical conditions
(`NO_MEMORY`, `GOLD_EVIDENCE`, `RETRIEVED_MEMORY`) and the three 3.2-E provisional
extensions (`SELECTED_MEMORY_AVAILABLE`, `DERIVED_MEMORY_AVAILABLE`,
`CONFLICTING_MEMORY_AVAILABLE`) — see `test_leakage.py`'s
`test_all_six_conditions_produce_clean_agent_visible_context` and
`test_all_six_conditions_flag_tampered_gold_field`, both parametrized over
`conditions.ALL_CONDITIONS`.

### 1.6 Reuse of `boundary.py`, not reimplementation

`leakage.validate_against_boundary()` calls `boundary.validate_agent_visible()` FIRST (the
existing, authoritative 3.2-B check) and only THEN layers this module's wider, recursive,
dataclass-aware, MetricResult-shape-aware check on top. `boundary.py`'s own walker is
reused verbatim for its part of the job; this module never reimplements dict/list key
scanning from scratch, it only extends what `boundary.py` cannot see (dataclass-embedded
values, tuples, the MetricResult shape).

### 1.7 Status vocabulary

`NO_LEAKAGE` / `LEAKAGE_DETECTED` / `VALIDATION_UNDEFINED`. Malformed input (not a
dict/list/tuple/dataclass/scalar, or an unrecognized `condition` string) is
`VALIDATION_UNDEFINED`, **never** silently coerced to `NO_LEAKAGE` — "we could not check
this" and "we checked and found nothing" are different claims.

### 1.8 Why the report never carries leaked values

A `LeakageResult` reports `findings` as `(path, violation_type, key_name)` tuples — it
never includes the offending VALUE, even for a short scalar. Rationale documented in
`leakage.py`'s `LeakageResult` docstring: a leakage REPORT that itself echoes gold
answers/evidence IDs risks becoming a second leakage vector the moment that report is
logged, displayed, or handed to anything agent-visible. This is the conservative choice
the task brief explicitly allowed ("use judgment and document the choice") — this stage
chose maximum conservatism over the convenience of an inline value preview.

## 2. Determinism

### 2.1 Repeated-run determinism

`determinism.check_repeated_run_determinism(run_fn, n=5)` calls `run_fn()` `n` times and
asserts every result is `==`-equal to the first. It is designed for, and tested against,
`phase3/evaluation/agent/outcomes.py::run_synthetic_agent` (the existing 3.2-E synthetic
agent) — this module does **not** build a second synthetic agent.

### 2.2 Order-sensitive vs. order-independent metrics (enumerated explicitly)

- **ORDER_SENSITIVE** (`determinism.ORDER_SENSITIVE_METRIC_NAMES`): `RECALL_AT_K`,
  `RECIPROCAL_RANK`, `MRR`. Reordering `retrieved_ranked_ids` changes these metrics'
  results, and that is **correct, load-bearing behavior** — rank position is the entire
  point. This module never "fixes" order-sensitivity by auto-sorting a ranked input.
- **ORDER_INDEPENDENT** (`determinism.ORDER_INDEPENDENT_METRIC_NAMES`):
  `EVIDENCE_PRECISION`, `EVIDENCE_RECALL`, `EVIDENCE_COVERAGE`, `IRRELEVANT_MEMORY_RATE`,
  `REDUNDANCY`, `SELECTION_COUNT`, `STRICT_TSR`, `SELECTION_CAPACITY`. These operate on
  sets; reordering their input list(s) must NOT change the result, and this is asserted
  directly (`test_scenario_order_independent_metric_unaffected_by_input_ordering`,
  `test_scenario_strict_tsr_unaffected_by_input_ordering`).

`determinism.classify_order_sensitivity(metric_name)` looks a name up in these two
enumerated sets and returns `ORDER_SENSITIVITY_UNKNOWN` for anything not yet classified —
never a guess.

### 2.3 Run isolation

`determinism.check_run_isolation(run_a_fn, run_b_fn)` executes run A, then run B, then run
A again, and asserts A's two executions are `==`-equal — proving B did not mutate shared
state that affected A's second run.

**Global mutable state audit (by inspection).** `phase3/evaluation/metrics/*.py` and
`phase3/evaluation/agent/*.py` were read in full for this stage. Every function reads only
its own parameters; the only module-level containers found anywhere in either package are
immutable (`frozenset`, `tuple`) or a small number of plain dicts used purely as static,
read-only lookup tables (e.g. `agent/conditions.py::CONDITION_DEFINITIONS`), never written
to anywhere in their own module's source. **Conclusion: no global mutable state was found
in either package by inspection.** `test_determinism.py` makes this an empirically-tested
claim (`test_agent_package_has_no_module_level_mutable_list_or_set_containers`,
`test_agent_package_module_level_dict_constants_are_never_written_to`,
`test_metrics_package_has_no_module_level_mutable_containers`), not merely an assertion in
prose — and `test_run_isolation_detects_contamination_via_shared_mutable_state` proves the
isolation CHECKER itself actually detects contamination when it is deliberately introduced
(in the test, not in production code), so a passing isolation result is not merely "the
checker never fails."

## 3. Canonical serialization rules

- Dict keys are **sorted** (`sort_keys=True`) — key order carries no meaning anywhere in
  this codebase's JSON-like structures, so sorting recovers one canonical form.
- **Lists are NEVER sorted.** `retrieved_ranked_ids` and similar rank-ordered sequences
  keep their exact given order through canonicalization. This is **the single most
  important design decision in this module** (stated verbatim in
  `reproducibility.py`'s module docstring): if lists were canonicalized by sorting, two
  DIFFERENT rankings would collapse to the SAME fingerprint, silently hiding a real
  difference in retrieval/reranking behavior — exactly the opposite of what fingerprinting
  is for.
- `set`/`frozenset` values ARE canonicalized (sorted into a list), because a Python set
  has no order to begin with — recovering a canonical form there discards nothing
  meaningful.
- Tuples normalize to lists, preserving order (used for `AgentExecutionResult`'s
  tuple-typed fields).
- Compact, stable separators (`(",", ":")`); UTF-8 throughout (`ensure_ascii=False`, then
  explicit `.encode("utf-8")` before hashing).
- Non-JSON-serializable input raises `TypeError` — never silently stringified or skipped.

## 4. Fingerprinting

`reproducibility.fingerprint(obj)` = SHA-256 hex digest of `canonical_serialize(obj)`,
UTF-8 encoded. **Never** Python's built-in `hash()`: `hash()` of a `str` is randomized
per-process by default (`PYTHONHASHSEED`), so it would produce a DIFFERENT fingerprint for
IDENTICAL data on every run — the opposite of reproducibility.
`test_module_never_uses_builtin_hash_for_fingerprinting` checks the module's own source
(with docstrings excluded, to avoid false-positiving on this very explanation) never calls
the bare builtin.

Fingerprinted, per manifest: `input_fingerprint`, `agent_visible_context_fingerprint`,
`evaluator_reference_fingerprint`, `configuration_fingerprint`. Artifacts (e.g. a memory
store file) are hashed separately via `digest_bytes()` (raw SHA-256 over bytes, not
`canonical_serialize`, since an artifact is not itself a JSON-like structure).

## 5. Reproducibility manifest

A plain **dict**, not a fixed dataclass — deliberately, so "this field is legitimately
absent" (`INCOMPLETE_MANIFEST`, scenario 11) is directly representable as "key not
present," distinct from "key present with value `None`."

Required fields (`reproducibility.REQUIRED_MANIFEST_FIELDS`): `run_id`, `task_ids`,
`conditions`, `input_fingerprint`, `agent_visible_context_fingerprint`,
`evaluator_reference_fingerprint`, `configuration_fingerprint`, `code_version`,
`contract_version`, `metric_version`, `seed`, `timestamp`, `artifact_refs`.

- **`seed`**: honestly recorded as `"NOT_APPLICABLE"` (`SEED_NOT_APPLICABLE`) when no
  randomness is used anywhere — true for every construct built in this stage (no Qwen, no
  sampling-based retrieval). Per `REPRODUCIBILITY_CONTRACT.md` sections 2–3, this is the
  honest answer, not an omission.
- **`timestamp`**: **metadata-only** (`MANIFEST_METADATA_ONLY_FIELDS`). Two manifests
  differing ONLY in `timestamp` are asserted to produce the SAME
  `manifest_semantic_fingerprint()` (`test_invariant_timestamp_does_not_alter_semantic_
  fingerprint`) — `manifest_semantic_fingerprint()` excludes it before fingerprinting.
- **`artifact_refs`**: list of `{"name", "digest"}` pairs (SHA-256 hex digests).
- Extra caller-supplied keys (via `build_manifest(**extra)`, e.g. `result_fingerprint`
  used only by the synthetic-reconstruction test) are carried verbatim and never part of
  completeness checking.
- **No secrets.** `safe_environment_metadata()` returns exactly `{"python_version",
  "platform"}` — never environment variables, credentials, tokens, or hostnames.

## 6. Artifact verification states

`STATUS_ARTIFACT_INTEGRITY_OK` / `STATUS_ARTIFACT_INTEGRITY_FAILURE` — a digest mismatch
is always surfaced, never auto-repaired or silently accepted.

`verify_reproducibility()` returns exactly one of, in this precedence order:
`INCOMPLETE_MANIFEST` (missing a required field — checked first; nothing else can be
meaningfully verified against an incomplete record) → `ARTIFACT_MISMATCH` → `CONFIGURATION_
MISMATCH` → `INPUT_MISMATCH` → `REPRODUCIBLE_MATCH`.

## 7. Reconstruction

`reproducibility.reconstruct_and_verify(manifest, rerun_fn)` re-runs a caller-supplied,
zero-argument, SYNTHETIC re-execution callable and compares its fingerprint against
`manifest["result_fingerprint"]` (an extra, opt-in manifest field — see section 5).
`test_scenario_synthetic_run_reconstruction_matches` builds a manifest + a
`run_synthetic_agent`-backed callable, re-runs it, and confirms the fingerprint matches;
`test_reconstruction_detects_mismatch_when_rerun_differs` proves a genuine mismatch is
caught, not glossed over. No real dataset or Qwen involved anywhere in this check.

## 8. Environment / scope limitations

- No real dataset (LoCoMo/LongMemEval/MSC/Conversation Chronicles), Qwen, or LLM
  integration exists anywhere in this stage — every scenario is synthetic, hand-authored
  Python data.
- `safe_environment_metadata()` is a minimal placeholder (Python version + platform
  string only); a future Qwen-integrated stage will need to record model weight hash,
  prompt template version, and decoding configuration per
  `REPRODUCIBILITY_CONTRACT.md` section 3 — none of that exists to record yet.
- Artifact-hashing helpers (`digest_bytes`, `verify_artifact_integrity`) only ever
  operate on bytes/paths the CALLER supplies; they never discover files on their own and
  never read from `data/raw/`, `data/processed/`, `data/metadata/`, or `data/reports/`.

## 9. Two mandatory overclaim guards

```
Reproducibility of the evaluation infrastructure does not guarantee bit-identical
output from a future stochastic external LLM.
```

```
The leakage detector is NOT a general steganography/semantic-inference solution --
only structural key-based protection for the explicitly enumerated evaluator-only
field set.
```

## 10. CANONICAL / PROVISIONAL / DIAGNOSTIC-ONLY classification

| Item | Classification | Rationale |
|---|---|---|
| Reuse of `boundary.FORBIDDEN_KEYS` / `validate_agent_visible()` | Inherited CANONICAL-in-practice (3.2-B) | Not re-derived here; used as-is. |
| `leakage.PROTECTED_FIELD_NAMES` additional entries | **PROVISIONAL** | No contract document enumerates this exact additional list; this stage's own explicit choice. |
| MetricResult-shape detection | **PROVISIONAL** | This stage's own construction; no contract document defines a "shape-based" leakage check. |
| Structural-key-only detection scope (vs. content/semantic scanning) | **PROVISIONAL, explicitly limited** | Deliberate false-positive-control design choice; see section 1.4. |
| `determinism.ORDER_SENSITIVE_METRIC_NAMES` / `ORDER_INDEPENDENT_METRIC_NAMES` | **PROVISIONAL** enumeration, but the underlying order-sensitivity FACTS (Recall@K/MRR are rank-based; evidence precision/recall are set-based) are load-bearing properties of the already-frozen-in-practice 3.2-C metric definitions. | This stage's own classification table; the metrics themselves are 3.2-C's. |
| Run-isolation checker (`check_run_isolation`) | **DIAGNOSTIC ONLY** | A testing utility, not a frozen contract object. |
| Canonical serialization rule (sort dict keys, never sort lists, sort sets) | **PROVISIONAL** | No contract document fixes a serialization convention; this stage's own, carefully-justified choice (section 3). |
| SHA-256 fingerprinting (never `hash()`) | **PROVISIONAL** format, but the underlying constraint ("never use a process-randomized hash for a persistent identifier") is a general correctness requirement, not an arbitrary choice. |
| Reproducibility manifest structure (`REQUIRED_MANIFEST_FIELDS`) | **PROVISIONAL** | `REPRODUCIBILITY_CONTRACT.md` section 3 lists WHAT must be recorded narratively; this stage is the first to give it a concrete field-name schema. |
| Artifact integrity states (`ARTIFACT_INTEGRITY_OK`/`FAILURE`) | **PROVISIONAL** | This stage's own vocabulary. |
| Verifier states (`REPRODUCIBLE_MATCH`/`ARTIFACT_MISMATCH`/`CONFIGURATION_MISMATCH`/`INPUT_MISMATCH`/`INCOMPLETE_MANIFEST`/`VERIFICATION_UNDEFINED`) | **PROVISIONAL** | This stage's own vocabulary and precedence ordering. |
| `safe_environment_metadata()` shape | **DIAGNOSTIC ONLY, explicitly a placeholder** | Acknowledged as incomplete for a future Qwen-integrated stage. |
| Synthetic run-reconstruction check | **DIAGNOSTIC ONLY** | Proves the mechanics work over synthetic data; not itself a frozen benchmark procedure. |

## Running the tests

```
python -m pytest phase3/evaluation/tests/ -q
```

436 tests total as of this stage: the prior 334 (unmodified) plus 102 new
(`test_leakage.py`: 40, `test_determinism.py`: 29, `test_reproducibility.py`: 33), all
passing, run multiple times (including once under `-W error`) to confirm determinism and
the absence of hidden warnings.

## What Phase 3.2-G builds next

Phase 3.2-G — **Dataset Evaluation Profiles** — is the next stage. It is NOT begun by this
stage, and this stage does not commit or push anything.
