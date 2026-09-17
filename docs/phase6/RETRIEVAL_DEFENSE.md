# Stage 6.6 — Retrieval-Time Defense

Status: 6.6 deliverable summary (design rationale lives in module docstrings under
`phase6/defense/retrieval/`; this document is the stage-gate record).

## Objective

Intervene on Phase 3's real 20-candidate pool before its unmodified hybrid rerank —
filtering, downranking, or escalating candidates based on legitimate signals —
without replacing or duplicating the frozen retrieval mechanism.

## What Was Implemented

- `phase6/defense/retrieval/signals.py` — `pool_consensus_divergence_signals()`: a
  lexical (Jaccard token-overlap) cross-candidate divergence proxy, adapting
  A-MemGuard's consensus-checking *concept* (6.2's strongest D3 candidate) without
  its LLM-as-judge or entity-relation extraction machinery.
- `phase6/defense/retrieval/consensus_guard.py` — `evaluate_retrieval_defense()`:
  reads each candidate's persisted D2 security state (supplied by the caller, not
  read from a ledger by this module — same plain-data-carrier discipline as
  `SignalContext`), excludes already-QUARANTINED/BLOCKED candidates outright,
  computes consensus divergence for the remaining eligible pool, applies a
  query-local `DOWNRANK` penalty above one threshold, and escalates to a
  **persistent** `QUARANTINE` decision above a second, higher threshold — the D3→D2
  escalation path the Scope Matrix anticipated. Every escalation is validated
  against Stage 6.3's frozen transition table before being attempted.
- This resolves the consistency-screening gap disclosed in
  `ADMISSION_DEFENSE.md`: comparing a candidate against the rest of its own
  retrieval pool *is* the practical, cheaply-computable form of "consistency
  against trusted memory" D3 can perform without a second full retrieval pass.

## The Inherited Weakness — Demonstrated, Then Partially Mitigated (2026-09-14)

`DEFENSE_LITERATURE_AUDIT.md` (Track A.5) already predicted that A-MemGuard's
consensus mechanism is structurally vulnerable to coordinated poisoning: several
mutually-consistent planted memories can make themselves look like the trustworthy
majority and a lone true fact look like the anomaly. This lexical-overlap adaptation
inherited that weakness, undamped, in the version first shipped this stage.

A genuine, partial mitigation was added on request: **near-duplicate deduplication
with square-root-dampened cluster weighting** (`signals.py`'s
`NEAR_DUPLICATE_THRESHOLD` / `DEDUP_DAMPENING_EXPONENT`). Candidates are first
greedily clustered by pairwise similarity; each other candidate's vote in the
divergence calculation is weighted by `1 / cluster_size ** 0.5` rather than counted
in full. This directly targets FARMA's and MemoryGraft's own real mechanism — both
manufacture consensus through **volume** (repeating near-identical content), which
is exactly what sub-linear cluster weighting discounts.

Three tests establish the honest, complete picture rather than a single pass/fail:

1. `test_coordinated_poisoning_still_favors_the_planted_majority_but_gap_narrows`
   — for near-duplicate planted poison, the true fact is **still** flagged as more
   divergent than the poison majority. The mitigation does not flip the outcome.
2. `test_dedup_dampening_measurably_reduces_manufactured_consensus_advantage` — the
   **same pool**, compared with dampening on vs. off, shows the poison's divergence
   score measurably increases (looks more suspicious) under dampening. This is the
   real, quantified improvement — narrowing the gap, not closing it.
3. `test_paraphrased_coordinated_poison_still_fully_evades_dedup` — three
   differently-**worded** (not near-duplicate) coordinated poison records, each
   pairwise similarity below the clustering threshold, never cluster at all, so
   dampening never engages. The defense is fooled exactly as before the fix. This
   test exists specifically so this boundary is never later miscast as solved.

**Why square-root dampening, not full deduplication** (collapsing each cluster to
one vote): a stronger version was tried and rejected — full deduplication removes
the genuine-majority signal entirely, making a real 2-witness majority against a
true 1-witness minority indistinguishable from 1-vs-1, which breaks the mechanism's
ability to do the ordinary, correct thing for benign cases (trust corroborated
content more than an uncorroborated outlier). Square-root dampening is a disclosed,
uncalibrated compromise between these two failure modes, not a claim of an optimal
setting.

