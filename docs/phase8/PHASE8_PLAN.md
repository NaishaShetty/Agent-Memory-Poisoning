# Phase 8 Plan — Sleeper / Dormant Poison Detection

Status: PROPOSED, not yet started. Written 2026-09-16. Supersedes nothing;
inherits from `phase4/attacks/sleeper_memory_poisoning/` (frozen), Phase 6's
`docs/phase6/SLEEPER_DEFENSE.md` (Stage 6.8) and `phase6/defense/sleeper/`,
Phase 5's real `RETRIEVAL_CANDIDATE_SCORED` event history, and Phase 7's real
5-condition trigger sweep (`phase7/propagation/sleeper_study.py`,
`real_retrieval_pipeline_study.py`).

This document is a planning artifact for a stage of work that has not yet
been executed, written in the same charter style as
`docs/phase7/PHASE7_PLAN.md` so Phase 8 can later be evaluated against a
pre-committed plan the way Phase 6 and 7 were.

---

## 1. Research Question

> Once a poisoned memory is admitted but its trigger condition has not yet
> occurred, can that dormancy be recognized from the outside — using only
> the memory's own content, its position in real temporal/retrieval history,
> and the shape of its activation when it does occur — early enough to act
> before the trigger fires and the attack succeeds?

This project already has a real, frozen attack whose entire mechanism *is*
dormancy (Sleeper Memory Poisoning), a real defensive heuristic that already
gestures at detecting it (`phase6/defense/sleeper/sleeper_guard.py`), and
real, already-collected evidence that the activation transition is
genuinely observable in a real retrieval pipeline
(`phase7/propagation/real_retrieval_pipeline_study.py`'s real finding: a
planted memory stays unselected under a distant query and becomes selected
under a matching one). Phase 8's job is not to prove dormancy exists or that
attacks can be dormant — that is already established. Its job is to build
and honestly evaluate a **detector**: something that looks at a memory
*before* its trigger fires and outputs a real, evidenced judgment about
whether it is dormant-and-suspicious, using signals a real deployed system
could legitimately compute today.

## 2. Why This Is Not Already Covered

