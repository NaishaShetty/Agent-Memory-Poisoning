# Phase 7 Plan — Propagation Monitoring

Status: PROPOSED, not yet started. Written 2026-09-16. Supersedes nothing; inherits
from `PHASE5_HANDOFF_REPORT.md` (repository root, §5), `phase5/wiring/lineage.py`,
`phase3/evaluation/foundations/taint_propagation.py`,
`phase6/defense/propagation/{signals.py,containment_guard.py}`, and Attribution's
`ATTRIBUTION_PROPAGATION` / `ATTRIBUTION_INFLUENCE` question types.

This document is explicitly **not** part of the Methodology Draft. It is a planning
artifact for a stage of work that has not yet been executed, written in the same
charter style as `docs/phase6/PHASE6_CHARTER.md` so that when Phase 7 is actually
built, it can be evaluated against a pre-committed plan the way Phase 6 was.

---

## 1. Research Question

> Once a poisoned memory is admitted, does its influence stay localized (one retrieval,
> one bad answer) or does it spread — through retrieval, reasoning, memory updates, or
> newly created memories — into a growing footprint across the memory store? And when
> it spreads, does it do so in ways that are structurally abnormal or self-reinforcing,
> as distinct from ordinary benign memory growth?

Phase 6 asked whether a defense can catch a poisoned memory at a lifecycle stage.
Phase 7 asks a different question: **after** admission (whether or not a Phase 6
defense caught it), what does the *shape* of its downstream influence look like over
time, across many memories and many tasks — not as a single before/after admission
decision, but as a graph-wide, longitudinal pattern. Phase 6's `containment_guard.py`
evaluates one descendant's ancestor chain at admission/retrieval time and cannot see
the aggregate picture. Phase 7 is the aggregate picture.

## 2. Why This Is Not Already Covered

This project already has real, frozen infrastructure that Phase 7 must reuse rather
than reinvent, and it is important to be precise about the boundary between "already
exists" and "Phase 7's actual job":

| Already exists | What it does | What it does NOT do |
|---|---|---|
| `phase5/wiring/lineage.py` (`MemoryInteractionEdge`, `derive_*_edges()`) | Builds a typed, evidence-tagged edge set between memories/decisions (`DERIVED_FROM`, `PRODUCED`, `SUPERSEDES`, `INFLUENCED`, `PROPAGATED_TO`, `REFERENCES`, `RETRIEVED_WITH`, `SELECTED_WITH`, `USED_BY`) | Aggregate graph-wide pattern detection across many memories/runs; it produces edges, not a monitored signal over time |
| `phase3/evaluation/foundations/taint_propagation.py::tainted_memories()` | Pure lineage-reachability (BFS/DFS) from a poisoned ancestor to descendants | Any notion of *rate*, *volume*, or *shape* of spread — it answers "is X reachable from poison Y," not "how many descendants, how fast, how branched" |
| `phase6/defense/propagation/signals.py::lineage_taint_signal()` | Per-descendant severity × distance-decay × content-retention score, `max()` over ancestors | Any signal about *multiple* descendants of the same ancestor considered together (crowding, fan-out) |
| `phase6/defense/propagation/containment_guard.py` | Single-descendant admission-time containment decision (caps at QUARANTINE) | Detecting the pattern *across* descendants or over time; it is intentionally single-hop-scoped |
| `attribution/schema.py` (`ATTRIBUTION_PROPAGATION`, `ATTRIBUTION_LINEAGE`) | Multi-hop lineage path for one attack→descendant query, on request | A standing monitor that watches the whole graph and flags abnormal regions unprompted |

Phase 7's job, stated precisely: **build a monitor that consumes the existing lineage
graph and taint signal as inputs, and adds the missing layer — aggregate, longitudinal,
cross-memory pattern detection — without re-deriving provenance edges or re-litigating
what counts as evidence.** Every edge Phase 7 reasons about must already carry one of
the four frozen evidence kinds (`OBSERVED_EVENT`, `EXPOSURE_ONLY`,
`COUNTERFACTUAL_EVIDENCE`, `LINEAGE_REACHABILITY`); Phase 7 does not invent a fifth.

