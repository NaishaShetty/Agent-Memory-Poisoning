# Phase 11.x Option 2 — Expanded Feature Vocabulary Investigation

Written after every real number below was actually computed, per this
project's own "never write the conclusion first" discipline. Nothing here
was tuned against, or has touched, `held_out_pools()`.

**Standing, protected finding from Option 1, unmodified by this report:**
*"The current 9-dimensional sanctioned Phase 6/10 feature vocabulary does not
provide a reliable compact-benign-region vs poison-anomaly structure at the
present data scale."* This report investigates a narrower, separate
question and does not rewrite that conclusion.

---

## 1. What new information was investigated

Two genuinely new information sources, kept as separate experimental
factors (never silently mixed):

- **Structural** (`phase11/expanded_features/structural_features.py`): 8 new
  features — `retrieval_count_raw`, `pool_size`, `graph_degree`,
  `retrieved_with_degree`, `derived_from_degree`, `ancestor_count`,
  `descendant_count`, `lineage_depth`. All computed from real fields already
  on `MemoryScenario`/`ScenarioPool` and the same real, sanctioned
  `RETRIEVED_WITH`/`DERIVED_FROM` edge vocabulary `phase11/gnn/graph_build.py`
  already uses — no new edge type, schema field, or event format.
- **Semantic** (`phase11/expanded_features/semantic_features.py`): the
  already-pinned `sentence-transformers/all-MiniLM-L6-v2` model (reused via
  `phase3/evaluation/foundations/similarity.py::_load_model()`, unmodified),
  reduced from 384 dims via a from-scratch PCA (`numpy.linalg.svd`) fit on
  real training data only.

## 2. Why each feature is scientifically justified

Full per-feature documentation (definition, source field, computation,
security interpretation, availability-before-prediction, leakage analysis,
attack-specificity) is in `structural_features.py`'s
`FEATURE_DOCUMENTATION` dict — tested (`test_every_structural_feature_is_documented`)
to cover every key. Two features (`ancestor_count`, `derived_from_degree`)
are adjacent to `lineage_taint_score`'s inputs but measure something
genuinely different: `lineage_taint_score` is a content-similarity judgment;
these are pure structural counts that never read `content_text`.

## 3. Exact data sources

Identical, non-circular split the Option-1 investigation already
established:

- **Representation-training pools**: `split.train_pools()` (13 real,
  hand-authored scenarios) + `real_benign_scenarios()` (135 real LoCoMo
  turns, tasks 1–9) — 148 real examples, 139 benign / 9 poison.
- **Dev-time evaluation pools**: `split.dev_pools()` (13 real scenarios) +
  `real_poison_scenarios()` (15 real forged memories from all 7 real Phase 4
  attacks, never used in representation training) — 28 real examples, 7
  benign / 21 poison.
- **`held_out_pools()`**: never imported, referenced, or computed against
  anywhere in `phase11/expanded_features/` — enforced by a regression test
  that inspects each function's actual bytecode name references, not just
  its prose.

## 4. Train/dev/held-out boundaries

Unchanged from Option 1. PCA is fit exactly once, on the representation-
training pools' real content only (`fit_semantic_pca_on_training_pools`);
every other call site only ever calls `apply_pca()` with that already-fitted
object — verified by `test_pca_is_fit_only_on_training_pool_content`.

## 5. Leakage analysis

No structural feature reads `is_poison_ground_truth`, `attack_family_ground_truth`,
or any detector output. Verified directly, not just asserted:
`test_structural_features_do_not_change_when_poison_labels_are_flipped`
flips every real scenario's poison label in a pool and confirms every
structural feature value is byte-for-byte identical. Semantic features are
computed from `content_text` only, via a model call identical in kind to the
one Phase 6.6 already makes for a different, already-sanctioned purpose.

## 6. Baseline reproduction

