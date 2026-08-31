# PerLTQA — Candidate Dataset Package (Phase 3.2-J.1)

**Status: `PREPARED_CANDIDATE`. Not activated. Not an active MAMBench dataset.**

## Identity verification

**CONFIRMED MATCH.** `Elvin-Yiming-Du/PerLTQA` (GitHub API-confirmed description: "PerLTQA
is a new benchmark for memory classification, retrieval, and synthesis of Large Language
Models"), paper arXiv:2402.16288 / ACL Anthology `2024.sighan-1.18`. The repo's citation
block matches the paper title/authors exactly. Full repo cloned at commit
`8d9e19868e239740ef701e603ec205cd581f221b`.

## What was done

1. Verified identity (above) via GitHub API + direct README/paper cross-reference.
2. Full `git clone --depth 1` of the repository (58.5MB, 10 files) — the entire dataset,
   not a sample. SHA-256 fingerprint of every file in `manifests/raw_fingerprint.json`.
3. Full-scan structural audit of all three shipped language releases (zh, en, en_v2) —
   `reports/raw_inventory.md`.
4. Built a loss-aware normalized view (`normalize.py`) preserving PerLTQA's native
   character/profile/social_relationship/events/dialogues hierarchy and its native
   memory-unit IDs, rather than flattening into a generic QA table. Verified deterministic
   (byte-identical output across two runs).
5. Wrote a capability profile (`profile/perltqa_profile.json`) and a per-metric
   MAMBench compatibility audit (`profile/mambench_compatibility.json`), the latter
   grounded in reading the actual metric function signatures in
   `phase3/evaluation/metrics/*.py` and `phase3/evaluation/agent/outcomes.py`.
6. Wrote `manifests/registry_entry.json` with `activation_status: "PREPARED_CANDIDATE"`.
7. Wrote `phase3/evaluation/tests/test_candidate_perltqa.py` and ran it twice.

## What was found

### Capability added / genuinely new relative to the active 4 + 3 prior candidates

**Memory classification** (profile-section QA: predict which of 15 source-native category
labels — Gender, Nickname, Title, Age, Occupation, Nationality, Physical Characteristics,
Hobbies, Achievements, Ethnic Background, Education Background, Employer, Awards and Role
Models, Protagonist — a question is grounded in) is a real task shape none of LoCoMo,
LongMemEval, MSC, Conversation Chronicles, MemoryAgentBench, MemBench, or MemoryArena has.
**Semantic-memory/episodic-memory/social-relationship structural separation** (profile+
events = semantic/episodic-ish content; social_relationship = an explicit relationship
graph; dialogues = conversational turns) is a genuinely distinct memory taxonomy from the
active datasets' flat conversational-turn model. **Native, memory-ID-typed gold evidence**
(the `Reference Memory` field, 100% internally-consistent in zh, full scan) is stronger
evidence grounding than 3 of the 4 active datasets have (MSC/Conversation Chronicles have
none at all; LoCoMo is only PARTIAL).

### Overlap with existing datasets

Low. No active or prior-candidate dataset has PerLTQA's character/social-graph/event
hierarchy or its classification-label task shape.

### Memory / evidence / answer availability (zh — the primary, fully usable release)

- **Memory:** 7,521 memory units (357 profile-field groups + 6,970 individual
  social_relationship/events/dialogues units) across 141 characters, full scan.
- **Evidence:** 8,236/8,236 (100%) of non-profile Reference Memory IDs resolve to a real
  memory-unit key in the correct character's record (full scan). Span-level (Memory
  Anchors) resolution is 88.4% (20,937/23,697 spans, full scan).
- **Answer:** 8,593/8,593 (100%) non-null, non-empty (full scan).

### English releases — a genuine, full-scan-confirmed limitation

Both shipped English releases (`en`, the original translation, and `en_v2`, the Dec-2025
update) have **null answers, missing Reference Memory, and missing Memory Anchors for
1,548/1,905 (81.3%) of their non-profile questions** — identical broken items in both
releases. Only the 357-item profile subset is usable in English. The Dec-2025 update's
changelog claim ("fixed the inconsistency issues") does not describe this specific gap;
it also introduced a schema change (the memory file's top-level container flipped from a
list to a dict) and one new character-name mismatch between the QA and memory files.
**PerLTQA is not Chinese-only** as initially framed — it ships all three releases — but
only the **zh** release is fully usable for task-level evaluation today.

### Language compatibility with MAMBench's existing metrics

`evaluate_answer_correctness` (`phase3/evaluation/agent/outcomes.py:126-194`, read
directly) applies only `.strip()` before exact-match comparison — no case-folding, no
ASCII/tokenization assumption. This is **NO_BLOCKER**: Chinese-language exact-match
answer correctness runs against the existing metric with zero framework changes. All of
`phase3/evaluation/metrics/*.py`'s ID-based metrics (Recall@K, MRR, evidence precision/
recall, Strict TSR, redundancy, selection count) are likewise language-agnostic — they
operate on IDs and counts, never on answer-string content.

### ID quality

Per-character stable, unique native IDs (0 duplicate memory-unit IDs within a character,
full scan). IDs are **scoped per character, not globally unique** — a MAMBench-style
global `memory_id` requires the composite `(character, native_memory_unit_id)`, which
`normalize.py` constructs explicitly rather than assuming the bare native ID is
sufficient.

### Provenance / lineage support

Dataset-level provenance (github commit) recorded per normalized record. No
`parent_ids`/`equivalent_to` edges exist anywhere in the source (full scan, all
languages) — `NOT_PROVIDED_BY_SOURCE`, matching all 7 existing MAMBench datasets, not a
PerLTQA-specific gap.

### Preprocessing performed

zh: full flatten into `memory_records.jsonl` (7,521 records) + `task_records.jsonl`
(8,593 records), zero drops. en/en_v2: profile-only normalization
(`en_profile_task_records.jsonl` / `en_v2_profile_task_records.jsonl`, 357 records each);
the 192 broken non-profile (character, section) groups per language are explicitly logged
in `manifests/exclusion_manifest.json`, never silently dropped — `raw/` retains every
original file unchanged.

### Licensing

CC BY-NC 4.0, confirmed independently against both `LICENSE.txt` and `README.md`'s
"License" section — **no disagreement found** (contrast with ConvoMem's GitHub-code-vs-
HF-dataset-card licensing split; see `../convomem/README.md`). Non-commercial research use
only.

### Reproducibility

- Raw: `manifests/raw_fingerprint.json` — SHA-256 for all 10 files, full corpus, not a
  sample. `FULLY_PRESERVED`.
- Normalization: `normalize.py`, verified byte-identical across two runs.
- Tests: `phase3/evaluation/tests/test_candidate_perltqa.py`.

## Recommended status

`PREPARED_CANDIDATE`.

## Advisory judgment: PROMOTE_TO_USABLE-eligible for the zh release only

PerLTQA's zh release has the strongest evidence-ID integrity of any dataset audited so far
in MAMBench (100% Reference-Memory-ID resolution, full scan) and adds a genuinely new
memory-classification task shape. Its two structural costs — per-character-scoped IDs
(a straightforward composite-key adapter, not a blocker) and a real, source-verified 81.3%
non-profile-item breakage in BOTH English releases — mean promotion should be scoped to
**zh only** initially, with en/en_v2 kept as profile-only supplementary material pending
upstream correction. See the main Phase 3.2-J.1 document for the full candidate decision.
