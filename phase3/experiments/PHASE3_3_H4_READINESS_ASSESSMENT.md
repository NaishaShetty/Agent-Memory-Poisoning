# Phase 3.3 Memory Foundation Readiness Assessment

Status: **CURRENT SNAPSHOT**, evaluated against
[MEMORY_FOUNDATION_STRENGTHENING_PLAN_REVISED.md §11](../specification/MEMORY_FOUNDATION_STRENGTHENING_PLAN_REVISED.md)
immediately after completion of Initiatives B, C, D, E, F, G, A and the H.3-R/H.3-R2
remediation. This is not itself a frozen decision — it is a dated evaluation that must be
re-run whenever any underlying capability changes materially (new live wiring, a real
qualification/counterfactual run, a further H.3-class fix).

## 1. Headline finding, stated up front

**Every mechanism the plan required now exists and is tested. Almost none of it has been
exercised against real data yet.** This is the single most important distinction this
assessment has to make, and the rubric's own eligibility rule (§11.4: a capability must be
"qualified," not merely implemented) means it changes the verdict materially from what a
naive "are the initiatives done? yes" read would suggest.

Concretely, of the seven initiatives:

| Initiative | Mechanism status | Live-wired into the actual evaluation pipeline? | Ever run for real (non-mock)? |
|---|---|---|---|
| B (`rejected`) | Complete, tested | No | No |
| C (`relationship_detected`) | Complete, tested | No (cannot be populated until a creation policy exists — by design, per its own mission's STOP condition) | No |
| D (qualification gate) | Complete, tested against mocks | No (gate not wired as a hard pre-flight check in `campaign_formal_runner.py`) | **Yes for Mem0 and A-MEM — both `QUALIFIED`, 15/15 fixtures ([PHASE3_3_H4_D_RUN_REPORT.md](PHASE3_3_H4_D_RUN_REPORT.md), [PHASE3_3_H4_D_A_RUN_REPORT.md](PHASE3_3_H4_D_A_RUN_REPORT.md)). Still no for Graphiti/Letta.** |
| E (content-level leakage gate) | Complete, tested | **Yes — wired fail-closed in `integration/pipeline.py`** | **Yes — this is the one initiative genuinely live today** |
| F (`config_fingerprint`) | Complete, tested | No | No |
| G (`tainted_by`) | Complete, tested, and — as of H.3-R2 — provably correct on real lifecycle resolution | No | Only against constructed/fixture data, not a real campaign |
| A (`counterfactually_influential`) | Complete, tested against mocks | No | **Yes — real sampled LoCoMo/Mem0 run complete and valid. Real sampled LoCoMo/A-MEM run complete but void (blocked on a newly-found `inspect_memory()` content bug).** |
| H.3-R / H.3-R2 | Complete, verified | N/A (a ledger-layer fix, not a pipeline stage) | Verified directly (§4 of its own report) but not yet exercised inside a real campaign |

**The frozen baseline campaign (LoCoMo/LongMemEval × Mem0/A-MEM) that produced the metrics
this whole plan was written to strengthen predates every one of these initiatives and
carries none of this instrumentation.** No existing result set can currently be described
using `rejected`/`relationship_detected`/`config_fingerprint`/`counterfactually_influential`
events, or a real `FoundationQualificationRecord`, because nothing has emitted them into a
real run yet.

## 2. Hard blocker evaluation (§11.1)

| # | Hard blocker | Mechanism | Verdict |
|---|---|---|---|
| 1 | Provenance integrity (H.1–H.3) | Frozen, and — critically — now **actually correct** for derived memories after H.3-R/H.3-R2 (previously, `reconstruct_version_history()` could not produce a valid result for any derived memory at all; this was undiscovered until H.4-D/G surfaced it) | **PASS** |
| 2 | Lifecycle/history integrity (H.3) | Same as #1 | **PASS** |
| 3 | Leakage prevention (Initiative E) | Structural (`boundary.py`/`leakage.py`, pre-existing, live via `run_agent_task()`) + content-level (`content_leakage.py`, H.4-E, now wired into **both** the real campaign path and `integration/pipeline.py`) | **PASS, and now genuinely live in the path that produces real evidence** — audit found it was previously wired only into a separate harness the real campaigns never called; fixed per `PHASE3_3_H4_CONTENT_LEAKAGE_WIRE_IMPLEMENTATION_REPORT.md` |
| 4 | Memory exposure/use traceability (`used`, `rejected`) | `used` (pre-existing H.2), `rejected` (H.4-BC) both schema-complete and tested | **PASS as a capability; NOT YET LIVE** — no real campaign has ever emitted a `rejected` event, so no existing result set can currently distinguish "retrieved-but-correctly-rejected" from "never retrieved" |
| 5 | Counterfactual influence measurement (Initiative A) | Real, sampled, valid measurements for **both** foundations: Mem0 17/13/0 ([PHASE3_3_H4_A_LOCOMO_SAMPLE_RUN_REPORT.md](PHASE3_3_H4_A_LOCOMO_SAMPLE_RUN_REPORT.md)), A-MEM 18/12/0 post-fix ([PHASE3_3_H4_A_LOCOMO_AMEM_RUN_REPORT.md](PHASE3_3_H4_A_LOCOMO_AMEM_RUN_REPORT.md) §7 addendum — the `inspect_memory()` bug is fixed and the corrected re-run confirms real, comparable answers) | **PASS for both Mem0/LoCoMo and A-MEM/LoCoMo** — both real, valid, small-n (6) measurements now exist |
| 6 | Attack traceability / attribution interfaces (Initiative G) | Complete, and now provably correct (§4 of the H.3-R2 report demonstrates a real lifecycle resolution succeeding where it previously could not) | **PASS as a capability; NOT YET LIVE** — no confirmed attack exists yet (expected — that's Phase 4's job), so this has only been exercised on constructed data |
| 7 | Foundation qualification integrity (Initiative D) | Harness/gate complete; **now run for real against Mem0 and A-MEM** ([PHASE3_3_H4_D_RUN_REPORT.md](PHASE3_3_H4_D_RUN_REPORT.md), [PHASE3_3_H4_D_A_RUN_REPORT.md](PHASE3_3_H4_D_A_RUN_REPORT.md)) — both `QUALIFIED`, 15/15 fixtures, zero mismatches | **PASS for Mem0 and A-MEM.** Graphiti/Letta still have zero real `FoundationQualificationRecord`s — both need a real infrastructure/policy decision first (cloud API key + graph DB for Graphiti; a self-hosted server or Cloud account for Letta) |
| 8 | Ability to reconstruct the relevant history for the claim | H.1/H.2/H.3(+R+R2)/H.4-BC/H.4-F | **PASS** |
| 9 | Absence of unresolved interpretive ambiguity | H.4-F's `config_fingerprint` resolvability is enforced, but its own report names an explicit, un-repaired limitation: event/config **temporal** ordering is not checked (a `retrieved` event could in principle reference a `config_fingerprint` appended after that event's own timestamp, and nothing currently catches this) | **PARTIAL** — this is a documented limitation, but per §11.2's own bar ("must be explicitly shown, not assumed, that it cannot invalidate the claim"), it has been *named*, not *shown safe*. Treat as an open item, not yet a cleared blocker |

