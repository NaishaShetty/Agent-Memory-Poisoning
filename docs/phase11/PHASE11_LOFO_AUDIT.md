# Phase 11 — GNN Leave-One-Attack-Family-Out Audit

Written before any LOFO retraining is run, per this project's own "audit
before experiment" discipline. Every claim below is traced directly from
the actual code paths (`phase11/gnn/train.py`, `features.py`,
`graph_build.py`, `model.py`, `phase11/data/split.py`,
`phase6/evaluation/ablations/dev_corpus.py`/`corpus.py`), not inferred from
prior reports' prose.

## 1. Attack-family identity — traced, not assumed

**Finding, stated plainly up front: the GNN's own training/held-out corpus
(`phase11/data/split.py`'s `all_dev_pools()`/`held_out_pools()`, which wrap
`phase6/evaluation/ablations/dev_corpus.py`/`corpus.py`) does NOT use the
Phase 4 attack-family taxonomy (`dsrm`, `farma`, `mpbench`, `memorygraft`,
`sleeper`, `agentpoison`, `minja`) that Phase 11.z's real-corpus work uses.**
It uses a separate, smaller, hand-authored taxonomy defined directly as
string literals on each `MemoryScenario.attack_family_ground_truth` in
`dev_corpus.py`/`corpus.py`:

| Canonical label (exact string, case-sensitive) | Origin | Real Phase 4 attack it is modeled on |
|---|---|---|
| `"FARMA"` | `dev_corpus.py::dev_admission_pool()`, `corpus.py`'s FARMA pools | FARMA (admission-guard forged-reasoning shape) |
| `"MemoryGraft-style-volume"` | `dev_corpus.py::dev_near_duplicate_pool()`/`dev_paraphrased_pool()`, `corpus.py`'s NEARDUP/PARAPHRASE pools | MemoryGraft (near-duplicate/paraphrase volume-consensus shape) |
| `"Sleeper"` | `dev_corpus.py::dev_sleeper_pool()`, `corpus.py`'s SLEEPER pools | Sleeper Memory Poisoning |
| `"propagated"` | `dev_corpus.py::dev_propagation_scenarios()`, `corpus.py`'s PROPAGATION pool | Not a Phase 4 attack at all — a structural category (propagation-guard-shaped lineage-taint scenarios), assigned this label by `split.py::_propagation_pool_from_dev_tuples()` |

**DSRM, MPBench-PCFI, AgentPoison, and MINJA never appear as a family label
anywhere in `dev_corpus.py` or `corpus.py`.** They exist only in
`phase11/data/real_corpus.py` (the real-LoCoMo/real-injector corpus used by
the *separate* real-data-expansion investigation, `PHASE11_REPORT.md` §2.1)
and in Phase 11.z's relational-signal work — neither of which
`run_gnn_feasibility_study()` (the shipped GNN) trains or evaluates
against. **This LOFO investigation is therefore scoped to the 4 families
the actual shipped GNN corpus contains — `FARMA`, `MemoryGraft-style-volume`,
`Sleeper`, `propagated` — not the 7 Phase 4 attacks.** This is disclosed
here explicitly rather than silently substituting a different, larger
family list that the GNN was never trained or evaluated on in the first
place.

**Where the label enters the GNN dataset**: `phase11/gnn/train.py::build_dataset()`
→ `phase11/gnn/graph_build.py::build_pools_graph()` reads
`MemoryScenario.is_poison_ground_truth` onto each graph node, but **the
graph itself never carries `attack_family_ground_truth`** — confirmed by
reading `build_pool_graph()` (`graph_build.py` lines 22-41): the only node
attribute set is `is_poison_ground_truth`. `attack_family_ground_truth` is
available only on the original `MemoryScenario` objects the pools are built
from, never propagated into the `GraphDataset`/`MinimalGNN` pipeline at
all. **The trained model architecture has no access to family identity as
a feature or label — confirmed directly, not assumed.** This matters for
§2 below: family identity cannot leak through the model's own inputs,
because it was never an input to begin with; the only way family identity
can matter is through which *scenarios* (and their real content/structure)
are present during training.

