# PerLTQA raw inventory (full scan, Phase 3.2-J.1)

Source: `git clone --depth 1 https://github.com/Elvin-Yiming-Du/PerLTQA.git`, commit
`8d9e19868e239740ef701e603ec205cd581f221b` (current HEAD as of this stage; the repo's own
README "News" section dates its most recent dataset update to 2025/12/22 -- this commit
is downstream of that update, per the task's instruction to use the current revision).

Full corpus obtained: 10 files, 58,479,133 bytes (`manifests/raw_fingerprint.json`, SHA-256
per file). This is the **entire** repository content relevant to the dataset (`Dataset/`,
`LICENSE.txt`, `README.md`) -- nothing was sampled or partially downloaded.

## Per-file schema and record counts (full scan, not sampled)

| File | Top-level type | Records | Notes |
|---|---|---:|---|
| `Dataset/zh/perltqa.json` | list | 32 character-keyed dicts, 8,593 questions | Original Chinese release |
| `Dataset/zh/perltmem.json` | list | 141 character records, 7,521 memory units | profile + social_relationship + events + dialogues |
| `Dataset/en/perltqa_en.json` | list | 32 character-keyed dicts, 1,905 questions | English v1 |
| `Dataset/en/perltmem_en.json` | list | 141 character records | Same shape as zh |
| `Dataset/en_v2/perltqa_en_v2.json` | list | 32 character-keyed dicts, 1,905 questions | English, Dec-2025 update |
| `Dataset/en_v2/perltmem_en_v2.json` | **dict** (NOT list) | 141 character records, keyed directly by name | Schema shape changed vs en/zh -- container type flipped from list-of-dicts to a single dict keyed by character name |

## Malformed / null / missing (full scan, zh -- the primary usable release)

- Malformed records: **0**
- Null answers: **0**
- Empty answers: **0**
- Missing evidence (non-profile Reference Memory ID does not resolve to a real memory-unit
  key): **0 / 8,236** (100% resolve)
- Duplicate `(character, Question)` pairs: **82** (source-side; not removed)
- Missing identifiers: **0** (every memory unit and every character name is present)
- Inconsistent schemas: **1** (en_v2's memory file container-type change, above)

## Malformed / null / missing (full scan, en and en_v2 -- both English releases)

- Null answers: **1,548 / 1,905 (81.3%)** in EACH of en and en_v2, for the exact same
  (character, section) pairs in both releases
- Missing Reference Memory field: same 1,548 items in each release
- Missing Memory Anchors field: same 1,548 items in each release
- Only the 357-item `profile` section per release has non-null answers and real
  classification labels

This is a genuine, full-scan finding, not a sample-based estimate: **every** non-profile
question in **both** English releases is unusable as a task record. The dataset's own
Dec-2025 changelog entry claims the update "fixed the inconsistency issues in the
dataset" -- this stage's audit finds that claim is **not accurate for the English
releases' non-profile content**, though it may accurately describe fixes elsewhere (e.g.
the zh release, or issues not visible from the file schemas alone). This document does not
speculate further; it reports what was independently observed.
