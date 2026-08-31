# ConvoMem — Candidate Dataset Package (Phase 3.2-J.1 / J.2)

**Status: `PREPARED_CANDIDATE`. Not activated. Not an active MAMBench dataset.**
**Usability classification (Phase 3.2-J.2): `USABLE_WITH_LIMITATIONS`.** See
`phase3/evaluation/datasets/PHASE3_2_J2_CONVOMEM_FEASIBILITY.md` for the full
evidence-reconstruction investigation that raised evidence coverage from 72.5% (J.1) to
97.0% (J.2) via purely deterministic exact/structural matching — no fabrication, no
fuzzy/LLM matching. The sections below are J.1's original findings; where J.2 superseded
a number, the superseded value is marked and the current value linked.

## Identity verification

**CONFIRMED MATCH** — GitHub `SalesforceAIResearch/ConvoMem` and HuggingFace
`Salesforce/ConvoMem` both correspond to paper arXiv:2511.10523 ("ConvoMem Benchmark").
One genuine surprise: the GitHub repo is a Scala/Gradle **evaluation-harness** (internal
project name `CRM_Mem_Bench`), not a Python data-processing repo — the actual per-persona
JSON QA data lives only on HuggingFace. See `source/identity_and_license_verification.md`
for the full evidence trail, including a real, unresolved **license disagreement** between
the GitHub repo (Apache-2.0) and the HuggingFace dataset card (CC-BY-NC-4.0) — do not
assume Apache-2.0 covers the data.

## What was done

1. Verified identity + licensing (above), including the code/data license split.
2. Full `huggingface_hub.snapshot_download` of `core_benchmark/evidence_questions/` — all
   1,242 files (1.16GB), matching the source's declared 75,336-QA-pair total exactly.
   `pre_mixed_testcases/` and `filler_conversations/` (13GB + 538MB) were inspected
   structurally (one sample file each) but not fully downloaded — see
   `reports/raw_inventory.md` for exactly why and what that means for reproducibility.
3. SHA-256 fingerprint of the full `evidence_questions/` corpus
   (`manifests/raw_fingerprint_full_corpus.json`); an 18-file representative sample is
   committed under `raw/` (the full corpus is `REACQUISITION_REPRODUCIBLE`, not
   `FULLY_PRESERVED` in-repo, given its size).
4. Full-scan structural + evidence-feasibility audit of all 75,336 items —
   `reports/raw_inventory.md`, `reports/evidence_audit.md`.
5. Built a loss-aware normalized view (`normalize.py`) that computes evidence identity via
   deterministic exact-text matching and labels it `ADAPTER_DERIVED_IDENTITY` — never
   claims a native evidence ID exists. Verified deterministic.
6. Wrote `profile/convomem_profile.json` and `profile/mambench_compatibility.json`,
   grounded in `phase3/evaluation/metrics/*.py` and `phase3/evaluation/agent/outcomes.py`.
7. Wrote `manifests/registry_entry.json` (`activation_status: "PREPARED_CANDIDATE"`).
8. Wrote `phase3/evaluation/tests/test_candidate_convomem.py` and ran it twice.

## What was found

### Capability added / genuinely new

Six evidence categories with a real category-label taxonomy (user facts, assistant facts,
changing facts, abstention, preferences, implicit connections) none of the active 4
datasets structure explicitly. **Abstention** with a clean, uniform sentinel answer is
genuinely new — none of the 4 active or 3 prior candidate datasets has a
first-class "no answer exists" category. Multi-message/implicit-connection items (7,546,
full scan) test multi-hop reasoning, though this stage found existing multi-ID Recall@K/
evidence-recall already handle this shape — it is a harder instance, not a new metric
requirement (Part 8 finding, `reports/evidence_audit.md`).

### Overlap with existing datasets

`changing_evidence`'s "facts evolve" semantics, despite the category name, rely on message
**order only** — zero timestamp fields exist anywhere (full scan) — so it does not exceed
MSC/Conversation Chronicles' existing `ORDERED_SEQUENCE_ONLY` temporal capability, contrary
to what "Changing Facts" might suggest.

### Memory / evidence / answer availability (full scan, 75,336 items)

