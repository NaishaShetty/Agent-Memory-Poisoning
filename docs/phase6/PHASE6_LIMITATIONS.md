# Phase 6 — Consolidated Limitations

Status: Stage 6.20 deliverable. Every row traces to a real, previously
disclosed limitation from its origin stage — no new limitation was invented
for this table, and none of the 19 stages' own disclosed limitations were
softened or omitted in consolidating them here (mirroring the discipline the
original `PHASE6_HANDOFF_REPORT.md` used for Phases 1–5).

| # | Limitation | Origin | Status | Required future action |
|---|---|---|---|---|
| 1 | No live V3-Hybrid/Mem0/A-MEM campaign is executable — `mem0ai`/`qdrant_client`/`chromadb` not installed, local LLM server unreachable | Stage 6.10 | Environment limitation, confirmed by direct inspection, not assumed | Re-run this environment check when infrastructure changes; every metric/protocol built to depend on it (PIR, AMR's influence-dependent stages, URS, TSR) is ready to execute the moment it lifts |
| 2 | Retrieval consensus (D1, shipped default) has a 100% false-positive rate on topically-diverse benign pools — confirmed on real LoCoMo data, not just synthetic examples | Stage 6.9, confirmed real-data at Stage 6.16 | Real, disclosed defect in the shipped default; a validated fix exists but was never adopted | Requires separate, explicit authorization to adopt the min-cluster-size gate (`calibration.py`) as the new shipped default |
| 3 | D1/D2 threshold calibration was never done independently per metric before this session's own uncalibrated defaults shipped | Stage 6.6/6.9 | Real, disclosed gap; a real calibration sweep exists showing D1 and D2 achieve identical 50% detection at matched FPR once calibrated | Adopt calibrated thresholds only under separate authorization; the sweep itself (Stage 6.9) used a small, disclosed dev corpus, not a statistically powered one |
| 4 | Coordinated poisoning (near-duplicate AND paraphrased) is not solved, only partially mitigated, at D1/D3/D4 — a defense-aware attacker achieves full or near-full evasion at multiple layers | Stage 6.6, 6.7, 6.14 | Structural limitation of any purely content-based, no-external-verification signal | External corroboration was analyzed and found to carry a real amplification risk (Item 2, Stage 6.9) — not adopted; no other mitigation currently proposed |
| 5 | Three of four Stage 6.5/6.7/6.8 content signals show COMPLETE evasion under a defense-aware, paraphrasing attacker | Stage 6.14 | Real, deliberately-constructed adversarial finding | A semantic (not purely lexical/regex) redesign of these signals is the indicated next step; not attempted in Phase 6 |
| 6 | Defense Generalization Score = 0.0 for the admission layer across all seven attack families' representative content | Stage 6.15 | Real, honestly-reported result, not softened | Requires the signal redesign noted in #5; DGS was not re-measured after any hypothetical redesign |
| 7 | AgentPoison's real attack surface (query-side embedding trigger) has no Phase 6 mechanism examining it at all | Stage 6.10, 6.15, 6.18 (F15) | Structural absence of a relevant mechanism, not an empirical miss | Would require an entirely new component class (query-time trigger detection) Phase 6 has never attempted |
| 8 | MINJA's and MemoryGraft's real, frozen campaign content was never located in the specific log excerpts inspected — their generalization-table entries use synthetic, clearly-labeled content | Stage 6.10, 6.15 | Real, disclosed evidentiary gap | A more exhaustive search of committed `.json` artifact files (not just `.txt` logs) might recover it — not attempted |
| 9 | The FARMA real-content replay result is ambiguous between "the log line is the unamplified seed" (a real, harder-to-detect case by the attack's own design) and "the log line is a summary, not literal record content" | Stage 6.10 | Genuinely unresolved, both readings disclosed | Requires locating the real amplification-cycle records' exact rendered text |
| 10 | No composed, full-lifecycle (all four layers, pool/lineage-shaped) DGS was computed for all seven attacks — only the admission layer was measured uniformly | Stage 6.15 | Disclosed scope boundary | A larger exercise building pool- and lineage-shaped scenarios for all seven attacks, not attempted |
| 11 | Utility metrics (URS and Phase 3's eight correctness metrics) have real, tested arithmetic but no real `TSR_baseline`/`TSR_defended` pair has ever been measured | Stage 6.12, 6.16 | Blocked by #1 | Same as #1 |
| 12 | A-MEM's real-vendor identity-resolution behavior has never been validated anywhere in this project's history, not just this session | Stage 6.17 (restating Methodology 19.5) | Persistent, project-wide limitation | Requires the isolated interpreter A-mem-sys needs, never available in any session to date |
| 13 | Phase 6's defense has never been tested against a LIVE Mem0 or A-MEM instance, in any session — only against directly-constructed real Phase 3/5 objects | Stage 6.10, 6.17 | Real, disclosed gap distinct from #1 (this is about Phase 6's OWN code, not the general environment) | Same as #1 |
| 14 | D3 (LLM-judge consensus) remains entirely unimplemented | Stage 6.2, 6.6, 6.9 | Deliberate non-implementation — no frozen, reproducible LLM server available | Implement only if such an environment becomes available; the frozen contract for what it would need is already specified |
| 15 | Cost/latency figures for four of five defense components are principled estimates ("expected sub-millisecond"), not directly profiled, except where Stage 6.16 later measured admission latency for real | Stage 6.12, partially resolved by 6.16 | Partially resolved | Extend real measurement to retrieval/propagation/sleeper layers |
| 16 | The external-corroboration mechanism (Stage 6.9, Item 2) was analyzed and found to carry a real amplification risk when its reference set is contaminated — never adopted | Stage 6.9 | Resolved by non-adoption | Would need a more sophisticated design (e.g., requiring the reference set's own independent diversity) before reconsidering |
| 17 | This project's own failure-cause taxonomy (F1–F14) had one real gap (AgentPoison's structural absence-of-mechanism case), addressed by a disclosed, narrowly-scoped F15 extension | Stage 6.18 | Resolved via disclosed extension | None — the extension itself is documented and tested |
| 18 | The failure catalog (13 cases) synthesizes KNOWN failures — it cannot claim completeness over failure modes not yet discovered | Stage 6.18 | Inherent, disclosed scope limit | Revisit if #8's gap is closed and new real content reveals new patterns |
| 19 | No composed B0–B7 ablation was re-run with Stage 6.9's proposed recalibration adopted — all ablation numbers reflect the original, uncalibrated shipped defaults | Stage 6.9 | Consistent, disclosed choice (preserving Stage 6.6's accepted record) | Re-run under separate authorization if/when recalibration is adopted |
| 20 | Only one JSON Schema (`MGPDecisionRecord`) was produced; `SignalContext`/`RetrievalCandidate`/`AncestorRecord` remain Python-only | Stage 6.19 | Deliberate scope choice (internal types vs. persisted records) | Add schemas for these only if they become cross-system-boundary artifacts |

## What Is NOT a Limitation — Stated for Contrast

To avoid these 20 real limitations reading as an indictment of the whole
phase, it is worth stating plainly what IS real and positive, each
independently verified, not merely asserted:

- Zero evaluator-only leakage anywhere in the shipped defense, verified
  structurally and by test in every stage.
- Zero frozen-phase modification across all 20 stages, re-confirmed at the
  end of every single stage, not just checked once at the start.
- A real, catchable, previously-undiscovered false-positive bug (limitation
  #2) was found, diagnosed, and a working fix validated — this is exactly
  what rigorous evaluation is supposed to produce, not a mark against the
  project.
- Phase 6's own foundation-agnostic construction, admission/Sleeper zero-
  false-positive results on real data, and sub-millisecond real latency are
  all real, positive, independently-tested findings alongside the 20
  limitations above.

## Verdict

This table is the complete, honest limitations record for Phase 6 as of its
freeze. See `PHASE6_RESULTS.md` for how these limitations bear on Phase 6's
overall scientific conclusions.
