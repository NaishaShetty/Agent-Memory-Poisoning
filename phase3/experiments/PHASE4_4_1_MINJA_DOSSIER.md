# Phase 4.1 — Attack Source Dossier: MINJA

Status: **DRAFT — 4.1**. Verified via arXiv, NeurIPS listing, and GitHub API as
of this drafting session. Unverified fields are marked `UNKNOWN / NOT
VERIFIED`. No MAMBench code was written or modified to produce this document.

## 1. Identity

| Field | Value |
|---|---|
| Paper title | "Memory Injection Attacks on LLM Agents via Query-Only Interaction" (the arXiv v1 HTML mirror carries an earlier working title, "A Practical Memory Injection Attack against LLM Agents" — the title changed across revisions; treat the NeurIPS/later-version title as canonical) |
| Authors | Shen Dong, Shaochen Xu, Pengfei He, Yige Li, Jiliang Tang, Tianming Liu, Hui Liu, Zhen Xiang |
| Affiliations | **UNKNOWN / NOT VERIFIED** (not surfaced in the extracted content) |
| Venue | **NeurIPS 2025 (poster) — now independently confirmed** by a second, unrelated source: the MPBench paper (Dash et al., 2026, arXiv:2606.04329) cites this work in its own references as "Dong, S., Xu, S., He, P., Li, Y., Tang, J., Liu, T., Liu, H., and Xiang, Z. Memory injection attacks on LLM agents via query-only interaction. In Advances in Neural Information Processing Systems (NeurIPS), 2025." — matching both the NeurIPS virtual listing and this dossier's author list exactly. |
| arXiv | [2503.03704](https://arxiv.org/abs/2503.03704), v1 submitted 2025-03-05, latest v5 2026-02-12 (multiple revisions between) |
| Notable author overlap | **Zhen Xiang** is a co-author on both MINJA and AgentPoison — the two most reference-implementation-mature attacks in this Phase 4 inventory share an author, which may mean shared code conventions or shared target-agent choices worth checking during 4.3. |
| Official repo | [dsh3n77/MINJA](https://github.com/dsh3n77/MINJA) — MIT License, 37 stars, created 2026-01-25, actively pushed (last observed 2026-08-11) |
| License | MIT — no MAMBench licensing blocker |

## 2. Classification

**`REFERENCE_IMPLEMENTATION` — real, MIT-licensed, actively maintained repo,
directly matching the published methodology's name and description.**

Like AgentPoison, this belongs on the 4.3 (Reference Implementation
Integration) track, not 4.4 reconstruction.

## 3. Threat Model / Attacker Assumptions — the key distinguishing fact

**MINJA requires only query-only interaction with the agent's normal
public-facing interface — no memory-write API access, no embedder gradients,
no insider access.** This is a third, distinct capability tier compared to
the other four attacks reviewed so far:

| Attack | Minimum required access |
|---|---|
| AgentPoison | White-box gradient access to the retrieval embedder |
| FARMA | Direct write access to the memory store (write-only) |
| **MINJA** | **Query-only — ordinary user-facing interaction, no privileged access at all** |

This makes MINJA the most realistic/low-privilege threat model of the three
examined in depth so far, and arguably the most directly relevant to a
"what can any user of a deployed agent do" framing for Phase 4's ground truth
(4.9).

The attack works by having the attacker issue a sequence of queries designed
so the agent's own memory-writing behavior (writing its own reasoning/results
back to memory, as many agent memory systems do) ends up storing malicious
records — the attacker never touches memory directly; they manipulate the
agent into poisoning its own memory through normal interaction.

## 4. Mechanism

Three named components, per the abstract/summary evidence gathered:

1. **Bridging steps** — a sequence of intermediate queries/reasoning steps
   engineered to link an eventual victim query to a malicious reasoning
   pattern, so that when the agent later processes a real victim query, it
   retrieves and follows the injected reasoning.
2. **Indication prompt** — a prompt used during the injection interaction to
   guide the agent to autonomously generate the desired bridging reasoning
   steps itself (i.e., the agent is induced to write its own poison).
3. **Progressive shortening strategy** — the indication prompt is gradually
   shortened/removed across the injection sequence, specifically to improve
   how retrievable the resulting malicious record is once no explicit
   indication remains (defeats "the injected content is discoverably
   artificial" concerns).

Reported effectiveness (source paper's own claims, **not MAMBench-verified**):
one search extraction reported "98.2% average success rate for injecting
malicious records"; a separate extraction of the same underlying work
reported "98.2% injection success and 76.8% attack success rate" — i.e.
injection success and *downstream* attack success are two different reported
numbers, and the higher figure (98.2%) refers to getting the record into
memory, not to the record subsequently causing the intended malicious agent
action. Treat these as two separate metrics, not one figure restated twice.

## 5. Target Surfaces (per attack surface taxonomy)

Primarily targets: **memory admission** (getting a malicious record accepted
via the agent's own self-writing behavior) and **retrieval** (bridging steps
and progressive shortening are explicitly retrieval-optimization techniques).
Notably does **not** require any capability targeting memory write APIs,
embedders, or memory lifecycle directly — the entire attack surface is the
agent's own query-processing/reasoning loop.

## 6. Original Evaluation Setup (NOT MAMBench's)

- **Agents evaluated**: RAP Agent (shopping/preference-pattern agent — the
  same RAP referenced in FARMA's evaluation), EHR Agent (medical —
  overlapping with both AgentPoison's and FARMA's EHRAgent evaluation), and a
  QA Agent. **This is a real, notable overlap**: three of the five attacks
  reviewed in this inventory (AgentPoison, FARMA, MINJA) all evaluate against
  an EHRAgent-family target, and FARMA/MINJA both use a RAP-family shopping
  agent. This is a genuine opportunity for Phase 4's 4.10 cross-attack
  validation — if MAMBench ever builds EHR- or RAP-style task adapters for
  one attack, the same adapter shape may be reusable for the others — but it
  is still not LoCoMo/conversational memory, so the domain-mismatch problem
  documented for AgentPoison and FARMA applies here too.
- **Victim/target pair types**: the paper considers four distinct
  victim-target pairing types — **UNKNOWN / NOT VERIFIED** what the four types
  specifically are; not resolved from the extracted content in this pass.

## 7. MAMBench Adaptation Required

1. **Most naturally compatible threat model of the attacks reviewed so far** —
   since it requires no privileged access, it maps directly onto simply
   issuing task queries to the real V3-Hybrid agent through its existing
   `run_condition_c_v3_mem0`/`run_condition_c_v3_amem` entry points. No new
   privileged injection path needs to be built into the adapter, unlike
   AgentPoison (needs an embedder-gradient path) or FARMA (needs a raw
   memory-write path).
2. **Domain/task mismatch** remains, same as the other attacks — bridging
   steps and indication prompts were designed for RAP/EHR/QA-style
   task-execution agents, not LoCoMo's conversational-memory QA setting. The
   bridging-step *technique* may transfer; the specific prompts/templates
   used in the original repo will not, and need MAMBench-specific redesign
   validated empirically, not assumed.
3. **Verify the reported 98.2%/76.8% figures are per-agent-per-task,** not a
   single pooled number, before treating either as a MAMBench comparison
   baseline — this needs the actual paper table, not just the abstract-level
   summary gathered in this pass.
4. Since the attack is entirely conducted through the agent's own
   query-response interface, MAMBench's injection ground truth (4.9) needs to
   record the **full query sequence** used (bridging steps + indication
   prompt + shortening schedule) as the poison artifact's provenance, not
   just a single "payload" string — the attack's identity is the sequence,
   not any one message.

## 8. Compatibility With Phase 4 Pre-Flight Decisions

- Does not depend on selection-policy manipulation (Decision 1).
- If piloted against A-MEM, subject to Decision 2 (A-MEM confound fix
  wired first).
- New campaign records carry environment provenance per Decision 3.
- Because MINJA's injection *is* a sequence of ordinary agent
  queries/executions, establishing what portion of that sequence was
  causally necessary for the eventual malicious record (vs. incidental) is
  exactly the kind of claim Decision 4 restricts — any such claim requires a
  new counterfactual measurement, not inference from retrieval alone.

## 9. Deviations / Unresolved Ambiguities

- **UNKNOWN / NOT VERIFIED**: author affiliations.
- **UNKNOWN / NOT VERIFIED**: exact venue confirmation directly from the
  arXiv page's own metadata (relied on the NeurIPS virtual-site listing as
  corroboration instead).
- **RESOLVED (2026-09-11)**: `rap/victim_target_pair/victim_target.json` was
  read directly. It is not four abstract "pairing types" — it is a flat list of
  **9 concrete victim→target product-substitution pairs** for the WebShop/RAP
  shopping domain, e.g. `{"victim": "camera", "target": "Samsung Business SR35
  Series 22-Inch FHD 1080p Computer Monitor...", "target_price": 120.00}`. The
  attack's premise in this domain: bridging queries falsely associate an
  innocuous victim item (e.g. "camera") with a completely unrelated target
  item (a monitor), and success is the agent recommending/selecting the
  mismatched target when a user later asks about the victim category. The
  original "four pair types" phrasing in this dossier's earlier draft appears
  to have been an inference from search-summary text, not something this file
  itself contains — if the source paper's own text separately describes four
  categorical pairing *strategies* (as opposed to these 9 concrete instances),
  that remains unverified and would require reading the paper directly, not
  this data file.
- **UNKNOWN / NOT VERIFIED**: whether the 98.2% and 76.8% figures are
  reported per-agent or pooled, and over how many trials.
- The repo's actual file-level completeness (does it cover all three agents
  end-to-end, are dependencies pinned, etc.) was confirmed to exist and be
  MIT-licensed via the GitHub API only — **not** independently inspected
  file-by-file in this pass. A deeper code read is 4.3 work, not 4.1.

## 10. Recommended 4.3 Integration Path

```text
Reference MINJA attack logic (bridging steps + indication prompt +
progressive shortening, reused directly)
      ↓
MAMBench Adapter: replaces RAP/EHR/QA-specific task/query templates with
LoCoMo-conversational-memory-appropriate query sequences targeting Condition
C (Mem0/A-MEM), tagged with a PoisonArtifact recording the full query
sequence as provenance (per 4.6)
      ↓
Common Attack Contract (4.2)
      ↓
V3-Hybrid environment, Condition C
```

Lowest-friction integration of the attacks reviewed so far, given the
query-only threat model requires no new privileged access path — but the
task-template redesign (item 2, Section 7) is real work, not a formality.

## 11. Sources

- [MINJA — arXiv:2503.03704](https://arxiv.org/abs/2503.03704)
- [arXiv:2503.03704 v1 HTML mirror](https://arxiv.org/html/2503.03704v1)
- [NeurIPS 2025 poster listing](https://neurips.cc/virtual/2025/poster/118152)
- [dsh3n77/MINJA — official repository](https://github.com/dsh3n77/MINJA)
- GitHub REST API (`api.github.com/repos/dsh3n77/MINJA`, `.../license`) —
  queried directly for license, star count, and push date.
