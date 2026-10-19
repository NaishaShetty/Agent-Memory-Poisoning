"""EXPLORATORY functional probe (not pre-registered as an evaluation; added after SA-5 showed no UPDATE events):
can a later USER turn cause Mem0 to UPDATE a document-planted memory and relabel its provenance as the user's
(native last-writer-wins), and does PRW's union-of-sources keep the document source?

For each SA-5 attack (45): fresh store = owner baseline (user) -> add the attack via DOCUMENT (infer=True, src=document)
-> add the note's TRIGGER message as a USER turn (infer=True, src=user_turn) -> inspect every memory that originated from
the document add: native src after step 2, and PRW union.
  mem0venv:  C:\\mem0venv\\Scripts\\python.exe -m phase17.defence_v5.laundering_probe
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "phase17" / "data" / "defence_v5" / "laundering_probe.json"


def _r(x):
    return list((x or {}).get("results", []) if isinstance(x, dict) else (x or []))


def run():
    sys.path.insert(0, str(ROOT))
    from phase17.defence_v5.prw_mem0 import DOC_PROMPT, INP
    from phase17.mem0_infer import run_pipeline as RP
    from phase17.mem0_infer.config import make_memory

    inp = json.loads(INP.read_text(encoding="utf-8"))
    tmp = tempfile.mkdtemp(prefix="mem0_launder_")
    m = make_memory(tmp, "defence_v5_launder")
    bases = {o: RP.baseline(m, o, inp["owners"][o]) for o in inp["owners"]}
    done = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    jobs = [j for j in inp["jobs"] if j["kind"] == "atk"]
    for n, j in enumerate(jobs, 1):
        if j["id"] in done:
            continue
        uid = f"lp-{n}"
        m.add([{"role": "user", "content": t} for t in bases[str(j["owner"])]], user_id=uid, infer=False,
              metadata={"src": "user_turn"})
        ev1 = _r(m.add([{"role": "user", "content": DOC_PROMPT}, {"role": "assistant", "content": f"The shared note says: {j['text']}"}],
                       user_id=uid, infer=True, metadata={"src": "retrieved_document", "item": j["id"]}))
        doc_ids = {e["id"] for e in ev1 if e.get("event") in ("ADD", "UPDATE")}
        prw = {i: {"retrieved_document"} for i in doc_ids}
        ev2 = _r(m.add([{"role": "user", "content": j["trigger"]}], user_id=uid, infer=True, metadata={"src": "user_turn"}))
        for e in ev2:
            if e.get("event") == "UPDATE" and e["id"] in prw:
                prw[e["id"]].add("user_turn")
        allm = {x["id"]: x for x in _r(m.get_all(filters={"user_id": uid}, top_k=100000))}
        rec = {"doc_memories": len(doc_ids), "events_step2": [(e.get("event"), e["id"] in doc_ids) for e in ev2], "mems": []}
        for i in doc_ids:
            x = allm.get(i)
            rec["mems"].append({"exists": x is not None, "native_src": ((x or {}).get("metadata") or {}).get("src"),
                                "prw_srcs": sorted(prw[i]), "updated_by_user_turn": "user_turn" in prw[i]})
        done[j["id"]] = rec
        m.delete_all(user_id=uid)
        OUT.write_text(json.dumps(done, indent=1), encoding="utf-8")
        print(f"  {n}/{len(jobs)}", flush=True)
    shutil.rmtree(tmp, ignore_errors=True)
    mem = [x for r in done.values() for x in r["mems"] if x["exists"]]
    upd = [x for x in mem if x["updated_by_user_turn"]]
    summ = {"label": "EXPLORATORY functional probe", "n_attacks": len(done), "doc_memories": len(mem),
            "updated_by_later_user_turn": len(upd),
            "native_relabelled_as_user": sum(x["native_src"] == "user_turn" for x in upd),
            "prw_keeps_document_source": sum("retrieved_document" in x["prw_srcs"] for x in upd)}
    done["_summary"] = summ
    OUT.write_text(json.dumps(done, indent=1), encoding="utf-8")
    print(summ)


if __name__ == "__main__":
    run()
