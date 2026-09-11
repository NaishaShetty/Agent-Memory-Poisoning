# Phase 4.3 — Reference-Implementation-Informed Reconstruction Plan: Sleeper Memory Poisoning

Status: **Milestones 1–2 DONE (2026-09-11, this document); Milestones
3–7 documented below and executed in the same pass.** Grounded in
[PHASE4_4_1_SLEEPER_MEMORY_POISONING_DOSSIER.md](PHASE4_4_1_SLEEPER_MEMORY_POISONING_DOSSIER.md)
(direct inspection of the paper and the real, public repository at commit
`70de017714abd6d12bb4681e93437461ba6f9a19`) and
[PHASE4_4_2_COMMON_ATTACK_CONTRACT.md](PHASE4_4_2_COMMON_ATTACK_CONTRACT.md)
(Revision 3, frozen — this document adds Sleeper's row to the existing
applicability table; it does not change the contract's schema). This is
the seventh attack, additive to the existing six — no prior attack's code,
results, or documentation is modified.

## 1. Why This Is Neither a Pure Integration Nor a Pure Reconstruction

Per the dossier's Section 2: real code exists (unlike FARMA/DSRM/MPBench),
but its license is ambiguous (unlike AgentPoison's clear MIT grant). This
plan therefore follows AgentPoison's *rigor* (real payload variants
inspected, real prompts read directly, real mechanism preserved) combined
with FARMA/DSRM's *attribution discipline* (an original re-implementation
of the described mechanism, never copy-pasted code) — labeled throughout
as **"MAMBench reconstruction of Sleeper Memory Poisoning, informed by
direct inspection of the source repository"**, never as "the Sleeper
Memory Poisoning implementation."

## 2. Phase 4.2 — Common Attack Contract Integration

### 2.1 Required Capabilities (verified against the dossier, not assumed)

| Candidate capability | Actually required? |
|---|---|
| Memory write | **Yes** — DIRECT_WRITE via the real Mem0 path, same as every other attack. |
| External-content ingestion | **Yes** — the attack's own delivery vector (dossier Section 3/5); MAMBench models this as the injected memory's `content` text, matching how every prior attack's payload is delivered. |
| Persistent memory | **Yes** — the entire mechanism depends on it (dossier Section 4). |
| Delayed/decoupled retrieval | **Yes, and this is the attack's real differentiator** — MAMBench's existing pattern (inject in one script phase, query separately in a later phase) already provides this structurally; no new V3-Hybrid capability needed, only a campaign-design discipline (Section 5 below). |
| Trigger recognition as a distinct mechanism | **No** — per the dossier's Section 6 finding, the "trigger" is ordinary semantic-similarity-driven retrieval, which `hybrid_selection.py` already provides unmodified. Nothing new is required here. |
| Conditional activation as a distinct mechanism | **No**, same reasoning — "activation" is just "was it selected and did it change the answer," already representable in the existing ground-truth vocabulary (Section 2.3 below). |
| Attacker-controlled content | **Yes** — DIRECT_WRITE, `attacker_originated=True`, matching every attack. |
| Agent-mediated write / LLM injection-judgment | **Yes, and genuinely required to preserve the paper's own defining mechanism** — see Section 2.2. |
| Specific memory metadata | No new field — existing metadata pattern (attack_id, attacker_originated, target_question) suffices. |
| Multimodal input | No — the dossier's document corpus (news, legal filings, code, etc.) has no LoCoMo-conversational analogue and is out of scope, matching every prior attack's single-modality (text) treatment. |

**Conclusion: no new V3-Hybrid capability is required.** Applicability:
`v3_hybrid` (canonical), **no extension** — matching AgentPoison, FARMA,
DSRM (core), and MPBench-PCFI's own rows.

### 2.2 Why an Injection-Admission Judgment Gate Is Required (not optional)