**What remains genuinely unsolved, not just under-tuned**: no purely content-based
mechanism with no external verification can fully distinguish "three independent
witnesses genuinely agree" from "one attacker wrote three sufficiently different
lies that happen to agree." The Signal Contract (Stage 6.4) deliberately withholds
attacker-identity and cross-source corroboration signals from this layer — so this
is a structural boundary of what a Signal-Contract-compliant D3 mechanism can ever
achieve alone, not a bug this component failed to fix.

Separately, escalation to a persistent `QUARANTINE` was changed from a single-event
trigger to requiring **accumulated evidence**: `MIN_TOTAL_FLAGS_FOR_ESCALATION = 2`,
checked via a caller-supplied `prior_downrank_count_for()` callback backed by the
memory's real `GovernanceLedger` history. The default callback (`lambda _: 0`) is
deliberately conservative — with no real history wired in, escalation never fires,
never over-eagerly.

## Design Choices Worth Flagging

- **No decision is recorded for passively-enforced exclusion.** A candidate already
  QUARANTINED/BLOCKED from a prior D1 decision is excluded at D3 without a new
  ledger entry — that decision was already made and already has its own evidence
  trail; re-recording it here would be redundant, not additional evidence.
- **Escalation now requires accumulated evidence** (fixed 2026-09-14 — see above):
  `prior_downrank_count_for()` lets the caller ground escalation in a memory's real
  decision history via `GovernanceLedger`, rather than a single retrieval's own
  signal. This does not require the cross-run *retrieval-frequency* aggregation the
  Signal Contract flagged as unbuilt (Stage 6.4, Section 5) — it reuses MGP's own
  already-existing decision ledger, which already tracks a memory's full history.
- **Divergence is computed only against the eligible sub-pool**, excluding
  already-ineligible candidates. This avoids letting an already-known-bad candidate
  distort the "consensus baseline" further, but does not solve the coordinated-
  poisoning weakness above (which concerns candidates that have not yet been
  flagged by anything).

## Tests and Evidence

26 tests (22 original + 4 added by the 2026-09-14 fix pass): divergence-formula
correctness (identical/disjoint/uniform/outlier pools), full pipeline behavior
(benign pool untouched, lone outlier downranked not excluded, the coordinated-
poisoning gap-narrowing comparison, the paraphrase-still-evades boundary,
already-quarantined/blocked exclusion produces no redundant decision, escalation
legality checked against every eligible starting state via Stage 6.3's real
transition validator, escalation now requires accumulated evidence and never fires
on a single event with the default callback), determinism, evidence-ref
pass-through, and static checks that this module never imports Phase 3's frozen
`hybrid_selection.py` or any Phase 4 attack code, and never hardcodes an attack name
as a string literal.

**Full Phase 6 suite (after the 2026-09-14 semantic-escalation follow-up): 109
passed, 0 failed** (37+14+21+26 original D1 tests across Stages 6.3–6.6, plus 11
new D2 tests across `test_semantic_vs_lexical_consensus.py` and
`test_semantic_consensus_guard.py`).
Frozen `phase3/`, `phase4/`, `phase5/`, `attribution/` verified unchanged.

## Limitations Carried Forward

