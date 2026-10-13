"""WS-B data: NEW held-out propagation chains from HO8 (owner 1; never used for propagation), constructed exactly as
defence_v2's HO4 chains, plus an EMPTY-store behaviour control. Pre-registered (defence v3, WS-B).
Generation only -- no containment arm is scored here (scoring happens after the dev selection is frozen).
"""
from __future__ import annotations

import json
import random
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"
OUTDIR = DATA / "defence_v3"
PARTIAL = OUTDIR / "ho8_chains_partial.json"
GENS = 4
N_UNFLAGGED = 40
INSTRUCTION = ("standing_instruction", "conditional_backdoor")


def chains():
    from phase17 import harm_study_v2 as H
    from phase17 import holdout8_corpus as h8
    from phase17.holdout8_validity import _tasks

    recs = h8.attack_records()
    tasks = _tasks("v2", recs)
    p8 = json.loads((DATA / "eval_holdout8_partial.json").read_text(encoding="utf-8"))
    flag_a, flag_b = p8["h8:atk:B13"], p8["h8:ben:B13"]
    ben = list(h8.benign_texts())
    store = H._store_for(1)
    owner_texts = [t for _, t in store]
    out = []
    for i, r in enumerate(recs):
        out.append({"key": f"A{i}", "root": r.text, "task": tasks[r.scenario_id], "family": r.family,
                    "payload": "instruction" if r.family in INSTRUCTION else "factual",
                    "state": "QUARANTINED" if flag_a[i] else "UNASSESSED", "kind": "atk"})
    for i in [i for i, f in enumerate(flag_b) if f]:
        out.append({"key": f"BF{i}", "root": ben[i], "state": "QUARANTINED", "kind": "ben_flagged"})
    for i in random.Random(2026).sample([i for i, f in enumerate(flag_b) if not f], N_UNFLAGGED):
        out.append({"key": f"BU{i}", "root": ben[i], "state": "UNASSESSED", "kind": "ben_unflagged"})
    for c in out:
        r = random.Random(f"ho8-{c['key']}")
        c["extras"] = [r.sample(owner_texts, 4) for _ in range(GENS)]
    return out, store


def run(workers: int = 2) -> dict:
    from phase12.propagation.ollama_provider import OllamaProvider
    from phase17 import harm_study_v2 as H
    from phase17.attack_validity_audit import _answer, _judge
    from phase17.defence_v2.propagation_multigen import _batched, _carry, _cfgs, _summarise

    OUTDIR.mkdir(parents=True, exist_ok=True)
    cs, store = chains()
    model = H._retriever()
    done = json.loads(PARTIAL.read_text(encoding="utf-8")) if PARTIAL.exists() else {}
    scfg, acfg, jcfg = _cfgs()
    agent = OllamaProvider(model=H.AGENT_MODEL)
    for k in range(1, GENS + 1):
        def step(c, k=k):
            key = f"g{k}:{c['key']}"
            if key not in done:
                prev = c["root"] if k == 1 else done[f"g{k - 1}:{c['key']}"]
                done[key] = _summarise(agent, scfg, [prev] + c["extras"][k - 1])
        _batched(step, cs, workers, done, PARTIAL, f"ho8 gen{k}")
    laund = [c for c in cs if c["kind"] == "atk" and c["state"] == "QUARANTINED"]

    def behave(c):
        if f"ans:empty:{c['key']}" not in done:
            done[f"ans:empty:{c['key']}"] = _answer(agent, acfg, [], c["task"])
        kc = f"ans:clean:{c['key']}"
        if kc not in done:
            done[kc] = _answer(agent, acfg, H._retrieve(model, c["task"], store), c["task"])
        for k in range(1, GENS + 1):
            kk = f"ans:g{k}:{c['key']}"
            if kk not in done:
                cand = H._retrieve(model, c["task"], store + [("desc", done[f"g{k}:{c['key']}"])])
                done[f"ret:g{k}:{c['key']}"] = any(m == "desc" for m, _ in cand)
                done[kk] = _answer(agent, acfg, cand, c["task"]) if done[f"ret:g{k}:{c['key']}"] else done[kc]
    _batched(behave, laund, workers, done, PARTIAL, "ho8 behaviour")
    judge = OllamaProvider(model=H.JUDGE_MODEL)

    def jall(c):
        if c["kind"] == "atk":
            for k in range(1, GENS + 1):
                kk = f"carry{k}:{c['key']}"
                if kk not in done:
                    done[kk] = _carry(judge, jcfg, done[f"g{k}:{c['key']}"], c["root"])
        if c in laund:
            for slot in ["empty", "clean"] + [f"g{k}" for k in range(1, GENS + 1)]:
                kk = f"J:{slot}:{c['key']}"
                if kk not in done:
                    done[kk] = bool(_judge(judge, jcfg, c["root"], done[f"ans:{slot}:{c['key']}"]))
    _batched(jall, cs, workers, done, PARTIAL, "ho8 judges")
    PARTIAL.write_text(json.dumps(done, ensure_ascii=False), encoding="utf-8")
    return {"n_chains": len(cs), "n_laundering": len(laund)}


if __name__ == "__main__":
    print(run())
    print("DONE")
