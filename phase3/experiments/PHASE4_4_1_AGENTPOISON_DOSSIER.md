# Phase 4.1 — Attack Source Dossier: AgentPoison

Status: **DRAFT — 4.1 (Attack Inventory & Source Verification)**. Produced against
the pre-flight-gated Phase 4 process
([PHASE4_PRE_FLIGHT_DECISIONS.md](PHASE4_PRE_FLIGHT_DECISIONS.md)). Fields are
backed by direct verification (GitHub API, repository README, arXiv listing) as
of this drafting session; anything not independently verified is marked
`UNKNOWN / NOT VERIFIED` rather than filled from assumption. No MAMBench code
was written or modified to produce this document.

## 1. Identity

| Field | Value |
|---|---|
| Paper title | "AgentPoison: Red-teaming LLM Agents via Poisoning Memory or Knowledge Bases" |
| Authors | Zhaorun Chen, Zhen Xiang, Chaowei Xiao, Dawn Song, Bo Li |
| Affiliations | University of Chicago, University of Illinois Urbana-Champaign, University of Wisconsin-Madison, UC Berkeley |
| Venue | NeurIPS 2024 (poster) |
| arXiv | [2407.12784](https://arxiv.org/abs/2407.12784), submitted 2024-07-17 |
| Official repo | [AI-secure/AgentPoison](https://github.com/AI-secure/AgentPoison) — MIT License, 243 stars, actively maintained (last push observed 2026-08-16) |
| Repo note | `BillChan226/AgentPoison` (the lead author's personal fork/original location) now HTTP-redirects ("Moved Permanently") to `AI-secure/AgentPoison`. Treat `AI-secure/AgentPoison` as the single canonical repo — do not treat the two as independent sources. |
| Commit observed | `7236bf43148211918fd6b84d862495525798ab3c` (latest on `master` as of this dossier's drafting; not yet pinned for MAMBench integration — pinning is a 4.3 task) |
| License | MIT (SPDX `MIT`) — permissive, no MAMBench licensing blocker |

## 2. Classification

**`REFERENCE_IMPLEMENTATION` — trustworthy, actively maintained, official author repo.**

This is the strongest-provenance resource of the six in scope: a maintained,
MIT-licensed, author-owned repository directly implementing the published
paper, still receiving commits as of mid-2026. 4.3 (Reference Implementation
Integration) is the correct track for AgentPoison, not 4.4 (reconstruction).

## 3. Threat Model / Attacker Assumptions

| Field | Value |
|---|---|
| Attacker capability | Write access to the target memory/knowledge base (can insert poisoned demonstrations) |
| Attacker knowledge | **White-box access to the embedding model used for retrieval** — trigger optimization is gradient-based against the embedder's own weights, not the agent LLM. This is a materially different assumption from "black-box query-only" attacks. |
| Model retraining required | No — the LLM agent itself is never fine-tuned; only the poisoned memory content and the trigger token sequence are optimized |
| Poison rate | Effective at <0.1% of the memory/knowledge base — a stealth-by-volume design |
| Stated benign-performance cost | ≤1% impact on clean-task accuracy per the paper's own reported results |
| Stated attack success | ≥80% average ASR across all three target agents (paper's own reported figure — **not independently re-verified against V3-Hybrid or any MAMBench infrastructure**) |

## 4. Mechanism

**Trigger optimization** (`algo/trigger_optimization.py` in the repo): a
discrete, gradient-guided search that:
- Runs gradient-based token-candidate scoring against the target embedder,
  accumulating gradients over a configurable number of steps (repo default
  observed: 30 accumulation steps),
- Samples a pool of discrete candidate tokens per iteration (repo default
  observed: 100 tokens/iteration),
- Optionally applies a perplexity-based coherence filter (keeps triggers
  fluent/inconspicuous rather than gibberish),
- Optionally uses target-gradient guidance approximating the downstream
  model's loss.

The objective is to find a trigger token sequence that maps triggered queries
into a tight embedding-space neighborhood shared with the poisoned
demonstrations, so that whenever a real user query happens to contain the
trigger, the poisoned memory is retrieved with high probability — while
non-triggered queries retrieve normally (this is the source of the low
benign-performance cost).

**Injection mechanism, as actually implemented in the repo — important
finding**: the reference implementation does **not** inject poison through a
generic memory-API call. It injects by direct source-code modification at
specific lines in each target agent's own pipeline:
- Agent-Driver: `agentdriver/planning/motion_planning.py:184`
- ReAct-StrategyQA: `ReAct/run_strategyqa_gpt3.5.py:112`
- EHRAgent: `EhrAgent/ehragent/main.py:90`

There is no documented automated/API-level injection script in the current
repo state; the authors' own evaluation workflow is "run once with the trigger
patched in, run once without, diff the two."

## 5. Target Surfaces (per attack surface taxonomy)

Primarily targets: **retrieval** (the embedding space the retriever operates
in) and **memory content** (the poisoned demonstrations themselves). Does not
target memory admission/lifecycle, provenance, or propagation mechanisms —
those are downstream of what AgentPoison manipulates, not what it manipulates
directly.

## 6. Embedders Attacked (paper/repo scope)

BERT (`bert-base-uncased`), DPR (`dpr-question_encoder-single-nq-base`), ANCE
(`ance-dpr-question-multi`), BGE (`bge-large-en`), REALM
(`realm-cc-news-pretrained-embedder`), ORQA (`realm-orqa-nq-openqa`).

## 7. Original Evaluation Datasets/Agents (NOT MAMBench's)

1. **Agent-Driver** — autonomous-driving motion planning, using the
   Agent-Driver framework's own motion-planning dataset.
2. **ReAct-StrategyQA** — question answering, built on the StrategyQA dataset
   (Allen Institute).
3. **EHRAgent** — healthcare/EHR question answering over electronic health
   record data.

None of these are LoCoMo or LongMemEval. AgentPoison was never evaluated
against a Mem0/A-MEM-style conversational memory agent in the original paper —
this is a genuine, disclosed gap between the source methodology and MAMBench's
target environment (Section 9).

## 8. Original Evaluation Metrics

- **ASR-r** — retrieval attack success rate (was the poisoned item retrieved?)
- **ASR-a** — agent action attack success rate (did the agent's action change
  as intended?)
- **ASR-t** — trajectory attack success rate (Agent-Driver only)
- **ACC** — benign/clean-task accuracy, measured in a separate no-trigger run

## 9. MAMBench Adaptation Required

This is substantial, not a drop-in integration, despite the strong provenance
status:

1. **Embedder mismatch — RESOLVED (2026-09-11), mixed result.** V3-Hybrid's
   Mem0 adapter uses `sentence-transformers/all-MiniLM-L6-v2` locally with
   `infer=False` (per
   [PHASE3_COMPLETE_HISTORY_AND_ARCHIVE.md](../PHASE3_COMPLETE_HISTORY_AND_ARCHIVE.md)
   §10). None of AgentPoison's six attacked embedders is MiniLM-L6-v2, but
   direct testing (`PHASE4_4_3_AGENTPOISON_INTEGRATION_PLAN.md` Section 6,
   Milestone 1) confirms the checkpoint loads cleanly via the same
   `BertModel`/`BertTokenizer` classes AgentPoison's code uses — no
   architecture incompatibility. However, direct inspection of
   `algo/utils.py::load_models()` found AgentPoison's default pooling
   convention (`bert_get_emb`: `.pooler_output`, used for `bert`,
   `classification`, `contrastive`, `dpr`, `ance`, and `bge`) does **not**
   match what Mem0's real embedder actually computes — directly measured:
   mean-pooled `last_hidden_state` matches the real SentenceTransformer
   output at cosine similarity 1.0; `pooler_output` matches at 0.004
   (uncorrelated). A new, precisely-specified pooling function is required
   before the reference optimization would faithfully target Mem0's real
   embedding space — small, known, not a blocker, but a real deviation from
   the reference implementation's own convention. A-MEM's embedding backend
   was not tested and needs the same check separately before assuming
   either outcome there.
2. **Injection mechanism mismatch.** The reference implementation injects via
   source-patching specific target-agent files, not through a memory-write
   API. MAMBench needs an adapter that produces the equivalent effect —
   inserting a poisoned demonstration into Mem0/A-MEM's actual memory
   store — rather than adopting the source-patch approach itself, which
   doesn't correspond to any real MAMBench entry point.
3. **Retrieval architecture mismatch.** AgentPoison's target agents use
   direct dense retrieval over one of the six listed embedders. V3-Hybrid uses
   `hybrid_selection.py` — a pool=20 → top-8 rerank combining cosine
   similarity (0.5), token overlap (0.3), and entity overlap (0.2), not a pure
   dense-retrieval top-k. A trigger optimized purely against embedding-space
   cosine distance may not reliably win the token-overlap/entity-overlap
   components of MAMBench's actual selection stage. This needs empirical
   validation once integrated, not an assumption either way.
4. **No conversational-memory precedent.** The attack has no prior evaluation
   on multi-turn conversational memory (LoCoMo-style) — MAMBench would be the
   first test of whether the trigger-optimization approach transfers to this
   memory genre at all.
5. **Task/domain mismatch.** None of the three original target agents resemble
   V3-Hybrid's question-answering-over-conversation-history setup closely
   enough to reuse their evaluation harnesses; only the core trigger-generation
   algorithm (`algo/trigger_optimization.py`) is expected to be directly
   reusable, not the agent-specific injection/evaluation code.

## 10. Compatibility With Phase 4 Pre-Flight Decisions

- Does not depend on selection-policy manipulation (Decision 1) — AgentPoison
  targets retrieval ranking, not the selection/rejection stage, so it remains
  eligible under the canonical identity-slice path without invoking the
  non-canonical selection-policy variant.
- If piloted against A-MEM, is subject to Decision 2 (A-MEM confound fix must
  be wired first).
- New campaign records must carry environment provenance per Decision 3.
- Any ground-truth claim about whether the poisoned memory *causally* changed
  V3-Hybrid's answer (vs. merely being retrieved) requires new counterfactual
  measurement per Decision 4 — the existing 40-record slice does not cover
  attack-condition runs.

## 11. Deviations / Unresolved Ambiguities

- **UNKNOWN / NOT VERIFIED**: full requirements/dependency pin list
  (`environment.yml` contents were not independently enumerated in this pass —
  only that it exists and is conda-based).
- **UNKNOWN / NOT VERIFIED**: whether the repo's trigger-optimization code
  runs against a locally-hosted embedder (as MiniLM-L6-v2 would need to be) or
  assumes API-hosted embedding endpoints for any of the six listed embedders.
- **UNKNOWN / NOT VERIFIED**: any author-side discussion of defenses or
  known limitations — the README does not surface one; the full paper body was
  not text-extracted in this pass (PDF fetch returned binary/undecoded
  content, not readable text). A follow-up pass should re-attempt full-text
  extraction (e.g. via an HTML/ar5iv mirror) before 4.3 implementation begins,
  since defense/limitation discussion could affect the reconstruction of a
  fair, disclosed ground-truth definition (4.9).
- **NOT VERIFIED**: independent reproduction of the paper's own ≥80% ASR / ≤1%
  benign-cost figures. These are reported as the source paper's claim, not
  confirmed by MAMBench.

## 12. Recommended 4.3 Integration Path

Adapter architecture (per the handoff's preferred 4.3 pattern):

```text
AgentPoison trigger_optimization.py (reused directly, targeting Mem0/A-MEM's
actual embedder — pending Section 9 item 1's embedder-compatibility check)
      ↓
MAMBench AgentPoison Adapter (new): translates optimized trigger + poisoned
demonstration into a real Mem0/A-MEM memory-write, tagged with a PoisonArtifact
record (per 4.6)
      ↓
Common Attack Contract (4.2)
      ↓
V3-Hybrid environment (Condition C only — AgentPoison targets retrieval,
which Condition A/B don't exercise)
```

This preserves the original trigger-optimization algorithm unmodified (per the
handoff's "do not rewrite a validated original implementation" rule) while
building only the injection-adapter layer AgentPoison's own repo doesn't
provide.

## 13. Sources

- [AgentPoison paper abstract — arXiv:2407.12784](https://arxiv.org/abs/2407.12784)
- [AI-secure/AgentPoison — official repository](https://github.com/AI-secure/AgentPoison)
- [NeurIPS 2024 poster listing](https://nips.cc/virtual/2024/poster/94715)
- GitHub REST API (`api.github.com/repos/AI-secure/AgentPoison`,
  `.../license`, `.../commits`) — queried directly for license, star count,
  push date, and latest commit SHA during this dossier's drafting.
