"""Targeted phase, U2 (pre-registration section 5, secondary): legitimate task completion when the policies remove
benign derived memories. Up to 150 LoCoMo QA items (seed 2026) whose linked observations are excluded by at least one
of A-ship, A-nom or B (correct-owner evidence, LOO thresholds). Store = the item's linked observations + 7 other
observations of the same owner (seed 2026), minus what each policy excludes; under B, deferred memories stay in the
store marked "(unverified)". Agent qwen2.5:7b (temperature 0, seed 42); judge llama3.1:8b against the gold answer
(b13_utility_strong_agent's prompt). Policies: none, A-ship, A-nom, B.
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import random
from pathlib import Path
from typing import Dict

DATA = Path(__file__).resolve().parents[1] / "data"
OUT = DATA / "remediation" / "b13_loo_utility.json"
PARTIAL = DATA / "remediation" / "b13_loo_utility_partial.json"
CAP = 150
POLICIES = ("none", "A-ship", "A-nom", "B")


def _items():
    from phase17.provenance_sets import _raw, observations

    loo = json.loads((DATA / "remediation" / "b13_owner_loo.json").read_text(encoding="utf-8"))
    dec = loo["benign_item_decisions_correct"]
    cands = []
    for o in range(10):
        obs = observations(o)
        d = dec[str(o)]
        by_dia: Dict[str, set] = {}
        for i, x in enumerate(obs):
            for dd in (x["evidence"] if isinstance(x["evidence"], list) else [x["evidence"]]):
                for e in str(dd).replace(",", ";").split(";"):
                    by_dia.setdefault(e.strip(), set()).add(i)
        for qi, qa in enumerate(_raw()[o]["qa"]):
            if qa.get("category") not in (1, 2, 3, 4):
                continue
            linked = sorted(set().union(*[by_dia.get(str(e).strip(), set()) for e in qa.get("evidence", [])]))
            if linked and any(d[p][i] for p in ("A-ship", "A-nom", "B") for i in linked):
                cands.append((o, qi, linked))
    rng = random.Random(2026)
    sample = rng.sample(cands, min(CAP, len(cands)))
    return cands, sample, dec


def run(workers: int = 2) -> Dict:
    from phase12.propagation.ollama_provider import OllamaProvider
    from phase17.attack_validity_audit import AGENT_MODEL, _answer
    from phase17.b13_utility_strong_agent import _judge_prompt
    from phase17.provenance_sets import _raw, observations
    from phase17.stats import paired_delta, rate_with_ci
    from phase3.evaluation.llm.provider import GenerationConfig

    cands, sample, dec = _items()
    done = json.loads(PARTIAL.read_text(encoding="utf-8")) if PARTIAL.exists() else {}
    acfg = GenerationConfig(temperature=0.0, seed=42, max_tokens=160, enable_thinking=False, n_ctx=4096,
                            request_timeout_sec=300.0)
    jcfg = GenerationConfig(temperature=0.0, seed=17, max_tokens=6, enable_thinking=False, n_ctx=4096,
                            request_timeout_sec=300.0)
    jobs = []
    for o, qi, linked in sample:
        obs = observations(o)
        others = [i for i in range(len(obs)) if i not in linked]
        store_ix = linked + random.Random(f"2026-{o}-{qi}").sample(others, min(7, len(others)))
        qa = _raw()[o]["qa"][qi]
        for pol in POLICIES:
            mem = []
            for i in store_ix:
                if pol != "none" and dec[str(o)][pol][i]:
                    continue
                t = obs[i]["text"]
                if pol == "B" and dec[str(o)]["B_deferred"][i]:
                    t = f"(unverified) {t}"
                mem.append((f"O{i}", t))
            jobs.append({"key": f"{o}:{qi}:{pol}", "mem": mem, "q": qa["question"], "gold": str(qa["answer"]),
                         "linked_kept": sum(1 for i in linked if pol == "none" or not dec[str(o)][pol][i]),
                         "n_linked": len(linked)})
    agent = OllamaProvider(model=AGENT_MODEL)

    def ans(j):
        if f"ans:{j['key']}" not in done:
            done[f"ans:{j['key']}"] = _answer(agent, acfg, j["mem"], j["q"])
    for i in range(0, len(jobs), 16):
        with cf.ThreadPoolExecutor(max_workers=workers) as ex:
            list(ex.map(ans, jobs[i:i + 16]))
        PARTIAL.write_text(json.dumps(done, ensure_ascii=False), encoding="utf-8")
    print("  answers done", flush=True)
    judge = OllamaProvider(model="llama3.1:8b")

    def jd(j):
        if f"j:{j['key']}" not in done:
            done[f"j:{j['key']}"] = judge.generate([{"role": "user", "content": _judge_prompt(
                j["q"], j["gold"], done[f"ans:{j['key']}"])}], jcfg).text.strip().upper().startswith("YES")
    for i in range(0, len(jobs), 16):
        with cf.ThreadPoolExecutor(max_workers=workers) as ex:
            list(ex.map(jd, jobs[i:i + 16]))
        PARTIAL.write_text(json.dumps(done, ensure_ascii=False), encoding="utf-8")
    keys = [f"{o}:{qi}" for o, qi, _ in sample]
    corr = {p: [bool(done[f"j:{k}:{p}"]) for k in keys] for p in POLICIES}
    jl = {j["key"]: j for j in jobs}
    out = {"preregistration": "docs/phase17/PREREGISTRATION_TARGETED_2026-10-13.md section 5 (U2, secondary)",
           "n_candidates": len(cands), "n_sampled": len(sample),
           "scope": "QA items AFFECTED by at least one policy -- not a population utility rate",
           "by_policy": {p: {"correct": rate_with_ci(sum(corr[p]), len(keys)),
                             "all_linked_removed": sum(jl[f"{k}:{p}"]["linked_kept"] == 0 for k in keys)} for p in POLICIES},
           "paired_vs_none": {p: paired_delta(corr[p], corr["none"]) for p in POLICIES if p != "none"},
           "paired_B_vs_A_ship": paired_delta(corr["B"], corr["A-ship"])}
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    r = run()
    print(json.dumps(r["by_policy"], indent=1))
    print(json.dumps(r["paired_vs_none"], indent=1))