**Ambiguous/multiple family membership**: none found. Every poison-bearing
pool in both `dev_corpus.py` and `corpus.py` is single-family (verified
directly, per-pool, in §7's table) — no pool mixes two different poison
families' scenarios together. Benign scenarios carry
`attack_family_ground_truth=None` (the dataclass default), never a family
label.

## 2. Leakage-path audit

Traced exhaustively through every stage `build_dataset()`/`train_model()`/
`evaluate()` actually touches:

| Path | Present in this pipeline? | Leakage risk for excluded family X |
|---|---|---|
| Training examples | Yes — `train_ds = build_dataset(filtered_pools)` | **Controlled**: filtering happens at the `ScenarioPool.memories` level, before any downstream computation. If family X's poison scenarios are removed from the pools passed to `build_dataset()`, no code path downstream can reintroduce them — `build_dataset()` only ever reads from the `pools` argument it is given. |
| Benign reference data | Yes, same pools | Benign scenarios carry no family label (§1) — not excludable or includable by family; unaffected by which family is held out. |
| Feature statistics | **None exist.** `features.py::pool_node_features()` computes every one of the 9 sanctioned features per-scenario (or per-pool, for `consensus_divergence_score` only) directly from real-time regex/lexical rules (`admission_signals`, `imperative_write_directive_signal`, `pool_consensus_divergence_signals`, `lineage_taint_signal`) — **no mean/std/min-max/scaler is fit anywhere in this pipeline** (confirmed by reading `model.py`: raw feature tensors are fed directly into `nn.Linear`, no normalization layer, no `StandardScaler`, no precomputed statistic of any kind). There is therefore no "fitted statistics" leakage path to audit — it does not exist in this architecture. |
| Normalization/standardization | **None.** Same finding as above. |
| PCA/dimensionality reduction | **None.** The GNN uses the raw 9-dim feature vector directly; PCA exists only in the separate Option 2 (`expanded_features/semantic_features.py`) investigation, never imported by `phase11/gnn/*`. |
| Graph construction | Yes — `build_pools_graph(pools)` | **Controlled, same as training examples**: the graph is built fresh from whatever `pools` are passed. Filtering before this call means family X's scenarios never become nodes, and (§6) their edges never form. One subtlety, confirmed by direct testing (§6 below): synthetic ancestor nodes (`graph_build.py` lines 32-40) are added only when a REMAINING scenario's `parent_ids`/`ancestors` reference them — removing a family's own poison scenarios that owned those references also removes the synthetic ancestor nodes that existed only for them. No orphaned family-X-derived node can survive filtering. |
| Adjacency construction | Yes, downstream of graph construction | Same as above — `node_order_and_adjacency()` operates on whatever graph it is given; no independent data access. |
| Batching | N/A — no batching; the whole graph is one forward pass. | No risk. |
| Model initialization | `torch.manual_seed(seed)` only, in `MinimalGNN.__init__` and again in `train_model()` | No data-dependent initialization of any kind — pure PRNG seeding, independent of which family is present. |
| Threshold selection | `_threshold_for_target_fpr(train_scores, train_ds.labels, ...)` | **Controlled if, and only if, `train_scores`/`train_ds` come from the SAME filtered (family-X-excluded) training set** — traced and confirmed: the existing `run_gnn_feasibility_study()` already computes the threshold from `train_ds`, never from held-out data. The LOFO implementation (§Part 3) reuses this exact function on the fold-local `train_ds`, so family X's held-out labels never enter this computation. |
| Calibration | N/A — no separate calibration step exists beyond the in-sample threshold above. | No risk. |
| Early stopping | **None.** Training runs a fixed `EPOCHS = 300` with no validation-based stopping criterion (confirmed: `train_model()`'s loop has no break condition, no dev-set evaluation inside the loop). | No risk — there is no stopping decision to leak into. |
| Hyperparameter selection | `hidden_dim=8, num_layers=2, WEIGHT_DECAY=0.0, LEARNING_RATE=0.05` — all frozen module-level constants, already swept once against the pooled-family held-out result in the original Phase 11.2 investigation (`PHASE11_REPORT.md` §2) and never touched again. | **Explicitly held fixed for this investigation** (Part 5 of the task instructions) — not re-swept per fold, so no per-fold hyperparameter-selection leakage is possible because no such selection happens. |
| Seed selection | `SEED=11` shipped default; seeds 11-20 explored in the original stability study | LOFO reuses the same `range(11, 21)` protocol (§9/Part 6) — every fold uses the identical seed set, not a family-tuned seed. |
| Evaluation helpers | `evaluate()` | Only ever called on `held_out_ds`, built once from unmodified `held_out_pools()` — never used to select anything upstream of itself. |

**Conclusion of §2: the only real leakage path in this architecture is
"does family X's data appear in the `pools` object passed into
`build_dataset()` for training." Every other stage (features, threshold,
model init, seeds) reads only from whatever `GraphDataset` it is handed —
none of them independently re-fetches broader corpus data. A single,
correctly-scoped filter at the `pools` level is therefore sufficient to
make every downstream stage leakage-safe — confirmed by tracing, not
assumed.**

## 3. Feature-construction audit

All 9 features are generated by calling the SAME shipped, already-frozen
Phase 6/10 signal functions `run_b9_risk_composed()` uses (`features.py`
lines 22-28) — no new feature logic was written for the GNN itself.

| Feature | Generation | Fitted or rule-derived? | Family-specific behavior? | Reads poison labels? |
|---|---|---|---|---|
| `consensus_divergence_score` | `pool_consensus_divergence_signals(contents)` — pairwise Jaccard token-set divergence within the SAME pool, dedup-clustered | Rule-derived (fixed thresholds `NEAR_DUPLICATE_THRESHOLD`/`DEDUP_DAMPENING_EXPONENT`, not fit on any corpus) | No — pure lexical-overlap computation; would score any near-duplicate cluster the same regardless of which attack authored it | **No** — reads only `content_text` |
| `decision_log_vocabulary_score`, `perfection_claim_score`, `self_reference_score` | `admission_signals()` (`reasoning_guard.py::compute_signals`) | Rule-derived (regex/keyword) | No — same phrase-pattern detector regardless of attack family | No |
| `imperative_write_directive_score` | `imperative_write_directive_signal()` | Rule-derived (regex, Stage 6.8) | No | No |
| `lineage_taint_score` | `lineage_taint_signal()`, only computed `if scenario.ancestors` | Rule-derived (content-overlap vs. ancestor state) | No | No — reads ancestor ADMISSION STATE (QUARANTINED/TRUSTED), a structural fact, not a poison label |
| `provenance_anomaly_score`, `template_anomaly_score` | `admission_signals()` (same call as above) | Rule-derived | No | No |
| `dormancy_activation_score` | Hardcoded constant `1.0` for every scenario (`features.py` line 98, disclosed in its own inline comment: this corpus models a single admission event with no retrieval history) | **Constant** — not derived from content, labels, or family at all | No — literally identical for every node | No |

**No feature reads `is_poison_ground_truth` or `attack_family_ground_truth`
anywhere** — confirmed by reading every function `pool_node_features()`
calls; each takes only `content_text`/`ancestors`/pool-level `contents` as
input, never the scenario's own label fields. **No feature has any global,
corpus-wide fitted statistic** (§2's finding, restated here for
completeness). **Known construction artifacts from earlier Phase 11
investigations**: none apply to these 9 raw features directly — the
confounds found in Options 1/2/Y (pool-size mismatch, Q+A-format bias) live
in *derived/expanded* features (`expanded_features/`, `relational_signals/`)
that the GNN's `FEATURE_KEYS` does not include. The GNN's own 9-feature
input is the same one Option 1 already found does not compactly separate
poison from benign (raw-centroid AUROC 0.25) — a pre-existing, disclosed
weakness of the feature set itself, orthogonal to the family-generalization
question this investigation asks.

**One real, disclosed pool-composition dependency, not a leakage path**:
`consensus_divergence_score` is computed per-POOL (all `contents` in a
pool compared against each other), so a benign scenario's own feature
VALUE can shift between "family X present in this pool" and "family X
excluded from this pool" — this is expected, correct behavior (the model
must see the real, recomputed pool composition of its own fold, not a
stale value), not a leakage channel, since it never uses X's *label*, only
X's *absence* changing what the remaining scenarios are compared against.
Confirmed moot for this corpus specifically: §7's table shows every
poison-bearing pool in `dev_corpus.py`/`corpus.py` is single-family, so
excluding family X's poison scenarios from a pool that only ever contained
family X's poison alongside pool-local benign truth memories reduces that
pool to (benign-only or empty), never to a "mixed-family, now
recalculated" pool — there is no cross-family contamination case to even
worry about in this specific corpus.

