"""v7 checkpoint status and resume guide. Safe to run at any time (read only, except `freeze-selections`).

  python -m phase17.defence_v7.status                 show every stage, its checkpoint and the next command(s)
  python -m phase17.defence_v7.status freeze-selections   after all DEV gates exist: hash them before any eval runs

Every stage resumes from its own checkpoint when its command is simply run again. Stages that use the same GPU model
can run together (noted per stage); stages that use different local models should run one at a time (6 GB GPU).
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "phase17" / "data" / "defence_v7"
LOG = "phase17/defence_v7/logs"
PY = "python"
MEM0PY = r"C:\mem0venv\Scripts\python.exe"
DEV_OUTPUTS = ("g1_regress_sa6dev.json", "g1_dev_sa7.json", "g3_pilot_sa7dev.json", "dcr_dev.json", "dcr2_dev.json",
               "g2_dev_explore.json")


def _j(name):
    p = D / name
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        return {"__corrupt__": str(e)}


def _cmd(mod, args="", log=None, py=PY):
    log = log or mod
    return f"{py} -m phase17.defence_v7.{mod} {args}".strip() + f" > {LOG}/{log}.log 2>&1"


def stages():
    out = []

    def add(name, state, detail, cmds=(), gpu="-"):
        out.append({"stage": name, "state": state, "detail": detail, "next": list(cmds), "gpu": gpu})

    # 1 SA-7 corpus (Gemini, remote)
    part, cache, frz = _j("sa7_corpus_partial.json"), _j("sa7_corpus.json"), _j("sa7_corpus_freeze.json")
    if frz:
        add("1 SA-7 corpus", "DONE", f"frozen {frz['frozen_utc']}, n={frz['n']}")
    elif cache:
        short = [k for k, v in cache["counts"].items() if v < 8]
        add("1 SA-7 corpus", "BUILT, NOT FROZEN", f"n={len(cache['items'])}, short cells={short}",
            [_cmd("sa7_corpus", "freeze", "sa7_freeze")])
    else:
        add("1 SA-7 corpus", "IN PROGRESS" if part else "TODO", f"Gemini calls done {len(part or {})}/160",
            [_cmd("sa7_corpus", "", "sa7_build")], "remote (Gemini)")
    sa7_ok = bool(frz)

    # 2 CSD-7 (Gemini)
    part, cache, frz = _j("csd7_partial.json"), _j("csd7_corpus.json"), _j("csd7_freeze.json")
    if frz:
        add("2 CSD-7 documents", "DONE", f"frozen {frz['frozen_utc']}, n={frz['n']}")
    elif cache:
        add("2 CSD-7 documents", "BUILT, NOT FROZEN", f"n={len(cache['items'])}", [_cmd("csd7", "freeze", "csd7_freeze")])
    elif sa7_ok:
        add("2 CSD-7 documents", "IN PROGRESS" if part else "TODO", f"rules done {len(part or {})}/40",
            [_cmd("csd7", "", "csd7_build")], "remote (Gemini)")
    else:
        add("2 CSD-7 documents", "WAITING", "needs stage 1 frozen")
    csd_ok = bool(frz)

    # 3 Mem0 ingestion (qwen2.5:7b)
    inp, st = _j("sa7_mem0_inputs.json"), _j("sa7_mem0_stage.json")
    if not (sa7_ok and csd_ok):
        add("3 Mem0 ingestion", "WAITING", "needs stages 1 and 2 frozen")
    elif not inp:
        add("3 Mem0 ingestion", "TODO", "inputs not exported", [_cmd("mem0_sa7", "export", "mem0_export"),
                                                                 _cmd("mem0_sa7", "run", "mem0_sa7", MEM0PY)], "qwen2.5:7b")
    else:
        n, k = len(inp["jobs"]), len((st or {}).get("items", {}))
        err = sum("error" in v for v in (st or {}).get("items", {}).values())
        add("3 Mem0 ingestion", "DONE" if k >= n else ("IN PROGRESS" if k else "TODO"), f"jobs {k}/{n} (failed {err})",
            [] if k >= n else [_cmd("mem0_sa7", "run", "mem0_sa7", MEM0PY)], "qwen2.5:7b (can share with stage 5 gen)")
    mem0_ok = bool(inp) and len((st or {}).get("items", {})) >= len(inp["jobs"]) if inp else False

    # 4 HO10 roots, flags, top-up, freeze (mistral; flags use the B13 judges)
    part, cache, flags, frz = _j("ho10_partial.json"), _j("ho10_corpus.json"), _j("ho10_flags.json"), _j("ho10_freeze.json")
    if frz:
        add("4 HO10 roots", "DONE", f"frozen {frz['frozen_utc']}, n={frz['n']}")
    elif not cache:
        add("4 HO10 roots", "IN PROGRESS" if part else "TODO", f"seeds attempted {len(part or {})}/1800 (early stop skips many)",
            [_cmd("ho10_corpus", "build", "ho10_build")], "mistral:7b-text")
    elif not flags or len(flags) < len(cache["items"]):
        add("4 HO10 roots", "FLAGGING", f"flags {len(flags or {})}/{len(cache['items'])}",
            [_cmd("ho10_corpus", "flags", "ho10_flags")], "B13 judges")
    else:
        fi = sum(flags[x["id"]]["B13"] for x in cache["items"] if x["payload"] == "instruction")
        ff = sum(flags[x["id"]]["B13"] for x in cache["items"] if x["payload"] == "factual")
        topup = (D / "ho10_topup.json").exists()
        if fi < 250 and not topup:
            add("4 HO10 roots", "DECISION", f"flagged instruction {fi} < 250 (factual {ff}): the ONE pre-registered top-up "
                "round is decided on these counts only -> ask Claude to write ho10_topup.json and run it", [], "-")
        else:
            add("4 HO10 roots", "FLAGGED, NOT FROZEN", f"flagged instruction {fi}, factual {ff}",
                [_cmd("ho10_corpus", "freeze", "ho10_freeze")])
    ho10_ok = bool(frz)

    # 5 HO10 chains (qwen gen + rewrites; llama judges)
    cp = _j("ho10_chains_partial.json")
    if not ho10_ok:
        add("5 HO10 chains", "WAITING", "needs stage 4 frozen")
    else:
        sys.path.insert(0, str(ROOT))
        from phase17.defence_v7 import ho10_chains as C10
        cs = C10.chains()
        cp = cp or {}
        gen = sum(f"rw4:{c['key']}" in cp for c in cs)
        atk = [c for c in cs if c["kind"] == "atk"]
        jud = sum(f"J:g4:{c['key']}" in cp and f"carryrw4:{c['key']}" in cp for c in atk)
        if gen < len(cs):
            add("5 HO10 chains", "IN PROGRESS (gen)", f"chains with all 4 generations + rewrites {gen}/{len(cs)}",
                [_cmd("ho10_chains", "gen", "ho10_chains_gen")], "qwen2.5:7b (can share with stage 3)")
        elif jud < len(atk):
            add("5 HO10 chains", "IN PROGRESS (judges)", f"attack chains judged {jud}/{len(atk)}",
                [_cmd("ho10_chains", "judge", "ho10_chains_judge")], "llama3.1:8b")
        else:
            add("5 HO10 chains", "DONE", f"{len(cs)} chains")
    chains_done = out[-1]["state"] == "DONE"

    # 6 DCR dev gate (NLI only; HO9)
    dcr = _j("dcr_dev.json")
    add("6 DCR dev gate (HO9)", "DONE" if dcr else "TODO/IN PROGRESS",
        f"carried_to_HO10={dcr['gate']['carried_to_HO10']}" if dcr else "rerun resumes from the v7 NLI cache",
        [] if dcr else [_cmd("dcr", "", "dcr_dev")], "deberta NLI (small; can share)")

    # 6b DCR-2 (addendum B) dev selection on HO9
    d2 = _j("dcr2_dev.json")
    fin = bool(d2 and "gate" in d2)
    add("6b DCR-2 dev selection (HO9, addendum B)", "DONE" if fin else ("IN PROGRESS" if d2 else "TODO"),
        f"carried_to_HO10={d2['gate']['carried_to_HO10']}" if fin else f"configs done {len((d2 or {}).get('configs', []))}/6",
        [] if fin else [_cmd("dcr2", "", "dcr2_dev")], "deberta NLI (small; can share)")

    # 7 development pilots and selection freeze
    have = {n: (D / n).exists() for n in DEV_OUTPUTS}
    cmds = []
    if not have["g1_regress_sa6dev.json"]:
        cmds.append(_cmd("g1_v7", "regress", "g1_regress"))
    if mem0_ok and not have["g1_dev_sa7.json"]:
        cmds.append(_cmd("g1_v7", "dev", "g1_dev"))
    if mem0_ok and not have["g3_pilot_sa7dev.json"]:
        cmds.append(_cmd("g3_v7", "pilot", "g3_pilot"))
    beh = _j("v7_behaviour_partial.json") or {}
    if mem0_ok and "dev|atk_highimpact,ben_highimpact" not in beh.get("_timing", {}):
        cmds.append(_cmd("g3_v7", "behaviour dev atk_highimpact,ben_highimpact", "hig_dev_pilot"))
    sel = _j("selections_freeze.json")
    if sel:
        add("7 Dev pilots + selection freeze", "DONE", f"frozen {sel['frozen_utc']}")
    elif all(have.values()):
        add("7 Dev pilots + selection freeze", "READY TO FREEZE", "all dev gates computed",
            [f"{PY} -m phase17.defence_v7.status freeze-selections"])
    else:
        add("7 Dev pilots + selection freeze", "TODO" if not any(have.values()) else "IN PROGRESS",
            f"present: {[n for n, v in have.items() if v]}", cmds or ["(waiting for stage 3 / 6)"], "llama3.1:8b")

    if (D / "selections_freeze_gap2.json").exists() and chains_done and not (D / "g2_eval_ho10.json").exists():
        add("8a Gap 2 held-out (HO10)", "TODO/IN PROGRESS", "Gap 2 selections frozen separately (selections_freeze_gap2.json)",
            [_cmd("g2_v7", "", "g2_eval")], "deberta NLI")
    elif (D / "g2_eval_ho10.json").exists():
        add("8a Gap 2 held-out (HO10)", "DONE", "g2_eval_ho10.json")
    # 8 held-out evaluation (ONLY after the selection freeze)
    if not sel:
        add("8 Held-out evaluation", "LOCKED", "runs only after stage 7 is frozen (no eval outcome before selection)")
    else:
        beh = _j("v7_behaviour_partial.json") or {}
        cmds = []
        if "eval|all" not in beh.get("_timing", {}):
            cmds.append(_cmd("g3_v7", "behaviour eval", "g3_behaviour_eval"))
        for f, c in (("g1_eval_sa7.json", _cmd("g1_v7", "eval", "g1_eval")), ("g3_eval_sa7.json", _cmd("g3_v7", "eval", "g3_eval")),
                     ("g3_csd_eval.json", _cmd("g3_v7", "csd eval", "g3_csd_eval"))):
            if not (D / f).exists():
                cmds.append(c)
        pass
        add("8 Held-out evaluation", "DONE" if not cmds else "TODO/IN PROGRESS",
            "order: behaviour -> g1 eval -> g3 eval (uses g1 items) ; g2 after stage 5", cmds, "qwen + llama")

    # 9 closure, reports, documents
    add("9 Closure, reports, both .docx", "DONE" if (D / "closure_v7.json").exists() else "TODO",
        "done by Claude after stage 8 (rubric mapping, 9 deliverables, Results Analysis + Methodology regenerated)")
    return out


def freeze_selections():
    missing = [n for n in DEV_OUTPUTS if not (D / n).exists()]
    if missing:
        raise SystemExit(f"cannot freeze: missing {missing}")
    if (D / "selections_freeze.json").exists():
        raise SystemExit("selections already frozen")
    files = [D / n for n in DEV_OUTPUTS] + [ROOT / "phase17/defence_v7" / f for f in
                                            ("g1_v7.py", "g2_v7.py", "g3_v7.py", "dcr.py", "common.py")]
    out = {"frozen_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "note": "all development gates computed; no held-out (SA-7 eval / MSD-7 eval / CSD-7 eval / HO10) outcome exists",
           "sha256": {str(f.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(f.read_bytes()).hexdigest() for f in files}}
    (D / "selections_freeze.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


def main():
    if sys.argv[1:2] == ["freeze-selections"]:
        return freeze_selections()
    corrupt = [p.name for p in D.glob("*.json") if "__corrupt__" in (_j(p.name) or {})]
    print("v7 checkpoint status  (run from the repository root; set PYTHONPATH=. first:")
    print("   Git Bash:  export PYTHONPATH=.      PowerShell:  $env:PYTHONPATH='.')\n")
    if corrupt:
        print(f"!! unreadable checkpoint files: {corrupt} -- tell Claude before running anything\n")
    for s in stages():
        print(f"[{s['state']}] {s['stage']}  --  {s['detail']}   (GPU: {s['gpu']})")
        for c in s["next"]:
            print(f"      next: {c}")
    print("\nAny command above can be stopped at any time (close the window / shut down) and simply run again: it resumes"
          "\nfrom its checkpoint. Stages 1-2 (Gemini) and 4 (mistral) can run together; 3 and 5-gen share qwen2.5.")


if __name__ == "__main__":
    main()
