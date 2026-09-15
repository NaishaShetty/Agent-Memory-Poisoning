# Phase 6 Defense Metrics & Evaluation Protocol — Stage 6.12

Status: 6.12 deliverable. Defines every metric precisely, grounded in what's
actually computable from Phase 6's real evidence substrate, and structurally
prevents the "one collapsed number" failure mode Section 19/35 of the brief
explicitly forbids.

---

## 1. The Intervention Stage Taxonomy — the Load-Bearing Mechanism

`phase6/evaluation/metrics/intervention_stage.py`'s `InterventionStage` enum is
what every other metric in this stage routes through, so "the defense worked"
can never collapse into one ambiguous category:

`PREVENTED_AT_ADMISSION` → `PREVENTED_AT_RETRIEVAL` → `CONTAINED_AT_PROPAGATION`
→ `DETECTED_SLEEPER_PRE_ACTIVATION` → (only if nothing intervened before
exposure) `INFLUENCE_STATUS_UNKNOWN` / `CONFIRMED_NO_INFLUENCE` /
`CONFIRMED_INFLUENCED_UNMITIGATED` / `CONFIRMED_INFLUENCED_THEN_RECOVERED`.

Priority order matches the real lifecycle (earliest intervention wins — an
item blocked at admission never reaches retrieval). The last four states are
governed **strictly by real counterfactual evidence**, never inferred from
exposure alone — enforced identically to Attribution's own "exposed ≠ used ≠
influenced" discipline (`classify_intervention_stage()` never returns a
confirmed-influence state without `counterfactual_influence` being explicitly
`True`, and reports `INFLUENCE_STATUS_UNKNOWN` rather than guessing when no
counterfactual test was ever run).

`DefenseSuccessResult`/`AttackMitigationResult`'s `stage_breakdown` field is
**not optional** — there is no code path in either `defense_success_rate()`
or `attack_mitigation_rate()` that returns a bare rate without it, verified by
a structural test inspecting the dataclass fields directly, not merely by
convention.

## 2. Security Metrics (`security_metrics.py`)

| Metric | Formula | Computable now? |
|---|---|---|
| PAR (Poison Acceptance Rate) | admitted poison / injection attempts | Yes — from real Stage 6.5 admission decisions + evaluator-only injection count |
| PSR (Poison Selection Rate) | selected poison / admitted poison | Yes — from real Stage 6.6 retrieval decisions |
| PIR (Poison Influence Rate) | counterfactual-confirmed-influenced poison / poison evaluated | **No** — requires real Attribution `influence` evidence, unavailable from Stage 6.9's synthetic corpus; needs Stage 6.10's blocked live-campaign environment |
| Propagation Rate | tainted descendants reaching exposure / total tainted descendants | Yes — from Stage 6.7 decisions + real lineage edges |
| SDR (Sleeper Detection Rate) | Sleeper payloads detected / Sleeper attempts | Yes — from Stage 6.5/6.8 decisions |
| AMR (Attack Mitigation Rate) | fraction landing in `NEUTRALIZED_STAGES` | Yes for the stages not requiring counterfactual evidence; the two influence-dependent stages inherit PIR's same limitation |

**Disclosed, not smoothed over**: PIR is the one security metric this stage
cannot compute today. Its function exists, is tested for its arithmetic
correctness, and raises rather than fabricates when given no real evidence —
consistent with Rule 7 (never infer influence merely from retrieval).

## 3. Defense Metrics (`defense_metrics.py`)

**DSR = AMR by construction, disclosed as intentional** (Section 19 of the
brief defines PAR/PSR/PIR/PR/SDR/AMR/DSR together without a formula-level
distinction between AMR and DSR beyond naming) — verified in code
(`test_dsr_matches_amr_by_construction`) rather than inventing an arbitrary
difference to make two same-shaped metrics look different.

**"Neutralized" is defined precisely** as membership in `NEUTRALIZED_STAGES`:
prevented at admission, prevented at retrieval, contained at propagation,
Sleeper detected pre-activation, confirmed no influence despite exposure, or
confirmed influenced then later recovered. This satisfies Section 19's own
explicit requirement not to mix "blocked at admission / blocked at retrieval /
prevented from exposure / prevented from influence / recovered after
influence" into one unexplained category — every DSR/AMR report necessarily
carries the full, ungrouped breakdown alongside the single rate.

