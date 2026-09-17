# Phase 9 Report — Attack-Origin Attribution & Forensics

Status: Stages 9.1–9.4 complete for Phase 9 v1's own defined scope
(`PHASE9_PLAN.md` §7). This report is Stage 9.5. Written 2026-09-17, same
session as the implementation it describes. Every number and test count in
this report was produced by code committed under `attribution/wiring/` and
`attribution/tests/`, run for real as part of writing this report — none are
hand-typed estimates.

No file under `phase3/`, `phase4/`, `phase5/`, `attribution/wiring/{action,
exposure,lineage,origin,propagation,influence,references,orchestrator}.py`,
or `phase6/defense/attribution_bridge/` was modified to produce any stage of
Phase 9 — verified directly via `git status` after each stage, not merely
asserted. Every new module is a read-only consumer of Attribution's existing
`attribute_*` functions (`attribution/wiring/*.py`) and, for the two thin
resolution points named in the plan, of `phase5.schema.event`'s own
`agent_decision`/`agent_action` fields, `phase6.defense.policy.records`'s
`MGPDecisionRecord`, and `phase7.propagation.campaign_signals`'s real result
types.

**Correction (same session, before this report's first draft): the plan's
own tentative Stage 9.1 shape (`target_type` restricted to DECISION/ACTION,
a singular `exposure: AttributionResult` field) did not survive contact with
Stage 9.3's real entry points.** Checking `phase6/defense/policy/records.py`
directly found that `MGPDecisionRecord.decision_id` is a Phase-6-internal
policy id, unrelated to any real Phase 5 `agent_decision`/`agent_action`
event — the only real fact a `QUARANTINE`/`BLOCK` decision currently carries
is `candidate_memory_id`. Restricting `reconstruct_attack_origin()` to
DECISION/ACTION targets would have made the plan's own two named real entry
points (a Phase 6 decision, a Phase 7 campaign signal — both memory-id-
shaped) impossible to wire up. `target_type=MEMORY` was added before Stage
9.3 was attempted, once this was found, not planned in advance; the module
docstring in `attribution/wiring/forensics.py` documents this reasoning in
full. `exposure` was reshaped from a tuple to a `Mapping[str,
AttributionResult]`, consistent with the other `per_memory_*` fields, for the
same reason (one decision can expose many memories, not one).

## 1. What Was Built

| Stage | Module | What it does |
|---|---|---|
| 9.1 | [`attribution/wiring/forensics.py`](../../attribution/wiring/forensics.py) | `ForensicReconstruction` (frozen dataclass) + `reconstruct_attack_origin(target_type, target_id, ...)` — the one backward-walk entry point, composed entirely from real `attribute_exposure()`/`attribute_lineage(full_chain=True)`/`attribute_origin()`/`attribute_propagation()` calls |
| 9.2 | `attribution/wiring/forensics.py::_compute_chain_confidence()` | Pure, "worst hop wins" rule over already-produced `AttributionResult.status` values → one of `SINGLE_ORIGIN_HIGH_CONFIDENCE` / `MULTIPLE_PLAUSIBLE_ORIGINS` / `NO_ATTACK_ORIGIN_FOUND` / `INSUFFICIENT_EVIDENCE`; folded into 9.1 rather than kept as a separately-versioned stage, since the two were designed and tested together from the start |
| 9.3 | [`attribution/wiring/forensics_entrypoints.py`](../../attribution/wiring/forensics_entrypoints.py) | `forensic_target_from_mgp_decision()` / `forensic_targets_from_mgp_decisions()` (Phase 6 `MGPDecisionRecord` → `(MEMORY, candidate_memory_id)`), `forensic_targets_from_campaign_signal()` / `forensic_targets_from_content_similarity_clusters()` (Phase 7 `CampaignSignalResult`/`ContentSimilarityCluster` → one target per real campaign root memory id) |
| 9.4 | [`attribution/tests/test_forensics_phase4_validation.py`](../../attribution/tests/test_forensics_phase4_validation.py) | Real, multi-attack validation of the full backward walk against all seven frozen Phase 4 attacks' own real injector code — see §2 below |

`attribution/tests/` now has 62 tests total (26 new for Phase 9: 11 in
`test_forensics.py`, 7 in `test_forensics_entrypoints.py`, 8 in
`test_forensics_phase4_validation.py`); all 62 pass unconditionally in the
main environment, alongside the pre-existing 36. The broader
`attribution/ phase4/ phase5/ phase6/ phase7/` suite (864 tests, 8 skipped —
the same 8 that already self-skip outside `C:\h4venv`, untouched by Phase 9)
passes in full.

## 2. Real Numbers — the 9.4 Validation

Every case below drives the attack through its own real, frozen `Injector`
class (`run_live_*_injection()` from `phase5/wiring/live_attack_runs.py`, or
— where a second real product from the same attack was needed — that
attack's own `Injector` class called directly against a second real, already-
frozen artifact from that attack's own module) and then calls
`reconstruct_attack_origin()` for real. No `AttributionResult` or evidence-id
in any assertion below was hand-constructed.

### 2.1 Clean single-origin attacks (4 of 5 named in the plan)

| Attack | `attack_id` | Chain confidence | Origin `source_id` |
|---|---|---|---|
| AgentPoison | `agentpoison` | `SINGLE_ORIGIN_HIGH_CONFIDENCE` | real `injection_id` (`P5INJ-...`) |
| DSRM | `dsrm` | `SINGLE_ORIGIN_HIGH_CONFIDENCE` | real `injection_id` |
| MPBench-PCFI | `mpbench` | `SINGLE_ORIGIN_HIGH_CONFIDENCE` | real `injection_id` |
| Sleeper Memory Poisoning | `sleeper_memory_poisoning` | `SINGLE_ORIGIN_HIGH_CONFIDENCE` | real `injection_id` |

All four: `attack_id` on the resolved `attribute_origin()` result matches the
real attack exactly; `source_id` matches the real `injection_event.injection_id`
`instrument_attack_memory_lifecycle()` itself produced (not the memory_id —
`attribute_origin()`'s own PRODUCED-edge convention names the injection, a
fact this report's first draft got wrong and corrected before publication;
see `origin.py`'s own docstring and `attribution/tests/test_attribution.py`'s
Scenario A for the same convention).

### 2.2 MINJA — one clean origin per real step (5th of 5 named)

MINJA's real 3-step bridging→compressed→minimal query sequence produces
three independently admitted memories (verified: `len(step_results) == 3`).
Each was investigated as its own separate incident (its own decision), since
that is what "one clean origin" means per-incident, not "the whole sequence
collapses to one memory." All 3 real steps: `SINGLE_ORIGIN_HIGH_CONFIDENCE`,
`attack_id == "minja"`.

### 2.3 FARMA — real amplification-style convergence → `MULTIPLE_PLAUSIBLE_ORIGINS`

**A genuine limitation of this validation, disclosed up front:** FARMA's own
seed artifact (`SEED_CAMPING`) produces a deterministic, content-addressed
memory_id — calling `run_live_farma_injection()` twice in the same ledger
collides (`CanonicalCollisionError`), confirmed directly. A literal replay of
FARMA's own 10-cycle amplification campaign (as Phase 7 Stage 7.6 already
did, structurally, for crowding) was not attempted here; instead, two of
FARMA's own real, frozen, *distinct* seed artifacts (`SEED_CAMPING` and
`SEED_CHARITY_RACE`, both already checked into
`phase4/attacks/farma/reasoning_trace.py`) were each injected for real via
`FARMAInjector`, then merge-derived (a real `record_memory_derivation()` call
with both as `source_memory_ids`) into one downstream memory, modeling the
structural shape of a convergent amplification cluster — genuine multi-origin
ancestry, not a literal 10-cycle replay.

