# Phase 4.10 — Cross-Attack Validation

Status: **DONE (2026-09-11).** Validates, with real evidence rather than
assumption, the cross-resource overlaps `PHASE4_4_1_SYNTHESIS.md` Section
4 flagged as "cross-check opportunities, not shortcuts to take without
separate validation" — that instruction is now actually carried out, for
all seven attacks. Also extends MPBench's own six-attack vulnerability
cross-check (`PHASE4_4_5_MPBENCH_INTEGRATION_PLAN.md` Milestone 6) to the
full seven, and records two genuine cross-attack consistency findings
that only became visible once every attack had real campaign evidence to
compare.

## 1. Validating the 4.1-Flagged Overlaps

`PHASE4_4_1_SYNTHESIS.md` Section 4 flagged four overlaps at inventory
time, explicitly unconfirmed. Checked now against real, built code:

| Flagged overlap | Validated? | Real evidence |
|---|---|---|
| MPBench's False Precedent Insertion ≈ FARMA's forged-reasoning-trace mechanism | **Validated, with a real, disclosed distinction** | `PHASE4_4_5_MPBENCH_INTEGRATION_PLAN.md` Milestone 2 confirmed FARMA's `reasoning_trace` schema and MemoryGraft's `PoisonedExperienceArtifact` both genuinely satisfy MPBench's own class definition — not by inspection alone, but by checking both already-real, already-campaigned artifact schemas directly against the definition. No third implementation was built, per the explicit decision not to triplicate. |
| MPBench's Skill-Procedure Insertion ≈ MemoryGraft's semantic-imitation mechanism | **Not validated — correctly left unconfirmed, because the underlying capability was never built** | Skill-Procedure Insertion requires MPBench's C4 write channel (experience-to-procedure synthesis), which `PHASE4_MPBENCH_SCOPE_AND_PRIORITY_POLICY.md` classifies `NOT_APPLICABLE` — V3-Hybrid has no skill-synthesis mechanism, and none was built solely to test this overlap, per the governing policy's own prohibition. The overlap remains a real, plausible conceptual observation from the dossiers, not something MAMBench's real code can confirm or deny. Reported as still-open, not silently dropped. |
| DSRM's "disguised as past experience" framing sits conceptually between FARMA and MemoryGraft | **Validated as a real, non-redundant middle position** | DSRM's real `AdversarialDecisionArtifact` (Planning Text + forged claim + CSRM justification) is neither a settled-precedent claim (FARMA's actual mechanism) nor an experience-imitation record needing a persistence judgment (MemoryGraft's actual mechanism) — it is a third, distinct thing: a claim that actively argues for its own trustworthiness. Confirmed by direct comparison of the three real artifact schemas in `PHASE4_4_6_POISON_ARTIFACT_AND_INJECTION_MODEL.md` Section 2, not merely restated from the dossier. |
| Author overlap (Zhen Xiang, AgentPoison/MINJA) | **N/A — not a testable claim** | A citation/provenance fact, not a mechanism overlap; nothing to validate against real code. Retained as historical record only. |

**New overlap found during this validation pass, not flagged in the
original 4.1 synthesis**: Sleeper Memory Poisoning's goal-rewriting
optimizer and DSRM's Self-Refine Module are the **same technique**
(black-box, LLM-driven, iterative cosine-similarity-gated rewriting) —
confirmed by direct comparison of `sleeper_eval/`'s real
`goal_optimization.txt` prompt (fetched and read from the source repo)
against `phase4/attacks/dsrm/srm.py`'s own real implementation
(`PHASE4_4_1_SLEEPER_MEMORY_POISONING_DOSSIER.md` Section 4's MAMBench
OBSERVATION). This is the only overlap in this project's whole inventory
discovered by reading a second source's methodology, not by comparing two
already-built MAMBench artifacts — and it directly shaped a real
implementation decision (Sleeper's reconstruction deliberately did not
build a second copy of the same optimizer).

## 2. Vulnerability Taxonomy — Extended to Seven Attacks

