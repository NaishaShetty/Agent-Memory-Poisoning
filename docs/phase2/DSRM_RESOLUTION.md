# DSRM Identity Resolution (Phase 2.1-R, Part 3)

## Status change

| | Before (Phase 1 / Phase 2.1) | After (Phase 2.1-R) |
|---|---|---|
| `phase1_status` | `INACCESSIBLE` | `INSPECTED` |
| `resource_identity` | unresolved — "NOT FOUND / COULD NOT VERIFY" | **VERIFIED** |
| `implementation_availability` | not applicable | **not found** (paper only; no public repo) |
| `acquisition_status` | paywalled article, HTTP 403, could not confirm acronym meaning | paper content verified via the project's own prior literature-review chapter |

The old "DSRM identity unresolved" issue is closed. It is replaced by an
accurate, bounded claim: the paper is identified and its mechanism is
documented; no implementation exists to run.

## The authoritative source

> Hao Jing, Fanxiao Li, Yunyun Dong, Wei Zhou, Renyang Liu. "Memory
> poisoning attacks on retrieval-augmented Large Language Model agents
> via deceptive semantic reasoning." *Engineering Applications of
> Artificial Intelligence*, Volume 167 (2026), Article 113968.

This citation was supplied directly for this remediation and is used as
the authoritative identity for the DSRM entry, per instruction. No DOI
was supplied or located in the sources checked.

**Discrepancy noted, not silently resolved:** the project's own prior
literature-review chapter (`Agent Memory Poisoning 2.docx`, Chapter 4
references list) cites this same paper (same journal, volume, article
number 113968) but lists its authors as "Li, F., Dong, Y., Zhou, W., &
Liu, R. (2026)" — omitting Jing, H. as first author. Both sources agree
on every other bibliographic detail (journal, volume 167, article
113968, year 2026), so this is almost certainly a citation-formatting
omission in the project's own earlier draft rather than a different
paper. The supplied citation (including Jing, H.) is treated as
authoritative per this remediation's explicit instruction; the
discrepancy itself is recorded here rather than quietly dropped.

## What DSRM does (documented, not fabricated)

The following is drawn from the project's own prior literature-review
chapter on this exact paper (`Agent Memory Poisoning 2.docx`, Section
4.3, "Attacks Addressed in the Engineering Applications of AI Paper (Jing
et al., 2026)") — a project-internal secondary source that had already
read and summarized the paper before this remediation pass, not
independently re-derived from the primary source here. This is disclosed
so the provenance of this documentation is clear.

- **Attack objective.** Cause a RAG-based tool-using agent to select a
  specific attacker-controlled tool for ordinary, benign-looking user
  tasks — steering the agent's *actions*, not just what it says.
