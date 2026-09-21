# Phase 12 Report — Systematic Evaluation: Security Metrics

Status: implementation complete for this pass's confirmed scope (PAR, SDR, AMR, DGS; PR defined but
explicitly not computed — see Section 4). Every number below was produced by real code
(`phase12/security_metrics.py`, `phase12/dgs.py`, `phase12/evaluation_matrix.py`), run for real against
real, unmodified Phase 4/6/11 infrastructure — none are hand-typed estimates. No file under
phase4/-phase11/ was modified — verified directly via `git status` (only `phase12/` and `docs/phase12/`
are new; `phase6/defense/risk/risk_score.py`, `phase6/evaluation/ablations/run_b0_b7.py`, and
`phase6/tests/test_run_b9_risk_composed.py` were already modified before this phase began, by an
unrelated, in-progress Phase 11 follow-on — untouched by this work).

## 0. Reconciliation

- **Scope confirmed with the user before implementation** (this document's own plan, Section 8): metric
  definitions accepted as written; workload axis dropped for this pass; new-dataset sample size matches
  `clean_expansion.py`'s existing `CONTROLLED_POOLS_PER_DATASET = 10`; a new, separate evaluation corpus
  was authorized (not `held_out_pools()` alone), with the guardrail that it never touches or modifies the
  existing reported corpus.
- **The plan's "722-test baseline" claim does not match current reality.** A full `pytest --collect-only`
  found 3163 tests across the repo, not 722. This is flagged, not silently corrected — Phase 12 extends
  the real, current suite (+22 tests, `phase12/tests/`), and does not rely on the stale number for anything.
- **PR (Propagation Rate) is defined but not computed this pass** — a real, disclosed scope narrowing
  made during implementation, not part of the original plan text. See Section 4.

## 1. What Was Built

| Module | What it does |
|---|---|
| [phase12/eval_corpus.py](../../phase12/eval_corpus.py) | New, separate real evaluation corpus: real LoCoMo turns + real records from 3 previously-unused unified-memory datasets (LongMemEval, MSC, Conversation Chronicles), each paired with the same real 15-scenario, 7-attack-family poison pool (`phase11.data.real_corpus.real_poison_scenarios()`). Guardrail-tested disjoint from `held_out_pools()`. |
| [phase12/security_metrics.py](../../phase12/security_metrics.py) | PAR (real, computed), PR (defined, not computed — disclosed), SDR (real, computed), AMR (real, computed). |
| [phase12/dgs.py](../../phase12/dgs.py) | Defense Generalization Score for B0–B8: real detection/FPR on the tuned (`corpus.py`) corpus vs. the new Phase 12 corpus. |
| [phase12/evaluation_matrix.py](../../phase12/evaluation_matrix.py) | The dataset × defense-configuration sweep (workload axis dropped, confirmed). Attack-family axis comes free from `compute_metrics()`'s existing `per_attack_family_detection`. |
| [phase12/tests/](../../phase12/tests/) | 22 new tests, all passing against real computed output (not mocked). |

## 2. Real Numbers

### 2.1 PAR — Poison Admission Rate

**100.0% (15/15)** real injection attempts admitted, across all 7 real attack families (dsrm, farma,
mpbench, minja, agentpoison, memorygraft, sleeper_memory_poisoning) — every family individually at 100%.
Every real seed/scenario object each attack ships was attempted once (DSRM/FARMA/MPBench/MINJA: 3 each;
AgentPoison/MemoryGraft/Sleeper: 1 each = 15 total), with no filtering on outcome.

### 2.2 PR — Propagation Rate

Not computed this pass. See Section 4.

### 2.3 SDR — Sleeper Detection Rate

**0.0%** for every (dataset, configuration) cell across all 9 rule-based configurations (B0–B8) and all
4 datasets (36 cells total) — including B8, the full four-layer stack. This tracks the pooled result
(Section 2.4): the Sleeper family is not a special case here, it fails for the same reason every other
family fails on this corpus.

### 2.4 AMR — Attack Mitigation Rate

**Undefined (`None`) for every configuration** — no configuration ever issued a QUARANTINE or BLOCK
action against any real poison scenario in this corpus (n_hard_mitigation_actions = 0 throughout), so
there is nothing to check re-exclusion against. This is a direct, mechanical consequence of Section 2.5's
finding, not a separate result.

### 2.5 The matrix and DGS — the real, governing finding

Every rule-based configuration B0–B8, evaluated against the new real corpus (real LoCoMo/LongMemEval/
MSC/Conversation-Chronicles benign content paired with real attack-injector poison output), scores
**0.0% poison detection and 0.0% benign false-positive rate**, identically across all 4 datasets:

| Config | Tuned corpus detection (known, `corpus.py`) | New corpus detection | Detection gap |
|---|---|---|---|
| B0 | 0.0% | 0.0% | 0.0 |
| B1 | 23.5% | 0.0% | −23.5 |
| B2 | 29.4% | 0.0% | −29.4 |
| B3 | 5.9% | 0.0% | −5.9 |
| B4 | 52.9% | 0.0% | −52.9 |
| B5 | 35.3% | 0.0% | −35.3 |
| B6 | 26.5% | 0.0% | −26.5 |
| B7 | 55.9% | 0.0% | −55.9 |
| B8 | 70.6% | 0.0% | **−70.6** |

The tuned-corpus column is not an estimate — it is `run_security_matrix`'s own code path re-run against
`corpus.py`'s `all_pools()`, and it reproduces every previously-reported B0–B8 number exactly (B8:
70.6%/7.3%, matching `docs/phase6/PHASE6_RESULTS.md` and `pipeline.py`'s own history). This is the load-
bearing evidence that the 0.0% new-corpus numbers are a real measurement, not a wiring bug in this
Phase 12 code: the identical function, called against a different real corpus, correctly reproduces a
known result on one input and a genuinely different result on the other.

**This extends, rather than contradicts, an already-known limitation.** `run_b10.py`'s own docstring
already discloses that the trained GNN+GLN blend, tested against `real_corpus.py`'s real 7-attack corpus,
measured AUROC 0.51–0.56 ("indistinguishable from chance... does not generalize"). Phase 12's DGS result
shows this is not specific to the learned components — every rule-based signal (admission, retrieval-
consensus, propagation-containment, sleeper) built and threshold-tuned exclusively against
`corpus.py`'s hand-authored synthetic text also fails completely against real attack-injector-produced
content, at every combination strength up to the full four-layer B8 stack.

## 3. Design Decisions Made During Implementation

- **AMR is scoped to QUARANTINE/BLOCK only** (`pipeline.py`'s two actions with genuine exclusion
  semantics), not ALLOW_WITH_RESTRICTION/DOWNRANK/REQUIRE_VALIDATION, which annotate rather than exclude
  by the severity model `combined_action()` itself already encodes. This scoping decision turned out not
  to matter for this pass's real result (n_hard = 0 everywhere regardless), but is disclosed as the
  definition actually implemented.
- **DGS scoped to B0–B8** (rule-based) this pass; B9/B10 (risk-composed and GNN/GLN-hybrid) require
  retraining a learned model per corpus and are left for a follow-on pass rather than attempted under
  this session's time budget — an explicit scope limit, not a silent omission.
- **The new corpus shares one poison population across all 4 datasets** rather than authoring
  dataset-specific poison, because this project's real attack injectors are not dataset-conditioned —
  there is exactly one real poison population to pair against each dataset's real benign population, not
  four independent ones.

## 4. PR — why it was not computed (a real, disclosed scope narrowing)

PR ("of admitted poison, the fraction that produces at least one real downstream DERIVED_FROM/
PROPAGATED_TO edge before any guard intervenes") is well-defined and buildable on the real, unmodified
`phase5.wiring.trace_assembly.build_propagation_graph()`/`lineage.derive_*` functions mapped in this
phase's exploration. It requires a genuine downstream event: a real agent retrieval → decision →
derivation loop actually producing a new memory derived from a previously-injected one
(`phase5.wiring.memory_lifecycle.record_memory_derivation`). This project has never wired that loop into
an automated, repeatable corpus sweep — the same gap the plan's own Section 8.5 names for utility
metrics ("Phase 6-11 has never been called from inside the Phase 3 agent runtime's own decision loop").
Manufacturing one synthetic derivation event per admitted poison item to produce a PR number would read
100% by construction and measure nothing real. Per this project's own standing discipline (no fabricated
ground truth; a negative or missing result is reported as such, not papered over), PR is left unmeasured
here and surfaced as a real, named dependency for Phase 14 (utility metrics), which must build that same
live loop regardless.

## 5. Out of Scope (this pass)

- The workload axis of the evaluation matrix (dropped, confirmed).
- PR (Section 4).
- B9/B10 in DGS (Section 3).
- Attribution metrics (Phase 13) and utility metrics (Phase 14) — untouched, per the plan's own division.
- Full cross-cutting sweep (Phase 15) and synthesis report (Phase 16).

## 6. What Remains Genuinely Open

- **Why does detection collapse completely, not just degrade, on real attack content?** DGS establishes
  the fact (0% vs. up to 70.6%) but not the mechanism. The rule-based signals were hand-tuned against
  `corpus.py`'s specific synthetic phrasing patterns (e.g. FARMA's "(Reconfirmed against prior notes on
  this — precedent count: 4.)" pattern); real injector output for the same attack families uses
  structurally different real content (real LoCoMo-conditioned text, real DSRM/FARMA seed phrasing) that
  may simply not trigger the same lexical/structural signal thresholds at all. This is a real,
  actionable next investigation, not covered by this pass's scope.
- Whether PAR being uniformly 100% across all 7 families reflects a real admission-guard gap (nothing
  this project's own attacks produce is ever rejected on ADMISSION, independent of downstream defense) or
  simply that admission-layer rejection was never the intended first line of defense for these families —
  worth checking against `docs/phase6/` admission-guard design intent before treating 100% as itself a
  finding.

## 7. Verdict

PAR, SDR, AMR, and DGS are implemented and real for the confirmed scope. The governing result is
negative and load-bearing: every rule-based defense configuration this project has built, up to and
including the full four-layer B8 stack, fails to detect any poison built from real attack-injector
output, across all four datasets swept, despite detecting up to 70.6% of the same attack families'
hand-authored synthetic equivalents. This is reported exactly as measured, consistent with every prior
phase's discipline — it is a real limitation of the current defense stack's generalization, not a defect
in this evaluation framework (the framework's own tuned-corpus reproduction of the known 70.6% number is
the evidence for that). Recommended for Phase 13's own scoping: check whether attribution confidence
correlates with this same generalization gap, since a defense that cannot detect real-content poison at
all cannot meaningfully attribute it either.
