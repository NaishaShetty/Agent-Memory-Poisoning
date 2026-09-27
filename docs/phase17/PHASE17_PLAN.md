# Phase 17 Plan — Ablation & Generalization

Status: **proposal, not a decision** — same discipline as every earlier phase plan. Nothing below
is implemented; Section 7's open questions need real answers before any code is written.

## 1. Research Question

*"Which parts of MAMBench's defense stack actually contribute to the results Phases 12–16
reported — and do those results hold on attacks, datasets, and workloads the stack was not tuned
against, or are they optimized for the 7 known attack families and 4 known datasets?"*

Two halves, deliberately kept separate because they answer different questions:
- **Ablation** — remove one component at a time, re-measure. Answers "is each part earning its
  place?"
- **Generalization** — hold the full stack fixed, change what it is tested on. Answers "is the
  stack fitted to its evaluation set?"

Phase 16 explicitly hands both to this phase, and names three open findings it should address:
(1) the learned B10 blend never decides anything on Phase 12's corpus (the corroboration gate does),
(2) one MINJA-family step is caught only by B8's sibling-propagation, (3) B10-live carries a small
benign cost (1.3%) no rule-based config does.

## 2. What Already Exists (verified by direct inspection, not assumed)

| Need | What exists | Real limit |
|---|---|---|
| Leave-one-**guard**-out | `DefenseConfiguration` already has flags for admission, retrieval (lexical/semantic), propagation, sleeper, sibling-propagation. `run_security_matrix(configs=...)` accepts any config list, so e.g. `replace(B8_ALL_FOUR, sibling_propagation_enabled=False)` needs no new plumbing. | Consolidation Guard is not a `DefenseConfiguration` component; activation-shape and dormancy are not separately switchable inside B8. |
| Leave-one-**signal**-out | B9/B10/Phase 14 build their own `signals` dict, so dropping a key and calling `compute_memory_risk_score(...)` works; missing keys are tolerated. | B8's `evaluate_admission()` has **no subset parameter** (`weighted_score()` sums all 14 keys) — B8-level signal ablation needs new, additive plumbing. `run_b9_risk_composed()` has no signal-subset hook either (small parallel function needed). |
| Rule/gate ablation | `rule=` selects among 4 composition rules; `admission_corroboration_floor=` is a parameter; `admission_corroboration_floor_sweep.py` already sweeps the floor. | Phase 14's live `_b9_actions()` hardcodes its rule (needs a hook for live-path rule ablation). |
| B10 learned-part ablation | Constants `W`, `SEEDS`, `WEIGHT_DECAY` are module-level; `W=0` should give an untrained-only blend. | No flags; needs a thin wrapper. |
| Prior "ablation" work | The B0–B8 leave-one-guard framework; risk/threshold sweeps. Phase 11 LOFO = leave-one-attack-**family**-out for the **trained** GNN/GLN. | **No signal-level leave-one-out exists anywhere.** Phase 11 LOFO removes training data, not defense components — different question. |
| Unseen attacks | `phase4/attacks/` has exactly the 7 known families. | **No vendored source contains genuinely new attack content** (convomem/perltqa/membench/memoryagentbench/memoryarena are benign benchmarks). See Section 4. |
| Real workloads | LoCoMo `category` 1–5 (282/321/96/841/446 QA pairs); LongMemEval `question_type` (temporal 133, multi-session 133, knowledge-update 78, single-session-user 70, -assistant 56, -preference 30; 30 abstention). | LoCoMo's category *names* are not in the file (numbers only). MSC/ConversationChronicles have no task layer. |
| Extra datasets | 5 vendored candidates (convomem 1,559 records, perltqa 7,521, memoryagentbench 146, membench 275, memoryarena 4,850), normalized JSONL + adapters. | None feed Phase 12's corpus today; no `ScenarioPool` loader exists for them. |

## 3. Two Real Constraints That Shape the Whole Phase

