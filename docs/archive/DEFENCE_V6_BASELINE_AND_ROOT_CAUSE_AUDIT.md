# Defence v6: Baseline and Root-Cause Audit (Phase 0)

**Date:** 2026-10-14. This audit was recorded **before any v6 code change**.

## 0. Repository state

| Item | Value |
|---|---|
| Branch | `remediation/2026-10-12` |
| HEAD | `2d0e8327` (documents updated after v5). v5's last experiment commit is `d04ef0a9`; v5 completed at `10feeaaa` |
| Uncommitted files (pre-existing; never touched) | `phase17/data/run_all_logs/{ollama_1012.log (M), audit_floorfix.log (??), audit_refs.log (??)}` |
| Versioning for v6 | Code `phase17/defence_v6/`; data `phase17/data/defence_v6/`; tables T27+. Earlier programmes, pre-registrations, results and judge caches stay untouched (caches change only by addition) |

## 1. Frozen rubric (verified)

The rubric is `FINAL_DEFENCE_BASELINE_AUDIT.md` §3. Its weights and critical flags match `phase17/figures_final.py: CLOSURE`.

**Caps:**
- if any critical capability scores 0, the gap is capped at 0.50;
- if any critical capability scores ≤ 0.25, the gap is capped at 0.60.

**Current scores:**

| Gap | Score |
|---|---|
| Gap 1 | **58.8%** |
| Gap 2 | **65.0%** |
| Gap 3 | **28.7%** (capped at 50%; not binding) |

Recomputed by `closure_scores()`.

## 2. Mem0 interfaces (inspected, 2.0.19)

| Interface | What it records | Relevance |
|---|---|---|
| `add(messages, metadata=…)` | Metadata on each ADDed memory payload | Application-level provenance. **Not authenticated**: any caller can set any value |
| `_update_memory` | `new_metadata = deepcopy(old); new_metadata.update(metadata)`, i.e. **last-writer-wins** on colliding keys | Laundering path, shown at code level in v5 |
| **`history(memory_id)`** (SQLite) | **Append-only** rows: `old_memory`, `new_memory`, `event` (ADD / UPDATE / DELETE), timestamps, `actor_id`, `role` (from metadata) | A **native** event log that survives UPDATE. It **could carry provenance and lineage independently of the rewritable payload**. Its actor fields are app-supplied, not authenticated |
| `search` / `get_all` | Payload metadata is returned with each memory | Provenance is available at retrieval time |

**Not available anywhere:**
- authenticated writer identity;
- source spans linking an extracted memory to the exact source text;
- the original conditional structure. Mem0 stores only its rewrite.

## 3. Verified current behaviour, and the precise remaining causes

| Gap | Remaining failure | Precise cause (from the evidence) |
|---|---|---|
| 1 | Lineage-aware B13 over-blocks | It inherits **corroboration** (a grounding test), and ungrounded legitimate items carry their false positive into every derived memory (v2). VPL fixes this by inheriting only the payload verdict through a **verified** link, but then gains only where a content signal existed (v3) |
| 1 | Wrong lineage | Fixed by link verification: wrong-link benign change of 0 points; 1–12% of wrong links pass the similarity check |
| 1 | Laundering | Last-writer-wins metadata on UPDATE. Natural frequency: 0 in 225 ingestions |
| 1 | Ungrounded legitimate memories | No text signal separates them from attacks; channel provenance does, **by assumption** |
| 1 | Mixed-source memories (many-to-one) | **Never tested.** Every harness ingested one item per store, so Mem0 never merged sources |
| 2 | Instruction-payload decay | Paraphrase lowers surface similarity (RCL). NLI tracking (CTC) helps, but its gen-4 tests have 8–18 carrying roots, so they are underpowered |
| 2 | Lineage deleted after writing | WTP needs the taint record. Registry matching cannot replace lineage (45–78% benign collateral) |
| 3 | Implicit sleepers | (a) Attacks and legitimate ungrounded rules share form; authorship is not in the text. (b) Mem0 deletes the conditional form, turning rules into preference facts. **Which information is necessary has never been measured directly** |

## 4. Data inventory (use history)

