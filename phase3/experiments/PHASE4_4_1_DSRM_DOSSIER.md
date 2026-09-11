# Phase 4.1 — Attack Source Dossier: DSRM

Status: **DRAFT — 4.1, REVISED.** The original pass of this dossier was built
from paywalled search-engine fragments only (both direct-fetch attempts
returned HTTP 403). The user has since supplied the full PDF locally
(`C:\RESEARCH\Engineering applications of AI.pdf`), which has now been read in
full. This revision replaces the earlier low-confidence draft with real,
verified content from the primary source. No MAMBench code was written or
modified to produce this document.

## 1. Identity

| Field | Value |
|---|---|
| Paper title | "Memory poisoning attacks on retrieval-augmented Large Language Model agents via deceptive semantic reasoning" |
| Attack name | DSRM — **Deceptive Semantic Reasoning Manipulation**, confirmed directly from the paper's own contributions section ("we propose an attack method named Deceptive Semantic Reasoning Manipulation (DSRM)") |
| Authors | Hao Jing, Fanxiao Li, Yunyun Dong, Wei Zhou, Renyang Liu |
| Affiliations | National Pilot School of Software / Engineering Research Center of Cyberspace / School of Information Science and Engineering / School of Engineering, Yunnan University, China; Institute of Data Science, National University of Singapore |
| Journal | *Engineering Applications of Artificial Intelligence*, vol. 167 (2026), article 113968. ISSN 0952-1976, Elsevier |
| Dates | Received 2025-06-12; revised 2025-12-15; accepted 2026-01-23; available online 2026-01-29 |
| DOI | 10.1016/j.engappai.2026.113968 |
| Code/data repository | **None released.** Data availability statement: *"Data will be made available on request."* The paper's own Ethical Considerations section explicitly states the authors withhold executable attack code: *"we avoid releasing fully executable attack scripts or system-specific poisoning payloads... we provide high-level algorithmic descriptions... to prevent misuse."* This is a deliberate, disclosed responsible-disclosure policy, not an omission. |
| License | N/A — no released code, by explicit authorial choice |

## 2. Classification

**`UNAVAILABLE` (by deliberate author policy) → `MAMBench_RECONSTRUCTION`
required — but now backed by a complete, directly-read methodology (not
fragments), which substantially raises reconstruction confidence over the
prior draft of this dossier.**

The paper itself anticipates and licenses reconstruction: it publishes full
pseudocode (Algorithms 1–2, black-box and white-box variants), the exact
prompt templates used (Appendix A, Tables A.1–A.3, reproduced in Section 4
below), and the exact loss function for the white-box retrieval-text
optimizer (Eq. 5). This is a case where faithful `MAMBench_RECONSTRUCTION`
is realistically achievable at high fidelity to the original, precisely
because the authors designed the paper to be reproducible from its own text
while withholding a literal executable artifact.

## 3. Threat Model / Attacker Assumptions

| Field | Value |
|---|---|
| Attacker's goal | Given user tasks drawn from various scenarios, select an attack tool $T_a$ to compromise the agent's reasoning/decision process and cause a harmful action $a_m$, by injecting adversarial "past experience" into the knowledge base so it is retrieved for query $Q$. |
| Attacker capability | **Cannot access the agent's core LLM** — no parameters, training data, or architecture; interacts only via API calls. **Fully understands the attack tools** (names, functions, semantics) and has already integrated them into the agent's tool ecosystem as apparently-legitimate third-party tools (via plugin marketplaces, third-party platforms, or external service interfaces) — the agent cannot distinguish them from benign tools. |
| Knowledge-base access | Two paths, explicitly both in scope: (a) compromising external sources (public wikis, data vendors) that feed the knowledge base, or (b) **more subtly, posing as a benign user and engaging in crafted dialogs that lead the agent to autonomously generate "past experiences" containing adversarial logic** — i.e. the agent internalizes malicious content without any direct database write by the attacker. This second path is conceptually close to MINJA's query-only bridging mechanism (see Section 9) and to FARMA's "agent writes its own poison" framing. |
| Retriever knowledge — two explicit settings | **Black-box**: the attacker knows only that a retriever is used (no architecture/parameter access) — the more realistic, primary setting. **White-box**: full access to the retriever's parameters, used for deeper vulnerability analysis via gradient-based optimization. |

This threat model sits between AgentPoison (which requires white-box
embedder gradient access as its baseline) and MINJA/FARMA (weaker
access) — DSRM explicitly evaluates **both** a low-privilege black-box mode
and a high-privilege white-box mode as two first-class variants, not as a
single fixed assumption.

## 4. Mechanism

The adversarial decision is composed of three parts, assembled into a
single injected "past experience" record:

