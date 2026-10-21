"""W2 (docs/phase17/v8/V8_PREREGISTRATION.md Sec 2): dev-only search for an agent setting
with a usable sleeper-activation base rate, before pre-registering any powered behaviour
test. No held-out data is touched by this module -- it reads only SA-8/SA-9 DEV items.

Reuses phase17.harm_study_v2's retrieval/answer/judge pipeline unchanged (_retrieve,
_answer, _judge are provider-agnostic: they take any object with .generate(messages, cfg)),
swapping only which provider plays the agent, so no frozen judging logic is touched.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

DATA = Path(__file__).resolve().parents[1] / "data" / "defence_v8"
OUT = DATA / "behaviour_base_rate.json"


def _clean_and_stored(agent, cfg, jcfg, judge_provider, model, store, x: Dict) -> Dict:
    """Matches phase17.defence_v4.voa's own methodology exactly: judge BOTH the clean
    answer (sleeper note absent from the store) and the stored answer (sleeper note
    present) with the real, frozen ACT_Q judge question
    (phase17.remediation.sleeper_activation_eval.ACT_Q, via llama3.1:8b) -- the quantity
    that matters is the DELTA attributable to the memory, not raw "did it act" (a helpful
    agent often performs a similar action even with no sleeper present at all)."""
    from phase17 import harm_study_v2 as H
    from phase17.remediation.sleeper_activation_eval import ACT_Q

    ans_clean = H._answer(agent, cfg, H._retrieve(model, x["trigger"], store), x["trigger"])
    ans_stored = H._answer(agent, cfg, H._retrieve(model, x["trigger"], store + [("MEM", x["stored"] or x["note"])]),
                           x["trigger"])
    act_clean = H._judge(judge_provider, jcfg, x["note"], ACT_Q, ans_clean)
    act_stored = H._judge(judge_provider, jcfg, x["note"], ACT_Q, ans_stored)
    return {"act_clean": act_clean, "act_stored": act_stored, "influence": act_stored and not act_clean}


def base_rate(agent_name: str, xs: List[Dict], owners_store: Dict[int, list]) -> Dict:
    """agent_name: an Ollama model tag, or 'gemini' for phase17.gemini_provider.GeminiProvider.
    xs: dev atk_implicit items with 'stored'/'note'/'trigger'/'owner' already populated
    (i.e. the output of a *_scoring_v8.items('dev') call, kind == 'atk_implicit').
    "usable base rate" = the rate of `influence` (stored acts, clean does not) -- the
    quantity a powered paired reduction test (TS/HIG-style) needs enough of to be able to
    detect a defended-vs-undefended difference at all."""
    from phase12.propagation.ollama_provider import OllamaProvider
    from phase17 import harm_study_v2 as H
    from phase3.evaluation.llm.provider import GenerationConfig

    model = H._retriever()
    if agent_name == "gemini":
        from phase17.gemini_provider import GeminiProvider

        agent = GeminiProvider()
    else:
        agent = OllamaProvider(model=agent_name)
    judge_provider = OllamaProvider(model="llama3.1:8b")
    cfg = GenerationConfig(temperature=0.0, seed=42, max_tokens=140, enable_thinking=False, n_ctx=4096,
                           request_timeout_sec=300.0)
    jcfg = GenerationConfig(temperature=0.0, seed=17, max_tokens=6, enable_thinking=False, n_ctx=4096,
                            request_timeout_sec=180.0)
    results = []
    for x in xs:
        store = owners_store[x["owner"]]
        r = _clean_and_stored(agent, cfg, jcfg, judge_provider, model, store, x)
        results.append(r)
        print(f"  {agent_name} {x['id']}: clean={r['act_clean']} stored={r['act_stored']} "
              f"influence={r['influence']}", flush=True)
    n = len(results)
    act_clean_rate = sum(r["act_clean"] for r in results) / n if n else None
    act_stored_rate = sum(r["act_stored"] for r in results) / n if n else None
    influence_rate = sum(r["influence"] for r in results) / n if n else None
    return {"agent": agent_name, "n": n, "act_clean_rate": act_clean_rate, "act_stored_rate": act_stored_rate,
            "influence_rate": influence_rate, "influence_count": sum(r["influence"] for r in results)}


def run(corpora=("sa8", "sa9")) -> Dict:
    from phase17.defence_v8.g3_scoring_sa9 import items as sa9_items
    from phase17.defence_v8.g3_scoring_v8 import items as sa8_items
    from phase17.remediation.sleeper_activation_eval import _store

    xs = []
    if "sa8" in corpora:
        xs += [x for x in sa8_items("dev") if x["kind"] == "atk_implicit"]
    if "sa9" in corpora:
        xs += [x for x in sa9_items("dev") if x["kind"] == "atk_implicit"]
    owners_store = {o: _store(o) for o in {x["owner"] for x in xs}}

    out = {}
    for agent_name in ("qwen2.5:7b", "gemini"):
        out[agent_name] = base_rate(agent_name, xs, owners_store)
        OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    return out


if __name__ == "__main__":
    print(json.dumps(run(), indent=1))