## 3. The Named, Already-Disclosed Gap This Phase Targets

`PHASE5_HANDOFF_REPORT.md` §5 already names this open question directly: *"FARMA's
amplification cluster crowded out 8 of 8 top-8 slots in one real trial. What, if
anything, should contain volume-based crowding?"* This is a real, observed phenomenon
in this project's own data (not a hypothetical), and it is exactly the shape of thing
Phase 7 exists to formalize and measure systematically rather than note once and move
on. FARMA's own design (`phase4/attacks/farma/`) is described in this project's own
docs as "amplification/self-reinforcement" — a poisoned memory that, once retrieved and
reasoned over, produces new memories that are themselves more retrievable, which get
retrieved and produce more such memories. That is a self-reinforcing propagation
pattern by construction, and it is currently unmeasured as a *pattern* (only Phase 4's
per-trial success/failure outcome is measured).

## 4. What Phase 7 Adds — Three New Concepts

Phase 6 added exactly one new concept (a security lifecycle). Phase 7 adds three,
kept deliberately narrow:

1. **Propagation footprint** — for a given poisoned memory (or admission event), the
   set of all memories/decisions reachable from it via the existing `lineage.py` edge
   types, partitioned by evidence kind, as a function of wall-clock/task-index time
   (not just a final static set). This is a longitudinal view of something
   `taint_propagation.py` currently only answers as a point-in-time reachability set.