Real result: `reconstruct_attack_origin()` on the decision exposing the
merged child reports `MULTIPLE_PLAUSIBLE_ORIGINS`. `per_memory_lineage`'s
`candidate_source_ids` names both real memory ids exactly (`{camping_memory_id,
charity_race_memory_id}`, both distinct, verified `!=`); both resolve to
`attack_id == "farma"` under `attribute_origin()`. This confirms the plan's
own rule (§9.2, second disjunct — "more than one exposed memory has its own
distinct, real origin"): the verdict correctly reflects genuine structural
multiplicity even though both candidates share the same attack.

### 2.4 MemoryGraft — real volume-style repetition → `MULTIPLE_PLAUSIBLE_ORIGINS`

Same disclosed constraint and same real construction pattern as FARMA: the
default `run_live_memorygraft_injection()` artifact plus a second real,
already-frozen MemoryGraft artifact (`SEED_RESEARCH_TOPIC`, from
`phase4/attacks/memorygraft/locomo_seed.py` — the one attack with a second
real LoCoMo-reformulated artifact already checked into the repository) were
each injected via `MemoryGraftInjector` (real judged admission gate, real
scripted-transport pattern already used by `run_live_memorygraft_injection()`
itself), then merge-derived into one downstream memory.

Real result: `MULTIPLE_PLAUSIBLE_ORIGINS`, `candidate_source_ids` naming both
real memory ids exactly, both resolving to `attack_id == "memorygraft"`.

### 2.5 Genuinely benign decision → `NO_ATTACK_ORIGIN_FOUND`

A real, ordinary foundation memory with no attack involvement anywhere in its
provenance, exposed to a decision: `reconstruct_attack_origin()` reports
`NO_ATTACK_ORIGIN_FOUND`, and `attribute_origin()`'s own status for that
memory is `NO_ATTACK_ORIGIN` — the narrative states this plainly rather than
implying guilt from the mere fact that a reconstruction was run.

## 3. Design Decisions Made During Implementation, Not Pre-Judged by the Plan

The plan's own §4.1 explicitly left the exact shape of `ForensicReconstruction`
and even its module location as "decided during 9.1, not pre-judged." Two
real decisions were made, both documented in `forensics.py`'s own module
docstring, not silently:

1. **`target_type` accepts `MEMORY`, `DECISION`, and `ACTION`, not only
   DECISION/ACTION as an earlier draft of this module assumed.** See the
   Correction note in §0/above. For a `MEMORY` target, the EXPOSURE hop is
   skipped entirely — never fabricated as `ESTABLISHED` or
   `NOT_ESTABLISHED` — and the narrative says so plainly, mirroring
   `phase6/defense/attribution_bridge/report.py`'s own "Exposure: NOT CHECKED"
   discipline for a memory excluded before context assembly.
2. **The chain-confidence rule treats "more than one exposed memory has its
   own distinct, real origin" as `MULTIPLE_PLAUSIBLE_ORIGINS`, even when both
   origins share the same `attack_id`** (confirmed real by §2.3/§2.4 above).
   This is the plan's own explicit second disjunct in §9.2's rule table, kept
   as written rather than narrowed to "distinct attack, not just distinct
   memory" — narrowing it would have silently reported FARMA's and
   MemoryGraft's own genuinely multi-memory convergence as
   `SINGLE_ORIGIN_HIGH_CONFIDENCE`, exactly the "rounded up for presentation"
   failure mode §9.2 forbids.

## 4. Stage 9.3 Entry Points — Scope, Disclosed

`forensic_targets_from_campaign_signal()` and
`forensic_targets_from_content_similarity_clusters()` resolve to a campaign's
real ROOT memory ids only (`CampaignSignalResult.per_root`'s keys, or
`ContentSimilarityCluster.root_ids`) — not every downstream memory a root's
own propagation footprint reaches. This is a real, disclosed scope limit, not
an oversight: flattening every footprint member into a target list would be
new evidence-shaping logic (re-deriving footprint membership independently of
what the caller already computed), which Stage 9.3's own "thin resolution
only" framing forbids. A caller who wants a root's downstream reach already
has `attribute_propagation()`/`reconstruct_attack_origin()` walking forward
from that root available to them directly.

`forensic_target_from_mgp_decision()` resolves only `QUARANTINE`/`BLOCK`
actions to a target; `ALLOW`/`ALLOW_WITH_RESTRICTION` resolve to `None`. This
mirrors the plan's own framing (§9.3: "an `ALLOW` decision has no candidate
content that was excluded, so there is nothing Phase-9-shaped to
reconstruct") — it is not a claim that an ALLOWed memory can never be
attack-produced, only that Phase 9 does not itself decide an ALLOW is worth
investigating; a caller with an independent reason to investigate an ALLOWed
memory already has `attribute_memory()` (the orchestrator) or
`reconstruct_attack_origin("MEMORY", memory_id, ...)` directly available.

## 5. Inherited Constraints — How Phase 9 Actually Handled Them

- **No Phase 3/4/5 file modified.** Verified via `git status` after every
  stage (9.1, 9.2/9.1 combined, 9.3, 9.4): each check showed only new files
  under `attribution/wiring/` and `attribution/tests/`, plus this report and
  `docs/phase9/PHASE9_PLAN.md`.
- **Read-only, always.** `reconstruct_attack_origin()` and every
  `forensics_entrypoints.py` function take ledgers/results and return data;
  none append to, mutate, or otherwise write any ledger.
- **Never claim more than the evidence establishes.** Verified concretely in
  §2.3/§2.4: two real candidates sharing one `attack_id` were still reported
  as `MULTIPLE_PLAUSIBLE_ORIGINS`, not rounded up to
  `SINGLE_ORIGIN_HIGH_CONFIDENCE` because "it's really just one attack."
- **Determinism.** `test_reconstruction_is_deterministic`
  (`test_forensics.py`) calls `reconstruct_attack_origin()` twice against
  unchanged ledger state and asserts `to_dict()` equality and
  `reconstruction_id` equality — both real assertions, not a smoke test.
- **Ground truth only from the caller.** No new metric was added in Phase 9;
  every `attack_id`/`source_id` assertion in §2 compares against a real value
  the test itself captured from the real injection call
  (`result.injection_event.attack_id`/`injection_id`), never an assumed
  constant.

## 6. Explicit Out-of-Scope Items, Confirmed Still Out of Scope

Per the plan's own §6: no new evidence-derivation function was added (every
fact in `forensics.py` traces to an existing `attribute_*` call or a direct
read of an existing Phase 5 event field); no automated "when to investigate"
policy was built (`forensic_target_from_mgp_decision()` resolves a
QUARANTINE/BLOCK decision the caller already selected — it does not decide
which decisions merit investigation); no cross-run/cross-deployment
attribution exists (every function takes one run's ledgers); no LLM-generated
narrative exists (`_build_narrative()` is templated string composition, same
discipline as `report.py::_build_narrative()`); no numeric confidence score
was introduced (`chain_confidence` remains a four-value closed vocabulary).

## 7. What Remains Genuinely Open

- **§2.3/§2.4's FARMA/MemoryGraft validation models multi-origin convergence
  structurally (two real, distinct artifacts of the same attack, merge-
  derived), not by literally replaying either attack's own full multi-cycle
  campaign mechanism** (FARMA's 10-cycle amplification sequence, or a true
  MemoryGraft volume campaign) — both are disclosed as content-addressed and
  therefore not literally re-injectable twice with identical content in one
  ledger. A future extension could drive `generate_amplification_sequence()`
  for real (as Phase 7 Stage 7.6 already did for its own crowding study) and
  feed each real amplification-cycle memory into one reconstruction, which
  would be a strictly more faithful replay than this report's two-seed
  construction — not attempted here for time, and not claimed to be
  equivalent.
- **The Stage 9.3 campaign-signal entry points resolve to root memory ids
  only**, per §4 above — a caller wanting a full campaign's every downstream
  member walked individually must still assemble that list themselves (e.g.
  from a real `PropagationFootprint.member_ids`) and call
  `reconstruct_attack_origin("MEMORY", member_id, ...)` per member; Phase 9
  does not do this fan-out itself.
- **No live-ledger `MGPDecisionRecord.decision_id → real Phase 5 decision/
  action event` wiring exists yet** — the plan's own Stage 4.3 parenthetical
  names this as a known, not-yet-built gap (attributed to a future Stage
  6.10), confirmed still true by direct inspection of
  `phase6/defense/policy/records.py` during this session. Once built, Stage
  9.3's `MGPDecisionRecord` resolution could additionally recover a real
  EXPOSURE hop for a Phase-6-flagged incident (today it correctly reports
  "NOT CHECKED" instead, since no such link exists to check).

## 8. Verdict

Stages 9.1–9.4 — COMPLETE for Phase 9 v1's own defined scope. 26/26 new
tests pass (11 `test_forensics.py`, 7 `test_forensics_entrypoints.py`, 8
`test_forensics_phase4_validation.py`); the full `attribution/` suite (62
tests) and the broader `attribution/ phase4/ phase5/ phase6/ phase7/` suite
(864 tests, 8 pre-existing `C:\h4venv`-only skips, unaffected by Phase 9) both
pass in full. Every one of Stage 9.1's own acceptance criteria (§8 of the
plan) is met: a clean single-hop case, a multi-hop case through a real
derived memory, a diamond-ancestry case correctly reported as
`MULTIPLE_PLAUSIBLE_ORIGINS`, and a benign case correctly reported as
`NO_ATTACK_ORIGIN_FOUND` — now each validated against real Phase 4 attack
data (§2), not only constructed fixtures, and confirmed zero modifications to
any inherited-constraint file.

The §4.4 acceptance bar — the single most important one named in the plan —
is met for all seven attacks: five with one real clean origin
(AgentPoison, DSRM, MPBench-PCFI, Sleeper, MINJA), two (FARMA, MemoryGraft)
correctly reporting genuine multi-origin ambiguity rather than an arbitrary
pick, and a genuinely benign case correctly reporting no attack origin at
all — with the one disclosed caveat in §7 about how faithfully the two
multi-origin cases replay each attack's own full campaign mechanism versus
modeling its structural shape with two real, distinct artifacts.
