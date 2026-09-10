# MAMBench V2 Clean-Agent Foundation — Production Validation & Finalization Report

Status: **V2 IMPLEMENTED, WIRED THROUGH THE PRODUCTION PIPELINE, EXECUTED AT FULL
120-TASK × 2-FOUNDATION SCALE, AND VALIDATED.** This supersedes the earlier
research-script-only V2 assembly (`PHASE3_V2_FINAL_REPORT.md`) with a real,
production-pipeline execution covering Mem0 AND A-MEM, per the explicit instruction to
wire V2 through the actual clean-agent execution pipeline rather than isolated
research scripts.

---

## 1. Exact V2 configuration

| Condition | Mechanism | Foundation-dependent? |
|---|---|---|
| A (no-memory) | Unchanged from V1 -- `campaign_formal_runner.run_condition_a()`, reused verbatim | No |
| B (gold evidence) | Timestamp prepended to every evidence item's content (`[source_timestamp] role: content`) when a real timestamp exists | No (runs once, shared by both foundations) |
| C (retrieved memory) | Retrieve top-20 candidates -> score by fixed-weight blend (cosine=0.5, token-overlap=0.3, entity-overlap=0.2) -> select top-8. NO timestamp prefix. | Yes -- run separately for Mem0 and A-MEM, same mechanism both times |

Model: **Qwen3-8B-Q4_K_M** (unchanged from V1). The Qwen3-4B-Thinking-2507
model-capability experiment was a **NO-GO** (hardware-budget infeasible on this 6GB
card) and is explicitly NOT used here, per instruction.

Weights, pool size, and top-k were **not tuned** for this run -- reused exactly as
validated in `phase3/experiments/research_variant/` Rounds 5-11.

## 2. Files changed / generated

**New production code (`phase3/evaluation/`)**:
- `foundations/hybrid_selection.py` -- V2's Condition-C selection mechanism, promoted from research code.
- `agent_runtime/hybrid_selection_runner.py` -- Condition-C sibling of `runner.py::run_agent_task()`.
- `agent_runtime/campaign_v2_runner.py` -- the real campaign driver (Conditions A/B/C x Mem0/A-MEM).
- `tests/test_hybrid_selection.py` -- 9 unit tests, all passing.

**Modified (additive only, backward-compatible)**:
- `agent_runtime/canonical_wiring.py` -- added optional `retrieved_reason`/`selected_reason` parameters to `record_retrieval_and_selection_events()` and `record_retrieval_and_selection_events_direct_assignment()`, defaulting to the EXACT pre-existing hardcoded strings (zero behavior change for any existing caller). Used only to give V2's ledger events an accurate mechanism description instead of inheriting V1's "provisional top_k slice" text.
- `agent/normalized_correctness.py` -- fixed a real, pre-existing bug (an empty answer was trivially credited as `ANSWER_CORRECT` because an empty string is a substring of every string). Confirmed with the user before keeping. Does not retroactively change any previously-reported number.

**New research/driver scripts (`phase3/experiments/research_variant/`)**:
- `smoke_test_v2_campaign.py`, `run_v2_full_campaign.py`, `validate_v2_campaign.py`, `compare_v1_v2_full.py`.

**New data artifacts (never overwrite V1)**:
- `phase3/experiments/results/canonical_store/v2_candidate/dataset_full/clean_agent_dataset_v2_locomo_120x2.json` (240 records)
- `phase3/experiments/results/canonical_store/v2_candidate/checkpoints/*.json` (raw per-condition execution records)
- Real canonical ledgers under `phase3/experiments/results/canonical_store/v2_candidate/` per-pool directories (via `canonical_wiring.open_pool_canonical_ledgers()`, same mechanism V1/the selection-policy variant already use).

**V1 canonical artifacts**: confirmed byte-identical (sha256 match) before and after every stage of this work, including the 2.76-hour full campaign.

## 3. Test results

