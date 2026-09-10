# MAMBench Phase 4 Handoff Report

Status: **Phase 3 is closed.** This document is the complete, standalone handoff —
everything a reader needs to understand what Phase 3 built, how it was validated,
and what Phase 4 must carry forward, without needing to read the dozens of
individual implementation/experiment reports this project produced. Those reports
remain the underlying evidence; this document is the synthesis. The full narrative
history behind every decision summarized here lives in
`phase3/PHASE3_COMPLETE_HISTORY_AND_ARCHIVE.md`.

**Revision note (final Phase 3 closure pass):** an earlier version of this report
named the V1 baseline agent (`runner.py::run_agent_task()`) as the canonical
artifact path. That is now stale. Following a full V1→V2→V3→V4→V5 research
sequence documented in the archive above, **V3-Hybrid is the final, canonical
Phase 3 memory foundation**, and every reference below has been corrected
accordingly. V1 remains real, frozen, shared infrastructure (V3-Hybrid's own
Condition A reuses it unchanged) but is no longer the artifact Phase 4 should treat
as "the" reference agent.

## 1. Final Phase 3 Foundation

**V3-Hybrid** (`phase3/evaluation/agent_runtime/campaign_v3_hybrid_runner.py`) is
the final Phase 3 memory foundation. It composes three independently-validated
pieces, not a new architecture:

- **Condition A (no memory)** — V1/V3's exact, unchanged `run_condition_a`.
- **Condition B (gold evidence)** — V3's exact temporal-resolved evidence
  construction, plus one bounded draft→verify→[revise] reasoning step
  (`canonical_verified_reasoning.generate_verified_answer`), the one mechanism
  originally validated during V5 experimentation with a real, reproduced gain on
  this condition specifically.
- **Condition C (retrieved memory, Mem0 and A-MEM)** — V3's exact, unchanged
  retrieval/selection/temporal-resolution pipeline. The same bounded verification
  step was tested here too and found not to reliably help (flat on A-MEM, a
  measured regression on Mem0), so V3-Hybrid deliberately does **not** apply it to
  Condition C.

## 2. Canonical Status

**FINAL / FROZEN / PHASE-4-ELIGIBLE.**

V1, V2, V3, V4, and V5 are historical/experimental variants, retained in full for
evidence and reproducibility, but are **not** the canonical foundation and must not
be promoted, merged into V3-Hybrid, or silently treated as "latest." `phase3_reference/`
is legacy, has zero live dependency from any active Phase 3 code (confirmed by
direct audit both when it was first segregated and again during this final closure),
and remains historical-only.

| | Canonical (use this) | Historical / non-canonical (real, but not the baseline) |
|---|---|---|
| Memory foundation | V3-Hybrid (`campaign_v3_hybrid_runner.py`) | V1 (`runner.py`), V2 (`campaign_v2_runner.py`, NO-GO), V3 (`campaign_v3_runner.py`), V4 (diagnosis-only, no runner), V5 (`campaign_v5_runner.py`, structured memory rejected) |
| Reasoning (Condition B) | `canonical_verified_reasoning.py` | `v5_reasoning_pipeline.py` (the original, untouched V5 source this was promoted from) |
| Dataset | `canonical_store/v3_hybrid_candidate/` | `dataset_full/`, `v2_candidate/`, `v3_candidate/`, `v5_candidate/` (all retained as real evidence) |
| Selection mechanism | `hybrid_selection.py` (pool=20, top-8, cosine 0.5/token-overlap 0.3/entity-overlap 0.2) | provisional identity-slice policy (superseded), `selection_policy.py`'s calibrated threshold policy (real, proven, not wired into the canonical path) |
| Legacy reference | — | `phase3_reference/` — zero active dependency, confirmed by direct audit |

## 3. Phase 4 Can Depend On

- `phase3/evaluation/agent_runtime/campaign_v3_hybrid_runner.py` — the sole
  canonical entry point (`run_condition_a`, `run_condition_b_hybrid`,
  `run_condition_c_v3_mem0`, `run_condition_c_v3_amem`, `V3_HYBRID_STORE`,
  `assemble_dataset_records`).