## 4. Normalization/statistics audit

**None exist in this pipeline — confirmed by direct code reading, not
absence-of-evidence reasoning.** `model.py`'s `MinimalGNN.forward()` feeds
the raw feature tensor straight into `nn.Linear` layers; no
`torch.nn.BatchNorm`, no manual mean/std computation, no min-max scaling
appears anywhere in `phase11/gnn/`. §2's table already covers this. There
is therefore no "was it fit training-only vs. globally" question to answer
for this specific model — the answer is "no statistic is fit at all," which
is itself the reason this leakage path does not need a correction in
Part 3/4's implementation.

## 5. Threshold-fitting audit

Traced directly from `train.py::run_gnn_feasibility_study()` and
`_threshold_for_target_fpr()`:

- **Selected on training data, in-sample** — the same real, disclosed
  trade-off `train.py`'s own module docstring already names (§2's approach
  2): the threshold is swept over `train_scores` (the model's own
  predictions on the data it was just trained on), not a disjoint
  validation set. This was a deliberate, previously-disclosed choice
  (splitting the already-tiny 23-scenario dev corpus further was tried —
  leave-one-pool-out cross-validation — and measurably failed to transfer,
  per `PHASE11_REPORT.md` §2 approach 1).
- **Not learned** — it is a deterministic sweep (`_threshold_for_target_fpr`)
  against a fixed `TARGET_TRAIN_FALSE_POSITIVE_RATE = 0.10`, not a
  gradient-optimized parameter.
