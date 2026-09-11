# Phase 4.12 — Phase 4 Freeze

Status: **FROZEN (2026-09-11).** This document closes Phase 4. It does not
introduce new mechanism, new code, or new real evidence — it is the final
consolidation: a master index of every Phase 4 document, a final
per-sub-phase status table, the final applicability summary across all
seven attacks, the honest, consolidated list of what remains open, and an
explicit statement of what "frozen" means from here forward.

## 1. What "Frozen" Means

From this point forward:

- No attack's real code, campaign scripts, or persisted run logs are
  modified to change a previously-reported result. New evidence about any
  of these seven attacks belongs in a new, dated, additive document or
  campaign — never a silent edit to an existing one.
- `phase3/evaluation/` remains frozen, as it has been for the whole of
  Phase 4 — verified via `git status --porcelain phase3/evaluation/`
  before and after every real campaign this project ran, always empty.
- The 4.2 Common Attack Contract (Revision 3) is frozen. Any future
  attack added to this inventory gets an additive row in its Section 9
  table, per the precedent Sleeper Memory Poisoning's own addition set —
  never a retroactive schema change to accommodate it.
- The applicability classifications in Section 3 below are frozen as
  reported. A future architectural review could revisit one with new,
  independent scientific justification (per the same governance
  `PHASE4_MPBENCH_SCOPE_AND_PRIORITY_POLICY.md` already established for
  `V3-Hybrid-Extended` candidates) — but not by assumption.

## 2. Master Document Index

**4.1 — Attack Inventory & Source Verification**
- [PHASE4_4_1_SYNTHESIS.md](PHASE4_4_1_SYNTHESIS.md) — the registry (7 resources)
- Per-attack dossiers: [AgentPoison](PHASE4_4_1_AGENTPOISON_DOSSIER.md), [MINJA](PHASE4_4_1_MINJA_DOSSIER.md), [FARMA](PHASE4_4_1_FARMA_DOSSIER.md), [MemoryGraft](PHASE4_4_1_MEMORYGRAFT_DOSSIER.md), [DSRM](PHASE4_4_1_DSRM_DOSSIER.md), [MPBench](PHASE4_4_1_MPBENCH_DOSSIER.md), [Sleeper Memory Poisoning](PHASE4_4_1_SLEEPER_MEMORY_POISONING_DOSSIER.md)

**4.2 — Common Attack Contract**
- [PHASE4_4_2_COMMON_ATTACK_CONTRACT.md](PHASE4_4_2_COMMON_ATTACK_CONTRACT.md) (Revision 3, frozen)
- [PHASE4_4_2_V3HYBRID_EXTENDED_ARCHITECTURE_REVIEW.md](PHASE4_4_2_V3HYBRID_EXTENDED_ARCHITECTURE_REVIEW.md)
- [PHASE4_MPBENCH_SCOPE_AND_PRIORITY_POLICY.md](PHASE4_MPBENCH_SCOPE_AND_PRIORITY_POLICY.md)
- [PHASE4_CROSS_ATTACK_ARCHITECTURE_REVIEW.md](PHASE4_CROSS_ATTACK_ARCHITECTURE_REVIEW.md)

**4.3/4.4 — Reference Implementation Integration / MAMBench Reconstruction**
- [AgentPoison](PHASE4_4_3_AGENTPOISON_INTEGRATION_PLAN.md), [MINJA](PHASE4_4_3_MINJA_INTEGRATION_PLAN.md), [MemoryGraft](PHASE4_4_3_MEMORYGRAFT_INTEGRATION_PLAN.md), [Sleeper Memory Poisoning](PHASE4_4_3_SLEEPER_MEMORY_POISONING_INTEGRATION_PLAN.md)
- [FARMA](PHASE4_4_4_FARMA_RECONSTRUCTION_PLAN.md), [DSRM](PHASE4_4_4_DSRM_RECONSTRUCTION_PLAN.md)

**4.5 — MPBench Integration**
- [PHASE4_4_5_MPBENCH_INTEGRATION_PLAN.md](PHASE4_4_5_MPBENCH_INTEGRATION_PLAN.md)

**4.6 — Poison Artifact & Injection Model**
- [PHASE4_4_6_POISON_ARTIFACT_AND_INJECTION_MODEL.md](PHASE4_4_6_POISON_ARTIFACT_AND_INJECTION_MODEL.md)

