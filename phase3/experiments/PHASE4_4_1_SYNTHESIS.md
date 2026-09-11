# Phase 4.1 — Attack Inventory & Source Verification: Synthesis

Status: **4.1 SYNTHESIS — six resources PASS cleanly (original pass);
updated 2026-09-11 to add Sleeper Memory Poisoning as a seventh, additive
resource** (own full dossier:
[PHASE4_4_1_SLEEPER_MEMORY_POISONING_DOSSIER.md](PHASE4_4_1_SLEEPER_MEMORY_POISONING_DOSSIER.md)).
Consolidates the seven per-attack dossiers produced under
[PHASE4_PRE_FLIGHT_DECISIONS.md](PHASE4_PRE_FLIGHT_DECISIONS.md) into the
single registry the handoff's 4.1 PASS criterion requires: *"A complete,
evidence-backed attack source registry exists for all in-scope resources,
with implementation/reconstruction status and provenance explicitly
established."* This document does not replace the seven dossiers — it is
the synthesis; each dossier remains the underlying evidence. Sections
below originally analyzed six resources; each has been extended with
Sleeper's own row/entry rather than rewritten, so the "original pass"
framing in Sections 1–8 is preserved as historical record where it
doesn't change the substance.

## 1. Registry

**Revision note**: DSRM and MPBench were originally drafted from
search-engine fragments (DSRM's primary source was paywalled). The user has
since supplied full PDFs for both — and for the MPBench source paper
specifically — which have now been read in full. Both dossiers are revised
below; confidence for both is substantially upgraded. AgentPoison, FARMA,
and MINJA are unchanged from the original pass.

| Attack | Paper / venue | Provenance status | Repo status | Confidence | Dossier |
|---|---|---|---|---|---|
| **AgentPoison** | NeurIPS 2024, Chen et al. | `REFERENCE_IMPLEMENTATION` | [AI-secure/AgentPoison](https://github.com/AI-secure/AgentPoison), MIT, active (243★) | High | [dossier](PHASE4_4_1_AGENTPOISON_DOSSIER.md) |
| **MINJA** | NeurIPS 2025 poster, Dong et al. — **venue now independently confirmed** via MPBench's own reference list | `REFERENCE_IMPLEMENTATION` | [dsh3n77/MINJA](https://github.com/dsh3n77/MINJA), MIT, active (37★) | High | [dossier](PHASE4_4_1_MINJA_DOSSIER.md) |
| **MemoryGraft** | arXiv 2512.16962, Srivastava & He | `REFERENCE_IMPLEMENTATION` | [Jacobhhy/MemoryGraft](https://github.com/Jacobhhy/MemoryGraft), MIT, active (23★) | Medium — repo verified via API, not code-read | [dossier](PHASE4_4_1_MEMORYGRAFT_DOSSIER.md) |
| **FARMA** | arXiv 2607.05029, Karamchandani et al. | `UNAVAILABLE` → `MAMBench_RECONSTRUCTION` | None found; no code by design (unstated) | High (full text read) | [dossier](PHASE4_4_1_FARMA_DOSSIER.md) |
| **DSRM** | *Eng. Applications of AI* 167:113968 (2026), Jing, Li, Dong, Zhou, Liu (Yunnan University / NUS) | `UNAVAILABLE` → `MAMBench_RECONSTRUCTION` | **No code by explicit authorial policy** ("Data will be made available on request"; authors state they deliberately withhold executable scripts for responsible disclosure) | **High — full text now read; complete pseudocode (Algorithms 1–2) and exact prompt templates (Appendix A) obtained** | [dossier](PHASE4_4_1_DSRM_DOSSIER.md) |
| **MPBench** | Published at AIWILD workshop, ICML 2026 (not arXiv-only as first thought); arXiv 2606.04329, Dash et al. (Huawei Canada / U. Waterloo) | `DATASET/BENCHMARK_RESOURCE` (requires taxonomy reconstruction — no artifact exists) | **Confirmed absent even after full-text read of all appendices** — no dataset/code link anywhere in the paper | **High — full generation methodology, exact JSON schema, and per-class dataset counts now obtained from Appendix D** | [dossier](PHASE4_4_1_MPBENCH_DOSSIER.md) |
| **Sleeper Memory Poisoning** *(added 2026-09-11, seventh resource)* | arXiv 2605.15338 (v2), Pulipaka, Hlebik, Raghav, Abdelnabi, Raina, Sheth, Fritz | `REFERENCE_IMPLEMENTATION` (real code, license ambiguous — see dossier Section 2) | [ivaxi0s/LLM-agent-memory-poisoning](https://github.com/ivaxi0s/LLM-agent-memory-poisoning), no declared license, commit `70de017714abd6d12bb4681e93437461ba6f9a19` | High (paper full text + real repo file tree + 7 attack-payload source files + 3 attack/critic/goal-optimization prompt files all read directly) | [dossier](PHASE4_4_1_SLEEPER_MEMORY_POISONING_DOSSIER.md) |

## 2. Attacker Capability Spectrum

The seven resources span a genuinely wide range of attacker access
assumptions, not seven variations on one theme — this is direct evidence
against collapsing them into one execution mechanism (per the handoff's 4.2
instruction):

| Attack | Minimum required access |
|---|---|
| AgentPoison | White-box gradient access to the retrieval embedder |
| FARMA | Direct write access to the memory store |
| MemoryGraft | Indirect — supplies ingestion-level content the agent chooses to persist |
| DSRM | Injection into the knowledge base (exact access model unconfirmed — paywalled) |
| MINJA | **Query-only** — ordinary user-facing interaction, no privileged access at all |
| MPBench | Not an attack itself; its six attack classes span multiple of the above channels |
| Sleeper Memory Poisoning | **Black-box, external-content only** — no model weights, no system-prompt access, no direct memory read/write, no retrieval-logic access; the attacker controls only a document/webpage/email the user later has the assistant process (dossier Section 3) |

MINJA and Sleeper Memory Poisoning are the two lowest-privilege, most
realistic threat models of the group — genuinely distinct from each other
despite both being query/content-only: MINJA's attacker interacts directly
with the agent as an ordinary user; Sleeper's attacker never interacts
with the agent at all, only with content the real user independently
brings to it. AgentPoison remains the highest-privilege. Any common attack
contract (4.2) must represent this spread explicitly (an
`attacker_capability`/`attacker_knowledge` field, not a fixed assumption).

## 3. Target Surface Spread

| Attack | Primary surfaces targeted |
|---|---|
| AgentPoison | Retrieval (embedding space), memory content |
| FARMA | Memory content, memory admission, propagation |
| MemoryGraft | Memory admission, memory content, retrieval, cross-session propagation |
| DSRM | Memory content, reasoning/evidence interpretation (provisional) |
| MINJA | Memory admission (via agent self-writing), retrieval |
| MPBench taxonomy | All of the above, spread across its 6 attack classes / 4 write channels |
| Sleeper Memory Poisoning | Memory admission (gated, per its own real injection judgment), retrieval, **and dormancy/trigger-state as a first-class, directly measured lifecycle dimension** — the one genuinely new target surface this seventh resource adds (dossier Section 6; see also `PHASE4_4_8_SLEEPER_MEMORY_POISONING_CAMPAIGN.md`) |

No single attack in the original six-resource inventory targeted
provenance or lifecycle directly — those remained MAMBench-side
measurement concerns (4.6, 4.9), not attack targets, consistent with the
handoff's framing. **Sleeper Memory Poisoning changes this**: its own
real campaign is the first in this project to treat dormancy/activation
as something the attack's own design and evaluation protocol directly
targets, not merely something MAMBench's infrastructure happens to be
able to measure after the fact.

## 4. Real Cross-Resource Overlaps Found

- **EHRAgent-family targets**: AgentPoison, FARMA, and MINJA all evaluate
  against an EHRAgent-style medical agent in their original papers.
- **RAP-family shopping-agent targets**: FARMA and MINJA both evaluate
  against a RAP-style agent.
- **Author overlap**: Zhen Xiang co-authors both AgentPoison and MINJA — the
  two strongest-provenance (`REFERENCE_IMPLEMENTATION`) resources in this
  inventory.
- **Taxonomy overlap**: MPBench's "False Precedent Insertion" class
  conceptually echoes FARMA's forged-reasoning-trace mechanism; MPBench's
  "Skill-Procedure Insertion" class echoes MemoryGraft's
  semantic-imitation/procedure mechanism; DSRM's "disguised as past
  experience" framing sits conceptually between FARMA and MemoryGraft.

None of these overlaps is confirmed to mean shared MAMBench implementation
work — they are flagged as **cross-check opportunities for 4.10 cross-attack
validation**, not shortcuts to take in 4.2/4.3/4.4 without separate
validation per attack.

## 5. Domain Mismatch — a constraint on every resource, not just one

Every one of the six resources was evaluated in its original form against a
task domain that is not LoCoMo-style conversational memory QA:
autonomous-driving planning and StrategyQA/EHR (AgentPoison), EHR/ReAct-QA/RAP
(FARMA), RAP/EHR/QA-agent (MINJA), MetaGPT DataInterpreter code/data analysis
(MemoryGraft), an unconfirmed domain (DSRM), and file/web/email/calendar/
Slack/script/skill-invocation tasks via OpenClaw/HERMES (MPBench). This is
the single most consistent adaptation burden across the whole inventory —
4.2's contract and 4.3/4.4/4.5's per-attack work should treat "translate to
LoCoMo-style conversational memory" as a shared, first-class design problem,
not an incidental detail solved once per attack.

## 6. What Blocks a Clean 4.1 PASS (revised — both prior exceptions now closed)

The handoff's 4.1 PASS criterion is *"a complete, evidence-backed attack
source registry... with implementation/reconstruction status and provenance
explicitly established."*

The original pass of this synthesis flagged two disclosed exceptions:
DSRM's paywall-blocked evidence base, and MPBench's unlocatable artifact.
Both have since been substantially resolved by the user supplying primary
sources directly:

1. **DSRM — resolved.** Full text now read (`Engineering applications of
   AI.pdf`). The paper turns out to publish complete pseudocode
   (black-box and white-box algorithms), exact prompt templates, and an
   exact loss function — a stronger reconstruction basis than most of the
   other five resources. The "no code" finding is now confirmed as
   **deliberate authorial policy** (explicit responsible-disclosure
   statement), not an unfound repository. Confidence upgraded from Low to
   High.
2. **MPBench — resolved to the extent an artifact can be resolved.** Full
   text now read (`From Untrusted Input to Trusted Memory...pdf`),
   including all four appendices. No dataset/code link exists anywhere in
   the paper — this is now a high-confidence negative finding (a full read
   found nothing, not a failed search). What *did* resolve is the
   reconstruction basis: the full generation methodology (template inputs,
   generator model, exact JSON schema, per-class counts) is documented in
   Appendix D, making a MAMBench-native reconstruction methodologically
   faithful rather than a loose approximation. 4.5 still needs to be scoped
   as reconstruction rather than mapping (this correction stands), but
   confidence in that reconstruction is now High, not Medium.

**Revised recommendation**: 4.1 now **PASSES cleanly** for all six
original resources — every attack has an evidence-backed provenance
classification built from primary-source material (five of six from
full-text reads; only MemoryGraft's dossier rests on repo-metadata-plus-
abstract rather than a full code or paper read, and is flagged accordingly,
Medium confidence). No resource requires blocking further work pending
additional access.

**Seventh resource, added 2026-09-11**: Sleeper Memory Poisoning's own
dossier is built from a full-text paper read plus a real repository read
(file tree, 7 attack-payload source files, 3 attack/critic/goal-
optimization prompt files) — High confidence, the same standard as
AgentPoison, MINJA, and MemoryGraft's target standard, actually exceeding
MemoryGraft's own confidence level (Sleeper's dossier reads real code
directly; MemoryGraft's dossier, per the note above, does not). 4.1 PASSES
cleanly for all seven resources now in scope.

## 7. Implications for 4.2 (Common Attack Contract) — preview only, not designed here

Based on Sections 2–5, the contract will need, at minimum:
- An explicit `attacker_capability`/`attacker_knowledge` field wide enough to
  span white-box-embedder-gradient through query-only interaction.
- A `target_surface` field (or set) distinguishing retrieval, memory
  admission, memory content, propagation, and reasoning/evidence
  interpretation, since attacks in this inventory concentrate on different
  combinations.
- A domain/task-translation layer as a shared, reusable contract concern
  (Section 5), not bespoke per attack.
- Support for `implementation_type` values actually observed here:
  `REFERENCE_IMPLEMENTATION` (3), `MAMBench_RECONSTRUCTION` (2, one
  low-confidence), `DATASET/BENCHMARK_RESOURCE` (1, itself requiring partial
  reconstruction).

Full 4.2 design is a separate stage; this section only records what 4.1's
evidence implies it must accommodate.

## 8. Recommended Immediate Next Steps (revised)

1. ~~Attempt to resolve DSRM's source-access blocker~~ — **done**, full text
   obtained and dossier revised.
2. ~~Re-check for an unindexed MPBench artifact~~ — **done**, full appendix
   read confirms none exists.
3. Proceed to 4.2 common attack contract design using Sections 2, 3, and 7
   above as the evidentiary basis, per your earlier decision to complete all
   six dossiers before shaping the contract. This is now unblocked with no
   outstanding source-access gaps among the six in-scope resources.
4. (Optional, out of scope) Consider whether MemoryGraft's dossier merits a
   full-text read as well, since it is currently the only
   `REFERENCE_IMPLEMENTATION`-classified resource resting on repo-metadata
   rather than a direct paper or code read (Section 1).

## 9. Adjacent Finding — Out of Scope, Flagged for Awareness

While reading the MPBench full text, its own reference list surfaced a
distinct attack not in this inventory: **MEXTRA (Memory EXTRaction
Attack)**, Wang et al. 2025, arXiv:2502.13172, "Unveiling privacy risks in
LLM agent memory" — an extraction rather than poisoning attack (it exfiltrates
prior users' stored interactions from long-term memory rather than injecting
false content). A third paper the user supplied
(`Egyption informatics journal.pdf` — Dhivyasree et al., *Egyptian
Informatics Journal* 34:100983, 2026, "CAMS") is a **defense** framework
evaluated against both MINJA and MEXTRA on a MIMIC-III-backed EHR agent,
reporting real ASR-reduction figures (92.3% end-to-end prevention) and
publishing its own MINJA/MEXTRA synthetic corpus generation methodology.

Neither MEXTRA nor CAMS is in Phase 4's six in-scope resources, and this
synthesis does not recommend adding them without your explicit decision —
noted per the handoff's instruction not to silently expand scope. If Phase 4
later wants an extraction-attack class alongside its six poisoning attacks,
or wants a real, published defense baseline to test MAMBench's own attacks
against, both are flagged here as concrete, evidence-backed candidates
rather than left undiscovered.
