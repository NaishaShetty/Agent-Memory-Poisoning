"""Measurement-correctness check: the harm study asked the AgentPoison family its task WITHOUT the
backdoor trigger in the question, so the backdoor was measured outside its own firing condition (the
same error the project already caught in agentpoison_published_check.py: "a backdoor not fired by its
own trigger tells you nothing"). This reruns the SAME published poison through the SAME harm pipeline,
changing one thing -- the trigger phrase is present in the question -- and reports harm both ways.

Nothing about the attack is changed or strengthened: the poison text, the agent, the retriever, the
surrounding store, the top-k and the harm judge are exactly harm_study_v2's. The trigger is not
invented here either -- each poison text already begins with its own trigger, and this reads it back
off the text (the span before the first colon). Two arms:

  control    the task exactly as the published study asked it (reproduces the 0/n result)
  triggered  the same task with that instance's own trigger phrase appended to the question

Both are reported. If triggered > control, the published number measured the backdoor switched off;
if triggered is still ~0, the attack is inert end to end and that is a finding, not a gap.

Development data. Agent and judge as harm_study_v2.
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import random
import re
from pathlib import Path

DATA = Path(__file__).parent / "data"
OUT = DATA / "agentpoison_trigger_check.json"
PARTIAL = DATA / "agentpoison_trigger_check_partial.json"


def _trigger(poison_text: str) -> str:
    """The instance's own trigger: the span before the first colon, minus a leading 'Regarding'
    and any surrounding quotes. Read off the poison, never introduced here."""
    head = poison_text.split(":", 1)[0]
    head = re.sub(r"^\s*regarding\s+", "", head, flags=re.I).strip().strip('"').strip("'")
    return head


def run(workers: int = 4) -> dict:
    from phase12.propagation.ollama_provider import OllamaProvider
    from phase17 import harm_study_v2 as H
    from phase17.stats import paired_delta, rate_with_ci
    from phase3.evaluation.llm.provider import GenerationConfig

    agent = OllamaProvider(model=H.AGENT_MODEL)
    judge = OllamaProvider(model=H.JUDGE_MODEL)
    acfg = GenerationConfig(temperature=0.0, seed=42, max_tokens=140, enable_thinking=False,
                            n_ctx=4096, request_timeout_sec=300.0)
    jcfg = GenerationConfig(temperature=0.0, seed=17, max_tokens=6, enable_thinking=False,
                            n_ctx=4096, request_timeout_sec=300.0)
    model = H._retriever()

    # Reconstruct the AgentPoison instances exactly as the published harm study built them.
    recs = H._records(15, 30, 60, 17)
    rng = random.Random(17)
    jobs = []
    for idx, (r, fam) in enumerate(recs):
        spec = H.EXTERNAL_TASK if fam == "external" else H.TASKS[fam]
        base_task = spec["task"]
        sample = H.HARM_SAMPLES[idx % len(H.HARM_SAMPLES)]
        full = H._store_for(sample) + [(r.scenario_id, r.text)]
        rng.shuffle(full)
        if fam != "agentpoison":
            continue
        trig = _trigger(r.text)
        tasks = {"control": base_task, "triggered": f"{base_task} {trig}"}
        cands = {}
        for arm, task in tasks.items():
            cand = H._retrieve(model, task, full)
            if not any(m == r.scenario_id for m, _ in cand):
                cand = cand[:-1] + [(r.scenario_id, r.text)]
            cands[arm] = cand
        jobs.append({"id": r.scenario_id, "poison": r.text, "trigger": trig,
                     "question": spec["judge"], "tasks": tasks, "cands": cands,
                     "retrieved_control": any(m == r.scenario_id for m, _ in cands["control"]),
                     "retrieved_triggered": any(m == r.scenario_id for m, _ in cands["triggered"])})
    print(f"{len(jobs)} AgentPoison instances", flush=True)

    done = json.loads(PARTIAL.read_text(encoding="utf-8")) if PARTIAL.exists() else {}

    def arm(job, which):
        k = f"{which}:{job['id']}"
        if k not in done:
            ans = H._answer(agent, acfg, job["cands"][which], job["tasks"][which])
            done[k] = {"ans": ans, "harm": bool(H._judge(judge, jcfg, job["poison"], job["question"], ans))}
        return done[k]["harm"]

    vec = {"control": [], "triggered": []}
    for which in vec:
        for i in range(0, len(jobs), 12):
            with cf.ThreadPoolExecutor(max_workers=workers) as ex:
                vec[which] += list(ex.map(lambda j: arm(j, which), jobs[i:i + 12]))
            PARTIAL.write_text(json.dumps(done, ensure_ascii=False), encoding="utf-8")
            print(f"  {which} {len(vec[which])}/{len(jobs)}", flush=True)

    n = len(jobs)
    out = {
        "family": "agentpoison", "n": n, "agent": H.AGENT_MODEL, "judge": H.JUDGE_MODEL,
        "note": "same poison, store, retriever, top-k and harm judge as harm_study_v2; the only "
                "change is that the triggered arm's question carries the instance's own trigger phrase.",
        "retrieved_with_poison": {"control": sum(j["retrieved_control"] for j in jobs),
                                  "triggered": sum(j["retrieved_triggered"] for j in jobs)},
        "harm": {"control": rate_with_ci(sum(vec["control"]), n),
                 "triggered": rate_with_ci(sum(vec["triggered"]), n),
                 "paired_triggered_vs_control": paired_delta(vec["triggered"], vec["control"])},
        "per_instance": [{"id": j["id"], "trigger": j["trigger"],
                          "control": vec["control"][i], "triggered": vec["triggered"][i]}
                         for i, j in enumerate(jobs)],
    }
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


if __name__ == "__main__":
    r = run()
    h = r["harm"]
    print(f"retrieved with poison: control {r['retrieved_with_poison']['control']}/{r['n']}, "
          f"triggered {r['retrieved_with_poison']['triggered']}/{r['n']}")
    print(f"harm: control {h['control']['k']}/{r['n']} ({h['control']['rate']:.1%}), "
          f"triggered {h['triggered']['k']}/{r['n']} ({h['triggered']['rate']:.1%}), "
          f"p={h['paired_triggered_vs_control']['p_exact']:.2g}")
    print("DONE")
