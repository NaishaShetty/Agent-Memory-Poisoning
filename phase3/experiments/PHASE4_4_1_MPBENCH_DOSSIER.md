# Phase 4.1 — Attack/Resource Source Dossier: MPBench

Status: **DRAFT — 4.1, REVISED.** Originally verified via arXiv (abstract +
HTML text); revised after the user supplied the full PDF locally
(`C:\RESEARCH\From Untrusted Input to Trusted Memory...pdf`), which has now
been read in full and resolves several fields left unverified in the
original pass. Unverified fields are marked `UNKNOWN / NOT VERIFIED`. No
MAMBench code was written or modified to produce this document.

## 1. Identity

| Field | Value |
|---|---|
| Source paper title | "From Untrusted Input to Trusted Memory: A Systematic Study of Memory Poisoning Attacks in LLM Agents" |
| Resource name | MPBench — introduced within this paper as its benchmark contribution, not published as a separately-titled work |
| Authors | Pritam Dash, Tongyu Ge, Aditi Jain, Zhiwei Shang (Huawei Canada), Tanmay Shah (University of Waterloo; work done during a Huawei internship) |
| Venue | **Confirmed peer-reviewed workshop, not arXiv-only as previously stated**: Published at the Second Workshop on Agents in the Wild: Safety, Security, and Beyond (AIWILD) at ICML 2026 |
| arXiv | [2606.04329](https://arxiv.org/abs/2606.04329), v1 2026-06-03, v2 2026-06-18 (cs.CR) |
| Code/data repository | **None found even after full-text read.** No code/data availability statement, appendix link, or GitHub reference appears anywhere in the paper, including its appendices (A–D) and references. This is now a higher-confidence negative finding than the earlier search-only pass — a full read found nothing, not just a failed search. |
| License | N/A — no released artifact found |

## 2. Classification

**`DATASET/BENCHMARK_RESOURCE` per the handoff's own instruction to treat
MPBench as a scenario/benchmark resource rather than a seventh attack
algorithm — but with an important caveat that changes what 4.5 actually
means here: no downloadable dataset or benchmark harness was found.**

This is a materially different situation from what "integrate MPBench" would
normally imply (mapping an existing released benchmark's scenarios into
MAMBench's representation, per the handoff's 4.5 description). As it stands,
MPBench currently appears to exist **only as described inside the paper**,
not as an obtainable artifact. Until a release is located (it may exist but
be unindexed, anonymous-linked, or planned-but-not-yet-published given the
paper's very recent June 2026 date), 4.5 needs to be scoped as **"reconstruct
MPBench's scenario taxonomy and methodology from the paper"** rather than
"integrate the released benchmark" — a meaningfully larger task, closer in
spirit to 4.4's reconstruction discipline than to 4.5's original "thin
mapping layer" framing.

## 3. What MPBench Actually Measures

Two-phase measurement, explicitly designed to distinguish getting poison
*into* memory from poison *changing subsequent agent behavior* — directly
relevant to MAMBench's own poison-lifecycle model (4.6):

1. **Write phase** — an adversarial payload is embedded in external
   environmental data and delivered to the agent through a task scenario; the
   agent processes the task and (if vulnerable) writes attacker-influenced
   content to persistent memory. Measured via **ASR** (Attack Success Rate):
   how often the malicious instruction actually reaches persistent memory.
2. **Retrieval phase** — a subsequent, separate session presents queries to
   test whether the previously-written poisoned memory influences the
   agent's future behavior. Measured via **RSR** (Retrieval Success Rate,
   called "Retrieval Success Rate" in the extraction — verify exact naming
   against primary text before adopting into MAMBench's own metric
   vocabulary): how often a poisoned entry actually influences subsequent
   behavior once retrieved.

This write/retrieve separation is explicitly the same distinction Phase 3's
own infrastructure and Phase 4's poison-lifecycle model (4.6, e.g.
`POISON_ADMITTED` vs. `POISON_RETRIEVED` vs. `POISON_INFLUENCED_RESPONSE`)
already make — MPBench's taxonomy is a strong structural match for MAMBench's
existing ground-truth vocabulary, more so than any other resource in this
inventory.