**Net: 4 of 9 hard blockers fully pass. 3 are capability-complete but have never been
exercised against real data (4, 6 partially, and by extension everything downstream of
D/A). 2 (D, A) are not yet satisfied for any actual claim. 1 (9) has a named-but-unproven
residual gap.**

## 3. Claim-specific eligibility (§11.3), applied concretely

| Claim | Required capabilities | Current status |
|---|---|---|
| Retrieval/selection quality (no poisoning claim) | Standard metrics, provenance/leakage blockers only | **READY** — this is exactly what the frozen baseline campaign already measured, and blockers #1/#2/#3/#8 all pass |
| Lifecycle / provenance / propagation behavior | Initiatives C, D, G | **READY WITH LIMITATIONS** for constructed/fixture-driven analysis (C/G's mechanisms are correct and tested); **NOT READY** for any claim requiring a *real* foundation's lifecycle behavior, since D has never qualified one |
| Counterfactual poisoning impact | Initiative A (fully run) + Initiative F (resolvable fingerprints for both runs) + a task/answer layer | **NOT ELIGIBLE FOR POISONING** — mechanism exists, zero real executions exist. This is a hard blocker (§11.1 item 5), not a documentable limitation |
| Attack-origin attribution | Initiative G + [PHASE4_INTERFACE_REQUIREMENTS.md](../specification/PHASE4_INTERFACE_REQUIREMENTS.md) + everything counterfactual impact requires | **NOT ELIGIBLE FOR POISONING** — inherits the previous row's blocker, plus no attack exists yet (expected, Phase 4 scope) |
| Causal attribution (stronger sense) | Not supported by design | **NOT ELIGIBLE** — by the plan's own explicit design, permanently, until a separate experimental design is specified |

## 4. Per-pairing determination

Per §9's original foundation-specific plan:

| Foundation | Qualification status (Initiative D) | Eligible for any poisoning claim today? |
|---|---|---|
| Mem0 | Has a frozen baseline campaign, and **now has a real `FoundationQualificationRecord`** — `QUALIFIED`, 15/15 fixtures, per [PHASE3_3_H4_D_RUN_REPORT.md](PHASE3_3_H4_D_RUN_REPORT.md) | **Not yet for any claim** — qualification (blocker #7) now passes, but counterfactual-influence measurement (blocker #5) is still unresolved for every pairing, including Mem0; §11.4 requires *all* claim-relevant blockers, not some |
| A-MEM | Same as Mem0 | **No** |
| A-MEM | **`QUALIFIED`** (real, 15/15 fixtures, [PHASE3_3_H4_D_A_RUN_REPORT.md](PHASE3_3_H4_D_A_RUN_REPORT.md)). Condition C now wired ([PHASE3_3_H4_WIRE_C_IMPLEMENTATION_REPORT.md](PHASE3_3_H4_WIRE_C_IMPLEMENTATION_REPORT.md)). Real counterfactual run attempted but void — see [PHASE3_3_H4_A_LOCOMO_AMEM_RUN_REPORT.md](PHASE3_3_H4_A_LOCOMO_AMEM_RUN_REPORT.md) | **No** — blocked on the `inspect_memory()` content bug, not on missing instrumentation. Every other capability for this pairing is now in place |
| Graphiti | Adapter exists; no baseline campaign yet; zero qualification records. Root blocker identified this session: `graphiti-core` has no local embedder at all (OpenAI/Azure/Gemini/Voyage only) — a real cloud API key is required just to attempt qualification, not merely a nice-to-have | **No** — blocked on an explicit policy decision (e.g. using Gemini's free tier), not yet made |
| Letta | Deferred, per its own long-standing status, reconfirmed this session (`letta-client` is a pure HTTP client; no in-process mode; self-hosting the server package was explicitly out of scope for the stage that wrote the adapter) | **No** — deferred by original plan scope, not revisited |

**No foundation/dataset pairing is currently POISONING ELIGIBLE for any claim**, per §11.4's
own rule: hard blockers #5 and #7 are unresolved for every pairing, and that alone is
sufficient to fail eligibility regardless of how well everything else scores.

## 5. What "READY WITH LIMITATIONS" actually means today

It is accurate, and useful, to say the memory foundation is currently
**"READY WITH LIMITATIONS" for general (non-poisoning) retrieval/selection-quality
experimentation and for lifecycle/provenance analysis on constructed data** — this reflects
genuine, substantial progress: every structural gap identified in the original review (the
`used`-conflation problem, missing rejection traceability, missing relationship detection
provenance, non-reproducible configuration, unenforced content-leakage, an unqualified
qualification process, no attack-propagation interface, and — discovered along the way — a
real, load-bearing bug in H.3's own versioning logic) has been closed at the mechanism
level, verified by tests, and left in a state where the *next* action is "run it for real,"
not "design and build it."

It is equally accurate, and important not to blur, that **the foundation is NOT currently
ready for any poisoning claim** — not because the design is wrong, but because the two
most expensive, most novel mechanisms (D's real qualification runs, A's real counterfactual
executions) have deliberately not been exercised yet, exactly as each of their own missions
scoped.

## 6. Concrete punch list to reach POISONING ELIGIBLE for the first claim

In dependency order, matching the plan's own §10 sequencing logic:

1. ~~Wire live event emission... into `campaign_formal_runner.py`~~ — **DONE for both
   conditions**: Condition B (Mem0) per `PHASE3_3_H4_WIRE_IMPLEMENTATION_REPORT.md`,
   Condition C (A-MEM) per
   [PHASE3_3_H4_WIRE_C_IMPLEMENTATION_REPORT.md](PHASE3_3_H4_WIRE_C_IMPLEMENTATION_REPORT.md).
2. ~~Run Initiative D's qualification harness for real~~ — **DONE for both foundations**:
   Mem0 per [PHASE3_3_H4_D_RUN_REPORT.md](PHASE3_3_H4_D_RUN_REPORT.md), A-MEM per
   [PHASE3_3_H4_D_A_RUN_REPORT.md](PHASE3_3_H4_D_A_RUN_REPORT.md) — both `QUALIFIED`.
3. ~~Run Initiative A's counterfactual mechanism for real, sampled~~ — **DONE and VALID for
   Mem0/LoCoMo** ([PHASE3_3_H4_A_LOCOMO_SAMPLE_RUN_REPORT.md](PHASE3_3_H4_A_LOCOMO_SAMPLE_RUN_REPORT.md)).
   **Attempted but VOID for A-MEM/LoCoMo** — surfaced a real, previously-undiscovered bug
   in `RealAMemAdapter.inspect_memory()` (never returns memory content) — see
   [PHASE3_3_H4_A_LOCOMO_AMEM_RUN_REPORT.md](PHASE3_3_H4_A_LOCOMO_AMEM_RUN_REPORT.md).
4. **New item, higher priority than the rest of this list**: fix
   `RealAMemAdapter.inspect_memory()`'s missing `content` field, in its own reviewed pass
   (check nothing else depends on the current incomplete shape, re-verify Phase 3.2-H.4
   conformance is unaffected), then re-run the A-MEM counterfactual sample against the fix.
5. Re-run this assessment once item 4 lands for A-MEM. **Mem0/LoCoMo is very likely already
   the first POISONING ELIGIBLE pairing for the counterfactual-influence claim right now**
   — provenance, leakage, exposure/rejection traceability, qualification, and a real,
   sampled counterfactual measurement are all in place for it; a formal pass through
   §11.4's eligibility rule (remaining limitations — n=6 sample size, the
   exact_normalized_match sensitivity noted in that report's §3 — explicitly documented,
   not just implied) should confirm this. Attack-origin attribution still requires Phase 4
   to exist, for any pairing.
6. Separately, address §2 item 9's named-but-unproven temporal-ordering gap in
   `config_fingerprint` resolvability, either by proving it cannot affect a specific
   planned claim or by adding the check.
7. Separately (lower priority, not blocking any of the above): the H.4-D/G skip-logic
   cleanup flagged in the H.3-R2 report remains open — recommended, not required.

## 7. Compatibility and freeze status

This assessment modifies no code, schema, or contract. It is a reading of the current,
verified state of the repository against the plan's own rubric, dated to the completion of
H.3-R2. It should be re-run, not silently assumed still accurate, after any of the punch
list items in §6 land.

## 8. Post-audit update

A separate, broader Phase 3 completion audit (checklist-driven, 27 sections) was run after
this assessment was first written, and found two additional gaps this document's own
rubric did not separately track:

1. **Content-level leakage was wired only into `integration/pipeline.py`, never into the
   real campaign path** (`campaign_formal_runner.py`) that produced every real result this
   session. Fixed — see
   `PHASE3_3_H4_CONTENT_LEAKAGE_WIRE_IMPLEMENTATION_REPORT.md`. Blocker #3 above is now
   genuinely live in the path that matters, not just a separate harness.
2. **No persisted lifecycle/provenance graph artifact existed** — only individually
   queryable ledgers. Fixed — see `PHASE3_3_H4_PROVENANCE_GRAPH_IMPLEMENTATION_REPORT.md`,
   a new `provenance_graph.py` module, verified against both synthetic fixtures and this
   session's own real Mem0/LoCoMo ledger data.

Both are now closed. Three further audit-flagged items were also closed in the same
session:

3. **`REPRODUCIBILITY_CONTRACT.md`'s unmet software-environment/artifact-hash
   requirement** — fixed via a new, independently-keyed `EnvironmentRecord`/
   `EnvironmentRecordLedger` (not folded into `RunConfigRecord`, to avoid retroactively
   changing already-stored `config_fingerprint` values). See
   `PHASE3_3_H4_ENVIRONMENT_RECORD_IMPLEMENTATION_REPORT.md`. A real record was captured
   for the `h4a-real-locomo-smoke-1` campaign, retroactively and explicitly labeled as
   such.
4. **`clean_agent_memory_v1` naming ambiguity** — clarified in
   `PHASE3_ACTIVE_CLEAN_BASELINE_CLARIFICATION.md`: the named artifact exists only under
   the untracked, historical `phase3_reference/`; the active tree's equivalent is
   `runner.py::run_agent_task()` (reference agent) + the 3.3-G-formal campaign evidence
   (frozen baseline).
5. **Mem0+A-MEM-only foundation scope** — recorded explicitly in
   `PHASE3_ACTIVE_FOUNDATION_SCOPE.md`, superseding the strengthening plan's earlier
   Graphiti-inclusive framing for scope purposes.

All five audit-flagged gaps are now closed as of this session.