Config **A** (the original 9 sanctioned features alone, rebuilt through the
new package's own generic pipeline) reproduces the Option-1 investigation's
real, previously-reported number exactly: raw-centroid AUROC = **0.25**
(`test_config_a_reproduces_the_existing_nine_feature_investigation_exactly`).
This confirms the new package is internally consistent with the protected
finding before any new feature is added.

## 7. Results for each feature configuration

Real numbers, `dev_pools() + real_poison_scenarios()` (n=28: 21 poison, 7
benign), seeds 11–20:

| Config | dim | raw-centroid AUROC | SVDD AUROC (mean, range) | AE AUROC (mean, range) |
|---|---|---|---|---|
| A (9 sanctioned, baseline) | 9 | 0.248 | 0.178 [0.07, 0.50] | 0.189 [0.12, 0.26] |
| B (A + structural) | 17 | 0.048 | 0.435 [0.25, 0.71] | 0.375 [0.07, 0.59] |
| S (structural only) | 8 | 0.051 | 0.122 [0.05, 0.49] | 0.220 [0.07, 0.50] |
| C (A + semantic, PCA-20) | 29 | 0.204 | 0.293 [0.16, 0.50] | 0.191 [0.12, 0.22] |
| M (semantic only, PCA-20) | 20 | **0.575** | 0.330 [0.09, 0.50] | **0.536 [0.43, 0.59]** |
| D (A + structural + semantic) | 37 | 0.048 | 0.327 [0.13, 0.56] | 0.350 [0.05, 0.57] |

PCA: 20 components retained (capped by `MAX_PCA_DIMS`; cumulative explained
variance on the 148 real training embeddings was only 59.9% at 20
components — the pre-registered cap bound the dimensionality before any
separation result was seen, exactly as intended, even though it means the
semantic representation is a lossy compression of the real embedding space).

**A real, identified confound in the structural results (not papered over):**
`pool_size`/`graph_degree`/`retrieved_with_degree` have enormous variance
(std ≈ 21.4) among the real benign training reference, because
`real_benign_scenarios()` bundles all 135 real LoCoMo turns into ONE pool
(`POOL-REAL-BENIGN-LOCOMO`), while `train_pools()`'s hand-authored benign
sit in much smaller pools (3–13 members) — a real corpus-construction
artifact, not a security-relevant structural difference. Standardized
("z-scored") distance does not fix this — it makes S *worse* (0.051 → 0.112,
still inverted), confirming the raw AUROC swings for B/S/D are dominated by
this confound rather than by genuine signal. **This report does not modify
`real_corpus.py` to fix it**, because doing so would change the pool
composition Option 1's own protected, already-tested numbers depend on —
exactly what the governing instructions prohibit. It is disclosed here as a
real limitation of what could be tested, not resolved.

## 8. Seed sensitivity

Reported directly in the range columns above (10 seeds, 11–20, for every
stochastic configuration). No configuration is seed-stable in an absolute
sense; M (semantic-only) has the tightest AE range (0.43–0.59) of any
non-baseline configuration.

## 9. MemoryGraft behavior

Rather than compare raw anomaly-score magnitudes across configs (invalid —
different feature scales, as the confound in Section 7 demonstrates), the
real memory's **percentile rank within the full 28-example eval set's SVDD
scores** (scale-invariant) was measured, averaged over seeds 11–20:

| Config | MemoryGraft mean percentile (1.0 = most anomalous) |
|---|---|
| A | 0.033 |
| S | 0.022 |
| C | 0.085 |
| M | 0.159 |
| B | 0.281 |
| D | 0.474 |

Config A's 0.033 confirms the original, disclosed blind spot exactly.
Structural/combined configs (B, D) raise it substantially — but **this
cannot be honestly attributed to a genuine structural detection of the
paraphrase-volume mechanism**: `real_poison_scenarios()` bundles MemoryGraft
into a single 15-member pool, giving it a `pool_size`/`graph_degree` value
that happens to sit further from the confounded benign reference than
`dev_pools()`'s small hand-authored pools do — the same Section 7 artifact,
not a mechanism-specific finding. No feature was constructed from
MemoryGraft's own label (verified by Section 5's leakage test), so this is
not attack-specific memorization — but it is also not established, credible
evidence that generic structural information detects this mechanism, given
the identified confound. Recorded honestly as **inconclusive**, not as a fix.

## 10. Whether the expanded representation actually improves separation

