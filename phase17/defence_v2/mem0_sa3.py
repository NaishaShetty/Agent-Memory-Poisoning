"""WS-A/WS-C: SA-3 EVAL notes (owners 5, 7, 8) through Mem0 2.0.19 with infer=True, document channel.
Pre-registered: docs/phase17/PREREGISTRATION_DEFENCE_V2_2026-10-13.md.

Two steps:
  main env:      python -m phase17.defence_v2.mem0_sa3 export      -> data/defence_v2/sa3_mem0_inputs.json
  mem0venv:      C:\\mem0venv\\Scripts\\python.exe -m phase17.defence_v2.mem0_sa3 run
Reuses run_pipeline's baseline()/one() unchanged (same config, top_k fixes). Baselines for owners 5 and 8 are new;
owner 7's existing frozen baseline is reused.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTDIR = ROOT / "phase17" / "data" / "defence_v2"
INP = OUTDIR / "sa3_mem0_inputs.json"
STAGE = OUTDIR / "sa3_mem0_stage1.json"


def export() -> dict:
    from phase17.defence_v2 import sa3_corpus as C
    from phase17.mem0_infer.make_inputs import BATCH, N_BASE
    from phase17.provenance_sets import owner_turns

    assert C.verify_frozen()
    owners = {}
    for s in C.EVAL_OWNERS:
        turns = [t["text"] for t in owner_turns(s)[:N_BASE]]
        owners[str(s)] = [turns[i:i + BATCH] for i in range(0, len(turns), BATCH)]
    items = [{"id": x["id"], "owner": x["owner"], "kind": x["kind"], "text": x["note"], "trigger": x["trigger"],
              "non_trigger": x["non_trigger"]} for x in C.items(split="eval")]
    d = {"owners": owners, "items": items}
    INP.write_text(json.dumps(d, indent=1, ensure_ascii=False), encoding="utf-8")
    return {"n_items": len(items)}


def run() -> None:
    sys.path.insert(0, str(ROOT))
    from phase17.mem0_infer import run_pipeline as RP
    from phase17.mem0_infer.config import CONFIG_SUMMARY, make_memory

    inp = json.loads(INP.read_text(encoding="utf-8"))
    tmp = tempfile.mkdtemp(prefix="mem0_sa3_")
    m = make_memory(tmp, "defence_v2_sa3")
    done = json.loads(STAGE.read_text(encoding="utf-8")) if STAGE.exists() else {"items": {}, "control": {}}
    done["config"] = CONFIG_SUMMARY
    bases = {o: RP.baseline(m, o, inp["owners"][o]) for o in inp["owners"]}
    print("baselines:", {o: len(b) for o, b in bases.items()}, flush=True)
    for n, x in enumerate(inp["items"], 1):
        key = f"{x['id']}|document"
        if key in done["items"]:
            continue
        q = {"trigger": x["trigger"], "non_trigger": x["non_trigger"]}
        for attempt in range(3):
            try:
                done["items"][key] = RP.one(m, f"u-sa3-{n}", bases[str(x["owner"])], x["text"], "document", q)
                break
            except Exception as e:
                print(f"  {key} attempt {attempt + 1} failed: {type(e).__name__}: {str(e)[:120]}", flush=True)
                time.sleep(5)
        else:
            done["items"][key] = {"error": "failed after 3 attempts"}
        if n % 10 == 0 or n == len(inp["items"]):
            STAGE.write_text(json.dumps(done, ensure_ascii=False), encoding="utf-8")
            print(f"  sa3 items {n}/{len(inp['items'])}", flush=True)
    STAGE.write_text(json.dumps(done, ensure_ascii=False), encoding="utf-8")
    shutil.rmtree(tmp, ignore_errors=True)
    print("sa3: DONE", flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "export":
        print(export())
    else:
        run()