- `phase3/evaluation/agent_runtime/canonical_verified_reasoning.py` — the canonical
  bounded-verification reasoning primitive, at most 3 LLM calls per task, no loop
  construct.
- Canonical memory/event/provenance/lifecycle infrastructure: `ledger.py`,
  `event_ledger.py`, `canonical.py`, `canonical_event.py`, `memory_versioning.py`,
  `provenance_graph.py`, `identity.py`.
- Retrieval/selection: `hybrid_selection.py`. Temporal resolution:
  `temporal_resolution.py`.
- Real foundation adapters: `foundations_real/mem0_real_adapter.py`,
  `foundations_real/amem_real_adapter.py` (both real-qualified, 15/15 fixtures
  each, zero divergence; both require the isolated `C:\h4venv` interpreter).
- Attack-origin attribution machinery: `taint_propagation.tainted_memories()`, the
  provenance graph's `attack_origin_lineage()` query, `derived_from` edge
  reconstruction — all real, tested, and directly usable for Phase 4's
  clean-vs-manipulated comparison methodology.
- Counterfactual masking mechanism — real, validated at n=20 real-task scale for
  both foundations (mechanism proof, not full-dataset coverage — see §6).
- Multi-boundary provenance composition — real, verified against actual composed
  data from two independent real experiment runs.
- The 8-metric evaluation stack (`normalized`, `content_recall`,
  `date_normalized`, `number_word_normalized`, `nli_entailment`,
  `multi_reference`, `llm_judge`, plus the original frozen `exact`), all additive
  and reported side by side.

## 4. Phase 4 Must Not Modify

- The frozen V1–V5 datasets and result JSONs under `canonical_store/` — these are
  historical scientific evidence, not scratch files.
- `campaign_v3_hybrid_runner.py`'s composition logic (which pieces go to which
  condition) without a real, disclosed, separately-validated reason — this is the
  final, validated architecture, not a draft.
- The evaluation metric definitions in `phase3/evaluation/agent/*_correctness.py` —
  changing these would silently invalidate every historical comparison in this
  report and the archive.
- `v5_reasoning_pipeline.py`, `v5_structured_memory.py`, or any other V1–V5 source
  file, merely to "clean them up" — they are frozen experimental record, not live
  code Phase 4 should touch.
- The boundary contract (`phase3/evaluation/contracts/boundary.py`) that prevents
  evaluator-only data from leaking into agent-visible context.

## 5. Current Known Limitations

