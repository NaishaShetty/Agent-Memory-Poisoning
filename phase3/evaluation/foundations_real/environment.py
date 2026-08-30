"""Phase 3.2-H.4 -- the pinned, resolved isolated-conformance-environment manifest.

This module is a plain, static record -- no filesystem/network access, no attempt to
re-derive or re-verify these numbers at import time (that would defeat the point of an
isolated venv: the numbers below are exactly what `pip freeze` reported inside `C:\\h4venv`
at the time this stage's real conformance runs were performed, transcribed once, by hand,
from that command's actual output). `test_foundation_conformance_h4.py` asserts every
foundation-relevant entry here is a non-empty, non-"latest" version string -- i.e. that
nothing in this stage's real-conformance story rests on an unpinned dependency.

WHY THIS LIVES OUTSIDE THE REPO'S OWN PYTHON ENVIRONMENT
--------------------------------------------------------------------------------
`C:\\h4venv` (created via `python -m venv C:\\h4venv`) is entirely separate from the
interpreter `python -m pytest phase3/evaluation/tests/ -q` runs under -- none of the
packages below are installed there, confirmed directly (`python -c "import mem0"` in the
repo's own environment raises `ModuleNotFoundError`, both before AND after this stage's
work). This satisfies the mission's dependency-isolation requirement: the 833-test baseline
never depended on, and still does not depend on, any real foundation package.

Placement note: an initial attempt created this venv nested deep under this session's
scratchpad directory (itself well outside the repo, satisfying the "prefer outside the repo
tree" preference) -- but every `pip install sentence-transformers` (which pulls in `torch`)
failed there with a Windows `OSError: [Errno 2] No such file or directory` on one of
torch's bundled CUDA header files, whose full path was measured at EXACTLY 260 characters --
Windows' classic `MAX_PATH` limit. `C:\\h4venv` (created fresh, at a short path, still
entirely outside `C:\\Agent Memory Poisoning`) has no such issue. This is recorded here
plainly as a real, mundane environment finding, not smoothed over.
"""

from __future__ import annotations

from typing import Mapping

VENV_PATH = r"C:\h4venv"
VENV_CREATION_COMMAND = "python -m venv C:\\h4venv"
PYTHON_VERSION = "3.11.3"

# Resolved via `C:\h4venv\Scripts\pip.exe freeze` after all installs for this stage
# completed. Only the packages load-bearing for this stage's real-conformance claims are
# reproduced here (the full freeze output, ~140 lines including transitive deps, is
# recorded in PHASE3_2_H4_DATASET_FOUNDATION_CONFORMANCE.md's installation-environment
# section verbatim).
PINNED_PACKAGE_VERSIONS: Mapping[str, str] = {
    # Mem0
    "mem0ai": "2.0.19",
    "qdrant-client": "1.19.0",
    # Graphiti
    "graphiti-core": "0.29.3",
    "kuzu": "0.11.3",
    "neo4j": "6.3.0",  # driver only -- no Neo4j SERVICE running; see doc for the distinction
    # A-MEM (A-mem-sys, cloned from source -- not on PyPI; see AMEM_SYS_SOURCE below)
    "sentence-transformers": "6.0.0",
    "torch": "2.13.0+cpu",
    "chromadb": "1.5.9",
    "rank-bm25": "0.2.2",
    "nltk": "3.10.3",
    "litellm": "1.98.0",
    "ollama": "0.6.2",  # python client package only -- no Ollama SERVER process running
    # Letta (structural inspection only; see doc)
    "letta-client": "1.12.1",
    # Shared / incidental
    "openai": "2.54.0",  # installed as a transitive dep of mem0ai/litellm; never given a
    # real API key anywhere in this stage -- see per-adapter MODEL_DEPENDENT markers.
    "pytest": "9.1.1",
    "jsonschema": "4.26.0",
}

AMEM_SYS_SOURCE = {
    "repository": "https://github.com/WujiangXu/A-mem-sys",
    "commit": "f303dfc71e07bdc787f4bc135d4cea328ae30e99",
    "commit_date": "2025-11-06T11:30:19-05:00",
    "clone_method": "git clone --depth 1 (shallow -- only this exact commit's tree, "
    "recorded here, was ever read)",
    "acquisition_note": (
        "Not installed via pip -- A-mem-sys is not published to PyPI under this name "
        "(this is the same 'paper-reproduction repo vs. packaged -sys repo' distinction "
        "H.3's capability_audit.py already documented; this stage uses the -sys "
        "implementation repo per that prior finding, imported directly via sys.path "
        "insertion in amem_real_adapter.py, never copied into this repository)."
    ),
}

LETTA_DOCS_RECHECK = {
    "url": "https://docs.letta.com/concepts/memory",
    "result": "HTTP 404 (re-fetched fresh in this stage, 2026-08-30 -- same finding as "
    "H.2/H.3, independently reconfirmed rather than assumed unchanged)",
}

EXTERNAL_SERVICES_REQUIRED_BUT_NOT_RUNNING = {
    "neo4j": "Graphiti's documented default graph backend -- no server process running "
    "in this environment; not installed as a service (only the Python driver package is "
    "installed, for import/inspection purposes).",
    "falkordb": "Graphiti's documented alternative graph backend -- same status as Neo4j.",
    "ollama_server": "A-mem-sys's/Mem0's local-LLM-backend option -- the `ollama` PYTHON "
    "PACKAGE is installed (lets the client object construct without an API key), but no "
    "Ollama SERVER process is running anywhere in this environment, so every LLM call "
    "attempted against it genuinely fails (caught gracefully by the calling library, per "
    "each adapter's own MODEL_DEPENDENT records) rather than genuinely succeeding.",
    "letta_server": "Letta's ADE/agent-server process (self-hosted or Letta Cloud) -- "
    "not running/reachable anywhere in this environment.",
}

NO_LLM_OR_EMBEDDING_API_KEY_CONFIGURED = True  # No OPENAI_API_KEY, ANTHROPIC_API_KEY, or
# any other production LLM provider credential is set anywhere in this environment or was
# used anywhere in this stage's real-adapter code, per the task's explicit prohibition on
# introducing a real LLM into H.4.


__all__ = [
    "VENV_PATH",
    "VENV_CREATION_COMMAND",
    "PYTHON_VERSION",
    "PINNED_PACKAGE_VERSIONS",
    "AMEM_SYS_SOURCE",
    "LETTA_DOCS_RECHECK",
    "EXTERNAL_SERVICES_REQUIRED_BUT_NOT_RUNNING",
    "NO_LLM_OR_EMBEDDING_API_KEY_CONFIGURED",
]