1. Lexical (token-overlap) divergence is a crude proxy for A-MemGuard's real
   semantic/entity-relation consensus mechanism. **Escalated, per explicit
   instruction, to a real D2 semantic variant** (see "D0–D4 Framework" below) —
   the limitation is no longer left unaddressed, though D2 introduces its own
   disclosed, narrower limitation (see point 2's update and the D2 section).
2. The coordinated-poisoning weakness is **mitigated at the mechanism level for
   near-duplicate content, in both D1 and D2, but the decision-layer outcome did
   not flip in the constructed test scenarios for either metric** — see the D2
   section below for the corrected, honest account (an earlier draft of this
   document overclaimed a full fix here and has been corrected). It remains a
   structural limit of any purely content-based, no-external-verification,
   single-pool signal — not an implementation gap this component could close on
   its own regardless of metric.
3. Escalation evidence-accumulation is **fixed**: requires
   `MIN_TOTAL_FLAGS_FOR_ESCALATION = 2` real flags via a caller-supplied ledger
   lookup, replacing the original single-event trigger.
4. This module's output contract (`AdjustedCandidate` list) is designed to feed
   Phase 3's real `select_by_hybrid_score()` unchanged, but that actual call-through
   wiring is not built here — Stage 6.10's job.
5. D3 (LLM-judge) is not implemented — no frozen, reproducible LLM server is
   available in this environment (see the D3 section below for what would be
   required if one becomes available).

## D0–D4 Framework (2026-09-14 semantic-escalation follow-up)

Per explicit instruction, the lexical mechanism is treated as a baseline, not
automatically the final defense. The full framework:

> **The two open questions this section raises (per-metric threshold
> calibration, and whether single-pool consensus is fundamentally sufficient
> at all) are formally tracked as Items 1 and 2 in
> [`STAGE_6_9_QUEUE.md`](STAGE_6_9_QUEUE.md), not left as loose ends.** This
> document's own conclusion is not revised by that queue — the queue is where
> the follow-up work is scoped, this document is where the 6.6 record stands.

| Variant | What it is | Status |
|---|---|---|
| D0 | No defense (raw candidate scores unchanged) | Implicit — any `RetrievalCandidate` list with no `evaluate_retrieval_defense()` call |
| D1 | Lexical (Jaccard) consensus, dedup-dampened | Implemented, tested (`signals.py`, default `divergence_fn`) |
| D2 | Semantic (embedding cosine) consensus, same dampening core | Implemented, tested (`embedding_signals.py`, `semantic_divergence_fn`) |
| D3 | LLM-judge consensus | **Not implemented** — see below |
| D4 | Combined/full-lifecycle | Deferred to Stage 6.9 (ablation framework), out of scope for a single-stage retrofit |

### D2 — what was actually found (corrected 2026-09-14)

An earlier version of this document and its tests claimed semantic embeddings
"correctly identify the paraphrased poison as the majority." **That claim was
wrong** and has been corrected in the test suite
(`test_semantic_vs_lexical_consensus.py`) and here. What is actually true,
verified with the real, locally-cached `sentence-transformers/all-MiniLM-L6-v2`
model (the same model Phase 3's own hybrid rerank and AgentPoison's real attack
already use):

1. **Mechanism-level improvement, verified real**: the three paraphrased poison
   records — which never cluster under lexical Jaccard (pairwise similarity
   0.54–0.67, below the 0.7 threshold) — DO correctly cluster under semantic
   cosine similarity (pairwise 0.919–0.941, comfortably above a 0.85 threshold),
   while the true, unrelated fact stays separate (0.134–0.156 similarity to the
   poison cluster). This is checked directly against cluster membership, not
   inferred from a downstream score.
2. **Quantified improvement, verified real**: dampening measurably increases the
   poison cluster's own apparent divergence relative to the undamped baseline
   (0.33 → 0.44 average, at the shipped `dampening_exponent=0.5`) — the same
   qualitative narrowing effect found for the lexical mechanism.
3. **Decision-layer outcome — does NOT flip, and this is a real, structural
   finding, not an implementation gap**: for a two-cluster pool (3 planted vs. 1
   true, unrelated-topic minority), dampening can mathematically only discount a
   *multi-member* cluster's own internal similarity inflation — it cannot reduce
   a *singleton's* divergence score at all, because every term in that
   singleton's weighted average shares the same weight and the weight cancels
   out. A parameter sweep confirmed poison only overtakes truth's fixed
   divergence at an extreme dampening exponent (~5, vs. the shipped 0.5) that
   would break genuine-majority trust elsewhere. `test_semantic_consensus_guard.py`
   confirms this holds at the actual decision layer too: swapping
   `divergence_fn` from lexical to semantic, with the same
   `THRESHOLD_DOWNRANK=0.6`, produces the SAME qualitative outcome (truth
   downranked, poison untouched) for this content.
4. **Implication**: realizing a decision-layer benefit from the semantic metric
   is not automatic from the metric swap alone — it would require
   metric-specific threshold calibration (the 0.6 threshold was chosen with
   reference only to the lexical score distribution) and/or a fundamentally
   different aggregation than single-pool dedup dampening (e.g., corroboration
   from OUTSIDE the current candidate pool — the trusted memory store at large —
   which no per-query pool-only mechanism, lexical or semantic, can provide by
   construction). This is carried forward as an open Stage 6.9 item, not
   resolved here. **Update (2026-09-17): the threshold-calibration half was
   resolved** — `THRESHOLD_DOWNRANK` is now `0.3` (was `0.6`), adopted from
   Stage 6.9's own dev-corpus sweep; see `docs/phase6/DEFENSE_COMPOSITION_AND_
   ABLATION.md` Section 3 and `PHASE6_RESULTS.md` Section 9 for the real,
   measured effect. The cross-pool-corroboration idea remains unresolved.

### D2 — measured cost (real, not estimated)

On this environment (CPU, no GPU used by the measurement): model load is a
one-time ~11s cost, amortized across a process's lifetime via the module-level
cache (`_get_model()`). Per-pool `encode()` cost for a 4-sentence pool measured
~0.31s cold (first call after load) and ~0.017s warm (subsequent calls) —
non-negligible compared to lexical Jaccard's effectively-instant computation, and
a real, disclosed cost that Stage 6.12's full cost/latency accounting must
include if D2 is used in a live pipeline, not amortized away.

### D2 — what was checked vs. what remains open

Checked directly, with real measurements: mechanism-level clustering
correctness, quantified dampening effect, decision-layer outcome (unchanged for
this content), reproducibility (byte-identical divergence scores across
repeated calls), a benign uniform pool (no false flag), and one semantic-
camouflage case (an opposite-meaning sentence sharing surface vocabulary is
correctly scored as more divergent than the group it lexically resembles).

**Not checked, and explicitly not claimed**: false-positive rate across a real,
sized benign corpus (only single spot-checks were run); cross-attack
generalization; held-out attack performance; and whether a recalibrated
threshold and/or a stronger cross-pool corroboration mechanism would close the
decision-layer gap found in point 3 above. These require Stage 6.9/6.10's real
campaign infrastructure, not a single-stage retrofit.

### D3 — LLM-judge, not implemented, and why

A-MemGuard's real mechanism is an LLM-as-judge consensus check (Track A.5 of
`DEFENSE_LITERATURE_AUDIT.md`). This stage does not implement or exercise a
live LLM-judge variant, for the same reason this project's own A-MEM real-vendor
tests self-report `NOT_VALIDATED` rather than a fabricated pass (Methodology
Section 19.5): there is no frozen, pinned, identity-verified local LLM server
available in this tool environment to call reproducibly. Building an executable
D3 module against a mocked or ad hoc LLM call would risk exactly what Rule 15
forbids — reporting an unavailable capability as validated. Building an
unexercised interface with no real test to back it would risk being mistaken for
tested capability later. Neither is done here.

**What D3 would require, if a suitable environment becomes available** (frozen
per explicit instruction, ready to implement against): a pinned model identity
and version string; a frozen prompt template (verbatim, versioned, quoted in
documentation the way `Appendix A` of the Methodology Draft quotes Phase 3's
real prompts); frozen `temperature`/generation parameters; a persisted
`policy_version`-style config fingerprint on every judge decision; the same
evaluator-only leakage guard every other signal in this project uses (no
ground-truth label ever in the judge's prompt); and a real, measured latency/
token-cost accounting per call. This is a specification, not a claim of
readiness.

## Verdict

**PASS** as a 6.6 deliverable. Of the three original limitations: escalation
evidence-accumulation is genuinely fixed; the coordinated-poisoning weakness has
a real, quantified (if narrower-than-first-claimed, and corrected once that was
discovered) mitigation at the mechanism level, with an honestly disclosed
decision-layer gap; and the lexical-vs-semantic question was escalated to a real,
separately-evaluable D2 built on an actual embedding model rather than left
permanently unresolved, with its comparison against D1 measured rather than
assumed — including catching and correcting a wrong claim in an earlier draft of
this same work, rather than letting it stand.
