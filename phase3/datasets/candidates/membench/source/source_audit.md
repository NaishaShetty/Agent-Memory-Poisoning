# MemBench Source Audit

## Identity verification

- **Official name (from README):** "MemBench: Towards More Comprehensive Evaluation on the
  Memory of LLM-based Agents"
- **GitHub URL:** https://github.com/import-myself/Membench
- **Commit hash used (pinned):** `f66d8d1028d3f68627d00f77a967b93fbb8694b6` (shallow clone,
  `--depth 1`, default branch, cloned 2026-08-28)
- **Paper:** arXiv:2506.21605 — "MemBench: Towards More Comprehensive Evaluation on the Memory
  of LLM-based Agents" (link taken directly from the README badge; abstract not independently
  re-fetched in this session, title/scope match confirmed by README content alone)
- **License:** README displays an `MIT` badge (`https://opensource.org/licenses/MIT`). **No
  `LICENSE` file exists in the repository at the pinned commit** (confirmed by full file walk,
  see `manifests/raw_fingerprint.json` — 57 files total, none named `LICENSE*`). Treat the
  license as **README-claimed MIT, not file-confirmed MIT** — flagged `UNKNOWN` /
  `CLAIMED_NOT_CONFIRMED` in the registry entry.
- **Author/project:** GitHub user/org `import-myself` (repo owner as observed; no separate
  AUTHORS file).

## Category / variant match against mission description

The mission asked to verify categories: simple, noisy, knowledge update, high-level reasoning,
recursive/multi-session, and first-person/third-person (Participation/Observation) variants.
All confirmed present, both in the README's own description and in the actual bundled data
(`MemData/`):

| Mission-named category | Confirmed in repo | Evidence |
|---|---|---|
| simple | yes | `MemData/{FirstAgent,ThirdAgent}/simple.json` |
| noisy | yes | `MemData/{FirstAgent,ThirdAgent}/noisy.json`, plus dedicated noise pools in `MakeNoise/NoiseMeta/{messagenoise_new,sessionnoise_new}.json` |
| knowledge update | yes | `MemData/{FirstAgent,ThirdAgent}/knowledge_update.json` |
| high-level reasoning | yes | `MemData/{FirstAgent,ThirdAgent}/highlevel.json`, plus `highlevel_rec.json` (recommendation variant, FirstAgent only) |
| recursive / multi-session | yes | `MemData/FirstAgent/RecMultiSession.json` (`multi_agent` scenario), plus `lowlevel_rec.json` |
| first-person / Participation | yes | `MemData/FirstAgent/*` — dialogue turns (`user_message`/`assistant_message` or `user`/`assistant`) |
| third-person / Observation | yes | `MemData/ThirdAgent/*` — single narrated `message` turns, no dialogue |

Additional categories present beyond the mission's list, also legitimate MemBench categories
per the README/paper structure: `aggregative`, `comparative`, `conditional`, `post_processing`.
These map to the paper's finer-grained low-level/high-level QA taxonomy (Appendix Table 6,
referenced by the README but not independently re-derived here beyond what the bundled data
and code reveal).

**Conclusion: this is confirmed to be the correct MemBench repository** referenced by the
mission. No mismatch found; proceeding.

## Documented data links (cross-checked against mission text)

- Google Drive: `https://drive.google.com/file/d/112Zraj4pTPH4Idph6i1uMOLA_LPFdGr0/view?usp=sharing`
  — **matches** the link given in the mission, byte-for-byte.
- Baidu Pan: `https://pan.baidu.com/s/1HqwY0nu5bltSAJ2TbnxcFQ?pwd=yzsj` (extraction code `yzsj`)
  — **matches** the link given in the mission.
- README also documents a `data2test` directory with pre-sampled "0-10k and 100k" length
  variants used in the paper's own experiments. This directory is **not present** in the
  GitHub repo itself (it is presumably inside the Drive/Baidu archive only) — confirmed absent
  by the full file walk in `manifests/raw_fingerprint.json`.

## Key surprise vs. mission expectation

The mission anticipated that the GitHub repo would likely contain, at most, "a handful of
example records" while the full corpus lived only behind Drive/Baidu. **That expectation did
not hold for this repository**: the GitHub repo itself bundles the complete `MemData/`
corpus — 19 category JSON files across `FirstAgent`/`ThirdAgent`, totalling roughly 650 MB
and 26,637 individual QA records (see `reports/raw_inventory.md`) — plus the noise pools used
to build the "noisy" category and the full benchmark harness / generation source code. This is
a materially better outcome than the mission's fallback path assumed, and is documented
explicitly here so the acquisition-limitation framing in the rest of this package is read in
its correct, narrower scope: **the GitHub-hosted corpus was obtained and fingerprinted; the
Drive/Baidu mirrors were not independently re-verified because they were not needed.**

## Download mechanism / file formats

- Format: JSON (UTF-8), one file per (variant, category) pair, each a dict keyed by
  "scenario" (e.g. `roles`, `events`, `movie`, `food`, `book`, `items`, `places`, `hybrid`,
  `multi_agent`) mapping to a list of QA-annotated conversation records.
- No dedicated loader/CLI is provided for the bundled data beyond `benchmark/load_test_data.py`
  (data-generation-side mixing/noise-injection utility) and `benchmark/env/Membenenv.py`
  (evaluation-harness side, consumes the same JSON shape directly with `json.load`).

## Known issues / limitations documented by the repo itself

- No LICENSE file (see above).
- `requirements.txt` is a **Git LFS pointer file**, not actual pinned dependency text
  (`oid sha256:43a3259a50563d1302a655ac57f0361df610de6af97813b8d745684ea4911908`, size 265
  bytes) — the real dependency list was not fetched (Git LFS content, not attempted; out of
  scope for a candidate data audit, noted here as a reproducibility gap for anyone wanting to
  run `benchmark/`).
- No GitHub Issues content was reviewed in this session (not fetched); "known issues" beyond
  what the README/code show directly are `UNKNOWN`.
- The README's own caveat on noise: "For each additional unit of noise length, the token count
  increases by about 1k on average" — i.e. the noise-injection utilities (`MakeNoise*`) are
  meant to be run by the user to *extend* context length beyond what ships in `MemData/`; the
  bundled `noisy.json` files are the paper's own pre-built noisy split, not a live generator
  output.
