# MemoryAgentBench -- Source Audit

## Identity

- Official name: MemoryAgentBench: Evaluating Memory in LLM Agents via Incremental Multi-Turn Interactions
- GitHub: https://github.com/HUST-AI-HYZ/MemoryAgentBench
- Hugging Face dataset: https://huggingface.co/datasets/ai-hyz/MemoryAgentBench
- Paper: https://arxiv.org/abs/2507.05257 (accepted at ICLR 2026; abstract/landing page fetched and read via `curl` during this audit)
- Authors: Yuanzhe Hu, Yu Wang, Julian McAuley (UC San Diego)
- Related follow-up work referenced in the repo's own README: MemoryArena (ICML 2026) -- a separate benchmark, NOT this one, and NOT prepared by this candidate package.

## Exact revisions used (this candidate pass)

- GitHub commit hash: `fe1735de8cf8b9908e1e3d3b5612afc815698062` (obtained via `git clone --depth 1` then `git log -1 --format=%H`)
- HF dataset revision sha: `7ea066982b140a19337e17e60d45d4076e042faf` (obtained via `curl https://huggingface.co/api/datasets/ai-hyz/MemoryAgentBench`'s `sha` field)
- Both fetched live from the network on 2026-08-28 (download timestamp recorded in `manifests/raw_fingerprint.json`); no cached/third-party snapshot was used anywhere in this pass.

## License

- GitHub repo `LICENSE` file: MIT License, copyright (c) 2026 Yuanzhe Hu. Full text preserved verbatim in `raw/github_repo/LICENSE`.
- HF dataset card (`raw/hf_dataset/README.md` front-matter): `license: mit`. Consistent with the GitHub repo.

## Download mechanism

- GitHub: `git clone --depth 1 https://github.com/HUST-AI-HYZ/MemoryAgentBench` into a scratch location, then all files except `.git/` copied into `raw/github_repo/` (1081 files, includes `agent.py`, `main.py`, `initialization.py`, `conversation_creator.py`, `requirements.txt`, `configs/` (agent_conf + data_conf YAMLs for every task variant), `assets/`, `bash_files/`, `cognee/`, `letta/`, `llm_based_eval/`, `mem0/`, `methods/`, `utils/`).
- Hugging Face: direct `curl` against `https://huggingface.co/datasets/ai-hyz/MemoryAgentBench/resolve/main/<file>` for `README.md`, `entity2id.json`, and all 4 `data/*.parquet` split files, into `raw/hf_dataset/`.

## Approximate size / coverage

- HF dataset card's own declared `download_size`: 74,805,902 bytes (~71 MB) across the 4 parquet files; `dataset_size` (uncompressed): 131,992,200 bytes (~126 MB).
- **This candidate downloaded ALL 4 parquet files in full** -- verified: each downloaded file's byte size matches the HF API's reported size exactly (Accurate_Retrieval: 20,024,386 bytes; Conflict_Resolution: 1,491,588 bytes; Long_Range_Understanding: 49,342,452 bytes; Test_Time_Learning: 3,947,476 bytes; sum = 74,805,902 bytes, matching the card's `download_size` exactly). **This is FULL coverage of the published HF parquet data, not a partial sample.**
- `entity2id.json` (1,758,081 bytes, 31,161-entry DBpedia URI-to-ID map) also downloaded in full.
- The GitHub repo itself does not host the dataset (it is fetched from HF at runtime by the benchmark's own code) -- so cloning it captures 100% of what exists there (code, configs, docs), with nothing left un-downloaded.
- **Nothing was left un-downloaded from either source in this pass.** There is no multi-GB corpus this candidate declined to fetch.

## Task / configuration structure (from the GitHub repo's own README and `configs/`)

Four core competencies, each with a `configs/data_conf/<Competency>/` directory of per-task-variant YAML configs:
- **Accurate Retrieval**: `configs/data_conf/Accurate_Retrieval/{EventQA,LongMemEval,Ruler/QA}/` -- 7 YAML configs (Eventqa_128k/64k/full, Longmemeval_s/s_star, Ruler_qa1_197k/qa2_421k).
- **Test-Time Learning**: `configs/data_conf/Test_Time_Learning/{ICL,Recsys}/` -- 6 YAML configs (ICL_banking77/clinic150/nlu/trec_coarse/trec_fine, Recsys_redial_full).
- **Long-Range Understanding**: `configs/data_conf/Long_Range_Understanding/` -- 2 YAML configs (Detective_QA, InfBench_sum).
- **Conflict Resolution**: `configs/data_conf/Conflict_Resolution/` -- 8 YAML configs (Factconsolidation_{mh,sh}_{6k,32k,64k,262k}).

Each YAML config specifies `dataset` (competency name), `chunk_size` (the "inject once, query multiple times" incremental-chunk size, e.g. 4096 tokens), `sub_dataset` (matches the parquet's `metadata.source` value), `context_max_length`, and evaluation parameters (`generation_max_length`, `shots`, etc.) -- these govern HOW the benchmark's own `main.py`/`agent.py` harness runs an agent against the data; this candidate did not run that harness (no model integration, per this task's explicit scope) and only read the configs to understand task/data shape.

## Documented revision history (from HF dataset card `README.md` changelog, `raw/hf_dataset/README.md`)

- 2025-07-07: initial dataset release.
- 2025-07-22: `uuid` field renamed to `qa_pair_ids`; `keypoints` field added to Long-Range-Understanding rows; note that `question_ids` is used ONLY for the LongMemEval task.
- 2025-07-26: bug fix applied to `qa_pair_ids`.
- 2025-08-05: `ruler_niah` and "some other datasets not used in main experiments" REMOVED from the published dataset (the authors state a subset will be released later for ablation study -- as of this candidate's revision, that has not appeared).
- 2025-09-29: paper updated, "removed some in-efficient and high-cost samples," added a DetectiveQA subsample.
- The GitHub repo's own README additionally documents a May 2026 update (GPT-5-Mini results added) and a January 2026 note (ICLR 2026 acceptance) -- these are paper/results updates, not documented as data changes.

**This candidate's revision (HF sha `7ea06698...`) is the CURRENT state after all of the above changes** -- it is not a re-derivation of any earlier state, and this audit did not attempt to reconstruct or diff against any prior HF revision (out of scope for this pass; flagged as a limitation, not silently assumed identical).

## Known bugs/limitations documented by the authors

- The GitHub README's own "Clarification on Evaluation Metrics" section states: for `exact_match` scoring, "the parsing is strict -- e.g., if the ground-truth label is '43' but the model returns 'label: 43', it will be counted as incorrect," and the authors themselves "recommend flexible parsing when adapting the benchmark to your own pipeline" -- i.e. the authors flag their own default scoring as overly strict for downstream reuse.
- The authors note `hipporag`-related package version conflicts requiring a separate conda environment (an infra note about the reference implementation, not about the data).
- The 2025-08-05 changelog entry ("we removed the ruler_niah and some other datasets... We will release a subset for ablation study in future") documents that MORE data existed in earlier releases than exists now -- this candidate's revision reflects the current, reduced set, and this audit does not claim access to the removed subset.

## What was NOT attempted in this pass

- No model/LLM/embeddings integration of any kind.
- No running of the benchmark's own evaluation harness (`main.py`, `agent.py`, `llm_based_eval/*`).
- No join of `entity2id.json` against `recsys_redial_full` answer strings to resolve human-readable movie titles (preserved verbatim, unjoined).
- No diff against any prior HF dataset revision to independently verify the changelog's claims beyond what the changelog itself states.
