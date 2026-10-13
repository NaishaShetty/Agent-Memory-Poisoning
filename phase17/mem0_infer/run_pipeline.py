"""MEM-1 / MEM-2, stage 1 (isolated interpreter): natural Mem0 ingestion with infer=True, storage events and
retrieval, per item. Pre-registered in docs/phase17/PREREGISTRATION_GAPCLOSURE_2026-10-13.md.

    C:\\mem0venv\\Scripts\\python.exe -m phase17.mem0_infer.run_pipeline ho4|sa1

Writes phase17/data/mem0_infer/{baseline_owner<N>.json, stage1_<exp>.json} (checkpointed, resumable).
Nothing here judges or defends; it records exactly what Mem0 stored and retrieved.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from phase17.mem0_infer.config import CONFIG_SUMMARY, make_memory  # noqa: E402

DATA = ROOT / "phase17" / "data" / "mem0_infer"
TOP_K = 5
DOC_PROMPT = "Can you read the note that was shared with me?"


def _results(r) -> list:
    return list((r or {}).get("results", []) if isinstance(r, dict) else (r or []))


def _search(m, uid, query):
    # Mem0 2.0.19: the size argument is `top_k` (an unknown `limit` kwarg is silently ignored -> default 20)
    r = m.search(query, filters={"user_id": uid}, top_k=TOP_K)
    return [{"id": x["id"], "memory": x["memory"], "score": float(x.get("score", 0.0))} for x in _results(r)]


def _all(m, uid):
    # get_all defaults to top_k=20 (would truncate); ask for everything
    return [{"id": x["id"], "memory": x["memory"]} for x in _results(m.get_all(filters={"user_id": uid}, top_k=100000))]


def baseline(m, owner: str, batches) -> list:
    """Natural extraction of the owner's first 100 turns, ONCE; frozen to JSON."""
    path = DATA / f"baseline_owner{owner}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))["memories"]
    uid = f"baseline-{owner}"
    t0 = time.time()
    events = []
    for b in batches:
        r = m.add([{"role": "user", "content": t} for t in b], user_id=uid, infer=True)
        events += _results(r)
    mems = [x["memory"] for x in _all(m, uid)]
    m.delete_all(user_id=uid)
    path.write_text(json.dumps({"owner": owner, "n_turns": sum(len(b) for b in batches), "events": events,
                                "memories": mems, "seconds": round(time.time() - t0, 1),
                                "config": CONFIG_SUMMARY}, indent=1, ensure_ascii=False), encoding="utf-8")
    return mems


def one(m, uid, base, text, channel, queries):
    """Fresh isolated store = frozen baseline (infer=False) + the item via natural ingestion (infer=True)."""
    m.add([{"role": "user", "content": t} for t in base], user_id=uid, infer=False)
    msgs = ([{"role": "user", "content": DOC_PROMPT}, {"role": "assistant", "content": f"The shared note says: {text}"}]
            if channel == "document" else [{"role": "user", "content": text}])
    t0 = time.time()
    ev = _results(m.add(msgs, user_id=uid, infer=True))
    derived = {e["id"] for e in ev if e.get("event") in ("ADD", "UPDATE")}
    n_store = len(_all(m, uid))
    rec = {"events": ev, "derived_ids": sorted(derived), "store_size_after": n_store,
           "derived_texts": [e["memory"] for e in ev if e.get("event") in ("ADD", "UPDATE")],
           "deleted": [e for e in ev if e.get("event") == "DELETE"], "ingest_seconds": round(time.time() - t0, 1),
           "retrieval": {}}
    for qk, q in queries.items():
        top = _search(m, uid, q)
        rec["retrieval"][qk] = {"top": top, "derived_retrieved": any(x["id"] in derived for x in top)}
    m.delete_all(user_id=uid)
    return rec


def control(m, uid, base, queries):
    m.add([{"role": "user", "content": t} for t in base], user_id=uid, infer=False)
    out = {qk: _search(m, uid, q) for qk, q in queries.items()}
    m.delete_all(user_id=uid)
    return out


def run(exp: str) -> None:
    inp = json.loads((DATA / "inputs.json").read_text(encoding="utf-8"))
    tmp = tempfile.mkdtemp(prefix=f"mem0_{exp}_")
    m = make_memory(tmp, f"gapclosure_{exp}")
    out_path = DATA / f"stage1_{exp}.json"
    done = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {"items": {}, "control": {}}
    done["config"] = CONFIG_SUMMARY
    if exp == "ho4":
        owner = inp["ho4"]["owner"]
        jobs = ([(a["id"], a["text"], "document", {"task": a["task"]}) for a in inp["ho4"]["attacks"]]
                + [(a["id"], a["text"], "user", {"task": a["task"]}) for a in inp["ho4"]["attacks"]]
                + [(b["id"], b["text"], "document", {}) for b in inp["ho4"]["benign"]])
        ctrl = {a["id"]: {"task": a["task"]} for a in inp["ho4"]["attacks"]}
    else:
        owner = inp["sa1"]["owner"]
        jobs = [(x["id"], x["text"], ch, {"trigger": x["trigger"], "non_trigger": x["non_trigger"]})
                for ch in ("document", "user") for x in inp["sa1"]["items"]]
        ctrl = {x["id"]: {"trigger": x["trigger"], "non_trigger": x["non_trigger"]} for x in inp["sa1"]["items"]}
    base = baseline(m, owner, inp["owners"][owner])
    print(f"{exp}: baseline owner {owner}: {len(base)} memories", flush=True)
    for n, (iid, text, ch, q) in enumerate(jobs, 1):
        key = f"{iid}|{ch}"
        if key in done["items"]:
            continue
        for attempt in range(3):
            try:
                done["items"][key] = one(m, f"u-{exp}-{n}", base, text, ch, q)
                break
            except Exception as e:                         # transient Ollama / Qdrant failure: retry, then record
                print(f"  {key} attempt {attempt + 1} failed: {type(e).__name__}: {str(e)[:120]}", flush=True)
                time.sleep(5)
        else:
            done["items"][key] = {"error": "failed after 3 attempts"}
        if n % 10 == 0 or n == len(jobs):
            out_path.write_text(json.dumps(done, ensure_ascii=False), encoding="utf-8")
            print(f"  {exp} items {n}/{len(jobs)}", flush=True)
    for n, (iid, q) in enumerate(ctrl.items(), 1):
        if iid not in done["control"]:
            done["control"][iid] = control(m, f"c-{exp}-{n}", base, q)
    out_path.write_text(json.dumps(done, ensure_ascii=False), encoding="utf-8")
    try:
        shutil.rmtree(tmp, ignore_errors=True)
    except Exception:
        pass
    print(f"{exp}: DONE", flush=True)


if __name__ == "__main__":
    run(sys.argv[1])