- **Uses poison labels** — yes, by design (it needs `train_ds.labels` to
  know which scores are benign, to keep the benign FPR at the target rate);
  these are the FOLD's own training labels, never the held-out family's.
- **Selected globally, not per-seed or per-fold in the original
  implementation** — because the original implementation has no folds.
  **For LOFO, this audit requires threshold selection to be fold-local AND
  seed-local**: each (fold, seed) combination trains its own model on its
  own family-X-excluded training set, and must select its own threshold
  from that SAME fold's own `train_scores`/`train_ds.labels` — reusing
  `_threshold_for_target_fpr()` unmodified, called fresh once per (fold,
  seed) pair. This is a direct, mechanical application of the existing
  function to fold-local inputs, not a new threshold-selection algorithm —
  no change to `_threshold_for_target_fpr()` itself is needed or made.
- **Never selected using the excluded family's test labels** — confirmed
  by construction: `train_ds` for fold X never contains family X's
  scenarios at all (§2), so `train_ds.labels` cannot contain a family-X
  poison label to sweep the threshold against.

## 6. Graph-construction audit

Confirmed directly from `graph_build.py`, not assumed:

- **One graph per `ScenarioPool`** (`build_pool_graph()`), **unioned into
  one combined graph per call to `build_pools_graph(pools)`** via
  `nx.union(..., rename=("", ""))` — `rename=("", "")` preserves each
  pool's own node ids verbatim (no pool-prefix renaming), which matters
  because scenario ids are already globally unique across pools in this
  corpus (confirmed: no id collision between e.g. `DEV-NEARDUP-POISON-0`
  and any `corpus.py` id).
