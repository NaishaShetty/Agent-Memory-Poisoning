# Final Selection-Policy Diagnostic — Primary Dataset vs. Selection-Policy Variant

Status: **DIAGNOSTIC — understanding and validation only, not optimization.** No
campaign was re-run to produce this report; every number below is computed directly
from the two already-existing real raw result sets:
`phase3/experiments/results/canonical_store/dataset_full/clean_agent_dataset_locomo_120x2.json`
(primary) and
`phase3/experiments/results/canonical_store/selection_policy_variant/selection_policy_variant_result.json`
(variant). The calibrated threshold (0.263) was not touched, recalibrated, or tuned
here.

## 1. Real comparison, both foundations, 120 tasks each

| Metric | MEM0 | AMEM |
|---|---|---|
| Avg. retrieved count — primary (N=5, fixed) | 5.00 | 5.00 |
| Avg. retrieved count — variant (N=20, fixed cap) | 16.48 | 17.78 |
| Avg. selected count — primary | 5.00 | 5.00 |
| Avg. selected count — variant | 4.89 | 4.89 |
| Avg. rejected count — variant (N/A for primary) | 11.58 | 12.89 |
| `max_k=5` binds in variant | 112/120 (93.3%) | 112/120 (93.3%) |
| Zero-selected cases in variant | 0/120 | 0/120 |
| Real answers differing (primary vs. variant) | 92/120 (76.7%) | 71/120 (59.2%) |
| Retrieved-set Jaccard overlap | **0.000** (see §2 — not meaningful) | 0.286 |
| Selected-set Jaccard overlap | **0.000** (see §2 — not meaningful) | 0.669 |

## 2. Critical methodological finding: retrieved/selected-ID overlap is only meaningful for A-MEM, not Mem0

Mem0's retrieved-set and selected-set Jaccard overlap between the primary and
variant runs is **exactly 0.000** — every single task, both metrics. This is NOT
evidence that the two runs retrieved completely disjoint real content. It is a
structural artifact of Mem0's own identity strategy: Mem0 auto-generates a fresh
UUID for every memory on `add_memory()` (`STRATEGY_METADATA_LOOKUP`, per
`identity.py`'s own established terminology this session used throughout). The
primary dataset and the selection-policy variant each performed a genuinely
SEPARATE, independent real ingestion into a SEPARATELY-NAMED Mem0 collection
(`"g_" + hash(...)` for the primary run, `"sp_" + hash(...)` for the variant) — so
even if the underlying real CONTENT retrieved were identical, the literal foundation
memory IDs are guaranteed to differ, because Mem0 never reuses an id across two
independent ingestions of the same content.

**A-MEM's overlap numbers, by contrast, ARE genuinely meaningful**, because A-MEM
uses `STRATEGY_DIRECT_ASSIGNMENT` (the real, canonical source `memory_id` is reused
directly as the foundation-native id, verified repeatedly this session) — a fresh
A-MEM ingestion of the same real content reuses the same ids, so overlap here
reflects genuine retrieval/selection behavior difference, not an identity-scheme
artifact.

**This diagnostic could not retroactively fix this for Mem0 without re-running
ingestion under a shared, reusable identity scheme (out of scope — no rerun was
permitted). Stated explicitly, per instruction, rather than silently reporting a
misleading 0.000 as if it meant something about content.** A real content-level
overlap comparison for Mem0 would require re-embedding/re-matching retrieved
content by text similarity, which was not attempted here (would itself be a new,
unrequested analysis, not a comparison of "existing raw results").

## 3. Selection effect vs. larger-retrieval-pool effect — cannot be perfectly isolated; here is what CAN be said

**This diagnostic cannot cleanly separate the two effects**, because the variant
changed both simultaneously (N=5→N=20 retrieval AND the provisional identity-slice
→ real threshold-based selection), with no ablation run (e.g. N=20 retrieval kept
under the OLD selection policy, or N=5 retrieval under the NEW threshold policy)
available in the existing raw data. Stated explicitly, as instructed.

What the existing data DOES support, as inference rather than clean isolation:

- **The retrieval-pool expansion is very likely the dominant driver of surfaced
  real answer differences.** 93.3% of variant selections (both foundations,
  identically) hit the `max_k=5` cap — meaning the calibrated threshold (0.263) only
  actively EXCLUDES a candidate in ~7% of tasks; for the large majority, the
  selection stage's real job was choosing WHICH 5 of the (now up to 20, real)
  candidates rank highest by real cosine score, not whether 5 clear the bar at all.
  Since the primary run's pool was capped at N=5 by construction (nothing to choose
  among), a materially different, larger real candidate pool reaching the reasoning
  layer is the most direct explanation for why 92/120 (Mem0) and 71/120 (A-MEM) real
  final answers changed.
- **The selection mechanism's own contribution is real but secondary at this
  threshold**: it determines the specific ranking/ordering among the enlarged pool,
  and produces the real, non-zero rejection this project has never had before
  (avg. 11.58-12.89 real rejected candidates/task) — but rarely reduces the
  selected count below 5 (0 zero-selection cases across 240 real tasks, both
  foundations).

## 4. Rejection events — correctly represented in the canonical event ledger

Verified directly against a real pool's raw event ledger (not assumed): pool
`locomo-sp_031ba2ff9ce2625c` (`phase3/experiments/results/canonical_store/3.3-SELECTION-POLICY-FULL-2026-09-07/locomo-sp_031ba2ff9ce2625c/events/events.jsonl`)
contains real, correctly-typed events: `{'retrieved': 47, 'selected': 15,
'rejected': 32}` for that pool's real tasks — `rejected` events exist, are typed
correctly, and their count is consistent with `retrieved - selected` for that pool.

## 5. Anomalous zero-selection cases

**None found.** 0/240 real variant tasks (both foundations) selected zero
candidates — the calibrated threshold (5th-percentile-of-real-gold-evidence-scores)
is permissive enough that some candidate always clears it in this real sample.
Whether this remains true at a different threshold or task distribution is not
tested here (out of scope — no recalibration).

## 6. Provenance reconstructability

Every variant pool's real canonical ledgers (`memory/`, `events/`, `run_config/`)
were written via the same, unmodified `canonical_wiring.py` helpers the primary
dataset's own real campaign already used — `provenance_graph.build_provenance_graph()`
can be called against any variant pool's ledger triple exactly as it can against any
primary-dataset pool's, with no new code path required. Not re-verified with a fresh
graph build in this diagnostic (out of scope — this is a structural claim, already
proven for the underlying mechanism by `PHASE3_3_H4_PROVENANCE_GRAPH_EXTENSION_IMPLEMENTATION_REPORT.md`
and `PHASE3_3_H4_MULTI_BOUNDARY_REAL_DEMONSTRATION_REPORT.md`, not something this
diagnostic needed to re-derive).

## 7. What this diagnostic does NOT do, per explicit instruction

- Does not recalibrate or tune the threshold.
- Does not re-run either campaign.
- Does not alter the primary dataset.
- Does not resolve which of retrieval-expansion or selection-mechanism is "more
  correct" — only which is the more likely dominant driver of the observed answer
  changes, stated as inference, not proof.

## 8. Conclusion

The variant is real, internally consistent, and its rejection/selection mechanics
are correctly recorded end-to-end. The primary dataset remains untouched and is not
superseded by this diagnostic. The dominant real effect distinguishing the two
appears to be the larger real retrieval pool, with the calibrated selection
threshold contributing a real but secondary re-ranking/occasional-rejection effect
at this specific threshold value — an inference from the `max_k`-binding rate, not a
clean, isolated measurement.
