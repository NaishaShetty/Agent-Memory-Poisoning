# Phase 3.3-H.4-D — Second Real Qualification Run (A-MEM) — Execution Report

Status: **COMPLETE**. Execution report, not an implementation report — no code was
modified. Mirrors [PHASE3_3_H4_D_RUN_REPORT.md](PHASE3_3_H4_D_RUN_REPORT.md) (Mem0)
exactly, run against `RealAMemAdapter` instead.

## 1. What was different from the Mem0 run, and why

`RealAMemAdapter.initialize()` takes no `collection_name` parameter — unlike Mem0's
on-disk, name-addressed store, A-mem-sys's `ChromaRetriever` constructs a fresh, **in-
memory** `chromadb.Client(Settings(allow_reset=True))` (confirmed by reading
`agentic_memory/retrievers.py` directly in the cloned source), so every new
`RealAMemAdapter()` instance gets its own, automatically isolated vector store — no
unique-collection-name scheme was needed the way Mem0's disk-based store required.

A real conformance probe (`INITIALIZE`/`RESET`/`ADD_MEMORY`/`RETRIEVE`) was run before
qualifying anything, per the same discipline as the Mem0 run — never inferred. All four
came back `REAL_FOUNDATION_CONFORMANCE`, confirming the A-mem-sys path fix from earlier
this session (re-cloning at the pinned commit into a stable location) produced a fully
real-conformant adapter, not merely an importable one.

**Noise, not a problem:** the run log contains repeated LiteLLM/Ollama connection error
output — this is A-mem-sys's own internal "link generation"/evolution step attempting its
`llm_backend="ollama"` client (no Ollama server running in this environment), caught
gracefully by A-mem-sys's own `try/except`, exactly as `amem_real_adapter.py`'s module
docstring already documents. It does not affect `ADD_MEMORY`/`RETRIEVE` conformance or the
qualification comparison logic, which never depends on LLM-generated content.

## 2. Result

```json
{
  "fixture_set_version": "qualification_fixtures_v1",
  "conformance_tag": "REAL_FOUNDATION_CONFORMANCE",
  "config_fingerprint": "CFG-e4a0d4b9835b855732633f18f89f5a6b5cef560e7a2730d215f339ead3552a6b",
  "adapter_revision": "h4-real-v1",
  "official_overall_verdict": "QUALIFIED",
  "official_per_fixture_pass_count": "15/15",
  "divergences": []
}
```

**A-MEM is now `QUALIFIED` under Initiative D's real gate** — the second real
qualification record this framework has produced, and (per the earlier probe) the
*easiest* of the four candidate foundations to qualify: no server, no API key, fully local
and in-memory.

## 3. Artifacts

`phase3/experiments/results/canonical_store/qualification/amem/` (untracked, kept as
evidence per the user's own stated preference for the Mem0/H.4-WIRE artifacts):
`qualification_ledger/qualifications.jsonl`, `run_config/run_configs.jsonl`,
`fixtures/<name>/`, `official_run/<name>/`, `run_summary.json`.

## 4. Updated foundation status

| Foundation | Qualification | What's needed for more |
|---|---|---|
| Mem0 | **QUALIFIED** (real) | Real sampled LoCoMo counterfactual run |
| A-MEM | **QUALIFIED** (real) | Condition C wiring into `campaign_formal_runner.py` (not yet attempted); a real counterfactual run |
| Graphiti | Not qualified | No local embedder in `graphiti-core` — needs a cloud LLM/embedding API key (e.g. Gemini) and a graph DB backend (Neo4j/FalkorDB); a real, deliberate policy decision, not yet made |
| Letta | Not qualified | Needs a self-hosted server or Letta Cloud account; deferred since the original strengthening plan itself, not revisited |

## 5. Freeze status

Not a frozen decision — a dated execution record.
