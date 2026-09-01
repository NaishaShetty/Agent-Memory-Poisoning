# Phase 3.3-B.0 — Local LLM Hardware + Model Feasibility Gate

**Status:** PRE-IMPLEMENTATION FEASIBILITY GATE. No agent, memory foundation, evaluator,
metric, or dataset code touched. Phase 3.3-A specification unmodified.

## Verdict

**PASS_WITH_LIMITATIONS**

Qwen3-8B in a 4-bit GGUF quantization (Q4_K_M) runs reliably on this machine's RTX 4050
laptop GPU — correctly, deterministically, without OOM, up to and including a
16K-token context window stress-tested with a real ~12K-token prompt. It is not an
unqualified PASS because VRAM headroom is genuinely thin (~4.8% free at 16K context)
and the only backend that actually works reliably on this CPU is the official
llama.cpp release binary driven over HTTP — the pip-installable `llama-cpp-python`
Python bindings crash unconditionally on this CPU. Both limitations are load-bearing
for how 3.3-B must be built and are detailed below, not glossed over.

## Hardware

Directly inspected, not assumed:

| Property | Value |
|---|---|
| GPU | NVIDIA GeForce RTX 4050 Laptop GPU |
| VRAM | 6141 MiB (~6 GB) total |
| GPU compute capability | 8.9 (Ada Lovelace) |
| GPU driver version | 610.88 (nvidia-smi) / 32.0.16.1088 (Windows driver store) |
| CUDA UMD (driver-reported) | 13.3 |
| CUDA runtime actually used | 12.4 (via pip `nvidia-cuda-runtime-cu12==12.4.127` / `nvidia-cublas-cu12==12.4.5.8`, and via the official llama.cpp `cudart-llama-bin-win-cuda-12.4-x64.zip` redistributable) |
| Secondary GPU | Intel UHD Graphics (integrated, not used) |
| CPU | 13th Gen Intel Core i7-13620H, 10 cores / 16 logical processors, 2.4 GHz base |
| RAM | 16,387,276 KB (~15.6 GB) total |
| OS | Windows 11 Home, 64-bit |
| Python (main project env) | 3.11.3 |
| PyTorch (main project env) | 2.12.0+cpu (CPU-only build; **not** used for this feasibility work — see Backend Decision) |
| Free disk space (C:) | 531 GB of 925 GB |

**Critical hardware constraint:** 6 GB VRAM is small for an 8B model even at 4-bit
quantization. This shaped every subsequent decision in this gate.

## Qwen3-8B

- **Model identifier:** `Qwen/Qwen3-8B-GGUF` (official Qwen organization repo on
  Hugging Face)
- **File:** `Qwen3-8B-Q4_K_M.gguf`
- **Repo revision (commit SHA):** `7c41481f57cb95916b40956ab2f0b139b296d974`
- **Quantization:** Q4_K_M (GGUF, llama.cpp's standard mixed 4-bit/6-bit-per-tensor
  scheme, the conventional referent of "4-bit quantized" for GGUF models)
- **File size:** 5,027,783,488 bytes (~4.68 GiB), verified via `HfApi.model_info` against
  the actual downloaded file size (exact match)
- **File SHA-256:** `d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785`
  — computed locally on the downloaded file and confirmed identical to the SHA-256 in
  the repo's Git-LFS pointer metadata (`BlobLfsInfo.sha256`) for that file. Not an
  unofficial or modified artifact.
- **Native training context:** 40,960 tokens (`n_ctx_train`, printed by llama.cpp at
  load) — 3.3-A's planned contexts (Part 3, Part 5 of the experimental spec) are well
  within this.
- **Backend:** official llama.cpp release binary `b10717` (commit `a32af33de`),
  `win-cuda-12.4-x64` build, driven via `llama-server.exe`'s OpenAI-compatible
  `/v1/chat/completions` HTTP endpoint (see Backend Decision).
- **Load result:** SUCCESS (with the official binary; FAILURE with the pip wheel — see
  below). 37/37 layers offloaded to GPU (`-ngl 99`). Load time consistently ~4-5
  seconds across all context sizes tested.
- **VRAM:** 4933 MiB at n_ctx=2048 up to 5849 MiB at n_ctx=16384 (see Resource Profile).
  At 16384, only ~292 MiB of the 6141 MiB total remains free (~4.8% headroom).
- **RAM:** `llama-server.exe` working set ~5.3 GB at 16K context (includes
  memory-mapped model file pages, not all of it exclusively-owned heap).