**Partially, in one place, modestly: semantic-only (config M) is the first
configuration across BOTH Option 1 and Option 2 to show real, above-chance
separation** — raw-centroid AUROC 0.575, autoencoder AUROC 0.536 with a
comparatively tight seed range (0.43–0.59). This is a real, non-fabricated,
non-confounded result (semantic features have no analogous pool-size
artifact). It is also **modest**: 0.53–0.58 AUROC is a weak signal, far
below what would be needed to build a controlled-FPR detector, and every
other configuration (B, S, C, D) either stays at chance or is dominated by
the structural confound in Section 7.

## 11. Whether this justifies continuing to calibration/gating/GLN

**No — not yet, and not on the current evidence.** Per Section 10 of the
governing instructions, downstream fusion is not justified by "one metric
improved slightly." Config M's AUROC (0.53–0.58) is a real but weak signal;
building calibration/residual-gating/decision-policy machinery on it now
would repeat the exact mistake this investigation exists to avoid — treating
a marginal, single-configuration result as if it were a validated detector.
**Recommended before any such investment**: (a) confirm config M's signal
survives a larger, still non-circular real evaluation set (the same
statistical-power concern Option 1 already addressed once), and (b)
resolve the Section 7 structural confound (would require restructuring
`real_corpus.py`'s benign pool granularity, itself a decision requiring
explicit authorization since it touches data Option 1's protected numbers
depend on) before structural features can be fairly judged at all.

## 12. Complete change audit

**Section 12a — as of the initial Option 2 investigation (before the
Section 15 pool-restructuring follow-on):**

```
FILES ADDED:
  phase11/expanded_features/__init__.py
  phase11/expanded_features/structural_features.py
  phase11/expanded_features/semantic_features.py
  phase11/expanded_features/dataset.py
  phase11/expanded_features/anomaly.py
  phase11/expanded_features/experiment.py
  phase11/tests/test_expanded_features.py
  docs/phase11/PHASE11_X_OPTION2_EXPANDED_FEATURES_REPORT.md (this file)

FILES MODIFIED:
  (none)

DATASETS CHANGED:
  none (real_corpus.py, dev_corpus.py, corpus.py, split.py all untouched)

EXISTING TESTS:
  before = 560 passed, 6 skipped (phase6/ attribution/ phase7/ phase11/, prior session)
  after  = 577 passed, 6 skipped (same suite, all pre-existing tests unchanged)
  phase8/: 22 passed, 7 skipped, confirmed unmodified via `git status --porcelain phase8`
```

**Section 12b — UPDATE (2026-09-19), the authorized pool-restructuring
follow-on (Section 15). This supersedes 12a's "FILES MODIFIED: none" and
"DATASETS CHANGED: none" lines — everything else in 12a stands.**

```
FILES ADDED (this follow-on):
  (none new -- Section 15's report content was added to this existing file)

FILES MODIFIED (this follow-on, explicitly authorized -- "proceed with this"):
  phase11/data/real_corpus.py
    - real_benign_scenarios(): return type changed ScenarioPool -> Tuple[ScenarioPool, ...];
      now returns 9 real per-task pools (15 members each) instead of 1 merged
      135-member pool. Real content (135 real LoCoMo turns) UNCHANGED -- only
      pool grouping changed.
    - real_corpus_pools(): updated to flatten the new tuple return
    - Both changes fully documented in-line with dated Update notes

  phase11/tests/test_gnn_train.py
    - test_real_benign_volume_stabilizes_detection_rate_across_seeds(): call-site
      updated for the new return type; asserted literal updated from
      `{round(24/34, 3)}` (0.706) to `{1.0}`, the real, re-measured detection
      rate under the corrected pool structure. Docstring extended with a dated
      Update note explaining exactly why and pointing to the real before/after
      numbers (both preserved, not deleted) in docs/phase11/PHASE11_REPORT.md

  phase11/expanded_features/experiment.py
  phase11/tests/test_expanded_features.py
  phase11/tests/test_relation_aware_anomaly_investigation.py
    - mechanical call-site update only: `+ (real_benign_scenarios(),)` ->
      `+ real_benign_scenarios()` (the function now returns an already-flat
      tuple). No assertions in test_expanded_features.py or
      test_relation_aware_anomaly_investigation.py needed numeric updates --
      re-verified their real numbers are unchanged (Section 15's own diagnostic
      table), since the sanctioned 9-feature raw values do not depend
      meaningfully on this specific pool-grouping change.

  docs/phase11/PHASE11_REPORT.md
    - Section 2.1: dated Update note added documenting the real, re-measured
      "dev + real benign" number under the corrected pool structure. The
      original 70.6% finding is preserved above it as the historical record,
      not deleted or rewritten.

  docs/phase11/PHASE11_X_OPTION2_EXPANDED_FEATURES_REPORT.md (this file)
    - Section 15 added with the full real result of the authorized change

DATASETS CHANGED (this follow-on, explicitly authorized):
  real_corpus.py's real_benign_scenarios() pool GROUPING only -- same 135
  real LoCoMo turns, same real content, regrouped from 1 pool into 9 real
  per-task pools. dev_corpus.py, corpus.py, split.py, held_out_pools() all
  untouched.

EXISTING TESTS (this follow-on):
  before = 428 passed (phase11/ + phase6/tests/, prior to this follow-on)
  after  = 428 passed (same suite, after the above updates -- one test's
           literal value updated per above, zero tests removed or skipped
           to force a pass)
  broader suite (phase6/ attribution/ phase7/ phase8/ phase11/):
           599 passed, 13 skipped, 0 failed
```

