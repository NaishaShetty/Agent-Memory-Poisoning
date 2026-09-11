# Phase 4.11 — Phase 4 Reproducibility

Status: **DONE (2026-09-11); updated 2026-09-11 — both Section 7 gaps
closed with real work, not just re-labeled.** Consolidates, in one place,
everything needed to re-run any real result produced across Phase 4's
seven attacks — environment setup, the exact recipe every real campaign
script in this project follows, a full table of every real entry-point
script with its environment requirements and persisted output, and the
determinism/non-determinism boundaries actually observed. This document
does not introduce new mechanism; it is a reference built by direct
inspection of every real script's own imports (verified via `grep`, not
assumed) and the persisted `.txt` logs already sitting next to each script.

## 1. Environment Prerequisites

| Requirement | Detail |
|---|---|
| Main Python interpreter | Used for all pure-logic code: math/optimization libraries (AgentPoison's `core.py`, DSRM's `white_box.py`), unit tests (`phase4/tests/`), and any script that touches a real LLM but NOT `mem0ai` |
| Isolated interpreter — `C:\h4venv` | Required whenever `RealMem0Adapter` OR `RealAMemAdapter` is imported (`mem0ai` and the cloned `a-mem-sys` checkout are both only available there) — confirmed by every attack's own campaign script docstring and by direct `grep` across all seven attack packages (Section 3 below) |
| Real LLM server | `C:\Users\naish\mambench_llm_feasibility\llama_cpp_binary\bin\llama-server.exe`, model `C:\Users\naish\mambench_llm_feasibility\models\Qwen3-8B-Q4_K_M.gguf` (pinned build b10717, commit a32af33de — verified via `LlamaServerProvider.verify_server_identity()` at the start of every real campaign script that needs one, never skipped) |
| Standard launch command | `llama-server.exe --host 127.0.0.1 --port 8811 -ngl 99 --ctx-size 16384 --parallel 4 --model <model path>` — identical across all seven attacks' real runs, never varied |
| Real LoCoMo data | `data/raw/locomo/locomo10.json` — task 0 (Caroline/Melanie) used by every attack in this project, for cross-attack content consistency (deliberate, not incidental) |

## 2. The Standard Recipe (identical across all seven attacks)

Every real campaign/dry-run script in this project follows the same four
steps, confirmed by direct inspection, not merely described once and
assumed to generalize:

1. **Launch the server** (background), then poll `GET /health` until
   `{"status":"ok"}` — never assumed ready immediately (the model load
   step takes several polling cycles in every real run observed this
   session).
2. **Run the script** under the correct interpreter (Section 3's table
   says which) — scripts requiring `RealMem0Adapter` run under
   `C:\h4venv\Scripts\python.exe -m <module>`; scripts that only need the
   LLM server (or neither) run under the main interpreter's
   `python -m <module>`.
3. **Redirect output to a `.txt` log**, then copy it into the attack's
   own package directory under a `_run_2026-09-11*.txt`-style name —
   every real result cited anywhere in Phase 4's documentation traces
   back to one of these persisted files, never to an unlogged run.
4. **Stop the server** (`taskkill //F //IM llama-server.exe`) before
   moving to the next attack, to avoid port/GPU-memory contention across
   sequential campaigns.

## 3. Every Real Entry-Point Script

Confirmed via `grep -rl '__name__ == "__main__"' phase4/attacks` — this
is the complete list, not a curated subset:

| Script | Needs `C:\h4venv`? | Needs live LLM server? | Persisted output |
|---|---|---|---|
| `agentpoison/core.py` | No | No | (internal smoke check only) |
| `agentpoison/milestone2_smoke_test.py` | No | No (local embedder only) | `agentpoison/milestone2_smoke_test_run_2026-09-11.txt` |
| `agentpoison/trigger_run.py` | No | No (local embedder only) | `agentpoison/milestone4_artifact_2026-09-11.json`, `..._v2.json` |
| `agentpoison/milestone5_campaign.py` | **Yes** | **Yes** | `agentpoison/milestone5_campaign_run_2026-09-11.txt` |
| `farma/dry_run_milestone2.py` | **Yes** | No | `farma/milestone2_dry_run_2026-09-11.txt` |
| `farma/dry_run_milestone3.py` | **Yes** | No | `farma/milestone3_dry_run_2026-09-11.txt` |
| `farma/dry_run_milestone4.py` | **Yes** | No | `farma/milestone4_dry_run_2026-09-11.txt` |
| `farma/milestone5_campaign.py` | **Yes** | **Yes** | `farma/milestone5_campaign_run_2026-09-11.txt` |
| `farma/dry_run_milestone6_store_evasion.py` | **Yes** | No | `farma/milestone6_store_evasion_run_2026-09-11.txt` |
| `farma/dry_run_milestone6_adaptive_paraphrase.py` | **Yes** | **Yes** | `farma/milestone6_adaptive_paraphrase_run_2026-09-11.txt` |
| `minja/dry_run_milestone3.py` | No | No | `minja/milestone3_dry_run_2026-09-11.txt` |
| `minja/milestone4_campaign.py` | **Yes** | **Yes** | `minja/milestone4_campaign_run_2026-09-11.txt` |
| `memorygraft/calibrate_gate.py` | No | **Yes** | `memorygraft/calibration_run_2026-09-11.txt`, `..._v2.txt` |
| `memorygraft/test_gate_foolability.py` | No | **Yes** | `memorygraft/foolability_run_2026-09-11.txt` |
| `memorygraft/test_gate_format_laundering.py` | No | **Yes** | `memorygraft/format_laundering_run_2026-09-11.txt` |
| `memorygraft/milestone3_4_campaign.py` | **Yes** | **Yes** | `memorygraft/milestone3_4_campaign_run_2026-09-11.txt` |
| `dsrm/dry_run_milestone2_3.py` | No | **Yes** | `dsrm/milestone2_3_dry_run_2026-09-11.txt` (+ a retained pre-fix `milestone3_csrm_truncation_bug_2026-09-11.txt`) |
| `dsrm/dry_run_milestone5.py` | No | No (local embedder only) | `dsrm/milestone5_white_box_run_2026-09-11.txt` |
| `dsrm/milestone4_campaign.py` | **Yes** | **Yes** | `dsrm/milestone4_campaign_run_2026-09-11.txt` |
| `mpbench/dry_run_milestone4.py` | **Yes** | No | `mpbench/milestone4_dry_run_2026-09-11.txt` |
| `mpbench/milestone5_campaign.py` | **Yes** | **Yes** | `mpbench/milestone5_campaign_run_2026-09-11.txt` |
| `sleeper_memory_poisoning/campaign.py` | **Yes** | **Yes** | `sleeper_memory_poisoning/campaign_run_2026-09-11.txt` |
| `sleeper_memory_poisoning/trigger_sensitivity.py` | **Yes** | **Yes** | `sleeper_memory_poisoning/trigger_sensitivity_run_2026-09-11.txt` |
| `mpbench/amem_campaign.py` *(added closing gap A-MEM)* | **Yes** (`RealAMemAdapter`) | **Yes** | `mpbench/amem_campaign_run_2026-09-11.txt` |
| `memorygraft/attack_failure_demo.py` *(added closing gap `ATTACK_FAILURE`)* | No | **Yes** | `memorygraft/attack_failure_demo_run_2026-09-11.txt` |
| `dsrm/white_box_campaign.py` *(added closing DSRM white-box gap)* | **Yes** | **Yes** | `dsrm/white_box_campaign_run_2026-09-11.txt` |

**26 real entry-point scripts, 25 with a corresponding persisted log or
JSON artifact** (`agentpoison/core.py`'s own `__main__` is an internal
smoke check with no persisted output of its own — the only script in this
table without one; verified by direct recount during the Phase 4 release
audit, correcting an earlier arithmetic error that had understated this
by one) — every real number, quote, or verdict cited anywhere in
Phase 4's documentation is reproducible by re-running the corresponding
row above under the stated environment, not merely re-readable from a
document that summarized it once.

## 4. Test Suite Reproduction

```bash
cd "C:\Agent Memory Poisoning"
python -m pytest phase4/tests/ -q
```

Runs entirely in the main interpreter (no `h4venv`, no live LLM server —
every test uses `MockMem0Adapter` and/or a scripted LLM transport, per
`phase3/evaluation/tests/test_llm_provider.py`'s own established mocking
pattern). **97 tests, 97 passing** — updated from 93 after this document's
own Section 7 gaps were closed and `phase4/shared/dormancy_report.py`'s
4 new tests were added (`phase4/tests/test_dormancy_report.py`).

## 5. Frozen Phase 3 Verification (run before and after any real work)

```bash
git status --porcelain phase3/evaluation/
```

