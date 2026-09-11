# Phase 4.6 — Poison Artifact & Injection Model (Consolidated)

Status: **DONE (2026-09-11); updated 2026-09-11 to add Sleeper Memory
Poisoning as a seventh attack.** This document does not introduce new
mechanism or new code — it consolidates the `PoisonArtifact`/
`InjectionEvent`/`InjectionSequence` abstract schema already frozen in
[PHASE4_4_2_COMMON_ATTACK_CONTRACT.md](PHASE4_4_2_COMMON_ATTACK_CONTRACT.md)
(Revision 3) against the **seven real, built, tested implementations** now
existing under `phase4/attacks/` (AgentPoison, MINJA, FARMA, MemoryGraft,
DSRM, MPBench-PCFI, Sleeper Memory Poisoning), each already validated
through at least one real campaign against `RealMem0Adapter`. Its purpose
is to answer, with evidence rather than design intent: *does one injection
model actually describe all seven attacks' real code, or did each one
quietly drift into its own shape?*

## 1. The Abstract Schema (recap, unchanged from 4.2)

```text
PoisonArtifact
├── poison_id
├── attack_id
├── content                      # open Mapping[str, Any] — carries
│                                 #   content_type as an ordinary key,
│                                 #   never a new top-level field
├── injection_sequence_ref       # -> InjectionSequence, null for
│                                 #   single-artifact/single-step attacks
├── generation_config            # attack-specific generation provenance
├── attacker_capability
└── provenance

InjectionSequence                # for attacks whose provenance is an
│                                 #   ORDERED SET of steps, not one artifact
├── sequence_id
├── attack_id
├── steps[]                      # {step_index, poison_id/injection_id, cites[]}
└── sequence_type                 # QUERY_CHAIN | SEED_AND_AMPLIFICATION | ...

InjectionEvent
├── injection_id
├── poison_id
├── injection_method              # DIRECT_WRITE | AGENT_MEDIATED_WRITE | QUERY_SEQUENCE
└── attacker_originated
```

## 2. Concrete Artifact Schema Per Attack (as actually built, not as planned)

| Attack | Real dataclass | Fields | `poison_id`/`artifact_id` analogue |
|---|---|---|---|
| AgentPoison | `AgentPoisonArtifact` (`trigger_run.py`) | `poison_id, trigger_tokens, trigger_text, malicious_demonstration, fitness_score_initial, fitness_score_final, iterations_run, num_grad_iter, num_cand` | `poison_id` (literal field) |
| MINJA | `QuerySequenceStep` + `QuerySequence` (`injector.py`) | step: `step_id, step_index, text, step_kind`; sequence: `sequence_id, steps[], victim_query` | `step_id` per step |
| FARMA | `ReasoningTraceArtifact` (`reasoning_trace.py`) | `artifact_id, task_id, target_question, gold_answer, forged_claim, precedent_count, cites` | `artifact_id` |
| MemoryGraft | `PoisonedExperienceArtifact` (`persistence_gate.py`) | `artifact_id, req, resp, tag, semantic_targets` | `artifact_id` |
| DSRM | `AdversarialDecisionArtifact` (`decision.py`) | `artifact_id, task_id, target_question, gold_answer, forged_claim, planning_text, initial_planning_text, csrm_justification, srm_iterations_used, srm_converged, srm_final_similarity, variant, retrieval_text` | `artifact_id` |
| MPBench-PCFI | `PCFIScenario` (`scenario.py`) | `scenario_id, task_id, context, expected_memory, retrieval_query, gold_answer, adversarial_goal` | `scenario_id` |
| Sleeper Memory Poisoning | `SleeperArtifact` (`artifact.py`) | `artifact_id, task_id, target_question, gold_answer, distant_question, forged_memory_text, document_text` | `artifact_id` |

**Observation**: every real artifact independently converged on the same
core shape the abstract schema predicts — an id, a target question/query,
a real gold answer for later counterfactual reference, and attack-specific
generation provenance — despite being designed and built in seven separate
passes over this session, each grounded in a different source (a real repo
with a clear license for AgentPoison, a real repo with an ambiguous
license for Sleeper, dossier-only reconstruction for the rest). This is
real convergent validation of the 4.2 contract's shape, not something
assumed in advance. Sleeper's own artifact adds exactly one field no prior
attack needed — `distant_question` — a direct, honest reflection of its
real methodological difference from the other six (Section 4.6 below):
every other attack's campaign only ever needed ONE query per artifact;
Sleeper's own dormancy/trigger design requires a paired second query by
construction.

