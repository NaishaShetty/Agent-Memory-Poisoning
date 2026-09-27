"""Phase 17 fix round 4 -- an LLM-PROXY blinded rating of the human-eval packet, using
Gemini (a model never otherwise used as a judge in this project) as a stand-in rater.

THIS IS NOT A SUBSTITUTE FOR HUMAN EVALUATION -- it is disclosed, everywhere it is
reported, as an LLM proxy, never as "human data." It exists because no human rater was
available during this automated session, and it gives a genuinely independent (different
model family, blinded to the automated verdicts) opinion on the SAME 60-item packet a
real human will eventually rate, so a comparison point exists in the meantime.
"""

from __future__ import annotations

import json
from pathlib import Path

DATA = Path(__file__).parent / "data"
CATEGORIES = ("correct", "incorrect", "paraphrase", "partial", "abstains", "ambiguous")

PROMPT = (
    "You are rating whether an AI assistant's answer correctly addresses a question, given the intended gold answer. "
    "Allow paraphrase/synonyms; do not require exact wording. Categories: correct (fully right), paraphrase (right, very "
    "differently worded), partial (right idea, missing part of a multi-part answer), incorrect (wrong or contradicts the "
    "gold answer), abstains (refuses or says it doesn't know), ambiguous (genuinely unclear).\n\n"
    "Question: {question}\nGold answer: {gold}\nAssistant's answer: {answer}\n\n"
    "Respond with exactly one word from: correct, paraphrase, partial, incorrect, abstains, ambiguous."
)


def run() -> dict:
    from phase17.gemini_provider import GeminiProvider
    from phase3.evaluation.llm.provider import GenerationConfig

    packet = json.loads((DATA / "human_eval_packet_blind.json").read_text(encoding="utf-8"))
    key = json.loads((DATA / "human_eval_packet_key.json").read_text(encoding="utf-8"))
    gemini = GeminiProvider()
    if not gemini.health_check():
        return {"error": "GEMINI_API_KEY not set or unreachable this session -- re-run with the key exported."}
    cfg = GenerationConfig(temperature=0.0, seed=17, max_tokens=8, enable_thinking=False, n_ctx=2048, request_timeout_sec=60.0)

    ratings = []
    for item in packet:
        prompt = PROMPT.format(question=item["question"], gold=item["gold_answer"], answer=item["model_answer"] or "(no answer)")
        try:
            r = gemini.generate([{"role": "user", "content": prompt}], cfg)
            label = r.text.strip().lower()
            label = next((c for c in CATEGORIES if c in label), "ambiguous")
        except Exception as exc:
            label = f"ERROR:{type(exc).__name__}"
        ratings.append({"item_id": item["item_id"], "gemini_label": label})

    # compare against the automated verdicts already in the key
    agree_judge = agree_string = n_defined = 0
    for r in ratings:
        k = key[str(r["item_id"])] if str(r["item_id"]) in key else key.get(r["item_id"])
        if k is None or r["gemini_label"].startswith("ERROR"):
            continue
        n_defined += 1
        gemini_correct = r["gemini_label"] in ("correct", "paraphrase")
        agree_judge += (gemini_correct == bool(k["llm_judge"]))
        agree_string += (gemini_correct == bool(k["string_date"]))

    out = {"n_items": len(ratings), "n_defined": n_defined, "ratings": ratings,
           "agreement_with_qwen_judge": agree_judge / n_defined if n_defined else None,
           "agreement_with_string_metric": agree_string / n_defined if n_defined else None,
           "label_distribution": {c: sum(1 for r in ratings if r["gemini_label"] == c) for c in CATEGORIES},
           "disclosure": "LLM PROXY rating (Gemini), NOT a human rating. Real human evaluation of this SAME packet "
                        "is still open (see HUMAN_EVAL_INSTRUCTIONS.md)."}
    (DATA / "llm_proxy_human_eval_results.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


if __name__ == "__main__":
    r = run()
    print(json.dumps({k: v for k, v in r.items() if k != "ratings"}, indent=1))
    print("DONE")
