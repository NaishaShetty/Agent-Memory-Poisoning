# Phase 11.x — Reliable Learned Detection: Redesign Design Document

**Status: DESIGN ONLY. Nothing in this document has been implemented.**
Per the user's own gating instruction (Section 26 of the brief this responds
to), the five implementation questions below are answered first, by reading
the actual Phase 11 code — not guessed — and no redesign code is written
until the user confirms the objective and reviews this design.

---

## Part 1 — The five implementation questions, answered from the actual code

### Q1. What is the current GNN graph unit?

**Answer: C, with a caveat — one graph per `ScenarioPool` (a "memory pool"),
and `build_pools_graph()` additionally unions several pools' graphs into one
`networkx.Graph` object for a training/eval run, but the pools remain
disjoint connected components inside it — no cross-pool edges are ever
created.**

Evidence: [`phase11/gnn/graph_build.py`](../../phase11/gnn/graph_build.py)
— `build_pool_graph(pool: ScenarioPool)` builds one graph per pool (nodes =
`pool.memories`, edges = `RETRIEVED_WITH` between every pair co-retrieved in
that pool, `DERIVED_FROM` from a memory to its real `parent_ids`/
`ancestors`). `build_pools_graph(pools)` unions multiple pool-graphs via
`nx.union(..., rename=("", ""))` — explicitly documented in that function's
own docstring: "pools stay disjoint components (no cross-pool edges are
invented) since a real RETRIEVED_WITH/DERIVED_FROM edge only ever exists
within one real query's candidate set or one real lineage chain."

So there is no single large lifecycle graph (D) spanning the whole corpus
with real cross-pool structure — what exists is a disjoint-union of small,
independent pool graphs (typically 3–15 nodes each), batched together only
for computational convenience during one training/eval call.

### Q2. What are the actual GNN node features?

**Answer: a 9-dimensional real-valued vector, one scalar per sanctioned
Phase 6/10 risk signal — no learned embedding, no raw text, no MiniLM.**

Evidence: [`phase11/gnn/features.py`](../../phase11/gnn/features.py) —
`FEATURE_KEYS` (sorted, so the exact order is deterministic but alphabetical,
not semantically grouped):