- **Planning Text $P_t$** — the overall task-execution strategy.
- **Tool Selection $T_s$** — specifies the attacker's tool.
- **Reasoning Text $R_t$** — logical justification for selecting that tool.

Two sequential optimization modules refine this:

1. **Self-Refine Module (SRM)** — iteratively rewrites the planning text
   $P_t$ so its semantic similarity to the target user task $Q$ (cosine
   similarity between text embeddings) exceeds a threshold $\tau$ (default
   0.6), looping up to a max-iteration bound, each iteration conditioned on
   the full history of prior attempts and their similarity scores. This
   directly targets the failure mode the paper identifies in prior
   memory-poisoning work: a retrieved-but-irrelevant-looking decision gets
   ignored by the agent even if retrieval succeeds.
2. **CoT-Strategy Reasoning Module (CSRM)** — generates the reasoning text
   $R_t$ via three structured chain-of-thought steps: (1) why this tool
   applies to the task, (2) why it's effective for completing the task, (3)
   what impact using it will have — explicitly designed to make the agent's
   own internal validation/reasoning accept the malicious tool as legitimate,
   not merely to get the record retrieved.

Separately, a **retrieval component $R$** is constructed so the assembled
record $R \oplus D_{attack}$ ranks in the top-$K$ retrieved results for the
target query:

- **Black-box**: $R = Q \oplus T_m$ (the retrieval text is literally the
  query plus the tool-set) — simple, and per the paper "proven to be the
  most direct and effective method."
- **White-box**: $R$ is optimized via a HotFlip-style discrete token search
  against a contrastive loss (Eq. 5, InfoNCE-style: maximize similarity to
  the positive/target query, minimize similarity to $n$ negative queries),
  30 iterative steps, greedy top-100-candidate token replacement per step.

Full black-box and white-box algorithms are given as Algorithm 1 and
Algorithm 2 in the paper — both directly reusable as MAMBench reconstruction
pseudocode with attribution.

## 5. Target Surfaces (per attack surface taxonomy)

Primarily targets: **memory content** (the constructed adversarial
decision) and **retrieval** (the separately-optimized retrieval component).
Directly and explicitly also targets **reasoning/evidence interpretation** —
this is DSRM's core differentiator versus prior work, per the paper's own
framing: existing methods "do not systematically address how to make a
malicious action plan appear both contextually relevant and logically
consistent during the agent's internal validation and reasoning processes."
DSRM is the attack in this six-resource inventory most explicitly designed
to defeat an agent's own internal plausibility-checking, not just its
retrieval ranking.

## 6. Original Evaluation Setup (NOT MAMBench's)

- **Dataset**: Agent Security Bench (ASB) (Zhang et al., 2024) — 50 agent
  tasks across 10 domains (finance, law, education, IT management,
  investment, legal advice, medicine, autonomous vehicles, and others),
  each with predefined legitimate tools, attack tools, and adversarial
  instructions. DSRM selects the first task from each of the 10 domains,
  combined with all 400 ASB attack tools, yielding 400 unique attack
  scenarios; remaining ASB tasks are treated as benign background traffic
  incorporated into the knowledge base to simulate realistic noisy
  retrieval.
- **LLM backbones tested**: Gemma2-27B, LLaMA3-8B/70B, LLaMA3.1-70B,
  Qwen2-7B/72B, GPT-4o-mini, GPT-4o (default: LLaMA3-70B).
- **Retrievers tested**: DPR, REALM ("ReaLM" in the paper), MiniLM
  (default: DPR). Top-$K=5$ retrieved documents, 512-token input truncation.
- **Baselines compared against**: Naive-Attack (raw instruction as the
  decision), PoisonedRAG (Zou et al., 2024 — the strongest baseline),
  ASB's own built-in prompt-injection attack, and Corpus Poisoning Attack
  (Zhong et al., 2023 — white-box only).

## 7. Original Evaluation Metrics

- **ASR_A** (Attack Success Rate – All): the agent executes the attacker's
  intended action via the attack tool.
- **ASR_R** (Attack Success Rate – Retrieval-conditioned): ASR_A computed
  only over cases where the adversarial content was actually retrieved.
- **RR** (Retrieval Rate): how often the adversarial decision was
  successfully retrieved at all.

## 8. Reported Results (source paper's own claims — not MAMBench-verified)

