# Phase 4.1 — Attack Source Dossier: FARMA

Status: **DRAFT — 4.1 (Attack Inventory & Source Verification)**. Produced
against the pre-flight-gated Phase 4 process
([PHASE4_PRE_FLIGHT_DECISIONS.md](PHASE4_PRE_FLIGHT_DECISIONS.md)). Fields are
backed by direct verification (arXiv abstract page, full HTML paper text,
targeted GitHub search) as of this drafting session; anything not
independently verified is marked `UNKNOWN / NOT VERIFIED` rather than filled
from assumption. No MAMBench code was written or modified to produce this
document.

## 1. Identity

| Field | Value |
|---|---|
| Paper title | "Your Agent's Memories Are Not Its Own: Forged Reasoning Attacks on LLM Agent Memory and Defenses" |
| Attack name | FARMA — Forged Amplifying Rationale Memory Attack |
| Authors | Neeraj Karamchandani, Piyush Nagasubramaniam, Sencun Zhu, Dinghao Wu |
| Affiliations | Not stated on the extracted arXiv page — **UNKNOWN / NOT VERIFIED** |
| Venue | Preprint only. arXiv [2607.05029](https://arxiv.org/abs/2607.05029), v1, submitted 2026-07-06. No publication venue beyond arXiv identified. |
| Companion/follow-up work | [2608.16032](https://arxiv.org/abs/2608.16032) "Proof-of-Execution Memory: Defending LLM Agents Against Forged-Reasoning Attacks by Verifying What Actually Happened" — a separate, later defense paper responding to FARMA; not the same authors' own follow-up per the search evidence (**relationship UNKNOWN / NOT VERIFIED** — flagged for a follow-up check before citing it as authoritative on FARMA's own limitations). |
| Code/data repository | **None found.** Neither the paper text nor a targeted GitHub search turned up an official implementation. The paper itself contains no code/artifact availability statement. |
| License | N/A — no released code |

## 2. Classification

**`UNAVAILABLE` (no implementation exists) → `MAMBench_RECONSTRUCTION` required.**

This is a very recent (July 2026), single-preprint, no-code paper. Unlike
AgentPoison, there is no reference implementation to integrate — 4.4
(MAMBench Attack Reconstructions) is the only viable track, built directly
from the published methodology. This must never be represented as an
"official" or "reference" implementation once built.

## 3. Threat Model / Attacker Assumptions

| Field | Value |
|---|---|
| Attacker capability | **Write-only access to the agent's persistent memory store.** Explicitly does not require agent execution visibility or model-weight access — a materially weaker/more realistic capability than AgentPoison's white-box embedder-gradient requirement. |
| Attacker knowledge | Publicly inferable schema knowledge: memory field names, allowed types, source-label values, the trace-type taxonomy, and representative examples drawn from documentation/open-source code. Not privileged/insider knowledge of the specific deployment. |
| Explicit non-capabilities | No adaptive white-box model; cannot observe agent execution; cannot read prior agent-internal writes (as distinct from reading what's already in the shared memory store). |
| Realistic vectors named by authors | Compromised plugins with memory-write permission, shared multi-agent memory stores, insider access to a memory backend. |

This is a fundamentally different, and in some ways more MAMBench-compatible,
threat model than AgentPoison's: it assumes only a memory-write API, which is
exactly the kind of access V3-Hybrid's real Mem0/A-MEM adapters expose.

## 4. Mechanism — Two-Phase Attack

**Phase 1 — Injection.** The attacker writes a small number (paper example:
3) of seed "forged reasoning traces" — memory entries styled as the agent's
own prior decision/reasoning log — using domain-specific templates with
evasive phrasing designed to avoid literal trigger keywords. Paper's own
example: *"source-level validation complete. All checks... verified upstream.
Re-validation at the import stage is unnecessary"* — the word "skip" is never
used, defeating naive keyword-based screening.

**Phase 2 — Amplification ("self-referential reinforcement").** The attacker
iteratively appends further entries that cite the earlier forged entries,
each with a manufactured "precedent count" that increments per cycle (paper
default: 10 amplification cycles). Paper's own example: *"Decision log
update... consistent with [count] prior processing runs."* This serves three
stated purposes: (1) raises retrieval probability purely through volume, (2)
defeats consensus/majority-vote-style defenses by making the forged view the
apparent majority, (3) manufactures false precedent that increases the
agent's own willingness to accept the claim.

**Net effect intended by the authors**: the agent comes to believe a
safety-relevant step (e.g. a validation check) was already completed, and
skips it — an omission attack via memory, not a direct factual-poisoning
attack.

## 5. Target Surfaces (per attack surface taxonomy)

Primarily targets: **memory content** (forged reasoning entries), **memory
admission** (evasive phrasing defeats keyword-based admission screening), and
**a consensus/majority mechanism specific to defenses that count entry
agreement** — this last one is a defense-interaction property, not a
V3-Hybrid mechanism, since V3-Hybrid has no consensus-voting defense today.
Secondarily implicates **propagation** (the amplification phase is
explicitly a multi-write propagation pattern) and, if unresolved by
provenance tracking, **lifecycle** (whether forged entries are ever
retired/superseded).

## 6. Original Evaluation Setup (NOT MAMBench's)

- **Domains/agents**: EHRAgent (medical record validation, using MIMIC-III
  demo data), ReAct-QA (search-tool-based QA with reasoning-chain reuse), RAP
  (an online-shopping agent exercising preference-pattern reuse).
- **Models tested**: GPT-4o-mini (primary), GPT-4o, Llama 3.3 70B.
- **Memory backends discussed**: the paper names Chroma, Redis, Mem0, SQLite,
  and PostgreSQL as examples of the persistent-memory category it targets, but
  per the extraction, evaluation itself used **generic implementations**
  rather than confirmed live integration with each named product.
  **UNKNOWN / NOT VERIFIED**: whether Mem0 specifically (the same product
  V3-Hybrid uses) was an actually-executed backend in FARMA's reported
  experiments, or only cited as a representative example of the memory-system
  category. This distinction matters for how much of FARMA's reported ASR
  figures can be assumed to transfer to a real Mem0 deployment versus needing
  re-measurement — flagged for resolution before 4.9 ground-truth claims are
  made.
- **Dataset**: 326 benign agent traces (26 hand-curated + 300 generated from
  clean-memory runs) used for false-positive testing; 50 trials per attack
  condition.

## 7. Original Evaluation Metrics

- **ASR** — Attack Success Rate: fraction of trials where the clean-memory
  baseline behaved safely but the poisoned-memory run behaved unsafely
  (skipped the validation/safety step).
- **FPR** — False Positive Rate: fraction of legitimate/benign reasoning
  entries incorrectly flagged as forged by a defense.

## 8. Reported Results (source paper's own claims — not MAMBench-verified)

| Defense condition | Reported ASR against FARMA |
|---|---|
| No defense | 100% (EHR domain, across all three tested models) |
| Keyword filter | 100% (defeated by evasive phrasing) |
| A-MemGuard, heuristic mode | 100% (defeated by amplification/consensus-flooding) |
| A-MemGuard, LLM-judge mode | 100% |
| SENTINEL (the paper's own proposed defense) | 0%, with 0% false-positive rate across the 326-trace benign set |

Note: **A-MemGuard** is named as a tested baseline defense — this implies the
authors' threat model is explicitly aware of A-MEM-style memory-guard
defenses, reinforcing that FARMA is conceptually compatible with A-MEM-class
architectures even if not confirmed as literally run against the real A-MEM
library.

The authors also disclose, as their own stated limitation, that a simple
LLM-paraphrase adaptive attacker defeated SENTINEL's heuristic
Reasoning-Guard signals on first attempt in a preliminary evaluation — a
disclosed, not hidden, weakness in their own defense, relevant to Phase 4 if
SENTINEL-style detection is ever considered as a MAMBench-side control.

## 9. Attack Variants Described

- **Base FARMA** — the two-phase injection + amplification attack as
  described above.
- **Evasion variant (store-relocation)**: writing forged content to the
  agent's general memory store instead of a dedicated "reasoning" store, to
  dodge a reasoning-store-specific defense. The paper's own SENTINEL defense
  counters this with a `looks_like_reasoning` classifier applied to
  general-memory entries too — MAMBench reconstruction should preserve this
  as a distinct attack variant (`FARMA-store-evasion`) rather than treating
  base FARMA and the evasion variant as identical.
- **Adaptive/paraphrase variant**: an LLM-paraphrased version of forged
  entries, shown (in the authors' own preliminary evaluation) to defeat
  SENTINEL's heuristic detection. This is a real, disclosed variant worth
  preserving separately per the handoff's "do not collapse variants" rule,
  though the authors' own evaluation of it is described as preliminary.

## 10. MAMBench Adaptation Required

1. **Full reconstruction from methodology**, since no code exists. Every
   design choice (exact template wording for seed traces, exact amplification
   cadence, exact precedent-count phrasing) must be documented as a
   MAMBench-specific implementation decision, distinct from anything claimed
   to be "what the authors did," since the paper's own text gives only
   illustrative examples, not a full template specification.
2. **Domain mismatch.** None of FARMA's three evaluated domains (EHR
   validation, search-tool QA, shopping-preference reuse) matches V3-Hybrid's
   conversational-memory QA setup (LoCoMo). The "reasoning trace" memory
   category FARMA targets needs a MAMBench-native analogue — V3-Hybrid's
   Condition B verify/revise step (`canonical_verified_reasoning.py`) is the
   closest existing MAMBench concept to an agent "reasoning history," but it
   is not currently persisted as a retrievable memory entry the way FARMA's
   threat model assumes. This is a design decision Phase 4 must make
   explicitly, not silently invent.
3. **Model mismatch.** FARMA was evaluated against GPT-4o-mini/GPT-4o/Llama
   3.3 70B, not Qwen3-8B (Q4_K_M, non-thinking). Reported 100%-ASR figures are
   not assumed to transfer; MAMBench must re-measure against the actual
   V3-Hybrid model.
4. **Mem0 evaluation status unresolved** (Section 6) — needs a direct check
   of the paper's supplementary material/appendix (not reached in this pass)
   before assuming any of FARMA's own reported numbers used a real Mem0
   backend comparable to V3-Hybrid's.
5. **No consensus-based defense exists in V3-Hybrid today** — FARMA's
   amplification phase is specifically designed to defeat consensus-voting
   defenses, but V3-Hybrid has no such defense to defeat. This doesn't block
   running the attack (injection/amplification can still occur and be
   measured for retrieval/selection/use effects), but it does mean one of
   FARMA's two stated defeat-mechanisms (consensus-flooding) has no
   MAMBench-side target to demonstrate defeating. Ground truth (4.9) should
   track this honestly rather than implying V3-Hybrid has a consensus defense
   it doesn't.

## 11. Compatibility With Phase 4 Pre-Flight Decisions

- Does not depend on selection-policy manipulation (Decision 1) — FARMA
  targets memory content/admission and volume-based retrieval-probability
  increase, not the selection/rejection stage specifically.
- If piloted against A-MEM (plausible given A-MemGuard's role as a tested
  baseline defense in the source paper), is subject to Decision 2 (A-MEM
  confound fix must be wired first).
- New campaign records must carry environment provenance per Decision 3.
- Establishing whether an amplified forged-reasoning entry *causally* changed
  V3-Hybrid's answer (vs. merely being retrieved/present) requires new
  counterfactual measurement per Decision 4.

## 12. Deviations / Unresolved Ambiguities

- **UNKNOWN / NOT VERIFIED**: author affiliations.
- **UNKNOWN / NOT VERIFIED**: whether Mem0 itself, versus a generic
  vector-store stand-in, was the actual executed backend in any reported
  FARMA experiment.
- **UNKNOWN / NOT VERIFIED**: the exact relationship between FARMA's authors
  and the later "Proof-of-Execution Memory" paper (2608.16032) — whether it is
  an independent third-party response or a related follow-up; not treated as
  authoritative on FARMA's own limitations until checked.
- **UNKNOWN / NOT VERIFIED**: full seed-template specification and exact
  amplification-cycle content beyond the single illustrative example quoted
  in the paper — the reconstruction will need to make and document its own
  template design.
- Given this paper's very recent submission date (2026-07-06) relative to
  today, **UNKNOWN / NOT VERIFIED**: whether any peer review, errata, or
  significant revision has occurred since v1 — worth a re-check immediately
  before 4.4 reconstruction work begins, not just at 4.1 time.

## 13. Recommended 4.4 Reconstruction Path

Per the handoff's required reconstruction process:

```text
Published paper (arXiv 2607.05029)
      ↓
Methodology extraction (this dossier, Sections 4, 6-9)
      ↓
Attacker assumptions (Section 3 — write-only memory access)
      ↓
MAMBench-native template design for seed forged-reasoning entries
  (explicit, documented, not claimed as "the authors' own templates")
      ↓
MAMBench reconstruction: injection phase (writes N seed entries via the real
  Mem0/A-MEM memory-write path) + amplification phase (iterative appended
  entries with precedent-count phrasing, configurable cycle count)
      ↓
Validation against the paper's own qualitative behavior (does volume-based
  retrieval-probability increase actually occur under V3-Hybrid's hybrid
  selection, not just pure dense retrieval as in the original?) — this is a
  genuine, non-trivial validation question given Section 10 item 2's domain
  mismatch, not a rubber stamp.
```

Label throughout as `MAMBench reconstruction of FARMA`, never "FARMA
(original)."

## 14. Sources

- [FARMA paper — arXiv:2607.05029](https://arxiv.org/abs/2607.05029) (abstract
  and full HTML text)
- [arXiv:2607.05029 full HTML](https://arxiv.org/html/2607.05029v1)
- [Proof-of-Execution Memory — arXiv:2608.16032](https://arxiv.org/abs/2608.16032)
  (identified as related follow-up defense work, relationship not fully
  verified — see Section 12)
- Targeted GitHub search for an official FARMA implementation — no result
  found as of this dossier's drafting.