| # | Feature key | Source function |
|---|---|---|
| 1 | `consensus_divergence_score` | `pool_consensus_divergence_signals()` (phase6/defense/retrieval/signals.py) |
| 2 | `decision_log_vocabulary_score` | `admission_signals()` (phase6/defense/admission/reasoning_guard.py) |
| 3 | `dormancy_activation_score` | hardcoded to `1.0` per scenario (single admission event, no retrieval history — see features.py's own comment) |
| 4 | `imperative_write_directive_score` | `imperative_write_directive_signal()` (phase6/defense/sleeper/signals.py) |
| 5 | `lineage_taint_score` | `lineage_taint_signal()`, only if `scenario.ancestors` is non-empty, else `0.0` |
| 6 | `perfection_claim_score` | `admission_signals()` |
| 7 | `provenance_anomaly_score` | `admission_signals()` |
| 8 | `self_reference_score` | `admission_signals()` |
| 9 | `template_anomaly_score` | `admission_signals()` |

Each is a scalar in (effectively) `[0, 1]`. There is no edge-feature vector
at all — `MessagePassingLayer` (`phase11/gnn/model.py`) consumes only a
dense row-normalized mean-adjacency matrix (uniform weight `1/|N(i)|` per
neighbor, no edge-type distinction between `RETRIEVED_WITH` and
`DERIVED_FROM` reaching the model itself — the edge *type* exists in the
`networkx.Graph`, per Q1's evidence, but `node_order_and_adjacency()`
collapses it to a single undifferentiated adjacency list before the model
ever sees it).

### Q3. What exactly are the 34 poison / 44 benign held-out samples?

**Answer: memory-level (node-level) labels, not scenario- or graph-level —
but "44 benign" includes 3 synthetic placeholder nodes that are not
authored `MemoryScenario` objects.**

Evidence: `held_out_pools()` returns `phase6/evaluation/ablations/corpus.py`'s
`all_pools()` — 8 real `ScenarioPool`s, 75 authored `MemoryScenario`s total
(confirmed directly: `34` poison + `41` benign = `75`). Each `MemoryScenario`
becomes exactly one graph node (`build_pool_graph`'s per-memory
`graph.add_node(...)` call) and one row in the GNN's per-node feature/label
tensors (`build_dataset()` in `phase11/gnn/train.py` builds one label per
node: `1.0 if is_poison_ground_truth else 0.0`). So there is no
pooling/aggregation step from memory-level to scenario- or graph-level — the
GNN's classification unit is literally one memory.

The extra 3 nodes: `build_pool_graph()` auto-creates a placeholder node
(`is_poison_ground_truth=False`) for any `parent_id`/`ancestor` referenced by
a `DERIVED_FROM` edge that is not itself already a memory in that pool (line
`if not graph.has_node(parent_id): graph.add_node(parent_id,
is_poison_ground_truth=False)`). `test_gnn_train.py`'s own comment confirms
this exactly: `"78 = 75 scenarios + 3 synthetic ancestor nodes"`. These 3
nodes carry no real content, no real features beyond whatever default the
feature lookup falls back to (`feature_map.get(nid, tuple(0.0 for _ in
FEATURE_KEYS))` in `train.py`'s `build_dataset()` — an all-zero feature
vector), and are hard-coded benign. This is a real, disclosable data-quality
detail: 3 of the reported "44 benign" held-out samples are not scenarios at
all, they are zero-vector graph-structure artifacts. Any redesign's reported
counts should separate these out explicitly rather than silently keep them
folded into "benign."

### Q4. Does the GNN directly consume the 384-dim MiniLM embedding?

**Answer: No.** A repo-wide search of `phase11/` for `MiniLM`,
`sentence_transformers`, `SentenceTransformer`, and `embed` returns zero
matches. The GNN's only semantic-adjacent signal is `consensus_divergence_score`
(from `pool_consensus_divergence_signals()`), which per Phase 6's own
signal contract is a **lexical/set-overlap divergence measure across a
pool's content strings** (or, in the `"semantic"` `retrieval_metric` mode
elsewhere in this project, an embedding-based divergence computed
*upstream* and handed in as a scalar) — not a MiniLM vector reaching the GNN
directly in any node-feature slot. The GNN's node representation is
therefore purely the 9-scalar sanctioned-signal vector in Q2; there is no
384-dim (or any other) dense semantic embedding anywhere in `phase11/gnn/`'s
input pipeline today.

### Q5. What is the exact objective?

The user's brief states a default position in Section 25/26: absent other
instruction, treat **B** — exceed ≈70.6% detection while keeping FPR near
the existing ≈7% level — as the research objective, with the frozen B10
result (≈70.6%/≈7.3%) as the reference point that must not regress.

**This document adopts B as the target objective**, but flags one thing the
user should explicitly confirm before implementation starts: the real,
measured evidence gathered in the prior session (real-data-expansion
investigation, `docs/phase11/PHASE11_REPORT.md` §2.1) shows every real,
tried lever so far trades detection gain for FPR increase, never both at
once. Objective B is therefore the harder of the two framings, and this
design's promotion criterion (Part 2.J below) is written against it
explicitly so "no improvement found" remains an honest, statable outcome —
consistent with the project's own standing rule that "not yet useful" is a
complete, valid finding, not a failure to deliver.

---

## Part 2 — Technical design (A–J)

### A. Data construction

- **Benign-normal corpus** (for learning `μ_B`, `Σ_B` / the benign manifold):
  `phase11/data/real_corpus.py::real_benign_scenarios()` — 135 real LoCoMo
  turns, tasks 1–9 (already built, already disjoint from held-out; see prior
  session). This becomes the PRIMARY training signal, not an auxiliary one —
  a reversal of the current supervised-classifier framing.
