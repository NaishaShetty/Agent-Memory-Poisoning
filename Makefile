# Added in response to external review (2026-09-28): "no single command that reproduces
# everything." SCOPE, disclosed honestly: `make regression` is the one real command that
# reproduces the frozen Phases 1-16 test suite plus Phase 17's structural tests (no local
# LLM required). `make phase17-live` additionally requires a local Ollama server with
# qwen2.5:7b/llama2/phi3:mini pulled (see phase17/OLLAMA_MODEL_PINS.md) and is NOT fully
# one-command reproducible yet for the live A-MEM/Mem0 numbers, which need the separate
# isolated environments documented in phase17/ISOLATED_ENVIRONMENTS.md -- `make
# amem-live` and `make mem0-live` run those stages assuming those environments already
# exist at the paths that file documents.

.PHONY: install regression phase17-structural phase17-live amem-live mem0-live bench-smoke

install:
	pip install -r requirements.txt

# CORRECTION (external review round 2, 2026-09-28): this target previously included the
# whole `phase17/` tree while claiming "no local LLM required" -- most of Phase 17's own
# test files DO need a local Ollama server or a GEMINI_API_KEY to pass (they are not
# merely slow; they fail outright without one). Restricted to the frozen Phases 1-16 suite
# plus the genuinely LLM-free Phase 17 structural tests, matching what
# `.github/workflows/tests.yml`'s `phase17-structural` job actually runs -- the claim "no
# local LLM required" is now true of what this target runs, not just its name.
regression:
	python -m pytest phase6/ phase8/ phase11/ phase12/ phase13/ phase14/ phase15/ attribution/ phase7/ phase3/ -m "not slow" -q
	$(MAKE) phase17-structural

phase17-structural:
	python -m pytest phase17/tests/test_workstreams.py phase17/tests/test_bench_runner.py phase17/tests/test_external_review_fixes.py phase17/tests/test_headline_numbers.py phase17/tests/test_live_foundation_stages.py phase17/tests/test_round3_fixes.py phase17/tests/test_arenas.py phase17/leakage_audit.py -q

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
