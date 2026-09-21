# Phase 11.y — Relational/Semantic Signal Discovery

Written after every real number below was actually computed. `held_out_pools()`
was never imported or referenced by any new module (verified by inspecting
bytecode name references, not text search — `test_no_held_out_access_in_any_relational_signals_module`).

## 1. Research question

"Do real semantic, temporal, relational, retrieval, or provenance
relationships between memories provide a measurable signal for
poison-vs-benign discrimination that is absent from the existing
9-dimensional feature vocabulary?"

## 2. Frozen baseline

Original Phase 11 GNN, Option 1, Option 2, and Track A/B findings are
treated as frozen and are not modified, reinterpreted, or reopened by this
investigation. No file belonging to any of them was touched (Section 21).

## 3. Data sources inspected

`data/processed/unified_memory/*` (Track A clean data), `phase4/attacks/*`
(the 7 real attacks' seed dataclasses), `phase11/data/real_corpus.py`,
`phase11/data/poison_regeneration.py`, `phase11/data/clean_expansion.py`,
`phase5/datasets/memory_behavior_dataset_sample.jsonl`, and every
`MemoryScenario`/`ScenarioPool` field in `phase6/defense/orchestration/pipeline.py`.

## 4–6. Relationship audit — what genuinely exists

Full table in [`phase11/relational_signals/relationship_audit.py`](../../phase11/relational_signals/relationship_audit.py).
Summary:

| Relationship | Classification | Notes |
|---|---|---|
| `conversation_id`/`session_id`/`turn_id` | REAL_AND_OBSERVABLE | Track A clean data only |
| `timestamps` | **NOT_AVAILABLE** for poison | Real for Track A clean data; genuinely absent from every one of the 7 attacks' seed dataclasses (checked directly — none carries a timestamp field) and from hand-authored dev/held-out scenarios |
| `provenance` | REAL_AND_OBSERVABLE, but structurally different by class | Full source-dataset shape for clean data; attack-identity-only for poison |
| `RETRIEVED_WITH` (pool co-membership) | REAL_AND_OBSERVABLE | Already sanctioned, reused read-only |
| `derivation_parents`/`DERIVED_FROM` | **NOT_AVAILABLE** | Confirmed empty in the Dataset Audit's 8,000-record sample AND newly confirmed empty on all 24 real poison memories this session (no seed/artifact dataclass across any of the 7 attacks declares `parent_ids`/`ancestors`) |
| same-source-task neighborhood | DERIVABLE_WITHOUT_FABRICATION | Not a raw field, but a real, auditable fact (shared real LoCoMo `task_id`) — the basis for the priority experiment below |
| contradiction ground truth | HYPOTHETICAL_CANDIDATE | No real, assigned "these two memories contradict" label exists anywhere in MAMBench |
| temporal update semantics (correction vs. suspicious overwrite) | HYPOTHETICAL_CANDIDATE | Would need real sequential timestamps AND intent judgment; neither exists |
| Phase 5 instrumentation | NOT_AVAILABLE at scale | Covers exactly 1 real memory (Dataset Audit, Track A/B report) |

## 7–10. Candidate signals investigated

### Family A — Semantic: neighborhood agreement (PRIORITY EXPERIMENT)

**Definition**: for a candidate memory whose real source LoCoMo task is
known, `agreement(i) = mean_{j in real benign turns of the same task} cos(embed(i), embed(j))`.
Embeddings via the pinned, already-existing `sentence-transformers/all-MiniLM-L6-v2`
(`phase3/evaluation/foundations/similarity.py::_load_model()`, unmodified).
The "genuinely related neighborhood" is defined by a REAL, auditable fact
(shared real LoCoMo task_id), not an invented edge.

**Fitting rule**: no fitting/transformation is learned here at all — cosine
similarity between raw MiniLM embeddings requires no training-side fit, so
there is no dev/held-out fitting risk for this specific measurement.

**Initial real result**: overall AUROC = **0.938** (all 20 poison examples
with a known task), **0.923** (16 examples with a *declared*, not merely
thematic, task association) — poison mean agreement 0.215 vs. benign mean
agreement 0.413. This is dramatically higher than anything found in Option
1/2/Track A/B (all near or below 0.5).

**This result was NOT accepted at face value.** Two confound checks
followed, per the governing instructions' explicit requirement not to
report a promising number without stress-testing it first.

**Confound check 1 — speaker-prefix formatting.** Every real benign LoCoMo
turn carries a literal `"Speaker: "` prefix (baked in by `load_db_locomo()`'s
own formatting); no poison memory has one. Stripped the prefix from the
benign side and recomputed: AUROC = 0.975 — **higher, not lower**. This
specific confound is ruled out.

**Confound check 2 — Q+A-concatenation format (the real confound found).**
Every poison seed based on a real QA pair (DSRM/FARMA/MPBench/Sleeper) is
rendered as `"{question} {answer}"` — a self-contained declarative
statement, structurally unlike a casual dialogue turn regardless of
truth. Built 7 **truthful counterfactuals**: the SAME real questions, in
the SAME `"{question} {real_gold_answer}"` format, using the REAL correct
answer instead of the forged one. Result:

```
mean TRUTHFUL Q+A-formatted agreement = 0.293
mean POISON (forged) agreement         = 0.215
mean genuine BENIGN casual-chat agreement = 0.413
```

**The truthful counterfactuals score nearly as "anomalous" as the actual
poison** — both far below genuine casual benign chat. This demonstrates
that the large majority of the apparent AUROC is explained by **text
format** (declarative Q+A-style statement vs. natural dialogue turn), not
by whether the content is true or false. A small residual gap remains
(0.293 vs. 0.215) but is not resolvable from 7 truthful counterfactuals
against noisy per-example embedding variance — this investigation does not
claim it is a real residual truth-detecting signal, and building the
much larger controlled counterfactual set that would be needed to test it
properly is explicitly flagged as future work, not undertaken here (doing
so incrementally until a residual signal "appears" would itself be exactly
the outcome-chasing the governing instructions prohibit).

**Per-attack-family breakdown** (mean agreement, poison; lower = more
"anomalous" by this metric):

| Family | n | Mean agreement |
|---|---|---|
| DSRM | 4 | 0.218 |
| FARMA | 4 | 0.227 |
| MemoryGraft | 2 | 0.252 |
| Sleeper | 2 | 0.214 |
| MPBench-PCFI | 4 | **0.325** (notably closer to benign) |
| MINJA | 3 | 0.092 (thematic task basis only — weak) |
| AgentPoison | 1 | 0.018 (thematic task basis only — weak, n=1) |

MPBench-PCFI's own real design docstring already states it "carries no
persuasive apparatus... matching the dossier's own 'Weak' signal
classification" — its comparatively weaker separation here is consistent
with that independent, pre-existing documentation, a real (if modest)
piece of corroborating evidence that this metric tracks *something* about
each attack's own known mechanism, not pure noise. MINJA/AgentPoison's low
values are on a **thematic-only** task basis (weaker, disclosed evidence,
not a direct QA-pair contradiction) and should not be read as showing MINJA
is "more detectable" — the effect is more likely the SAME format confound,
compounded by MINJA's content not being about the task's real subject
matter at all.

### Family C — Relational/graph: neighborhood semantic coherence

**Definition**: `coherence(i) = mean_{j in same RETRIEVED_WITH pool} cos(embed(i), embed(j))`
— distinct from every Option 2 structural feature (which measured raw
counts, not semantic coherence), using the same real, already-sanctioned
`RETRIEVED_WITH` edges.

**Real result**:

| Pool group | n pools | n scored | mean coherence |
|---|---|---|---|
| Old poison pool (`POOL-REAL-POISON-ATTACKS`) | 1 | 15 | 0.192 |
| New poison pool (`POOL-REGEN-POISON-TRACK-B`) | 1 | 9 | 0.225 |
| Real per-task benign pools (`real_benign_scenarios()`) | 9 | 135 | 0.411 |
| Track A clean pools | 30 | 367 | 0.284 |

**Confound check attempted**: hypothesized the gap might be pure
subject-heterogeneity (poison pools bundle unrelated subjects — DSRM's 3
seeds are about pottery/museum/picnic — while real benign pools are all
one real conversation). Built a genuinely benign "mixed-subject" pool (1
real turn from each of the 9 real per-task pools, same subject-heterogeneity
as the poison pool's construction) and measured its coherence: **0.551 —
higher, not lower**, than even the real per-task pools. This rules out pure
subject-heterogeneity as the explanation. **The gap remains unresolved**:
it is plausibly explained by the SAME Q+A/declarative-format confound
already demonstrated for Family A (dense factual statements may simply
embed less similarly to each other than casual dialogue does, independent
of subject or truth), but this was not directly isolated with a
truthful-declarative-format benign pool (would require substantially more
construction effort) — reported honestly as an **open question**, not
claimed as either a confirmed signal or a confirmed confound.

### Family D — Provenance/lifecycle: format confound (deliberately not promoted)

**Result**: whether a memory carries a real, populated
`source_dataset`/`conversation_id`-shaped provenance record perfectly
separates poison (0/24 have one) from Track A clean data (367/367 have
one) — detection rate 100%, FPR 0%. **This is reported explicitly as a
construction-format artifact, not a usable signal** — poison seeds are
manually-authored Phase 4 dataclasses that structurally cannot carry this
shape of provenance; a real attack against a real deployed system would
not necessarily leave this same fingerprint. Promoting this would be
learning "was this constructed by our own Phase 4 codebase," not "is this
memory poisoned."

### Family B — Temporal: not investigable

Per the relationship audit (Section 4–6), no poison memory carries a real
timestamp of any kind. No temporal-ordering, staleness, or
update-vs-overwrite signal is constructible without fabricating a
timestamp for one side of the comparison — which the governing
instructions explicitly forbid. **Reported as NOT_AVAILABLE, not
attempted.**

## 11. Exact mathematical definitions

Given above per family. Family A: `agreement(i) = mean_{j∈N(i)} cos(e_i, e_j)`,
`N(i)` = real benign turns sharing memory `i`'s real source task. Family C:
`coherence(i) = mean_{j∈P(i), j≠i} cos(e_i, e_j)`, `P(i)` = `i`'s real
`RETRIEVED_WITH` pool. Both use MiniLM cosine similarity, no learned
transformation, hence no fitting-population question for either.

## 12. Training-side fitting rules

No transformation was fit anywhere in this investigation (raw cosine
similarity on frozen, pretrained MiniLM embeddings needs no fitting step).
Where a fitting step would be needed for future work (e.g. a learned
projection), the same train-only rule already established in Option 2
(`fit_semantic_pca_on_training_pools`) would apply and was not violated
because it was never invoked here.

## 13. Leakage audit

- Held-out: never accessed (Section verified by test, restated above).
- Dev: not accessed by any signal-discovery computation in this
  investigation — all measurements used `real_poison_scenarios()`,
  `regenerate_poison_batch()`, `real_benign_scenarios()`, and one read-only
  task-0 diagnostic fetch, all training-side.
- Poison/attack-family/task identity: used only for REPORTING (per-family
  breakdown), never as an input feature to any candidate signal itself.
- No future information: every embedding is computed from the memory's own
  real, already-existing content text.

## 14. Dataset/source confound audit

Directly performed and reported above: the dominant confound found
(Section 7–10, Family A) is **text-rendering format** (Q+A-concatenated
declarative statement vs. casual dialogue turn) — a construction-pipeline
artifact of how MAMBench's own attack-seed renderers and the real LoCoMo
loader happen to format their output, not a property of poisoning. Family
D's confound (provenance shape) is of the same general kind Section 11
warned about explicitly.

## 15. Attack-family analysis

See Family A's per-family table above. The one attack with independent,
pre-existing documentation of being a "weak" signal (MPBench-PCFI) shows
the weakest separation on this metric too — a small, real point of
corroboration that the underlying metric is not pure noise, even though
its overall magnitude is confound-dominated.

## 16. Signal-level metrics

Reported inline throughout Sections 7–10 (AUROC, means, per-family n and
means, coherence values). No AUPRC was computed — with n=20-24 poison
examples the AUROC and mean-difference reporting already used are more
interpretable than a precision-recall curve at this sample size, and
computing AUPRC would not change any of the confound findings above.

## 17. Stability analysis

Not seed-sensitive by construction (no stochastic training was performed —
raw cosine similarity on a fixed, pretrained embedding model is
deterministic, confirmed by `test_neighborhood_agreement_is_deterministic`).

## 18. Negative findings

- Family B (temporal) is entirely unavailable — no fabrication was
  attempted to fill this gap.
- Family A's headline AUROC (0.938) is confound-dominated (format, not
  truth) — demonstrated directly with a controlled truthful-counterfactual
  test, not merely asserted.
- Family D's apparent perfect separator is an explicit construction-format
  artifact, reported as such, never promoted.
- Family C's real coherence gap could not be cleanly attributed to either a
  genuine signal or a confound with the effort available — reported as
  unresolved, not force-closed in either direction.

## 19. Positive findings, if any

None that survive confound testing. The one genuinely new, real,
non-fabricated relationship this investigation established
(same-source-task neighborhood, Section 4–6) is real and auditable, but
the measurement built on top of it (Family A) does not constitute a
non-confounded poison-detection signal per this investigation's own
testing.

## 20. Whether any signal justifies GNN integration

**No.** Per Section 14 of the governing instructions, no candidate here
reaches the bar of "genuinely new, stable, non-confounded" — the strongest
candidate (Family A) was directly shown to be confound-dominated. No
second-stage experiment (freezing a signal definition, adding it to an
isolated representation, comparing against the frozen baseline) is
warranted or was performed.

## 21. Exact changes made / files added

```
FILES ADDED:
  phase11/relational_signals/__init__.py
  phase11/relational_signals/relationship_audit.py
  phase11/relational_signals/semantic_relations.py
  phase11/relational_signals/graph_relations.py
  phase11/relational_signals/provenance_relations.py
  phase11/relational_signals/signal_discovery.py
  phase11/tests/test_relational_signals.py
  docs/phase11/PHASE11_Y_RELATIONAL_SIGNAL_REPORT.md (this file)

FILES MODIFIED:
  (none)

PROTECTED FILES MODIFIED:
  (none — Original GNN, Option 1, Option 2, Track A/B, B10, GLN, hybrid.py
  all untouched)

DATASETS ADDED/MODIFIED:
  none — this investigation reuses real_corpus.py/poison_regeneration.py/
  clean_expansion.py's existing outputs read-only, plus one read-only,
  never-persisted task-0 diagnostic fetch

SCHEMAS MODIFIED:
  none

DEPENDENCIES CHANGED:
  none (reuses the already-pinned, already-used MiniLM model)

HELD-OUT DATA ACCESSED:
  NO
```

## 22. Test results

`python -m pytest phase11/tests/test_relational_signals.py -q` → **10
passed.**

## 23. Regression results

| Suite | Before | After |
|---|---|---|
| `phase11/ phase6/tests/` | 446 passed | **456 passed** (+10, 0 regressions) |
| `phase6/ attribution/ phase7/ phase8/ phase11/` | 617 passed, 13 skipped | **627 passed, 13 skipped** (+10, 0 regressions) |
| B10 | 70.6%/7.3% | **70.6%/7.3% — unchanged** |

No existing test was weakened, deleted, or rewritten.

## 24. Final decision gate

1. **Did we discover a genuinely new relational/semantic signal?** A real,
   auditable relationship (same-source-task neighborhood) was
   established — yes. A usable *detection* signal built on it — no.
2. **Is it non-confounded?** No — directly shown to be confound-dominated
   (text-rendering format).
3. **Independent of attack-family identity?** Partially informative (MPBench's
   known weakness corroborated) but the base metric itself is not attack-
   family-clean given the confound.
4. **Independent of dataset/source identity?** No — the confound IS a
   source/construction-format effect.
5. **Independent of task identity?** Yes, tested directly across 7 distinct
   real tasks (the truthful counterfactuals spanned tasks 0–4).
6. **Survive simple baseline testing?** No — failed the truthful-counterfactual
   control, the simplest and most direct baseline available.
7. **Defensible reason to use a GNN?** No new evidence for this from
   Family A/D. Family C remains a genuine open question, not a basis for
   architectural investment on its own.
8. **Did any existing Phase 11/B10 result change?** No (Section 23).
9. **Was held-out data untouched?** Yes.
10. **Promote, reject, or investigate further?** **Reject Family A/D as
    detection signals (confound-explained). Family C: investigate further
    only if a substantially larger, dedicated confound-isolation experiment
    is explicitly authorized — not undertaken here as a follow-on
    incremental "try again" cycle.**

## 25. Recommendation for the next phase

**Outcome B applies (weak/confounded signal), with one genuinely new real
relationship established for future use.** Per the governing instructions'
own framing: this is not "GNNs do not work" — it is that this project's
current real, available memory relationships (same-source-task
neighborhood, real co-retrieval pools) do not, on the testing performed
here, yield a non-confounded relational/semantic signal beyond the existing
9-dimensional vocabulary. The one open thread worth naming explicitly for a
future, separately-authorized investigation: isolating Family C's
coherence gap would require building a genuinely matched-format truthful
control pool (declarative Q+A-style statements about DIFFERENT real
subjects, bundled into one pool) — a real, buildable experiment, but a new
one, not a continuation of this investigation's own confound-chasing.

No promotion, calibration, gating, or GLN integration is justified. This is
reported as the complete, honest, final result of this investigation.