**(a) Statistical power is thin.** Phase 12's poison population is 15 scenarios, so one record is
6.7 points of detection. An ablation that changes detection by "1 record" is indistinguishable from
noise. `regenerate_poison_batch()` (used by Phase 11) already yields ~9 more real candidates from
the same 7 families — a real, non-fabricated way to grow the poison set — but the phase should
report raw counts and refuse to over-claim small deltas.

**(b) In-sample contamination.** Signals 12–14 (`synthetic_repetition_padding`,
`unverifiable_closure`, `preference_decision_update`) were written from the *same isolated Track B
poison instances* that also form the evaluation poison — removing one and re-measuring on that data
is in-sample by construction. A meaningful generalization test needs poison the signals were not
written from (the regenerated batch, or leave-one-family-out with the signal-to-family map below).

Signal → family it was written from (from the inline provenance in `signals.py`): self_reference→FARMA,
decision_log→MemoryGraft, template_anomaly→DSRM, interrogative_restatement→DSRM,
stale_precedent→FARMA, third_person_report→MPBench, entity_link_directive→MINJA,
forged_provenance_confirmation→AgentPoison, synthetic_repetition_padding→DSRM,
unverifiable_closure→FARMA, preference_decision_update→MPBench. This map is what makes a
**signal-removal generalization** test well-defined: remove the signal built for family X, measure
family X, and see who else still catches it.

## 4. Proposed Scope

### Part A — Ablation (mostly cheap: signal computation, no LLM calls)

- **A1. Leave-one-guard-out** on B8 (5 components) and B9: existing flags / rule parameters, run
  through `run_security_matrix`. Answers "does each guard earn its place?"
- **A2. Leave-one-signal-out** over the 14 admission signals (needs the small additive plumbing
  above), reported per attack family and per dataset. Answers "which signals carry which
  families, and which are redundant?" A signal whose removal changes nothing is a real finding
  (redundancy), not a failure.
- **A3. Rule/gate ablations**: retrieval-corroboration on/off, admission floor on/off and swept,
  each measured for BOTH what it costs (detection of purely retrieval-driven attacks) and what it
  buys (false positives). The B9 and B10 gates were introduced this project to fix real false
  positives; this measures their real price on a corpus that *does* contain retrieval-only attacks
  (the frozen `corpus.py` near-duplicate pools), which Phase 12's corpus lacks.
- **A4. B10 learned-part ablation**: untrained-only (`W=0`), GNN-only, blend, and gated vs
  ungated — directly answers Phase 16's finding that the learned blend adds no demonstrated value,
  including on a corpus where retrieval-only evidence *can* decide (again the frozen corpus).
- **A5. Consolidation Guard** on/off for Track B stage-2 protection (uses existing LLM-backed
  stage; a small run).
- Utility is re-measured **only** for ablations that change what gets excluded live (LLM-call
  cost is the expensive part; most ablations only need the offline matrix).

### Part B — Generalization

- **B1. Leave-one-attack-family-out for the rule-based stack** (the signal-removal test above):
  the analog of Phase 11's LOFO but for the defense components, not a trained model.
- **B2. Held-out poison**: evaluate the fixed stack on `regenerate_poison_batch()` content the
  signals were not written from (in-family but unseen instances).
- **B3. Workloads from real structure**: stratify Track A utility and benign false-positive rate by
  real question category (LoCoMo 1–5, LongMemEval `question_type`) — this is Phase 12's dropped
  workload axis, definition (b) ("real task types"), now feasible. Note honestly that security
  detection is content-based and should not vary by question type; the axis matters for utility
  and benign FPR.
- **B4. Additional real datasets** for the *security* signals: convomem and perltqa memory records
  (real conversational memory, no QA needed) via a new `ScenarioPool` loader — a real fifth/sixth
  benign population for false-positive testing at scale (the 50,045-text FP test in Phase 15
  already showed this is where real limits surface).
- **B5. Unseen attacks — see Question 1**: no genuinely new real attack exists in the repo. Options
  are laid out below rather than chosen silently.

## 5. What Phase 17 Does Not Do

- Does not build new defenses or retune thresholds to improve numbers — it measures. (Consistent
  with the project's "measurement phase" scope; the open MINJA-step gap and B10-live's 1.3% cost are
  to be *characterized*, not fixed, unless you say otherwise.)
