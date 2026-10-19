# Added in response to external review (2026-09-28): "no single command that reproduces
# everything." SCOPE, disclosed honestly: `make regression` is the one real command that
# reproduces the frozen Phases 1-16 test suite plus Phase 17's structural tests (no local
# LLM required). `make phase17-live` additionally requires a local Ollama server with
# qwen2.5:7b/llama2/phi3:mini pulled (see phase17/OLLAMA_MODEL_PINS.md) and is NOT fully
# one-command reproducible yet for the live A-MEM/Mem0 numbers, which need the separate
# isolated environments documented in phase17/ISOLATED_ENVIRONMENTS.md -- `make
# amem-live` and `make mem0-live` run those stages assuming those environments already
# exist at the paths that file documents.

.PHONY: install regression phase17-structural benchmark-check benchmark-all phase17-live amem-live mem0-live bench-smoke review5-pipeline         review4-baselines review4-frozen-eval review4-harm review4-all

install:
	pip install -r requirements.txt

# CORRECTION (external review round 2, 2026-09-28): this target previously included the
# whole `phase17/` tree while claiming "no local LLM required" -- most of Phase 17's own
# test files DO need a local Ollama server or a GEMINI_API_KEY to pass (they are not
# merely slow; they fail outright without one). Restricted to the frozen Phases 1-16 suite
# plus the genuinely LLM-free Phase 17 structural tests, matching what
# `.github/workflows/tests.yml`'s `phase17-structural` job actually runs -- the claim "no
# local LLM required" is now true of what this target runs, not just its name.
#
# UPDATE (unified-benchmark and CI audit, 2026-10-18): these targets now run exactly what the
# CI jobs run (.github/workflows/tests.yml). phase4/, phase5/ and tests/ were previously in
# neither; the full Phase 17 suite passes without a live model (cached judges), so the
# hand-picked "structural" list is replaced by the whole suite. Set OLLAMA_BASE_URL to a
# closed port (as CI does) to be certain nothing calls a live model.
regression:
	python -m pytest phase3/ phase4/ phase5/ phase6/ phase7/ phase8/ phase11/ phase12/ phase13/ phase14/ phase15/ attribution/ tests/ -m "not slow" -q -rs
	$(MAKE) phase17-structural
	$(MAKE) benchmark-check

phase17-structural:
	python -m pytest phase17/ -m "not slow" -q -rs
	# leakage_audit.py is not a test module (pytest collects nothing from it); its checks run as
	# benchmark tasks. The full four-check audit needs data/raw and data/processed (BLOCKED otherwise).
	python -m mambench run --task integrity.leakage_audit --task integrity.leakage_text_and_metadata

# Unified benchmark (mambench/): registry validation, its own tests, and the offline smoke run.
benchmark-check:
	python -m mambench validate
	python -m pytest mambench/tests -q
	python -m mambench run --smoke --strict

benchmark-all:
	python -m mambench run --all

phase17-live:
	python -m pytest phase17/ -m "not slow" -q

amem-live:
	python -m phase17.amem_live.make_inputs
	"C:\h4venv\Scripts\python.exe" -m phase17.amem_live.stage1_amem
	python -m phase17.amem_live.stage2_defend

mem0-live:
	python -m phase17.amem_live.make_inputs
	"C:\mem0venv\Scripts\python.exe" -m phase17.mem0_live.stage1_mem0
	python -m phase17.mem0_live.stage2_defend

bench-smoke:
	python -m phase17.bench_runner --defense B12 --split held_out_novel

# --- external review round 4 (2026-09-30) ------------------------------------------------
# All of these need a local Ollama server. `review4-baselines` additionally pulls nothing
# but expects llama-guard3:8b and llama3.1:8b to be present, and downloads two HuggingFace
# models on first run (protectai/deberta-v3-base-prompt-injection-v2, gpt2).
# Run them one at a time: two concurrent jobs evict each other's model on a small GPU and
# each run ends up several times slower.
# See phase17/RUNNING_THE_PIPELINE.md before running these: one job at a time, and kill
# orphaned python processes between stages (stopping a backgrounded shell does NOT stop its
# python child, and four of them competing for one 6GB GPU is indistinguishable from a client
# bug). `make review5-pipeline` does the whole sequence with that cleanup between stages.
review5-pipeline:
	powershell -NoProfile -ExecutionPolicy Bypass -File scripts/kill_orphan_phase17.ps1
	python -u -m phase17.precompute_features
	powershell -NoProfile -ExecutionPolicy Bypass -File scripts/kill_orphan_phase17.ps1
	python -u -m phase17.eval_round5
	powershell -NoProfile -ExecutionPolicy Bypass -File scripts/kill_orphan_phase17.ps1
	python -u -m phase17.attack_validity_audit
	powershell -NoProfile -ExecutionPolicy Bypass -File scripts/kill_orphan_phase17.ps1
	python -u -m phase17.attack_register

review4-baselines:
	python -m phase17.external_baselines B12 B13

review4-frozen-eval:
	python -m phase17.frozen_eval_b13

review4-harm:
	python -m phase17.harm_study_v2

review4-all: review4-baselines review4-frozen-eval review4-harm
