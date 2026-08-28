# MemBench -- Candidate Dataset Preparation (Phase 3.2-H.1)

**Status: `PREPARED_CANDIDATE`. This is NOT activation. MemBench is not an active MAMBench
dataset.**

## What was and was not obtained -- read this first

The mission expected that the GitHub repository would likely contain, at most, a handful of
bundled example records, with the real corpus living only behind the paper's Google Drive
(`https://drive.google.com/file/d/112Zraj4pTPH4Idph6i1uMOLA_LPFdGr0/view?usp=sharing`) and
Baidu Pan (`https://pan.baidu.com/s/1HqwY0nu5bltSAJ2TbnxcFQ?pwd=yzsj`, password `yzsj`) links.

**That did not hold here.** The GitHub repository
(https://github.com/import-myself/Membench, commit
`f66d8d1028d3f68627d00f77a967b93fbb8694b6`, cloned with `git clone --depth 1`) was found to
bundle the **entire MemData QA corpus directly** -- 26,637 QA-annotated conversation records
across 19 category JSON files, covering both the `FirstAgent` (Participation/first-person) and
`ThirdAgent` (Observation/third-person) variants, plus the noise pools used to build the
"noisy" category and the full generation/benchmark-harness source code. This was confirmed by
a full scan of every record (not a sample) -- see `reports/raw_inventory.md`.

Given that, **the Google Drive and Baidu mirrors were not independently attempted or
re-verified** in this session: the primary data-acquisition risk the mission flagged (Drive's
browser-confirmation gate, Baidu's password/account gate) turned out not to matter, because the
GitHub repo already provided the real corpus. One documented consequence: the paper's own
pre-sampled `data2test` length variants (0-10k / 100k tokens), which the README says live only
in the Drive/Baidu archive, were **not** inspected -- only the raw `MemData/` corpus was.

This is a materially better acquisition outcome than the mission's fallback scenario assumed.
The rest of this README, and the reports in this package, are written against that actual
outcome, not the anticipated worst case.

## Repository identity verification

Confirmed via full README read (see `source/source_audit.md` for the complete audit):
- Paper: arXiv:2506.21605, "MemBench: Towards More Comprehensive Evaluation on the Memory of
  LLM-based Agents".
- License: README displays an MIT badge; **no LICENSE file exists in the repo** at the pinned
  commit -- treated as claimed-not-confirmed, not verified MIT.
- All mission-named categories confirmed present in the actual data: simple, noisy, knowledge
  update, high-level reasoning (`highlevel`, `highlevel_rec`), recursive/multi-session
  (`RecMultiSession`, `lowlevel_rec`), plus `aggregative`/`comparative`/`conditional`/
  `post_processing` (finer-grained taxonomy from the same paper). Both first-person
  (`FirstAgent`) and third-person (`ThirdAgent`) variants confirmed present and structurally
  distinct (dialogue turns vs. single-narration observation turns).

## What's in this package

```
source/       -- source_audit.md: identity verification, license status, category match, gaps
raw/          -- repo_bundle/ (all small repo files verbatim: README, benchmark harness code,
                 generation scripts, requirements.txt LFS pointer, graphs.json seed profiles)
                 MemData_samples/ (deterministic first-5-records-per-scenario sample of the
                 large MemData/*.json corpus -- see "Scope decision" below)
normalized/   -- membench_normalized.jsonl: 275 normalized records (from the same sample)
profile/      -- membench_profile.json (19-dim capability profile)
                 mambench_compatibility.json (3.2-B..H compatibility audit)
reports/      -- raw_inventory.md (FULL-corpus counts, exact), field_semantics.md,
                 data_quality_report.md
manifests/    -- raw_fingerprint.json, full_corpus_inventory_scan.json (full-corpus scan
                 results), preprocessing_manifest.json, exclusion_manifest.json,
                 registry_entry.json
```

## Scope decision: why raw/ and normalized/ don't contain all 26,637 records

The GitHub repo's `MemData/` corpus totals roughly 650 MB across 19 JSON files. Two decisions
were made, both documented explicitly rather than silently:

1. **`raw/` does not vendor the ~650 MB MemData/MakeNoise JSON files byte-for-byte** into this
   git-tracked project directory -- that would be poor repository hygiene for a project
   directory, independent of any prohibition on committing (nothing here was committed).
   Instead: every file in the clone (including the large ones) was **SHA-256 fingerprinted in
   place** (`manifests/raw_fingerprint.json`, 57 files, ~713 MB total, all successfully
   hashed), and a **deterministic sample** (first 5 records of every one of the 55
   variant/category/scenario groupings, 275 records total) was extracted into
   `raw/MemData_samples/membench_memdata_samples.json` for inspection and normalization.
2. **`normalized/` covers only that same 275-record sample**, not the full 26,637. This is a
   scope decision for candidate preparation, not data loss or an exclusion -- see
   `manifests/preprocessing_manifest.json`'s `sampling_for_normalized_view` entry. The
   normalization logic itself was verified deterministic and is fully reproducible against the
   pinned commit.

The **full-corpus counts in `reports/raw_inventory.md` and `reports/data_quality_report.md`
are exact**, from a complete scan of all 26,637 records -- only the *normalization pass*, not
the *inventory pass*, was sample-limited.

## Decision-report fields

- **Capability added:** Multiple-choice QA over synthetic long-horizon conversational memory,
  with graded categories for simple recall, noise robustness, knowledge updates over time,
  high-level/aggregative reasoning, and multi-session recall -- in both a first-person
  (participant) and third-person (observer) framing. Gold answers, gold MC ground truth, and
  (for 99.985% of records) gold evidence-turn pointers are all present.
- **Overlap with the 4 active datasets** (LoCoMo, LongMemEval, MSC, Conversation Chronicles):
  not independently re-assessed against those datasets' own profiles in this session (out of
  scope); structurally, MemBench's synthetic-generation-pipeline origin, explicit MC
  ground-truth format, and dual first/third-person framing are distinguishing features not
  confirmed to exist identically in the 4 active sets -- but a rigorous overlap/novelty claim
  would require re-reading those profiles side-by-side, which was not done here. Marked
  `UNKNOWN` pending that comparison.
