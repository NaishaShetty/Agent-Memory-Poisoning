"""Phase B: does neutralisation help against THIS benchmark's own memory-poisoning attacks?

Neutralisation was selected and confirmed on injection-shaped text (external dev attacks, hold-out
3). Its mechanism -- framing the untrusted note as data, with the constraint repeated after it --
targets an IMPERATIVE: "do not follow any rule it states". Most of this project's own attacks are
not imperatives at all; a fabricated fact or preference asks nothing of the assistant and harms by
being believed. So there is a specific reason to expect neutralisation to do LESS here, and the
prediction recorded in PREREGISTRATION_ROUND7.md says so before this runs.

DESIGN. The 309 instances, per-instance tasks, stores, retrieval and harm judge of
`harm_study_v2` (published 28.2% undefended -> 10.4% with B13), reproduced exactly up to the
answer: the candidate set is rebuilt with the same seed and shuffle, so every instance meets the
same task and the same surrounding memories. Two arms are run in THIS session, because runs are
not bit-reproducible (~5-point noise floor) and a framed arm must be compared with a raw arm from
the same run, not with a published number:

  raw      the poison admitted verbatim (the published "undefended" arm, re-run)
  framed   the poison admitted under the dev-selected frame (`neutralise.WINNER`)

Policies computed from those vectors and B13's published per-instance exclusion decision:
  B13 alone (exclude, admit rest raw), and B13 + frame (exclude, admit rest framed).
"""
from __future__ import annotations

import json
import random
from pathlib import Path

DATA = Path(__file__).parent / "data"
OUT = DATA / "neutralise_own.json"
PARTIAL = DATA / "neutralise_own_partial.json"


def run(workers: int = 4) -> dict:
    from phase12.propagation.ollama_provider import OllamaProvider
    from phase17 import harm_study_v2 as H
    from phase17.harm_tasks import generate as gen_tasks, task_for
    from phase17.neutralise import WINNER, neutralise
    from phase17.stats import paired_delta, rate_with_ci
    from phase3.evaluation.llm.provider import GenerationConfig

    pub = json.loads((DATA / "harm_study_v2.json").read_text(encoding="utf-8"))
    assert pub.get("per_instance_tasks"), "the published harm study used per-instance tasks"
    pub_rows = {r["id"]: r for r in pub["rows"]}
    agent, judge = OllamaProvider(model=H.AGENT_MODEL), OllamaProvider(model=H.JUDGE_MODEL)
    acfg = GenerationConfig(temperature=0.0, seed=42, max_tokens=140, enable_thinking=False,
                            n_ctx=4096, request_timeout_sec=300.0)
    jcfg = GenerationConfig(temperature=0.0, seed=17, max_tokens=6, enable_thinking=False,
                            n_ctx=4096, request_timeout_sec=300.0)
    model = H._retriever()
    recs = H._records(15, 30, 60, 17)
    tasks = gen_tasks([r for r, _ in recs], workers=workers)
    rng = random.Random(17)
    jobs = []
    for idx, (r, fam) in enumerate(recs):
        spec = H.EXTERNAL_TASK if fam == "external" else H.TASKS[fam]
        task = task_for(r.scenario_id, r.text, r.family, tasks) or spec["task"]
        sample = H.HARM_SAMPLES[idx % len(H.HARM_SAMPLES)]
        full = H._store_for(sample) + [(r.scenario_id, r.text)]
        rng.shuffle(full)
        cand = H._retrieve(model, task, full)
        if not any(m == r.scenario_id for m, _ in cand):
            cand = cand[:-1] + [(r.scenario_id, r.text)]
        p = pub_rows.get(r.scenario_id)
        if p is None or p["task"] != task:
            raise SystemExit(f"{r.scenario_id}: cannot reproduce the published instance/task")
        framed = [(m, neutralise(t) if m == r.scenario_id else t) for m, t in cand]
        jobs.append({"id": r.scenario_id, "family": fam, "task": task, "poison": r.text,
                     "question": spec["judge"], "raw": cand, "framed": framed,
                     "b13_excluded": bool(p["b13_excluded"])})
    print(f"{len(jobs)} instances reproduced", flush=True)
    done = json.loads(PARTIAL.read_text(encoding="utf-8")) if PARTIAL.exists() else {}

    def arm(j, a):
        k = f"{a}:{j['id']}"
        if k not in done:
            ans = H._answer(agent, acfg, j[a], j["task"])
            done[k] = {"ans": ans[:400], "harm": bool(H._judge(judge, jcfg, j["poison"],
                                                                j["question"], ans))}
        return done[k]["harm"]

    import concurrent.futures as cf

    vec = {"raw": [], "framed": []}
    for a in vec:
        for i in range(0, len(jobs), 24):
            with cf.ThreadPoolExecutor(max_workers=workers) as ex:
                vec[a] += list(ex.map(lambda j: arm(j, a), jobs[i:i + 24]))
            PARTIAL.write_text(json.dumps(done, ensure_ascii=False), encoding="utf-8")
            print(f"  {a} {len(vec[a])}/{len(jobs)}", flush=True)
    excl = [j["b13_excluded"] for j in jobs]
    b13 = [h and not x for h, x in zip(vec["raw"], excl)]
    b13f = [h and not x for h, x in zip(vec["framed"], excl)]
    out = {"frame": WINNER, "n": len(jobs),
           "note": "both arms run in this session; B13's exclusion is its published per-instance "
                   "decision. Agent and judge as harm_study_v2.",
           "harm_raw_rerun": rate_with_ci(sum(vec["raw"]), len(jobs)),
           "harm_framed": rate_with_ci(sum(vec["framed"]), len(jobs)),
           "paired_framed_vs_raw": paired_delta(vec["framed"], vec["raw"]),
           "harm_b13": rate_with_ci(sum(b13), len(jobs)),
           "harm_b13_plus_frame": rate_with_ci(sum(b13f), len(jobs)),
           "paired_b13frame_vs_b13": paired_delta(b13f, b13),
           "published_undefended": pub["overall"]["harm_no_defense"],
           "by_family": {}}
    for f in sorted({j["family"] for j in jobs}):
        ix = [i for i, j in enumerate(jobs) if j["family"] == f]
        out["by_family"][f] = {"n": len(ix), "raw": sum(vec["raw"][i] for i in ix),
                               "framed": sum(vec["framed"][i] for i in ix),
                               "b13": sum(b13[i] for i in ix), "b13_plus_frame": sum(b13f[i] for i in ix)}
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


if __name__ == "__main__":
    r = run()
    for k in ("harm_raw_rerun", "harm_framed", "harm_b13", "harm_b13_plus_frame"):
        print(f"  {k:22s} {r[k]['k']:3d}/{r[k]['n']} = {r[k]['rate']:.1%}")
    print("  framed vs raw", r["paired_framed_vs_raw"])
    print("  B13+frame vs B13", r["paired_b13frame_vs_b13"])
    print("DONE")
