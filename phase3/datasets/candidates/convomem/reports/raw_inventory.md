# ConvoMem raw inventory (full scan, Phase 3.2-J.1)

Source: HuggingFace `Salesforce/ConvoMem`, revision `e3e9b39115b02346824c70d349350de738f8be41`,
acquired via `huggingface_hub.snapshot_download` (no `datasets` library, no auth token).

## Corpus components (full directory listing, `core_benchmark/`)

| Component | Files | Approx. size | Role |
|---|---:|---:|---|
| `evidence_questions/` | 1,242 | 1.16 GB | The actual QA-pair corpus: per-persona JSON files, one per (category, evidence-count-bucket) |
| `pre_mixed_testcases/` | 471 (`batched_NNN.json`, each a LIST of pre-assembled test cases) | ~13 GB | Full long-context evaluation variant: each item bundles real evidence conversations spliced with filler content into one larger multi-conversation context. **Key-naming inconsistency found**: uses camelCase `evidenceItems`/`message_evidences` vs. `evidence_questions/`'s snake_case `evidence_items` -- a real, source-side schema inconsistency, not introduced by this stage. |
| `filler_conversations/` | 100 (one per persona) | ~538 MB | Distractor/filler generation templates (400 filler prompts per persona file), used to build the long-context pre-mixed variant. Not evidence for any QA item. |
| `personas/` | 1 (`personas_default.json`) | 304 KB | A single file with a `roles` list -- the persona/role vocabulary referenced by all the above. |

**Total corpus size: ~14.7 GB.** This is far larger than any dataset previously prepared
as a MAMBench candidate (MemBench's full corpus was ~700MB and MemoryArena's ~17MB) and
too large to commit into this git repository. This stage's disposition, per Part 22 of
the task brief:

- **`evidence_questions/` (the actual QA/evidence corpus this candidate's `normalize.py`
  consumes)**: **FULLY ACQUIRED, FULLY SCANNED, FULLY SHA-256-FINGERPRINTED**
  (`manifests/raw_fingerprint_full_corpus.json`, all 1,242 files / 1,212,565,824 bytes) --
  but only an 18-file representative sample (one evidence-count bucket per category, 3
  persona files each) is committed under `raw/` for schema illustration and test
  fixtures. The full corpus is `REACQUISITION_REPRODUCIBLE` (revision-pinned, re-downloadable
  byte-identically) rather than `FULLY_PRESERVED` in-repo.
- **`pre_mixed_testcases/` and `filler_conversations/`**: inspected structurally (one
  sample file each, reported below) but **NOT** fully downloaded, hashed, or scanned in
  this stage -- 13GB+538MB is beyond what this stage's time/disk budget could responsibly
  spend on components `normalize.py` does not consume. Classified `PARTIALLY_REPRODUCIBLE`:
  their existence, revision, and top-level shape are documented and re-acquirable, but no
  full-corpus integrity scan (malformed-record count, null-answer count, etc.) was
  performed for them. This is a genuine, disclosed limitation, not a claimed full audit.

## Per-category counts, `evidence_questions/` (full scan -- matches every count in the
GitHub README's own table exactly)

| Category | Items (this scan) | README-declared |
|---|---:|---:|
| user_evidence (User Facts) | 16,733 | 16,733 |
| assistant_facts_evidence | 12,745 | 12,745 |
| changing_evidence | 18,323 | 18,323 |
| abstention_evidence | 14,910 | 14,910 |
| preference_evidence | 5,079 | 5,079 |
| implicit_connection_evidence | 7,546 | 7,546 |
| **Total** | **75,336** | **75,336** |

Null answers: **0 / 75,336**. Empty answers: **0 / 75,336**. Malformed JSON files: **0 /
1,242** (every file parsed successfully).

## `evidenceItems` vs `evidence_items` naming inconsistency (pre_mixed_testcases)

Confirmed by direct inspection of `pre_mixed_testcases/abstention_evidence/1_evidence/
batched_000.json`: its per-case key is `evidenceItems` (camelCase), while every file in
`evidence_questions/` uses `evidence_items` (snake_case) for the same concept. This is a
genuine source-side inconsistency between ConvoMem's two evaluation variants, not
something this stage introduced, and not something `normalize.py` attempts to paper over
silently -- `normalize.py` only reads `evidence_questions/`, and does not attempt to
ingest `pre_mixed_testcases/` at all in this stage.
