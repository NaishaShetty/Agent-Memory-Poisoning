# Pinned Ollama Model Digests

Added in response to external review (2026-09-28): "Ollama model digests aren't
recorded, so 'qwen2.5:7b' can silently change underneath the results." A model tag like
`qwen2.5:7b` is mutable — Ollama can update what it points to on a later `pull`. Every
Phase 17 result in this project was produced against the following exact digests
(`ollama list`, run on the machine that produced every Phase 17 result in this
repository, at the time of the last full regression):

| Tag | Digest (short ID) | Size |
|---|---|---|
| `qwen2.5:7b` | `845dbda0ea48` | 4.7 GB |
| `llama2:latest` | `78e26419b446` | 3.8 GB |
| `phi3:mini` | `4f2222927938` | 2.2 GB |

To reproduce this project's exact model versions on another machine:

```bash
ollama pull qwen2.5:7b
ollama pull llama2
ollama pull phi3:mini
ollama list
```

Compare the `ID` column against the table above. If any digest differs, Ollama has
updated that tag since this table was recorded — re-running Phase 17's judge/detector
tests against a different digest is a real, disclosed source of drift this project cannot
fully control (Ollama tags are not content-addressed the way a pinned pip package
version is), but recording the digest at least makes that drift detectable rather than
silent.

This table should be refreshed (`ollama list`, copy the `ID` column) whenever a new full
Phase 17 regression is run and reported as canonical.

## Update (2026-10-12 remediation): every model this project uses

The table above listed three models; Phase 17 also uses the judges and baselines below. All IDs were
recorded from `ollama list` on 2026-10-12. After an interrupted Ollama auto-update deleted the local
model store, the first five were re-pulled the same day and their IDs re-verified IDENTICAL
(`remediation/logs/ollama_repull.log`), so the weights behind every published number are unchanged.

| Tag | Digest (short ID) | Role | Re-verified 2026-10-12 |
|---|---|---|---|
| `qwen2.5:7b` | `845dbda0ea48` | agent | yes |
| `llama3.1:8b` | `46e0c10c039e` | judge C0/C1/J0, llm_prompt baseline | yes |
| `mistral:7b` | `6577803aa9a0` | judge C3, mechanism judge, HO4 author | yes |
| `llama2:latest` | `78e26419b446` | early phases; regression tests | yes |
| `phi3:mini` | `4f2222927938` | multi-agent checks; tests | yes |
| `llama-guard3:8b` | `46f211c3d866` | baseline (scores cached) | recorded only |
| `mistral:7b-text` | `495ae085225b` | hold-out 7 author | recorded only |

Runtime: Ollama 0.40.3 (CUDA). Between 2026-10-11 17:33 and the 2026-10-12 reinstall the server ran
CPU-only (incomplete CUDA libraries); see docs/release/REPRODUCE.md section 3.