Black-box, DPR retriever, LLaMA3-70B backbone (paper's default config):
DSRM ASR_A 43.00% vs. PoisonedRAG 36.00%, ASB 23.00%, Naive 16.00%, no-attack
baseline 11.00%. White-box (same config): DSRM ASR_A 44.50–49.00% depending
on table/ablation context (Table 3 reports 44.50%; Table 9's ablation full-
DSRM figure reports 49.00% under a different $K$/config — both are the
paper's own numbers, not reconciled by this dossier; a MAMBench
reconstruction should re-derive its own baseline rather than average these).

**Persistence under memory dilution** — directly relevant to MAMBench's
poison-lifecycle model (4.6): after diluting a DSRM-poisoned knowledge base
with up to 1,000 new benign memories, ASR_A on GPT-4o remained at ~39%
(from an initial 41%), demonstrating the attack is not merely a
freshness/recency artifact.

**Stealth against detection** — directly relevant to Phase 4's cross-attack
validation (4.10) and any future defense-evaluation work: LLM-based
detection showed an average 80.4% false-negative rate against DSRM;
perplexity-based detection scored AUC 0.49 (statistically indistinguishable
from random guessing); a perplexity-based re-ranking defense also failed to
meaningfully alter retrieval rankings, since DSRM's own generated content
exhibits low perplexity by design (it's optimized for fluency and task
relevance, not just semantic proximity).

**Ablation** (Table 9 of the source): removing SRM or CSRM individually both
substantially reduce ASR_A relative to full DSRM, with SRM's removal
costing more — confirming both modules are load-bearing, not redundant.

**Stability**: ASR_A across 4 random seeds varied within a narrow band
(e.g. 40.00–42.00% on LLaMA3-70B, mean 41.18%), supporting reproducibility
of the reported effect (modulo the general non-determinism caveat that
applies to any LLM-based campaign, including V3-Hybrid's own documented
run-to-run variation).

## 9. Attack Variants

- **Black-box DSRM** (Algorithm 1) — the primary, more realistic variant;
  retrieval text is simply query+toolset concatenation.
- **White-box DSRM** (Algorithm 2) — requires retriever parameter access;
  adds HotFlip-style gradient-guided retrieval-text optimization on top of
  the same SRM/CSRM decision-construction pipeline.

These are genuinely distinct attacker-knowledge variants sharing a common
decision-construction core — directly analogous to how the handoff
instructs DSRM's variants be preserved separately (the original Phase 4
prompt anticipated black-box/white-box DSRM variants specifically, and this
is now confirmed as the paper's actual structure, not a guess).

## 10. Relationship to Other In-Scope Attacks (cross-check for 4.10)

- DSRM's "disguise adversarial content as past experience/historical
  knowledge" framing is conceptually close to **FARMA**'s forged-reasoning-
  trace mechanism and **MemoryGraft**'s poisoned-"successful experience"
  mechanism — but DSRM's two-stage optimization (semantic-similarity-gated
  refinement + structured CoT justification) is a more explicit, more
  formally specified construction than either, and is evaluated against a
  much broader model/retriever grid (6 LLMs × 3 retrievers vs. FARMA's 3
  models, MemoryGraft's 1 model).
- DSRM's white-box retrieval-text optimization (HotFlip + contrastive loss)
  is mechanically similar in spirit to **AgentPoison**'s gradient-based
  trigger optimization, though DSRM optimizes the retrieval text per-query
  rather than a universal trigger token sequence, and targets the
  paper-defined ASB retriever set (DPR/REALM/MiniLM) rather than
  AgentPoison's six embedders.
- DSRM explicitly benchmarks against **AgentPoison** and **PoisonedRAG** by
  name as related/competing methods in its own Related Work section,
  characterizing AgentPoison's white-box-only dependency as a practical
  limitation DSRM's black-box mode is designed to avoid — this is the
  clearest explicit positioning of one in-scope attack against another
  found anywhere in this inventory.

## 11. MAMBench Adaptation Required

1. **Direct reconstruction path is now strong.** Full pseudocode
   (Algorithms 1–2), exact prompts (Tables A.1–A.3, reproduced faithfully
   below), and the exact contrastive loss (Eq. 5) are available — this
   reconstruction can be built with materially higher fidelity to the
   source than FARMA's (which had only illustrative examples, no
   pseudocode).
2. **Domain mismatch remains real.** ASB's 10-domain, 400-attack-tool
   structure (system administration, financial analysis, legal, medical,
   autonomous driving, etc.) is entirely tool-invocation-oriented — it has
   no analogue in V3-Hybrid's conversational LoCoMo QA setting, which has
   no "tools" to hijack. DSRM's core mechanism (bias the agent toward
   selecting an attacker tool) needs a MAMBench-native reformulation:
   V3-Hybrid's closest analogue to "tool selection" is which memory content
   the agent treats as authoritative when constructing its answer, not a
   literal tool call. This is a substantive reinterpretation, not a
   relabeling, and should be documented as a explicit MAMBench design
   decision, distinct from DSRM's original mechanism.
3. **Retriever mismatch.** DPR/REALM/MiniLM are not Mem0's actual
   `all-MiniLM-L6-v2`-based local embedder (though MiniLM is in the tested
   set, which is a partial overlap worth exploiting) nor A-MEM's embedding
   backend — re-validation against V3-Hybrid's actual `hybrid_selection.py`
   (cosine + token-overlap + entity-overlap rerank, not pure dense
   retrieval) is required before assuming DSRM's reported ASR transfers.
