# Source Audit — MemoryArena

## Identity

- **Official name:** MemoryArena
- **GitHub URL:** https://github.com/ZexueHe/MemoryArena
- **Cloned commit hash:** `6cd9de14b71915e39ac742a20dc33785e14b6aab` (`git log -1 --format=%H`,
  captured in `raw/` after `git clone --depth 1`)
- **Commit date:** `2026-05-31T20:10:42-04:00` (`git log -1 --format=%cI`)
- **Paper:** "MemoryArena: Benchmarking Agent Memory in Interdependent Multi-Session
  Agentic Tasks", arXiv:2602.16313 (https://arxiv.org/abs/2602.16313)
- **Authors:** Zexue He, Yu Wang, Churan Zhi, Yuanzhe Hu, Tzu-Ping Chen, Lang Yin, Ze Chen,
  Tong Arthur Wu, Siru Ouyang, Zihan Wang, Jiaxin Pei, Julian McAuley, Yejin Choi,
  Alex Pentland.
- See `source/identity_verification.md` for the full identity-verification evidence trail.

## License

- **Code repo (`ZexueHe/MemoryArena` on GitHub):** no `LICENSE` file was found anywhere in
  the cloned tree (`find . -iname "licen*"` returned no matches). The repo's README does
  not state a code license either. **Code license status: UNKNOWN / NOT STATED BY SOURCE.**
- **Dataset (`ZexueHe/memoryarena` on HuggingFace):** the dataset card's README explicitly
  states: "This dataset is licensed under the Creative Commons Attribution 4.0
  International (CC-BY-4.0) license." — this is the license that actually governs the
  `data.jsonl` files used for this candidate's task/answer content.
- **arXiv paper itself:** distributed under arXiv's non-exclusive distribution license
  (`http://arxiv.org/licenses/nonexclusive-distrib/1.0/`), separate from the code/dataset
  licenses above.

## Download mechanism

Two separate download steps were required, because the GitHub repo is a *framework*
(agent/environment/memory harness code) and does not itself contain the task data:

1. `git clone --depth 1 https://github.com/ZexueHe/MemoryArena.git` into `raw/` (the repo
   root; 203 tracked files under `.git`-excluded paths).
2. The repo's own task-config JSON files (e.g.
   `configs/formal_reasoning_configs/math_task.json`) point to
   `"hf_dataset": "ZexueHe/memoryarena"` on HuggingFace. The actual task/answer data was
   downloaded via `curl` (no HF token, no `datasets` library, no execution) from
   `https://huggingface.co/datasets/ZexueHe/memoryarena/resolve/main/<config>/data.jsonl`
   for all five published configs, into `raw/hf_dataset/`.

No further external hosting (Google Drive, S3, etc.) is referenced by the repo's README
for the *task/answer* data itself. Some environment-specific auxiliary data IS referenced
but was NOT downloaded (see "Limitations / not obtained" below) because obtaining it would
require running scripts, API keys, or executing code, all out of scope for this
data-only, no-execution candidate-preparation task.

## Size

- GitHub repo clone: 203 files (excluding `.git/`), ~11.2 MB.
- HuggingFace dataset (`hf_dataset/`): 5 JSONL files + 1 README, ~12.3 MB combined,
  681 task records total across all 5 configs.
- Combined `raw/` directory: 211 files, ~17.4 MB (`du -sb`).

## File formats

- Code: Python (`.py`), Markdown setup guides (`.md`), JSON task-run configs (`.json`),
  CSV reference data for the travel-planner environment (`.csv`), a small number of
  `.gitignore`/`.txt`/`.yml` files.
- Task data (the actual MAMBench-relevant artifact): JSON Lines (`.jsonl`), one JSON object
  per line, UTF-8, no compression.

## Repo structure (top level)

```
agent/    - task agent implementations (base_agent.py, math.py, search.py, travel_planner.py, webshop.py)
env/      - environment server/client + env_systems/ (per-task-type environment implementations:
            formal_reasoning_env, travel_planner_env (with a bundled CSV database of
            flights/hotels/restaurants/attractions), web_search_env (corpus + embedding-index
            build scripts), a webshop-style shopping environment)
memory/   - memory client/server harness supporting long-context, Letta, Mirix, Mem0/Mem0-g,
            ReasoningBank, BM25, text-embedding RAG, GraphRAG, MemoRAG as pluggable backends
configs/  - per-task-type run configs (formal_reasoning_configs/, travel_planner_configs/,
            web_search_configs/, web_shopping_configs/) — each config wires one memory
            backend to one task type; these are agent-run configuration, NOT the task
            data itself
```

## Task/environment/memory structure (as described in repo + HF dataset READMEs)

MemoryArena's premise (per both the paper abstract and the repo README) is that
**memorization and action are coupled**: an agent interacts with an environment across
multiple sessions/subtasks, must acquire memory from earlier interaction, and is then
scored on whether it correctly *uses* that memory in later, dependent subtasks — not
merely on whether it can recall isolated facts. The repo's own "Example Flow" (verbatim
from README): "1. Task prompt -> memory wraps prompt. 2. Agent generates action. 3. Env
`step()` executes tool or accepts final. 4. Observation + reward returned. 5. Memory stores
action/observation/reward(optional)."

The actual benchmark data (HuggingFace `ZexueHe/memoryarena`) is organized as five
**task-type configs**, each a JSONL file of "agentic task" records. Each record bundles a
whole **chain of interdependent subtasks** (its own `questions`/`answers` lists) that must
be solved *in order*, with later subtasks depending on context established by earlier ones
within the same record — this is the "interdependent multi-session" structure named in the
paper title, represented natively as one JSON object per task chain rather than as
independent flat QA rows. See `reports/raw_inventory.md` for the exact field-by-field
breakdown of all five configs.

## Documented revisions / limitations (as stated by the source itself)

- The GitHub README states explicitly: *"This code is preview version. We are still
  actively maintaining and improving this codebase."* — the source itself flags this as a
  preview/non-final release.
- No `CHANGELOG`, version tag, or release was found in the shallow clone (depth 1); no
  claim is made here about prior revisions since none are visible from a depth-1 clone.
- The HuggingFace dataset's `lastModified` (per the HF API) is `2026-03-03T00:39:50Z`,
  `createdAt` is `2026-02-22T08:08:44Z`, and `sha` (HF dataset repo commit) is
  `da1a37c8b19280e18627ca01cf368195a5e1d92e` — recorded here as the dataset's own
  source_revision, distinct from the GitHub code commit hash above.

## Not obtained (explicit limitation, not fabricated)

- `env/env_systems/web_search_env/` references a `download_embeddings_from_hf.py` script
  and `decrypt_dataset.py` for an encrypted corpus/embedding index — these require running
  Python code and are out of scope for this no-execution candidate-preparation task; the
  underlying corpus text referenced by `progressive_search`/web-search environment configs
  was NOT independently downloaded or decrypted. The `progressive_search` **task
  questions/answers themselves** (from the HF `ZexueHe/memoryarena` dataset) WERE obtained
  in full; only the background retrieval *corpus* the environment would search over at
  execution time was not.
- `env/env_systems/travel_planner_env/database/` (flights/hotels/restaurants/attractions
  CSVs) WAS obtained via the GitHub clone itself (bundled directly in the repo, no separate
  download needed).
- No model, embedding, or vector-DB code from `memory/memory_systems/` was executed,
  instantiated, or inspected beyond reading file names/structure — per the "no model
  integration" rule for this task.
