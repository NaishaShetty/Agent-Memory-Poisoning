"""v7 ingestion: SA-7 single notes, URA (user-relayed attacks), MSD-7 and CSD-7 through Mem0 2.0.19 (infer=True) with the
v6 PL ledger, unchanged (`phase17.defence_v6.mem0_sa6.one`). Pre-registered SA7_PREREGISTRATION.md §1.

  main env:  python -m phase17.defence_v7.mem0_sa7 export
  mem0venv:  C:\\mem0venv\\Scripts\\python.exe -m phase17.defence_v7.mem0_sa7 run
"""
from __future__ import annotations

from phase17.defence_v7 import atomic  # noqa: F401  (crash-safe checkpoints: atomic file writes)

import json
import random
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTDIR = ROOT / "phase17" / "data" / "defence_v7"
INP = OUTDIR / "sa7_mem0_inputs.json"
STAGE = OUTDIR / "sa7_mem0_stage.json"
LEDGERS = OUTDIR / "ledgers"
BEN_FOR_MSD = ("ben_unground", "ben_future", "ben_unusual")


def msd7_docs(items):
    """v6 MSD construction, explicit attack documents only (pre-registered), + 4 benign-only documents per owner."""
    docs = []
    by_owner = {}
    for x in items:
        by_owner.setdefault(x["owner"], []).append(x)
    for o in sorted(by_owner):
        xs = by_owner[o]
        ben = [x for x in xs if x["kind"] in BEN_FOR_MSD]
        rng = random.Random(f"msd7-{o}")
        for a in [x for x in xs if x["kind"] == "atk_explicit"]:
            parts = [a] + rng.sample(ben, 2)
            rng.shuffle(parts)
            docs.append({"id": f"MSD7-{a['id']}", "owner": o, "split": a["split"], "attack": a["kind"],
                         "parts": [{"id": p["id"], "kind": p["kind"], "note": p["note"]} for p in parts]})
        for k in range(4):
            parts = rng.sample(ben, 3)
            docs.append({"id": f"MSD7-BEN-{o}-{k}", "owner": o, "split": parts[0]["split"], "attack": None,
                         "parts": [{"id": p["id"], "kind": p["kind"], "note": p["note"]} for p in parts]})
    return docs


def ura_items(items):
    """User-relayed attack stratum: first 2 atk_implicit + first 2 atk_explicit notes per owner (by id), user channel."""
    out = []
    for o in sorted({x["owner"] for x in items}):
        for k in ("atk_implicit", "atk_explicit"):
            out += sorted([x for x in items if x["owner"] == o and x["kind"] == k], key=lambda x: x["id"])[:2]
    return out


def export() -> dict:
    from phase17.defence_v7 import csd7, sa7_corpus as C
    from phase17.mem0_infer.make_inputs import BATCH, N_BASE
    from phase17.provenance_sets import owner_turns

    assert C.verify_frozen() and csd7.verify_frozen()
    xs = C.items()
    owners = {}
    for s in sorted({x["owner"] for x in xs}):
        turns = [t["text"] for t in owner_turns(s)[:N_BASE]]
        owners[str(s)] = [turns[i:i + BATCH] for i in range(0, len(turns), BATCH)]
    jobs = [{"job": f"N|{x['id']}", "type": "note", "id": x["id"], "owner": x["owner"], "kind": x["kind"],
             "split": x["split"], "channel": x["channel"], "text": x["note"], "claims": [x["note"]],
             "trigger": x["trigger"], "non_trigger": x["non_trigger"]} for x in xs]
    for x in ura_items(xs):
        jobs.append({"job": f"U|{x['id']}", "type": "ura", "id": x["id"], "owner": x["owner"], "kind": x["kind"],
                     "split": x["split"], "channel": "user", "text": x["note"], "claims": [x["note"]]})
    for d in msd7_docs(xs):
        jobs.append({"job": f"D|{d['id']}", "type": "msd", "id": d["id"], "owner": d["owner"], "kind": d["attack"] or "benign_doc",
                     "split": d["split"], "channel": "document", "text": " ".join(p["note"] for p in d["parts"]),
                     "claims": [p["note"] for p in d["parts"]], "parts": d["parts"]})
    for d in csd7.items():
        jobs.append({"job": f"C|{d['id']}", "type": "csd", "id": d["id"], "owner": d["owner"], "kind": d["kind"],
                     "split": d["split"], "channel": "document", "text": d["text"], "claims": d["sentences"],
                     "rule_index": d["rule_index"], "variant": d["variant"]})
    INP.write_text(json.dumps({"owners": owners, "jobs": jobs}, indent=1, ensure_ascii=False), encoding="utf-8")
    return {"n_jobs": len(jobs), **{t: sum(j["type"] == t for j in jobs) for t in ("note", "ura", "msd", "csd")}}


def run() -> None:
    sys.path.insert(0, str(ROOT))
    from phase17.defence_v6.mem0_sa6 import one
    from phase17.mem0_infer import run_pipeline as RP
    from phase17.mem0_infer.config import CONFIG_SUMMARY, make_memory

    inp = json.loads(INP.read_text(encoding="utf-8"))
    LEDGERS.mkdir(parents=True, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="mem0_sa7_")
    m = make_memory(tmp, "defence_v7_sa7")
    done = json.loads(STAGE.read_text(encoding="utf-8")) if STAGE.exists() else {"items": {}}
    done["config"] = CONFIG_SUMMARY
    bases = {o: RP.baseline(m, o, inp["owners"][o]) for o in inp["owners"]}
    order = sorted(inp["jobs"], key=lambda j: (j["split"] != "dev", j["type"], j["job"]))   # dev first
    t0 = time.time()
    for n, job in enumerate(order, 1):
        if job["job"] in done["items"]:
            continue
        lp = LEDGERS / f"{job['job'].replace('|', '_')}.jsonl"
        for attempt in range(3):
            try:
                if lp.exists():
                    lp.unlink()          # an interrupted attempt's ledger belongs to a discarded store
                done["items"][job["job"]] = one(m, f"u-sa7-{n}", bases[str(job["owner"])], job, lp)
                break
            except Exception as e:  # noqa: BLE001
                print(f"  {job['job']} attempt {attempt + 1} failed: {type(e).__name__}: {str(e)[:160]}", flush=True)
                time.sleep(5)
        else:
            done["items"][job["job"]] = {"error": "failed after 3 attempts"}
        if n % 10 == 0 or n == len(order):
            STAGE.write_text(json.dumps(done, ensure_ascii=False), encoding="utf-8")
            print(f"  sa7 jobs {n}/{len(order)}  {time.time() - t0:.0f}s", flush=True)
    STAGE.write_text(json.dumps(done, ensure_ascii=False), encoding="utf-8")
    shutil.rmtree(tmp, ignore_errors=True)
    print("sa7 mem0: DONE", flush=True)


if __name__ == "__main__":
    print(export()) if sys.argv[1] == "export" else run()