| Data | Status for v6 |
|---|---|
| SA-3 dev (owners 0, 2, 4, 6; raw and Mem0-stored) | **Development** (used for selection in v2–v5) |
| SA-3 eval (5, 7, 8), SA-4 (1, 3, 9), SA-5 (5, 7, 8) | **Spent** as confirmatory data. Exploratory only |
| HO4, HO8, HO7 chains | **Spent** for containment. Exploratory only. Usable as **simulation substrate** for metadata-deletion conditions, labelled as such |
| v2/v3 development chains (P2 249 + 79) | **Development** |
| **New, needed:** SA-6 (fresh sleeper notes and legitimate rules); a fresh instruction-style root corpus for **powered** propagation; a transformation benchmark for claim fingerprints; mixed-source documents for claim-level provenance | To be built in v6 and frozen before scoring |

## 5. Candidate solutions, with risks and validating experiments

| # | Candidate | Root cause addressed | Risk / expected trade-off | Validating experiment |
|---|---|---|---|---|
| G1-a | **Source-event log**: an immutable record (event id, channel, digest of the original text, original text) kept **outside** the rewritable payload. Mem0's history and the PRW sidecar are both candidates | Provenance and laundering; deleted lineage | Application-level, not authenticated; extra storage | Provenance survival through ADD / UPDATE / extraction / retrieval (forced UPDATE via the API, natural UPDATE counted) |
| G1-b | **Claim-level provenance for mixed-source memories**: each derived memory claim is linked to its most consistent source note (validated), and the source verdict is applied per claim | Many-to-one over-blocking | Ambiguous mappings; claim splitting | **New:** documents that mix an attack note with a legitimate note, through Mem0. Compare item-level vs claim-level inheritance on attack claims blocked and legitimate claims kept |
| G1-c | **Fail-safe lineage validation**: digest consistency + semantic link check + duplicate/conflict detection; unverifiable → no inheritance, flagged for reverification | Wrong lineage | Missed true links | Wrong, duplicate and conflicting mappings injected |
| G2-a | **Claim fingerprints**: hybrid exact digest + semantic + NLI matching, validated on a transformation benchmark | Paraphrase drift; lineage recovery | False lineage matches on benign same-topic text | Benchmark of controlled transformations (copy, mild/heavy paraphrase, split, merge, negation, action change, benign same-topic) |
| G2-b | **Sidecar lineage recovery** after deletion (an append-only taint log keyed by output digest) | Lineage deleted after writing | Recovers exact-content memories only; a rewritten memory becomes an orphan (→ reverify) | Conditions A (present), B (never persisted), C (deleted) on chain data (simulation of deletion; real chains) |
| G2-c | **Powered instruction-payload evaluation** of the existing root-anchored rules | Underpowered gen-4 | Compute | Power analysis, then a fresh instruction-style root corpus |
| G3-a | **Information-boundary experiment** over conditions A–F | Unknown necessary information | None: it is a measurement | Fresh SA-6, dev-selected decision rule per condition, the same held-out notes under every condition, legitimate rules on **both** channels |
| G3-b | **Two-stage sleeper defence** (ingestion record + retrieval-time reassessment against the original record) | Mem0 deletes the conditional form | Only as good as the preserved record | Part of G3-a (conditions D–F), plus activation prevention |

## 6. Addendum: Mem0 write path, read in full before Phase 1

| Finding | Location (mem0 2.0.19, `memory/main.py`) | Consequence |
|---|---|---|
| `add(infer=True)` is **ADD-only**. Extraction returns new memories, which are de-duplicated by md5 hash and batch-inserted. `_update_memory` is reached only from the public `update()` API | `_add_to_vector_store` (Phases 0–7); `_update_memory` called only at line 1865 (`update`) | Explains **0 UPDATE events in 225 ingestions** (v5). Laundering through the extractor is **structurally impossible** in this version. It needs an application or tool that calls `update()` |
| History rows written on the infer path carry **no `actor_id` or `role`** (batch history records omit them). Only `infer=False` records `role` (from the message) and `actor_id` (from the message `name`) | `batch_add_history` records; `infer=False` branch | Mem0's native history keeps text events (ADD / UPDATE / DELETE with old and new text) but **not the writer**, for extracted memories |
| `actor_id` passed in caller metadata is **stripped** (`_IDENTITY_KEYS`) | `_strip_identity_keys` | The app cannot attach a writer label via `actor_id`. Custom metadata keys (e.g. `src`) do survive |
| The extractor emits an LLM-inferred `attributed_to` ("user" / "assistant") | `configs/prompts.py`; `main.py` line 1036 | Native but **model-generated**; never identity. Its agreement with the recorded channel is reported as exploratory |
