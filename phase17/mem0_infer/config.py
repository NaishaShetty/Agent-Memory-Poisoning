"""One Mem0 configuration for every extraction-enabled (infer=True) experiment.

Choices, all recorded in the output of every experiment that uses them:
  * LLM: Ollama qwen2.5:7b (digest 845dbda0ea48) -- the same model as the project's agent, so no new model
    family enters the pipeline; temperature 0. Mem0's default would be OpenAI, which is unavailable offline;
    the provider is a deployment choice Mem0 documents, and the extraction and update PROMPTS are Mem0's own
    defaults, unmodified.
  * Embedder: HuggingFace sentence-transformers/all-MiniLM-L6-v2 (the project's retrieval model).
  * Vector store: local on-disk Qdrant, one collection per isolated store.
  * infer=True on every add: Mem0's fact extraction + ADD/UPDATE/DELETE/NONE update step run as shipped.
"""
from __future__ import annotations

import os

os.environ.setdefault("MEM0_TELEMETRY", "False")

LLM_MODEL = "qwen2.5:7b"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CONFIG_SUMMARY = {"mem0": "2.0.19", "infer": True, "llm": f"ollama/{LLM_MODEL}", "temperature": 0.0,
                  "embedder": f"huggingface/{EMBED_MODEL}", "vector_store": "qdrant (local, on-disk)",
                  "prompts": "Mem0 defaults (unmodified)"}


def make_memory(path: str, collection: str):
    from mem0 import Memory

    cfg = {
        "llm": {"provider": "ollama", "config": {"model": LLM_MODEL, "temperature": 0.0, "max_tokens": 1500,
                                                 "ollama_base_url": "http://127.0.0.1:11434"}},
        "embedder": {"provider": "huggingface", "config": {"model": EMBED_MODEL}},
        "vector_store": {"provider": "qdrant", "config": {"collection_name": collection, "path": path,
                                                          "embedding_model_dims": 384, "on_disk": True}},
        "history_db_path": os.path.join(path, "history.db"),
    }
    return Memory.from_config(cfg)