## 3. Concrete Injection Mechanics Per Attack

| Attack | `content_type` (final, post-fix) | `injection_method` | Judgment gate? | Sequence? | Key metadata (beyond `attacker_originated`/`attack_id`) |
|---|---|---|---|---|---|
| AgentPoison | `CONVERSATIONAL_FACT` | DIRECT_WRITE | No | No (`injection_sequence_ref` null) | — |
| MINJA | `CONVERSATIONAL_FACT` | QUERY_SEQUENCE (agent-mediated) | No | **Yes** — `sequence_id`, `step_index`, `step_kind` | — |
| FARMA | `REASONING_TRACE` | DIRECT_WRITE | No | **Yes** — `sequence_id`, `sequence_type=SEED_AND_AMPLIFICATION`, `cites[]`, `precedent_count` | — |
| MemoryGraft | `EXPERIENCE_PRECEDENT` | AGENT_MEDIATED_WRITE (gated) | **Yes** — `persistence_gate.judge_persistence()` | No | `gate_config_fingerprint`, `semantic_targets` |
| DSRM | `GENERAL_FACT` | DIRECT_WRITE | No | No | `variant` (black_box/white_box), `srm_converged`, `srm_iterations_used`, `srm_final_similarity` |
| MPBench-PCFI | `GENERAL_FACT` | DIRECT_WRITE (C2 channel) | No | No | `retrieval_query`, `adversarial_goal` |
| Sleeper Memory Poisoning | `GENERAL_FACT` | DIRECT_WRITE (external-manager/Mem0-analogue regime only) | **Yes** — `injection_gate.judge_injection()` | No | `distant_question`, `gate_decision`, `gate_rationale` |

Every attack's `add_memory()` call is real (via `RealMem0Adapter` in at
least one real campaign each) — this table describes executed code, not a
design intent that was never run. **Sleeper's `content_type` was
`GENERAL_FACT` from its first build**, not fixed after a defect was found
— the only attack among all seven where the self-labeling mistake
(Section 4.1 below) never happened at all, because the lesson from three
prior attacks was already in hand before Sleeper's code was written.
Sleeper is also the second attack (after MemoryGraft) with a real
judgment gate — a deliberate, disclosed design choice
(`PHASE4_4_3_SLEEPER_MEMORY_POISONING_INTEGRATION_PLAN.md` Section 2.2),
not a reflexive copy of MemoryGraft's: same missing-V3-Hybrid-capability
pattern, a different real question asked of the gate.

## 4. Cross-Cutting Patterns Found Empirically (not designed in advance)

### 4.1 The `content_type` self-labeling anti-pattern recurred three times independently