**HELD-OUT DATA ACCESSED (both 12a and 12b):**
  NO for the Option 2 investigation's own new code
  (`phase11/expanded_features/`) — verified by a regression test inspecting
  bytecode name references, not just prose. `test_real_benign_volume_stabilizes_detection_rate_across_seeds`
  (`phase11/tests/test_gnn_train.py`) DOES call `held_out_pools()` — this is
  pre-existing, already-authorized usage from the EARLIER real-data-expansion
  investigation (a prior session, its own established, one-time-per-design
  evaluation protocol, unrelated to Option 1/2's stricter no-held-out rule)
  — re-running it to get its real, updated literal after an authorized
  upstream data change is not a new access for a new purpose, and no
  threshold/config was chosen by looking at that result first.

**DEPENDENCIES CHANGED:** none, in either 12a or 12b.

**SCHEMAS CHANGED:** none, in either 12a or 12b (pool grouping is not a
schema; `ScenarioPool`/`MemoryScenario` themselves are unchanged).

NEW TESTS:
  13 (phase11/tests/test_expanded_features.py) + 4 already existing from the
  Option-1 investigation (test_relation_aware_anomaly_investigation.py,
  content unchanged, still passing) = 17 real, passing regression tests
  added across both Option-1 and Option-2 work. 0 new tests added in the
  12b follow-on (one existing test's literal updated, per above).

REGRESSION STATUS:
  PASS (599 passed, 13 skipped -- all pre-existing, unrelated h4venv-only/
  other environment-gated skips -- 0 failed, phase6/ attribution/ phase7/
  phase8/ phase11/ combined)
```

## 13. Regression test results

Before the Section 15 follow-on: `python -m pytest phase6/ attribution/ phase7/ phase11/ -q`
→ **577 passed, 6 skipped, 0 failed.** `python -m pytest phase11/tests/test_expanded_features.py -q`
→ **13 passed.**

After the Section 15 follow-on: `python -m pytest phase11/ phase6/tests/ -q`
→ **428 passed, 0 failed.** `python -m pytest phase6/ attribution/ phase7/ phase8/ phase11/ -q`
→ **599 passed, 13 skipped, 0 failed.** `python -m phase11.evaluation.run_b10`
reconfirms B9/B10 at **70.6%/7.3%**, unchanged.

## 14. Recommendation for the next step (SUPERSEDED — see Section 15)

The three options originally listed here are addressed by the authorized
follow-on in Section 15 below. Preserved for the historical record:
Section 15's real result is that Option (2), attempted in full, did NOT
recover a usable structural signal — a different, more informative negative
finding than "not yet tried."

---

## 15. UPDATE (2026-09-19) — authorized pool-restructuring follow-on, real result

**Authorized change**: `real_benign_scenarios()` (`phase11/data/real_corpus.py`)
restructured from one merged 135-member pool into 9 real per-task pools (15
members each, matching each real LoCoMo conversation's own natural session
boundary — not an arbitrary chunk size, though it lands within the
requested N=5–20 range). Every call site updated accordingly (`real_corpus_pools()`,
this package's `experiment.py`, and the affected test files) — full list in
the updated change audit, Section 12 below.

**Real result: the confound moved, it did not resolve.** Re-running the
Section 7/9 experiments under the corrected pool structure:

| Config | dim | raw AUROC (before → after) | SVDD mean (before → after) | AE mean (before → after) |
|---|---|---|---|---|
| A (baseline) | 9 | 0.248 → 0.248 (unchanged) | 0.178 → 0.229 | 0.189 → 0.189 |
| B (A + structural) | 17 | 0.048 → 0.048 (unchanged) | 0.435 → 0.146 (worse) | 0.375 → 0.079 (worse) |
| S (structural only) | 8 | 0.051 → 0.051 (unchanged) | 0.122 → 0.122 (unchanged) | 0.220 → 0.116 (worse) |
| M (semantic only) | 20 | 0.575 → 0.575 (unchanged) | 0.330 → 0.412 | 0.536 → **0.565** [0.44, 0.61] |
| D (combined) | 37 | 0.048 → 0.048 (unchanged) | 0.327 → 0.135 (worse) | 0.350 → 0.044 (much worse) |

**Root cause of the non-fix, diagnosed directly, not assumed:** the
restructuring did reduce the benign TRAINING reference's own internal
`pool_size` variance (std 21.4 → 1.27 — the originally-diagnosed confound is
gone). But it exposed a *different*, pre-existing mismatch: the real
evaluation corpus (`dev_pools()`, hand-authored ablation pools of 3–13
members, mean `pool_size` ≈ 1.9) uses an entirely different, unrelated
pool-construction convention than either the new real-benign training
reference (mean `pool_size` ≈ 14.8) or the real poison pool
(`real_poison_scenarios()`, one 15-member pool, mean `pool_size` ≈ 11.7 —
*closer* to the benign training reference than the eval corpus's own real
benign examples are). Measured directly:

```
benign train (9 real LoCoMo pools): pool_size mean=14.79, std=1.27
eval poison  (1 real attack pool):  pool_size mean=11.71
eval benign  (dev_pools(), small):  pool_size mean=1.86
```

This is not a fixable implementation bug — it is a genuine, structural
incompatibility between how this project's real corpora
(`real_corpus.py`, organized by real conversation-task boundaries) and its
hand-authored ablation corpora (`dev_corpus.py`/`corpus.py`, organized by
attack-scenario groupings of 3–13) construct pools, for reasons unrelated to
security. No further re-grouping of the benign reference ALONE can resolve
this without either (a) changing the protected `dev_pools()`/`held_out_pools()`
pool construction (explicitly out of scope — those are the evaluation
corpora, not this experiment's to alter), or (b) choosing benign pool sizes
specifically to match the eval corpus's incidental sizes, which would be
constructing training data to fit a known evaluation outcome — exactly the
outcome-chasing the governing instructions prohibit.

**Revised, final conclusion on structural features**: not usable as tested,
for a real, now well-understood reason (a cross-corpus pool-size-convention
mismatch), not because graph-degree-style structural information is
inherently non-informative. Confirming this would need real retrieval logs
with naturally varying co-retrieval-pool sizes per query — not available in
this project.

**Semantic (config M) is unaffected and, if anything, slightly stronger**:
identical raw AUROC (0.575, semantic features don't depend on pool
topology), and the autoencoder result actually tightened (0.565, range
[0.44, 0.61]) under the corrected structure. This is independent
confirmation that M's modest signal is real, not an artifact of the
structural confound investigated here.

**Recommendation, updated**: Section 11's conclusion stands unchanged — 0.53–0.58
AUROC is still too weak to justify calibration/gating investment on its
own. Of the three original options, (2) has now been attempted and produced
a real, informative negative result; (1) stop here, or (3) pursue config M
further on a larger real evaluation set, remain the two live choices. No
further action taken without your direction.
