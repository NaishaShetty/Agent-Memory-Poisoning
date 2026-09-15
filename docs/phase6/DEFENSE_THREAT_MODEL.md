# Phase 6 Defense Threat Model

Status: DRAFT under 6.1. Inherits Methodology §3 (Threat Model and Problem
Formulation) and §17.3 (Attack Inventory) rather than inventing a new taxonomy.
Every row below is traceable to a real, previously-documented attack mechanism —
none is invented for Phase 6.

---

## 1. Formal Setting (inherited, unchanged)

Let A = the memory-augmented agent (V3-Hybrid, frozen), M = memory foundation
(Mem0 or A-MEM), c = condition (A: no memory / B: gold evidence / C: retrieved
memory). Phase 6 adds a defense function D that may intervene between memory
creation and condition-C context assembly. D must not alter conditions A or B's
mechanics — a defense that changes gold-evidence handling is out of scope, since
Condition B measures reasoning alone and Phase 4/5 never poisoned it.

## 2. Attacker Objectives (inherited from §17.3, categorized)

| Objective | Attacks that pursue it | Lifecycle stage where objective is realized |
|---|---|---|
| Single-shot misdirection | MPBench-PCFI (unmarked fabricated fact), one-off FARMA seed record | exposure/use |
| Persistent behavioral drift | FARMA amplification (manufactured precedent count), MemoryGraft (forged "successful experience") | propagation → influence |
| Retrieval dominance | AgentPoison (MMD-maximized trigger embedding), DSRM white-box (InfoNCE) | retrieval → selection |
| Trigger-based / dormant activation | Sleeper Memory Poisoning | storage (dormant) → retrieval (on trigger) |
| Belief implantation via legitimate-looking interaction | MINJA (progressive query-mediated insertion) | admission (agent's own ingestion writes it) |
| Self-refining evasion of detection | DSRM black-box (LLM-driven similarity-gated rewriting) | admission (content is iteratively laundered before injection) |

## 3. Attacker Capability Profiles (inherited from §17.3 — this IS the project's real capability taxonomy; Phase 6 does not invent a separate C1–C4 attacker-capability scale)

| Attack | Access model | Optimization capability | Requires model internals? |
|---|---|---|---|
| AgentPoison | White-box | Gradient-driven (HotFlip + backward-pass gradient against MiniLM embedder) | Yes — embedding model gradients |
| MINJA | Query-only | Discrete query-sequencing strategy, no optimization | No |
| FARMA | Direct-memory-write (harness-level) | None (rule-based seed + amplification schedule) | No |
| MemoryGraft | Gated write (must pass a real LLM persistence-judgment gate) | None core; adaptive social-proof language found effective in a foolability probe | No |
| DSRM (black-box) | Black-box | LLM-driven iterative self-refinement toward similarity target | No (uses an LLM, not gradients) |
| DSRM (white-box) | White-box | Gradient-driven (shared AgentPoison machinery, InfoNCE objective) | Yes |
| MPBench-PCFI | Direct-memory-write (harness-level) | None | No |
| Sleeper Memory Poisoning | Document-embedded, dormant | None (structural: write instruction embedded in external content) | No |

**Note on MPBench's real C1–C4 taxonomy** (write-channel, not attacker capability):
C1 = explicit instruction-executed write, C2 = system-prompt-driven write (agent
judges retention), C3 = compaction-driven write, C4 = experience-to-procedure write.
Of these, only C1/C2-analogues exist in V3-Hybrid: six of the seven attacks use a
harness-level DIRECT_WRITE (bypassing agent judgment entirely — closer to an
attacker with direct store access than to C1's "explicit instruction" concept, and
disclosed as such in the frozen Common Attack Contract), and MemoryGraft alone
exercises a genuine C2-like agent-mediated-write channel via its persistence
gate. C3/C4 are `NOT_APPLICABLE` to V3-Hybrid and out of scope (Charter §8).

## 4. Injection Surfaces (where attacker-controlled content enters)

1. **Direct memory-store write** (harness DIRECT_WRITE) — AgentPoison, FARMA, DSRM,
   MPBench-PCFI, Sleeper. The attacker (or attack harness, standing in for a
   capability the source paper assumes) writes to Mem0/A-MEM's real ingestion path
   without going through the agent's own conversational turn.
2. **Agent-mediated conversational turn** — MINJA. The attacker only ever sends
   ordinary-looking queries; V3-Hybrid's own normal ingestion is what commits them to
   memory. This is the injection surface a "screen incoming user turns" defense would
   need to operate on, and the one furthest from a content-signature approach (no
   single turn looks malicious in isolation).
3. **LLM-judged gate** — MemoryGraft. The injection surface is the gate's own
   judgment call; a defense here means calibrating or hardening that specific judgment
   function, not screening raw content before the gate ever sees it.
4. **External document content, dormant** — Sleeper. The injection surface is
   whatever ingests "external documents" into memory; the write instruction is inert
   until a later, unrelated-looking query triggers it.

## 5. Protected Lifecycle Stages and Defense-Relevant Observables

Per stage, what Phase 5 actually persists (Charter §5's D1–D4 mapping is grounded in
this, not in what a defense theoretically wants):

| Stage | Real Phase 5 evidence available | Legitimately defense-usable? |
|---|---|---|
| injection | `attack_injection` Phase5Event — but its `attack_id`/`attacker_originated` fields are evaluator-only | Only the *fact and channel* of a write event; not its attacker-origin label |
| admission | `CanonicalEvent` created-type event, ingestion channel/source metadata | Yes |
| storage | `CanonicalMemoryLedger` content, version/supersession links | Yes |
| retrieval | Full per-candidate score records (cosine, token-overlap, entity-overlap sub-scores), `canonical_status` | Yes |
| selection | selected/rejected status, blended score, rank | Yes |
| exposure | rendered agent-visible context + fingerprint | Yes (content only — not evaluator-only labels about what was exposed) |
| use/influence | `used_memories_observability` (always NOT_OBSERVABLE by design), `counterfactually_influential` events | Influence events are post-hoc and evaluator/analysis-only — NOT usable for a same-query runtime decision (Charter §6) |
| propagation | relationship edges (DERIVED_FROM, PRODUCED, etc.) with evidence-kind labels | Yes — structural edges only, not the ground-truth label of what's at the other end |
| detection | (Phase 6 adds this — no Phase 5 precedent) | N/A — new in Phase 6 |
| attribution | six attribution types, read-only | Usable for **post-hoc** analysis of what a defense mitigated (Stage 6.13), never as a runtime defense input |

## 6. Acceptable False-Positive / Utility Boundary (deferred to 6.12, referenced here for completeness)

Not fixed by this document. What is fixed: any threshold must be justified against
data seen only during defense development, never against the held-out attack in a
leave-one-out evaluation (Rule 14), and must be reported alongside its benign-utility
cost (Charter §7).

## 7. Explicitly NOT This Threat Model's Concern

- Attacks on the LLM's weights/training data (out of MAMBench's scope entirely).
- Attacks on Mem0/A-MEM's own infrastructure (e.g., Qdrant/ChromaDB compromise) —
  MAMBench treats these as trusted infrastructure per Phase 3's own framing.
- Prompt injection via tool-call arguments unrelated to persistent memory (this is
  what AgentDojo/InjecAgent primarily cover per the pending 6.2 literature audit —
  MAMBench's victim has no tool-use surface, so this class of attack has no analogue
  here).

## 8. Verdict

**PASS** as a 6.1 deliverable — every attacker capability, objective, and injection
surface traces to a real, already-executed Phase 4 attack; no new attacker class is
invented; the observable/non-observable split in Section 5 is what Stage 6.4's full
Signal Contract will formalize with tests.
