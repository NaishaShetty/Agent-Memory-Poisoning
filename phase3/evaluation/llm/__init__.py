"""Phase 3.3-B -- the `LLMProvider` abstraction and its concrete llama-server backend.

See `phase3/specification/PHASE3_3_EXPERIMENTAL_SPEC.md` Part 4 for the frozen design
requirement this package implements: the concrete backend (an official llama.cpp
`llama-server.exe` process, per `PHASE3_3_B0_LLM_FEASIBILITY.md`'s Backend Decision)
must stay entirely behind three methods -- `generate`, `model_metadata`,
`configuration_fingerprint` -- with no HTTP/process/CUDA/DLL detail ever crossing that
boundary into agent or evaluator code.
"""
