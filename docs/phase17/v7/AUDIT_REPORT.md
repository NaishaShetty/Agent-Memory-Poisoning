# Defence v7: Read-only Audit (Workstream 0)

**Date:** 2026-10-15. **Scope:** Gaps 1, 2 and 3 (Gap 3 per the v7 Gap-3 brief; Gaps 1 and 2 share the programme).
Nothing in the repository was modified during this audit. Development-only diagnostics written while auditing are listed in §7.

**Sources read:** `FINAL_DEFENCE_BASELINE_AUDIT.md` §3 (frozen rubric), `docs/phase17/PREREGISTRATION_DEFENCE_V6_2026-10-14.md`
(+ addendum A), `DEFENCE_V6_*.md`, `phase17/defence_v6/{g1_eval,g2_eval,g3_eval,ledger,mem0_sa6,sa6_corpus,ho9_*}.py`,
`phase17/defence_v3/{sleeper_v3,vpl,ctc}.py`, `phase17/defence_v2/sleeper_v2.py`, `phase17/defence_v4/{voa,prc}.py`,
`results/TABLE_INDEX.md`, `REMEDIATION_MASTER_REGISTER.md`, both deliverable documents.

**Missing artifact:** the brief names `Methodology Draft(8).docx`. No such file exists; the authoritative methodology is
`Methodology Draft.docx` (repository root), generated from the same sources as the Results Analysis. That file was used.

## 1. Gap 3: current implementation

| Component | Current implementation | Evidence | Known limitation |
|---|---|---|---|
| **K** (content detector) | `N1 ∧ INTENT_v1`, selected once on SA-6 dev raw notes (`g3_selection.json`), labelled FAILING (no candidate met the dev limits on raw text). N1 = a steering verb (`_STEER` regex) **and** a capitalised entity absent from the owner's conversation text (`sleeper_v3.n1`); INTENT_v1 = llama3.1:8b, temp 0, seed 17, "does the rule mainly benefit a party other than the user …? YES/NO" | Dev 28/32 implicit, 13/96 ungrounded | N1 treats "name appears in the conversation" as familiarity (the brief forbids inferring a relationship from name presence); INTENT_v1 is already a beneficiary judge |
| **C** | channel ∈ {document, missing} (application-recorded, unauthenticated) | Eval 48/48, 85/144 ungrounded | Flags every untrusted legitimate rule |
| **C∧K** | C ∧ K(any stored Mem0 memory of the item) | Eval 34/48, 8/144 (5.6%), grounded 0/48 | Exploratory on SA-6 eval (not the dev-selected point) |
| **D** (v6 frozen operating point) | C ∧ K(original source record, by ledger event id) | Eval 38/48, 16/144 (11.1%), grounded 0/48 → fails 3.3 | Dev 8/96 = 8.3% left no margin to the 10% limit |
| **E** | C ∧ K(record linked by semantics, no event id): each stored memory is linked to the most similar record in the owner's registry of ingested source records if sem ≥ 0.490; if no link, K(stored) | Eval 38/48, 11/144 (7.6%), explicit 41/48 | Tied with D on dev and lost the frozen tie-break; in v6 the registry was **all eval notes of the owner** (every item's own note is in it), so E's links can land on a different note of the same owner; part of E's lower false-positive rate may come from mis-links (to be measured, §5) |
| **F** | C ∧ ACT(trigger, stored) ∧ ¬ACT(trigger, clean): compliance judge C0 (llama3.1) on the agent's answer to the trigger message, with vs without the memory | Eval 23/48, 6/144 (4.2% ungrounded flagged) | Two of the four counterfactual cells only (trigger absent cells exist for dormancy but are not used in F); coverage limited by retrieval (6/48 not retrieved) and activation |
| **S** | SIMULATION: principal ≠ owner | 48/48, 46/144 | Never credited; missing-provenance stratum has no principal |
| **TS** (accepted, 3.4) | Retrieval-time: for an untrusted memory whose source record is conditional, show the original rule with the F2 frame ("unverified … ask the user before acting") | Implicit unconfirmed activation 19 → 4/48 (Holm p = 8.2e-4) | Behaviour measured with LLM judges; no real users |
| Where evaluated | K on raw notes at write time; B/C∧K on stored memories (storage); D/E at storage via the ledger/registry; F at action time (agent answer); TS at retrieval | — | — |
| Counting | Item-level: an item is "flagged" if the rule flags it (any stored memory for B/C∧K/E). Detection = flagged attacks / attacks of that kind; ungrounded flag rate = flagged `ben_unground`+`ben_future`+`ben_unusual` / all of them (pooled over channels); grounded = `ben_ground` | `g3_eval._limits` | 144 ungrounded items: one item = 0.69 points |
| Activation | `voa`: agent = `H.AGENT_MODEL`; ACT = C0 compliance judge on the memory's prescribed action; ASK = llama3.1 "asks the user to confirm"; unconfirmed activation = ACT ∧ ¬ASK ∧ ¬ACT(clean) | `g3_eval._beh` | Judges are LLMs (C0 κ = 0.596 vs humans) |
| FP / FN | FP = legitimate rule flagged; FN = attack not flagged; no "uncertain" class exists in v6 | — | Uncertain outcomes are not represented |
| Rubric | 3.2 (0.30) and 3.3 (0.25) scored **jointly at one operating point**; v6 pre-registration capped each at **0.5** because detection rests on unauthenticated channel labels and a pre-registered channel mix; 0.75 needs the limits in the all-document stratum too | `closure_v6.json` | Max achievable on 3.2/3.3 under that rule without the all-document stratum: 0.5 each |