- **Access setting.** The attacker cannot access the agent's core LLM
  (parameters, training data, architecture) and interacts only via API
  calls, but can insert content into the agent's knowledge base — either
  by compromising an external data source, or by posing as a benign user
  and inducing the agent to autonomously generate and store a poisoned
  "past experience." Two variants are studied: **black-box** (attacker
  knows only that a retriever is used) and **white-box** (attacker has
  full access to the retriever's parameters).
- **Injection mechanism — deceptive semantic reasoning.** Every
  adversarial decision has three parts: a Planning Text, a Tool
  Selection, and a Reasoning Text. Two refinement stages disguise and
  justify it:
  - **Self-Refine Module (SRM):** iteratively revises the planning text,
    measuring cosine similarity to the user's actual task at each step,
    until a calibrated similarity threshold is crossed — disguising the
    adversarial decision as a natural extension of the user's own task.
  - **CoT-Strategy Reasoning Module (CSRM):** builds the Reasoning Text
    as three explicit chain-of-thought justification steps (why the tool
    applies, why it's effective, its expected positive impact) to make
    the adversarial tool choice appear logically sound.
- **Retrieval construction.** Black-box: direct concatenation of the
  target query and tool set, relying on surface-level similarity.
  White-box: contrastive-loss optimization of the retrieval text (via
  HotFlip-style gradient-guided token substitution) to maximize
  similarity to the target query while minimizing similarity to
  distractor queries.
- **Target behavior / retrieval setting.** RAG-based agentic tool
  selection specifically — the paper positions this against prior
  knowledge-corruption attacks (e.g. PoisonedRAG, AgentPoison) that
  target a QA agent's final textual output, arguing those do not address
  making an entire malicious *action plan* appear contextually relevant
  and logically consistent under an agent's own reasoning.
- **Persistence.** The paper reports poisoned decisions remain effective
  even after the knowledge base is diluted with up to 1,000 additional
  benign entries.

## Black-box / white-box settings — explicitly distinguished, per instruction

Both settings are real, distinct conditions studied in the paper (see
above); this project does not collapse them into one.

## Evaluation environment — accurately characterized, not overclaimed

The DSRM paper reproduces several **baseline attacks for comparison**,
including one derived from **ASB (Agent Security Bench)'s attack
methodology** (direct prompt injection), alongside Naive-Attack,
PoisonedRAG, and a Corpus Poisoning Attack. This means: **ASB's attack
methodology is one of DSRM's reproduced comparison baselines** — it is
not accurate to say "DSRM uses ASB as its evaluation environment," and
this document does not make that claim. This project's own registry
entry for ASB (`resource_id: asb`) remains unchanged; it is a separate,
independently-tracked security-benchmark resource.

## Paper verified ≠ implementation verified

- `RESOURCE_IDENTITY = VERIFIED` — the paper is identified with full
  bibliographic confidence and its mechanism is documented.
- `IMPLEMENTATION_AVAILABILITY` — **no public implementation found.** No
  GitHub repository or downloadable artifact was located under "DSRM" or
  any plausible expansion, in this remediation pass or in the original
  Phase 1 research.
- The registry's `local_path` for `dsrm` remains `None`. No claim is made
  that this project has, has run, or has verified DSRM's original code.

This mirrors how AgentPoison, MINJA, MemoryGraft, FARMA, and MPBench are
already treated in the registry: paper-verified specification, not a
runnable implementation. Per the project's own Methodology (§5.1), an
attack lacking a released downloadable artifact is eligible to be
**reconstructed** later (Phase 4) from its published methodology as a
declarative payload generator — explicitly disclosed as a reconstruction,
never presented as equivalent to an attack with an original public
implementation. No such reconstruction has been performed in this
remediation pass; that is Phase 4 work.

## The paper's reported results are literature evidence, not MAMBench results

The paper reports DSRM achieving, for example, a 43.0% Attack Success
Rate against LLaMA3-70B with a DPR retriever (vs. 36.0% for the
strongest reproduced baseline, PoisonedRAG), evading LLM-based detectors
(false-negative rate up to 80%) and perplexity-based detectors (ROC AUC
0.49). **These are the DSRM paper's own reported numbers, from their own
experimental setup — they are not, and must not be presented as,
MAMBench experimental results.** No DSRM-related experiment has been run
by this project. This document cites those figures only as literature
context establishing why DSRM is a credible, worthwhile attack to
eventually include in the benchmark's attack suite.

## What changed in the repository

- `preprocessing/registry.py`: the `dsrm` `ResourceEntry` was updated
  (identity, status, mechanism documentation, citation, discrepancy
  note) and `data/metadata/resource_registry.json` was regenerated from
  it.
- `data/metadata/phase2_input_manifest.json` was regenerated;
  `dsrm.phase2_status` moved from `UNAVAILABLE` to `INSPECTED`.
  `phase2_input_approved` remains `False` — DSRM is an attack-category
  resource and is not, and should not be, part of the Phase 2.1
  clean-foundation approval regardless of identity resolution (see
  `DATA_BOUNDARY.md`).
- `tests/test_registry.py` and `tests/test_phase2_boundary.py` were
  updated to check the new, resolved status instead of the old
  placeholder status — the underlying fact changed via this authorized
  remediation, so the tests were updated to match it, not weakened.