| Already exists | What it does | What it does NOT do |
|---|---|---|
| `phase4/attacks/sleeper_memory_poisoning/injection_gate.py::judge_injection()` | Write-time LLM judgment of whether a document's content would cause a reasonable assistant to persist `forged_memory_text` | Nothing at or after admission — a one-shot gate, not a standing monitor |
| `phase4/shared/dormancy_report.py::describe_dormancy()` | Per-run, per-query 3-way classification (`STATE_SELECTED_TOP_K` / `STATE_IN_CANDIDATE_POOL` / `STATE_NOT_RETRIEVED`) of one artifact against one `AgentRunOutcome` | Any persistence across runs/queries — it has no memory of prior calls, so it cannot say "this memory has been dormant for N queries" |
| `phase6/defense/sleeper/sleeper_guard.py::evaluate_sleeper_admission()` | Write-time regex heuristic (persistence marker AND directive verb) → `QUARANTINE`/`ALLOW` | Anything content-based beyond two regex classes; disclosed as evadable by paraphrase/directive-splitting (`SLEEPER_DEFENSE.md`'s own limitations) |
| `phase6/defense/sleeper/sleeper_guard.py::evaluate_sleeper_retrieval_risk()` | Retrieval-time score = `directive_score × dormancy_activation_signal(prior_retrieval_count)`, where the activation term is `1/(1+prior_retrieval_count)` | Reading any real ledger for `prior_retrieval_count` — the caller must supply that integer by hand; **disclosed, never wired, Stage 6.10's own gap** |
| `phase5/wiring/retrieval_instrumentation.py::instrument_retrieval_and_selection()` | Persists a real, timestamped `RETRIEVAL_CANDIDATE_SCORED` event per candidate per task, including `cosine_score`/`token_overlap_score`/`entity_overlap_score`/`blended_score`/`selected` | Any aggregation of this history into a temporal/activation signal — it is raw, per-call data, not a computed pattern |
| `phase7/propagation/real_retrieval_pipeline_study.py::run_sleeper_real_retrieval_study()` | One real, already-measured 5-condition sweep proving the real activation transition is observable (selected under exact/paraphrased/near/partial, correctly not under distant) | A standing detector — it is a one-time research measurement, run once per call, not a monitor that watches new memories as they arrive |

Phase 8's job, stated precisely: **build a real detector that consumes
the real, already-persisted retrieval history (Phase 5) and the real
content of a memory (Phase 4's own attack artifacts, generalized to any
memory) to (a) wire Stage 6.10's own disclosed gap — a real
`prior_retrieval_count` computed from the real ledger, not a caller-supplied
integer — and (b) add the temporal/content signals `sleeper_guard.py`
explicitly does not yet have.** Phase 8 does not re-derive the attack, the
ground-truth vocabulary, or the real activation transition Phase 7 already
measured; it builds the detection layer on top of them.

## 3. The Named, Already-Disclosed Gaps This Phase Targets

`docs/phase6/SLEEPER_DEFENSE.md`'s own limitations section names exactly the
open items this phase exists to close, quoted rather than paraphrased into
something stronger:

1. **"No real ledger wired in yet"** — `evaluate_sleeper_retrieval_risk()`
   takes `prior_retrieval_count` as a bare integer parameter; nothing in the
   frozen codebase today computes it from Phase 5's real event history. Note:
   `SLEEPER_DEFENSE.md`'s own limitation text (§"Limitations Carried
   Forward", item 4) names the caller-supplied source as a real
   `EventRunMembershipLedger`/`GovernanceLedger`, not Phase 5's
   `RETRIEVAL_CANDIDATE_SCORED` event ledger. Phase 8's Signal 1 (§4) wires a
   *different, related* real ledger — Phase 5's own retrieval-scoring
   history — into the same parameter. This closes the same practical gap
   (a real count instead of a hand-typed integer) but is a substitution, not
   literally the source the limitation names, and this plan should be read
   that way.
2. **"Regex evadable by paraphrase-splitting"** — the write-time admission
   heuristic (`imperative_write_directive_signal()`) requires a persistence
   marker AND a directive verb to both appear; an attacker who splits the
   imperative across two sentences, or paraphrases the directive without a
   recognized verb, defeats it.
3. **"No non-English-directive detection"** — the regex is English-only by
   construction.
4. **"Uncalibrated thresholds"** — the `≥0.5`/`≥0.2` cutoffs in
   `evaluate_sleeper_retrieval_risk()` were chosen for illustration, not
   calibrated against any real benign-vs-attack distribution.

Separately, Phase 7's own real, measured finding is a concrete design input
Phase 8 must build on rather than re-discover: the real activation
transition (dormant → triggered) is only cleanly observable through a real
embedding-based retrieval pipeline (`RealMem0Adapter`) — the mock-based
harness could not reproduce it (`phase7/propagation/sleeper_study.py`'s own
disclosed "selected in all 5 conditions" result). Any Phase 8 detector that
claims to observe real activation behavior must be validated against the
real pipeline, not the mock, or its own claims will repeat that same gap.

## 4. What Phase 8 Adds — Four New Signals, One Wiring Fix

Phase 6 added one new concept (a security lifecycle); Phase 7 added three
(propagation footprint, propagation-shape signals, an abnormality
baseline). Phase 8 adds four detection signals plus one concrete wiring fix,
kept narrow and each traceable to a real, already-existing data source:

1. **Real retrieval-count wiring (closes gap 1 directly)**:
   `real_prior_retrieval_count(memory_id, *, phase5_event_ledger, as_of_task_id)`
   — counts real `RETRIEVAL_CANDIDATE_SCORED` events for `memory_id` with an
   earlier timestamp/task ordering than `as_of_task_id`, and feeds that real
   count into `evaluate_sleeper_retrieval_risk()`'s existing
   `dormancy_activation_signal()` term, unmodified. No new event type, no
   new heuristic — purely replacing a caller-supplied guess with a real,
   ledger-derived count.
2. **Dormancy-window signal**: for an admitted memory, the real elapsed
   distance (in tasks processed, or in real `Phase5Event` timestamps) between
   its `POISON_ADMITTED` transition and its first `POISON_SELECTED_TOP_K` — a
   real, computed duration from already-recorded ground-truth transitions
   (`phase5/schema/event.py`'s `ATTACK_GROUND_TRUTH_TRANSITION`), not a new
   instrumentation point. Correction from an earlier draft of this plan: a
   memory that never activates is reported as `ever_selected=False`
   ("not yet selected, as of the ledger's current state"), never labeled
   `ATTACK_FAILURE` — direct read of `phase5/wiring/ground_truth.py`'s own
   module docstring shows `ATTACK_FAILURE` is deliberately NOT mechanically
   derived there (it "require[s] a task-specific, calibrated success/behavior
   judgment" that module explicitly refuses to invent), so Stage 8.4 has no
   more basis for assigning that label than `ground_truth.py` itself does.
   A memory admitted long ago but never yet selected is measurably different
   from one selected on its very next query — this signal makes that
   difference explicit and queryable without overclaiming a judgment this
   project's own ground-truth deriver already declined to make.
3. **Content-based directive generalization (addresses gap 2/3)**: rather
   than replacing `imperative_write_directive_signal()`'s regex outright
   (which would require modifying a frozen Phase 6 file), Phase 8 adds a
   read-only, disclosed **evaluation** of how many of the real Sleeper
   artifact corpus's variants (paraphrased/split imperatives, generated the
   same way Phase 7's own trigger-condition queries were derived — real
   paraphrase, not fabricated) the existing regex actually catches versus
   misses, producing a real, measured evasion rate rather than the
   qualitative "evadable" the limitation currently states. Whether a
   stronger content classifier gets built depends on what that measurement
   actually shows (Stage 8.3 below).
4. **Activation-shape signal**: using Phase 7's real
   `run_sleeper_real_retrieval_study()`-style pipeline, measure how
   *sharply* a memory's real selection status changes across the 5 real
   trigger conditions (a step function: not-selected under 4 conditions,
   selected the moment a 5th, closely-matching query arrives) versus a
   benign memory's own real selection pattern across the same 5 queries
   (expected: smoother, more gradual relevance falloff, not a step). This is
   the closest real, computable analogue to "detect activation from its own
   shape," and it is validated against real embeddings, not a mock.

None of these four signals introduces a new evidence kind or lifecycle
state; every one is a read-only aggregation of already-real events
(`RETRIEVAL_CANDIDATE_SCORED`, `ATTACK_GROUND_TRUTH_TRANSITION`) or a
measured evaluation of an existing heuristic's real hit rate. Signal 1 is a
direct fix to a named gap, not a new design.

## 5. Inherited Constraints (frozen, carried over unchanged)

- **The evaluator-only / legitimate boundary**
  (`phase3/evaluation/contracts/boundary.py`, `FORBIDDEN_KEYS`) — none of
  the four signals above may read `attack_label`/`attack_labels`, the
  ground-truth label itself, or the Sleeper trigger phrase as a known label
  (`FORBIDDEN_KEYS` has no literal `attack_id` entry; the actual forbidden
  keys are `attack_label`/`attack_labels`). `real_prior_retrieval_count()`
  and the dormancy-window signal both read only real, legitimately-available
  event history (retrieval scores, ground-truth *transitions* a real system
  could also observe as they happen — never the eventual outcome label
  read backward in time).
- **Single-heuristic-never-blocks discipline**
  (`phase6/defense/sleeper/sleeper_guard.py`'s own design: both its
  functions cap at `QUARANTINE`/`DOWNRANK`, never `BLOCK`) — Phase 8 is
  explicitly a **monitor/signal layer**, matching Phase 7's own framing, not
  a new intervention. If Signal 1's real-count wiring changes
  `evaluate_sleeper_retrieval_risk()`'s output, the function's own action
  ceiling is untouched.
- **Frozen Phase 4 attack and Phase 6 defense code** — `sleeper_guard.py`,
  `injection_gate.py`, `injector.py` are read, called, and measured against;
  none is modified. Signal 1 wires a REAL count into an EXISTING parameter
  the function already accepts — it does not change `sleeper_guard.py`'s
  own signature or logic.
- **Evidence-kind discipline** (§18.7 vocabulary, inherited via Phase 7 §5)
  — every Phase 8 signal must state which real evidence kind
  (`OBSERVED_EVENT`, `LINEAGE_REACHABILITY`, etc.) it rests on, mirroring
  Phase 7's own `SignalResult.evidence_kinds` convention.
- **The real-vs-mock retrieval boundary Phase 7 already found**
  (`docs/phase7/PHASE7_REPORT.md` §5.5/§2.5) — any Phase 8 claim about real
  activation behavior must be validated through `RealMem0Adapter` (real
  embeddings), not `MockMem0Adapter`, or it inherits the same
  "selected in all 5 conditions" false-negative Phase 7 already disclosed
  and fixed once. Phase 8 does not re-litigate that fix; it reuses
  `real_retrieval_pipeline_study.py`'s own pattern directly.

## 6. Explicit Out-of-Scope for Phase 8 v1

- Any new intervention/blocking mechanism for a detected dormant memory —
  Phase 8 measures and flags, per §5's inherited discipline; a future phase
  (or a Phase 6 extension) would decide what a real system does once
  flagged.
- Calibrating `sleeper_guard.py`'s own `≥0.5`/`≥0.2` thresholds against a
  real benign-vs-attack distribution at scale — gap 4 (uncalibrated
  thresholds) is named but a full calibration campaign is a larger,
  separate undertaking than this plan scopes; Phase 8 v1 reports the real
  distribution it measures and leaves threshold-setting as a disclosed next
  step, mirroring Phase 6's own "not fixed by this charter" treatment of its
  operating envelope.
- A general-purpose, model-backed content classifier for arbitrary
  dormant-poison text (replacing the regex heuristic outright) — Signal 3
  measures the regex's real evasion rate; building a stronger replacement is
  conditional on what that measurement shows, not pre-committed here.
- Non-English directive detection (gap 3) — named, not solved; solving it
  well would require real non-English Sleeper-style artifacts this project
  does not currently have, and fabricating them without linguistic
  grounding would be worse than leaving the gap disclosed.
- Extending detection to attacks other than Sleeper. FARMA/MemoryGraft/etc.
  have their own real activation-adjacent behaviors (documented in Phase 7's
  §2.2), but Phase 8 v1 is scoped to the one attack whose entire mechanism
  is dormancy — generalizing the detector to other attacks is a natural
  Phase 8 v2 candidate, not this plan's job.

## 7. Proposed Stage Breakdown

- **8.1 — Charter & Scope** (this document). Cross-check against actual
  code before execution begins, same discipline as Phase 6 §9 / Phase 7 §8.
- **8.2 — Real Retrieval-Count Wiring**: implement
  `real_prior_retrieval_count()` as a thin, read-only function over
  `Phase5EventLedger`, and a regression test proving
  `evaluate_sleeper_retrieval_risk()`'s real output changes correctly when
  fed a real count from an actual multi-query retrieval history (built via
  `instrument_retrieval_and_selection()`, unmodified) instead of a
  hand-typed integer. Closes gap 1.
- **8.3 — Directive-Regex Real Evasion Measurement**: construct a small set
  of real, disclosed paraphrase/split-imperative variants of directive-shaped
  Sleeper-style content (same paraphrase-generation discipline Phase 7
  already used for its own trigger conditions — real, labeled variants, not
  fabricated attack traffic), run them through
  `imperative_write_directive_signal()` unmodified, and report the real
  hit/miss rate. Correction from an earlier draft of this plan: the real
  persisted memory content for `SEED_DESTRESS` is `forged_memory_text`
  ("Melanie relies on long solo drives to destress...") — a plain factual
  statement, confirmed by direct read of `injector.py`'s `add_memory(content=
  {"text": artifact.forged_memory_text, ...})` call — not `document_text`
  (the carrier article text, never itself persisted as a memory). Neither
  field contains imperative/persistence language to begin with, so 8.3 also
  reports that baseline fact directly (a real MISS on
  `imperative_write_directive_signal()` for reasons prior to and distinct
  from paraphrase evasion), then separately measures paraphrase/split
  evasion against directive-shaped content built the same way Phase 6's own
  `test_sleeper_defense.py` true-positive fixtures already were (synthetic,
  modeled on the attack's documented structural mechanism, never this
  project's literal frozen trigger phrase). This turns "evadable"
  (qualitative) into a real measured
  number.
- **8.4 — Dormancy-Window Signal**: implement the real
  admitted-to-activated (or admitted-to-attack-failure) duration signal
  over real `ATTACK_GROUND_TRUTH_TRANSITION` events, and validate it against
  at least one real Sleeper trial run through the full lifecycle (admission
  → several non-matching queries → the matching query that activates it).
- **8.5 — Activation-Shape Signal, Real Pipeline**: extend
  `real_retrieval_pipeline_study.py`'s own pattern (or add a sibling module)
  to compute the real selection-pattern "shape" (step vs. gradual) across
  the 5 real trigger conditions for the real planted memory AND for a real
  benign LoCoMo memory from the same ingested pool, as a same-conditions
  comparison — closing the "detect from shape" half of the plan's own
  research question with a real baseline, not just the attack's own numbers.
- **8.6 — Cross-Signal Real Trial**: run all four signals together against
  one real, full Sleeper lifecycle (using the real
  `RealMem0Adapter`-backed pipeline from 8.5), and report what each signal
  says at each real point in that lifecycle — before, during, and after the
  real activation transition Phase 7 already proved is observable.
- **8.7 — Benign False-Positive Check**: run the same four signals against
  real benign memories from the same ingested LoCoMo pool that are
  legitimately rarely retrieved (e.g., a memory about a one-off topic no
  later query touches) to check that "rarely selected so far" alone does not
  get flagged the same way a real dormant-attack memory does — mirroring
  Phase 7's own benign-baseline discipline (never report a detection number
  without its false-positive-on-benign-behavior counterpart).
- **8.8 — Reporting & Limitations**: write results with the same
  evidence-kind labeling and honest-limitations discipline used throughout
  Phases 5–7 — explicit disclosure of what gap 3 (non-English) and gap 4
  (calibration) still leave open, and whether Signal 3's measured evasion
  rate justifies building a stronger classifier in a future stage.

## 8. Acceptance Criteria for 8.1

8.1 PASSES when:
1. This plan is internally consistent with the actual current state of
   `phase4/attacks/sleeper_memory_poisoning/`, `phase6/defense/sleeper/`,
   `phase5/wiring/retrieval_instrumentation.py`, and
   `phase7/propagation/{sleeper_study,real_retrieval_pipeline_study}.py`
   (spot-checked against real code for this draft — function/class names
   above were confirmed to exist as named).
2. Every new signal proposed (§4) is stated in terms of event types and
   functions that already exist — no new event type, evidence kind, or
   ground-truth state is invented without explicit justification here
   (none was needed).
3. The named gaps this phase targets (§3) are quoted/paraphrased faithfully
   from their real source (`SLEEPER_DEFENSE.md`'s own limitations section),
   not strengthened into something the source does not claim.
4. No frozen file (Phase 3–7, Attribution) is modified to produce this plan
   or would need to be modified to begin 8.2 — Signal 1 wires a real value
   into an existing parameter, it does not change `sleeper_guard.py` itself.

## 9. Verdict

**8.1 — PROPOSED / NOT YET STARTED.** This document is a plan for future
work, not a record of work performed. Given how much Phases 5–7 continued to
evolve after their own charters were first written (the UNASSESSED-default
fix, the corpus scale-up, Decision 2's mid-Phase-7 wiring), this plan should
be re-verified against the codebase immediately before Phase 8 execution
begins rather than assumed still accurate.
