# Phase 5 Handoff Report

**Historical document — preserved as scientific record, not current guidance.** Written
at the point of Phase 4's freeze (2026-09-11), before Phase 5's actual scope was decided.
Phase 5 in fact became **Instrumentation & Monitoring** (event schema, lifecycle/
retrieval/agent-decision/lineage instrumentation, trace assembly, validation), not the
"defense evaluation" direction this document's own Section 7 recommended — that
recommendation was never binding (Section 7 says so explicitly) and a different, real
research need (observability before defense) was chosen instead. Phase 5 is now complete
and frozen; see [`phase5/PHASE5_CHECKLIST.md`](phase5/PHASE5_CHECKLIST.md) for its actual
final state and [`PHASE6_HANDOFF_REPORT.md`](PHASE6_HANDOFF_REPORT.md) for the current,
up-to-date handoff into Phase 6. This document is kept unmodified below for chronology —
it accurately records what Phase 4 established and what was open at that exact point in
time, not what is true of the repository today.

Status: **Handoff document, not a Phase 5 implementation plan.** Written
at the point of Phase 4's freeze (2026-09-11), for whoever (human or
agent) picks up Phase 5 next. This document does not decide Phase 5's
architecture — it hands over what Phase 4 actually established, what it
deliberately did not, and the real open questions that remain, so Phase 5
starts from evidence rather than from re-deriving Phase 4's own state.

## 1. Current Project State

- **Phase 3: frozen.** `phase3/evaluation/` — the canonical V3-Hybrid
  implementation (retrieval, selection, agent runtime, foundations, LLM
  provider, counterfactual masking, contracts/boundary enforcement) — has
  not been modified since before Phase 4 began, and was never modified
  during Phase 4. Verified via `git status --porcelain phase3/evaluation/`
  repeatedly throughout Phase 4's entire duration, always empty.
- **Phase 4: frozen, as of 2026-09-11.** Full record:
  [`phase3/experiments/PHASE4_4_12_PHASE4_FREEZE.md`](phase3/experiments/PHASE4_4_12_PHASE4_FREEZE.md).
- **Canonical victim architecture**: V3-Hybrid (canonical, unmodified).
- **Seven attacks**, all with at least one real, executed campaign:
  AgentPoison, MINJA, FARMA, MemoryGraft, DSRM, MPBench-PCFI, Sleeper
  Memory Poisoning.
- **97/97 tests passing** (`phase4/tests/`), fully mocked/scripted, no
  external infrastructure required to run.
- **26 real entry-point scripts**, 25 with persisted, citable evidence
  (logs or JSON artifacts).
- **Reproducibility**: fully documented
  (`phase3/experiments/PHASE4_4_11_PHASE4_REPRODUCIBILITY.md`) — exact
  environment, exact recipe, exact determinism boundaries.

## 2. What Phase 4 Established

Real, evidence-backed findings — every one traces to a persisted log:

- **Seven structurally diverse memory-poisoning mechanisms** (white-box
  gradient optimization, black-box LLM-driven reasoning, query-only
  agent-mediated insertion, gated experience-imitation, dormant/
  trigger-activated document injection, and two flavors of unmarked
  fabricated facts) all successfully wrote content into V3-Hybrid's real
  memory store and, when their own designed trigger condition was met,
  had that content reach the agent's visible context and measurably
  influence the generated answer.
- **10 of 10 real query trials** (across the original seven-attack
  comparison) where an attack's own trigger condition was met resulted in
  selection into the agent-visible top-8 — zero exceptions.
- **Real counterfactual dependence confirmed** in every successful trial,
  via single-artifact or joint (multi-artifact) masking — interventional
  dependence evidence, explicitly never claimed as causal proof.
- **The single-mask-vs-joint-mask distinction is real and consequential**:
  MINJA's own Milestone 4 first showed a single mask can report
  "influential" while the underlying false belief persists; this directly
  motivated building joint masking, which FARMA then used from its own
  first campaign without rediscovering the problem.
- **The project's core finding is not Mem0-specific**: one real trial
  against the unmodified A-MEM adapter (run under Decision 2's own
  disclosed-confound fallback, since wiring A-MEM's Ollama fix would mean
  editing a frozen Phase 3 file) showed the same pattern.
- **A real judgment gate's refusal capability was confirmed firing outside
  its own calibration set**: a deliberately weak, LoCoMo-grounded
  artifact was genuinely `DISCARD`ed by MemoryGraft's gate in a real
  trial, not merely in isolated calibration.
- **Cross-attack learning compounded, verifiably**: 3 of 7 attacks'
  contract re-validation passes (AgentPoison, FARMA, DSRM) each found and
  fixed one real schema/content-type defect; the 4 built afterward
  (MINJA, MemoryGraft, MPBench, Sleeper) came back clean, applying
  lessons the earlier three had already surfaced.

## 3. What Phase 4 Did NOT Establish

Stated explicitly, not left implicit:

- **No exhaustive attack coverage.** Seven attacks were implemented; this
  is not a claim that these are the only, or the most severe,
  memory-poisoning techniques that exist.
- **No statistically powered success rate.** Every real result is n=1 or
  n=2 per condition. Real and reproducible — not a claim that "attack X
  succeeds Y% of the time" in any general sense.
- **No defense evaluation.** Every one of the seven attacks' own source
  papers evaluates at least one defense; MAMBench has built and evaluated
  zero. This was never in Phase 4's charter.
- **No broad A-MEM generalization.** One real trial, one attack, one
  scenario. Evidence the finding generalizes at all — not general A-MEM
  coverage.
- **No post-admission failure evidence.** The project's one real
  `ATTACK_FAILURE`/`POISON_NOT_ADMITTED` observation is pre-admission (a
  gate refusing an artifact before it ever reached the memory store). A
  case where a poison is admitted, selected, yet generation genuinely
  resists it has never been observed in any real trial.
- **No automated CI/re-run harness.** Every real result was run manually,
  once, by a human-directed agent session, following a documented but
  not automated recipe.

## 4. Canonical Frozen Components

Available for Phase 5 to build on, unmodified:

- **V3-Hybrid** (`phase3/evaluation/`) — canonical victim architecture.
- **Common Attack Contract, Revision 3** (`PHASE4_4_2_COMMON_ATTACK_CONTRACT.md`)
  — the `PoisonArtifact`/`InjectionEvent`/`InjectionSequence` schema and
  9-state ground-truth vocabulary.
- **`AttackAdapter`** (`phase4/shared/adapter.py`) — shared `execute()`/
  `collect()`, attack-specific `validate()`/`prepare()`/`generate()`/
  `inject()`.
- **`phase4/shared/campaign_runner.py`** — the real, shared retrieve →
  select → render → generate pipeline every attack's campaign uses.
- **`phase4/shared/counterfactual_joint_mask.py`** — multi-artifact
  counterfactual masking.
- **`phase4/shared/dormancy_report.py`** — ground-truth-state (candidate-
  pool vs. selected) reporting, now used by every attack's campaign.
- **`phase4/shared/controlled_campaign.py`** — the `ControlledCampaignRecord`
  uniform result shape.
- **Seven real attack implementations** under `phase4/attacks/`, each
  with real injectors, real (where applicable) judgment gates, and real
  persisted campaign evidence.
- **Evaluation semantics**: `attacker_originated`/`attack_id`/gate
  decisions live in metadata only, never in agent-visible `content` —
  enforced by `phase3/evaluation/contracts/boundary.py`'s
  `FORBIDDEN_KEYS`, confirmed to actually fire (not just exist on paper)
  during FARMA's Milestone 2.

## 5. Open Scientific Questions

Carried forward, not decided:

- **Memory-entry defenses**: can V3-Hybrid's write path be given a real
  admission policy (beyond the attack-harness-side judgment gates
  MemoryGraft/Sleeper built to simulate a missing capability) without
  breaking legitimate memory formation?
- **Lifecycle governance**: should dormancy/trigger-state (Sleeper's own
  real contribution) become a first-class V3-Hybrid-Extended capability
  rather than campaign-side measurement?
- **Provenance enforcement**: provenance metadata exists and is tracked,
  but nothing in V3-Hybrid currently *acts* on it (no filtering, no
  trust-scoring). Should it?
- **Self-reinforcing propagation/containment**: FARMA's amplification
  cluster crowded out 8 of 8 top-8 slots in one real trial. What, if
  anything, should contain volume-based crowding?
- **Sleeper/dormant-attack detection**: no detection mechanism was built
  or evaluated against any of the seven attacks.
- **Attack-origin attribution**: metadata-level attribution exists;
  whether it survives realistic conditions (e.g., an attacker who forges
  the metadata itself) was never tested.
