# Defence v5: Targeted Fixes Report

**Date:** 2026-10-14.

**Pre-registration:** `docs/phase17/PREREGISTRATION_DEFENCE_V5_2026-10-14.md`
- main plan: `aa968239`;
- addendum A: `59a4fd1c`;
- addendum B: `b2236404`.

**Commits:** `aa968239` to `d04ef0a9`. Nothing was pushed. `run_all_logs` is untouched.

**Purpose.** Attack the three failure modes left by v4:
1. authorship is not recorded;
2. the warning frame fails after Mem0;
3. lost lineage.

## Fix 1: recording authorship through extraction (PRW)

| Finding | Evidence |
|---|---|
| Mem0 stores per-memory metadata, and it survives extraction | SA-5, 137/137 derived memories carry the correct source, natively and under PRW (`af_eval.json` → provenance) |
| **Mem0's UPDATE is last-writer-wins on metadata.** A user-channel update relabels a document-planted memory as the user's | Read in `Memory._update_memory`. **Demonstrated** deterministically on the code path: native `retrieved_document` becomes `user_turn`; PRW keeps both (`launder_codepath.json`) |
| How often the extractor actually triggers it | **0 UPDATE events in 225 ingestions** across three runs (SA-5 PRW ingestion, 135; trigger-turn probe, 45; refinement-turn probe B1, 45. An earlier commit message said "135 attempts"; the correct total is 225). B1's pre-declared outcome: "not exercisable in this harness" (`launder2_eval.json`) |
| Provenance gating preserves legitimate user rules | 39 SA-5 legitimate rules ingested via the user channel were never framed. Surfaced 22/39 under every arm |

**Verdict.**
- **Authorship recording works** in this pipeline.
- **The laundering vulnerability is real at code level, and PRW closes it there.**
- Its real-world frequency is unmeasured: Mem0's extractor never produced the update in this harness.

## Fix 2: a frame that survives Mem0 rewriting

**Selected on SA-3 dev: AF2** (the attribution frame). Dev, stored text: attacks 21 → 7/60; benign surfaced 33 → 33/58.

**SA-5 held-out** (Mem0-stored; frames applied only to memories PRW marks as document-sourced):

| Group | Undefended | **AF2 (selected)** | F2 (v4 comparator; not a candidate) |
|---|---|---|---|
| Attacks, unconfirmed activation | 11/45 | **6/45** (+3/−8, p = 0.23) | 1/45 |
| Legitimate rules via **user** channel, surfaced | 22/39 | 22/39 (not framed) | 22/39 |
| Legitimate rules via **document**, surfaced / unconfirmed activation | 33 / 11 of 45 | 30 / 7 | 33 / 2 |

**Acceptance:**

| Criterion | Result | Met? |
|---|---|---|
| C1: activation halved on stored text | 11 → 6, p = 0.23 | **No** |
| C2: user-channel legitimate rules preserved | 22/39 → 22/39 | Yes |
| C4: provenance | 137/137 | Yes |

**AF2 is not accepted.**

**The comparator.** F2, gated by recorded provenance, cut activation from 11 to 1 on SA-5. But it was **not the selected candidate**, and under N1 ∨ B13 gating on SA-4 the same frame went only from 8 to 7. **The frame effect after rewriting is inconsistent across sets.** It is reported as exploratory, not as a result.

## Fix 3: containment without lineage

| Attempt | Result |
|---|---|
| **RAC:** registry matching, frozen thresholds | **Rejected.** Catches the payload (generation 4: 9/10, 35/35, 18/18) but blocks 45–78% of the owner's real benign memories (limit 3%) |
| **RAC-D:** thresholds re-selected on dev for the no-lineage setting (addendum A) | **No admissible thresholds.** Dev collateral never falls below 15.9%, so it was not evaluated |
| **WTP:** write-time taint propagation (addendum B2) | **Accepted** on HO7, HO8 and HO4. Equals RCL-with-lineage item for item (110/110, 158/158, 119/119). Beats the frozen guard with no persisted lineage (generation 4: 6/10, 20/35, 15/18 vs 0). Unflagged collateral 0 |

**Diagnosis.**
- Lineage acts as a strong prior: it limits checks to descendants of flagged roots.
- Without it, similarity and entailment cannot tell an owner's benign memories from flagged claims about the same person.
- WTP keeps that prior **without a stored graph** by tainting outputs at write time.
- It does **not** recover lineage deleted after writing. That case remains open.

## Defects found and fixed during v5

| Defect | Handling |
|---|---|
| `nli_entail` wrote any caller's cache to defence_v3's cache file, overwriting it on disk (never committed) | Restored from git (all 3,859 entries; values identical). Explicit per-caller cache paths. Regression test |
| A launch with an unpatched gating function | Aborted before any output (verified: no output file existed). Fixed and committed before re-running |
| Ollama auto-upgraded 0.40.3 → 0.40.4 mid-run | Models and digests unchanged; GPU verified. Answers generated after the upgrade come from 0.40.4 (environment deviation) |
| Windows refused rapid repeated cache writes | Cache now persisted once per stage |

## Effect on closure scores (rubric unchanged)

| Gap | v4 | v5 | Change |
|---|---|---|---|
| 1 | 59% | **59%** | No scored change. Authorship recording and laundering protection are demonstrated, but code-level only for laundering. The Fix 2 behaviour criterion failed |
| 2 | 58% | **65%** | 2.6 (lineage loss): 0 → 0.5. WTP handles "never persisted" on held-out chains; deleted lineage is still unsolved |
| 3 | 29% | **29%** | AF2 failed on SA-5. The F2 comparator is exploratory and inconsistent |

## Tests (GPU visible)

| Suite | Result |
|---|---|
| Phase 17 + leakage audit | **230 passed / 0 failed** |
| Frozen Phases 1–16 | **2,690 passed / 0 failed / 30 skipped / 9 deselected** |

**Logs:** `phase17/defence_v5/logs/tests_*.log`.

**Judge caches:** unchanged since `be965cf2` (0 added, 0 changed, 0 removed).