- **Latency:** sub-second to a few seconds for short prompts (0.17-0.5s at low context
  for a 3-token ping; 1.2-8.3s for realistic ~20-200 token completions). For a
  near-full-context real prompt (12,282 tokens at n_ctx=16384), a single request took
  2 minutes 17 seconds end to end — this is the dominant cost driver for MAMBench's
  planned experiment matrix and must be budgeted for explicitly (see Remaining
  Limitations).
- **Context results:** see Resource Profile table below. No failure or degradation
  observed at any tested size, including a genuine 12,282-token filled prompt (not
  just an allocation test) at n_ctx=16384.
- **Stability:** stable and reliable **only** via the official llama.cpp binary.
  Confirmed FAIL for the pip `llama-cpp-python` wheel (see Backend Decision) — this is
  reported as a defect of that specific distribution channel on this CPU, not of
  Qwen3-8B or of llama.cpp itself.
- **Reproducibility:** identical output across 3 repeated runs of the same prompt with
  fixed `seed=42, temperature=0` within one server session (see Reproducibility below
  for what this does and does not establish).

## Qwen3-4B

**Not evaluated.** Per the mission's Test 10 trigger condition ("Only if Qwen3-8B is
not practical"), the 4B fallback is only exercised when 8B fails the practicality bar
entirely. Qwen3-8B was classified `PASS_WITH_LIMITATIONS`, not `FAIL` — it is
genuinely practical, with documented constraints that do not block Phase 3.3-B. Per
the mission's explicit instruction not to "automatically select the smaller model
simply because it is faster," and per "the objective is the strongest model that is
genuinely practical," 4B was not downloaded or tested.

## Backend Decision

**Chosen: the official llama.cpp release binary (`ggml-org/llama.cpp` GitHub
releases, Windows CUDA 12.4 build), driven via its built-in OpenAI-compatible HTTP
server (`llama-server.exe`), not the `llama-cpp-python` pip package.**

This was not the first choice — it is the result of a documented, evidence-driven
pivot:

1. `llama-cpp-python` 0.3.35 was already present in the main project environment (CPU
   build only, no GPU offload support). A CUDA-enabled build was installed into a
   fresh isolated venv from `https://abetlen.github.io/llama-cpp-python/whl/cu124`.
2. That wheel's `ggml-cuda.dll` initially failed to load at all — Windows could not
   resolve its CUDA runtime dependencies (`cudart64_12.dll`, `cublas64_12.dll`,
   `cublasLt64_12.dll`), because this machine has an NVIDIA driver but no CUDA Toolkit
   installed. This was fixed by installing the pip-redistributed runtime packages
   (`nvidia-cuda-runtime-cu12==12.4.127`, `nvidia-cublas-cu12==12.4.5.8`) into the venv
   and adding their `bin/` directories to the Windows DLL search path and `PATH`
   before import (llama_cpp's own loader only auto-adds these via a `CUDA_PATH`
   environment variable, which was not set) — see
   `C:\Users\naish\mambench_llm_feasibility\scripts\_env_setup.py`.
3. With CUDA loading fixed, `Llama(...)` from that wheel **crashed unconditionally**
   during `llama_context` construction with `OSError(22, 'Windows Error 0xc000001d', ...)`
   — `STATUS_ILLEGAL_INSTRUCTION`. This reproduced identically with full GPU offload
   (`n_gpu_layers=-1`) and with GPU offload fully disabled (`n_gpu_layers=0`), and at
   every context size tried (1024, 2048, 16384) — ruling out a CUDA-specific or
   context-size-specific cause and pointing at the CPU backend specifically. The
   wheel ships a single `ggml-cpu.dll` with no runtime CPU-feature dispatch. The
   working hypothesis is an instruction-set mismatch (most likely an AVX-512-family
   instruction) against this CPU: 13th-gen Intel H-series (Raptor Lake, hybrid
   P-core/E-core) has AVX-512 disabled in hardware/microcode across the product line.
4. No C/C++ compiler (MSVC `cl.exe`, GCC, or Clang) is present on this machine, so
   rebuilding `llama-cpp-python` from source with `GGML_AVX512=OFF` was not a viable
   local fix without a large additional toolchain install.
5. The user was asked and approved switching to the official `ggml-org/llama.cpp`
   GitHub release binaries instead. That release (build `b10717`, `win-cuda-12.4-x64`)
   ships **multiple** CPU backend DLLs
   (`ggml-cpu-alderlake.dll`, `ggml-cpu-icelake.dll`, `ggml-cpu-sapphirerapids.dll`,
   `ggml-cpu-skylakex.dll`, `ggml-cpu-x64.dll`, etc.) with genuine runtime CPU-feature
   detection (`GGML_CPU_ALL_VARIANTS`), which correctly avoids the unsupported
   instruction set on this CPU. It loaded and ran without any crash on the first
   attempt.