Must return empty output. Run and confirmed empty at the start and end of
every one of Phase 4's seven attacks' work in this session — the single
most-repeated command in this entire project, and never once returned
non-empty output. **Specifically re-verified for
`phase3/evaluation/foundations_real/amem_real_adapter.py`** after the
gap-closing A-MEM campaign (`PHASE4_4_9_ATTACK_GROUND_TRUTH.md` Section
2.4) — that file is the one most tempting to edit, since Decision 2's own
text describes "wiring the fix" as touching it, and the campaign was run
against the real, unmodified file specifically because editing it is not
permitted; the targeted check confirms this was actually honored, not
merely asserted.

## 6. Determinism — What's Actually Pinned, and What Isn't

| Factor | Pinned? |
|---|---|
| Model identity | Yes — `verify_server_identity()` checked at the start of every real campaign needing the LLM, never skipped |
| `temperature` | Yes — `0.0` for every real campaign-stage generation call (SRM/CSRM/gate calls sometimes use `0.7`, disclosed per-script, e.g. DSRM's SRM refinement and Sleeper's paraphrase-generation calls, where some sampling diversity was the intended behavior) |
| `seed` | Yes — `42`, universally, across every `GenerationConfig` in every real script |
| `max_tokens`/`n_ctx` | Pinned per-script, values vary by call purpose (a real, disclosed choice — not an oversight; DSRM's CSRM truncation bug, Milestone 3, is the one place an undersized value caused a real failure, since fixed) |
| Retrieval pool/top-k | Yes — `RETRIEVAL_POOL_SIZE_N=20`, `DEFAULT_TOP_K=8`, frozen Phase 3 constants, never touched |
| Embedder | Yes — Mem0's real local `all-MiniLM-L6-v2`-based embedder throughout; AgentPoison/DSRM's white-box optimization additionally load a directly-instantiated `BertModel`/`BertTokenizer` copy of the same checkpoint, confirmed identical via Milestone 1's own cosine-similarity check (`1.0`) |
| **What is NOT strictly pinned**: exact wall-clock ordering of concurrent requests under `--parallel 4`, and llama.cpp/GPU kernel-level floating-point non-determinism | **No** — temperature 0 + fixed seed makes output highly reproducible in practice (confirmed by this session's own repeat structural patterns, e.g. AgentPoison's Milestone 4 v1 vs v2 runs used the SAME seed deliberately to isolate the iteration-count variable, and produced the expected monotonic improvement both times), but is not a formal bit-for-bit determinism guarantee across different hardware or llama.cpp builds |
| File timestamps / generated ids (Mem0 UUIDs) | **No**, and not expected to be — every real memory id quoted in this project's documentation is illustrative of a real run, not a stable identifier a re-run will reproduce exactly; re-running any script will mint new UUIDs, which is expected and does not affect the validity of the documented findings |

## 7. Known Reproducibility Gaps — Both Closed (2026-09-11)

- **RESOLVED — `retrieved_memory_ids` now logged for all seven attacks.**
  Originally: the six pre-Sleeper campaign scripts only ever printed
  `selected_memory_ids`. Built `phase4/shared/dormancy_report.py` (real,
  unit-tested — 4/4 passing) and wired it into all six scripts, then
  re-ran all six for real against a single live server session
  (`phase4/attacks/_cross_attack_dormancy_reruns_2026-09-11.txt`). This
  re-run also caught and fixed two real latent bugs from the Phase 4.7
  refactor that `py_compile`-level syntax checking could not catch (a
  missing `DEFAULT_TOP_K` import in FARMA's script; missing `user_id`/
  `task_id` kwargs in MPBench's script) — found only because this
  gap-closing pass actually executed every script, not merely re-checked
  its syntax. Full detail: `PHASE4_4_9_ATTACK_GROUND_TRUTH.md` Section 2.1.
- **RESOLVED, scoped honestly — real orchestration reuse, not a
  full CI system.** `phase4/shared/dormancy_report.py` is the concrete,
  bounded, genuinely reusable piece this gap actually called for (ground-
  truth-state reporting is identical logic across all seven attacks,
  exactly like `retrieve_select_generate()` itself was found to be in
  Phase 4.7) — now used everywhere. A full automated CI/scheduler-driven
  re-run harness was considered and deliberately NOT built: this is a
  research project with no CI infrastructure, and wrapping Section 3's
  table into a fake "automation" layer that a human would still have to
  invoke manually would add process without adding evidence. The honest
  scope of what "orchestration reuse" meant here is now real and shared;
  literal continuous-integration automation remains out of scope by
  informed choice, not oversight.

## 8. Sources

- Every attack's own integration/reconstruction plan and campaign
  documentation under `phase3/experiments/`
- `phase4/tests/` (the reproducible, mocked test suite)
- `phase4/attacks/*/` (every real script and its persisted log, Section 3)
