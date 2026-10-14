"""v6 Phase 2/4 ingestion: SA-6 single notes and MSD mixed-source documents through Mem0 2.0.19 (infer=True) with the
PL ledger. Pre-registered (§1, §2). Each job: fresh store = the owner's frozen baseline (infer=False, channel user)
+ the item via natural ingestion. Channels: user -> user turn; document -> assistant reading a shared note;
missing -> delivered by its true origin (benign: user turn; attack: document) with NO channel recorded.

After ingestion of SINGLE-NOTE ATTACK jobs: a FORCED UPDATE through the public API (the only path to _update_memory in
2.0.19) relabelling the memory as user-sourced, to test native vs ledger provenance survival. Native history rows are
captured (m.history). Retrieval: top-5 for the trigger and non-trigger messages.

  main env:  python -m phase17.defence_v6.mem0_sa6 export
  mem0venv:  C:\\mem0venv\\Scripts\\python.exe -m phase17.defence_v6.mem0_sa6 run
"""
from __future__ import annotations

import json
import random
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTDIR = ROOT / "phase17" / "data" / "defence_v6"
INP = OUTDIR / "sa6_mem0_inputs.json"
STAGE = OUTDIR / "sa6_mem0_stage.json"
LEDGERS = OUTDIR / "ledgers"
TOP_K = 5
DOC_PROMPT = "Can you read the note that was shared with me?"
BEN_FOR_MSD = ("ben_unground", "ben_future", "ben_unusual")


def msd_docs(items):
    """Deterministic MSD construction (pre-registered): attack note + 2 benign notes of the same owner; plus 4
    benign-only documents of 3 notes per owner."""
    docs = []
    by_owner = {}
    for x in items:
        by_owner.setdefault(x["owner"], []).append(x)
    for o in sorted(by_owner):
        xs = by_owner[o]
        ben = [x for x in xs if x["kind"] in BEN_FOR_MSD]
        rng = random.Random(f"msd-{o}")
        for a in [x for x in xs if x["kind"].startswith("atk")]:
            parts = [a] + rng.sample(ben, 2)
            rng.shuffle(parts)
            docs.append({"id": f"MSD-{a['id']}", "owner": o, "split": a["split"], "attack": a["kind"],
                         "parts": [{"id": p["id"], "kind": p["kind"], "note": p["note"]} for p in parts]})
        for k in range(4):
            parts = rng.sample(ben, 3)
            docs.append({"id": f"MSD-BEN-{o}-{k}", "owner": o, "split": parts[0]["split"], "attack": None,
                         "parts": [{"id": p["id"], "kind": p["kind"], "note": p["note"]} for p in parts]})
    return docs


def export() -> dict:
    from phase17.defence_v6 import sa6_corpus as C
    from phase17.mem0_infer.make_inputs import BATCH, N_BASE
    from phase17.provenance_sets import owner_turns

    assert C.verify_frozen()
    xs = C.items()
    owners = {}
    for s in sorted({x["owner"] for x in xs}):
        turns = [t["text"] for t in owner_turns(s)[:N_BASE]]
        owners[str(s)] = [turns[i:i + BATCH] for i in range(0, len(turns), BATCH)]
    jobs = [{"job": f"N|{x['id']}", "type": "note", "id": x["id"], "owner": x["owner"], "kind": x["kind"],
             "split": x["split"], "channel": x["channel"], "text": x["note"], "claims": [x["note"]],
             "trigger": x["trigger"], "non_trigger": x["non_trigger"]} for x in xs]
    for d in msd_docs(xs):
        jobs.append({"job": f"D|{d['id']}", "type": "msd", "id": d["id"], "owner": d["owner"], "kind": d["attack"] or "benign_doc",
                     "split": d["split"], "channel": "document", "text": " ".join(p["note"] for p in d["parts"]),
                     "claims": [p["note"] for p in d["parts"]], "parts": d["parts"]})
    INP.write_text(json.dumps({"owners": owners, "jobs": jobs}, indent=1, ensure_ascii=False), encoding="utf-8")
    return {"n_jobs": len(jobs), "notes": len(xs), "msd": len(jobs) - len(xs)}


def _results(r):
    return list((r or {}).get("results", []) if isinstance(r, dict) else (r or []))


