# Phase 10 Plan — Adaptive Risk-Based Hardening

Status: DRAFT, written before the implementation it governs, per this project's own
standing discipline (see `attribution/ATTRIBUTION_METHODOLOGY.md`'s and
`docs/phase9/PHASE9_PLAN.md`'s own opening lines). Finalized once the implementation and
its real test scenarios validate against it; any change forced by implementation reality
is reconciled here explicitly, not silently.

## 1. Research Question

*"Instead of every memory-lifecycle decision collapsing to a single discrete action
chosen by whichever one guard fired loudest, can a memory's real, already-computed
signals across ALL of Phase 6's guards, Phase 7's propagation monitor, Phase 8's sleeper
signals, and Phase 9's forensic reconstructions be combined into one continuous,
disclosed risk estimate — and can that estimate drive a genuinely graduated response
(retrieval ranking, monitoring priority, a verification step, or quarantine) that
increases real detection without increasing real false positives beyond what Phase 6's
own already-measured trade-off curve would predict?"*

This is a **decision-composition** question, not a new-signal question. Phase 10 invents
no new way to detect poisoning; it asks whether the detection signals this project
already has, built across five phases, are being combined as well as they could be.

## 2. Why This Is Not Already Covered

Every real signal Phase 10 would consume already exists and is already tested. What does
**not** exist is a layer that combines them into one estimate before deciding what to do:

| Existing capability | Where | What it is, and its real limit |
|---|---|---|
| Four independent guards, each thresholding its OWN signal into a discrete action | `phase6/defense/{admission,retrieval,propagation,sleeper}/*.py` | Each guard sees only its own signal. The admission guard never knows the retrieval guard flagged the same memory last week; the sleeper guard never knows Phase 7 found it in a crowded campaign. |
| `combined_action()` | `phase6/defense/orchestration/pipeline.py` | Takes the MAX-severity action among enabled guards' outputs — but explicitly **"Used ONLY for ablation reporting"** (its own docstring), discards every real signal SCORE the moment each guard discretizes it, and is never called from any live decision path. |
| Evidence accumulation over time, within ONE guard | `consensus_guard.py`'s `MIN_TOTAL_FLAGS_FOR_ESCALATION` / `prior_downrank_count_for()` | Real precedent for "don't escalate on the first flag alone" — but scoped to the retrieval guard's own repeated flags only; a QUARANTINE-worthy pattern split across the admission guard once and the propagation guard once is invisible to it. |
| Campaign-level and content-similarity aggregation | `phase7/propagation/campaign_signals.py` | Real, but read-only and reported, never fed back into any guard's own decision. |
| Four dormancy/activation signals, combined multiplicatively | `phase6/defense/sleeper/sleeper_guard.py` | The one place in this project two real signals ARE genuinely composed into one score before thresholding — the existing, closest real precedent for what Phase 10 generalizes, and also the place Phase 8/6.9 proved that a naive product can create a false-positive collision (Section 21.9's age-gate fix) — a real, disclosed cautionary case Phase 10 must not repeat blindly. |
| `chain_confidence` | `attribution/wiring/forensics.py` | A real, already-built "combine several hop verdicts into one verdict" mechanism — but its rule ("worst hop wins") produces a four-value CLASSIFICATION for a completed forensic walk, after the fact, never a live, continuous, PRE-decision risk estimate a guard could act on in real time. |
| The B0–B8 detection/FPR trade-off curve | `phase6/evaluation/ablations/`, `docs/phase6/PHASE6_RESULTS.md` | The real, measured empirical ceiling any new combination must be judged against — combining signals differently is worthless if it cannot be shown, on the same real corpus, to move a point on this curve rather than just relabel it. |

**The real, named gap Phase 10 exists to close**: every guard, every signal, and every
aggregation this project has built computes something real — but nothing before a guard's
own threshold check ever asks "what do ALL of this memory's real signals, across every
guard and every phase, say together, right now" and nothing after a decision ever routes
a memory to anything other than the same four hard-coded, per-guard actions. A "risk
score" in the sense this phase means is not a new detector; it is the missing arithmetic
between detectors already built.

## 3. The Named, Already-Disclosed Gaps This Phase Targets

1. **Guards are blind to each other's real, current signal values.** The retrieval guard
   cannot see that the admission guard's reasoning-guard score for the same memory was
   0.4 (not enough to admission-flag alone, but real, nonzero evidence); nothing combines
   the two before either one decides.
2. **`combined_action()`'s max-severity rule discards graded evidence.** Two guards each
   independently landing at a middling, sub-threshold score currently combine to
   "whichever one's discrete action is more severe" (often `ALLOW`, since neither alone
   crossed its own bar) — never to "two real, moderate, independent signals agreeing is
   itself evidence," the same kind of corroboration Phase 6's own admission guard
   (Stage 6.5, five weighted signals) already uses INTERNALLY within one guard, but never
   ACROSS guards.
3. **The action vocabulary has no verification tier.** `ALLOW` / `ALLOW_WITH_RESTRICTION`
   / `DOWNRANK` / `QUARANTINE` / `BLOCK` / `RELEASE` covers admit-or-not and
   trust-or-not, but nothing routes a memory of GENUINELY AMBIGUOUS risk to an extra,
   bounded check before it is either fully trusted or persistently flagged — the user's
   own framing names this explicitly ("verification" as a distinct lever from
   "retrieval," "monitoring," or "quarantine").
4. **Monitoring priority is not risk-weighted.** Phase 7's campaign signals and Phase 9's
   forensic reconstructions are real and correct, but nothing currently uses a memory's
   own risk estimate to decide it deserves a Phase 9 reconstruction sooner, or a tighter
   Phase 7 campaign-aggregation watch, than an unrelated low-risk memory — investigation
   priority today is entirely a human, out-of-band judgment call (by design, per Phase 9's
   own §6 "no automated when-to-investigate policy" boundary, which Phase 10 does not
   remove, only feeds with a better real number).

## 4. What Phase 10 Adds

### 10.1 — A real, disclosed, rule-based (never learned) risk-composition function

A new, pure function — tentatively `phase6/defense/risk/risk_score.py`'s
`compute_memory_risk_score(signals, weights) -> RiskEstimate` — that takes the REAL,
ALREADY-COMPUTED signal dict every guard already produces (`imperative_write_directive_score`,
`consensus_divergence_score`, `lineage_taint_score`, `dormancy_activation_score`, the
Phase 8 signals, etc. — never a new signal invented for this stage) and combines them
into one `RiskEstimate`:

```
RiskEstimate:
    memory_id: str
    risk_score: float          # [0, 1], a disclosed, versioned WEIGHTED function — never a
                                # learned/trained model (see §6 — no calibration data exists
                                # to train one honestly, and an untrained score would violate
                                # this project's own "never fabricate a number" discipline)
    contributing_signals: Mapping[str, float]   # every real signal that fed the score, for audit
    risk_band: str              # LOW / MODERATE / ELEVATED / HIGH — a closed, disclosed
                                 # vocabulary (never silently re-derived from risk_score
                                 # inline at each call site), calibrated the same
                                 # dev-corpus-only, non-circular way Section 21.9 recalibrated
                                 # THRESHOLD_DOWNRANK
    rationale: Tuple[str, ...]  # which signals drove the score, mirroring every existing
                                 # guard's own `reason` string discipline
```

The composition rule itself (weighted sum vs. the sleeper guard's own multiplicative-gate
precedent vs. something else) is **not pre-decided here** — Stage 10.1's own job is to
try candidates against the disjoint dev corpus (`phase6/evaluation/ablations/dev_corpus.py`,
extended if needed with Phase 7/8/9 fixture-shaped cases) and report which one, if any,
real evidence supports, mirroring Section 21.9's own"never tune on the held-out corpus"
discipline exactly. If no combination rule beats the current per-guard max-severity
baseline on real, non-circular evidence, that negative result is reported as Phase 10's
own finding, not hidden by shipping a combination rule anyway.

### 10.2 — A verification tier in the action vocabulary

A new action, tentatively `NEEDS_VERIFICATION`, added to `phase6/defense/policy/states.py`'s
existing, already-once-extended action vocabulary (the brief's own six actions already grew
to seven when `RELEASE` was found necessary — Phase 10's `NEEDS_VERIFICATION` follows the
same precedent: a disclosed, evidenced addition, not invented speculatively). A memory in
the `MODERATE`/`ELEVATED` risk band routes here instead of `ALLOW` or `QUARANTINE` — genuine
middle ground the current all-or-nothing action set cannot express. **Scope, disclosed up
front**: Phase 10 v1 defines the state-machine transition and the decision surface only; it
does NOT wire `NEEDS_VERIFICATION` into Phase 3's real `Verify`/`Revise` generation-time
modules (that would be a live integration touching a frozen phase's own generation
pipeline, a materially larger and separately-scoped change) — the real wiring is named
explicitly as a follow-on item, the same "Stage 6.10 live-ledger wiring" pattern this
project already uses elsewhere for a deliberately-deferred integration, never silently
implied to already work end to end.

### 10.3 — Risk-weighted retrieval ranking, generalizing the existing binary downrank

`consensus_guard.py`'s `MAX_DOWNRANK_PENALTY` currently applies a fixed-shape penalty
once a candidate crosses `THRESHOLD_DOWNRANK`. Stage 10.3 asks whether a `RiskEstimate`
(10.1) can replace that single threshold-crossing check with a real, continuously-scaled
penalty (proportional to `risk_score`, not just "did it cross the line") — evaluated
against the SAME real corpus and the SAME false-positive accounting discipline Section
21.9 already established, never assumed better without a real, measured comparison.

### 10.4 — Risk-weighted monitoring priority (Phase 7/9 feed-forward, not new policy)

`RiskEstimate.risk_band` becomes an optional, additional real input `forensic_targets_from_campaign_signal()`
(Phase 9) and `campaign_content_similarity_clusters()` (Phase 7) callers MAY use to order
an already-existing, human-chosen investigation queue — Phase 10 does not build a new
"decide what to investigate" policy (Phase 9's own explicit non-goal, inherited
unmodified), it only gives an existing human decision a real number to sort by, if the
caller chooses to use it.

### 10.5 — Real, multi-attack validation against the existing B0–B8 corpus

Every claim in 10.1–10.3 is measured, not argued: re-run the real B0–B8-style ablation
(`phase6/evaluation/ablations/run_b0_b7.py`'s own real driver, extended with a new B9
"risk-composed" configuration) on the SAME 75-scenario corpus Section 21.9 already
reports 70.6%/7.3% for, and report the real, resulting detection/FPR pair for the
risk-composed configuration next to it — a genuine improvement, a genuine regression, or
no significant change are all acceptable, reportable outcomes; only silence about the
result is not.

## 5. Inherited Constraints (frozen, carried over unchanged)

- **The Signal Contract still applies in full.** Every signal `compute_memory_risk_score()`
  consumes must already be a real, sanctioned signal per `docs/phase6/DEFENSE_SIGNAL_CONTRACT.md`
  — Phase 10 introduces no new signal category, no new evaluator-only field, and is
  verified by the same static-import/`FORBIDDEN_SIGNAL_KEYS` checks every existing signal
  function already carries.
- **No `BLOCK` from a single uncorroborated signal.** The "indirect/single-source evidence
  caps below BLOCK" discipline (Stage 6.5/6.7/6.8's own shared precedent) applies to
  `compute_memory_risk_score()`'s output exactly as it does to every existing guard: a
  `RiskEstimate` built from only one real contributing signal cannot alone justify a
  `BLOCK`-equivalent risk band, regardless of that one signal's own magnitude.
- **No modification to any frozen Phase 3/4/5 file, or to Attribution's/Phase 9's own
  core wiring.** Phase 10 is additive over Phase 6/7/8/9's already-shipped signal
  functions and result types, the same relationship Phase 9 held to Attribution.
- **Determinism.** `compute_memory_risk_score()` is a pure function of its real signal
  inputs — identical inputs produce a byte-identical `RiskEstimate`, verified the same way
  every other deterministic component in this project already is.
- **Calibration only against disjoint development data.** Any weight, threshold, or band
  boundary Phase 10 introduces is calibrated exclusively against `dev_corpus.py`-shaped
  data, never the reported B0–B8 corpus — Section 21.9's own disclosed near-miss with
  calibration circularity is the explicit cautionary precedent this stage must not repeat.
- **Ground truth only from the caller.** Any accuracy or improvement claim is measured
  against real, caller-supplied ground truth (the same `is_poison_ground_truth` /
  `attack_family_ground_truth` fields the existing ablation corpus already carries),
  never assumed.

## 6. Explicit Out-of-Scope for Phase 10 v1

- **No learned/trained risk model.** A weighted or rule-based combination is the only
  form `compute_memory_risk_score()` may take in v1. This project has no labeled,
  held-out-appropriate corpus at a scale that would make training a real model honest
  rather than overfit theater — the same reasoning that kept Phase 6's own thresholds as
  disclosed, versioned constants rather than fitted parameters.
- **No live wiring of `NEEDS_VERIFICATION` into Phase 3's real Verify/Revise modules.**
  Named explicitly in §4.2 as a follow-on, not attempted here.
- **No new "when to investigate" automation for Phase 7/9.** §4.4 only supplies an
  optional sort key to an existing human decision; it does not decide anything on its own.
- **No time-based risk DECAY.** Whether a memory's risk should fall after a sustained
  period of safe, corroborated use is a real, disclosed open question this plan does not
  pre-answer — `MIN_TOTAL_FLAGS_FOR_ESCALATION`'s own existing precedent only ever
  accumulates evidence upward, never down, and Phase 10 v1 inherits that same one-directional
  shape rather than inventing an undecayed/decayed choice without real evidence either way.
- **No cross-run or cross-deployment risk persistence.** `RiskEstimate` is computed fresh
  per real, single-run evaluation, the same boundary every other Phase 6/7/8/9 component
  already carries.

## 7. Proposed Stage Breakdown

| Stage | Deliverable |
|---|---|
| 10.1 | `RiskEstimate` schema + `compute_memory_risk_score()`, with at least two real candidate composition rules (e.g. weighted-sum vs. sleeper-guard-style multiplicative-with-gate) tried against the disjoint dev corpus; unit tests for the Signal-Contract/no-single-signal-BLOCK invariants |
| 10.2 | `NEEDS_VERIFICATION` action + state-machine transition additions in `phase6/defense/policy/states.py`, with the same illegal-transition-raises discipline every existing action already has; explicitly NOT wired into Phase 3 |
| 10.3 | Risk-weighted retrieval-ranking variant of `consensus_guard.py`'s penalty function, A/B-measured against the existing fixed-threshold penalty on the same real corpus |
| 10.4 | Optional `risk_band`/`risk_score` sort-key parameters added to the existing Phase 9 `forensic_targets_from_*` resolution functions — thin, opt-in, no new policy |
| 10.5 | The real B9 "risk-composed" ablation configuration and its real, measured detection/FPR comparison against B8's 70.6%/7.3%, reported honestly regardless of direction |
| 10.6 | `PHASE10_REPORT.md`, written after all real numbers exist, per this project's own "never write the conclusion first" discipline |

## 8. Acceptance Criteria for 10.1

- `compute_memory_risk_score()` raises on any input signal key not present in the Signal
  Contract's sanctioned vocabulary — verified by a real test supplying a forbidden key.
- A `RiskEstimate` built from exactly one nonzero contributing signal never produces a
  risk band whose real, current mapping would justify `BLOCK` — verified directly, not
  merely asserted in a docstring.
- Calling `compute_memory_risk_score()` twice with identical inputs produces a
  byte-identical `RiskEstimate` (determinism).
- At least one real, dev-corpus-measured comparison exists between the chosen composition
  rule and the existing `combined_action()` max-severity baseline, with the real numbers
  reported either way.

## 9. Verdict

Not yet applicable — this document is the plan, written before Stage 10.1 begins. Per
this project's own standing discipline, no verdict, PASS/FAIL claim, or real number is
written here; `PHASE10_REPORT.md` (§7, Stage 10.6) is where that verdict belongs, after
the real implementation and real B9 comparison exist to support it.