1. **Multi-hop / aggregation weakness.** Questions requiring aggregation across
   multiple memories remain a real, unresolved weak point. The one architectural
   attempt to address this (V5's structured-memory layer) was tried and rejected —
   it regressed general performance and failed its own motivating case on direct
   test.
2. **Reasoning failures despite evidence being present.** Even with gold evidence
   directly in context, the model sometimes fails to state the answer it was
   directly given ("quote-then-hedge"). Bounded verification (Condition B only)
   measurably helps this but does not eliminate it.
3. **Evidence-use / hedging behavior.** Two independent attempts to fix hedging via
   prompt engineering (an instruction, then a few-shot example) both backfired,
   making the model reach for one over-usable refusal phrase more often, including
   on cases it previously answered correctly. Neither was kept.
4. **Residual retrieval/selection failures.** Small and already well-characterized:
   ≈0.8% retrieval loss and ≈5.0% selection loss of the total Condition-B-vs-C gap
   (V4's attribution waterfall). Confirmed, not re-derived, during this closure —
   retrieval/selection is not the dominant bottleneck.
5. **Semantic-vs-string evaluation gap.** `normalized`/`content_recall` under-count
   genuine semantic correctness. `nli_entailment` recovers a real majority of that
   gap (63% of the normalized-vs-judge gap on held-out validation data) but not
   all of it; `llm_judge` remains the closest but is not asserted as ground truth.
   These are additive metrics, not a replacement hierarchy.
6. **LoCoMo annotation / evidence-link problems.** At least one directly-verified
   real case exists where LoCoMo's gold-evidence link points to a turn that does
   not itself state the fact (a different, adjacent, non-included turn does). This
   is a benchmark-annotation property; it must not be reinterpreted as an agent
   failure.
7. **Verification transfer uncertainty.** The bounded verify/revise mechanism's
   benefit was validated only for Condition B. Its non-transfer to Condition C was
   measured (flat on A-MEM, a real regression on Mem0) but never root-caused. This
   is an open question, not a solved one.
8. **Reproducibility / nondeterminism.** A real, measured, disclosed run-to-run
   variation exists even at `temperature=0` (Condition A shifted 3.3%→5.0% between
   otherwise-identical V2/V3 runs). GPU floating-point/embedding nondeterminism and
   retrieval tie-breaking are plausible contributors; this was never fully
   root-caused. Do not claim deterministic reproducibility.
9. **Model capability ceiling.** Qwen3-8B (Q4_K_M, non-thinking) has no scratch
   space to aggregate facts across turns in one pass. A smaller "thinking-capable"
   alternative (Qwen3-4B-Thinking) was piloted and rejected after producing 7/15
   empty/truncated answers under a realistic token budget — a measured feasibility
   failure, not a preference.
10. **Hardware / VRAM constraint.** A single RTX 4050-class GPU (6GB VRAM),
    already ~96% utilized by one running Qwen3-8B instance, with no headroom for a
    second concurrent model. This is a real experimental boundary, not an excuse,
    and it is the direct reason no larger/second model was evaluated.
11. **Engineering defect found and fixed during final closure.**
    `campaign_v3_hybrid_runner.py` was found, during this closure audit, to import
    `V5_VERIFIED`/`run_condition_b_v5` directly from `campaign_v5_runner.py` — a
    real isolation violation (Phase 4 must not need to import V5). Fixed by
    promoting the underlying, unmodified reasoning mechanism to
    `canonical_verified_reasoning.py` and reimplementing Condition B against
    shared, non-versioned primitives. A regression test
    (`test_hybrid_runner_has_zero_v5_imports`, parses real import statements via
    `ast`) now guards against this recurring silently.
12. **Observability limitation.** `used_memory_ids` (causally-observed, as opposed
    to merely retrieved/selected, memory use) is not populated anywhere in the
    runtime. This is a known, disclosed absence, not a bug being hidden.
13. **Lifecycle/provenance limitation.** A full independent re-audit of every
    H.1–H.4 mechanism's runtime authority (whether "implemented" fully matches
    "authoritative at runtime") beyond what the passing test suite already
    exercises was not separately re-derived from first principles during this
    closure. The passing test suite is real, direct evidence of correct function,
    but this specific meta-question was not re-litigated from scratch.

**Also flagged, unresolved, not part of the numbered limitations above:**
`"PROCESS DOCUMENTATION.docx"` — a file tracked since the project's original
baseline commit — is currently deleted in the working tree. This deletion is not
attributable to any action taken during Phase 3 closure and was not silently
accepted or restored; it is flagged here for the user's own review (git history
confirms it was tracked since `adfa4f7 Initial commit`).

## 6. What Phase 4 Should Investigate (opportunities, not solved problems)

- Why bounded verification helps Condition B but not Condition C — a real,
  disclosed open question with direct relevance to any Phase 4 mechanism that adds
  a verification/self-check step to a retrieval-based pipeline.
- Whether a genuinely different multi-hop/aggregation mechanism (not structured
  memory, which was tried and rejected) could close that gap — Phase 4's attack
  scenarios may need to reason about this gap either way, since a multi-hop
  reasoning failure and a memory-manipulation-induced failure can look similar in
  string-match terms.
- Extending real counterfactual coverage beyond the current 40/240-record sample if
  Phase 4's design needs broader causal-influence evidence than the existing
  mechanism proof provides.
