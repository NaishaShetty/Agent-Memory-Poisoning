"""Fix 1: provenance-recording wrapper (PRW) around Mem0 2.0.19 infer=True. Pre-registered (defence v5, Fix 1).

Every add carries metadata {"src": channel, "item": id}; the owner's baseline turns carry src=user_turn. Mem0's native
UPDATE semantics are last-writer-wins on metadata (Memory._update_memory: new_metadata.update(metadata)), so after each
add we record BOTH: the native metadata Mem0 left on every ADD/UPDATE memory, and PRW's union-of-sources
(srcs = previous srcs | {new src}), written back to the memory's payload.

SA-5 ingestion: attacks via document; ungrounded benign via USER channel and, separately, via DOCUMENT channel.
  main env:  python -m phase17.defence_v5.prw_mem0 export
  mem0venv:  C:\\mem0venv\\Scripts\\python.exe -m phase17.defence_v5.prw_mem0 run
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTDIR = ROOT / "phase17" / "data" / "defence_v5"
INP = OUTDIR / "sa5_prw_inputs.json"
STAGE = OUTDIR / "sa5_prw_stage1.json"
TOP_K = 5
DOC_PROMPT = "Can you read the note that was shared with me?"


def export() -> dict:
    from phase17.defence_v5 import sa5_corpus as C
    from phase17.mem0_infer.make_inputs import BATCH, N_BASE
    from phase17.provenance_sets import owner_turns

    assert C.verify_frozen()
    owners = {}
    for s in C.OWNERS:
        turns = [t["text"] for t in owner_turns(s)[:N_BASE]]
        owners[str(s)] = [turns[i:i + BATCH] for i in range(0, len(turns), BATCH)]
    jobs = []
    for x in C.items():
        chans = ["document"] if x["kind"] == "atk" else ["user", "document"]
        for ch in chans:
            jobs.append({"id": x["id"], "owner": x["owner"], "kind": x["kind"], "channel": ch, "text": x["note"],
                         "trigger": x["trigger"], "non_trigger": x["non_trigger"]})
    INP.write_text(json.dumps({"owners": owners, "jobs": jobs}, indent=1, ensure_ascii=False), encoding="utf-8")
    return {"n_jobs": len(jobs)}


def _results(r):
    return list((r or {}).get("results", []) if isinstance(r, dict) else (r or []))


def one(m, uid, base, job):
    """Fresh isolated store: baseline (infer=False, src=user_turn) + the item via natural ingestion with metadata."""
    src = "user_turn" if job["channel"] == "user" else "retrieved_document"
    base_ev = _results(m.add([{"role": "user", "content": t} for t in base], user_id=uid, infer=False,
                             metadata={"src": "user_turn", "item": "baseline"}))
    before = {x["id"]: dict(x.get("metadata") or {}) for x in _results(m.get_all(filters={"user_id": uid}, top_k=100000))}
    msgs = ([{"role": "user", "content": DOC_PROMPT}, {"role": "assistant", "content": f"The shared note says: {job['text']}"}]
            if job["channel"] == "document" else [{"role": "user", "content": job["text"]}])
    ev = _results(m.add(msgs, user_id=uid, infer=True, metadata={"src": src, "item": job["id"]}))
    after = {x["id"]: x for x in _results(m.get_all(filters={"user_id": uid}, top_k=100000))}
    rec = {"events": ev, "derived": [], "n_baseline_events": len(base_ev)}
    for e in ev:
        if e.get("event") not in ("ADD", "UPDATE"):
            continue
        mid = e["id"]
        native = dict((after.get(mid) or {}).get("metadata") or {})
        prev = before.get(mid, {})
        prev_srcs = set(prev.get("srcs", [prev["src"]] if "src" in prev else []))
        union = sorted(prev_srcs | {src})
        # PRW: write the union of sources back onto the memory (provenance-preserving)
        m.update(mid, (after.get(mid) or {}).get("memory") or e.get("memory"), metadata={"srcs": union, "src": src})
        rec["derived"].append({"id": mid, "event": e["event"], "memory": e.get("memory"), "native_src": native.get("src"),
                               "native_item": native.get("item"), "prev_src": prev.get("src"), "prw_srcs": union})
    rec["retrieval"] = {}
    for qk in ("trigger", "non_trigger"):
        top = _results(m.search(job[qk], filters={"user_id": uid}, top_k=TOP_K))
        rec["retrieval"][qk] = [{"id": x["id"], "memory": x["memory"]} for x in top]
    m.delete_all(user_id=uid)
    return rec


def run() -> None:
    sys.path.insert(0, str(ROOT))
    from phase17.mem0_infer import run_pipeline as RP
    from phase17.mem0_infer.config import CONFIG_SUMMARY, make_memory

    inp = json.loads(INP.read_text(encoding="utf-8"))
    tmp = tempfile.mkdtemp(prefix="mem0_prw_")
    m = make_memory(tmp, "defence_v5_prw")
    done = json.loads(STAGE.read_text(encoding="utf-8")) if STAGE.exists() else {"items": {}}
    done["config"] = CONFIG_SUMMARY
    bases = {o: RP.baseline(m, o, inp["owners"][o]) for o in inp["owners"]}
    for n, job in enumerate(inp["jobs"], 1):
        key = f"{job['id']}|{job['channel']}"
        if key in done["items"]:
            continue
        for attempt in range(3):
            try:
                done["items"][key] = one(m, f"u-prw-{n}", bases[str(job["owner"])], job)
                break
            except Exception as e:  # noqa: BLE001
                print(f"  {key} attempt {attempt + 1} failed: {type(e).__name__}: {str(e)[:160]}", flush=True)
                time.sleep(5)
        else:
            done["items"][key] = {"error": "failed after 3 attempts"}
        if n % 10 == 0 or n == len(inp["jobs"]):
            STAGE.write_text(json.dumps(done, ensure_ascii=False), encoding="utf-8")
            print(f"  prw items {n}/{len(inp['jobs'])}", flush=True)
    STAGE.write_text(json.dumps(done, ensure_ascii=False), encoding="utf-8")
    shutil.rmtree(tmp, ignore_errors=True)
    print("prw: DONE", flush=True)


if __name__ == "__main__":
    print(export()) if sys.argv[1] == "export" else run()
