# Phase 3.3-H.4-A — First Real Counterfactual Run (Mem0 + Qwen3-8B) — Execution Report

Status: **COMPLETE**. Execution report, not an implementation report — no code was
modified. First real (non-mock, non-fabricated-answer) run of the H.4-A counterfactual
mechanism, resolving hard blocker #5 of
[PHASE3_3_H4_READINESS_ASSESSMENT.md](PHASE3_3_H4_READINESS_ASSESSMENT.md) for a small,
deliberately-legible smoke case — **not** a full LoCoMo-scale sampled campaign, which
remains a separate, larger follow-up (see §5).

## 1. Infrastructure stood up for this run

Real Qwen3-8B, served by the exact `llama-server.exe` binary the frozen G.1 baseline
campaign used (`build 10717, commit a32af33de` — verified directly via `--version`,
matching `provider.py`'s own pinned `QWEN3_8B_Q4_K_M_IDENTITY` exactly), launched fresh for
this session at `http://127.0.0.1:8811` (`-ngl 99`, `--ctx-size 16384`, `--parallel 4`,
model at `C:\Users\naish\mambench_llm_feasibility\models\Qwen3-8B-Q4_K_M.gguf`). One
observed, minor difference from the original G.1 server log: `kv_unified = 'false'` here
vs. `'true'` in the archived log — the exact original launch flags were not recorded
anywhere retrievable, so this run's flags were reconstructed from the log's visible
parameters, not replayed byte-identical. This does not affect correctness of generation,
only KV-cache sharing behavior across parallel slots; noted for completeness, not
corrected, since this run used only one slot at a time. `phase3/evaluation/tests/
test_llm_provider.py` was re-run against this live server as a framework-level integration
check: **20/20 passed** (previously 17/20 + 3 skipped in every prior regression run this
session — all three real-server-dependent tests now genuinely execute and pass).

`RealMem0Adapter` under `C:\h4venv`, same as the [Initiative D run](PHASE3_3_H4_D_RUN_REPORT.md).

## 2. What was run

A small, fabricated, deliberately legible example — not a real LoCoMo pool — chosen so the
counterfactual signal is checkable by inspection, matching the same "small synthetic
sample, not full scale" posture the H.4-A mission itself specified as the minimum bar and
H.4-WIRE's own dry run already established as this project's convention for a first real
exercise of new machinery:

- Three canonical memories, written via `write_canonical_memory()` into a real Mem0
  collection: `mem-color` ("The user's favorite color is blue."), `mem-dog` ("The user's
  dog is named Max."), `mem-job` ("The user works as a software engineer.").
- One task: *"What is the user's favorite color? Answer with just the color."*
- Baseline run via the real, unmodified `run_agent_task()`: real Mem0 dense retrieval
  (`top_k=3`), real Qwen3-8B generation (`clean_baseline_generation_config()` —
  `temperature=0.0`, `seed=42`, `enable_thinking=False`, `n_ctx=4096`).
- For each memory `run_agent_task()` actually selected, `run_counterfactual_mask()` +
  `compare_counterfactual_run()` — the real, unmodified H.4-A mechanism, masking exactly
  one memory at a time and never re-invoking retrieval, exactly as designed.

## 3. Result

Real Mem0 retrieval returned only **2** of the 3 ingested memories for this query
(`mem-job` was never retrieved at all) — genuine semantic filtering, not a bug; confirmed
by direct inspection of the real alias records
(`memory/aliases.jsonl`, written by `write_canonical_memory()`):

| Foundation (vendor) memory id | Canonical memory id |
|---|---|
| `93184142-92aa-4f3f-afce-22b090854f4c` | `mem-color` |
| `4716997e-25db-471c-8ae6-fdd74b91fd23` | `mem-dog` |

**Baseline answer: `"blue"`** (correct).

**Masking `mem-color`:** masked answer —
*"The question is about the user's favorite color, but the provided memory only mentions
the user's dog's name. There is no relevant information about the user's favorite color.
Therefore, the answer cannot be determined from the given information."*
→ **`COUNTERFACTUALLY_INFLUENTIAL`**.

**Masking `mem-dog`:** masked answer — `"blue"` (unchanged) →
**`NOT_COUNTERFACTUALLY_INFLUENTIAL`**.

**This is exactly the expected real-world pattern**: removing the one memory that actually
supports the answer changed the observable under the mechanism's `exact_normalized_match`
criterion; removing an irrelevant memory did not. The mechanism's own status vocabulary,
diff criterion, and masking logic all behaved correctly against real model output for the
first time — not just against mocked/scripted answers in `test_counterfactual.py`.

**Correction, stated honestly:** the smoke-test script's own inline "sanity check" printout
compared `masked_memory_id` (a vendor-native Mem0 UUID, since neither `run_agent_task()` nor
`run_counterfactual_mask()` performs identity resolution — that is deliberately a separate
concern, per H.4-WIRE's own scoping) directly against the fabricated canonical string id
`"mem-color"`, so it printed "DOES NOT MATCH" for the correct case. This was a bug in the
throwaway verification script's own labeling logic, not in the mechanism itself — resolved
by reading the real `aliases.jsonl` record directly (§3's table above), which is
authoritative. Recorded here so the discrepancy isn't silently glossed over.

## 4. Reminder of what this result does and does not mean

Per [PHASE3_3_H4_A_MISSION.md §1](../specification/PHASE3_3_H4_A_MISSION.md): a
`COUNTERFACTUALLY_INFLUENTIAL` finding is interventional dependence under this frozen
masking protocol, never causal attribution in a stronger sense. This one real example
demonstrates the mechanism works correctly end to end against real infrastructure — it is
not a claim that Mem0-on-LoCoMo counterfactual influence has now been "measured" as a
research result. That requires the sampled, LoCoMo-scale run described in §5.

## 5. What remains — the actual punch-list item is still open

The readiness assessment's punch-list item 3 ("run Initiative A's counterfactual mechanism
for real against a sampled set of (task, memory) pairs from the existing LoCoMo baseline")
is **not** what this run did. This run validated the *mechanism* against real
infrastructure on fabricated data — a necessary, but smaller, precursor. A real,
sampled LoCoMo/Mem0 counterfactual campaign would additionally require:

- Real dataset ingestion (`_ingest_pool`) instead of 3 fabricated memories.
- A defined sampling strategy/budget (mission §7 — deliberately left as a per-campaign
  decision, not fixed here).
- Wiring through `campaign_formal_runner.py`'s own Condition B path (H.4-WIRE) so results
  are captured in the same structure as the frozen baseline, with real identity resolution
  applied consistently.
- Meaningfully more compute time (dozens–hundreds of LLM calls, not 3).

This is a separate, larger action, appropriately not undertaken as part of this smoke
verification.

## 6. Server lifecycle

The `llama-server.exe` process launched for this run remains running at
`127.0.0.1:8811` at the time of writing (background task, GPU currently at ~5.8/6.1 GiB
used) — left up in case immediate follow-up real-LLM work is wanted. It was not started as
a persistent service and will not survive a reboot; stop it (or let the user's own session
management stop it) when no longer needed, since it holds nearly all available VRAM.

## 7. Artifacts

`phase3/experiments/results/canonical_store/counterfactual/mem0_locomo_smoke/` (currently
untracked, same open question as the H.4-D and H.4-WIRE artifacts): `memory/` (canonical
ledger + real `aliases.jsonl`), `run_summary.json`.

## 8. Freeze status

Not a frozen decision — a dated execution record.
