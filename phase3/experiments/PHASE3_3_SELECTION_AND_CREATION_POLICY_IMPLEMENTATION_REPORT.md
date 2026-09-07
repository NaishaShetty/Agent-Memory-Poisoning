# Selection Policy & Creation Policy (superseded_by half) — Implementation Report

Status: **COMPLETE** for the scope the user approved
(`PHASE3_SELECTION_AND_CREATION_POLICY_DESIGN_REVIEW.md` §5, decisions 1-4, all
approved as recommended). Built in parallel with the background 120×2 dataset
campaign — fully additive, no shared state or resource with that campaign, no
existing file's default behavior changed.

## 1. What was built

### `superseded_by`-detection half of the creation policy (decision 4)

[`foundations/creation_policy.py`](../evaluation/foundations/creation_policy.py) (new)
— `emit_superseded_by_detected()` appends a real `relationship_detected(superseded_by)`
`CanonicalEvent` (semantic `(superseded, superseding)` order, `mechanism=
"explicit_supersession_call"`); `supersede_memory_with_detection()` orchestrates it
alongside an unmodified `supersede_memory()` call, reporting (not swallowing) a
detection-emission failure independently of the already-durable supersession result.
`memory_versioning.py` itself is untouched — this stays a pure sibling module, per the
design review's own explicit reasoning for why that file should not be touched a third
time for a new capability (only real bug fixes, via the reviewed H.3-R/H.3-R2 process,
justified touching it before).

`equivalent_to`/`conflicts_with` detection remains fully untouched, exactly as decided.

### Selection policy (decisions 1-3)

- [`foundations/similarity.py`](../evaluation/foundations/similarity.py) (new) — the
  benchmark-owned cosine-similarity utility (Option B), pinned to
  `sentence-transformers/all-MiniLM-L6-v2` (the SAME model both `RealMem0Adapter`/
  `RealAMemAdapter` already load internally — no new model dependency). Verified for
  real: `score_candidates("hello world", [...])` returned 0.93 for genuinely related
  text and 0.12 for unrelated text, via the real model under `C:\h4venv`.
- [`foundations/selection_policy.py`](../evaluation/foundations/selection_policy.py)
  (new) — `select_by_threshold()` (threshold-based, capped, can select zero, per
  decision 2); `RETRIEVAL_POOL_SIZE_N = 20` (decision 3, fixed benchmark-wide);
  `calibrate_threshold_from_gold_evidence()` (the empirical calibration procedure).

### Real empirical threshold calibration

Ran `calibrate_threshold_from_gold_evidence()` against **all 125 real (question, gold
evidence) pairs from the full, frozen 120-task LoCoMo formal sample** (seed 33005) —
real content pulled from `_ingest_pool()`, real embeddings from the real pinned model,
not estimated or faked. Result: **threshold = 0.2632820487022401** at the 95%-coverage
target. Real score distribution: min=0.1072, p5=0.2599 (≈ the calibrated threshold, as
expected by construction), median=0.4891, max=0.8351. Recorded as
`CALIBRATED_THRESHOLD_LOCOMO` in `selection_policy.py` (with the real distribution
summary in its own comment) and preserved uncompressed at
`phase3/experiments/results/canonical_store/selection_threshold_calibration.json`
(all 125 raw scores, never only the derived constant).

## 2. What is explicitly NOT done (matches the design review's own scope boundary)

- **Not wired into any live campaign path.** `runner.py::select_from_retrieved()` is
  untouched; the already-executed and currently-running 120×2 dataset campaign uses
  the existing provisional identity-slice policy throughout, unaffected by this work.
  Wiring the new threshold-based policy into `campaign_formal_runner.py`'s live
  conditions is a separate, later decision — it would require re-running every
  affected campaign under the new mechanism, which was not what was approved here.
- **`equivalent_to`/`conflicts_with` detection** — untouched, per the design review's
  own recommendation (genuinely novel research decision, needs an NLI model or
  LLM-judge, out of scope).
- **No `RunConfigRecord.retrieval_pool_size` field added yet** — the design review
  proposed this (§2.3) as where N=20 should eventually live once the selection policy
  is wired into a real run; not added here since nothing yet calls it in a live path
  that would populate it meaningfully.

## 3. Tests

- [`test_creation_policy.py`](../evaluation/tests/test_creation_policy.py) — 2 tests,
  both pass: real event construction/validation, and the orchestrated
  supersession+detection call.
- [`test_selection_policy.py`](../evaluation/tests/test_selection_policy.py) — 5 tests
  (fake-scorer, no real model load, matching this codebase's existing fast-unit-test
  convention), all pass: threshold filtering, zero-selection, max_k capping, empty
  input, and calibration-procedure correctness.
- `similarity.py`'s real-model behavior was verified directly (not just unit-tested
  with a fake) via the standalone probe in §1, and via the real 125-pair calibration
  run in §1 — both real, both under `C:\h4venv`.
