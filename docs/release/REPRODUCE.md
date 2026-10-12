# Reproducing the Paper's Results

This guide covers the paper's results, not all 17 project phases. Every number in `paper/` comes from a table in `results/tables/`. That table is generated from artifacts in `phase17/data/` by the scripts listed below.

## 0. Three levels of reproduction

| Level | What it means | Needs |
|---|---|---|
| **A. Recompute the tables** | Regenerate every table from saved per-item decisions and verdicts. No model is called. | Python environment only. About 2 minutes. |
| **B. Re-score deterministic defences** | Re-run admission decisions (B12/B13 components, anomaly signals) on frozen text. Bit-identical up to floating point. | The environment plus the HF models (`all-MiniLM-L6-v2`, `cross-encoder/nli-deberta-v3-xsmall`). The B13 lineage/worm judge tiers come from `judge_cache.json`; a cache miss calls Ollama. |
| **C. Re-run model-generated quantities** | Agent answers, judge verdicts, consolidation summaries. | Ollama with the pinned digests. **Not bit-reproducible** (see §3). |

## 1. Environment (as used on 2026-10-12)

- **Hardware:** Windows 11 Home; Intel Core i7-13620H; 15.6 GB RAM; NVIDIA GeForce RTX 4050 Laptop GPU (6 GB).
  - llama3.1:8b and mistral:7b run partly on CPU (17–25%) because they do not fit fully in 6 GB.
- **Python:** 3.11.3; pinned dependencies in `requirements-lock.txt` (206 packages).
- **Key packages:** torch 2.6.0+cu124, transformers 5.12.1, sentence-transformers 5.6.0, scikit-learn 1.9.0, numpy 2.4.6, scipy 1.17.1.
- **Ollama:** 0.40.3.

**Model digests.** These were verified identical before and after a full re-pull on 2026-10-12 (`remediation/logs/ollama_repull.log`):

| Tag | ID |
|---|---|
| qwen2.5:7b | 845dbda0ea48 |
| llama3.1:8b | 46e0c10c039e |
| mistral:7b | 6577803aa9a0 |
| llama2:latest | 78e26419b446 |
| phi3:mini | 4f2222927938 |
| llama-guard3:8b | 46f211c3d866 |
| mistral:7b-text | 495ae085225b |

The last two were recorded from `ollama list` before the re-pull and were not re-pulled.

**Remote models.** gemini-3.5-flash-lite (hold-out 8 and SA-1 author; adopted harm judge J2) is a hosted model, so its version is not pinnable. Output that has already been generated is cached in the artifacts.

## 2. Commands

```bash
python -m phase17.remediation.authoritative_tables
```
(level A: all tables + `results/TABLE_INDEX.md`)

```bash
python -m phase17.remediation.predictions_tally
```
(level A: every pre-registered prediction)

```bash
python -m phase17.remediation.ho8_anomaly_devfit
```
(level B: the hold-out-8 anomaly arms)

```bash
python -m phase17.remediation.b13_decomposition
```
(level B: B13 components; hold-out 7 recomputed)

```bash
python -m phase17.remediation.validity_judge_sensitivity
```
(level C: about 10.5k judge calls)

```bash
python -m phase17.remediation.sleeper_activation_eval
```
(level C: SA-1)

```bash
python -m phase17.remediation.propagation_2gen
```
(level C: P2)

```bash
python -m pytest phase17/tests/test_remediation.py -q
```
(the remediation's property tests)

To keep Ollama on the GPU, run the model-backed jobs one at a time, with `CUDA_VISIBLE_DEVICES=-1` set for the Python process. `remediation/run_gpu_queue.sh` does this.

## 3. Known non-determinism and integrity checks

- **Generation and judging use temperature 0 with fixed seeds, but are not bit-reproducible.** Ollama's concurrent batching varies output.
  - Measured run-to-run spread: compliance 61/62/63 and 36/40/39 of 120; undefended harm 87/89/94 of 309.
  - A judge-only re-run of identical answers moved 94 → 99 of 309 (`results/tables/T8_harm.json`). So the "5-point noise floor" holds at n = 120, but at n = 309 judge variation alone reached 1.6 points.
- **Backend change.** From 2026-10-11 17:33 until the 2026-10-12 reinstall, an interrupted Ollama update left the server **without CUDA**. Model calls in that window ran on the CPU backend; this includes hold-out 8's scoring on 2026-10-11 evening. CPU and GPU backends can differ numerically, which is a further source of non-bit-reproducibility. The weights were unaffected (digests identical).
- **Frozen corpora are digest-checked at load.** Hold-outs 1–8 and SA-1: each evaluation module calls `verify_frozen()` and refuses to run on a mismatch.
- **Pre-registrations are git-committed before the run they govern.** See `docs/phase17/PREREGISTRATION_*.md` and `git log`.