- Whether wiring the real, calibrated selection-policy variant into a canonical
  path would materially change what Phase 4 can study for selection-manipulation
  attacks (currently the canonical path's selection stage is not meaningfully
  attackable — see §7 of the prior closure's own finding, preserved below).

## 7. What Phase 4 Must Not Assume

- That retrieval/selection is a fully solved problem for any task distribution
  beyond what was tested — it was found sufficient for LoCoMo at this scale, not
  proven universally sufficient.
- That verification (or any V3-Hybrid mechanism) provides a benefit on retrieved
  memory (Condition C) — it does not, on the evidence gathered.
- That normalized/content-recall scores reflect true semantic correctness — they
  systematically under-count it.
- That 85–90% correctness under strict string metrics is achievable on this
  model/hardware — it was explicitly assessed as not realistic.
- That answers are deterministic run-to-run — they are provably not.
- That `used_memory_ids` or any causal-usage signal is available at runtime — it
  is not populated.
- That V1/V2/V4/V5 code paths are safe to import into Phase 4 — none of them is
  the canonical foundation, and V5 specifically was found to have leaked into what
  should have been a clean dependency chain (now fixed).
- That LoCoMo's gold-evidence annotations are always complete or correctly
  attributed — they are not, in at least one directly-verified case.
- That the canonical path's selection stage is meaningfully attackable for a
  selection-manipulation study — it currently is not (identity-slice-derived, not
  the calibrated threshold policy), unless Phase 4 explicitly wires that in first.
- That `equivalent_to`/conversational `conflicts_with` automatic relationship
  detection works at deployable quality — it does not (best real F1 ≈ 0.533 for
  `equivalent_to`; `conflicts_with` only proven on a different, non-conversational
  genre).
- That Graphiti/Letta are qualified foundations — both remain genuinely out of
  scope, unqualified, unrevived.

## 8. Frozen Evidence

- **Primary V3-Hybrid evidence**:
  `phase3/experiments/results/canonical_store/v3_hybrid_candidate/dataset_full/clean_agent_dataset_v3_hybrid_locomo_120x2.json`
  (240 records = 120 LoCoMo tasks × {Mem0, A-MEM}) and
  `phase3/experiments/research_variant/results/score_v3_hybrid_full_campaign_results.json`
  (the authoritative scored tallies — see the archive's Section 15 table).
- Historical full-scale datasets: `dataset_full/` (V1), `v2_candidate/` (V2),
  `v3_candidate/` (V3), `v5_candidate/` (V5, plus corrected-prompt re-validation
  runs), all retained in full.
- Foundation qualification records: `canonical_store/qualification/{mem0,amem}/`
  (15/15 fixtures each, both foundations).
- Full research narrative and every rejected-approach rationale:
  `phase3/PHASE3_COMPLETE_HISTORY_AND_ARCHIVE.md`.
- Export schemas: `phase3/schemas/clean_agent_dataset_record_schema.json`,
  `phase3/schemas/provenance_graph_schema.json`.

## 9. Final Phase 3 Certification

**PASS**, with the limitations in §5 explicitly carried forward (not resolved by
declaring the foundation frozen). Verdict basis: the one real, material
engineering defect found during closure (the V5-coupling isolation violation, §5
item 11) has been fixed and is now guarded by an automated regression test; the
full regression suite passes (1751 passed, 14 skipped, 0 failed, post-fix); Mem0
and A-MEM adapters are both confirmed functional via direct smoke test;
leakage/canonical-wiring/provenance/ledger/versioning/identity tests all pass
(444 passed, 11 skipped, 0 failed on the targeted subset); the V3-Hybrid
architecture is a validated composition of independently-tested pieces, not a
speculative design; and no scientific evidence, dataset, gold answer, or
historical result was altered to reach this verdict. None of the limitations in
§5 block Phase 4's safe use of V3-Hybrid as the memory foundation for
manipulation-attack research — they define its honest boundaries.

**Phase 3 is closed. Phase 4 may now begin, carrying forward the limitations in
§5-§7.**
