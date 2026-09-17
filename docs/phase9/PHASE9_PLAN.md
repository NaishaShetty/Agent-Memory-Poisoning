# Phase 9 Plan — Attack-Origin Attribution & Forensics

Status: DRAFT, written before the implementation it governs, per this project's own
standing discipline (see `attribution/ATTRIBUTION_METHODOLOGY.md`'s own opening line).
Finalized once the implementation and its real test scenarios validate against it; any
change forced by implementation reality is reconciled here explicitly, not silently.

## 1. Research Question

*"Once a defense signal or propagation-monitoring signal flags suspicious behavior, can
we automatically reconstruct — backward, from the flagged action to the original
poisoned memory — the real chain of evidence that explains how the attack entered the
system, while explicitly reporting when that chain cannot be determined with full
confidence?"*

This is a **forensics** question, not a detection or defense question: Phase 9 never
decides whether something is an attack (Phase 6's job) or monitors how it spread (Phase
7's job). It answers, after the fact and on demand, *"where did this come from, and how
sure are we?"*

## 2. Why This Is Not Already Fully Covered

This phase does **not** start from zero. A substantial, already-built, already-tested
analytical layer exists and must be reused, not reinvented:

| Existing capability | Where | What it answers |
|---|---|---|
| `attribute_origin()` | `attribution/wiring/origin.py` | Which attack (if any) produced this memory directly? |
| `attribute_lineage(..., full_chain=True/False)` | `attribution/wiring/lineage.py` | This memory's real ancestor chain — one hop, or the complete graph, including honest `MULTIPLE_POSSIBLE_SOURCES` reporting for a diamond-shaped ancestry |
| `attribute_propagation()` | `attribution/wiring/propagation.py` | Which attack-tainted memories (if any) is this memory reachable from? |
| `attribute_exposure()` | `attribution/wiring/exposure.py` | Was this memory exposed to a given decision? |
| `attribute_action()` | `attribution/wiring/action.py` | Resolves an `agent_action` to its decision, delegates to EXPOSURE |
| `attribute_influence()` | `attribution/wiring/influence.py` | Is there a real counterfactual finding this memory influenced an outcome? |
| `attribute_references()` | `attribution/wiring/references.py` | Does this memory's content literally cite another real memory? |
| `attribute_memory()` (orchestrator) | `attribution/wiring/orchestrator.py` | Composes every applicable question type for ONE target |
| `explain_defense_mitigation()` | `phase6/defense/attribution_bridge/report.py` | Narrates what a specific Phase 6 defense decision actually mitigated, using the orchestrator |
| Closed uncertainty vocabulary | `attribution/schema.py` | `UNIQUE` / `MULTIPLE_POSSIBLE_SOURCES` / `INSUFFICIENT_EVIDENCE` / `NO_ATTACK_ORIGIN` / `NO_LINEAGE_ANCESTOR` / `*_ESTABLISHED` / `*_NOT_ESTABLISHED` — never a bare boolean, every status already forces an honest "don't know" or "not applicable" outcome where the evidence doesn't support more |
| Ground-truth metrics | `attribution/metrics.py` | `origin_attribution_accuracy`, `lineage_reconstruction_accuracy`, `ambiguity_rate`, `false_attribution_rate`, `influence_attribution_accuracy` — all computed only over caller-supplied real ground truth, never assumed |
| Campaign-level aggregation (edge-based AND now content-similarity-based) | `phase7/propagation/campaign_signals.py` | Groups attack roots that share structural edges, or — as of the 2026-09-17 extension — no edges but similar real content |

**The real, named gap Phase 9 exists to close**: every one of the above answers ONE
question about ONE target. Nothing today walks the chain *automatically* — starting from
a real, flagged incident (a Phase 6 `QUARANTINE`/`BLOCK` decision, or a Phase 7
propagation-monitoring alert) and composing EXPOSURE → LINEAGE (full chain) → ORIGIN →
PROPAGATION into one coherent, ordered forensic narrative with a single, honestly-derived
confidence verdict for the whole chain, not just per-hop status codes a human has to
mentally combine themselves.

## 3. The Named, Already-Disclosed Gaps This Phase Targets

1. **No automatic backward walk.** An analyst (or an automated report) must currently
   call `attribute_action()`, then manually take its exposed memory ids and call
   `attribute_lineage(full_chain=True)` on each, then `attribute_origin()` on whatever
   the lineage walk terminates at — by hand, per incident. There is no single function
   that performs this walk and returns one structured result.
2. **No chain-level confidence verdict.** `AttributionResult.status` is correct and
   honest per-hop, but a forensic reconstruction spanning 3–4 hops (action → decision →
   exposed memories → ancestors → origin) currently has no defined rule for what the
   COMBINED confidence of the whole chain is when, say, hop 2 is `UNIQUE` but hop 3 is
   `MULTIPLE_POSSIBLE_SOURCES`.
3. **No validated, whole-chain reconstruction against real campaigns.** Each attribution
   primitive is unit-tested against constructed scenarios (A–K) and the Phase 6 bridge is
   tested against 3 constructed scenarios — but no one has run the FULL backward chain
   against a real, live Phase 4 campaign end-to-end and confirmed it correctly points back
   to that campaign's own real, known origin memory (or correctly reports ambiguity where
   the real graph is genuinely ambiguous, e.g. FARMA's or MemoryGraft's real
   volume/self-reinforcement campaigns, which by design produce more than one plausible
   "first" memory).
4. **No forensic-report artifact.** `explain_defense_mitigation()`'s narrative is the
   closest existing analogue, but it explains one memory's mitigation story, not a
   multi-hop origin reconstruction with an evidence timeline an analyst could actually
   read and act on.

## 4. What Phase 9 Adds

### 9.1 — `ForensicReconstruction`: one new, composed, read-only result type

A new, frozen dataclass (tentatively `attribution/wiring/forensics.py`, or a new
top-level `forensics/` package if the composition logic grows large enough to warrant
its own home — decided during 9.1, not pre-judged here) representing one full backward
walk, built ENTIRELY from calls to the existing `attribute_*` functions above — no new
evidence-derivation logic, no new edge type, no new Phase 5 instrumentation. Candidate
shape:

```
ForensicReconstruction:
    triggering_target: (target_type, target_id)      # the flagged ACTION or DECISION
    exposure: AttributionResult                        # attribute_exposure()/attribute_action()'s own result
    per_memory_lineage: Dict[memory_id, AttributionResult]   # attribute_lineage(full_chain=True) per exposed memory
    per_memory_origin: Dict[memory_id, AttributionResult]    # attribute_origin() per terminal ancestor
    per_memory_propagation: Dict[memory_id, AttributionResult]  # attribute_propagation() per exposed memory
    chain_confidence: str        # a new, closed vocabulary — see 9.2
    narrative: str               # human-readable summary, same discipline as report.py's _build_narrative()
```

Every field is either a real, unmodified `AttributionResult` this layer already produces,
or a plain composition (dict/tuple) of them. `ForensicReconstruction` computes nothing
new about the underlying ledgers — it only walks and assembles.

### 9.2 — A closed, disclosed chain-confidence vocabulary

A new, explicit rule set (not an ML score, not a fabricated percentage) mapping the
COMBINATION of per-hop statuses to one whole-chain verdict. Proposed starting rules
(finalized during 9.1 against real scenarios, not assumed correct in advance):

| Whole-chain verdict | Rule |
|---|---|
| `SINGLE_ORIGIN_HIGH_CONFIDENCE` | Every hop in the walk is `UNIQUE`/`EXPOSURE_ESTABLISHED`, and the walk terminates in exactly one `attribute_origin()` result that is not `NO_ATTACK_ORIGIN` |
| `MULTIPLE_PLAUSIBLE_ORIGINS` | The walk terminates in more than one distinct real origin candidate — either because `attribute_lineage(full_chain=True)` itself reported `MULTIPLE_POSSIBLE_SOURCES` (a real diamond ancestry) or because more than one exposed memory has its own distinct, real origin |
| `NO_ATTACK_ORIGIN_FOUND` | Every terminal ancestor's `attribute_origin()` reports `NO_ATTACK_ORIGIN` — the exposed content is real, but nothing in it is attack-produced by this evidence |
| `INSUFFICIENT_EVIDENCE` | Any required hop itself reports `INSUFFICIENT_EVIDENCE`, or a target the walk needs (e.g. the triggering decision) does not exist in the ledger at all |

This is a disclosure mechanism, not a scoring model: it must never claim more confidence
than its worst constituent hop, and every `ForensicReconstruction.narrative` must name
WHICH hop, specifically, is responsible for a non-`SINGLE_ORIGIN_HIGH_CONFIDENCE`
verdict — mirroring `explain_defense_mitigation()`'s own "explicitly refuse the
inference, in words" discipline (Stage 6.13).

### 9.3 — Real entry points from Phase 6 and Phase 7

Two real, already-existing triggers this phase wires INTO (never modifies):
- A Phase 6 `MGPDecisionRecord` with `action in (QUARANTINE, BLOCK)` — its
  `candidate_memory_id` (or, once Stage 6.10's live-ledger wiring exists, the real
  `decision_id`/`action_id` that produced it) becomes a `ForensicReconstruction`'s
  `triggering_target`.
- A Phase 7 campaign-level signal exceeding whatever the caller judges "worth
  investigating" (e.g. a non-empty `campaign_content_similarity_clusters()` result, or a
  `campaign_re_entry_rate()` above some caller-chosen watch level) — its member memory
  ids become a batch of `ForensicReconstruction` targets.