4. **Prompt templates are directly reusable as a starting point**
   (Section 12) with light MAMBench-specific field substitution
   (`{user task}`, `{tools}`, `{instruction}` need conversational-memory
   equivalents), reducing reconstruction risk relative to attacks with no
   published templates at all.

## 12. Reference Prompt Templates (verbatim from paper Appendix A, for direct reuse in reconstruction)

**Initial adversarial decision construction (Table A.1)**: instructs the
model to break the user task into a structured multi-step plan with tool
selection, given `{user task}`, `{tools}`, `{instruction}`.

**Iterative semantic-similarity refinement (Table A.2)**: instructs the
model to refine each step's `message` to improve relevance to the user task
given the current similarity score, while preserving step count/order and
`tool_use` fields exactly.

**Interpretable CoT tool-selection justification (Table A.3)**: instructs
the model to add a 3-part `interpretable` field to each step (why this
tool applies / why it's effective / expected impact), without modifying
`message` or `tool_use`.

All three use a fixed JSON list-of-steps output format
(`{"message": ..., "tool_use": [...]}`), which the MAMBench reconstruction
can adapt directly by substituting LoCoMo-conversational-task semantics for
the tool-invocation semantics.

## 13. Compatibility With Phase 4 Pre-Flight Decisions

- Does not depend on selection-policy manipulation (Decision 1) — DSRM
  targets retrieval ranking and reasoning acceptance, not the
  selection/rejection stage specifically.
- If piloted against A-MEM, subject to Decision 2 (A-MEM confound fix wired
  first) — DSRM was not evaluated against A-MEM or Mem0 in its original
  form (ASB uses its own tool-invocation agents), so this would be a novel
  MAMBench application regardless.
- New campaign records carry environment provenance per Decision 3.
- The paper's own persistence and stealth findings (Section 8) are strong
  candidates for new MAMBench counterfactual measurement (Decision 4) —
  establishing whether a DSRM-style injected decision *causally* changed
  V3-Hybrid's answer, versus merely being retrieved, requires fresh
  measurement; the source paper's ASR figures cannot be inherited as
  causal evidence.

## 14. Deviations / Unresolved Ambiguities

- Table 2 vs. Table 9 report different ASR_A figures for the same
  black-box DSRM/LLaMA3-70B/DPR-adjacent configuration (43.00% vs. 49.00%)
  — likely due to differing $K$ or ablation-context settings not fully
  disambiguated in this pass; flagged rather than silently reconciled.
- The relationship between the paper's "two-stage optimization" framing in
  the abstract (semantic disguise + content expansion) and the SRM/CSRM
  module framing in the method section is now fully resolved — they are
  the same two stages, described at different levels of abstraction (this
  ambiguity from the earlier draft of this dossier is now closed).
- **UNKNOWN / NOT VERIFIED**: any post-publication code release beyond
  what "available on request" implies — worth a follow-up direct request to
  the corresponding authors if reconstruction fidelity needs to exceed what
  the paper's own text provides.

## 15. Recommended 4.4 Reconstruction Path

```text
Published paper (Jing et al., 2026, Eng. Applications of AI 167:113968)
      ↓
Full pseudocode + prompts directly available (Sections 4, 12) — highest-
fidelity reconstruction basis of any attack in this inventory requiring
reconstruction
      ↓
MAMBench-native reformulation: replace ASB's tool-selection objective with
a V3-Hybrid-native objective (biasing which memory content the agent treats
as authoritative for its answer), preserving SRM's similarity-gated
refinement loop and CSRM's structured justification generation unchanged
      ↓
Black-box variant (primary) + white-box variant (if retriever gradient
access to Mem0's local embedder is judged in-scope) implemented and
labeled separately per Section 9
      ↓
Validate against V3-Hybrid's hybrid_selection.py rerank (not pure dense
retrieval) — re-derive ASR/ASR_R/RR-equivalent metrics rather than
assuming the source paper's figures transfer
```

Label throughout as `MAMBench reconstruction of DSRM`, never as the
original authors' implementation, per the handoff's explicit requirement.

## 16. Sources

- Full text of Jing, H., Li, F., Dong, Y., Zhou, W., Liu, R. (2026).
  "Memory poisoning attacks on retrieval-augmented Large Language Model
  agents via deceptive semantic reasoning." *Engineering Applications of
  Artificial Intelligence*, 167, 113968.
  https://doi.org/10.1016/j.engappai.2026.113968 — supplied by the user as
  `C:\RESEARCH\Engineering applications of AI.pdf` and read in full for
  this revision.