`PHASE4_4_5_MPBENCH_INTEGRATION_PLAN.md`'s own vulnerability cross-check
(dossier Section 6/8b's nine structural vulnerabilities) was built against
six attacks' real campaigns, before Sleeper existed. Re-checked here
against all seven — every conclusion **holds**, and Sleeper's own
campaign adds a new, sharper piece of evidence to two rows:

| Vulnerability | Channel | Status (unchanged from the six-attack pass) | What Sleeper's real campaign adds |
|---|---|---|---|
| V-M1 Instruction-Data Boundary Blindness | C1 | Reinterpreted, present in spirit | Sleeper's own payload is a *literal* instruction-data boundary attack (the paper's own C1-adjacent mechanism, dossier Section 8) — the clearest direct instance of this vulnerability's ORIGINAL, non-reinterpreted form in the whole inventory, even though V3-Hybrid's real injection path bypasses the model-decision step this vulnerability is actually about (Section 9 of the Sleeper integration plan). |
| V-M2 Source Attribution Failure | C2/C3 | Confirmed present | Sleeper's `gate_decision`/`gate_rationale` metadata — real provenance information that exists in this project's own data model — was never exposed to the agent's visible context in any real trial, confirmed directly, extending the six-attack finding to a seventh independently-built mechanism. |
| V-P1 Memory Write Policy Under-Specification | C2 | Confirmed present | Sleeper's own `injection_gate.py` is itself further proof this vulnerability is real: the attack-harness had to build a judgment step from scratch because none exists in canonical V3-Hybrid — the second attack (after MemoryGraft) forced to build the same missing capability independently. |
| V-P2 Compaction Without Source Filtering | C3 | Not applicable | Unchanged — Sleeper has no compaction-relevant mechanism either. |
| V-S1 No Write-Path Validation | C1/C2/C3 | Confirmed present | Sleeper's real `add_memory()` calls succeeded whenever its own gate said `KEEP`, with zero additional victim-side check — consistent with all six prior attacks. |
| V-S2 Shared Multi-Source Context | C1/C2/C3 | Confirmed present | Sleeper's campaign is the sharpest evidence yet: the SAME poisoned memory was shown, in the SAME real pool, to be selected under four related queries and correctly excluded under one unrelated query — direct proof the pool has no source-isolation, only ordinary topical relevance, gating what reaches the agent. |
| V-S3 Manipulable Compaction Trigger | C3 | Not applicable | Unchanged. |
| V-S4 No Validation for Skill Creation | C4 | Not applicable | Unchanged. |
| V-S5 Self-Improvement as Amplification | C4 | Not applicable | Unchanged. |

**Conclusion, unchanged in substance, now confirmed by a seventh
independent mechanism**: the same 5 of 9 vulnerabilities apply, the same
4 of 9 do not, for the same underlying architectural reason (no
compaction, no skill synthesis) — this is not a coincidence repeating
itself, it is the same root cause producing the same consequence every
time it's checked, which is itself a form of validation.

## 3. Cross-Attack Consistency Findings (visible only once all seven existed)

### 3.1 The "single-mask can mislead" failure mode was discovered once, then generalized correctly — never rediscovered from scratch

MINJA's Milestone 4 first found that `COUNTERFACTUALLY_INFLUENTIAL`
single-mask status can co-exist with an unchanged false *belief*
(`PHASE4_4_3_MINJA_INTEGRATION_PLAN.md`). This directly motivated building
joint masking (`phase4/shared/counterfactual_joint_mask.py`), which FARMA
then used from its own first real campaign, never rediscovering the
problem independently. `PHASE4_4_9_ATTACK_GROUND_TRUTH.md` Section 2.3
shows both attacks' real single-mask/joint-mask verdicts side by side —
this is the clearest documented case in the whole project of one attack's
real finding directly changing how a later attack's campaign was
designed, not just informing documentation.

### 3.2 The `content_type` self-labeling mistake was learned once, then never repeated

