"""v8 addendum W1b ingestion: SA-9 single notes through Mem0 2.0.19 (infer=True), mirroring
mem0_sa8.py exactly (reuses v6's `one()` unchanged). Own store/collection
("defence_v8_sa9"), own STAGE/LEDGERS files.

  main env:    python -m phase17.defence_v8.mem0_sa9 export
  mem0venv:    C:\\mem0venv\\Scripts\\python.exe -m phase17.defence_v8.mem0_sa9 run
"""
from __future__ import annotations

from phase17.defence_v7 import atomic  # noqa: F401  (crash-safe checkpoints: atomic file writes)

import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTDIR = ROOT / "phase17" / "data" / "defence_v8"
INP = OUTDIR / "sa9_mem0_inputs.json"
STAGE = OUTDIR / "sa9_mem0_stage.json"
LEDGERS = OUTDIR / "ledgers_sa9"


def export() -> dict:
    from phase17.defence_v8 import sa9_corpus as C
    from phase17.mem0_infer.make_inputs import BATCH, N_BASE
    from phase17.provenance_sets import owner_turns  # dispatches to longmemeval_owners for ids >= 200

    assert C.verify_frozen()
    xs = C.items()
    owners = {}
    for s in sorted({x["owner"] for x in xs}):
        turns = [t["text"] for t in owner_turns(s)[:N_BASE]]
        owners[str(s)] = [turns[i:i + BATCH] for i in range(0, len(turns), BATCH)]
    jobs = [{"job": f"N|{x['id']}", "type": "note", "id": x["id"], "owner": x["owner"], "kind": x["kind"],
             "split": x["split"], "channel": x["channel"], "text": x["note"], "claims": [x["note"]],
             "trigger": x["trigger"], "non_trigger": x["non_trigger"]} for x in xs]
    INP.write_text(json.dumps({"owners": owners, "jobs": jobs}, indent=1, ensure_ascii=False), encoding="utf-8")
    return {"n_jobs": len(jobs)}


def run() -> None:
    sys.path.insert(0, str(ROOT))
    from phase17.defence_v6.mem0_sa6 import one
    from phase17.mem0_infer import run_pipeline as RP
    from phase17.mem0_infer.config import CONFIG_SUMMARY, make_memory

    inp = json.loads(INP.read_text(encoding="utf-8"))
    LEDGERS.mkdir(parents=True, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="mem0_sa9_")
    m = make_memory(tmp, "defence_v8_sa9")
    done = json.loads(STAGE.read_text(encoding="utf-8")) if STAGE.exists() else {"items": {}}
    done["config"] = CONFIG_SUMMARY
    bases = {o: RP.baseline(m, o, inp["owners"][o]) for o in inp["owners"]}
    order = sorted(inp["jobs"], key=lambda j: (j["split"] != "dev", j["type"], j["job"]))
    t0 = time.time()
    for n, job in enumerate(order, 1):
        if job["job"] in done["items"]:
            continue
        lp = LEDGERS / f"{job['job'].replace('|', '_')}.jsonl"
        for attempt in range(3):
            try:
                if lp.exists():
                    lp.unlink()
                done["items"][job["job"]] = one(m, f"u-sa9-{n}", bases[str(job["owner"])], job, lp)
                break
            except Exception as e:  # noqa: BLE001
                print(f"  {job['job']} attempt {attempt + 1} failed: {type(e).__name__}: {str(e)[:160]}", flush=True)
                time.sleep(5)
        else:
            done["items"][job["job"]] = {"error": "failed after 3 attempts"}
        if n % 10 == 0 or n == len(order):
            STAGE.write_text(json.dumps(done, ensure_ascii=False), encoding="utf-8")
            print(f"  sa9 jobs {n}/{len(order)}  {time.time() - t0:.0f}s", flush=True)
    STAGE.write_text(json.dumps(done, ensure_ascii=False), encoding="utf-8")
    shutil.rmtree(tmp, ignore_errors=True)
    print("sa9 mem0: DONE", flush=True)


if __name__ == "__main__":
    print(export()) if sys.argv[1] == "export" else run()