**4.7 — Attack ↔ Phase 3 Agent Integration**
- [PHASE4_4_7_ATTACK_PHASE3_INTEGRATION.md](PHASE4_4_7_ATTACK_PHASE3_INTEGRATION.md)

**4.8 — Controlled Attack Campaigns**
- [PHASE4_4_8_CONTROLLED_ATTACK_CAMPAIGNS.md](PHASE4_4_8_CONTROLLED_ATTACK_CAMPAIGNS.md)
- [PHASE4_4_8_SLEEPER_MEMORY_POISONING_CAMPAIGN.md](PHASE4_4_8_SLEEPER_MEMORY_POISONING_CAMPAIGN.md)

**4.9 — Attack Ground Truth**
- [PHASE4_4_9_ATTACK_GROUND_TRUTH.md](PHASE4_4_9_ATTACK_GROUND_TRUTH.md)

**4.10 — Cross-Attack Validation**
- [PHASE4_4_10_CROSS_ATTACK_VALIDATION.md](PHASE4_4_10_CROSS_ATTACK_VALIDATION.md)

**4.11 — Reproducibility**
- [PHASE4_4_11_PHASE4_REPRODUCIBILITY.md](PHASE4_4_11_PHASE4_REPRODUCIBILITY.md)

**4.12 — Freeze**
- PHASE4_4_12_PHASE4_FREEZE.md (this document)

**Governing/foundational**
- [PHASE4_HANDOFF_REPORT.md](PHASE4_HANDOFF_REPORT.md) (Phase 3 → 4 handoff, pre-existing)
- [PHASE4_PRE_FLIGHT_DECISIONS.md](PHASE4_PRE_FLIGHT_DECISIONS.md) (4 governing decisions)

**29 documents total** (`ls phase3/experiments/PHASE4_*.md | wc -l`,
re-verified during this freeze's own release audit — corrected from an
earlier stated count of 28, which omitted this document from its own
index), every cross-reference checked programmatically (every `.md` link
and every `phase4/*.py`/`.txt`/`.json` path referenced in backticks across
all 29 documents resolves to a real file — 84 distinct `phase4/` paths
checked, 0 missing) as of this freeze.

## 3. Final Applicability Summary (all seven attacks)

| Attack | Applicability | Architecture | Real campaign(s) | Real defect(s) found & fixed |
|---|---|---|---|---|
| AgentPoison | `APPLICABLE` | v3_hybrid (canonical) | Trigger-bearing + benign control (Mem0) | 1 (`content_type` self-labeling) |
| MINJA | `APPLICABLE` | v3_hybrid (canonical) | 2 candidates, single+joint mask (Mem0) | 0 |
| FARMA | `APPLICABLE` (reconstruction) | v3_hybrid (canonical) | Base + store_evasion + adaptive_paraphrase (Mem0) | 1 (`InjectionSequence`/`sequence_id` gap) |
| MemoryGraft | `APPLICABLE` | v3_hybrid (canonical) | Real campaign + real `ATTACK_FAILURE` demo (Mem0) | 0 (clean re-validation) |
| DSRM | `APPLICABLE` (both variants) | v3_hybrid (canonical) | Black-box + white-box, both carried to full campaign (Mem0) | 1 (`content_type` mismatch vs. contract) |
| MPBench-PCFI | `APPLICABLE` (2 of 6 classes); C1/C3/C4 `NOT_APPLICABLE`, documented | v3_hybrid (canonical) | 3 scenarios (Mem0) **+ 1 scenario (A-MEM)** | 0 (clean on first build) |
| Sleeper Memory Poisoning | `PARTIALLY_APPLICABLE` (external-manager regime only; tool-based regime `NOT_APPLICABLE`) | v3_hybrid (canonical) | Full 2×2 + 5-condition trigger sweep (Mem0) | 0 (clean on first build) |

**3 of 7 attacks' re-validation passes found and fixed one real defect
each** (AgentPoison, FARMA, DSRM); **4 of 7 came back clean** (MINJA never
needed one, MemoryGraft/MPBench/Sleeper each built correctly on the first
pass, applying lessons the earlier three had already surfaced). This
progression — real defects front-loaded, later attacks clean — is itself
evidence the project's own cross-attack learning was real, not
decorative (`PHASE4_4_10_CROSS_ATTACK_VALIDATION.md` Section 3.2).