- Does not fabricate attack content: any "unseen attack" must be real output of a real mechanism
  (an existing injector run with new seeds, or an LLM-generated variant whose generation is itself
  recorded), never hand-written examples.
- Does not modify frozen Phase 3–16 code except by additive, default-preserving parameters (the
  pattern used throughout Phases 14–15), each verified against the full regression suite.

## 6. Risks / Honest Limits Up Front

- Small poison n (15, ~24 with regeneration): ablation deltas of a single record are not
  significant; the report will show counts and say so.
- Leave-one-family-out over only 7 families gives 7 folds of 2–3 records each — indicative, not
  statistically strong.
- "Unseen" attacks that are variants of known mechanisms test robustness to paraphrase/evasion,
  not novelty of mechanism — the report must say which it is.
- Workload stratification will show ~zero security effect by design; a null result there is the
  expected, informative outcome, not a gap.

## 7. Open Questions Requiring Your Confirmation Before Implementation

1. **What counts as an "unseen attack"?** The repo contains no genuinely new attack family.
   Options: (a) **leave-one-family-out** only (remove a family's own signals/calibration and test
   on it — cheapest, fully real); (b) **new instances of known families** from
   `regenerate_poison_batch()` / fresh injector seeds (real, unseen instances, same mechanism);
   (c) **adaptive/evasion variants**: use the local LLM to rewrite known poison so it avoids the
   signals that catch it (real generation, tests true robustness, but it is *my* construction —
   needs your OK that LLM-generated evasions count as legitimate real attack content, with each
   generation recorded); (d) all of the above. Recommendation: (a)+(b)+(c), with (c) clearly
   labelled as adversarially adapted, not an independent attack family.
2. **Ablation breadth**: full leave-one-out over all 14 signals + 5 guards + rules + B10 parts
   (as in Part A), or a smaller focused set (e.g. only the components added in Phases 14–15, plus
   B10's learned parts)? Full breadth is offline and cheap; the cost is report size.
3. **Fix or characterize?** If ablation shows a component is redundant or harmful (e.g. the
   learned blend), should Phase 17 only report it, or also propose/apply a simplification? I
   recommend report-only, with recommendations, so this phase stays a clean measurement.
4. **Extra datasets (B4)**: build the convomem/perltqa `ScenarioPool` loader and include them as
   new benign populations for security false-positive testing — yes/no? (Only security; their task
   layers are not needed and utility is out of scope for them.)
5. **Workload definition**: confirm (b) real question categories, and that LoCoMo's numeric
   categories 1–5 may be named per the LoCoMo paper (I could not verify the mapping from the file
   itself — I would cite the paper's mapping and say so, or leave them numeric).
6. **Poison scale-up**: authorize growing the evaluation poison set via `regenerate_poison_batch()`
   (and fresh injector seeds) to improve statistical power, reported separately from the original
   15 so Phase 12–16 numbers stay comparable?
7. **Compute**: Part A/B1/B2/B4 are offline (minutes). Part B3 utility stratification and any A5/
   evasion-generation work use the local LLM (each n=150/150 utility run ≈ 2 hours). Cap the
   LLM-backed portion to what you're comfortable with, or run it all?

## 8. Deliverables (once scope is confirmed)

1. `phase17/` — new additive module tree (ablation runner over configs/signals/rules, held-out
   poison + leave-one-family-out harness, workload stratification, loader for extra datasets);
   existing code touched only via additive default-preserving parameters.
2. Real, executed ablation and generalization tables with raw counts, including cells where a
   component turns out redundant or where the stack fails to generalize.
3. `docs/phase17/PHASE17_ABLATION_GENERALIZATION_REPORT.md` — measured results, root-caused
   surprises, and an explicit "what remains open" section, following the project's disclosure
   discipline.
4. Regression suite extended, never replaced; full cross-phase run after every shared-code change.
5. A closing recommendation on which components to keep, simplify, or remove, and what the results
   do and do not support claiming about generalization.
