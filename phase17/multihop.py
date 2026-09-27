"""Phase 17 -- 'multi-hop reasoning weakness': separate RETRIEVAL failure from REASONING failure and test
a fix for the retrieval half.

Cases: real LoCoMo category-1 (multi-hop) questions with >= 2 evidence turns. The memory store for a case is
ALL turns of that conversation's evidence sessions' neighbourhood (evidence turns + 12 same-conversation
distractor turns). Conditions (same answer prompt everywhere):
  single_shot   : top-4 turns by embedding similarity to the question;
  decomposed    : qwen2.5:7b splits the question into sub-questions; top-2 turns per sub-question, de-duplicated;
  oracle        : exactly the gold evidence turns (reasoning-only ceiling).
Agents: llama2 (the Phase 14 agent) and qwen2.5:7b. Scoring: string-normalized OR (LLM judge AND NLI) -- the strict
semantic ensemble from `phase17/utility_repeats.py` analysis -- reported separately with Wilson intervals.
Evidence-recall (fraction of gold turns retrieved) is reported per condition: it is the retrieval half."""

from __future__ import annotations

import json
import random
import re
from pathlib import Path

import numpy as np

OUT = Path(__file__).parent / "data" / "multihop_results.json"
LOCOMO = Path("data/raw/locomo/locomo10.json")
N_CASES = 60


def _cases(seed=17):
    raw = json.loads(LOCOMO.read_text(encoding="utf-8"))
    rng, cases = random.Random(seed), []
    for ci, c in enumerate(raw):
        turns = {}
        for k, v in c["conversation"].items():
            if k.startswith("session_") and isinstance(v, list):
                for t in v:
                    turns[t["dia_id"]] = f'{t["speaker"]}: {t["text"]}'
        for q in c["qa"]:
            ev = [e for e in q.get("evidence", []) if e in turns]
            if q["category"] == 1 and len(ev) >= 2 and q.get("answer"):
                others = [d for d in turns if d not in ev]
                rng.shuffle(others)
                cases.append({"cid": ci, "q": q["question"], "gold": str(q["answer"]), "evidence": ev,
                              "store": {d: turns[d] for d in ev + others[:12]}})
    rng.shuffle(cases)
    return cases[:N_CASES]


def main():
    from phase12.propagation.ollama_provider import OllamaProvider
    from phase17.semantic_detector import _embed
    from phase3.evaluation.llm.provider import GenerationConfig
    from phase17.stats import rate_with_ci

    cfg = GenerationConfig(temperature=0.0, seed=42, max_tokens=80, enable_thinking=False, n_ctx=2048, request_timeout_sec=180.0)
    qwen, llama = OllamaProvider(model="qwen2.5:7b"), OllamaProvider(model="llama2")
    ask = lambda prov, q, mem: prov.generate([{"role": "user", "content": "Memories:\n" + "\n".join(f"- {m}" for m in mem) +
                                               f"\n\nQuestion: {q}\nAnswer briefly using only the memories."}], cfg).text.strip()
    cases = _cases()
    rows = []
    for c in cases:
        ids = list(c["store"]); vec = _embed([c["store"][i] for i in ids])
        top = lambda text, k: [ids[j] for j in np.argsort(-(vec @ _embed([text])[0]))[:k]]
        single = top(c["q"], 4)
        subs = qwen.generate([{"role": "user", "content": f"Split this question into 2-3 short factual sub-questions, one per line, no numbering:\n{c['q']}"}], cfg).text.strip().split("\n")
        subs = [re.sub(r"^[\-\d\.\)\s]+", "", s).strip() for s in subs if s.strip()][:3] or [c["q"]]
        dec = list(dict.fromkeys(i for s in subs for i in top(s, 2)))
        conds = {"single_shot": single, "decomposed": dec, "oracle": c["evidence"]}
        row = {"q": c["q"], "gold": c["gold"], "subs": subs, "conds": {}}
        for name, sel in conds.items():
            row["conds"][name] = {"evidence_recall": len(set(sel) & set(c["evidence"])) / len(c["evidence"]), "n_mem": len(sel)}
            for an, prov in (("llama2", llama), ("qwen", qwen)):
                row["conds"][name][an] = ask(prov, c["q"], [c["store"][i] for i in sel])
        rows.append(row)
        OUT.write_text(json.dumps({"rows": rows}, indent=1), encoding="utf-8")
        print(len(rows), flush=True)
    print("DONE")


if __name__ == "__main__":
    main()
