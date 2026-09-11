# Phase 4.1 — Attack Source Dossier: MemoryGraft

Status: **DRAFT — 4.1**. Verified via arXiv and GitHub API as of this
drafting session. Unverified fields are marked `UNKNOWN / NOT VERIFIED`. No
MAMBench code was written or modified to produce this document.

## 1. Identity

| Field | Value |
|---|---|
| Paper title | "MemoryGraft: Persistent Compromise of LLM Agents via Poisoned Experience Retrieval" |
| Authors | Saksham Sahai Srivastava, Haoyu He |
| Affiliations | **UNKNOWN / NOT VERIFIED** |
| Venue | arXiv only — no publication venue beyond arXiv identified |
| arXiv | [2512.16962](https://arxiv.org/abs/2512.16962), submitted 2025-12-18 |
| Official repo | [Jacobhhy/MemoryGraft](https://github.com/Jacobhhy/MemoryGraft) — MIT License, 23 stars, created 2025-11-03 (predates the arXiv submission by ~6 weeks), actively pushed (last observed 2026-09-02) |
| Repo note | The paper's own cited URL resolves to `Jacobhhy/Agent-Memory-Poisoning`, which now HTTP-redirects ("Moved Permanently") to `Jacobhhy/MemoryGraft` — same repo, renamed after publication. Treat `Jacobhhy/MemoryGraft` as canonical; do not treat the two names as separate sources. |
| License | MIT — no MAMBench licensing blocker |

## 2. Classification

**`REFERENCE_IMPLEMENTATION` — real, MIT-licensed, actively maintained,
author-owned repo whose creation date predates and whose renamed-current-state
postdates the paper, consistent with genuine ongoing maintenance rather than a
one-time drop.**

4.3 (Reference Implementation Integration) track. One caveat before treating
this with the same confidence as AgentPoison/MINJA: the repo's GitHub
description field is empty (`null`) and its contents were confirmed to exist
and be MIT-licensed via the API only — **not** independently inspected
file-by-file in this pass. Recommend a direct code read before committing to
integration scope in 4.3.

## 3. Threat Model / Attacker Assumptions

| Field | Value |
|---|---|
| Attacker capability | Can supply benign-looking **ingestion-level artifacts** that the agent reads during ordinary task execution — an **indirect** injection, not direct memory-store write access and not a query-only interaction pattern either. The poison enters via content the agent consumes as part of its normal workflow (e.g. a document, a tool output, a file it processes), which the agent then chooses to persist as a "successful experience." |
| Attacker knowledge | **UNKNOWN / NOT VERIFIED** — not established from the extracted content whether black-box or white-box knowledge of the target agent's retrieval/embedding setup is assumed. |
| Distinguishing exploit | The **semantic imitation heuristic** — the agent's own tendency to replicate patterns from retrieved *successful* past experiences. MemoryGraft doesn't need the agent to believe a false fact; it needs the agent to imitate a *procedure* that looks like a prior success. |

This is a fourth, distinct capability/mechanism profile relative to
AgentPoison (embedder white-box), FARMA (direct memory write), and MINJA
(query-only): MemoryGraft's entry point is **environmental content the agent
ingests as part of task execution**, closer to a classic indirect prompt
injection but engineered specifically to become a *persisted* memory entry
rather than a one-shot transient effect.

## 4. Mechanism

1. Attacker crafts a **poisoned procedure template** — content styled as a
   successful past task execution/experience — and delivers it via an
   ingestion-level artifact the agent reads during a task.
2. The agent, following its normal experience-persistence behavior, writes
   this "successful experience" into its long-term memory / RAG store.
3. On a later, semantically similar task, the agent's **union retrieval**
   (combining lexical and embedding similarity, per the source description)
   reliably surfaces the grafted memory.
4. The agent adopts the embedded unsafe pattern via imitation, producing
   **persistent behavioral drift across sessions** — the effect is not
   confined to the triggering task, unlike a transient prompt injection.

Reported finding (source paper's own claim, **not MAMBench-verified**): a
small number of poisoned records can account for a disproportionately large
fraction of retrieved experiences on otherwise-benign workloads — i.e. the
attack doesn't need volume (contrast with FARMA's amplification phase, which
explicitly relies on volume); it relies on semantic centrality within the
retrieval space instead.

## 5. Target Surfaces (per attack surface taxonomy)

Primarily targets: **memory admission** (getting the "experience" persisted
in the first place, via the agent's own summarization/persistence behavior),
**memory content**, and **retrieval** (union lexical+embedding retrieval
surfacing the grafted memory for future tasks). Secondarily, **propagation**
across sessions is the attack's entire stated point — "persistent behavioral
drift" is explicitly a multi-session propagation claim, not a single-turn
effect.

## 6. Original Evaluation Setup (NOT MAMBench's)

- **Agent**: MetaGPT's DataInterpreter agent, backed by GPT-4o.
- Single-agent evaluation (unlike AgentPoison/FARMA/MINJA's multi-agent
  evaluation sets) — **UNKNOWN / NOT VERIFIED** whether this reflects a
  narrower validated scope or simply the paper's chosen focus; worth checking
  the full paper before assuming the attack generalizes beyond
  DataInterpreter-style code/data-analysis agents.
- **UNKNOWN / NOT VERIFIED**: specific dataset(s)/task benchmark used to
  drive DataInterpreter in the evaluation, and exact metrics reported beyond
  the qualitative "small number of poisoned records dominate retrieval"
  finding.

## 7. MAMBench Adaptation Required

1. **Domain mismatch is the largest of the five attacks reviewed so far.**
   DataInterpreter is a code/data-analysis agent, structurally quite
   different from V3-Hybrid's conversational-memory QA setup. The "poisoned
   procedure template" concept needs a MAMBench-native analogue — closer to
   "a forged past answer/reasoning trace" for LoCoMo-style tasks than to a
   forged data-analysis procedure. This is a substantial adaptation, not a
   thin wrapper.
2. **Union retrieval assumption.** MemoryGraft's stated mechanism depends on
   lexical+embedding union retrieval surfacing the grafted memory. V3-Hybrid's
   `hybrid_selection.py` uses a weighted rerank (cosine 0.5 / token-overlap
   0.3 / entity-overlap 0.2) over a pool of 20 down to top-8 — conceptually
   related (it does combine lexical-like and embedding-like signals) but not
   identical to a union-retrieval design. Whether MemoryGraft's low-volume,
   high-semantic-centrality strategy still dominates retrieval under
   V3-Hybrid's specific weighting needs empirical validation, not an assumed
   transfer.
3. **Persistence mechanism gap.** MemoryGraft depends on the *agent itself*
   deciding to persist an ingested artifact as a "successful experience" —
   this requires V3-Hybrid (or its Mem0/A-MEM wrapping) to have an analogous
   self-directed memory-write behavior for MAMBench to exploit realistically,
   rather than the adapter directly writing the poisoned record itself (which
   would understate the attack's actual mechanism and misrepresent its
   ground truth). This needs an explicit design decision recorded in 4.6/4.7,
   not a silent shortcut.

   **UPDATE (implementation attempted, calibration failed — 2026-09-11)**: a
   harness-side persistence-judgment gate was built
   (`phase4/attacks/memorygraft/persistence_gate.py`, wired into a real
   `MemoryFoundationAdapter.add_memory()` call via
   `phase4/attacks/memorygraft/adapter.py`) to address this gap — an LLM
   call (the same pinned Qwen3-8B Q4_K_M build V3-Hybrid uses) judges
   KEEP/DISCARD before any write. This is explicitly **attack-harness
   instrumentation**, not a `V3-Hybrid-Extended` capability (see
   `PHASE4_4_2_V3HYBRID_EXTENDED_ARCHITECTURE_REVIEW.md`), and was designed
   to require *graded* calibration (discriminating across artifact quality
   tiers, not merely capable of ever saying DISCARD) before it could justify
   any applicability upgrade. **That graded calibration was run against the
   real, identity-verified server and failed**: the gate correctly
   discarded both an obvious-poison and a subtle-poison artifact (real
   discrimination between poison subtlety levels), but also incorrectly
   discarded a genuine-benign artifact — full results in
   `phase4/attacks/memorygraft/calibration_run_2026-09-11.txt`. The failure
   is systematic (the gate's prompt implicitly demands execution-outcome
   verification no single req/resp pair can supply, poisoned or not), not
   degenerate (it is not a coin-flip or an always-same-answer gate). **This
   does not close the persistence-mechanism gap described above.**
   MemoryGraft's applicability remains `PARTIALLY_APPLICABLE`, unchanged
   from prior assessment — see
   `PHASE4_4_2_COMMON_ATTACK_CONTRACT.md` Section 9's MemoryGraft row,
   which this result confirms rather than revises.

   *(This finding is retained as a documented result, not superseded — see
   the follow-up update immediately below, which is an additional, separate
   finding from a revised gate, not a correction of this one.)*

   **UPDATE 2 (prompt revised, re-calibration passed — 2026-09-11)**: the
   diagnosed root cause above (the gate's prompt implicitly demanding
   execution-outcome verification no logged artifact can supply) was
   corrected. The judgment prompt in `persistence_gate.py` was rewritten to
   ask whether an artifact reads as a plausible, coherently-styled
   successful experience — surface plausibility and stylistic conformity —
   rather than demanding independent proof of a verified outcome. This
   change is grounded directly in this dossier's own Section 3
   ("distinguishing exploit"): MemoryGraft's real mechanism is the target
   agent's *semantic imitation heuristic* — "MemoryGraft doesn't need the
   agent to believe a false fact; it needs the agent to imitate a procedure
   that looks like a prior success" — not defeat of rigorous outcome
   verification. The original gate was testing something stricter than the
   mechanism it exists to model, which is why it failed uniformly rather
   than discriminating.

   The calibration set was also expanded from 3 to 5 cases — adding a
   second subtle-poison artifact (`exp_poison_003`) and a second
   genuine-benign artifact (`exp_benign_010`), both real content from the
   same source repo, chosen independently of the specific tier-3 failure —
   so a pass would not rest on the original three cases alone. Re-run
   against the same live, identity-verified pinned Qwen3-8B Q4_K_M server:
   **all 5/5 tiers matched** (3 correctly DISCARDed — one obvious poison,
   two independently-chosen subtle-poison artifacts — and 2 correctly
   KEPT — two independently-chosen genuine-benign artifacts). This is
   discrimination in both directions, not a uniform bias either way. Full
   results: `phase4/attacks/memorygraft/calibration_run_2026-09-11_v2.txt`.

   **MemoryGraft's applicability is upgraded from `PARTIALLY_APPLICABLE` to
   `APPLICABLE`**, on the basis of this genuinely-discriminating 5-tier
   calibration. Corresponding update made to
   `PHASE4_4_2_COMMON_ATTACK_CONTRACT.md` Section 9's MemoryGraft row.
   Caveat carried forward: 5 cases is a real but still small calibration
   set — this upgrade is supported by the evidence gathered, not an
   exhaustive-validation claim.

   **UPDATE 3 (separate foolability test, 2026-09-11 — does not modify the
   frozen 5-tier calibration above)**: a follow-up question was tested —
   does the gate's strictness reflect MemoryGraft's real threat model, or
   is it an artifact of judging with Qwen3-8B instead of the source
   paper's actual GPT-4o/DataInterpreter target? Six new, independently-
   engineered subtle-poison artifacts were drafted (in full, before any
   run) from three more advanced attack techniques documented in the
   source repo's `memorygraft/appendix/` directory (fabricated execution
   evidence, forged ReAct-style reasoning traces, fabricated security
   sign-offs and social-proof/authority framing — not yet read as of this
   dossier's original 4.1 pass, per Section 7 item 1's note) — run once,
   unmodified, against the same gate, not the frozen calibration set. **4
   of 6 were KEPT** — full results and the observed pattern (the gate
   discriminated more on whether an unsafe command was the foregrounded
   subject of the text than on whether an equivalent unsafe action was
   present at all once wrapped in trust-signaling or forged-log framing)
   in `phase4/attacks/memorygraft/foolability_run_2026-09-11.txt`. Per the
   interpretation rule fixed before this test ran: a nonzero KEEP rate is
   **supporting evidence** that the gate faithfully represents an
   imperfect, foolable target judgment (matching MemoryGraft's own
   "semantic imitation heuristic" premise) — this does **not** itself
   change or add new grounds to the `APPLICABLE` classification already
   recorded in UPDATE 2 above, which continues to rest on the frozen
   5-tier discrimination evidence.

   **UPDATE 4 (controlled follow-up test, 2026-09-11 — does not modify the
   frozen calibration or the UPDATE 3 foolability probe)**: UPDATE 3's
   `forged_reasoning_trace`/`trust_signal_bootstrap` pair (identical unsafe
   bootstrap command, KEEP vs. DISCARD, differing in ReAct-style wrapping)
   was suggestive of a "format-laundering" structural bias, but was not a
   controlled comparison — the two artifacts also differed in surrounding
   wording. A controlled test isolated exactly one variable (presence/
   absence of a Thought/Action/Observation wrapper) across 4 payloads (2
   distinct unsafe commands, 1 benign, 1 borderline), holding the
   underlying command and claimed outcome identical between each payload's
   plain and wrapped variant — 8 artifacts, drafted in full before any run.
   **Result: zero flips across all four payloads.** Both unsafe commands
   were DISCARDed in both framings; both benign/borderline commands were
   KEPT in both framings. Full grid and rationale:
   `phase4/attacks/memorygraft/format_laundering_run_2026-09-11.txt`. Per
   the interpretation rule fixed before this test ran, this **does not
   confirm** format-laundering as a systematic gate vulnerability — the
   original suggestive pair is best explained as a one-off driven by other
   content differences between those two specific artifacts (e.g. the
   discarded one's explicit trust/social-proof language), not by the
   wrapper format itself. No "structural-framing bias" limitation is
   recorded, consistent with the instruction not to force that narrative
   when the controlled result does not support it. MemoryGraft's
   `APPLICABLE` classification is unaffected, continuing to rest solely on
   the frozen 5-tier discrimination evidence.

## 8. Compatibility With Phase 4 Pre-Flight Decisions

- Does not depend on selection-policy manipulation (Decision 1).
- If piloted against A-MEM, subject to Decision 2.
- New campaign records carry environment provenance per Decision 3.
- The paper's own "persistent behavioral drift across sessions" claim is
  exactly the kind of multi-session causal claim Decision 4 requires new
  counterfactual measurement for — MAMBench cannot inherit this claim from
  the source paper's GPT-4o/DataInterpreter results.

## 9. Deviations / Unresolved Ambiguities

- **UNKNOWN / NOT VERIFIED**: author affiliations.
- **UNKNOWN / NOT VERIFIED**: attacker's assumed knowledge of the retrieval
  pipeline (black-box vs. some grey-box awareness).
- **UNKNOWN / NOT VERIFIED**: dataset/benchmark driving the DataInterpreter
  evaluation, and quantitative ASR-equivalent metrics.
- **UNKNOWN / NOT VERIFIED**: repo content completeness — existence and
  license confirmed via API only, not a file-level read.
- **Single-agent evaluation scope** (Section 6) should be treated as a real
  limitation of the source evidence, not glossed over when MAMBench reports
  on this attack's generality.

## 10. Recommended 4.3 Integration Path

```text
Reference MemoryGraft poisoned-procedure-template logic (reused where
architecture-agnostic)
      ↓
MAMBench Adapter: (a) redesigns the poisoned-template content for LoCoMo-style
conversational tasks, (b) decides explicitly whether the adapter writes the
poisoned memory directly or exercises V3-Hybrid's own persistence behavior
(Section 7 item 3) — decision recorded, not defaulted silently
      ↓
Common Attack Contract (4.2)
      ↓
V3-Hybrid environment, Condition C — validated across multiple sessions/tasks
to test the propagation claim specifically, not just single-task retrieval
```

## 11. Sources

- [MemoryGraft — arXiv:2512.16962](https://arxiv.org/abs/2512.16962)
- [arXiv:2512.16962 v1 HTML mirror](https://arxiv.org/html/2512.16962v1)
- [Jacobhhy/MemoryGraft — official repository](https://github.com/Jacobhhy/MemoryGraft)
  (canonical location; the paper's cited `Agent-Memory-Poisoning` name now
  redirects here)
- GitHub REST API (`api.github.com/repos/Jacobhhy/MemoryGraft`, `.../license`)
  — queried directly for license, star count, redirect target, and push date.