The dossier's Section 4 establishes that the paper's own Stage 1
(Injection Rate) is explicitly a **judgment** question — does the target
model, upon processing the poisoned document, actually decide to write
the specified content to memory — not a given. V3-Hybrid's real
`RealMem0Adapter` is configured `infer=False` (confirmed repeatedly across
this project's prior work): nothing decides *whether* to keep ingested
content, only *that* it is stored verbatim. This is the **exact same
missing-capability gap** `phase4/attacks/memorygraft/persistence_gate.py`
was built to address for MemoryGraft's own analogous Stage-2 "is this
judged a legitimate successful experience" question.

**Decision, made explicitly rather than defaulted**: per the handoff's own
explicit warning not to implement this "as a generic fabricated fact"
that skips the defining mechanism, this reconstruction builds a second,
**distinct** judgment gate —
`phase4/attacks/sleeper_memory_poisoning/injection_gate.py` — reusing
MemoryGraft's gate's *pattern* (a real LLM call, KEEP/DISCARD-shaped,
strict parsing, no silent default) but asking Sleeper's own actual
question ("would processing this document cause a memory-worthy write of
the following fact?"), not MemoryGraft's question ("is this a plausible
successful past experience?"). Building a second gate rather than reusing
the first's exact prompt is deliberate: the two questions are related in
*shape* (both are attack-harness instrumentation simulating a missing
V3-Hybrid judgment step) but different in *substance*, and conflating them
would misrepresent one or both attacks' actual mechanism.

This gate is, per `persistence_gate.py`'s own established disclosure
pattern, **attack-harness instrumentation** — not a `V3-Hybrid-Extended`
capability, living entirely in Phase 4 code, never described as something
V3-Hybrid itself does.

### 2.3 Ground-Truth Vocabulary — Checked, No New State Needed

The existing 9-state chain (`PHASE4_4_2_COMMON_ATTACK_CONTRACT.md`
Section 7a): `POISON_NOT_ADMITTED | POISON_ADMITTED |
POISON_IN_CANDIDATE_POOL | POISON_SELECTED_TOP_K |
POISON_RETRIEVED_BUT_NOT_USED | POISON_INFLUENCED_RESPONSE |
TARGET_BEHAVIOR_TRIGGERED | ATTACK_SUCCESS | ATTACK_FAILURE` already maps
onto the user-requested PLANTED/DORMANT/TRIGGERED/ACTIVE/INFLUENTIAL
distinction **when read per-query-condition**, not as a static artifact
property:

| Requested state | Existing vocabulary equivalent |
|---|---|
| PLANTED | `POISON_ADMITTED` |
| DORMANT | `POISON_ADMITTED` ∧ `POISON_IN_CANDIDATE_POOL` (or not even that) ∧ **not** `POISON_SELECTED_TOP_K`, under a goal-distant query |
| TRIGGERED | `POISON_SELECTED_TOP_K`, under a goal-adjacent query |
| ACTIVE / INFLUENTIAL | `POISON_INFLUENCED_RESPONSE`, confirmed via counterfactual mask per Decision 4 |

**Finding, reported honestly**: unlike every one of AgentPoison's,
FARMA's, and DSRM's own Milestone 6/7 contract re-validations (each of
which found and fixed one real schema defect), this check comes back
**clean** — no new field, no schema change, no defect. This is reported
as a genuine "no defect found" result, matching MPBench's own Milestone 6
outcome, not manufactured to fit a pattern. The dormancy/trigger
distinction the user's directive asks for is a **campaign-design and
measurement discipline** (running the same artifact against both query
types and reading the existing per-query states), not a missing schema
field.

### 2.4 Applicability Matrix Row (additive to contract Section 9, no other row modified)

```text
| Sleeper Memory Poisoning | v3_hybrid (canonical, external-manager
regime only) | none (injection-admission judgment is attack-harness
instrumentation, per MemoryGraft's own precedent, not a
V3-Hybrid-Extended capability) | APPLICABLE (external-manager regime);
tool-based regime NOT_APPLICABLE (no V3-Hybrid tool-call-initiated write
surface, same gap as MPBench's C1) | DIRECT_WRITE via real ingestion,
gated by injection_gate | GENERAL_FACT (inside content) |
REFERENCE_IMPLEMENTATION (code exists, ambiguous license — treated as a
faithful, attributed reconstruction, not direct reuse) | single-artifact,
paired goal-adjacent/goal-distant query design |
```

## 3. Phase 4.5 — MPBench Correspondence (full analysis in the dossier's Section 8)

**Direct correspondence** to MPBench's **C1 (Explicit/Conditional Command
Insertion)** — both are explicit, instruction-bearing memory-write
commands embedded in external content, "Strong" signal strength. This is
the opposite end of MPBench's taxonomy from the C2 classes (Policy
Conformant Fact Injection, False Precedent Insertion) already integrated
into MAMBench. **C1 was previously `NOT_APPLICABLE`** per the governing
MPBench scope policy, for the same architectural reason that applies to
Sleeper's tool-based regime (Section 2.1 above) — this is now a
**confirmed, not merely inferred**, instance of that same gap, found
independently by a different attack's own analysis. **No MPBench
taxonomy category captures Sleeper's genuine contribution** (the
dormancy/goal-adjacent-vs-distant experimental protocol, dossier Section
6) — MPBench's taxonomy is organized by write channel and payload
disguise level, not by temporal/session decoupling, so this is a real gap
in MPBench's own taxonomy relative to what MAMBench's lifecycle model
(4.6) already anticipates, not a failure to find a mapping that exists.

## 4. Phase 4.6 — Poison Artifact & Injection Model

```text
SleeperArtifact
├── artifact_id
├── task_id
├── target_question        # the "goal-adjacent" query this artifact targets
├── gold_answer             # real LoCoMo gold answer, for counterfactual reference
├── distant_question         # a real, deliberately UNRELATED LoCoMo question
│                             #   (Control 2/goal-distant condition)
├── forged_memory_text       # the fact to be written -- MAMBench's own
│                             #   analogue of the paper's m_adv
├── document_text            # the (short, LoCoMo-flavored) carrier text the
│                             #   injection payload is embedded in --
│                             #   AGENT-VISIBLE, this is what reaches
│                             #   _extract_content_text() if injection uses
│                             #   this path (see injection method below)
├── injection_payload_text   # the actual save-to-memory instruction wrapper
│                             #   (original re-implementation, not copied
│                             #   from the repo -- Section 6 below)
└── gate_decision             # the real injection_gate's KEEP/DISCARD/rationale
```