Across three separate Milestone 6/7 contract re-validations
(AgentPoison, FARMA cross-checked against AgentPoison's finding, DSRM), a
first implementation attempt used a `content_type` value that named the
attack itself (`AGENTPOISON_MALICIOUS_DEMONSTRATION`,
`ADVERSARIAL_DECISION`) rather than a legitimate content role. Each time,
this was caught by direct comparison against the contract's own specified
value or against a sibling attack's established pattern, and fixed to a
stealth-correct, contract-matching value (`CONVERSATIONAL_FACT`,
`GENERAL_FACT`, `EXPERIENCE_PRECEDENT`, `REASONING_TRACE`) — **by the time
MPBench and, later, Sleeper Memory Poisoning were built, this lesson was
applied on the first pass, with zero defect found in either's own
Milestone 6/7 re-validation.** This is the single clearest example in
Phase 4 of learning compounding across attacks rather than each
implementation starting from zero — now confirmed across two
consecutively-built attacks (MPBench, then Sleeper), not one.

### 4.2 Attack identity always lives in metadata, never in `content`

Confirmed structurally across all six: `attacker_originated`, `attack_id`,
and every attack-specific provenance field (`precedent_count`,
`srm_converged`, `gate_config_fingerprint`, `adversarial_goal`, etc.) are
metadata-only. This is not incidental — `_extract_content_text()` (per
`phase3/evaluation/agent_runtime/runner.py`) only ever surfaces `content.text`
to the agent's visible context, confirmed directly (not assumed) during
both the AgentPoison and DSRM re-validations. Metadata is where ground
truth and provenance live; `content` is exactly what a real attacker would
control and nothing more — a real, load-bearing separation the schema
enforces by construction, not by convention alone.

### 4.3 A hard security boundary was hit once, for real

FARMA's Milestone 2 attempted to write a `attack_label` metadata key and
was correctly rejected by `phase3/evaluation/contracts/boundary.py`'s
`FORBIDDEN_KEYS` enforcement (`FoundationBoundaryViolation`) — confirmed
defense-in-depth against evaluator-only data reaching a real foundation
call actually fires, not just exists on paper. Every attack's required
labeling string ("MAMBench reconstruction of X" / "MAMBench scenario
inspired by MPBench's taxonomy") lives in code comments, logs, and
documentation only, as a direct consequence.

### 4.4 Single-artifact vs. sequence-shaped attacks is a real, not cosmetic, distinction

MINJA and FARMA are genuinely sequence-shaped (a `sequence_id` groups
multiple ordered/related writes) — and this distinction had real
downstream consequences: FARMA's Milestone 5 needed **joint masking**
(single-mask alone was `NOT_COUNTERFACTUALLY_INFLUENTIAL` because 7
redundant copies remained selected), while every single-artifact attack
(AgentPoison, DSRM, MPBench-PCFI) only ever needed single masking, because
there was only ever one artifact to mask. The contract's
`injection_sequence_ref`/`InjectionSequence` schema is doing real
structural work, not decorative bookkeeping — confirmed by the one case
(FARMA) that actually needed it and the two design mistakes (the FARMA
`sequence_id` gap found in its own Milestone 7) that resulted from
under-using it.

### 4.5 No attack has a unified `AttackAdapter` class — RESOLVED by 4.7, and confirmed by Sleeper's own build

At the time this document was first written, none of the six attacks
implemented the full `validate`/`prepare`/`generate`/`inject`/`execute`/
`collect` interface on one class. Phase 4.7
(`PHASE4_4_7_ATTACK_PHASE3_INTEGRATION.md`) built `phase4/shared/adapter.py`'s
`AttackAdapter` and wrapped all six existing attacks in it. **Sleeper
Memory Poisoning is the first attack in this project built with a
concrete `AttackAdapter` subclass from its very first line of code**, not
retrofitted afterward — `SleeperAdapter` inherits `execute()`/`collect()`
unchanged and only implements `validate`/`prepare`/`generate`/`inject`,
exactly the shape 4.7 established. This is real confirmation that 4.7's
interface generalizes to a genuinely new attack, not just to the six it
was originally built to unify.

## 5. What This Consolidation Confirms Versus What Remains Open

**Confirmed by seven real, executed implementations**:
- The abstract `PoisonArtifact` shape (id + target + gold answer + generation
  provenance) is a faithful description of every attack actually built,
  not just a design aspiration.
- `content_type` carried inside `content`, never as a new top-level field,
  holds across all seven — zero exceptions, zero schema violations found in
  the final (post-fix) state of any attack.
- The sequence/single-artifact distinction maps directly onto when joint
  masking is actually needed, not just onto abstract "some attacks have
  multiple parts."
- The unified `AttackAdapter` interface (Section 4.5) generalizes to a
  genuinely new, seventh attack built directly against it, not only to
  the six it was retrofitted onto.

**Still open, tracked for a future phase, not resolved here**:
- `generation_config`'s exact shape (per-attack provenance fields) is
  consistent in spirit across attacks but not literally the same field
  names — a future formalization could standardize this, but doing so now
  would mean touching working, tested code across seven modules for a
  cosmetic gain, not a functional one; deferred rather than done reflexively.

## 6. Sources

- [PHASE4_4_2_COMMON_ATTACK_CONTRACT.md](PHASE4_4_2_COMMON_ATTACK_CONTRACT.md) (Revision 3, frozen)
- [PHASE4_4_7_ATTACK_PHASE3_INTEGRATION.md](PHASE4_4_7_ATTACK_PHASE3_INTEGRATION.md)
  (the `AttackAdapter` interface, Section 4.5's resolution)
- All seven attacks' real code under `phase4/attacks/` and their
  integration/reconstruction plans: `PHASE4_4_3_AGENTPOISON_INTEGRATION_PLAN.md`,
  `PHASE4_4_3_MINJA_INTEGRATION_PLAN.md`,
  `PHASE4_4_3_MEMORYGRAFT_INTEGRATION_PLAN.md`,
  `PHASE4_4_4_FARMA_RECONSTRUCTION_PLAN.md`,
  `PHASE4_4_4_DSRM_RECONSTRUCTION_PLAN.md`,
  `PHASE4_4_5_MPBENCH_INTEGRATION_PLAN.md`,
  `PHASE4_4_3_SLEEPER_MEMORY_POISONING_INTEGRATION_PLAN.md`