**Attack channels.** SA-6 attacks arrive only on the document or missing channel (the threat model is content
injection). There is no user-originated attack in any SA set. A user who relays (pastes) attacker text on the user channel
is outside every provenance-based method; it has never been measured.

**High-impact actions.** SA-6 generation **dropped** attacks mentioning money, payment, sharing or sending
(`explicit_harm`, 28 dropped). No SA set contains high-impact actions; workstream 4 needs new data.

**Documents.** SA-6 "document" items are single notes delivered as "the shared note says: …"; MSD documents are three
unrelated notes concatenated. There is **no coherent source document** in which a rule sits among related content, so
document-context consistency (workstream 2) cannot be measured on existing data.

## 2. Gap 1: current implementation

| Component | Current implementation | Evidence | Known limitation |
|---|---|---|---|
| PL ledger | Append-only JSONL per store; events (channel, unverified principal, sha256, original text, parsed conditional) and links (memory id, ADD/UPDATE, event id, digest) | 622/622 channel correct; forced UPDATE: native relabelled 183/183, ledger kept 183/183 | Application-recorded, not authenticated |
| FLV | Link valid only if event exists, payload sev/channel agree, digest or sem ≥ 0.490 continuity, sem(memory, event claim) ≥ 0.490 | Wrong-link acceptance 0/265; all 5 corruptions ≤ 0 points | — |
| CLP | Claim (sentence) of a memory → best source claim (sem ≥ 0.490, margin δ = 0); inherits **B12 of the raw source claim** | Explicit 44/48 vs B13s 16/48 | Inherits B12's false positives on unusual harmless rules |
| PAB13 | B13 only for memories with a document/missing source | Ungrounded 35 → 17/144 | Corroboration flags legitimate untrusted rules (the Gap-3 root cause) |
| PCL | PAB13 ∨ CLP | 1.1 fails on MSD (+16 pts benign); 1.3 fails (24.3% / 6.25%) | — |
| Decision | Binary: exclude or keep | — | No intermediate action for weak evidence |

**Development diagnosis (SA-6 dev only, §7):** Mem0 stores 214/218 note memories and 172/174 MSD benign memories as a
**single claim**, so claim-level redaction has nothing to act on. The MSD benign cost is entirely **correct** links to
benign source notes that B12 flags (ben_unusual 13, ben_future 2), not mis-links. On notes, CLP inheritance also flags 6
user-channel legitimate items (attacks never arrive on the user channel in this threat model).

## 3. Gap 2: current implementation

| Component | Current implementation | Evidence | Known limitation |
|---|---|---|---|
| FG | Frozen guard, bounded decay 0.5^(dist−1) | HO9 gen 4: 18/73 | Decay is a root cause |
| ND | FG without decay | 41/73, non-carrying 14.7% | Not pre-registered as a candidate in v6 |
| PRC | Instruction roots → CTC (NLI S1 ≥ τ_ctc), factual → RCL (sem ≥ 0.5) | 43/73 = 58.9% (< 60%), non-carrying 29.4% (> 25%) | Misses C1 by one root, breaches C5 |
| RAR-B | Root-anchored, HFP-B (bidirectional NLI on the whole root) | 15/73 | Whole-root entailment fails on 4-memory consolidations |
| Recovery | C1 exact digest log 296/296; C2 (simulated rewrite) 76% owner false association | — | Summaries contain the owner's own text |
| Owners used for propagation | HO4 = 7, HO7 = 8, HO8 = 1, HO9 = 2, 3, 5, 9 | — | **Owners 0, 4, 6 have never been used for propagation** |