- **Memory/Answer:** 75,336/75,336 (100%) non-null, non-empty answers.
- **Evidence:** `message_evidences` is **verbatim copied text, never a native ID or
  index** — confirmed by inspecting every field name in every downloaded record. J.1's
  exact-text-match adapter resolved 104,890/144,598 (72.5%) of spans. **J.2 extended this
  to a deterministic waterfall** (exact match → unicode/whitespace/punctuation
  normalization → unique-substring truncation match → unique multi-message-window match)
  that resolves **140,225/144,598 (97.0%)** of spans; **94.8% of items are now fully
  resolved**, only **2.3% are zero-resolved** (down from 20.0%) — still classified
  `PARTIALLY_SUPPORTED`, never silently upgraded to `FULLY_SUPPORTED`, because a genuine
  residual gap remains. See `reports/evidence_audit_j2.md` for the full taxonomy.

### ID quality

No native `memory_id`/`evidence_id` field anywhere in `evidence_questions/` — files are
identified only by a UUID+role filename (persona-scoped, not per-message).

### Provenance / lineage support

Dataset-level provenance (HF revision sha) recorded per normalized record. No
`parent_ids`/`equivalent_to` edges anywhere (full scan) — shared gap with all 7 existing
MAMBench datasets.

### Synthetic-data status

Strong circumstantial evidence of LLM generation: a uniform `checkpoint` hash field
present in nearly every file, templated professional-persona UUID naming, and a
dedicated `filler_conversations/` generation-template pipeline (400 filler prompts per
persona). Not automatically disqualifying — the controlled, templated structure is a
genuine complement to the real-dialogue-sourced active datasets for controlled ablation
studies, though it means ConvoMem cannot claim "real conversational data" the way
LoCoMo/MSC can.

### Preprocessing performed

One `memory_records.jsonl` + one `task_records.jsonl` entry per evidence item, zero
content transformation; `evidence_resolution` computed via the J.2 `ADAPTER_DERIVED_IDENTITY`
waterfall, anchored to the source's native `conversations[i].id` field, explicitly
labeled `NOT_RESOLVABLE_FROM_SOURCE` (never a fabricated location) for the 2.3% of items
with no matchable evidence after all deterministic methods were tried.

### Licensing

**Still `LICENSE_UNRESOLVED`, reconfirmed in J.2**: Apache-2.0 (GitHub code repo) vs.
CC-BY-NC-4.0 (HF dataset-card tag). J.2 found a THIRD signal — the dataset's own embedded
`dataset_info.json` also declares Apache-2.0 — shifting the weight of evidence without
resolving the disagreement (see `source/identity_and_license_verification.md`). Practical
status unchanged: treat the DATA as CC-BY-NC-4.0 (the more restrictive reading), pending
upstream clarification. J.2's technical evidence-coverage improvement explicitly does
NOT resolve this.

### Reproducibility

- `evidence_questions/`: `FULLY_FINGERPRINTED` (SHA-256, full 1,242-file corpus),
  `REACQUISITION_REPRODUCIBLE` in-repo (18-file sample committed, full corpus
  re-downloadable byte-identically from the pinned HF revision).
- `pre_mixed_testcases/`/`filler_conversations/`: `PARTIALLY_REPRODUCIBLE` — revision
  pinned and structurally documented, but not fully scanned or hashed in this stage.
- Normalization: `normalize.py`, verified byte-identical across two runs (against the
  committed sample).

## Recommended status

`PREPARED_CANDIDATE` (activation status unchanged — this package remains prepared, not
activated). **Usability classification: `USABLE_WITH_LIMITATIONS`** (Phase 3.2-J.2,
upgraded from J.1's `KEEP_CANDIDATE_ONLY`).

## Advisory judgment: USABLE_WITH_LIMITATIONS (evidence gap substantially closed;
licensing and size remain open)

J.2 closed the evidence-integrity gap that primarily justified J.1's KEEP_CANDIDATE_ONLY
call: 97.0% of spans / 94.8% of items now resolve deterministically, with the residual
3.0% explicitly represented, never fabricated. Two limitations remain and are why this is
`USABLE_WITH_LIMITATIONS` rather than `PROMOTE_TO_USABLE`: (1) the GitHub-vs-HF license
disagreement remains formally unresolved even after a third signal was found (J.2 does
not treat improved technical coverage as resolving a licensing question), and (2) the
corpus's true size (~14.7GB) still makes full in-repo preservation impractical. See
`phase3/evaluation/datasets/PHASE3_2_J2_CONVOMEM_FEASIBILITY.md` for the full decision
record.