2. **Propagation-shape signals** — a small set of graph-structural measurements over
   the footprint, computed per poisoned-memory root, not per single descendant:
   - **Fan-out rate**: number of new `DERIVED_FROM`/`PRODUCED` edges originating from
     any memory in the footprint, per unit time or per task processed.
   - **Re-entry rate**: fraction of retrieval events (`RETRIEVED_WITH`/`SELECTED_WITH`)
     in a task whose top-K pool contains 2+ members of the same footprint
     simultaneously — a direct, measurable formalization of the "8 of 8 slots" crowding
     observation above.
   - **Cycle/reinforcement depth**: longest chain of `DERIVED_FROM` → `USED_BY` →
     `DERIVED_FROM` edges within the footprint (a memory descended from the poison
     being used to produce another memory that is *also* in the footprint) — the
     closest graph-native definition of "self-reinforcing" available from real,
     already-collected edge types, without inventing a new one.
   - **Cross-task bleed**: whether the footprint spans more than one
     task_id/episode_id (per `phase5/identity/run_identity.py`'s episode concept) —
     distinguishes contained, single-task influence from cross-session spread.
3. **Abnormality baseline** — every one of the four signals above must be computed
   identically over **benign** memory growth (no attack present) in the same corpus,
   so "abnormal" is a comparison against a measured benign distribution, never an
   arbitrary threshold invented for this phase. This directly follows this project's
   own established discipline (e.g. Phase 6's B0 no-defense control, Phase 3's
   Condition A no-memory baseline) of never reporting a detection number without its
   corresponding false-positive-on-benign-behavior number alongside it.

None of these three concepts replace or modify `lineage.py`, `taint_propagation.py`,
or `containment_guard.py` — they are read-only consumers layered on top, exactly as
Attribution is a read-only consumer of the canonical event ledger.

## 5. Inherited Constraints (frozen, carried over unchanged)

- **The evaluator-only / legitimate boundary** (`phase3/evaluation/contracts/boundary.py`,
  `FORBIDDEN_KEYS`) — a propagation monitor is, by construction, a Phase 5/Attribution-
  style **post-hoc analytical layer**, not a runtime defense decision. It may freely
  consume `attack_id`/ground-truth labels for its own **evaluation** (measuring whether
  it correctly flagged real poisoned footprints), the same way Attribution and Phase 5's
  own validation suite do — but if any part of Phase 7 is later wired into a live
  defense signal (e.g., feeding `containment_guard.py`), that specific wiring must
  re-apply the Phase 6 boundary from scratch. This charter does not pre-authorize that
  wiring.
- **Evidence-kind discipline** (§18.7 vocabulary) — every propagation-shape signal
  must cite which evidence kind(s) its underlying edges carry. A fan-out count built
  from `LINEAGE_REACHABILITY` edges is a *reachability* footprint, not a
  *counterfactual-influence* footprint, and must be labeled as such — mirroring
  Attribution's own refusal to invent a confidence score on top of discrete evidence
  (§2 above).
- **`LIFECYCLE_STATUS_UNKNOWN_VERSIONING_GAP`** (frozen Phase 3 defect,
  `phase3/evaluation/foundations/taint_propagation.py`) — inherited as-is. Because
  every genuinely tainted descendant hits this status by construction
  (`memory_versioning.reconstruct_version_history()` cannot distinguish a `derived`
  event's target from its sources), any Phase 7 signal that depends on a memory's
  *current version* rather than its *existence in the footprint* will be systematically
  degraded for exactly the memories Phase 7 most cares about. Phase 7 must either (a)
  route around `get_current_version()` entirely for footprint construction (using raw
  `derived`/`PRODUCED` events instead, which do not depend on version reconstruction),
  or (b) explicitly disclose every signal that cannot be computed because of this gap,
  the same way Phase 5/6 already disclose it rather than silently degrade. Repairing
  the gap itself remains explicitly out of scope (inherited from Phase 6 §8).
- **Paraphrase/content-drift evasion** (`docs/phase6/ADAPTIVE_ATTACKER_KNOWLEDGE.md`,
  taint score 0.091 under paraphrase) — `lineage_taint_signal()`'s content-retention
  term is Jaccard-based and already disclosed as defeatable by paraphrase. Phase 7's
  fan-out/re-entry/cycle-depth signals are structural (edge-count-based), not
  content-similarity-based, and so are not subject to this exact evasion — but this
  must be verified empirically (Stage 7.x below), not assumed, since a sufficiently
  adaptive attacker could also try to keep fan-out low per hop while still achieving
  wide reach (many shallow trees instead of one deep chain).
- **Frozen attacks and V3-Hybrid** — Phase 7 observes the seven real attacks and the
  real agent runtime exactly as Phase 4/6 do; it does not modify them to make
  propagation "more visible."

## 6. Explicit Out-of-Scope for Phase 7 v1

- Any new defense/intervention mechanism. Phase 7 is a **monitor**, not a defense —
  it may recommend where a future D4-style intervention would attach, but does not
  itself block, quarantine, or modify anything. (A defense that *acts* on these
  signals would be a Phase 6 extension or a Phase 8, not Phase 7.)
- Repairing `LIFECYCLE_STATUS_UNKNOWN_VERSIONING_GAP` (see §5).
- Real A-MEM note-evolution propagation (`RealAMemAdapter.process_memory()`) as a
  live channel, since it is `MODEL_DEPENDENT` and does not exercise real evolution
  in this environment (no reachable LLM backend for `should_evolve` decisions per the
  A-MEM adapter's own disclosed behavior). Phase 7 may still analyze `MemoryNote.links`
  as a **static, already-stored** relationship channel (real, not dependent on a live
  call), but cannot claim to observe live note-evolution propagation without a reachable
  backend — if one is available at execution time, this should be revisited, not
  silently assumed absent.
- A statistically definitive claim that any specific attack is "the most
  self-reinforcing." Phase 7 will report the four signals per attack with confidence
  intervals over however many trials are actually run, honestly, mirroring the
  Methodology's own treatment of small-sample findings (§12.16, §12.18) rather than
  overclaiming a ranking from a handful of trials.
- Unifying this with Attribution's six question types into a seventh. Phase 7 consumes
  `ATTRIBUTION_PROPAGATION`/`ATTRIBUTION_LINEAGE` outputs as one input source; it does
  not add a new attribution question type of its own.

## 7. Proposed Stage Breakdown

Mirroring the granularity of Phase 5/6's own stage numbering (for continuity, not
because a specific stage count is load-bearing):

- **7.1 — Charter & Scope** (this document). Cross-check against actual code (not
  just prior docs), same acceptance discipline as Phase 6 §9.
- **7.2 — Footprint Construction**: implement `build_propagation_footprint(root_memory_id)`
  as a thin, read-only wrapper composing `lineage.py`'s existing `derive_*_edges()`
  functions plus `phase5/wiring/trace_assembly.py::build_propagation_graph()`
  (already referenced in `docs/phase6/DEFENSE_SCOPE_MATRIX.md`) into one longitudinal,
  timestamped structure per root. No new edge-derivation logic — pure composition of
  what already exists.
- **7.3 — Benign Baseline**: run footprint construction over a benign-only corpus
  (no attacks present, or attacks present but their footprint excluded) to establish
  the four signals' natural distribution during ordinary memory growth (consolidation,
  legitimate cross-referencing, A-MEM's real `find_related_memories()` linking). This
  must exist before any "abnormal" threshold is proposed (§4, point 3).
- **7.4 — Signal Implementation**: implement fan-out rate, re-entry rate, cycle/
  reinforcement depth, and cross-task bleed as pure functions over a footprint object
  from 7.2, each returning its value plus the evidence-kind(s) it is built from.
- **7.5 — Per-Attack Footprint Study**: run 7.2–7.4 against real, already-stored
  trial data for each of the seven frozen attacks (reusing existing Phase 4 campaign
  artifacts and Phase 5 event ledgers where already collected; only running new trials
  for attacks whose stored artifacts do not already contain enough downstream
  derived/produced events to build a non-trivial footprint — likely FARMA and
  MemoryGraft first, given their own design descriptions already suggest
  multi-generation memory chains, and A-MEM-adjacent conditions for
  `find_related_memories()`-based linking).
- **7.6 — Crowding Formalization**: specifically instrument and report the FARMA
  "8 of 8 top-K slots" phenomenon named in `PHASE5_HANDOFF_REPORT.md` §5 using the
  re-entry-rate signal, closing that named open question with a real measurement
  rather than a single anecdotal trial.
- **7.7 — Adaptive-Evasion Check**: test whether the structural (non-content-based)
  signals resist the same paraphrase-style evasion already documented against
  `lineage_taint_signal()`'s content-retention term (§5), and separately test a
  "shallow-and-wide" adaptive variant (many independent short chains instead of one
  deep chain) against fan-out/cycle-depth specifically, since these signals were not
  designed with that adversary in mind and must not be assumed robust to it without
  a real check.
- **7.8 — Reporting & Limitations**: write results with the same evidence-kind
  labeling and honest-limitations discipline used throughout Phases 5–6 (explicit
  section on what the versioning gap prevents measuring, what the A-MEM
  model-dependent gap prevents observing live, and what sample sizes actually
  support statistically).

## 8. Acceptance Criteria for 7.1

7.1 PASSES when:
1. This plan is internally consistent with the actual current state of
   `phase5/wiring/lineage.py`, `phase3/evaluation/foundations/taint_propagation.py`,
   and `phase6/defense/propagation/*` (spot-checked against real code, not prior
   documentation alone — done for this draft; function/class names above were
   confirmed to exist as named).
2. Every new signal proposed (§4, point 2) is stated in terms of edge types and
   evidence kinds that already exist — no new edge type or evidence kind is invented
   without explicit justification here (none was needed).
3. The named, pre-existing open question this phase targets (§3) is quoted from its
   real source rather than paraphrased into something stronger than the source
   actually claims.
4. No frozen file (Phase 3–6, Attribution) is modified to produce this plan or would
   need to be modified to begin 7.2.

## 9. Verdict

**7.1 — PROPOSED / NOT YET STARTED.** This document is a plan for future work, not a
record of work performed. It should be revisited and re-verified against the codebase
immediately before Phase 7 execution begins, since Phases 5 and 6 continued to evolve
(e.g. the UNASSESSED-default fix, the corpus scale-up) after their own charters were
first written — the same should be expected here.