## 4. Final Numbers

- **7 attacks**, all with at least one real, executed campaign against
  real infrastructure (real `RealMem0Adapter`/`RealAMemAdapter`, a real
  identity-verified pinned LLM server).
- **97 unit tests, 97 passing** (`phase4/tests/`), all mocked/scripted,
  reproducible with no external infrastructure.
- **26 real entry-point scripts** (25 with a persisted, citable log or
  artifact file — `agentpoison/core.py`'s own `__main__` is an internal
  smoke check with no persisted output of its own), per
  `PHASE4_4_11_PHASE4_REPRODUCIBILITY.md` Section 3. Corrected from an
  earlier stated count of 25 during this freeze's own release audit — the
  underlying table was already complete and accurate; only the prose
  summary count above it had an arithmetic error.
- **10 real query trials** where an attack's own designed trigger
  condition was used resulted in the poison reaching the agent's visible
  context — 0 exceptions (`PHASE4_4_8_CONTROLLED_ATTACK_CAMPAIGNS.md`
  Section 4).
- **1 real trial** against A-MEM (in addition to Mem0-only coverage for
  the other six), **1 real `POISON_NOT_ADMITTED`/`ATTACK_FAILURE`
  observation**, and **1 real white-box DSRM campaign** — all added during
  this freeze's own final gap-closing pass, per user direction.
- **Zero modifications to any frozen `phase3/evaluation/` file**, verified
  repeatedly throughout, confirmed one final time as part of this freeze.

## 5. What Remains Genuinely Open (disclosed, not resolved by this freeze)

Freezing Phase 4 does not mean every disclosed limitation was closed —
only that every one still open is named explicitly here, not left
implicit:

1. **A-MEM coverage is n=1.** One real trial, one scenario, one attack.
   Real evidence the project's core finding generalizes at all beyond
   Mem0 — not general A-MEM coverage across all seven attacks.
2. **No genuine post-admission `ATTACK_FAILURE` has been observed.** The
   one real `ATTACK_FAILURE` evidence this project has is pre-admission
   (a gate refusing an artifact). A case where a poison is admitted,
   selected, yet generation genuinely resists it has never occurred in
   any real trial.
3. **No defense/mitigation evaluation exists anywhere in this project.**
   Every one of the seven source papers evaluates at least one defense;
   MAMBench has built none. This is a real scope boundary, not an
   oversight — defenses were never in Phase 4's charter.
4. **MemoryGraft's Milestone 2 content design has 1 real scenario**, not
   the originally-planned 3–5.
5. **Every real result is n=1 or n=2 per condition.** Consistently
   disclosed throughout every attack's own documentation — real,
   reproducible, single/few-trial evidence, not statistically powered
   claims.
6. **No automated CI/re-run harness exists** — by informed choice, not
   oversight (`PHASE4_4_11_PHASE4_REPRODUCIBILITY.md` Section 7).

None of these block the freeze — Phase 4's own stated goal (per
`PHASE4_MPBENCH_SCOPE_AND_PRIORITY_POLICY.md` Section 17) was "maximum
scientific validity + mechanism diversity + reproducibility + lifecycle
coverage + provenance + attribution within a coherent victim
architecture — not maximum attack count" or exhaustive coverage. Every
item above is a legitimate direction for a future phase, not a defect in
this one.

## 6. Scientific Positioning Statement

MAMBench Phase 4 should be described as: **a unified benchmark
implementing seven structurally diverse memory-poisoning attack
mechanisms against a single, frozen, real victim architecture
(V3-Hybrid), each validated through at least one real, reproducible
campaign with real counterfactual measurement, real provenance tracking,
and an honestly-scoped ground-truth vocabulary — not a benchmark claiming
exhaustive attack coverage, statistically powered success rates, or
defense evaluation.**

Every one of the seven attacks' real campaigns produced convergent, not
contradictory, evidence: when an attack's own designed trigger condition
was met, its poison reliably reached the agent's visible context and
measurably influenced the generated answer, across white-box gradient
optimization, black-box LLM-driven reasoning, query-only agent-mediated
insertion, gated experience-imitation, and dormant/trigger-activated
mechanisms alike. This is the project's central real finding — stated at
the scope the real evidence supports, not beyond it.

## 7. Sources

Every document listed in Section 2.
