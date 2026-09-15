# Phase 6 — Final Results Report

Status: Stage 6.20 deliverable, the capstone scientific record for Phase 6.
Synthesizes 19 prior stage documents; every claim below cites the stage and
test that established it. Written after all experiments described are
complete, per the explicit instruction never to write the conclusion first.

---

## 1. Research Question

*"Can a provenance-aware, lifecycle-aware memory defense reduce successful
memory poisoning across structurally different attack mechanisms while
preserving benign memory utility?"* (Charter, Stage 6.1)

## 2. Threat Model

Inherited, not invented: the seven real Phase 4 attacks' own capability
profiles (white-box gradient optimization, query-only insertion, forged
reasoning, gated forged experience, self-refinement + white-box optimization,
weak-signal fact injection, dormant document-embedded instruction), MPBench's
real C1–C4 write-channel taxonomy, and the ten-stage lifecycle (`DEFENSE_
THREAT_MODEL.md`). No new attacker class was invented for Phase 6.

## 3. Defense Design

A native Memory Governance Policy (MGP): six security states
(`UNASSESSED/TRUSTED/SUSPICIOUS/QUARANTINED/BLOCKED/RELEASED`), seven actions
(the brief's original six plus a disclosed, necessary `RELEASE`), and a
frozen transition table enforcing that no `BLOCK` is ever reachable directly
from `TRUSTED` (Stage 6.3). Chosen over wholesale adoption of any external
defense because the 6.2 literature audit found no single external system
spans more than one or two of the four intervention layers (D1–D4) the
research question requires, and none addresses D2 (persistent, propagating
trust) at all (`DEFENSE_GAP_ANALYSIS.md`).

## 4. Defense Components

| Layer | Mechanism | Stage |
|---|---|---|
| D1 Admission | 5-signal weighted heuristic (self-reference, decision-log vocabulary, perfection claims, template anomaly, provenance anomaly) — adapted, not reproduced, from FARMA's own SENTINEL defense | 6.5 |
| D2/D3 Retrieval | Dedup-dampened consensus divergence, lexical (D1) and semantic (D2, real `all-MiniLM-L6-v2` embeddings) variants sharing one clustering/dampening core | 6.6 |
| D4 Propagation | Lineage-taint signal: severity × distance-decay × content-retention, capped at `QUARANTINE` never `BLOCK` | 6.7 |
| Sleeper | Persistence-marker + response-directive-verb structural detection, multiplicatively gated by real retrieval-history dormancy | 6.8 |

## 5. Literature Positioning

Two external mechanisms proved faithfully reproducible (A-MemGuard's
consensus+lessons architecture; FARMA's own SENTINEL Reasoning Guard) and
were adapted as inspiration for D3 and D1 respectively — never adopted
wholesale, since neither alone met the lifecycle-spanning requirement.
ASB's, AgentPoison's, and MINJA's own published defenses are documented
negative results, retained as comparison floors (`DEFENSE_LITERATURE_
AUDIT.md`, `DEFENSE_COMPARISON_MATRIX.md`).

## 6. Implementation Architecture

41 Python modules under `phase6/defense/` and `phase6/evaluation/`, 19 test
files, 293 tests. Foundation-agnostic by construction — zero import-level
coupling to Mem0/A-MEM anywhere (Stage 6.17). Zero LLM/embedding cost for
four of five components; D2's real cost is measured (~11s one-time model
load, ~17ms warm per-pool encode) (Stage 6.12, 6.6).

## 7. Experimental Protocol

Frozen before any larger campaign (Stage 6.11): n=120 (matching Phase 3's own
precedent), Wilson score intervals, McNemar's exact test (verified to
reproduce the Methodology Draft's own two published p-values exactly),
Connor's (1987) sample-size formula, Benjamini-Hochberg FDR correction. n=120
is disclosed as detecting only a fairly strong effect (psi≈3.35) at the
pilot's own discordance rate — not claimed adequate for every possible effect
size.

## 8. Attack Evaluation

Real, frozen Phase 4 campaign content was replayed (never re-run — the
attacks' own frozen code was never invoked) against Stage 6.5's admission
guard (Stage 6.10): **FARMA (likely seed-only), DSRM, and MPBench-PCFI
content all evaded detection**; one real Sleeper document fragment was too
short to trigger its guard. AgentPoison, MINJA, and MemoryGraft's exact
real injected content was not located in the log excerpts inspected;
representative content (real fragment for AgentPoison, clearly-labeled
synthetic for the other two) was used instead (Stage 6.15).

## 9. Ablation Study

The full B0–B7 matrix was run (Stage 6.9). The original run's numbers were
**invalidated by a discovered bug** (the diverse-benign-pool false positive)
and re-run corrected: **B7 (all three layers) performs no better than B6
(admission+propagation) and strictly worse on false positives** — a real,
measured negative-interaction finding, not assumed. Sleeper is evaluated as
its own standalone condition per the brief's own structure.

## 10. Statistical Analysis

McNemar's test and Wilson intervals are implemented and validated (Stage
6.11) but have not yet been applied to a live campaign result — the
environment blocker (Section 19) means no real baseline-vs-defended paired
outcome data exists yet to run them against. The machinery is proven correct;
its first real application remains pending.

## 11. Cross-Attack Generalization

**Defense Generalization Score = 0.0** for the admission layer across all
seven attack families' representative content, computed fresh in one
internally-consistent pass (Stage 6.15) — not softened, not reinterpreted. A
real circularity risk in Stage 6.9's calibration data (overlap with the
FARMA/MemoryGraft mechanism family) was checked and confirmed not to
contaminate this specific number, since the calibration was never adopted as
a shipped default. AgentPoison's zero is qualitatively different from the
other six: a structural absence of any relevant mechanism (formalized as
Stage 6.18's disclosed F15 extension), not an empirical miss.

## 12. Benign Utility

Real LoCoMo conversational data (30 turns, `data/raw/locomo/locomo10.json`)
shows **zero false positives at the admission and Sleeper layers**, but
**100% false positives at the shipped retrieval-consensus layer** — an
independent, real-data confirmation of Stage 6.9's originally-synthetic
finding (Stage 6.16). A validated fix exists (the min-cluster-size gate,
re-confirmed on this same real data) but was never adopted as the shipped
default. Full task-success/correctness-metric utility measurement remains
blocked by the live-environment limitation.

## 13. Latency/Cost

Real, measured: admission layer ~53 microseconds/item on real LoCoMo content
(Stage 6.16); D2 embedding cost ~11s one-time load, ~17ms warm per-pool
encode (Stage 6.6/6.12). Four of five components have genuinely zero
model-call/token overhead, confirmed by import inspection, not merely assumed
(Stage 6.12).

## 14. Propagation Containment

All six required scenarios (direct descendant, benign transformation,
partial inheritance, mixed-origin, independent benign, suspicious-but-benign
derivation) produce distinct, correct outcomes (Stage 6.7). The "lineage
alone never BLOCKs" design rule is enforced by an explicit code assertion,
verified to hold even at the theoretical maximum taint score. A defense-aware
attacker fully launders taint through paraphrasing (Stage 6.14, V3) — the
same lexical blind spot D1 has, now confirmed to transfer to D4.

## 15. Sleeper Evaluation

All seven required scenarios (before/near/at/after activation, benign
dormant-looking, false trigger, semantically-similar-benign) produce
distinct, correct outcomes (Stage 6.8), using only legitimately-available
signals — the actual trigger phrase was never used, verified by static
analysis. A defense-aware attacker achieves full evasion via indirect
phrasing (Stage 6.14, V4).

## 16. Attribution Analysis

A read-only bridge (Stage 6.13) calls Attribution's real, unmodified
`attribute_memory()` orchestrator and structurally refuses the exact fallacy
the brief warns against ("blocked, therefore prevented influence"). Three
real evidence scenarios (never-admitted, admitted-but-untested,
counterfactually-confirmed) demonstrate the bridge reports only what real
`AttributionResult` values establish — Attribution itself was never modified.

## 17. Adaptive Attacker Results

Four new, defense-aware variants (never modifying frozen Phase 4 attacks):
**three of four achieve complete evasion** (V1 against D1, V3 against D4, V4
against Sleeper — all scoring exactly 0.0, not merely below threshold). The
fourth (V2, wider paraphrase spread against D1/D2) produced a genuinely
non-obvious result: spreading poison wider *degrades its own lexical
cohesion*, narrowing but not closing the detection gap, while semantic
clustering (D2) held firm regardless (Stage 6.14).

## 18. Failure Analysis

13 real failure cases synthesized from Stages 6.5–6.17, classified against
F1–F14 plus one disclosed F15 extension (Stage 6.18). **F2 (poison hidden
from admission detector) dominates at 4 of 13 cases** — the single most
consistent failure mode this project found. Three cases are resolved (a
pre-ship bug fix, an intentional design constraint, a rejected prototype),
kept in the record rather than deleted.

## 19. Limitations

20 consolidated limitations (`PHASE6_LIMITATIONS.md`), the most consequential
being: no live campaign is executable in this environment (blocking PIR,
AMR's influence stages, URS, TSR, and any real statistical test application);
the shipped retrieval defense has a known, unfixed 100% real-data
false-positive mode; and three of four targeted defense mechanisms are
fully defeated by a defense-aware attacker.

## 20. Reproducibility

Every threshold, version, and configuration is persisted in a real
`Phase6ReproducibilityManifest` reusing Phase 2/3's own canonical fingerprint
primitive (Stage 6.19). A real JSON Schema validates `MGPDecisionRecord`
instances. A real, generated (not fabricated) worked-example artifact is
committed.

## 21. Scientific Conclusions

Phase 6 built a real, modular, lifecycle-spanning defense architecture and
subjected it to genuinely adversarial, honest evaluation — including against
itself. The evidence supports a specific, bounded claim, not the strongest
one the brief's own "strong result" examples describe (Section 29 of the
Phase 6 directive):

**Phase 6 demonstrates that a lifecycle-aware defense architecture CAN be
built with strict evidence discipline (zero evaluator-only leakage, verified
structurally throughout) and CAN catch specific, real failure modes it was
never explicitly designed to find (the diverse-benign-pool bug) — but its
CURRENT, shipped content-detection signals do not yet generalize across
attack mechanisms (DGS=0.0) or survive a defense-aware adversary (3 of 4
targeted mechanisms fully evaded).** The propagation and retrieval layers'
real, structural design (lineage-capped-at-QUARANTINE, dedup-dampened
consensus) are sound engineering with disclosed, quantified limits, not
broken designs — but Phase 6 has not yet shown these mechanisms deliver
attack-mitigation value beyond what a well-instrumented, honestly-evaluated
absence-of-evidence report can claim.

This is not the strongest result Phase 6 could have reported, and it is not
the weakest either — it is the one the actual evidence, gathered without
shaping the search to find a predetermined conclusion, supports.

## 22. Future Work

In priority order, per the evidence gathered: (1) a semantic redesign of
Stages 6.5/6.7/6.8's content signals, since the lexical/regex approach shows
consistent, structural evasion; (2) adoption (under explicit authorization)
of the min-cluster-size gate and recalibrated D1/D2 thresholds, both already
validated on real data; (3) closing the live-environment blocker to unlock
PIR/AMR/URS/TSR and a real statistical-protocol application; (4) a
query-side detection component for AgentPoison-style trigger attacks, an
entirely new mechanism class Phase 6 has not attempted; (5) locating
MINJA/MemoryGraft's real injected content to close Phase 6's remaining
synthetic-content gaps.