Phase 9 does not invent a new alerting policy or threshold for "when to investigate" —
that decision remains the caller's (a human analyst, or a future orchestration layer),
consistent with this whole layer's read-only, post-hoc framing.

### 9.4 — Real, multi-attack validation of the WHOLE reconstruction

Run the full backward walk against each of the seven real Phase 4 attacks' own real,
live campaign data (reusing the same real ledger-building helpers `phase7/propagation/`
and `attribution/tests/` already use — `new_study_ledgers()`, `record_memory_creation()`,
`record_memory_derivation()`, the real frozen injectors), starting from a real, flagged
decision or a real downstream memory, and confirm:
- For attacks with one clean origin (Sleeper, AgentPoison, MPBench-PCFI, DSRM,
  MINJA): the reconstruction reaches `SINGLE_ORIGIN_HIGH_CONFIDENCE` and correctly names
  the real planted artifact's own memory id.
- For attacks whose real mechanism produces multiple plausible originating memories by
  DESIGN (FARMA's amplification cluster, MemoryGraft's volume-style repetition): the
  reconstruction correctly reports `MULTIPLE_PLAUSIBLE_ORIGINS`, naming every real
  candidate — never collapsed to one arbitrary "first" pick, and never silently
  reported as `SINGLE_ORIGIN_HIGH_CONFIDENCE` to make the report look cleaner than the
  evidence supports.