## 4. Six Attack Classes (taxonomy)

1. **Explicit Command Insertion** — direct memory-write instructions embedded
   in external content.
2. **Conditional Command Insertion** — instructions conditioned on the user
   giving an affirmative response before triggering.
3. **Salience-Driven Compaction Poisoning** — repeated malicious content
   exploited during summarization/compaction, where repetition itself signals
   "importance" to the compaction mechanism.
4. **Policy Conformant Fact Injection** — fabricated information presented in
   a way that conforms to the agent's own retention/acceptance policy,
   passing as legitimate knowledge.
5. **False Precedent Insertion** — fabricated task records formatted as
   historical experience. **Directly overlaps conceptually with FARMA's
   forged-reasoning-trace mechanism and, more loosely, with MemoryGraft's
   poisoned-experience mechanism** — worth using as a cross-check point during
   4.10 cross-attack validation, not collapsing into either.
6. **Skill-Procedure Insertion** — adversarial steps embedded in task
   interactions that trigger the agent's own skill-synthesis behavior.
   **Directly overlaps conceptually with MemoryGraft's semantic-imitation
   mechanism** for the same reason.

## 5. Four Memory Write Channels

- **C1** — explicit instruction-executed write (direct user command).
- **C2** — system-prompt-driven write (agent evaluates content against its
  own retention policy).
- **C3** — compaction-driven write (consolidation triggered by context
  limits or session termination).
- **C4** — experience-to-procedure write (synthesizing a completed task into
  a reusable skill).

**UNKNOWN / NOT VERIFIED**: how directly these four channels map onto
V3-Hybrid's actual write paths (Mem0/A-MEM ingestion via
`run_condition_c_v3_mem0`/`run_condition_c_v3_amem`) — V3-Hybrid does not
currently have a compaction (C3) or skill-synthesis (C4) mechanism as far as
established Phase 3 evidence shows, meaning two of MPBench's four channels may
have no MAMBench-side target at all, similar to the consensus-defense gap
noted in FARMA's dossier. This should be checked explicitly, not assumed away.

## 6. Nine Structural Vulnerabilities

Model level: Instruction-Data Boundary Blindness (V-M1); Source Attribution
Failure in Multi-Source Contexts (V-M2). Prompt-design level: Memory Write
Policy Under-Specification (V-P1); Compaction Without Source Filtering
(V-P2). System-architecture level: No Write-Path Validation (V-S1); Shared
Multi-Source Context (V-S2); Manipulable Compaction Trigger (V-S3); No
Validation for Skill Creation (V-S4); Self-Improvement as Amplification
(V-S5).