- **Benign hard negatives**: NOT YET AVAILABLE from real data at this
  project's scale. The brief's list (high-retrieval-frequency, high-degree,
  many-descendants, contradiction, etc. memories that are still genuinely
  benign) requires either (a) real telemetry this project's static,
  single-pass ablation corpus does not contain (there is no real multi-week
  retrieval log — same constraint `gln/stream.py`'s own docstring already
  discloses for temporal features), or (b) deliberately constructing pools
  with those real *structural* properties from the existing real LoCoMo
  corpus (e.g., select real LoCoMo memories that happen to already have high
  real lexical/consensus divergence scores from `pool_consensus_divergence_signals()`,
  or real memories with many real `DERIVED_FROM` ancestors from
  `parent_ids` chains already present in `dev_corpus.py`'s pools) — real
  content, selected for structural properties, not fabricated content. This
  design proposes (b) only; it does not propose synthesizing any new
  hard-negative content.
- **Poison corpus**: `phase11/data/real_corpus.py::real_poison_scenarios()`
  (15 real forged memories, all 7 attacks) plus `dev_corpus.py`'s original
  hand-authored poison scenarios — used only for dev-time discrimination
  threshold work and attack-family analysis, never for defining "benign," per
  Section 5 of the brief.
- **Split discipline**: unchanged three-way split
  (`train_pools()`/`dev_pools()`/`held_out_pools()`, extended by
  `all_dev_pools()`/`real_corpus.py`), already covered by
  `test_gnn_gln_corpus_is_disjoint.py`. The anomaly estimator's `μ_B`/`Σ_B`
  (or kNN/cosine reference set) must be fit on `train_pools()` +
  `real_benign_scenarios()` only; `dev_pools()` is for choosing which
  estimator (Mahalanobis vs. cosine vs. kNN) and for threshold selection;
  `held_out_pools()` is opened once, at the end, exactly as today.

### B. Feature design

| Feature | Status |
|---|---|
| 9 sanctioned scalar signals (Q2's table) | **Already implemented** |
| `RETRIEVED_WITH` / `DERIVED_FROM` edge typing in the graph object | **Already implemented** (in `networkx.Graph`, but currently discarded before reaching the model — see Q2) |
| Relation-specific message passing (§7 of the brief) | **Newly proposed** — feasible today, since edge types already exist in the graph structure; only the model's adjacency handling needs to change (two adjacency matrices, one per edge type, instead of one undifferentiated one) |
| Temporal features (real retrieval/propagation acceleration, real neighborhood change over real time) | **Not available.** This project's real corpora are single-pass/static; there is no real timestamped multi-event log per memory. `gln/stream.py`'s `STREAM_EVENTS_PER_MEMORY`-step streams are a disclosed, simulated extrapolation of one real signal (`dormancy_activation_score`) over a synthetic step index, not real temporal telemetry. Any "temporal anomaly" component (§8, §11's `A_T`) can only be built on this same simulated axis today — it must be labeled as simulated in every report, exactly as the current GLN section already does, not upgraded to look like real temporal data. |
| 384-dim semantic embedding (MiniLM or otherwise) node feature | **Not available / not currently wired** — confirmed by Q4. Could be added as a genuinely new real feature (MiniLM is already a real, available model per the Methodology Draft's own citation of `sentence-transformers/all-MiniLM-L6-v2` elsewhere in this project), but doing so is a real scope expansion beyond "redesign the anomaly framing" and is called out as optional/Phase-11.x-stretch below, not assumed. |
| Provenance features beyond `provenance_anomaly_score`/`lineage_taint_score` | **Already implemented** (these two scalars); no additional real provenance signal exists in this project's signal contract today. |

### C. GNN architecture

- Keep the existing from-scratch, plain-`torch`, dense-adjacency
  `MessagePassingLayer` shape (no `torch_geometric`/`dgl` — unnecessary at
  this node count, per the existing, already-justified design constraint).
- **Relation-aware extension**: replace the single `mean_adj` matrix with two
  — `mean_adj_retrieved_with` and `mean_adj_derived_from` — and give each its
  own `W_r` (`nn.Linear`), matching §7's simplest defensible formulation
  (`h_i' = W_0 h_i + Σ_r Σ_{j∈N_r(i)} α_{ij}^{(r)} W_r h_j` with
  `α_{ij}^{(r)} = 1/|N_r(i)|`, i.e., relation-specific mean aggregation, no
  attention — attention is not justified at this node/edge count and is not
  proposed).
- Output: instead of one final `nn.Linear(dims[-1], 1)` logit trained against
  a poison/benign label, the readout becomes the representation `h_i` itself
  (dimension = `hidden_dim`), consumed by the anomaly estimator in D. The
  classifier head is *not deleted* — it remains available as one of the
  §19 conventional-comparison arms (GNN output can still be probed with a
  small supervised head for comparison), but it is no longer the primary
  training objective.
- Training objective: self-supervised / benign-reconstruction-style
  objective on `train_pools() + real_benign_scenarios()` (e.g., a benign-vs-
  corrupted-feature contrastive or autoencoding loss over the 9-dim feature
  vectors) rather than binary cross-entropy against poison labels. The exact
  self-supervised loss must be chosen and justified on dev data (candidates:
  feature-reconstruction MSE, or a simple deep-SVDD-style compactness loss
  pulling benign `h_i` toward a learned center) — not frozen here without a
  dev-time comparison.

### D. Anomaly estimator (`h_i → A_i`)

Per §6, three candidates are compared on `dev_pools()`, never on held-out:

1. **Mahalanobis**: `A_i = sqrt((h_i - μ_B)^T Σ_B^{-1} (h_i - μ_B))`, with
   `μ_B`/`Σ_B` estimated from benign `train_pools() + real_benign_scenarios()`
   representations. Caveat that must be checked before trusting this: at
   `hidden_dim=8` and only ~150 real benign training examples, `Σ_B` may be
   ill-conditioned; use a shrinkage estimator (e.g. Ledoit-Wolf, or simple
   diagonal-loading `Σ_B + εI`) rather than a raw sample covariance, and
   report the condition number as a real diagnostic, not hide it.
2. **Cosine distance to benign centroid**: `A_i^cos = 1 - h_i·μ_B / (||h_i|| ||μ_B||)`
   — cheapest, most robust at low `n`, weakest at capturing anisotropic
   benign spread.
3. **kNN distance in benign representation space**: `A_i^kNN = mean_{j∈N_k(i)} d(h_i, h_j)`
   over the real benign training set — most flexible, most sensitive to `k`
   and to the real benign set's coverage (135 real LoCoMo turns is a thin
   reference set for kNN at `k>5`; this must be disclosed if kNN is chosen).

Selection criterion: whichever gives the best dev-set separation
(dev-poison mean anomaly vs. dev-benign mean anomaly, plus dev AUROC) **and**
the most stable dev-FPR across the same seed sweep (11–20) already used in
the prior session's seed-sensitivity investigation — reusing that exact
methodology rather than inventing a new one.

### E. Calibration (`A_i → P_i`)

- Given the real data scale (~150 real benign, ~30 real poison examples
  after §A), **Platt scaling is the honest default**, not isotonic
  regression or Beta calibration — isotonic needs materially more monotonic
  bins than this project's real poison count supports to avoid overfitting
  the calibration curve itself to a handful of points, and Beta calibration
  is explicitly gated in the brief on "data volume and calibration
  diagnostics" justifying it, which this project's real `n` does not meet.
- Fit `a, b` in `σ(a·A + b)` on `dev_pools()` scores only.
- Report reliability diagram, Brier score, and ECE on `dev_pools()` as the
  real, pre-registered calibration diagnostic; held-out is used once, at the
  very end, purely to confirm the calibration was not overfit to dev (a
  real dev-vs-held-out calibration-drift check, not a re-fit).

### F. Residual gate

Do not subtract `A_GNN` and `E(A_rule)` directly — their scales are not
comparable (`A_rule` here is best represented as the existing
`compute_memory_risk_score()` output, itself already a bounded `[0,1]`
GROUPED_GATED composite, whereas `A_GNN` is an unbounded anomaly distance
before calibration). Correct approach:

1. Calibrate both to comparable `[0,1]` probability-like scales:
   `P_GNN = σ(a·A_GNN + b)` (per E), and `P_rule = compute_memory_risk_score(...)`
   (already `[0,1]` by construction, per `phase6/defense/risk/risk_score.py`).
2. Define the residual as an **evidence gate**, not a literal subtraction:
   `R_GNN = P_GNN · (1 − P_rule)` — this rewards the GNN only in proportion
   to how much rule-based evidence is currently *absent* (Case A of §10: low
   rule evidence, high GNN anomaly → `R_GNN` stays large; Case B: rule
   evidence already high → `(1 − P_rule)` shrinks toward 0, correctly
   discounting redundant GNN evidence). This is a deliberately simple,
   auditable multiplicative gate rather than an unjustified subtraction of
   incompatible quantities — it must still be validated on dev data before
   being trusted (in particular, checking it does not degenerate to always-
   near-zero or always-near-`P_GNN` given this project's actual real
   `P_rule` distribution on `dev_pools()`).
3. `R_GNN` feeds the two-threshold decision policy in H, not `P_GNN` alone.

### G. GLN integration

- The GLN is invoked **only** when `R_GNN` (or `A_GNN` pre-gate, whichever
  the dev-time comparison in the ablations of Part 2.I favors) lands in the
  `Uncertain` band (H below) — never on every memory, and never on memories
  already confidently `Normal`.
- What it consumes: the same simulated per-memory event stream
  `gln/stream.py` already builds (`STREAM_EVENTS_PER_MEMORY` steps of the
  9-dim feature vector with `dormancy_activation_score` evolving) — labeled
  explicitly, again, as a simulated extrapolation, not real multi-event
  telemetry, exactly matching the existing disclosed caveat.
- Its output (`GLN risk score`, already real and existing) becomes one more
  input to Phase 6–10's `compute_memory_risk_score()` for `Uncertain`-band
  memories only — via the existing `LEARNED_SIGNAL_KEYS`/`gln_risk_score`
  mechanism already wired in `risk_score.py`, not a new fusion formula.

### H. Decision policy

Three states, thresholds `T_low < T_high` chosen on dev data only (§13/§14):

- **Normal** (`R_GNN < T_low`): no learned-signal contribution; Phase 6–10's
  existing rule-based risk score is authoritative, unchanged from today.
- **Uncertain** (`T_low ≤ R_GNN < T_high`): invoke GLN (G); combine its
  output with Phase 6–10 evidence via the existing `GROUPED_GATED`
  `learned_group` mechanism (already shipped, MIN-based) — do not
  auto-escalate to block on GNN evidence alone.
- **Anomalous** (`R_GNN ≥ T_high`): escalate directly to the existing
  Phase 6–10 decision pipeline as an additional, high-weight signal (still
  through `compute_memory_risk_score()`, never a hard override that bypasses
  it — preserving §Core-Principle's explicit prohibition on "GNN says
  poison → block").

`T_low`/`T_high` are solved via the brief's own §13 formulation
(`min_τ FN(τ) s.t. FPR(τ) ≤ α`) run twice — once for `T_high` at a
conservative `α` (e.g., the existing system's own ~7% reference budget), and
once for `T_low` at a looser `α` (e.g., 2–3×) to bound how much traffic
enters `Uncertain` before it becomes operationally unworkable. Both `α`
values must be fixed and written down *before* touching `held_out_pools()`,
per §13's explicit requirement — this design does not pre-select numeric
`α` values here, since that is itself a dev-time decision the brief
correctly reserves for after real dev-score distributions are seen.

### I. Evaluation protocol

- **Training experiments**: self-supervised benign-representation training
  (C), compared against the existing supervised classifier as a same-data
  ablation arm.
- **Development experiments**: anomaly-estimator choice (D), calibration
  method (E), residual-gate formula validation (F), `T_low`/`T_high`
  selection (H) — all on `dev_pools()` (+ `real_benign_scenarios()`'s own
  held-back dev slice, if one is carved out for this purpose — TBD at
  implementation time, not decided here to avoid a premature, un-validated
  split), never on `held_out_pools()`.
- **Final held-out experiment**: exactly one run of the frozen, dev-selected
  configuration against `held_out_pools()`, reported once.
- **Ablations** (§21): every listed ablation is feasible given what's
  already implemented, EXCEPT "no temporal features" is close to a no-op
  ablation given temporal features are already minimal/simulated — this
  should be reported honestly as "temporal features contribute little
  because they are a simulated single-axis extrapolation, not real
  multi-signal temporal data" rather than a stronger claim.
- **Attack-family / unseen-attack evaluation**: leave-one-attack-family-out,
  reusing `real_corpus.py`'s real per-attack pools — train the anomaly
  estimator with one real attack family entirely excluded from any dev-time
  decision, then check whether it is still flagged as anomalous at
  held-out time. This is the project's most direct real test of §16's
  "behavioral generalization, not attack-name memorization" claim, and
  should be run explicitly, not asserted.
- **False-positive analysis / novel-signal analysis (§22)**: build the
  4-way partition (rule-only, GNN-only, both, neither) directly from
  `held_out_pools()`'s real per-memory outcomes under both B9 (rule-only)
  and the new hybrid, exactly mirroring the existing `run_b10.py` structure
  — this is a natural, low-effort extension of code that already exists.
- **MemoryGraft/paraphrase-volume investigation (§23)**: test whether
  `consensus_divergence_score` (already real, already computed) or a new,
  real, cheaply-computable "duplicate/near-duplicate density in the pool"
  statistic (derivable from the same real content strings
  `pool_consensus_divergence_signals()` already processes, no new data
  needed) separates `POOL-PARAPHRASE`'s real held-out scenarios from benign
  — using the *mechanism* (duplicate-density), never `attack_id`, as the
  brief requires.

### J. Promotion criteria

The redesigned learned detector (any state past "GNN only") is promoted to
become the new Phase 11 shipped default **only if, on the one-time final
held-out run**:

1. Detection rate ≥ 70.6% (does not regress B10's frozen reference), **and**
2. FPR ≤ 7.3% × 1.5 (an explicit, pre-committed tolerance band around the
   existing reference — not "whatever number comes out," and not the
   existing exact 7.3% ceiling, since some real trade-off room is
   reasonable for a genuinely novel-signal system; this multiplier is a
   design choice this document proposes and the user should confirm or
   adjust before implementation, not something to silently pick after
   seeing a result), **and**
3. The §22 novel-detection-gain analysis shows a non-zero
   "detected only by GNN" set on held-out — i.e., the system is
   demonstrably contributing signal Phase 6–10 did not already have, not
   merely reproducing B9/B10's existing 70.6% under a different mechanism.

If (1)–(3) are not simultaneously met, the honest, acceptable outcome (per
the project's own standing discipline) is: **"the redesign clarified why the
GNN is unreliable and what a fix would require, but did not, at this data
scale, produce a promotable detector"** — reported exactly that way, not
reframed as a partial win.

---

## What this document does NOT do

- It does not implement any code.
- It does not touch `held_out_pools()`, `corpus.py`, or the frozen Phase
  6–10 rule-based system.
- It does not fix numeric values for `T_low`, `T_high`, `α`, `k` (kNN), or
  the promotion FPR-tolerance multiplier in J(2) — these are flagged as
  open, dev-time or user decisions, not silently pre-selected.
- It does not propose adding the MiniLM embedding as a GNN feature by
  default — that is noted as a real, available, but separate scope
  expansion (Part 2.B) requiring its own explicit go-ahead, since it changes
  the feature contract (`assert_features_are_sanctioned()`'s current
  restriction to `SANCTIONED_RISK_SIGNAL_KEYS` would need a deliberate,
  disclosed extension, not a quiet one).

**Recommended next step**: confirm (a) objective B as stated, (b) the J(2)
FPR-tolerance multiplier (or supply a different one), and (c) whether the
MiniLM-embedding feature expansion is in scope for this redesign or deferred
to a later Phase-11.x follow-on — then implementation of Part 2 can begin,
starting with A (real_corpus.py extensions for hard negatives) and C
(relation-aware layer), since those are the only two components with no
open numeric parameter blocking a first real, dev-only measurement.

---

## Part 3 — Decisions resolved (2026-09-18), and the real Step 1/2 result

**Objective**: confirmed as B (exceed 70.6% detection, FPR near 7%).

**MiniLM embedding**: deferred, not included this pass. The current
classifier's own hidden layer was found to collapse to 4 unique states over
148 real benign training examples at 8 hidden dims — adding a 384-dim raw
embedding on top (`n≈150 < d=393`) would make covariance-based estimation
rank-deficient by construction. Revisit only if the 9-dim approach shows a
real, working signal first, and then only via a dimensionality-reduced
projection, never the raw vector.

**Promotion FPR-tolerance multiplier**: 2.32× (90% one-sided Wilson upper
bound on the true FPR given the real `k=3, n=41` held-out benign result) —
promotion requires held-out FPR ≤ 17.0%, not an arbitrary margin.

**`α_high`/`α_low`**: fixed as policy inputs at 0.073 / 0.22 (the latter at
the same ~2.3× Wilson-bound order of magnitude), before any dev score was
observed.

**`T_low`/`T_high`**: Part 2.C/2.D (Steps 1–2) were implemented for real —
`phase11/gnn/relation_model.py` (relation-aware encoder, two real edge
types, no attention) and `phase11/gnn/self_supervised.py` (deep-SVDD-style
compactness training and reconstruction-autoencoder training, both strictly
benign-only per Section 5 of the brief). Both were trained on real data
(`train_pools()` + `real_benign_scenarios()`) and evaluated on real,
non-circular dev data (`dev_pools()`, then enlarged with the real, unused
`real_poison_scenarios()` pool to n=28 for more statistical power — still
never touching `held_out_pools()`).

**Real, measured result — the anomaly-distance premise does not hold at
this data scale:**

| Configuration | Dev AUROC (n=28) |
|---|---|
| Raw-feature Euclidean distance to benign centroid | 0.25 (inverted) |
| ...with the `dormancy_activation_score` dimension excluded | 0.50 (chance) |
| Per-dimension standardized ("z-scored") distance | 0.34 |
| Deep-SVDD-trained encoder | 0.18 (seed range 0.07–0.50) |
| Reconstruction-autoencoder-trained encoder | 0.19 (seed range 0.12–0.26) |

Root cause identified, not just observed: `dormancy_activation_score` is
hardcoded to `1.0` for every real poison scenario in this corpus (they are
all constructed as fresh, single admission events — the same value the real
LoCoMo benign reference also takes for the same reason), while several real
dev-pool BENIGN scenarios are deliberately constructed with a different
`prior_retrieval_count` (to test re-assessment cases), giving them a
*different* dormancy value. Because this dimension dominates raw distance
magnitude, it actively inverts the anomaly signal — a construction artifact,
not a security signal. Removing it recovers exactly chance-level separation
(0.50), not an improvement; neither trained encoder beats that raw baseline,
confirming this is not an optimization problem — the 9-dim sanctioned
feature vocabulary itself does not carry a "compact benign region vs.
distant poison region" structure at this project's real scale. Locked in as
a regression test: `phase11/tests/test_relation_aware_anomaly_investigation.py`
(4/4 passing).

**Recommendation:** stop before Steps 3–8 (calibration, residual gate,
decision policy, ablations, held-out run). Building threshold/calibration/
decision machinery on top of a signal shown, across six real configurations,
not to separate the two real populations would not produce a promotable
result — it would only spend more effort arriving at the same real
conclusion by a longer path. Per Section 26 of the brief and this project's
own standing discipline, **"no promotable improvement found" is the honest,
current, real conclusion of this investigation** — not because the redesign
idea itself is unsound in principle, but because this project's real,
available feature vocabulary and real data scale do not support it yet. See
the report update for the two concrete, real options going forward (a
different/expanded feature vocabulary, or accepting this as Phase 11.x's
final finding).