- For a genuinely benign flagged decision (a Phase 6 false positive from before this
  session's fixes, or a residual one after them): the reconstruction correctly reaches
  `NO_ATTACK_ORIGIN_FOUND`, and the narrative says so plainly rather than implying guilt
  by the mere fact that a reconstruction was run at all.

This is the single most important acceptance bar for this phase: **a forensic tool that
overclaims confidence on ambiguous real campaigns is worse than one that abstains.**

## 5. Inherited Constraints (frozen, carried over unchanged)

- **No Phase 3/4/5 file is modified.** Every `attribute_*` function, `derive_*` lineage
  function, and Phase 5 event/ledger primitive Phase 9 depends on is called verbatim,
  exactly as `attribution/` and `phase6/defense/attribution_bridge/` already do.
- **Read-only, always.** Nothing in Phase 9 blocks, quarantines, releases, or otherwise
  mutates any security state or ledger. `ForensicReconstruction` is a report, never a
  decision.
- **Never claim more than the evidence establishes** (the Attribution Methodology's own
  central standard, verbatim, inherited without modification). A `ForensicReconstruction`
  is exactly as trustworthy as the weakest `AttributionResult` it composes — never
  stronger, never "rounded up" for presentation.
- **Determinism.** Re-running a `ForensicReconstruction` against unchanged ledger state
  must produce a byte-identical result, mirroring `test_bridge_is_deterministic`-style
  checks already established for the Phase 6 bridge.
- **Ground truth only from the caller.** Any accuracy metric Phase 9 reports (e.g. "did
  the reconstruction name the REAL planted artifact") must be computed the same way
  `attribution/metrics.py` already insists on — over caller-supplied real ground truth,
  never inferred or assumed by the metric itself.

## 6. Explicit Out-of-Scope for Phase 9 v1

- **No new evidence-derivation function.** If a real forensic scenario needs an edge
  type Phase 5's lineage functions don't already derive, that is a Phase 5 gap to
  disclose, not a Phase 9 workaround to invent.
- **No automated "when to investigate" policy.** Phase 9 answers "given this incident,
  what's the real backward story," not "which incidents deserve investigation" — that
  remains a human/operational decision, same framing Phase 7 already uses for its own
  monitor-not-defense boundary.
- **No cross-run / cross-deployment attribution.** Scoped to one real run's ledger state,
  same boundary every other Phase 5/6/7/Attribution component already carries.
- **No natural-language generation beyond a templated narrative.** `narrative` is
  composed from real field values via string templates (same discipline as
  `_build_narrative()`), never an LLM call — this stays a deterministic, auditable report,
  not a generated one.
- **No new confidence SCORE (a float/probability).** The chain-confidence vocabulary in
  §4.2 is a closed set of named, rule-derived verdicts, not a numeric estimate — inventing
  a probability with no real calibration data behind it would violate this project's own
  "never fabricate a number" discipline more directly than any prior phase's thresholds
  did, since those were at least disclosed as uncalibrated defaults over a real [0,1]
  signal; a bare confidence percentage here would have no real signal underneath it at
  all.

## 7. Proposed Stage Breakdown

| Stage | Deliverable |
|---|---|
| 9.1 | `ForensicReconstruction` schema + the backward-walk function (`reconstruct_attack_origin()` or similar), built entirely on existing `attribute_*` calls; unit tests against constructed single-hop and multi-hop scenarios |
| 9.2 | Chain-confidence vocabulary (§4.2) implemented as a pure function over the assembled per-hop statuses; unit tests for every combination rule, including the "worst hop wins" invariant |
| 9.3 | Real entry-point wiring from a Phase 6 `MGPDecisionRecord` and a Phase 7 campaign signal result to a `ForensicReconstruction` target list — thin resolution code only, no new logic |
| 9.4 | The real, multi-attack validation described in §4.4, against all seven real Phase 4 attacks' live campaign data, reusing existing real ledger-building helpers |
| 9.5 | Forensic report document (`PHASE9_REPORT.md`), written after all real numbers exist, per this project's own "never write the conclusion first" discipline — reporting exactly which attacks reconstruct cleanly, which correctly report ambiguity, and any real false-attribution or missed-origin case found along the way |

## 8. Acceptance Criteria for 9.1

- `reconstruct_attack_origin()` (or its eventual real name) takes a `target_type` +
  `target_id` (an ACTION or DECISION, matching Attribution's own existing target
  vocabulary) and returns one `ForensicReconstruction`, built only from real, unmodified
  `attribute_*` calls — verified by a static import/call-graph check, the same discipline
  `test_never_imports_phase4_dormancy_report_or_phase5`-style tests already use elsewhere
  in this project.
- Calling it twice against identical, unchanged ledger state produces a byte-identical
  result (determinism, per §5).
- At least one constructed scenario each for: a clean single-hop reconstruction, a
  multi-hop reconstruction through a real derived memory, a diamond-ancestry case
  correctly reported as `MULTIPLE_PLAUSIBLE_ORIGINS`, and a benign/no-attack case
  correctly reported as `NO_ATTACK_ORIGIN_FOUND`.
- Zero modifications to any file under `phase3/`, `phase4/`, `phase5/`, `attribution/`,
  or `phase6/defense/attribution_bridge/` — Phase 9 is purely additive, exactly as
  Attribution itself was relative to Phase 5.

## 9. Verdict

Not yet applicable — this document is the plan, written before Stage 9.1 begins. Per
this project's own standing discipline, no verdict, PASS/FAIL claim, or real number is
written here; `PHASE9_REPORT.md` (§7, Stage 9.5) is where that verdict belongs, after the
real implementation and real validation against all seven attacks exist to support it.