This vulnerability taxonomy is a useful checklist for Phase 4.7 (Attack ↔
Phase 3 Agent Integration) — before integrating any attack against V3-Hybrid,
checking which of these nine V3-Hybrid structurally has (e.g. it plausibly
has V-M1/V-M2-style boundary issues in principle, but has no compaction
mechanism at all, so V-P2/V-S3 don't apply) would give Phase 4 an
evidence-based rather than assumed compatibility map.

## 7. Evaluated Agents (NOT MAMBench's)

- **OpenClaw** — a personal AI assistant supporting file operations, web
  browsing, email, calendar management, Slack, script execution, and skill
  invocation.
- **HERMES** — an agent framework emphasizing autonomous skill creation and
  self-improvement.

Reported ASR: HERMES 66.67%, OpenClaw 34.25% — the paper attributes the gap to
HERMES's more aggressive memory-write policy and lower summarization
threshold. Average ASR across both: 50.46%; average RSR: 41.05%.

Neither agent resembles V3-Hybrid's conversational-QA-over-LoCoMo setup —
both are broad, tool-using personal/autonomous assistants, a materially
different agent class than any of the other five resources in this inventory
were evaluated against either, but especially distant from V3-Hybrid.

## 8. Dataset Specification

3,240 adversarial test cases plus 2,997 benign examples, spanning the six
attack classes above across **seven domain types**: file operations, web
browsing, email, calendar management, Slack, script/code execution, and skill
invocation. **Now confirmed exact per-class counts** (Table 7 of the source):
Explicit Command Insertion 600, Conditional Command Insertion 600,
Salience-Driven Compaction Poisoning 600, Policy Conformant Fact Injection
600, False Precedent Insertion 600, Skill-Procedure Insertion 240 (lower —
generated exclusively for HERMES, since OpenClaw lacks the C4 write channel
that class requires). Total 3,240 + 2,997 benign = 6,237 records.

**Model used**: all experiments used a single model, **GPT-OSS-120B**, with
each agent's default system prompt and default memory-write configuration —
this was previously unconfirmed and materially affects how ASR/RSR figures
should be interpreted (single-model results, explicitly disclosed by the
authors as a limitation — see Section 8a).

**Exact per-attack-class results** (Table 2 of the source; previously only
averages were captured):

| Attack class | Signal | Channel | OpenClaw ASR / RSR | HERMES ASR / RSR |
|---|---|---|---|---|
| Explicit Command Insertion | Strong | C1 | 18.25% / 44.23% | 42.67% / 86.33% |
| Conditional Command Insertion | Strong | C1 | 67.89% / 13.79% | 76.00% / 92.76% |
| Salience-Driven Compaction Poisoning | Strong | C3 | 45.10% / 11.31% | 85.17% / 69.86% |
| Policy-Conformant Fact Injection | Weak | C2 | 8.33% / 5.93% | 64.50% / 42.12% |
| False Precedent Insertion | Weak | C2 | 31.67% / 11.72% | 73.33% / 35.45% |
| Skill-Procedure Insertion | Weak | C4 | N/A (unsupported) | 58.33% / 61.67% |
| **Average** | — | — | **34.25% / 17.40%** | **66.67% / 64.70%** |

**Data generation pipeline — now fully documented, not a black box.** Each
test case is generated from a structured template fixing four inputs (attack
class, signal strength, domain, adversarial goal), using
Meta-Llama-3.1-70B-Instruct to synthesize the variable components (user
query, payload-bearing context, expected memory entry, retrieval query),
validated for schema compliance and spot-checked. **Full JSON schema**
(Figure 3 of the source): `id`, `attack_type`, `attack_signal`
(strong/moderate/weak), `domain`, `adversarial_goal` (credential harvesting,
data exfiltration, recommendation poisoning, auth bypass, unauthorized
action, trust hijacking), `user_query`, `context`, `expected_memory`,
`retrieval_query`. Per-class generation constraints are individually
documented in Appendix D.3 (e.g. exact trigger-keyword table for Explicit
Command Insertion, exact repetition-count/disguise-level rules for
Salience-Driven Compaction Poisoning).

**This is a materially stronger basis for reconstruction than the earlier
pass assumed** — see Section 9a below.

## 8a. Author-Disclosed Limitations (directly transferable to MAMBench's own disclosure)

- **Single model only** (GPT-OSS-120B) — different models may produce
  different ASR/RSR; MAMBench should not assume these figures transfer to
  Qwen3-8B without re-measurement, exactly as this dossier's other entries
  already note for their own source models.
- **Delivery-mode caveat**: for email, Slack, and web-browsing domains, the
  benchmark delivers the payload as a labeled context block alongside the
  user query, rather than simulating the full tool-call/retrieval pipeline a
  real deployment would use — the authors call this "a controlled emulation
  of real deployment," consistent with prior agent-security benchmark
  methodology (InjecAgent), not a full-fidelity simulation. Any MAMBench
  scenario built on this methodology should carry the same disclosed caveat.
- **Defense evaluation** (Section 8b) used four prompt-injection defenses
  (PIGuard, DataFilter, CommandSans, PromptArmor) and found none achieves
  both high true-positive and low false-positive rates against memory
  poisoning; even the best (PromptArmor, 70B-parameter LLM guardrail)
  reaches only 67.67% TPR at 1.00% FPR off-the-shelf, and retraining/
  adaptation does not meaningfully close the gap — weak-signal attacks
  (Policy-Conformant Fact Injection, False Precedent Insertion,
  Skill-Procedure Insertion) are systematically harder to detect than
  strong-signal ones across every defense tested. This is directly relevant
  to Phase 4's own negative-control and defense-adjacent thinking (4.10).

## 8b. Vulnerability Taxonomy Detail (now fully confirmed, not partial)

Nine structural vulnerabilities, exactly mapped to write channels (Table 1
of the source, confirmed verbatim): **V-M1** Instruction-Data Boundary
Blindness (→C1, direct), **V-M2** Source Attribution Failure (→C2/C3,
inferred), **V-P1** Memory Write Policy Under-Specification (→C2,
inferred), **V-P2** Compaction Without Source Filtering (→C3, inferred),
**V-S1** No Write-Path Validation (→C1/C2/C3), **V-S2** Shared Multi-Source
Context (→C1/C2/C3), **V-S3** Manipulable Compaction Trigger (→C3),
**V-S4** No Validation for Skill Creation (→C4), **V-S5** Self-Improvement
as Amplification (→C4 only — "has no equivalent in static memory systems").

Attacker threat model, now fully confirmed from the primary text: external
adversary, **no privileged access** — cannot read/modify memory directly,
cannot alter the system prompt, cannot impersonate the user, cannot observe
internal reasoning; relies solely on black-box interaction via environmental
content (webpages, documents, emails, tool outputs) the agent processes
during normal operation, plus publicly available agent documentation. This
is a **third distinct capability tier**, alongside AgentPoison's white-box
embedder access, FARMA's direct write access, and MINJA's query-only
interaction — MPBench's threat model is closest to MemoryGraft's
"ingestion-level artifact" framing but formalized across four distinct
trigger/write-authority channels rather than one.

## 9a. Reconstruction Confidence — revised upward

The original pass of this dossier flagged 4.5 as needing to become a
taxonomy reconstruction rather than a dataset-mapping exercise. That
conclusion still holds (no artifact exists), but the confidence in that
reconstruction is now substantially higher: the full generation
methodology (template inputs, generator model, exact JSON schema, and
per-class generation constraints) is documented in the paper's Appendix D,
not merely inferred from an abstract. A MAMBench-native scenario generator
built on this specification is a faithful methodological reconstruction,
not a loose approximation — closer in spirit to DSRM's reconstruction
confidence (Section 11 of that dossier) than to the original, lower-
confidence assessment of this resource.

## 9. MAMBench Adaptation Required

1. **Resolve the artifact-availability question first** (Section 2) — this
   determines whether 4.5 is a mapping task or a reconstruction task.
2. **Domain translation is the largest gap of any resource in this
   inventory.** None of file operations/web browsing/email/calendar/Slack/
   script execution/skill invocation maps onto LoCoMo's conversational
   question-answering domain. Only the underlying **taxonomy structure**
   (six attack classes, four write channels, nine vulnerabilities, two-phase
   ASR/RSR measurement) is portable — the actual scenario content is not.
3. **Channel applicability check** (Section 5) should be done before scenario
   design, not after, since it may narrow MPBench's six classes down to a
   smaller MAMBench-relevant subset (e.g. Explicit/Conditional Command
   Insertion and False Precedent Insertion look directly portable to a
   Mem0/A-MEM write path; Compaction Poisoning and Skill-Procedure Insertion
   may not have a V3-Hybrid target at all).
4. **Metric naming**: adopt MPBench's ASR/RSR distinction into MAMBench's own
   ground-truth vocabulary (4.9) explicitly, since it's a close structural
   match to `POISON_ADMITTED`/`POISON_RETRIEVED`/`POISON_INFLUENCED_RESPONSE`
   — but confirm exact metric definitions against primary text first (the RSR
   name was not independently double-checked against the paper's own
   notation in this pass).

## 10. Compatibility With Phase 4 Pre-Flight Decisions

- MPBench's False Precedent Insertion and related classes could, in
  principle, be used to construct a selection-manipulation scenario — if so,
  Decision 1 applies and any such MAMBench scenario must explicitly disclose
  use of the non-canonical selection-policy variant, not the canonical path.
- If any adapted scenario targets A-MEM, Decision 2 applies.
- New campaign records carry environment provenance per Decision 3.
- ASR/RSR-style claims about whether poison "influenced behavior" fall
  squarely under Decision 4's causal-claim restriction — MPBench's own RSR
  metric measures whether poison was retrieved *and subsequently correlated
  with* a behavior change, which is evidence of interventional dependence at
  best, not proof of causation, when re-measured under MAMBench.

## 11. Deviations / Unresolved Ambiguities

- **UNKNOWN / NOT VERIFIED**: author affiliations.
- **UNKNOWN / NOT VERIFIED**: whether any code/dataset release exists but was
  simply not indexed by the search tools used in this pass (recommend a
  direct check of the paper's own appendix/supplementary section, not just
  the abstract/body text, before finalizing 4.5 scope).
- **UNKNOWN / NOT VERIFIED**: exact per-domain/per-class signal-strength
  distribution of the 3,240+2,997 dataset.
- **UNKNOWN / NOT VERIFIED**: precise definition and computation of RSR as
  named in the primary text (this dossier's Section 3 description is a
  reasonable-confidence paraphrase from extracted content, not a verbatim
  definition).
- Given the paper's very recent date (v2 2026-06-18) relative to today,
  worth a re-check for a later version or an accompanying artifact release
  immediately before 4.5 work begins, not only at 4.1 time.

## 12. Recommended 4.5 Path (revised given Section 2's finding)

```text
Published paper (arXiv 2606.04329) — taxonomy + methodology only, no artifact
      ↓
Extract portable structure: 6 attack classes, 4 write channels,
9 vulnerabilities, 2-phase ASR/RSR measurement model
      ↓
Channel-applicability check against V3-Hybrid's actual write paths
(Section 5) — narrows which classes have a real MAMBench target
      ↓
MAMBench-native scenario construction for the applicable subset, using
LoCoMo-conversational-memory content — explicitly documented as MAMBench's
own scenario design, not claimed as "the MPBench dataset"
      ↓
Map into MAMBench's attack-contract representation (4.2) and ground-truth
vocabulary (4.9), reusing the ASR/RSR-style write/retrieve distinction
```

This is closer to a **reconstruction of MPBench's methodology**, in the same
spirit as 4.4's discipline for FARMA/DSRM, than to 4.5's originally-described
"thin mapping layer over an existing released resource." Label any
MAMBench-built scenario as `MAMBench scenario inspired by MPBench's
taxonomy`, never as "the MPBench benchmark," unless and until an actual
released dataset is located and directly incorporated.

## 13. Sources

- [MPBench source paper — arXiv:2606.04329](https://arxiv.org/abs/2606.04329)
- [arXiv:2606.04329 v1 full HTML text](https://arxiv.org/html/2606.04329v1)
- Targeted search for an MPBench code/data repository — no direct hit found;
  only a third-party citation in
  [TeleAI-UAGI/Awesome-Agent-Memory](https://github.com/TeleAI-UAGI/Awesome-Agent-Memory).
