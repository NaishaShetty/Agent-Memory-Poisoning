"""Score `multihop_results.json`: strict semantic ensemble (LLM judge AND NLI) plus a permissive substring
check, per condition x agent, with evidence recall. Reports Wilson intervals."""
import json
import re
from pathlib import Path

from phase12.propagation.ollama_provider import OllamaProvider
from phase3.evaluation.agent.llm_judge_correctness import _build_judge_messages, _parse_verdict
from phase3.evaluation.agent.nli_entailment_correctness import check_entailment_equivalence
from phase3.evaluation.llm.provider import GenerationConfig
from phase17.stats import rate_with_ci

D = Path(__file__).parent / "data"


def main():
    rows = json.loads((D / "multihop_results.json").read_text(encoding="utf-8"))["rows"]
    judge = OllamaProvider(model="qwen2.5:7b")
    cfg = GenerationConfig(temperature=0.0, seed=42, max_tokens=8, enable_thinking=False, n_ctx=4096)
    norm = lambda s: re.sub(r"[^a-z0-9 ]", " ", s.lower())
    res = {}
    for cond in ("single_shot", "decomposed", "oracle"):
        for agent in ("llama2", "qwen"):
            j = n = sub = 0
            both = 0
            for r in rows:
                ans, gold, q = r["conds"][cond][agent], r["gold"], r["q"]
                jv = bool(_parse_verdict(judge.generate(_build_judge_messages(q, gold, ans), cfg).text))
                nv = bool(check_entailment_equivalence(gold, ans, q)["is_equivalent"])
                j += jv; n += nv; both += (jv and nv)
                sub += all(w in norm(ans) for w in norm(gold).split() if len(w) > 3)
            k = len(rows)
            res[f"{cond}|{agent}"] = {"judge": rate_with_ci(j, k), "nli": rate_with_ci(n, k), "strict_judge_and_nli": rate_with_ci(both, k),
                                      "gold_words_all_present": rate_with_ci(sub, k)}
            print(cond, agent, {m: f"{v['k']}/{v['n']}" for m, v in res[f'{cond}|{agent}'].items()}, flush=True)
    for cond in ("single_shot", "decomposed", "oracle"):
        res[f"evidence_recall|{cond}"] = sum(r["conds"][cond]["evidence_recall"] for r in rows) / len(rows)
    (D / "multihop_scored.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print("DONE", {k: round(v, 3) for k, v in res.items() if k.startswith("evidence")})


if __name__ == "__main__":
    main()