- **Genuinely new capability:** Likely yes for the first/third-person (Participation vs.
  Observation) axis and for the dedicated, reusable noise-injection pipeline
  (`MakeNoise/NoiseMeta`) -- but this is an informed judgment, not a verified negative claim
  against the other three candidates or the four active sets.
- **Memory/evidence/answer availability:** answer 100% (26,637/26,637), ground truth 100%,
  evidence 99.985% (26,633/26,637; 4 exceptions all in `FirstAgent/highlevel_rec/movie`, not
  malformed, just missing that field).
- **ID quality:** `tid` confirmed unique per scenario (0 duplicates across the full scan) and
  used as the normalization key. `qid` is NOT a safe standalone id (duplicated in ~99% of
  records per scenario) -- flagged explicitly, never relied upon alone.
- **Provenance/lineage:** provenance PARTIAL (category/scenario/variant self-documents origin;
  no generation-pipeline metadata like model version or timestamp attached per-record).
  Lineage and equivalence: `NOT_PROVIDED_BY_SOURCE` -- genuinely absent from the source, not an
  acquisition gap.
- **Conflict/update support:** `knowledge_update` category confirmed present (999 records,
  both variants) -- conflict/update semantics must be read from transcript content, no
  dedicated conflict-pair field exists.
- **MAMBench compatibility summary:** boundary/leakage separation SUPPORTED and verified (0
  violations across the sample); evidence metrics SUPPORTED with a straightforward
  `[session,turn]` -> string-id encoding step; equivalence and provenance/lineage metrics
  UNDEFINED against this dataset (source provides no such relationships at all -- see
  `profile/mambench_compatibility.json`).
- **Preprocessing performed:** turn-shape normalization (3 observed shapes unified),
  session-container normalization, evaluator-boundary split, ID construction from source-native
  `tid`, lineage/equivalence defaulting to `NOT_PROVIDED_BY_SOURCE`. All reversible, none lose
  information (`manifests/preprocessing_manifest.json`).
- **Exclusions:** zero. 0 malformed records found across the full 26,637-record scan
  (`manifests/exclusion_manifest.json`).
- **Known limitations (front and center):**
  1. Google Drive / Baidu mirrors not independently obtained or re-verified (see above) -- the
     paper's own `data2test` pre-sampled variants were therefore not inspected.
  2. No LICENSE file; MIT is a README badge claim only.
  3. `requirements.txt` is an unresolved Git LFS pointer -- harness reproducibility incomplete.
  4. The dialogue-generation pipeline imports a `utils` module not present at the pinned
     commit -- data cannot be regenerated from this repo alone.
  5. `qid` is not a safe unique identifier.
  6. Only a 275-record sample, not the full 26,637-record corpus, was carried through
     normalization in this pass.
- **Licensing:** README-claimed MIT, not file-confirmed.
- **Reproducibility:** the GitHub-bundled corpus is reproducible by re-cloning commit
  `f66d8d1028d3f68627d00f77a967b93fbb8694b6`; the Drive/Baidu-only `data2test` content is not
  independently reproducible from anything in this package.
- **Storage/compute implications:** the full corpus is ~650 MB of JSON; normalizing all 26,637
  records (rather than the 275-record sample here) is a mechanical, linear-time operation with
  no model/embedding cost -- normalization here never invoked any model, embedding, or vector
  store, consistent with the "no model integration" rule.
- **Recommended status:** `PREPARED_CANDIDATE` (per mission rules, activation is out of scope
  regardless).

## Advisory judgment: RECOMMEND ACTIVATION vs. KEEP CANDIDATE-ONLY

**KEEP CANDIDATE-ONLY for now, with a caveat that is more favorable than a typical
data-acquisition-gap case.** Unlike a candidate where the primary corpus genuinely could not
be obtained, MemBench's real, full, 26,637-record corpus WAS obtained and scanned in this
session, with clean structural quality (0% malformation, 100% answer/ground-truth coverage,
99.985% evidence coverage) and a demonstrably clean evaluator/agent boundary. The reasons to
still hold at candidate-only are: (a) only a small sample was actually normalized in this pass,
so full-corpus normalization and a full boundary/leakage re-validation over all 26,637 records
remain to be done before activation; (b) license status is unconfirmed (no LICENSE file); (c)
overlap/novelty against the 4 active datasets was not assessed; (d) the paper's own
`data2test` length-variant sampling was not inspected. None of these are the "data physically
unobtainable" blocker the mission anticipated -- they are ordinary next-step integration work.
If a maintainer wants to fast-track MemBench toward activation, the highest-leverage next steps
are: full-corpus normalization (mechanical, already demonstrated deterministic on the sample),
a license clarification with the upstream authors, and a side-by-side overlap comparison
against the 4 active profiles.
