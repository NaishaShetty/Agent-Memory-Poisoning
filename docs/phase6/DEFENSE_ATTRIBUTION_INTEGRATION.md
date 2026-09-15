# Stage 6.13 — Defense ↔ Attribution Integration

Status: 6.13 deliverable. A read-only, post-hoc analytical bridge answering
"what did this defense decision actually mitigate?" — built entirely on
Attribution's real, unmodified orchestrator, tested against real (not
mocked) Phase 3/5 ledger state.

---

## 1. Design — Reuse the Real Orchestrator, Never Modify Attribution

`phase6/defense/attribution_bridge/report.py`'s `explain_defense_mitigation()`
calls `attribution/wiring/orchestrator.py`'s real, frozen `attribute_memory()`
— the same six-question-type orchestrator Attribution already validated (31
tests passing, per its own implementation report) — and composes a narrative
from its real return values. **Nothing here writes to any ledger, and nothing
here is imported by any D1–D4 runtime decision function** — confirmed by a
static import check and a determinism test (calling the bridge twice against
identical ledger state produces byte-identical results and leaves the event
ledger's count unchanged).

## 2. The Fallacy This Stage Exists to Structurally Prevent

The brief names it explicitly: *"Defense blocked retrieval, therefore it
prevented influence"* is not automatically valid. `_build_narrative()` never
derives an influence claim from an admission/retrieval/propagation action —
it reports Attribution's own real `AttributionResult.status` for the
`INFLUENCE` question type verbatim, and when the defense's own action means
no downstream event trail exists (a `BLOCK`ed memory was never even written),
the narrative says exactly that — explicitly refusing the inference, in
words, not just by omission (`test_blocked_memory_has_no_real_event_trail_
and_narrative_says_so` asserts the refusal is literally present in the
narrative text, not merely that no false claim happens to appear).

## 3. Three Real Scenarios, Each Demonstrating a Different Honest Outcome

Built with real Phase 5 wiring functions (`record_memory_creation()`,
`record_memory_derivation()` — the actual, already-tested instrumentation
functions, never hand-rolled event construction) and Attribution's real
orchestrator:

1. **`BLOCK`ed memory, never admitted**: `attribute_origin`/`attribute_
   lineage` correctly and gracefully return `NO_ATTACK_ORIGIN`/
   `NO_LINEAGE_ANCESTOR` (real, valid absence findings — confirmed by direct
   inspection of those functions' own code, which never errors on an unknown
   memory_id, it reports honest absence). The narrative explains this is
   because the memory was never written, not a security finding about
   influence.
2. **`ALLOW`ed memory with a real, one-hop derivation** but no counterfactual
   test ever run: `attribute_lineage` returns a real `STATUS_UNIQUE` finding
   with the actual parent id and lineage path; `attribute_influence` returns
   `INFLUENCE_NOT_ESTABLISHED` — reported as absence of evidence, explicitly
   **not** "proven harmless."
3. **A real `counterfactually_influential` CanonicalEvent exists**:
   `attribute_influence` returns `INFLUENCE_ESTABLISHED` with the real
   evidence event id cited — the narrative confirms influence **only** here,
   where real evidence supports it.

These three scenarios cover the three qualitatively different evidence states
a defense decision can correspond to (never-existed, exists-but-untested,
exists-and-confirmed) — not just the "happy path."

## 4. What Attribution's Own Guarantees Contribute for Free

`retrieved ≠ selected ≠ exposed ≠ used ≠ influenced` and `lineage reachability
≠ causal influence` are inherited by construction, not re-implemented: every
fact this bridge reports is an unmodified `AttributionResult.status` value.
The bridge adds no inference layer on top of Attribution's own discipline —
its only original contribution is the narrative text explaining, in plain
language, why a given status does or doesn't support a given claim about the
defense's effect.

## 5. Tests and Evidence

5 new tests: the three scenarios above, a read-only/determinism check, and a
static import-surface check confirming the bridge only imports from
Attribution's real orchestrator/schema, never a write path.

**Full Phase 6 suite: 244 passed, 0 failed.** Frozen `phase3/`, `phase4/`,
`phase5/`, `attribution/` verified unchanged — `attribution/` in particular is
the frozen boundary this stage is most likely to tempt touching, and it was
not touched.

## 6. Limitations Carried Forward

1. This stage cannot demonstrate the bridge against a real, live seven-attack
   campaign's actual event ledgers — the same environment limitation Stage
   6.10 confirmed (no `mem0ai`, unreachable LLM server). All three scenarios
   use directly-constructed, real (not mocked) ledger state, the same
   evidentiary standard Attribution's own test suite already uses.
2. `attribute_exposure`/`attribute_action` (requiring a real `decision_id`/
   `action_id`) were not exercised in this stage's tests — no real
   `agent_decision`/`agent_action` event was constructed, since doing so
   faithfully would require simulating Stage 5.6's full agent-decision
   instrumentation, judged out of scope for demonstrating the bridge's core
   mechanism. The narrative code path for this case (explicit "NOT CHECKED"
   messaging when no `decision_id` is supplied) is exercised by Scenario 1.
3. The bridge's narrative is plain, hand-composed English, not a structured
   report format — sufficient for this stage's demonstration purpose; a
   future stage packaging Phase 6's final results (Stage 6.19/6.20) may want
   a more structured serialization.

## Verdict

**PASS** as a 6.13 deliverable. The central fallacy the brief warns against is
prevented structurally (Attribution's real status values are the only source
of truth the narrative ever cites) and demonstrated failing safely across
three qualitatively distinct real evidence scenarios, without modifying
Attribution or writing to any ledger.