def one(m, uid, base, job, ledger_path):
    from phase17.defence_v6.ledger import Ledger

    L = Ledger(ledger_path)
    origin = job["channel"]
    if origin == "missing":
        origin = "document" if job["kind"].startswith("atk") else "user"
    recorded = None if job["channel"] == "missing" else job["channel"]
    beid = L.record_event("\n".join(base), "user", principal="owner(unverified)")
    m.add([{"role": "user", "content": t} for t in base], user_id=uid, infer=False,
          metadata={"sev": beid, "src": "user"})
    base_ids = {x["id"]: x["memory"] for x in _results(m.get_all(filters={"user_id": uid}, top_k=100000))}
    for mid, t in base_ids.items():
        L.link(mid, "ADD", beid, t)
    eid = L.record_event(job["text"], recorded, principal=None, claims=job["claims"])
    msgs = ([{"role": "user", "content": DOC_PROMPT}, {"role": "assistant", "content": f"The shared note says: {job['text']}"}]
            if origin == "document" else [{"role": "user", "content": job["text"]}])
    meta = {"sev": eid} if recorded is None else {"sev": eid, "src": recorded}
    t0 = time.time()
    ev = _results(m.add(msgs, user_id=uid, infer=True, metadata=meta))
    ingest_s = time.time() - t0
    after = {x["id"]: x for x in _results(m.get_all(filters={"user_id": uid}, top_k=100000))}
    rec = {"events": [{k: e.get(k) for k in ("id", "event", "memory")} for e in ev], "derived": [],
           "ingest_seconds": round(ingest_s, 2), "origin": origin, "recorded_channel": recorded}
    t1 = time.time()
    for e in ev:
        if e.get("event") not in ("ADD", "UPDATE"):
            continue
        mid = e["id"]
        L.link(mid, e["event"], eid, e.get("memory") or "")
        md = dict((after.get(mid) or {}).get("metadata") or {})
        rec["derived"].append({"id": mid, "event": e["event"], "memory": e.get("memory"), "native_src": md.get("src"),
                               "native_sev": md.get("sev"), "attributed_to": md.get("attributed_to"),
                               "ledger_channels": L.channels(mid)})
    rec["ledger_seconds"] = round(time.time() - t1, 4)
    rec["n_update_events_natural"] = sum(e.get("event") == "UPDATE" for e in ev)
    if job["type"] == "note":
        rec["retrieval"] = {}
        for qk in ("trigger", "non_trigger"):
            top = _results(m.search(job[qk], filters={"user_id": uid}, top_k=TOP_K))
            rec["retrieval"][qk] = [{"id": x["id"], "memory": x["memory"]} for x in top]
    if job["type"] == "note" and job["kind"].startswith("atk"):
        forced = []
        for d in rec["derived"]:
            ueid = L.record_event(d["memory"], "user", principal="owner(unverified)")
            m.update(d["id"], d["memory"], metadata={"src": "user", "sev": ueid})
            L.link(d["id"], "UPDATE", ueid, d["memory"])
            got = m.get(d["id"]) or {}
            md = dict(got.get("metadata") or {})
            hist = [{k: h.get(k) for k in ("event", "actor_id", "role", "old_memory", "new_memory")}
                    for h in (m.history(d["id"]) or [])]
            forced.append({"id": d["id"], "native_src_after": md.get("src"), "native_sev_after": md.get("sev"),
                           "ledger_channels_after": L.channels(d["id"]), "ledger_untrusted_after": L.untrusted(d["id"]),
                           "native_history": hist})
        rec["forced_update"] = forced
    m.delete_all(user_id=uid)
    return rec


def run() -> None:
    sys.path.insert(0, str(ROOT))
    from phase17.mem0_infer import run_pipeline as RP
    from phase17.mem0_infer.config import CONFIG_SUMMARY, make_memory

    inp = json.loads(INP.read_text(encoding="utf-8"))
    LEDGERS.mkdir(parents=True, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="mem0_sa6_")
    m = make_memory(tmp, "defence_v6_sa6")
    done = json.loads(STAGE.read_text(encoding="utf-8")) if STAGE.exists() else {"items": {}}
    done["config"] = CONFIG_SUMMARY
    bases = {o: RP.baseline(m, o, inp["owners"][o]) for o in inp["owners"]}
    order = sorted(inp["jobs"], key=lambda j: (j["split"] != "dev", j["type"], j["job"]))   # dev first
    for n, job in enumerate(order, 1):
        if job["job"] in done["items"]:
            continue
        lp = LEDGERS / f"{job['job'].replace('|', '_')}.jsonl"
        for attempt in range(3):
            try:
                if lp.exists():
                    lp.unlink()          # an interrupted attempt's ledger belongs to a discarded store
                done["items"][job["job"]] = one(m, f"u-sa6-{n}", bases[str(job["owner"])], job, lp)
                break
            except Exception as e:  # noqa: BLE001
                print(f"  {job['job']} attempt {attempt + 1} failed: {type(e).__name__}: {str(e)[:160]}", flush=True)
                time.sleep(5)
        else:
            done["items"][job["job"]] = {"error": "failed after 3 attempts"}
        if n % 10 == 0 or n == len(order):
            STAGE.write_text(json.dumps(done, ensure_ascii=False), encoding="utf-8")
            print(f"  sa6 jobs {n}/{len(order)}", flush=True)
    STAGE.write_text(json.dumps(done, ensure_ascii=False), encoding="utf-8")
    shutil.rmtree(tmp, ignore_errors=True)
    print("sa6 mem0: DONE", flush=True)


if __name__ == "__main__":
    print(export()) if sys.argv[1] == "export" else run()