`PHASE4_4_6_POISON_ARTIFACT_AND_INJECTION_MODEL.md` Section 4.1 already
documented this across AgentPoison → DSRM. Confirmed here as holding
through the full seven: MPBench and Sleeper both used a correct,
contract-matching `content_type` from their first build, and MemoryGraft's
own dedicated re-validation (`PHASE4_4_3_MEMORYGRAFT_INTEGRATION_PLAN.md`
Milestone 5, closed in Phase 4.9) confirmed it was correct from ITS first
build too, despite predating the lesson chronologically — three
consecutive attacks (MemoryGraft by luck, MPBench and Sleeper by applied
lesson) with zero instances of this specific mistake, against three
consecutive earlier attacks (AgentPoison, FARMA, DSRM) that each made and
fixed it once.

### 3.3 No attack in this inventory contradicts another's real finding

A direct check, not assumed: does any attack's real campaign evidence
conflict with another's? None found. Every attack that achieved
`POISON_SELECTED_TOP_K` also showed the baseline answer reflecting its
forged claim (`PHASE4_4_9_ATTACK_GROUND_TRUTH.md` Section 1, ten
consistent real trials) — seven independently-designed mechanisms,
targeting the same frozen V3-Hybrid pipeline, produced convergent rather
than conflicting evidence. This is itself the strongest real finding
4.10 was positioned to make: it is not that each attack "works" in
isolation, it is that they all fail to be resisted by the same underlying
gaps (Section 2), which is a materially stronger scientific claim than
seven independent success stories would be on their own.

## 3.4 Addendum (2026-09-11): the finding now has real, if limited, cross-foundation support

Section 3.3's claim — that no attack contradicts another, and that all
seven produce convergent evidence against the same underlying V3-Hybrid
gaps — was, at the time this document was first written, evidence from
Mem0 campaigns only. `PHASE4_4_9_ATTACK_GROUND_TRUTH.md` Section 2.4 has
since added one real trial against the real, unmodified A-MEM adapter
(MPBench-PCFI's "activities" scenario, run per
`PHASE4_PRE_FLIGHT_DECISIONS.md` Decision 2's own disclosed-confound
fallback, since wiring the fix would mean editing a frozen Phase 3 file).
That trial showed the same qualitative pattern — selected, forged claim
reflected in the answer, real counterfactual dependence confirmed — as
every Mem0 trial. This is real, if single-trial, evidence that Section
3.3's cross-attack consistency finding is not an artifact of Mem0's own
specific retrieval behavior; it is not evidence that every attack would
behave identically against A-MEM (only one attack/scenario has been
tried), and is reported at exactly that scope, not generalized further.

## 4. What This Phase Does Not Claim

- Does not claim V3-Hybrid is uniquely vulnerable compared to any other
  memory-agent architecture — no other architecture was evaluated in this
  project.
- Does not claim these seven attacks are exhaustive or representative of
  all memory-poisoning techniques — only that, within this inventory,
  their real campaign evidence is mutually consistent rather than
  contradictory.
- Does not upgrade any attack's applicability classification — this phase
  validates existing classifications with evidence, it does not revise them.

## 5. Sources

- [PHASE4_4_1_SYNTHESIS.md](PHASE4_4_1_SYNTHESIS.md) Section 4 (the
  original, unconfirmed overlap flags)
- [PHASE4_4_5_MPBENCH_INTEGRATION_PLAN.md](PHASE4_4_5_MPBENCH_INTEGRATION_PLAN.md)
  Milestone 6 (the six-attack vulnerability cross-check this phase extends)
- [PHASE4_4_6_POISON_ARTIFACT_AND_INJECTION_MODEL.md](PHASE4_4_6_POISON_ARTIFACT_AND_INJECTION_MODEL.md),
  [PHASE4_4_9_ATTACK_GROUND_TRUTH.md](PHASE4_4_9_ATTACK_GROUND_TRUTH.md)
  (the consolidations this phase cross-references rather than repeats)
- [PHASE4_4_1_SLEEPER_MEMORY_POISONING_DOSSIER.md](PHASE4_4_1_SLEEPER_MEMORY_POISONING_DOSSIER.md)
  Section 4 (the DSRM/Sleeper optimizer overlap)