- **Defense generalization**: whether a defense effective against one
  attack mechanism (e.g., a gate tuned on MemoryGraft's patterns)
  transfers to structurally different mechanisms (e.g., AgentPoison's
  gradient-optimized trigger) is completely open.
- **Post-admission attack resistance**: does anything in V3-Hybrid ever
  cause a selected, visible poison to NOT influence the answer? Never
  observed — worth deliberately testing for, not just waiting to see.
- **Cross-memory-foundation generalization**: one real A-MEM trial exists.
  Whether all seven attacks generalize to A-MEM, and whether A-MEM's own
  real architectural differences (note-linking, evolution steps, ChromaDB
  retrieval) create attack-specific effects Mem0 doesn't have, is open.

## 6. Frozen Limitations (carried forward from Phase 4.12 Section 5)

1. A-MEM coverage is n=1.
2. No genuine post-admission `ATTACK_FAILURE` has been observed.
3. No defense/mitigation evaluation exists anywhere in this project.
4. MemoryGraft's Milestone 2 content design has 1 real scenario, not the
   originally-planned 3–5.
5. Every real result is n=1 or n=2 per condition.
6. No automated CI/re-run harness exists.

## 7. Recommended Phase 5 Direction

The natural transition, given Section 5's open questions:

**Phase 4 asked: can diverse memory attacks compromise the unified victim
pipeline? → Answer: yes, consistently, across seven structurally
different mechanisms, with real counterfactual evidence.**

**Phase 5 could ask: can the memory lifecycle be defended against these
same seven attacks without destroying legitimate memory utility?**

This is a recommendation, not a decision already made by existing project
artifacts — no prior Phase 4 document commits to this framing as the only
valid next step. If Phase 5 pursues it, the natural evaluation shape is:
build one or more real defenses (write-path admission policy, retrieval-
time filtering, provenance-aware selection, detection-then-quarantine),
run them against the SAME seven frozen attacks under the SAME real
infrastructure, and measure both attack-suppression and benign-utility
preservation together — never one without the other, since a defense that
blocks all writes trivially "defeats" every attack while destroying the
system's actual purpose.

## 8. Phase 5 Non-Negotiable Principles

- **Phase 4 remains frozen.** No existing attack result, campaign log, or
  artifact is modified retroactively by Phase 5 work.
- **No silent retroactive changes** to any frozen document — Phase 5's
  own findings belong in new, dated, additive documents.
- **Defenses must be evaluated against the same frozen attacks** — not
  new, defense-favorable attack variants invented to make a defense look
  effective.
- **Clean-victim utility must be preserved and measured** — a defense
  evaluation without a benign-condition control is not a real evaluation.
- **Defense evaluation must include both attack and benign conditions**,
  run under the same real infrastructure, same discipline as Phase 4's
  own controlled campaigns (`PHASE4_4_8_CONTROLLED_ATTACK_CAMPAIGNS.md`).
- **Provenance must remain auditable** — attacker-origin metadata stays
  separate from agent-visible content, per the boundary enforcement
  Phase 4 relied on throughout.
- **Counterfactual evaluation remains intervention evidence, not causal
  proof** — the same Decision 4 discipline Phase 4 applied to every
  single influence claim.
- **No attack-specific defense hacks** unless independently, scientifically
  justified — a defense tuned to defeat one attack's specific artifact
  wording is not a defense, it's overfitting.
- **Every defense must be independently evaluated** against every attack
  it's claimed to address — not assumed to generalize.
- **Preserve baseline/control conditions** in every real campaign, exactly
  as Sleeper's 2×2 design and every other attack's benign-control trials
  already established as this project's own standard.

## 9. Suggested Phase 5 Evaluation Dimensions

Carried forward from the original handoff's own metric vocabulary — map
these to the actual research question asked, don't force every metric
into every experiment:

- **PAR** (Poison Admission Rate) — analogous to this project's own
  `POISON_ADMITTED` ground-truth state, now with a defense in front of it.
- **PR** (Poison Retention) — does a poison, once admitted, persist
  across the defense's own operation (e.g., a later re-scan)?
- **SDR** (Sleeper Detection Rate) — specifically relevant given Sleeper
  Memory Poisoning's own dormancy mechanism.
- **AMR** (Adversarial Mitigation Rate) — the direct attack-suppression
  counterpart to Phase 4's own `ATTACK_SUCCESS` rate.
- **DGS** (Defense Generalization Score) — does a defense trained/tuned
  against one attack transfer to the other six?
- **TSR** (True Success Rate, presumably benign-task success under
  defense) — the utility-preservation counterpart, never omitted.
- **URS** (Utility Retention Score) — same purpose, paired metric.
- **Latency/memory overhead** — a real defense has a real cost; Phase 4
  itself never instrumented this and flagged it as open.
- **Attribution accuracy / lineage-path fidelity** — whether Phase 4's
  existing metadata-level attribution actually holds up under adversarial
  conditions (Section 5).
- **Uncertainty / time-to-attribution** — if a detection-based defense is
  pursued, how confidently and how quickly.

## 10. Starting Point

Before writing any Phase 5 code, a future session should read, in order:

1. `phase3/experiments/PHASE4_4_12_PHASE4_FREEZE.md` — the full freeze
   record and master document index.
2. `phase3/experiments/PHASE4_4_2_COMMON_ATTACK_CONTRACT.md` — the frozen
   contract every attack (and any future defense evaluation) must respect.
3. `phase3/experiments/PHASE4_4_9_ATTACK_GROUND_TRUTH.md` — the real,
   evidence-cited ground-truth registry across all seven attacks, the
   natural baseline any defense evaluation compares against.
4. `phase4/shared/adapter.py` and `phase4/shared/campaign_runner.py` —
   the real, reusable infrastructure a defense evaluation would build on
   top of, not duplicate.
5. `phase3/experiments/PHASE4_4_11_PHASE4_REPRODUCIBILITY.md` — how to
   actually re-run any of the seven attacks for real, which any defense
   evaluation needs to do.

Then decide, with the user, whether Section 7's recommended direction
(defense evaluation against the frozen seven) is the actual Phase 5
scope, or whether a different research question from Section 5 takes
priority — this handoff does not make that call.
