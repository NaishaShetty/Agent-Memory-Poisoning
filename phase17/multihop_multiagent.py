"""Is the multi-hop ceiling a MODEL limit or a qwen limit? Test it across agent families.

WHY. This project declares multi-hop reasoning outside what the benchmark measures, on the
grounds that the ORACLE condition hands the agent exactly the gold evidence turns and it still
answers only 36/60 correctly -- so a defense can be neither credited nor blamed for the 24 it
fails with perfect evidence. That argument is only as good as its evidence base, and the base
was two agents (llama2 and qwen2.5:7b), both small and both from the same era. "A 7B model
cannot do this" and "our 7B model cannot do this" are different claims, and only the second was
measured.

So the oracle condition -- the ceiling condition, and the only one the scoping argument rests on
-- is re-run across every agent family available, reusing the EXISTING cases, prompt and
scoring ensemble so the numbers are comparable to the published ones rather than a new
experiment that happens to look better.

  qwen2.5:7b    the agent behind every harm number in this project
  llama2        the Phase 14 agent; already in the published comparison
  llama3.1:8b   a newer family
  mistral:7b    a third family
  phi3:mini     much smaller, as a floor
  gemini-*      a far more capable hosted model, IF GEMINI_API_KEY is set. This is the decisive
                arm: if a strong model clears the ceiling the scoping claim is confirmed as a
                capability limit, and if even it fails the limit is the task or the gold
                annotations, which would be a finding about LoCoMo rather than about any agent.

WHAT EACH OUTCOME MEANS, fixed before running so the result cannot be read to suit:
  * all local families cluster near 36/60 and Gemini is much higher -> the ceiling is model
    capability; the scoping stands, and the defended multi-hop figure stays uninterpretable at
    7B but would be interpretable on a stronger agent.
  * every family including Gemini sits near 36/60 -> the ceiling is NOT agent capability. The
    cases or their gold answers are the problem, the current scoping explanation is wrong, and
    the honest move is to say so and audit the cases.
  * local families differ widely among themselves -> "a 7B ceiling" is the wrong description
    and the figure is agent-specific, which also invalidates the current wording.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Dict, List

OUT = Path(__file__).parent / "data" / "multihop_multiagent.json"
PARTIAL = Path(__file__).parent / "data" / "multihop_multiagent_partial.json"
RESULTS = Path(__file__).parent / "data" / "multihop_results.json"
LOCAL_AGENTS = ("qwen2.5:7b", "llama2", "llama3.1:8b", "mistral:7b", "phi3:mini")
JUDGE = "qwen2.5:7b"          # the judge the published scoring used; kept for comparability


def _cases_with_oracle() -> List[dict]:
    """Reuse the published cases and their oracle memory sets, not new ones."""
    from phase17.multihop import _cases

    cases = _cases()
    return [{"q": c["q"], "gold": c["gold"],
             "oracle_mem": [c["store"][i] for i in c["evidence"]]} for c in cases]


def _ask(prov, cfg, q: str, mem) -> str:
    # The published prompt, verbatim, so the comparison is to the published numbers.
    p = ("Memories:\n" + "\n".join(f"- {m}" for m in mem)
         + f"\n\nQuestion: {q}\nAnswer briefly using only the memories.")
    try:
        return prov.generate([{"role": "user", "content": p}], cfg).text.strip()
    except Exception as exc:
        return f"__ERROR__ {type(exc).__name__}"


def run(workers: int = 3) -> dict:
    import concurrent.futures as cf

    from phase12.propagation.ollama_provider import OllamaProvider
    from phase17.stats import rate_with_ci
    from phase3.evaluation.agent.llm_judge_correctness import _build_judge_messages, _parse_verdict
    from phase3.evaluation.agent.nli_entailment_correctness import check_entailment_equivalence
    from phase3.evaluation.llm.provider import GenerationConfig

    cases = _cases_with_oracle()
    print(f"multi-hop ORACLE condition on {len(cases)} published cases", flush=True)
    acfg = GenerationConfig(temperature=0.0, seed=42, max_tokens=80, enable_thinking=False,
                            n_ctx=2048, request_timeout_sec=180.0)
    jcfg = GenerationConfig(temperature=0.0, seed=42, max_tokens=8, enable_thinking=False,
                            n_ctx=4096)

    agents: List[tuple] = [(m, lambda m=m: OllamaProvider(model=m)) for m in LOCAL_AGENTS]
    gem_key = os.environ.get("GEMINI_API_KEY")
    if gem_key:
        from phase17.gemini_provider import DEFAULT_MODEL, GeminiProvider

        agents.append((f"gemini ({DEFAULT_MODEL})", lambda: GeminiProvider()))
        print(f"  Gemini arm ENABLED ({DEFAULT_MODEL})", flush=True)
    else:
        print("  Gemini arm SKIPPED: GEMINI_API_KEY is not set in this environment. The decisive "
              "high-capability arm is therefore absent and the conclusion below is limited to "
              "local models.", flush=True)

    done = json.loads(PARTIAL.read_text(encoding="utf-8")) if PARTIAL.exists() else {}
    judge = OllamaProvider(model=JUDGE)
    out = {"n_cases": len(cases), "condition": "oracle (gold evidence turns supplied)",
           "prompt": "identical to phase17/multihop.py", "judge_model": JUDGE,
           "gemini_arm": bool(gem_key), "per_agent": {}}

    for name, make in agents:
        key_ans = [f"ans:{name}:{i}" for i in range(len(cases))]
        todo = [i for i, k in enumerate(key_ans) if k not in done]
        if todo:
            prov = make()
            # Hosted providers rate-limit; drive them sequentially.
            w = 1 if name.startswith("gemini") else workers
            with cf.ThreadPoolExecutor(max_workers=w) as ex:
                for n, (i, ans) in enumerate(zip(todo, ex.map(
                        lambda i: _ask(prov, acfg, cases[i]["q"], cases[i]["oracle_mem"]), todo)), 1):
                    done[key_ans[i]] = ans
                    if n % 10 == 0:
                        PARTIAL.write_text(json.dumps(done, ensure_ascii=False), encoding="utf-8")
                        print(f"  {name}: {n}/{len(todo)}", flush=True)
            PARTIAL.write_text(json.dumps(done, ensure_ascii=False), encoding="utf-8")

        answers = [done[k] for k in key_ans]
        jk = nk = both = err = 0
        for c, a in zip(cases, answers):
            if a.startswith("__ERROR__"):
                err += 1
                continue
            jv = bool(_parse_verdict(judge.generate(
                _build_judge_messages(c["q"], c["gold"], a), jcfg).text))
            nv = bool(check_entailment_equivalence(c["gold"], a, c["q"])["is_equivalent"])
            jk += jv
            nk += nv
            both += (jv and nv)
        n = len(cases) - err
        out["per_agent"][name] = {
            "n_scored": n, "n_errors": err,
            "judge": rate_with_ci(jk, n) if n else None,
            "nli": rate_with_ci(nk, n) if n else None,
            "strict_judge_and_nli": rate_with_ci(both, n) if n else None,
        }
        s = out["per_agent"][name]["strict_judge_and_nli"]
        print(f"  {name:24s} oracle strict {s['k']}/{s['n']} = {s['rate']:.1%}"
              + (f"  ({err} errors)" if err else ""), flush=True)

    rates = {k: v["strict_judge_and_nli"]["rate"] for k, v in out["per_agent"].items()
             if v["strict_judge_and_nli"]}
    local = {k: v for k, v in rates.items() if not k.startswith("gemini")}
    gem = {k: v for k, v in rates.items() if k.startswith("gemini")}
    spread = (max(local.values()) - min(local.values())) if local else 0.0
    out["analysis"] = {
        "local_rates": local, "gemini_rate": gem or None,
        "local_spread_points": round(100 * spread, 1),
        "verdict": (
            "NOT a general ceiling: the strong hosted model clears it, so the limit is agent "
            "capability and the scoping claim holds as stated for 7B agents"
            if gem and max(gem.values()) - max(local.values()) >= 0.15 else
            "NOT agent capability: every family tested, including the hosted model, sits in the "
            "same band, so the cases or their gold answers are the limiting factor and the "
            "current scoping explanation is wrong"
            if gem else
            "INCONCLUSIVE on capability: no high-capability arm was available (GEMINI_API_KEY "
            "unset), so this run can only show whether local families agree with each other"),
        "local_agreement_note": (
            "local families cluster within %.1f points, consistent with a shared capability "
            "limit rather than a qwen-specific one" % (100 * spread)
            if spread <= 0.15 else
            "local families differ by %.1f points, so 'a 7B ceiling' is the wrong description "
            "and the published figure is agent-specific" % (100 * spread)),
    }
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


if __name__ == "__main__":
    r = run()
    print("\n### Multi-hop ORACLE condition by agent (strict judge AND NLI)")
    for a, v in r["per_agent"].items():
        s = v["strict_judge_and_nli"]
        print(f"  {a:26s} {s['k']:3d}/{s['n']:<3d} = {s['rate']:6.1%}")
    print(f"\nlocal spread: {r['analysis']['local_spread_points']} points")
    print(f"VERDICT: {r['analysis']['verdict']}")
    print(f"NOTE: {r['analysis']['local_agreement_note']}")
    print("DONE")