- **Nodes**: every `MemoryScenario.scenario_id` in a pool, plus any
  `parent_id`/`ancestor.memory_id` referenced by a scenario in that pool
  that is not already a node (added with `is_poison_ground_truth=False` —
  a real, pre-existing, disclosed default for "an ancestor we don't have a
  full record for," not something this investigation introduces).
- **Edges**: `RETRIEVED_WITH` between every pair of scenarios in the SAME
  pool (complete graph within a pool); `DERIVED_FROM` from a scenario to
  each of its own real `parent_ids`/`ancestors`. No other edge type exists
  in this codepath (confirmed: only these two `graph.add_edge()` call sites
  exist in `build_pool_graph()`).
- **Pools stay disjoint components** — confirmed directly: `nx.union` with
  disjoint node-id sets (true here) produces disjoint connected components
  unless two pools happen to reference the same ancestor id, which does not
  occur in this corpus (checked: `DEV-PROPAGATION`'s ancestor ids
  `dev-anc-quarantined`/`dev-anc-quarantined-2`/`dev-anc-trusted` are
  local to that one pool, referenced nowhere else). **No cross-pool,
  cross-family edge exists anywhere in this corpus.**
- **Graph topology never depends on poison/benign labels** — edges are
  added purely from pool co-membership and parent/ancestor references,
  never gated on `is_poison_ground_truth`.
- **Can construction indirectly expose the excluded family?** No — traced
  in §2/§3: family X's scenarios and their synthetic ancestor nodes exist
  in the graph if and only if they are present in the `pools` argument;
  filtering at that single point removes them from every downstream
  structure (nodes, edges, adjacency, features) with no separate code path
  that could reintroduce them.

## 7. Family sample-size table

Counts obtained by direct enumeration of `split.all_dev_pools()` and
`split.held_out_pools()` (`python -c` inspection of real `MemoryScenario`
objects, not read from a prior report):

| Family | Training-eligible poison n (`all_dev_pools()`) | Held-out poison n (`held_out_pools()`) | Unique poison-bearing pools (train / held-out) | Power classification |
|---|---|---|---|---|
| `FARMA` | 6 | 7 | 1 / 2 | Interpretable (smallest family that still clears single-digit n on both sides) |
| `MemoryGraft-style-volume` | 6 | 20 | 2 / 2 | Interpretable — largest held-out n by a wide margin |
| `Sleeper` | 1 | 5 | 1 / 2 | **Low-power on the training-exclusion side** (only 1 real example is ever removed from training for this fold — the fold's "excluded family" contributes almost nothing to what the pooled model would have learned about Sleeper specifically in the first place) but held-out n=5 is workable for a detection-rate/AUROC number |
| `propagated` | 2 | 2 | 1 / 1 | **Low-power on both sides** — n=2 held-out is descriptive only; any single-example flip changes the reported rate by 50 percentage points |

Benign counts are shared across all folds (not family-specific):
`all_dev_pools()` benign n=8 real scenarios + 3 synthetic ancestor nodes =
11 (matches `PHASE11_REPORT.md`'s own reported train row exactly — a direct
cross-check against the frozen baseline, not a new number); `held_out_pools()`
benign n=41 real scenarios + 3 synthetic ancestor nodes = 44 (matches
`test_gnn_held_out_split_is_the_real_corpus_size`'s locked-in 78 = 34 + 44
exactly).

**Per this audit's own classification rule (interpretable vs. low-power vs.
descriptive-only), `propagated` is classified low-power/descriptive-only
and `Sleeper` is classified low-power specifically on the
training-exclusion side.** Both are still run (per the task instructions:
"Do NOT discard small families just because they make the results look
unstable"), reported, and their limited statistical weight is carried
through explicitly into every downstream table rather than silently
excluded.

## 8. Aggregation protocol (defined before running the experiment)

**Primary per-family metrics** (computed once per family, per seed, then
summarized): AUROC (via the project's own from-scratch
`phase11.gnn.self_supervised.auroc`, Mann-Whitney U — the same function
`train.py`/`signal_discovery.py` already use, no new metric implementation),
detection rate and FPR at the fold's own in-sample threshold, and n.

**Pooling rule, defined precisely, before results are seen:**

1. **Pooled detection rate (micro-average, the headline pooled number)**:
   `sum(detected_i for every fold) / sum(n_poison_i for every fold)` —
   i.e. total real poison examples detected across all 4 folds, divided by
   total real poison examples evaluated across all 4 folds. This does NOT
   blindly average 4 family rates with equal weight (which would let
   `propagated`'s n=2 count as much as `MemoryGraft-style-volume`'s n=20) —
   it is n-weighted by construction.
2. **Macro FPR (mean of each fold's own FPR on the shared 44-node benign
   reference)**: because every fold trains a DIFFERENT model, the 44 real
   benign held-out nodes get 4 different scores (one per fold's model) —
   pooling all 4×44 benign score instances into one set would silently
   4x-inflate the effective benign sample size for any metric computed on
   the pooled set. This is flagged explicitly as a real methodological
   subtlety of LOFO evaluation with a shared negative class, not glossed
   over: the **macro FPR (simple mean of the 4 folds' own real FPRs, n=44
   each)** is reported as the primary pooled FPR figure specifically
   because it does not manufacture extra effective sample size.
3. **Pooled AUROC, reported with its inflation caveat stated inline**:
   computed by concatenating each fold's (family-X poison scores + that
   SAME fold's 44 benign scores) into one combined score/label list. This
   number is reported for completeness (comparable in kind to a standard
   pooled-out-of-fold AUROC) but is explicitly labeled as counting each of
   the 44 real benign examples 4 times (once under each fold's differently-
   trained model) — not a claim of 176 independent benign observations.
4. **Per-family AUROC/detection/FPR/n**: the primary, most trustworthy
   results table — no pooling ambiguity applies to a single family's own
   numbers.
5. **Macro summary (unweighted mean of the 4 per-family AUROCs)**: reported
   only as a secondary, explicitly-labeled descriptive statistic, per the
   task instruction not to average blindly when n varies this much between
   families (6-to-20-fold difference in held-out n between `propagated` and
   `MemoryGraft-style-volume`).

## 9. Baseline comparisons, defined before running the experiment

- **Baseline A — the original, frozen, pooled-family GNN result**:
  `run_gnn_feasibility_study()`'s own shipped number, **55.9% detection at
  6.8% FPR** (`PHASE11_REPORT.md` §2, `SEED=11`), re-confirmed unchanged by
  this investigation in §Part 11 below (not rerun with different settings —
  the exact existing function, untouched).
- **Baseline B — a real, measured chance reference**: real uniform-random
  scores (not an analytic assumption) drawn for the SAME evaluation
  population each fold actually uses (family-X poison n + 44 shared
  benign), AUROC computed the same way, repeated 100 times per fold to
  report a real distribution rather than a single lucky/unlucky draw.
- **Baseline C — the frozen 9-feature representation, no GNN, no training**:
  a simple, non-learned score (`sum` of the 9 raw sanctioned feature
  values per node, zero fitting, zero graph message-passing) evaluated
  against the exact same per-fold population. This isolates "does
  message-passing/training add anything beyond the raw features
  themselves" — directly relevant to interpreting a LOFO result, since a
  collapse that also occurs in Baseline C would implicate the FEATURES
  (already known to be weak per Option 1's 0.25 raw-centroid AUROC), not
  specifically the GNN's own family-fingerprinting.

No new, stronger baseline is invented in response to a poor GNN result —
these three are fixed here, before any LOFO fold is trained.

## 10. Interpretation criteria (defined before running the experiment)

- **Evidence compatible with cross-family generalization**: a held-out
  family's LOFO AUROC/detection meaningfully exceeds both Baseline B
  (chance) and Baseline C (frozen features, no graph training) — i.e. the
  trained message-passing model itself, having never seen that family, does
  better than either "guessing" or "the raw features alone" at flagging it.
- **Evidence compatible with family fingerprinting**: a held-out family's
  LOFO result collapses toward Baseline B (chance) even though Baseline A
  (the pooled-family model, which DID see that family during training)
  detects it well — the gap between "seen" and "never seen" performance is
  the relevant signal, not the LOFO number in isolation.
- **This experiment cannot, by construction, prove what the network
  internally represents** — only whether its OUTPUT generalizes on this
  specific, real, very small held-out population. A collapse is consistent
  with (but does not uniquely prove) family fingerprinting; it is equally
  consistent with "this family's held-out n is too small to measure
  anything reliably" for `propagated` (n=2) and, to a lesser extent,
  `Sleeper` (train n=1). Both readings are reported side by side wherever
  the data cannot distinguish them, per §7's power classification.

---

# Part 2 — Internal review of this audit before proceeding

1. **Is the proposed LOFO split leakage-safe?** Yes, per §2/§6: the single
   filter point (`ScenarioPool.memories`, before `build_dataset()`) is
   sufficient, because no downstream stage (features, threshold, model
   init) independently re-reads broader corpus data — confirmed by tracing
   every stage, not assumed.
2. **Can the current GNN support fold-local fitting without changing the
   frozen architecture?** Yes — `build_dataset()`, `train_model()`,
   `_threshold_for_target_fpr()`, and `evaluate()` are all already pure
   functions of whatever `pools`/`GraphDataset` they are given; none of
   them needs to change to be called once per fold. `MinimalGNN` itself is
   untouched.
3. **Would any protected corpus need to be modified?** No.
   `held_out_pools()` is read exactly once per fold, unmodified, exactly as
   `run_gnn_feasibility_study()` already does — never filtered, never
   re-labeled. `dev_corpus.py`/`corpus.py` are never edited; filtering
   happens at the `phase11/gnn/lofo.py` call-site level, on tuples returned
   by `split.all_dev_pools()`, not on the source modules themselves.
4. **Does any family have insufficient examples for meaningful evaluation?**
   Yes — `propagated` (held-out n=2) is descriptive-only; `Sleeper`'s
   training-exclusion side is low-power (only 1 example is ever removed).
   Both are run anyway (per instruction) and explicitly labeled, never
   silently dropped.
5. **Is any required data unavailable?** No — every family's poison and the
   shared benign reference already exist in `all_dev_pools()`/
   `held_out_pools()`; no new content needs to be authored or fetched.

**Conclusion: the LOFO experiment can be performed without touching any
protected evaluation data or the frozen GNN architecture. Proceeding to
Part 3 (implementation) in this same pass, per the governing instructions.**