**False positives are NOT one number.** `false_positive_rate()` (benign
memories `BLOCK`ed — the strongest, most destructive action) is reported
separately from `benign_quarantine_rate()` (persisted but recoverable),
`benign_downrank_rate()` (query-local, no persisted state), and
`benign_retrieval_suppression_rate()` (an outcome measure — did a benign
memory actually lose top-K access — distinct from the state-based quarantine
rate). Four independent numbers, per Section 19's explicit instruction not to
treat every intervention as equivalent.

## 4. Utility Metrics (`utility_metrics.py`)

**Phase 3's eight existing correctness metrics (Methodology Section 12.13)
are reused verbatim, never reimplemented.** Answerability, semantic
correctness, temporal correctness, and multi-hop correctness are NOT new
Phase 6 metrics — building separate versions would duplicate already-validated
machinery (including the NLI-entailment classifier validated on held-out
data) and risk silent drift from it. `utility_retention_score()` is the one
genuinely new Phase 6 metric: `URS = TSR_defended / TSR_baseline`, computed
identically regardless of which of Phase 3's eight metrics supplies
`TSR_*` — reported honestly even if `URS > 1.0` (not clamped to always look
like a pure cost).

## 5. Cost Metrics (`cost_metrics.py`)

Every non-semantic Phase 6 component (Stage 6.5 admission, Stage 6.6's D1
lexical retrieval, Stage 6.7 propagation, Stage 6.8 Sleeper) has **genuinely
zero** model-call and token overhead — confirmed by direct inspection of their
imports (none imports an LLM client or embedding library). This is a real,
positive, disclosed design property (consistent with the "interpretable
baseline before black-box detector" instruction), not an unmeasured gap.

D2 (semantic retrieval) cites Stage 6.6's own **real measured** numbers
(~11s one-time model load, ~0.017s warm / ~0.31s cold per-pool encode) rather
than re-measuring — avoiding two divergent "real" numbers for the same thing
existing in the project. D3 (LLM-judge) is explicitly marked as
**unimplemented, not zero-cost** — its `model_call_overhead=0` field means "no
component exists to call," never "this component is free," a distinction the
module docstring states explicitly to prevent future misreading.

`total_query_latency_seconds()` returns `None` (never a falsely-complete
low number) if any component's latency in a configuration is unmeasured.

## 6. Security-Utility Pareto Relationship (`pareto.py`)

Per Section 19's own instruction, security and utility are **not** combined
into one weighted score (which would silently bake in an arbitrary tradeoff
preference no evidence justifies). `pareto_frontier()` returns which named
configurations are non-dominated — the frontier itself, not a ranking. Both
axes are higher-is-better by convention; a caller must explicitly transform a
lower-is-better security metric (e.g., PAR, FPR) into its complement before
constructing a point, stated in the docstring so this transformation is never
silently implicit.

## 7. Tests and Evidence

38 new tests (`test_metrics.py`): every intervention-stage transition
(including that admission's earlier lifecycle position overrides retrieval
evidence, and that `later_quarantined` is correctly ignored when no influence
was confirmed), all five security metric formulas plus their input-validation
edge cases, DSR's structural guarantee of always carrying its breakdown and
its verified equivalence to AMR, the four independent benign-rate metrics,
URS in both directions (loss and no-loss) plus its zero-baseline rejection,
the real zero-cost confirmation for four components and the real nonzero cost
for D2, and Pareto frontier correctness (dominated-point exclusion, tied
points both retained, single-point trivial case).

**Full Phase 6 suite: 239 passed, 0 failed.** Frozen `phase3/`, `phase4/`,
`phase5/`, `attribution/` verified unchanged.

## 8. Limitations Carried Forward

1. PIR (and, correspondingly, the two influence-dependent `NEUTRALIZED_STAGES`
   members) cannot be computed until Stage 6.10's environment blocker lifts
   and a real campaign produces genuine counterfactual-influence evidence.
2. Utility metrics require Phase 3's own real generation pipeline (also
   blocked in this environment) — `utility_retention_score()`'s arithmetic is
   tested, but no real `TSR_defended`/`TSR_baseline` pair has been measured
   yet.
3. Most cost figures for non-semantic components are principled estimates
   ("expected sub-millisecond," based on the operations' own nature) rather
   than directly profiled — disclosed as such, not presented as measured.

## Verdict

**PASS** as a 6.12 deliverable. Every metric the brief named is either
implemented and tested now, or explicitly marked as blocked on the same
confirmed environment limitation Stage 6.10 already established — none is
silently stubbed to return a plausible-looking fabricated number.
