# Phase 6 Charter — Lifecycle-Aware Memory Defense

Status: DRAFT under active 6.1 development. Written 2026-09-13. Supersedes nothing;
inherits from `PHASE6_HANDOFF_REPORT.md` (repository root) and the Methodology Draft's
Sections 3 (Threat Model), 17 (Phase 4), 18–19 (Phase 5), and 20 (Attribution).

---

## 1. Research Question

> Can a provenance-aware, lifecycle-aware memory defense reduce successful memory
> poisoning across structurally different attack mechanisms while preserving benign
> memory utility?

This is a claim about a *defense*, not about the seven attacks. Phase 6 does not exist
to re-demonstrate that the attacks work (Phase 4 already established that, with real
counterfactual evidence) or to re-instrument the lifecycle (Phase 5 already did that).
Phase 6 exists to determine whether intervening at one or more lifecycle stages,
using only information a real deployed system could legitimately have, changes the
attacks' real-world outcome without destroying the agent's benign usefulness.

## 2. What Phase 6 Inherits (does not re-derive)

- **The ten-stage lifecycle** (Methodology §17.2): injection → admission → storage →
  retrieval → selection → exposure/use → propagation → influence → detection →
  attribution. Phase 6 defense intervention points are expressed against these ten
  stages, not a new lifecycle model.
- **The seven real attacks and their real capability profiles** (Methodology §17.3):
  AgentPoison (white-box gradient trigger optimization), MINJA (query-only,
  agent-mediated progressive insertion), FARMA (forged reasoning traces,
  self-referential amplification), MemoryGraft (gated, LLM-judged forged
  "successful experience" records), DSRM (black-box self-refinement + white-box
  InfoNCE optimization), MPBench-PCFI (unmarked fabricated facts), Sleeper Memory
  Poisoning (dormant, trigger-activated write). These remain frozen; Phase 6 evaluates
  against them, does not modify them.
