# Running the Phase 17 LLM pipeline (and the mistakes that cost a day)

This project's evaluations are long LLM jobs on one consumer GPU (the results were produced
on a 6GB RTX 4050). That combination has failure modes that look like bugs in the code and
are not. This file records them because a reviewer or a future session reproducing these
numbers will hit the same ones.

## Run one job at a time, and kill orphans between them

```bash
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/kill_orphan_phase17.ps1
python -u -m phase17.<module>
```

**Stopping a backgrounded shell command does not stop the python process it spawned.** During
external review round 5 this left four phase17 jobs running simultaneously — `eval_round5`
(833 CPU-seconds), `precompute_features` (491s), `attack_validity_audit`, `defense_cost` —
holding 4.4GB of a 6GB card between them. Ollama then could not load a 5GB model, and every
request against it timed out.

The symptom is indistinguishable from a bug in the client: read timeouts, a server that
answers `/api/tags` but never returns a completion, `ollama ps` showing a model pinned that
nothing should be using. It was misdiagnosed three times in a row — as concurrency set too
high, as a missing retry, as a stale connection pool — and each "fix" restarted the job,
which *added* another competing process. Check what actually holds the GPU first:

```bash
nvidia-smi --query-gpu=memory.used,memory.total --format=csv
powershell "Get-CimInstance Win32_Process -Filter \"Name like '%python%'\" | Select ProcessId,CommandLine"
```

## Two 8B models do not fit in 6GB — evict explicitly

`llama-guard3:8b`, `qwen2.5:7b` and `llama3.1:8b` are each ~5GB resident. Switching between
them under load is where the server wedges. `phase17/external_baselines.py::unload()` sends
`keep_alive: 0` to evict a model, and `precompute_features.py` calls it between scorers.
Never interleave two models in one loop.

## Batch, but not past the hardware

Ollama batches concurrent requests, and it is worth a great deal: a `llama-guard3` call costs
~5.6s issued one at a time and ~0.35s effective at 8-way. But 8-way against a partly
CPU-offloaded model on this card trips read timeouts. **4-way is the measured sweet spot
here**; `precompute_features` uses 3. Results are unaffected either way — temperature 0 and
fixed seeds throughout, only dispatch changes.

## Long jobs must checkpoint

Every LLM-backed cache in `phase17/` merges and writes atomically (`phase17/cache_io.py`)
because a plain `write_text` raced with a reader and killed a two-hour run with a
`JSONDecodeError`. `precompute_features` flushes every 64 texts and skips what is cached, so
an interrupted run resumes; `attack_validity_audit` checkpoints every 50 results. A stage that
cannot resume will eventually be run three times.

## Order

`phase17/precompute_features.py` first — it fills the feature cache that `eval_round5` and
B14 need, so those then do no LLM work of their own. Then:

```
precompute_features → eval_round5 → defense_cost → founding_family_regen
→ attack_validity_audit → attack_register → harm_study_v2 --per-instance-tasks
→ evidence_available_check → adaptive_query_attacker B14
```

## What a clean run looks like

With an empty GPU, the precompute's cheap scorers finish in seconds (`deberta_pi_v2` 8.3s,
`perplexity_gpt2` 7.6s against 134.5s under contention — an 18x difference from nothing but
removing competing processes). If a scorer that should take seconds is taking minutes,
something else is on the card.
