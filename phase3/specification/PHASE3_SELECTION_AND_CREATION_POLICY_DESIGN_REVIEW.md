# Selection Policy & Creation Policy — Design Review (Pre-Implementation)

Status: **DESIGN REVIEW — NOT IMPLEMENTED.** Written while the full 120×2 dataset
campaign runs in the background, at the user's explicit request to start reviewing
these two deliberately-deferred items now, design-only. **Nothing below should be
implemented until reviewed and either approved, amended, or rejected.** Mirrors the
process `PHASE3_PROVENANCE_GRAPH_DESIGN_REVIEW.md` should have followed from the start
— review first, implement only after a decision is recorded.

Both items remain exactly as deferred: `memory_schema.md §8` and
`relationship_schema.md §5` both explicitly leave these unfrozen, and the current
provisional behavior (`runner.py::select_from_retrieved()`'s identity-slice; no
creation-policy code exists anywhere) stays untouched by this document.

## 1. Why these two, and why they're linked

Both are instances of the same underlying gap: **"decide whether two things are
similar/relevant enough to matter"** — for selection, whether a retrieved candidate is
relevant enough to keep; for creation, whether two memories are similar/contradictory
enough to link. Both require a real similarity/relevance MECHANISM (not just a
threshold number) that does not exist anywhere in this codebase today as a
benchmark-owned utility — every embedding computation that exists right now lives
*inside* a foundation adapter (Mem0/A-MEM each independently load
`sentence-transformers/all-MiniLM-L6-v2`), not as something `phase3/evaluation` itself
owns and can call directly. That absence is the first real design fork for both items
(§2.1, §3.1 below).

## 2. Selection policy

### 2.1 The core fork: reuse a foundation's embeddings, or own a benchmark-level mechanism

