# Phase 6 Defense Gap Analysis

Status: 6.2 deliverable. Synthesizes `DEFENSE_LITERATURE_AUDIT.md` and
`DEFENSE_COMPARISON_MATRIX.md` into what is actually missing from the existing
literature relative to Phase 6's research question, and what that implies for
architecture selection (Stage 6.3 onward).

---

## 1. Lifecycle Coverage Gap

No investigated defense — across either research track — provides a real, evaluated
mechanism for **D2 (Provenance / Integrity / Trust)** as Phase 6's charter defines it:
a security state that is written once (at or after admission) and then legitimately
read and propagated across storage, retrieval, and derivation. Every external defense
found either:
- re-evaluates content fresh at each use point with no persistent memory of prior
  judgments (MEMSAD, ASB, AgentPoison's/MINJA's own defenses), or
- accumulates a *side* memory of flagged patterns (A-MemGuard's lessons store) without
  attaching a state to the *original* memory identity itself, or
- intervenes once at write-time with no mechanism for the judgment to survive or
  propagate into anything derived from that memory later (SENTINEL, ASB).

This directly validates Charter §5's original four-layer decomposition — D2 was
correctly identified as a gap *before* this audit (Scope Matrix §2 flagged it as
"does not exist yet — this is Phase 6's own additive contribution") and the literature
confirms no external system fills it. **This is the strongest single argument for a
MAMBench-native design rather than an imported one**: the RQ specifically asks about
a "provenance-aware, lifecycle-aware" defense, and provenance-awareness in the sense
the RQ means — a state that survives and propagates — has no faithful external
precedent to reproduce.

## 2. Cross-Attack Generalization Gap

No external defense has been evaluated against more than 2–3 of MAMBench's seven
attack mechanisms, and the mechanisms that exist have structurally predictable blind
spots against the mechanisms they were never tested on:

| Defense | Evaluated against | Predictable gap against untested MAMBench attacks |
|---|---|---|
| SENTINEL | FARMA only | Targets reasoning-trace forgery signals (self-reference, precedent counts, perfection claims); has no signal tuned to catch AgentPoison/DSRM's optimized retrieval-trigger tokens (a ranking attack, not a content-forgery attack) or MPBench-PCFI's deliberately unmarked, plain-fact content (by design, has none of SENTINEL's five target signals) |
| A-MemGuard | AgentPoison, MINJA, misinformation | Consensus-based detection is structurally exposed to attacks that manufacture agreement across multiple planted memories — exactly FARMA's amplification design and MemoryGraft's precedent-building design |
| MEMSAD | AgentPoison, MINJA, InjecMEM | Proven (by its own theorem) to fail against discrete paraphrase — the dominant style of FARMA, MemoryGraft, and MPBench-PCFI's natural-language content |
| ASB (PPL/LLM) | ASB's own simple attack | Fails even there (66% FNR); would be expected to fail worse against MAMBench's more sophisticated seven |

No combination of existing defenses, taken as-is, has been shown (or would be
plausibly expected, given the mechanisms) to cover all seven MAMBench attack families
without gaps. This is a genuine, evidence-grounded finding, not a assumption.

## 3. What CAN Be Faithfully Salvaged

Two components are real, precisely specified, and reproducible without guessing:

1. **SENTINEL's Reasoning Guard heuristic** (D1) — a weighted, five-signal content
   scorer. Faithfully portable to MAMBench's admission stage as one input among
   several, not as the complete D1 mechanism (its narrow target — reasoning-trace
   forgery — means it should be one signal in a broader admission policy, not the
   entire policy).
2. **A-MemGuard's consensus-validation + lessons architecture** (D3/D4) — faithfully
   portable via its live repository. Its coordinated-poisoning weakness means it
   should not be the sole gate at retrieval time, but its lessons-store idea (an
   append-only record of previously-flagged reasoning patterns, checked against future
   candidates) is a genuine, reusable containment primitive for Phase 6's own D4 work.

Everything else in the matrix is either a documented negative result (useful only as
a comparison floor) or unvalidated by its own source (usable only as an idea to
prototype and test fresh, never as "reproduction of an established result").

## 4. Implication for Stage 6.3 Architecture

Given (1) the D2 gap has no external precedent, (2) no single external defense
generalizes across the seven attacks, and (3) two real components ARE faithfully
reproducible for D1 and D3/D4 respectively — the evidence supports:

**A MAMBench-native Memory Governance Policy (MGP) as the primary Phase 6
architecture**, structured so that:
- D1 (Admission Governance) incorporates a faithfully-reproduced SENTINEL-style
  Reasoning Guard as **one** signal among a small, interpretable, multi-signal policy
  (Stage 6.5 already specifies this multi-signal design independently of this
  finding — the literature audit now gives one concrete, real signal to include
  rather than inventing one from scratch).
- D2 (Provenance/Trust) is designed natively — there is no external precedent to
  reproduce, so this is original MAMBench design work, evaluated on its own merits,
  built on Phase 5's real lineage/relationship infrastructure (already verified to
  exist and be reusable — Scope Matrix §2).
- D3 (Retrieval-Time Defense) incorporates a faithfully-reproduced A-MemGuard-style
  consensus check as **one** candidate mechanism to ablate against MAMBench's
  existing per-candidate score infrastructure — not adopted uncritically, given its
  known coordinated-poisoning weakness, which is directly relevant to two of
  MAMBench's seven attacks.
- D4 (Propagation/Lineage Containment) is designed natively, optionally informed by
  A-MemGuard's lessons-store idea as a component, built on Phase 5's real
  `build_propagation_graph()` and relationship-derivation functions (verified reusable).
- ASB's perplexity/LLM-judgment defenses, AgentPoison's/MINJA's own defenses, and
  MEMSAD are retained as **explicitly labeled weak external baselines** for
  comparison in Stage 6.10/6.12 — not as components of MGP itself. Their known
  failure modes make them scientifically useful precisely as a floor MGP should beat,
  and reporting that floor honestly is stronger evidence than omitting weak baselines
  entirely.

## 5. What Remains Genuinely Uncertain (do not resolve prematurely)

- Whether SENTINEL's five signals, reimplemented against MAMBench's actual attack
  content (not FARMA's own EHR/RAP/ReAct-QA domains), reproduce anything close to the
  reported 0%-ASR/0%-FPR result. This is an empirical question for Stage 6.5/6.9, not
  assumable from the source paper's own numbers.
- Whether A-MemGuard's consensus mechanism, ported to MAMBench's LoCoMo conversational
  domain (a domain it was never evaluated on), performs comparably to its
  AgentPoison/MINJA-domain results.
- What the actual mechanism for "genuine benign transformation vs. malicious
  inheritance" at D4 should be (Scope Matrix §2's second flagged gap) — no literature
  reviewed here answers this; it is native, unsolved MAMBench design work for Stage
  6.7.
- The DSRM paper's own defense section remains unresolved (paywalled) — carried
  forward as an open item, not assumed empty.

## 6. Verdict

**PASS** as a 6.2 deliverable. The audit did not select a defense reflexively; it
determined, from real mechanism-level evidence, that no single external system meets
the RQ's lifecycle-spanning and cross-attack-generalizing requirements, that two
specific external components are faithfully reproducible and worth incorporating as
ablatable pieces, and that the RQ's core novel claim (D2 provenance-propagation) has
no external precedent at all and must be built natively. This is the honest basis for
recommending MGP as Phase 6's primary architecture rather than "reproducing" any one
paper's defense wholesale.