- **MPBench's real write-channel taxonomy, C1–C4** (`PHASE4_4_1_MPBENCH_DOSSIER.md`):
  C1 = explicit instruction-executed write, C2 = system-prompt-driven write (agent
  evaluates content against its own retention policy), C3 = compaction-driven write,
  C4 = experience-to-procedure write. This is a *write-channel* taxonomy already
  frozen in this repository — Phase 6 reuses it rather than inventing a parallel
  "attacker capability C1–C4" framework. Cross-reference against V3-Hybrid's real
  channels: V3-Hybrid's live Mem0/A-MEM ingestion is a harness-level DIRECT_WRITE for
  six of the seven attacks (the attack harness writes directly, bypassing any
  agent-mediated judgment), and a genuine C2-like agent-mediated write only for
  MemoryGraft, whose harness-side persistence-judgment gate is the sole place in this
  project where "the agent evaluates content against its own retention policy" is a
  real, exercised mechanism. C3 (compaction) and C4 (experience-to-procedure) have
  no V3-Hybrid mechanism at all (`NOT_APPLICABLE`, confirmed in
  `PHASE4_4_2_COMMON_ATTACK_CONTRACT.md`) — Phase 6 cannot defend a write channel
  V3-Hybrid does not implement, and does not attempt to add one (that would be a
  Phase 3 modification for Phase 6's convenience, prohibited).
- **The nine-state ground-truth vocabulary** (§17.8): POISON_NOT_ADMITTED →
  POISON_ADMITTED → POISON_IN_CANDIDATE_POOL → POISON_SELECTED_TOP_K →
  POISON_RETRIEVED_BUT_NOT_USED / POISON_INFLUENCED_RESPONSE →
  TARGET_BEHAVIOR_TRIGGERED → ATTACK_SUCCESS / ATTACK_FAILURE. Phase 6 measures
  defense effect against this existing vocabulary; it does not define a new one.
- **The evidence-kind vocabulary** (§18.7): OBSERVED_EVENT, EXPOSURE_ONLY,
  COUNTERFACTUAL_EVIDENCE, LINEAGE_REACHABILITY. Any Phase 6 claim about what a
  defense mitigated must be labeled with one of these, exactly as Attribution already
  does — Phase 6 does not get to claim causal influence from anything weaker than a
  real `counterfactually_influential` event.
- **The agent-visible / evaluator-only boundary** (`phase3/evaluation/contracts/boundary.py`,
  `FORBIDDEN_KEYS`). This boundary is the single most important inherited constraint
  for Phase 6's Signal Contract (6.4): a real defense sits on the *legitimate* side of
  this boundary, never the evaluator-only side.

## 3. What Phase 6 Adds

Phase 6 introduces exactly one new concept the prior phases do not have: a **security
lifecycle**, running in parallel with Phase 3's existing memory lifecycle status
(`active` / `superseded` / `retired`) and Phase 5's ground-truth vocabulary, never
replacing either. This is formalized in Stage 6.3 (Memory Governance Policy) after
6.2's literature audit determines what states are actually defensible design choices
rather than borrowed vocabulary. No security-state model is frozen by this charter.

## 4. Protected Assets

1. **Memory store integrity** — the correctness and provenance-traceability of what
   persists in `CanonicalMemoryLedger` across Mem0/A-MEM.
2. **Agent-visible context integrity** — the rendered context a generation call
   actually sees (Phase 5 already fingerprints this; Phase 6 defends against it being
   poisoned, it does not change how it is measured).
3. **Task correctness** — V3-Hybrid's real, measured benign performance
   (81.7% Condition B / 82.5–85.8% Condition C LLM-judge correctness) as a
   non-negotiable floor. A defense that improves security while collapsing this floor
   is not a successful defense (Methodology §6, §19 of the Phase 6 prompt).
4. **Evidence integrity** — the evaluator-only / defense-available separation itself.
   A defense that works only because it silently read an evaluator-only field is not
   evidence of a working defense; it is evidence of a broken experiment.

## 5. Defense Intervention Points (frozen for 6.1; components to fill them are NOT frozen until 6.2)

Four conceptual layers, corresponding to lifecycle stage groups:

| Layer | Lifecycle stages covered | What "intervention" means here |
|---|---|---|
| D1 — Admission Governance | injection → admission | Decide whether a candidate memory is written to the store at all, and under what security state |
| D2 — Provenance / Integrity / Trust | admission → storage (persists across retrieval/propagation) | Attach and propagate a trust/security state that later stages can read |
| D3 — Retrieval-Time Defense | retrieval → selection → exposure | Filter/downrank/quarantine candidates in the pool before or during hybrid rerank |
| D4 — Propagation / Influence Control | propagation → (informs) detection/attribution | Contain contamination into derived/descendant memories without assuming all descendants of a suspicious memory are themselves malicious |

These four layers are a **scope decomposition**, not a promise of four specific
mechanisms. 6.2 may find that a published defense covers two layers at once, that one
layer has no reproducible candidate at all (in which case MGP fills it natively), or
that the layer boundaries themselves need adjusting before 6.5 implementation begins.
The charter freezes the *lifecycle decomposition*; it does not freeze *how* each layer
is filled.

## 6. Legitimate vs. Evaluator-Only Information (frozen — this is the one boundary that must not move)

**Never available to a runtime defense decision**, per explicit instruction and
Rule 5/12 of the Phase 6 directive:
- `attack_id`, `attacker_originated` (Phase 4/5 evaluator-only provenance fields)
- Any of the nine ground-truth states above `POISON_ADMITTED` (i.e., the ground-truth
  label itself, as opposed to the raw events a real system could observe)
- The Sleeper Memory Poisoning trigger phrase/condition as a known label
- Any post-hoc counterfactual-influence finding (Attribution's `influence` type) —
  these exist only after generation has already happened and cannot inform an
  admission or retrieval-time decision for that same query
- Attribution's own outputs, as *inputs* to a runtime decision (Attribution is a
  read-only analytical consumer; Phase 6 may consume Attribution for **post-hoc
  analysis** of what a defense mitigated, per Stage 6.13, but a deployed defense
  component's own decision function must not call Attribution)

**Legitimately available** (subject to 6.4's full signal contract, not finalized here):
lifecycle event history for a memory identity, its ingestion source/channel, retrieval
frequency/rank history, structural relationship edges it participates in (from Phase
5's real relationship-derivation functions, not the ground-truth labels those
functions are sometimes compared against), and the memory's own content.

An **evaluator-only oracle baseline** (a defense given privileged information, run
purely for upper-bound comparison) is permitted but must be implemented as a clearly
separate, explicitly labeled NON-DEPLOYABLE / UPPER-BOUND-ONLY condition, never
blended into the deployable defense's own reported numbers.

## 7. Acceptable Operating Envelope (initial, non-final — see Stage 6.12)

- False-positive tolerance, latency budget, and memory/storage overhead ceilings are
  **not fixed by this charter**. They are Stage 6.12's job, informed by 6.2's finding
  of what published defenses actually report (so Phase 6's own targets are calibrated
  against real prior work, not invented in a vacuum).
- The one non-negotiable constraint fixed here: **utility retention is measured, not
  assumed**. Any defense configuration is reported alongside its benign-utility cost;
  none is accepted as "the" Phase 6 defense before that comparison exists (Stage 6.16).

## 8. Explicit Out-of-Scope for Phase 6 v1

- Repairing `LIFECYCLE_STATUS_UNKNOWN_VERSIONING_GAP` (frozen Phase 3 defect,
  Rule 10).
- Unifying the seven attacks' per-attack artifact dataclasses into one schema for
  convenience (explicit instruction; Phase 6 consumes Phase 5's common event
  substrate instead).
- Any modification to Attribution's six question types or its evidence discipline.
- Statistically definitive, publication-grade power for every claim — Stage 6.11 will
  set an honest, justified sample size; Phase 6 will report confidence intervals and
  non-significance honestly rather than overclaim (mirroring the Methodology's own
  §12.16 treatment of its McNemar's tests).
- A full defense against MPBench's C3/C4 channels, since V3-Hybrid has no C3/C4
  mechanism to defend (inherited NOT_APPLICABLE classification).

## 9. Stage 6.1 Acceptance Criteria

6.1 PASSES when:
1. This charter, the threat model, and the scope matrix are internally consistent
   with each other and with the frozen Phase 3/4/5/Attribution record (spot-checked
   against actual code, not just prior documentation — see repository audit).
2. Every defense intervention point named is mapped to a real, existing Phase 5
   evidence source (no intervention point is proposed that Phase 5 cannot actually
   observe).
3. The evaluator-only boundary is stated unambiguously and independently checkable
   (i.e., a future test can assert a specific field is never read by a specific
   function).
4. No frozen file was modified to produce these documents.

## 10. Verdict

**6.1 — PASS**, pending final cross-check against `DEFENSE_THREAT_MODEL.md` and
`DEFENSE_SCOPE_MATRIX.md` (this charter is one of three required 6.1 deliverables;
see those documents for the per-attack threat table and the lifecycle×layer×evidence
matrix respectively).