**Option A — reuse the foundation's own ranking.** `foundation.retrieve()` already
returns candidates in *some* order (each foundation's own internal similarity ranking).
A selection policy could simply threshold or truncate that existing order (e.g. "keep
items whose foundation-reported score exceeds threshold T," where available) —
zero new infrastructure, but couples the selection policy's behavior to whatever each
foundation's internal ranking already does, which differs between Mem0 and A-MEM
(different embedding pipelines, different internal scoring) — a same-named "selection
policy" would not actually behave identically across foundations, which sits awkwardly
against `CLEAN_AGENT_INTERFACES.md`'s layer-separation principle (retrieval and
selection are supposed to be separable stages, not entangled with foundation-internal
scoring quirks).

**Option B — a benchmark-owned reranking/selection mechanism.** Retrieve a genuinely
larger candidate pool (`retrieve(top_k=N)`, N > the eventual selection size) then apply
one, single, foundation-independent mechanism on top — e.g. compute cosine similarity
between the task prompt and each candidate's content using ONE pinned model
(`sentence-transformers/all-MiniLM-L6-v2`, already used by both foundations, so no new
model dependency — only a new *use* of it, owned by `phase3/evaluation` directly rather
than borrowed from inside an adapter), keep the top-k by that score. This makes
"selection" mean the same thing regardless of foundation, and is what makes
`rejected` events start actually firing (today's near-vacuity, documented in
`canonical_wiring.py`'s own comment, is a direct consequence of `retrieve()` and
`select_from_retrieved()` both capping at the same `top_k` — Option B breaks that
coupling by construction: retrieve N, select k < N).

**Recommendation: Option B.** It is the only one of the two that makes "selection" a
real, comparable, foundation-independent stage — which is also exactly what
`PHASE4_INTERFACE_REQUIREMENTS.md §3`'s "Selection influence analysis" capability
needs (manipulating what gets selected, independent of which foundation is under
test). Cost: one new, small, benchmark-owned similarity utility; a decision on where
`retrieve(top_k=N)`'s N comes from (see §2.3).

### 2.2 What counts as "relevant enough" — threshold vs. fixed-k

Two sub-options once Option B is chosen:

- **Fixed-k top-k-by-score** (like today, but now over a real score instead of
  retrieval order) — deterministic, simple, but never actually rejects anything for a
  task with fewer than k genuinely-relevant candidates (a low-relevance candidate still
  gets selected if the pool has fewer than k items) — same shape of vacuity risk as
  today, just moved.
- **Threshold-based, size-varying selection** — keep everything above similarity
  threshold T, capped at some maximum k' as a safety bound. Produces genuine
  `rejected` events for irrelevant candidates AND allows zero-selection on a task with
  no relevant memory — a real, meaningful "the pool had nothing good enough" case,
  which fixed-k can never represent.

**Recommendation: threshold-based, capped.** Fixed-k dresses up "we always pick
something" as a policy; threshold-based is the only one of the two that can produce a
genuine `NO_SELECTED_EVIDENCE` observation (`agent/diagnostics.py`'s own
`UTILIZATION_NO_SELECTED_EVIDENCE` category already exists for exactly this — currently
unreachable in real data because nothing ever selects zero). **Open question for you**:
the actual threshold value is a genuine empirical/research decision (calibrated against
what? LoCoMo's own gold-evidence similarity distribution? A fixed literature-typical
cosine cutoff like 0.5–0.7?) — this document does not propose a number, since picking
one without empirical calibration would be exactly the kind of premature, unreviewed
commitment this whole exercise exists to avoid.

### 2.3 Retrieval pool size N vs. selection size k

Needs its own value, decoupled from `top_k=5` (today's single, conflated parameter).
Proposal: introduce `retrieval_pool_size` (N, e.g. 15–20) as a new, explicit
`RunConfigRecord` field alongside the existing `retrieval_k`, so the *canonical*
retrieval-configuration record (H.4-F) — already the right place, already
fingerprinted, already resolvable per event — carries this without inventing a second
config mechanism. `retrieval_k` keeps meaning "how many were returned by
`foundation.retrieve()`", reinterpreted at pool size N; the NEW selection stage then
narrows N down to the real selected set by threshold (§2.2). **Open question for you**:
does N vary per foundation/dataset, or should it be one fixed value across the whole
benchmark for comparability? (Recommendation: one fixed value — matches this session's
general preference for configuration uniformity across the Mem0/A-MEM comparison
established during the n=20 counterfactual work.)

### 2.4 Determinism / reproducibility

Cosine similarity over a pinned embedding model is fully deterministic (same
`REPRODUCIBILITY_CONTRACT.md §3` guarantee `EnvironmentRecord` already extends to
everything else this session built) — no new nondeterminism risk from Option B, unlike
an LLM-judge-based selection mechanism would introduce (not proposed here for exactly
that reason).

## 3. Creation policy (populates `relationship_detected`)

### 3.1 Same core fork as selection: mechanism ownership

Same Option A/B fork as §2.1, same recommendation (Option B — a benchmark-owned
mechanism, not something borrowed from inside a foundation adapter) for the same
reason: `equivalent_to`/`conflicts_with` detection needs to mean the same thing
regardless of which foundation ingested the memory, since `relationship_schema.md`'s
`relationship_detected` event is itself foundation-independent (it lives entirely in
the canonical event ledger, never in a foundation's own store).

### 3.2 Two distinct sub-mechanisms, not one

`relationship_type` covers three values, but `superseded_by` is different in kind from
the other two:

- **`superseded_by`** — already has a real, frozen ACTION mechanism
  (`memory_versioning.py`'s `supersede_memory()`, exercised for real this session via
  H.3-R/H.3-R2). What's missing is only the DETECTION-side `relationship_detected`
  event that should fire *before* (or independent of) that action — `relationship_
  schema.md §3.2`'s own note that "detection may occur without the corresponding
  action ever being taken" is the precedent here. This is the SMALLER, more tractable
  half of the creation policy: whenever `supersede_memory()` is actually called, emit a
  `relationship_detected(superseded_by)` event alongside it, using
  `mechanism="explicit_supersession_call"` (a legitimate, already-real "mechanism" —
  no similarity threshold needed, since supersession here is always an explicit,
  already-decided action, never a discovered candidate).
- **`equivalent_to`/`conflicts_with`** — genuinely need a NEW discovery mechanism (no
  existing call site decides these today). This is the substantial, genuinely novel
  research decision: `equivalent_to` plausibly reuses the same cosine-similarity
  mechanism §2 proposes for selection (very high similarity ⇒ likely equivalent);
  `conflicts_with` is qualitatively harder — cosine similarity cannot distinguish "these
  two memories are near-duplicates" from "these two memories are on the same topic but
  contradict each other" (e.g. "the meeting is on Tuesday" vs. "the meeting is on
  Wednesday" score as SIMILAR by embedding distance, not dissimilar, despite being
  contradictory) — a real contradiction detector needs either an NLI
  (natural-language-inference) model or an LLM-judge call, both of which are new
  dependencies/nondeterminism this codebase does not currently carry anywhere in its
  benchmark-owned (non-adapter) code.

**Recommendation: split the work exactly along this line.** Wire the `superseded_by`
detection event now (small, mechanical, reuses an already-frozen, already-tested
action) as a NON-controversial, purely-additive extension — it requires no new
research decision, just an event emission at an existing call site. Leave
`equivalent_to`/`conflicts_with` detection fully deferred — that is where the genuine,
unfrozen research decision actually lives, not in the supersession half.

**Open question for you**: do you want the `superseded_by`-detection half implemented
now (it is not actually a novel research decision, just a missing event emission at an
existing, frozen call site), while `equivalent_to`/`conflicts_with` stays deferred? Or
should the whole creation policy stay untouched as one unit until you're ready to
decide the harder half too? This document takes no position by defaulting either way —
flagging it because splitting it is a real, available option this review surfaced,
not because either half is obviously right for you to pick now.

### 3.3 When creation-policy detection would run

If §3.2's harder half is ever built: at ingestion time (checked against every
already-ingested memory in the same pool — O(pool_size) per new memory, tractable at
LoCoMo's pool sizes of 10–47) vs. as a periodic/batch scan (decouples detection latency
from ingestion, but introduces a "detection lag" state that doesn't exist today).
**Recommendation, if/when built: ingestion-time**, matching this benchmark's existing
preference for synchronous, immediately-observable state (every other event this
session wired — retrieved/selected/rejected — fires synchronously within the same task
execution, never deferred to a batch job).

## 4. What this review deliberately does not do

- Does not propose a numeric similarity/conflict threshold (§2.2) — an empirical
  calibration decision, not a design-structure decision.
- Does not implement `equivalent_to`/`conflicts_with` detection, or decide its exact
  mechanism (NLI model choice, LLM-judge prompt) — flagged in §3.2 as the one piece
  that remains genuinely, substantially unfrozen research work.
- Does not touch `runner.py`, `memory_versioning.py`, or any frozen-adjacent file.

## 5. Summary of what needs your decision before any implementation

1. **§2.1** — selection mechanism ownership: Option A (reuse foundation ranking) vs.
   Option B (benchmark-owned cosine-similarity reranking). Recommendation: B.
2. **§2.2** — fixed-k vs. threshold-based selection. Recommendation: threshold-based.
   Requires a real threshold value, which requires empirical calibration this document
   does not attempt.
3. **§2.3** — retrieval pool size N: fixed benchmark-wide value or per-foundation/
   dataset. Recommendation: fixed.
4. **§3.2** — split the creation policy: build the `superseded_by`-detection half now
   (non-controversial, reuses `supersede_memory()`), leave `equivalent_to`/
   `conflicts_with` deferred? Or keep the whole thing untouched as one unit?

Nothing here is implemented. If/when you're ready to decide any of these, the next
step (matching the graph's own corrected process) is: you decide, then a mission brief
gets written for exactly the scope you approved, then implementation follows.