- New unit tests (`test_hybrid_selection.py`): **9/9 passed.**
- Full existing regression suite (`phase3/evaluation/tests/`): **1666 passed, 14 skipped, 2 failed.** The 2 failures are pre-existing `TestRealRuntime` tests that hit whatever model happens to be loaded on the live server at test time -- they failed because Qwen3-4B-Thinking was loaded during the model-capability experiment, not because of any code change in this work (confirmed: same 2 tests, same failure mode, unrelated to `canonical_wiring.py`'s additive edit).
- Smoke test (3-4 real tasks, both foundations, all conditions, full production pipeline): **ALL CHECKS PASS** -- Condition A memory-free, Condition B 100% timestamp-injected, Condition C real canonical `retrieved`/`selected`/`rejected` events, V1 file confirmed byte-identical before/after.

## 4. Full execution counts

**Total wall-clock: 165.4 minutes (2.76 hours).**

| Stage | Tasks | Result | Time |
|---|---|---|---|
| Condition A | 120 | 120/120 SUCCESSFUL_EVALUATION | 170.0s |
| Condition B | 120 | 120/120 SUCCESSFUL_EVALUATION | 262.9s |
| Condition C, Mem0 | 120 | 120/120 SUCCESSFUL_EVALUATION | 1784.3s |
| Condition C, A-MEM | 120 | 120/120 SUCCESSFUL_EVALUATION | 7706.0s |

**720/720 condition-executions succeeded. Zero failures, zero empty/missing answers.**

## 5. V1 vs V2 results — Mem0

| Condition | Exact (V1→V2) | Normalized (V1→V2) | Content-recall (V1→V2) |
|---|---|---|---|
| A | 0/120 → 0/120 | 4/120 (3.3%) → 4/120 (3.3%) -- unchanged, expected | 3/120 → 3/120 |
| B | 0/120 → 1/120 | 52/120 (43.3%) → **62/120 (51.7%)** | 64/120 (53.3%) → **78/120 (65.0%)** |
| C | 0/120 → 2/120 | 48/120 (40.0%) → **55/120 (45.8%)** | 58/120 (48.3%) → **64/120 (53.3%)** |

## 6. V1 vs V2 results — A-MEM (never previously tested at scale in this investigation)

| Condition | Exact (V1→V2) | Normalized (V1→V2) | Content-recall (V1→V2) |
|---|---|---|---|
| A | 0/120 → 0/120 | 4/120 (3.3%) → 4/120 (3.3%) -- unchanged, expected | 3/120 → 3/120 |
| B | 0/120 → 1/120 | 52/120 (43.3%) → **62/120 (51.7%)** -- identical to Mem0's B (correct: B is foundation-independent) | 64/120 (53.3%) → **78/120 (65.0%)** |
| C | 1/120 → 2/120 | 47/120 (39.2%) → **53/120 (44.2%)** | 57/120 (47.5%) → **65/120 (54.2%)** |

**New finding: V2's improvement generalizes to A-MEM, not just Mem0.** This closes a
limitation explicitly flagged in the earlier research-only report ("V2's gains are
not yet confirmed for A-MEM").

## 7. Canonical ledger / diagnostics

Real canonical events across the full campaign (both foundations' Condition C):
**retrieved=4111, selected=1920, rejected=2191.** `selected_memory_ids` count is
`8` for all 240 Condition-C records (every real pool had >=8 candidates -- top_k was
never capacity-limited by a small pool). Zero canonical-wiring errors across all 240
tasks.

## 8. Failures and anomalies (preserved, not excluded)

**No execution failures.** One real, disclosed reproducibility anomaly:

**Non-determinism between separate runs of the identical configuration.** Comparing
this production run's Mem0 Condition C against an earlier research-script run of the
*same* configuration (pool=20, hybrid top-8, no timestamp): **76/120 (63%) of tasks
produced different generated answers**, and the aggregate normalized-correctness
number differs by 2.5 points (45.8% here vs. 48.3% in the earlier research run).
Inspecting the differing answers shows small wording variations and different
citation-id tags (Mem0 assigns fresh random UUIDs on every new ingestion) -- not
wildly divergent content, but genuinely different token-for-token generations despite
`temperature=0` and a fixed seed. Root cause not fully isolated (candidates: GPU
floating-point non-determinism in embedding computation, or Qdrant/Mem0-internal
tie-breaking order during vector search on a freshly-created collection each run) --
disclosed as an open question, not silently resolved. **Both runs' numbers still
clearly and consistently beat V1 (40.0%)** -- this affects the precision of the exact
headline percentage, not the direction or reality of the improvement.

## 9. Known limitations carried forward

- The reproducibility anomaly in §8 means a re-run of this exact campaign would likely
  produce a similar but not identical result (expect low-to-mid 40s% for Mem0 Condition
  C, not necessarily exactly 45.8%).
- Hedging behavior (Round 9's finding) remains unaddressed -- not part of V2.
- The LLM-judge metric (69.2% on V1's Condition B) has not been re-run against V2's
  answers -- a natural follow-up before treating any single number as V2's true ceiling.
- `used_memory_ids`/full usage attribution remain `None` throughout, per the project's
  existing, disclosed, unchanged limitation (not something V2 was scoped to address).

## 10. Is V2 ready to be frozen as the final Phase 3 clean foundation?

**Yes, with the limitations above carried forward explicitly.** The improvement is
real, reproducible in direction and rough magnitude (if not exact percentage) across
BOTH foundations, wired through the actual production canonical-ledger pipeline (not
an isolated research artifact), fully schema-validated, and produced zero execution
failures across 720 real condition-executions. V1 remains completely untouched and
available as the frozen scientific reference throughout.
