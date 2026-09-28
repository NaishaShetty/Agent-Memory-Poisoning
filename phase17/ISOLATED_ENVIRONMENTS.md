# Isolated Real-Vendor Environments (h4venv, mem0venv)

Added in response to external review (2026-09-28): "the setup depends on `C:\h4venv` and
`C:\mem0venv`, which aren't in the repo." These two Python virtual environments are
deliberately NOT part of this repository (they exist outside the repo tree by design —
`phase3/evaluation/foundations_real/environment.py`'s own module docstring explains why:
Windows `MAX_PATH` issues when a similar venv was nested under a long scratchpad path).
This file makes their setup fully reproducible from a fresh machine without committing
the venvs themselves (which would mean committing several GB of compiled/vendored
packages).

Both are needed ONLY for the live A-mem-sys / Mem0 numbers reported in Phase 17
(`phase17/amem_live/`, `phase17/mem0_live/`); every other Phase 17 result runs in this
project's normal environment (`pip install -r requirements.txt`).

## `C:\h4venv` — real A-mem-sys

```bash
python -m venv C:\h4venv
C:\h4venv\Scripts\pip.exe install torch sentence-transformers chromadb litellm ollama jsonschema
git clone https://github.com/WujiangXu/A-mem-sys C:\h4venv\a-mem-sys-repo
cd C:\h4venv\a-mem-sys-repo
git checkout f303dfc71e07bdc787f4bc135d4cea328ae30e99
```

(exact repository and commit from `phase3/evaluation/foundations_real/environment.py::AMEM_SYS_SOURCE`.)

See `phase3/evaluation/foundations_real/environment.py::PINNED_PACKAGE_VERSIONS` for the
exact versions this project's own real-conformance numbers were produced against, and
`phase3/evaluation/foundations_real/amem_real_adapter.py`'s module docstring for
`AMEM_SYS_SOURCE` (the exact commit A-mem-sys was cloned at).

## `C:\mem0venv` — real Mem0 (added 2026-09-27, first live Mem0 run in this project)

```bash
python -m venv C:\mem0venv
C:\mem0venv\Scripts\pip.exe install mem0ai==2.0.19 qdrant-client sentence-transformers ollama jsonschema
```

Versions confirmed working (`pip freeze` inside `C:\mem0venv`, at the time of the last
live Mem0 run reported in this project):

```
mem0ai==2.0.19
qdrant-client==1.19.1
sentence-transformers==6.1.0
ollama==0.6.2
jsonschema==4.26.0
```

## Running the live-foundation stages

```bash
# Stage 0 (main env): dump the test cases
python -m phase17.amem_live.make_inputs

# Stage 1 (isolated env): ingest + retrieve
C:\h4venv\Scripts\python.exe -m phase17.amem_live.stage1_amem
C:\mem0venv\Scripts\python.exe -m phase17.mem0_live.stage1_mem0

# Stage 2 (main env): apply the real defenses to what was actually retrieved
python -m phase17.amem_live.stage2_defend
python -m phase17.mem0_live.stage2_defend
```

`MAMBENCH_H4VENV_PATH` (an environment variable `amem_real_adapter.py` reads) can point
`C:\h4venv`'s own adapter code at a different path than `C:\h4venv` if you place it
somewhere else; there is no equivalent override for `mem0venv` yet (Mem0 does not need
one — its adapter has no local source-repo dependency the way A-mem-sys's does).