## 4. Rubric (frozen; unchanged by v7)

`FINAL_DEFENCE_BASELINE_AUDIT.md` §3: weights, critical flags and caps as published. v6 per-capability scores are the
starting point: Gap 1 = 63.8%, Gap 2 = 65.0%, Gap 3 = 33.8% (`closure_v6.json`). v6 scoring conventions are carried
unchanged (notably the 0.5 cap on 3.2/3.3 and its all-document condition for 0.75).

## 5. Data used so far, and whether SA-7 / HO10 can be held out

| Set | Use | Owners | Status in v7 |
|---|---|---|---|
| SA-1 … SA-5 | dev / held-out in v2–v5 | various | spent; near-duplicate blocking only |
| SA-6 dev | v6 selection | 0, 2, 4, 6 | v7 development |
| SA-6 eval, MSD eval | v6 confirmation | 1, 3, 5, 7, 8, 9 | **spent**; exploratory only (E and C∧K were observed there) |
| HO4, HO7, HO8, HO9 | propagation | 7; 8; 1; 2, 3, 5, 9 | spent; HO9 = v7 Gap-2 development |
| FPB | fingerprints | — | spent |

**Owner pool.** LoCoMo has 10 owners and SA-6 used all of them. SA-7 can be **item-disjoint** (new Gemini generations
with new seeds, near-duplicate blocked against SA-1…SA-6 and across splits) and **owner-disjoint between its own dev and
eval splits** (same split as SA-6: dev 0, 2, 4, 6; eval 1, 3, 5, 7, 8, 9), so no SA-7 eval owner contributes to any v7
selection. It cannot be owner-disjoint from SA-6 eval. Because E, C∧K and K contain no owner-specific parameter and all
v7 selection uses dev owners only, SA-7 is a credible held-out set **for items**, with the owner overlap stated as a
limitation. HO10 can be fully owner-disjoint from all earlier propagation sets (owners 0, 4, 6).

**Generator.** Same author model (gemini-3.5-flash-lite) and SA-6 template and gates, so SA-7 tests generalisation to new
items from the same generator, not to a new generator. Stated limitation.

## 6. Implementation points for the proposed changes

| Change | Where | Evaluated how |
|---|---|---|
| Gap 3: E as primary, C∧K secondary, D baseline | reuse `g3_eval._conditions` unchanged (imported, not copied) | SA-7 eval, once |
| Gap 3: document consistency (DC) | new `phase17/defence_v7/signals.py`; needs new coherent documents (CSD) | CSD dev pilot → eval |
| Gap 3: beneficiary familiarity | audit N1/INTENT_v1 (exist); new relationship-evidence variant only on first-person owner statements | SA-7 dev pilot, by channel |
| Gap 3: high-impact gate | new action-time policy; needs high-impact kinds in SA-7 | behavioural, SA-7 eval |
| Gap 3: F second stage | reuse v6 F definition; 4-cell counterfactual added as a versioned variant | SA-7 eval flagged subset |
| Gap 1: graded provenance | new decision function beside `g1_eval.arms_for` (imported) | SA-7 eval + MSD-7 eval |
| Gap 2: sentence-level fingerprint, ND unions | new arms beside `g2_eval.block` | HO9 (dev) → HO10 (held-out) |

## 7. Development diagnostics written during the audit (disclosed)

- `phase17/data/defence_v7/` scratch outputs were not written; the two Gap-1 diagnostics ran from the session scratchpad
  on **SA-6 dev rows only** (an assertion checked that every row's owner ∈ {0, 2, 4, 6}). They read the v6 decision cache
  and added **no** new entries to it (a backup was taken first; verified unchanged in REPRODUCIBILITY.md).
- `phase17/defence_v7/g2_dev.py`: HO9 (v6 held-out, now spent) as Gap-2 development substrate; writes only to
  `phase17/data/defence_v7/`.
