# Phase 11 Plan — GNN + GLN Learned Components

Status: DRAFT, written before the implementation it governs, per this project's own
standing discipline (see `docs/phase9/PHASE9_PLAN.md`'s and
`docs/phase10/PHASE10_PLAN.md`'s own opening lines). Finalized once the implementation
and its real test scenarios validate against it; any change forced by implementation
reality is reconciled here explicitly, not silently.

## 0. A Direct Tension With This Project's Own Standing Rule, Named Up Front

`docs/phase10/PHASE10_PLAN.md` §6 stated: *"No learned/trained risk model... this
project has no labeled, held-out-appropriate corpus at a scale that would make training
a real model honest rather than overfit theater."* That was correct when written, and
the real data situation has not changed: the reported ablation corpus is 75 hand-authored
scenarios (Section 21.6), the disjoint dev corpus is smaller still, and there are exactly
seven real Phase 4 attacks. Phase 11 does not pretend this constraint has been lifted —
it is undertaken anyway, at the user's explicit direction, on the following terms, stated
before any code is written rather than discovered after training something disappointing:

- **Phase 11 v1 is a feasibility study, not a production defense component.** Its real,
  honest deliverable is an answer to *"can a learned model do anything useful at all on
  the real graph/temporal data this project actually has,"* not a claim that it
  outperforms Phase 6–10's rule-based signals.
- **Every real accuracy number this phase produces will be reported with its real n**,
  the same discipline Phase 6/8's own small-corpus disclosures already use ("a single
  scenario's reclassification can still move a reported percentage by several points" —
  `PHASE6_RESULTS.md` §21.8). A high held-out accuracy on a double-digit real sample is
  not evidence of generalization, and this report will say so plainly rather than let a
  clean-looking number imply more than it supports.
- **If the honest result is "the learned components do not beat the existing rule-based
  baseline at this data scale," that is a fully acceptable, reportable Phase 11 v1
  outcome** — the same "a regression is an acceptable, reportable outcome; only silence
  is not" discipline `docs/phase10/PHASE10_PLAN.md` §10.5 already established, carried
  over unmodified.

## 1. Research Question

*"Can a graph neural network, learning directly from the real memory/lifecycle graph
structure Phase 5–9 already assemble, and a continual (Gated Linear Network) risk
learner, tracking how a memory's real risk evolves as new evidence streams in over time,
each add real, measured detection value beyond Phase 6–10's existing hand-designed
signals and rule-based risk composition — and can the two be combined into one hybrid
estimate without violating any constraint (the Signal Contract, non-circular evaluation,
no evaluator-only leakage) every prior phase's own signals already had to satisfy?"*

## 2. Why This Is Not Already Covered

Every real graph and every real temporal signal Phase 11 would learn from already
exists — as hand-designed features, never as inputs to a learned model:

| Existing capability | Where | What it is, and why it is not a learned component |
|---|---|---|
| The real memory/lifecycle graph itself | `phase5/wiring/trace_assembly.py`'s `PropagationGraph`/`build_propagation_graph()` | Real nodes and real, typed edges (`DERIVED_FROM`, `PROPAGATED_TO`, `RETRIEVED_WITH`, `SELECTED_WITH`, `USED_BY`, ...) — but nothing today learns a representation over it; every consumer (Phase 6's propagation guard, Phase 7's footprints, Phase 9's forensics) reads specific, hand-chosen edges for one hand-designed computation each. |
| Structural graph signals | `phase7/propagation/{footprint,signals,campaign_signals}.py` | `fan_out_rate`, `cycle_reinforcement_depth`, `re_entry_rate`, `cross_task_bleed`, campaign-level aggregation, content-similarity clustering — all real, all correct, all HAND-DESIGNED. A GNN's real value proposition over this is discovering a combination or a structural pattern none of these five specific formulas happens to capture. |
| Backward graph reconstruction | `attribution/wiring/forensics.py`'s `reconstruct_attack_origin()` | Walks real edges with a hand-written, rule-based "worst hop wins" confidence rule — a real precedent for combining graph-derived evidence into one verdict, but never a learned one. |
| Cross-guard risk composition | `phase6/defense/risk/risk_score.py` | Combines real signals with a disclosed, hand-chosen weighting (`GROUPED_GATED`'s per-group 0.25 split) — Section 21.9/Phase 10's own recalibration improved this via a real dev-corpus SWEEP, still never a learned function. |
| Evidence accumulation over time, WITHIN one guard | `consensus_guard.py`'s `MIN_TOTAL_FLAGS_FOR_ESCALATION`/`prior_downrank_count_for()` | A real, but purely count-based, one-directional accumulator — no notion of a continuously-updated, per-memory risk state that could rise OR fall as new real evidence streams in over time. |
| The disclosed, still-open temporal question | `docs/phase10/PHASE10_PLAN.md` §6 | *"Whether a memory's risk should fall after a sustained period of safe, corroborated use is a real, disclosed open question this plan does not pre-answer."* This is, precisely, the problem a continual/online learner (the GLN half of this phase) is architecturally suited to, and no component in this project attempts it today. |

**The real, named gap Phase 11 exists to close**: this project has extensive real graph
structure and extensive real signal history, and has, so far, only ever hand-designed
what to do with either. Phase 11 asks whether a model that LEARNS a graph representation
(GNN) or LEARNS how risk should evolve over a real evidence stream (GLN) can do better
than the next hand-designed formula would — evaluated honestly, on real data, at the
real (small) scale this project actually has.

## 3. Why a GNN and a GLN Specifically, Not a Generic Classifier

- **GNN** — the memory/lifecycle graph (Phase 5's own real structure) is exactly the
  input shape a graph neural network is built for: a poisoned memory's risk plausibly
  depends on its real neighbors' states (an admission-flagged parent, a co-selected
  sibling, a campaign-clustered peer — Phase 7's own hand-designed signals already probe
  exactly this kind of neighborhood relationship). A GNN's real proposition is learning
  which neighborhood patterns matter, and how to weight them, instead of five
  independently hand-tuned formulas.
- **GLN** (Gated Linear Network — Veness et al., real, published continual-learning
  architecture, gated per-neuron online updates, no catastrophic forgetting by
  construction) — chosen specifically over a generic recurrent/streaming model because
  its real, documented strength is exactly this project's real shape of problem: a small
  number of real examples arriving in a genuine streaming order (each retrieval, each
  guard flag, each Phase 9 reconstruction is one more real data point about a memory,
  arriving over time, never available in advance) — a batch-trained GNN is a poor fit for
  "how does this specific memory's own risk change as of *this* new event," and the GLN
  is architecturally built for exactly that regime.
- **Not, in v1, one combined end-to-end learned model.** The plan's own title says
  "hybrid system," but §6 explicitly defers END-TO-END joint training — v1 builds each
  component separately, evaluates each separately against the existing rule-based
  baseline, and only THEN asks whether combining their two real outputs (not their
  internals) helps, mirroring Phase 10's own "combine already-computed signals" framing
  rather than inventing a new joint-training pipeline this project's real data could not
  honestly support.

## 4. What Phase 11 Adds

### 11.1 — A real, disclosed, non-circular train/dev/held-out split

Before any model is written: extend the exact separation discipline
`dev_corpus.py`/`corpus.py` already established (Section 21.9's own precedent) to
graph-shaped and temporal-shaped data. Real graphs are built from the SAME real
ledger-building helpers Phase 5/7/9's own tests already use
(`phase7.propagation.attack_study.new_study_ledgers()`, the real frozen Phase 4
injectors) over GENUINELY DIFFERENT real content per split — training/dev graphs use
`dev_corpus.py`-shaped or newly-added disjoint content; the held-out evaluation graphs
are the SAME reported corpus (`corpus.py`) Section 21.9/Phase 10 already report numbers
against, touched only once, at the end, exactly as every prior phase's own non-circular
discipline requires. A new `test_gnn_gln_corpus_is_disjoint.py`-style standing check
(the same pattern `test_calibration_corpus_disjoint.py` already established) enforces
this is never silently violated.

### 11.2 — The GNN: a real, minimal architecture, not a black box adopted on faith

A small (1–2 message-passing layer), disclosed graph neural network — built on `torch`
and `networkx` (both already present in this project's environment; no new heavy
dependency such as `torch_geometric`/`dgl` is added without first checking whether a
minimal, from-scratch message-passing implementation suffices, per this project's own
"establish interpretable baselines before a black-box detector" discipline, `reasoning_guard.py`'s
own module docstring). Node features are drawn EXCLUSIVELY from the Signal Contract's
sanctioned vocabulary (the same `SANCTIONED_RISK_SIGNAL_KEYS` Phase 10 already defines,
extended only if a new feature is itself a real, already-legitimate Phase 5 event field,
never an evaluator-only one) — a static analysis check, mirroring every existing
`FORBIDDEN_SIGNAL_KEYS` guard, confirms this before any training run. Task: real
node-level binary classification (is this real memory poisoned), evaluated the same
detection-rate-at-controlled-FPR way every other Phase 6–10 component already is, so the
result is directly, honestly comparable to B8/B9's own real numbers — not a new,
incomparable metric invented to flatter the model.

### 11.3 — The GLN: a real, from-scratch continual risk learner

A real, disclosed Gated Linear Network implementation (validated first against a small,
constructed, non-project toy sequence with a known right answer — the same "validate the
regex against constructed true/false positives before real use" discipline Stage 6.8
already established for `imperative_write_directive_signal()` — before ever being
trusted on real project data), consuming a real, ordered STREAM of per-memory evidence
events (each real retrieval, each real guard flag, each real Phase 9 reconstruction
touching that memory) and producing an updated risk estimate after each one. Directly
answers Phase 10's own named open question (§6: does risk ever fall after sustained safe
use) with a real, measured answer instead of leaving it open by default.

### 11.4 — Hybrid combination, only after each half is independently evaluated

Once 11.2's real GNN output and 11.3's real GLN output each have their own real,
independently-measured detection/FPR numbers (never combined before being measured
separately — the same discipline that made Phase 10's own GROUPED_GATED-vs-WEIGHTED_SUM
comparison meaningful), a real, disclosed combination (starting from the simplest
honest option — e.g. treating each learned output as one more sanctioned signal key fed
into Phase 10's own existing `compute_memory_risk_score()`, rather than inventing a new,
separate combination mechanism) is tried and measured the same non-circular way.

### 11.5 — Real validation against the existing corpus, honest about scale

Extend `run_b0_b7.py`'s own real driver with a new configuration (tentatively B10) that
substitutes or augments the existing rule-based signals with the trained GNN/GLN/hybrid
outputs, measured on the SAME held-out reported corpus B0–B9 already report real numbers
against. Whatever the real result — an improvement, a regression, or noise
indistinguishable from B9 at this sample size — is reported with its own real confidence
caveat (this corpus's real n is far below what would let a held-out accuracy difference
of a few points mean anything), the same honesty Phase 10's own B9 regression-then-recalibration
report already modeled.

## 5. Inherited Constraints (frozen, carried over unchanged)

- **The Signal Contract applies to every learned component's input features, without
  exception.** A GNN/GLN is not exempt from `FORBIDDEN_SIGNAL_KEYS`/`SANCTIONED_RISK_SIGNAL_KEYS`
  just because it is "learning," and a static check must confirm this before any real
  training run, the same discipline every hand-designed signal function already carries.
- **No modification to any frozen Phase 3/4/5 file, or to Attribution's/Phase 7's/Phase
  9's/Phase 10's own core wiring.** Phase 11 is additive over already-shipped signal
  functions, graph-assembly functions, and result types, the same relationship every
  prior phase held to the ones before it.
- **Non-circular evaluation, extended to graphs and temporal streams, not just static
  corpora.** §4.1's train/dev/held-out separation is Phase 11's own version of Section
  21.9's already-established anti-circularity discipline — never trained or tuned
  against the same real data its final number is reported against.
- **Determinism, wherever real determinism is achievable.** Model weights, once trained,
  and inference over identical real inputs, must be deterministic and reproducible (a
  fixed real random seed, disclosed, not hidden) — training itself may be stochastic, but
  a specific trained artifact's real evaluation run must not be.
- **No fabricated confidence.** Exactly Phase 10 plan §6's own rule, carried over
  unmodified: no bare accuracy/precision number is reported without its real n stated
  alongside it, and no learned-component output may alone justify a BLOCK-equivalent
  action without real, disclosed corroboration, the same "indirect/single-source
  evidence caps below BLOCK" discipline every guard and Phase 10's `RiskEstimate` already
  share.
- **Ground truth only from the caller, never invented by this phase.** Every real
  training/evaluation label is the SAME `is_poison_ground_truth`/`attack_family_ground_truth`
  vocabulary already used throughout Phase 6–10's own evaluator-only harnesses — Phase 11
  adds no new ground-truth category and fabricates no additional labeled examples beyond
  what those harnesses already, honestly, contain.

## 6. Explicit Out-of-Scope for Phase 11 v1

- **No claim that the learned components are production-ready, or that they beat the
  rule-based baseline**, unless real, disclosed evidence at this project's real (small)
  data scale actually supports that claim — see §0's terms, which govern this entire
  phase.
- **No new heavy ML dependency** (`torch_geometric`, `dgl`, `jax`) is added by default —
  `torch`/`networkx`/`numpy`/`scikit-learn` (already present) are the starting toolset;
  adding anything heavier requires a real, disclosed justification that a minimal,
  from-scratch implementation genuinely cannot do the job, decided during 11.2/11.3, not
  assumed here.
- **No end-to-end joint training of the GNN and GLN together.** §3's own reasoning
  applies: v1 evaluates each component independently before ever combining their
  OUTPUTS, never their internals.
- **No live wiring into any real defense/decision pipeline.** Exactly the same
  "defined but not live-wired" deferral Phase 10 already used for `REQUIRE_VALIDATION`
  and Phase 3's Verify/Revise modules — a trained model directing a real, live QUARANTINE/BLOCK
  decision is a materially larger, separately-scoped change than this plan covers.
- **No synthetic data generation beyond what this project's own existing corpora already
  provide.** If the real, existing corpora prove too small to train anything meaningful
  (a real, acceptable possible outcome per §0), the honest response is reporting that
  finding, not inflating the training set with fabricated examples to manufacture a
  trainable-looking dataset.
- **No new, incomparable evaluation metric.** Every real number this phase reports is
  measured the same detection-rate-at-controlled-FPR way every existing Phase 6–10
  component already is, so it can sit next to B0–B9's own real numbers honestly.

## 7. Proposed Stage Breakdown

| Stage | Deliverable |
|---|---|
| 11.1 | The train/dev/held-out graph and temporal-stream data split, with its own standing disjointness regression test |
| 11.2 | The real, minimal GNN — architecture decision (from-scratch vs. a new dependency), Signal-Contract-compliant feature extraction, real node-classification training and evaluation against the held-out corpus |
| 11.3 | The real, from-scratch GLN — validated first against a constructed toy sequence, then run over real per-memory event streams; a real, measured answer to Phase 10's own open "does risk decay" question |
| 11.4 | The hybrid hook — feeding each learned component's real output into Phase 10's existing `compute_memory_risk_score()` as new sanctioned signal keys, measured the same way GROUPED_GATED vs. WEIGHTED_SUM already was |
| 11.5 | The real B10 ablation configuration and its real, measured comparison against B8/B9, reported with its own explicit small-sample caveat |
| 11.6 | `PHASE11_REPORT.md`, written after all real numbers exist, per this project's own "never write the conclusion first" discipline, and explicitly required to state whether Phase 11 v1's honest conclusion is "useful," "not yet useful at this data scale," or "inconclusive at this sample size" — any of the three being an acceptable, real finding |

## 8. Acceptance Criteria for 11.1–11.2

- The train/dev/held-out split shares no real content or scenario id across any two of
  its three parts, verified by a real, standing test analogous to
  `test_calibration_corpus_disjoint.py`.
- Every GNN input feature is drawn from `SANCTIONED_RISK_SIGNAL_KEYS` or an explicitly
  justified, equally-real extension of it — verified by a static check that raises on any
  other field, the same discipline `compute_memory_risk_score()`'s own
  `UnsanctionedRiskSignalError` already established.
- The trained GNN's real held-out detection/FPR numbers are reported next to B8/B9's own
  real numbers on the SAME corpus, with the real held-out sample size stated in the same
  sentence as any percentage derived from it.
- A single-signal-only `RiskEstimate` contribution from either learned component still
  cannot alone justify a BLOCK-equivalent band, verified directly, not merely asserted.

## 9. Verdict

Not yet applicable — this document is the plan, written before Stage 11.1 begins. Per
this project's own standing discipline, no verdict, PASS/FAIL claim, or real number is
written here, and — per §0's terms, stated up front rather than discovered later — the
verdict that eventually belongs in `PHASE11_REPORT.md` may honestly be "the learned
components do not yet add real value at this project's real data scale," which would be
a complete, valid, non-negative outcome for this plan's own research question, not a
failure of the phase to answer it.
