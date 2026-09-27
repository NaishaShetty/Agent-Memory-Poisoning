"""Stage 1 (run with C:\h4venv\Scripts\python.exe): ingest each case's memories into a FRESH real
A-mem-sys store via the frozen RealAMemAdapter (real embeddings, real ChromaDB, real llama2-driven note
evolution through Ollama), then retrieve with A-MEM's own search for the question. Records what A-MEM
actually returns and how it rewrote notes (links/tags/context), so defenses can be run on live A-MEM output."""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from phase3.evaluation.foundations.adapter import FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL
from phase3.evaluation.foundations_real.amem_real_adapter import RealAMemAdapter

HERE = Path(__file__).parent


def main():
    cases = json.loads((HERE / "inputs.json").read_text(encoding="utf-8"))
    out = []
    for c in cases:
        t0 = time.time()
        a = RealAMemAdapter()
        f = a.initialize({"llm_backend": "ollama", "embedding_model": "all-MiniLM-L6-v2"})
        if f.availability not in (FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL):
            raise SystemExit(f"A-MEM unavailable: {f.availability}")
        a.reset()
        for mid, text in c["items"]:
            a.add_memory(mid, {"text": text, "user_id": "phase17-amem-live"}, {"tags": ["phase17"], "keywords": [], "context": "live"})
        native = a._mem.search(c["question"], k=4)
        notes = {}
        for mid, _ in c["items"]:
            n = a._mem.memories.get(mid)
            notes[mid] = {"content": getattr(n, "content", None), "links": list(getattr(n, "links", []) or []),
                          "tags": list(getattr(n, "tags", []) or []), "context": getattr(n, "context", "")}
        out.append({**c, "retrieved_ids": [r["id"] for r in native], "retrieved": [{"id": r["id"], "content": r.get("content"), "score": r.get("score")} for r in native],
                    "notes": notes, "seconds": round(time.time() - t0, 1)})
        a.shutdown()
        print(c["id"], c["kind"], "retrieved", [r["id"] for r in native][:4], flush=True)
        (HERE / "stage1_out.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