**Content-type / boundary discipline** (tested explicitly, per this
document's own instruction, since this was a real boundary problem in
three prior attacks — AgentPoison, FARMA, DSRM each independently made
and then fixed a self-labeling `content_type` mistake): `content_type`
is `GENERAL_FACT` (matching DSRM's and MPBench-PCFI's contract-specified
value), never `SLEEPER_POISON` or similar. `attacker_originated`,
`attack_id="sleeper_memory_poisoning"`, `gate_decision`, and
`distant_question` all live in **metadata only** — confirmed by the same
unit-test pattern every other attack's injector already uses (assert
`content["content_type"]` is not self-labeling, assert forbidden keys
raise `FoundationBoundaryViolation`).

## 5. Phase 4.4/4.7 — Lifecycle Reconstruction and Real Phase 3 Integration

```text
Injection        -> real foundation.add_memory() call, gated by injection_gate.judge_injection()
    ↓
Admission         -> gate KEEP -> ADMITTED (POISON_ADMITTED); gate DISCARD -> NOT_ADMITTED, reported honestly
    ↓
Storage           -> real Mem0 store (RealMem0Adapter)
    ↓
Dormancy          -> measured via a real query using `distant_question` (goal-distant condition):
                      expect POISON_IN_CANDIDATE_POOL (retrieved into the 20-candidate pool, since
                      it's a real, embedded fact) but NOT POISON_SELECTED_TOP_K (not surfaced into
                      the agent-visible top-8) -- measured, not assumed
    ↓
Retrieval/Trigger evaluation -> measured via a real query using `target_question` (goal-adjacent
                      condition): expect POISON_SELECTED_TOP_K
    ↓
Activation/Exposure -> agent-visible context construction (shared campaign_runner.py, real,
                      unmodified Phase 3 build_agent_visible_context/render_messages)
    ↓
Influence           -> real generation via generate_with_retries; POISON_INFLUENCED_RESPONSE only
                      after a real counterfactual mask, per Decision 4
    ↓
Propagation/Attribution -> attack_id/attacker_originated metadata, same pattern as all six prior
                      attacks; no new lineage mechanism needed
```

Uses `phase4.shared.campaign_runner.retrieve_select_generate()` (4.7)
unmodified for every query in the campaign, and the new
`SleeperAdapter(AttackAdapter)` (4.7's interface) for `validate`/
`prepare`/`generate`/`inject` — `execute`/`collect` inherited from the
base class exactly as every other attack's adapter already does. **Clean
V3-Hybrid vs. V3-Hybrid + Sleeper attack** is tested directly by Control 1
(Section 6 below) — the same real pipeline, run once against an
unpoisoned pool and once against a poisoned one, with everything else
held fixed.

## 6. The Injection Payload — Original Re-Implementation, Not Copied

Per Section 1's attribution discipline, `payload.py` implements the three
structural elements the dossier's Section 5 found common to every real
repo variant — written fresh, not copied:

```text
"{document_text}

[a context-boundary break, e.g. a natural end-of-document marker]
[a first-person, casual instruction to save `forged_memory_text` to memory/profile]
[a close instructing normal processing to continue]"
```

## 7. Staged Validation Plan

**Milestone 1 — DONE.** Source verification (the dossier).

**Milestone 2 — DONE (this document).** Contract integration, MPBench
correspondence, artifact/injection model design.

**Milestones 3–7 — DONE, executed in the same pass as this document
(2026-09-11)**: real code built (`phase4/attacks/sleeper_memory_poisoning/`),
unit-tested, and run through a real 4-control campaign — full results in
Section 8 below and the companion completion report
`PHASE4_4_8_SLEEPER_MEMORY_POISONING_CAMPAIGN.md`.

## 8. Sources

- [PHASE4_4_1_SLEEPER_MEMORY_POISONING_DOSSIER.md](PHASE4_4_1_SLEEPER_MEMORY_POISONING_DOSSIER.md)
- [PHASE4_4_2_COMMON_ATTACK_CONTRACT.md](PHASE4_4_2_COMMON_ATTACK_CONTRACT.md)
- [PHASE4_MPBENCH_SCOPE_AND_PRIORITY_POLICY.md](PHASE4_MPBENCH_SCOPE_AND_PRIORITY_POLICY.md)
  (C1 precedent)
- [PHASE4_4_7_ATTACK_PHASE3_INTEGRATION.md](PHASE4_4_7_ATTACK_PHASE3_INTEGRATION.md)
  (`AttackAdapter`, `campaign_runner.py`)
- `phase4/attacks/memorygraft/persistence_gate.py` (the judgment-gate
  pattern reused, not the prompt content, for `injection_gate.py`)
