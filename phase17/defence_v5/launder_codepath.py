"""Code-level demonstration (not an ecological result): Mem0 2.0.19's UPDATE path is last-writer-wins on metadata, so a
user-channel UPDATE relabels a document-planted memory as the user's; PRW's union keeps the document source.
Exercises Memory.update() exactly as Memory._update_memory is reached on an UPDATE event (infer=False; no LLM).
  mem0venv:  C:\mem0venv\Scripts\python.exe -m phase17.defence_v5.launder_codepath
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "phase17" / "data" / "defence_v5" / "launder_codepath.json"


def run():
    sys.path.insert(0, str(ROOT))
    from phase17.mem0_infer.config import make_memory

    tmp = tempfile.mkdtemp(prefix="mem0_cp_")
    m = make_memory(tmp, "defence_v5_cp")
    r = m.add([{"role": "user", "content": "Jon prefers ordering a cold brew from Blue Bottle Coffee in the morning."}],
              user_id="cp", infer=False, metadata={"src": "retrieved_document"})
    mid = (r.get("results") if isinstance(r, dict) else r)[0]["id"]
    before = m.get(mid)["metadata"]["src"]
    prw = {"retrieved_document"}
    m.update(mid, "Jon prefers ordering a cold brew from Blue Bottle Coffee in the morning, with oat milk.",
             metadata={"src": "user_turn"})                                 # the UPDATE a user refinement triggers
    prw.add("user_turn")
    after = m.get(mid)["metadata"]["src"]
    out = {"label": "code-level demonstration (deterministic; not an ecological frequency)",
           "native_src_before": before, "native_src_after_user_update": after, "native_laundered": after == "user_turn",
           "prw_srcs_after": sorted(prw), "prw_keeps_document": "retrieved_document" in prw}
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    shutil.rmtree(tmp, ignore_errors=True)
    print(out)


if __name__ == "__main__":
    run()