**Why this remains the simplest technically defensible choice, not scope creep:** it
is a single official upstream artifact (not a third-party wheel, not an additional
inference framework), requires no compiler installation, and its HTTP server exposes
an OpenAI-compatible `/v1/chat/completions` API — the same interface shape Phase
3.3-A's `LLMProvider` abstraction (Part 4) is designed to wrap regardless of which
concrete provider backs it. Transformers + bitsandbytes was not pursued: bitsandbytes'
8-bit/4-bit quantized inference on Windows has materially weaker driver/toolchain
support than GGUF/llama.cpp, and would not obviously have avoided a similar
CPU-dispatch class of issue while adding a much heavier dependency footprint (full
`transformers` + `accelerate` + `bitsandbytes` stack) for a 6 GB VRAM budget that GGUF
partial/full offload handles more gracefully.

**Consequence for 3.3-B:** the `LLMProvider.generate()` implementation for this
backend must be an HTTP client against a running `llama-server.exe` process (or must
shell out to `llama-cli.exe` for a one-shot call), not a `llama_cpp.Llama(...)` Python
binding. This is a concrete, load-bearing design constraint for the next stage, not a
detail to silently work around later.

## Resource Profile

| Measurement | Qwen3-8B Q4_K_M (llama.cpp b10717, CUDA 12.4, `-ngl 99`) |
|---|---|
| Model file size | 5,027,783,488 bytes (~4.68 GiB) |
| Peak VRAM (idle, n_ctx=16384) | 5849 MiB / 6141 MiB total (~95.2% used, ~292 MiB free) |
| Peak VRAM (n_ctx=2048) | 4933 MiB |
| Peak VRAM (n_ctx=4096) | 5223 MiB |
| Peak VRAM (n_ctx=8192) | 5803 MiB |
| Peak VRAM (n_ctx=16384) | 5843-5849 MiB (idle and post-generation, both context-allocation-dominated) |
| RAM (server working set, n_ctx=16384) | ~5.3 GB (includes mmap'd model pages) |
| Load time | ~4-5 s, consistent across all tested context sizes |
| 2K latency (3-token ping) | 0.496 s |
| 4K latency (3-token ping) | 0.176 s |
| 8K latency (3-token ping) | 0.167 s |
| 16K latency (3-token ping, empty context) | 0.314 s |
| 16K latency (real ~12,282-token filled prompt) | 137.18 s total (prompt processing dominated) |
| Generation throughput | 26.32 tokens/sec (measured, `enable_thinking:false` off; llama.cpp-reported `predicted_per_second`) |
| Prompt-processing throughput | ~75-90 tokens/sec (varies with context fill; llama.cpp-reported `prompt_per_second`) |
| OOM? | No — not at any tested context size, including the 12,282-real-token stress test |
| Stable? | Yes, on the official llama.cpp binary. **No**, on the `llama-cpp-python` pip wheel (illegal-instruction crash, documented above) |

## Chinese Sanity Check

Runtime result only — **not** a benchmark-level Chinese-capability claim, and PerLTQA
was not touched, translated, or preprocessed.

Prompt: `请用一句话介绍北京。` ("Introduce Beijing in one sentence.")

Output (with `enable_thinking:false`, `temperature=0`, `seed=42`):
> 北京是中华人民共和国的首都，拥有悠久的历史和丰富的文化遗产，同时也是现代化的国际大都市。

Coherent, on-topic, grammatical Chinese output, produced in 1.24 s (22 completion
tokens). One earlier attempt at this same test produced an incoherent English
non-answer — root-caused to a shell/UTF-8 quoting artifact in how the prompt was
passed via an inline `curl -d` argument in the sandboxed Bash tool, not a model
limitation; the retest via a UTF-8-encoded JSON file payload succeeded cleanly and
was reproduced identically across repeated runs (see Reproducibility). This is
recorded here as a caution for 3.3-B: any HTTP client implementation of `LLMProvider`
must send request bodies as UTF-8-encoded file/stream payloads or an equivalent
encoding-safe method, not raw inline shell-interpolated strings, when non-ASCII
content (e.g. PerLTQA zh) is involved.

A synthetic memory-style prompt (retrieved-memory citations, per Test 6) was also run
as a runtime sanity check only: given three labeled synthetic memories and a question,
the model correctly identified the relevant two, answered correctly, and cited their
memory IDs in brackets as instructed. This is not a benchmark result and no MAMBench
dataset content was used.

## Reproducibility

- **Seed control:** supported (`seed` parameter, llama.cpp's own RNG). Confirmed to
  produce byte-identical output text across 3 repeated identical requests
  (`temperature=0, seed=42`) within one running server process, for both an English
  and a Chinese prompt.
- **What this does NOT establish:** bit-for-bit determinism across process restarts,
  across different `-ngl`/batch-size configurations, across GPU driver versions, or
  across hardware, was not tested and is not claimed. Floating-point non-associativity
  in GPU-accelerated matrix operations is a known general source of run-to-run drift
  in llama.cpp/GGML across configuration changes even with a fixed seed; per Phase
  3.3-A's `REPRODUCIBILITY_CONTRACT.md`-aligned position (Part 5 of the experimental
  spec), no claim beyond "deterministic within a held-fixed session/configuration, as
  observed here" is made.
- **Must be recorded per run** to make results attributable later (per Part 33 of the
  3.3-A spec): repo revision `7c41481f57cb95916b40956ab2f0b139b296d974`, file SHA-256
  `d98cdcbd...5745785`, llama.cpp build `b10717` / commit `a32af33de` (both reported
  by the server as `system_fingerprint: "b10717-a32af33de"` on every response — a
  ready-made configuration-fingerprint input), `-ngl` value, `-c` (context) value,
  `temperature`, `seed`, and the `enable_thinking` flag (see below — this materially
  changes output shape and is easy to omit by accident).
- **Thinking-mode caveat (new finding, not anticipated in the 3.3-A spec):** Qwen3
  defaults to an internal "thinking" / chain-of-thought mode that can consume an
  entire `max_tokens` budget without producing any final answer content
  (`finish_reason: "length"`, empty `content`, all budget spent on
  `reasoning_content`) unless explicitly disabled via
  `chat_template_kwargs: {"enable_thinking": false}` in the request. This must become
  an explicit, recorded, controlled variable in 3.3-B's `LLMProvider` configuration
  (alongside temperature/seed/max_tokens in Part 3 of the 3.3-A spec's controlled-variable
  list) — silently leaving it at its default would silently degrade or corrupt every
  MAMBench experiment that expects a direct answer within a bounded token budget.

## Phase 3.3-A Compatibility

Confirmed that the chosen (model, backend) pair can implement the frozen `LLMProvider`
interface (Part 4 of `PHASE3_3_EXPERIMENTAL_SPEC.md`) without leaking backend detail
to the agent or evaluator — **not implemented in this gate**, only confirmed feasible:

- `generate(messages, config)` → `POST /v1/chat/completions` against `llama-server.exe`,
  with `config` mapping to `{temperature, seed, max_tokens, chat_template_kwargs:
  {enable_thinking}}`. Returns text + usage/timing metadata, matching the interface's
  required return shape.
- `model_metadata()` → a plain struct assembled from data already gathered in this
  gate: `{repo_id: "Qwen/Qwen3-8B-GGUF", file: "Qwen3-8B-Q4_K_M.gguf", repo_revision:
  "7c41481f...", file_sha256: "d98cdcbd...", quantization: "Q4_K_M", llama_cpp_build:
  "b10717", llama_cpp_commit: "a32af33de"}` — no HTTP client, CUDA, or DLL-loading
  detail included.
- `configuration_fingerprint()` → a stable hash over the decoding config plus the
  server's own `system_fingerprint` field (`"b10717-a32af33de"`), which llama-server
  already returns on every response — a convenient, already-available input.

No provider/backend-specific detail (HTTP endpoint, DLL search-path workaround,
process-launch mechanics) needs to cross this boundary; all of it stays inside the
concrete `LLMProvider` implementation to be written in 3.3-B.

## Phase 3.3-B Readiness

**Ready, with three concrete constraints 3.3-B must build around, not around which it
can casually design:**

1. The `LLMProvider` implementation must talk to `llama-server.exe` over HTTP (or
   shell out per-call to `llama-cli.exe`), not use the `llama-cpp-python` Python
   bindings — that path is confirmed broken on this CPU.
2. `enable_thinking` must be a first-class, recorded configuration field, defaulted
   explicitly (not left to the backend's own default) for every 3.3 experiment.
3. VRAM headroom at the tested 16K context is ~4.8% — Phase 3.3-B's pilot (Part 22 of
   the experimental spec) should re-verify this headroom holds under whatever
   concurrent load a real agent loop adds (e.g. an embedding model for a memory
   foundation running alongside the LLM on the same GPU) before assuming it is safe
   for the full campaign matrix.

## Repository Integrity

Protected surfaces checked and confirmed untouched by this gate:

- Phase 3.2 evaluator, metrics, datasets, dataset adapters, foundations, foundation
  adapters — untouched (no files under `phase3/evaluation/`, `phase3/datasets/` were
  modified)
- `phase3/specification/PHASE3_3_EXPERIMENTAL_SPEC.md` — untouched
- Canonical contracts (`phase3/contracts/*.md`) — untouched
- All model weights, the isolated venv, and the llama.cpp binaries were placed at
  `C:\Users\naish\mambench_llm_feasibility\` — **entirely outside** the
  `C:\Agent Memory Poisoning` git repository, so no `.gitignore` entry was even
  necessary; nothing there can be accidentally staged or committed from within this
  repo.

This stage adds exactly one new file inside the repository:
`phase3/specification/PHASE3_3_B0_LLM_FEASIBILITY.md`.

## Tests

```
python -m pytest phase3/evaluation/tests/ -q            → 990 passed, 3 skipped
python -m pytest phase3/evaluation/tests/ -q             → 990 passed, 3 skipped   (2nd run, identical)
python -m pytest phase3/evaluation/tests/ -q -W error    → 990 passed, 3 skipped
```

Identical to the Phase 3.2-I / 3.3-A baseline (same 3 skips: real Mem0/Graphiti/A-MEM
library conformance tests that only run in the isolated `C:\h4venv`, unrelated to this
gate). No regression.

## Files Created

Inside the repository:
- [phase3/specification/PHASE3_3_B0_LLM_FEASIBILITY.md](phase3/specification/PHASE3_3_B0_LLM_FEASIBILITY.md)

Outside the repository (feasibility scratch area, `C:\Users\naish\mambench_llm_feasibility\`):
- `venv\` — isolated Python 3.11 venv (huggingface_hub, psutil, and an abandoned
  CUDA `llama-cpp-python` install kept only as a documented negative result)
- `models\Qwen3-8B-Q4_K_M.gguf` (4.68 GiB) + `models\sha256sum.txt`
- `llama_cpp_binary\bin\` — extracted official llama.cpp `b10717` win-cuda-12.4-x64
  release + cudart redistributable
- `scripts\_env_setup.py`, `scripts\test_load_and_generate.py`,
  `scripts\test_context_sweep.py`, `scripts\make_long_ctx_payload.py`
- `results\*.json`, `results\*.log` — raw test outputs from this gate

## Files Modified

None inside the repository.

## Remaining Limitations

Explicit, carried forward into 3.3-B:

1. **VRAM headroom is thin (~4.8% free at 16K context).** Not re-tested under
   concurrent GPU load from a memory foundation's own embedding/extraction model
   (e.g. Mem0's internal LLM calls) running alongside the reasoning LLM on the same
   6 GB card — this is a real risk for Phase 3.3-B's pilot and must be verified there,
   not assumed safe by extrapolation from this gate's LLM-only tests.
2. **Long-context latency is substantial.** ~2m17s for a single 12,282-token prompt
   pass. Phase 3.3-A's experiment matrix (Part 21) and repetition strategy (Part 23,
   N=3 initial) must budget wall-clock time accordingly, especially for
   LongMemEval-scale contexts — this was not previously quantified and materially
   affects campaign planning.
3. **The pip `llama-cpp-python` CUDA wheel is confirmed broken on this CPU class**
   (illegal-instruction crash, root-caused to CPU-dispatch, not fixed by any tested
   workaround short of switching binaries entirely). This is a durable environment
   fact, not a one-off flake — any future attempt to use that Python-binding path on
   this or a similarly-configured (12th/13th-gen hybrid Intel) machine should expect
   the same failure.
4. **`enable_thinking` default behavior is a trap.** Left at its default, Qwen3 can
   silently consume an entire generation budget on chain-of-thought with zero final
   answer. This must be a hard-coded, explicit, recorded default in 3.3-B, not an
   implicit backend default relied upon.
5. **Determinism was only verified within one live server session.** Cross-session,
   cross-restart, or cross-configuration determinism was not tested and per Phase
   3.3-A's `REPRODUCIBILITY_CONTRACT.md`-aligned stance, is not claimed.
6. **Qwen3-4B was not evaluated** (Test 10 not triggered, per the mission's own
   decision rule) — if a future stage finds the 8B VRAM headroom or latency
   unworkable under real agent-loop conditions, the 4B feasibility tests remain an
   open, well-scoped fallback investigation, not yet performed.
