# ConvoMem — source, revision, and licensing verification (Phase 3.2-J.1)

## Identity

- **GitHub**: `SalesforceAIResearch/ConvoMem` (API-confirmed: id 1067958323, org
  `SalesforceAIResearch`, `created_at` 2025-10-01, `pushed_at` 2026-06-02, default branch
  `main`).
- **Paper**: arXiv:2511.10523, "ConvoMem Benchmark: Why Your First 150 Conversations
  Don't..." (title truncated in the fetched HF dataset-card summary; matches the citation
  the GitHub README and HF dataset card both link).
- **HuggingFace**: `Salesforce/ConvoMem`, dataset sha `e3e9b39115b02346824c70d349350de738f8be41`,
  `lastModified` 2025-11-18T16:06:25Z, 75,336 declared rows (`train` split,
  `dataset_info.splits`).

## A genuine surprise: the GitHub repo is NOT a Python data-processing repo for ConvoMem — it's a Scala/Gradle evaluation harness for a differently-named internal project

Direct inspection of the repo's file tree (`AI_ETHICS.md`, `CODEOWNERS`, `build.gradle`,
`gradlew`, `src/main/scala/...`) and its README's own "Repository Structure" section shows
the top-level project directory is literally named `CRM_Mem_Bench/`, and the harness is a
Java/Scala Gradle application (`./gradlew run --args="evaluate ..."`), not a Python
package. The GitHub repo IS the genuine ConvoMem project (README content, category
names/counts, and citation all match the HF dataset card and the paper exactly) — this is
simply the *evaluation-harness code* companion to the dataset, not the dataset's own
processing pipeline. The actual per-persona JSON data files live only on HuggingFace
(`Salesforce/ConvoMem`), not in this GitHub repo at all. This is a legitimate, if
initially confusing, code/data split — not a wrong-repository situation (contrast with
H.2's "Memary" 404 case, which WAS a wrong-URL situation).

## Licensing — an unresolved disagreement between the GitHub code repo and the HF dataset card

**GitHub repo (`SalesforceAIResearch/ConvoMem`)**:
- `LICENSE.txt` (fetched verbatim, 200 OK): Apache License Version 2.0, Copyright (c) 2024
  Salesforce, Inc.
- README.md badge: `[![License: Apache 2.0]...]`
- GitHub API's own license detector: `{"key": "apache-2.0", "spdx_id": "Apache-2.0"}`

**HuggingFace dataset card (`Salesforce/ConvoMem`)**:
- `cardData.license`: **`"cc-by-nc-4.0"`** (fetched verbatim via `huggingface.co/api/
  datasets/Salesforce/ConvoMem`)
- Dataset-card tags array also lists `"license:cc-by-nc-4.0"`

**These disagree, and this document does NOT silently resolve the disagreement**, per the
task's explicit instruction. The most defensible reading, based on what each artifact
actually contains, is that Apache-2.0 governs the Scala/Gradle *evaluation-harness code*
in the GitHub repo, while CC-BY-NC-4.0 governs the *dataset content itself* (the 75,336
QA-pair JSON files hosted on HuggingFace) — a common pattern (permissive code license,
restrictive data license) that Salesforce did not state explicitly anywhere in either
artifact. **No single page states this split outright; it is this stage's inference from
the fact that the two artifacts contain genuinely different content (code vs. data) under
genuinely different license declarations, not a confirmed statement from the source.**
A consumer who saw only the GitHub README's "Apache 2.0" badge and assumed it covered the
dataset would be **wrong** — this is exactly the failure mode the task instructions warned
against, and it is real, not hypothetical.

**Practical consequence for MAMBench**: because the QA-pair *data* is CC-BY-NC-4.0
(non-commercial), ConvoMem cannot be treated as "Apache-2.0, do anything" the way a naive
README-badge read would suggest. Its licensing status for this candidate package is
recorded as **CC-BY-NC-4.0 (data) / Apache-2.0 (harness code, not used by this
package)** — never simplified to a single license string.

## Revision pinned

- HF dataset sha: `e3e9b39115b02346824c70d349350de738f8be41`
- GitHub repo commit (harness code, not used for data acquisition):
  fetched via `git clone --depth 1`, recorded in `raw/convomem_code_commit.txt`.

## Phase 3.2-J.2 re-verification and a third licensing signal

J.2 independently re-fetched the GitHub `pushed_at`/`default_branch` and the HF
`sha`/`license` tag from scratch (not read from this file) — both **unchanged** from J.1:
GitHub `pushed_at: 2026-07-22T18:39:19Z`, HF `sha: e3e9b39115b02346824c70d349350de738f8be41`,
HF `license: cc-by-nc-4.0`. `LICENSE.txt` content was re-fetched verbatim and is
byte-identical to J.1's record (Apache License Version 2.0, Copyright (c) 2024
Salesforce, Inc.).

J.2 also found a metadata file J.1's audit had not surfaced: `dataset_info.json`
(1,018 bytes, LFS-tracked, at the HF repo root, sibling to `core_benchmark/`):

```json
{
  "name": "CRM_Mem_Bench",
  "version": "1.0.0",
  "license": "Apache-2.0",
  "homepage": "https://github.com/salesforce/CRM_Mem_Bench",
  ...
}
```

This is a **third, independent signal**, embedded in the dataset's own bundled metadata
(not the HF web UI's separate card-tag system), and it says **Apache-2.0** — agreeing
with the GitHub code repo, disagreeing with the HF dataset-card tag. The weight of
evidence is now 2 sources (GitHub `LICENSE.txt` + the dataset's own `dataset_info.json`)
saying Apache-2.0 versus 1 source (the HF card's `cardData.license` tag) saying
CC-BY-NC-4.0.

**This does NOT resolve the disagreement.** None of these three sources is
unambiguously authoritative over the other two: `dataset_info.json`'s own `homepage`
field points to `github.com/salesforce/CRM_Mem_Bench` — a different capitalization/path
than the actual live repo (`SalesforceAIResearch/ConvoMem`), suggesting this metadata
file may be a stale or internally-generated artifact carried over from an earlier
project name, not necessarily updated in lockstep with the HF card's own license tag.
Only Salesforce can actually resolve which is authoritative. Per this stage's explicit
Part 19 instruction ("the technical evidence-resolution result does NOT resolve the
licensing problem... do not promote to an actively redistributed benchmark artifact
merely because technical conformance improved"), this stage records the status as
**`LICENSE_UNRESOLVED`** (not "resolved in favor of Apache-2.0" and not "resolved in
favor of CC-BY-NC-4.0") and continues to treat the data as CC-BY-NC-4.0 in practice — the
more restrictive of the two readings, pending upstream clarification.
