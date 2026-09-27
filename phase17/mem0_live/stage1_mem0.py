"""Stage 1 (run with the isolated mem0venv interpreter): ingest each Track B/benign case
into a FRESH real Mem0 store (real Qdrant on-disk vector store, real HuggingFace
embeddings, LLM-free `infer=False` add path -- the same, frozen `RealMem0Adapter` this
project already has), then retrieve with Mem0's own real search for the question."""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from phase3.evaluation.foundations.adapter import FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL
from phase3.evaluation.foundations_real.mem0_real_adapter import RealMem0Adapter

HERE = Path(__file__).parent


def main():
    cases = json.loads((ROOT / "phase17" / "amem_live" / "inputs.json").read_text(encoding="utf-8"))
    out = []
    for c in cases:
        t0 = time.time()
        a = RealMem0Adapter()
        f = a.initialize({})
        if f.availability not in (FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL):
            raise SystemExit(f"Mem0 unavailable: {f.availability}")
        a.reset()
        id_map = {}
        for mid, text in c["items"]:
            r = a.add_memory(mid, {"text": text}, {})
            if r.availability == FOUNDATION_AVAILABLE:
                id_map[r.value["memory_id"]] = mid
        rr = a.retrieve({"text": c["question"]}, top_k=4)
        native_ids = rr.value or []
        retrieved_ids = [id_map.get(nid, nid) for nid in native_ids]
        out.append({**c, "retrieved_ids": retrieved_ids, "seconds": round(time.time() - t0, 1)})
        print(c["id"], c["kind"], "retrieved", retrieved_ids[:4], flush=True)
        (HERE / "stage1_out.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
