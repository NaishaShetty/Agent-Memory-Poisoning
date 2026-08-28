# Identity Verification — MemoryArena

**Outcome: CONFIRMED MATCH.** This candidate is the genuine `ZexueHe/MemoryArena` project
associated with the paper "MemoryArena: Benchmarking Agent Memory in Interdependent
Multi-Session Agentic Tasks" (arXiv:2602.16313). It is NOT the unrelated
`xmpuspus/memory-arena` project.

## Checks performed and evidence

### (a) arXiv paper title/abstract match

Fetched `https://arxiv.org/abs/2602.16313` directly (`curl -s -L`).

- `<title>` tag (verbatim): `[2602.16313] MemoryArena: Benchmarking Agent Memory in
  Interdependent Multi-Session Agentic Tasks`
- `og:title` meta (verbatim): `MemoryArena: Benchmarking Agent Memory in Interdependent
  Multi-Session Agentic Tasks`
- Abstract meta description (verbatim, truncated at ~700 chars as returned by curl):
  "Existing evaluations of agents with memory typically assess memorization and action in
  isolation. One class of benchmarks evaluates memorization by testing recall of past
  conversations or text but fails to capture how memory is used to guide future decisions.
  Another class focuses on agents acting in single-session tasks without the need for
  long-term memory. However, in realistic settings, memorization and action are tightly
  coupled: agents acquire memory while interacting with the environment, and subsequently
  rely on that memory to so[...]" — this is exactly the "interdependent multi-session
  agentic tasks" framing named in the task brief, not a coincidental title match.
- Authors listed on the abstract page: Zexue He, Yu Wang, Churan Zhi, Yuanzhe Hu,
  Tzu-Ping Chen, Lang Yin, Ze Chen, Tong Arthur Wu, Siru Ouyang, Zihan Wang, Jiaxin Pei,
  Julian McAuley, Yejin Choi, Alex Pentland.
- License link on the abstract page: `http://arxiv.org/licenses/nonexclusive-distrib/1.0/`
  (arXiv's non-exclusive distribution license for the paper itself — separate from the
  dataset's own CC-BY-4.0 license, see below).

### (b) GitHub repo exists, non-empty, matches

- `curl -s -L -o /dev/null -w "%{http_code}"` against `https://github.com/ZexueHe/MemoryArena`
  returned `200`.
- GitHub API (`https://api.github.com/repos/ZexueHe/MemoryArena`) confirms
  `full_name: "ZexueHe/MemoryArena"`, `private: false`, `fork: false`.
- Shallow-cloned (`git clone --depth 1`) into `raw/` successfully; 203 tracked files,
  non-empty (README, `agent/`, `env/`, `memory/`, `configs/` subtrees all present — see
  `source/README.md` for the full structure).
- The repo's own `README.md` (verbatim excerpt): "Implementation for **MemoryArena:
  Benchmarking Agent Memory in Interdependent Multi-Session Agentic Tasks**
  (https://arxiv.org/abs/2602.16313)." — the README explicitly names and links the exact
  arXiv ID given in this task, and its citation block is:

  ```bibtex
  @article{he2026memoryarena,
    title={MemoryArena: Benchmarking Agent Memory in Interdependent Multi-Session Agentic Tasks},
    author={He, Zexue and Wang, Yu and Zhi, Churan and Hu, Yuanzhe and Chen, Tzu-Ping and Yin, Lang and Chen, Ze and Wu, Tong Arthur and Ouyang, Siru and Wang, Zihan and others},
    journal={arXiv preprint arXiv:2602.16313},
    year={2026}
  }
  ```

  This citation's author list, title, and arXiv ID are an exact match to the arXiv abstract
  page fetched in step (a) (the repo's "and others" elides the last three authors —
  Jiaxin Pei, Julian McAuley, Yejin Choi, Alex Pentland — but the first ten listed match
  verbatim and in the same order).

### (c) Not the unrelated `xmpuspus/memory-arena` project

The repo cloned is `ZexueHe/MemoryArena` (owner `ZexueHe`, GitHub user id 36160549), not
`xmpuspus/memory-arena`. No content from `xmpuspus/memory-arena` was fetched, referenced,
or used anywhere in this candidate package.

### Additional corroboration: HuggingFace dataset

The repo's task-config JSON files (e.g. `configs/formal_reasoning_configs/math_task.json`)
reference `"hf_dataset": "ZexueHe/memoryarena"`. Querying
`https://huggingface.co/api/datasets/ZexueHe/memoryarena` returned a dataset card whose
`tags` include `"arxiv:2602.16313"` (an exact-match, machine-readable tag independently
linking the HF dataset back to the same arXiv ID) and whose citation block is byte-identical
to the GitHub README's citation block above. This is a third independent source (beyond the
arXiv page and the GitHub README) confirming the same paper/repo/dataset triple.

## Conclusion

All three identity-verification gates in the task brief are satisfied: (a) paper
title/abstract genuinely describes MemoryArena as specified, (b) GitHub repo exists,
is non-empty, and its README/citation match the same paper, (c) confirmed distinct from
`xmpuspus/memory-arena`. Proceeding with full candidate preparation.
